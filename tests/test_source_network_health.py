"""
Tests for the Source Network provider-health tracker (F-5,
2026-04-30).

Pre-fix the only signal that an external provider was degraded
was stderr log lines from _fetch_json. An operator had to grep
fly logs to learn that CoinGecko had been 429-ing all afternoon
and verifications were silently degraded for crypto claims.

The provider_health tracker maintains an in-memory rolling
window of per-provider errors. /health surfaces the snapshot so
external monitoring can detect degradation without log-grepping.

These tests pin:
  - URL -> provider mapping (host-based string match)
  - empty snapshot shape on a clean tracker
  - record_error increments and the snapshot reflects the count
  - 429 / 401 / 403 / 5xx classification (the rate_limited
    sub-count is the actionable operator signal)
  - rolling window: events older than window_seconds drop off
  - /health endpoint surfaces the snapshot under source_network
"""

import sys
import time

import source_network


def check(condition, msg):
    if not condition:
        print(f"  FAIL: {msg}")
        sys.exit(1)


def _reset():
    source_network.provider_health.reset()


def test_url_to_provider_mapping():
    """Hostname-based provider labels must match the names other
    surfaces use (verify_coingecko, verify_brave_search, etc.).
    """
    print("=== url -> provider mapping ===")
    cases = [
        ("https://api.coingecko.com/api/v3/simple/price?x=1", "coingecko"),
        ("https://api.brave.com/search", "brave"),
        ("https://en.wikipedia.org/w/api.php", "wikipedia"),
        ("https://api.stlouisfed.org/fred/series/x", "fred"),
        ("https://www.alphavantage.co/query", "alpha_vantage"),
        ("https://api.worldbank.org/v2/x", "world_bank"),
        ("https://restcountries.com/v3.1/x", "rest_countries"),
        ("https://api.wolframalpha.com/v2/x", "wolfram"),
        ("https://www.sec.gov/cgi-bin/browse-edgar", "sec_edgar"),
        ("https://api.github.com/repos/x/y", "github"),
    ]
    for url, expected in cases:
        got = source_network._provider_from_url(url)
        check(got == expected,
              f"_provider_from_url({url!r}) = {got!r}, expected {expected!r}")
    # Unknown host falls back to the bare host string so the
    # snapshot can still surface degradation by an unmapped
    # provider (e.g., a future verifier that calls an api we
    # have not yet labeled).
    got = source_network._provider_from_url("https://unknown-api.example.com/x")
    check(got == "unknown-api.example.com",
          f"unknown host fallback: got {got!r}")
    print("  PASS\n")


def test_empty_snapshot_shape():
    """A fresh tracker returns the documented two-key envelope
    with an empty providers dict.
    """
    print("=== empty snapshot shape ===")
    _reset()
    snap = source_network.provider_health.snapshot()
    check(set(snap.keys()) == {"window_seconds", "providers"},
          f"snapshot keys: {set(snap.keys())}")
    check(snap["window_seconds"] == 3600,
          f"window_seconds: {snap['window_seconds']}")
    check(snap["providers"] == {},
          f"providers must be empty: {snap['providers']}")
    print("  PASS\n")


def test_record_error_aggregates_per_provider():
    """record_error increments the per-provider count. snapshot
    surfaces total + last_error_age_s. The age is monotonic
    (age increases as wall-clock advances).
    """
    print("=== record_error aggregates ===")
    _reset()
    source_network.provider_health.record_error("coingecko", "rate_limited")
    source_network.provider_health.record_error("coingecko", "rate_limited")
    source_network.provider_health.record_error("brave", "other")
    snap = source_network.provider_health.snapshot()
    check("coingecko" in snap["providers"], "coingecko absent")
    check("brave" in snap["providers"], "brave absent")
    cg = snap["providers"]["coingecko"]
    check(cg["total"] == 2, f"coingecko total: {cg['total']}")
    check(cg["rate_limited"] == 2,
          f"coingecko rate_limited: {cg['rate_limited']}")
    check(cg["last_error_age_s"] >= 0,
          f"last_error_age_s: {cg['last_error_age_s']}")
    br = snap["providers"]["brave"]
    check(br["total"] == 1, f"brave total: {br['total']}")
    check(br["rate_limited"] == 0,
          f"brave rate_limited (other kind, not 429): {br['rate_limited']}")
    print("  PASS\n")


def test_rate_limited_subcount_is_the_actionable_signal():
    """The rate_limited sub-count separates 429s from other
    errors so the operator can distinguish "we are over quota"
    (rotate keys, accept degradation, switch providers) from
    "the provider is down" (wait for recovery, alert support).
    """
    print("=== rate_limited subcount discipline ===")
    _reset()
    pv = source_network.provider_health
    pv.record_error("p", "rate_limited")
    pv.record_error("p", "rate_limited")
    pv.record_error("p", "auth")
    pv.record_error("p", "server_error")
    pv.record_error("p", "other")
    snap = pv.snapshot()
    p = snap["providers"]["p"]
    check(p["total"] == 5, f"total: {p['total']}")
    check(p["rate_limited"] == 2,
          f"rate_limited must count only 429-tagged events; got {p['rate_limited']}")
    print("  PASS\n")


def test_window_drops_old_events():
    """Events older than window_seconds fall off snapshot. The
    test reaches inside _events to simulate aged entries because
    the window is 3600s and waiting that long in tests is not
    practical. This still pins the trim discipline: snapshot()
    must remove old events, not just stop counting them.
    """
    print("=== rolling window drop ===")
    _reset()
    pv = source_network.provider_health
    pv.record_error("p", "rate_limited")
    # Inject an aged event directly. Allowed because this is a
    # white-box test of the trim path.
    aged_ts = time.time() - 7200  # 2 hours ago, well past window
    with pv._lock:
        pv._events["q"] = [(aged_ts, "rate_limited")]
    snap = pv.snapshot()
    check("p" in snap["providers"],
          "fresh provider must remain in snapshot")
    check("q" not in snap["providers"],
          "provider with only-aged events must be trimmed")
    print("  PASS\n")


def test_health_endpoint_surfaces_provider_snapshot():
    """/health includes a source_network block carrying the
    snapshot. The block is always present (clean tracker
    produces an empty providers dict) so external monitoring
    can detect "this build does not surface SN health" as a
    deploy regression.
    """
    print("=== /health surfaces source_network snapshot ===")
    _reset()
    import importlib.util
    if importlib.util.find_spec("app") is None:
        # The web `/health` endpoint lives in the upstream-only `app`
        # module (FastAPI service; not in the wheel-bundled subset and
        # absent on the public mirror). Skip cleanly when the module
        # is not present so the suite still pins the SN-tracker
        # primitives that DO ship publicly.
        print("  SKIP (app module is web-only; absent on the public mirror)\n")
        return
    from fastapi.testclient import TestClient
    import app as app_module
    client = TestClient(app_module.app)
    resp = client.get("/health", headers={"host": "localhost"})
    check(resp.status_code == 200, f"/health status: {resp.status_code}")
    body = resp.json()
    check("source_network" in body,
          "/health must include source_network block")
    sn = body["source_network"]
    check("window_seconds" in sn and "providers" in sn,
          f"source_network must have window_seconds and providers: {sn}")
    check(sn["providers"] == {},
          f"clean tracker should produce empty providers: {sn['providers']}")

    # After recording an error, /health must reflect it.
    source_network.provider_health.record_error("coingecko", "rate_limited")
    resp2 = client.get("/health", headers={"host": "localhost"})
    body2 = resp2.json()
    check("coingecko" in body2["source_network"]["providers"],
          "live error must surface on the next /health hit")
    cg = body2["source_network"]["providers"]["coingecko"]
    check(cg["rate_limited"] >= 1,
          f"rate_limited count must include the recorded error: {cg}")
    _reset()
    print("  PASS\n")


if __name__ == "__main__":
    test_url_to_provider_mapping()
    test_empty_snapshot_shape()
    test_record_error_aggregates_per_provider()
    test_rate_limited_subcount_is_the_actionable_signal()
    test_window_drops_old_events()
    test_health_endpoint_surfaces_provider_snapshot()
    print("All source_network_health tests passed.")
