"""Regression tests for numerical claim extraction.

The 2026-04-16 first calibration run surfaced that
"Wakanda has a population of 6 million" extracted zero claims
(FINDINGS.md Category C). Root cause: extract_numbers_for_matching
required multi-digit bare integers, and no pattern handled the
digit+spelled-scale shape outside a currency context.

A scaled_integer pattern was added with a scale-word multiplier.
These tests lock in:
  - Positive coverage: the previously-missed shapes extract
    with correct magnitude (6 million -> 6_000_000, not 6)
  - Regression safety: the existing dollar pattern still wins
    for "$6 billion" (no double-extraction)
  - False-positive resistance: non-claim uses of scale words
    ("millions of readers", "A million years ago") do NOT
    extract

Every claim against the pattern set should have one of these
tests exercising it. If the pattern is ever rewritten, this
file tells the next engineer what the contract is.
"""

from clarethium_measure import extract_numbers_for_matching
from claim_analysis import analyze_claims


# ================================================================
# Core positive: spelled-scale extraction with multiplier
# ================================================================

class TestScaledIntegerExtraction:

    def test_single_digit_plus_million(self):
        nums = extract_numbers_for_matching("Wakanda has a population of 6 million.")
        scaled = [n for n in nums if n["type"] == "integer"]
        assert scaled, "6 million should extract as a scaled integer"
        assert scaled[0]["value"] == "6000000"

    def test_decimal_plus_million(self):
        nums = extract_numbers_for_matching("Germany population is 83.2 million people.")
        vals = [n["value"] for n in nums if n["type"] == "integer"]
        assert "83200000" in vals

    def test_billion(self):
        nums = extract_numbers_for_matching("The company has 2 billion users worldwide.")
        vals = [n["value"] for n in nums if n["type"] == "integer"]
        assert "2000000000" in vals

    def test_thousand(self):
        nums = extract_numbers_for_matching("Revenue grew to 500 thousand dollars last quarter.")
        vals = [n["value"] for n in nums if n["type"] == "integer"]
        assert "500000" in vals

    def test_trillion(self):
        nums = extract_numbers_for_matching("US debt topped 34 trillion in 2024.")
        vals = [n["value"] for n in nums if n["type"] == "integer"]
        assert "34000000000000" in vals

    def test_decimal_trillion(self):
        nums = extract_numbers_for_matching("Global GDP was 100.5 trillion in 2024.")
        vals = [n["value"] for n in nums if n["type"] == "integer"]
        assert "100500000000000" in vals


# ================================================================
# Regression: existing patterns still win where appropriate
# ================================================================

class TestExistingPatternsPreserved:
    """The dollar pattern (which runs first) must still win for
    currency-prefixed claims. Adding scaled_integer MUST NOT cause
    'NVIDIA revenue $60.9 billion' to produce two numbers
    (60.9 as dollar AND 60900000000 as integer)."""

    def test_dollar_plus_billion_stays_as_dollar_only(self):
        nums = extract_numbers_for_matching("NVIDIA revenue was $60.9 billion.")
        # The dollar pattern claims the range, scaled_integer gets blocked
        by_type = {n["type"] for n in nums}
        assert "dollar" in by_type
        # Exactly one extraction, not two
        assert len(nums) == 1

    def test_dollar_plus_million_stays_as_dollar_only(self):
        nums = extract_numbers_for_matching("Apple reported $383 million in services revenue.")
        assert len(nums) == 1
        assert nums[0]["type"] == "dollar"

    def test_mid_number_digits_not_double_matched(self):
        # "166 million" must extract as 166_000_000 once, NOT also
        # as "66 million" = 66_000_000.
        nums = extract_numbers_for_matching("The company has 166 million users.")
        vals = [n["value"] for n in nums if n["type"] == "integer"]
        assert "166000000" in vals
        assert "66000000" not in vals


# ================================================================
# Negative: scale words without digit prefix must not extract
# ================================================================

class TestNoFalsePositives:

    def test_plural_scale_word_no_extract(self):
        nums = extract_numbers_for_matching("Millions of readers enjoyed the book.")
        # No digit before "millions", so no scaled_integer match.
        scaled = [n for n in nums if n["type"] == "integer"]
        assert scaled == []

    def test_indefinite_article_no_extract(self):
        # "a million" has 'a' instead of a digit.
        nums = extract_numbers_for_matching("A million years ago dinosaurs roamed.")
        scaled = [n for n in nums if n["type"] == "integer"]
        assert scaled == []

    def test_millennium_does_not_match(self):
        # The word "millennium" shares a prefix with "million" but
        # is not captured because there is no digit before it.
        nums = extract_numbers_for_matching("The new millennium began in 2000.")
        # "2000" extracts as integer (it's a 4-digit number), but
        # "millennium" itself does not produce a scaled match.
        # Pattern safety is what this test locks in.
        vals = [n["value"] for n in nums]
        # No value with million-scale multiplier in the sentence
        assert "1000000" not in vals

    def test_scale_word_inside_longer_word_no_extract(self):
        # "millionth", "millionaire" etc. must not trigger extraction.
        for text in ("The millionth visitor", "She is a millionaire"):
            nums = extract_numbers_for_matching(text)
            scaled = [n for n in nums if n["type"] == "integer"]
            assert not scaled, (
                f"Unexpected scaled_integer extraction on {text!r}"
            )


# ================================================================
# End-to-end: analyze_claims pipeline
# ================================================================

class TestAnalyzeClaimsPipeline:
    """End-to-end coverage: the synthetic-claims path from
    analyze_claims must build a claim for each previously-missed
    shape. This is the path the /profile endpoint and the
    calibration harness actually exercise."""

    def test_wakanda_now_extracts(self):
        """The specific FINDINGS.md Category C case."""
        r = analyze_claims("Wakanda has a population of 6 million.")
        assert len(r["claims"]) >= 1

    def test_small_digit_population_extracts(self):
        # Historical case that motivated the fix: single-digit
        # integer + scale word.
        r = analyze_claims("The city of Prague has 1.3 million residents in 2023.")
        assert len(r["claims"]) >= 1

    def test_large_digit_scale_still_works(self):
        # Sanity: the pre-fix working case still works.
        r = analyze_claims("Japan has a population of 500 million.")
        assert len(r["claims"]) >= 1
