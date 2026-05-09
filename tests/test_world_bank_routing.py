"""Regression tests for _detect_wb_indicator branch ordering.

The 2026-04-16 first calibration run surfaced wb-002: a claim about
Germany's GDP PER CAPITA was routed to the total GDP indicator
(NY.GDP.MKTP.CD), not the per-capita indicator (NY.GDP.PCAP.CD).
Root cause: _detect_wb_indicator checked 'gdp' before 'per capita',
so a sentence containing 'GDP per capita' matched the total-GDP
branch first and returned early.

The fix reorders the branches so the more specific match runs
first. These tests lock in that ordering so a future refactor
cannot silently regress the calibration finding.
"""


from source_network import _detect_wb_indicator


class TestPerCapitaPrecedence:
    """The fix: per-capita MUST be matched before the broader
    'gdp' branch. Without this, calibration claim wb-002 misroutes."""

    def test_gdp_per_capita_routes_to_per_capita_indicator(self):
        code, label = _detect_wb_indicator(
            "Germany's GDP per capita was $50,000 in 2022.",
            "gdp_per_capita",
        )
        assert code == "NY.GDP.PCAP.CD"
        assert "per capita" in label.lower()

    def test_bare_per_capita_phrase_also_routes_correctly(self):
        code, _label = _detect_wb_indicator(
            "Income per capita in 2022",
            "per_capita_income",
        )
        assert code == "NY.GDP.PCAP.CD"

    def test_plain_gdp_still_routes_to_total(self):
        # Regression guard the other way: reordering must not steal
        # plain GDP claims from the total-GDP indicator.
        code, label = _detect_wb_indicator(
            "France GDP was $2.78 trillion in 2022",
            "gdp",
        )
        assert code == "NY.GDP.MKTP.CD"
        assert "per capita" not in label.lower()

    def test_metric_gdp_without_text_signal_routes_to_total(self):
        # If the metric parameter says gdp but the sentence doesn't
        # mention gdp or per capita, it should still hit total.
        code, _label = _detect_wb_indicator(
            "France economy in 2022",
            "gdp",
        )
        assert code == "NY.GDP.MKTP.CD"

    def test_gross_domestic_product_still_routes_to_total(self):
        # The gdp branch also matches "gross domestic". Verify
        # per-capita reorder didn't break this alternate phrasing.
        code, _label = _detect_wb_indicator(
            "France's gross domestic product reached $2.78T",
            "gdp",
        )
        assert code == "NY.GDP.MKTP.CD"


class TestOtherIndicators:
    """Sanity checks on the non-GDP branches so the reorder didn't
    silently change ordering elsewhere."""

    def test_population(self):
        code, _ = _detect_wb_indicator(
            "Japan population is 125 million", "population"
        )
        assert code == "SP.POP.TOTL"

    def test_life_expectancy(self):
        code, _ = _detect_wb_indicator(
            "Life expectancy in Japan is 84", "lifespan"
        )
        assert code == "SP.DYN.LE00.IN"

    def test_unemployment(self):
        code, _ = _detect_wb_indicator(
            "US unemployment was 3.7%", "unemployment"
        )
        assert code == "SL.UEM.TOTL.ZS"

    def test_no_match_returns_none(self):
        code, label = _detect_wb_indicator(
            "The cat sat on the mat", ""
        )
        assert code is None
        assert label is None
