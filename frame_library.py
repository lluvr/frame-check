"""
Frame library suggestions based on framing analysis output.

Maps the structural signals from framing.py (coverage, voice, temporal,
epistemic) to FVS library entries. Each suggestion names the frame,
gives a one-sentence explanation of why it was detected, and provides
a teaching prompt that helps the reader see past the frame.

Construct honesty: this function detects STRUCTURAL PATTERNS that
correlate with known frames. It does not detect semantic framing.
A document that structurally matches the Growth Frame pattern
(high trends, absent risks) might actually be a balanced analysis
of a growing market. The suggestions are hypotheses, not verdicts.
"""

import re
from typing import Any


# Growth-context vocabulary discriminator for FVS-008 (Growth Frame)
# detection. Move D-FVS-008 (2026-04-27): the structural signal alone
# (trends/causes covered + risks missing + voice not descriptive) over-fires
# on analytical documents that use directional-change vocabulary in
# non-business contexts (e.g., "scaling laws" in a literature review,
# "evolution" in institutional governance analysis, "growth" of a population
# or field). The frame's CONSTRUCT is business-growth framing specifically
# (organizing information around growth metrics, market expansion, upward
# trajectory). This regex requires explicit business-growth vocabulary
# alongside the structural signal so the rule fires only when the document
# is substantively about business growth.
#
# Conservative scope: business-growth markers (revenue, sales, earnings,
# market share/expansion/opportunity, customer/user/subscriber growth,
# adoption metrics, TAM, top-line, commercialization) plus quantified-growth
# patterns (X grew by $Y, N percent growth/annualized). Excludes bare
# "grow" / "expansion" / "scale" used generically in non-business contexts.
#
# Cross-fixture evidence: epistemic_via_paraphrased_sourcing (literature
# review on language-model interpretability) and cross_domain_stakeholder
# (Antarctic Treaty governance) both produced FVS-008 over-fire under the
# pre-Move-D rule and both correctly suppress under this discriminator.
# Validation-corpus check: 9 of 28 docs over-fire pre-Move-D; all 9 lack
# business-growth vocabulary and correctly suppress post-Move-D.
_FVS_008_GROWTH_CONTENT_RE = re.compile(
    r'\b('
    r'revenue|sales|earnings|profits?|TAM|top.line|bottom.line|'
    r'market\s+(?:share|growth|expansion|opportunity|size|cap)|'
    r'addressable\s+market|'
    r'customer\s+(?:growth|adoption|acquisition|base)|'
    r'user\s+(?:growth|adoption|acquisition|base)|'
    r'subscriber\s+(?:growth|adoption|base)|'
    r'installed\s+base|commercialization|monetization|'
    r'(?:grew|growth|growing|grow)\s+(?:by|to|from|at|of|its)\s+'
    r'(?:[\$\d]|the\s+market|customer|the\s+business)|'
    r'\d+\s*(?:percent|%)\s+(?:growth|annualized|grew|growing)'
    r')\b',
    re.IGNORECASE,
)


# Identity marker patterns for FVS-006 Identity Framing Asymmetry detection.
# The rule fires when the text uses role-claim language at meaningful density.
# See DETECTION_RULE_AUDIT_v1.md §4.4 for the proposed rule and honest-
# limits note: this regex detects the STRUCTURAL signal (identity claim
# density), not the SEMANTIC signal (whether the claimed identity produced
# behavioral shift). Teaching question frames the gap explicitly.
IDENTITY_MARKERS_RE = re.compile(
    r'\b(as\s+an?\s+(?:expert|analyst|professional|specialist|authority|'
    r'consultant|researcher|practitioner|scientist|economist|strategist)|'
    r'from\s+the\s+perspective\s+of\s+an?|'
    r'speaking\s+as|in\s+my\s+role|playing\s+the\s+role\s+of|'
    r'act(?:ing)?\s+as|my\s+(?:role|perspective|expertise|experience))\b',
    re.IGNORECASE,
)

# Human-readable names for FVS IDs. Used by the mirror template
# to show "Growth Frame" instead of "FVS-008" in session cards.
FVS_NAMES: dict[str, str] = {
    "FVS-001": "Frame Amplification",
    "FVS-002": "Fluency-Quality Illusion",
    "FVS-003": "Prompt Attribution Error",
    "FVS-004": "Default Geometry",
    "FVS-005": "System Attribution Error",
    "FVS-006": "Identity Framing Asymmetry",
    "FVS-007": "Failure Framing",
    "FVS-008": "Growth Frame",
    "FVS-009": "Risk Frame",
    "FVS-010": "Completeness Illusion",
    "FVS-011": "Stakeholder Frame",
    "FVS-012": "Uncertainty Frame",
    "FVS-013": "Oracle Frame",
    "FVS-014": "Temporal Anchoring",
    "FVS-015": "Efficiency Frame",
    "FVS-016": "Authority by Citation",
    "FVS-017": "False Balance",
    "FVS-018": "Scope Narrowing",
    "FVS-019": "Narrative Coherence",
    "FVS-020": "The Invisible Frame",
}

# Canonical teaching questions per FVS entry. Mirrors the questions
# the firing rules in suggest_frames() emit when a frame matches;
# extracted here as a lookup so absent_frames (which never fire and
# therefore never get a question via _add) can be paired with their
# canonical teaching question for documentation, agent_guidance,
# and frame_opportunities composition.
#
# TODO(operator-authorship): 8 of 20 entries lack a teaching question
# (FVS-003, 004, 005, 006, 013, 018, 019, 020; all meta-side frames,
# 3 of 8 are withdrawn from v1 publication: FVS-003, 004, 018, 019).
# Authoring queue + per-entry construct-hint context lives in
# OPERATOR_AUTHORING_QUEUE.md. Per the project's "no LLM drafting of
# substantive content" discipline, teaching questions are operator-
# authored. The harness L7 FAIL is the visible gate that holds until
# the queue is closed; do not paper over it with placeholder questions.
# See get_teaching_question() below: it returns None for unauthored
# IDs and call sites must handle that path explicitly.
TEACHING_QUESTIONS: dict[str, str] = {
    "FVS-001": (
        "What is the framing this analysis is amplifying, and what "
        "would change if the frame itself were named explicitly?"
    ),
    "FVS-002": (
        "If this were written in rough notes instead of polished "
        "prose, would you still accept the claims?"
    ),
    "FVS-007": (
        "What would have to be true for this analysis to be wrong?"
    ),
    "FVS-008": (
        "What would a risk analyst say about this same data?"
    ),
    "FVS-009": (
        "Is the risk analysis proportionate, or is it overweighting "
        "worst-case scenarios?"
    ),
    "FVS-010": (
        "Does this document MENTION all perspectives or ANALYZE all "
        "perspectives?"
    ),
    "FVS-011": (
        "Is the stakeholder analysis substantive (specific impacts "
        "per group, tradeoffs named) or performative (stakeholder "
        "groups mentioned without analyzing who wins and who loses)?"
    ),
    "FVS-012": (
        "Is the uncertainty named substantively (ranges, assumptions, "
        "expert disagreement) or merely hedged (language softened "
        "without specifics)?"
    ),
    "FVS-014": (
        "What has changed since this data was current? Is the "
        "document presenting historical data as if it were the "
        "present?"
    ),
    "FVS-015": (
        "Is efficiency the right lens here, or has it been applied "
        "by default?"
    ),
    "FVS-016": (
        "Can you look up the specific sources cited? Would the "
        "argument survive if the citations were removed?"
    ),
    "FVS-017": (
        "What perspective is being excluded by this framing's "
        "balance? Is the balance structural or rhetorical?"
    ),
}


def get_teaching_question(fvs_id: str) -> str | None:
    """Return the canonical teaching question for an FVS ID, or None
    when no question is curated for that entry. Used by
    frame_opportunities to pair absent frames with their general
    teaching question before LLM composition."""
    return TEACHING_QUESTIONS.get(fvs_id)


_DEFINITIONS: dict[str, str] = {
    "FVS-001": (
        "When AI converges on a frame, each iteration produces more "
        "sophisticated analysis within that frame. The analysis gets "
        "sharper. The conclusions get more confident. The frame itself "
        "goes unexamined."
    ),
    "FVS-002": (
        "Both humans and LLMs treat fluency as a proxy for quality. "
        "Smooth delivery, confident tone, and polished language make "
        "content feel correct whether or not it is. Errors hide in "
        "plain sight because the output feels good."
    ),
    "FVS-007": (
        "Specifying what counts as failure constrains output more "
        "sharply than specifying what success looks like. This document "
        "makes claims without naming what would make them wrong."
    ),
    "FVS-008": (
        "The default analytical frame for most AI-generated business "
        "content. Organizes information around growth metrics, market "
        "expansion, and upward trajectory while omitting risks, "
        "stakeholders, and uncertainty."
    ),
    "FVS-010": (
        "A document that addresses all expected dimensions can still "
        "operate from a single dominant frame. Breadth of coverage is "
        "not breadth of perspective. One sentence on risks is not "
        "risk analysis."
    ),
    "FVS-009": (
        "Organizes information around what could go wrong, what is "
        "vulnerable, and what depends on assumptions that might not hold. "
        "The counter-default to the growth frame. Risk analysis, not pessimism."
    ),
    "FVS-014": (
        "A document anchors the reader's perception of time by "
        "choosing which temporal orientation to emphasize. Past-anchored, "
        "future-projected, or present-focused: each hides the others."
    ),
    "FVS-015": (
        "Organizes information around cost reduction, optimization, "
        "and doing more with less. AI defaults to the efficiency "
        "frame because AI is itself positioned as an efficiency "
        "technology."
    ),
    "FVS-016": (
        "A document establishes credibility by citing sources. When "
        "citations are fabricated, misattributed, or real but not "
        "supporting the specific claim, the appearance of evidence "
        "substitutes for evidence."
    ),
    "FVS-011": (
        "Organizes information around who is affected, who benefits, "
        "who bears costs, and whose perspective is represented or "
        "excluded. The stakeholder frame asks 'for whom' and reveals "
        "whose interests the analysis serves by default."
    ),
    "FVS-012": (
        "Organizes information around what is unknown, contested, or "
        "dependent on assumptions that might not hold. The uncertainty "
        "frame surfaces the gap between confidence of presentation and "
        "confidence of evidence."
    ),
}


def suggest_frames(
    coverage: dict[str, Any],
    voice: dict[str, Any],
    temporal: dict[str, Any],
    epistemic: dict[str, Any],
    text: str | None = None,
) -> list[dict[str, str]]:
    """Suggest FVS library entries that match the framing analysis output.

    Returns a list of dicts, each with:
      fvs_id:      stable identifier (e.g., "FVS-008")
      name:        human-readable frame name
      signal:      which detection outputs triggered this suggestion
      question:    one teaching question the reader should ask
      definition:  one-paragraph explanation of the frame

    Optional `text` parameter enables text-dependent rules that cannot
    operate on structural dicts alone (FVS-006 Identity Framing
    Asymmetry's identity-marker density). Non-breaking: when text is
    None, text-dependent rules simply do not fire. Existing callers
    unaffected; new callers that want full detection coverage pass the
    raw document.
    """
    suggestions = []
    cats = coverage.get("categories", {})
    covered = set(coverage.get("covered", []))
    missing = set(coverage.get("missing", []))
    voice_type = voice.get("voice", "")
    sourced_pct = epistemic.get("sourced_pct", 100)
    total_sentences = voice.get("total_sentences", 0)

    # Guard: suppress suggestions on very short documents (<5 sentences).
    # Detection is unreliable on short text because a single keyword
    # match triggers coverage and the frame suggestions become noise.
    if total_sentences < 5:
        return suggestions

    def _add(fvs_id, name, signal, question, pattern_kind="present_detected"):
        # `pattern_kind` encodes the V1-detector emission convention as a
        # structured enum field. Five values correspond to the five suffix
        # conventions historically encoded in `name`:
        #   "present_detected"  positive present-pattern detection
        #                       (FVS-002, FVS-008, FVS-009, FVS-010,
        #                        FVS-011, FVS-012, FVS-015, FVS-016 sites)
        #   "absence_detected"  absence-pattern detection (FVS-007 site)
        #   "present_past"      directional past-anchored present
        #                       (FVS-014 past site)
        #   "present_future"    directional future-anchored present
        #                       (FVS-014 future site)
        # The legacy suffix in `name` is preserved for backward compat with
        # operator-facing UI rendering at `V4_2_GAP_INVENTORY_v1.md:194`
        # (the chip-renderer that distinguishes "(active)" vs "(absent)")
        # and with hand-authored test fixtures at
        # `test_decision_readiness.py:407, 1095` that pin the literal
        # "Failure Framing (absent)" name shape. Future cleanup that
        # strips the suffix is a separate decision; this change is purely
        # additive at the wire surface.
        suggestions.append({
            "fvs_id": fvs_id,
            "name": name,
            "signal": signal,
            "question": question,
            "definition": _DEFINITIONS.get(fvs_id, ""),
            "url": f"/corpus/library/{fvs_id}.html",
            "pattern_kind": pattern_kind,
        })

    # ── Growth Frame (FVS-008) ──
    # Move D-FVS-008 (2026-04-27): the structural signal alone (trends/causes
    # covered + risks missing + voice not descriptive) is too coarse: it fires
    # on any analytical document with directional-change vocabulary (trends
    # regex matches "evolution", "shift", "emerging", "transformation",
    # "expand" generically). Two adversarial fixtures provided cross-domain
    # worked examples of the over-fire (epistemic_via_paraphrased_sourcing
    # and cross_domain_stakeholder); validation corpus showed 9 of 28 docs
    # with the same over-fire signature, none of them substantively about
    # business growth. The frame's CONSTRUCT is business-growth framing
    # specifically (frame_library.py::_DEFINITIONS["FVS-008"]: "Organizes
    # information around growth metrics, market expansion, and upward
    # trajectory while omitting risks, stakeholders, and uncertainty"); the
    # fix is a content discriminator requiring growth-context vocabulary
    # alongside the structural signal. When text is None, FVS-008 falls
    # through per the standing "text-dependent rules don't fire when text
    # is None" discipline (see function docstring).
    has_growth_signal = (
        ("trends" in covered or "causes" in covered)
        and "risks" in missing
        and voice_type not in ("descriptive", "insufficient")
        and text is not None
        and bool(_FVS_008_GROWTH_CONTENT_RE.search(text))
    )
    if has_growth_signal:
        _add(
            "FVS-008", "Growth Frame",
            "High trends/causes coverage with risks absent and "
            "growth-context vocabulary present",
            "What would a risk analyst say about this same data?",
        )

    # ── Fluency-Quality Illusion (FVS-002) ──
    if voice_type == "promotional" and sourced_pct < 30:
        _add(
            "FVS-002", "Fluency-Quality Illusion",
            "Promotional voice with few sourced claims",
            "If this were written in rough notes instead of polished prose, would you still accept the claims?",
        )

    # ── Completeness Illusion (FVS-010) ──
    if coverage.get("coverage_count", 0) >= 4:
        densities = [
            cats[c]["density_per_1kw"]
            for c in covered
            if cats.get(c, {}).get("density_per_1kw", 0) > 0
        ]
        if len(densities) >= 2:
            max_d = max(densities)
            min_d = min(d for d in densities if d > 0)
            if max_d / min_d > 3:
                _add(
                    "FVS-010", "Completeness Illusion",
                    f"Covers {coverage['coverage_count']} dimensions but density is {max_d / min_d:.0f}x skewed",
                    "Does this document MENTION all perspectives or ANALYZE all perspectives?",
                )

    # ── Frame Amplification (FVS-001) ── RETIRED 2026-04-18.
    # Rule removed from production. Retirement rationale:
    # METHODOLOGY.md §2.4.1 and fvs_eval/validation_study/RULE_AUDIT.md §2.1.
    # The v1 signal substrate (coverage/voice/temporal/epistemic density)
    # cannot distinguish FVS-001 target cases from similarly-shaped non-
    # cases: "the rule labels vocabulary-distribution patterns as
    # amplification" (RULE_AUDIT §2.1). The frame concept stands as a
    # library entry; detection is pending richer signals (V4.2 LLM-judge
    # or new signals in framing.py). See test_frame_library.py
    # TestFrameAmplificationRetired for the sentinel test guarding against
    # unintentional resurrection.

    # ── Failure Framing absence (FVS-007) ──
    if "risks" in missing and "uncertainty" in missing:
        unhedged_pct = 100 - sourced_pct
        if unhedged_pct > 60:
            _add(
                "FVS-007", "Failure Framing (absent)",
                "No risk or uncertainty coverage, high unsupported assertion rate",
                "What would have to be true for this analysis to be wrong?",
                pattern_kind="absence_detected",
            )

    # ── Efficiency Frame (FVS-015) ──
    has_efficiency_signal = (
        ("trends" in covered or "causes" in covered)
        and "stakeholders" in missing
        and "uncertainty" in missing
        and voice_type not in ("descriptive", "insufficient")
    )
    if has_efficiency_signal and not has_growth_signal:
        _add(
            "FVS-015", "Efficiency Frame",
            "Optimization metrics present, stakeholder impact and uncertainty absent",
            "Is efficiency the right lens here, or has it been applied by default?",
        )

    # ── Risk Frame (FVS-009, positive detection) ──
    # Signal: risks covered with substantive density (>5/1Kw),
    # analytical voice, and the document also covers uncertainty.
    # This is a POSITIVE frame identification, not a problem.
    # The teaching question acknowledges the risk frame while
    # asking whether it is overweighted.
    risks_density = cats.get("risks", {}).get("density_per_1kw", 0)
    if (
        "risks" in covered
        and risks_density > 5
        and "uncertainty" in covered
        and voice_type == "analytical"
    ):
        _add(
            "FVS-009", "Risk Frame (active)",
            f"Substantive risk analysis ({risks_density}/1Kw) with uncertainty acknowledged",
            "Is the risk analysis proportionate, or is it overweighting worst-case scenarios?",
        )

    # ── Stakeholder Frame (FVS-011, positive detection) ──
    # Signal: stakeholders covered with substantive density, analytical
    # or advisory voice. Mirrors the FVS-009 pattern for positive frame
    # identification. The teaching question asks the substantive-vs-
    # performative distinction the entry names as its honest limit:
    # the detector cannot distinguish specific impact analysis from
    # vacuous "stakeholders include everyone" phrasing.
    stakeholder_density = cats.get("stakeholders", {}).get("density_per_1kw", 0)
    if (
        "stakeholders" in covered
        and stakeholder_density > 5
        and voice_type in ("analytical", "advisory")
    ):
        _add(
            "FVS-011", "Stakeholder Frame (active)",
            f"Stakeholder coverage present ({stakeholder_density}/1Kw) in analytical voice",
            "Is the stakeholder analysis substantive (specific impacts per group, tradeoffs named) or performative (stakeholder groups mentioned without analyzing who wins and who loses)?",
        )

    # ── Uncertainty Frame (FVS-012, positive detection) ──
    # Signal: uncertainty covered with meaningful density. Lower density
    # threshold than risks/stakeholders because uncertainty markers are
    # naturally sparser (hedges and qualifiers live in fewer sentences
    # than risk or stakeholder nouns do). Voice gate excluded: uncertainty
    # coverage is interesting in any voice type, not only analytical.
    uncertainty_density = cats.get("uncertainty", {}).get("density_per_1kw", 0)
    if "uncertainty" in covered and uncertainty_density > 3:
        _add(
            "FVS-012", "Uncertainty Frame (active)",
            f"Uncertainty coverage present ({uncertainty_density}/1Kw)",
            "Is the uncertainty named substantively (ranges, assumptions, expert disagreement) or merely hedged (language softened without specifics)?",
        )

    # ── Temporal Anchoring (FVS-014) ──
    # Signal: one temporal orientation dominates heavily (>70%).
    # The document anchors the reader in one time perspective.
    past_pct = temporal.get("past_pct", 0)
    future_pct = temporal.get("future_pct", 0)
    if past_pct >= 70:
        _add(
            "FVS-014", "Temporal Anchoring (past)",
            f"Past-oriented language in {past_pct}% of sentences",
            "What has changed since this data was current? Is the document presenting historical data as if it were the present?",
            pattern_kind="present_past",
        )
    elif future_pct >= 60:
        _add(
            "FVS-014", "Temporal Anchoring (future)",
            f"Future-oriented language in {future_pct}% of sentences",
            "What is the historical base rate for projections like these? How accurate have similar forecasts been?",
            pattern_kind="present_future",
        )

    # ── Authority by Citation (FVS-016) ──
    # Signal: high sourced_pct (many claims use citation language) in
    # any voice. The original rule only fired on promotional/advisory
    # voice. Adversarial testing (ADV-07) showed that fabricated
    # citations in analytical voice were undetected. Broadened: the
    # rule now fires when sourced_pct >= 50% regardless of voice,
    # because high citation density in any voice warrants the question
    # "can you look up these sources?" The threshold is raised from
    # 40% to 50% to compensate for the broader voice scope.
    if sourced_pct >= 50:
        _add(
            "FVS-016", "Authority by Citation",
            f"High citation density ({sourced_pct}% of claims source-attributed)",
            "Can you look up the specific sources cited? Would the argument survive if the citations were removed?",
        )

    # ── FVS-006, FVS-017, FVS-019 rules DEFERRED ──
    # DETECTION_RULE_AUDIT §4.4, §4.5, §4.6 proposed text-side detection
    # rules for these entries. Implementation attempt on 2026-04-20
    # surfaced three canon conflicts that block unilateral shipping:
    #
    # 1. INDEX.md `Class` column lists all three as `meta-side` with
    #    Detection `n/a`. Adding text-side rules is a library taxonomy
    #    change, which is a curator decision, not a unilateral edit.
    # 2. FVS-019 is additionally marked `absorbed` into FVS-002 in
    #    INDEX.md's v1 publication-state table. A separate text-side
    #    rule would surface FVS-019 as an independent suggestion even
    #    though the library's editorial position is "covered by FVS-002."
    # 3. FVS-017's proposed rule collides with
    #    `test_balanced_document_produces_no_suggestions`, which asserts
    #    that a structurally-balanced analytical document produces zero
    #    suggestions. FVS-017 by design fires on that shape.
    #
    # Resolution requires curator decisions on:
    #   - Class reclassification (meta-side -> text-side) and INDEX.md
    #     update, for whichever entries the curator accepts.
    #   - FVS-019 absorption status vs standalone detection.
    #   - FVS-017 "balanced = false-balance-candidate" design question.
    #
    # The proposal drafts in `DETECTION_RULE_AUDIT_v1.md` §4.4-§4.6
    # remain open for curator review. The regex `IDENTITY_MARKERS_RE`
    # at module top is retained because a future activation is trivial
    # once curator approves the class change; same for the text kwarg
    # on `suggest_frames` below. Neither is load-bearing for any
    # currently active rule.

    return suggestions
