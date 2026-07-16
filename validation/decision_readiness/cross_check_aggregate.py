"""Cross-check the aggregate outlier findings against expert
ratings.

When the aggregate corpus findings identify an LLM as the outlier
on a dimension via median-distance computation, expert ratings
(when they arrive) provide an independent check: do experts also
rate that LLM as the most-different on that dimension?

Agreement between the aggregate's structural outlier and the
expert-derived outlier is the load-bearing validation signal for
the cross-LLM analysis. This script computes that agreement,
when ratings exist; it runs cleanly with no ratings (reports
"awaiting ratings" rather than crashing).

The cross-check is the bridge between the descriptive aggregate
(corpus-state findings) and the inferential validation (expert
ratings as ground truth). When ratings arrive, this script's
output becomes the published validation finding.

Reads:
  results/{date-hash}/aggregate.json  (latest)
  ratings/{doc_id}/{rater}.yaml       (all)

Writes:
  results/{date-hash}/cross_check.json
  results/{date-hash}/cross_check.md

Run AFTER aggregate_corpus_findings.py (which writes the
aggregate the cross-check reads from).
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
CORPUS_DIR = HERE / "corpus"
RATINGS_DIR = HERE / "ratings"
RESULTS_DIR = HERE / "results"


DIMENSIONS = [
    "coverage",
    "calibration",
    "evidence",
    "robustness",
    "counterfactual",
]


def _load_yaml(path: Path):
    try:
        import yaml
    except ImportError:
        print("ERROR: PyYAML required. pip install pyyaml", file=sys.stderr)
        sys.exit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _llm_label_from_slug(slug: str) -> str:
    """Same heuristic as aggregate_corpus_findings."""
    known = {"claude", "openai", "grok", "gemini"}
    for token in reversed(slug.split("-")):
        if token in known:
            return token
    return "other"


def _find_latest_aggregate() -> Path:
    """Return the most recent aggregate.json by directory mtime,
    or None if none exists."""
    if not RESULTS_DIR.is_dir():
        return None
    candidates = []
    for d in RESULTS_DIR.iterdir():
        if not d.is_dir():
            continue
        agg = d / "aggregate.json"
        if agg.is_file():
            candidates.append(agg)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _expert_means_per_doc_per_dim() -> dict:
    """{doc_id: {dim: mean_rating}} from all rating files."""
    if not RATINGS_DIR.is_dir():
        return {}
    out = defaultdict(lambda: defaultdict(list))
    for doc_dir in RATINGS_DIR.iterdir():
        if not doc_dir.is_dir():
            continue
        doc_id = doc_dir.name
        for rater_file in doc_dir.glob("*.yaml"):
            data = _load_yaml(rater_file)
            if not data:
                continue
            ratings = data.get("ratings") or {}
            for dim, val in ratings.items():
                if isinstance(val, (int, float)):
                    out[doc_id][dim].append(float(val))
    means = {}
    for doc_id, dims in out.items():
        means[doc_id] = {}
        for dim, vals in dims.items():
            means[doc_id][dim] = sum(vals) / len(vals) if vals else None
    return means


def _expert_outlier_per_group(per_group_outliers: dict, expert_means: dict) -> dict:
    """For each peer group + each dimension, compute the expert-
    derived outlier (LLM whose mean expert rating is most distant
    from the group median expert rating).

    Mirrors the aggregate's outlier method but applied to expert
    ratings instead of structural signals.

    Returns {group_name: {dim: {expert_outliers, expert_median,
    n_rated_members, non_comparable, reason}}}.
    """
    out = {}
    for group_name, dims in per_group_outliers.items():
        # Get the member slugs for this group from the aggregate's
        # values_by_member (any dim has the same set).
        group_members = []
        for dim_data in dims.values():
            group_members = list(dim_data["values_by_member"].keys())
            break
        if len(group_members) < 3:
            out[group_name] = {
                dim: {
                    "expert_outliers": [],
                    "expert_median": None,
                    "n_rated_members": 0,
                    "non_comparable": True,
                    "reason": (
                        f"Peer group has {len(group_members)} members; "
                        f"outlier needs N >= 3."
                    ),
                }
                for dim in DIMENSIONS
            }
            continue

        out[group_name] = {}
        for dim in DIMENSIONS:
            ratings_per_member = {}
            for slug in group_members:
                doc_means = expert_means.get(slug, {})
                v = doc_means.get(dim)
                if isinstance(v, (int, float)):
                    ratings_per_member[slug] = float(v)
            if len(ratings_per_member) < 3:
                out[group_name][dim] = {
                    "expert_outliers": [],
                    "expert_median": None,
                    "n_rated_members": len(ratings_per_member),
                    "non_comparable": True,
                    "reason": (
                        f"Only {len(ratings_per_member)} group members "
                        f"have expert ratings on {dim}; need >= 3."
                    ),
                }
                continue
            sorted_vals = sorted(ratings_per_member.values())
            n = len(sorted_vals)
            if n % 2 == 1:
                median = sorted_vals[n // 2]
            else:
                median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
            distances = {
                slug: abs(v - median)
                for slug, v in ratings_per_member.items()
            }
            max_distance = max(distances.values())
            if max_distance == 0:
                outliers = []
            else:
                outliers = [
                    slug for slug, d in distances.items()
                    if d == max_distance
                ]
            out[group_name][dim] = {
                "expert_outliers": outliers,
                "expert_median": median,
                "n_rated_members": len(ratings_per_member),
                "non_comparable": False,
                "reason": "",
            }
    return out


def _compute_agreement(structural: dict, expert: dict) -> dict:
    """For each (group, dim), compare structural outlier vs expert
    outlier. Three outcomes:
      - agree: same LLM (after llm-label normalization)
      - disagree: different LLM
      - non_comparable: at least one side is non-comparable

    Returns counts and per-cell breakdown.
    """
    counts = {
        "agree": 0,
        "disagree": 0,
        "non_comparable": 0,
        "total": 0,
    }
    per_cell = {}
    for group_name, struct_dims in structural.items():
        per_cell[group_name] = {}
        for dim, struct_data in struct_dims.items():
            counts["total"] += 1
            expert_data = (expert.get(group_name) or {}).get(dim, {})
            if struct_data.get("non_comparable") or expert_data.get("non_comparable"):
                counts["non_comparable"] += 1
                per_cell[group_name][dim] = {
                    "outcome": "non_comparable",
                    "structural_outliers": struct_data.get("outliers", []),
                    "expert_outliers": expert_data.get("expert_outliers", []),
                    "reason": (
                        struct_data.get("non_comparable_reason", "")
                        or expert_data.get("reason", "")
                    ),
                }
                continue

            struct_llms = {
                _llm_label_from_slug(s)
                for s in struct_data.get("outliers", [])
            }
            expert_llms = {
                _llm_label_from_slug(s)
                for s in expert_data.get("expert_outliers", [])
            }
            if struct_llms & expert_llms:
                counts["agree"] += 1
                outcome = "agree"
            else:
                counts["disagree"] += 1
                outcome = "disagree"
            per_cell[group_name][dim] = {
                "outcome": outcome,
                "structural_outliers": sorted(struct_llms),
                "expert_outliers": sorted(expert_llms),
            }
    return {"counts": counts, "per_cell": per_cell}


def _format_md_report(payload: dict) -> str:
    counts = payload["agreement"]["counts"]
    per_cell = payload["agreement"]["per_cell"]
    n_total = counts["total"]
    n_comp = n_total - counts["non_comparable"]
    agreement_rate = (counts["agree"] / n_comp * 100) if n_comp > 0 else 0
    rate_str = (
        f"{agreement_rate:.0f}% of {n_comp} comparable cells"
        if n_comp > 0 else "no comparable cells"
    )

    lines = [
        "# Aggregate vs expert: outlier cross-check",
        "",
        f"- **Computed at:** {payload['computed_at_utc']}",
        f"- **Aggregate file:** `{payload['aggregate_source']}`",
        f"- **Ratings discovered:** "
        f"{payload['n_ratings_discovered']} rating "
        f"file{'s' if payload['n_ratings_discovered'] != 1 else ''}",
        f"- **Documents with ratings:** "
        f"{payload['n_docs_with_ratings']}",
        "",
        "## Methodology",
        "",
        "The aggregate identifies the **structural outlier** for "
        "each (peer group, dimension) cell via per-group median-"
        "distance on Frame Check's signal_value. This cross-check "
        "applies the same median-distance method to expert mean "
        "ratings per dimension per LLM and compares the two outlier "
        "identifications.",
        "",
        "Three outcomes per cell:",
        "- **agree**: structural outlier IS the expert outlier "
        "(or shares it in tie cases)",
        "- **disagree**: structural outlier is NOT the expert outlier",
        "- **non-comparable**: at least one side has insufficient "
        "data (e.g., dimension non-comparable in aggregate, OR "
        "fewer than 3 members rated)",
        "",
        "## Agreement rate",
        "",
        f"- Agree:           **{counts['agree']}** of {n_total} cells",
        f"- Disagree:        {counts['disagree']} of {n_total}",
        f"- Non-comparable:  {counts['non_comparable']} of {n_total}",
        "",
        f"**Agreement rate (of comparable cells): {rate_str}.**",
        "",
    ]
    if n_comp == 0:
        lines += [
            "_All cells are non-comparable in this run. The cross-",
            "check needs ratings on at least 3 members of at least",
            "one peer group on at least one dimension before",
            "agreement can be computed. See README.md for how to",
            "submit ratings._",
            "",
        ]
        return "\n".join(lines) + "\n"

    lines += [
        "## Per-cell breakdown",
        "",
    ]
    for group_name, group_cells in sorted(per_cell.items()):
        lines.append(f"### {group_name}")
        lines.append("")
        for dim in DIMENSIONS:
            cell = group_cells.get(dim, {})
            outcome = cell.get("outcome", "non_comparable")
            struct = cell.get("structural_outliers", [])
            exp = cell.get("expert_outliers", [])
            if outcome == "non_comparable":
                reason = cell.get("reason", "")
                lines.append(
                    f"- **{dim}**: non-comparable. {reason}"
                )
            elif outcome == "agree":
                lines.append(
                    f"- **{dim}**: AGREE. Structural outlier(s) "
                    f"{struct}; expert outlier(s) {exp}."
                )
            else:
                lines.append(
                    f"- **{dim}**: DISAGREE. Structural outlier(s) "
                    f"{struct}; expert outlier(s) {exp}. "
                    "These divergence cases are the most informative "
                    "for methodology revision."
                )
        lines.append("")

    lines += [
        "## What this cross-check tells you",
        "",
        "- **High agreement**: the structural signal aligns with "
        "expert judgment on outlier identification. The aggregate "
        "is a useful proxy for cross-LLM divergence at the dimension "
        "level.",
        "- **Low agreement**: the structural signal disagrees with "
        "expert judgment. Either the structural proxy is too crude "
        "(needs methodology revision) OR the expert ratings are "
        "noisy (needs more raters per document) OR the dimension "
        "is itself contested.",
        "- **Non-comparable**: the comparison cannot be made yet. "
        "Add ratings or fix the underlying corpus signal.",
        "",
        "## What this cross-check does NOT tell you",
        "",
        "- Whether the absolute signal values are correctly "
        "calibrated to expert ratings (this is a different "
        "question; see Phase 2 Spearman correlation work)",
        "- Whether the chosen outliers are the BEST representations "
        "of LLM behavior on these questions (the median-distance "
        "method has assumptions; alternative outlier methods exist)",
        "- Anything about LLMs in general (results are corpus-state "
        "descriptive, not population-inferential)",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    print("Frame Check decision-readiness cross-check harness")
    print("=" * 60)

    aggregate_path = _find_latest_aggregate()
    if aggregate_path is None:
        print(
            "No aggregate.json found. Run "
            "`python3 aggregate_corpus_findings.py` first."
        )
        return 0
    print(f"Reading aggregate: {aggregate_path}")
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    per_group_outliers = (aggregate.get("outlier_findings") or {}).get("per_group", {})

    expert_means = _expert_means_per_doc_per_dim()
    n_ratings = sum(
        len(list(d.glob("*.yaml")))
        for d in (RATINGS_DIR.iterdir() if RATINGS_DIR.is_dir() else [])
        if d.is_dir()
    )
    n_docs_with_ratings = len(expert_means)
    print(f"Ratings discovered: {n_ratings}")
    print(f"Documents with ratings: {n_docs_with_ratings}")

    if not expert_means:
        print()
        print(
            "No ratings present. The cross-check writes a status "
            "report with no agreement computation; compute will "
            "become meaningful once ratings start arriving. See "
            "README.md and rater_guide.md for how to contribute."
        )
        # Still emit a status report so the run produces an artifact.

    expert_outliers = _expert_outlier_per_group(per_group_outliers, expert_means)
    agreement = _compute_agreement(per_group_outliers, expert_outliers)

    # Repo-relative aggregate_source so absolute filesystem paths
    # (which would carry a machine-specific prefix) are not written
    # into cross_check.{json,md}.
    repo_root = HERE.parent.parent
    try:
        aggregate_source_str = str(aggregate_path.relative_to(repo_root))
    except ValueError:
        # Aggregate file is outside the repo (unusual). Fall back to
        # a results-anchored relative form rather than leaking the
        # absolute path.
        aggregate_source_str = "validation/decision_readiness/results/" + str(
            aggregate_path.relative_to(RESULTS_DIR)
        )

    payload = {
        "computed_at_utc": datetime.now(timezone.utc).isoformat(),
        "aggregate_source": aggregate_source_str,
        "n_ratings_discovered": n_ratings,
        "n_docs_with_ratings": n_docs_with_ratings,
        "expert_outliers_per_group": expert_outliers,
        "agreement": agreement,
        "framing": (
            "Cross-check between Frame Check's structural outlier "
            "identification (median-distance on signal_value) and "
            "expert outlier identification (median-distance on "
            "expert mean ratings). Agreement rate is the validation "
            "signal that turns the descriptive aggregate into "
            "inferentially supported finding when ratings are "
            "sufficient."
        ),
    }

    out_dir = aggregate_path.parent
    json_path = out_dir / "cross_check.json"
    md_path = out_dir / "cross_check.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_format_md_report(payload), encoding="utf-8")

    print()
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    counts = agreement["counts"]
    print()
    print(f"Agree:           {counts['agree']} of {counts['total']} cells")
    print(f"Disagree:        {counts['disagree']}")
    print(f"Non-comparable:  {counts['non_comparable']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
