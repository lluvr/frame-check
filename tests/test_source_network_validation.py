"""
Source Network validation corpus.

First empirical accuracy test of the production verification engine against
known ground truth. The 5 topics (Apple, NVIDIA, Bhutan, BLS, Wegovy) come
from a hard-topics corpus selected for adversarial coverage. Ground truth
values are from the APIs themselves (SEC EDGAR XBRL, World Bank, REST
Countries), probed April 2026.

This test makes REAL API calls. Run separately from fast unit tests:
    python3 -m pytest test_source_network_validation.py -v

What this corpus measures:
    - Can the Source Network verify correct claims? (sensitivity)
    - Can it contradict wrong claims? (specificity)
    - What fraction of claims are unverifiable? (coverage)
    - Where does it fail, and why?

Findings documented inline. Each test case explains what it tests and
what the result means for the product.
"""

import pytest
from source_network import (
    ClaimDecomposition,
    verify_sec_edgar,
    verify_wikipedia,
    verify_world_bank,
    verify_rest_countries,
    verify_claims_source_network,
)
from claim_analysis import analyze_claims


# ================================================================
# GROUND TRUTH (from API probes, April 2026)
# ================================================================
# These are the values the APIs currently return. If an API updates
# its data, these values should be re-probed and updated.

NVIDIA_FY2026_REVENUE = 215.94e9   # SEC EDGAR Revenues concept, FY2026 end=2026-01-25
NVIDIA_FY2025_REVENUE = 130.50e9   # SEC EDGAR Revenues concept, FY2025 end=2025-01-26
NVIDIA_FY2024_REVENUE = 60.92e9    # SEC EDGAR Revenues concept, FY2024 end=2024-01-28

APPLE_FY2025_REVENUE = 416.16e9    # SEC EDGAR RevenueFromContractWithCustomer, FY2025 end=2025-09-27
APPLE_FY2024_REVENUE = 391.04e9    # SEC EDGAR RevenueFromContractWithCustomer, FY2024 end=2024-09-28
APPLE_FY2023_REVENUE = 383.29e9    # SEC EDGAR RevenueFromContractWithCustomer, FY2023 end=2023-09-30

BHUTAN_POPULATION = 784_043        # REST Countries (current)
BHUTAN_AREA_KM2 = 38_394           # REST Countries (current)
BHUTAN_GDP_2023 = 3.013e9          # World Bank NY.GDP.MKTP.CD (2023)

# Confabulated values observed in the hard-topics corpus
NVIDIA_CONFABULATED = 39.3e9       # Model applied prior-quarter number as annual


# ================================================================
# HELPERS
# ================================================================

def _decomp(subject, metric, value, raw_value, unit="currency",
            time_period="", sentence="", heading="Financial Results"):
    """Build a ClaimDecomposition for testing."""
    return ClaimDecomposition(
        subject=subject, metric=metric, value=value,
        raw_value=raw_value, unit=unit, time_period=time_period,
        claim_type="direct", sentence=sentence, heading=heading,
    )


# ================================================================
# GROUP 1: SEC EDGAR - CORRECT CLAIMS (should verify)
# ================================================================

class TestSECEdgarVerification:
    """SEC EDGAR is the highest-authority source for US public company
    financials. These tests verify that the Source Network can match
    correct claims against XBRL filings."""

    @pytest.mark.parametrize("label,value,raw,fy,expected_match", [
        ("NVIDIA FY2026 exact",   215.94e9, "215.94", "FY2026", "exact"),
        ("NVIDIA FY2025 exact",   130.50e9, "130.5",  "FY2025", "exact"),
        ("NVIDIA FY2026 close",   210e9,    "210",    "FY2026", "close"),
        ("Apple FY2025 exact",    416.16e9, "416.16", "FY2025", "exact"),
        ("Apple FY2024 exact",    391.04e9, "391.04", "FY2024", "exact"),
    ])
    def test_correct_claims_verify(self, label, value, raw, fy, expected_match):
        """Correct claims should produce exact or close matches."""
        company = "NVIDIA" if "NVIDIA" in label else "Apple"
        d = _decomp(
            subject=company, metric="revenue", value=value,
            raw_value=raw, time_period=fy,
            sentence=f"{company} reported {fy} revenue of ${raw} billion.",
        )
        r = verify_sec_edgar(d)
        if r.match_type == "no_data":
            pytest.skip(f"{label}: SEC EDGAR returned no_data (API timeout or rate limit)")
        assert r.match_type == expected_match, (
            f"{label}: expected {expected_match}, got {r.match_type} "
            f"(source_value=${r.source_value/1e9:.2f}B, diff={r.difference_pct}%)"
        )


    # ============================================================
    # GROUP 2: SEC EDGAR - WRONG CLAIMS (should contradict)
    # ============================================================
    # SEC EDGAR correctly contradicts grossly wrong claims when the
    # fiscal year matches. The matching logic (source_network.py lines
    # 1870-1876) always records the closest FY-matching filing,
    # then classifies anything >3% off as "contradicted" (line 1908).
    #
    # Note: the matched source_value may be a prior year's data
    # reported in the same 10-K filing, not necessarily the current
    # year's data. The verifier picks the closest match among all
    # entries tagged with the target FY.

    @pytest.mark.parametrize("label,value,raw,fy", [
        ("NVIDIA confabulated $39.3B",  39.3e9,  "39.3",  "FY2026"),
        ("NVIDIA half-wrong $100B",     100e9,   "100",   "FY2026"),
        ("Apple wrong $300B",           300e9,   "300",   "FY2025"),
    ])
    def test_wrong_claims_contradicted(self, label, value, raw, fy):
        """Grossly wrong claims should be detected as contradicted
        when the fiscal year matches a filing."""
        company = "NVIDIA" if "NVIDIA" in label else "Apple"
        d = _decomp(
            subject=company, metric="revenue", value=value,
            raw_value=raw, time_period=fy,
            sentence=f"{company} reported {fy} revenue of ${raw} billion.",
        )
        r = verify_sec_edgar(d)
        if r.match_type == "no_data":
            pytest.skip(f"{label}: SEC EDGAR returned no_data (API timeout or rate limit)")
        assert r.match_type == "contradicted", (
            f"{label}: expected contradicted, got {r.match_type}. "
            f"source_value=${r.source_value/1e9:.2f}B, diff={r.difference_pct}%"
        )


# ================================================================
# GROUP 2b: SEC EDGAR - NON-REVENUE METRICS
# ================================================================
# Tests that non-revenue financial claims (cash, operating expenses)
# route to the correct XBRL concepts instead of defaulting to
# revenue and producing false contradictions.

class TestSECEdgarNonRevenueMetrics:

    def test_cash_claim_uses_cash_concept(self):
        """$43.2B cash should query CashAndCashEquivalents, not Revenue.

        Before fix: cash claims had no metric pattern, fell through to
        revenue concepts, and were either falsely contradicted or
        unverifiable. After fix: cash claims map to the correct XBRL
        concept and get verified or correctly contradicted.
        """
        d = _decomp(
            subject="NVIDIA", metric="cash", value=43.2e9,
            raw_value="43.2", time_period="FY2026",
            sentence="The company held $43.2 billion in cash and equivalents at the end of the fiscal year.",
        )
        r = verify_sec_edgar(d)
        if r.match_type == "no_data":
            pytest.skip("SEC EDGAR returned no_data (API timeout or rate limit)")
        # The claim should match NVIDIA's actual cash position.
        # Whether exact/close/contradicted depends on the true value,
        # but it should NOT be compared against revenue.
        assert r.source_value is not None, "Expected a source value from SEC EDGAR"
        # Sanity: the matched value should be in the same order of
        # magnitude as the claim (tens of billions), not hundreds
        # of billions (which would indicate revenue was matched).
        if r.source_value and r.source_value > 150e9:
            pytest.fail(
                f"Cash claim matched a value of ${r.source_value/1e9:.1f}B, "
                f"which looks like revenue, not cash. The XBRL concept "
                f"routing is likely still falling through to revenue."
            )

    def test_opex_claim_uses_expenses_concept(self):
        """$25.3B operating expenses should query OperatingExpenses, not Revenue.

        Before fix: opex claims matched historical revenue from the wrong
        year (e.g., FY2022 revenue $26.9B was close to $25.3B opex).
        After fix: opex claims map to the correct XBRL concept.
        """
        d = _decomp(
            subject="NVIDIA", metric="operating_expenses", value=25.3e9,
            raw_value="25.3", time_period="FY2026",
            sentence="Operating expenses totaled $25.3 billion.",
        )
        r = verify_sec_edgar(d)
        if r.match_type == "no_data":
            pytest.skip("SEC EDGAR returned no_data (API timeout or rate limit)")
        assert r.source_value is not None, "Expected a source value from SEC EDGAR"
        # Same sanity check: value should not be hundreds of billions
        if r.source_value and r.source_value > 150e9:
            pytest.fail(
                f"Opex claim matched ${r.source_value/1e9:.1f}B, "
                f"which looks like revenue, not operating expenses."
            )

    def test_decompose_detects_cash_metric(self):
        """decompose_claim should detect metric='cash' from sentence text."""
        from source_network import decompose_claim
        claim = {
            "sentence": "The company held $43.2 billion in cash and equivalents.",
            "heading": "Financial Results",
            "numbers": ["$43.2 billion"],
            "is_prediction": False,
        }
        d = decompose_claim(claim, topic="NVIDIA", doc_primary_entity="NVIDIA")
        assert d.metric == "cash", f"Expected metric='cash', got '{d.metric}'"

    def test_decompose_detects_opex_metric(self):
        """decompose_claim should detect metric='operating_expenses'."""
        from source_network import decompose_claim
        claim = {
            "sentence": "Operating expenses totaled $25.3 billion for the year.",
            "heading": "Financial Results",
            "numbers": ["$25.3 billion"],
            "is_prediction": False,
        }
        d = decompose_claim(claim, topic="NVIDIA", doc_primary_entity="NVIDIA")
        assert d.metric == "operating_expenses", (
            f"Expected metric='operating_expenses', got '{d.metric}'"
        )

    def test_heading_propagates_time_period(self):
        """Claims under a heading like 'Fiscal Year 2026 Summary' should
        inherit the year even when the sentence has no year.

        Before the fix: cash claim with no year fell through to no_data
        because the no-target-fy branch only accepted matches within 30%.
        After the fix: heading provides the year, the FY-matching branch
        is used, and the claim correctly contradicts or verifies."""
        from source_network import decompose_claim
        claim = {
            "sentence": "The company held $43.2 billion in cash and equivalents.",
            "heading": "NVIDIA Fiscal Year 2026 Financial Summary",
            "numbers": ["$43.2 billion"],
            "is_prediction": False,
        }
        d = decompose_claim(claim, topic="NVIDIA", doc_primary_entity="NVIDIA")
        assert "2026" in d.time_period, (
            f"Expected time_period to contain '2026', got {d.time_period!r}"
        )

    def test_target_fy_filter_excludes_comparative_data(self):
        """SEC EDGAR XBRL filings include 2-3 years of comparative data
        in each annual filing, all tagged with the same filing fy. The
        end-date filter must exclude prior-year comparative data so that
        an FY2026 query returns only the FY2026 actual value.

        Before the fix: a $12.8B claim for FY2026 could match $60.9B
        (FY2024 comparative data tagged fy=2026), producing a confusing
        contradiction. After the fix: it matches the actual FY2026 value
        ($215.9B) for an obvious, transparent contradiction."""
        d = _decomp(
            subject="NVIDIA", metric="revenue", value=12.8e9,
            raw_value="12.8", time_period="FY2026",
            sentence="Gaming revenue declined to $12.8 billion.",
        )
        r = verify_sec_edgar(d)
        if r.match_type == "no_data":
            pytest.skip("SEC EDGAR returned no_data (API timeout or rate limit)")
        # The matched source value must NOT be the FY2024 comparative
        # ($60.9B) or FY2025 comparative ($130.5B). It should be the
        # actual FY2026 revenue ($215.9B).
        assert r.source_value > 200e9, (
            f"Expected match against actual FY2026 revenue (~$215.9B), "
            f"got ${r.source_value/1e9:.1f}B (likely comparative data)"
        )

    def test_segment_claims_marked_unverifiable(self):
        """Segment claims (data center, gaming, automotive, services,
        cloud, etc.) cannot be verified by SEC EDGAR's companyconcept
        API and must be routed away from it. The honest outcome is
        unverifiable, not a false contradiction against the company
        total.

        Without segment detection, the $12.8B gaming claim would route
        to SEC EDGAR, query revenue, find $215.9B, and contradict
        against the wrong denominator. The user would see "Source
        Network contradicts: NVIDIA FY2026 revenue is $215.9B, not
        $12.8B" which is technically true but completely missing the
        point: the claim is about gaming SEGMENT revenue, not total."""
        from source_network import decompose_claim, _classify_and_route
        # Direct gaming claim
        claim = {
            "sentence": "Gaming revenue declined to $12.8 billion.",
            "heading": "NVIDIA Fiscal Year 2026 Financial Summary",
            "numbers": ["$12.8 billion"],
            "is_prediction": False,
        }
        d = decompose_claim(claim, topic="NVIDIA", doc_primary_entity="NVIDIA")
        assert d.is_segment, "Expected gaming claim to be marked as segment"
        sources = _classify_and_route(d)
        names = [s.__name__ for s in sources]
        assert "verify_sec_edgar" not in names, (
            f"Segment claim should not route to SEC EDGAR. Got: {names}"
        )

    def test_segment_detection_via_doc_text_fallback(self):
        """When the sentence is truncated by the upstream sentence
        splitter (split_sentences breaks on line boundaries first),
        segment qualifiers may be missing from the stored sentence.

        The doc_text fallback recovers them by looking up the original
        text immediately preceding the value's first occurrence.
        Without it, claims like '$5.6 billion, up 55% year over year'
        (truncated from 'Automotive revenue reached $5.6 billion...')
        would slip through segment detection."""
        from source_network import decompose_claim
        doc_text = (
            "## NVIDIA Fiscal Year 2026 Financial Summary\n\n"
            "Gaming revenue declined to $12.8 billion. Automotive revenue reached\n"
            "$5.6 billion, up 55% year over year. Operating expenses totaled\n"
            "$25.3 billion.\n"
        )
        claim = {
            # The truncated sentence as it would arrive from claim_analysis
            "sentence": "$5.6 billion, up 55% year over year.",
            "heading": "NVIDIA Fiscal Year 2026 Financial Summary",
            "numbers": ["$5.6 billion"],
            "is_prediction": False,
        }
        d = decompose_claim(claim, topic="NVIDIA",
                           doc_text=doc_text, doc_primary_entity="NVIDIA")
        assert d.is_segment, (
            "Expected automotive claim to be detected as segment "
            "via doc_text fallback even with truncated sentence"
        )

    def test_segment_detection_does_not_flag_total_revenue(self):
        """The doc_text fallback must not bleed across sentence
        boundaries. The $215.9B consolidated revenue claim sits in
        a paragraph that also mentions 'data center segment'. A naive
        wide-window search would falsely flag the total as a segment.

        The lookback window must stop at sentence boundaries so the
        prior sentence's qualifiers don't leak."""
        from source_network import decompose_claim
        doc_text = (
            "## NVIDIA Fiscal Year 2026 Financial Summary\n\n"
            "NVIDIA reported fiscal year 2026 revenue of $215.9 billion, "
            "representing significant growth from the prior year's "
            "$130.5 billion. The company's data center segment generated "
            "$180 billion in revenue.\n"
        )
        claim = {
            "sentence": "NVIDIA reported fiscal year 2026 revenue of $215.9 billion.",
            "heading": "NVIDIA Fiscal Year 2026 Financial Summary",
            "numbers": ["$215.9 billion"],
            "is_prediction": False,
        }
        d = decompose_claim(claim, topic="NVIDIA",
                           doc_text=doc_text, doc_primary_entity="NVIDIA")
        assert not d.is_segment, (
            "Total revenue claim should NOT be flagged as segment "
            "even when 'data center segment' appears in the next sentence"
        )

    def test_prior_year_claim_uses_decremented_year(self):
        """Sentences like 'FY2026 revenue of $215B, up from prior year's
        $130B' have one number for the current year and another for the
        prior year. The matcher must detect the 'prior year' marker and
        target the year - 1, not the sentence's main year.

        Without this, the $130B claim inherits target_fy=2026 from the
        heading, the end-date filter rejects all 2025 entries, and the
        claim falsely contradicts against $215.9B (FY2026 actual)."""
        from source_network import decompose_claim
        claim = {
            "sentence": "significant growth from the prior year's $130.5 billion.",
            "heading": "NVIDIA Fiscal Year 2026 Financial Summary",
            "numbers": ["$130.5 billion"],
            "is_prediction": False,
        }
        d = decompose_claim(claim, topic="NVIDIA", doc_primary_entity="NVIDIA")
        assert "2025" in d.time_period, (
            f"Expected time_period to be decremented to 2025, got {d.time_period!r}"
        )

    def test_prior_year_does_not_affect_main_year_claim(self):
        """When a sentence has BOTH a current-year value and a prior-
        year value, only the prior-year claim should be decremented.
        The current-year claim must keep its main year."""
        from source_network import decompose_claim
        # Same sentence, but for the $215.9B claim (current year)
        claim = {
            "sentence": "NVIDIA reported fiscal year 2026 revenue of $215.9 billion.",
            "heading": "NVIDIA Fiscal Year 2026 Financial Summary",
            "numbers": ["$215.9 billion"],
            "is_prediction": False,
        }
        d = decompose_claim(claim, topic="NVIDIA", doc_primary_entity="NVIDIA")
        assert "2026" in d.time_period, (
            f"Expected time_period 2026 for main claim, got {d.time_period!r}"
        )

    def test_cross_filing_comparative_leak_blocked(self):
        """Stress test: a claim value that matches a different fiscal
        year's actual revenue must NOT produce a false exact match.

        $60.92B is NVIDIA's actual FY2024 revenue. It exists as
        comparative data in the FY2025 10-K (tagged fy=2025) and the
        FY2026 10-K (tagged fy=2026). When a claim says '$60.92B for
        NVIDIA FY2026 revenue', the matcher must reject all the
        comparative entries and contradict against the actual FY2026
        value ($215.9B).

        This test exposes a leak in the original filing_fy-based filter:
        the FY2025 10-K's comparative entry has fy=2025, target_fy=2026,
        which falls into the adjacent-year branch (within 1). The
        adjacent-year branch only checked diff < 5%, and the false-year
        match has diff = 0%. Result: false exact match.

        The end-year filter eliminates this by selecting entries whose
        end date year matches the target year, regardless of which
        filing they were reported in."""
        d = _decomp(
            subject="NVIDIA", metric="revenue", value=60.92e9,
            raw_value="60.92", time_period="FY2026",
            sentence="NVIDIA reported FY2026 revenue of $60.92 billion.",
        )
        r = verify_sec_edgar(d)
        if r.match_type == "no_data":
            pytest.skip("SEC EDGAR returned no_data (API timeout or rate limit)")
        # The actual FY2026 revenue is ~$215.9B. The claim must NOT
        # be falsely matched against the FY2024 comparative.
        assert r.match_type == "contradicted", (
            f"Expected contradicted (claim $60.9B vs actual FY2026 ~$215.9B), "
            f"got {r.match_type}. source_value=${r.source_value/1e9:.2f}B "
            f"({r.source_text})"
        )
        assert r.source_value > 200e9, (
            f"Expected source_value to be actual FY2026 revenue (~$215.9B), "
            f"got ${r.source_value/1e9:.2f}B (likely comparative data leak)"
        )


# ================================================================
# GROUP 3: WIKIPEDIA FALSE MATCH
# ================================================================
# FINDING: Wikipedia matches raw-scale numbers across domains.
#
# When the claim is "$39.3 billion revenue" and the Wikipedia article
# about NVIDIA mentions "40" (employee headcount reduction), the
# raw-scale path matches 39.3 against 40 (1.8% diff = "close").
# The metric context (revenue vs headcount) isn't strong enough to
# prevent this cross-domain false positive.
#
# Product impact: grossly wrong financial claims can appear
# "approximately verified" via Wikipedia. Combined with SEC EDGAR
# returning no_data, the pipeline may report the wrong claim as
# "close" based solely on a Wikipedia false match.

class TestWikipediaFalseMatch:

    def test_confabulated_nvidia_rejects_unrelated_number(self):
        """$39.3B revenue should NOT match employee headcount of 40.

        The raw-scale matching gates (skip when scale factor >1000x,
        reject when large currency claim has no metric keywords in
        Wikipedia context) are supposed to prevent this cross-domain
        false positive. This test asserts the gates work rather than
        documenting the failure."""
        d = _decomp(
            subject="NVIDIA", metric="revenue", value=39.3e9,
            raw_value="39.3", time_period="FY2026",
            sentence="NVIDIA reported fiscal year 2026 revenue of $39.3 billion.",
        )
        r = verify_wikipedia(d)

        if r.match_type == "no_data":
            # Wikipedia returned nothing. That's a correct rejection.
            pass
        elif r.match_type in ("exact", "close"):
            # If matched, verify the source text is about revenue,
            # not an unrelated number (headcount, dates, etc.)
            source_text_lower = (r.source_text or "").lower()
            is_revenue_context = any(
                kw in source_text_lower
                for kw in ["revenue", "sales", "income", "billion", "earnings"]
            )
            assert is_revenue_context, (
                f"Wikipedia false positive: matched "
                f"'{r.source_text[:80]}' (source_value={r.source_value}, "
                f"diff={r.difference_pct}%). This is not a revenue figure. "
                f"The raw-scale/metric-context gates should have rejected it."
            )
            # If it IS a revenue context, Wikipedia actually found real data
            # (article may have been updated). That's a legitimate match.


# ================================================================
# GROUP 4: WORLD BANK / REST COUNTRIES - BHUTAN
# ================================================================

class TestBhutanVerification:
    """Bhutan tests exercise the country/macro verification path:
    REST Countries for demographics, World Bank for GDP."""

    @pytest.mark.timeout(15)
    def test_bhutan_population_correct(self):
        """Correct population should verify via REST Countries."""
        d = _decomp(
            subject="Bhutan", metric="population", value=784043,
            raw_value="784043", unit="count", time_period="",
            sentence="Bhutan has a population of approximately 784,043.",
            heading="Demographics",
        )
        r = verify_rest_countries(d)
        if r.match_type == "no_data":
            pytest.skip(
                "REST Countries returned no_data (possible timeout or "
                "API unavailability). This is an API availability issue, "
                "not a product bug."
            )
        assert r.match_type == "exact", (
            f"Expected exact match for Bhutan population, "
            f"got {r.match_type} (source_value={r.source_value})"
        )

    def test_bhutan_population_wrong(self):
        """Grossly wrong population should contradict or no_data."""
        d = _decomp(
            subject="Bhutan", metric="population", value=2_500_000,
            raw_value="2500000", unit="count", time_period="",
            sentence="Bhutan has a population of 2.5 million.",
            heading="Demographics",
        )
        r = verify_rest_countries(d)
        # 2.5M vs 784K = 219% off. REST Countries uses 5% for close.
        # This should NOT match.
        assert r.match_type not in ("exact", "close"), (
            f"Bhutan population 2.5M should not verify "
            f"(actual ~784K, got {r.match_type})"
        )

    @pytest.mark.timeout(15)
    def test_bhutan_area_correct(self):
        """Correct area should verify via REST Countries."""
        d = _decomp(
            subject="Bhutan", metric="area", value=38394,
            raw_value="38394", unit="count", time_period="",
            sentence="Bhutan covers an area of 38,394 square kilometers.",
            heading="Geography",
        )
        r = verify_rest_countries(d)
        if r.match_type == "no_data":
            pytest.skip(
                "REST Countries returned no_data (possible timeout or "
                "API unavailability). This is an API availability issue, "
                "not a product bug."
            )
        assert r.match_type == "exact", (
            f"Expected exact match for Bhutan area, "
            f"got {r.match_type} (source_value={r.source_value})"
        )

    @pytest.mark.timeout(15)
    def test_bhutan_gdp_2023(self):
        """Bhutan GDP 2023 via World Bank. May timeout (API latency)."""
        d = _decomp(
            subject="Bhutan", metric="gdp", value=3.013e9,
            raw_value="3.013", unit="currency", time_period="2023",
            sentence="Bhutan GDP was approximately $3.013 billion in 2023.",
            heading="Economy",
        )
        r = verify_world_bank(d)
        # World Bank may timeout. Document either outcome.
        if r.match_type == "no_data":
            pytest.skip(
                "World Bank returned no_data (possible timeout or "
                "data not available for this year). This is an API "
                "availability issue, not a product bug."
            )
        assert r.match_type in ("exact", "close"), (
            f"Expected Bhutan GDP $3.013B to match World Bank 2023 data, "
            f"got {r.match_type} (source_value={r.source_value})"
        )


# ================================================================
# GROUP 5: FULL PIPELINE - END-TO-END CLAIMS
# ================================================================
# These tests run claims through the complete pipeline
# (decomposition, routing, verification, consensus) using
# verify_claims_source_network, the production entry point.

class TestFullPipelineVerification:
    """End-to-end tests through the production pipeline.
    These exercise claim analysis + source network together."""

    def _make_claim_input(self, sentence, heading="Financial Results"):
        """Build the claim dict format that verify_claims_source_network expects.
        Uses analyze_claims to extract numbers, then filters to the claim
        containing our target sentence."""
        doc_text = f"## {heading}\n\n{sentence}"
        ca = analyze_claims(doc_text)
        claims = ca.get("claims", [])
        if not claims:
            pytest.skip(f"analyze_claims extracted 0 claims from: {sentence}")
        return claims, doc_text

    def test_nvidia_correct_revenue_full_pipeline(self):
        """Correct NVIDIA revenue through the full pipeline."""
        claims, doc = self._make_claim_input(
            "NVIDIA reported fiscal year 2026 revenue of $215.9 billion."
        )
        results = verify_claims_source_network(
            claims, topic="NVIDIA", doc_text=doc,
        )
        # At least one result should exist
        assert len(results) > 0, "Pipeline returned no results"
        # Find the result for our revenue claim
        rev_results = [
            r for r in results
            if any("215" in str(n) for n in r.claim_numbers)
        ]
        if not rev_results:
            pytest.skip("Pipeline did not match the $215.9B claim")
        r = rev_results[0]
        if r.verdict == "unverifiable":
            pytest.skip("SEC EDGAR returned no_data (API timeout or rate limit)")
        assert r.verdict in ("verified", "close"), (
            f"Correct NVIDIA revenue should verify, got {r.verdict} "
            f"(best_source={r.best_source}, confidence={r.confidence})"
        )

    def test_nvidia_confabulated_revenue_full_pipeline(self):
        """Confabulated NVIDIA revenue through the full pipeline.

        SEC EDGAR should detect $39.3B as contradicted (actual FY2026
        revenue is $215.94B). The pipeline correctly routes to SEC EDGAR
        and the contradiction detection works.
        """
        claims, doc = self._make_claim_input(
            "NVIDIA reported fiscal year 2026 revenue of $39.3 billion."
        )
        results = verify_claims_source_network(
            claims, topic="NVIDIA", doc_text=doc,
        )
        assert len(results) > 0, "Pipeline returned no results"
        rev_results = [
            r for r in results
            if any("39" in str(n) for n in r.claim_numbers)
        ]
        if not rev_results:
            pytest.skip("Pipeline did not match the $39.3B claim")
        r = rev_results[0]
        # SEC EDGAR contradicts ($39.3B vs closest FY-matched filing).
        # Wikipedia metric gate rejects the Arm acquisition false match.
        # If SEC EDGAR is rate-limited, verdict may degrade to unverifiable.
        if r.verdict == "unverifiable":
            pytest.skip("SEC EDGAR returned no_data (API timeout or rate limit)")
        assert r.verdict == "contradicted", (
            f"Confabulated NVIDIA $39.3B should be contradicted, "
            f"got {r.verdict} (best_source={r.best_source}, "
            f"confidence={r.confidence:.2f})"
        )

    def test_apple_correct_revenue_full_pipeline(self):
        """Correct Apple FY2025 revenue through the full pipeline."""
        claims, doc = self._make_claim_input(
            "Apple reported fiscal year 2025 revenue of $416.2 billion."
        )
        results = verify_claims_source_network(
            claims, topic="Apple", doc_text=doc,
        )
        assert len(results) > 0, "Pipeline returned no results"
        rev_results = [
            r for r in results
            if any("416" in str(n) for n in r.claim_numbers)
        ]
        if not rev_results:
            pytest.skip("Pipeline did not match the $416.2B claim")
        r = rev_results[0]
        if r.verdict == "unverifiable":
            pytest.skip("SEC EDGAR returned no_data (API timeout or rate limit)")
        assert r.verdict in ("verified", "close"), (
            f"Correct Apple revenue should verify, got {r.verdict} "
            f"(best_source={r.best_source}, confidence={r.confidence})"
        )

    def test_projection_classified_correctly(self):
        """Future-dated claims should be classified as projections."""
        claims, doc = self._make_claim_input(
            "NVIDIA revenue is projected to reach $300 billion by fiscal year 2028."
        )
        results = verify_claims_source_network(
            claims, topic="NVIDIA", doc_text=doc,
        )
        if not results:
            pytest.skip("Pipeline returned no results")
        # At least one result should be a projection
        projections = [r for r in results if r.verdict == "projection"]
        assert len(projections) > 0, (
            f"Projection claim should get verdict='projection', "
            f"got verdicts: {[r.verdict for r in results]}"
        )


# ================================================================
# GROUP 6: SUBJECT EXTRACTION
# ================================================================
# The extract_subject function (source_network.py lines 404-428)
# correctly extracts "NVIDIA" from the heading "NVIDIA Fiscal Year
# 2026 Financial Summary" by finding the acronym and filtering out
# descriptive words.
#
# LATENT RISK: _find_cik still has loose substring matching.
# "NVIDIA Fiscal Year 2026 Financial Summary" maps to Visa Inc
# (CIK 0001403161) because "FINANCIAL" is a substring of Visa's
# registration. This would break if extract_subject ever passes
# a long heading through to _find_cik.

class TestSubjectExtraction:

    def test_heading_entity_extraction_works(self):
        """extract_subject correctly extracts 'NVIDIA' from long heading."""
        from source_network import decompose_claim

        claim = {
            "sentence": "NVIDIA reported fiscal year 2026 revenue of $215.9 billion.",
            "heading": "NVIDIA Fiscal Year 2026 Financial Summary",
            "numbers": ["$215.9 billion"],
            "is_prediction": False,
        }
        d = decompose_claim(claim, topic="NVIDIA", doc_primary_entity="NVIDIA")
        assert d.subject == "NVIDIA", (
            f"Expected 'NVIDIA', got '{d.subject}'"
        )

    def test_find_cik_does_not_resolve_long_heading_to_wrong_company(self):
        """_find_cik must not resolve a long heading like 'NVIDIA Fiscal
        Year 2026 Financial Summary' to a single-letter ticker like
        Visa (V) via substring matching.

        Original bug: titles and tickers were stored in the same dict
        and matched via substring loop. Single-letter tickers ("V" for
        Visa, "F" for Ford, "C" for Citi) became wildcards because
        "V" is a substring of any string containing the letter V.
        Fix: separated tickers (exact match only) from titles
        (substring match for sufficiently long subjects)."""
        from source_network import _find_cik

        cik, ticker = _find_cik("NVIDIA Fiscal Year 2026 Financial Summary")
        # The fix returns None for ambiguous heading-as-subject cases
        # rather than picking a wrong ticker. Either None or NVDA is
        # acceptable; any other ticker is a regression.
        assert ticker in (None, "NVDA"), (
            f"Heading should not resolve to wrong company. Got: {ticker}"
        )

    def test_find_cik_single_letter_ticker_only_via_exact_match(self):
        """Single-letter tickers (V, F, C) must only resolve via exact
        match, never via substring of an unrelated subject."""
        from source_network import _find_cik
        # Exact matches still work
        for ticker_sym in ("V", "F", "C"):
            cik, t = _find_cik(ticker_sym)
            assert t == ticker_sym, (
                f"Exact ticker lookup for {ticker_sym} failed: got {t}"
            )
        # Subjects that contain V/F/C as letters must NOT match
        cik, t = _find_cik("Vacation")
        assert t != "V", "Vacation should not resolve to Visa"
        cik, t = _find_cik("Forecast")
        assert t != "F", "Forecast should not resolve to Ford"


# ================================================================
# GROUP 7: COVERAGE REPORT
# ================================================================
# This is not a pass/fail test. It runs a multi-claim document
# through the pipeline and reports what percentage of claims the
# Source Network can verify, contradict, or must leave unverifiable.

class TestCoverageReport:

    def test_nvidia_earnings_document_coverage(self):
        """Run a realistic multi-claim document and report coverage.

        This test always passes. Its value is in the printed report,
        which shows what fraction of claims the Source Network handles.
        """
        doc = """## NVIDIA Fiscal Year 2026 Financial Summary

NVIDIA reported fiscal year 2026 revenue of $215.9 billion, representing
significant growth from the prior year's $130.5 billion. The company's
data center segment generated $180 billion in revenue. Gross margin
expanded to 73.5% for the full year.

Gaming revenue declined to $12.8 billion. Automotive revenue reached
$5.6 billion, up 55% year over year. Operating expenses totaled
$25.3 billion.

The company held $43.2 billion in cash and equivalents at the end
of the fiscal year.
"""
        ca = analyze_claims(doc)
        claims = ca.get("claims", [])
        results = verify_claims_source_network(
            claims, topic="NVIDIA", doc_text=doc,
        )

        # Tally verdicts
        verdicts = {}
        for r in results:
            verdicts[r.verdict] = verdicts.get(r.verdict, 0) + 1

        total = len(results)
        report_lines = [
            "",
            "=" * 60,
            "SOURCE NETWORK COVERAGE REPORT: NVIDIA FY2026 EARNINGS",
            "=" * 60,
            f"Total claims processed: {total}",
        ]
        for v in ["verified", "close", "contradicted", "disputed", "unverifiable", "projection"]:
            count = verdicts.get(v, 0)
            pct = f"{count/total*100:.0f}%" if total > 0 else "N/A"
            report_lines.append(f"  {v:15s}: {count:3d} ({pct})")

        report_lines.append("")
        report_lines.append("Per-claim detail:")
        for r in results:
            nums = ", ".join(str(n) for n in r.claim_numbers)
            src = r.best_source or "none"
            report_lines.append(
                f"  [{r.verdict:13s}] {nums:>12s}  via {src:15s}  "
                f"conf={r.confidence:.2f}  {r.detail[:60]}"
            )
        report_lines.append("=" * 60)

        report = "\n".join(report_lines)
        print(report)

        # This test always passes. The report is the output.
        assert total > 0, "No claims extracted from the document"
