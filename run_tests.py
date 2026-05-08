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
    # Source Network wall-clock budget primitive (2026-05-02). Pins
    # the architectural compromise documented at
    # framecheck_mcp/source_network.py:SN_BUDGET_SECONDS: best-effort
    # bound on cumulative SN time so a slow / rate-limited provider
    # cannot blow the outer _structural budget. Also pins that
    # budget-exhausted fallback uses existing verdict vocabulary
    # ('unverifiable') so template + aggregation paths are unchanged.
    # Two tests (~0.04s); registered here so a refactor that drops the
    # budget primitive fails CI at PR time rather than producing
    # production "Analysis timed out" rejections later.
    "test_source_network_budget.py",
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
    # Observatory scheduler default-safe gate (2026-04-30 polarity
    # inversion). Pin the boot-time refusal so a future refactor
    # cannot quietly re-introduce the default-on shape that fired
    # external API calls on every fresh deploy.
    "test_observatory_gate.py",
    # Web JSON / api/profile vs MCP frame_check parity. Catches
    # plumbing dropouts (the field-omitted-from-JSON class), schema
    # drift (a field renamed on one surface but not the other), and
    # detector divergence (a future refactor that changes analyzer
    # args on one surface but not the other). Parametrized over
    # every adversarial + in-cap worked-example document.
    "test_web_mcp_parity.py",
    # Source Network external-provider health visibility (F-5,
    # 2026-04-30). Pins URL -> provider mapping, rolling-window
    # trim, 429 sub-count classification, and the /health
    # surface that operators (and external monitoring) read to
    # detect silent verification degradation without grepping
    # fly logs.
    "test_source_network_health.py",
    # SERVER_VERSION coherence (mcp_server.py:121 must match
    # pyproject.toml [project] version with .dev0 suffix
    # stripped). The orchestrator's lift_dry_run gate catches
    # mismatches AT RELEASE TIME via the wheel smoke-test, but a
    # drift introduced between releases stays invisible until the
    # next cut. Pinning at PR time so the upstream tree stays
    # coherent and operators running `python3 mcp_server.py
    # --version` from a clone see the version that will ship.
    "test_version_coherence.py",
    # detector_empirics harness helpers. The end-to-end harness run
    # is on-demand (slow: subprocess MCP per document); these unit
    # tests exercise the helpers (`_frame_deepening_fires`,
    # `_aggregate`, `_markdown_report`) with synthetic payloads so a
    # regression is caught at PR time instead of when the next
    # harness run produces a malformed report. Registered here
    # (rather than left to plain pytest discovery) because CI uses
    # `python3 run_tests.py` as the primary invocation path; an
    # unregistered file would only run via the pytest-smoke secondary
    # job's explicit list.
    "test_detector_empirics.py",
    # Bitcoin/gold stress-test regression scaffold (2026-04-30).
    # Locks the observed `build_epistemic_payload` and
    # `build_compare_payload` output on a real advocacy document
    # plus a deliberately-asymmetric counter-document so subsequent
    # detector / renderer changes produce a visible diff. Pins
    # several construct-honesty boundaries already documented in
    # data/adversarial_fixtures/: numbered-argument essay
    # classifies as instruction (candidate new fixture, NOT
    # covered by sales_pitch_as_analysis); quantitative risk
    # vocabulary under-detected by coverage regex (related to
    # coverage_via_noncanonical_vocabulary; correct fix is
    # caveat propagation in framing_headline, not regex
    # expansion); analytical voice as cascade residual at high
    # confidence (deliberate design per voice_residual_analytical).
    # The truth-in-labelling assertion on evidence.signal_text
    # was the first delta closed by the same-day decision_readiness
    # _evidence_dimension fix; this regression asserts the
    # corrected text and pins it against future regressions.
    "test_regression_bitcoin_gold_2026_04_30.py",
    # MCP tool-surface boundary: frame_check + frame_compare
    # make zero outbound socket.connect calls. Pins the agent-
    # server architectural separation (server = deterministic
    # structural analysis; agent = adaptive work including
    # external source fetching). A future refactor that re-couples
    # I/O into the substrate path (e.g., adds verify_via_brave
    # inside a detector) fails this pin at PR time. Same pattern
    # as the existing V4.2 LLM-judge delegation already documented
    # in MCP_SERVER.md; this test extends from LLM-only to
    # all-network-I/O.
    "test_mcp_server_no_outbound_http.py",

    # Public-extract inventory discipline. Three structural-pin
    # tests catch the bug class that put the public mirror's CI
    # on a red badge for ~3 days post-v0.8.3 (15 test files in
    # INCLUDE_FILES whose target modules were operator-only).
    # Tests: every test in INCLUDE_FILES has its top-level local
    # imports resolvable on the public surface; every name in
    # pyproject.toml py-modules has a source file at repo root;
    # every suite declared in SUITES / PYTEST_SUITES exists at
    # repo root. <100ms total; pure source-grep / AST walk.
    "test_public_extract_inventory.py",

    # llm_client.xai_endpoint resolution + helpers. llm_client is
    # the single source of truth for "where do we send Grok
    # requests?" for 8 importing modules across the codebase
    # (consensus.py, framing_ai.py, comparison.py, framing_sdk.py,
    # reframe.py, pipeline.py, fvs_eval/v4/v4_2_engine.py, app.py).
    # Pins the four resolution branches (proxy / proxy-degrades-
    # to-direct / direct / unconfigured) plus the empty-string and
    # whitespace-only env edge cases that would otherwise produce
    # silently-401-ing clients on misconfigured deploys. A
    # regression here would silently mis-route every xAI call
    # across the surface.
    "test_llm_client.py",
]

REPO_ROOT = Path(__file__).resolve().parent


def run_suite(name: str, quiet: bool, timeout_seconds: int,
              pytest_mode: bool = False,
              suite_path: "Path | None" = None) -> tuple:
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
    # Tests live under `tests/` per the 0.8.5 organization. When run
    # via legacy `python3 tests/test_X.py` invocation (the standalone-
    # script pattern), the test file's directory is `tests/`, not the
    # repo root, so bare imports against root-level modules
    # (`from clarethium_measure import measure`) fail with
    # ModuleNotFoundError unless the repo root is on PYTHONPATH.
    # `tests/conftest.py` covers the pytest invocation path; this
    # PYTHONPATH override covers the legacy-script path. Both
    # invocations now resolve root-level modules consistently.
    existing_pythonpath = suite_env.get("PYTHONPATH", "")
    suite_env["PYTHONPATH"] = (
        str(REPO_ROOT) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    )
    # Pytest-mode invocation: `python3 -m pytest <file> -q`. Legacy
    # mode: `python3 <file>` (the file is a standalone script with an
    # `if __name__ == "__main__"` runner). Both return 0 on success,
    # non-zero on failure, which is what run_suite checks.
    # Resolve the path to invoke. `suite_path` is the resolved Path
    # from the caller (handles both root-level and tests/-located
    # files). Fall back to bare `name` for backward compatibility
    # with any external caller that does not pass suite_path.
    invoke_path = str(suite_path) if suite_path is not None else name
    if pytest_mode:
        cmd = [sys.executable, "-m", "pytest", invoke_path, "-q", "--no-header"]
    else:
        cmd = [sys.executable, invoke_path]
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
        suite failed AND --bail is set (signals the caller to stop).

        A missing file (not present at REPO_ROOT) is a structural skip,
        not a failure: this happens by design on the public mirror
        where `run_tests.py` ships verbatim from upstream but several
        SUITES entries reference upstream-only test files. The skip is
        printed for visibility and excluded from the results list so
        `len(SUITES) - len(results)` resolves to the real skipped count
        in the summary footer; folding missing files into `results`
        with `(name, False, 0.0)` (the prior shape) inflated the
        failed count and rendered the public-mirror CI badge red on
        a structurally clean run.
        """
        # Tests live under `tests/` per the repo organization that
        # landed alongside this comment. The path resolution here uses
        # the historical bare-name lookup at REPO_ROOT for backward
        # compatibility (so any test ever-located at root still
        # resolves via the structural-skip path), then falls back to
        # `REPO_ROOT / "tests" / suite_name` for the canonical
        # location. Two-step lookup keeps the missing-file SKIP
        # discipline working across the move and any future operator
        # who reverts a test back to root.
        path = REPO_ROOT / suite_name
        if not path.exists():
            path = REPO_ROOT / "tests" / suite_name
        if not path.exists():
            print(f"  SKIP   {suite_name}  (missing)")
            return True
        success, elapsed, output = run_suite(
            suite_name, args.quiet, args.timeout, pytest_mode=pytest_mode,
            suite_path=path,
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
