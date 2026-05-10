"""Composition helpers for the Frame Check MCP server.

The compose layer carries every response-building helper that turns
detector output into the MCP epistemic payload structure.
`mcp_server.py` retains only the JSON-RPC envelope, method handlers,
dispatch loop, CLI version / test modes, and the test-mode module-
attribute proxy; everything from raw analyzer output to the final
tool-response dict lives here.

Module layout (top to bottom):

  Provenance:
    PRODUCTION_STATUS, PRODUCTION_STATUS_NOTE
    _build_provenance (canonical provenance block; reads
      SERVER_VERSION lazily, see import-cycle note below)

  Corpus-context delegators (over corpus_intelligence):
    _frame_corpus_context_or_none
    _dimension_corpus_context_or_none
    _corpus_summary_or_none

  Document-signal aggregator:
    _build_document_signals (frame_deepening, epistemic, voice,
      claims_extracted -> doc_signals dict for pattern matching)

  MCP contract v2 dimension builders:
    _build_coverage_v2 (per-dimension coverage evidence +
      construct block)
    _build_voice_construct (Phase B voice classification-confidence)
    _build_temporal_construct (Phase B temporal distribution)

  Per-level construct treatment:
    _CLAIM_LEVEL_DETECTOR / _CLASSIFIER / _LLM_CLASSIFIER /
      _COMPOSED / _AGENT_GENERATED (level identifiers)
    _CLAIM_LEVEL_TREATMENTS (claim_type / validation_status /
      caveats / how_to_cite per level; consumed by
      agent_guidance.claim_level_treatments)
    _apply_v2_only_preference (legacy v1 coverage drop)

  Frame Divergence block (FRAME_DIVERGENCE_CONTRACT_v1 Part 2):
    _extract_teaching_question (FVS markdown teaching-question
      extractor)
    _signal_strength_for_absent_frame (canon + coverage tier)
    _DIMENSION_CLUSTER_READINGS (5 curated cluster reading
      templates)
    _CLUSTER_MIN_ABSENT / _CLUSTER_MIN_CANON_FRACTION /
      _CLUSTER_MIN_DOCUMENT_WORDS / _CLUSTER_TIER_ORDER (cluster
      firing thresholds)
    _build_absence_clusters (substrate-side cluster surfacing)
    _build_divergence_block (divergence + agent_guidance_additions
      builder; the 818-line contract-driven entry point)

  Compose-budget helper:
    _compress_agent_guidance_to_load_bearing (compresses
      agent_guidance for compose_budget=standard/minimal; ~31KB
      to ~12KB cut; consumed by build_epistemic_payload)

  Suggested next actions:
    _build_suggested_next_actions (derives 2-4 specific next-action
      suggestions from analysis + divergence findings; consumed by
      build_epistemic_payload as the discovery-loop closer)

  Top-level payload builders (the two MCP tool entry points):
    build_epistemic_payload (frame_check tool: analysis +
      agent_guidance + divergence + provenance)
    _per_document_core / _summarize_per_document (per-document
      helpers consumed by build_compare_payload)
    build_compare_payload (frame_compare tool: per-document core
      measurements + cross-document deltas + provenance)

Import-cycle note: SERVER_VERSION is read INSIDE _build_provenance
rather than imported at module top. mcp_server runs as __main__ when
executed via `python mcp_server.py --version` (the CLI fingerprint
path); at that moment, no module named `mcp_server` exists in
sys.modules, so a top-level `from mcp_server import SERVER_VERSION`
in mcp_compose would re-import mcp_server.py as a SECOND module
distinct from __main__, re-entering the very compose import that
triggered it and producing a circular-import failure. Lazy-importing
SERVER_VERSION inside the function body sidesteps the cycle: by the
time _build_provenance runs (at request-handling time), the import
graph is settled, and the lookup resolves either against the __main__
instance (CLI path) or against the cached mcp_server module (library
path) without re-executing mcp_server.py. The same lazy pattern
applies to FRAME_CHECK_VERSION and CLARETHIUM_VERSION inside
_build_provenance for consistency, though those imports do not face
the __main__ cycle.

The other module-top imports (mcp_resources, mcp_schema, mcp_log,
corpus_intelligence) are not subject to the cycle because none of
those modules imports mcp_server. The function-local imports inside
_build_divergence_block and the two top-level payload builders
(corpus_intelligence helpers, frame_library, frame_opportunities,
frame_patterns, genre_classifier, user_goals, decision_readiness,
the framing engine, claim_analysis, clarethium_measure) stay
function-local because they are heavy modules invoked only on the
request-handling path; importing them at module top would slow
`python mcp_server.py --version` and the test-collection import
without benefit.
"""

from __future__ import annotations

from typing import Any

import time

from mcp_resources import (
    RESOURCE_SCHEME,
    _signal_strength_for,
    _CORPUS_ENTRIES_DIR,
    _AGGREGATE_RESULTS_DIR,
    _ensure_caches,
    _library_entry_ref,
    _library_v3_entries,
    _dimensions_affecting,
    _get_frame_statuses,
    _get_frame_library_version,
    _get_frame_versions,
    _get_frame_adjacency,
)
from mcp_schema import _SPEC_VERSION
from mcp_log import log

# Corpus intelligence aggregator. Reads the validation corpus
# (10 entries today) once at first query, builds per-frame and
# per-dimension stats, and exposes them as `corpus_context` blocks
# attached to matched frames, absent frames, and absence clusters.
# Substrate stays deterministic: aggregation is read-only over
# existing profile.json files; no LLM is invoked. When the corpus
# is unavailable (e.g., wheel without bundled corpus), every
# context lookup returns None and the MCP response simply omits
# the corpus_context fields rather than carrying empty placeholders.
from corpus_intelligence import (
    get_frame_corpus_context,
    get_dimension_corpus_context,
    get_corpus_summary,
)


# ── Provenance: hosting state disclosure ──────────────────────────

PRODUCTION_STATUS = "active"
PRODUCTION_STATUS_NOTE = (
    "Production hosting at frame.clarethium.com is active. The "
    "tool_url, methodology_paper, frame_library, and "
    "calibration_corpus fields in this provenance block resolve "
    "directly. Always-resolvable mirrors that survive any future "
    "hosting transition: GitHub repository "
    "https://github.com/Clarethium/frame-check; PyPI package "
    "frame-check-mcp (this server)."
)


# ── Provenance builder ────────────────────────────────────────────

def _build_provenance(
    analysis_layer: str,
    elapsed_ms: int,
    determinism_note: str | None = None,
) -> dict[str, Any]:
    """Build the provenance block shared by every MCP tool response.

    Keeping construction in one place means a version bump,
    license correction, or citation update propagates to every
    tool automatically. Callers pass the analysis_layer they are
    producing (deterministic_structural_only / _plus_verification
    / _comparison) and, when the default determinism claim is not
    right for the shape of the response, an explicit override.
    The default phrasing is singular ("identical input"); the
    compare tool uses "identical input pair" because two documents
    are the unit of determinism there.
    """
    _ensure_caches()
    # SERVER_VERSION is imported here, not at module top, to avoid a
    # `python mcp_server.py` re-entry cycle where mcp_server runs as
    # __main__ and a separate `mcp_server` module gets re-loaded by
    # mcp_compose's import. See the module docstring's import-cycle
    # note. By the time _build_provenance runs, the import graph is
    # settled and this resolves cleanly.
    from mcp_server import SERVER_VERSION
    from version import FRAME_CHECK_VERSION
    from clarethium_measure import __version__ as CLARETHIUM_VERSION
    import datetime as _dt

    note = determinism_note or (
        "Identical input produces identical output. No LLM is "
        "invoked in this response."
    )
    # UTC timestamp of the response, in ISO-8601 with a trailing Z.
    # Academic citations frequently want wall-clock precision
    # ("as of 2026-04-17T15:32:00Z, Frame Check v1.3 found X");
    # without this field an agent quoting the analysis would have to
    # generate the timestamp separately and race the actual analysis
    # time. The format is seconds-precision because sub-second
    # resolution would add apparent precision that the measurement
    # does not carry.
    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
    timestamp_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "tool_name": "Frame Check",
        "tool_url": "https://frame.clarethium.com",
        "tool_author": "Lovro Lucic",
        "methodology_paper": "https://frame.clarethium.com/corpus/methodology/",
        "frame_library": "https://frame.clarethium.com/corpus/library/",
        "calibration_corpus": "https://frame.clarethium.com/corpus/calibration/",
        "production_status": PRODUCTION_STATUS,
        "production_status_note": PRODUCTION_STATUS_NOTE,
        "license": {
            "code": "Apache-2.0",
            "corpus": "CC-BY-4.0",
            "analysis_output": (
                "CC-BY-4.0 - this response may be reproduced with "
                "attribution to Frame Check."
            ),
        },
        "frame_check_version": FRAME_CHECK_VERSION,
        # The MCP server's wheel version. Distinct axis from
        # frame_check_version above (which is the brand/methodology
        # version, also stamped into telemetry events and CITATION.cff;
        # see version.py for the two-axes rationale). server_version
        # is the version an MCP integrator sees in the initialize
        # handshake's serverInfo.version; surfacing it in provenance
        # lets agents and bug reports cross-reference the wheel without
        # having to re-issue an initialize handshake. Both fields are
        # legitimate; an integrator running frame-check-mcp 0.8.x
        # against a Frame Check methodology snapshot at brand version Y
        # will see server_version=0.8.x and frame_check_version=Y.
        "server_version": SERVER_VERSION,
        # clarethium_measure is the measurement stack. Its version
        # is pinned independently from the app version so MCP
        # clients can verify the measurement contract separately
        # from the site.
        "clarethium_measure_version": CLARETHIUM_VERSION,
        "frame_library_version": _get_frame_library_version(),
        # Engine identity. The MCP surface runs only the deterministic
        # Layer A stack server-side (regex detectors +
        # clarethium_measure verification). The V4.2 LLM-judge step is
        # delegated to the caller's agent per FRAME_DIVERGENCE_CONTRACT_v1
        # §7 "caller_side V4.2" regime.
        # Saved-analysis readers branch on framing_engine == "layer_a"
        # for the MCP-produced server-side block, same as the web
        # surface uses for its Layer A fallback path. engine_version is
        # the Layer A version space (independent of V4.2's semver).
        "engine_version": "1.0.0",
        "framing_engine": "layer_a",
        "analysis_cost_usd": 0.0,
        "analysis_latency_ms": elapsed_ms,
        "analysis_timestamp_utc": timestamp_iso,
        "analysis_layer": analysis_layer,
        "analysis_determinism": note,
        "citation": (
            f"Lucic, L. ({now.year}). Frame Check: a research "
            f"instrument for framing and verification in documents. "
            f"https://frame.clarethium.com"
        ),
    }


# ── Corpus-context helpers ────────────────────────────────────────

def _frame_corpus_context_or_none(fvs_id: str) -> dict[str, Any] | None:
    """Return per-frame corpus_context or None if unavailable.
    Centralizes the path arguments so call sites stay terse."""
    if not fvs_id:
        return None
    return get_frame_corpus_context(
        fvs_id, _CORPUS_ENTRIES_DIR, _AGGREGATE_RESULTS_DIR,
    )


def _dimension_corpus_context_or_none(dimension: str) -> dict[str, Any] | None:
    """Return per-dimension corpus_context or None if unavailable.
    Used by the cluster builder so each cluster can carry empirical
    dimension-level evidence."""
    if not dimension:
        return None
    return get_dimension_corpus_context(
        dimension, _CORPUS_ENTRIES_DIR, _AGGREGATE_RESULTS_DIR,
    )


def _corpus_summary_or_none() -> dict[str, Any] | None:
    """Return whole-corpus summary for the divergence envelope, or
    None if unavailable. Carries the small-N caveat so the agent
    surfacing prevalence stays construct-honest."""
    return get_corpus_summary(
        _CORPUS_ENTRIES_DIR, _AGGREGATE_RESULTS_DIR,
    )


# ── Document signals aggregator ───────────────────────────────────

def _build_document_signals(analysis: dict[str, Any]) -> dict[str, Any]:
    """Assemble doc_signals dict for pattern matching. Pulls from
    frame_deepening (temporal_scope, stakeholder_map,
    falsification_conditions), epistemic (sourced_pct), voice
    (classification), and claims_extracted (hedge ratio).

    Signals that are unavailable (None or missing in analysis)
    pass through as None; pattern triggers degrade to FVS-only
    logic when their discriminator signal is absent (graceful
    degradation discipline)."""
    fd = analysis.get("frame_deepening", {}) or {}
    ts = fd.get("temporal_scope") or {}
    sm = fd.get("stakeholder_map") or {}
    fc = fd.get("falsification_conditions") or {}
    epist = analysis.get("epistemic", {}) or {}
    voice = analysis.get("voice", {}) or {}
    claims = analysis.get("claims_extracted", {}) or {}
    total = claims.get("total") or 0
    hedged = claims.get("hedged_count") or 0
    hedge_ratio = (
        round(hedged / total, 3) if total > 0 else None
    )
    return {
        "falsification_count": fc.get("primary_match_count"),
        "stakeholder_role_count": sm.get("role_count"),
        "projection_phrase_count": ts.get("projection_phrase_count"),
        "sourced_pct": epist.get("sourced_pct"),
        "voice_label": voice.get("classification"),
        "hedge_ratio": hedge_ratio,
    }


# ── MCP contract v2 dimension builders ────────────────────────────

def _build_coverage_v2(cov: dict[str, Any]) -> dict[str, Any]:
    """Build the MCP contract v2 coverage payload from detect_coverage output.

    cov is the dict returned by framing.detect_coverage (v1 shape, unchanged).
    The v2 shape reorganizes the same information to carry the vocabulary-based
    construct through structure: per-dimension evidence (markers_matched),
    vocabulary samples, and a first-class construct block.

    """
    from framing import ANALYTICAL_VOCAB_SAMPLES

    categories = cov.get("categories", {}) or {}
    dimensions: dict[str, dict] = {}
    for cat_name in ("causes", "risks", "stakeholders", "trends", "uncertainty"):
        cat_entry = categories.get(cat_name, {}) or {}
        density = cat_entry.get("density_per_1kw", 0) or 0
        markers = list(cat_entry.get("markers_matched", []) or [])
        truncated = bool(cat_entry.get("markers_matched_truncated", False))
        covered = bool(cat_entry.get("covered", False))
        dim_entry = {
            "status": "detected" if covered else "not_detected",
            "markers_matched": markers,
            "markers_matched_truncated_at_20": truncated,
            "marker_count": int(cat_entry.get("count", 0) or 0),
            "density_per_1kw": float(density),
            "signal_strength": _signal_strength_for(density),
            "vocabulary_searched_sample": ANALYTICAL_VOCAB_SAMPLES.get(cat_name, []),
            "vocabulary_source": (
                f"framing.py::ANALYTICAL_CATEGORIES[\"{cat_name}\"]"
            ),
        }
        # Sentence-level attribution, when detect_coverage was called with
        # include_attribution=True. Passes through the per-match sentence
        # mapping so agents can cite WHERE the marker fired, not just that
        # it did. Empty list when attribution was not computed.
        sentence_matches = cat_entry.get("sentence_matches")
        if sentence_matches is not None:
            dim_entry["sentence_matches"] = sentence_matches
            dim_entry["distinct_sentences_detected"] = int(
                cat_entry.get("distinct_sentences_detected", 0) or 0
            )
        # Candidate-miss surfacing, when detect_coverage was called with
        # include_candidates=True. Only populated for not-detected
        # dimensions per framing.detect_coverage contract. Construct-
        # honest: each candidate carries an explicit caveat field.
        candidate_sentences = cat_entry.get("candidate_sentences")
        if candidate_sentences is not None:
            dim_entry["candidate_sentences"] = candidate_sentences
        dimensions[cat_name] = dim_entry

    detected_count = sum(1 for d in dimensions.values() if d["status"] == "detected")
    total_count = len(dimensions)
    return {
        "contract_version": 2,
        "dimensions": dimensions,
        "summary": {
            "dimensions_with_detected_markers": detected_count,
            "dimensions_without_detected_markers": total_count - detected_count,
            "total_dimensions": total_count,
            "coverage_balance": cov.get("coverage_balance"),
        },
        "construct": {
            "signal_type": "vocabulary_and_pattern_detector",
            "statement": (
                "The coverage signal is vocabulary-and-pattern based. Each "
                "dimension has a regex expressing the lexical markers the "
                "detector counts as evidence. 'detected' means the detector "
                "matched at least one marker; 'not_detected' means it "
                "matched none. Both directions carry measurement error: "
                "'detected' may be substantive or nominal (see "
                "signal_strength and density_per_1kw), and 'not_detected' "
                "may reflect vocabulary the detector does not recognize "
                "rather than absence of coverage in the document. The "
                "measurement is a lower-bound claim about vocabulary, not "
                "an upper-bound claim about the document."
            ),
            "reference": (
                "https://frame.clarethium.com/corpus/methodology/"
            ),
            "how_to_serialize": (
                "When restating this analysis to a user, say 'the detector "
                "found markers for X, Y, Z' rather than 'the document covers "
                "X, Y, Z.' Say 'no markers detected for X' rather than 'the "
                "document does not address X.' Under-detection is a known "
                "failure mode and this construct statement is the "
                "authoritative phrasing."
            ),
        },
    }


def _build_voice_construct(voice: dict[str, Any]) -> dict[str, Any]:
    """Build the Phase B voice construct block for MCP v2.

    Unlike the lower-bound detection posture (coverage/epistemic/claims),
    voice is a cascade classification signal: every document is
    classified; there is no 'not_detected' state. The analogous
    construct posture is classification-confidence: expose the
    margin to the winning rule's thresholds, the runner-up class, and
    a borderline flag when a small feature change could flip the
    classification.

    Returns a dict suitable for embedding as `voice.construct` in the
    MCP payload. Parallels the `coverage_v2.construct` block shape.
    """
    return {
        "signal_type": "cascade_classification",
        "statement": (
            "Voice classification is a 7-rule deterministic cascade. "
            "The winning class is the first rule whose threshold "
            "conditions are satisfied. margin_to_threshold is the best "
            "margin across the winning class's firing rules (positive "
            "= decisively crossed; near zero = barely crossed). "
            "runner_up is the next cascade class (different from "
            "winner) that would be evaluated if the winner's rule had "
            "not fired; runner_up_margin is that class's best rule "
            "margin (positive = it would fire too, preempted by "
            "cascade; negative = missed activation by that much). "
            "confidence is 'borderline' when margin_to_threshold < 2 "
            "or runner_up_margin > -2 (small feature change could "
            "flip the classification); 'high' otherwise. This is the "
            "classification-confidence construct: the analogue for "
            "categorical signals of the lower-bound detection posture "
            "used for presence/absence signals (coverage, epistemic, "
            "claims)."
        ),
        "reference": (
            "https://frame.clarethium.com/corpus/methodology/"
        ),
        "how_to_serialize": (
            "When restating this classification to a user, say "
            "'classified as X' rather than 'the document is X.' "
            "When confidence is 'borderline', name the runner-up "
            "class explicitly: 'classified as X, borderline; Y nearly "
            "fired.' Do not restate a borderline classification as "
            "decisive. When confidence is 'high' AND voice is NOT "
            "'analytical', the classification is safe to restate "
            "without the margin caveat. When voice is 'analytical', "
            "note that analytical is the cascade RESIDUAL: no "
            "prescriptive/promotional/descriptive/advisory rule fired, "
            "so the label reflects absence of positive voice evidence "
            "rather than decisive analytical detection. Restate as "
            "'classified as analytical (no other voice markers "
            "detected)' rather than 'the document is analytical.' "
            "This mirrors the under-detection discipline applied to "
            "the coverage signal."
        ),
    }


def _build_temporal_construct(temp: dict[str, Any]) -> dict[str, Any]:
    """Build the Phase B temporal construct block for MCP v2.

    Temporal is a distribution signal (past/present/future percentages
    summing to 100). The construct posture surfaces
    `dominant_margin` (lead over runner-up tense) and a `balanced` flag
    (no tense reaches 50% and dominant margin < 10 points). A balanced
    document should not be read as time-anchored regardless of the
    dominant label.

    Returns a dict suitable for embedding as `temporal.construct`.
    """
    return {
        "signal_type": "distribution_with_dominant",
        "statement": (
            "Temporal orientation is the distribution of past, "
            "present, and future tense markers across sentences "
            "(summing to approximately 100%). The dominant tense is "
            "the highest percentage; dominant_margin is the lead over "
            "the second-place tense. balanced is True when no tense "
            "reaches 50% and dominant_margin is under 10 points; in "
            "that state the document is temporally spread and the "
            "dominant label does not signal time-anchoring. A "
            "high-margin dominant (e.g., past at 75%) is a genuine "
            "time-anchor; a low-margin dominant (e.g., past at 38%, "
            "present at 35%) is not. Reader judgment integrates the "
            "dominant label with the margin."
        ),
        "reference": (
            "https://frame.clarethium.com/corpus/methodology/"
        ),
        "how_to_serialize": (
            "When restating, say 'X-oriented with a Y-point margin "
            "over the runner-up tense' rather than 'the document is "
            "X-oriented.' When balanced is True, say 'temporally "
            "balanced; no tense dominates' rather than restating the "
            "dominant label. The dominant field is still populated "
            "when balanced=True but should be treated as a weak "
            "signal."
        ),
    }


# ── Per-level construct treatment ────────────────────────────────────
#
# The substrate produces three qualitatively different kinds of claim:
# detector measurements, classifier outputs, and composed patterns.
# Evidence discipline applies differently at each level: a
# detector firing is a lower-bound vocabulary claim; a classifier
# output is a margin-aware classification with no IRR data; a composed
# pattern's trigger is deterministic but its reading is a single-curator
# normative claim about what the trigger means.
#
# Each composed entity in the substrate carries a `claim_level` field
# pointing at one of the three treatments. Agents (and external
# evaluators) read agent_guidance.claim_level_treatments for the
# per-level discipline, then cite each entity per the matching
# treatment. This makes the substrate's epistemic claim chain explicit
# instead of inheriting one composition_discipline across all levels.

_CLAIM_LEVEL_DETECTOR = "detector_measurement"
_CLAIM_LEVEL_CLASSIFIER = "classifier_output"
# Added 2026-04-28 per CONSTRUCT_VALIDITY_AUDIT_v1 v1.2 / OPEN_DECISIONS
# v1 D1 Proposal A. Names the LLM-judge binary classification shape
# distinct from `classifier_output`'s deterministic-cascade-with-
# confidence shape. V4.2 emissions are the canonical instance: binary
# `exhibits` value with reasoning text and per-frame reliability tier
# but no per-emission confidence or runner-up. The borderline-vs-
# decisive distinction is a property of the macro aggregate (macro-F1
# across the validation corpus, intra-rater AC1 across run-pairs)
# rather than the per-emission. As of 2026-04-28 V4.2 ships only on
# the evaluation engine surface; the first MCP wheel that ships V4.2
# emissions on the wire MUST tag them with this claim_level.
_CLAIM_LEVEL_LLM_CLASSIFIER = "llm_classifier_output"
_CLAIM_LEVEL_COMPOSED = "composed_pattern"
_CLAIM_LEVEL_AGENT_GENERATED = "agent_generated"

# Module-level constant: the per-level construct treatments. Built
# once at import (no inputs, no per-call variation). Each treatment
# carries:
#   claim_type: one-line description of the claim shape at this level
#   validation_status: structured honesty about what is / isn't
#     validated (deterministic, methodology_documented,
#     inter_rater_reliability, validity_data)
#   caveats: list of specific things the agent must surface when citing
#   how_to_cite: phrasing template (used in tandem with the per-signal
#     construct.how_to_serialize fields where present)
#
# The treatments are keyed by claim_level value so the agent can look
# up the discipline from the entity's claim_level. The substrate stays
# construct-honest: validation_status names what is NOT yet measured
# (no inter-rater reliability pilot on the classifier or pattern
# catalog; no precision/recall against labeled gold-standard) so the
# agent does not over-claim on the user's behalf.
_CLAIM_LEVEL_TREATMENTS: dict[str, Any] = {
        _CLAIM_LEVEL_DETECTOR: {
            "claim_type": (
                "Deterministic feature/regex detector firing or "
                "non-firing on the document text."
            ),
            "validation_status": {
                "deterministic": True,
                "methodology_documented": True,
                "inter_rater_reliability": "not_applicable",
                "validity_data": (
                    "Vocabulary-and-pattern detection with documented "
                    "lower-bound detection posture. Per-signal construct blocks "
                    "(analysis.coverage_v2.construct, "
                    "analysis.epistemic.note, candidate-miss surfacing "
                    "on coverage / epistemic / claims) carry the "
                    "detector-specific caveats. IRR is not applicable "
                    "to algorithmic detectors; reproducibility is the "
                    "validity claim and is documented per signal."
                ),
            },
            "caveats": [
                ("Detector firing is a lower-bound vocabulary claim, "
                "not an upper-bound document claim."),
                ("Non-firing may reflect vocabulary the detector does "
                "not recognize rather than absence of the dimension "
                "in the document."),
                ("Cite as 'Frame Check's detector found markers for "
                "X' or 'no markers detected for X' rather than 'the "
                "document covers X' or 'the document does not "
                "address X'."),
            ],
            "how_to_cite": (
                "Frame Check's detector found markers for X / no "
                "markers detected for X."
            ),
        },
        _CLAIM_LEVEL_LLM_CLASSIFIER: {
            "claim_type": (
                "LLM-judge binary or categorical classification with "
                "curated definition + reasoning text but WITHOUT "
                "per-emission confidence/runner-up structure. V4.2 "
                "FVS detection is the canonical instance."
            ),
            "validation_status": {
                "deterministic": False,
                "methodology_documented": True,
                "inter_rater_reliability": "macro_aggregate_only",
                "validity_data": (
                    "Reliability is reported at the macro aggregate "
                    "level (macro-F1 across the validation corpus, "
                    "intra-rater AC1 across run-pairs), not at the "
                    "per-emission level. The borderline-vs-decisive "
                    "distinction is a property of the aggregate, not "
                    "the per-emission. Two named per-frame chronic "
                    "gaps (FVS-007 over-fire, FVS-001 low-recall) "
                    "are diagnosed at substrate level."
                ),
            },
            "caveats": [
                ("The reasoning text is the engine's rationale for "
                "the binary judgment, not a confidence proxy. Do not "
                "paraphrase it as 'Frame Check is X% confident'."),
                ("Per-emission borderline-vs-decisive distinction is "
                "unavailable. Cite the per-frame reliability tier as "
                "the macro-aggregate evidence; do not treat any "
                "single emission as decisive without disclosing the "
                "intra-rater variance."),
                ("Surface honest_limit caveats verbatim when the "
                "engine emits one. The honest_limit text is per-"
                "frame and names the operationalization gap in "
                "single-emission terms."),
                ("The construct is LLM-judged, not deterministic. "
                "Two engine runs on the same document at temperature "
                "0 can disagree on individual binary judgments at "
                "rates within the moderate-noise band; aggregate "
                "reliability is the load-bearing evidence."),
            ],
            "how_to_cite": (
                "Frame Check's V4.2 engine judged the document as "
                "exhibiting X (tier Y reliability; honest_limit Z "
                "when present)."
            ),
        },
        _CLAIM_LEVEL_CLASSIFIER: {
            "claim_type": (
                "Deterministic cascade or scoring classifier with "
                "margin-aware confidence and runner-up reporting."
            ),
            "validation_status": {
                "deterministic": True,
                "methodology_documented": True,
                "inter_rater_reliability": "not_yet_measured",
                "validity_data": (
                    "Classifier uses deterministic feature scoring "
                    "with documented thresholds; abstains without "
                    "feature evidence (post-2026-04 fix on the genre "
                    "classifier closes the no-features-but-claims "
                    "advocacy artifact). No precision/recall against "
                    "labeled gold-standard yet; no inter-rater "
                    "reliability pilot. Per-signal construct blocks "
                    "(voice.construct cascade-classification, "
                    "temporal.construct distribution-with-dominant, "
                    "genre.construct per-genre description) carry the "
                    "classifier-specific caveats."
                ),
            },
            "caveats": [
                ("Classifier confidence is margin-to-runner-up, not "
                "external validity data."),
                ("Borderline classifications must surface the "
                "runner-up explicitly so the cascade's hesitation is "
                "visible to the reader."),
                ("Single-author calibrated; no IRR data; treat the "
                "classification as Frame Check's reading rather than "
                "a measured property of the document."),
            ],
            "how_to_cite": (
                "Frame Check classified as X (confidence Y; "
                "runner-up Z when borderline)."
            ),
        },
        _CLAIM_LEVEL_COMPOSED: {
            "claim_type": (
                "Substrate-side composition over detector and "
                "classifier outputs. Trigger conditions are "
                "deterministic; the reading text inside the "
                "composition is a single-curator normative claim "
                "about what the trigger means."
            ),
            "validation_status": {
                "deterministic": True,
                "methodology_documented": True,
                "inter_rater_reliability": "not_yet_measured",
                "validity_data": (
                    "Trigger conditions deterministic and "
                    "reproducible (canon-graph set membership for "
                    "absence_clusters; multi-frame plus doc-signal "
                    "discriminators for frame_patterns). The reading "
                    "text and the curator's pattern catalog (eight "
                    "named patterns in frame_patterns._PATTERNS; "
                    "five canonical dimension cluster readings in "
                    "_DIMENSION_CLUSTER_READINGS) are single-author "
                    "authored. No IRR pilot has measured whether "
                    "other readers compose the same patterns from "
                    "the same triggers; no precision/recall against "
                    "an external rater set."
                ),
            },
            "caveats": [
                ("The trigger match is reproducible; the reading "
                "inside is the curator's normative claim about what "
                "the trigger means."),
                ("Cite the reading as Frame Check's reading, not as "
                "a measured property of the document."),
                ("No inter-rater reliability data on whether other "
                "readers would compose the same pattern from the "
                "same triggers; treat the named composition as "
                "Frame Check's recognition of a structural shape, "
                "not a verdict on the document."),
            ],
            "how_to_cite": (
                "Frame Check identified pattern X (composed "
                "deterministically by trigger Y); the substrate's "
                "reading of pattern X is: ..."
            ),
        },
        _CLAIM_LEVEL_AGENT_GENERATED: {
            "claim_type": (
                "Opt-in LLM-composed content. The substrate "
                "delegates the composition to an external model "
                "(provider + model + cost tracked per-output in "
                "model_provenance). Distinct from the other three "
                "levels because the output is non-deterministic: "
                "different runs by different model versions can "
                "produce different content from the same inputs."
            ),
            "validation_status": {
                "deterministic": False,
                "methodology_documented": True,
                "inter_rater_reliability": "not_applicable",
                "validity_data": (
                    "LLM-composed content; reproducibility is not "
                    "the validity claim because the output is "
                    "non-deterministic by design (Item 12 strategic "
                    "discipline). Each output carries "
                    "model_provenance with provider, model, cost in "
                    "USD, input/output token counts, and "
                    "is_deterministic=false. The substrate-"
                    "deterministic identity is preserved: when the "
                    "opt-in flag is omitted, the substrate composes "
                    "without LLM (clusters, patterns, absences with "
                    "goal/genre relevance) and the agent gets the "
                    "deterministic substrate alone. IRR is not "
                    "applicable because the output is generative; "
                    "different models or different runs producing "
                    "different content is the design, not a "
                    "validity gap."
                ),
            },
            "caveats": [
                ("Generated content is non-reproducible across "
                "model versions and runs; cite the model_"
                "provenance fields (provider, model, cost) as the "
                "audit trail."),
                ("The frame's general teaching_question_general is "
                "the stable catalog reference; the generated_"
                "question is one document-specific application "
                "composed by the LLM, not a measurement."),
                ("Never present LLM-generated content as Frame "
                "Check's measurement; the construct-honest cite "
                "is 'Frame Check requested an LLM-composed "
                "question (provider X, model Y, cost Z; "
                "is_deterministic=false in model_provenance); the "
                "generated application is: ...'."),
            ],
            "how_to_cite": (
                "Frame Check requested an LLM-composed question "
                "(provider X, model Y, cost Z USD; "
                "is_deterministic=false in model_provenance); the "
                "generated application of FVS-N's general teaching "
                "question to this document is: ..."
            ),
        },
}


def _apply_v2_only_preference(payload: dict[str, Any]) -> None:
    """Remove the legacy v1 coverage block when the client prefers v2.

    Leaves coverage_v2 as the only coverage field. Intended for clients
    that have migrated to v2 and want to avoid payload duplication.
    Keeps all other signals (voice, temporal, epistemic, claims) in
    their v1 shape since the v2 redesign for those is deferred to v3.

    Phase 1: additive emission is the default. Phase 2 (future
    release) adds a deprecation notice to v1. Phase 3 (conditional)
    stops emitting v1 regardless of preference.
    """
    analysis = payload.get("analysis") or {}
    if "coverage" in analysis and "coverage_v2" in analysis:
        # Drop v1 coverage; promote v2 by keeping it under its current key.
        del analysis["coverage"]


# ── Frame Divergence block (FRAME_DIVERGENCE_CONTRACT_v1 Part 2) ─────
#
# Per the contract: when `include_divergence=true` is passed to
# frame_check, the response carries a top-level `divergence` block
# alongside analysis / agent_guidance / provenance, plus two
# agent_guidance additions. This function builds that block.
#
# MCP-surface semantics (Contract §7.1): Frame Check's MCP server
# does NOT invoke an external LLM. absent_frames are computed from
# the library_v3 catalog minus frames present in V1 frame_library_matches;
# `absence_basis` is scaffolding text describing what the caller's
# model should verify; `agent_guidance.how_to_render_divergence`
# carries V4.2 judge prompt scaffolding so the caller's own agent
# model can complete the composition.
#
# Contract §2.3 reserves the names `frame_divergence`, `frame_inventory`,
# `frame_gap` in the MCP tool namespace. This implementation honors
# Rec II (enhance `frame_check`, no separate tool).


def _extract_teaching_question(md_path: str) -> str | None:
    """Extract the first "Teaching question" line from an FVS entry
    markdown file. Returns None if the entry does not define one.
    """
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    import re as _re
    m = _re.search(
        r'(?:^|\n)(?:\*\*)?Teaching question(?:\*\*)?[:\s]+(.+?)(?=\n\n|\n\*\*|\Z)',
        text, flags=_re.IGNORECASE | _re.DOTALL,
    )
    if not m:
        return None
    return m.group(1).strip()[:400]


def _signal_strength_for_absent_frame(
    affects_dims: list[str],
    cov_missing: list[str],
) -> str:
    """Score an absent frame's reader-relevance for THIS document.

    Three tiers:
      - high: frame is canon for ≥2 decision-readiness dimensions
        AND the coverage dimension is canon for the frame AND the
        document is weak on coverage (any missing categories).
      - medium: frame is canon for ≥1 decision-readiness dimension.
      - low: frame is not canon for any decision-readiness dimension
        (e.g., FVS-013 Oracle, FVS-014 Temporal Anchoring,
        FVS-019 Narrative Coherence as meta-level frames).

    The heuristic uses only the canon-graph (DIMENSION_LIBRARY_ENTRIES
    in decision_readiness.py) plus the coverage-missing signal. It is
    deliberately conservative: a future move (per the §12 extension
    pattern) can layer in domain applicability metadata, full
    decision_readiness profile signals across all five dimensions,
    and document-content semantics. The current heuristic produces a
    defensible baseline that the caller's V4.2 model can override.
    """
    n_dims = len(affects_dims)
    coverage_canon = "coverage" in affects_dims
    coverage_weak = bool(cov_missing)
    if n_dims >= 2 and coverage_canon and coverage_weak:
        return "high"
    if n_dims >= 1:
        return "medium"
    return "low"


# Substrate-side composition over absent frames. Where the agent
# previously had to discover patterns across the absent_frames list
# (e.g., "these four absent frames cluster on the counterfactual
# dimension"), the substrate now surfaces the pattern directly with
# a dimension-specific reading. Each reading is curated, reading-
# form (not verdict-form), and tied to the canon-graph dimension
# definition. The five dimensions match DIMENSION_LIBRARY_ENTRIES in
# decision_readiness.py; new dimensions added there must add a
# matching reading here or get the construct-honest placeholder.
_DIMENSION_CLUSTER_READINGS = {
    "coverage": (
        "Load-bearing absences cluster on the coverage dimension: "
        "the document's framing leaves out perspectives that would "
        "broaden how it sees its subject. The reader cannot stress-"
        "test the analysis against viewpoints the framing does not "
        "carry."
    ),
    "calibration": (
        "Load-bearing absences cluster on the calibration dimension: "
        "the document does not signal where its confidence is "
        "provisional, where its claims are hedged, or where the "
        "evidence under-determines the conclusion."
    ),
    "evidence": (
        "Load-bearing absences cluster on the evidence dimension: "
        "the document's claims do not lean on citable sources, "
        "named authorities, or independent grounding the reader "
        "can verify."
    ),
    "robustness": (
        "Load-bearing absences cluster on the robustness dimension: "
        "the document does not test its claims against alternative "
        "interpretations, methodologies, or counter-evidence the "
        "framing would resist."
    ),
    "counterfactual": (
        "Load-bearing absences cluster on the counterfactual "
        "dimension: the document does not name conditions under "
        "which its conclusion would be wrong, alternative scenarios "
        "where the pattern shifts, or risks that would invalidate "
        "the framing."
    ),
}

# Cluster firing threshold. A cluster surfaces when at least
# _CLUSTER_MIN_ABSENT absent frames share a dimension AND the
# absent set covers at least _CLUSTER_MIN_CANON_FRACTION of that
# dimension's canon membership. The two-condition logic is
# calibration-honest: an absolute threshold of three would silently
# bias the substrate to surface only multi-canon dimensions
# (coverage, counterfactual) and never small-canon dimensions
# (calibration with 2 canon members; both absent is 100% of canon
# and a strong signal that an absolute threshold misses).
# Single-canon dimensions (evidence, robustness in DIMENSION_LIBRARY
# _ENTRIES) cannot reach 2 absent and so cannot cluster; that is
# honest, since "cluster" is meaningless for a one-element canon.
_CLUSTER_MIN_ABSENT = 2
_CLUSTER_MIN_CANON_FRACTION = 0.5

# Document word-count floor below which the cluster builder
# abstains. Below this floor, absent_frames is largely a function
# of catalog size minus a handful of matches (or zero matches);
# clusters fire mechanically on the canon graph rather than on a
# document signal worth surfacing. Mirrors frame_deepening's
# 100-word floor for analogous construct honesty.
_CLUSTER_MIN_DOCUMENT_WORDS = 100

# Tier order for cluster signal_strength aggregation.
_CLUSTER_TIER_ORDER = {"high": 0, "medium": 1, "low": 2}


def _build_absence_clusters(
    absent_records: list[dict],
    *,
    document_word_count: int | None = None,
    matched_frame_count: int | None = None,
    document_claim_count: int | None = None,
) -> list[dict]:
    """Group absent frames by shared canonical dimensions and surface
    clusters that meet the firing threshold.

    The cluster is the substrate's composition over the divergence
    set. Replaces agent-side cluster discovery with substrate-side
    cluster surfacing while staying deterministic (no LLM, no
    document-content semantics; only canon-graph set membership and
    aggregation of per-frame signal_strength).

    Each cluster carries:
      - dimension: canonical dimension name
      - member_frames: sorted FVS IDs that are absent and canon for
        this dimension
      - member_count: integer count of member frames
      - canon_size: total canon members for this dimension
      - canon_coverage_fraction: member_count / canon_size, rounded
        to two decimals
      - signal_strength: highest member-frame tier (high > medium >
        low); the cluster is at least as strong as its strongest
        member
      - reading: dimension-specific prose composition with member-
        count and canon-coverage anchoring

    Returns a list sorted by signal_strength (high first), then
    canon_coverage_fraction descending (most under-attended first),
    then dimension alphabetical for stable tiebreaking. Empty list
    when no dimension meets the firing threshold OR when the
    document is below the word-count floor (the substrate stays
    construct-honest about whether the absences carry document
    signal).
    """
    # Construct-honest abstention: below the word-count floor, the
    # absent set is dominated by catalog size minus a small number
    # of matches; clusters would fire on the canon graph rather
    # than on real document signal. Surface no clusters.
    if (
        document_word_count is not None
        and document_word_count < _CLUSTER_MIN_DOCUMENT_WORDS
    ):
        return []
    # Construct-honest abstention: when zero frames match, the
    # absent_records list IS the catalog. Clusters then surface
    # canon-graph structure rather than document signal. This
    # commonly fires on off-methodology text (non-English, code,
    # poetry, fragments) above the word-count floor; the matched-
    # frames count distinguishes those cases from documents whose
    # framing is genuinely under-attended on multiple dimensions.
    # Threshold is 1: a single match is enough to indicate the
    # detector found analytical signal.
    if matched_frame_count is not None and matched_frame_count == 0:
        return []
    # Construct-honest abstention: zero claims detected is a
    # second-line off-methodology signal. Some FVS detectors fire
    # vacuously on non-analytical text (e.g. FVS-007 fires when
    # 'risks' and 'uncertainty' are both missing and unhedged_pct
    # is high; on Lorem ipsum or code, all of those conditions
    # trivially hold). When the claim extractor found zero claims,
    # the document does not carry analytical content; clusters
    # would surface canon-graph noise.
    if (
        document_claim_count is not None
        and document_claim_count == 0
    ):
        return []

    from decision_readiness import DIMENSION_LIBRARY_ENTRIES

    # Index absent frames by dimension and capture each member's
    # signal_strength tier so the cluster can aggregate.
    by_dimension: dict[str, list[tuple[str, str]]] = {}
    for record in absent_records:
        affects_dims = record.get("affects_dimensions") or []
        fvs_id = record.get("frame_id")
        tier = record.get("signal_strength", "low")
        if not fvs_id:
            continue
        for dim in affects_dims:
            by_dimension.setdefault(dim, []).append((fvs_id, tier))

    clusters: list[dict] = []
    for dim, members in by_dimension.items():
        canon_size = len(DIMENSION_LIBRARY_ENTRIES.get(dim, []))
        if canon_size <= 0:
            # Unknown dimension; canon size unavailable. Skip to
            # avoid surfacing a cluster we cannot honestly anchor.
            continue
        member_count = len(members)
        if member_count < _CLUSTER_MIN_ABSENT:
            continue
        coverage_fraction = member_count / canon_size
        if coverage_fraction < _CLUSTER_MIN_CANON_FRACTION:
            continue

        # Aggregate signal_strength as the highest member tier; the
        # cluster is at least as strong as its strongest absence.
        member_tiers = [tier for _, tier in members]
        cluster_signal = min(
            member_tiers,
            key=lambda t: _CLUSTER_TIER_ORDER.get(t, 9),
        )

        sorted_frames = sorted(fvs_id for fvs_id, _ in members)
        reading_template = _DIMENSION_CLUSTER_READINGS.get(dim)
        if not reading_template:
            # Unknown dimension. Emit a construct-honest placeholder
            # so the agent sees the grouping; do not fabricate prose
            # for a dimension whose reading was not curated.
            reading_template = (
                f"Load-bearing absences cluster on the {dim} "
                f"dimension; a dimension-specific reading is not "
                f"yet curated for this canonical dimension."
            )
        # Anchor the curated reading in the cluster's evidence: how
        # many member frames out of canon are absent. This is the
        # smallest move from generic dimension prose to evidence-
        # specific reading while staying deterministic.
        reading = (
            f"{reading_template} "
            f"{member_count} of {canon_size} {dim}-canon frames "
            f"are absent in this document."
        )

        # corpus_context for this dimension cluster: empirical
        # dimension-level evidence from the aggregate (peer-pair
        # difference rate; cross-question outlier finding when
        # available). The cluster reading composes catalog assertion
        # ("the dimension is under-attended") with corpus evidence
        # ("and that dimension differs across N of M peer pairs in
        # our validation corpus"). None when aggregate unavailable.
        dim_corpus_ctx = _dimension_corpus_context_or_none(dim)

        clusters.append({
            "dimension": dim,
            "member_frames": sorted_frames,
            "member_count": member_count,
            "canon_size": canon_size,
            "canon_coverage_fraction": round(coverage_fraction, 2),
            "signal_strength": cluster_signal,
            # Per-level construct treatment: the cluster is a
            # composed_pattern (canon-graph set membership over
            # absent_frames; threshold-firing). Trigger is deterministic;
            # the reading text below is curator-authored. Cite per
            # agent_guidance.claim_level_treatments[composed_pattern].
            "claim_level": _CLAIM_LEVEL_COMPOSED,
            "reading": reading,
            "corpus_context": dim_corpus_ctx,
        })

    # Sort: signal_strength first (high before medium before low),
    # then canon_coverage_fraction descending (most under-attended
    # first), then dimension alphabetical for stable tiebreaking.
    clusters.sort(
        key=lambda c: (
            _CLUSTER_TIER_ORDER.get(c["signal_strength"], 9),
            -c["canon_coverage_fraction"],
            c["dimension"],
        )
    )
    return clusters


def _build_divergence_block(
    frame_library_matches: list[dict],
    *,
    domain_hint: str | None,
    rendering: str,
    catalog_version_pin: str | None,
    engine_status: str = "beta",
    cov_missing: list[str] | None = None,
    user_context_present: bool = False,
    document_genre: str | None = None,
    document_word_count: int | None = None,
    document_claim_count: int | None = None,
    user_goal: str | None = None,
    document_text_for_opportunities: str | None = None,
    include_frame_opportunities: bool = False,
    document_signals: dict | None = None,
    compose_budget: str = "full",
) -> dict[str, Any]:
    """Build the FRAME_DIVERGENCE_CONTRACT_v1 Part 2 `divergence` block.

    Signature is minimal but takes enough document signal (cov_missing)
    to score each absent frame's reader-relevance per the c1.0 §13
    signal_strength tier. Does NOT invoke any LLM (MCP surface per
    Contract §7.1).

    `rendering` affects only AbsentFrameRecord decoration
    (teaching_question present when "teaching_questions"). All other
    rendering variants are caller-rendered presentation layers over the
    same data.

    Returns the {divergence, agent_guidance_additions} pair; caller
    integrates both into the frame_check response.
    """
    # Pin catalog version (only library_v3 supported in c1.0)
    catalog_version = catalog_version_pin or "library_v3"
    if catalog_version != "library_v3":
        # Contract §9.1 CATALOG_VERSION_NOT_FOUND would be the error
        # code; for this initial integration we coerce to library_v3
        # and add a limitation. When additional catalog versions ship,
        # this path becomes an error.
        catalog_version = "library_v3"

    cov_missing = cov_missing or []

    library = _library_v3_entries()
    present_ids = {
        m.get("fvs_id") for m in frame_library_matches
        if isinstance(m, dict) and m.get("fvs_id")
    }

    # Pull the canon-graph (FVS -> decision-readiness dimensions) once
    # so each absent frame's tier can be computed in O(1).
    from decision_readiness import dimensions_affecting

    absent_records: list[dict] = []
    provisional_count = 0
    tier_counts = {"high": 0, "medium": 0, "low": 0}
    for fvs_id, title, md_path, version in library:
        if fvs_id in present_ids:
            continue

        # Contract §5.3: no frames currently flagged provisional under
        # library_v3. FVS-020 is excluded in _library_v3_entries(). The
        # stability field is retained so future library revisions can
        # flag frames without a contract change.
        stability = "stable"

        affects_dims = list(dimensions_affecting(fvs_id))
        signal = _signal_strength_for_absent_frame(affects_dims, cov_missing)
        tier_counts[signal] += 1

        affects_str = ", ".join(affects_dims) if affects_dims else None
        if signal == "high":
            relevance_rationale = (
                f"{fvs_id} is canon for {len(affects_dims)} decision-"
                f"readiness dimensions ({affects_str}); the document "
                f"is weak on coverage "
                f"({len(cov_missing)} of 5 categories not detected). "
                f"High reader-relevance signal."
            )
        elif signal == "medium" and affects_str:
            relevance_rationale = (
                f"{fvs_id} is canon for {len(affects_dims)} decision-"
                f"readiness dimension(s) ({affects_str}). Medium "
                f"reader-relevance signal; the caller's model decides "
                f"whether the absence matters for this document."
            )
        elif signal == "medium":
            relevance_rationale = (
                f"{fvs_id} has a domain-level signal but no canon-"
                f"graph link to decision-readiness dimensions. Medium "
                f"reader-relevance signal."
            )
        else:
            relevance_rationale = (
                f"{fvs_id} is a meta-level frame; not canon for any "
                f"decision-readiness dimension. Low reader-relevance "
                f"signal; consider only in cross-cutting analyses."
            )
        if domain_hint:
            relevance_rationale += f" Hinted domain: '{domain_hint}'."

        # corpus_context for this absent frame: empirical evidence
        # of how this frame behaves across the validation corpus.
        # Cite-back: the agent reading an absent frame gets
        # prevalence, typical co-absences, and corpus_resource_uris
        # pointing at corpus entries where THIS frame fires.
        # The agent can chain to those entries to see the frame in
        # use and contrast with the current document's absence.
        # None when corpus unavailable.
        frame_corpus_ctx = _frame_corpus_context_or_none(fvs_id)

        # goal_relevance for this absent frame: substrate-side
        # composition Item 11. When the user (or agent) signals a
        # goal (decide / brainstorm / persuade / learn / audit),
        # absences load-bearing for that goal carry priority +
        # reason. None when no goal is set or goal is 'audit'.
        from user_goals import get_goal_relevance as _get_goal_rel
        frame_goal_relevance = (
            _get_goal_rel(fvs_id, user_goal) if user_goal else None
        )

        # genre_relevance for this absent frame: substrate-side
        # composition Item 3. When the document is classified into
        # a structural genre (recommendation, analysis, narrative,
        # advocacy, exploration, instruction), some absences are
        # load-bearing for that genre's reasoning. The substrate
        # promotes those absences with a curated reason. None when
        # the document genre is unknown or this frame is not in the
        # genre's load-bearing list. Substrate stays deterministic;
        # the relevance map is curated per genre.
        from genre_classifier import get_genre_relevance as _get_gr
        frame_genre_relevance = (
            _get_gr(fvs_id, document_genre) if document_genre else None
        )

        record = {
            "frame_id": fvs_id,
            "frame_version": f"v{version}" if version else "v?",
            "frame_title": title,
            "stability": stability,
            "signal_strength": signal,
            # Per-level construct treatment: the absent_frame record
            # is a non-firing of the V1 detector. Cite per
            # agent_guidance.claim_level_treatments[detector_measurement].
            # signal_strength inside the record
            # is itself a classifier_output (canon-graph + coverage
            # weakness composition); the agent reading the tier should
            # honor classifier_output discipline (margin / runner-up /
            # IRR-not-yet) when surfacing the tier label.
            "claim_level": _CLAIM_LEVEL_DETECTOR,
            "affects_dimensions": affects_dims,
            "citation_uri": f"{RESOURCE_SCHEME}://library/{fvs_id}",
            # GitHub URL pointing at the entry's markdown source on
            # the public repository (Clarethium/frame-check). End-users
            # in MCP clients (Claude Desktop, Cursor) cannot click
            # frame-check://library/... resource URIs because those
            # are MCP-internal; the library_url gives them an HTTP
            # link they can follow. Always-resolvable regardless of
            # hosted-production status. None when no canonical
            # filename is known for the ID.
            "library_url": (
                _library_entry_ref(fvs_id).get("public_url")
                if fvs_id else None
            ),
            "corpus_context": frame_corpus_ctx,
            "genre_relevance": frame_genre_relevance,
            "goal_relevance": frame_goal_relevance,
            # Contract §4.2 absence_basis on MCP: scaffolding string
            # for the caller's model to verify. Not prescriptive.
            "absence_basis": (
                f"Caller's model must confirm no {fvs_id} identification "
                f"cues fired in the supplied document. V1 rule-based "
                f"detection on this document did not match {fvs_id}. "
                f"See frame-check://library/{fvs_id} for identification "
                f"cues and counter-examples that inform the judgment."
            ),
            "domain_relevance_rationale": relevance_rationale,
        }

        # Contract §4.2 optional teaching_question: only emitted when
        # rendering is "teaching_questions". The FVS entry's teaching
        # question is extracted from the markdown body if present;
        # absent when the entry does not define one.
        if rendering == "teaching_questions":
            teaching_question = _extract_teaching_question(md_path)
            if teaching_question:
                record["teaching_question"] = teaching_question

        absent_records.append(record)

    # Sort absent_records by signal_strength tier (high first), then
    # frame_id ascending within tier. Stable, deterministic ordering
    # so a caller can take the first N entries and get the highest-
    # leverage absences without further filtering.
    _tier_order = {"high": 0, "medium": 1, "low": 2}
    # Sort: signal_strength tier first (catalog + coverage logic;
    # objective document signal). Within tier, goal_relevance
    # priority promotes (the user's stated intent). Within same
    # goal priority, genre_relevance priority promotes (the
    # document's structural shape). Within same genre priority,
    # frame_id alphabetical for stability.
    #
    # The composition: signal is empirical (catalog + coverage),
    # goal is user intent, genre is document state. Goal precedes
    # genre because the user's stated goal is more direct than
    # inferred document classification; signal precedes goal
    # because empirical signal cannot be overridden by user
    # preference. Records without a relevance entry sort with
    # priority 999 so they fall after curated entries.
    def _sort_key(r):
        gr = r.get("goal_relevance") or {}
        gnr = r.get("genre_relevance") or {}
        return (
            _tier_order.get(r["signal_strength"], 9),
            gr.get("priority", 999),
            gnr.get("priority", 999),
            r["frame_id"],
        )
    absent_records.sort(key=_sort_key)

    # Contract §4.3 envelope
    if domain_hint is None:
        domain_inferred = "unfiltered"
    else:
        # v1 implementation: pass-through hint; actual FVS-metadata-based
        # filtering is flagged as a limitation and deferred.
        domain_inferred = domain_hint

    limitations: list[str] = [
        ("V4.2 caller-side composition: absence_basis fields are "
        "scaffolding for the caller's agent model. Caller's model "
        "determines the final absence verdict per "
        "FRAME_DIVERGENCE_CONTRACT_v1 §7.1."),
    ]
    if domain_hint is not None:
        limitations.append(
            "Domain filter not yet wired to FVS entry metadata; "
            "all absent frames returned and envelope.domain_inferred "
            "echoes the hint without field-level filtering. Future "
            "contract minor version will add applicability metadata "
            "per FVS entry."
        )

    # Substrate-side composition: cluster absent frames by shared
    # canonical dimension. Where the agent previously had to discover
    # patterns across the absent_frames list, the substrate surfaces
    # the dimension-level theme directly. Stays deterministic; canon-
    # graph set membership only.
    absence_clusters = _build_absence_clusters(
        absent_records,
        document_word_count=document_word_count,
        matched_frame_count=len(frame_library_matches or []),
        document_claim_count=document_claim_count,
    )

    # Substrate-side composition Item 4: named structural patterns
    # over present-frame + absent-frame + genre combinations, with
    # corpus prevalence as empirical anchoring. Where clusters
    # surface dimension-level themes over absences alone, patterns
    # surface RECOGNIZED structural shapes that the substrate names
    # as load-bearing (e.g., "recommendation-without-falsification",
    # "growth-without-risk"). Stays deterministic.
    from frame_patterns import match_patterns as _match_patterns
    matched_ids_set: set[str] = {
        m["fvs_id"] for m in (frame_library_matches or [])
        if isinstance(m, dict) and isinstance(m.get("fvs_id"), str)
    }
    absent_ids_set: set[str] = {
        r["frame_id"] for r in absent_records
        if isinstance(r.get("frame_id"), str)
    }
    # doc_signals are passed through so pattern triggers can use
    # frame_deepening + epistemic discriminators beyond raw FVS
    # membership. Without these, patterns fire on most documents in
    # their target genre and lose discriminating value (a label
    # rather than a pattern). With them, patterns require document-
    # content evidence confirming the structural shape.
    # Forward all keys from document_signals so new pattern
    # discriminators (projection_phrase_count, voice_label,
    # hedge_ratio) are visible to the matcher. Dropping any key
    # silently degrades patterns that depend on it to FVS-only.
    doc_signals = dict(document_signals or {})
    triggered_patterns = _match_patterns(
        matched_ids_set, absent_ids_set, document_genre,
        doc_signals=doc_signals,
    )
    # For each triggered pattern, attach corpus_context with the
    # prevalence count over the validation corpus's frame-shape
    # match (genre constraint not applied to corpus matching at
    # this contract version; documented in count_corpus_pattern_
    # matches docstring). Also attach claim_level for the per-level
    # construct treatment: each pattern is a composed_pattern
    # (deterministic trigger over present + absent frames + doc
    # signals; curator-authored reading inside).
    for p in triggered_patterns:
        p["claim_level"] = _CLAIM_LEVEL_COMPOSED
        # Reconstruct the trigger from the pattern definition for
        # the corpus prevalence call. We have the pattern's
        # supporting_evidence but the original trigger is in
        # frame_patterns._PATTERNS; re-derive by looking up the id.
        from frame_patterns import _PATTERNS as _ALL_PATTERNS
        trigger = next(
            (pat["trigger"] for pat in _ALL_PATTERNS
             if pat["id"] == p["id"]),
            None,
        )
        if trigger is None:
            p["corpus_context"] = None
            continue
        if not isinstance(trigger, dict):
            p["corpus_context"] = None
            continue
        from corpus_intelligence import (
            count_corpus_pattern_matches as _count_pattern,
        )
        corpus_match = _count_pattern(
            trigger, _CORPUS_ENTRIES_DIR, _AGGREGATE_RESULTS_DIR,
        )
        if corpus_match is None:
            p["corpus_context"] = None
        else:
            n = corpus_match["matches"]
            tot = corpus_match["total"]
            tg = corpus_match.get("trigger_genre")
            n_in_genre = corpus_match.get("matches_in_genre")
            genre_tot = corpus_match.get("genre_total")
            ctx = {
                "prevalence": (
                    f"matches the frame-shape trigger of this "
                    f"pattern in {n} of {tot} corpus documents"
                ),
                "matches_count": n,
                "total_corpus": tot,
                "match_rate": corpus_match["match_rate"],
            }
            if tg and n_in_genre is not None and genre_tot:
                # Segmented prevalence (Item E): the more
                # statistically meaningful denominator. Only emit
                # when genre_total > 0 to avoid divide-by-zero noise.
                ctx["genre_segmented_prevalence"] = (
                    f"matches in {n_in_genre} of {genre_tot} "
                    f"corpus {tg}-genre documents"
                )
                ctx["matches_in_genre_count"] = n_in_genre
                ctx["genre_total"] = genre_tot
                ctx["genre_match_rate"] = corpus_match[
                    "genre_match_rate"
                ]
                ctx["trigger_genre"] = tg
                ctx["low_n_warning"] = corpus_match.get(
                    "genre_segmented_low_n_warning", False
                )
                if ctx["low_n_warning"]:
                    ctx["small_n_caveat"] = (
                        f"The trigger genre is '{tg}' but the "
                        f"corpus has only {genre_tot} document"
                        f"{'s' if genre_tot != 1 else ''} in that "
                        f"genre (low_n_warning=true). The segmented "
                        f"rate is not statistically meaningful at "
                        f"this denominator; cite as a corpus "
                        f"observation, not a population estimate. "
                        f"Full-corpus prevalence is included for "
                        f"reference but mixes genres."
                    )
                else:
                    ctx["small_n_caveat"] = (
                        f"The trigger genre is '{tg}'; segmented "
                        f"prevalence (matches_in_genre_count of "
                        f"genre_total) is the like-vs-like "
                        f"comparison and the more meaningful "
                        f"denominator. Full-corpus prevalence is "
                        f"included for reference. Both numbers are "
                        f"small-N; treat as corpus signals not "
                        f"population estimates."
                    )
            else:
                ctx["small_n_caveat"] = (
                    "Frame-shape match across the full corpus. "
                    "Pattern has no genre constraint, so segmented "
                    "prevalence is not applicable. Treat as small-N "
                    "corpus signal, not a population estimate."
                )
            p["corpus_context"] = ctx

    n_absent = len(absent_records)
    n_clusters = len(absence_clusters)
    catalog_size = len(library)
    if n_clusters > 0:
        cluster_dims = ", ".join(c["dimension"] for c in absence_clusters)
        cluster_phrase = (
            f" Substrate composes {n_clusters} absence cluster"
            f"{'s' if n_clusters != 1 else ''} on the {cluster_dims} "
            f"dimension{'s' if n_clusters != 1 else ''} (see "
            f"divergence.absence_clusters); each cluster names a "
            f"shared theme across multiple absent frames and is the "
            f"recommended composition starting point."
        )
    else:
        cluster_phrase = (
            f" No absence cluster met the minimum threshold "
            f"({_CLUSTER_MIN_ABSENT} or more absent frames sharing a "
            f"canonical dimension at >="
            f"{int(_CLUSTER_MIN_CANON_FRACTION * 100)} percent canon "
            f"coverage); the substrate did not compose a "
            f"dimension-level theme for this document."
        )
    # Genre-relative ranking phrase (Item 3). When the document is
    # classified into a genre, name how many absent_frames carry
    # genre_relevance; the sort already promotes those entries
    # within their tier.
    n_genre_relevant = sum(
        1 for r in absent_records if r.get("genre_relevance")
    )
    if document_genre and n_genre_relevant > 0:
        plural = n_genre_relevant != 1
        genre_phrase = (
            f" Document genre is '{document_genre}'; "
            f"{n_genre_relevant} absent frame{'s' if plural else ''} "
            f"{'carry' if plural else 'carries'} genre_relevance "
            f"(load-bearing for this genre's reasoning per the "
            f"curated per-genre map) and "
            f"{'are' if plural else 'is'} promoted within "
            f"{'their' if plural else 'its'} tier in the sort."
        )
    else:
        genre_phrase = ""
    n_goal_relevant = sum(
        1 for r in absent_records if r.get("goal_relevance")
    )
    if user_goal and user_goal != "audit" and n_goal_relevant > 0:
        plural_g = n_goal_relevant != 1
        goal_phrase = (
            f" User goal is '{user_goal}'; "
            f"{n_goal_relevant} absent frame"
            f"{'s' if plural_g else ''} "
            f"{'carry' if plural_g else 'carries'} goal_relevance "
            f"and {'are' if plural_g else 'is'} promoted within "
            f"{'their' if plural_g else 'its'} tier in the sort "
            f"(goal precedes genre in the within-tier ranking)."
        )
    elif user_goal == "audit":
        goal_phrase = (
            " User goal is 'audit'; the substrate applies the "
            "default catalog/coverage/genre ranking with no "
            "goal-specific override (audit is sovereignty posture: "
            "see the frame the document chose)."
        )
    else:
        goal_phrase = ""
    n_patterns = len(triggered_patterns)
    if n_patterns > 0:
        pattern_names = ", ".join(
            f"'{p['name']}'" for p in triggered_patterns
        )
        pattern_phrase = (
            f" Substrate matches {n_patterns} named structural "
            f"pattern{'s' if n_patterns != 1 else ''} on this "
            f"document: {pattern_names} (see "
            f"divergence.frame_patterns). Each pattern is a "
            f"recognized substrate composition over present and "
            f"absent frames; the curated reading is the substrate's "
            f"reading."
        )
    else:
        pattern_phrase = ""
    divergence_summary = (
        f"Catalog-driven perspective absence with faithfulness "
        f"constraints. {n_absent} of {catalog_size} catalog frames "
        f"not detected by V1 rule-based detection: "
        f"{tier_counts['high']} high-signal "
        f"({tier_counts['medium']} medium, "
        f"{tier_counts['low']} low). Records are sorted by "
        f"signal_strength so callers can take the first N and get "
        f"the highest-leverage absences.{cluster_phrase}{genre_phrase}{goal_phrase}{pattern_phrase} The reader's "
        f"model composes the perspective-widening interpretation per "
        f"agent_guidance.how_to_render_divergence; this block is the "
        f"substrate, not the verdict."
    )

    # Whole-corpus summary for envelope-level provenance. Carries
    # the small-N caveat so any prevalence statement on a per-frame
    # or per-dimension corpus_context lands honestly. None when
    # corpus is unavailable; envelope still emits, just without
    # the corpus_summary key (caller-side serializer drops Nones).
    corpus_summary = _corpus_summary_or_none()

    envelope = {
        "spec_version": _SPEC_VERSION,
        "catalog_version": catalog_version,
        "surface": "mcp",
        "divergence_summary": divergence_summary,
        "corpus_summary": corpus_summary,
        "v4_2_execution": {
            "location": "caller_side",
            "tier": "caller_model",
            "note": (
                "V4.2 judge step delegated to caller's agent model per "
                "Rec I. Frame Check's MCP server does not invoke an "
                "external LLM. See agent_guidance.how_to_render_divergence "
                "for composition instructions."
            ),
        },
        "v4_2_engine_status": engine_status,
        "v4_2_engine_status_reference": (
            "Engine status reflects production-readiness of the V4.2 "
            "detection layer; the value is informational for callers "
            "that gate on stability."
        ),
        "domain_inferred": domain_inferred,
        "provisional_count": provisional_count,
        "tier_counts": dict(tier_counts),
        "faithfulness_note": (
            "Absent frames are named from the FVS catalog as not "
            "detected in the supplied document. Domain relevance is "
            "the tool's best judgment. Whether any absent frame is "
            "useful is the thinker's call. This is not a list of "
            "frames that should have been used."
        ),
        "limitations": limitations,
    }

    # Item 12: opt-in LLM-augmented frame-opportunity composition.
    # When include_frame_opportunities=True, generate document-
    # specific questions for the top absent frames using the
    # absent frame's teaching question + document content + genre +
    # goal as the LLM prompt. Substrate-deterministic discipline:
    # each opportunity carries is_deterministic=False; total cost
    # is tracked; LLM unavailability degrades gracefully (empty
    # opportunities list with available=False).
    frame_opportunities_block: dict[str, Any] = {
        "opportunities": [],
        "total_cost_usd": 0.0,
        "available": None,
        "note": (
            "Frame-opportunity composition is opt-in via "
            "include_frame_opportunities=true. The deterministic "
            "substrate (clusters, patterns, absences with goal and "
            "genre relevance) provides the same insights without "
            "LLM cost when this flag is omitted. See "
            "agent_guidance.frame_opportunities_discipline for the "
            "rules that apply when opportunities are surfaced."
        ),
    }
    if include_frame_opportunities and document_text_for_opportunities:
        # Pre-populate teaching_question on the top N candidates,
        # regardless of rendering mode, so the LLM prompt has the
        # frame's curated teaching question as context. Source of
        # truth is frame_library.TEACHING_QUESTIONS (mirrors the
        # questions the firing rules emit; available for absent
        # frames that never fire).
        from frame_library import (
            get_teaching_question as _get_tq,
        )
        from frame_opportunities import (
            generate_frame_opportunities as _generate_opps,
        )
        candidates = []
        for record in absent_records[:3]:
            tq = record.get("teaching_question") or _get_tq(
                record["frame_id"]
            )
            enriched = dict(record)
            if tq:
                enriched["teaching_question"] = tq
            candidates.append(enriched)
        # Item C: pass substrate-level composition (cluster readings,
        # pattern readings) into the LLM prompt so the generated
        # questions consume the substrate's own composition rather
        # than treating absent frames in isolation.
        cluster_readings: list[str] = [
            c["reading"] for c in absence_clusters
            if isinstance(c.get("reading"), str)
        ]
        pattern_readings: list[str] = [
            p["reading"] for p in triggered_patterns
            if isinstance(p.get("reading"), str)
        ]
        result = _generate_opps(
            candidates,
            document_text_for_opportunities,
            document_genre=document_genre,
            user_goal=user_goal,
            cluster_readings=cluster_readings,
            pattern_readings=pattern_readings,
        )
        frame_opportunities_block.update({
            "opportunities": result["opportunities"],
            "total_cost_usd": result["total_cost_usd"],
            "available": result["available"],
        })
        if "unavailable_reason" in result:
            frame_opportunities_block["unavailable_reason"] = (
                result["unavailable_reason"]
            )

    # Apply compose_budget slicing: bound the substrate's output
    # volume so an agent
    # with a tight working-memory budget can request a compact reading
    # without losing structural shape. The envelope's tier_counts
    # remain PRE-slice (they reflect what the substrate found) so the
    # agent sees the truncation honestly rather than thinking the
    # substrate found fewer absences. The compose_budget_applied
    # field surfaces the slice level + per-layer truncation counts.
    #
    # Slice levels:
    #   minimal: top-3 absent_frames, top-1 cluster, top-1 pattern.
    #     agent_guidance compressed (downstream block). For agents in
    #     tight working-memory budgets (quick responses).
    #   standard: top-5 absent_frames, all clusters, all patterns.
    #     agent_guidance compressed (same compression as minimal).
    #     Middle ground; preserves full cluster + pattern surfaces
    #     while halving guidance token cost.
    #   full (default): unfiltered output, full inline guidance.
    #     Backwards-compatible with prior callers who omit the
    #     parameter; suitable for first-time orientation and
    #     methodology demos where worked examples earn their tokens.
    pre_slice_absent = len(absent_records)
    pre_slice_clusters = len(absence_clusters)
    pre_slice_patterns = len(triggered_patterns)
    if compose_budget == "minimal":
        absent_records = absent_records[:3]
        absence_clusters = absence_clusters[:1]
        triggered_patterns = triggered_patterns[:1]
    elif compose_budget == "standard":
        absent_records = absent_records[:5]
    # full: no slice

    compose_budget_applied = {
        "level": compose_budget,
        "absent_frames_returned": len(absent_records),
        "absent_frames_total": pre_slice_absent,
        "absence_clusters_returned": len(absence_clusters),
        "absence_clusters_total": pre_slice_clusters,
        "frame_patterns_returned": len(triggered_patterns),
        "frame_patterns_total": pre_slice_patterns,
        "note": (
            "compose_budget bounds output volume; envelope.tier_counts "
            "reflects PRE-slice counts. The agent should surface the "
            "truncation when relevant ('Frame Check identified N "
            "absences; showing top M')."
            if compose_budget != "full"
            else "compose_budget=full; no slicing applied."
        ),
    }

    divergence = {
        "absent_frames": absent_records,
        "absence_clusters": absence_clusters,
        "frame_patterns": triggered_patterns,
        "frame_opportunities": frame_opportunities_block,
        "envelope": envelope,
        "compose_budget_applied": compose_budget_applied,
    }

    # Contract §4.4: two required agent_guidance additions.
    agent_guidance_additions = {
        "how_to_render_divergence": (
            "To complete the divergence composition on the caller side: "
            "(1) START with divergence.absence_clusters when present. "
            "Each cluster groups absent frames sharing a canonical "
            "decision-readiness dimension (coverage, calibration, "
            "evidence, robustness, counterfactual) and carries a "
            "dimension-specific reading composed by the substrate. The "
            "cluster reading is Frame Check's composition over the "
            "divergence set; cite it as Frame Check's reading and use "
            "it as the lead synthesis ('the substrate reads the "
            "absences as concentrated on the X dimension because Y'). "
            "Then walk the supporting absent_frames entries that share "
            "the cluster's dimension. Clusters are prioritized over "
            "per-frame walks because they carry the dimension-level "
            "theme; the per-frame walk is supporting evidence. When "
            "absence_clusters is empty, fall back to per-frame "
            "composition over absent_frames. "
            "(2) For each entry in divergence.absent_frames, verify the "
            "absence_basis claim by inspecting the document with your "
            "own model's judgment. Records are sorted by signal_strength "
            "(high first); for most readers the high-tier entries are "
            "the load-bearing surface. "
            "(3) If you agree the frame is absent and reader-relevant, "
            "render it per the requested "
            f"divergence_rendering ('{rendering}'): 'list' = flat list "
            "with citations; 'completeness_check' = checklist with "
            "domain-relevance rationale; 'teaching_questions' = "
            "per-frame teaching question (already attached to records "
            "when requested); 'narrative' = single prose paragraph "
            "naming absent frames with citations inline. "
            "(4) NEVER restate absent frames or clusters as 'missing "
            "frames you should consider' or equivalent prescriptive "
            "language (contract §4.5). Say 'not detected in the "
            "current framing' or 'absent from the document'. The "
            "cluster reading describes what the framing does not do; "
            "it never tells the user what the document should have "
            "done. "
            "(5) Cite each absent frame by frame_id and citation_uri. "
            "Cite cluster readings as 'Frame Check's substrate-"
            "composition of the divergence set on the X dimension'. "
            "(6) Catalog version note: "
            "the divergence catalog is pinned to library_v3 per "
            "FRAME_DIVERGENCE_CONTRACT_v1 c1.0 contract stability. "
            "(6.4) Goal-relative ranking (Item 11): when the user "
            "(or agent on behalf of the user) has signalled a goal "
            "via the user_goal parameter (decide / brainstorm / "
            "persuade / learn / audit), absent frames load-bearing "
            "for that goal carry a goal_relevance dict with "
            "priority and reason. The absent_frames sort puts "
            "goal-relevance ahead of genre-relevance within tier; "
            "the agent surfacing absences should cite "
            "goal_relevance.reason as the structural basis ('for "
            "the goal of deciding, FVS-009 absent is load-bearing "
            "because risk-frame absence at decision time leaves "
            "downside structurally invisible'). The 'audit' goal "
            "applies no override (sovereignty posture); "
            "goal_relevance is None on every absent_frame. When "
            "user_goal is omitted, behavior matches 'audit'. "
            "(6.5) Genre-relative ranking (Item 3): when the "
            "document is classified into a structural genre "
            "(analysis.genre.classification), absent frames that "
            "are load-bearing for that genre's reasoning carry a "
            "genre_relevance dict with priority and reason. The "
            "absent_frames sort promotes genre-relevant entries "
            "within their tier; the agent surfacing absences "
            "should cite genre_relevance.reason as the structural "
            "basis ('for recommendation genre, FVS-007 absent is "
            "load-bearing because recommendations without "
            "falsification conditions cannot be stress-tested'). "
            "Genre-relevance is curated per genre; reasons are "
            "reading-form not verdict-form. "
            "(6.7) Named structural patterns (Item 4): when "
            "divergence.frame_patterns is non-empty, the substrate "
            "has matched one or more recognized structural shapes "
            "(e.g., 'recommendation-without-falsification', "
            "'growth-without-risk'). Each pattern carries a curated "
            "reading composing present and absent frames into a "
            "named composition, plus corpus_context with prevalence "
            "(how often the same frame-shape appears in the "
            "validation corpus). Patterns are stronger evidence "
            "than per-frame walks because they name a recognized "
            "shape; lead with the pattern reading when present, "
            "before walking individual absent_frames or clusters. "
            "Cite the pattern's id and the frames in "
            "supporting_evidence inline. The same prescription-"
            "prevention discipline applies: pattern readings name "
            "what the framing does, never what the document should "
            "have done. "
            "(7) Corpus context layer: when "
            "envelope.corpus_summary is non-null, every frame and "
            "cluster carries an empirical context block. For matched "
            "and absent frames, corpus_context.prevalence reports "
            "firing rate across Frame Check's validation corpus "
            "(small N; honor the small_n_caveat). typical_co_fires "
            "and typical_co_absences name structural patterns the "
            "corpus has surfaced. corpus_entries_fired_uris point "
            "back to specific corpus entries; cite as 'in our "
            "validation corpus, X fires alongside Y at rate Z; see "
            "frame-check://corpus/{slug}'. For clusters, "
            "corpus_context.peer_pair_difference_rate is empirical "
            "evidence the dimension is consequential under peer "
            "comparison; cross_question_outlier names a specific "
            "model-by-dimension outlier finding from validation. "
            "Cite corpus context only when it sharpens the reading; "
            "small-N data should not become rhetorical scenery. "
            "(7.1) Genre-segmented prevalence discipline. Per-frame "
            "corpus_context.fires_in_by_genre carries one stat per "
            "genre bucket (recommendation, analysis, narrative, "
            "advocacy, exploration, instruction, plus _unclassified "
            "for documents the genre classifier abstained on). For "
            "each: fires_in_count, genre_total, rate, "
            "low_n_warning (true when genre_total < 3), and "
            "is_unclassified_bucket. Discipline: prefer the "
            "segmented denominator over the full-corpus rate when "
            "available; cite as 'fires in N of M Y-genre documents' "
            "rather than 'fires in N of total documents'. When "
            "low_n_warning=true on a genre, do NOT cite the rate "
            "as if statistically calibrated; the substrate is "
            "construct-honest about per-genre denominators. NEVER "
            "cite the _unclassified bucket as if it were a genre; "
            "it is documents whose structural shape couldn't be "
            "inferred. For frame_patterns, "
            "corpus_context.genre_segmented_prevalence is the "
            "like-vs-like rate; use it as the primary citation, "
            "with the full-corpus prevalence as reference."
        ),
        "absence_is_not_prescription": (
            "Divergence output never implies the user should have used "
            "the absent frames. The tool surfaces absence, the thinker "
            "decides relevance. A user explicitly asking 'what's "
            "missing?' may be answered descriptively (naming absences); "
            "the discipline forbids prescription (telling them they "
            "should have used X), not description."
        ),
    }

    if user_context_present:
        # The caller passed a user_context string in the frame_check
        # call args. The MCP does NOT echo the user_context value into
        # the response (privacy posture: caller-side context never
        # round-trips through the server); the caller's agent has
        # the value from its own call args. Extend
        # how_to_render_divergence to instruct the agent on contextual
        # filtering with the prescription-prevention guardrail.
        agent_guidance_additions["how_to_render_divergence"] += (
            "\n\nUser context was provided in the frame_check call (the "
            "caller's agent has it from the call args; the MCP does not "
            "echo the value back). Use that context to filter divergence "
            "relevance for the user's specific situation: surface "
            "absences that matter for the context first; deprioritize "
            "catalog-true but contextually irrelevant absences. "
            "Discipline: NEVER use the user_context to prescribe what "
            "the user should have used. The context personalizes "
            "RELEVANCE FILTERING; the absence_is_not_prescription "
            "guarantee extends to contextual surfacing. A user "
            "explicitly asking 'what is missing for my situation?' may "
            "be answered descriptively (naming context-relevant "
            "absences); the discipline forbids prescription, not "
            "context-aware description."
        )

    return {
        "divergence": divergence,
        "agent_guidance_additions": agent_guidance_additions,
    }


# ── Compose-budget helper ─────────────────────────────────────────

def _compress_agent_guidance_to_load_bearing(
    full_guidance: dict[str, Any], level: str = "minimal",
) -> dict[str, Any]:
    """Compress agent_guidance to load-bearing prescriptions only.

    Used when compose_budget is "standard" (the default) or "minimal"
    to reduce per-call token cost. The default at the tool-call surface
    is "standard": empirical measurement (frame-check 0.8.4) showed
    full=111KB, standard=61KB, minimal=53KB on the same call. The four
    agent_guidance keys this function strips at standard
    (composition_discipline, how_to_render_divergence,
    how_to_map_user_intent, suggested_response_shape) are large prose
    surfaces the agent rarely re-reads on every invocation; their
    load-bearing content survives via shorter sibling notes. Callers
    that need the full inline tables (claim_level_treatments) or the
    uncompressed prose opt in via compose_budget="full".

    The compression is identical at the "standard" and "minimal" tiers;
    the two tiers differ in their divergence-side slicing (top-5 vs
    top-3 absent_frames; all clusters/patterns vs top-1). The `level`
    parameter only flows into compose_budget_applied_note so callers
    sizing token budgets can confirm which tier produced the cut.

    Compression rules:
      - composition_discipline: keep the discipline points as a
        compressed list, drop worked examples (the cite-by-name
        lesson, the per-level example trios). Worked examples teach
        the discipline at first read; once the agent has seen them
        in `full` mode, repeating on every call is dead weight.
      - how_to_cite_faithfully: condense to one sentence per rule
        (name Frame Check, no paraphrase, no "fails to address",
        no quality-score use).
      - when_invoked_on_own_output: keep (load-bearing for the self-
        audit case which is the most frequent per-turn invocation).
      - claim_level_treatments: replaced with a short note because
        the table is identical across calls; an agent can fetch it
        once via a compose_budget="full" call and cache for
        subsequent compose_budget="standard"/"minimal" calls.
        Surfaced as claim_level_treatments_note so the schema-shaped
        key survives and consumers parse around it.
      - what_this_tool_tells_you / what_this_tool_does_not_tell_you:
        replaced with a single inline pair of sentences. The full
        text is for first-time orientation, not per-call discipline.
      - how_to_map_user_intent: dropped. The agent has its own NLU;
        the guidance was for surface-level prompts and is not load-
        bearing for tight-loop callers.
      - how_to_cite_frame_matches / how_to_cite_claims: rolled into
        how_to_cite_faithfully.
      - dual_use_note: kept (anti-misuse is load-bearing).
      - scope_regime_guidance: passed through verbatim if present
        (it is verification-conditional and already concise).
      - frame_opportunities_discipline / how_to_render_divergence /
        any other divergence-merged keys: passed through verbatim
        because they govern dynamic blocks the caller asked for.

    Measured reduction on a representative document: agent_guidance
    drops from ~31 KB to ~12 KB (roughly 2.6x). The actual cut is
    reported in compose_budget_applied.note in the divergence
    envelope so a caller sizing token budget can confirm it.
    """
    compressed = {
        "composition_discipline": (
            "Compose ONE insight grounded in cited measurements, in "
            "reading-form ('the pattern reads as X'), never verdict-"
            "form ('the document is X'). Cite measurements as Frame "
            "Check's; the reading is the agent's. Do not walk the "
            "measurements one by one. Discipline: "
            "(1) every clause cites a measurement; "
            "(2) reading-form, never verdict-form; "
            "(3) confidence-gate (under 100 words, non-English, non-"
            "analytical structure) pivots the frame to a reading of "
            "Frame Check's scope, not a reading of the document; "
            "(4) cross-context compounding only when it sharpens the "
            "reading, never as scenery; "
            "(5) absence is not prescription (name what the framing "
            "does, never what the document should have done); "
            "(6) per-level claim treatment per the claim_level field "
            "on each entity; "
            "(7) when divergence.frame_patterns is non-empty, lead "
            "with the pattern reading and cite the pattern by its id "
            "verbatim; when frame_patterns is empty and "
            "divergence.absence_clusters is non-empty, lead with the "
            "cluster reading and cite by dimension name."
        ),
        "claim_level_treatments_note": (
            "Full per-level claim discipline is available inline at "
            "compose_budget='full' under "
            "agent_guidance.claim_level_treatments. The table is "
            "identical across calls; an agent can fetch once via a "
            "compose_budget='full' invocation and cache the result "
            "for subsequent compose_budget='standard'/'minimal' calls."
        ),
        "what_this_tool_tells_you": (
            "Structural framing of the document: coverage across five "
            "analytical perspectives, voice classification, temporal "
            "orientation, epistemic basis, named pattern matches from "
            "the Frame Vocabulary Standard, claim-density and hedge "
            "calibration, and (with source_text) source-fidelity."
        ),
        "what_this_tool_does_not_tell_you": (
            "Whether the document is correct, balanced, or rigorous. "
            "Whether the framing is appropriate for the user's goal. "
            "Verdicts, rankings, or pass/fail judgments. The "
            "posture is structural-shape only."
        ),
        "how_to_cite_faithfully": (
            "Name Frame Check explicitly as the source of "
            "measurements. Do not paraphrase measurements as the "
            "agent's own reading. Do not restate 'missing' as 'fails "
            "to address' (the detector may have under-detected). Do "
            "not use coverage gaps, voice classifications, or FVS "
            "matches as a quality score, truthfulness verdict, or "
            "editing rule that suppresses minority framings. "
            "frame_library_matches: 'draft' entries cite as 'per the "
            "draft Frame Vocabulary Standard entry FVS-XXX'; 'canon' "
            "entries cite by id verbatim. claims block: cite COUNTS "
            "(detector-reported), never paraphrase individual claim "
            "sentences as if Frame Check surfaced them."
        ),
        "when_invoked_on_own_output": (
            "If document_text is the agent's own response (self-"
            "audit), do not evaluate correctness or claim balance, "
            "rigor, or caveats the measurements did not detect. "
            "Surface the structural frame, name FVS matches with "
            "their teaching_question, stop. Under 100 words: "
            "density-based detectors are noisy; name that limit."
        ),
        "dual_use_note": (
            "Frame Check expands the reader's view of one document; "
            "do not rank documents against each other. Surface the "
            "structural observation; the reader's judgment is the "
            "interpretive layer, not the agent's."
        ),
        "compose_budget_applied_note": (
            f"compose_budget={level}: agent_guidance compressed to "
            "load-bearing prescriptions only (Frame Check naming, "
            "reading-form discipline, dual-use note, self-audit rule, "
            "citation discipline). Worked examples in "
            "composition_discipline, the full claim_level_treatments "
            "table, and how_to_map_user_intent are dropped at this "
            "tier. Pass compose_budget='full' for the complete "
            "guidance inline."
        ),
    }

    # Preserve dynamic / context-conditional keys verbatim. These are
    # generated per-request, are concise, and govern blocks the caller
    # explicitly asked for (divergence rendering, opt-in opportunities,
    # verification-regime guidance). Compressing them would silently
    # change the caller's contract for those blocks.
    for key in (
        "scope_regime_guidance",
        "how_to_render_divergence",
        "frame_opportunities_discipline",
        "absence_is_not_prescription",
        # suggested_next_actions is per-call-derived from the call's
        # specific structural findings (highest-signal absent_frame,
        # claim hedge rate, sourced_pct). It is concise (4 entries
        # max) and is the load-bearing affordance for the user's
        # next move; compressing it would drop the discovery loop
        # into the rest of the product surface (the four MCP prompts,
        # the FVS catalog via library_url). The rendering instruction
        # passes through alongside so a compressed-tier caller still
        # knows how to surface the actions to the user.
        "suggested_next_actions",
        "how_to_render_suggested_next_actions",
    ):
        if key in full_guidance:
            compressed[key] = full_guidance[key]

    return compressed


# ── Suggested next actions ────────────────────────────────────────

def _build_suggested_next_actions(
    analysis: dict[str, Any],
    divergence: dict | None,
) -> list[dict]:
    """Derive 2-4 specific next-action suggestions from this call's
    findings. Each action is structural-finding-anchored: it points
    at a concrete gap in the analysis and gives the user (via the
    agent) a concrete move that addresses it.

    The actions surface the rest of the product surface (the
    challenge_document MCP prompt, the FVS catalog via library_url)
    so an end-user reading a Frame Check result has a discoverable
    path forward, not just a static reading. Prior to this block
    being shipped, the tool surfaced findings without telling the
    user what to do about them; the discovery loop into the four
    MCP prompts and the 100+ resources was invisible.

    Each entry shape:
      kind            "reprompt" | "resource" | "prompt_followup"
      action_text     human-readable description; agent renders
                      verbatim or near-verbatim
      rationale       one sentence on why this action is suggested
                      for THIS specific call's findings (so the
                      reader can judge relevance)
      related_url     library_url for "resource" kind, optional
      related_fvs_id  FVS-ID for "resource" kind, optional

    Capped at 4 entries: more becomes noise. Ordering:
      1. Highest signal_strength absent_frame resource pointer
         (most actionable, most specific to the document)
      2-3. Up to two reprompt suggestions derived from claim/
         epistemic/coverage findings when the thresholds fire
      Last. Always-include prompt_followup pointing at
         challenge_document so the deeper multi-turn loop is
         discoverable on every call

    Deterministic: same input produces same output, same order.
    """
    actions: list[dict] = []

    # Rule 1: highest-signal absent_frame -> resource pointer.
    # absent_frames are sorted by signal_strength tier (high first)
    # then frame_id ascending; absent_frames[0] is the strongest
    # absence-shaped finding for this document.
    if divergence:
        absent_frames = divergence.get("absent_frames", []) or []
        if absent_frames:
            top = absent_frames[0]
            fvs_id = top.get("frame_id", "")
            title = top.get("frame_title", "")
            url = top.get("library_url")
            if fvs_id and title and url:
                actions.append({
                    "kind": "resource",
                    "action_text": (
                        f"Read the entry for the strongest absent frame "
                        f"in this reading: [{fvs_id} {title}]({url})."
                    ),
                    "rationale": (
                        f"{fvs_id} ({title}) is the highest signal_strength "
                        f"absent_frame in the divergence block; reading "
                        f"the catalog entry grounds the absence in the "
                        f"frame's identification cues and worked examples, "
                        f"not the agent's paraphrase."
                    ),
                    "related_fvs_id": fvs_id,
                    "related_url": url,
                })

    # Rule 2: high unhedged claim rate -> reprompt for hedging.
    # Threshold 0.5 picks documents where the majority of numeric
    # claims operate in the confidence register; below that the
    # signal does not justify a prompt for the user.
    claims = analysis.get("claims_extracted", {}) or {}
    total_claims = claims.get("total", 0) or 0
    unhedged_count = claims.get("unhedged_count", 0) or 0
    if total_claims >= 5 and unhedged_count / total_claims >= 0.5:
        unhedged_pct = round(100 * unhedged_count / total_claims)
        actions.append({
            "kind": "reprompt",
            "action_text": (
                "Ask the source AI: \"For each numeric claim in your "
                "analysis, what is the confidence interval, and where "
                "does the figure come from?\""
            ),
            "rationale": (
                f"{unhedged_count} of {total_claims} numeric claims "
                f"({unhedged_pct} percent) carry no hedging language. "
                f"A hedge-by-claim pass surfaces the uncertainty the "
                f"original draft did not name."
            ),
        })

    # Rule 3: very low sourced_pct -> reprompt for attribution.
    # Threshold 10 percent picks documents whose claims read as the
    # author's own knowledge rather than measurements someone made.
    epistemic = analysis.get("epistemic", {}) or {}
    sourced_pct = epistemic.get("sourced_pct", 100)
    total_sentences = epistemic.get("total_sentences", 0) or 0
    if total_sentences >= 5 and sourced_pct < 10:
        actions.append({
            "kind": "reprompt",
            "action_text": (
                "Ask the source AI: \"For the claims in this analysis, "
                "what specific sources support each one? Cite per "
                "claim, not in a closing footnote.\""
            ),
            "rationale": (
                f"Only {sourced_pct} percent of sentences carry "
                f"detector-recognized attribution markers; the claims "
                f"read as facts the author knows rather than "
                f"measurements someone made."
            ),
        })

    # Always-include: prompt_followup pointing at the
    # challenge_document MCP prompt so the deeper multi-turn loop
    # is discoverable on every call. The user can invoke it by
    # asking the agent to "use the challenge_document prompt"; the
    # prompt derives adversarial questions traced to the structural
    # gaps in this reading.
    actions.append({
        "kind": "prompt_followup",
        "action_text": (
            "Use the `challenge_document` MCP prompt for an "
            "adversarial-questions readout traced directly to the "
            "structural gaps surfaced here."
        ),
        "rationale": (
            "challenge_document derives questions from the absent_frames "
            "and weakest dimensions in this reading; running it gives "
            "a structured list of follow-up questions the user can put "
            "back to the source AI."
        ),
    })

    # Cap at 4. Resource pointer (if present) wins position 1;
    # prompt_followup always wins last position; the middle is
    # filled with reprompt suggestions in derivation order.
    return actions[:4]


# ── Top-level payload entry points ────────────────────────────────
#
# build_epistemic_payload (frame_check) and build_compare_payload
# (frame_compare) are the two MCP tool entry points exposed via the
# CallToolResult JSON-RPC method. Everything above this line
# composes into one of these two builders.

def build_epistemic_payload(
    document_text: str, source_text: str | None = None,
    *,
    include_divergence: bool = True,
    domain_hint: str | None = None,
    divergence_rendering: str = "list",
    catalog_version_pin: str | None = None,
    user_context: str | None = None,
    user_goal: str | None = None,
    include_frame_opportunities: bool = False,
    compose_budget: str = "full",
) -> dict[str, Any]:
    """Run Frame Check's deterministic analyzers on the document and
    return the full epistemic payload: analysis, agent_guidance,
    provenance.

    When source_text is provided, the payload also includes a
    verification block (Layer 4 source_fidelity + Layer 11
    grounding_decomposition with scope_assessment regime). The
    agent_guidance narrative adapts to the regime so a client agent
    is told WHICH signal to trust on number-dense sources.

    All measurements in the analysis block are reproducible. Calling
    this twice with the same inputs returns an identical payload
    except for analysis_latency_ms in provenance (wall-clock).
    """
    # Import lazily so server startup stays fast. Heavy modules pull
    # in numpy / regex machinery we do not want to load on handshake.
    # Version constants live in _build_provenance, not here: the
    # function uses the analyzers but not the version strings.
    from clarethium_measure import measure
    from claim_analysis import analyze_claims
    from framing import (
        detect_coverage,
        temporal_orientation,
        detect_voice,
        detect_epistemic_basis,
        framing_portrait,
        framing_headline,
    )
    from frame_library import suggest_frames

    t_start = time.perf_counter()

    ca = analyze_claims(document_text)
    # Request sentence-level attribution and candidate-miss surfacing
    # for the MCP v2 coverage payload. Enables per-dimension
    # sentence_matches (where markers fired) and candidate_sentences
    # (where primary detector may have under-detected on the dimension).
    # suggest_frames uses only legacy fields and is unaffected.
    cov = detect_coverage(
        document_text,
        include_attribution=True,
        include_candidates=True,
    )
    voice = detect_voice(document_text)
    # Request candidate-attribution surfacing to expose scholarly-style
    # attribution the primary _is_sourced pipeline misses. Additive;
    # legacy fields unchanged.
    epist = detect_epistemic_basis(document_text, include_candidates=True)
    temp = temporal_orientation(document_text)
    # Pass raw text to enable text-dependent rules (FVS-006). Rules
    # without text dependency are unaffected.
    frames = suggest_frames(cov, voice, temp, epist, text=document_text)

    # Populate library-info caches (status map, version) on first
    # use. See _ensure_caches docstring for rationale.
    _ensure_caches()

    # Verification layer (only runs when the caller supplied source_text).
    # measure() composes source_fidelity + grounding_decomposition + the
    # scope_assessment regime classification in a single pass. Skipped
    # when no source is provided so the deterministic-only promise in
    # provenance stays honest for the no-source case.
    profile_with_source = None
    if source_text and source_text.strip():
        profile_with_source = measure(document_text, source=source_text)

    # Portrait and headline synthesize the raw coverage/voice/temporal/
    # epistemic signals into a single readable narrative. An agent
    # surfacing the portrait verbatim carries Frame Check's measurement
    # shape forward; surfacing the raw category lists without the
    # portrait risks reducing to a score the tool does not emit.
    portrait = framing_portrait(cov, temp, voice, epist, ca)
    headline = framing_headline(cov, temp, voice, epist, ca)
    # Substrate-side composition Items 8 / 9 / 10: per-frame
    # deepening. Three deterministic regex-based detectors that
    # give the agent specific document-content evidence beyond
    # the FVS firing/absence signals.
    from frame_deepening import (
        detect_temporal_scope as _detect_temporal_scope,
        detect_stakeholder_map as _detect_stakeholder_map,
        detect_falsification_conditions as _detect_falsification,
    )
    temporal_scope_data = _detect_temporal_scope(document_text)
    stakeholder_map_data = _detect_stakeholder_map(document_text)
    falsification_data = _detect_falsification(document_text)
    # Substrate-side composition Item 2: structural genre
    # classification. Composes voice + claim distribution + text-
    # feature regexes into a bounded-set classification with
    # construct-honest confidence reporting (mirrors voice). The
    # foundational primitive for Item 3 (per-genre absence ranking)
    # and Item 4 (pattern composition with prevalence). Deterministic.
    from genre_classifier import classify_genre as _classify_genre
    genre_data = _classify_genre(document_text, voice=voice, claims=ca)

    elapsed_ms = int((time.perf_counter() - t_start) * 1000)

    coverage_cats = cov.get("categories", {}) or {}

    analysis = {
        "document": {
            "word_count_estimate": len(document_text.split()),
            "char_count": len(document_text),
            "sentence_count": voice.get("total_sentences", 0),
        },
        "coverage": {
            "addressed": cov.get("covered", []),
            "missing": cov.get("missing", []),
            "addressed_count": cov.get("coverage_count", 0),
            "total_categories": cov.get("total_categories", 5),
            "per_category_density_per_1kw": {
                cat: coverage_cats.get(cat, {}).get("density_per_1kw", 0)
                for cat in coverage_cats
            },
            "caveat": (
                "Coverage is keyword-and-pattern based. The 'addressed' "
                "list names categories where the detector found its "
                "vocabulary; the 'missing' list names categories where "
                "it did not. Both directions carry measurement error: "
                "a category flagged as addressed may be covered "
                "substantively or only nominally, and a category flagged "
                "as missing may be discussed using vocabulary the "
                "detector does not recognize. Reader judgement is "
                "required to distinguish. Density per 1,000 words is a "
                "rough proxy: higher density correlates with substantive "
                "coverage but does not prove it. DEPRECATION NOTICE "
                "(Phase 2, 2026-04-21): coverage (v1) is deprecated. "
                "coverage_v2 is the forward contract; new integrations "
                "MUST read coverage_v2. The v1 block is retained during "
                "the compatibility window and will be removed in a future "
                "Phase 3 release."
            ),
        },
        "coverage_v2": _build_coverage_v2(cov),
        "voice": {
            "classification": voice.get("voice"),
            "signals": {
                "first_person_plural_pct": voice.get("we_pct"),
                "second_person_pct": voice.get("you_pct"),
                "imperative_count": voice.get("imperative_count"),
                "speculative_pct": voice.get("spec_pct"),
            },
            "available_classes": [
                "promotional", "prescriptive", "analytical",
                "descriptive", "advisory",
            ],
            # Phase B classification-confidence construct. Parallels
            # the coverage_v2 construct block shape: data fields +
            # first-class construct sub-block with serialize guidance.
            # See framing.py::detect_voice for the cascade.
            "confidence": voice.get("confidence"),
            "margin_to_threshold": voice.get("margin_to_threshold"),
            "runner_up": voice.get("runner_up"),
            "runner_up_margin": voice.get("runner_up_margin"),
            "construct": _build_voice_construct(voice),
            # Per-level construct treatment: voice is a 7-rule
            # cascade classifier with margin-
            # aware confidence. Cite per
            # agent_guidance.claim_level_treatments[classifier_output];
            # honor the existing construct.how_to_serialize for the
            # voice-specific phrasing (e.g., the analytical-residual
            # caveat).
            "claim_level": _CLAIM_LEVEL_CLASSIFIER,
        },
        # Genre is a higher-order classification composed from voice
        # + claim distribution + text-feature regexes. Bounded set:
        # recommendation, analysis, narrative, advocacy, exploration,
        # instruction. Construct-honest classification-confidence
        # shape (mirrors voice). Substrate-side composition Item 2:
        # foundational primitive that Item 3 (per-genre absence
        # ranking) and Item 4 (pattern composition) build on.
        "genre": {
            "classification": genre_data.get("genre"),
            "confidence": genre_data.get("confidence"),
            "runner_up": genre_data.get("runner_up"),
            "runner_up_margin": genre_data.get("runner_up_margin"),
            "score_distribution": genre_data.get(
                "score_distribution", {}
            ),
            "available_classes": [
                "recommendation", "analysis", "narrative",
                "advocacy", "exploration", "instruction",
            ],
            "construct": genre_data.get("construct"),
            # Per-level construct treatment: genre is a deterministic
            # scoring classifier with feature-evidence gate (post-
            # 2026-04 fix). Cite per
            # agent_guidance.claim_level_treatments[classifier_output];
            # surface runner_up when confidence is borderline.
            "claim_level": _CLAIM_LEVEL_CLASSIFIER,
        },
        # Per-frame deepening: surgical additions to FVS-014
        # (temporal_scope), FVS-011 (stakeholder_map), and
        # FVS-007/009 (falsification_conditions). Each sub-field
        # is None when the document is too short for the analysis
        # to be meaningful (under 100 words).
        "frame_deepening": {
            "temporal_scope": temporal_scope_data,
            "stakeholder_map": stakeholder_map_data,
            "falsification_conditions": falsification_data,
            # Per-level construct treatment: each sub-field is a
            # regex/feature detector emitting structural document
            # evidence
            # (years referenced, stakeholder roles, falsification
            # statements). The detector-measurement discipline
            # applies to the cited evidence inside each sub-field
            # (e.g. 'years_referenced: [2026, 2030]' is a
            # lower-bound claim about explicit year markers; the
            # document may carry temporal anchoring via vocabulary
            # the detector does not match). Cite per
            # agent_guidance.claim_level_treatments
            # [detector_measurement].
            "claim_level": _CLAIM_LEVEL_DETECTOR,
        },
        "temporal": {
            "dominant": temp.get("dominant"),
            "distribution_pct": {
                "past": temp.get("past_pct"),
                "present": temp.get("present_pct"),
                "future": temp.get("future_pct"),
            },
            # Phase B distribution-with-dominant construct. Exposes
            # dominant_margin (lead over runner-up tense) and balanced
            # flag so agents can distinguish genuine time-anchoring
            # from near-tied distributions.
            "dominant_margin": temp.get("dominant_margin"),
            "balanced": temp.get("balanced"),
            "construct": _build_temporal_construct(temp),
            # Per-level construct treatment: temporal is a
            # distribution classifier (past/present/future percentages
            # with dominant + balanced flag). Cite per
            # agent_guidance.claim_level_treatments[classifier_output];
            # honor the balanced flag (low-margin dominants must not
            # be restated as time-anchoring).
            "claim_level": _CLAIM_LEVEL_CLASSIFIER,
        },
        "epistemic": {
            "sourced_pct": epist.get("sourced_pct"),
            "sourced_sentences": epist.get("sourced"),
            "numeric_sentences": epist.get("numeric_sentences"),
            "unsupported_numeric": epist.get("unsupported_numeric"),
            "total_sentences": epist.get("total_sentences"),
            # Candidate-attribution surfacing extends the Fix A
            # lower-bound detection posture from coverage (Phase A) to
            # the epistemic signal. Sentences where EPISTEMIC_CANDIDATE_
            # ATTRIBUTION fires but the primary _is_sourced pipeline
            # did not. Each carries an explicit caveat. See
            # framing.py::EPISTEMIC_CANDIDATE_ATTRIBUTION.
            "candidate_attribution_sentences": epist.get(
                "candidate_attribution_sentences", []
            ),
            "candidate_attribution_count": epist.get(
                "candidate_attribution_count", 0
            ),
            "note": (
                "sourced_pct is the share of sentences where the "
                "detector matched an attribution or external-reference "
                "pattern (e.g., 'according to X', 'X reported', named "
                "entity with reporting verb). Low values are common in "
                "essayistic writing; high values are typical of academic "
                "or regulatory text. This is a signal, not a quality "
                "judgement. Under-detection is a known failure mode: "
                "scholarly-style attribution ('observers raise', "
                "'analysts argue') and passive constructions may not "
                "fire the regex, so a low sourced_pct is a lower-bound "
                "claim about attribution-marker density, not an "
                "upper-bound claim about whether the document is "
                "attributed."
            ),
        },
        "claims_extracted": {
            "total": ca.get("total_claims", 0),
            # Bug fix 2026-04-20: previously the sum used c.get("hedged"),
            # but claim dicts from analyze_claims carry framing="hedged"
            # as a string, not a hedged boolean. The .get("hedged")
            # always returned None, so hedged_count was always 0 and
            # unhedged_count was always total_claims. The correct values
            # live at the top of analyze_claims' return dict, already
            # computed from the framing classifier.
            "hedged_count": ca.get("hedged_count", 0),
            "unhedged_count": ca.get("unhedged_count", 0),
            "prediction_count": ca.get("prediction_count", 0),
            "by_type": ca.get("claims_by_type", {}),
            # Candidate-hedge surfacing extends the Fix A under-detection
            # construct from coverage (Phase A) and epistemic (Phase A-
            # extended) to the claims signal, completing the same-class-
            # signal trilogy. Each sample carries an explicit caveat.
            # See claim_analysis.py::CANDIDATE_HEDGE_RE.
            "candidate_hedge_count": ca.get("candidate_hedge_count", 0),
            "candidate_hedge_samples": [
                {
                    "sentence_preview": (
                        c["sentence"][:120]
                        + ("..." if len(c["sentence"]) > 120 else "")
                    ),
                    "candidate_hedge_marker": c.get("candidate_hedge_marker"),
                    "caveat": c.get("candidate_hedge_caveat"),
                }
                for c in ca.get("claims", [])
                if c.get("candidate_hedge_marker") is not None
            ][:10],
        },
        "portrait": portrait,
        "headline": headline,
        "frame_library_matches": [
            {
                "fvs_id": f.get("fvs_id"),
                "name": f.get("name"),
                # GitHub URL pointing at the entry's markdown source
                # on the public repository (Clarethium/frame-check).
                # End-users can click this to read the entry directly;
                # GitHub is always resolvable regardless of hosted-
                # production status (frame.clarethium.com is paused
                # 2026-04-23, so the previous-form library_url
                # pointing at the corpus site has been retired).
                # None when no canonical filename is known for the ID.
                "library_url": (
                    _library_entry_ref(f.get("fvs_id", "")).get("public_url")
                    if f.get("fvs_id") else None
                ),
                # MCP resource URI for the same library entry.
                # Agents running entirely through MCP (no web
                # access) can chain this tool response into
                # resources/read on the matching FVS entry directly,
                # without having to construct the URI themselves.
                "library_resource_uri": (
                    f"{RESOURCE_SCHEME}://library/{f.get('fvs_id')}"
                    if f.get("fvs_id") else None
                ),
                # Per-entry version pinned from the entry's
                # **Version:** meta line. Cites this match against
                # a specific version of the entry, not the library-
                # wide version in provenance. None when the entry
                # predates per-entry versioning.
                "library_entry_version": (
                    (_get_frame_versions() or {}).get(f.get("fvs_id", ""))
                ),
                "teaching_question": f.get("question"),
                "definition": f.get("definition"),
                "signal": f.get("signal"),
                # Stability status from INDEX.md. 'draft' means ID is
                # stable but name/identification may revise; 'canon'
                # means full stability. Agents surfacing this match to
                # a user should communicate the status.
                "status": (_get_frame_statuses() or {}).get(f.get("fvs_id", ""), "draft"),
                # Related FVS entries the curator named as adjacent
                # to this one. Each carries its MCP resource URI so
                # an agent can pull the adjacent entry in one
                # resources/read call. Order follows the source
                # file's Adjacent-frames line. Empty list when the
                # entry declares no adjacents or references only
                # non-FVS vocabularies.
                "adjacent_frames": [
                    _library_entry_ref(adj_id)
                    for adj_id in (_get_frame_adjacency() or {}).get(
                        f.get("fvs_id", ""), []
                    )
                ],
                # affects_dimensions: which decision-readiness
                # dimensions this matched frame is canon for.
                # Lets an agent surfacing the match name the
                # downstream impact ("FVS-001 detected; affects
                # Coverage and Counterfactual on the
                # decision-readiness profile") without needing
                # to consult DIMENSION_LIBRARY_ENTRIES separately.
                # Empty list for meta-side entries (FVS-002,
                # FVS-005, FVS-006, FVS-013, FVS-020) that do
                # not map to a specific dimension; honest empty.
                "affects_dimensions": _dimensions_affecting(
                    f.get("fvs_id", "")
                ),
                # corpus_context: empirical anchoring from Frame
                # Check's validation corpus. Carries this frame's
                # firing prevalence, typical co-fires and co-
                # absences, and corpus_resource_uris pointing at
                # corpus entries where this frame fires. The
                # substrate stays deterministic (read-only
                # aggregation over corpus profile.json files).
                # None when the corpus is unavailable.
                "corpus_context": _frame_corpus_context_or_none(
                    f.get("fvs_id", "")
                ),
                # Per-level construct treatment: a frame_library_matches entry is
                # a V1 detector firing on the document. Cite per
                # agent_guidance.claim_level_treatments
                # [detector_measurement]. The detector uses
                # vocabulary-and-pattern matching; under-detection
                # construct applies (firing is a lower-bound
                # vocabulary claim, not an upper-bound document
                # claim).
                "claim_level": _CLAIM_LEVEL_DETECTOR,
                # pattern_kind encodes the V1-detector emission
                # convention as a structured enum, replacing the
                # historical practice of distinguishing fire shapes
                # by parsing the suffix in `name` (e.g. "(active)" /
                # "(absent)" / "(past)" / "(future)" / bare). Five
                # values: "present_detected" (positive present-
                # pattern; the most common shape; covers both
                # "(active)"-suffixed and bare-name historical
                # conventions), "absence_detected" (V1 absence-
                # pattern detector; today only FVS-007 fires this
                # shape), "present_past" / "present_future"
                # (directional sub-categorization of FVS-014 only).
                # The legacy suffix in `name` is preserved for
                # backward compat with hand-authored test fixtures;
                # the enum is the load-bearing wire field for new
                # agent consumers.
                "pattern_kind": f.get(
                    "pattern_kind", "present_detected"
                ),
            }
            for f in frames or []
        ],
    }

    # Verification block. Present only when source_text was supplied.
    # Keeps the schema stable: clients that never pass a source get the
    # analysis-only shape; clients that pass a source get the full
    # epistemic picture including the Monte-Carlo-verified scope regime.
    if profile_with_source is not None:
        sf = profile_with_source.get("source_fidelity", {}) or {}
        gd = profile_with_source.get("grounding_decomposition", {}) or {}
        scope = gd.get("scope_assessment", {}) or {}
        analysis["verification"] = {
            "source_fidelity": {
                "total_numbers": sf.get("total_numbers", 0),
                "in_source": sf.get("in_source", 0),
                "not_in_source": sf.get("not_in_source", 0),
                "unsourced_rate": sf.get("unsourced_rate", 0.0),
                "note": (
                    "Digit-level match. A number 'in_source' appears as "
                    "an exact digit substring in the source text. "
                    "'not_in_source' does not; those claims may be "
                    "derived, rounded, or fabricated."
                ),
            },
            "grounding_decomposition": {
                "proportions": gd.get("proportions"),
                "has_projection": gd.get("has_projection"),
                "recommendation": gd.get("recommendation"),
                "status": gd.get("status"),
                "scope_assessment": {
                    "source_num_count": scope.get("source_num_count"),
                    "derivation_regime": scope.get("derivation_regime"),
                    "cross_reference_layer_4_for_numbers": scope.get(
                        "cross_reference_layer_4_for_numbers",
                    ),
                    "note_user_facing": scope.get("note_user_facing"),
                },
            },
        }

    # Decision-readiness profile (Phase 1.5: experimental, validation
    # in progress per /corpus/decision-readiness/). Composes the
    # existing structural + claims + verification signals into the
    # five-dimension profile. Lead use case per the methodology page
    # is AI-response audit at the moment of conversation, which is
    # the MCP path; the profile MUST be reachable from MCP responses
    # for that positioning to be implemented, not just documented.
    #
    # Synthetic source_network when source_text was supplied: the
    # MCP context uses Layer 4 source_fidelity (digit-substring
    # presence) rather than the web flow's Source Network claim
    # verification. The mapping is approximate: 'in_source' is a
    # weaker positive signal than full claim verification, but it is
    # the only verification data available in the MCP context. The
    # decision_readiness output documents this in its evidence
    # dimension explanation.
    try:
        from decision_readiness import compute_decision_readiness as _cdr
        synth_source_network = {
            "checked": 0, "verified": 0, "contradicted": 0,
            "disputed": 0, "verified_providers": [],
        }
        if profile_with_source is not None:
            sf2 = profile_with_source.get("source_fidelity", {}) or {}
            synth_source_network = {
                "checked": int(sf2.get("total_numbers", 0)),
                "verified": int(sf2.get("in_source", 0)),
                "contradicted": 0,
                "disputed": 0,
                "verified_providers": [],
            }
        synth_display = {
            "framing": {
                "coverage": cov,
                "voice": voice,
                "temporal": temp,
                "epistemic": epist,
                "frame_suggestions": frames,
            },
            "claims": {
                "total_claims": ca.get("total_claims", 0),
                # Bug fix 2026-04-20: see build_epistemic_payload for the
                # parallel fix. Same root cause (framing string vs hedged
                # boolean). Using analyze_claims' pre-computed totals.
                "hedged_count": ca.get("hedged_count", 0),
                "unhedged_count": ca.get("unhedged_count", 0),
                "prediction_count": ca.get("prediction_count", 0),
            },
            "source_network": synth_source_network,
        }
        readiness = _cdr(synth_display)
        if readiness is not None:
            # Per-level construct treatment: each per-dimension reading is a
            # substrate composition over multiple measurements
            # with a curated signal_text. Trigger conditions are
            # deterministic (multi-feature scoring per dimension);
            # signal_text is single-curator authored. Same shape
            # as absence_clusters and frame_patterns; mark each
            # dimension dict with claim_level=composed_pattern so
            # the agent honors the per-level discipline (cite
            # the trigger as deterministic AND the signal_text as
            # Frame Check's curator reading) rather than treating
            # the prose as a measurement.
            dims_block = readiness.get("dimensions") or {}
            for _dim_name, dim_data in dims_block.items():
                if isinstance(dim_data, dict):
                    dim_data["claim_level"] = _CLAIM_LEVEL_COMPOSED
            analysis["decision_readiness"] = readiness
    except Exception as exc:
        # Decision-readiness must never break the MCP response. If
        # the composition raises (future signal change broke the
        # mapping), the rest of the analysis still ships and the
        # log records the failure for follow-up.
        log(
            f"decision_readiness composition raised "
            f"{type(exc).__name__}: {exc}"
        )

    what_this_tells_you = [
        "Structural framing patterns detected in the document",
        "Which of five analytical perspectives are keyword-present and which are absent",
        "Voice classification (promotional, prescriptive, analytical, descriptive, advisory)",
        "Temporal orientation (past, present, future distribution)",
        "Epistemic basis (share of sentences with external attribution)",
        "Named matches from the Frame Vocabulary Standard with teaching questions; each match carries a pattern_kind enum naming the V1-detector emission convention (present_detected for positive present-pattern fires, absence_detected for absence-pattern fires like FVS-007 Failure Framing absence, present_past or present_future for FVS-014 Temporal Anchoring directional fires). The legacy parenthetical suffix in name (e.g. (active), (absent), (past), (future)) is preserved for UI rendering compatibility; new agent consumers should read pattern_kind for the structured signal.",
        "Adjacency hints for each matched frame (MCP URIs of related library entries, for in-session chaining)",
        "Extracted numeric claims with hedging status",
        "A synthesized portrait and headline describing what the document does to reader perception",
        "A decision-readiness profile across five dimensions (coverage, calibration, evidence, robustness, counterfactual) with explicit experimental status pending Phase 2 expert validation",
        "Structural genre classification (recommendation / analysis / narrative / advocacy / exploration / instruction) with construct-honest confidence. Classifies on specific marker patterns (first-person pick statements for recommendation; numbered-step procedural patterns for instruction; year-anchored past-event constructions for narrative; etc.) and abstains with classification=null when no markers fire. Empirically the abstention rate is around 54% on the calibration corpus (see calibration/results/detector_empirics_*); this is a feature, not a defect.",
        "Per-frame deepening: temporal_scope (years referenced + projection windows), stakeholder_map (regulators / investors / customers / employees / etc. mentioned vs absent), falsification_conditions (explicit 'would be wrong if' statements when present)",
        "Optional opt-in (include_frame_opportunities=true): LLM-augmented frame opportunities, document-specific questions composed from absent frame teaching questions + document content. Carries cost + non-determinism flag in provenance. Default: not surfaced (deterministic substrate works without LLM).",
    ]
    what_this_does_not_tell_you = [
        "Whether perspectives flagged as addressed are covered substantively or only nominally",
        "Whether perspectives flagged as missing are truly absent, or discussed using vocabulary the detector does not recognize (under-detection is a known failure mode)",
        "Reasoning quality, logical validity, or causal inference errors",
        "Human-perceived quality; structural measurements are roughly orthogonal (r approx 0.1) to reader-perceived quality",
        "Whether the document is persuasive, useful, or correct for the reader's purpose",
        "Whether hedge markers in claims activate the uncertainty coverage dimension. Coverage detection for the uncertainty dimension uses vocabulary markers (uncertain, unknown, contested, range, depends, varies) rather than hedge markers in claim positions (might, could, expected to, projected to). A document can carry a high hedge ratio (e.g., 21% of claims hedged) while uncertainty coverage shows zero markers; this is a detector boundary, not a contradiction. When you observe this disconnect, name it as a methodological observation about Frame Check's measurement layers rather than as a finding about the document.",
    ]

    if profile_with_source is None:
        what_this_does_not_tell_you.append(
            "Whether the numeric claims are factually correct. Pass "
            "source_text to enable Layer 4 source_fidelity and Layer 11 "
            "grounding_decomposition."
        )
        regime_guidance = (
            "No source provided. The portrait and frame matches describe "
            "structure only. If the user needs a truth check, ask them "
            "for the source material and re-invoke with source_text."
        )
    else:
        scope = (
            profile_with_source.get("grounding_decomposition", {})
            .get("scope_assessment", {})
        )
        regime = scope.get("derivation_regime")
        if regime == "saturated":
            regime_guidance = (
                "Source is number-dense (scope_assessment.derivation_regime "
                "= 'saturated'). The Layer 11 sentence-level P-signal is "
                "effectively disabled here: fabricated numbers can pass via "
                "coincidental arithmetic match. For numerical claims, cite "
                "verification.source_fidelity.unsourced_rate (Layer 4), NOT "
                "verification.grounding_decomposition.has_projection."
            )
        elif regime == "transition":
            regime_guidance = (
                "Source is moderately number-dense (scope_assessment."
                "derivation_regime = 'transition'). Layer 11 is noisy; "
                "cross-reference Layer 4 source_fidelity for numerical "
                "claims."
            )
        elif regime == "diagnostic":
            regime_guidance = (
                "Source is not number-dense (scope_assessment."
                "derivation_regime = 'diagnostic'). Layer 11's primary "
                "P-signal is reliable; both layers can be cited."
            )
        else:
            regime_guidance = (
                "Verification ran; regime classification unavailable "
                "(likely pre-v1.5 profile). Prefer Layer 4 source_fidelity "
                "for numerical claims."
            )

    agent_guidance: dict[str, Any] = {
        "composition_discipline": (
            "The measurements are Frame Check's; the reading is the "
            "agent's. Compose ONE insight that is a reading the user "
            "could not see by re-reading their own document, grounded "
            "in specific cited measurements (analysis.genre "
            "classification, analysis.frame_deepening sub-fields "
            "(temporal_scope / stakeholder_map / "
            "falsification_conditions), frame_library_matches "
            "entries, voice classification, divergence "
            "frame_patterns, absence_clusters, and absent_frames "
            "(with goal_relevance and genre_relevance fields when "
            "present), decision_readiness dimension readings, and "
            "any corpus_context fields where present). "
            "When divergence.frame_patterns is non-empty, the "
            "substrate has matched a recognized structural shape "
            "(e.g., 'recommendation-without-falsification'); the "
            "pattern reading is the strongest substrate composition "
            "available and should be the lead synthesis. CITE THE "
            "PATTERN BY ITS id verbatim, not paraphrased. Worked "
            "example: instead of 'the pick gets a one-sided "
            "defense pattern' (paraphrase, substrate invisible), "
            "write 'this matches Frame Check's "
            "recommendation-without-falsification pattern' "
            "(substrate identified, user can chain to definition). "
            "The substantive observation can follow the cite, but "
            "the cite must come first. When frame_patterns is "
            "empty and divergence.absence_clusters is non-empty, "
            "the cluster reading is Frame Check's substrate-side "
            "composition over multiple absent frames; cite it as Frame "
            "Check's reading and use it as the lead synthesis (the "
            "cluster names a dimension-level theme the per-frame walk "
            "cannot). CITE THE CLUSTER BY ITS dimension name "
            "verbatim. Worked example: instead of 'four high-"
            "signal absent frames cluster on the same blind spot' "
            "(paraphrase), write 'Frame Check identified the "
            "counterfactual cluster (FVS-007, FVS-009, FVS-014, "
            "FVS-017)' (substrate's dimension name + member "
            "frames). The dimension name is canon-graph anchored "
            "and lets the user trace the cluster to "
            "decision-readiness methodology. When corpus_context "
            "fields are attached to "
            "matched frames, absent frames, or clusters, treat the "
            "prevalence and co-pattern fields as empirical anchoring "
            "from Frame Check's validation corpus (small N; honor the "
            "small_n_caveat in envelope.corpus_summary when present). "
            "Cross-context compounding rule (4) applies: cite corpus "
            "context only when it sharpens the reading, never as "
            "scenery. Do NOT walk the measurements one by one; a "
            "measurement dump is not a reading. Discipline: "
            "(1) INSIGHT-GROUNDED. Every insight clause must cite a "
            "specific measurement. If you cannot cite, do not assert. "
            "(2) READING-FORM, NEVER VERDICT-FORM. 'The pattern reads "
            "as X' is a reading. 'The document is X' is a verdict. "
            "Frame Check does not verdict; do not verdict on its "
            "behalf. "
            "(3) CONFIDENCE-GATE PIVOTS THE FRAME. When an off-"
            "methodology signal fires (under 100 words / non-English "
            "/ non-analytical structure), pivot the insight from 'a "
            "reading of the document' to 'what this run reveals about "
            "Frame Check's scope'. The user still gets a reading; it "
            "is now about the tool's calibration, not the document's "
            "framing. "
            "(4) CROSS-CONTEXT COMPOUNDING ONLY WHEN IT ADDS. Cite the "
            "validation aggregate or prior measurements only when they "
            "sharpen the reading; never as scenery. "
            "(5) ABSENCE IS NOT PRESCRIPTION. Compose insights that "
            "name what the framing does, never what the document "
            "should have done. The reader decides what to do with the "
            "seeing; that is the sovereignty case this tool serves. "
            "(6) PER-LEVEL CLAIM TREATMENT. The substrate produces "
            "four qualitatively different kinds of claim, each with "
            "its own construct discipline: detector_measurement (a "
            "regex/feature firing or non-firing; lower-bound "
            "vocabulary claim, not upper-bound document claim); "
            "classifier_output (a deterministic cascade or scoring "
            "classifier with margin-aware confidence; surface "
            "runner_up when borderline; no IRR data); "
            "composed_pattern (a deterministic composition with "
            "deterministic trigger and a curator-authored reading; "
            "trigger is reproducible, reading is single-author "
            "normative claim about what the trigger means; no IRR "
            "data on whether other readers compose the same pattern "
            "from the same triggers); agent_generated (opt-in LLM-"
            "composed content from Item 12 frame_opportunities; "
            "non-deterministic by design; each output carries "
            "model_provenance with provider, model, and cost; the "
            "absent frame's general teaching_question_general "
            "remains the stable catalog reference, the "
            "generated_question is one document-specific "
            "application). Every composed entity in this "
            "payload carries a claim_level field naming which "
            "treatment applies; agent_guidance.claim_level_treatments "
            "carries the per-level discipline keyed by claim_level "
            "value. When citing an entity, honor the treatment for "
            "its claim_level: detector measurements get the "
            "lower-bound vocabulary phrasing; classifier outputs "
            "surface confidence and runner-up with the no-IRR "
            "caveat; composed patterns cite the trigger as "
            "deterministic AND the reading as Frame Check's curator "
            "reading; agent_generated content surfaces the model "
            "provenance and cost AND is never presented as Frame "
            "Check's measurement. Worked examples (the same lesson the "
            "cite-by-name discipline shipped: abstract instructions "
            "do not change agent behavior, concrete contrasts do): "
            "for a detector_measurement entity, instead of 'the "
            "document covers risks' (verdict, ignores under-detection "
            "construct), write 'Frame Check's detector found markers "
            "for risks (vocabulary-and-pattern based; lower-bound "
            "claim about marker density)'; for a classifier_output "
            "entity, instead of 'the document is promotional' "
            "(verdict, drops confidence and runner-up), write 'Frame "
            "Check classified voice as promotional (high confidence; "
            "runner-up advisory)' OR for borderline cases 'classified "
            "as promotional, borderline; advisory nearly fired'; for "
            "a composed_pattern entity, instead of 'this is a "
            "recommendation without falsification' (verdict, treats "
            "the curator's reading as a measurement), write 'Frame "
            "Check identified the recommendation-without-"
            "falsification pattern (deterministic trigger over "
            "FVS-007 firing plus FVS-009 absence plus zero "
            "falsification statements); the substrate's reading: "
            "recommendations without falsification conditions cannot "
            "be stress-tested by the reader'. This per-level "
            "discipline replaces the prior uniform construct "
            "treatment that conflated the four epistemic claim "
            "levels under one composition rule set."
        ),
        "claim_level_treatments": _CLAIM_LEVEL_TREATMENTS,
        "what_this_tool_tells_you": what_this_tells_you,
        "what_this_tool_does_not_tell_you": what_this_does_not_tell_you,
        "how_to_cite_faithfully": (
            "When passing this analysis to the user, name Frame Check "
            "explicitly as the source of the measurements. For example: "
            "\"Frame Check's structural analysis found markers for 3 of "
            "5 analytical perspectives and classified the voice as "
            "promotional.\" Do not paraphrase these measurements as "
            "your own reading of the document, and do not restate "
            "'missing' as 'the document fails to address' (the detector "
            "may have missed vocabulary it does not recognize). The "
            "measurements are deterministic and reproducible; "
            "paraphrasing breaks that reproducibility and strips the "
            "provenance the reader needs to evaluate the claim."
        ),
        "how_to_cite_frame_matches": (
            "Render every FVS reference as a clickable markdown link "
            "using the entry's library_url field: "
            "`[FVS-XXX Frame Title](library_url)`. The library_url "
            "points at the entry's markdown source on the public "
            "GitHub repository, which is always resolvable for the "
            "end-user. Plain-text 'FVS-XXX' references give the "
            "reader an identifier they cannot follow; the markdown "
            "link gives them the full identification text, worked "
            "examples, and adjacent-frames graph in one click. "
            "Apply this to frame_library_matches entries, to "
            "absent_frames entries inside the divergence block, and "
            "to typical_co_fires / typical_co_absences inside each "
            "absent_frames entry's corpus_context. Each carries the "
            "same library_url field. "
            "Stability discipline: each frame_library_matches entry "
            "carries a status field. 'canon' entries have stable "
            "ID, name, and identification. 'draft' entries have a "
            "stable ID but name or identification may revise. When "
            "surfacing a draft match, prefix the link with 'per the "
            "draft entry' so the stability guarantee is carried "
            "forward; canon matches need no prefix."
        ),
        "how_to_cite_claims": (
            "The claims block reports per-type COUNTS extracted from "
            "the document (total, hedged, unhedged, prediction, by "
            "numerical type). It does NOT report individual claim "
            "text. When restating, say 'Frame Check's claim extractor "
            "identified N numerical claims, M of which carried hedging "
            "language.' Do not synthesize or paraphrase individual "
            "claim sentences as if Frame Check surfaced them; the "
            "block is a distribution summary, not a quote list. "
            "candidate_hedge_samples carries up to 10 preview "
            "sentences for evidence surfacing (hedges the "
            "primary detector did not recognize); these are clearly "
            "labeled as candidates and should be cited as such, not "
            "as verified hedges. Verification verdicts (if present) "
            "should be cited with the specific verifier and f1 tier "
            "as per how_to_cite_faithfully."
        ),
        "when_to_invoke_again": (
            "frame_check is deterministic for the same inputs. Calling "
            "it twice on identical (document_text, source_text) returns "
            "identical measurements. Re-invoke only if the text changed."
        ),
        "how_to_map_user_intent": (
            "When the user invokes Frame Check via natural language "
            "(not by typing prompt arguments directly), translate "
            "their intent to the option space the four sovereignty "
            "prompts expose (depth, goal, questions). The user does "
            "NOT need to know what compose_budget or "
            "include_frame_opportunities are; those are MCP-layer "
            "names. The user types in their own vocabulary; you "
            "translate. Concrete mappings:\n"
            " - 'quick check' / 'TL;DR' / 'fast read' / 'just a "
            "summary' -> depth=quick (compact response).\n"
            " - 'careful audit' / 'deep dive' / 'thorough review' / "
            "(no qualifier) -> depth=thorough (default).\n"
            " - 'I'm trying to decide whether to' / 'should I' / "
            "'help me decide' / 'figure out if' -> goal=decide.\n"
            " - 'what am I missing' / 'what's not addressed' / "
            "'gaps in this' / 'check for blind spots' -> goal=audit "
            "(default; explicit naming is fine when the user asks for "
            "audit-shaped reading).\n"
            " - 'challenge this' / 'play devil's advocate' / "
            "'adversarial review' / 'questions to push back' -> "
            "goal=challenge (the response composes structural-"
            "weakness questions rather than a portrait).\n"
            " - 'help me explore options' / 'what perspectives am I "
            "missing' / 'broaden my thinking' -> goal=explore.\n"
            " - 'teach me about the framing' / 'walk me through' / "
            "'help me understand' -> goal=learn.\n"
            " - 'questions to think about' / 'help me question this' "
            "/ 'what should I ask' -> questions=yes (opt-in LLM-"
            "composed document-specific questions; the substrate's "
            "deterministic patterns + clusters work without this).\n"
            "\n"
            "Discipline: surface the chosen options briefly to the "
            "user before invoking ('I'll do a thorough decision-"
            "focused audit') so the user can adjust before the call "
            "lands. Never silently default to the maximal option "
            "set; that wastes the user's attention budget. When the "
            "user request is ambiguous about depth, default to "
            "thorough; ambiguous about goal, default to audit; "
            "ambiguous about questions, default to no (opportunities "
            "are opt-in for cost reasons; do not invoke them without "
            "user signal). When the user explicitly types prompt "
            "arguments, honor those values verbatim; do not override "
            "with your inference."
        ),
        "scope_regime_guidance": regime_guidance,
        "suggested_response_shape": (
            "Surface the portrait first (what kind of document this is), "
            "then name any frame_library_matches with their "
            "teaching_question so the reader has a question to ask of "
            "the document themselves. If verification is present, state "
            "the source_fidelity ratio verbatim and apply "
            "scope_regime_guidance. Close with the method's own limits "
            "from what_this_tool_does_not_tell_you so the reader knows "
            "where your response stops being grounded."
        ),
        "when_invoked_on_own_output": (
            "If document_text is your own last response to the user "
            "(the self-audit pattern surfaced by the "
            "frame_check_my_response prompt), the response shape "
            "changes. Do not evaluate whether you were correct. Do "
            "not claim balance, rigor, or caveats the measurements "
            "did not detect. Surface the structural frame you chose "
            "(coverage, voice, temporal, sourced_pct), name any FVS "
            "matches with their teaching_question, and stop. The "
            "user sees the frame you chose and decides what to do "
            "with the seeing; that is the sovereignty case this "
            "tool exists to serve. One bound: if your response is "
            "under about 100 words, the density-based detectors are "
            "noisy and category coverage flags should be treated as "
            "weak signal. Name that limit to the user rather than "
            "overstating what the measurements can tell them."
        ),
        "frame_opportunities_discipline": (
            "frame_opportunities is the opt-in LLM-augmented "
            "composition layer. When the caller passes "
            "include_frame_opportunities=true, divergence."
            "frame_opportunities.opportunities carries 0-3 "
            "document-specific questions composed by the LLM from "
            "an absent frame's teaching question + the document's "
            "content + the user's goal. Discipline: "
            "(1) Each opportunity carries model_provenance with "
            "is_deterministic=false; cite this clearly when "
            "surfacing the question to the user. The deterministic "
            "substrate (clusters, patterns, absences) is "
            "reproducible across runs; opportunities are not. "
            "(2) Carry the cost. divergence.frame_opportunities."
            "total_cost_usd is the spend for this invocation; "
            "include it in audit trails. "
            "(3) Surface the generated_question alongside the "
            "frame's general teaching_question, not as a "
            "replacement. The general teaching question is the "
            "stable catalog reference; the generated question is "
            "the document-specific application. "
            "(4) Never present LLM-generated content as Frame "
            "Check's measurement. Frame Check's measurements are "
            "the deterministic substrate; opportunities are agent-"
            "side composition delegated to an LLM by Frame Check. "
            "(5) When opportunities is empty and available=false, "
            "the LLM was unavailable; surface this as graceful "
            "degradation (the deterministic substrate still works) "
            "and do not retry without explicit user request."
        ),
        "dual_use_note": (
            "Frame Check is designed to expand the reader's view of a "
            "document, not to rank documents against each other. Agent "
            "integrators who consume this payload should NOT use "
            "coverage gaps, voice classifications, or FVS matches as a "
            "quality score, a truthfulness verdict, or an editing rule "
            "that suppresses minority framings. The under-detection "
            "posture surfaces what the detector measures and what it "
            "does not, precisely so that "
            "a downstream agent cannot reduce the measurements to a "
            "pass/fail judgment. If you find yourself producing prose "
            "like 'this document is biased' or 'this document lacks "
            "rigor' from Frame Check's output, you are using the tool "
            "outside its design scope. Surface the structural observation "
            "and the teaching question; the reader's judgment is the "
            "interpretive layer, not yours."
        ),
    }

    provenance = _build_provenance(
        analysis_layer=(
            "deterministic_structural_plus_verification"
            if profile_with_source is not None
            else "deterministic_structural_only"
        ),
        elapsed_ms=elapsed_ms,
    )

    # Analysis manifest. Sibling to provenance, with a different
    # cut: provenance is identity / citation metadata (versions,
    # license, author); manifest is operational disclosure ("which
    # analytical layers ran on THIS call, with explicit reasons for
    # any that did not"). On the MCP surface every dynamic layer is
    # delegated to the caller's agent (no SN, no V4.2, no AI
    # interpret), so the manifest's main value is naming each
    # delegation explicitly so an agent integrator knows what it
    # owes the user that this response did not provide. Web
    # surfaces (/check, /compare) emit the same manifest shape with
    # different layer states; the structural parity is the point.
    from manifest import build_check_manifest as _build_manifest
    manifest = _build_manifest(
        sn_results=[],
        sn_status="skipped",
        sn_status_reason=(
            "Source Network is not invoked on the MCP server-side "
            "path. Per FRAME_DIVERGENCE_CONTRACT_v1 §7, network-bound "
            "verification is a caller-side responsibility on this "
            "surface; the agent integrator runs SN against its own "
            "provider set and budget."
        ),
        reliability_tiers={},
        source_name_to_provider_key={},
        ai_interpret=None,
        v4_2_result=None,
        consistency_ran=bool(source_text and source_text.strip()),
    )
    # Surface the MCP-specific delegation in the manifest so the
    # client agent's reading of "what didn't run" matches the
    # contract docs without having to cross-reference them.
    manifest["surface"] = "mcp_frame_check"

    # FRAME_DIVERGENCE_CONTRACT_v1 Part 2 integration. When
    # include_divergence=True: compute absent-frame records from the
    # library_v3 catalog minus the V1 frame_library_matches, build
    # the faithfulness envelope, and extend agent_guidance with the
    # two required divergence keys. MCP surface per Contract §7.1:
    # zero LLM invoked; caller's agent model completes the composition
    # using agent_guidance.how_to_render_divergence.
    payload: dict[str, object] = {
        "analysis": analysis,
        "agent_guidance": agent_guidance,
        "provenance": provenance,
        "manifest": manifest,
    }
    if include_divergence:
        # Pass cov_missing so the divergence builder can compute
        # signal_strength tiers per absent frame; "coverage weakness"
        # is the document-side signal that distinguishes high-tier
        # absences (catalog-multi-dim AND coverage canon AND coverage
        # weak) from medium and low.
        cov_missing_for_signal = list(cov.get("missing", []) or [])
        # Item 3: pass the classified genre so absent_frames can
        # carry genre_relevance and the sort can promote load-bearing
        # absences for this document's genre.
        document_genre = (
            analysis.get("genre", {}) or {}
        ).get("classification")
        divergence_bundle = _build_divergence_block(
            frame_library_matches=analysis.get("frame_library_matches", []) or [],
            domain_hint=domain_hint,
            rendering=divergence_rendering,
            catalog_version_pin=catalog_version_pin,
            engine_status="beta",
            cov_missing=cov_missing_for_signal,
            user_context_present=bool(user_context),
            document_genre=document_genre,
            document_word_count=analysis.get(
                "document", {},
            ).get("word_count_estimate"),
            document_claim_count=analysis.get(
                "claims_extracted", {},
            ).get("total"),
            user_goal=user_goal,
            document_text_for_opportunities=document_text,
            include_frame_opportunities=include_frame_opportunities,
            document_signals=_build_document_signals(analysis),
            compose_budget=compose_budget,
        )
        payload["divergence"] = divergence_bundle["divergence"]
        # Merge the two required agent_guidance additions per §4.4.
        for key, value in divergence_bundle["agent_guidance_additions"].items():
            agent_guidance[key] = value

    # Suggested next actions: 2-4 specific moves the user can take
    # based on this call's findings. Surfaces the rest of the
    # product (challenge_document MCP prompt, FVS catalog via
    # library_url) so a Frame Check finding has a discoverable
    # path forward, not a static reading. Built AFTER divergence
    # because the highest-leverage action draws on the strongest
    # absent_frame, which only exists when include_divergence=True.
    # When divergence is off, the action list still includes the
    # findings-based reprompts and the always-present prompt
    # followup.
    divergence_block = payload.get("divergence")
    agent_guidance["suggested_next_actions"] = (
        _build_suggested_next_actions(
            analysis,
            divergence_block if isinstance(divergence_block, dict) else None,
        )
    )
    agent_guidance["how_to_render_suggested_next_actions"] = (
        "When composing the response, present "
        "suggested_next_actions as a small explicit list at the end "
        "of the reading (after the insight + question), introduced "
        "with one sentence like 'Things you can do next:'. Render "
        "the action_text verbatim or near-verbatim; do not paraphrase "
        "the rationale. The list is bounded (max 4 entries); render "
        "all entries the tool returned. Each 'resource' kind action "
        "already carries a clickable markdown link in its action_text "
        "(library_url-shaped); preserve the link form so the user "
        "can follow it. The 'reprompt' kind actions give the user a "
        "ready-made follow-up question for the source AI; render the "
        "quoted question verbatim. The 'prompt_followup' kind action "
        "names a Frame Check MCP prompt the user can ask you to "
        "invoke; surface it so the multi-turn loop is discoverable."
    )

    # compose_budget="standard" and "minimal" both compress
    # agent_guidance to load-bearing prescriptions only. The two tiers
    # differ in their divergence-side slicing (handled in the slicing
    # block above), not in the agent_guidance shape. Compression runs
    # AFTER the divergence merge so any divergence-specific keys
    # (how_to_render_divergence, frame_opportunities_discipline) are
    # preserved verbatim. compose_budget="full" keeps the rich
    # agent_guidance unchanged for first-time orientation, methodology
    # demos, or any case where the inline worked examples + claim-
    # level table earn their tokens. See
    # _compress_agent_guidance_to_load_bearing for compression rules.
    if compose_budget in ("standard", "minimal"):
        payload["agent_guidance"] = _compress_agent_guidance_to_load_bearing(
            agent_guidance, level=compose_budget,
        )
    return payload


# Compare path: per-document helpers + builder.

def _per_document_core(text: str) -> dict[str, Any]:
    """Run the per-document deterministic analyzers and return the
    dict shape comparison.py's _build_structural_framing_data
    expects (coverage, voice, epistemic, temporal, claim_count,
    hedged/unhedged counts). Used by build_compare_payload; keeps
    the per-doc analysis call site in one place.
    """
    from claim_analysis import analyze_claims
    from framing import (
        detect_coverage,
        temporal_orientation,
        detect_voice,
        detect_epistemic_basis,
    )
    from frame_library import suggest_frames

    ca = analyze_claims(text)
    # Same attribution + candidate-miss treatment as the single-doc tool.
    cov = detect_coverage(
        text, include_attribution=True, include_candidates=True,
    )
    voice = detect_voice(text)
    epist = detect_epistemic_basis(text, include_candidates=True)
    temp = temporal_orientation(text)
    frames = suggest_frames(cov, voice, temp, epist, text=text)

    return {
        "coverage": cov,
        "voice": voice,
        "epistemic": epist,
        "temporal": temp,
        "claims_raw": ca,
        "frames": frames or [],
        # Keys _build_structural_framing_data reads directly:
        "claim_count": ca.get("total_claims", 0),
        # Bug fix 2026-04-20: claim dicts carry framing="hedged" string,
        # not a hedged boolean. Previous sum always returned 0 (hedged)
        # and total (unhedged). Using analyze_claims' top-level totals.
        "unhedged_count": ca.get("unhedged_count", 0),
        "hedged_count": ca.get("hedged_count", 0),
    }


def _summarize_per_document(doc: dict[str, Any], text: str) -> dict[str, Any]:
    """Shape the per-document analysis for the compare payload.
    Smaller than the single-document frame_check payload because the
    point of compare is the cross-document signal; per-document
    detail is available by calling frame_check on each document
    individually.
    """
    cov = doc["coverage"]
    coverage_cats = cov.get("categories", {}) or {}
    return {
        "document": {
            "word_count_estimate": len(text.split()),
            "char_count": len(text),
            "sentence_count": doc["voice"].get("total_sentences", 0),
        },
        "coverage": {
            "addressed": cov.get("covered", []),
            "missing": cov.get("missing", []),
            "addressed_count": cov.get("coverage_count", 0),
            "total_categories": cov.get("total_categories", 5),
            "per_category_density_per_1kw": {
                cat: coverage_cats.get(cat, {}).get("density_per_1kw", 0)
                for cat in coverage_cats
            },
        },
        "coverage_v2": _build_coverage_v2(cov),
        "voice": {
            "classification": doc["voice"].get("voice"),
            "signals": {
                "first_person_plural_pct": doc["voice"].get("we_pct"),
                "second_person_pct": doc["voice"].get("you_pct"),
                "imperative_count": doc["voice"].get("imperative_count"),
            },
            # Phase B classification-confidence construct (see single-
            # doc endpoint for full construct commentary).
            "confidence": doc["voice"].get("confidence"),
            "margin_to_threshold": doc["voice"].get("margin_to_threshold"),
            "runner_up": doc["voice"].get("runner_up"),
            "runner_up_margin": doc["voice"].get("runner_up_margin"),
            "construct": _build_voice_construct(doc["voice"]),
            # Per-level construct treatment: parity with the frame_check tool
            # response so a client can handle both surfaces
            # uniformly. See agent_guidance.claim_level_treatments
            # in the frame_check payload (same payload shape on
            # frame_compare's agent_guidance).
            "claim_level": _CLAIM_LEVEL_CLASSIFIER,
        },
        "temporal": {
            "dominant": doc["temporal"].get("dominant"),
            "distribution_pct": {
                "past": doc["temporal"].get("past_pct"),
                "present": doc["temporal"].get("present_pct"),
                "future": doc["temporal"].get("future_pct"),
            },
            # Phase B distribution-with-dominant construct.
            "dominant_margin": doc["temporal"].get("dominant_margin"),
            "balanced": doc["temporal"].get("balanced"),
            "construct": _build_temporal_construct(doc["temporal"]),
            # Per-level construct treatment: parity with frame_check.
            "claim_level": _CLAIM_LEVEL_CLASSIFIER,
        },
        "epistemic": {
            "sourced_pct": doc["epistemic"].get("sourced_pct"),
        },
        "claims_extracted": {
            "total": doc["claim_count"],
            "hedged_count": doc["hedged_count"],
            "unhedged_count": doc["unhedged_count"],
            "by_type": doc["claims_raw"].get("claims_by_type", {}),
        },
        "frame_library_matches": [
            {
                "fvs_id": f.get("fvs_id"),
                "name": f.get("name"),
                # GitHub URL pointing at the entry's markdown source
                # on the public repository (Clarethium/frame-check).
                # See the frame_check tool's matching field for the
                # full rationale; same shape, same resolution
                # behavior, so a client can handle both surfaces
                # uniformly.
                "library_url": (
                    _library_entry_ref(f.get("fvs_id", "")).get("public_url")
                    if f.get("fvs_id") else None
                ),
                # MCP resource URI and per-entry version (same
                # fields as the frame_check tool response so a
                # client can handle both surfaces uniformly).
                "library_resource_uri": (
                    f"{RESOURCE_SCHEME}://library/{f.get('fvs_id')}"
                    if f.get("fvs_id") else None
                ),
                "library_entry_version": (
                    (_get_frame_versions() or {}).get(f.get("fvs_id", ""))
                ),
                "teaching_question": f.get("question"),
                "status": (
                    (_get_frame_statuses() or {}).get(f.get("fvs_id"))
                    if _get_frame_statuses() is not None else None
                ),
                "adjacent_frames": [
                    _library_entry_ref(adj_id)
                    for adj_id in (_get_frame_adjacency() or {}).get(
                        f.get("fvs_id", ""), []
                    )
                ],
                # affects_dimensions: same field as in the
                # frame_check tool response so a client can
                # handle both surfaces uniformly. See the
                # frame_check construction for full rationale.
                "affects_dimensions": _dimensions_affecting(
                    f.get("fvs_id", "")
                ),
                # Per-level construct treatment: parity with frame_check. Each
                # frame match is a V1 detector firing.
                "claim_level": _CLAIM_LEVEL_DETECTOR,
                # pattern_kind: parity with the frame_check builder.
                # See the frame_check construction site for the full
                # explanation of the five enum values
                # (present_detected, absence_detected, present_past,
                # present_future).
                "pattern_kind": f.get(
                    "pattern_kind", "present_detected"
                ),
            }
            for f in doc["frames"]
        ],
    }


def build_compare_payload(
    doc_a_text: str, doc_b_text: str,
    a_name: str = "Document A", b_name: str = "Document B",
) -> dict[str, Any]:
    """Run Frame Check's structural comparison on two documents and
    return the three-section epistemic payload.

    The analysis section carries (a) per-document summaries and (b)
    the cross-document comparison: shared blind spots, unique blind
    spots, voice / temporal match flags, coverage and sourcing
    deltas, and the structural framing differences built from the
    same comparison.py._build_structural_framing_data that powers
    the /compare page. Zero LLM. Deterministic for identical inputs.

    The agent_guidance and provenance sections mirror frame_check
    so a client agent handling either tool can rely on the same
    integrity contract. The comparison-specific guidance names the
    interpretive pitfalls that are unique to the compare surface:
    agreement does not mean truth, divergence does not name which
    side is correct, the tool does not rank documents.
    """
    from comparison import _build_structural_framing_data

    _ensure_caches()

    t_start = time.perf_counter()

    a = _per_document_core(doc_a_text)
    b = _per_document_core(doc_b_text)

    missing_a = set(a["coverage"].get("missing", []))
    missing_b = set(b["coverage"].get("missing", []))
    shared_blind = sorted(missing_a & missing_b)
    only_a_blind = missing_a - missing_b
    only_b_blind = missing_b - missing_a

    framing_data = _build_structural_framing_data(
        a_name, a, b_name, b,
        shared_blind, only_a_blind, only_b_blind,
    )

    elapsed_ms = int((time.perf_counter() - t_start) * 1000)

    analysis = {
        "documents": {
            a_name: _summarize_per_document(a, doc_a_text),
            b_name: _summarize_per_document(b, doc_b_text),
        },
        "comparison": {
            "coverage": {
                "shared_blind_spots": shared_blind,
                "only_a_misses": sorted(only_a_blind),
                "only_b_misses": sorted(only_b_blind),
                "addressed_count_delta": (
                    b["coverage"].get("coverage_count", 0)
                    - a["coverage"].get("coverage_count", 0)
                ),
            },
            "voice": {
                "match": (
                    a["voice"].get("voice") == b["voice"].get("voice")
                ),
                "a_classification": a["voice"].get("voice"),
                "b_classification": b["voice"].get("voice"),
                # Phase B cross-document classification-confidence
                # comparison. Both a and b are cascade-classified;
                # each carries a confidence label. Surfacing both
                # confidences lets the consumer distinguish "same
                # class, both decisive" (strong match) from "same
                # class, one borderline" (weaker match).
                "a_confidence": a["voice"].get("confidence"),
                "b_confidence": b["voice"].get("confidence"),
                "a_runner_up": a["voice"].get("runner_up"),
                "b_runner_up": b["voice"].get("runner_up"),
                "both_borderline": (
                    a["voice"].get("confidence") == "borderline"
                    and b["voice"].get("confidence") == "borderline"
                ),
                "construct_note": (
                    "Voice match/mismatch does not fully capture "
                    "classification agreement: two documents both "
                    "classified as the same class can differ in "
                    "confidence. Agents should surface a_confidence "
                    "and b_confidence when either is borderline."
                ),
            },
            "temporal": {
                "match": (
                    a["temporal"].get("dominant")
                    == b["temporal"].get("dominant")
                ),
                "a_dominant": a["temporal"].get("dominant"),
                "b_dominant": b["temporal"].get("dominant"),
                # Phase B cross-document distribution comparison.
                # dominant_margin + balanced exposed per side so the
                # consumer can distinguish "both past-dominant with
                # large margin" from "both past-dominant but a is
                # balanced" (different structural reads).
                "a_dominant_margin": a["temporal"].get("dominant_margin"),
                "b_dominant_margin": b["temporal"].get("dominant_margin"),
                "a_balanced": a["temporal"].get("balanced"),
                "b_balanced": b["temporal"].get("balanced"),
                "both_balanced": (
                    bool(a["temporal"].get("balanced"))
                    and bool(b["temporal"].get("balanced"))
                ),
                "construct_note": (
                    "Temporal match/mismatch on dominant tense does "
                    "not capture distribution shape. Agents should "
                    "surface a_balanced and b_balanced when either is "
                    "True, and the dominant_margin on both sides when "
                    "match=True to distinguish decisive co-orientation "
                    "from near-tied co-orientation."
                ),
            },
            "epistemic": {
                "a_sourced_pct": a["epistemic"].get("sourced_pct", 0),
                "b_sourced_pct": b["epistemic"].get("sourced_pct", 0),
                "sourced_pct_delta": (
                    (b["epistemic"].get("sourced_pct", 0) or 0)
                    - (a["epistemic"].get("sourced_pct", 0) or 0)
                ),
            },
            "framing_differences": framing_data,
        },
    }

    agent_guidance = {
        "what_this_tool_tells_you": [
            "Where two documents on the same subject diverge structurally",
            "Blind spots shared by both (perspectives where neither document shows detected markers)",
            "Coverage, voice, temporal, and epistemic deltas",
            "A structured framing-differences narrative with per-dimension reader implications",
            "Which named frame patterns each document activates",
        ],
        "what_this_tool_does_not_tell_you": [
            "Which document is more correct (agreement on a claim does not mean the claim is true; two documents can cite the same wrong training data)",
            "Which document the reader should trust more",
            "Whether structural differences translate to decision-relevant differences for the reader's purpose",
            "Reasoning quality, logical validity, or causal inference",
            "Numeric claim verification against external sources is not invoked in this response",
            "Whether perspectives flagged as missing in either document are truly absent, or discussed using vocabulary the detector does not recognize (under-detection is a known failure mode; 'missing' is a lower-bound claim)",
        ],
        "how_to_cite_faithfully": (
            "When surfacing this comparison to the user, name Frame "
            "Check and distinguish structural comparison from "
            "evaluative judgement. \"Frame Check's structural "
            "comparison found markers for 2 more analytical "
            "perspectives in Document A than in Document B\" is the "
            "right shape. \"Frame Check determined Document A is "
            "better than Document B\" is wrong: Frame Check does not "
            "rank documents. The measurements are deterministic and "
            "reproducible; paraphrasing them as your own ranking "
            "strips the method's scope."
        ),
        "how_to_surface_framing_differences": (
            "The framing_differences block has a headline (if one "
            "dimension dominates the divergence), per-dimension "
            "cards with a_value/b_value/note, and a shared_blind_note "
            "when both documents leave the same perspective unsaid. "
            "Surface the headline first, then the cards, then the "
            "shared_blind_note as closing. Each card's note is a "
            "reader implication, not a verdict."
        ),
        "when_to_invoke_again": (
            "frame_compare is deterministic for the same input pair. "
            "Calling it twice on identical (doc_a_text, doc_b_text) "
            "returns identical measurements. Re-invoke only when "
            "either document changes."
        ),
        # Per-level construct treatment (substrate-side composition
        # L5): frame_compare's per-document blocks carry claim_level
        # on each composed entity (frame_library_matches, voice,
        # temporal). The treatments dict is shared with frame_check
        # so a client handles both surfaces uniformly.
        "claim_level_treatments": _CLAIM_LEVEL_TREATMENTS,
    }

    # Provenance mirrors frame_check so a client can treat either
    # tool's output with the same integrity contract. The
    # analysis_layer names the compare path so downstream telemetry
    # and citations can distinguish the two surfaces; the
    # determinism note uses "input pair" because the unit of
    # determinism here is two documents, not one.
    provenance = _build_provenance(
        analysis_layer="deterministic_structural_comparison",
        elapsed_ms=elapsed_ms,
        determinism_note=(
            "Identical input pair produces identical output. No "
            "LLM is invoked in this response."
        ),
    )

    # Analysis manifest. Same structural shape as frame_check's
    # manifest above; documents-mode comparison surface, every LLM
    # path explicitly skipped because MCP's compare flow is also
    # zero-LLM by contract (FRAME_DIVERGENCE_CONTRACT_v1 §7).
    # Mirrors the web /compare manifest so an agent that reads both
    # surfaces sees the same provenance vocabulary.
    from manifest import build_compare_manifest as _build_cm
    manifest = _build_cm(
        mode="documents",
        analyzed_models={},
        reliability_tiers={},
        source_name_to_provider_key={},
        framing_comparison_call={
            "ran": False,
            "reason_skipped": (
                "Cross-document AI framing comparison is not invoked "
                "on the MCP server-side path. Per "
                "FRAME_DIVERGENCE_CONTRACT_v1 §7, AI narratives are a "
                "caller-side responsibility on this surface; the "
                "agent integrator composes the cross-document narrative "
                "using the structural comparison data above."
            ),
        },
        stability_call=None,
        topic_generation_calls=None,
    )
    manifest["surface"] = "mcp_frame_compare"

    return {
        "analysis": analysis,
        "agent_guidance": agent_guidance,
        "provenance": provenance,
        "manifest": manifest,
    }
