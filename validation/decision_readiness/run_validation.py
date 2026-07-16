"""Decision-readiness validation harness.

Phase 2 of the validation work. Computes per-dimension correlations
between expert ratings and Frame Check's computed profile, and
inter-rater reliability across raters per dimension.

Reads:
  corpus/{doc_id}/profile.json   - Frame Check's computed profile
  corpus/{doc_id}/metadata.yaml  - genre, source, date
  ratings/{doc_id}/{rater}.yaml  - one rater's scores for one document

Writes:
  results/{date}/correlations.json  - per-dimension Spearman + ICC
  results/{date}/divergence.md      - documents where profile and raters diverge

Runs cleanly with zero ratings (validates the pipeline before any
rating data exists). Status output makes the empty case visible:
the harness prints what it found, what is missing, and what it
would compute when the data is in place.

Dependencies kept minimal: standard library only for the empty
case; numpy + scipy for correlations once data exists. The script
imports them lazily so the empty-case run does not require them.
"""

import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent
CORPUS_DIR = REPO_ROOT / "corpus"
RATINGS_DIR = REPO_ROOT / "ratings"
RESULTS_DIR = REPO_ROOT / "results"

# Dimensions in the same order as the methodology page and the
# decision_readiness module. Order is load-bearing for the
# correlations.json output.
DIMENSIONS = [
    "coverage",
    "calibration",
    "evidence",
    "robustness",
    "counterfactual",
]


def _load_yaml(path: Path) -> Optional[dict]:
    """Load a YAML file if PyYAML is available, else None.

    Lazy YAML import: the empty-case run does not require yaml.
    Real validation runs do; the script reports the missing
    dependency clearly when it fires for the first time.
    """
    try:
        import yaml
    except ImportError:
        print(
            "ERROR: PyYAML required to load rating files. Install with:\n"
            "  pip install pyyaml",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(
            f"WARN: could not parse {path}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None


def _discover_corpus() -> dict:
    """Discover documents in the corpus.

    Returns {doc_id: {profile, metadata}}. Documents missing either
    profile.json or metadata.yaml are skipped with a warning; the
    correlation harness needs both to compute anything meaningful.
    """
    if not CORPUS_DIR.is_dir():
        return {}
    docs = {}
    for doc_dir in sorted(CORPUS_DIR.iterdir()):
        if not doc_dir.is_dir():
            continue
        doc_id = doc_dir.name
        profile_path = doc_dir / "profile.json"
        metadata_path = doc_dir / "metadata.yaml"
        if not profile_path.is_file():
            print(f"WARN: {doc_id} missing profile.json; skipping",
                  file=sys.stderr)
            continue
        if not metadata_path.is_file():
            print(f"WARN: {doc_id} missing metadata.yaml; skipping",
                  file=sys.stderr)
            continue
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(
                f"WARN: could not parse {profile_path}: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue
        metadata = _load_yaml(metadata_path)
        if metadata is None:
            continue
        docs[doc_id] = {"profile": profile, "metadata": metadata}
    return docs


def _discover_ratings() -> dict:
    """Discover ratings under ratings/{doc_id}/{rater_id}.yaml.

    Returns {doc_id: {rater_id: rating_dict}}. Malformed rating
    files are skipped with a warning.
    """
    if not RATINGS_DIR.is_dir():
        return {}
    out = defaultdict(dict)
    for doc_dir in sorted(RATINGS_DIR.iterdir()):
        if not doc_dir.is_dir():
            continue
        doc_id = doc_dir.name
        for rater_file in sorted(doc_dir.glob("*.yaml")):
            rater_id = rater_file.stem
            rating = _load_yaml(rater_file)
            if rating is None:
                continue
            out[doc_id][rater_id] = rating
    return dict(out)


def _profile_signal(profile: dict, dimension: str) -> Optional[float]:
    """Extract the Frame Check signal_value for one dimension.

    Coverage is an integer count; calibration / evidence are
    floats or None; robustness is a count; counterfactual is a
    boolean. The harness coerces booleans to 0/1 so the
    correlation is computable; None is preserved.
    """
    dims = profile.get("dimensions") or {}
    d = dims.get(dimension) or {}
    val = d.get("signal_value")
    if isinstance(val, bool):
        return 1.0 if val else 0.0
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _expert_mean(ratings_for_doc: dict, dimension: str) -> Optional[float]:
    """Mean of rater scores for one dimension on one document.

    Skips raters who used `null` for this dimension. Returns None
    if no rater provided a numeric score for the dimension.
    """
    scores = []
    for _rater_id, rating in ratings_for_doc.items():
        per_dim = rating.get("ratings") or {}
        v = per_dim.get(dimension)
        if isinstance(v, (int, float)):
            scores.append(float(v))
    if not scores:
        return None
    return sum(scores) / len(scores)


def _spearman(xs: list, ys: list) -> Optional[float]:
    """Spearman rank correlation between two lists.

    Uses scipy when available. Returns None if N < 3 (correlation
    is meaningless on tiny samples) or if scipy is unavailable.
    """
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    try:
        from scipy.stats import spearmanr
    except ImportError:
        print(
            "WARN: scipy required for Spearman correlation. "
            "Install with: pip install scipy",
            file=sys.stderr,
        )
        return None
    rho, _p = spearmanr(xs, ys)
    if math.isnan(rho):  # NaN check (constant input)
        return None
    return float(rho)


def _icc_estimate(values_per_rater_per_doc: dict) -> Optional[float]:
    """Naive ICC estimate (one-way random effects, single rater).

    Computes the variance attributable to documents over the total
    variance, treating raters as random and documents as the unit
    of measurement.

    Real ICC computation should use a dedicated package (e.g.,
    `pingouin.intraclass_corr`) for proper ICC(2,k) variants.
    This estimate is sufficient as a first pass; replace before
    publishing v1 results.
    """
    # Build the per-document mean and variance arrays.
    rows = []  # list of (doc_id, [score_from_each_rater])
    for doc_id, rater_scores in values_per_rater_per_doc.items():
        scores = [s for s in rater_scores.values() if isinstance(s, (int, float))]
        if len(scores) >= 2:
            rows.append((doc_id, scores))
    if len(rows) < 2:
        return None
    # Within-document variance (mean of per-doc variance)
    import statistics as _stats
    within_var = _stats.mean(
        _stats.variance(scores) for _, scores in rows
    )
    # Between-document variance (variance of per-doc means)
    doc_means = [_stats.mean(scores) for _, scores in rows]
    if len(doc_means) < 2:
        return None
    between_var = _stats.variance(doc_means)
    total = within_var + between_var
    if total == 0:
        return None
    return between_var / total


def run_validation() -> int:
    """Run the validation harness end-to-end.

    Returns 0 on success, 2 on missing dependency, 1 on data
    integrity error. Prints a status report to stdout regardless
    of whether ratings exist; the empty-case report is itself a
    useful artifact (shows what is missing for the next iteration).
    """
    print("Frame Check decision-readiness validation harness")
    print("=" * 60)

    docs = _discover_corpus()
    ratings = _discover_ratings()

    print(f"Corpus documents found:   {len(docs)}")
    print(f"Documents with ratings:   {len(ratings)}")
    if not docs:
        print(
            "\nNo corpus documents yet. Add at least one document under "
            "corpus/{doc_id}/ with profile.json and metadata.yaml. "
            "See README.md for the corpus entry format.",
        )
        return 0
    if not ratings:
        print(
            "\nNo ratings submitted yet. Raters: see rater_guide.md, "
            "copy rating_template.yaml into ratings/{doc_id}/{rater_id}.yaml, "
            "and open a pull request.",
        )
        return 0

    # Build per-dimension arrays for correlation.
    print("\nPer-dimension data points (documents with at least one rating):")
    profile_signals_by_dim = {d: [] for d in DIMENSIONS}
    expert_means_by_dim = {d: [] for d in DIMENSIONS}
    rater_scores_by_dim_by_doc = {d: defaultdict(dict) for d in DIMENSIONS}

    for doc_id, doc_ratings in ratings.items():
        if doc_id not in docs:
            print(f"  WARN: ratings/{doc_id} has no matching corpus entry; skipping")
            continue
        profile = docs[doc_id]["profile"]
        for dim in DIMENSIONS:
            signal = _profile_signal(profile, dim)
            mean = _expert_mean(doc_ratings, dim)
            if signal is not None and mean is not None:
                profile_signals_by_dim[dim].append(signal)
                expert_means_by_dim[dim].append(mean)
            # Collect per-rater scores for ICC
            for rater_id, rating in doc_ratings.items():
                v = (rating.get("ratings") or {}).get(dim)
                if isinstance(v, (int, float)):
                    rater_scores_by_dim_by_doc[dim][doc_id][rater_id] = float(v)

    correlations = {}
    icc_estimates = {}
    for dim in DIMENSIONS:
        n = len(profile_signals_by_dim[dim])
        rho = _spearman(profile_signals_by_dim[dim], expert_means_by_dim[dim])
        icc = _icc_estimate(rater_scores_by_dim_by_doc[dim])
        correlations[dim] = {
            "n_documents": n,
            "spearman_rho": rho,
        }
        icc_estimates[dim] = icc
        rho_str = f"{rho:.3f}" if rho is not None else "n/a (need >=3 docs)"
        icc_str = f"{icc:.3f}" if icc is not None else "n/a (need >=2 raters/doc)"
        print(f"  {dim:16s} n={n:3d}  Spearman={rho_str}  ICC~{icc_str}")

    # Per-genre breakdown (computed but not printed in detail in
    # this skeleton; real runs publish it to the results file).
    per_genre = defaultdict(lambda: {d: {"signals": [], "means": []} for d in DIMENSIONS})
    for doc_id, doc_ratings in ratings.items():
        if doc_id not in docs:
            continue
        genre = (docs[doc_id]["metadata"] or {}).get("genre", "unknown")
        profile = docs[doc_id]["profile"]
        for dim in DIMENSIONS:
            signal = _profile_signal(profile, dim)
            mean = _expert_mean(doc_ratings, dim)
            if signal is not None and mean is not None:
                per_genre[genre][dim]["signals"].append(signal)
                per_genre[genre][dim]["means"].append(mean)

    per_genre_correlations = {}
    for genre, by_dim in per_genre.items():
        per_genre_correlations[genre] = {}
        for dim, vals in by_dim.items():
            per_genre_correlations[genre][dim] = {
                "n_documents": len(vals["signals"]),
                "spearman_rho": _spearman(vals["signals"], vals["means"]),
            }

    # Write results. Run-directory naming: ISO date plus a short
    # input-content hash so two runs on the same day with different
    # rating data produce distinct output directories. Same data
    # twice in one day produces the same hash and overwrites the
    # earlier output (which is the correct behavior: a re-run with
    # identical input is the same artifact).
    RESULTS_DIR.mkdir(exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Hash of (corpus doc_ids + rating doc_ids + rating count) is
    # stable across re-runs with the same data and changes when
    # ratings change. Short prefix (8 hex chars) is enough for
    # in-day disambiguation; collisions across days are not a
    # concern because the date is in the directory name.
    import hashlib
    input_signature = "|".join(sorted([
        f"corpus:{','.join(sorted(docs.keys()))}",
        f"rated:{','.join(sorted(ratings.keys()))}",
        f"count:{sum(len(r) for r in ratings.values())}",
    ]))
    run_hash = hashlib.sha256(input_signature.encode("utf-8")).hexdigest()[:8]
    out_dir = RESULTS_DIR / f"{today}-{run_hash}"
    out_dir.mkdir(exist_ok=True)

    results_payload = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "n_documents": len(docs),
        "n_documents_with_ratings": len(ratings),
        "dimensions": correlations,
        "icc_estimates": icc_estimates,
        "per_genre": per_genre_correlations,
        "thresholds": {
            "spearman_min_average": 0.6,
            "spearman_min_per_genre": 0.4,
            "rationale": "see /corpus/decision-readiness/ methodology page",
        },
    }
    correlations_path = out_dir / "correlations.json"
    correlations_path.write_text(
        json.dumps(results_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {correlations_path}")

    # Divergence cases: documents where Frame Check signal and
    # expert mean disagree by more than 1.5 (on the 1-5 scale, or
    # the equivalent gap on coercion-normalized signals).
    divergence_lines = ["# Divergence cases", "",
                         f"Computed: {today}", ""]
    for doc_id, doc_ratings in ratings.items():
        if doc_id not in docs:
            continue
        profile = docs[doc_id]["profile"]
        doc_div = []
        for dim in DIMENSIONS:
            signal = _profile_signal(profile, dim)
            mean = _expert_mean(doc_ratings, dim)
            if signal is None or mean is None:
                continue
            # Crude scale alignment: this comparison is approximate.
            # Real divergence detection should normalize signals to
            # the 1-5 expert scale per dimension. For the skeleton,
            # we surface absolute differences > 1.5 as candidates.
            if abs(signal - mean) > 1.5:
                doc_div.append(
                    f"- **{dim}**: profile signal={signal:.2f}, "
                    f"expert mean={mean:.2f}"
                )
        if doc_div:
            divergence_lines.append(f"## {doc_id}")
            divergence_lines.extend(doc_div)
            divergence_lines.append("")

    if len(divergence_lines) > 4:
        divergence_path = out_dir / "divergence.md"
        divergence_path.write_text(
            "\n".join(divergence_lines) + "\n", encoding="utf-8",
        )
        print(f"Wrote {divergence_path}")
    else:
        print("(No divergence cases this run.)")

    return 0


if __name__ == "__main__":
    sys.exit(run_validation())
