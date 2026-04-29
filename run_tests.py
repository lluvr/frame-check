#!/usr/bin/env python3
"""Run every test suite in sequence and report a single summary.

The project uses standalone test scripts (no pytest collection)
because the suites predate any test runner setup. This script is
the missing piece: one command, one summary, one exit code.

Usage:
    python3 run_tests.py            # run all suites
    python3 run_tests.py --quiet    # only print suite names + results
    python3 run_tests.py --bail     # stop on first failure

Exit code: 0 if every suite passes, 1 if any suite fails.

Why a runner script (not pytest):
  The existing tests use a check(condition, msg) helper and run
  as `python3 test_X.py`. Migrating them to pytest would change
  the failure-reporting style and require touching every test
  function. This runner respects the existing pattern: each
  test file is a self-contained executable that exits 0 on
  success, non-zero on failure.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Suites in dependency order: pure unit tests first, then HTTP
# integration tests that depend on the FastAPI app being importable.
# Order matters only for failure isolation: a broken pipeline
# would also break SSE / pages, so we report the root cause first.
SUITES = [
    "test_pipeline.py",          # Core analyzer pipeline
    "test_telemetry.py",         # Frame Check Corpus event store
    "test_tier_a_builder.py",    # Tier A event builders
    "test_telemetry_recovery.py", # SQLite portability + recovery
    "test_export_corpus.py",     # Daily NDJSON + Parquet export
    "test_model_registry.py",    # Phase 1.6a Prereq 7
    "test_classifiers.py",       # Phase 1.6a Prereqs 2 + 3
    "test_observatory_stability.py", # Phase 1.6a Prereq 6
    "test_source_latency.py",    # Phase 1.6e item 4: per-source latency stamping
    "test_observatory.py",       # Phase 1.6b Observatory worker
    "test_phase1_smoke.py",      # phase1_smoke.py post-deploy verification
    "test_schema_check.py",      # Phase 1.6d schema_check.py
    "test_phase1_load.py",       # Phase 1.6d Section 11 load test
    "test_sse.py",               # SSE stream protocol
    "test_compare_save.py",      # saved_compare module + endpoints
    "test_compare_examples.py",  # compare_examples module + integration
    "test_og_image.py",          # OG image generator + endpoints
    "test_mcp_server.py",        # MCP server: payload schema + JSON-RPC + stdio
    "test_decision_readiness.py", # Phase 1.5: profile composition contract
    "test_decision_readiness_diff.py", # transformation-pair diff contract
    "test_decision_readiness_peer.py", # peer-comparison contract
    "test_canon_graph_consistency.py", # bidirectional library<->methodology<->module
    "test_validation_scaffolding.py", # Phase 2: validation harness scaffolding
    "test_frame_library_index.py", # INDEX.md format parser (statuses + titles)
    "test_build_corpus_polish.py", # corpus_site builder helpers
    "test_pages.py",             # Page smoke tests + flow integration
]

# Pytest-style suites: test files that rely on pytest discovery rather
# than the legacy `if __name__ == "__main__"` runner pattern used by
# SUITES above. Added 2026-04-21 after a pre-deploy audit found 19
# such files (~484 tests) that were never executed by the single
# `python3 run_tests.py` entry point. Every file below passes cleanly
# under `python3 -m pytest <file> -q`. Ordered roughly by dependency
# risk: security + cost gates first so a regression fails early.
PYTEST_SUITES = [
    # Security + cost gates (highest deploy-risk if regressed)
    "test_circuit_breaker.py",      # Persistent daily spend cap + date rollover
    "test_llm_cost.py",              # Token-to-cost measurement (feeds circuit breaker)
    "test_origin_protection.py",    # Cloudflare origin guard + IP resolution
    "test_trust_tier_weighting.py", # Trust-tier downgrade when SN dominated by weak providers
    # Pipeline + framing invariants
    "test_grounding.py",             # Layer 11 grounding decomposition
    "test_reframe.py",               # L2 reframe path + telemetry wiring
    "test_mirror.py",                # Mirror / self-audit path
    "test_frame_library.py",         # FVS suggest_frames behavior
    "test_framing_validation.py",   # Framing detector rule thresholds
    # Routing + classifiers
    "test_entity_classifier.py",
    "test_time_context.py",
    "test_routing_by_entity_type.py",
    "test_routing_by_time_context.py",
    "test_world_bank_routing.py",
    # Source Network calibration substrate
    "test_calibration_harness.py",
    "test_source_network_validation.py",
    "test_numerical_extraction.py",
    "test_domain_baselines.py",
    "test_documented_boundaries.py",
    # Discipline boundary (post-2026-04-24 library_v4 stress-test)
    "test_v4_2_discipline_boundary.py",
    # Adversarial fixture suite (operational test of substrate-side
    # composition L5 per-level construct treatment)
    "test_adversarial_fixtures.py",
    # MCP server hardening: Phase 5 + 0.8.0 publish-readiness audit
    "test_mcp_security_phase5.py",
    "test_mcp_adversarial.py",
    # Prompt-injection guard for non-V4.2 LLM endpoints
    # (framing_ai, reframe, comparison, consensus). Every endpoint
    # must reject sentinel-bearing user content before any LLM client
    # is constructed; the suite uses patched-client assertions to
    # catch any future refactor that re-orders rejection past the
    # network call.
    "test_prompt_safety.py",
]

REPO_ROOT = Path(__file__).resolve().parent


def run_suite(name: str, quiet: bool, timeout_seconds: int,
              pytest_mode: bool = False) -> tuple:
    """Run one test suite. Returns (success, elapsed_seconds, output).

    A timeout protects against a hung test (deadlock, infinite loop,
    waiting on an external API that never responds). Without it the
    runner could hang indefinitely. The default timeout is generous
    (5 minutes) so the slowest legitimate suite (test_compare_examples
    at ~85s with real network calls) has plenty of headroom, but a
    truly hung suite cannot block the whole run.

    Each suite gets its own temporary FRAME_CHECK_EVENTS_DB path so
    the dev artifact in ./data/ stops accumulating across runs and
    so suites cannot pollute each other's telemetry state. The
    temporary directory is removed after the suite finishes
    regardless of pass / fail / timeout, via the try/finally below.
    """
    started = time.time()
    # Per-suite temp directory for the telemetry event store. The
    # FRAME_CHECK_EVENTS_DB env var overrides telemetry's path
    # resolution chain, so any test that boots app.py (via
    # FastAPI TestClient or otherwise) ends up writing to this
    # tempfile instead of /data or ./data. The directory wraps
    # the file because SQLite WAL mode creates -wal and -shm
    # siblings that need cleanup too.
    suite_tmp = tempfile.mkdtemp(prefix=f"frame_check_test_{Path(name).stem}_")
    suite_db = Path(suite_tmp) / "events.sqlite"
    suite_env = os.environ.copy()
    suite_env["FRAME_CHECK_EVENTS_DB"] = str(suite_db)
    # Same isolation for the export state file (Phase 1.4),
    # which lives next to the events database in production.
    suite_env["FRAME_CHECK_EXPORT_STATE"] = str(Path(suite_tmp) / "export_state.json")
    # Same isolation for the global cost circuit breaker state.
    # Without this override the breaker writes to the shared
    # data/circuit_breaker.json (or /data/circuit_breaker.json
    # when the Fly mount is present), which lets one suite leak
    # a tripped-or-charged state into later suites. Evidence of
    # the leak was cents_spent accumulating across dev test runs
    # visible via /health. Per-suite tmp path closes the gap.
    suite_env["CIRCUIT_BREAKER_PATH"] = str(Path(suite_tmp) / "circuit_breaker.json")
    # Pytest-mode invocation: `python3 -m pytest <file> -q`. Legacy
    # mode: `python3 <file>` (the file is a standalone script with an
    # `if __name__ == "__main__"` runner). Both return 0 on success,
    # non-zero on failure, which is what run_suite checks.
    if pytest_mode:
        cmd = [sys.executable, "-m", "pytest", name, "-q", "--no-header"]
    else:
        cmd = [sys.executable, name]
    try:
        try:
            proc = subprocess.run(
                cmd,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=suite_env,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.time() - started
            # Combine any captured output with the timeout notice so the
            # caller sees both how far the suite got AND why it died.
            partial = ""
            if exc.stdout:
                partial += exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode("utf-8", errors="replace")
            if exc.stderr:
                partial += exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", errors="replace")
            partial += (
                f"\n\n[run_tests] TIMEOUT after {timeout_seconds}s. "
                f"The suite was killed."
            )
            return False, elapsed, "" if quiet else partial
        elapsed = time.time() - started
        if quiet:
            return proc.returncode == 0, elapsed, ""
        return proc.returncode == 0, elapsed, proc.stdout + proc.stderr
    finally:
        # Always clean up the per-suite tempdir, including
        # WAL/SHM SQLite siblings, regardless of how the suite
        # exited. Without this, /tmp accumulates one directory
        # per test run.
        import shutil as _shutil
        _shutil.rmtree(suite_tmp, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Run every Frame Check test suite in sequence.",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-suite output; show only the summary",
    )
    parser.add_argument(
        "--bail", action="store_true",
        help="Stop on the first failing suite instead of running all",
    )
    parser.add_argument(
        "--timeout", type=int, default=300,
        help="Per-suite timeout in seconds (default: 300, "
             "generous enough for the slowest legitimate suite)",
    )
    args = parser.parse_args()

    print("Running Frame Check test suites...")
    print()

    total_started = time.time()
    results = []
    bailing = False

    def _run_and_record(suite_name: str, pytest_mode: bool) -> bool:
        """Run one suite and append to results. Returns False if the
        suite failed AND --bail is set (signals the caller to stop)."""
        path = REPO_ROOT / suite_name
        if not path.exists():
            print(f"  SKIP   {suite_name}  (missing)")
            results.append((suite_name, False, 0.0))
            return True
        success, elapsed, output = run_suite(
            suite_name, args.quiet, args.timeout, pytest_mode=pytest_mode,
        )
        status = "PASS" if success else "FAIL"
        mode_tag = " [pytest]" if pytest_mode else ""
        print(f"  {status}   {suite_name:<32} ({elapsed:.2f}s){mode_tag}")
        if not success and not args.quiet:
            print()
            print("  ── output " + "─" * 50)
            for line in output.splitlines():
                print(f"  {line}")
            print("  " + "─" * 60)
            print()
        results.append((suite_name, success, elapsed))
        if not success and args.bail:
            print()
            print("  --bail: stopping on first failure")
            return False
        return True

    for suite in SUITES:
        if not _run_and_record(suite, pytest_mode=False):
            bailing = True
            break

    if not bailing:
        for suite in PYTEST_SUITES:
            if not _run_and_record(suite, pytest_mode=True):
                break

    total_elapsed = time.time() - total_started
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    total_declared = len(SUITES) + len(PYTEST_SUITES)
    skipped = total_declared - len(results)

    print()
    print("─" * 60)
    print(
        f"Total: {len(results)} suites run in {total_elapsed:.2f}s. "
        f"{passed} passed, {failed} failed"
        + (f", {skipped} skipped" if skipped else "")
    )
    print("─" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
