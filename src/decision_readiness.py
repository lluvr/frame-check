"""Decision-readiness profile computation.

Phase 1.5 of the decision-readiness work (per
/corpus/decision-readiness/ methodology). Computes the structured
five-dimension profile from existing display measurements.

Phase 1 was the methodology page. This module is Phase 1.5: the
profile data structure with backend computation, exposed via the
JSON download (display.decision_readiness). Deliberately NOT
surfaced in the UI because the profile remains experimental until
Phase 2 (expert validation) lands. Power users who download the
JSON can see the profile and provide feedback on the data structure
before it becomes a visible signal.

The profile composition rule is strict: every dimension is derived
from existing Frame Check measurements. We do not invent new
signals; we structure the ones we already publish so the user can
read decision-readiness without re-deriving it from raw fields.

What this module deliberately does NOT do:
  - Compute a single composite score (rejected by methodology)
  - Apply categorical labels with implied thresholds (rejected)
  - Generate a guidance sentence (Phase 2 work, after validation)
  - Adjust for genre (Phase 2 work; document_type-aware
    interpretation requires validation per genre first)

The output structure pairs every dimensional reading with the
underlying signal value, the secondary value where relevant, a
plain-language description, and an explanation tying the dimension
to the methodology page. The pairing is the construct-honesty
pattern: the user sees the signal AND its summary, and can question
the summary by reading the signal.
"""

from typing import Optional


METHODOLOGY_URL = "/corpus/decision-readiness/"
METHODOLOGY_VERSION = "v0.1"
PROFILE_STATUS = "experimental"  # bumps to "validated" after Phase 2

# Canon-graph reference URI scheme. Per-dimension library_entries
# are emitted as objects {fvs_id, library_resource_uri, public_url}
# so the canon graph is self-resolvable from any consumer:
#   - MCP agents: read library_resource_uri via MCP resources/read
#   - HTTP consumers: GET public_url for the citable HTML page
#   - Bare-ID consumers: fvs_id is still present for back-compat reads
# Same shape as adjacent_frames in mcp_server.py so an agent that
# already chains via adjacent_frames does not need a second schema
# for canon-graph citations from the decision-readiness profile.
#
# LIBRARY_RESOURCE_SCHEME must match RESOURCE_SCHEME in mcp_server.py
# (frame-check://). A test in test_decision_readiness.py pins the
# agreement so the two cannot drift silently.
LIBRARY_RESOURCE_SCHEME = "frame-check"
# public_url points at the entry's canonical markdown source on the
# public GitHub repository (Clarethium/frame-check). GitHub is always
# resolvable for end-users regardless of the hosted-production status
# at frame.clarethium.com (paused 2026-04-23). The previous form
# (https://frame.clarethium.com/corpus/library/FVS-XXX.html) returned
# rendered HTML when production was up but is unreachable while
# production is paused; the GitHub URL gives a citer a stable address
# that does not change across hosting state. Per-entry slugs come
# from frame_library_index.parse_entry_filenames() so the URL stays
# accurate when entries are renamed without touching this constant.
LIBRARY_PUBLIC_URL_BASE = (
    "https://github.com/Clarethium/frame-check"
    "/blob/master/data/frame_library"
)
# Corpus entry URL base, parallel to LIBRARY_PUBLIC_URL_BASE.
# Used by corpus_entry_ref to build public_url fields so consumers
# can chain from cross-question findings to the browsable corpus
# entry page. The MCP scheme is shared (frame-check://); only the
# path prefix differs (library/ vs corpus/).
CORPUS_PUBLIC_URL_BASE = (
    "https://frame.clarethium.com/corpus/decision-readiness/corpus"
)

# Module-cached title lookup. Populated EAGERLY at module import
# time (not lazily) because cross-module callers, particularly
# validation/decision_readiness/aggregate_corpus_findings.py,
# import library_entry_ref under a transient sys.path.insert that
# they pop before any ref-building call fires. A lazy import of
# frame_library_index inside _frame_titles would then fail (the
# REPO_ROOT is no longer on sys.path) and silently fall back to
# empty titles. Eager loading at module-import time happens while
# the caller's sys.path is still right.
#
# Two reasons titles live here (vs at the call site):
#   1. The canon-graph reference shape is owned by this module,
#      so the title injection lives at the same source of truth.
#   2. Cross-module callers (mcp_server adjacent_frames, aggregate
#      findings) get titles for free without each having to wire
#      their own INDEX.md parser.
try:
    from frame_library_index import (
        parse_entry_titles as _parse_entry_titles,
        parse_entry_filenames as _parse_entry_filenames,
    )
    _FRAME_TITLES_CACHE = _parse_entry_titles()
    _FRAME_FILENAMES_CACHE = _parse_entry_filenames()
except Exception:
    # frame_library_index is a sibling module at repo root; in
    # normal operation it always loads. The try/except is a defensive
    # fallback so a missing INDEX.md (or a clean checkout without
    # the frame_library tree) does not break decision_readiness
    # import. library_entry_ref falls back to the bare fvs_id when
    # a title is missing, and to a None public_url when no filename
    # is known, so the rest of the system still functions.
    _FRAME_TITLES_CACHE = {}
    _FRAME_FILENAMES_CACHE = {}


def _frame_titles() -> dict:
    """Returns {fvs_id: title}. Eagerly populated at module import."""
    return _FRAME_TITLES_CACHE


def _frame_filenames() -> dict:
    """Returns {fvs_id: filename}. Eagerly populated at module import.
    Filenames carry the entry's slug after the FVS-ID prefix; used to
    construct stable GitHub URLs that do not require slug derivation
    at the call site."""
    return _FRAME_FILENAMES_CACHE


def dimensions_affecting(fvs_id: str) -> list:
    """Returns the list of decision-readiness dimensions for which
    `fvs_id` is canon (a member of DIMENSION_LIBRARY_ENTRIES[dim]).
    Order follows the canonical DIMENSION_LIBRARY_ENTRIES iteration
    order (coverage, calibration, evidence, robustness, counterfactual)
    so consumers see dimensions in the same sequence as the
    methodology page's section ordering.

    Public API. Used by mcp_server.py to surface affects_dimensions
    on each frame_library_matches entry: an agent that detects a
    frame can immediately see which decision-readiness dimensions
    the detection threatens, closing the matched_frame ->
    affected_dimensions direction of the canon graph.

    Returns [] when the FVS-ID is not in any dimension's canon list
    (e.g., meta-side entries like FVS-002, FVS-005, FVS-006, FVS-013,
    FVS-020). Empty is honest: the entry is in the library but does
    not affect a specific decision-readiness dimension."""
    return [
        dim for dim, fvs_ids in DIMENSION_LIBRARY_ENTRIES.items()
        if fvs_id in fvs_ids
    ]


def library_entry_ref(fvs_id: str) -> dict:
    """Returns the canonical canon-graph reference object for a
    library entry. Public API: this function is the single source
    of truth for the canon-graph reference shape used across
    decision_readiness profiles, MCP adjacent_frames, and aggregate
    findings. Cross-module import is intended; do not duplicate the
    construction in any consumer.

    The title field carries the human-readable Name from INDEX.md
    so consumers can render "FVS-007 Failure Framing" inline rather
    than forcing a lookup or showing bare IDs. Falls back to the
    fvs_id when no title is available (INDEX.md missing, FVS-ID
    not in INDEX.md, etc.) so the field is always present."""
    titles = _frame_titles()
    filenames = _frame_filenames()
    fname = filenames.get(fvs_id)
    public_url = (
        f"{LIBRARY_PUBLIC_URL_BASE}/{fname}" if fname else None
    )
    # URI/URL field aliases: library_resource_uri is the canonical
    # MCP-resource URI; citation_uri is the alias name used on
    # divergence.absent_frames[*] and corpus_context.typical_co_*
    # records (since pre-1.0). Both carry the same
    # frame-check://library/<fvs_id> value. public_url is the
    # canonical HTTPS GitHub URL on this block; library_url is the
    # alias name used on absent_frames + frame_library_matches.
    # Both carry the same value. The v1.0.12 normalization emits
    # both names from this single builder so every caller propagates
    # the full {citation_uri, library_resource_uri, library_url,
    # public_url} quartet — adopters get one consistent shape
    # regardless of which block they read from.
    lib_resource_uri = f"{LIBRARY_RESOURCE_SCHEME}://library/{fvs_id}"
    return {
        "fvs_id": fvs_id,
        "title": titles.get(fvs_id) or fvs_id,
        "library_resource_uri": lib_resource_uri,
        "citation_uri": lib_resource_uri,
        "public_url": public_url,
        "library_url": public_url,
    }


def corpus_entry_ref(slug: str, title: str | None = None) -> dict:
    """Returns the canonical canon-graph reference object for a
    validation corpus entry. Parallel to library_entry_ref for
    library entries; both follow the same shape convention:

      - identifier (fvs_id OR slug)
      - title (human-readable, falls back to identifier when missing)
      - resource_uri (MCP frame-check:// URI for chaining)
      - public_url (HTTP URL for the browsable page)

    Used by aggregate cross_question_findings to carry corpus_entries
    references that MCP agents can chain to directly (via resource_uri)
    without reconstructing URIs. Same pattern as library_entry_ref,
    different namespace (corpus/ vs library/).

    Title falls back to slug when None so the field is always a
    non-empty string. Caller passes the title explicitly because
    corpus titles live in per-entry metadata.yaml, not in a shared
    index parsed at module load like frame_library_index."""
    # Field name carries the "corpus" namespace qualifier so an
    # agent iterating refs can tell which namespace from field
    # names alone (library_resource_uri vs corpus_resource_uri);
    # parity with library_entry_ref's namespace-qualified field.
    return {
        "slug": slug,
        "title": title or slug,
        "corpus_resource_uri": f"{LIBRARY_RESOURCE_SCHEME}://corpus/{slug}",
        "public_url": f"{CORPUS_PUBLIC_URL_BASE}/{slug}/",
    }


# FVS-016 Authority by Citation: detection thresholds.
#
# Derived directly from the library entry's "Branch applicability"
# section: "high sourced_pct (many claims use citation language)
# with low verification rate (Source Network cannot confirm the
# cited values). The gap between 'claims that look sourced' and
# 'claims that ARE verified' is the signal."
#
# Conservative by design. The library entry's "Honest limits"
# acknowledges the proxy cannot verify whether cited sources are
# real, only whether citation density mismatches verification
# outcomes. False positives would pollute the canon-graph signal
# across every document analyzed; missing some real FVS-016 cases
# is the correct failure mode.
#
# Promoted to module constants so a researcher tuning sees them in
# one place with rationale, not buried inline. Tuning these is a
# curatorial decision (changes the canon-graph signal everywhere);
# they are not exposed as runtime parameters.
FVS016_MIN_SOURCED_PCT = 30        # substantial citation markers
FVS016_MIN_CHECKED = 3              # enough claims for a stable ratio
FVS016_MAX_VERIFICATION_RATIO = 0.5  # most checked claims do NOT verify


def _synthesize_local_firings(framing: dict, sn: dict) -> list:
    """Synthesize canon-graph firings from this module's local view
    of source_network + epistemic signals: patterns that the
    detector layer (domain_baselines.py, framing.py) cannot detect
    because it does not have access to all the required inputs.

    Currently emits one pattern: FVS-016 Authority by Citation.
    Future patterns synthesized from local signals can be added
    here without changing the calling convention. The function is
    named generically so a future addition does not require
    renaming.

    FVS-016 firing rule (see FVS016_* threshold constants above):
      - sourced_pct >= FVS016_MIN_SOURCED_PCT (30%)
      - checked >= FVS016_MIN_CHECKED (3 numerical claims)
      - verification_ratio <= FVS016_MAX_VERIFICATION_RATIO (0.5)

    The salient question is taken verbatim from the library entry's
    "Salient questions under this frame" section so the canon
    remains the authoritative source for what to ask the reader.

    MCP-context note. In MCP responses, source_network is a
    SYNTHETIC structure built from source_fidelity (literal-digit-
    substring presence in the user-supplied source_text), not from
    Source Network authoritative-provider verification. The FVS-016
    firing semantics in MCP context are therefore softer: "the
    document's digits don't even appear in the source text the user
    uploaded" rather than "the cited values fail authoritative
    verification." Both signals are real expressions of the
    Authority by Citation pattern, but the MCP-context reading is a
    weaker proxy. The library entry's "Honest limits" section
    covers this kind of proxy gap; agents surfacing the firing
    should not overstate the verification authority.

    Returns a list of frame_suggestion-shaped dicts (fvs_id, name,
    signal, question) ready to merge with any detector-layer
    emissions. Empty list when the thresholds are not met so
    callers can unconditionally concatenate.
    """
    sourced_pct = (framing.get("epistemic") or {}).get("sourced_pct")
    checked = (sn or {}).get("checked", 0) or 0
    verified = (sn or {}).get("verified", 0) or 0
    if (
        sourced_pct is None
        or checked < FVS016_MIN_CHECKED
        or sourced_pct < FVS016_MIN_SOURCED_PCT
    ):
        return []
    verification_ratio = verified / checked
    if verification_ratio > FVS016_MAX_VERIFICATION_RATIO:
        return []
    return [{
        "fvs_id": "FVS-016",
        "name": "Authority by Citation",
        "signal": (
            f"Citation markers in {sourced_pct}% of sentences but only "
            f"{verified} of {checked} numerical claims verified "
            f"({int(verification_ratio * 100)}% verification rate)"
        ),
        # Verbatim from FVS-016 library entry's "Salient questions
        # under this frame" section. Keeping the canon as the
        # source of truth for what readers should ask.
        "question": "Can I look up the specific source cited?",
    }]


def _fired_library_entries(dim_name: str, framing: dict) -> list:
    """Returns the subset of DIMENSION_LIBRARY_ENTRIES[dim_name]
    whose detector emitted a frame_suggestion in this analysis,
    as canonical canon-graph reference objects (same shape as the
    full library_entries list).

    Why filter to canon-graph members only:
      The detector layer also emits FVS-002 (Confidence Imbalance)
      which fires the existing calibration boolean
      (confidence_imbalance_fired), but FVS-002 is NOT in
      calibration's library_entries because the library entry
      FVS-002 is "Fluency-Quality Illusion" (a meta-side frame
      about reader evaluation, not the same concept as the
      detector pattern). The detector-vs-library naming mismatch
      is documented on the methodology page; surfacing FVS-002 in
      fired_library_entries would propagate that mismatch into
      every per-document profile and confuse agents about which
      canonical entry to chain to. The existing booleans carry
      the detector signal verbatim for callers that want it; this
      list is canon-aligned focused chaining.

    Returns an empty list (never None) when no canonically-mapped
    detector fired for the dimension. Empty is honest: the
    analysis ran, no canon entry's pattern was detected.
    """
    suggestions = framing.get("frame_suggestions") or []
    detected_ids = {
        s.get("fvs_id") for s in suggestions if s.get("fvs_id")
    }
    canon_ids = DIMENSION_LIBRARY_ENTRIES.get(dim_name, [])
    return [
        library_entry_ref(fid)
        for fid in canon_ids
        if fid in detected_ids
    ]

# Bidirectional canon graph: per-dimension library cross-
# references. Each library entry's markdown source carries a
# "Decision-readiness implication" section pointing at the
# dimension(s) it affects; this dict carries the reverse pointer
# so the profile JSON itself surfaces library citations per
# dimension. Curated mapping; aligned with the methodology page's
# "Related library entries" subsections.
#
# Detector-vs-library naming note: the detector code in
# domain_baselines.py emits a calibration pattern labeled
# "Confidence Imbalance" with ID FVS-002, but the library entry
# FVS-002 is "Fluency-Quality Illusion" (a meta-side frame about
# reader evaluation). The two are different concepts. The
# methodology page and this mapping cite FVS-012 (Uncertainty
# Frame) as the canonical library entry for calibration; the
# detector's FVS-002 label is an open issue requiring
# curator-level resolution (rename detector pattern OR add a new
# library entry under its own FVS-ID).
DIMENSION_LIBRARY_ENTRIES = {
    "coverage": [
        "FVS-001", "FVS-008", "FVS-009", "FVS-010",
        "FVS-011", "FVS-014", "FVS-015", "FVS-017",
    ],
    "calibration": ["FVS-012", "FVS-017"],
    "evidence": ["FVS-016"],
    "robustness": ["FVS-016"],
    "counterfactual": [
        "FVS-001", "FVS-007", "FVS-009", "FVS-012", "FVS-014",
    ],
}


def compute_decision_readiness(display: dict) -> Optional[dict]:
    """Build the decision-readiness profile from a display dict.

    Returns the structured profile, or None when the display lacks
    the minimum data needed (no framing, no claims). The None case
    is honest: a profile derived from missing data would mislead.

    The display dict is the same one the result-page template reads
    from; this function does not query analyzers or run any new
    detection. All five dimensions are read off existing fields.

    Output shape:
      {
        "methodology_url": "/corpus/decision-readiness/",
        "methodology_version": "v0.1",
        "status": "experimental",
        "dimensions": {
          "coverage": {...},
          "calibration": {...},
          "evidence": {...},
          "robustness": {...},
          "counterfactual": {...},
        },
      }

    Each dimension dict carries:
      name: human-readable dimension name
      signal_value: primary numeric signal (raw, not rounded)
      signal_secondary: secondary numeric signal where applicable
      signal_text: plain-language one-liner describing the reading
      explanation: tie-back to methodology dimension definition
    """
    if not display or not isinstance(display, dict):
        return None

    framing = display.get("framing") or {}
    claims = display.get("claims") or {}
    sn = display.get("source_network") or {}

    # Profile requires at minimum a framing block. Without it we have
    # no coverage signal and the profile is not meaningful.
    if not framing:
        return None

    dims = {
        "coverage": _coverage_dimension(framing),
        "calibration": _calibration_dimension(claims, framing),
        "evidence": _evidence_dimension(sn, framing),
        "robustness": _robustness_dimension(sn),
        "counterfactual": _counterfactual_dimension(framing),
    }
    # Build an effective frame_suggestions list that merges the
    # detector-layer emissions (already in framing.frame_suggestions
    # from framing.py) with any FVS-016 synthesis from this
    # module's local view of source_network +
    # epistemic. The synthesis is needed because the detector layer
    # does not have source_network access and FVS-016's defining
    # signal requires it. The merge happens against a SHALLOW COPY
    # so the caller's framing dict is not mutated (other code that
    # consumes display.framing should not see synthesized entries
    # unless it explicitly opts in).
    synthesized = _synthesize_local_firings(framing, sn)
    if synthesized:
        framing_for_firing = dict(framing)
        framing_for_firing["frame_suggestions"] = (
            list(framing.get("frame_suggestions") or []) + synthesized
        )
    else:
        framing_for_firing = framing

    # Attach library-entry citations per dimension. The graph
    # closes the bidirectional canon loop: each library entry's
    # markdown source has a "Decision-readiness implication"
    # section pointing at dimensions; this attaches the reverse
    # pointer so the profile JSON itself surfaces library
    # citations. Consumers can route to /corpus/library/{fvs_id}
    # without traversing the methodology page.
    for dim_name, dim_data in dims.items():
        # Object form: each entry carries fvs_id + MCP resource URI +
        # public URL so an agent receiving the profile can chain to
        # the named library entry without doing schema translation.
        # Mirrors the adjacent_frames shape already shipping in MCP
        # responses for matched frames.
        dim_data["library_entries"] = [
            library_entry_ref(fvs_id)
            for fvs_id in DIMENSION_LIBRARY_ENTRIES.get(dim_name, [])
        ]
        # fired_library_entries: the canon-aligned SUBSET that the
        # detector layer specifically detected in this document. Same
        # ref shape as library_entries so an agent iterating receives
        # the focused set ("here are the named patterns that fired
        # for this analysis") without having to scan the full canon
        # list. Empty list when no canonically-mapped detector fired.
        # Existing booleans (confidence_imbalance_fired,
        # failure_framing_absent) remain authoritative for diff/peer
        # comparison logic; fired_library_entries is the agent-facing
        # canon-aligned view.
        dim_data["fired_library_entries"] = _fired_library_entries(
            dim_name, framing_for_firing,
        )
        # Append a named-pattern mention to signal_text when FVS-016
        # fires in this dimension, mirroring the existing convention:
        # calibration's signal_text mentions Confidence Imbalance
        # when FVS-002 fires; counterfactual's mentions Failure
        # Framing when FVS-007 fires. Without this, evidence and
        # robustness would surface the firing only in the structured
        # field, missing the prose channel that the MCP sovereignty
        # prompts instruct agents to use ("name each dimension by
        # its signal_text reading").
        if any(
            r.get("fvs_id") == "FVS-016"
            for r in dim_data["fired_library_entries"]
        ):
            dim_data["signal_text"] = (
                dim_data["signal_text"]
                + " Authority by Citation pattern detected (FVS-016)."
            )

    return {
        "methodology_url": METHODOLOGY_URL,
        "methodology_version": METHODOLOGY_VERSION,
        "status": PROFILE_STATUS,
        "dimensions": dims,
    }


def _coverage_dimension(framing: dict) -> dict:
    """Coverage of perspectives.

    Signal: how many of the five analytical dimensions (causes,
    risks, stakeholders, trends, uncertainty) the document
    addresses, plus the coverage balance (ratio of thinnest
    addressed dimension to thickest).
    """
    coverage = framing.get("coverage") or {}
    count = coverage.get("coverage_count")
    total = coverage.get("total_categories", 5)
    balance = coverage.get("coverage_balance")
    covered = coverage.get("covered") or []
    missing = coverage.get("missing") or []

    if count is None:
        text = "No coverage data."
    else:
        parts = [f"{count} of {total} perspectives addressed."]
        if balance is not None and count >= 2:
            parts.append(f"Coverage balance: {round(balance * 100)}%.")
        text = " ".join(parts)

    return {
        "name": "Coverage of perspectives",
        "signal_value": count,
        "signal_secondary": balance,
        "signal_text": text,
        "covered": list(covered),
        "missing": list(missing),
        "explanation": (
            "Of five analytical dimensions (causes, risks, "
            "stakeholders, trends, uncertainty), how many the document "
            "addresses and how balanced their coverage densities are. "
            "An analysis that addresses many dimensions superficially "
            "is the Completeness Illusion (FVS-010)."
        ),
    }


def _calibration_dimension(claims: dict, framing: dict) -> dict:
    """Claim calibration.

    Signal: hedge ratio (hedged claims / total claims) and count of
    claims stated as predictions. High unhedged + high prediction
    counts suggest overconfidence.
    """
    total = claims.get("total_claims") or 0
    hedged = claims.get("hedged_count") or 0
    unhedged = claims.get("unhedged_count") or 0
    predictions = claims.get("prediction_count") or 0

    hedge_ratio = (hedged / total) if total > 0 else None

    # Confidence Imbalance (FVS-002) flags ratio > 3 with count >= 3.
    suggestions = framing.get("frame_suggestions") or []
    confidence_imbalance_fired = any(
        s.get("fvs_id") == "FVS-002" for s in suggestions
    )

    if total > 0:
        parts = [f"{hedged} of {total} claims hedged."]
        if predictions > 0:
            parts.append(
                f"{predictions} stated as prediction"
                f"{'s' if predictions != 1 else ''}."
            )
        if confidence_imbalance_fired:
            parts.append("Confidence Imbalance pattern detected.")
        text = " ".join(parts)
    else:
        text = "No claims extracted to calibrate."

    return {
        "name": "Claim calibration",
        "signal_value": hedge_ratio,
        "signal_secondary": predictions,
        "signal_text": text,
        "claim_total": total,
        "claim_hedged": hedged,
        "claim_unhedged": unhedged,
        "claim_predictions": predictions,
        "confidence_imbalance_fired": confidence_imbalance_fired,
        "explanation": (
            "Are claims appropriately hedged given their epistemic "
            "status? Overconfidence is the canonical decision "
            "pathology in the calibration literature; the hedge "
            "ratio is a textual proxy for it."
        ),
    }


def _evidence_dimension(sn: dict, framing: dict) -> dict:
    """Evidence backing.

    Signal: share of numerical claims that match an authoritative
    source, plus the share of sentences attributed to a source.
    """
    checked = sn.get("checked") or 0
    verified = sn.get("verified") or 0
    epistemic = framing.get("epistemic") or {}
    sourced_pct = epistemic.get("sourced_pct")
    numeric_sentences = epistemic.get("numeric_sentences") or 0

    verification_ratio = (verified / checked) if checked > 0 else None
    providers = sn.get("verified_providers") or []
    n_providers = len(providers)

    parts = []
    if checked > 0:
        if n_providers > 0:
            parts.append(
                f"{verified} of {checked} numerical claims "
                f"source-verified across {n_providers} "
                f"provider{'s' if n_providers != 1 else ''}."
            )
        else:
            parts.append(
                f"{verified} of {checked} numerical claims source-verified."
            )
    elif sourced_pct is not None:
        # Distinguish "document carries no numerical claims" from
        # "numerical claims exist but the source network attempted
        # zero verifications" (the dominant pipx-installed case
        # where API keys are absent). Collapsing these two into
        # "No numerical claims to verify" inverts the actual signal
        # for any agent reading evidence.signal_text. Phrasing
        # parallels the verified branch ("X of Y numerical claims
        # source-verified") so an agent walking the dimensions
        # reads consistent grammar across success and zero-attempt
        # paths.
        if numeric_sentences > 0:
            parts.append(
                f"0 of {numeric_sentences} numerical claim"
                f"{'s' if numeric_sentences != 1 else ''} "
                f"source-verified (source network attempted "
                f"no verifications)."
            )
        else:
            parts.append("No numerical claims to verify against sources.")
    else:
        parts.append("No evidence-backing data.")

    if sourced_pct is not None:
        parts.append(
            f"{sourced_pct}% of sentences attributed to sources."
        )

    text = " ".join(parts)

    return {
        "name": "Evidence backing",
        "signal_value": verification_ratio,
        "signal_secondary": sourced_pct,
        "signal_text": text,
        "verified": verified,
        "checked": checked,
        "providers_count": n_providers,
        "sourced_pct": sourced_pct,
        "explanation": (
            "Are claims supported by sources, or floating "
            "assertions? Numerical claims are checked against "
            "authoritative providers (calibrated by F1 in the "
            "calibration corpus). Source-attribution share is a "
            "second proxy for evidence backing at the sentence "
            "level."
        ),
    }


def _robustness_dimension(sn: dict) -> dict:
    """Robustness.

    Signal: count of contradicted or disputed claims. Each
    contradicted claim is a load-bearing assertion the analysis
    failed to align with an external source.
    """
    contradicted = sn.get("contradicted") or 0
    disputed = sn.get("disputed") or 0
    checked = sn.get("checked") or 0

    fail_count = contradicted + disputed

    if checked > 0:
        if fail_count == 0:
            text = f"No contradictions across {checked} checked claims."
        elif fail_count == 1:
            text = f"1 of {checked} checked claims contradicts its source."
        else:
            text = (
                f"{fail_count} of {checked} checked claims "
                f"contradict their sources."
            )
    else:
        text = "No claims checked against sources."

    return {
        "name": "Robustness",
        "signal_value": fail_count,
        "signal_secondary": checked,
        "signal_text": text,
        "contradicted": contradicted,
        "disputed": disputed,
        "checked": checked,
        "explanation": (
            "Does the analysis hold up under scrutiny from "
            "available evidence? Contradicted numerical claims are "
            "the load-bearing test: a single contradiction can "
            "invalidate a chain of reasoning."
        ),
    }


def _counterfactual_dimension(framing: dict) -> dict:
    """Counterfactual thinking.

    Signal: presence of failure-framing markers (FVS-007 fires when
    limitations / risks are absent) and presence of the uncertainty
    dimension in coverage. Both negative-signal absences here are
    treated as signals of weak counterfactual thinking.
    """
    suggestions = framing.get("frame_suggestions") or []
    coverage = framing.get("coverage") or {}
    covered = coverage.get("covered") or []

    failure_framing_absent = any(
        s.get("fvs_id") == "FVS-007" for s in suggestions
    )
    uncertainty_addressed = "uncertainty" in covered
    risks_addressed = "risks" in covered

    # Composite signal: True if the document does engage with
    # counterfactual thinking (at least one positive signal AND no
    # negative signal). The signal is conservative; we err toward
    # marking as weak when uncertain.
    engages = (
        not failure_framing_absent
        and (uncertainty_addressed or risks_addressed)
    )

    parts = []
    if failure_framing_absent:
        parts.append("Failure Framing absent (FVS-007 detected).")
    not_addressed = []
    if not uncertainty_addressed:
        not_addressed.append("uncertainty")
    if not risks_addressed:
        not_addressed.append("risks")
    if not_addressed:
        if len(not_addressed) == 1:
            parts.append(
                f"No markers detected for the {not_addressed[0]} "
                f"dimension."
            )
        else:
            joined = " and ".join(not_addressed)
            parts.append(
                f"No markers detected for the {joined} dimensions."
            )
    elif not failure_framing_absent:
        parts.append(
            "Markers detected for both uncertainty and risks."
        )
    text = " ".join(parts) if parts else "No counterfactual signal."

    return {
        "name": "Counterfactual thinking",
        "signal_value": engages,
        "signal_secondary": None,
        "signal_text": text,
        "failure_framing_absent": failure_framing_absent,
        "uncertainty_addressed": uncertainty_addressed,
        "risks_addressed": risks_addressed,
        "explanation": (
            "Does the analysis name what would falsify it, or what "
            "alternatives it has considered? Confirmation bias is "
            "the most-documented decision pathology; the absence of "
            "limitations / risks / uncertainty markers is the "
            "structural proxy for it."
        ),
    }
