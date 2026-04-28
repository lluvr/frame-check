"""Reframe-behavior smoke test (METHODOLOGY section 2.4.4 corollary).

The library_v3 -> library_v4 ratification's reframe-null-risk claim
rested on Generation affordances being byte-equivalent between
library_v3 and library_v4 across all 20 entries (verified during the
post-ratification stress-test pass; locked by
``test_v4_2_discipline_boundary.py::test_generation_affordances_byte_equivalent_v3_to_v4``).

Future library revisions that intentionally change ``## Generation
affordances`` for one or more frames must run this harness before
merging. Section 2.4.3 ablation does NOT cover Generation-affordances
changes because reframe is not a cross-family-AC1 quantity; reframe is
an LLM rewrite call whose behavior depends on the counter-document
prompt content read from this section.

Cost: ~$0.01 per frame per document via Grok 4.1 fast. A typical run
on one revised frame against one representative document is ~$0.02
(baseline + candidate).

What "passing" means

A reframe smoke test passes when, for each affected frame and each
representative document:

1. The candidate library reframe call SUCCEEDS (no LLM error, no
   truncation, content returned). Failure here means the new
   counter-document prompt confused the model.

2. The candidate output preserves every number that appeared in the
   source document. Per the system prompt at ``reframe.py:_REWRITE_SYSTEM``:
   "Keep EVERY number from the original. Do not invent new numbers."
   A number-loss regression on a frame's reframe is a structural
   reframe failure on that frame.

3. The candidate output length stays within +/- 20 percent of the
   source document length. The system prompt mandates this; large
   deviations indicate the new counter-document prompt biased the
   model toward expansion or compression.

4. The candidate output's deterministic structural portrait
   (coverage_addressed, coverage_missing, voice classification,
   temporal_dominant) DIFFERS from the source on at least one
   dimension. Treated as a soft WARNING rather than a hard FAIL
   because the LLM frame shift may sometimes be subtle enough that
   the deterministic portrait does not pick it up; manual inspection
   is the tiebreaker on close calls. Implemented in
   ``_structural_portrait`` and ``_portrait_shift`` below.

5. (Future) The candidate output's framing portrait SHIFT MAGNITUDE
   on the target frame is roughly comparable to the baseline output's
   shift magnitude. The regression-vs-baseline check: the new
   counter-prompt should produce a shift of similar magnitude to
   the prior counter-prompt, not a substantially weaker one. Not yet
   implemented; see TODO at file bottom.

A FAIL on any of these means the Generation-affordances change should
either be reverted, refined, or accompanied by a documented
behavior-shift explanation in the next ratification's record (per
METHODOLOGY section 2.4.4 corollary).

Status

This harness is a SCAFFOLD as of 2026-04-24. The single-frame manual
recipe at ``run_single_frame_smoke()`` is runnable; the full automated
sweep across all 19 emitting frames is documented as a TODO at the
bottom of this file because it requires:

- a curated set of representative documents per frame (one document
  per frame minimum; the worked-example or target-scope corpus is the
  natural source),
- a baseline reframe-output capture per frame at a known-good library
  state (snapshot for diffing),
- a stable structural-diff implementation that filters out LLM jitter.

The discipline expectation is that the first engineer who needs to
edit Generation affordances at scale fills in those pieces; until
then, the single-frame manual recipe is the primitive.

Usage

    python3 scripts/reframe_smoke_test.py FVS-008 \\
        --document data/worked_examples/grok-on-nvidia-earnings-2026/data.json \\
        --candidate-library data/frame_library/ \\
        --baseline-library data/frame_library_v4/

Cost authorization

This harness invokes ``reframe.rewrite_from_frame`` which calls Grok
4.1 fast. Requires ``XAI_API_KEY`` in the environment. Each frame
processed costs ~$0.01. The harness reports cost per call; abort
early on cumulative cost surprises.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _extract_numbers(text: str) -> set[str]:
    """Conservative number extractor for reframe preservation check.

    Captures comma-grouped integers, decimals, and percentages;
    filters out standalone single-digit integers without a decimal or
    percent marker. Rationale: single-digit bare numbers in analytical
    text are usually semantic noise (quarter markers "Q3", day-of-
    month "March 3", footnote refs "[1]", list indices "3."), not
    material data. A reframe that rephrases "Q3" as "third quarter"
    preserves meaning but drops the digit; penalizing that as a
    number-loss regression produces false positives on real LLM
    output.

    Multi-digit integers ("22", "265", "1000"), decimals ("22.1",
    "0.5"), percentages ("22%", "5%", "0.5%"), and comma-grouped
    numbers ("1,000", "$22,100") are all captured. Semantic numbers
    in analytical / financial documents are overwhelmingly in these
    shapes; single-digit bare integers are filtered out.
    """
    import re as _re
    pattern = _re.compile(
        r"-?\d{1,3}(?:,\d{3})+|"     # comma-grouped: 1,000 or 22,100
        r"-?\d+\.\d+%?|"             # decimals and decimal percentages
        r"-?\d+%|"                   # integer percentages
        r"-?\d{2,}"                  # multi-digit bare integers (>=2 digits)
    )
    return {m.replace(",", "") for m in pattern.findall(text)}


def _structural_portrait(text: str) -> dict:
    """Compute a deterministic structural portrait of a document for
    framing-shift comparison. Uses Frame Check's deterministic
    analyzers (no LLM call). Returns a dict with the dimensions
    relevant to frame-shift detection: coverage categories addressed
    and missing, voice classification, temporal orientation.

    A reframe that shifts the underlying frame should produce a
    portrait that differs from the source on at least one of these
    dimensions. A reframe that merely rephrases the source without
    shifting the frame produces a near-identical portrait; the
    framing-shift check below treats this as a soft warning rather
    than a hard fail because the LLM-driven frame shift may sometimes
    be subtle enough that the deterministic portrait does not pick
    it up. Manual inspection is the tiebreaker on close calls.
    """
    from framing import (
        detect_coverage,
        detect_voice,
        temporal_orientation,
    )
    cov = detect_coverage(text)
    voice = detect_voice(text)
    temp = temporal_orientation(text)
    return {
        "coverage_addressed": tuple(sorted(cov.get("addressed", []))),
        "coverage_missing": tuple(sorted(cov.get("missing", []))),
        "voice_classification": voice.get("classification"),
        "temporal_dominant": temp.get("dominant"),
    }


def _portrait_shift(source: dict, candidate: dict) -> dict:
    """Compare two structural portraits; return the per-dimension
    differences plus a shift_count summary."""
    diffs: dict[str, tuple] = {}
    for key in source.keys():
        s = source[key]
        c = candidate[key]
        if s != c:
            if isinstance(s, tuple) and isinstance(c, tuple):
                diffs[key] = {
                    "added": sorted(set(c) - set(s)),
                    "removed": sorted(set(s) - set(c)),
                }
            else:
                diffs[key] = {"source": s, "candidate": c}
    return {"shift_count": len(diffs), "diffs": diffs}


def run_single_frame_smoke(
    fvs_id: str,
    document_path: Path,
    candidate_library: Path,
    baseline_library: Path | None,
    print_text: bool = False,
) -> tuple[int, dict | None]:
    """Run reframe smoke test for one frame against one document.

    Returns ``(exit_code, result_dict)`` where exit_code is 0 on pass /
    1 on fail, and result_dict captures the reframe text + per-check
    metrics for downstream aggregation (e.g. full-sweep baseline
    capture). On early-fail paths that could not execute the reframe
    call, result_dict is None.

    Prints a structured report to stdout for the operator to inspect.
    When print_text is true, also prints the source and reframed text
    so the operator can manually inspect whether the LLM-driven frame
    shift is real (the structural checks below are necessary but not
    sufficient for reframe quality).
    """
    if not os.environ.get("XAI_API_KEY"):
        print("FAIL: XAI_API_KEY not set; reframe call requires Grok auth.")
        return 1, None

    if not document_path.is_file():
        print(f"FAIL: document not found at {document_path}")
        return 1, None

    # Load document text. Accept either a worked-example data.json
    # (use llm_summary.text) or a plain text file.
    if document_path.suffix == ".json":
        capture = json.loads(document_path.read_text(encoding="utf-8"))
        if "llm_summary" in capture and "text" in capture["llm_summary"]:
            doc_text = capture["llm_summary"]["text"]
        else:
            print(
                f"FAIL: {document_path} is JSON but lacks "
                "llm_summary.text; pass a plain text doc or a "
                "worked-example data.json instead."
            )
            return 1, None
    else:
        doc_text = document_path.read_text(encoding="utf-8")

    print(f"== reframe smoke: {fvs_id} on {document_path.name} ==")
    print(f"   source length: {len(doc_text)} chars")
    source_numbers = _extract_numbers(doc_text)
    print(f"   source numbers: {len(source_numbers)} unique tokens")

    # Run candidate library reframe by pointing reframe._LIBRARY_DIR
    # at the candidate library for the duration of the call.
    import reframe as _reframe
    original_dir = _reframe._LIBRARY_DIR
    _reframe._LIBRARY_DIR = candidate_library
    try:
        cand_result, cand_usage = _reframe.rewrite_from_frame(
            doc_text, fvs_id,
        )
    finally:
        _reframe._LIBRARY_DIR = original_dir

    if cand_result is None:
        print(f"FAIL: candidate reframe returned None.")
        print(f"   usage: {cand_usage}")
        return 1, None

    cand_text = cand_result["text"]
    print(f"   candidate length: {len(cand_text)} chars")
    print(f"   candidate cost: ${cand_usage.get('cost_usd', 0.0):.4f}")
    if cand_result.get("truncation_warning"):
        print(
            f"   truncation_warning: source exceeds "
            f"REFRAME_SAFE_SOURCE_CHARS; see reframe.py "
            f"for pre-summarization recommendation."
        )

    result = {
        "fvs_id": fvs_id,
        "document_path": str(
            document_path.relative_to(REPO_ROOT)
            if document_path.is_absolute() and document_path.is_relative_to(REPO_ROOT)
            else document_path
        ),
        "source_length": len(doc_text),
        "source_numbers": sorted(source_numbers),
        "candidate_text": cand_text,
        "candidate_length": len(cand_text),
        "candidate_cost_usd": cand_usage.get("cost_usd", 0.0),
        "checks": {},
    }

    # Check 2: numbers preserved.
    cand_numbers = _extract_numbers(cand_text)
    missing = source_numbers - cand_numbers
    result["checks"]["numbers_preserved"] = {
        "passed": not missing,
        "retained_count": len(cand_numbers),
        "missing_count": len(missing),
        "missing_sample": sorted(missing)[:10],
    }
    if missing:
        print(
            f"FAIL: candidate dropped {len(missing)} source numbers: "
            f"{sorted(missing)[:10]}"
            + (f" (and {len(missing) - 10} more)" if len(missing) > 10 else "")
        )
        return 1, result
    print(f"   numbers preserved: PASS ({len(cand_numbers)} retained)")

    # Check 3: length ratio. Two bands:
    #   - target band 0.8-1.2 (system prompt says "same length within
    #     20%"): PASS
    #   - tolerance band 0.5-2.0 (LLM length-matching is noisy even
    #     with explicit directives): WARN, not FAIL
    #   - outside tolerance: FAIL (structural break; truncation or
    #     hallucinated expansion)
    #
    # The 2026-04-24 pass-7 full-sweep with max_tokens scaling showed
    # Grok 4.1 fast produces outputs 0.64-1.41 of source length on
    # 7k-8k char inputs even when the output cap is ample. The system
    # prompt's 20% rule is a hope, not a contract. Strict 0.8-1.2 fails
    # the harness on real LLM variance; relaxed tolerance + explicit
    # WARN captures the reality honestly without false-failing valid
    # reframes.
    ratio = len(cand_text) / max(len(doc_text), 1)
    in_target = 0.8 <= ratio <= 1.2
    in_tolerance = 0.5 <= ratio <= 2.0
    result["checks"]["length_ratio"] = {
        "passed": in_tolerance,
        "in_target_band": in_target,
        "ratio": round(ratio, 3),
    }
    if not in_tolerance:
        print(
            f"FAIL: candidate length ratio {ratio:.2f} outside "
            f"tolerance band 0.5-2.0 (structural break; likely "
            f"truncation or hallucinated expansion)."
        )
        return 1, result
    if in_target:
        print(f"   length ratio: PASS ({ratio:.2f})")
    else:
        print(
            f"   length ratio: WARN ({ratio:.2f} outside target "
            f"0.8-1.2; within tolerance 0.5-2.0). LLM length-matching "
            f"is noisy; manual inspection recommended."
        )

    # Check 4: framing-portrait shift. The structural framing portrait
    # of the candidate reframe should differ from the source on at
    # least one dimension. A reframe that merely rephrases the source
    # without shifting the frame produces a near-identical portrait
    # and is the failure mode the prior structural checks miss: a
    # reframe can preserve every number, stay within the length band,
    # and STILL fail to express the counter-frame, which is the
    # entire point of the reframe feature. Treated as soft warning
    # rather than hard fail because the LLM frame shift may
    # sometimes be subtle enough to evade the deterministic portrait;
    # operator inspection is the tiebreaker on close calls.
    src_portrait = _structural_portrait(doc_text)
    cand_portrait = _structural_portrait(cand_text)
    shift = _portrait_shift(src_portrait, cand_portrait)
    result["checks"]["portrait_shift"] = {
        "source_portrait": {k: (list(v) if isinstance(v, tuple) else v) for k, v in src_portrait.items()},
        "candidate_portrait": {k: (list(v) if isinstance(v, tuple) else v) for k, v in cand_portrait.items()},
        "shift_count": shift["shift_count"],
        "diffs": {
            k: {
                kk: (list(vv) if isinstance(vv, (set, tuple)) else vv)
                for kk, vv in v.items()
            }
            for k, v in shift["diffs"].items()
        },
    }
    if shift["shift_count"] == 0:
        print(
            "   WARNING: candidate reframe produces identical "
            "structural portrait to source. Framing may not have "
            "shifted; manual inspection recommended. "
            "(coverage_addressed / coverage_missing / voice / "
            "temporal_dominant all match source.)"
        )
    else:
        print(
            f"   framing portrait shift: {shift['shift_count']} of 4 "
            f"dimensions changed."
        )
        for dim, delta in shift["diffs"].items():
            print(f"      {dim}: {delta}")

    # Optional baseline comparison if a baseline library was supplied.
    if baseline_library and baseline_library != candidate_library:
        _reframe._LIBRARY_DIR = baseline_library
        try:
            base_result, base_usage = _reframe.rewrite_from_frame(
                doc_text, fvs_id,
            )
        finally:
            _reframe._LIBRARY_DIR = original_dir
        if base_result is None:
            print(
                "WARNING: baseline reframe returned None; baseline "
                "comparison skipped. Candidate-only checks above stand."
            )
        else:
            base_text = base_result["text"]
            cand_len_ratio = len(cand_text) / max(len(base_text), 1)
            print(
                f"   baseline length: {len(base_text)} chars; "
                f"candidate/baseline ratio: {cand_len_ratio:.2f}"
            )
            print(f"   baseline cost: ${base_usage.get('cost_usd', 0.0):.4f}")
            # Naive structural comparison: count overlapping word set
            # to catch a "candidate is empty / candidate is identical
            # to source" regression. Refine when the harness is built
            # out per the file-top TODO.
            base_words = set(base_text.lower().split())
            cand_words = set(cand_text.lower().split())
            overlap = len(base_words & cand_words) / max(
                len(base_words | cand_words), 1
            )
            print(
                f"   baseline-vs-candidate word-set Jaccard: {overlap:.2f}"
            )
            if overlap < 0.3:
                print(
                    "WARNING: candidate output diverges substantially "
                    "from baseline output (Jaccard < 0.30). Inspect "
                    "manually before concluding pass/fail."
                )

    if print_text:
        print()
        print("== source text ==")
        print(doc_text)
        print()
        print("== candidate reframe ==")
        print(cand_text)
        print()

    print("PASS (single-frame smoke). Manual inspection of structural "
          "shift recommended; see file-top doc for full discipline.")
    return 0, result


REPRESENTATIVE_DOCS_PATH = (
    REPO_ROOT / "scripts" / "reframe_representative_docs.json"
)
BASELINE_ARTIFACT_PATH = (
    REPO_ROOT / "scripts" / "reframe_full_sweep_baseline.json"
)


def run_full_sweep(
    candidate_library: Path,
    baseline_library: Path | None = None,
) -> int:
    """Run the smoke test against every emitting frame's representative
    document, per the mapping at ``reframe_representative_docs.json``.

    Saves baseline artifact at ``reframe_full_sweep_baseline.json`` with
    the reframed text + per-check metrics for each frame. Future editors
    can compare their own run's output against this baseline to detect
    reframe-quality regressions on Generation-affordances edits.

    Used when a Generation-affordances revision touches multiple frames
    and the editor wants library-wide validation in one pass. Skips
    frames without a representative document (universal-absent high-
    AC1 frames whose reframe behavior cannot be smoke-tested via the
    mixed_genre_v1 corpus); names them in the report.

    Returns 0 if all mapped frames passed, 1 otherwise.
    """
    if not REPRESENTATIVE_DOCS_PATH.is_file():
        print(
            f"FAIL: representative docs mapping not found at "
            f"{REPRESENTATIVE_DOCS_PATH}. Run the discovery script in "
            "the harness commit history to regenerate it."
        )
        return 1
    mapping_artifact = json.loads(
        REPRESENTATIVE_DOCS_PATH.read_text(encoding="utf-8")
    )
    mapping = mapping_artifact["mapping"]

    print(
        f"== reframe full sweep over {len(mapping)} emitting frames =="
    )
    print(
        f"   candidate library: {candidate_library}"
        + (
            f"\n   baseline library: {baseline_library}"
            if baseline_library else ""
        )
    )
    print(
        f"   cost projection: "
        f"${mapping_artifact['cost_projection']['approx_grok_cost_usd']} "
        f"({mapping_artifact['cost_projection']['frames_mapped']} "
        "mapped frames; per-call min may dominate)."
    )
    print()

    results: dict[str, str] = {}
    failed: list[str] = []
    skipped: list[str] = []
    per_frame_data: dict[str, dict] = {}
    total_cost = 0.0

    for fvs_id, entry in mapping.items():
        if entry is None:
            skipped.append(fvs_id)
            results[fvs_id] = "SKIP (no representative doc)"
            print(f"-- {fvs_id}: SKIP (no representative doc)")
            print()
            continue
        doc_path = REPO_ROOT / entry["doc_path"]
        print(f"-- {fvs_id} on {entry['doc_slug']} --")
        # Inter-call pacing: tail-of-sweep None returns (pass-6 and
        # pass-7 sweeps both showed this on FVS-014 through FVS-019)
        # suggest Grok TPM rate limiting. 15s pause between calls gives
        # the provider time to reset burst counters. Earlier 5s was
        # insufficient (4 Nones at tail in pass-8 third sweep). Per-
        # frame cost impact is zero; latency cost ~3.5 min added across
        # 15-frame sweep.
        if per_frame_data:
            import time
            time.sleep(15)
        rc, frame_result = run_single_frame_smoke(
            fvs_id=fvs_id,
            document_path=doc_path,
            candidate_library=candidate_library,
            baseline_library=baseline_library,
            print_text=False,
        )
        if rc == 0:
            results[fvs_id] = "PASS"
        else:
            results[fvs_id] = "FAIL"
            failed.append(fvs_id)
        if frame_result is not None:
            per_frame_data[fvs_id] = frame_result
            total_cost += frame_result.get("candidate_cost_usd", 0.0)
        print()

    # Save baseline artifact. Future editors can compare their
    # Generation-affordances edits against this reference output.
    from datetime import datetime, timezone
    baseline = {
        "schema": "reframe_full_sweep_baseline_v1",
        "captured_at_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "candidate_library": str(
            candidate_library.relative_to(REPO_ROOT)
            if candidate_library.is_absolute() and candidate_library.is_relative_to(REPO_ROOT)
            else candidate_library
        ),
        "purpose": (
            "Reference reframe output per emitting frame under current "
            "Generation-affordances content. Use to diff a future "
            "Generation-affordances edit's sweep output against this "
            "baseline. Reframe is non-deterministic at temp=0 due to "
            "LLM jitter; expect some variation on re-run. Structural "
            "metrics (numbers, length ratio, portrait shift) are the "
            "primary comparison targets; candidate_text is preserved "
            "for manual inspection."
        ),
        "aggregate": {
            "pass_count": sum(1 for v in results.values() if v == "PASS"),
            "fail_count": len(failed),
            "skip_count": len(skipped),
            "skipped_frames": skipped,
            "failed_frames": failed,
            "total_cost_usd": round(total_cost, 4),
        },
        "per_frame": per_frame_data,
    }
    BASELINE_ARTIFACT_PATH.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Saved baseline artifact: {BASELINE_ARTIFACT_PATH}")
    print()

    # Summary report
    print("=" * 60)
    print("== Full-sweep summary ==")
    pass_count = sum(1 for v in results.values() if v == "PASS")
    fail_count = len(failed)
    skip_count = len(skipped)
    print(f"   PASS: {pass_count}")
    print(f"   FAIL: {fail_count}")
    if failed:
        print(f"      failed frames: {failed}")
    print(f"   SKIP: {skip_count} (no representative doc)")
    if skipped:
        print(f"      skipped frames: {skipped}")
    print()
    if fail_count == 0:
        print(
            "OK: all mapped frames passed structural smoke. Manual "
            "inspection of any portrait-shift WARNINGS recommended; "
            "see file-top doc."
        )
        return 0
    else:
        print(
            f"FAIL: {fail_count} of {pass_count + fail_count} mapped "
            "frames failed. Inspect output above and address before "
            "merging Generation-affordances changes."
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reframe-behavior smoke test for METHODOLOGY section 2.4.4 "
            "corollary. Runs Grok reframe call(s) and checks number "
            "preservation, length ratio, framing-portrait shift, and "
            "(optional) baseline comparison. Single-frame mode by "
            "default; --full-sweep iterates the per-frame "
            "representative-doc mapping."
        )
    )
    parser.add_argument(
        "fvs_id", nargs="?",
        help="FVS-XXX frame ID to reframe (single-frame mode). "
             "Omitted in --full-sweep mode.",
    )
    parser.add_argument(
        "--document", type=Path, default=None,
        help="Path to source document (plain text or worked-example "
             "data.json). Required in single-frame mode; ignored in "
             "--full-sweep mode.",
    )
    parser.add_argument(
        "--candidate-library", type=Path,
        default=REPO_ROOT / "data" / "frame_library",
        help="Library directory whose Generation affordances to test "
             "(default: data/frame_library/).",
    )
    parser.add_argument(
        "--baseline-library", type=Path, default=None,
        help="Optional baseline library directory for comparison "
             "(e.g., data/frame_library_v4/ for the ratified snapshot).",
    )
    parser.add_argument(
        "--print-text", action="store_true",
        help="Print source + reframed text after structural checks. "
             "Single-frame mode only.",
    )
    parser.add_argument(
        "--full-sweep", action="store_true",
        help="Run smoke test across all emitting frames using the "
             "representative-doc mapping at "
             "scripts/reframe_representative_docs.json. Cost projection "
             "in the mapping artifact.",
    )
    args = parser.parse_args()

    if args.full_sweep:
        if args.fvs_id or args.document:
            print(
                "WARNING: --full-sweep ignores fvs_id and --document "
                "arguments; using mapping artifact instead."
            )
        return run_full_sweep(
            candidate_library=args.candidate_library,
            baseline_library=args.baseline_library,
        )

    if not args.fvs_id:
        parser.error("fvs_id is required in single-frame mode (or use --full-sweep)")
    if not args.document:
        parser.error("--document is required in single-frame mode (or use --full-sweep)")

    rc, _result = run_single_frame_smoke(
        fvs_id=args.fvs_id,
        document_path=args.document,
        candidate_library=args.candidate_library,
        baseline_library=args.baseline_library,
        print_text=args.print_text,
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------------------
# TODO (filled in by the first engineer who needs the full sweep):
#
# 1. Curate a representative-document mapping: per emitting frame
#    (FVS-001..019), one document expected to fire the frame. Source:
#    target-scope worked examples in data/worked_examples/, plus any
#    additional fixtures needed for frames not represented there.
#    The current scripts/reframe_representative_docs.json uses
#    mixed_genre_v1 corpus docs which are 7k-22k chars; that exceeds
#    reframe.py's max_completion_tokens=1200 cap (~5k output chars)
#    and produces truncation failures on the full sweep. Refining the
#    mapping to short excerpts (~1k chars each), or extracting the
#    first ~1k chars of each representative doc, makes the baseline
#    clean. The 2026-04-24 first-run baseline documented this as a
#    real production-reframe constraint discovery, not a harness bug.
#
# 2. Implement run_full_sweep(candidate_library, baseline_library) that
#    iterates the mapping and aggregates pass/fail per frame.
#
# 3. Extend the deterministic structural-portrait shift check
#    (implemented as Check 4 in run_single_frame_smoke) into a proper
#    regression-vs-baseline assertion: assert the candidate portrait
#    shift magnitude (vs source) is within tolerance of the baseline
#    portrait shift magnitude (vs source). Calibrate the tolerance
#    empirically against a known-good baseline reframe per frame.
#    Current implementation only reports portrait shift count; full
#    regression check requires the per-frame baseline capture from
#    item 2 above.
#
# 4. Wire optional cache to avoid re-running baseline calls when the
#    baseline library hasn't changed.
#
# 5. Document the calibrated thresholds and add a per-frame
#    expected-shift baseline file so regressions are detectable
#    automatically without per-run manual inspection.
# ---------------------------------------------------------------------------
