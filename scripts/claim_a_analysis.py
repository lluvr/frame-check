#!/usr/bin/env python3
"""Claim A pre-registered analysis script per CLAIM_A_PROTOCOL_v1.md sections 6.4 + 7.

Consumes:
- treatment_mapping.SEALED.json (output_uuid -> case_id, treatment)
- grading_records.json (output_uuid -> rubric_scores, grader_treatment_suspicion, etc.)

Produces:
- claim_a_results.json (machine-readable analysis output)
- claim_a_results.md (human-readable summary table)

Pre-registered before data collection per protocol section 7.5. No retroactive
changes to analysis logic after data collection begins. Analysis applies
section 1.2 falsifiability conditions plus section 7.4 sensitivity analyses.

Usage:
    python scripts/claim_a_analysis.py \\
        --mapping data/claim_a/analysis_outputs/treatment_mapping.SEALED.json \\
        --grading data/claim_a/grading/grading_records.json \\
        --output-dir data/claim_a/results/
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


RUBRIC_DIMENSIONS = [
    "information_surfaced",
    "blind_spots_caught",
    "action_readiness",
    "time_to_utility",
]

# Protocol section 1.2 falsifiability thresholds.
WIN_THRESHOLD = 0.5  # paired difference required to call a dimension "won"
LOSS_THRESHOLD = -0.5  # paired difference at or below this is a "loss" on that dimension
PASS_DIMENSIONS_REQUIRED = 3  # how many dimensions chain must win to Pass
PASS_OVERALL_LEAD = 1.0  # alternative Pass if overall mean lead exceeds this

# Protocol section 7.4 sensitivity thresholds.
LENGTH_RATIO_TRIGGER = 1.8  # if chain output is this much longer than single, run length-normalized
GRADER_DETECTION_BLIND_FAILURE_THRESHOLD = 0.70  # grader detection rate above this = blinding failed


def paired_t_test(differences: list[float]) -> dict[str, float]:
    """Two-sided paired t-test on a list of paired differences."""
    n = len(differences)
    if n < 2:
        return {"n": n, "mean": 0.0, "std": 0.0, "t": 0.0, "p_two_sided": 1.0, "cohens_d": 0.0}
    mean = sum(differences) / n
    variance = sum((d - mean) ** 2 for d in differences) / (n - 1)
    std = math.sqrt(variance)
    if std == 0:
        return {"n": n, "mean": mean, "std": 0.0, "t": float("inf"), "p_two_sided": 0.0, "cohens_d": 0.0}
    se = std / math.sqrt(n)
    t = mean / se
    df = n - 1
    # Survival function approximation for two-sided p-value (Student's t).
    # Use the relation between t-distribution and the regularized incomplete beta function.
    p_two_sided = student_t_two_sided_p(t, df)
    cohens_d = mean / std
    return {"n": n, "mean": mean, "std": std, "t": t, "p_two_sided": p_two_sided, "cohens_d": cohens_d}


def student_t_two_sided_p(t: float, df: int) -> float:
    """Compute two-sided p-value for Student's t-distribution.

    Uses the regularized incomplete beta function relationship:
    p_two_sided = I_{df / (df + t^2)}(df/2, 1/2)
    """
    x = df / (df + t * t)
    return regularized_incomplete_beta(x, df / 2.0, 0.5)


def regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta function I_x(a, b). Pure-Python; no scipy dependency."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * beta_continued_fraction(x, a, b) / a
    return 1.0 - bt * beta_continued_fraction(1.0 - x, b, a) / b


def beta_continued_fraction(x: float, a: float, b: float, max_iter: int = 200, eps: float = 3e-7) -> float:
    """Continued-fraction evaluation for incomplete beta function."""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    return h


def load_data(mapping_path: Path, grading_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    grading = json.loads(grading_path.read_text(encoding="utf-8"))
    return mapping, grading


def join_data(
    mapping: list[dict[str, Any]],
    grading: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join mapping (output_uuid -> case_id, treatment) with grading records."""
    mapping_by_uuid = {m["output_uuid"]: m for m in mapping}
    joined = []
    for g in grading:
        uuid = g["output_uuid"]
        if uuid not in mapping_by_uuid:
            print(f"WARN: grading record for unknown output_uuid {uuid}; skipping")
            continue
        m = mapping_by_uuid[uuid]
        joined.append(
            {
                "output_uuid": uuid,
                "case_id": m["case_id"],
                "treatment": m["treatment"],
                "rubric_scores": g["rubric_scores"],
                "output_word_count": g.get("output_word_count", 0),
                "grader_treatment_suspicion": g.get("grader_treatment_suspicion", "unsure"),
                "grader_treatment_confidence": g.get("grader_treatment_confidence", 0),
                "outcome_memory_flag": g.get("outcome_memory_flag", False),
                "notes": g.get("notes", ""),
            }
        )
    return joined


def compute_paired_differences(
    joined: list[dict[str, Any]],
) -> tuple[dict[str, list[float]], list[str]]:
    """For each case, compute chain - single_frame paired differences per dimension."""
    by_case = defaultdict(dict)  # case_id -> {treatment: rubric_scores}
    for j in joined:
        by_case[j["case_id"]][j["treatment"]] = j["rubric_scores"]

    paired_diffs: dict[str, list[float]] = {dim: [] for dim in RUBRIC_DIMENSIONS}
    paired_diffs["mean_of_dimensions"] = []
    used_cases: list[str] = []
    for case_id, treatments in sorted(by_case.items()):
        if "single_frame" not in treatments or "adversarial_chain" not in treatments:
            print(f"WARN: case {case_id} missing one or both treatments; excluding from paired analysis")
            continue
        sf = treatments["single_frame"]
        ch = treatments["adversarial_chain"]
        case_diffs = []
        for dim in RUBRIC_DIMENSIONS:
            d = ch[dim] - sf[dim]
            paired_diffs[dim].append(d)
            case_diffs.append(d)
        paired_diffs["mean_of_dimensions"].append(sum(case_diffs) / len(case_diffs))
        used_cases.append(case_id)
    return paired_diffs, used_cases


def apply_falsifiability(paired_diffs: dict[str, list[float]]) -> dict[str, Any]:
    """Apply protocol section 1.2 Pass / Mixed / Fail decision rule."""
    per_dim_means = {dim: (sum(diffs) / len(diffs) if diffs else 0.0) for dim, diffs in paired_diffs.items() if dim != "mean_of_dimensions"}
    overall_mean = sum(paired_diffs["mean_of_dimensions"]) / len(paired_diffs["mean_of_dimensions"]) if paired_diffs["mean_of_dimensions"] else 0.0

    wins = sum(1 for dim in RUBRIC_DIMENSIONS if per_dim_means[dim] >= WIN_THRESHOLD)
    losses = sum(1 for dim in RUBRIC_DIMENSIONS if per_dim_means[dim] <= LOSS_THRESHOLD)

    if losses >= 1:
        verdict = "Fail"
        reason = f"Chain has {losses} dimension loss(es) (paired diff <= {LOSS_THRESHOLD})"
    elif wins == 0:
        verdict = "Fail"
        reason = "Chain wins on 0 of 4 dimensions"
    elif wins >= PASS_DIMENSIONS_REQUIRED or overall_mean >= PASS_OVERALL_LEAD:
        verdict = "Pass"
        if wins >= PASS_DIMENSIONS_REQUIRED:
            reason = f"Chain wins on {wins} of 4 dimensions (>= {PASS_DIMENSIONS_REQUIRED} required)"
        else:
            reason = f"Overall mean lead {overall_mean:.3f} >= {PASS_OVERALL_LEAD}"
    else:
        verdict = "Mixed"
        reason = f"Chain wins on {wins} of 4 dimensions (between Pass and Fail)"

    return {
        "verdict": verdict,
        "reason": reason,
        "per_dimension_mean_diff": per_dim_means,
        "overall_mean_diff": overall_mean,
        "wins": wins,
        "losses": losses,
    }


def length_sensitivity(joined: list[dict[str, Any]]) -> dict[str, Any]:
    """Protocol section 7.4 length-confound sensitivity."""
    lengths_by_treatment = defaultdict(list)
    for j in joined:
        lengths_by_treatment[j["treatment"]].append(j["output_word_count"])
    sf_lengths = lengths_by_treatment.get("single_frame", [])
    ch_lengths = lengths_by_treatment.get("adversarial_chain", [])
    sf_mean = sum(sf_lengths) / len(sf_lengths) if sf_lengths else 0
    ch_mean = sum(ch_lengths) / len(ch_lengths) if ch_lengths else 0
    ratio = ch_mean / sf_mean if sf_mean > 0 else 0
    return {
        "single_frame_mean_words": sf_mean,
        "chain_mean_words": ch_mean,
        "chain_to_single_ratio": ratio,
        "length_confound_triggered": ratio > LENGTH_RATIO_TRIGGER,
        "trigger_threshold": LENGTH_RATIO_TRIGGER,
    }


def length_normalized_analysis(
    joined: list[dict[str, Any]],
    paired_diffs: dict[str, list[float]],
) -> dict[str, Any]:
    """If length-confound triggered, recompute analysis on rubric points per 100 words."""
    by_case = defaultdict(dict)
    for j in joined:
        wc = max(j["output_word_count"], 1)
        normalized = {dim: (j["rubric_scores"][dim] / wc) * 100 for dim in RUBRIC_DIMENSIONS}
        by_case[j["case_id"]][j["treatment"]] = normalized

    normalized_diffs: dict[str, list[float]] = {dim: [] for dim in RUBRIC_DIMENSIONS}
    normalized_diffs["mean_of_dimensions"] = []
    for case_id, treatments in by_case.items():
        if "single_frame" not in treatments or "adversarial_chain" not in treatments:
            continue
        sf = treatments["single_frame"]
        ch = treatments["adversarial_chain"]
        case_diffs = []
        for dim in RUBRIC_DIMENSIONS:
            d = ch[dim] - sf[dim]
            normalized_diffs[dim].append(d)
            case_diffs.append(d)
        normalized_diffs["mean_of_dimensions"].append(sum(case_diffs) / len(case_diffs))
    return {
        "per_dimension_mean_normalized_diff": {
            dim: (sum(d) / len(d) if d else 0.0) for dim, d in normalized_diffs.items()
        },
        "overall_normalized_mean": sum(normalized_diffs["mean_of_dimensions"]) / len(normalized_diffs["mean_of_dimensions"]) if normalized_diffs["mean_of_dimensions"] else 0.0,
    }


def grader_detection_sensitivity(joined: list[dict[str, Any]]) -> dict[str, Any]:
    """Protocol section 7.4 stylistic-leak sensitivity."""
    correct = 0
    incorrect = 0
    unsure = 0
    confidence_when_correct = []
    for j in joined:
        suspicion = j.get("grader_treatment_suspicion", "unsure")
        if suspicion == "unsure":
            unsure += 1
        elif suspicion == j["treatment"]:
            correct += 1
            confidence_when_correct.append(j.get("grader_treatment_confidence", 0))
        else:
            incorrect += 1
    total_guessed = correct + incorrect
    detection_rate = (correct / total_guessed) if total_guessed > 0 else 0
    return {
        "correct_guesses": correct,
        "incorrect_guesses": incorrect,
        "unsure": unsure,
        "detection_rate": detection_rate,
        "blinding_failed": detection_rate > GRADER_DETECTION_BLIND_FAILURE_THRESHOLD,
        "blinding_failure_threshold": GRADER_DETECTION_BLIND_FAILURE_THRESHOLD,
    }


def per_source_breakdown(joined: list[dict[str, Any]], paired_diffs_by_source: dict[str, dict[str, list[float]]]) -> dict[str, Any]:
    """Per-source paired-difference summary."""
    summary = {}
    for source, diffs in paired_diffs_by_source.items():
        summary[source] = {
            dim: (sum(d) / len(d) if d else 0.0) for dim, d in diffs.items() if dim != "mean_of_dimensions"
        }
        if diffs.get("mean_of_dimensions"):
            summary[source]["overall_mean"] = sum(diffs["mean_of_dimensions"]) / len(diffs["mean_of_dimensions"])
    return summary


def infer_source(case_id: str) -> str:
    """Infer source from case_id prefix (a_, b_, c_)."""
    prefix = case_id.split("_", 1)[0].lower() if "_" in case_id else ""
    if prefix == "a":
        return "A"
    if prefix == "b":
        return "B"
    if prefix == "c":
        return "C"
    return "unknown"


def compute_all(mapping_path: Path, grading_path: Path) -> dict[str, Any]:
    mapping, grading = load_data(mapping_path, grading_path)
    joined = join_data(mapping, grading)
    paired_diffs, used_cases = compute_paired_differences(joined)

    # Primary analysis
    primary_t = {dim: paired_t_test(diffs) for dim, diffs in paired_diffs.items()}
    falsifiability = apply_falsifiability(paired_diffs)

    # Sensitivity: length
    length_summary = length_sensitivity(joined)
    length_normalized = (
        length_normalized_analysis(joined, paired_diffs)
        if length_summary["length_confound_triggered"]
        else None
    )

    # Sensitivity: grader detection (blinding integrity)
    grader_summary = grader_detection_sensitivity(joined)

    # Per-source breakdown
    paired_diffs_by_source: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {dim: [] for dim in RUBRIC_DIMENSIONS + ["mean_of_dimensions"]}
    )
    by_case = defaultdict(dict)
    for j in joined:
        by_case[j["case_id"]][j["treatment"]] = j["rubric_scores"]
    for case_id in used_cases:
        source = infer_source(case_id)
        treatments = by_case[case_id]
        sf = treatments["single_frame"]
        ch = treatments["adversarial_chain"]
        case_diffs = []
        for dim in RUBRIC_DIMENSIONS:
            d = ch[dim] - sf[dim]
            paired_diffs_by_source[source][dim].append(d)
            case_diffs.append(d)
        paired_diffs_by_source[source]["mean_of_dimensions"].append(sum(case_diffs) / len(case_diffs))
    source_summary = per_source_breakdown(joined, paired_diffs_by_source)

    # Sensitivity: with and without Source B (hindsight check)
    diffs_excl_b = {dim: [] for dim in RUBRIC_DIMENSIONS + ["mean_of_dimensions"]}
    for case_id in used_cases:
        if infer_source(case_id) == "B":
            continue
        treatments = by_case[case_id]
        sf = treatments["single_frame"]
        ch = treatments["adversarial_chain"]
        case_diffs = []
        for dim in RUBRIC_DIMENSIONS:
            d = ch[dim] - sf[dim]
            diffs_excl_b[dim].append(d)
            case_diffs.append(d)
        diffs_excl_b["mean_of_dimensions"].append(sum(case_diffs) / len(case_diffs))
    falsifiability_excl_b = apply_falsifiability(diffs_excl_b) if diffs_excl_b["mean_of_dimensions"] else None

    return {
        "n_paired_cases": len(used_cases),
        "used_cases": used_cases,
        "primary_analysis": {
            "per_dimension_t_tests": primary_t,
            "falsifiability": falsifiability,
        },
        "sensitivity": {
            "length_summary": length_summary,
            "length_normalized": length_normalized,
            "grader_detection": grader_summary,
            "per_source_breakdown": source_summary,
            "falsifiability_excluding_source_b": falsifiability_excl_b,
        },
    }


def write_markdown_summary(results: dict[str, Any], output_path: Path) -> None:
    lines = []
    fal = results["primary_analysis"]["falsifiability"]
    lines.append("# Claim A Analysis Results")
    lines.append("")
    lines.append(f"**Verdict:** {fal['verdict']}")
    lines.append(f"**Reason:** {fal['reason']}")
    lines.append(f"**Cases analyzed (paired):** {results['n_paired_cases']}")
    lines.append("")
    lines.append("## Primary Analysis: Per-Dimension Paired Differences (chain - single_frame)")
    lines.append("")
    lines.append("| Dimension | Mean Diff | Std | t | p (two-sided) | Cohen's d | n |")
    lines.append("|---|---|---|---|---|---|---|")
    for dim in RUBRIC_DIMENSIONS + ["mean_of_dimensions"]:
        t = results["primary_analysis"]["per_dimension_t_tests"][dim]
        lines.append(
            f"| {dim} | {t['mean']:.3f} | {t['std']:.3f} | {t['t']:.3f} | {t['p_two_sided']:.4f} | {t['cohens_d']:.3f} | {t['n']} |"
        )
    lines.append("")
    lines.append("## Sensitivity: Output Length")
    ls = results["sensitivity"]["length_summary"]
    lines.append(
        f"- Single-frame mean words: {ls['single_frame_mean_words']:.1f}"
    )
    lines.append(f"- Chain mean words: {ls['chain_mean_words']:.1f}")
    lines.append(f"- Ratio (chain / single): {ls['chain_to_single_ratio']:.2f}")
    lines.append(f"- Length-confound triggered: {ls['length_confound_triggered']}")
    if results["sensitivity"]["length_normalized"]:
        ln = results["sensitivity"]["length_normalized"]
        lines.append("")
        lines.append("### Length-Normalized Analysis (rubric points per 100 words)")
        for dim in RUBRIC_DIMENSIONS:
            lines.append(f"- {dim}: {ln['per_dimension_mean_normalized_diff'][dim]:.4f}")
        lines.append(f"- Overall normalized mean: {ln['overall_normalized_mean']:.4f}")
    lines.append("")
    lines.append("## Sensitivity: Blinding Integrity (Grader Detection)")
    gs = results["sensitivity"]["grader_detection"]
    lines.append(f"- Correct guesses: {gs['correct_guesses']}")
    lines.append(f"- Incorrect guesses: {gs['incorrect_guesses']}")
    lines.append(f"- Unsure: {gs['unsure']}")
    lines.append(f"- Detection rate: {gs['detection_rate']:.2f}")
    lines.append(f"- Blinding failed (rate > {gs['blinding_failure_threshold']}): {gs['blinding_failed']}")
    lines.append("")
    lines.append("## Sensitivity: Per-Source Breakdown")
    for source, summary in results["sensitivity"]["per_source_breakdown"].items():
        lines.append(f"### Source {source}")
        for dim in RUBRIC_DIMENSIONS:
            if dim in summary:
                lines.append(f"- {dim}: {summary[dim]:.3f}")
        if "overall_mean" in summary:
            lines.append(f"- Overall mean: {summary['overall_mean']:.3f}")
        lines.append("")
    if results["sensitivity"]["falsifiability_excluding_source_b"]:
        feb = results["sensitivity"]["falsifiability_excluding_source_b"]
        lines.append("## Sensitivity: Verdict Excluding Source B")
        lines.append(f"- Verdict (without Source B cases): {feb['verdict']}")
        lines.append(f"- Reason: {feb['reason']}")
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mapping", type=Path, required=True, help="Path to treatment_mapping.SEALED.json")
    parser.add_argument("--grading", type=Path, required=True, help="Path to grading_records.json")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for results output")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = compute_all(args.mapping, args.grading)

    json_path = args.output_dir / "claim_a_results.json"
    md_path = args.output_dir / "claim_a_results.md"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_markdown_summary(results, md_path)

    print(f"Verdict: {results['primary_analysis']['falsifiability']['verdict']}")
    print(f"Reason: {results['primary_analysis']['falsifiability']['reason']}")
    print(f"Results: {json_path}")
    print(f"Summary: {md_path}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
