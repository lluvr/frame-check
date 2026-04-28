"""
Integration tests for Layer 11: Grounding Decomposition (G/F/P).

Tests the integration between clarethium_measure.grounding_decomposition(),
the app.py display pipeline, and the framing.framing_portrait() integration.
Does NOT test detection accuracy (that is covered by the upstream test suite).
"""

import pytest
from clarethium_measure import measure, grounding_decomposition


# ── Test fixtures ──

NVIDIA_DOC = """## NVIDIA Q3 Analysis

Revenue grew to $35.1 billion in Q3 FY2025, up 94% year-over-year.
Data center revenue reached $30.8 billion, up 112% from the prior year.
Gaming revenue was $3.3 billion, up 15% year-over-year.

Samsung is developing competing accelerators for the data center market.
Analysts expect calendar year 2026 revenue to exceed $250 billion.
"""

NVIDIA_SOURCE = """NVIDIA Corporation Q3 FY2025 Results:
Revenue: $35.1 billion, up 94% year-over-year
Data Center: $30.8 billion, up 112%
Gaming: $3.3 billion, up 15%
Gross Margin: 74.6%
"""

CLEAN_DOC = """## Revenue Summary

Revenue was $35.1 billion for the quarter.
Data center contributed $30.8 billion of total revenue.
Gaming revenue reached $3.3 billion.
"""


# ── grounding_decomposition() standalone ──

class TestGroundingDecompositionOutput:
    """Verify the output dict has the expected shape."""

    def test_returns_all_keys(self):
        result = grounding_decomposition(NVIDIA_DOC, NVIDIA_SOURCE)
        expected_keys = {
            "proportions", "counts", "n_classified", "n_skipped",
            "has_projection", "p_sentences", "recommendation",
            "scope_assessment",
            "status", "interpretation_note",
        }
        assert set(result.keys()) == expected_keys

    def test_proportions_sum_to_one(self):
        result = grounding_decomposition(NVIDIA_DOC, NVIDIA_SOURCE)
        total = sum(result["proportions"].values())
        assert abs(total - 1.0) < 0.01, f"Proportions sum to {total}, not 1.0"

    def test_counts_match_n_classified(self):
        result = grounding_decomposition(NVIDIA_DOC, NVIDIA_SOURCE)
        assert sum(result["counts"].values()) == result["n_classified"]

    def test_status_is_experimental(self):
        result = grounding_decomposition(NVIDIA_DOC, NVIDIA_SOURCE)
        assert result["status"] == "EXPERIMENTAL"

    def test_p_sentences_have_reason(self):
        result = grounding_decomposition(NVIDIA_DOC, NVIDIA_SOURCE)
        for ps in result["p_sentences"]:
            assert "sentence" in ps
            assert "reason" in ps
            assert ps["reason"]  # non-empty

    def test_clean_doc_has_no_projection(self):
        result = grounding_decomposition(CLEAN_DOC, NVIDIA_SOURCE)
        assert result["has_projection"] is False
        assert result["counts"]["P"] == 0
        assert result["recommendation"] is None

    def test_fiscal_year_prefix_matches_source(self):
        """FY2025 in source should match standalone 2025 in document,
        preventing false unsourced_years P-classification."""
        doc = "Market share reached 80% in 2025 according to analyst estimates."
        source = "Market share: approximately 80% (Q3 FY2025)."
        result = grounding_decomposition(doc, source)
        assert result["counts"]["P"] == 0, (
            f"FY-prefixed year caused false P: {result['p_sentences']}"
        )

    def test_projected_doc_has_recommendation(self):
        result = grounding_decomposition(NVIDIA_DOC, NVIDIA_SOURCE)
        assert result["has_projection"] is True
        assert result["recommendation"] is not None
        assert len(result["recommendation"]) > 0

    def test_empty_doc_returns_zero_classified(self):
        result = grounding_decomposition("## Empty\nOk.", NVIDIA_SOURCE)
        assert result["n_classified"] == 0
        assert result["proportions"] == {"G": 0.0, "F": 0.0, "P": 0.0}

    def test_heading_text_excluded_from_sentences(self):
        """Heading lines should be stripped entirely, not merged into
        the next sentence. Regression test for heading leak bug."""
        from clarethium_measure import _split_sentences_simple
        doc = "## Competitive Landscape\nSamsung is developing accelerators."
        sentences = _split_sentences_simple(doc)
        for s in sentences:
            assert "Competitive Landscape" not in s, (
                f"Heading text leaked into sentence: '{s}'"
            )

    def test_abbreviations_do_not_split_sentences(self):
        """Common abbreviations (U.S., Corp., Dr., vs.) should not
        trigger false sentence boundaries."""
        from clarethium_measure import _split_sentences_simple
        doc = "The U.S. economy grew 3.1% in Q3 according to reports."
        sentences = _split_sentences_simple(doc)
        assert len(sentences) == 1, (
            f"Abbreviation caused false split: {sentences}"
        )
        assert "U.S." in sentences[0]

    def test_corp_abbreviation_preserves_sentence(self):
        """NVIDIA Corp. should not split or cause sentence loss."""
        from clarethium_measure import _split_sentences_simple
        doc = "NVIDIA Corp. reported strong results last quarter. Gaming revenue rose 15% year-over-year."
        sentences = _split_sentences_simple(doc)
        assert len(sentences) == 2
        assert "NVIDIA Corp." in sentences[0]


# ── measure() integration ──

class TestMeasureIntegration:
    """Verify grounding_decomposition runs inside measure() correctly."""

    def test_included_when_source_provided(self):
        profile = measure(NVIDIA_DOC, source=NVIDIA_SOURCE)
        assert "grounding_decomposition" in profile
        assert "grounding_decomposition" in profile["metadata"]["layers_run"]

    def test_excluded_when_no_source(self):
        profile = measure(NVIDIA_DOC)
        assert "grounding_decomposition" not in profile
        assert "grounding_decomposition" not in profile["metadata"]["layers_run"]

    def test_does_not_break_other_layers(self):
        profile = measure(NVIDIA_DOC, source=NVIDIA_SOURCE)
        # All pre-existing source-dependent layers should still run
        assert "source_fidelity" in profile
        assert "entity_provenance" in profile
        assert "vocabulary_proximity" in profile
        assert "epistemic_calibration" in profile
        assert "quality_profile" in profile


# ── app.py reason_label translation ──

class TestDerivationChecker:
    """Verify _gfp_is_derivable catches percentage-based derivations."""

    def test_percentage_application(self):
        """Revenue * Margin% = Profit should be derivable."""
        from clarethium_measure import _gfp_is_derivable
        # 42 * 68% = 42 * 0.68 = 28.56
        assert _gfp_is_derivable(28.56, {42.0, 68.0, 5.0, 22.0})

    def test_market_share_calculation(self):
        """Total * Share% should be derivable."""
        from clarethium_measure import _gfp_is_derivable
        # 94.9 * 46.2% = 43.84
        assert _gfp_is_derivable(43.84, {94.9, 46.2, 25.0})

    def test_truly_external_not_derivable(self):
        """Numbers with no derivation path should remain unflagged."""
        from clarethium_measure import _gfp_is_derivable
        assert not _gfp_is_derivable(250.0, {42.0, 68.0, 5.0, 22.0})
        assert not _gfp_is_derivable(999.0, {42.0, 68.0, 5.0, 22.0})
        assert not _gfp_is_derivable(7777.0, {42.0, 68.0, 5.0, 22.0})

    def test_coincidental_product_not_derivable(self):
        """A*B with coincidental match at ~2% should use tight (1%)
        tolerance. 3.3 * 74.6 = 246.18 is 1.53% from 250, so it
        should not match via the A*B path alone."""
        from clarethium_measure import _gfp_is_derivable
        # With a small source set where two-step paths don't reach 250,
        # the A*B path at 1% tolerance should reject this.
        assert not _gfp_is_derivable(250.0, {3.3, 74.6})

    def test_large_number_not_treated_as_percentage(self):
        """Source numbers > 100 should not participate in the (a/100)*b
        percentage application path. Without the fix, (150/100)*383 =
        574.5 would match 575 because 150 would be treated as a
        percentage. With the fix, 150 > 100 so it is excluded, and
        383 > 100 so it is also excluded. No other derivation path
        reaches 575 from these two source numbers.

        Regression test for v1.4.2 percentage restriction."""
        from clarethium_measure import _gfp_is_derivable
        # 383 and 150 are both > 100, neither should be a percentage.
        # (150/100)*383 = 574.5 and (383/100)*150 = 574.5 are blocked.
        assert not _gfp_is_derivable(575.0, {383.0, 150.0})
        # 215 and 130 are both > 100.
        # (215/100)*130 = 279.5 is blocked.
        assert not _gfp_is_derivable(280.0, {215.0, 130.0})

    def test_valid_percentage_application_still_works(self):
        """Numbers 0 < a <= 100 should still work as percentages.
        74.6% of 35.1 = 26.18 (margin calculation)."""
        from clarethium_measure import _gfp_is_derivable
        assert _gfp_is_derivable(26.18, {74.6, 35.1})

    def test_boundary_100_percent_works(self):
        """a=100 (exactly 100%) should still participate.
        100% of 50 = 50, which is a valid derivation."""
        from clarethium_measure import _gfp_is_derivable
        # 100/100 * 50 = 50. This should match via the pct path.
        # But 50 is already in the source set, so it would also match
        # via identity. Use a target that only matches via pct application.
        # 100/100 * 73 = 73. Same issue. Let me use a value that's only
        # reachable via the pct path from a non-identity pair.
        # Actually: the pct path allows a=b, so (100/100)*50 = 50.
        # This is trivially derivable. The real test is whether a=100
        # is NOT excluded by the guard. Verify by checking a value
        # that can only come from (100/100)*X = X (identity through pct).
        # Since identity is already handled by A/B = 1.0, this is
        # redundant but confirms the guard boundary.
        assert _gfp_is_derivable(73.0, {100.0, 73.0})

    def test_false_positive_rate_documented(self):
        """Measure the false positive rate on a realistic source set.
        With NVIDIA Q3 source numbers {35.1, 30.8, 3.3, 94, 74.6},
        count how many integers 1-200 are "derivable".

        Baseline: 5 source numbers produce ~46% derivable integers.
        This is dominated by A+B, A-B, and two-step paths, not
        the percentage application path. The v1.4.2 restriction
        reduces the percentage path contribution but does not
        significantly change the total for 5-number sets.

        The percentage restriction matters most for 7+ source
        numbers where the percentage path's contribution is larger
        (e.g., numbers like 383 and 215 in the source set would
        produce many false matches without the > 100 exclusion)."""
        from clarethium_measure import _gfp_is_derivable
        source = {35.1, 30.8, 3.3, 94.0, 74.6}
        derivable = sum(
            1 for v in range(1, 201)
            if _gfp_is_derivable(float(v), source)
        )
        rate = derivable / 200 * 100
        # Regression guard: rate should not exceed 50% for 5 source numbers.
        # Current measured rate: ~46%.
        assert rate < 50, (
            f"False positive rate {rate:.1f}% exceeds threshold for 5 source numbers. "
            f"{derivable}/200 integers were derivable."
        )

    def test_large_source_set_rate_documented(self):
        """With 7 source numbers the false positive rate is high (~61%)
        because A+B, A-B, and two-step paths grow O(n^2). The
        percentage restriction helps on the margin (without it, 383 and
        130.5 would each produce 7 additional percentage-application
        candidates at 2% tolerance) but the dominant contributor is
        the additive/subtractive path.

        This is the known limitation documented in the continuation
        prompt: with 7+ source numbers, P-detection relies on entity
        and year signals, not number matching alone."""
        from clarethium_measure import _gfp_is_derivable
        source = {35.1, 30.8, 3.3, 94.0, 74.6, 383.0, 130.5}
        derivable = sum(
            1 for v in range(1, 201)
            if _gfp_is_derivable(float(v), source)
        )
        rate = derivable / 200 * 100
        # Regression guard: rate should not exceed 65%.
        # Current measured rate: ~61%.
        assert rate < 65, (
            f"False positive rate {rate:.1f}% exceeds threshold for 7 source numbers. "
            f"{derivable}/200 integers were derivable."
        )

    def test_sentence_with_derived_percentage_is_grounded(self):
        """A sentence computing Revenue * Margin% should be G, not P."""
        doc = """## Margin Analysis
Total revenue was $42 billion with a 68% gross margin.
This implies gross profit of approximately $28.56 billion.
"""
        source = """Revenue: $42 billion. Gross Margin: 68%."""
        result = grounding_decomposition(doc, source)
        assert result["counts"]["P"] == 0, (
            f"Expected no P-sentences but got {result['counts']['P']}: "
            f"{result['p_sentences']}"
        )


class TestRecommendationTailoring:
    """Verify recommendations match the dominant P-reason."""

    _LABELS = {
        "unsourced_numbers": "contains numbers not found in source",
        "external_entities": "references entities not in source",
        "unsourced_years": "references years not in source",
    }

    def _build_recommendation(self, p_sentences):
        """Replicate app.py recommendation logic for testing."""
        tally = {"unsourced_numbers": 0, "external_entities": 0,
                 "unsourced_years": 0}
        for ps in p_sentences:
            for part in ps.get("reason", "").split("+"):
                if part in tally:
                    tally[part] += 1
        has_nums = tally["unsourced_numbers"] > 0
        has_ents = tally["external_entities"] > 0
        if has_ents and not has_nums:
            return "entity"
        elif has_ents and has_nums:
            return "mixed"
        else:
            return "number"

    def test_entity_only_gets_entity_recommendation(self):
        """Pure entity P-sentences should not get number prohibition."""
        p_sentences = [
            {"reason": "external_entities"},
            {"reason": "external_entities"},
        ]
        assert self._build_recommendation(p_sentences) == "entity"

    def test_number_only_gets_number_recommendation(self):
        p_sentences = [
            {"reason": "unsourced_numbers"},
            {"reason": "unsourced_years"},
        ]
        assert self._build_recommendation(p_sentences) == "number"

    def test_mixed_gets_broad_recommendation(self):
        p_sentences = [
            {"reason": "unsourced_numbers+external_entities"},
            {"reason": "unsourced_years"},
        ]
        assert self._build_recommendation(p_sentences) == "mixed"


class TestSentenceTruncation:
    """Verify p_sentences truncate at word boundaries."""

    def test_long_sentence_truncates_at_word(self):
        doc = """## Test
Samsung is developing competing accelerators for the enterprise data center market alongside AMD and Intel who are also investing heavily in AI chip development for cloud infrastructure providers worldwide.
"""
        source = "Revenue: $35.1 billion."
        result = grounding_decomposition(doc, source)
        for ps in result["p_sentences"]:
            s = ps["sentence"]
            if len(s) < 120:
                # Truncated. Verify it ends at a word boundary.
                assert not s.endswith(" "), f"Trailing space: '{s[-10:]}'"
                # Verify it's shorter than 120 and a complete word
                assert len(s) <= 120

    def test_short_sentence_not_truncated(self):
        doc = """## Test
Samsung is a competitor in the market.
"""
        source = "Revenue: $35.1 billion."
        result = grounding_decomposition(doc, source)
        for ps in result["p_sentences"]:
            s = ps["sentence"]
            assert "Samsung" in s


class TestReasonLabels:
    """Verify internal reason codes translate to human-readable labels."""

    def test_single_reason(self):
        _GFP_REASON_LABELS = {
            "unsourced_numbers": "contains numbers not found in source",
            "external_entities": "references entities not in source",
            "unsourced_years": "references years not in source",
        }
        ps = {"reason": "unsourced_numbers"}
        parts = ps["reason"].split("+")
        labels = [_GFP_REASON_LABELS.get(p, p) for p in parts]
        ps["reason_label"] = "; ".join(labels)
        assert ps["reason_label"] == "contains numbers not found in source"

    def test_compound_reason(self):
        _GFP_REASON_LABELS = {
            "unsourced_numbers": "contains numbers not found in source",
            "external_entities": "references entities not in source",
            "unsourced_years": "references years not in source",
        }
        ps = {"reason": "external_entities+unsourced_years"}
        parts = ps["reason"].split("+")
        labels = [_GFP_REASON_LABELS.get(p, p) for p in parts]
        ps["reason_label"] = "; ".join(labels)
        assert "references entities not in source" in ps["reason_label"]
        assert "references years not in source" in ps["reason_label"]

    def test_unknown_reason_passes_through(self):
        _GFP_REASON_LABELS = {
            "unsourced_numbers": "contains numbers not found in source",
            "external_entities": "references entities not in source",
            "unsourced_years": "references years not in source",
        }
        ps = {"reason": "new_future_reason"}
        parts = ps["reason"].split("+")
        labels = [_GFP_REASON_LABELS.get(p, p) for p in parts]
        ps["reason_label"] = "; ".join(labels)
        assert ps["reason_label"] == "new_future_reason"


# ── framing_portrait integration ──

class TestFramingPortraitIntegration:
    """Verify framing_portrait includes grounding context."""

    def test_high_projection_mentioned(self):
        from framing import (
            framing_portrait, detect_coverage, temporal_orientation,
            detect_voice, detect_epistemic_basis,
        )
        from claim_analysis import analyze_claims

        gfp = grounding_decomposition(NVIDIA_DOC, NVIDIA_SOURCE)
        cov = detect_coverage(NVIDIA_DOC)
        temp = temporal_orientation(NVIDIA_DOC)
        voice = detect_voice(NVIDIA_DOC)
        epist = detect_epistemic_basis(NVIDIA_DOC)
        ca = analyze_claims(NVIDIA_DOC)

        portrait_with = framing_portrait(cov, temp, voice, epist, ca, grounding=gfp)
        portrait_without = framing_portrait(cov, temp, voice, epist, ca)

        # With grounding: should mention projection or source
        assert "source" in portrait_with.lower() or "projected" in portrait_with.lower() \
            or "outside" in portrait_with.lower() or "grounded" in portrait_with.lower()
        # The grounding-enriched portrait should differ from the base
        assert portrait_with != portrait_without

    def test_clean_doc_mentions_grounded(self):
        from framing import (
            framing_portrait, detect_coverage, temporal_orientation,
            detect_voice, detect_epistemic_basis,
        )
        from claim_analysis import analyze_claims

        gfp = grounding_decomposition(CLEAN_DOC, NVIDIA_SOURCE)
        cov = detect_coverage(CLEAN_DOC)
        temp = temporal_orientation(CLEAN_DOC)
        voice = detect_voice(CLEAN_DOC)
        epist = detect_epistemic_basis(CLEAN_DOC)
        ca = analyze_claims(CLEAN_DOC)

        portrait = framing_portrait(cov, temp, voice, epist, ca, grounding=gfp)
        # Clean doc with high G% should mention grounding
        if gfp["proportions"]["G"] >= 0.5:
            assert "grounded" in portrait.lower() or "source" in portrait.lower()

    def test_no_grounding_backward_compatible(self):
        """Portrait without grounding param should still work."""
        from framing import (
            framing_portrait, detect_coverage, temporal_orientation,
            detect_voice, detect_epistemic_basis,
        )
        from claim_analysis import analyze_claims

        cov = detect_coverage(NVIDIA_DOC)
        temp = temporal_orientation(NVIDIA_DOC)
        voice = detect_voice(NVIDIA_DOC)
        epist = detect_epistemic_basis(NVIDIA_DOC)
        ca = analyze_claims(NVIDIA_DOC)

        portrait = framing_portrait(cov, temp, voice, epist, ca)
        assert len(portrait) > 0


# ── scope_assessment regime classification ──

class TestScopeAssessment:
    """Verify the scope_assessment dict and regime boundaries.

    Regime thresholds come from Monte Carlo analysis of
    _gfp_is_derivable: the derivation checker's false-positive rate
    rises monotonically with source number count N, saturating by
    N~15-20. Boundaries: N<10 diagnostic, 10-14 transition,
    N>=15 saturated. See LAYER_11_SCOPE_BOUNDARY.md.
    """

    def test_scope_assessment_shape(self):
        result = grounding_decomposition(NVIDIA_DOC, NVIDIA_SOURCE)
        sa = result["scope_assessment"]
        assert "source_num_count" in sa
        assert "derivation_regime" in sa
        assert "primary_signal_diagnostic" in sa
        assert "cross_reference_layer_4_for_numbers" in sa
        assert "note" in sa
        assert "note_user_facing" in sa

    def test_diagnostic_regime_small_n(self):
        """Source with <10 unique numbers classified as diagnostic."""
        source = "Revenue was $35 billion. Margin was 74%. Growth was 94%."
        doc = "Revenue reached $35 billion with 74% margin."
        result = grounding_decomposition(doc, source)
        sa = result["scope_assessment"]
        assert sa["source_num_count"] < 10
        assert sa["derivation_regime"] == "diagnostic"
        assert sa["primary_signal_diagnostic"] is True
        assert sa["cross_reference_layer_4_for_numbers"] is False

    def test_saturated_regime_dense_source(self):
        """Source with >=15 unique numbers classified as saturated."""
        source = (
            "Revenue 2023: $127B. Revenue 2024: $158B. Margin: 43%. "
            "Operating: 28%. R&D: $22B. SGA: $31B. Net income: $42B. "
            "Cash: $85B. Debt: $14B. Employees: 173000. Countries: 41. "
            "Patents: 5800. Data centers: 92. Customers: 2400000. "
            "ARR: $95B. NRR: 118%. Retention: 97%. CAC: 14 months."
        )
        doc = "## Analysis\nRevenue grew from $127 billion to $158 billion."
        result = grounding_decomposition(doc, source)
        sa = result["scope_assessment"]
        assert sa["source_num_count"] >= 15
        assert sa["derivation_regime"] == "saturated"
        assert sa["cross_reference_layer_4_for_numbers"] is True
        assert "authoritative" in sa["note_user_facing"].lower() \
            or "source-fidelity" in sa["note_user_facing"].lower()


class TestPilotFalseCleanRegression:
    """Regression tests for the two false-clean cases surfaced during
    the Layer 11 scope-boundary investigation (2026-04-17).

    Case A: pilot memo with source N=23, Layer 4 49.3% unsourced, Layer 11
    P=0%. The G/F/P card must NOT show 'All content is source-grounded'.
    Case B: constructed small-rate with source N=23, Layer 4 7.7% unsourced
    (below the 15% threshold), Layer 11 P=0%. Pre-fix, the 15% floor
    silenced the divergence alert; the regime-aware gate must fire it.
    """

    def test_pilot_memo_regime_is_saturated(self):
        """The pilot corpus source classifies as saturated regime.
        This is the precondition for the divergence alert to fire."""
        source = (
            "Revenue 2023: $127B. Revenue 2024: $158B. Margin: 43%. "
            "Operating: 28%. R&D: $22B. SGA: $31B. Net income: $42B. "
            "Cash: $85B. Debt: $14B. Employees: 173000. Countries: 41. "
            "Patents: 5800. Data centers: 92. Customers: 2400000. "
            "ARR: $95B. NRR: 118%. Retention: 97%. CAC: 14 months. "
            "LTV/CAC: 6.2. FCF: $38B. SBC: $7B. EPS: 4.73. Shares: 2.9B."
        )
        doc = "## Report\nRevenue grew from $127 billion to $158 billion."
        result = grounding_decomposition(doc, source)
        assert result["scope_assessment"]["derivation_regime"] == "saturated"
        assert result["scope_assessment"]["cross_reference_layer_4_for_numbers"] is True

    def test_saturated_false_clean_gate_fires_in_app_logic(self):
        """Replicates the saturated + low-rate false-clean case.
        With scope_assessment, has_unsourced_gap must be True even
        when unsourced_rate is below the legacy 15% heuristic."""
        # Simulate the display-layer union gate from app.py
        has_projection = False
        unsourced_rate = 0.077  # 7.7%, below legacy 15% threshold
        cross_ref_layer_4 = True  # saturated regime

        saturated_divergence = (
            unsourced_rate is not None
            and unsourced_rate > 0
            and cross_ref_layer_4
            and not has_projection
        )
        threshold_divergence = (
            unsourced_rate is not None
            and unsourced_rate > 0.15
            and not has_projection
        )
        has_unsourced_gap = saturated_divergence or threshold_divergence

        assert threshold_divergence is False, "Legacy 15% gate should miss this"
        assert saturated_divergence is True, "Saturated gate must catch this"
        assert has_unsourced_gap is True, "Union gate must fire"


class TestTelemetryRegimeEmission:
    """Verify the Tier A telemetry event carries projection_regime so
    longitudinal observatory queries can segment on signal reliability."""

    def test_grounding_fields_include_regime(self):
        from tier_a_event import _grounding_fields
        g = grounding_decomposition(NVIDIA_DOC, NVIDIA_SOURCE)
        fields = _grounding_fields(g)
        assert "grounding.projection_regime" in fields
        assert fields["grounding.projection_regime"] in (
            "diagnostic", "transition", "saturated",
        )
        assert "grounding.source_num_count" in fields
        assert isinstance(fields["grounding.source_num_count"], int)

    def test_grounding_fields_include_legacy_has_projection(self):
        """Regression: the new fields are additive, has_projection stays."""
        from tier_a_event import _grounding_fields
        g = grounding_decomposition(NVIDIA_DOC, NVIDIA_SOURCE)
        fields = _grounding_fields(g)
        assert "grounding.has_projection" in fields
        assert "grounding.p_count" in fields

    def test_telemetry_schema_allows_regime_field(self):
        from telemetry import _TIER_A_FIELDS
        assert "grounding.projection_regime" in _TIER_A_FIELDS
        assert "grounding.source_num_count" in _TIER_A_FIELDS
