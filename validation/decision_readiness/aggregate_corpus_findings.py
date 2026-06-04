"""Aggregate decision-readiness findings across the corpus.

Walks corpus/{slug}/peer_with_*.json and diff_with_*.json files
and computes descriptive aggregate statistics: per-dimension
divergence rates, per-LLM outlier rates, per-group breakdowns.

Intentional framing decisions:

  - DESCRIPTIVE, NOT INFERENTIAL. The corpus is convenience-
    sampled; aggregate statistics describe THIS CORPUS STATE,
    not the population of LLM behaviors. Every output names its
    N prominently so readers cannot mistake a small-sample
    description for a generalizable claim.

  - VERSIONED AGAINST CORPUS STATE. Every aggregate output
    includes a SHA-256 of the corpus directory contents at run
    time. Two aggregate runs on the same corpus produce the
    same hash; comparing aggregates across corpus revisions is
    explicit (the hash changes, surfacing the data revision).

  - HUMAN-READABLE FIRST. Output is markdown by default for
    pedagogue / researcher consumption; structured JSON exists
    alongside for downstream tooling. Both ship together.

  - COMPOUNDS WITH GROWTH. The same code produces increasingly
    meaningful output as the corpus grows. At N=12 the output is
    a small-sample description; at N=200 it is a real research
    finding. The tool is the durable artifact; the headline N
    changes over time.

Run:
  python3 validation/decision_readiness/aggregate_corpus_findings.py

Outputs:
  results/{date}-{corpus_hash}/aggregate.json
  results/{date}-{corpus_hash}/aggregate.md

The corpus_hash in the directory name disambiguates aggregate
runs against different corpus states; same hash means same
underlying data. The date prefix gives chronological order.
"""

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
CORPUS_DIR = HERE / "corpus"
RESULTS_DIR = HERE / "results"

# Dimensions in the canonical order, matching the methodology page
# and decision_readiness module.
DIMENSIONS = [
    "coverage",
    "calibration",
    "evidence",
    "robustness",
    "counterfactual",
]

# Canon graph access. Aggregate findings cite the FVS library entries
# affecting each dimension so a reader of the aggregate has the named
# vocabulary for what they're seeing (e.g., "claude is the
# Counterfactual outlier" carries inline cites of the library entries
# that describe Counterfactual structural patterns). Sources of truth:
# decision_readiness.DIMENSION_LIBRARY_ENTRIES (module constant) and
# the bidirectional canon graph tests in test_canon_graph_consistency.py.
sys.path.insert(0, str(REPO_ROOT))
try:
    from framecheck.decision_readiness import (
        DIMENSION_LIBRARY_ENTRIES,
        library_entry_ref,
        corpus_entry_ref,
    )
finally:
    sys.path.pop(0)


def _library_entries_for_dim(dim: str) -> list:
    """Returns the list of canon-graph reference OBJECTS declared as
    affecting `dim` in DIMENSION_LIBRARY_ENTRIES. Each object carries
    fvs_id + library_resource_uri + public_url so the aggregate's
    library citations are the same shape as the per-document profile
    JSON's library_entries field. Single source of truth: the
    library_entry_ref helper in decision_readiness.py."""
    return [
        library_entry_ref(fid)
        for fid in DIMENSION_LIBRARY_ENTRIES.get(dim, [])
    ]


def _format_library_cite(refs: list) -> str:
    """Formats a list of canon-graph reference objects as a
    comma-separated string of library URLs for markdown rendering.
    Each ref is the {fvs_id, title, public_url, ...} object emitted
    by library_entry_ref. Inlines the title so the reader sees
    "FVS-007 Failure Framing" rather than a bare ID; falls back to
    the bare fvs_id (without an extra space) if the title equals
    the fvs_id (the documented missing-title fallback in
    library_entry_ref). Returns 'none declared' when the list is
    empty (kept explicit so the absence is visible rather than
    rendered as awkward whitespace)."""
    if not refs:
        return "none declared"
    parts = []
    for ref in refs:
        fvs_id = ref["fvs_id"]
        title = ref.get("title") or fvs_id
        # When title is the bare fvs_id (lookup miss), avoid
        # rendering "FVS-007 FVS-007" by collapsing to just the ID.
        label = fvs_id if title == fvs_id else f"{fvs_id} {title}"
        parts.append(f"[{label}]({ref['public_url']})")
    return ", ".join(parts)


def _corpus_state_hash() -> str:
    """SHA-256 of the corpus directory contents.

    Hashes the bytes of every profile.json, metadata.yaml,
    diff_with_*.json, and peer_with_*.json file inside corpus/.
    Document.md is excluded because the rated text itself is not
    derived from the analyzers, so its content does not affect
    the aggregate output.

    Returns the first 12 hex chars (sufficient for in-day
    disambiguation between corpus revisions).
    """
    if not CORPUS_DIR.is_dir():
        return "no-corpus"
    h = hashlib.sha256()
    rel_paths = []
    for p in sorted(CORPUS_DIR.rglob("*")):
        if not p.is_file():
            continue
        if p.name == "document.md":
            continue
        rel = p.relative_to(CORPUS_DIR)
        rel_paths.append(str(rel))
        h.update(str(rel).encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:12]


def _load_yaml(path: Path):
    try:
        import yaml
    except ImportError:
        print(
            "ERROR: PyYAML required to read metadata.yaml. "
            "Install: pip install pyyaml",
            file=sys.stderr,
        )
        sys.exit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _llm_label_from_slug(slug: str) -> str:
    """Heuristic: extract the LLM label from a corpus slug.

    Slugs follow the pattern '{group-prefix}-{question}-{llm}'
    (e.g., 'four-llms-bitcoin-claude'). The last hyphen-segment
    is the llm label when it matches one of the known labels;
    otherwise returns 'other'.
    """
    known = {"claude", "openai", "grok", "gemini"}
    for token in reversed(slug.split("-")):
        if token in known:
            return token
    return "other"


def _scan_corpus():
    """Walk corpus/, return (entries_meta, peer_files, diff_files)."""
    entries = {}
    peer_files = []
    diff_files = []
    if not CORPUS_DIR.is_dir():
        return entries, peer_files, diff_files
    for entry_dir in sorted(CORPUS_DIR.iterdir()):
        if not entry_dir.is_dir():
            continue
        slug = entry_dir.name
        meta_path = entry_dir / "metadata.yaml"
        if meta_path.is_file():
            meta = _load_yaml(meta_path) or {}
            entries[slug] = meta
        for f in sorted(entry_dir.glob("peer_with_*.json")):
            peer_files.append((slug, f))
        for f in sorted(entry_dir.glob("diff_with_*.json")):
            diff_files.append((slug, f))
    return entries, peer_files, diff_files


def _is_dim_non_comparable(comparison_text: str) -> bool:
    """A dimension is non-comparable when the comparison_text says
    so explicitly. Evidence and Robustness commonly fall here when
    the corpus profiles were computed offline (no Source Network).
    Distinguishing 'non-comparable' from 'agrees' matters: peers
    agreeing is a finding; data missing is a corpus gap."""
    text_lower = (comparison_text or "").lower()
    return (
        "not comparable" in text_lower
        or "neither peer had" in text_lower
        or "unavailable on one side" in text_lower
        or "neither peer has" in text_lower
    )


def _aggregate_outlier_per_group(entries: dict) -> dict:
    """Per peer-group, per dimension: identify the outlier LLM.

    True outlier definition: for a peer group of N members, compute
    each member's signal_value on each dimension, take the group
    median, and rank members by distance from median. The member
    with the max distance is the dimension's outlier in that group.
    Ties are reported as multiple outliers (the comparison cannot
    distinguish them).

    Returns:
      {
        peer_group_name: {
          dimension: {
            "outliers": [llm_label, ...],   # may be empty
            "values_by_member": {slug: value},
            "median": float | None,
            "non_comparable": bool,         # True if values not numeric
          }
        }
      }

    A dimension is non_comparable for a group when at least one
    member's signal_value is None (e.g., evidence verification
    ratio when Source Network was not run on the corpus). The
    bare participation count was the wrong signal; this median-
    distance computation is the right one.
    """
    # Collect group memberships and load profiles.
    groups = defaultdict(list)
    for slug, meta in entries.items():
        peer_group = meta.get("peer_group")
        if peer_group:
            groups[peer_group].append(slug)

    out = {}
    for group_name, slugs in groups.items():
        if len(slugs) < 2:
            continue
        # Load profiles for group members.
        profiles = {}
        for slug in slugs:
            path = CORPUS_DIR / slug / "profile.json"
            if not path.is_file():
                continue
            try:
                profiles[slug] = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

        out[group_name] = {}
        for dim in DIMENSIONS:
            values_by_member = {}
            # Per-dimension secondary signals used to detect "no
            # data" cases where signal_value looks numeric but
            # the underlying measurement was not actually
            # performed. Robustness specifically: signal_value=0
            # can mean "no contradictions" (agreement) OR "no
            # claims checked" (no SN run). We disambiguate via
            # signal_secondary which is the checked count.
            secondary_by_member = {}
            for slug, prof in profiles.items():
                d = (prof.get("dimensions") or {}).get(dim) or {}
                v = d.get("signal_value")
                if isinstance(v, bool):
                    v = 1.0 if v else 0.0
                elif isinstance(v, (int, float)):
                    v = float(v)
                else:
                    v = None
                values_by_member[slug] = v
                secondary_by_member[slug] = d.get("signal_secondary")

            # Dimension-aware non-comparable detection for cases
            # where signal_value is numeric but the measurement
            # was not actually performed. Robustness: secondary
            # is the checked count; if every member has 0 checks
            # the dimension is not measured, even though
            # signal_value=0 looks like agreement.
            if dim == "robustness" and all(
                (s == 0 or s is None) for s in secondary_by_member.values()
            ):
                out[group_name][dim] = {
                    "outliers": [],
                    "values_by_member": values_by_member,
                    "median": None,
                    "non_comparable": True,
                    "non_comparable_reason": (
                        "All group members have 0 checked claims; "
                        "signal_value=0 reflects no Source Network "
                        "data, not peer agreement."
                    ),
                }
                continue

            numeric_values = [v for v in values_by_member.values() if v is not None]
            if not numeric_values or len(numeric_values) < len(values_by_member):
                # At least one member has no comparable signal:
                # the outlier ranking is ill-defined. Mark non-
                # comparable rather than picking a fake outlier.
                out[group_name][dim] = {
                    "outliers": [],
                    "values_by_member": values_by_member,
                    "median": None,
                    "non_comparable": True,
                    "non_comparable_reason": (
                        "At least one peer has no comparable "
                        "signal_value on this dimension."
                    ),
                }
                continue

            # Outlier-via-median-distance is methodologically
            # ill-defined for groups with fewer than 3 members:
            # at N=2 every member has equal distance to the
            # median (which is the midpoint between them), and
            # at N=1 there's no comparison to make. Mark non-
            # comparable rather than report a fake outlier.
            if len(numeric_values) < 3:
                out[group_name][dim] = {
                    "outliers": [],
                    "values_by_member": values_by_member,
                    "median": None,
                    "non_comparable": True,
                    "non_comparable_reason": (
                        f"Peer group has only {len(numeric_values)} "
                        f"comparable members; outlier detection "
                        f"requires N >= 3."
                    ),
                }
                continue

            # Median of numeric values
            sorted_vals = sorted(numeric_values)
            n = len(sorted_vals)
            if n % 2 == 1:
                median = sorted_vals[n // 2]
            else:
                median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2

            # Rank members by distance; outliers are max-distance.
            distances = {
                slug: abs(v - median)
                for slug, v in values_by_member.items()
                if v is not None
            }
            if not distances:
                out[group_name][dim] = {
                    "outliers": [],
                    "values_by_member": values_by_member,
                    "median": median,
                    "non_comparable": True,
                }
                continue
            max_distance = max(distances.values())
            # Only report an outlier when the max distance is
            # strictly positive AND the gap to the next-closest
            # member is non-trivial. If everyone is at the median
            # (all same value), no outlier exists.
            if max_distance == 0:
                outliers = []
            else:
                outliers = [
                    slug for slug, d in distances.items()
                    if d == max_distance
                ]

            out[group_name][dim] = {
                "outliers": outliers,
                "values_by_member": values_by_member,
                "median": median,
                "non_comparable": False,
            }
    return out


def _aggregate_outlier_counts_by_llm(per_group_outliers: dict) -> dict:
    """Aggregate per-LLM outlier counts across peer groups.

    For each LLM and each dimension, count the number of peer
    groups in which this LLM was identified as the outlier.
    Distinct from the per-LLM PARTICIPATION counts: those said
    'this LLM was in N pairs where some divergence happened';
    these say 'this LLM was the most-different member of its
    peer group on this dimension in N groups'.
    """
    counts_per_llm = defaultdict(lambda: {dim: 0 for dim in DIMENSIONS})
    appearances_per_llm = Counter()
    non_comparable_per_llm = defaultdict(lambda: {dim: 0 for dim in DIMENSIONS})

    for group_name, dims in per_group_outliers.items():
        # Determine the LLMs in this group via any dimension's
        # values_by_member (they're all the same set).
        group_members = set()
        for dim_data in dims.values():
            for slug in dim_data["values_by_member"]:
                group_members.add(slug)
            break
        for slug in group_members:
            appearances_per_llm[_llm_label_from_slug(slug)] += 1

        for dim, dim_data in dims.items():
            if dim_data["non_comparable"]:
                for slug in group_members:
                    non_comparable_per_llm[_llm_label_from_slug(slug)][dim] += 1
                continue
            for outlier_slug in dim_data["outliers"]:
                counts_per_llm[_llm_label_from_slug(outlier_slug)][dim] += 1

    # Sort by LLM label at emission time so the aggregate.json byte
    # output is deterministic across re-runs. Counter + defaultdict
    # preserve insertion order, which comes from Python set iteration
    # over group_members (non-deterministic hash order). Without the
    # sort, identical inputs produce different on-disk byte sequences,
    # showing as dict-reorder noise in git diffs of re-runs. Dimension
    # dicts inside each LLM entry keep rubric order (coverage,
    # calibration, evidence, robustness, counterfactual) because they
    # are built from the DIMENSIONS constant.
    return {
        "appearances_per_llm": {
            llm: appearances_per_llm[llm] for llm in sorted(appearances_per_llm)
        },
        "outlier_counts_per_llm": {
            llm: dict(counts_per_llm[llm]) for llm in sorted(counts_per_llm)
        },
        "non_comparable_per_llm": {
            llm: dict(non_comparable_per_llm[llm]) for llm in sorted(non_comparable_per_llm)
        },
    }


def _aggregate_peer_findings(peer_files):
    """Aggregate per-dimension divergence rates across peer pairs.

    Each peer comparison file is mirrored in BOTH peers'
    directories, so a single pair appears in `peer_files` twice.
    Dedupe by sorted (label_a, label_b) tuple.

    Per dimension we track THREE outcomes per pair:
      - differs: peers measurably differ on this dimension
      - non_comparable: data missing on at least one side (e.g.,
        Source Network not run, no claims to compare)
      - agrees: peers comparable AND signals match
    The three counts sum to n_pairs. Conflating non_comparable
    with agrees would hide corpus gaps as findings.
    """
    seen_pairs = set()
    pair_records = []
    for owner_slug, file_path in peer_files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        a = data.get("label_a", "")
        b = data.get("label_b", "")
        key = tuple(sorted([a, b]))
        if not a or not b or key in seen_pairs:
            continue
        seen_pairs.add(key)
        pair_records.append({
            "label_a": a,
            "label_b": b,
            "peer_group": data.get("peer_group", "ungrouped"),
            "dimensions": data.get("dimensions", {}),
        })

    n_pairs = len(pair_records)

    per_dimension_differs = {dim: 0 for dim in DIMENSIONS}
    per_dimension_non_comparable = {dim: 0 for dim in DIMENSIONS}
    per_group_pair_count = Counter()
    per_group_dim_differs = defaultdict(lambda: {dim: 0 for dim in DIMENSIONS})
    per_group_dim_non_comparable = defaultdict(
        lambda: {dim: 0 for dim in DIMENSIONS}
    )
    per_llm_appearances = Counter()
    per_llm_dim_participation = defaultdict(
        lambda: {dim: 0 for dim in DIMENSIONS}
    )

    for rec in pair_records:
        per_group_pair_count[rec["peer_group"]] += 1
        per_llm_appearances[_llm_label_from_slug(rec["label_a"])] += 1
        per_llm_appearances[_llm_label_from_slug(rec["label_b"])] += 1
        for dim in DIMENSIONS:
            d = rec["dimensions"].get(dim, {})
            text = d.get("comparison_text", "")
            if _is_dim_non_comparable(text):
                per_dimension_non_comparable[dim] += 1
                per_group_dim_non_comparable[rec["peer_group"]][dim] += 1
                continue
            if d.get("differs"):
                per_dimension_differs[dim] += 1
                per_group_dim_differs[rec["peer_group"]][dim] += 1
                per_llm_dim_participation[
                    _llm_label_from_slug(rec["label_a"])
                ][dim] += 1
                per_llm_dim_participation[
                    _llm_label_from_slug(rec["label_b"])
                ][dim] += 1

    return {
        "n_pairs": n_pairs,
        "n_groups": len(per_group_pair_count),
        "per_dimension_differs": per_dimension_differs,
        "per_dimension_non_comparable": per_dimension_non_comparable,
        "per_group_pair_count": dict(per_group_pair_count),
        "per_group_dim_differs": {
            g: dict(d) for g, d in per_group_dim_differs.items()
        },
        "per_group_dim_non_comparable": {
            g: dict(d) for g, d in per_group_dim_non_comparable.items()
        },
        "per_llm_appearances": dict(per_llm_appearances),
        "per_llm_dim_participation": {
            llm: dict(dims) for llm, dims in per_llm_dim_participation.items()
        },
    }


def _collect_llm_fired_patterns(
    llm: str, dim: str, per_group_outliers: dict,
) -> tuple:
    """For an LLM that's the outlier on `dim` across multiple peer
    groups, aggregate the fired_library_entries across this LLM's
    profile.json files in those groups.

    Returns (fired_counts, docs_examined) where:
      fired_counts: {fvs_id: count_of_LLM_docs_where_this_pattern_fired}
      docs_examined: count of LLM's profiles successfully read

    Why count fires-per-document instead of just listing patterns:
      A pattern that fires in EVERY one of the LLM's outlier
      documents is a stronger structural signal than one that
      fires in just one. Surfacing the count lets a reader see
      consistency vs sporadic detection at a glance.

    A pattern present in fired_library_entries but appearing only
    in some of the LLM's docs (e.g., "FVS-007 in 1 of 2") is
    still informative, different documents may exercise different
    failure modes within the same dimension. The reader can judge.

    Returns empty Counter when the LLM's docs have no canon-aligned
    pattern detections for this dimension. The cross-question
    finding is still valid (the outlier signal comes from raw
    values, not pattern detection) but the canon graph cannot
    point to a specific named pattern in this case.
    """
    fired_counts = Counter()
    docs_examined = 0
    for group_name, dims in per_group_outliers.items():
        dim_data = dims.get(dim) or {}
        if dim_data.get("non_comparable"):
            continue
        members = dim_data.get("values_by_member") or {}
        # Match this LLM's slugs in the group's membership. _llm_label_from_slug
        # is the same heuristic used to build the per-LLM aggregate counts,
        # so this filter agrees with the outlier_counts_per_llm structure.
        llm_slugs = [
            s for s in members.keys()
            if _llm_label_from_slug(s) == llm
        ]
        if not llm_slugs:
            continue
        outliers = set(dim_data.get("outliers") or [])
        # Only count this LLM's docs that were ACTUALLY the outlier in
        # this group, not all of the LLM's docs in the group. The
        # cross-question finding asks "what fired in claude's outlier
        # documents," so non-outlier docs would dilute the signal.
        outlier_llm_slugs = [s for s in llm_slugs if s in outliers]
        for slug in outlier_llm_slugs:
            profile_path = CORPUS_DIR / slug / "profile.json"
            if not profile_path.is_file():
                continue
            try:
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            fired = (
                (profile.get("dimensions") or {}).get(dim, {})
                .get("fired_library_entries") or []
            )
            docs_examined += 1
            for ref in fired:
                fid = ref.get("fvs_id")
                if fid:
                    fired_counts[fid] += 1
    return fired_counts, docs_examined


def _collect_corpus_entries_for_llm(
    llm: str, entries: dict,
) -> list:
    """Return the corpus entries that belong to this LLM, as
    {slug, title} dicts.

    The aggregate cites an LLM name in cross-question findings;
    downstream consumers (web post-processing for deep links, MCP
    agents chaining to documents) need the specific corpus slugs
    that belong to that LLM. Emitting the mapping in the aggregate
    JSON itself means no consumer has to reimplement the slug
    heuristic, single source of truth.

    Match rule mirrors _llm_label_from_slug (last known-label
    hyphen-segment wins) so findings and entries use the same
    label vocabulary. Entries are sorted by slug for deterministic
    output across rebuilds."""
    matches = []
    for slug in sorted(entries.keys()):
        if _llm_label_from_slug(slug) != llm:
            continue
        meta = entries[slug] or {}
        # Use corpus_entry_ref so the shape matches the canon-graph
        # reference convention (parallel to library_entry_ref):
        # {slug, title, resource_uri, public_url}. Agents chaining
        # from a cross-question finding to a corpus entry can use
        # resource_uri directly (frame-check://corpus/{slug}) without
        # having to reconstruct the URI.
        matches.append(corpus_entry_ref(
            slug, title=meta.get("title"),
        ))
    return matches


def _compute_cross_question_findings(
    per_group_outliers: dict, outlier_summary: dict,
    entries: dict | None = None,
) -> list:
    """Return the list of (llm, dim) cells where the LLM is the
    outlier in EVERY comparable peer group it appears in (the
    cross-question consistency signal). Each finding carries:

      - llm, dimension
      - outlier_count, comparable_count (e.g., "all 2 of 2")
      - library_entries: the dimension's full canon space
        (same shape as the per-document profile's library_entries)
      - fired_patterns: which canon-aligned patterns actually
        fired in this LLM's outlier documents, with firing counts
        (read from per-document profile.json fired_library_entries)
      - documents_examined: how many of the LLM's outlier docs
        were profiled (denominator for the firing counts)
      - corpus_entries: list of {slug, title} dicts for the
        specific corpus entries that belong to this LLM. The
        chain affordance for agents who want to go from the
        finding ("claude is the outlier") to the actual
        documents being cited ("claude's outlier documents are
        four-llms-bitcoin-claude and four-llms-startup-claude").
        Emitted at the harness level so both the web rendering
        (aggregate page deep links) and MCP consumers (chaining
        to frame-check://corpus/{slug}) read the same mapping.
        Empty list when entries is None (callers can omit).

    Computed once and consumed by both the JSON payload (for
    structured downstream tooling) and the markdown report (for
    human-readable findings). Single source of truth so the two
    surfaces cannot drift.

    Threshold: at least 2 comparable peer groups. With <2, the
    "consistency" claim is ill-defined (you cannot be "consistent
    across questions" if you only appear in one question).
    """
    findings = []
    appearances = outlier_summary.get("appearances_per_llm", {})
    outlier_counts = outlier_summary.get("outlier_counts_per_llm", {})
    non_comp_counts = outlier_summary.get("non_comparable_per_llm", {})
    for llm in sorted(appearances.keys()):
        n_groups = appearances[llm]
        for dim in DIMENSIONS:
            nc = non_comp_counts.get(llm, {}).get(dim, 0)
            comparable = n_groups - nc
            if comparable < 2:
                continue
            outlier_count = outlier_counts.get(llm, {}).get(dim, 0)
            if outlier_count != comparable:
                continue
            # The LLM is consistently the outlier on this dim.
            # Build the structured finding.
            fired_counts, docs_examined = _collect_llm_fired_patterns(
                llm, dim, per_group_outliers,
            )
            # Sort by count descending, then alphabetical fvs_id within
            # ties. most_common() alone resolves ties in insertion
            # order, which would shift if corpus iteration order
            # changes. Adding the alphabetical tiebreaker keeps the
            # aggregate output reproducible across any corpus refresh
            # whose firing counts are equal.
            sorted_firings = sorted(
                fired_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
            fired_patterns = [
                {
                    **library_entry_ref(fid),
                    "fired_in_n_documents": count,
                }
                for fid, count in sorted_firings
            ]
            corpus_entries = (
                _collect_corpus_entries_for_llm(llm, entries)
                if entries is not None else []
            )
            findings.append({
                "llm": llm,
                "dimension": dim,
                "outlier_count": outlier_count,
                "comparable_count": comparable,
                "library_entries": _library_entries_for_dim(dim),
                "fired_patterns": fired_patterns,
                "documents_examined": docs_examined,
                "corpus_entries": corpus_entries,
            })
    return findings


def _aggregate_diff_findings(diff_files):
    """Aggregate transformation-diff signals across pairs.

    Diffs are also mirrored in both halves of each pair; dedupe.
    """
    seen_pairs = set()
    pair_records = []
    for owner_slug, file_path in diff_files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        src = data.get("source_label", "")
        xfm = data.get("transformed_label", "")
        key = tuple(sorted([src, xfm]))
        if not src or not xfm or key in seen_pairs:
            continue
        seen_pairs.add(key)
        pair_records.append({
            "source_label": src,
            "transformed_label": xfm,
            "transformation_kind": data.get("transformation_kind", ""),
            "dimensions": data.get("dimensions", {}),
        })

    n_pairs = len(pair_records)

    per_dimension_moved = {dim: 0 for dim in DIMENSIONS}
    per_kind_pair_count = Counter()

    for rec in pair_records:
        per_kind_pair_count[rec["transformation_kind"] or "unspecified"] += 1
        for dim in DIMENSIONS:
            d = rec["dimensions"].get(dim, {})
            if d.get("moved"):
                per_dimension_moved[dim] += 1

    return {
        "n_pairs": n_pairs,
        "per_dimension_moved": per_dimension_moved,
        "per_kind_pair_count": dict(per_kind_pair_count),
    }


def _format_md_report(payload: dict) -> str:
    """Human-readable markdown report. Every claim names its N
    inline; the descriptive-not-inferential framing is
    structural in the section headers."""
    n_entries = payload["corpus"]["n_entries"]
    n_with_profile = payload["corpus"]["n_with_profile"]
    n_paired = payload["corpus"]["n_with_pair_metadata"]
    n_peer_grouped = payload["corpus"]["n_with_peer_group"]
    corpus_hash = payload["corpus"]["state_hash"]
    computed_at = payload["computed_at_utc"]

    peer = payload["peer_findings"]
    diff = payload["diff_findings"]

    lines = [
        "# Decision-readiness corpus aggregate findings",
        "",
        "**Descriptive of corpus state, not inference about populations.**",
        "Every claim below names its sample size inline. With small N,",
        "individual outliers may be sampling noise rather than signal.",
        "Aggregate findings become inference-grade only when N grows",
        "substantially across genres and questions.",
        "",
        f"- **Computed at:** {computed_at}",
        f"- **Corpus state hash:** `{corpus_hash}` "
        f"(SHA-256 prefix; identifies the exact corpus revision)",
        f"- **Corpus entries:** {n_entries} "
        f"({n_with_profile} with profile.json, "
        f"{n_paired} with paired_with metadata, "
        f"{n_peer_grouped} with peer_group metadata)",
        "",
        "## Peer-comparison findings",
        "",
        f"Aggregated across **N = {peer['n_pairs']} pairwise peer "
        f"comparisons** in **{peer['n_groups']} peer groups**. "
        f"Each comparison is non-directional; counts below "
        f"represent the number of pairs in which the two peers "
        f"measurably differed on a given dimension.",
        "",
        "### Per-dimension divergence rate",
        "",
        f"Of {peer['n_pairs']} pairs, three outcomes per "
        f"dimension: peers measurably differ, peers agree (signals "
        f"comparable and match), or non-comparable (data missing on "
        f"one or both sides; e.g., evidence and robustness when "
        f"corpus profiles were computed without Source Network).",
        "",
        "| Dimension | Differ | Agree | Non-comparable | Rate (of comparable) |",
        "|-----------|-------:|------:|---------------:|---------------------:|",
    ]
    n = peer["n_pairs"]
    for dim in DIMENSIONS:
        differs = peer["per_dimension_differs"].get(dim, 0)
        non_comp = peer["per_dimension_non_comparable"].get(dim, 0)
        agree = n - differs - non_comp
        comparable = n - non_comp
        rate = (differs / comparable * 100) if comparable > 0 else 0
        rate_str = f"{rate:.0f}% of {comparable}" if comparable > 0 else "n/a"
        lines.append(
            f"| {dim} | {differs} | {agree} | {non_comp} | {rate_str} |"
        )

    # Library citations per dimension. Lets a reader of the aggregate
    # navigate to the named patterns that describe the failure modes
    # producing each dimension's divergence. The mapping comes from
    # decision_readiness.DIMENSION_LIBRARY_ENTRIES; the bidirectional
    # canon graph test pins agreement with the methodology page and
    # the library entries' own implication sections.
    lines += [
        "",
        "### Named library entries per dimension",
        "",
        "When a dimension diverges in this aggregate, the named "
        "patterns in the Frame Vocabulary Standard describe the "
        "structural failure modes that produce the divergence. "
        "Click through to read the canonical entry for each frame.",
        "",
    ]
    for dim in DIMENSIONS:
        lines.append(
            f"- **{dim.capitalize()}**: "
            f"{_format_library_cite(_library_entries_for_dim(dim))}"
        )

    lines += [
        "",
        "### Per-peer-group breakdown",
        "",
        "Counts within each peer group. A group with N members "
        "yields C(N, 2) pairs.",
        "",
    ]
    for group, count in sorted(peer["per_group_pair_count"].items()):
        group_dims = peer["per_group_dim_differs"].get(group, {})
        lines.append(f"**{group}** ({count} pair{'s' if count != 1 else ''}):")
        lines.append("")
        for dim in DIMENSIONS:
            d_count = group_dims.get(dim, 0)
            lines.append(f"  - {dim}: {d_count} of {count} pairs differ")
        lines.append("")

    lines += [
        "### Per-LLM participation in differing pairs",
        "",
        "When two peers differ on a dimension, BOTH peers participated. "
        "These counts are descriptive of HOW OFTEN each LLM is in a "
        "pair where some divergence was measured. Cross-LLM behavioral "
        "claims require larger N.",
        "",
    ]
    # Outlier table replaces the prior participation table. The
    # participation count was a proxy that conflated being in a
    # differing pair with being the CAUSE of the difference.
    # Outlier identification computes per-group median signal and
    # marks the member with max distance from median as the
    # outlier. This is the methodologically correct cross-LLM
    # signal.
    outlier = payload["outlier_findings"]
    summary = outlier.get("summary_per_llm", {})
    appearances = summary.get("appearances_per_llm", {})
    if appearances:
        dim_abbrev = {
            "coverage": "Cov",
            "calibration": "Cal",
            "evidence": "Evi",
            "robustness": "Rob",
            "counterfactual": "CF",
        }
        lines.append(
            "Outlier identification: per peer group, the member "
            "whose signal value is most different from the group "
            "median on a given dimension is identified as the "
            "outlier on that dimension. Counts below report how "
            "many groups each LLM was the outlier in (out of the "
            "groups it appeared in)."
        )
        lines.append("")
        lines.append(
            "| LLM | Groups | "
            + " | ".join(dim_abbrev[d] for d in DIMENSIONS)
            + " |"
        )
        lines.append(
            "|-----|------:|"
            + "|".join(["----:"] * len(DIMENSIONS))
            + "|"
        )
        outlier_counts = summary.get("outlier_counts_per_llm", {})
        non_comp_counts = summary.get("non_comparable_per_llm", {})
        for llm in sorted(appearances.keys()):
            n_groups = appearances[llm]
            llm_outliers = outlier_counts.get(llm, {})
            llm_nc = non_comp_counts.get(llm, {})
            row = [llm, str(n_groups)]
            for dim in DIMENSIONS:
                nc = llm_nc.get(dim, 0)
                if nc == n_groups:
                    row.append("n/a")
                else:
                    row.append(
                        f"{llm_outliers.get(dim, 0)} of {n_groups - nc}"
                    )
            lines.append("| " + " | ".join(row) + " |")
        lines += [
            "",
            "Legend: Cov = Coverage, Cal = Calibration, "
            "Evi = Evidence, Rob = Robustness, CF = Counterfactual. "
            "Cell shows outlier-count of comparable-group-count "
            "(n/a when the dimension was non-comparable in every "
            "group containing this LLM).",
        ]

    # Cross-question outlier consistency. Consumes the structured
    # findings from _compute_cross_question_findings (built once,
    # also exposed in the JSON payload) so the markdown and JSON
    # surfaces cannot drift.
    cross_question_findings = payload.get("cross_question_findings") or []
    cross_question_lines = []
    for finding in cross_question_findings:
        llm = finding["llm"]
        dim = finding["dimension"]
        comparable = finding["comparable_count"]
        canon_cite = _format_library_cite(finding["library_entries"])
        # Fired patterns: which canon-aligned patterns actually
        # fired in this LLM's outlier documents. When non-empty,
        # this is the focused signal, sharper than the canon
        # candidate list. When empty, the cross-question outlier
        # signal still holds (it comes from raw signal_value
        # distance from the group median) but no detector-mapped
        # pattern covers it; honest framing matters.
        fired = finding["fired_patterns"]
        docs_examined = finding["documents_examined"]
        if fired:
            # Inline the title so the reader sees "FVS-007 Failure
            # Framing (2 of 2)" without clicking to identify the
            # pattern. Same fallback as _format_library_cite when
            # title is unavailable.
            fired_parts = []
            for p in fired:
                fvs_id = p["fvs_id"]
                title = p.get("title") or fvs_id
                label = (
                    fvs_id if title == fvs_id else f"{fvs_id} {title}"
                )
                fired_parts.append(
                    f"[{label}]({p['public_url']}) "
                    f"({p['fired_in_n_documents']} of {docs_examined})"
                )
            fired_summary = ", ".join(fired_parts)
            fired_line = (
                f" Fired patterns in {llm}'s outlier documents: "
                f"{fired_summary}."
            )
        else:
            fired_line = (
                f" No canon-mapped patterns fired in {llm}'s outlier "
                f"documents (the outlier signal comes from raw "
                f"signal_value distance, not detector-identified "
                f"named patterns)."
            )
        # Corpus-entry deep link in markdown: the same corpus_entries
        # field the JSON payload carries, rendered inline so readers
        # of the markdown report see the specific documents the
        # finding cites. Previously this deep link was generated by
        # downstream during rendering; emitting it
        # at the harness level means web + MCP consume the same data
        # and can't drift.
        corpus_entries = finding.get("corpus_entries") or []
        if corpus_entries:
            # Title may contain parentheses ("Claude on ... (bitcoin)").
            # The site's minimal md_to_html link regex uses `[^\]]+`
            # for link text (stops at `]`, tolerates `(` and `)` in
            # text) and `[^)]+` for URL (stops at `)`, which is fine
            # for our URLs that don't contain nested parens). So
            # parens in titles render correctly without any escaping.
            # `]` and `[` in titles are theoretical edge cases; escape
            # them defensively.
            def _md_link_text(t: str) -> str:
                return (
                    t.replace("\\", "\\\\")
                     .replace("[", "\\[")
                     .replace("]", "\\]")
                )
            # Use the canon-graph reference's public_url field
            # directly rather than reconstructing the URL from the
            # slug. corpus_entry_ref emits public_url consistently
            # so the URL stays in sync with any future base-URL
            # change made to CORPUS_PUBLIC_URL_BASE.
            corpus_links = ", ".join(
                f"[{_md_link_text(ce['title'])}]({ce['public_url']})"
                for ce in corpus_entries
            )
            corpus_line = (
                f" See {llm}'s corpus entries: {corpus_links}."
            )
        else:
            corpus_line = ""
        cross_question_lines.append(
            f"- **{llm}** is the {dim} outlier in "
            f"**all {comparable} of {comparable}** "
            f"comparable peer groups it appears in."
            f"{fired_line}"
            f" Named library entries for {dim} (full canon space): "
            f"{canon_cite}."
            f"{corpus_line}"
        )

    if cross_question_lines:
        lines += [
            "",
            "## Cross-question outlier consistency",
            "",
            "When the same LLM is identified as the outlier on "
            "the same dimension across multiple distinct peer "
            "groups (different questions), that consistency is a "
            "stronger structural signal than any single-group "
            "outlier identification. The findings below report "
            "every (LLM, dimension) cell where the LLM is the "
            "outlier in EVERY comparable group it appears in.",
            "",
        ]
        lines.extend(cross_question_lines)
        lines.append("")
        lines.append(
            "These findings still inherit the corpus-level N "
            "caveat (current peer groups: "
            f"{len(payload['outlier_findings']['per_group'])}). "
            "Cross-question consistency is more compelling at 2 "
            "groups than at 1, more compelling at 5 than at 2. "
            "The threshold for 'corpus-level finding' rises with "
            "the question-diversity of the peer groups."
        )

    lines += [
        "",
        "## Transformation-diff findings",
        "",
        f"Aggregated across **N = {diff['n_pairs']} transformation "
        f"pair{'s' if diff['n_pairs'] != 1 else ''}**. Each pair is a "
        f"directional source -> derived comparison.",
        "",
    ]
    if diff["n_pairs"] == 0:
        lines += [
            "No transformation pairs in corpus yet. Add pairs by "
            "declaring `paired_with` and `transformation_kind` in "
            "two entries' metadata.yaml.",
            "",
        ]
    else:
        # Small-sample warning. With N < 3 transformation pairs,
        # rate columns are misleading (a single pair gives
        # "100% of 1" or "0% of 1"). Surface the warning before
        # the table so a reader cannot mistake a single-pair
        # rate for a corpus-level finding.
        if diff["n_pairs"] < 3:
            lines += [
                f"**Small sample warning.** N = {diff['n_pairs']} "
                f"is below the threshold (3) at which per-"
                f"dimension rates become interpretive. Rates "
                f"below should be read as raw counts, not as "
                f"corpus-level findings. The aggregate becomes "
                f"informative as more transformation pairs are "
                f"added (see `CORPUS_GENRE_GAPS.md`).",
                "",
            ]
        lines += [
            "### Per-dimension movement rate",
            "",
            f"Of {diff['n_pairs']} pairs, the count of pairs where "
            f"the transformation measurably moved a dimension:",
            "",
            "| Dimension | Pairs moved | Rate |",
            "|-----------|------------:|-----:|",
        ]
        for dim in DIMENSIONS:
            moved = diff["per_dimension_moved"].get(dim, 0)
            rate = (moved / diff["n_pairs"] * 100) if diff["n_pairs"] else 0
            rate_str = (
                f"{rate:.0f}%" if diff["n_pairs"] >= 3
                else f"{moved}/{diff['n_pairs']} (small N)"
            )
            lines.append(
                f"| {dim} | {moved} of {diff['n_pairs']} | {rate_str} |"
            )
        lines += [
            "",
            "### Per-transformation-kind breakdown",
            "",
        ]
        for kind, count in sorted(diff["per_kind_pair_count"].items()):
            lines.append(f"- **{kind}**: {count} pair{'s' if count != 1 else ''}")
        lines.append("")

    lines += [
        "## Honest limits",
        "",
        f"- **Sample size**: peer N = {peer['n_pairs']}, "
        f"transformation N = {diff['n_pairs']}. Conclusions about "
        "specific LLMs or specific transformation effects need "
        "substantially larger N.",
        "- **Convenience sampling**: the v1 corpus is convenience-"
        "sampled from existing worked examples (see methodology "
        "page). Selection bias is acknowledged; v2 randomly-"
        "sampled component is the planned correction.",
        "- **Genre coverage**: the corpus is heavily ai_response. "
        "Cross-genre claims require corpus expansion (see "
        "CORPUS_GENRE_GAPS.md).",
        "- **Profile validation**: per-dimension absolute signals "
        "remain experimental until Phase 2 expert validation lands. "
        "Comparison signals (peer differs / transformation moved) "
        "are LESS dependent on absolute signal validity but still "
        "inherit the underlying methodology.",
        "",
        "## Citation",
        "",
        "Lucic, L. ({year}). Frame Check decision-readiness "
        "aggregate findings, corpus revision `{hash}`, "
        "computed {date}. https://frame.clarethium.com/corpus/decision-readiness/".format(
            year=datetime.now(timezone.utc).year,
            hash=corpus_hash,
            date=computed_at[:10],
        ),
        "",
    ]

    return "\n".join(lines) + "\n"


def main() -> int:
    print("Frame Check decision-readiness corpus-aggregate harness")
    print("=" * 60)

    entries, peer_files, diff_files = _scan_corpus()
    n_entries = len(entries)
    n_with_profile = sum(
        1 for slug in entries
        if (CORPUS_DIR / slug / "profile.json").is_file()
    )
    n_with_pair = sum(1 for m in entries.values() if m.get("paired_with"))
    n_with_peer = sum(1 for m in entries.values() if m.get("peer_group"))
    corpus_hash = _corpus_state_hash()

    print(f"Corpus entries:         {n_entries}")
    print(f"Entries with profile:   {n_with_profile}")
    print(f"Entries with paired_with: {n_with_pair}")
    print(f"Entries with peer_group:  {n_with_peer}")
    print(f"Corpus state hash:      {corpus_hash}")

    if n_entries == 0:
        print()
        print(
            "No corpus entries. Curate at least one entry "
            "(see curate_corpus.py) before running aggregate."
        )
        return 0

    peer_findings = _aggregate_peer_findings(peer_files)
    diff_findings = _aggregate_diff_findings(diff_files)

    # True outlier detection: per peer-group, identify which member
    # is the most-different from the group median on each
    # dimension. This is methodologically distinct from the
    # participation counts already in peer_findings; participation
    # tells you "this LLM was in N differing pairs," outlier tells
    # you "this LLM was the most-different member in N groups."
    # Participation was a proxy that conflates being in a differing
    # pair with being the cause of the difference.
    per_group_outliers = _aggregate_outlier_per_group(entries)
    outlier_summary = _aggregate_outlier_counts_by_llm(per_group_outliers)

    # Cross-question consistency findings: which (LLM, dimension)
    # pairs had the LLM as outlier in EVERY comparable peer group
    # it appeared in, with fired_patterns identifying which
    # canon-aligned patterns specifically fired across those
    # documents. Computed here so the JSON payload and the
    # markdown report consume the same structured findings.
    cross_question_findings = _compute_cross_question_findings(
        per_group_outliers, outlier_summary, entries=entries,
    )

    payload = {
        "computed_at_utc": datetime.now(timezone.utc).isoformat(),
        "corpus": {
            "state_hash": corpus_hash,
            "n_entries": n_entries,
            "n_with_profile": n_with_profile,
            "n_with_pair_metadata": n_with_pair,
            "n_with_peer_group": n_with_peer,
        },
        "peer_findings": peer_findings,
        "diff_findings": diff_findings,
        "outlier_findings": {
            "per_group": per_group_outliers,
            "summary_per_llm": outlier_summary,
        },
        # Cross-question consistency findings: structured form of
        # the markdown "Cross-question outlier consistency" section
        # so downstream tooling can consume the same findings as
        # human readers, with fired_patterns identifying which
        # detector-aligned canon entries specifically fired across
        # the LLM's outlier documents.
        "cross_question_findings": cross_question_findings,
        # Canon-graph projection: the FVS library entries declared
        # to affect each dimension. Mirrors the per-dimension
        # library_entries field on individual profile.json outputs
        # so downstream tooling sees the same citation set whether
        # consuming a per-document profile or this corpus aggregate.
        "library_entries_per_dimension": {
            dim: _library_entries_for_dim(dim) for dim in DIMENSIONS
        },
        "framing": (
            "DESCRIPTIVE of this corpus state. Not inference about "
            "LLM populations. Every count names its N inline. "
            "Aggregate findings compound with corpus growth; the "
            "tool is durable, the headline N changes."
        ),
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = RESULTS_DIR / f"{today}-{corpus_hash}"
    out_dir.mkdir(exist_ok=True)

    json_path = out_dir / "aggregate.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    md_path = out_dir / "aggregate.md"
    md_path.write_text(_format_md_report(payload), encoding="utf-8")

    print()
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print()
    print(
        f"Peer pairs aggregated:           {peer_findings['n_pairs']}"
    )
    print(
        f"Transformation pairs aggregated: {diff_findings['n_pairs']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
