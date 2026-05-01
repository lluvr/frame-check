"""Regression tests for TimeContext integration into verifiers.

Two main surfaces:

  1. SEC EDGAR quarterly filter. FINDINGS.md B.1: Tesla Q4 2023
     claim returned annual revenue because the filter fell back
     from 10-Q to 10-K when no quarterly data existed. With
     TimeContext, quarterly claims either get 10-Q data or
     no_data; never annual-data-used-as-quarterly-contradiction.

  2. REST Countries historical guard. A current-only data source
     cannot verify a HISTORICAL claim; attempting to do so
     produces coincidental matches (e.g. Japan 2010 population
     happens to be near Japan 2026 population) that look like
     verifications but aren't. With TimeContext, HISTORICAL
     subjects return no_data from REST Countries.

The time_context classifier itself is exhaustively tested in
test_time_context.py. These tests are specifically about the
routing / verifier integration; they lock in the behaviour that
Bug B.1 is fixed by construction and that the analogous
correctness guard for REST Countries holds.

These tests do not hit the network (the verifier functions return
no_data early when the guards fire) and do not require API keys.
"""

import pytest

from source_network import (
    ClaimDecomposition,
    _classify_and_route,
    verify_sec_edgar,
    verify_rest_countries,
)


def _decomp(**kwargs):
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
# TimeContext attached to decomposition by the router
# ================================================================

class TestTimeContextAttachedToDecomp:

    def test_quarterly_claim_populates_time_fields(self):
        d = _decomp(
            subject="Tesla",
            sentence="Tesla reported Q4 2023 revenue of $25.167 billion.",
            time_period="Q4 2023",
        )
        _classify_and_route(d)
        assert d.time_period_type == "quarterly"
        assert d.time_quarter == 4
        assert d.time_year == 2023
        assert d.time_classification_reason == "quarterly_q_notation"

    def test_annual_claim_populates_time_fields(self):
        d = _decomp(
            subject="France",
            sentence="France's GDP in 2022 was $2.78 trillion.",
        )
        _classify_and_route(d)
        assert d.time_period_type == "annual"
        assert d.time_year == 2022

    def test_historical_claim_populates_time_fields(self):
        d = _decomp(
            subject="India",
            sentence="India had a population of 1.2 billion in 2010.",
        )
        _classify_and_route(d)
        # 2010 is > 5 years before reference_year so HISTORICAL
        assert d.time_period_type == "historical"
        assert d.time_year == 2010

    def test_claim_with_no_time_anchor(self):
        d = _decomp(
            subject="NVIDIA",
            sentence="NVIDIA reported strong growth.",
        )
        _classify_and_route(d)
        assert d.time_period_type == "unknown"
        assert d.time_year is None
        assert d.time_quarter is None


# ================================================================
# SEC EDGAR quarterly guard (FINDINGS B.1)
# ================================================================
# verify_sec_edgar hits the network; we can't easily test the
# full happy path without API calls. The behaviour we CAN test:
# the decomposition's time_period_type drives the filter's
# "is_quarterly_claim" flag. We assert the decomp flow produces
# the right flag; the filter behaviour itself is exercised by
# the calibration corpus (sec-005 Tesla Q4 2023 on a live run
# with SEC access).

class TestSecQuarterlyGuard:
    """The integration contract: when decomp.time_period_type is
    'quarterly', the SEC filter uses 10-Q filtering and does NOT
    fall back to 10-K. The direct behavioural test requires the
    SEC ticker cache + network access; the integration test
    below verifies the decomp fields needed for that decision
    are populated correctly."""

    def test_quarterly_claim_time_fields_ready_for_sec_filter(self):
        d = _decomp(
            subject="Tesla",
            sentence="Tesla reported Q4 2023 revenue of $25.167 billion.",
            time_period="Q4 2023",
            metric="revenue",
            unit="currency",
            value=25_167_000_000,
        )
        _classify_and_route(d)
        # SEC filter reads these exact fields to decide quarterly vs annual
        assert d.time_period_type == "quarterly"
        assert d.time_quarter == 4
        assert d.time_year == 2023

    def test_annual_claim_time_fields_drive_annual_filter(self):
        d = _decomp(
            subject="Apple",
            sentence="Apple reported fiscal year 2023 revenue of $383 billion.",
            time_period="FY2023",
            metric="revenue",
            unit="currency",
            value=383_000_000_000,
        )
        _classify_and_route(d)
        assert d.time_period_type == "annual"
        assert d.time_year == 2023
        assert d.time_quarter is None


# ================================================================
# REST Countries historical guard
# ================================================================

class TestRestCountriesHistoricalGuard:

    def test_historical_claim_returns_no_data(self):
        # Japan historical population claim. REST Countries serves
        # current data only and has no time series; verifying a
        # historical claim against current data risks a coincidental
        # verified verdict that would be misleading. The guard
        # returns no_data without a network call.
        d = _decomp(
            subject="Japan",
            sentence="Japan had a population of 125 million in 2010.",
            metric="population",
        )
        _classify_and_route(d)
        assert d.time_period_type == "historical"
        result = verify_rest_countries(d)
        assert result.match_type == "no_data", (
            "HISTORICAL claim must get no_data from REST Countries, "
            f"got {result.match_type}"
        )

    def test_current_claim_still_flows_normally(self):
        # A CURRENT or UNKNOWN claim proceeds to the network path
        # as before. We can't test the full happy path without
        # network, but we assert the guard does NOT fire for
        # non-historical claims: the time_period_type is not
        # 'historical' after classification.
        d = _decomp(
            subject="Germany",
            sentence="Germany's population is 83 million.",
            metric="population",
        )
        _classify_and_route(d)
        assert d.time_period_type != "historical"

    def test_annual_recent_year_is_not_historical(self):
        # Recent annual claims stay annual (not historical) so the
        # REST Countries guard does NOT fire.
        d = _decomp(
            subject="Germany",
            sentence="Germany's population was 83 million in 2023.",
            metric="population",
        )
        _classify_and_route(d)
        assert d.time_period_type == "annual"  # not historical


# ================================================================
# Contract stability
# ================================================================

# ================================================================
# Cross-classifier interaction: both EntityType and TimeContext
# on the same claim
# ================================================================

class TestCrossClassifierInteraction:
    """Both classifiers fire on every claim. A claim that is
    COUNTRY + QUARTERLY must gate SEC (entity) AND correctly handle
    quarterly filing logic (time). A claim that is COMPANY +
    HISTORICAL must still route to SEC but should return no_data
    from REST Countries if applicable. These tests verify the
    interaction path that neither classifier's dedicated test
    file exercises alone."""

    def test_country_quarterly_gates_sec_and_sets_time(self):
        d = _decomp(
            subject="France",
            sentence="France's GDP was $2.78 trillion in Q4 2023.",
            metric="gdp",
            time_period="Q4 2023",
        )
        _classify_and_route(d)
        assert d.entity_type == "country"
        assert d.time_period_type == "quarterly"
        assert d.time_quarter == 4
        assert d.time_year == 2023
        # SEC must be gated by entity (country)
        sources = [s.__name__ for s in _classify_and_route(d)]
        assert "verify_sec_edgar" not in sources

    def test_company_historical_routes_sec_but_rc_gates(self):
        d = _decomp(
            subject="Apple",
            sentence="Apple reported revenue of $200 billion in 2010.",
            metric="revenue",
            unit="currency",
            value=200e9,
        )
        _classify_and_route(d)
        # Entity: company (if SEC cache warm) or unknown (cold)
        assert d.entity_type in ("company", "unknown")
        # Time: historical (2010 is > 5 years from now)
        assert d.time_period_type == "historical"
        # REST Countries gates on historical
        result = verify_rest_countries(d)
        assert result.match_type == "no_data"

    def test_crypto_current_gates_sec(self):
        d = _decomp(
            subject="Bitcoin",
            sentence="Bitcoin currently trades at $90,000.",
            unit="currency",
            value=90_000,
        )
        _classify_and_route(d)
        assert d.entity_type == "crypto_asset"
        assert d.time_period_type == "current"
        sources = [s.__name__ for s in _classify_and_route(d)]
        assert "verify_sec_edgar" not in sources


class TestDecompositionFieldContract:
    """The ClaimDecomposition time_* fields are read by verifiers
    and surfaced in the Tier A corpus event histogram. Their names
    and types are a stable contract."""

    def test_default_values(self):
        d = _decomp()
        assert d.time_period_type == ""
        assert d.time_year is None
        assert d.time_quarter is None
        assert d.time_year_range is None
        assert d.time_classification_reason == ""

    def test_field_types_after_classification(self):
        d = _decomp(sentence="Q4 2023 revenue was strong.", subject="Tesla")
        _classify_and_route(d)
        assert isinstance(d.time_period_type, str)
        assert isinstance(d.time_year, int)
        assert isinstance(d.time_quarter, int)
        # year_range stays None for non-range claims
        assert d.time_year_range is None
        assert isinstance(d.time_classification_reason, str)
