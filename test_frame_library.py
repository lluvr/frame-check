"""Tests for frame_library.suggest_frames.

Verifies that the library suggestion engine produces the expected
FVS entries for known framing patterns. Each test creates a specific
framing analysis output (coverage, voice, temporal, epistemic) and
asserts that the correct library entries are suggested.
"""

from frame_library import suggest_frames


def _coverage(covered, missing, densities=None):
    """Build a coverage dict matching framing.detect_coverage output."""
    all_cats = {"causes", "risks", "stakeholders", "trends", "uncertainty"}
    cats = {}
    for c in all_cats:
        d = (densities or {}).get(c, 3.0 if c in covered else 0.0)
        cats[c] = {
            "count": int(d * 2) if d > 0 else 0,
            "density_per_1kw": d,
            "covered": c in covered,
        }
    return {
        "categories": cats,
        "covered": sorted(covered),
        "missing": sorted(missing),
        "coverage_count": len(covered),
        "total_categories": 5,
    }


def _voice(voice_type):
    return {"voice": voice_type, "you_pct": 0, "we_pct": 0,
            "imperative_count": 0, "total_sentences": 10}


def _temporal():
    return {"past_pct": 20, "present_pct": 50, "future_pct": 30,
            "dominant": "present"}


def _epistemic(sourced_pct=50):
    return {"sourced_pct": sourced_pct, "sourced": 5,
            "numeric_sentences": 10, "unsupported_numeric": 5,
            "total_sentences": 20}


class TestGrowthFrame:

    # Move D-FVS-008 (2026-04-27): the structural rule now requires
    # growth-context vocabulary in `text` alongside the structural signal.
    # These tests pass minimal growth-vocab text (revenue + market growth)
    # so the structural rule still fires; the test assertions remain
    # focused on the structural conditions.
    GROWTH_VOCAB_TEXT = (
        "The company's revenue grew by 35 percent year over year. "
        "Market expansion accelerated through new customer adoption."
    )

    def test_trends_covered_risks_missing_analytical(self):
        cov = _coverage({"trends", "causes"}, {"risks", "stakeholders", "uncertainty"})
        result = suggest_frames(
            cov, _voice("analytical"), _temporal(), _epistemic(),
            text=self.GROWTH_VOCAB_TEXT,
        )
        ids = [s["fvs_id"] for s in result]
        assert "FVS-008" in ids, f"Growth Frame should be suggested, got {ids}"

    def test_suggestion_includes_definition_and_url(self):
        cov = _coverage({"trends", "causes"}, {"risks", "stakeholders", "uncertainty"})
        result = suggest_frames(
            cov, _voice("analytical"), _temporal(), _epistemic(),
            text=self.GROWTH_VOCAB_TEXT,
        )
        growth = [s for s in result if s["fvs_id"] == "FVS-008"][0]
        assert growth.get("definition"), "Growth Frame suggestion should include a definition"
        assert "default" in growth["definition"].lower(), "Definition should describe the frame"
        assert growth.get("url") == "/corpus/library/FVS-008.html", (
            f"Suggestion should link to corpus surface, got {growth.get('url')}"
        )

    def test_not_suggested_when_risks_present(self):
        cov = _coverage({"trends", "risks"}, {"causes", "stakeholders", "uncertainty"})
        result = suggest_frames(
            cov, _voice("analytical"), _temporal(), _epistemic(),
            text=self.GROWTH_VOCAB_TEXT,
        )
        ids = [s["fvs_id"] for s in result]
        assert "FVS-008" not in ids, "Growth Frame should NOT be suggested when risks are covered"

    def test_not_suggested_for_descriptive_voice(self):
        cov = _coverage({"trends"}, {"risks", "causes", "stakeholders", "uncertainty"})
        result = suggest_frames(
            cov, _voice("descriptive"), _temporal(), _epistemic(),
            text=self.GROWTH_VOCAB_TEXT,
        )
        ids = [s["fvs_id"] for s in result]
        assert "FVS-008" not in ids, "Growth Frame should NOT be suggested for descriptive voice"

    def test_not_suggested_without_growth_vocabulary(self):
        """Move D-FVS-008 content discriminator: structural signal alone
        is no longer sufficient. A document with trends/causes covered +
        risks missing + analytical voice but NO business-growth vocabulary
        (e.g., literature review using 'scaling laws', institutional
        analysis using 'evolution') must NOT trigger FVS-008. Cross-domain
        evidence: epistemic_via_paraphrased_sourcing/audit.md and
        cross_domain_stakeholder/audit.md.
        """
        cov = _coverage({"trends", "causes"}, {"risks", "stakeholders", "uncertainty"})
        non_growth_text = (
            "The field has accumulated a body of small-scale demonstrations. "
            "Scaling laws apply to interpretability difficulty as much as to "
            "capability. The architecture continues to operate as designed, "
            "with subsequent decisions shaped by institutional ambiguity."
        )
        result = suggest_frames(
            cov, _voice("analytical"), _temporal(), _epistemic(),
            text=non_growth_text,
        )
        ids = [s["fvs_id"] for s in result]
        assert "FVS-008" not in ids, (
            f"Growth Frame should NOT fire on non-business-growth content "
            f"despite trends covered + risks missing + analytical voice; got {ids}"
        )

    def test_not_suggested_when_text_is_none(self):
        """Move D-FVS-008: when no text is passed, the discriminator cannot
        be evaluated, so FVS-008 falls through (consistent with the
        function's standing 'text-dependent rules don't fire when text is
        None' discipline). Pinned so callers know they must pass text to
        get FVS-008 detection.
        """
        cov = _coverage({"trends", "causes"}, {"risks", "stakeholders", "uncertainty"})
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-008" not in ids, (
            f"Growth Frame should NOT fire when text is None (discriminator "
            f"cannot be evaluated); got {ids}"
        )


class TestFluencyQualityIllusion:

    def test_promotional_low_sourcing(self):
        cov = _coverage({"trends"}, {"risks", "causes", "stakeholders", "uncertainty"})
        result = suggest_frames(cov, _voice("promotional"), _temporal(), _epistemic(sourced_pct=15))
        ids = [s["fvs_id"] for s in result]
        assert "FVS-002" in ids, f"Fluency-Quality should be suggested, got {ids}"

    def test_not_suggested_high_sourcing(self):
        cov = _coverage({"trends"}, {"risks", "causes", "stakeholders", "uncertainty"})
        result = suggest_frames(cov, _voice("promotional"), _temporal(), _epistemic(sourced_pct=60))
        ids = [s["fvs_id"] for s in result]
        assert "FVS-002" not in ids, "Fluency-Quality should NOT be suggested with high sourcing"


class TestCompletenessIllusion:

    def test_high_coverage_skewed_density(self):
        densities = {"trends": 12.0, "causes": 8.0, "risks": 1.5, "stakeholders": 1.0}
        cov = _coverage(
            {"trends", "causes", "risks", "stakeholders"},
            {"uncertainty"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-010" in ids, f"Completeness Illusion should be suggested, got {ids}"

    def test_not_suggested_balanced_density(self):
        densities = {"trends": 4.0, "causes": 3.5, "risks": 3.0, "stakeholders": 3.2}
        cov = _coverage(
            {"trends", "causes", "risks", "stakeholders"},
            {"uncertainty"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-010" not in ids, "Completeness Illusion should NOT be suggested with balanced density"


class TestFrameAmplificationRetired:
    """FVS-001 Frame Amplification v1 detection rule retired 2026-04-18.

    Retirement rationale: METHODOLOGY.md §2.4.1 and
    fvs_eval/validation_study/RULE_AUDIT.md §2.1. The v1 signal substrate
    cannot distinguish FVS-001 target cases from similarly-shaped non-
    cases. The sentinel below asserts the rule does NOT fire on the
    canonical v1 trigger input (high single-dimension density + three
    missing categories). Unintentional resurrection of the rule would
    fail this test.
    """

    def test_retired_rule_does_not_fire(self):
        densities = {"trends": 15.0}
        cov = _coverage(
            {"trends"},
            {"causes", "risks", "stakeholders", "uncertainty"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-001" not in ids, (
            f"FVS-001 v1 rule retired; must not fire. Got {ids}. "
            f"If this test fails, the rule block in frame_library.py "
            f"suggest_frames was re-introduced."
        )


class TestFailureFramingAbsent:

    def test_no_risks_no_uncertainty_low_sourcing(self):
        cov = _coverage({"trends", "causes"}, {"risks", "uncertainty", "stakeholders"})
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic(sourced_pct=20))
        ids = [s["fvs_id"] for s in result]
        assert "FVS-007" in ids, f"Failure Framing should be suggested, got {ids}"

    def test_not_suggested_when_risks_present(self):
        cov = _coverage({"trends", "risks"}, {"causes", "stakeholders", "uncertainty"})
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic(sourced_pct=20))
        ids = [s["fvs_id"] for s in result]
        assert "FVS-007" not in ids, "Failure Framing should NOT be suggested when risks are covered"


class TestRiskFrame:

    def test_substantive_risk_with_uncertainty(self):
        densities = {"risks": 8.0, "uncertainty": 5.0, "trends": 3.0}
        cov = _coverage(
            {"risks", "uncertainty", "trends"},
            {"causes", "stakeholders"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-009" in ids, f"Risk Frame should be suggested, got {ids}"

    def test_not_suggested_promotional_voice(self):
        densities = {"risks": 8.0, "uncertainty": 5.0, "trends": 3.0}
        cov = _coverage(
            {"risks", "uncertainty", "trends"},
            {"causes", "stakeholders"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("promotional"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-009" not in ids, "Risk Frame should NOT fire for promotional voice"

    def test_not_suggested_low_risk_density(self):
        densities = {"risks": 2.0, "uncertainty": 3.0}
        cov = _coverage(
            {"risks", "uncertainty"},
            {"causes", "stakeholders", "trends"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-009" not in ids, "Risk Frame should NOT fire at low density"


class TestStakeholderFrame:
    """FVS-011 positive detection. Fires when stakeholders are covered
    with substantive density in an analytical or advisory voice. The
    pattern mirrors FVS-009 Risk Frame (active); the teaching question
    asks the substantive-vs-performative distinction that the entry's
    own 'honest limits' section names."""

    def test_substantive_stakeholder_analytical_voice(self):
        densities = {"stakeholders": 8.0, "risks": 4.0, "trends": 3.0}
        cov = _coverage(
            {"stakeholders", "risks", "trends"},
            {"causes", "uncertainty"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-011" in ids, f"Stakeholder Frame should be suggested, got {ids}"

    def test_substantive_stakeholder_advisory_voice(self):
        densities = {"stakeholders": 7.0, "trends": 3.0}
        cov = _coverage(
            {"stakeholders", "trends"},
            {"causes", "risks", "uncertainty"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("advisory"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-011" in ids, f"Stakeholder Frame should fire in advisory voice, got {ids}"

    def test_not_suggested_promotional_voice(self):
        densities = {"stakeholders": 8.0, "trends": 3.0}
        cov = _coverage(
            {"stakeholders", "trends"},
            {"causes", "risks", "uncertainty"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("promotional"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-011" not in ids, (
            "Stakeholder Frame should NOT fire in promotional voice; "
            "promotional use of stakeholder language is typically selling, "
            "not analysis"
        )

    def test_not_suggested_low_density(self):
        """Low-density stakeholder mention is performative, not substantive.
        Honoring the entry's honest-limits note: a single 'stakeholders
        include everyone' mention should not trigger the frame."""
        densities = {"stakeholders": 2.5, "trends": 4.0}
        cov = _coverage(
            {"stakeholders", "trends"},
            {"causes", "risks", "uncertainty"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-011" not in ids, "Stakeholder Frame should NOT fire at low density"


class TestUncertaintyFrame:
    """FVS-012 positive detection. Fires when uncertainty is covered
    with meaningful density. Density threshold is lower than risks
    because uncertainty markers (hedges, ranges, qualifiers) are
    naturally sparser than risk nouns."""

    def test_substantive_uncertainty_any_voice(self):
        densities = {"uncertainty": 5.0, "trends": 3.0}
        cov = _coverage(
            {"uncertainty", "trends"},
            {"causes", "risks", "stakeholders"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-012" in ids, f"Uncertainty Frame should be suggested, got {ids}"

    def test_fires_in_descriptive_voice_too(self):
        """Uncertainty framing is interesting regardless of voice type,
        unlike stakeholder framing which we gate on analytical/advisory.
        Pin that design choice."""
        densities = {"uncertainty": 5.0, "trends": 3.0}
        cov = _coverage(
            {"uncertainty", "trends"},
            {"causes", "risks", "stakeholders"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("descriptive"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-012" in ids, (
            f"Uncertainty Frame should fire regardless of voice, got {ids}"
        )

    def test_not_suggested_low_density(self):
        densities = {"uncertainty": 1.5, "trends": 4.0}
        cov = _coverage(
            {"uncertainty", "trends"},
            {"causes", "risks", "stakeholders"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-012" not in ids, "Uncertainty Frame should NOT fire at low density"

    def test_not_suggested_when_uncertainty_missing(self):
        densities = {"trends": 4.0}
        cov = _coverage(
            {"trends"},
            {"causes", "risks", "stakeholders", "uncertainty"},
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-012" not in ids, (
            "Uncertainty Frame requires uncertainty in covered categories"
        )


class TestTemporalAnchoring:

    def test_past_dominant(self):
        cov = _coverage({"trends"}, {"risks", "causes", "stakeholders", "uncertainty"})
        temp = {"past_pct": 75, "present_pct": 20, "future_pct": 5, "dominant": "past"}
        result = suggest_frames(cov, _voice("analytical"), temp, _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-014" in ids, f"Temporal Anchoring (past) should be suggested, got {ids}"

    def test_future_dominant(self):
        cov = _coverage({"trends"}, {"risks", "causes", "stakeholders", "uncertainty"})
        temp = {"past_pct": 10, "present_pct": 25, "future_pct": 65, "dominant": "future"}
        result = suggest_frames(cov, _voice("analytical"), temp, _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-014" in ids, f"Temporal Anchoring (future) should be suggested, got {ids}"

    def test_not_suggested_balanced(self):
        cov = _coverage({"trends"}, {"risks", "causes", "stakeholders", "uncertainty"})
        temp = {"past_pct": 35, "present_pct": 40, "future_pct": 25, "dominant": "present"}
        result = suggest_frames(cov, _voice("analytical"), temp, _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-014" not in ids, "Temporal Anchoring should NOT be suggested with balanced temporal"


class TestAuthorityByCitation:

    def test_high_sourcing_promotional(self):
        cov = _coverage({"trends"}, {"risks", "causes", "stakeholders", "uncertainty"})
        result = suggest_frames(cov, _voice("promotional"), _temporal(), _epistemic(sourced_pct=50))
        ids = [s["fvs_id"] for s in result]
        assert "FVS-016" in ids, f"Authority by Citation should be suggested, got {ids}"

    def test_not_suggested_low_sourcing(self):
        cov = _coverage({"trends"}, {"risks", "causes", "stakeholders", "uncertainty"})
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic(sourced_pct=30))
        ids = [s["fvs_id"] for s in result]
        assert "FVS-016" not in ids, "Authority by Citation should NOT be suggested when sourced_pct < 50%"


class TestEfficiencyFrame:

    def test_optimization_without_stakeholders_or_uncertainty(self):
        cov = _coverage({"trends", "causes"}, {"stakeholders", "uncertainty", "risks"})
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-015" in ids or "FVS-008" in ids, (
            f"Efficiency or Growth Frame should be suggested, got {ids}"
        )

    def test_not_suggested_when_stakeholders_present(self):
        cov = _coverage({"trends", "causes", "stakeholders"}, {"risks", "uncertainty"})
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-015" not in ids, "Efficiency Frame should NOT be suggested when stakeholders are covered"


class TestDeferredRulesDoNotFire:
    """Canon-conflict guard: FVS-006, FVS-017, FVS-019 are classified
    `meta-side | n/a` in `data/frame_library/INDEX.md`. A prior
    implementation attempt on 2026-04-20 added text-side rules that
    contradicted the library taxonomy; the rules were reverted pending
    curator approval of class reclassification per
    `DETECTION_RULE_AUDIT_v1.md` §10.

    These tests pin the reverted state so a future re-introduction
    without coordinated INDEX.md update is caught immediately.
    """

    def test_fvs006_does_not_fire_on_identity_dense_text(self):
        text = (
            "Speaking as an expert in semiconductor policy, the market "
            "dynamics favor consolidation. From the perspective of an "
            "analyst, the numbers support restructuring. In my role as "
            "a strategist, I see the same patterns."
        )
        cov = _coverage({"trends"}, {"risks", "stakeholders", "uncertainty", "causes"})
        result = suggest_frames(
            cov, _voice("analytical"), _temporal(), _epistemic(), text=text,
        )
        ids = [s["fvs_id"] for s in result]
        assert "FVS-006" not in ids, (
            f"FVS-006 must not fire: the entry is meta-side per INDEX.md "
            f"and a text-side rule would contradict canon without curator "
            f"approval. Got {ids}. See DETECTION_RULE_AUDIT §10 and the "
            f"frame_library.py deferral comment."
        )

    def test_fvs019_does_not_fire_on_coherence_conditions(self):
        densities = {"trends": 7.5, "causes": 3.5, "risks": 0.0,
                     "stakeholders": 2.0, "uncertainty": 0.8}
        cov = _coverage(
            {"trends", "causes", "stakeholders", "uncertainty"},
            {"risks"},
            densities=densities,
        )
        voice = {"voice": "analytical", "you_pct": 0, "we_pct": 0,
                 "imperative_count": 0, "total_sentences": 15}
        result = suggest_frames(cov, voice, _temporal(), _epistemic())
        ids = [s["fvs_id"] for s in result]
        assert "FVS-019" not in ids, (
            f"FVS-019 must not fire: entry is meta-side per INDEX.md and "
            f"additionally marked 'absorbed' into FVS-002 in the v1 "
            f"publication-state table. Got {ids}."
        )

    def test_fvs017_does_not_fire_on_balanced_analytical(self):
        densities = {"trends": 4.0, "causes": 3.5, "risks": 3.0,
                     "stakeholders": 3.2, "uncertainty": 2.8}
        cov = _coverage(
            {"trends", "causes", "risks", "stakeholders", "uncertainty"},
            set(),
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(),
                                _epistemic(sourced_pct=45))
        ids = [s["fvs_id"] for s in result]
        assert "FVS-017" not in ids, (
            f"FVS-017 must not fire: entry is meta-side per INDEX.md and "
            f"the proposed rule would collide with "
            f"test_balanced_document_produces_no_suggestions. Got {ids}."
        )


class TestNoSuggestions:

    def test_balanced_document_produces_no_suggestions(self):
        densities = {"trends": 4.0, "causes": 3.5, "risks": 3.0,
                     "stakeholders": 3.2, "uncertainty": 2.8}
        cov = _coverage(
            {"trends", "causes", "risks", "stakeholders", "uncertainty"},
            set(),
            densities=densities,
        )
        result = suggest_frames(cov, _voice("analytical"), _temporal(), _epistemic(sourced_pct=45))
        assert len(result) == 0, f"Balanced document should produce no suggestions, got {[s['fvs_id'] for s in result]}"


# ================================================================
# End-to-end detection: real text through full pipeline
# ================================================================

from framing import detect_coverage, detect_voice, temporal_orientation, detect_epistemic_basis


def _detect_frames(text):
    """Run the full detection pipeline and return suggested FVS IDs."""
    cov = detect_coverage(text)
    voice = detect_voice(text)
    temp = temporal_orientation(text)
    epist = detect_epistemic_basis(text)
    suggestions = suggest_frames(cov, voice, temp, epist, text=text)
    return [s["fvs_id"] for s in suggestions]


class TestEndToEndGrowthDetection:
    """Growth-framed text should trigger FVS-008."""

    GROWTH_TEXT = """\
## AI Market Analysis

The global AI market reached $196 billion in 2023, representing 50% \
year-over-year growth. Enterprise AI adoption accelerated with 73% of \
companies deploying at least one AI application. Investment in AI \
startups exceeded $50 billion for the third consecutive year. \
Cloud computing providers expanded their AI infrastructure spending \
by 40%, signaling sustained demand for AI compute resources. \
The semiconductor industry for AI chips grew 35% as NVIDIA, AMD, \
and custom silicon makers competed for market share. \
Revenue from generative AI services more than doubled, reaching \
$12 billion in annual recurring revenue across major providers.
"""

    def test_growth_frame_fires(self):
        ids = _detect_frames(self.GROWTH_TEXT)
        assert "FVS-008" in ids, f"Growth text should trigger Growth Frame, got {ids}"

    def test_growth_text_does_not_trigger_risk(self):
        ids = _detect_frames(self.GROWTH_TEXT)
        assert "FVS-009" not in ids, f"Growth text should not trigger Risk Frame, got {ids}"


class TestEndToEndRiskDetection:
    """Risk-framed text should trigger FVS-009 when analytical."""

    RISK_TEXT = """\
## AI Market Risk Assessment

The AI market reached $196 billion in 2023, but the growth rate is \
historically unsustainable beyond 2-3 years. Investment concentration \
risk is elevated: if enterprise ROI fails to materialize at scale, \
the $50 billion annual startup funding could collapse rapidly. \
Data quality risks threaten model reliability across healthcare \
and financial applications. Regulatory uncertainty in the EU and \
US creates compliance exposure for firms building on proprietary \
models. Supply chain vulnerabilities in chip manufacturing remain \
acute, with TSMC concentration representing a single point of \
failure. The possibility of an AI investment bubble cannot be \
ruled out given historical parallels with prior technology cycles. \
Workforce displacement risks are poorly understood and may trigger \
political backlash that constrains adoption.
"""

    def test_risk_text_does_not_trigger_growth(self):
        """Risk text should not trigger FVS-008."""
        ids = _detect_frames(self.RISK_TEXT)
        assert "FVS-008" not in ids, (
            f"Risk text should NOT trigger Growth Frame, got {ids}"
        )

    def test_risk_text_does_not_trigger_fvs_001(self):
        """Risk text must NOT trigger FVS-001 (Frame Amplification).

        Historical note: the v1 rule fired on this text via the high
        density + missing categories signature. That firing was the
        exact false-positive pattern documented in
        fvs_eval/validation_study/RULE_AUDIT.md §2.1 and addressed by
        the 2026-04-18 retirement: vocabulary concentration is not the
        same signal as within-session sophistication growth (the frame's
        actual definition per FVS-001 entry).

        With the rule retired, no frame in the current v1 rule set fires
        on this text. That is consistent with the retirement rationale
        and is the honest post-retirement behavior.
        """
        ids = _detect_frames(self.RISK_TEXT)
        assert "FVS-001" not in ids, (
            f"FVS-001 must not fire (rule retired). Got {ids}."
        )
        assert "FVS-008" not in ids, (
            f"Risk text must not trigger Growth Frame. Got {ids}."
        )


class TestEndToEndBalancedDetection:
    """Balanced text covering multiple perspectives should produce
    fewer or no suggestions."""

    BALANCED_TEXT = """\
## Semaglutide Clinical Review

Semaglutide demonstrated 15% mean weight loss at 68 weeks in the \
STEP 1 trial involving 1,961 participants. Common side effects \
included nausea (44%), diarrhea (30%), and vomiting (24%), with \
discontinuation rates reaching 17% due to gastrointestinal events. \
The SELECT trial showed a 20% reduction in major adverse cardiovascular \
events, suggesting benefits beyond weight management. However, \
long-term safety data remains limited to 2-3 years of follow-up. \
Cost barriers are significant: annual treatment exceeds $10,000 \
without insurance, limiting access for lower-income patients who \
may benefit most. Novo Nordisk faces supply constraints that have \
delayed access in multiple markets. The FDA approved semaglutide \
for chronic weight management in June 2021.
"""

    def test_balanced_text_no_growth_frame(self):
        ids = _detect_frames(self.BALANCED_TEXT)
        assert "FVS-008" not in ids, (
            f"Balanced clinical text should not trigger Growth Frame, got {ids}"
        )

    def test_balanced_text_fewer_suggestions(self):
        """Balanced text should produce fewer suggestions than
        growth-framed text."""
        growth_text = TestEndToEndGrowthDetection.GROWTH_TEXT
        growth_ids = _detect_frames(growth_text)
        balanced_ids = _detect_frames(self.BALANCED_TEXT)
        assert len(balanced_ids) <= len(growth_ids), (
            f"Balanced ({len(balanced_ids)} suggestions) should have "
            f"<= growth ({len(growth_ids)} suggestions)"
        )


class TestEndToEndTemporalAnchoring:
    """Future-heavy text should trigger FVS-014."""

    FUTURE_TEXT = """\
## Market Projections 2030

By 2030, the quantum computing market is projected to reach $125 \
billion. Experts predict that quantum advantage will be achieved \
for drug discovery by 2028. The industry will generate over 500,000 \
new jobs by the end of the decade. Investment in quantum startups \
is expected to exceed $30 billion annually by 2027. Government \
spending on quantum research will double over the next five years. \
Analysts forecast that 40% of Fortune 500 companies will have \
quantum computing programs by 2029. The transition to quantum-safe \
cryptography will require an estimated $50 billion in infrastructure \
upgrades over the coming decade.
"""

    def test_temporal_anchoring_fires(self):
        ids = _detect_frames(self.FUTURE_TEXT)
        assert "FVS-014" in ids, (
            f"Future-heavy text should trigger Temporal Anchoring, got {ids}"
        )


class TestEndToEndShortDocument:
    """Documents under 5 sentences should produce no suggestions."""

    SHORT_TEXT = """\
## Brief Note

Revenue grew 10% this quarter. Costs remained stable.
"""

    def test_short_document_no_suggestions(self):
        ids = _detect_frames(self.SHORT_TEXT)
        assert len(ids) == 0, (
            f"Short document should produce no suggestions, got {ids}"
        )
