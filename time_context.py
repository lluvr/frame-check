"""Classify the TIME DIMENSION of a claim so verifiers can route
and filter precisely against time-scoped data sources.

Parallel in spirit to entity_classifier.py. Where that module
answers "what kind of SUBJECT is this claim about", this one
answers "what time scope does this claim refer to". Both are
typed, stable-slug classifiers that the router consults once,
attaches to the ClaimDecomposition, and uses to make correct
routing and filtering decisions rather than inferring them from
regex features of the sentence.

## Why this matters

The first calibration run (2026-04-16) surfaced a Q4-quarterly
claim that returned annual revenue data from SEC EDGAR and got
verdict=contradicted with a 284% diff. See
`calibration/results/2026-04-16-first-run/FINDINGS.md`
category B.1.

The immediate symptom was a regex gap: "fourth quarter 2023"
spelled-out did not match `_TIME_RE`. The deeper failure mode
was bigger: when the SEC filter fell back from 10-Q to 10-K
because quarterly data was unavailable, it used the annual
number as a contradiction target against a claim that was
specifically about a quarter. That is false authority; honest
"unverifiable" beats confident wrong.

A typed TimeContext lets every verifier make the right call:

  * REST Countries (current-data-only) returns `contradicted`
    for HISTORICAL claims rather than matching current against
    the historical value, OR returns `no_data` gracefully so
    consensus doesn't invent disagreement.
  * SEC EDGAR filters 10-Q for QUARTERLY claims and returns
    no_data (not annual) when the quarterly data is absent.
  * World Bank queries a specific ANNUAL year rather than
    relying on end-range bracketing.
  * FRED selects the observation closest to the claim's period
    rather than the most recent available.

## Design commitments

* **Specificity order.** Rules run from tightest (explicit
  "Q[1-4] YYYY") to broadest (fallback CURRENT). Priority is
  encoded in classify_time's if-chain and locked by tests.

* **Numeric extraction.** The year and quarter fields are
  populated as int when unambiguously parseable so downstream
  filters can use them directly. None when the period is
  narrative ("currently", "last year" with no year anchor).

* **Explainable.** Every TimeContext carries a stable reason
  slug suitable for corpus telemetry and audit trails.

* **Honest UNKNOWN.** A sentence with no extractable time
  anchor and no "currently" / "today" marker gets UNKNOWN, not
  CURRENT-by-default. UNKNOWN is first-class.

* **Fast + pure.** Regex and dict lookups only. No network.
  Safe to call once per claim on the hot routing path.
"""

import re
from enum import Enum
from typing import NamedTuple, Optional


class TimePeriodType(str, Enum):
    """The time scope of a claim.

    Values are stable across releases; corpus consumers and UI
    consumers filter on these strings.
    """

    ANNUAL = "annual"          # "in 2023", "fiscal year 2024"
    QUARTERLY = "quarterly"    # "Q4 2023", "fourth quarter 2024"
    RANGE = "range"            # "between 2020 and 2023", "over 2020-2024"
    CURRENT = "current"        # "currently", "today", "as of now"
    HISTORICAL = "historical"  # explicit year more than HISTORICAL_CUTOFF_YEARS ago
    UNKNOWN = "unknown"        # no time anchor present


class TimeContext(NamedTuple):
    """The classification result.

    period_type: which bucket the claim's time scope lands in.
    period_value: the raw matched text ("Q4 2023", "2022", "").
    year: primary year as int, or None when unresolvable.
    quarter: 1-4 for QUARTERLY, or None otherwise.
    year_range: (start, end) for RANGE, otherwise None.
    reason: stable slug describing which rule fired. Values:
        'quarterly_q_notation', 'quarterly_spelled_out',
        'annual_fy_notation', 'annual_bare_year',
        'annual_month_year', 'range_between', 'range_dash',
        'current_marker', 'historical_old_year', 'no_time_anchor',
        'empty_input'.
    """

    period_type: TimePeriodType
    period_value: str
    year: Optional[int]
    quarter: Optional[int]
    year_range: Optional[tuple]  # (int, int)
    reason: str


# ================================================================
# Tunables
# ================================================================

# A year older than this many years from the reference point is
# classified HISTORICAL. The reference point is the current UTC
# year evaluated at call time (not at module load) so long-running
# processes still classify correctly after a year rollover.
HISTORICAL_CUTOFF_YEARS = 5

# Lower bound for "plausible claim year" parsing. The claim text
# often contains digit sequences (version numbers, counts) that
# pass as years if accepted blindly; clamping to a sensible range
# rejects those. A mid-20th-century floor comfortably covers
# financial-data historical claims while rejecting decades-old-
# software-version artifacts like "Python 2020-ABC".
MIN_PLAUSIBLE_YEAR = 1900
MAX_PLAUSIBLE_YEAR = 2100


# ================================================================
# Compiled patterns
# ================================================================

# Quarterly forms with explicit year:
#   Q4 2023, Q4 FY2023, Q4 FY 2023, q4 2023, q-4 2023
_Q_WITH_YEAR = re.compile(
    r"\bQ\s*-?\s*([1-4])\s+(?:FY\s*)?(\d{4})\b",
    re.IGNORECASE,
)

# Quarterly forms spelled out:
#   "fourth quarter 2023", "first quarter of 2024", "Q4"
#   plus year elsewhere.
_Q_SPELLED = re.compile(
    r"\b(first|second|third|fourth)\s+quarter\b(?:\s+(?:of\s+)?(?:FY\s*)?(\d{4}))?",
    re.IGNORECASE,
)

_QUARTER_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4,
}

# Annual forms:
#   "fiscal year 2023", "FY 2023", "FY2023", "in 2023"
_ANNUAL_FY = re.compile(
    r"\b(?:fiscal\s+(?:year\s+)?|FY\s*)(\d{4})\b",
    re.IGNORECASE,
)

# Month + year: "January 2023"
_MONTH_YEAR = re.compile(
    r"\b(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+(\d{4})\b",
    re.IGNORECASE,
)

# Bare four-digit year surrounded by word boundaries. We require
# a year-like context preposition ("in", "during", "for", "as of",
# "ending") before the year so stray digit sequences don't match.
_BARE_YEAR_IN_CONTEXT = re.compile(
    r"\b(?:in|during|for|as\s+of|ending|through|by|since|from|"
    r"throughout|across|reported|posted|announced|disclosed|"
    r"ended)\s+(\d{4})\b",
    re.IGNORECASE,
)

# Range forms: "between 2020 and 2023", "2020-2023", "2020 to 2023"
_RANGE_BETWEEN = re.compile(
    r"\bbetween\s+(\d{4})\s+and\s+(\d{4})\b",
    re.IGNORECASE,
)
_RANGE_DASH = re.compile(
    r"\b(\d{4})\s*(?:-|–|to)\s*(\d{4})\b",
)

# Current-time markers. Phrases explicitly signalling "now" / "today".
_CURRENT_MARKERS = re.compile(
    r"\b(currently|today|presently|at\s+present|as\s+of\s+now|"
    r"right\s+now|these\s+days|nowadays|at\s+this\s+time)\b",
    re.IGNORECASE,
)


# ================================================================
# Classification
# ================================================================

def classify_time(
    sentence: str,
    time_period_hint: Optional[str] = None,
    reference_year: Optional[int] = None,
) -> TimeContext:
    """Classify the time scope of a claim.

    Inputs:
        sentence: full claim sentence. Scanned for time anchors.
        time_period_hint: the raw time_period string extracted by
            upstream decomposition (decomp.time_period). Scanned
            first so explicit decomposition results take priority
            over broader sentence scans. May be empty or None.
        reference_year: the "now" year used to decide HISTORICAL.
            Defaults to the current UTC year evaluated at call
            time. Injectable for deterministic tests.

    Priority order (most specific first):
        1. Quarterly with year (Q4 2023, Q-1 FY2024, q4 2023)
        2. Quarterly spelled out with year nearby (fourth quarter 2023)
        3. Range forms (between 2020 and 2023, 2020-2023)
        4. Annual with FY / fiscal year qualifier
        5. Annual bare year in recognised context ("in 2023")
        6. Annual month-year ("January 2023")
        7. Current markers ("currently", "today")
        8. Historical classification applied to ANNUAL results
           when the year is older than the reference cutoff.
        9. Fallback: UNKNOWN.

    A QUARTERLY result can also be HISTORICAL if its year is old
    enough; the final TimeContext carries BOTH pieces of
    information (period_type=QUARTERLY, quarter=4, year=1990,
    reason='historical_old_year_quarterly' etc.). This keeps
    routing decisions orthogonal: a verifier can decide based on
    period_type first, then adjust on year age.
    """
    from datetime import datetime, timezone

    if not sentence or not sentence.strip():
        if not time_period_hint:
            return TimeContext(
                TimePeriodType.UNKNOWN, "", None, None, None, "empty_input"
            )
        sentence = ""  # fall through with just the hint text

    if reference_year is None:
        reference_year = datetime.now(timezone.utc).year

    # Build the search corpus: the hint text (highest priority,
    # often a tightly-matched period string from decomp) and the
    # full sentence. We search the hint first so decomposition's
    # pre-extracted period takes precedence.
    hint_text = (time_period_hint or "").strip()
    search_texts = [t for t in (hint_text, sentence) if t]

    # ----------------------------------------------------------------
    # 1. Quarterly with explicit year (Q4 2023)
    # ----------------------------------------------------------------
    for text in search_texts:
        m = _Q_WITH_YEAR.search(text)
        if m:
            q = int(m.group(1))
            year = int(m.group(2))
            if not (MIN_PLAUSIBLE_YEAR <= year <= MAX_PLAUSIBLE_YEAR):
                continue
            is_historical = (reference_year - year) > HISTORICAL_CUTOFF_YEARS
            return TimeContext(
                period_type=(
                    TimePeriodType.HISTORICAL if is_historical
                    else TimePeriodType.QUARTERLY
                ),
                period_value=m.group(0),
                year=year,
                quarter=q,
                year_range=None,
                reason=(
                    "historical_old_year_quarterly" if is_historical
                    else "quarterly_q_notation"
                ),
            )

    # ----------------------------------------------------------------
    # 2. Quarterly spelled out (fourth quarter 2023)
    # ----------------------------------------------------------------
    for text in search_texts:
        m = _Q_SPELLED.search(text)
        if m:
            word = m.group(1).lower()
            year_str = m.group(2)
            q = _QUARTER_WORDS.get(word)
            if q is None:
                continue
            year = None
            if year_str:
                y = int(year_str)
                if MIN_PLAUSIBLE_YEAR <= y <= MAX_PLAUSIBLE_YEAR:
                    year = y
            if year is None:
                # No year anchor in the spelled-out form; scan the
                # surrounding sentence for a four-digit year. Keep
                # the claim classified QUARTERLY even without year
                # so downstream SEC can decide based on the quarter
                # alone if it must.
                y_match = re.search(r"\b(\d{4})\b", sentence)
                if y_match:
                    yc = int(y_match.group(1))
                    if MIN_PLAUSIBLE_YEAR <= yc <= MAX_PLAUSIBLE_YEAR:
                        year = yc
            is_historical = (
                year is not None
                and (reference_year - year) > HISTORICAL_CUTOFF_YEARS
            )
            return TimeContext(
                period_type=(
                    TimePeriodType.HISTORICAL if is_historical
                    else TimePeriodType.QUARTERLY
                ),
                period_value=m.group(0),
                year=year,
                quarter=q,
                year_range=None,
                reason=(
                    "historical_old_year_quarterly" if is_historical
                    else "quarterly_spelled_out"
                ),
            )

    # ----------------------------------------------------------------
    # 3. Range forms
    # ----------------------------------------------------------------
    for text in search_texts:
        m = _RANGE_BETWEEN.search(text)
        if m:
            y1, y2 = int(m.group(1)), int(m.group(2))
            if all(MIN_PLAUSIBLE_YEAR <= y <= MAX_PLAUSIBLE_YEAR for y in (y1, y2)):
                start, end = sorted((y1, y2))
                return TimeContext(
                    period_type=TimePeriodType.RANGE,
                    period_value=m.group(0),
                    year=None,
                    quarter=None,
                    year_range=(start, end),
                    reason="range_between",
                )
    for text in search_texts:
        m = _RANGE_DASH.search(text)
        if m:
            y1, y2 = int(m.group(1)), int(m.group(2))
            # Guard: a dash-separated pair looking like "2020-2023"
            # is a range; "2020" alone or "2020-01-15" (date) is not.
            # The range regex already requires two 4-digit groups
            # with no more digits; the plausibility bounds filter
            # out junk.
            if all(MIN_PLAUSIBLE_YEAR <= y <= MAX_PLAUSIBLE_YEAR for y in (y1, y2)):
                start, end = sorted((y1, y2))
                return TimeContext(
                    period_type=TimePeriodType.RANGE,
                    period_value=m.group(0),
                    year=None,
                    quarter=None,
                    year_range=(start, end),
                    reason="range_dash",
                )

    # ----------------------------------------------------------------
    # 4. Annual with FY / fiscal year qualifier
    # ----------------------------------------------------------------
    for text in search_texts:
        m = _ANNUAL_FY.search(text)
        if m:
            y = int(m.group(1))
            if not (MIN_PLAUSIBLE_YEAR <= y <= MAX_PLAUSIBLE_YEAR):
                continue
            is_historical = (reference_year - y) > HISTORICAL_CUTOFF_YEARS
            return TimeContext(
                period_type=(
                    TimePeriodType.HISTORICAL if is_historical
                    else TimePeriodType.ANNUAL
                ),
                period_value=m.group(0),
                year=y,
                quarter=None,
                year_range=None,
                reason=(
                    "historical_old_year" if is_historical
                    else "annual_fy_notation"
                ),
            )

    # ----------------------------------------------------------------
    # 5. Annual bare year with year-like preposition context
    # ----------------------------------------------------------------
    for text in search_texts:
        m = _BARE_YEAR_IN_CONTEXT.search(text)
        if m:
            y = int(m.group(1))
            if not (MIN_PLAUSIBLE_YEAR <= y <= MAX_PLAUSIBLE_YEAR):
                continue
            is_historical = (reference_year - y) > HISTORICAL_CUTOFF_YEARS
            return TimeContext(
                period_type=(
                    TimePeriodType.HISTORICAL if is_historical
                    else TimePeriodType.ANNUAL
                ),
                period_value=m.group(0),
                year=y,
                quarter=None,
                year_range=None,
                reason=(
                    "historical_old_year" if is_historical
                    else "annual_bare_year"
                ),
            )

    # ----------------------------------------------------------------
    # 6. Annual month + year
    # ----------------------------------------------------------------
    for text in search_texts:
        m = _MONTH_YEAR.search(text)
        if m:
            y = int(m.group(2))
            if not (MIN_PLAUSIBLE_YEAR <= y <= MAX_PLAUSIBLE_YEAR):
                continue
            is_historical = (reference_year - y) > HISTORICAL_CUTOFF_YEARS
            return TimeContext(
                period_type=(
                    TimePeriodType.HISTORICAL if is_historical
                    else TimePeriodType.ANNUAL
                ),
                period_value=m.group(0),
                year=y,
                quarter=None,
                year_range=None,
                reason=(
                    "historical_old_year" if is_historical
                    else "annual_month_year"
                ),
            )

    # ----------------------------------------------------------------
    # 7. Current markers
    # ----------------------------------------------------------------
    for text in search_texts:
        m = _CURRENT_MARKERS.search(text)
        if m:
            return TimeContext(
                period_type=TimePeriodType.CURRENT,
                period_value=m.group(0),
                year=reference_year,
                quarter=None,
                year_range=None,
                reason="current_marker",
            )

    # ----------------------------------------------------------------
    # 8. Fallback: UNKNOWN
    # ----------------------------------------------------------------
    return TimeContext(
        period_type=TimePeriodType.UNKNOWN,
        period_value="",
        year=None,
        quarter=None,
        year_range=None,
        reason="no_time_anchor",
    )
