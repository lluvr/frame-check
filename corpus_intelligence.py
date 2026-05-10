"""Corpus aggregation as substrate intelligence for the MCP surface.

Framecheck ships with a small validation corpus (~10 documents under
`validation/decision_readiness/corpus/`) plus aggregate findings under
`validation/decision_readiness/results/{date}-{hash}/aggregate.json`.
The corpus has empirical signal that until now did not surface
through the MCP response: per-frame firing rates, co-fire patterns,
co-absence patterns, per-dimension peer-difference rates, and
cross-question outlier findings.

This module reads the corpus once (lazy, cached) and exposes query
functions that mcp_server.py uses to attach `corpus_context` to
matched frames, absent frames, and absence clusters. The substrate
stays deterministic: aggregation reads existing JSON files; no LLM
is invoked.

Evidence discipline:
  - The corpus is small (currently 10 entries). Every prevalence
    statement carries the denominator so the small-N is honest.
  - Outcome data based on expert ratings is not yet available
    (cross_check.json reports n_ratings_discovered=0 today). The
    "outcome signal" surfaced here is peer-difference rate and
    cross-question outlier findings from validation runs, not
    expert evaluation. Each surfaced field names its source.
  - When the corpus is unavailable (e.g., wheel without bundled
    corpus, or filesystem error), every query returns None rather
    than a fabricated value. The MCP response then omits
    corpus_context fields rather than carrying empty placeholders.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any, Optional

# library_entry_ref is the single source of truth for the canon-graph
# reference shape. Importing here so typical_co_fires / typical_co_absences
# can carry the same {library_resource_uri, library_url} pair as the
# top-level frame_library_matches and absent_frames blocks; without this
# the co-pattern entries were citation_uri-only and end-users in MCP
# clients had no clickable link to follow.
from decision_readiness import library_entry_ref as _library_entry_ref


# Top-K cap on co-fire and co-absence lists. Three is a balance
# between informativeness (the agent gets the dominant pattern) and
# noise (longer lists drift into low-prevalence false patterns under
# the corpus's small-N).
_CO_PATTERN_TOP_K = 3

# Cache. None means uninitialized; a dict (possibly with empty values)
# means initialization completed and the result is final until the
# server restarts. Populated by _load_corpus_state() under the lazy-
# load discipline.
_state: Optional[dict[str, Any]] = None


def _load_profile(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _profile_fired_set(profile: dict) -> set[str]:
    """Return the union of fired_library_entries.fvs_id across all
    five dimensions in a profile. The same FVS may appear in multiple
    dimensions (canon membership is multi-dimensional); the union
    gives the per-document set of frames that fired.
    """
    fired: set[str] = set()
    dims = profile.get("dimensions") or {}
    if not isinstance(dims, dict):
        return fired
    for dim_data in dims.values():
        if not isinstance(dim_data, dict):
            continue
        for entry in dim_data.get("fired_library_entries") or []:
            if isinstance(entry, dict):
                fvs_id = entry.get("fvs_id")
                if fvs_id:
                    fired.add(fvs_id)
    return fired


def _classify_corpus_entry_genre(slug_dir: str) -> Optional[str]:
    """Run the structural genre classifier on a corpus entry's
    document.md, with claims + voice analysis, and return the
    classified genre label (or None when the classifier abstains).

    Returns None on any I/O or analysis failure so a single
    misshapen corpus entry cannot break the aggregator.
    """
    doc_path = os.path.join(slug_dir, "document.md")
    if not os.path.exists(doc_path):
        return None
    try:
        with open(doc_path, "r", encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError):
        return None
    try:
        from genre_classifier import classify_genre
        from claim_analysis import analyze_claims
        from framing import detect_voice
    except ImportError:
        return None
    try:
        voice = detect_voice(text)
        claims = analyze_claims(text)
        result = classify_genre(text, voice=voice, claims=claims)
    except Exception:
        return None
    return result.get("genre")


def _load_aggregate(aggregate_results_dir: str) -> Optional[dict]:
    """Find and load the most recent aggregate.json under
    aggregate_results_dir. Returns None if no aggregate is available.
    """
    try:
        entries = sorted(
            d for d in os.listdir(aggregate_results_dir)
            if os.path.isdir(os.path.join(aggregate_results_dir, d))
        )
    except OSError:
        return None
    for slug in reversed(entries):
        path = os.path.join(aggregate_results_dir, slug, "aggregate.json")
        if os.path.exists(path):
            data = _load_profile(path)
            if data is not None:
                return data
    return None


def _initialize(
    corpus_entries_dir: str,
    aggregate_results_dir: str,
) -> dict[str, Any]:
    """Walk the corpus and build per-frame and per-dimension stats.

    Output structure:
      {
        "n_documents": int,
        "available": bool,
        "state_hash": str | None,
        "computed_at_utc": str | None,
        "per_frame": {
          fvs_id: {
            "fires_in": int,
            "corpus_entries_fired": [slug, ...],
            "corpus_entries_absent": [slug, ...],
            "typical_co_fires": [(fvs_id, count), ...],
            "typical_co_absences": [(fvs_id, count), ...],
          }
        },
        "per_dimension": {
          dim_name: {
            "peer_pair_difference_count": int,
            "peer_pair_total": int,
            "cross_question_outlier": {llm, outlier_count, ...} | None,
            "canon_size": int,
          }
        },
      }

    "available" is False when corpus or aggregate is missing; the MCP
    surface checks this and skips emitting corpus_context rather than
    surfacing zeros.
    """
    state: dict[str, Any] = {
        "n_documents": 0,
        "available": False,
        "state_hash": None,
        "computed_at_utc": None,
        "per_frame": {},
        "per_dimension": {},
        "per_genre_counts": {},
        "per_document_genre": {},
    }

    # Walk corpus entries to build per-document fired sets.
    try:
        slugs = sorted(
            d for d in os.listdir(corpus_entries_dir)
            if os.path.isdir(os.path.join(corpus_entries_dir, d))
        )
    except OSError:
        return state

    if not slugs:
        return state

    per_document: dict[str, set[str]] = {}
    per_document_genre: dict[str, Optional[str]] = {}
    for slug in slugs:
        slug_dir = os.path.join(corpus_entries_dir, slug)
        profile_path = os.path.join(slug_dir, "profile.json")
        profile = _load_profile(profile_path)
        if profile is None:
            continue
        fired = _profile_fired_set(profile)
        per_document[slug] = fired
        # Classify the corpus document by structural genre. None
        # when the classifier abstains (no feature regex matched).
        # Item E of the substrate-side composition polish: per-genre
        # segmentation of corpus prevalence.
        per_document_genre[slug] = _classify_corpus_entry_genre(slug_dir)

    if not per_document:
        return state

    # Per-genre counts. Documents the classifier abstained on are
    # bucketed under "_unclassified" so the agent can see how much
    # of the corpus is in unsegmentable territory.
    per_genre_counts: dict[str, int] = {}
    for genre in per_document_genre.values():
        bucket = genre or "_unclassified"
        per_genre_counts[bucket] = per_genre_counts.get(bucket, 0) + 1

    # Catalog of all FVS IDs ever appearing in any document's fired
    # set OR in any dimension's library_entries. We use the full
    # canonical FVS set from DIMENSION_LIBRARY_ENTRIES; any FVS ID
    # appearing in the canon graph is in scope.
    from decision_readiness import DIMENSION_LIBRARY_ENTRIES
    all_fvs: set[str] = set()
    for ids in DIMENSION_LIBRARY_ENTRIES.values():
        all_fvs.update(ids)
    # Also add anything seen in actual fires (defensive: future canon
    # additions or detector emissions outside the canon).
    for fired_set in per_document.values():
        all_fvs.update(fired_set)

    # Build per-frame stats with genre segmentation.
    per_frame: dict[str, dict[str, Any]] = {}
    for fvs_id in sorted(all_fvs):
        fired_in_slugs: list[str] = []
        absent_in_slugs: list[str] = []
        co_fire_counter: Counter[str] = Counter()
        co_absence_counter: Counter[str] = Counter()
        # Item E: track firing rate segmented by classified genre.
        # fires_in_by_genre maps genre name -> count of documents
        # in that genre where this frame fired. Genre=None entries
        # bucket under "_unclassified".
        fires_in_by_genre: Counter[str] = Counter()
        for slug, fired in per_document.items():
            slug_genre = per_document_genre.get(slug) or "_unclassified"
            if fvs_id in fired:
                fired_in_slugs.append(slug)
                fires_in_by_genre[slug_genre] += 1
                # Co-fires: other frames that fired in the same doc.
                for other in fired:
                    if other != fvs_id:
                        co_fire_counter[other] += 1
            else:
                absent_in_slugs.append(slug)
                # Co-absences: other frames absent in the same doc
                # (i.e., NOT in fired set, restricted to canon to
                # avoid combinatorial blowup over arbitrary IDs).
                doc_absent = all_fvs - fired - {fvs_id}
                for other in doc_absent:
                    co_absence_counter[other] += 1
        per_frame[fvs_id] = {
            "fires_in": len(fired_in_slugs),
            "fires_in_by_genre": dict(fires_in_by_genre),
            "corpus_entries_fired": fired_in_slugs,
            "corpus_entries_absent": absent_in_slugs,
            "typical_co_fires": [
                {"fvs_id": fid, "count": cnt}
                for fid, cnt in co_fire_counter.most_common(_CO_PATTERN_TOP_K)
            ],
            "typical_co_absences": [
                {"fvs_id": fid, "count": cnt}
                for fid, cnt in co_absence_counter.most_common(_CO_PATTERN_TOP_K)
            ],
        }

    # Read aggregate.json for per-dimension peer-difference rates and
    # cross-question outlier findings.
    aggregate = _load_aggregate(aggregate_results_dir)
    per_dimension: dict[str, dict[str, Any]] = {}
    state_hash = None
    computed_at = None
    if aggregate is not None:
        corpus_meta = aggregate.get("corpus") or {}
        state_hash = corpus_meta.get("state_hash")
        computed_at = aggregate.get("computed_at_utc")
        peer = aggregate.get("peer_findings") or {}
        per_dim_diff = peer.get("per_dimension_differs") or {}
        n_pairs = peer.get("n_pairs") or 0
        cqf = aggregate.get("cross_question_findings") or []
        cqf_by_dim: dict[str, dict] = {}
        for finding in cqf:
            if isinstance(finding, dict):
                dim = finding.get("dimension")
                if dim and dim not in cqf_by_dim:
                    # Keep first finding per dimension; multiple
                    # findings on the same dimension would need
                    # ranking. None today.
                    cqf_by_dim[dim] = {
                        "llm": finding.get("llm"),
                        "outlier_count": finding.get("outlier_count"),
                        "comparable_count": finding.get("comparable_count"),
                    }
        for dim, canon_ids in DIMENSION_LIBRARY_ENTRIES.items():
            per_dimension[dim] = {
                "peer_pair_difference_count": per_dim_diff.get(dim),
                "peer_pair_total": n_pairs,
                "cross_question_outlier": cqf_by_dim.get(dim),
                "canon_size": len(canon_ids),
            }

    state.update({
        "n_documents": len(per_document),
        "available": True,
        "state_hash": state_hash,
        "computed_at_utc": computed_at,
        "per_frame": per_frame,
        "per_dimension": per_dimension,
        "per_genre_counts": per_genre_counts,
        "per_document_genre": per_document_genre,
    })
    return state


def _ensure_loaded(
    corpus_entries_dir: str,
    aggregate_results_dir: str,
) -> dict[str, Any]:
    global _state
    if _state is None:
        _state = _initialize(corpus_entries_dir, aggregate_results_dir)
    return _state


def reset_cache() -> None:
    """Reset the cached aggregation. Test-only helper."""
    global _state
    _state = None


def get_corpus_summary(
    corpus_entries_dir: str,
    aggregate_results_dir: str,
) -> Optional[dict]:
    """Return whole-corpus context for envelope use. None when
    corpus is unavailable.
    """
    state = _ensure_loaded(corpus_entries_dir, aggregate_results_dir)
    if not state["available"]:
        return None
    return {
        "n_documents": state["n_documents"],
        "state_hash": state["state_hash"],
        "aggregate_computed_at_utc": state["computed_at_utc"],
        "per_genre_counts": dict(state.get("per_genre_counts") or {}),
        "small_n_caveat": (
            "Framecheck's validation corpus is small "
            f"(N={state['n_documents']} documents). Prevalence and "
            "co-pattern statistics carry the denominator; treat any "
            "single-figure rate as a corpus signal, not a population "
            "estimate. Outcome data based on expert ratings is not "
            "yet available; the outcome-shaped signals surfaced are "
            "peer-pair-difference rates and cross-question outlier "
            "findings from validation runs. Per-genre segmentation "
            "(per_genre_counts) is provided so callers can compute "
            "like-vs-like prevalence; the '_unclassified' bucket "
            "groups documents the genre classifier abstained on."
        ),
    }


def get_frame_corpus_context(
    fvs_id: str,
    corpus_entries_dir: str,
    aggregate_results_dir: str,
) -> Optional[dict]:
    """Return per-frame corpus context for an FVS ID. None when
    corpus is unavailable or the frame is unknown.

    Output:
      {
        "prevalence": "fires in N of M corpus documents",
        "fires_in_count": N,
        "fires_in_total": M,
        "typical_co_fires": [{fvs_id, count, citation_uri}, ...],
        "typical_co_absences": [{fvs_id, count, citation_uri}, ...],
        "corpus_entries_fired_uris": [corpus_resource_uri, ...],
      }
    """
    state = _ensure_loaded(corpus_entries_dir, aggregate_results_dir)
    if not state["available"]:
        return None
    frame_stats = state["per_frame"].get(fvs_id)
    if not frame_stats:
        return None
    n = state["n_documents"]
    fires = frame_stats["fires_in"]
    fires_by_genre = dict(frame_stats.get("fires_in_by_genre") or {})
    per_genre_counts = state.get("per_genre_counts") or {}
    # Build fires_in_by_genre with denominators so the agent can
    # surface like-vs-like prevalence directly. Each entry carries
    # the numerator (frame fired in N genre-X documents) AND the
    # denominator (M total genre-X documents in corpus). When the
    # genre's denominator is too small, the agent should treat the
    # rate as informative-not-statistical (small_n_caveat applies).
    # Per-genre stats with low-N warning. When genre_total < 3, the
    # rate (0% or 100% in extreme cases) is not statistically
    # meaningful at the per-genre level. The substrate flags this
    # with low_n_warning so the agent does not cite the rate as if
    # it were calibrated against meaningful N.
    by_genre_with_totals = {
        genre: {
            "fires_in_count": fires_by_genre.get(genre, 0),
            "genre_total": per_genre_counts.get(genre, 0),
            "rate": (
                round(
                    fires_by_genre.get(genre, 0)
                    / per_genre_counts.get(genre, 1),
                    3,
                )
                if per_genre_counts.get(genre, 0) > 0 else 0.0
            ),
            "low_n_warning": per_genre_counts.get(genre, 0) < 3,
            "is_unclassified_bucket": (genre == "_unclassified"),
        }
        for genre in per_genre_counts
    }
    return {
        "prevalence": f"fires in {fires} of {n} corpus documents",
        "fires_in_count": fires,
        "fires_in_total": n,
        "fires_in_by_genre": by_genre_with_totals,
        "typical_co_fires": [
            {
                "fvs_id": entry["fvs_id"],
                "count": entry["count"],
                "citation_uri": f"frame-check://library/{entry['fvs_id']}",
                "library_url": _library_entry_ref(entry["fvs_id"]).get("public_url"),
            }
            for entry in frame_stats["typical_co_fires"]
        ],
        "typical_co_absences": [
            {
                "fvs_id": entry["fvs_id"],
                "count": entry["count"],
                "citation_uri": f"frame-check://library/{entry['fvs_id']}",
                "library_url": _library_entry_ref(entry["fvs_id"]).get("public_url"),
            }
            for entry in frame_stats["typical_co_absences"]
        ],
        "corpus_entries_fired_uris": [
            f"frame-check://corpus/{slug}"
            for slug in frame_stats["corpus_entries_fired"]
        ],
    }


def count_corpus_pattern_matches(
    pattern_trigger: dict,
    corpus_entries_dir: str,
    aggregate_results_dir: str,
) -> Optional[dict]:
    """For a given pattern trigger (frame_present + frame_absent
    constraints, plus optional genre), count corpus entries that
    match the trigger.

    Item E of the substrate-side composition polish: when the
    pattern carries a `genre` constraint, the corpus prevalence is
    reported as both:
      - frame-shape match across the full corpus (legacy denominator)
      - frame-shape AND genre match within the genre's segment
        (segmented denominator)

    Returns:
      {
        "matches": int (frame-shape match across full corpus),
        "total": int (full corpus size),
        "match_rate": float,
        "matches_in_genre": int | None (frame-shape AND classified
                                         genre matches the trigger
                                         genre; None when trigger
                                         has no genre constraint),
        "genre_total": int | None (count of corpus documents
                                    classified into trigger genre),
        "genre_match_rate": float | None,
        "trigger_genre": str | None,
      }

    None when corpus is unavailable.

    Trigger fields honored: frames_present_all, frames_absent_all,
    frames_present_any, frames_absent_any, and (for segmented
    counting) genre.
    """
    state = _ensure_loaded(corpus_entries_dir, aggregate_results_dir)
    if not state["available"]:
        return None
    # Need the per-document fired sets the aggregator built. They
    # are not directly exposed in the public state; re-derive from
    # per_frame.corpus_entries_fired (each frame's slug list).
    per_frame = state["per_frame"]
    if not per_frame:
        return None
    # Build per-document fired sets from the per_frame index.
    per_document_fired: dict[str, set[str]] = {}
    for fvs_id, frame_stats in per_frame.items():
        for slug in frame_stats["corpus_entries_fired"]:
            per_document_fired.setdefault(slug, set()).add(fvs_id)
    # Documents with no fired frames are still in the corpus; those
    # appear as empty sets. Reconstruct full document list from the
    # union of fired + absent slug membership.
    all_slugs: set[str] = set()
    for frame_stats in per_frame.values():
        all_slugs.update(frame_stats["corpus_entries_fired"])
        all_slugs.update(frame_stats["corpus_entries_absent"])
    for slug in all_slugs:
        per_document_fired.setdefault(slug, set())

    # Catalog: every FVS in the per_frame index. A document's absent
    # set is catalog minus its fired set.
    catalog = set(per_frame.keys())

    per_document_genre = state.get("per_document_genre") or {}
    trigger_genre = pattern_trigger.get("genre")

    matches = 0
    matches_in_genre = 0
    for slug, fired in per_document_fired.items():
        absent = catalog - fired
        if "frames_present_all" in pattern_trigger:
            if not all(
                f in fired for f in pattern_trigger["frames_present_all"]
            ):
                continue
        if "frames_absent_all" in pattern_trigger:
            if not all(
                f in absent for f in pattern_trigger["frames_absent_all"]
            ):
                continue
        if "frames_present_any" in pattern_trigger:
            if not any(
                f in fired for f in pattern_trigger["frames_present_any"]
            ):
                continue
        if "frames_absent_any" in pattern_trigger:
            if not any(
                f in absent for f in pattern_trigger["frames_absent_any"]
            ):
                continue
        # Frame-shape match across full corpus.
        matches += 1
        # Genre-segmented match: same frame shape AND classified
        # genre matches the trigger's genre constraint.
        if trigger_genre and per_document_genre.get(slug) == trigger_genre:
            matches_in_genre += 1

    total = len(per_document_fired)
    rate = matches / total if total > 0 else 0.0
    per_genre_counts = state.get("per_genre_counts") or {}
    if trigger_genre:
        genre_total = per_genre_counts.get(trigger_genre, 0)
        genre_match_rate = (
            round(matches_in_genre / genre_total, 3)
            if genre_total > 0 else 0.0
        )
        low_n_warning = genre_total < 3
    else:
        matches_in_genre = None
        genre_total = None
        genre_match_rate = None
        low_n_warning = False
    return {
        "matches": matches,
        "total": total,
        "match_rate": round(rate, 3),
        "matches_in_genre": matches_in_genre,
        "genre_total": genre_total,
        "genre_match_rate": genre_match_rate,
        "trigger_genre": trigger_genre,
        "genre_segmented_low_n_warning": low_n_warning,
    }


def get_dimension_corpus_context(
    dimension: str,
    corpus_entries_dir: str,
    aggregate_results_dir: str,
) -> Optional[dict]:
    """Return per-dimension corpus context for a canonical dimension.
    None when corpus or aggregate is unavailable, or the dimension is
    unknown.

    Output:
      {
        "peer_pair_difference_rate": "differs across N of M peer pairs",
        "peer_pair_difference_count": N,
        "peer_pair_total": M,
        "cross_question_outlier": {llm, outlier_count, comparable_count} | None,
        "canon_size": int,
      }
    """
    state = _ensure_loaded(corpus_entries_dir, aggregate_results_dir)
    if not state["available"]:
        return None
    dim_stats = state["per_dimension"].get(dimension)
    if not dim_stats:
        return None
    diff_count = dim_stats.get("peer_pair_difference_count")
    total = dim_stats.get("peer_pair_total") or 0
    if diff_count is not None and total > 0:
        rate_text = (
            f"differs across {diff_count} of {total} peer pairs in "
            f"the validation corpus"
        )
    else:
        rate_text = None
    return {
        "peer_pair_difference_rate": rate_text,
        "peer_pair_difference_count": diff_count,
        "peer_pair_total": total,
        "cross_question_outlier": dim_stats.get("cross_question_outlier"),
        "canon_size": dim_stats.get("canon_size"),
    }
