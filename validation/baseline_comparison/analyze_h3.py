"""H3 reproducibility analyzer for the baseline_comparison protocol.

Mechanically computes Jaccard distance on named-pattern sets across
runs of each side (Frame Check + LLM-baseline). The H3 hypothesis
is purely measurement-driven; no human rater required.

Pre-registered claims (PROTOCOL_v1 §"Hypothesis" H3):
  - Frame Check returns byte-identical structured output for byte-
    identical input across runs (deterministic). Pre-registered:
    distance = 0.
  - LLM-baseline returns materially-different framing analyses
    across runs at temperature > 0. Pre-registered: distance > 0.

Inputs: a results directory produced by run_baseline.py with
--call-llm --runs-per-side 5 (or higher).

Outputs: per-document H3 metric breakdown and an aggregate finding
suitable for inclusion in REPORT.md.

Usage:
  python3 validation/baseline_comparison/analyze_h3.py \\
      --results-dir /tmp/baseline-h3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from itertools import combinations
from pathlib import Path
from typing import Any


# Fields that legitimately vary across deterministic Frame Check runs:
# timestamps, latency measurements, anything wall-clock-tied. These
# are stripped before the byte-equality check on Frame Check side.
FRAME_CHECK_VOLATILE_PATHS = [
    "manifest.analysis_run_at",
    "provenance.analysis_run_at",
    "provenance.analysis_timestamp_utc",
    "provenance.analysis_latency_ms",
]


def _strip_volatile(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove the time/latency fields that legitimately vary across
    deterministic re-runs. Returns a copy."""
    copy = json.loads(json.dumps(payload, default=str))
    for path in FRAME_CHECK_VOLATILE_PATHS:
        node = copy
        parts = path.split(".")
        for p in parts[:-1]:
            if not isinstance(node, dict) or p not in node:
                node = None
                break
            node = node[p]
        if isinstance(node, dict):
            node.pop(parts[-1], None)
    return copy


def _frame_check_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(_strip_volatile(payload), sort_keys=True, default=str).encode()
    ).hexdigest()


def _extract_json_block(text: str) -> dict[str, Any] | None:
    """LLM responses sometimes wrap JSON in markdown fences. Extract
    the structured object."""
    # Try direct parse first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try fenced block.
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try to find the first { ... } block heuristically.
    start = text.find("{")
    if start >= 0:
        # Greedy: take the longest balanced-brace string starting at `{`.
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None
    return None


def _extract_named_pattern_set(llm_response_text: str) -> set[str]:
    """Build the set of named patterns the LLM surfaced in this run.
    Includes voice classification, addressed perspectives, detected
    pattern names, and absent pattern names. Order-independent set."""
    obj = _extract_json_block(llm_response_text)
    if obj is None:
        return set()
    items: set[str] = set()
    voice = obj.get("voice_classification") or obj.get("voice")
    if isinstance(voice, str):
        items.add(f"voice:{voice.lower().strip()}")

    perspectives = obj.get("analytical_perspectives") or obj.get("perspectives") or {}
    if isinstance(perspectives, dict):
        for cat, val in perspectives.items():
            present = (
                val.get("present") if isinstance(val, dict) else val
            )
            tag = "present" if present else "absent"
            items.add(f"perspective:{cat.lower().strip()}:{tag}")

    detected = obj.get("detected_framing_patterns") or obj.get("framing_patterns") or []
    if isinstance(detected, list):
        for entry in detected:
            name = entry.get("pattern") if isinstance(entry, dict) else entry
            if isinstance(name, str):
                items.add(f"detected:{name.strip().lower()}")

    absent = (
        obj.get("structurally_absent_framing_patterns")
        or obj.get("absent_patterns")
        or []
    )
    if isinstance(absent, list):
        for entry in absent:
            name = entry.get("pattern") if isinstance(entry, dict) else entry
            if isinstance(name, str):
                items.add(f"absent:{name.strip().lower()}")

    return items


def _jaccard_distance(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return 1.0 - (inter / union) if union > 0 else 0.0


def _frame_check_named_pattern_set(payload: dict[str, Any]) -> set[str]:
    """Build the equivalent named-pattern set from a Frame Check
    payload, for cross-side comparison context."""
    items: set[str] = set()
    an = payload.get("analysis", {})
    voice = an.get("voice", {}).get("classification")
    if voice:
        items.add(f"voice:{voice.lower().strip()}")
    cov = an.get("coverage", {})
    for cat in cov.get("addressed", []) or []:
        items.add(f"perspective:{cat.lower().strip()}:present")
    for cat in cov.get("missing", []) or []:
        items.add(f"perspective:{cat.lower().strip()}:absent")
    for m in an.get("frame_library_matches", []) or []:
        fid = m.get("fvs_id")
        if fid:
            items.add(f"detected:{fid.lower().strip()}")
    div = payload.get("divergence", {}) or {}
    for af in div.get("absent_frames", []) or []:
        fid = af.get("frame_id") or af.get("fvs_id")
        if fid:
            items.add(f"absent:{fid.lower().strip()}")
    return items


def analyze_doc(slug_dir: Path) -> dict[str, Any]:
    data_path = slug_dir / "data.json"
    data = json.loads(data_path.read_text())
    fc_runs = data.get("frame_check_runs", [])
    llm_runs = data.get("llm_baseline_runs", [])

    fc_hashes = [_frame_check_hash(p) for p in fc_runs]
    fc_distinct = len(set(fc_hashes))
    fc_pattern_sets = [_frame_check_named_pattern_set(p) for p in fc_runs]
    fc_pairwise = [
        _jaccard_distance(a, b) for a, b in combinations(fc_pattern_sets, 2)
    ]
    fc_mean_jaccard = sum(fc_pairwise) / len(fc_pairwise) if fc_pairwise else 0.0

    llm_pattern_sets: list[set[str]] = []
    llm_parse_failures = 0
    for run in llm_runs:
        text = run.get("raw_response_text") or ""
        items = _extract_named_pattern_set(text)
        if not items:
            llm_parse_failures += 1
        llm_pattern_sets.append(items)

    llm_pairwise = [
        _jaccard_distance(a, b) for a, b in combinations(llm_pattern_sets, 2)
    ]
    llm_mean_jaccard = sum(llm_pairwise) / len(llm_pairwise) if llm_pairwise else 0.0
    llm_max_jaccard = max(llm_pairwise) if llm_pairwise else 0.0
    llm_min_jaccard = min(llm_pairwise) if llm_pairwise else 0.0

    return {
        "slug": data["slug"],
        "frame_check": {
            "runs": len(fc_runs),
            "byte_identical_runs_after_stripping_timestamps": fc_distinct == 1,
            "distinct_post_strip_hashes": fc_distinct,
            "mean_pairwise_jaccard_distance": round(fc_mean_jaccard, 4),
            "named_pattern_sample_size": (
                len(fc_pattern_sets[0]) if fc_pattern_sets else 0
            ),
        },
        "llm_baseline": {
            "runs": len(llm_runs),
            "parse_failures": llm_parse_failures,
            "mean_pairwise_jaccard_distance": round(llm_mean_jaccard, 4),
            "min_pairwise_jaccard_distance": round(llm_min_jaccard, 4),
            "max_pairwise_jaccard_distance": round(llm_max_jaccard, 4),
            "named_pattern_set_sizes_per_run": [
                len(s) for s in llm_pattern_sets
            ],
        },
        "h3_pre_registered_outcome": {
            "frame_check_distance_zero": fc_mean_jaccard == 0.0,
            "llm_distance_above_zero": llm_mean_jaccard > 0.0,
            "outcome_consistent_with_pre_reg": (
                fc_mean_jaccard == 0.0 and llm_mean_jaccard > 0.0
            ),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, required=True)
    args = ap.parse_args()

    if not args.results_dir.is_dir():
        print(f"results dir not found: {args.results_dir}", file=sys.stderr)
        return 1

    findings = []
    for slug_dir in sorted(args.results_dir.iterdir()):
        if not slug_dir.is_dir():
            continue
        if not (slug_dir / "data.json").exists():
            continue
        findings.append(analyze_doc(slug_dir))

    print(json.dumps({"h3_findings": findings}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
