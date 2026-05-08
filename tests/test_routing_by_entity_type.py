"""Regression tests for source_network._classify_and_route under
the entity-type-aware routing scheme.

The 2026-04-16 first calibration run surfaced that "US national
debt exceeded $34 trillion" was routed to SEC EDGAR because the
subject "United States" matched the has_company capitalization
gate. SEC returned $243M from an unrelated filing, the consensus
went to `disputed`, and the user saw what looked like a real
contradiction. See FINDINGS.md category B.3.

The fix lands in two places:
  1. entity_classifier.classify_subject, which runs as a pure
     function on the subject string before routing.
  2. _classify_and_route, which consults the classifier and gates
     the SEC / Alpha Vantage branches on the result.

These tests lock in the routing matrix: for each entity type and
claim shape, which verifiers must the router include or exclude?
A future refactor that silently collapses the country / company
distinction will fail these tests loudly.
"""

import os

import pytest

from source_network import (
    ClaimDecomposition,
    _classify_and_route,
    verify_wikipedia,
    verify_sec_edgar,
    verify_alpha_vantage,
    verify_fred,
    verify_coingecko,
    verify_world_bank,
    verify_rest_countries,
    verify_wolfram,
)


def _names(sources):
    return [s.__name__ for s in sources]


def _decomp(**kwargs):
    """Build a ClaimDecomposition with sensible defaults for routing tests."""
    defaults = {
        "subject": "",
        "metric": "",
        "value": 0.0,
        "raw_value": "",
        "unit": "",
        "time_period": "",
        "claim_type": "direct",
        "sentence": "",
        "heading": "",
        "is_segment": False,
    }
    defaults.update(kwargs)
    return ClaimDecomposition(**defaults)


# ================================================================
# The headline regression: Bug 2
# ================================================================

class TestCountrySubjectNeverHitsSEC:
    """FINDINGS.md B.3: country subjects must not reach SEC EDGAR
    or Alpha Vantage, no matter how financial the sentence looks."""

    def test_us_national_debt_does_not_route_to_sec(self):
        d = _decomp(
            subject="United States",
            sentence="US national debt exceeded $34 trillion in January 2024.",
            unit="currency",
            value=34e12,
        )
        sources = _names(_classify_and_route(d))
        assert "verify_sec_edgar" not in sources
        assert "verify_alpha_vantage" not in sources

    def test_us_abbreviation_classified_and_gated(self):
        d = _decomp(
            subject="US",
            sentence="The US has revenue of $6 trillion in tax receipts.",
            unit="currency",
            value=6e12,
        )
        sources = _names(_classify_and_route(d))
        assert "verify_sec_edgar" not in sources

    def test_country_claim_gets_wikipedia(self):
        # Positive check: the structural fix must not starve country
        # claims of ALL verifiers. Wikipedia is always available.
        d = _decomp(
            subject="Germany",
            sentence="Germany's GDP was $4.2 trillion in 2023.",
            metric="gdp",
            value=4.2e12,
        )
        sources = _names(_classify_and_route(d))
        assert "verify_wikipedia" in sources

    def test_country_entity_type_attached_to_decomp(self):
        d = _decomp(
            subject="France",
            sentence="France's population is 67 million.",
        )
        _classify_and_route(d)
        assert d.entity_type == "country"
        assert d.entity_canonical == "France"
        assert d.entity_classification_reason == "country_alias_match"


# ================================================================
# Crypto routing preserved + gated against SEC
# ================================================================

class TestCryptoSubjectRouting:

    def test_crypto_subject_never_reaches_sec(self):
        d = _decomp(
            subject="Bitcoin",
            sentence="Bitcoin market cap is $1.2 trillion.",
            unit="currency",
            value=1.2e12,
        )
        sources = _names(_classify_and_route(d))
        assert "verify_sec_edgar" not in sources
        assert "verify_alpha_vantage" not in sources

    def test_crypto_entity_type_attached(self):
        d = _decomp(subject="BTC", sentence="BTC is trading near $90k.")
        _classify_and_route(d)
        assert d.entity_type == "crypto_asset"


# ================================================================
# Company routing preserved; unknown subjects still work
# ================================================================

class TestCompanyRoutingPreserved:
    """Companies recognizable via the SEC ticker cache should still
    route to SEC. When the cache is cold (offline test environment)
    the classifier returns UNKNOWN and the historical keyword-based
    routing takes over; still producing SEC in the route list."""

    def test_nvidia_financial_claim_routes_to_sec(self):
        d = _decomp(
            subject="NVIDIA",
            sentence="NVIDIA reported revenue of $60.9 billion in fiscal 2024.",
            unit="currency",
            value=60.9e9,
        )
        sources = _names(_classify_and_route(d))
        assert "verify_sec_edgar" in sources

    def test_segment_claim_skips_sec_as_before(self):
        # Pre-existing guard: is_segment=True skips SEC regardless
        # of entity type. Verify the new classifier-gate didn't
        # accidentally loosen this.
        d = _decomp(
            subject="Apple",
            sentence="Apple Services revenue was $85B in fiscal 2023.",
            unit="currency",
            value=85e9,
            is_segment=True,
        )
        sources = _names(_classify_and_route(d))
        assert "verify_sec_edgar" not in sources

    def test_unknown_entity_with_financial_keyword_still_routes(self):
        # A non-SEC-listed company with a financial keyword is
        # UNKNOWN to the classifier but still deserves a SEC attempt
        # (which will return no_data honestly). This preserves the
        # historical path for European companies like BASF.
        d = _decomp(
            subject="RandomPrivateCorp LLC",
            sentence="RandomPrivateCorp reported revenue of $500M in 2023.",
            unit="currency",
            value=500e6,
        )
        sources = _names(_classify_and_route(d))
        # SEC should still be routed for unknown subjects with
        # financial keywords so the legacy behaviour is preserved.
        assert "verify_sec_edgar" in sources


# ================================================================
# FRED, World Bank, REST Countries preserved
# ================================================================

class TestMacroRoutingPreserved:
    """Country-macro routing was not touched by the classifier
    integration; verify the preservation explicitly since the
    has_company refactor could plausibly have broken it."""

    def test_world_bank_still_routes_for_country_macro(self):
        d = _decomp(
            subject="France",
            sentence="France's GDP was $2.78 trillion in 2022.",
            metric="gdp",
            value=2.78e12,
        )
        sources = _names(_classify_and_route(d))
        assert "verify_world_bank" in sources

    def test_rest_countries_still_routes_for_population(self):
        d = _decomp(
            subject="Germany",
            sentence="Germany has a population of 83 million.",
            metric="population",
            value=83e6,
        )
        sources = _names(_classify_and_route(d))
        assert "verify_rest_countries" in sources

    @pytest.mark.skipif(
        not os.environ.get("FRED_API_KEY"),
        reason="FRED routing requires FRED_API_KEY present",
    )
    def test_fred_still_routes_for_us_macro_with_key(self):
        d = _decomp(
            subject="United States",
            sentence="US unemployment was 3.7% in December 2023.",
            metric="unemployment",
            value=3.7,
        )
        sources = _names(_classify_and_route(d))
        assert "verify_fred" in sources


# ================================================================
# Unknown subjects fall through to legacy behaviour
# ================================================================

class TestUnknownSubjectFallthrough:

    def test_empty_subject_only_wikipedia(self):
        d = _decomp(subject="", sentence="A claim without an extractable subject.")
        sources = _names(_classify_and_route(d))
        assert sources == ["verify_wikipedia"]

    def test_garbage_subject_does_not_hit_sec_without_keywords(self):
        d = _decomp(subject="asdjkhasd", sentence="asdjkhasd is asdf.")
        sources = _names(_classify_and_route(d))
        assert "verify_sec_edgar" not in sources


# ================================================================
# Decomposition attributes: classifier result flows through
# ================================================================

class TestEntityAttributeAttachment:
    """The classifier result must attach to the decomp so downstream
    consumers (SourceNetworkResult, display formatter, telemetry)
    can read the entity type without re-running the classifier."""

    def test_entity_type_defaults_empty(self):
        d = _decomp(subject="")
        # Before routing runs, the field is empty.
        assert d.entity_type == ""

    def test_entity_type_populated_after_routing(self):
        for subject, expected in [
            ("France", "country"),
            ("US", "country"),
            ("bitcoin", "crypto_asset"),
            ("asdjkhasd", "unknown"),
            ("North Korea", "country"),
            ("South Korea", "country"),
            ("Cote d'Ivoire", "country"),
        ]:
            d = _decomp(subject=subject, sentence=f"{subject} claim.")
            _classify_and_route(d)
            assert d.entity_type == expected, (
                f"subject={subject!r} produced entity_type={d.entity_type!r}, "
                f"expected {expected!r}"
            )


# ================================================================
# Asymmetry: classifier sees only subject; _detect_country scans
# sentence + heading. They can disagree. This test class makes the
# current behaviour explicit so a future refactor cannot silently
# change either direction.
# ================================================================

class TestClassifierDetectCountryAsymmetry:
    """classify_subject runs on decomp.subject only. _detect_country
    runs on decomp.sentence + decomp.heading. When they disagree,
    each contributes independently to routing:

      * Classifier COUNTRY + sentence has no country mention:
        SEC/AV gated OFF (classifier); WB/REST not routed
        (_detect_country found nothing). Macro verifiers miss.

      * Classifier UNKNOWN + sentence mentions a country:
        SEC/AV available (no COUNTRY classification to gate them);
        WB/REST routed (_detect_country matched). Both paths fire.

    These are not bugs; they are the documented asymmetry of the
    two systems. The tests below lock in the behaviour so the
    asymmetry is visible in the test surface and the next
    engineer does not have to reason it out from scratch."""

    def test_country_subject_no_country_in_sentence_misses_macro(self):
        # Subject declares the country; sentence does not. _detect_country
        # scans sentence + heading and finds nothing. WB/REST Countries
        # route is gated on _detect_country, not on the classifier, so
        # macro verifiers are NOT added in this asymmetric case.
        d = _decomp(
            subject="France",
            sentence="The nation's GDP was $2.78 trillion in 2022.",
            metric="gdp",
        )
        sources = _names(_classify_and_route(d))
        assert "verify_world_bank" not in sources, (
            "asymmetry surfaced: subject-only country detection does not "
            "drive the macro-verifier branch. If this starts passing "
            "the classifier has been wired into the macro branch too; "
            "update the test and RUNBOOK asymmetry note accordingly."
        )
        # But the classifier DID classify and DID gate SEC:
        assert d.entity_type == "country"
        assert "verify_sec_edgar" not in sources

    def test_unknown_subject_with_country_in_sentence_hits_macro(self):
        # Subject is garbage; sentence mentions a country. _detect_country
        # catches the sentence mention and routes WB/REST. Classifier
        # returns UNKNOWN so the SEC gate is NOT applied; existing
        # keyword-driven SEC routing still runs for financial keywords.
        d = _decomp(
            subject="asdjkhasd",
            sentence="France's GDP was $2.78 trillion in 2022.",
            metric="gdp",
        )
        sources = _names(_classify_and_route(d))
        assert "verify_world_bank" in sources
        # Classifier is UNKNOWN so no entity-type gate fired
        assert d.entity_type == "unknown"
