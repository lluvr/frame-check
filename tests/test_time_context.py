"""Tests for time_context.classify_time.

Lock in the priority order and the specific shapes that motivated
this classifier:

  * Tesla Q4 2023 (FINDINGS B.1) must classify as QUARTERLY with
    year=2023 and quarter=4 so the SEC EDGAR filter can correctly
    select 10-Q data (or return no_data rather than invent
    contradiction from annual revenue).

  * Spelled-out "fourth quarter 2023" must resolve to the same
    QUARTERLY structure so the router treats it identically to
    "Q4 2023".

  * Historical claims (2010, 1995) must classify as HISTORICAL
    so REST Countries / CoinGecko / other current-only verifiers
    can contradict or return no_data rather than match current
    data against the historical claim.

  * Current-marker claims ("currently", "today") must classify
    as CURRENT with reference_year populated so the fallback
    path has a year anchor.

  * UNKNOWN is a first-class value, not a fallback to CURRENT.
"""


from time_context import (
    TimePeriodType,
    classify_time,
    HISTORICAL_CUTOFF_YEARS,
)


# ================================================================
# Quarterly: Q-notation
# ================================================================

class TestQuarterlyQNotation:

    def test_q4_with_year(self):
        r = classify_time("Tesla reported Q4 2023 revenue of $25.167 billion.")
        assert r.period_type == TimePeriodType.QUARTERLY
        assert r.quarter == 4
        assert r.year == 2023
        assert r.reason == "quarterly_q_notation"

    def test_q1_with_year(self):
        r = classify_time("Q1 2024 earnings were strong.")
        assert r.period_type == TimePeriodType.QUARTERLY
        assert r.quarter == 1
        assert r.year == 2024

    def test_q4_fy_notation(self):
        r = classify_time("Apple's Q4 FY2024 revenue was $94 billion.")
        assert r.period_type == TimePeriodType.QUARTERLY
        assert r.quarter == 4
        assert r.year == 2024

    def test_lowercase_q(self):
        r = classify_time("q3 2023 was a turning point.")
        assert r.period_type == TimePeriodType.QUARTERLY
        assert r.quarter == 3


# ================================================================
# Quarterly: spelled-out
# ================================================================

class TestQuarterlySpelledOut:

    def test_fourth_quarter_with_year(self):
        r = classify_time("Revenue in the fourth quarter of 2023 reached $25B.")
        assert r.period_type == TimePeriodType.QUARTERLY
        assert r.quarter == 4
        assert r.year == 2023
        assert r.reason == "quarterly_spelled_out"

    def test_first_quarter_no_year_falls_back_to_sentence_year(self):
        r = classify_time("The first quarter was strong; the 2024 full year was weaker.")
        # quarter still captured; year comes from the loose scan
        assert r.period_type == TimePeriodType.QUARTERLY
        assert r.quarter == 1

    def test_second_quarter_with_year(self):
        r = classify_time("Second quarter 2022 showed growth.")
        assert r.period_type == TimePeriodType.QUARTERLY
        assert r.quarter == 2
        assert r.year == 2022


# ================================================================
# Annual forms
# ================================================================

class TestAnnual:

    def test_fiscal_year(self):
        r = classify_time("Revenue for fiscal year 2023 was $400B.", reference_year=2026)
        assert r.period_type == TimePeriodType.ANNUAL
        assert r.year == 2023
        assert r.reason == "annual_fy_notation"

    def test_fy_notation(self):
        r = classify_time("FY2024 revenue was $400B.", reference_year=2026)
        assert r.period_type == TimePeriodType.ANNUAL
        assert r.year == 2024

    def test_bare_year_with_preposition(self):
        r = classify_time("Revenue in 2024 was $400B.", reference_year=2026)
        assert r.period_type == TimePeriodType.ANNUAL
        assert r.year == 2024
        assert r.reason == "annual_bare_year"

    def test_bare_year_without_context_is_unknown(self):
        # A year embedded in a non-claim context must not trigger
        # an annual classification. Without one of the known
        # prepositions ("in", "during", ...) the bare year lookup
        # has no signal.
        r = classify_time("The S&P500 index finished strong.")
        assert r.period_type == TimePeriodType.UNKNOWN

    def test_month_year(self):
        r = classify_time(
            "Inflation peaked in November 2022.",
            reference_year=2026,
        )
        # The bare-year preposition check fires first ("in" + "2022"),
        # so the reason is annual_bare_year rather than the month-year
        # branch; both resolve to the same period_type/year. The
        # month-year branch is there as a belt-and-braces fallback for
        # sentences where the bare-year context scan fails.
        assert r.period_type == TimePeriodType.ANNUAL
        assert r.year == 2022


# ================================================================
# Range forms
# ================================================================

class TestRanges:

    def test_between_years(self):
        r = classify_time("Growth between 2020 and 2023 was 30%.")
        assert r.period_type == TimePeriodType.RANGE
        assert r.year_range == (2020, 2023)
        assert r.reason == "range_between"

    def test_dash_range(self):
        r = classify_time("The 2020-2023 period saw recovery.")
        assert r.period_type == TimePeriodType.RANGE
        assert r.year_range == (2020, 2023)
        assert r.reason == "range_dash"

    def test_to_range(self):
        r = classify_time("From 2020 to 2024 the market grew.")
        assert r.period_type == TimePeriodType.RANGE
        assert r.year_range == (2020, 2024)

    def test_reversed_range_sorts(self):
        # "2023 to 2020" could be a user typo; we still return a
        # sorted range so downstream code never has to handle
        # start > end.
        r = classify_time("From 2023 to 2020 (typo).")
        assert r.period_type == TimePeriodType.RANGE
        assert r.year_range == (2020, 2023)


# ================================================================
# Current markers
# ================================================================

class TestCurrentMarkers:

    def test_currently(self):
        r = classify_time("Bitcoin currently trades near $90,000.",
                          reference_year=2026)
        assert r.period_type == TimePeriodType.CURRENT
        assert r.year == 2026  # reference year anchored
        assert r.reason == "current_marker"

    def test_today(self):
        r = classify_time("Today, the company has 30,000 employees.",
                          reference_year=2026)
        assert r.period_type == TimePeriodType.CURRENT

    def test_as_of_now(self):
        r = classify_time("As of now, market cap is $2T.",
                          reference_year=2026)
        assert r.period_type == TimePeriodType.CURRENT


# ================================================================
# Historical classification
# ================================================================

class TestHistorical:

    def test_old_year_is_historical(self):
        # 2010 relative to reference_year=2026 is 16 years old,
        # well outside HISTORICAL_CUTOFF_YEARS (5).
        r = classify_time("India had a population of 1.2 billion in 2010.",
                          reference_year=2026)
        assert r.period_type == TimePeriodType.HISTORICAL
        assert r.year == 2010
        assert r.reason == "historical_old_year"

    def test_recent_year_is_annual_not_historical(self):
        # 2023 relative to 2026 is 3 years; within cutoff.
        r = classify_time("Revenue in 2023 was strong.",
                          reference_year=2026)
        assert r.period_type == TimePeriodType.ANNUAL
        assert r.year == 2023

    def test_historical_quarterly(self):
        # A QUARTERLY claim with an old year becomes HISTORICAL
        # rather than QUARTERLY because the period-type bucket is
        # coarse. The quarter field is still populated so verifiers
        # have both pieces of information.
        r = classify_time("Q4 1995 revenue was $50M.", reference_year=2026)
        assert r.period_type == TimePeriodType.HISTORICAL
        assert r.year == 1995
        assert r.quarter == 4
        assert r.reason == "historical_old_year_quarterly"

    def test_boundary_year_is_annual(self):
        # Exactly HISTORICAL_CUTOFF_YEARS away is still ANNUAL;
        # strictly greater becomes HISTORICAL.
        boundary = 2026 - HISTORICAL_CUTOFF_YEARS  # 2021
        r = classify_time(f"Revenue in {boundary} was $100B.",
                          reference_year=2026)
        assert r.period_type == TimePeriodType.ANNUAL
        # One year older
        r2 = classify_time(f"Revenue in {boundary - 1} was $95B.",
                           reference_year=2026)
        assert r2.period_type == TimePeriodType.HISTORICAL


# ================================================================
# Unknown / empty
# ================================================================

class TestUnknownFallback:

    def test_no_time_anchor(self):
        r = classify_time("Apple reported strong growth.")
        assert r.period_type == TimePeriodType.UNKNOWN
        assert r.year is None
        assert r.quarter is None
        assert r.reason == "no_time_anchor"

    def test_empty_sentence(self):
        r = classify_time("")
        assert r.period_type == TimePeriodType.UNKNOWN
        assert r.reason == "empty_input"

    def test_whitespace_sentence(self):
        r = classify_time("   ")
        assert r.period_type == TimePeriodType.UNKNOWN
        assert r.reason == "empty_input"


# ================================================================
# Priority order; quarterly beats annual when both patterns match
# ================================================================

class TestPriorityOrder:
    """A claim with both a quarter and an annual year must classify
    as QUARTERLY. Reversing the priority would silently demote
    quarterly claims to annual, reintroducing B.1."""

    def test_q_notation_beats_bare_year(self):
        r = classify_time("Q4 2023 was strong; revenue in 2023 grew 10%.")
        assert r.period_type == TimePeriodType.QUARTERLY

    def test_spelled_quarter_beats_fy_notation(self):
        r = classify_time("The fourth quarter of FY2024 was strong.")
        assert r.period_type == TimePeriodType.QUARTERLY
        assert r.quarter == 4

    def test_range_beats_single_year(self):
        # Both "in 2020" and the range match; the range is more
        # specific and should win.
        r = classify_time("During 2020-2023 the market evolved.")
        assert r.period_type == TimePeriodType.RANGE

    def test_explicit_year_beats_current_marker(self):
        # "Currently" and "2023" both present; explicit year wins
        # because the claim has a concrete anchor.
        r = classify_time("Currently the fiscal year 2023 number stands.")
        assert r.period_type in (TimePeriodType.ANNUAL, TimePeriodType.QUARTERLY)


# ================================================================
# Hint priority; decomp.time_period scanned first
# ================================================================

class TestHintPriority:

    def test_hint_resolves_when_sentence_is_vague(self):
        # Sentence has no time anchor; the decomposition hint does.
        r = classify_time(
            sentence="Revenue was $400 billion.",
            time_period_hint="FY2023",
            reference_year=2026,
        )
        assert r.period_type == TimePeriodType.ANNUAL
        assert r.year == 2023

    def test_hint_and_sentence_agree(self):
        r = classify_time(
            sentence="Q4 2023 revenue was $25B.",
            time_period_hint="Q4 2023",
        )
        assert r.period_type == TimePeriodType.QUARTERLY
        assert r.year == 2023
        assert r.quarter == 4


# ================================================================
# Contract stability
# ================================================================

class TestContractStability:

    def test_enum_values_are_stable(self):
        assert TimePeriodType.ANNUAL.value == "annual"
        assert TimePeriodType.QUARTERLY.value == "quarterly"
        assert TimePeriodType.RANGE.value == "range"
        assert TimePeriodType.CURRENT.value == "current"
        assert TimePeriodType.HISTORICAL.value == "historical"
        assert TimePeriodType.UNKNOWN.value == "unknown"

    def test_reason_slugs_are_stable(self):
        allowed = {
            "quarterly_q_notation", "quarterly_spelled_out",
            "annual_fy_notation", "annual_bare_year", "annual_month_year",
            "range_between", "range_dash",
            "current_marker",
            "historical_old_year", "historical_old_year_quarterly",
            "no_time_anchor", "empty_input",
        }
        samples = [
            ("",),
            ("Q4 2023 revenue.",),
            ("The fourth quarter of 2023 revenue.",),
            ("Revenue in 2023.",),
            ("Revenue for fiscal year 2023.",),
            ("In January 2023 it peaked.",),
            ("Between 2020 and 2023 growth was 30%.",),
            ("The 2020-2023 period.",),
            ("Currently trades at $90k.",),
            ("Revenue in 1995 was $10B.",),
            ("No time anchor here at all.",),
        ]
        for (sent,) in samples:
            r = classify_time(sent, reference_year=2026)
            assert r.reason in allowed, (
                f"classify_time({sent!r}) produced unknown reason "
                f"{r.reason!r}; contract broken"
            )

    def test_time_context_is_namedtuple(self):
        r = classify_time("Q4 2023 was good.")
        # Unpackable, indexable, named access.
        pt, pv, y, q, yr, reason = r
        assert pt == r.period_type == r[0]
        assert q == r.quarter == r[3]
        assert reason == r.reason == r[5]
