"""V4.2 model probe CLI: detect silent vendor-side model drift.

Problem addressed (Phase 2 item 14 per V4_2_GAP_INVENTORY_v1.md):
the V4.2 engine's reliability metadata (LIBRARY_RELIABILITY
cross-family AC1 and grok_intra_rater_ac1.json intra-rater AC1) was
measured on a specific snapshot of grok-4-1-fast-non-reasoning. If
xAI updates the model weights behind that label without changing the
label, our reliability claims become stale without our knowing. The
first external reviewer will ask "how do you know the model still
matches the measured model?" This probe gives the answer: a scheduled
verdict-pattern check against a frozen baseline.

Design choices (from stress-testing the original hash-probe-at-startup
proposal):

1. Verdict-pattern comparison, not hash comparison. Temp=0 has ~0.10
   sampling variance on V4.2 per V4_2_GAP_INVENTORY_v1.md gap #11;
   strict hash match would fire false positives on normal noise.

2. Scheduled via cron / GitHub Actions / Fly cron, not serving-path.
   Startup probe per cold-start would waste budget on infrastructure
   events unrelated to model drift, and a vendor update would take the
   site offline rather than triggering a review-and-decide posture.

3. Dual threshold, grounded in measurement. Gap #11 measured ~2 of 19
   frames flipping on repeat calls with identical input. That IS the
   sampling-variance baseline. Useful drift detection must exceed it:

   - per-doc threshold: more than 2 frame flips on any single doc
     (above single-doc sampling variance)
   - aggregate threshold: more than 6 flips across all probe docs
     (above combined 3-doc sampling variance budget of 2 x 3)

   Either condition triggers exit 1. This filters normal noise while
   catching meaningful drift.

4. Exit codes distinguish failure modes:
   - 0: verdicts within tolerance (model behaves as measured)
   - 1: drift detected (operator review needed)
   - 2: probe could not run (API down, config error, missing docs)

Usage:

  # First-time baseline capture, typically after a new intra-rater
  # measurement study. Pick 3 corpus documents with known Step 4
  # verdicts; the probe will re-run V4.2 on them to capture current
  # single-family output for comparison against future runs.
  python3 scripts/probe_v4_2_model.py baseline \\
      --docs fvs_eval/mixed_genre_v2/corpus/doc1.txt \\
             fvs_eval/mixed_genre_v2/corpus/doc2.txt \\
             fvs_eval/mixed_genre_v2/corpus/doc3.txt \\
      --out fvs_eval/v4/model_probe_baseline.json

  # Scheduled drift check, e.g. weekly via cron.
  python3 scripts/probe_v4_2_model.py check \\
      --baseline fvs_eval/v4/model_probe_baseline.json

Cost: 3 calls per check run at ~$0.006 each = $0.018 per run.
Weekly schedule: ~$0.94/year. Negligible.

Cost for baseline capture: same 3 calls. Regenerate any time a new
intra-rater measurement study reset the reliability metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "fvs_eval" / "v4"))

from v4_2_engine import (  # noqa: E402
    FRAME_IDS_EMISSION,
    FRAMING_ENGINE,
    LLMUnavailable,
    V4_2_VERSION,
    detect_framing_v4_2,
    library_hash,
)


# ── Threshold constants (documented in module docstring) ────────────

PER_DOC_FLIP_THRESHOLD = 2   # flips STRICTLY greater than this triggers alert
AGGREGATE_FLIP_THRESHOLD = 6  # total flips STRICTLY greater than this triggers alert

EXIT_OK = 0
EXIT_DRIFT_DETECTED = 1
EXIT_PROBE_FAILED = 2


# ── Baseline capture ────────────────────────────────────────────────

def _capture_one(doc_path: Path) -> dict:
    """Run V4.2 on a single document; return the verdict map plus
    execution metadata. Raises on any engine failure; caller decides
    whether to abort the baseline or mark the doc as unrunnable."""
    text = doc_path.read_text(encoding="utf-8")
    result = detect_framing_v4_2(
        text,
        title=doc_path.stem,
        source=f"model_probe:{doc_path.name}",
    )
    verdicts = {e["fvs_id"]: e["exhibits"] for e in result["entries"]}
    return {
        "verdicts": verdicts,
        "model_served": result["meta"]["model_served"],
        "cost_estimate_usd": result["meta"]["cost_estimate_usd"],
        "stop_reason": result["meta"].get("stop_reason"),
        "frames_missing_or_invalid":
            result["meta"]["validation"]["frames_missing_or_invalid"],
    }


def cmd_baseline(args: argparse.Namespace) -> int:
    """Capture current V4.2 verdicts on the given probe documents.
    Writes a baseline JSON suitable for future `check` comparison.
    """
    docs = [Path(p) for p in args.docs]
    for d in docs:
        if not d.exists():
            print(f"[probe:baseline] missing doc: {d}", file=sys.stderr)
            return EXIT_PROBE_FAILED

    captured = {}
    total_cost = 0.0
    for d in docs:
        print(f"[probe:baseline] capturing {d.name}...", file=sys.stderr)
        try:
            entry = _capture_one(d)
        except LLMUnavailable as exc:
            print(f"[probe:baseline] LLM unavailable: {exc}", file=sys.stderr)
            return EXIT_PROBE_FAILED
        except Exception as exc:
            print(f"[probe:baseline] unexpected error on {d.name}: "
                  f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return EXIT_PROBE_FAILED
        captured[str(d)] = entry
        total_cost += entry["cost_estimate_usd"]

    baseline = {
        "schema_version": "1.0",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine_version": V4_2_VERSION,
        "framing_engine": FRAMING_ENGINE,
        "library_hash": library_hash(),
        "model_served": next(iter(captured.values()))["model_served"]
                         if captured else None,
        "total_cost_estimate_usd": round(total_cost, 6),
        "per_doc": captured,
        "thresholds": {
            "per_doc_flip_threshold": PER_DOC_FLIP_THRESHOLD,
            "aggregate_flip_threshold": AGGREGATE_FLIP_THRESHOLD,
            "threshold_rationale": (
                "Per V4_2_GAP_INVENTORY_v1.md gap #11, temp=0 single-family "
                "sampling variance is ~2 of 19 frames per doc. Per-doc "
                "threshold is STRICTLY GREATER THAN 2; aggregate threshold "
                "is STRICTLY GREATER THAN 2 * n_docs."
            ),
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(baseline, indent=2) + "\n")
    print(f"[probe:baseline] wrote {out_path} ({len(captured)} docs, "
          f"${total_cost:.4f} total cost)", file=sys.stderr)
    return EXIT_OK


# ── Drift check ─────────────────────────────────────────────────────

def _count_flips(
    baseline_verdicts: dict[str, bool],
    current_verdicts: dict[str, bool],
) -> tuple[int, list[str]]:
    """Compare two per-frame verdict maps. Return (flip_count,
    flipped_frame_ids). A frame missing from either map counts as a
    flip (defensive: a missing frame signals something changed in the
    emission panel or the engine).
    """
    flipped = []
    all_frames = set(baseline_verdicts) | set(current_verdicts) | set(FRAME_IDS_EMISSION)
    for fvs_id in sorted(all_frames):
        b = baseline_verdicts.get(fvs_id)
        c = current_verdicts.get(fvs_id)
        if b != c:
            flipped.append(fvs_id)
    return len(flipped), flipped


def cmd_check(args: argparse.Namespace) -> int:
    """Re-run V4.2 on each baselined doc, compare verdicts against
    the baseline, apply dual threshold, and exit.

    Exit codes:
      0 = match within tolerance
      1 = drift detected
      2 = probe could not run
    """
    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        print(f"[probe:check] missing baseline: {baseline_path}", file=sys.stderr)
        return EXIT_PROBE_FAILED

    try:
        baseline = json.loads(baseline_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"[probe:check] baseline parse error: {exc}", file=sys.stderr)
        return EXIT_PROBE_FAILED

    per_doc_baseline = baseline.get("per_doc", {})
    if not per_doc_baseline:
        print("[probe:check] baseline has no per_doc entries; regenerate "
              "via `baseline` subcommand.", file=sys.stderr)
        return EXIT_PROBE_FAILED

    # Threshold values come from baseline (so updating thresholds at
    # baseline-regen time is the operational flow), falling back to
    # module constants.
    thresholds = baseline.get("thresholds", {})
    per_doc_threshold = thresholds.get(
        "per_doc_flip_threshold", PER_DOC_FLIP_THRESHOLD,
    )
    aggregate_threshold = thresholds.get(
        "aggregate_flip_threshold", AGGREGATE_FLIP_THRESHOLD,
    )

    # Check library_hash drift first. A library revision changes the
    # prompt and therefore the expected verdicts; drift under a new
    # library_hash is not a vendor-model-drift signal, it is a library-
    # change signal. Operator should regenerate baseline.
    current_lib_hash = library_hash()
    if baseline.get("library_hash") != current_lib_hash:
        print(f"[probe:check] library_hash changed: baseline="
              f"{baseline.get('library_hash')!r} vs current="
              f"{current_lib_hash!r}. Regenerate baseline after a "
              f"library revision.", file=sys.stderr)
        return EXIT_PROBE_FAILED

    total_flips = 0
    per_doc_results = []
    for doc_path_str, baseline_entry in per_doc_baseline.items():
        doc_path = Path(doc_path_str)
        if not doc_path.exists():
            print(f"[probe:check] baselined doc missing: {doc_path}",
                  file=sys.stderr)
            return EXIT_PROBE_FAILED
        print(f"[probe:check] checking {doc_path.name}...", file=sys.stderr)
        try:
            current = _capture_one(doc_path)
        except LLMUnavailable as exc:
            print(f"[probe:check] LLM unavailable: {exc}", file=sys.stderr)
            return EXIT_PROBE_FAILED
        except Exception as exc:
            print(f"[probe:check] unexpected error on {doc_path.name}: "
                  f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return EXIT_PROBE_FAILED

        n_flips, flipped_frames = _count_flips(
            baseline_entry["verdicts"], current["verdicts"],
        )
        total_flips += n_flips
        per_doc_results.append({
            "doc": doc_path.name,
            "n_flips": n_flips,
            "flipped_frames": flipped_frames,
            "per_doc_threshold_exceeded": n_flips > per_doc_threshold,
        })

    # Apply dual threshold.
    any_per_doc_exceeded = any(r["per_doc_threshold_exceeded"]
                                for r in per_doc_results)
    aggregate_exceeded = total_flips > aggregate_threshold

    report = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseline_captured_at": baseline.get("captured_at"),
        "engine_version": V4_2_VERSION,
        "library_hash": current_lib_hash,
        "total_flips": total_flips,
        "aggregate_threshold": aggregate_threshold,
        "aggregate_exceeded": aggregate_exceeded,
        "per_doc": per_doc_results,
        "drift_detected": any_per_doc_exceeded or aggregate_exceeded,
    }
    print(json.dumps(report, indent=2))

    if report["drift_detected"]:
        print(f"[probe:check] DRIFT DETECTED. total_flips={total_flips} "
              f"(threshold > {aggregate_threshold}); "
              f"per-doc exceeded: {[r['doc'] for r in per_doc_results if r['per_doc_threshold_exceeded']]}",
              file=sys.stderr)
        return EXIT_DRIFT_DETECTED

    print(f"[probe:check] ok. total_flips={total_flips}/{aggregate_threshold+1}+; "
          f"no per-doc exceedance.", file=sys.stderr)
    return EXIT_OK


# ── CLI entry point ─────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="V4.2 model probe: detect silent vendor-side model drift."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_baseline = sub.add_parser(
        "baseline",
        help="Capture current V4.2 verdicts on probe documents.",
    )
    p_baseline.add_argument(
        "--docs", nargs="+", required=True,
        help="Path to one or more probe documents (typically 3).",
    )
    p_baseline.add_argument(
        "--out", required=True,
        help="Path to write the baseline JSON.",
    )
    p_baseline.set_defaults(func=cmd_baseline)

    p_check = sub.add_parser(
        "check",
        help="Re-run V4.2 on baselined docs and compare verdicts.",
    )
    p_check.add_argument(
        "--baseline", required=True,
        help="Path to a baseline JSON produced by the `baseline` subcommand.",
    )
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
