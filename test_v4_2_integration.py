"""Phase 6 item 11: end-to-end integration tests for the V4.2 default
stack.

These tests exercise the orchestrator with REAL security.py instances
(v4_2_framing_daily, DailyCircuitBreaker) and a REAL SQLite cache
file. Only the innermost LLM call (detect_framing_v4_2) is mocked. The
goal is to catch integration regressions that unit-level tests with
mocked caps cannot surface:

  - Does the per-IP cap tracked by real DailyFeatureLimit correctly
    cap the 21st request?
  - Does the real SQLite cache actually persist across calls (not just
    respond to in-memory mocks)?
  - Do the counters increment on the decision-flow paths that real
    security.py gates drive?
  - Does cache hit truly skip the IP cap charge under real state?

Complementary to test_framing_sdk.py (fine-grained decision flow with
mocked gates), test_profile_v4_2_wiring.py (template-rendering after
/profile POST), and test_v4_2_observability.py (counter shape).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "fvs_eval" / "v4"))

import framing_sdk as sdk  # noqa: E402
import security  # noqa: E402
import v4_2_engine as engine  # noqa: E402


@pytest.fixture(autouse=True)
def _integration_isolation(monkeypatch, tmp_path):
    """Reset all shared state between tests. The real caps and circuit
    breaker live in security.py as module singletons; wiping their
    internal _usage dicts between tests prevents bleed-through."""
    monkeypatch.setattr(sdk, "_CACHE_DB_PATH", tmp_path / "integration_cache.sqlite")
    monkeypatch.setattr(sdk, "_cache_initialized", False)
    monkeypatch.setenv("XAI_API_KEY", "integration-test-key")

    # Reset counters and breakers.
    sdk._COUNTERS.reset()
    engine._LLM_BREAKER.reset()

    # Reset per-IP caps used by the integration tests.
    with security.v4_2_framing_daily._lock:
        security.v4_2_framing_daily._usage.clear()

    yield

    sdk._COUNTERS.reset()
    engine._LLM_BREAKER.reset()
    with security.v4_2_framing_daily._lock:
        security.v4_2_framing_daily._usage.clear()


def _unique_doc_for_test() -> str:
    """Each test gets a document content unique enough to avoid any
    cross-test cache hits in the unlikely event of a stale tmp path."""
    return f"Integration test document {uuid.uuid4().hex}. " * 4


def _fake_engine_success() -> dict:
    return {
        "entries": [
            {
                "fvs_id": f"FVS-{i:03d}",
                "exhibits": i == 8,
                "reasoning": "integration test reasoning",
                "reliability": {
                    "source": "llm_v4_2",
                    "library_version": "library_v4",
                    "library_hash": "integrationtesthash",
                    "library_consensus_ac1": 0.785,
                    "detector_intra_rater_ac1": 0.945,
                    "detector_intra_rater_null_reason": None,
                    "reliability_tier": "strong",
                },
                "honest_limit": None,
            }
            for i in range(1, 20)
        ],
        "meta": {
            "engine_version": "4.2.0",
            "framing_engine": "v4_2",
            "cost_estimate_usd": 0.006,
            "tokens": {"input": 10000, "output": 500},
            "model_served": "grok-4-1-fast-non-reasoning",
            "library_hash": "integrationtesthash",
            "library_version": "library_v4",
            "fvs_020_status": "excluded",
            "stop_reason": "stop",
            "reliability_note": "integration",
            "validation": {
                "frames_returned_valid_dict": 19,
                "frames_returned_bool_only": 0,
                "frames_missing_or_invalid": 0,
                "total_frames_emitted": 19,
                "warnings": [],
            },
        },
    }


# ── Cache + rate-limit interaction ───────────────────────────────────

def test_cache_hit_does_not_consume_real_ip_cap():
    """Integration property: after priming the cache on a document, a
    second identical call must hit cache and must NOT consume a slot
    from the real DailyFeatureLimit. This is the cost-efficiency
    invariant that makes 20 calls/day per IP generous: legit users
    re-reading a saved doc don't burn slots."""
    doc = _unique_doc_for_test()
    ip = "203.0.113.42"

    # First call: real cap + fresh cache
    with patch.object(sdk, "detect_framing_v4_2",
                      return_value=_fake_engine_success()):
        result1 = sdk.detect_framing_orchestrated(
            doc, ip=ip, ip_cap=security.v4_2_framing_daily,
        )
    assert result1["meta"]["framing_engine"] == "v4_2"
    assert result1["meta"]["cache_hit"] is False
    # One slot consumed
    remaining_after_first = security.v4_2_framing_daily.remaining(ip)

    # Second call: cache hit; engine must NOT be called
    def should_not_be_called(*args, **kwargs):
        raise AssertionError("engine called on cache hit")
    with patch.object(sdk, "detect_framing_v4_2",
                      side_effect=should_not_be_called):
        result2 = sdk.detect_framing_orchestrated(
            doc, ip=ip, ip_cap=security.v4_2_framing_daily,
        )
    assert result2["meta"]["cache_hit"] is True
    # Zero additional slots consumed
    remaining_after_second = security.v4_2_framing_daily.remaining(ip)
    assert remaining_after_second == remaining_after_first


def test_ip_cap_exhaustion_causes_fallback_with_real_daily_feature_limit():
    """Fill the real v4_2_framing_daily cap (20 calls default) with
    unique documents; the 21st call must fallback with
    budget_exhausted_ip, not hit the engine, not raise."""
    ip = "198.51.100.7"
    cap = security.v4_2_framing_daily.max_per_day

    # Consume the cap with unique-content calls (so cache never hits)
    with patch.object(sdk, "detect_framing_v4_2",
                      return_value=_fake_engine_success()):
        for i in range(cap):
            doc = f"Distinct document {i} {uuid.uuid4().hex}. " * 3
            result = sdk.detect_framing_orchestrated(
                doc, ip=ip, ip_cap=security.v4_2_framing_daily,
            )
            assert result["meta"]["framing_engine"] == "v4_2"
    assert security.v4_2_framing_daily.remaining(ip) == 0

    # Next unique call must fallback; engine must NOT be called
    def should_not_be_called(*args, **kwargs):
        raise AssertionError(
            "engine called after real cap exhausted; fallback must fire"
        )
    with patch.object(sdk, "detect_framing_v4_2",
                      side_effect=should_not_be_called):
        result = sdk.detect_framing_orchestrated(
            f"Yet another doc {uuid.uuid4().hex}. " * 3,
            ip=ip, ip_cap=security.v4_2_framing_daily,
        )
    assert result["meta"]["framing_engine"] == "layer_a"
    assert result["meta"]["fallback_reason"] == "budget_exhausted_ip"


def test_different_ips_have_independent_caps():
    """Per-IP cap is per-IP. IP A exhausting its cap must not affect
    IP B. This is the bedrock of per-IP rate limiting; regressions here
    would mean one attacker draining the budget for everyone."""
    cap = security.v4_2_framing_daily.max_per_day
    ip_a, ip_b = "192.0.2.1", "192.0.2.2"

    with patch.object(sdk, "detect_framing_v4_2",
                      return_value=_fake_engine_success()):
        # Exhaust IP A
        for i in range(cap):
            sdk.detect_framing_orchestrated(
                f"IP-A doc {i} {uuid.uuid4().hex}. " * 3,
                ip=ip_a, ip_cap=security.v4_2_framing_daily,
            )
        assert security.v4_2_framing_daily.remaining(ip_a) == 0
        # IP B is unaffected
        assert security.v4_2_framing_daily.remaining(ip_b) == cap

        # IP B can still successfully call
        result = sdk.detect_framing_orchestrated(
            f"IP-B doc {uuid.uuid4().hex}. " * 3,
            ip=ip_b, ip_cap=security.v4_2_framing_daily,
        )
    assert result["meta"]["framing_engine"] == "v4_2"
    assert security.v4_2_framing_daily.remaining(ip_b) == cap - 1


# ── Counter + real stack ────────────────────────────────────────────

def test_counters_reflect_full_stack_activity():
    """The observability counters (_COUNTERS) must increment during
    real-stack orchestrator runs, not just mocked-cap tests. This
    catches any regression where a future refactor wires counters in
    a code path that bypasses the real rate limiter."""
    ip = "192.0.2.99"
    doc_prefix = uuid.uuid4().hex

    with patch.object(sdk, "detect_framing_v4_2",
                      return_value=_fake_engine_success()):
        # 5 unique calls → 5 successes, 0 cache hits
        for i in range(5):
            sdk.detect_framing_orchestrated(
                f"{doc_prefix}-counter-{i}-content. " * 3,
                ip=ip, ip_cap=security.v4_2_framing_daily,
            )
        # Repeat the first doc → 1 cache hit
        sdk.detect_framing_orchestrated(
            f"{doc_prefix}-counter-0-content. " * 3,
            ip=ip, ip_cap=security.v4_2_framing_daily,
        )

    snap = sdk.counters_snapshot()
    assert snap["v4_2_success"] == 5
    assert snap["cache_hits"] == 1
    assert snap["cache_misses"] == 5
    assert snap["total_requests"] == 6
    assert snap["v4_2_fallback_total"] == 0
    assert snap["v4_2_blocked_total"] == 0


def test_counters_record_real_budget_exhaustion():
    """After real budget exhaustion the budget_exhausted_ip fallback
    counter increments; observability tracks a real-world condition,
    not just a mocked one."""
    cap = security.v4_2_framing_daily.max_per_day
    ip = "192.0.2.55"

    with patch.object(sdk, "detect_framing_v4_2",
                      return_value=_fake_engine_success()):
        # Exhaust
        for i in range(cap):
            sdk.detect_framing_orchestrated(
                f"exhaust-{i}-{uuid.uuid4().hex}. " * 3,
                ip=ip, ip_cap=security.v4_2_framing_daily,
            )
        # Trigger one fallback
        sdk.detect_framing_orchestrated(
            f"fallback-trigger-{uuid.uuid4().hex}. " * 3,
            ip=ip, ip_cap=security.v4_2_framing_daily,
        )

    snap = sdk.counters_snapshot()
    assert snap["v4_2_fallback_by_reason"] == {"budget_exhausted_ip": 1}


# ── Cache survives across isolated calls ────────────────────────────

def test_cache_write_persists_in_sqlite_across_orchestrator_calls():
    """Integration property: the SQLite cache writes from call 1 are
    visible to call 2 via the file system, not just in-memory state.
    Catches regressions where cache writes silently fail (e.g. a
    schema-init race) without raising but leaving the cache empty."""
    doc = _unique_doc_for_test()
    ip = "192.0.2.77"

    with patch.object(sdk, "detect_framing_v4_2",
                      return_value=_fake_engine_success()):
        sdk.detect_framing_orchestrated(
            doc, ip=ip, ip_cap=security.v4_2_framing_daily,
        )

    # Verify cache entry exists at the filesystem level
    import sqlite3
    conn = sqlite3.connect(str(sdk._CACHE_DB_PATH))
    try:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM v4_2_cache"
        ).fetchone()
    finally:
        conn.close()
    assert count == 1, (
        "cache write did not persist to disk; orchestrator wrote to "
        "in-memory state only"
    )


# ── Engine breaker + orchestrator interaction ───────────────────────

def test_engine_circuit_breaker_triggers_orchestrator_fallback():
    """When the engine's real circuit breaker opens (sustained failure
    threshold reached), the orchestrator surfaces the circuit_open
    fallback. Integration because it uses the real breaker state, not
    a mock."""
    # Override with tight breaker for fast test, then trip it
    tight = engine._FailureRateBreaker(threshold=2, window_s=60, cooldown_s=600)
    tight.record_failure()
    tight.record_failure()
    assert tight.is_open()
    engine._LLM_BREAKER = tight

    try:
        def should_not_be_called(*args, **kwargs):
            raise AssertionError("engine called when breaker open")
        with patch.object(sdk, "detect_framing_v4_2",
                          side_effect=should_not_be_called):
            result = sdk.detect_framing_orchestrated(
                "Breaker integration test doc " + uuid.uuid4().hex,
                ip="192.0.2.111", ip_cap=security.v4_2_framing_daily,
            )
        assert result["meta"]["framing_engine"] == "layer_a"
        assert result["meta"]["fallback_reason"] == "circuit_open"
    finally:
        engine._LLM_BREAKER = engine._FailureRateBreaker()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
