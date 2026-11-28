"""
Source Network: Multi-source claim verification.

Tier 1 of the FrameCheck verification cascade. Routes claims to
authoritative data sources (Wikipedia, World Bank,
CoinGecko), matches claim values against source data with context
awareness, and produces the combined verdict verdicts.

Zero LLM. All computational. Free or near-free API calls.

Architecture:
  1. Decompose the claim (subject, metric, value, time, type)
  2. Route to 2-3 sources in parallel
  3. Context-aware matching against source data
  4. The combined verdict across sources -> verdict
"""

import os
import re
import datetime
import json
import sys
import threading
import time
import urllib.request
import urllib.parse
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as _FuturesTimeoutError
from dataclasses import dataclass, field, replace
from typing import Optional

from claim_analysis import _own_sentence
from claim_reader import figure_key, read_figures
from prose import plain_prose


# ================================================================
# Per-request operational counters
# ================================================================
#
# A counter is needed for the actual number of Brave Search queries
# issued during a verification run for the corpus monitoring path.
# The previous implementation used a
# threading.local sidecar, which broke under FastAPI's async
# dispatch: verify_claims_source_network runs on the analysis
# thread pool worker, but the corpus monitoring read happens on
# the event loop thread after the awaited future resolves, so
# the read always returned the threading.local default of 0.
#
# The fix: callers that need the count pass an `out_state` dict;
# verify_claims_source_network fills `out_state["brave_query_count"]`
# before returning. The dict travels back with the result on
# the same execution context that called the verification
# function, so the value is always observable. Callers that do
# not need the count omit `out_state` and pay nothing.


# ================================================================
# Data structures
# ================================================================

@dataclass
class ClaimDecomposition:
    """Structured decomposition of a claim."""
    subject: str = ""           # "Hyperion tree", "Apple Inc.", "France"
    metric: str = ""            # "height", "revenue", "population"
    value: float = 0.0          # Normalized to base units
    raw_value: str = ""         # Original string: "$383B", "116.22"
    unit: str = ""              # "USD", "meters", "count", "percent"
    time_period: str = ""       # "2023", "Q4 2024", ""
    # The year came from an earlier sentence. It can confirm a figure, but
    # refuting one needs the sentence itself to point back at that year.
    year_inherited: bool = False
    # The inherited year is the only one the text has named so far.
    year_sole: bool = False
    # The year is written right beside the figure, in a sentence giving
    # several figures each its own year: "5.5% in 2022 and 5.1% in 2023".
    year_own: bool = False
    # "(NYSE: MSM)": the tickers the document declares for itself.
    doc_tickers: str = ""
    # "fiscal 2024 ended February 1, 2025": the year and the date it ended,
    # as "2024|2025-02-01". Companies name fiscal years differently; the
    # text's own date says which period it means.
    fiscal_end: str = ""
    # The year the document names most often, when one leads. A year the
    # sentence does not name, and the document is not mainly about, is a
    # guess.
    doc_main_year: str = ""
    # The whole sentence, when the claim is one clause of it.
    full_sentence: str = ""
    # The document points at the US economy and names no other country.
    doc_is_us: bool = False
    # The document names no country at all: FRED may confirm, never refute.
    doc_no_country: bool = False
    # How often the document names each country ({"Mexico": 3}). A refutation
    # needs its country named in the figure's sentence or at least twice.
    doc_country_counts: dict = field(default_factory=dict)
    # Where the figure is written: its paragraph, and the country labelling its
    # section ("## Peru", "**Peru.**"). None when built without a document.
    place_paragraph: Optional[str] = None
    place_label: str = ""
    # Every country the document names, currency words not ("US dollars").
    place_doc_countries: frozenset = frozenset()
    # The country the document opens on ("" for a comparison).
    place_doc_lead: str = ""
    # The document is about a country's economy (names GDP or the economy):
    # bare "Growth was 1.2% in 2016" there is GDP growth (confirm-only).
    doc_about_economy: bool = False
    # A weaker binding may confirm a figure, never call it wrong.
    confirm_only: bool = False
    # The document says its figures are annual averages ("Here are the annual
    # averages you asked for"), so a rate in it is not December's.
    doc_says_averages: bool = False
    # The metric came from the claim reader; the sentence names none.
    metric_inferred: bool = False
    # The subject came from context in a document naming several entities, so
    # which one the sentence means is a guess. It may confirm, not refute.
    subject_ambiguous: bool = False
    claim_type: str = "direct"  # "direct", "derived", "projection"
    sentence: str = ""          # Full claim sentence
    heading: str = ""           # Section heading
    is_segment: bool = False    # True for sub-component claims (segment,
                                # product line, region) that consolidated
                                # data sources like SEC EDGAR's
                                # companyconcept API cannot verify.
    # Entity-type classification attached at routing time by
    # _classify_and_route. Kept on the decomposition so the
    # SourceNetworkResult builder, display formatter, and corpus
    # event emitter can read it without re-running the classifier.
    # Values are the .value of EntityType from entity_classifier
    # ("company", "country", "crypto_asset", "unknown"). Empty
    # string before routing runs.
    entity_type: str = ""
    entity_canonical: str = ""
    entity_classification_reason: str = ""
    # Time-context classification attached at routing time by
    # _classify_and_route (time_context.classify_time). Verifiers
    # use time_period_type to gate decisions (e.g. SEC EDGAR
    # returns no_data for QUARTERLY claims when 10-Q data is
    # unavailable rather than falling back to annual; REST
    # Countries returns no_data for HISTORICAL claims rather than
    # matching current population against the historical value).
    # The time_period field above is the raw extracted string;
    # these fields are the typed result. Values are the .value
    # of TimePeriodType from time_context ("annual", "quarterly",
    # "range", "current", "historical", "unknown") plus the
    # parsed numeric fields.
    time_period_type: str = ""
    time_year: int | None = None
    time_quarter: int | None = None
    time_year_range: tuple | None = None
    time_classification_reason: str = ""


@dataclass
class SourceResult:
    """Result from a single source query."""
    source_name: str            # "Wikipedia", "World Bank", "CoinGecko"
    source_url: str = ""        # Direct link to the source
    source_value: float = 0.0   # The value the source provides
    source_text: str = ""       # Context around the matched value
    match_type: str = "no_data" # "exact", "close", "contradicted", "no_data"
    difference_pct: float = 0.0 # % difference from claim
    confidence: float = 0.0     # 0.0-1.0
    # Wall-clock milliseconds the verifier spent producing this
    # result, stamped by _timed_verify at the dispatch site. The
    # monitoring worker reads this field directly off each
    # SourceResult to populate the per-source latency histogram.
    # Default 0 means the
    # caller did not go through the timed dispatch path (e.g.,
    # internal fixtures in tests); existing non-corpus callers
    # ignore the field, which keeps the change non-breaking.
    # Phase 1.6e item 4. Stored as int ms because the Tier B
    # schema uses integer milliseconds everywhere else.
    query_latency_ms: int = 0
    # True when this came from a web search snippet. A page mentioning
    # the same digits is a lead for the reader to follow, not a check:
    # _consensus never lets it decide a verdict.
    is_web_search: bool = False
    # A structured source holds the value and it differs, though not by
    # enough to call the claim wrong. Text matches cannot then confirm it.
    disagrees: bool = False
    # The source's figure differs and that source has not earned the right
    # to call the claim wrong. The figure stays so it can be shown. The
    # claim is not a disagreement.
    withheld_refute: bool = False


# The identity path's own SEC row earned refute: those sealed verdicts
# contradicted no true figure. verify_sec_edgar did not, so it withholds
# its own disagreements below and keeps the filed figure. "This document"
# is the document's own arithmetic. Wikipedia's match is settled in
# _consensus, which already refuses to let a page decide. Every other
# source may confirm. It may not call a figure wrong until a fresh sealed
# set earns that. Rules fitted on one open set did not carry to the next.
# The World Bank earned it on v32 (2026-11-28, pre-registered, scored once:
# 0 of 2,224 true figures contradicted, 169 false caught), and refutes only
# where the figure's place is written (_place_written); v26-v31 each failed
# first and are recorded in the maintainers' evaluation record.
_REFUTE_EARNED = frozenset({"SEC Filing", "This document", "Wikipedia", "World Bank"})
# Measurement only: REFUTE_TRIAL="World Bank,FRED" lets those sources refute in
# this process, so a harness can score what they would gain and cost before a
# fresh set decides. Production never sets it; the default is the set above.
_REFUTE_TRIAL = frozenset(
    name.strip() for name in os.environ.get("REFUTE_TRIAL", "").split(",") if name.strip()
)


def _may_refute(source_name):
    return source_name in _REFUTE_EARNED or source_name in _REFUTE_TRIAL


def _withhold_refute(result):
    """Keep the figure. Do not leave a disagreement for the combined verdict to announce."""
    result.match_type = "no_data"
    result.withheld_refute = True
    result.disagrees = True
    result.confidence = 0.0
    return result


def _hold_unearned_refute(result):
    """Keep the source's figure and do not announce a disagreement.

    A true figure called wrong is the worst error this check can make.
    Only a source that has earned refute may do it. A web page never
    decides a verdict; leaving it alone keeps the page named as a lead.
    """
    if result is None or result.match_type != "contradicted":
        return result
    if result.is_web_search or _may_refute(result.source_name):
        return result
    return _withhold_refute(result)


def _timed_verify(fn, decomp):
    """Run a per-source verifier and stamp the wall-clock
    latency on the returned SourceResult.

    Phase 1.6e item 4. The monitoring worker reads
    query_latency_ms directly off each SourceResult to populate
    Section 5.3's per-source latency histogram. The wrapper uses
    perf_counter for monotonic wall-clock timing (right signal
    for network budget, wrong signal for CPU attribution, which
    is fine here because the actual source calls are I/O bound).
    A verifier that returns None (no match) is not stamped; the
    caller drops None before appending. Module-level so the unit
    test can exercise it without going through the full
    verify_claims_source_network call graph.
    """
    start = time.perf_counter()
    result = fn(decomp)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    if result is not None:
        result.query_latency_ms = elapsed_ms
        # A weaker binding may confirm, never refute, whichever source answers
        # (review 2026-11-27: only the World Bank path honoured the flag).
        if getattr(decomp, "confirm_only", False) and result.match_type == "contradicted":
            result.match_type = "no_data"
            result.confidence = 0.0
    return result


# ================================================================
# Unit normalization
# ================================================================

_SCALE_SUFFIXES = {
    "T": 1e12, "trillion": 1e12,
    "B": 1e9, "billion": 1e9, "bn": 1e9,
    "M": 1e6, "million": 1e6, "mn": 1e6, "mil": 1e6,
    "K": 1e3, "thousand": 1e3, "k": 1e3,
}

# Scale words in sentence context. Single-letter suffixes (T, B, M, K)
# only match when directly attached to the number (no space) to avoid
# false positives with units like "m" (meters), "m" (minutes).
_SCALE_RE = re.compile(
    r'(\d+(?:[.,]\d+)?)\s+'
    r'(trillion|billion|million|thousand|bn|mn|mil)\b',
    re.IGNORECASE
)

# For raw value suffixes (attached directly: "$383B", "27.4T", "$60.9bn")
_RAW_SUFFIX_RE = re.compile(r'(?:bn|mn|[TBMKk])$', re.IGNORECASE)


def normalize_value(raw, sentence=""):
    """Normalize a claim value to base units.

    "$27.4 trillion" -> 27_400_000_000_000
    "$383B" -> 383_000_000_000
    "68 million" -> 68_000_000
    "116.22" -> 116.22
    "24.3%" -> 24.3 (kept as percentage for matching)
    """
    # Clean the raw value: strip currency symbols, qualifiers, units
    cleaned = raw.strip()
    # Strip common qualifiers that precede numbers
    cleaned = re.sub(
        r'^(?:approximately|approx\.?|roughly|about|around|nearly|'
        r'over|under|more than|less than|up to|at least)\s+',
        '', cleaned, flags=re.IGNORECASE,
    )
    # Strip currency symbols (USD and non-USD) and the
    # approximate marker. The non-USD symbols were missing
    # before Phase 1.6e, which caused normalize_value to
    # return 0.0 for inputs like "€30.9B" because float()
    # could not parse the leftover "€". Every non-USD
    # monetary claim was structurally unverifiable as a
    # result (value=0 triggers the early-return in
    # _verify_one). The symbol set matches
    # comparison._CURRENCY_SYMBOLS.
    cleaned = cleaned.lstrip("$€£¥₹~").rstrip("%")
    # "$(52.5)M": a statement's loss. The sign is applied where it matters.
    cleaned = re.sub(r'^\((\s*\d[\d,.]*\s*)\)', r'\1', cleaned)
    cleaned = cleaned.replace(",", "")
    # A duration: "83 years" is 83. Reaching float() with the unit attached
    # returned 0, which skips the claim, so no life expectancy was checked.
    cleaned = re.sub(
        r'\s*(?:years?|months?|weeks?|days?|hours?)$', '', cleaned,
        flags=re.IGNORECASE,
    )

    # Check for scale suffix (single char: $383B) or scale word (574.3 billion)
    attached_scale = None

    # Attached suffix: "$383B", "$1.2T", "$60.9bn", "$3.8mn"
    cleaned_raw = raw.strip().rstrip(".")
    suffix_match = _RAW_SUFFIX_RE.search(cleaned_raw)
    if suffix_match:
        suffix_key = suffix_match.group(0).lower()
        # Normalize single-char keys to uppercase for _SCALE_SUFFIXES lookup
        if len(suffix_key) == 1:
            suffix_key = suffix_key.upper()
        if suffix_key in _SCALE_SUFFIXES:
            attached_scale = _SCALE_SUFFIXES[suffix_key]
            cleaned = _RAW_SUFFIX_RE.sub('', cleaned)

    # Scale word in the cleaned string: "574.3 billion", "3.8 million"
    if attached_scale is None:
        scale_match = re.search(
            r'\b(trillion|billion|million|thousand)\b', cleaned, re.IGNORECASE
        )
        if scale_match:
            word = scale_match.group(1).lower()
            word_scales = {
                "trillion": 1e12, "billion": 1e9,
                "million": 1e6, "thousand": 1e3,
            }
            attached_scale = word_scales.get(word)
            cleaned = cleaned[:scale_match.start()].strip()

    try:
        base = float(cleaned)
    except ValueError:
        return 0.0

    if attached_scale:
        return base * attached_scale

    # Check for scale words in the surrounding sentence
    # e.g., "383 billion", "27.4 trillion"
    # Only matches multi-character scale words (not single letters)
    for m in _SCALE_RE.finditer(sentence):
        try:
            num = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if abs(num - base) < 0.01 * max(abs(num), 1):
            suffix_word = m.group(2).lower()
            for key, scale in _SCALE_SUFFIXES.items():
                if key.lower() == suffix_word:
                    return base * scale

    return base


# ================================================================
# Subject extraction
# ================================================================

_PROPER_NOUN_RE = re.compile(
    r'\b([A-Z][a-zA-Z]*[a-z](?:-[A-Za-z][a-z]+)*'
    r'(?:(?:[ \t]+(?:of|the|and|de|von|van|&))?[ \t]+[A-Z][a-zA-Z]*[a-z])*)\b'
)

# Common sentence-start words that are NOT proper nouns
_POSSESSIVE_SUBJECT_RE = re.compile(
    r"\b((?:[A-Z][\w&.-]*\s+){0,3}[A-Z][\w&.-]*)['\u2019]s\b"
)
_LEADING_WORD_RE = re.compile(
    r'^(?:While|Although|Though|After|Before|As|When|Since|Because|With|Despite|'
    r'If|In|On|At|For|From|By|Under|Over|But|And|Yet|So|Meanwhile|According|'
    r'The|A|An)\s+'
)
_CALENDAR_WORDS = frozenset({
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December", "Monday", "Tuesday",
    "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
})
# Sentence openers that are ordinary nouns, not names. Capitalized only by
# position, and "Life expectancy was 78" is not about something called Life.
_COMMON_OPENERS = frozenset({
    "Life", "Inflation", "Merchandise", "Net", "Gross", "Average", "Total",
    "Operating", "Consumer", "Revenue", "Sales", "Income", "Unemployment",
    "Population", "Annual", "Diluted", "Earnings", "Cash", "Capital", "One",
    "Analysts", "Investors", "Economists", "Prices", "Growth", "Profit",
    "Margins", "Costs", "Debt", "Assets",
})
_DOLLAR_DENOMINATION_RE = re.compile(
    r'\b(?:U\.?S\.?|American)\s+dollars?\b', re.IGNORECASE,
)
_ANAPHORIC_OPENING_RE = re.compile(
    r'^\s*(?:(?:The|This|That)\s+(?:company|firm|group|retailer|carmaker|'
    r'automaker|bank|airline|business|country|nation|economy|state|tower|'
    r'bridge|river|mountain|planet|building)\b|It\b|Its\b|They\b|Their\b)',
)
_REGIONS = frozenset({
    "Asia", "Southeast Asia", "East Asia", "South Asia", "Central Asia",
    "Europe", "Central Europe", "Eastern Europe", "Western Europe",
    "Northern Europe", "Southern Europe", "Africa", "North Africa",
    "Sub-Saharan Africa", "West Africa", "East Africa", "Southern Africa",
    "Latin America", "South America", "North America", "Central America",
    "Middle East", "Scandinavia", "Oceania", "Caribbean", "European Union",
    "Eurozone", "Sun",
    # Who reported a figure, not who it is about.
    "World Bank", "IMF", "International Monetary Fund", "OECD", "United Nations",
    "Reuters", "Bloomberg", "Wikipedia", "NASA", "Federal Reserve", "SEC",
})
_YEAR_REFERENCE_RE = re.compile(
    r'\b(?:the|that|same|this)\s+(?:fiscal\s+)?year\b|\byear[- ]end\b|'
    r'\bannual\b', re.IGNORECASE,
)
_CLAUSE_BREAK_RE = re.compile(
    r',\s+(?:and|while|whereas|but|with|yet)\s+|;\s+|'
    r',\s+or\s+(?=[$€£¥₹])|'
    r'\s+and\s+(?:generated|spent|reported|posted|earned|had|made)\b|'
    r'(?:\s+and|,)\s+(?=(?:its\s+|the\s+)?(?:net\s+income|net\s+loss|revenues?|sales|'
    r'operating\s+\w+|gross\s+\w+|total\s+\w+|GDP|population|diluted|EPS|R&D|'
    r'cash|capex|capital\s+expenditures|(?:stock|share)holders)\b)|'
    # "and Germany's GDP was" is the other figure, including a pasted
    # apostrophe. "real GDP" and "GDP in real terms" are still that
    # figure. "GDP ministry spent" and "was not" stay with the first.
    r"(?:\s+and|,)\s+(?=(?:[A-Z][\w.&-]*\s+){0,3}[A-Z][\w.&-]*"
    "['\u2019]"
    r"s\s+(?:(?:(?:real|nominal)\s+)?GDP"
    r"(?:\s+in\s+(?:real\s+terms|nominal\s+terms|constant\s+prices))?|"
    r"net\s+income|net\s+loss|revenues?|sales|operating\s+\w+|gross\s+\w+|"
    r"total\s+\w+|GDP|population|diluted|EPS|R&D|cash|capex|"
    r"capital\s+expenditures|(?:stock|share)holders)\s+"
    r"(?:was|were|is|are)\b(?!\s+(?:not|never)\b))|"
    r'\s+with\s+(?:a|an)\s+(?=\w+\s+of\b)|'
    r'\s+(?:against|vs\.?|versus)\s+(?=\S*[\d$€£¥₹A-Z])'
)
_SENTENCE_STARTERS = {
    "The", "This", "That", "These", "Those", "It", "Its", "There",
    "Here", "What", "When", "Where", "How", "Why", "Which", "Who",
    "In", "On", "At", "By", "For", "With", "From", "To", "An", "A",
    "As", "If", "But", "And", "Or", "So", "Yet", "Not", "No",
    "However", "Although", "While", "Since", "Because", "After",
    "Before", "During", "Between", "About", "Among", "Through",
    "Most", "Some", "All", "Many", "Several", "Each", "Every",
    "Both", "Either", "Neither", "Such", "Overall", "Total",
    "According", "Based", "Given", "Despite", "Regarding",
    "Currently", "Recently", "Previously", "Historically",
    "Average", "Global", "Annual", "Estimated", "Approximately",
    # Pronouns and self-references (anonymous claims)
    "Our", "We", "Us", "Their", "Them", "They", "He", "She", "His", "Her",
    "My", "Me", "Mine", "Your", "Yours",
    # Common nouns frequently capitalized at sentence start
    "Customer", "Customers", "Client", "Clients", "User", "Users",
    "Revenue", "Revenues", "Profit", "Profits", "Sales", "Income",
    "Earnings", "Margin", "Margins", "Cost", "Costs", "Price", "Prices",
    "Growth", "Increase", "Decrease", "Decline", "Rate", "Rates",
    "Performance", "Quality", "Service", "Services", "Product", "Products",
    "Company", "Companies", "Business", "Businesses", "Organization",
    "Industry", "Industries", "Market", "Markets", "Sector", "Sectors",
    "Insurance", "Investment", "Investments", "Funding", "Capital",
    "Operating", "Operations", "Management", "Leadership",
    "Studies", "Research", "Analysts", "Analysis", "Reports",
    "Common", "Side", "Effect", "Effects", "Treatment", "Treatments",
    "Patients", "Participants", "Subjects", "Doctors", "Physicians",
    "Americans", "Europeans", "Asians", "Africans",
    "Net", "Gross", "Roughly", "Nearly", "Almost", "Over", "Under",
    "Less", "More", "Fewer", "Higher", "Lower",
    # Generic acronyms that are metrics/concepts, not entities
    "ROI", "ROE", "ROA", "EBITDA", "GAAP", "CAGR", "YOY", "QOQ",
    "GDP", "CPI", "PPI", "USD", "EUR", "GBP", "JPY", "CNY",
    "CEO", "CFO", "COO", "CTO", "CIO", "VP", "SVP", "EVP",
    "API", "SDK", "URL", "HTML", "CSS", "JSON", "XML", "HTTP", "HTTPS",
    "AI", "ML", "NLP", "GPU", "CPU", "RAM", "SSD", "HDD",
    "B2B", "B2C", "SaaS", "PaaS", "IaaS",
    "FY", "Q1", "Q2", "Q3", "Q4", "H1", "H2",
    "TTM", "YTD", "MTD", "QTD",
}

# Generic single words that should not count as entity subjects.
#
# This is the master non-entity list used by is_likely_entity. Words
# here will not be returned as a subject for verification, even when
# capitalized at sentence start. The list is intentionally generous:
# the cost of a false negative (a real entity wrongly rejected) is
# small (we just skip verification), while the cost of a false positive
# (verifying "98.7% customer satisfaction" against an unrelated company
# whose page contains 98%) actively misleads users.
#
# Categories below are alphabetized within each block for maintainability.
_NON_ENTITY_SUBJECTS = {s.lower() for s in _SENTENCE_STARTERS}
_NON_ENTITY_SUBJECTS.update({
    # Analyst ratings: "Rating: Outperform" is a verdict, not the company.
    "accumulate", "outperform", "overweight", "rating", "underperform",
    "underweight",
    # Document parts
    "chapter", "figure", "line", "page", "section", "table",
    # Generic organization references
    "business", "company", "department", "firm", "group", "organization",
    "team",
    # Generic tech/product nouns
    "analytics", "api", "application", "applications", "capability",
    "capabilities", "cloud", "compute", "computing", "consumer",
    "content", "core", "database", "desktop", "device", "devices",
    "edge", "engine", "enterprise", "feature", "features", "framework",
    "hardware", "hybrid", "information", "infrastructure", "innovation",
    "intelligence", "learning", "library", "media", "mobile", "model",
    "models", "network", "platform", "premium", "process", "processes",
    "product", "professional", "release", "server", "service", "services",
    "software", "solution", "solutions", "standard", "storage", "system",
    "tool", "tools", "training", "transformation", "version", "workflow",
    # Generic business/strategy nouns
    "advisory", "consulting", "digitalization", "effectiveness",
    "efficiency", "engagement", "experience", "insights", "loyalty",
    "operations", "optimization", "performance", "planning",
    "satisfaction", "strategy", "technology",
    # Generic financial/market nouns
    "asset", "assets", "benchmark", "bond", "debt", "dividend", "earnings",
    "equity", "exchange", "fund", "funds", "index", "portfolio", "return",
    "returns", "spread", "stock", "stocks", "trading", "valuation", "yield",
    # Generic medical/scientific nouns
    "antibody", "cell", "cells", "cohort", "condition", "diagnosis",
    "disease", "dosage", "dose", "drug", "drugs", "experiment", "gene",
    "medication", "outcome", "outcomes", "patient", "protein", "result",
    "results", "sample", "study", "studies", "symptom", "symptoms", "test",
    "tests", "therapy", "treatment", "trial", "trials", "vaccine",
    # People aggregates
    "customers", "individuals", "people", "users",
    # Generic geographic/temporal nouns
    "century", "city", "continent", "country", "county", "day", "decade",
    "earth", "globe", "month", "province", "quarter", "region", "state",
    "week", "world", "year",
    # Sequence/ordinal
    "first", "last", "next", "previous", "second", "third",
    # What a labeled figure measures: "Inventory: about $4.1 billion"
    "balance", "capex", "cash", "density", "diluted", "eps",
    "exports", "full-year", "gravity", "headline", "highlights", "imports", "inflation", "internet", "inventory", "life",
    "literacy", "per", "population", "temperature", "unemployment",
    "urbanisation", "urbanization",
    # People and things a company answers to: "Shareholders received"
    "board", "committee", "dividends", "ebit", "employees", "engineers", "ltd",
    "investors", "memorandum", "shareholders", "staff", "stockholders",
    # Stock exchanges, named beside a company: "(NYSE: ROL)"
    "nasdaq", "nyse",
})

# Words that make a heading a section label rather than a name.
_SECTION_WORDS = frozenset({
    "balance", "basics", "cash", "flow", "for", "full", "half", "headline",
    "highlights", "immediate", "inflation", "income", "line", "memo",
    "memorandum", "metrics", "notes", "numbers", "profitability", "recap",
    "release", "returns", "sheet", "take", "top",
    "snapshot", "standards", "statement", "year",
})
_HEADING_FILLER = frozenset({"a", "an", "and", "at", "for", "of", "the", "my", "our"})


# Followed by one of these, or by a word ending like a verb, a capitalized word
# opening a sentence is doing something, so it can be a name. "Apple reported"
# can; "Around $4 billion", "Rev $4 billion" and "How big" cannot.
_ORDINARY_OPENERS = frozenset({
    "above", "after", "again", "almost", "already", "also", "around", "away",
    "below", "best", "better", "big", "bottom", "brief", "certain", "clear",
    "close", "current", "down", "early", "even", "ever", "far", "few", "fine",
    "good", "great", "half", "hard", "high", "how", "just", "large", "later",
    "like", "little", "long", "low", "mix", "much", "near", "need", "new", "now",
    "off", "often", "old", "once", "only", "out", "own", "past", "perhaps",
    "quick", "rather", "real", "recovery", "right", "same", "short", "small",
    "soon", "still", "strong", "then", "thin", "top", "trough", "true", "up",
    "very", "weak", "well", "worth", "yes",
    # What a measurement is of: "Surface gravity is", "Mean density is"
    "escape", "financial", "mean", "median", "orbital", "surface",
})
# Abstract nouns, people in general, adverbs and participles: "Emigration
# remains", "Builders embedded", "Slowly, at", "Pulled together".
_ORDINARY_WORD_RE = re.compile(
    r'(?:ness|tion|sion|ment|ity|ism|ly|[eo]rs|ists|ants|ents|als|ing|ed)$'
)


def _reads_as_a_name(word, sentence):
    """Whether a capitalized word opening a sentence is used as a name.

    Listing what can follow a name fails on the first verb left out: "Micron
    swung". So this rules out what ordinary words look like instead.
    """
    rest = sentence.lstrip()[len(word):]
    # "Toro's" and "Starbucks'" own something.
    if rest[:1] in ("'", "\u2019"):
        return True
    if (word.lower().split('-')[0] in _ORDINARY_OPENERS
            or _ORDINARY_WORD_RE.search(word)):
        return False
    if rest[:1] == ",":
        return True
    following = re.match(r'\s+([a-z]+)', rest)
    return bool(following) and following.group(1) != "such"


_GENERIC_HEADINGS = {
    "overview", "introduction", "analysis", "summary", "conclusion",
    "background", "methodology", "results", "discussion", "references",
    "key findings", "growth projections", "market overview",
    "investment landscape", "adoption patterns", "economic overview",
    "financial overview", "market analysis", "industry overview",
    "manufacturing investment", "market projections", "key players",
    "battery technology", "ai chip segment", "market size",
    "revenue breakdown", "financial results", "investment",
    "demographics", "statistics", "data", "trends", "forecast",
    "historical data", "current state", "future outlook",
    "competitive landscape", "market share", "pricing",
    "supply chain", "technology", "innovation", "regulation",
    # Narrative-flow section labels common in business prose. The
    # 2026-05-06 SN debug on the NVIDIA example showed
    # "Growth and Challenges" and "Outlook" being accepted as
    # entity-bearing headings; sentence-level proper nouns (Amazon
    # Web Services, Microsoft, Google) got masked because heading
    # took precedence in extract_subject's fallback chain. Adding
    # them here forces fall-through to sentence-level entity
    # extraction.
    "growth and challenges", "outlook", "findings", "next steps",
    "key takeaways", "learnings", "challenges", "growth",
    "opportunities", "risks", "strengths", "weaknesses",
    "objectives", "goals", "context", "rationale", "recommendation",
    "recommendations", "implications", "limitations",
}


# Two to four words, only the first capitalized, then a colon: "Put simply:".
_LEAD_IN_RE = re.compile(r'\s*(?:[-*]\s*)?([A-Z][a-z]+(?:\s+[a-z]+){1,3}):\s+')


def _without_lead_in(sentence):
    lead = _LEAD_IN_RE.match(sentence or "")
    if lead and not _COUNTRY_NAMES_RE.search(lead.group(1)):
        return sentence[lead.end():]
    return sentence


def extract_subject(heading, sentence, topic="", doc_text="", num_raw="",
                    doc_primary_entity=""):
    """Extract the most likely subject from heading, sentence, or topic.

    Fallback chain:
    1. Section heading (if it names a specific entity, not a generic title)
    2. Country names in the sentence
    3. Acronyms in the sentence (NVIDIA, TSMC, AMD)
    4. Proper nouns in the sentence (skip sentence starters)
    5. Backward search from number position in doc_text (for truncated contexts)
    6. Document primary entity (most-mentioned entity in the full doc)
    7. User-provided topic

    Each candidate is filtered through is_likely_entity to reject
    generic words like "Customer", "Revenue", "Our". This prevents
    false-positive web verifications where Brave Search matches numbers
    to unrelated companies via topical word coincidence.

    The doc_primary_entity fallback lets sentences inherit the document's
    main subject when they do not name an entity themselves. This is the
    common case for medical and financial reporting where successive
    sentences refer to the same drug or company implicitly.
    """
    # "Put simply: Cote d'Ivoire has grown", "In short: Peru ...": a short
    # lead-in before a colon is not the subject (2026-11-27: "Put" was the
    # subject of every figure after it). Kept when it names a place or a
    # proper name ("Kenya:", "Apple Inc:").
    sentence = _without_lead_in(sentence)
    # "GDP in current US dollars was $5.7 billion": the currency names no
    # subject (v29: a Maldives answer that never names the Maldives had its
    # figures checked as the United States').
    sentence = _without_us_currency(sentence) if sentence else sentence

    # 1. Heading (best signal, but only if it names a specific entity)
    if heading:
        clean = re.sub(r'^#+\s*', '', heading).strip()
        clean = re.sub(r'^\d+\.\s*', '', clean).strip()
        clean = re.split(r'[:(]', clean)[0].strip()
        if len(clean) >= 2 and clean.lower() not in _GENERIC_HEADINGS:
            # Does the heading contain a recognizable entity?
            has_entity = bool(_COUNTRY_NAMES_RE.search(clean))
            # Multi-word proper nouns: "Giant Pacific Octopus", "Apple Inc"
            # But NOT descriptive titles: "Global Semiconductor Market"
            _DESCRIPTIVE_WORDS = {
                "global", "international", "national", "regional", "local",
                "market", "industry", "technology", "investment", "segment",
                "sector", "landscape", "overview", "analysis", "report",
                "annual", "quarterly", "current", "future", "historical",
                "key", "major", "primary", "main", "total", "overall",
                "new", "recent", "modern", "early", "late",
                "results", "financial", "chip", "data", "performance",
                "manufacturing", "production", "development", "growth",
                "projections", "trends", "statistics", "comparison",
            }
            if not has_entity:
                multi = re.findall(r'[A-Z][a-z]+', clean)
                # Entity if at least one word is NOT a common descriptive word
                non_descriptive = [w for w in multi if w.lower() not in _DESCRIPTIVE_WORDS]
                has_entity = len(non_descriptive) >= 2 or (
                    len(non_descriptive) == 1 and len(multi) <= 2
                )
            # Acronyms: "TSMC", "NVIDIA", "AMD", "CATL"
            if not has_entity:
                has_entity = bool(re.search(r'\b[A-Z]{2,}\b', clean))
            # Parenthetical names: "Giant Pacific Octopus (Enteroctopus dofleini)"
            if not has_entity:
                has_entity = '(' in clean
            if has_entity:
                # If the heading is long (>4 words), it is likely a descriptive
                # title like "NVIDIA Fiscal Year 2026 Financial Summary." Extract
                # just the entity (acronym or leading proper noun) rather than
                # returning the full heading, which confuses downstream CIK
                # lookup (substring match on "FINANCIAL" can hit Visa Inc).
                words = clean.split()
                if len(words) > 4:
                    # Try acronym first (NVIDIA, TSMC, AMD)
                    acro = re.search(r'\b([A-Z]{2,})\b', clean)
                    if acro and is_likely_entity(acro.group(1)):
                        return acro.group(1)
                    # Try leading proper noun: take the first titlecase word
                    # that is not a descriptive or temporal term
                    _HEADING_STOP = _DESCRIPTIVE_WORDS | {
                        "fiscal", "year", "quarter", "q1", "q2", "q3", "q4",
                        "fy", "summary", "earnings", "revenue", "profit",
                        "income", "expenses", "breakdown", "third", "fourth",
                        "first", "second", "half", "full",
                    }
                    for w in words:
                        if (w[0].isupper() and w.lower() not in _HEADING_STOP
                                and not re.match(r'^\d', w)):
                            return w
                return clean

    # "in current US dollars" is a currency, not a mention of the country.
    if sentence:
        sentence = _DOLLAR_DENOMINATION_RE.sub('dollars', sentence)

    # 2a. A possessive names what the sentence is about, ahead of any
    # country inside it: "Chipotle Mexican Grill's revenue" is not Mexico.
    # Only before the figure: in "$579 billion, less than Walmart's sales"
    # the figure is not Walmart's.
    if sentence:
        possessive = _POSSESSIVE_SUBJECT_RE.search(sentence)
        figure_at = sentence.find(str(num_raw).strip()) if num_raw else -1
        if possessive and figure_at >= 0 and possessive.start() > figure_at:
            possessive = None
        if possessive:
            # A capitalized opening word is not part of the name: "While
            # Kraft Heinz's sales", "The Walt Disney Company's revenue".
            name = _LEADING_WORD_RE.sub('', possessive.group(1))
            if is_likely_entity(name) and not _COUNTRY_NAMES_RE.fullmatch(name):
                return name
            # "France's Millau Viaduct": the country locates the named thing.
            owned = _PROPER_NOUN_RE.match(sentence[possessive.end():].lstrip())
            if owned and is_likely_entity(owned.group(1)):
                return owned.group(1)

    # 2a'. "Lake Titicaca (Peru/Bolivia)": a place in parentheses after a name
    # only locates it.
    if sentence:
        located = re.match(
            r'\s*(?:The\s+)?((?:[A-Z][\w&.\'-]*\s+){0,4}[A-Z][\w&.\'-]*)\s*\(([^)]*)\)',
            sentence,
        )
        if (located and _COUNTRY_NAMES_RE.search(located.group(2))
                and not _COUNTRY_NAMES_RE.fullmatch(located.group(1))
                and is_likely_entity(located.group(1))):
            return located.group(1)

    # 2. Country names in the sentence (specific pattern, high confidence)
    if sentence:
        country_match = _COUNTRY_NAMES_RE.search(sentence)
        # "Panama Canal": the country is part of a longer name, unless the
        # next word is a title-cased ordinary word that only follows it.
        if country_match:
            rest = sentence[country_match.end():]
            named = re.match(r'\s+(Canal|Strait|Bridge|Tunnel|River|Bay|Sea|'
                             r'Railway|Airlines|Airways|Bank|Dam|Lake|Gulf)\b',
                             rest)
            if named:
                return f"{country_match.group()} {named.group(1)}"
        if country_match:
            # "Angel Falls in Venezuela": the country locates the subject.
            before = sentence[:country_match.start()]
            if re.search(r'\b(?:in|from)\s+(?:the\s+)?$', before):
                for name in _PROPER_NOUN_RE.findall(before):
                    name = re.sub(r'^(?:The|A|An)\s+', '', name)
                    if len(name.split()) >= 2 and is_likely_entity(name):
                        return name
            matched = country_match.group()
            return _COUNTRY_CANONICAL.get(matched, _COUNTRY_CANONICAL.get(matched.title(), matched))
        abbrev_match = _COUNTRY_ABBREV_RE.search(sentence)
        if abbrev_match:
            return _COUNTRY_CANONICAL.get(abbrev_match.group(), abbrev_match.group())

    # 3. Acronyms in the sentence (NVIDIA, TSMC, AMD, CHIPS, CATL)
    #    Most tech/finance entities are all-caps. Check before proper nouns.
    if sentence:
        acronyms = re.findall(r'\b([A-Z]{2,}(?:-\d+)?(?:[ \t]+[A-Z][a-z]+)*)\b', sentence)
        for a in acronyms:
            if (a not in _SENTENCE_STARTERS
                    and len(a) >= 2
                    and is_likely_entity(a)):
                return a

    # 4. Proper nouns in the sentence (Title Case words)
    if sentence:
        matches = [
            re.sub(r'^(?:The|A|An|Is|Are|Was|Were|Do|Does|Did|Can|Will)\s+', '', found)
            for found in _PROPER_NOUN_RE.findall(sentence)
        ]
        for m in matches:
            if (m not in _SENTENCE_STARTERS
                    and m not in _CALENDAR_WORDS
                    and m.split()[0] not in _COMMON_OPENERS
                    and len(m) > 2
                    and is_likely_entity(m)):
                if (' ' not in m and sentence.lstrip().startswith(m)
                        and not _reads_as_a_name(m, sentence)):
                    continue
                return m

    # 5. Document primary entity (sentence-level inheritance).
    # When the sentence has no entity of its own, the document's
    # most-mentioned entity is the implicit subject. This is more
    # reliable than backward search because it uses doc-wide
    # frequency rather than physical proximity, so it does not get
    # confused by transient mentions of unrelated entities.
    if doc_primary_entity and is_likely_entity(doc_primary_entity):
        return doc_primary_entity

    # 6. Backward search from number position in document.
    # Fallback when no primary entity is available. For truncated
    # claim contexts, the entity name may be in the preceding 200
    # characters of the original document.
    if doc_text and num_raw:
        num_pos = doc_text.find(str(num_raw))
        if num_pos > 0:
            lookback = doc_text[max(0, num_pos - 200):num_pos]
            lookback = _without_us_currency(re.sub(r'(?m)^#.*$', '', lookback))
            # Try country names first
            country_match = _COUNTRY_NAMES_RE.search(lookback)
            if country_match:
                matched = country_match.group()
                return _COUNTRY_CANONICAL.get(matched, _COUNTRY_CANONICAL.get(matched.title(), matched))
            abbrev_match = _COUNTRY_ABBREV_RE.search(lookback)
            if abbrev_match:
                return _COUNTRY_CANONICAL.get(abbrev_match.group(), abbrev_match.group())
            # Try acronyms (TSMC, NVIDIA, etc.) - last one = closest
            acros = re.findall(r'\b([A-Z]{2,})\b', lookback)
            for a in reversed(acros):
                if (a not in _SENTENCE_STARTERS
                        and len(a) >= 2
                        and is_likely_entity(a)):
                    return a
            # Try proper nouns (take the LAST one, closest to the number)
            pn_matches = _PROPER_NOUN_RE.findall(lookback)
            for m in reversed(pn_matches):
                if (m in _SENTENCE_STARTERS or m in _CALENDAR_WORDS
                        or m.split()[0] in _COMMON_OPENERS or len(m) <= 2):
                    continue
                result = re.sub(r'^(?:The|A|An)\s+', '', m)
                if len(result) > 2 and is_likely_entity(result):
                    return result

    # 7. User topic (gated through entity check too)
    if topic:
        candidate = topic[:100].strip()
        if is_likely_entity(candidate):
            return candidate

    return ""


def _is_single_word_entity(word):
    """Check if a single word is a likely entity.

    Helper for is_likely_entity. Single-word check:
      - Reject empty/very short
      - Reject if in non-entity blacklist
      - Accept country names
      - Accept all-caps acronyms (length >= 3)
      - Accept mixed-case Title words (length >= 3)
    """
    if not word or len(word) < 2:
        return False
    if word.lower() in _NON_ENTITY_SUBJECTS:
        return False
    # Country names always allowed
    if _COUNTRY_NAMES_RE.fullmatch(word):
        return True
    # All-caps acronyms: only if length >= 3
    # ("AI" and "ML" are too ambiguous; "TSMC" and "NVIDIA" are entities)
    if word.isupper() and len(word) >= 3:
        return True
    # Mixed-case Title word: likely a proper noun
    # ("Tesla", "Apple", "Ozempic" - common nouns already filtered above)
    if word[0].isupper() and any(c.islower() for c in word) and len(word) >= 3:
        return True
    return False


def is_likely_entity(subject):
    """Determine if a subject string represents a real entity vs a generic word.

    Returns True for:
      - Single proper nouns NOT in the common-word blacklist: "Tesla", "Apple"
      - Country names: "France", "United States"
      - Distinctive acronyms: "TSMC", "NVIDIA", "STEP"
      - Multi-word phrases containing at least one real entity: "Novo Nordisk",
        "Apple Inc.", "Microsoft Corporation"

    Returns False for:
      - Single common nouns: "Customer", "Revenue", "Insurance"
      - Pronouns: "Our", "We", "They"
      - Generic acronyms: "ROI", "GDP", "CEO"
      - Multi-word phrases of only generic words: "Our Cloud", "Common Side"
      - Empty or very short strings

    This is the gate that prevents false positives in web verification:
    a generic word like "Customer" will match anything on the web,
    but "Novo Nordisk" will only match results that actually mention
    the entity.
    """
    if not subject or len(subject) < 2:
        return False

    s = subject.strip()

    # Reject pure punctuation or numbers
    if not re.search(r'[a-zA-Z]', s):
        return False

    words = s.split()

    # Multi-word: requires at least one word that is itself entity-like
    # ("Novo Nordisk" -> "Novo" or "Nordisk" passes; "Our Cloud" -> neither does)
    if len(words) >= 2:
        return any(_is_single_word_entity(w) for w in words)

    # Single word: apply single-word rules
    return _is_single_word_entity(s)


def extract_doc_primary_entity(doc_text, topic=""):
    """Find the document's primary entity for sentence-level inheritance.

    Many documents are about a single entity (a drug, a company, a product)
    but only name it explicitly in some sentences. The other sentences
    refer to it implicitly: "Common side effects include nausea (44%)" in
    a document about Ozempic should be verified as an Ozempic claim.

    Returns the most-mentioned likely entity in the document, or empty
    string if no entity dominates clearly.

    Heuristic: count occurrences of every distinct candidate entity (proper
    nouns, country names, distinctive acronyms). The candidate with the
    highest count wins, requiring at least 2 mentions to avoid noise from
    one-off references. The user-supplied topic is preferred when its
    leading entity also appears in the document.
    """
    if not doc_text or len(doc_text) < 20:
        return ""

    # Strip markdown formatting that confuses tokenization
    cleaned = re.sub(r'[#*_\[\]()]', ' ', doc_text)
    # "US dollars" names a currency, not the entity (v29: an answer that
    # never names its country had "United States" as its primary entity).
    cleaned = _without_us_currency(cleaned)
    # "Put simply:" opening each paragraph is not the entity (2026-11-27).
    cleaned = "\n".join(
        " ".join(_without_lead_in(s) for s in _SENTENCE_BREAK_RE.split(line))
        for line in cleaned.split("\n"))

    # Collect entity candidates
    counts = {}

    # 1. Country names (map demonyms to canonical form)
    for m in _COUNTRY_NAMES_RE.finditer(cleaned):
        raw = m.group()
        ent = _COUNTRY_CANONICAL.get(raw, _COUNTRY_CANONICAL.get(raw.title(), raw))
        if is_likely_entity(ent):
            counts[ent] = counts.get(ent, 0) + 1
    for m in _COUNTRY_ABBREV_RE.finditer(cleaned):
        ent = _COUNTRY_CANONICAL.get(m.group(), m.group())
        if is_likely_entity(ent):
            counts[ent] = counts.get(ent, 0) + 1

    # 2. All-caps acronyms (length >= 3)
    for m in re.finditer(r'\b([A-Z]{3,})\b', cleaned):
        ent = m.group(1)
        if is_likely_entity(ent):
            counts[ent] = counts.get(ent, 0) + 1

    # 3. Capitalized title-case words (likely proper nouns).
    # Skip sentence starters which are usually false positives.
    for m in _PROPER_NOUN_RE.finditer(cleaned):
        ent = m.group(1).strip()
        # Strip leading determiners
        ent = re.sub(r'^(?:The|A|An)\s+', '', ent)
        if not ent or ent in _SENTENCE_STARTERS:
            continue
        # Take just the first word (entity head) for counting
        head = ent.split()[0]
        if not _is_single_word_entity(head):
            continue
        counts[head] = counts.get(head, 0) + 1

    if not counts:
        return ""

    # Pick the most-mentioned entity. Require at least 2 mentions so a
    # one-off proper noun does not become the document subject.
    sorted_ents = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top_entity, top_count = sorted_ents[0]
    if top_count < 2:
        return ""

    # If the user provided a topic and its leading entity word also
    # appears in the document, prefer it (the user knows the subject).
    if topic:
        topic_words = topic.strip().split()
        if topic_words:
            topic_head = re.sub(r'^(?:The|A|An)\s+', '', topic_words[0])
            if topic_head and topic_head in counts:
                return topic_head

    return top_entity


# ================================================================
# Claim decomposition
# ================================================================

_TIME_RE = re.compile(
    r'\b((?:FY|fiscal\s+(?:year\s+)?)?20[1-3]\d|'
    r'Q[1-4]\s+(?:FY\s*)?20[1-3]\d|'
    r'(?:January|February|March|April|May|June|July|August|'
    r'September|October|November|December)\s+20[1-3]\d)\b',
    re.IGNORECASE
)

# Metric pattern dict. Order matters: the FIRST pattern that matches
# wins, so multi-word / specific patterns must come before single-word
# patterns that could swallow them. Concretely:
#   - "operating_expenses" includes "cost of revenue" / "cost of goods",
#     so it must come BEFORE both "revenue" (which would match the
#     trailing "revenue") and "price" (which has "cost" as a keyword).
#   - "cash" is unambiguous and can sit anywhere.
_METRIC_PATTERNS = {
    "eps": re.compile(
        r'\b(earnings\s+per\s+share|EPS|(?:loss\s+)?per\s+(?:diluted\s+|basic\s+)?share)\b',
        re.IGNORECASE,
    ),
    "operating_income": re.compile(
        r'\b(operating\s+(?:income|profit)|income\s+from\s+operations)\b',
        re.IGNORECASE,
    ),
    "gross_profit": re.compile(r'\b(gross\s+profit)\b', re.IGNORECASE),
    "research_development": re.compile(
        r'\b(research\s+and\s+development|R&D)\b', re.IGNORECASE,
    ),
    "cost_of_revenue": re.compile(
        r'\b(cost\s+of\s+(?:revenues?|sales|goods(?:\s+(?:and\s+services\s+)?sold)?))\b',
        re.IGNORECASE,
    ),
    "operating_expenses": re.compile(
        r'\b(operating\s+expenses?|opex|cost\s+of\s+(?:goods|revenue|sales))\b',
        re.IGNORECASE,
    ),
    "operating_cash_flow": re.compile(
        r'\b(operating\s+cash(?:\s+flow)?|cash\s+(?:flow\s+)?(?:provided\s+by|from)'
        r'\s+operat\w+(?:\s+activities)?|op\s+cash\s+flow)\b',
        re.IGNORECASE,
    ),
    "total_assets": re.compile(r'\b(total\s+assets)\b', re.IGNORECASE),
    "employees": re.compile(
        r'\b(employees|employed|employs|workforce|headcount|staff\s+of)\b', re.IGNORECASE,
    ),
    "stockholders_equity": re.compile(
        r"\b((?:stock|share)holders['\u2019]?\s+equity)\b", re.IGNORECASE,
    ),
    "long_term_debt": re.compile(r'\b(long[- ]term\s+debt)\b', re.IGNORECASE),
    "dividends_paid": re.compile(r'\b(dividends?(?:\s+paid)?)\b', re.IGNORECASE),
    "inventory": re.compile(r'\b(inventor(?:y|ies))\b', re.IGNORECASE),
    "capex": re.compile(r'\b(capital\s+expenditures?|capex)\b', re.IGNORECASE),
    "cash": re.compile(
        r'(?<!free\s)\b(cash(?:\s+and\s+(?:cash\s+)?equivalents)?|liquidity)\b'
        r'(?!\s+flow)',
        re.IGNORECASE,
    ),
    "revenue": re.compile(r'\b(revenues?|sales|turnover)\b', re.IGNORECASE),
    "profit": re.compile(r'\b(profits?|earnings|earned|net\s+income|net\s+loss|EBITDA)\b', re.IGNORECASE),
    "market_cap": re.compile(r'\b(market\s+cap|valuation|valued\s+at)\b', re.IGNORECASE),
    "population": re.compile(r'\b(population|inhabitants|residents|people)\b', re.IGNORECASE),
    "area": re.compile(
        r'\b(area|square\s+(?:km|miles?|kilomet(?:er|re)s?)|sq\.?\s+(?:km|mi)|km2|km\u00b2|mi2)(?![a-z])',
        re.IGNORECASE,
    ),
    "height": re.compile(r'\b(height|tall|elevation|altitude)\b', re.IGNORECASE),
    "diameter": re.compile(r'\b(diameter|radius)\b', re.IGNORECASE),
    "weight": re.compile(r'\b(weight|mass|weighs?|kg|kilograms?|tonnes?)\b', re.IGNORECASE),
    "length": re.compile(r'\b(length|long|span|arm\s+span|mantle|runs?\s+for|stretch(?:es)?\s+for)\b', re.IGNORECASE),
    # "could expect to live 75.4 years", "people live to 83" (v21).
    "lifespan": re.compile(r'\b(lifespan|life\s+span|life\s+expectancy|years?\s+old|longevity|'
                           r'expect(?:ed|s)?\s+to\s+live|live\s+(?:to|for|until))\b', re.IGNORECASE),
    "price": re.compile(
        r'\b(price|cost|priced?\s+at|trading\s+at|(?<!economy\sis\s)(?<!economy\swas\s)worth)\b',
        re.IGNORECASE,
    ),
    "gdp_per_capita": re.compile(
        r'\b((?:GDP|income|output)\s+(?:per\s+(?:capita|head|person|inhabitant)|/\s*capita)'
        r'|(?:GDP|income|output)\s+on\s+a\s+per\s+person\s+basis)\b',
        re.IGNORECASE,
    ),
    "gdp": re.compile(
        r'\b(GDP|gross\s+domestic\s+product|economy\s+(?:is|was)\s+worth)\b',
        re.IGNORECASE,
    ),
    "growth": re.compile(r'\b(grew|growth|increase[ds]?|decline[ds]?|change[ds]?)\s+', re.IGNORECASE),
    "count": re.compile(r'\b(species|number\s+of|approximately|about|around|some)\b', re.IGNORECASE),
}

_DERIVED_RE = re.compile(
    r'\b(grew|growth|increase[ds]?\s+(?:by|of)|decline[ds]?\s+(?:by|of)|'
    r'change[ds]?\s+(?:by|of)|up\s+\d|down\s+\d|rose\s+\d|fell\s+\d)\b',
    re.IGNORECASE
)

_PRIOR_FIGURE_RE = re.compile(
    r'(?P<lead>\bup\s+from|\bdown\s+from|\bcompared\s+(?:with|to)|\bfrom|\bvs\.?|\bversus)\s+'
    r'(?:FY\s?(?P<before_figure>20[1-3]\d)\s+)?'
    r'(?P<approx>(?:about|around|roughly|nearly|almost|approximately|some|just)\s+)?'
    r'(?P<figure>[$\u20ac\u00a3\u00a5\u20b9]?\d[\d,]*(?:\.\d+)?'
    r'(?:\s*(?:bn|mn|billion|million|thousand|trillion)\b|[mMbBkK]\b|\s?%)?)'
    r'(?:\s+(?P<period>in\s+(?:fiscal\s+|FY\s*)?(?P<year>20[1-3]\d)\b|'
    r'(?:in\s+)?(?:a\s+year\s+(?:earlier|ago|before)|(?:the\s+)?(?:prior|previous)\s+year|'
    r'the\s+year\s+before|last\s+year)|PY\b))?',
    re.IGNORECASE,
)
# "slowed to 0.2% after 5.3% in 2022": a rate, then the earlier rate and its
# year. Only a rate with its period: "after 2.3 million job losses" and
# "after 2020" are not earlier figures.
_AFTER_RATE_RE = re.compile(
    r'\bafter\s+(?:(?:a|an|very|strong|weak|robust|solid|brisk|sluggish|modest|'
    r'expanding|growing|contracting|shrinking|rising|falling|by)\s+){0,3}'
    r'(?P<approx>(?:about|around|roughly|nearly|almost|some|just)\s+)?'
    r'(?P<figure>-?\d+(?:\.\d+)?\s?%)\s+'
    r'(?P<period>in\s+(?:fiscal\s+)?(?P<year>20[1-3]\d)\b|'
    r'(?:in\s+)?(?:a\s+year\s+(?:earlier|ago|before)|(?:the\s+)?(?:prior|previous)\s+year|'
    r'the\s+year\s+before|last\s+year))',
    re.IGNORECASE,
)
# "the 10-for-1 stock split that took effect in November 2025": the date of
# an event in the sentence, not the period of its figure.
_EVENT_DATE_RE = re.compile(
    r'\b(?:split|merger|acquisition|spin-?off|IPO|listing|deal|takeover)\b[^.;,]{0,40}?'
    r'\b(?:in|on|from)\s+(?:(?:early|mid|late)[- ])?(?:[A-Z][a-z]+\s+)?(?:\d{1,2},?\s+)?20[0-3]\d\b',
)
# "a rebound after the drought-hit 2023": the year it came after, not its own.
_AFTER_YEAR_RE = re.compile(
    r'\b(?:after|following)\s+(?:(?:a|an|the|very|[\w-]+)\s+){0,3}?20[1-3]\d\b(?!\s*%)',
    re.IGNORECASE,
)
_FIGURE_AFTER_VS_RE = re.compile(r'\b(?:vs\.?|versus)\s+$', re.IGNORECASE)
# A sentence that opens with a name and its verb: "Tesla sells", "Acme Corp reported".
_NAME_OPENS_RE = re.compile(
    r"^((?:[A-Z][\w&.'-]*\s){1,3}?)(?:sells|sold|makes|made|builds|built|reported|posted|"
    r"operates|employs|ships|shipped|opened|exports|imports|earns|earned|delivered|launched)\b")
_PASSING_MENTION_RE = re.compile(
    r'\b(?:such\s+as|including|like|between|with|against|than|behind|ahead\s+of|'
    r'compared\s+(?:to|with)|rivals?|competitors?|'
    # "the same level as the Northern Mariana Islands": a comparison, not the
    # subject a later "Its" refers to (v28).
    r'(?:the\s+)?same\s+(?:level|size|rate|pace|amount)\s+as|'
    r'as\s+(?:high|large|low|big|small|much|fast)\s+as)\b',
)
_COMPARED_YEAR_RE = re.compile(
    r'\b(?:than|compared\s+(?:to|with)|versus|vs\.?)\s+(?:in\s+|the\s+|fiscal\s+|'
    r'year\s+|FY\s*)*20[1-3]\d\b',
    re.IGNORECASE,
)

_EXTREME_RE = re.compile(
    r'\b(?:peak(?:ed|s)?|highest|lowest|all-time|high\s+of|low\s+of|topped\s+out|bottomed)\b',
    re.IGNORECASE,
)
_FORECAST_WORDING_RE = re.compile(
    r'\b(?:forecasts?|projected|projections?|expects?|expected|estimates?|estimated|'
    r'guidance|guided|target|outlook|could|would|might|may|likely|anticipates?|'
    r'plans?|aims?|hopes?|bet|guess|think|believe|by\s+20[2-9]\d|20[2-9]\dE|'
    r'FY\d{2,4}E|next\s+year|will)\b',
    re.IGNORECASE,
)
_PROJECTION_RE = re.compile(
    r'\b(projected|forecast|expected\s+to|will\s+reach|by\s+20[3-9]\d|'
    r'estimated\s+to\s+reach|poised\s+to)\b',
    re.IGNORECASE
)

# Segment / sub-component qualifiers. When a financial claim references
# a specific segment, product line, or geographic region, the SEC EDGAR
# companyconcept API cannot verify it; that endpoint returns
# consolidated values across all dimensions. The XBRL filings DO contain
# segment data under us-gaap:StatementBusinessSegmentsAxis, but it
# requires the companyfacts endpoint and dimensional parsing.
#
# Until segment-aware verification is implemented, claims that match
# these patterns are routed away from SEC EDGAR so they end up
# "unverifiable" rather than falsely contradicted against the
# consolidated total.
#
# Three signals (any one is sufficient):
#   1. _SEGMENT_KEYWORD_RE: literal "segment" / "division" / "business
#      unit" / "product line" / etc.
#   2. _SUBCOMPONENT_PRODUCT_RE: known product/brand names that are
#      unambiguous proper nouns (iPhone, Azure, AWS, ...). Matched
#      alone, no trailer required.
#   3. _SUBCOMPONENT_GENERIC_RE: generic nouns (gaming, services,
#      automotive) that need a financial trailer (revenue/sales/...) to
#      reduce false positives in everyday usage.
_SEGMENT_KEYWORD_RE = re.compile(
    r'\b(segments?|divisions?|business\s+units?|product\s+lines?|'
    r'business\s+segments?|reportable\s+segments?|operating\s+segments?)\b',
    re.IGNORECASE
)

# Sub-component qualifiers come in two flavors:
#
#   1. PRODUCT/BRAND names (iphone, azure, aws, xbox, ...): proper
#      nouns that very rarely appear outside of a segment context.
#      We match them alone without requiring a financial trailer, so
#      "Azure grew 30%" and "AWS generated $90B" are caught.
#
#   2. GENERIC nouns (gaming, services, search, advertising, automotive)
#      that have non-financial meanings. We require a financial trailer
#      ("revenue", "sales", "business", "operations") to avoid false
#      positives on sentences that use these words in everyday contexts.
#
# False positives on non-currency claims are harmless: is_segment is
# only consulted by the SEC EDGAR / Alpha Vantage routing, both of
# which already require currency-typed claims with substantial values.
_SUBCOMPONENT_PRODUCT_RE = re.compile(
    r'\b('
    # Apple product lines
    r'iphones?|ipads?|macs?|apple\s+watch|wearables?|airpods?|'
    # Cloud infrastructure brands
    r'azure|aws|gcp|google\s+cloud|amazon\s+web\s+services|'
    # Gaming console brands
    r'xbox|playstation|nintendo|'
    # Microsoft segment names (they are unambiguous proper nouns)
    r'productivity\s+and\s+business\s+processes|intelligent\s+cloud|'
    r'more\s+personal\s+computing|linkedin|dynamics|'
    # Tesla product lines
    r'self.driving|robotaxi|tesla\s+energy|'
    # NVIDIA / semiconductor segment names
    r'professional\s+visualization|crypto\s+mining|'
    # Specific Google products
    r'youtube'
    r')\b',
    re.IGNORECASE
)

_SUBCOMPONENT_GENERIC_RE = re.compile(
    r'\b('
    # Cloud / data infrastructure (generic words)
    r'data\s*center|datacenter|cloud|'
    # Gaming / media (generic)
    r'gaming|games?|streaming|'
    # Mobility / automotive (generic)
    r'automotive|'
    # Services / subscriptions (generic)
    r'services|subscriptions?|app\s+store|advertising|ads?|search|'
    # Hardware verticals (generic)
    r'workstation|networking|'
    # Telecom (generic)
    r'wireless|broadband|fiber|enterprise\s+wireline|consumer\s+wireline|'
    # Microsoft generic
    r'office'
    # Trailing context required: a financial verb or another
    # sub-component noun. The "advertising" / "ads" trailer catches
    # Google's "search advertising" naming.
    r')\s+(?:revenue|sales|business|operations|advertising|ads?|segment)',
    re.IGNORECASE
)


_PRIOR_YEAR_RE = re.compile(
    r'\b(prior|previous|preceding|last)\s+year',
    re.IGNORECASE,
)


def _is_prior_year_claim(sentence, raw_value):
    """Detect when a specific number in a sentence refers to the prior
    fiscal year rather than the sentence's main year.

    The pattern is: a number that appears within ~50 characters after
    a "prior year" / "previous year" / "last year" marker. This catches
    sentences like "FY2026 revenue of $215B, up from the prior year's
    $130B" where the heading-inferred year (FY2026) applies to $215B
    but $130B is the prior year (FY2025).

    Returns True if raw_value appears immediately after a prior-year
    marker. Caller should decrement the inferred year by 1.
    """
    if not raw_value:
        return False
    bare = raw_value.lstrip("$€£¥₹").strip().split()[0]
    if not bare:
        return False
    for m in _PRIOR_YEAR_RE.finditer(sentence):
        window = sentence[m.end():m.end() + 50]
        if bare in window:
            return True
    return False


def _detect_segment_claim(sentence, heading, doc_text="", raw_value=""):
    """Detect whether a claim is about a sub-component (segment, product
    line, region) rather than the consolidated total.

    Returns True if any segment signal is found in the sentence,
    heading, or (when doc_text is provided) a context window around
    the claim's raw_value in the original document.

    The doc_text fallback exists because clarethium_measure's
    split_sentences breaks paragraphs at line boundaries before
    sentence boundaries. A sentence like "Automotive revenue reached
    $5.6 billion" can lose its leading "Automotive revenue reached"
    if there's a line break before the dollar amount, leaving
    decompose_claim with only "$5.6 billion, up 55% year over year."
    to work with. Looking up the original document recovers the lost
    qualifier.
    """
    text = f"{sentence} {heading}"
    if _matches_segment_signal(text):
        return True
    if _labels_a_business_line(sentence, heading, raw_value):
        return True
    if _listed_as_a_part(sentence, raw_value):
        return True

    # Backward-window fallback in the original document text. Segment
    # qualifiers come BEFORE the dollar amount ("Automotive revenue
    # reached $5.6 billion"), so we only need to look at the text
    # immediately preceding the value.
    #
    # The window is bounded by the previous sentence boundary (period +
    # whitespace) so we don't bleed into the prior sentence. This
    # prevents the $215.9B consolidated claim from being mis-flagged
    # as a segment because the next sentence happens to mention "data
    # center segment".
    if doc_text and raw_value:
        bare_value = raw_value.lstrip("$€£¥₹").strip()
        if bare_value:
            idx = doc_text.find(bare_value)
            if idx >= 0:
                # Look back up to 120 chars but stop at a sentence boundary
                start = max(0, idx - 120)
                lookback = doc_text[start:idx]
                # Trim to the last sentence boundary in the window so
                # qualifiers from the prior sentence don't leak in.
                last_period = max(
                    lookback.rfind(". "),
                    lookback.rfind(".\n"),
                    lookback.rfind("\n\n"),
                )
                if last_period >= 0:
                    lookback = lookback[last_period + 1:]
                if _matches_segment_signal(lookback):
                    return True
    return False


# A bullet's label that names what is measured, when, or the whole company.
_LABEL_NOT_A_LINE_RE = re.compile(
    r'\b(?:revenues?|sales|income|loss|profit|earnings|margins?|cash|dividends?|'
    r'total|net|gross|full[\s-]year|fy|fiscal|quarter|q[1-4]|outlook|guidance|'
    r'years?|20\d\d|headcount|employees|staff|debt|assets|liabilit\w*|equity|capex|'
    r'spending|buybacks?|repurchases?|shares?|stock|price|market|valuation|ebitda|'
    r'bottom\s+line|top\s+line|summary|overall|consolidated|highlights?|key|'
    r'results?|growth|returns?|costs?|expenses?|tax|backlog|bookings|'
    r'comparable|same[\s-]store|comps|customers|users|subscribers|members|'
    r'units|deliveries|stores|restaurants|locations)\b',
    re.IGNORECASE,
)


_PART_CUE_RE = re.compile(
    r'\b(?:including|of\s+which|comprising|consisting\s+of|made\s+up\s+of|'
    r'split\s+between|broken\s+down\s+into)\b', re.IGNORECASE)


def _listed_as_a_part(sentence, raw_value):
    """"Total revenue was $254.5 billion, including net sales of $249.6
    billion and membership fees of $4.83 billion": the figures after
    "including" are parts of the one before it."""
    raw = str(raw_value or "").strip()
    at = (sentence or "").find(raw) if raw else -1
    if at <= 0:
        return False
    cue = _PART_CUE_RE.search(sentence, 0, at)
    # A figure before the cue is the whole the parts belong to.
    return bool(cue and re.search(r'\d', sentence[:cue.start()]))


def _labels_a_business_line(sentence, heading, raw_value):
    """"Wizards of the Coast & Digital Gaming: revenue up 10% to $1.46
    billion" labels a business line, so the figure is that line's, not the
    company's. A label naming a measure, a period or the company is not."""
    label = re.match(r'\s*([^:]{3,60}):\s', sentence or "")
    if not label:
        return False
    at = sentence.find(str(raw_value).strip()) if raw_value else -1
    if at != -1 and at < label.end():
        return False
    words = label.group(1)
    if _LABEL_NOT_A_LINE_RE.search(words):
        return False
    if any(p.search(words) for p in _METRIC_PATTERNS.values()):
        return False
    # The company itself, named in the heading: "Hasbro: revenue of $5B".
    named = {w.lower() for w in re.findall(r'[A-Za-z]{3,}', heading or "")}
    if any(w.lower() in named for w in re.findall(r'[A-Za-z]{3,}', words)):
        return False
    # A business line is a name: at least one capitalized word.
    return bool(re.search(r'\b[A-Z][a-z]', words))


def _matches_segment_signal(text):
    """True if any of the three segment signals is present:
    keyword (segment/division), product brand, or generic qualifier
    with a financial trailer.
    """
    if _SEGMENT_KEYWORD_RE.search(text):
        return True
    if _SUBCOMPONENT_PRODUCT_RE.search(text):
        return True
    if _SUBCOMPONENT_GENERIC_RE.search(text):
        return True
    if _OPERATIONS_LINE_RE.search(text):
        return True
    return False


# "Equipment ops net sales" or "Financial Services operations revenue" is one
# line of the business; continuing operations are the whole of it.
_OPERATIONS_LINE_RE = re.compile(
    r'\b(?!(?:Continuing|Discontinued|Total|Consolidated|Global|Worldwide|Our|Its|'
    r'Their|Net|Overall|Core|All|Company|Group|Combined)\b)'
    r'[A-Z][a-z]+\s+(?:ops|operations)\s+(?:net\s+)?(?:sales|revenues?)\b',
)


def _split_multi_figure_claims(claims):
    """One claim per clause when a sentence states figures in separate
    clauses: "Gross profit was $27B, while assets were $38B". Only one figure
    per claim is ever compared, so the other went unchecked. A comparison like
    "$60.9 billion, up 126% from $26.97 billion" stays one claim.
    """
    out = []
    for claim in (c for whole in claims for c in _split_series(whole)):
        numbers = [str(n) for n in claim.get("numbers") or []]
        sentence = claim.get("sentence") or ""
        clauses = _CLAUSE_BREAK_RE.split(sentence) if len(numbers) > 1 else []
        placed = [
            (clause, [n for n in numbers if n.strip() in clause])
            for clause in clauses
        ]
        placed = [(clause, held) for clause, held in placed if held]
        if len(placed) < 2 or sum(len(h) for _, h in placed) != len(numbers):
            out.append(claim)
            continue
        for clause, held in placed:
            out.append({
                **claim, "sentence": clause.strip(), "numbers": held,
                "full_sentence": claim.get("full_sentence") or sentence,
            })
    return out


def _heading_names_something(heading, doc_text):
    """False for "Balance sheet" or "Full-Year 2025 Highlights", which label
    a section. Reading one as a name checks the figures against nothing, or
    against whatever page happens to carry those words.
    """
    clean = re.split(r'[:(]', re.sub(r'^#+\s*', '', heading or ""))[0].strip()
    if _COUNTRY_NAMES_RE.search(clean) or re.search(r'\b[A-Z]{2,}\b', clean):
        return True
    words = [
        w for w in re.findall(r"[A-Za-z][A-Za-z'&.]*", clean)
        if w.lower() not in _HEADING_FILLER
    ]
    if not words or all(w.lower() in _SECTION_WORDS for w in words):
        return False
    if all(w[0].isupper() for w in words):
        return True
    # Sentence case reads as a label, unless the text uses it as a name.
    first = words[0]
    return bool(re.search(r'[a-z,]\s+' + re.escape(first) + r'\b', doc_text))


# Measures only the US publishes under these names: an answer about "nonfarm
# payrolls" or "core PCE" is about the US even when it never names the country
# (half of v18's answers to questions about the US economy did not).
_US_MEASURES_RE = re.compile(
    r"\b(?:non-?farm|payrolls?|core\s+pce|\bpce\b|personal\s+consumption\s+expenditures|"
    r"u-?3\b|30-year\s+(?:fixed|mortgage)|fed\s+funds|federal\s+funds)", re.IGNORECASE)


# "US dollars", "US$" and "U.S. dollar" name a currency, not the country: a
# Turkiye answer quoting GDP in current US dollars is not about the US.
_US_CURRENCY_RE = re.compile(
    r"\b(?:US|U\.\s?S\.?|United\s+States)\s*(?:dollars?\b|\$)|\bUS\$|\bUSD\b",
    re.IGNORECASE,
)


def _without_us_currency(text):
    return _US_CURRENCY_RE.sub(" ", text or "")


# Measures only a country (not a company or a city's council) reports.
_COUNTRY_MEASURE_RE = re.compile(
    r"\b(?:GDP|gross\s+domestic\s+product|inflation|consumer\s+prices?|"
    r"unemploy\w*|jobless|life\s+expectancy|population|lifespan|"
    r"per\s+(?:capita|person|head)|income\s+per|expect(?:ed|s)?\s+to\s+live|"
    r"(?:people|residents|inhabitants)\s+(?:lived|live|living)\s+(?:there|in\s+the\s+country))\b",
    re.IGNORECASE)
# Words that open a measure's label in an answer, never its subject.
# Not "Total", "Real" or "Value": companies are named that (review, 2026-11-27).
_MEASURE_LABEL_WORDS = frozenset({
    "jobless", "unemployment", "economic", "economy", "size", "output", "growth",
    "inflation", "prices", "population", "income", "gdp", "lifespan", "figure", "measure",
})
# The economy, named: not "revenue growth" or a factory's output.
_COUNTRY_MEASURE_EXTRA_RE = re.compile(
    r"\b(?:economic\s+growth|economy|(?:total|economic|overall)\s+output)\b", re.IGNORECASE)
# Who publishes a figure is never what it is about: "Unemployment (ILO
# modeled)", "according to the IMF".
_DATA_PRODUCERS = frozenset({
    "ILO", "IMF", "OECD", "UN", "UNDP", "WHO", "World Bank", "Eurostat", "IEA", "BLS", "BEA",
})


def _country_settled(decomp, country):
    """The figure's sentence names the country, or the document names it at
    least twice. Without either, a source may confirm but not refute."""
    sentence = _without_us_currency(decomp.full_sentence or decomp.sentence or "")
    for c in _COUNTRY_NAMES_RE.findall(sentence) + _COUNTRY_ABBREV_RE.findall(sentence):
        if _COUNTRY_CANONICAL.get(c, _COUNTRY_CANONICAL.get(c.title(), c.title())) == country:
            return True
    counts = decomp.doc_country_counts or {}
    if not counts:
        return True  # built without a document (a direct call): no evidence either way
    return counts.get(country, 0) >= 2


def _countries_named(text):
    """The countries a text names, demonyms included, currency words not."""
    text = _without_us_currency(text or "")
    return {_COUNTRY_CANONICAL.get(c, _COUNTRY_CANONICAL.get(c.title(), c.title()))
            for c in _COUNTRY_NAMES_RE.findall(text) + _COUNTRY_ABBREV_RE.findall(text)}


# Where one clause of a sentence ends and the next begins: ", and eased to
# 4.2%", "whereas Timor-Leste's was", "yet its GDP per capita".
_PLACE_CLAUSE_RE = re.compile(
    r",\s*(?:and|but|yet|while|whereas|though|although|which|so)\b|"
    r"\s(?:while|whereas|but|yet|though|although)\s|;|\s[-:]\s")


def _place_clause(sentence, raw):
    """The clause of the sentence that holds the figure, cut at any clause word."""
    sentence = sentence or ""
    at = sentence.find(raw or "\0")
    if at < 0:
        return sentence
    starts = [m.end() for m in _PLACE_CLAUSE_RE.finditer(sentence, 0, at)]
    end = _PLACE_CLAUSE_RE.search(sentence, at + len(raw))
    return sentence[starts[-1] if starts else 0:end.start() if end else len(sentence)]


# A country named only to compare with: "well above Mexico's", "similar to
# Mali's", "stronger than in Germany", "far below Djibouti's".
_PLACE_COMPARED_RE = re.compile(
    r"\b(?:than(?:\s+in)?|above|below|beyond|behind|ahead\s+of|similar\s+to|like|unlike|"
    r"compared\s+(?:with|to)|versus|vs\.?|relative\s+to)\s+(?:[\w'-]+\s+){0,4}$", re.IGNORECASE)


def _place_aside_free(clause, raw):
    """The clause without asides that do not hold the figure: parentheses,
    paired dashes, paired commas."""
    def drop(m):
        return m.group() if raw and raw in m.group() else " "
    clause = re.sub(r"\([^()]*\)", drop, _without_us_currency(clause or ""))
    clause = re.sub(r"\s-\s[^-]*?\s-\s", drop, clause)
    return re.sub(r",[^,]*,", lambda m: m.group() if raw and raw in m.group() else ",", clause)


def _place_in_clause(clause, raw):
    """The countries the figure's clause names as its place: not in an aside
    that does not hold the figure (parentheses, paired dashes or commas), and
    not after a comparison word (v31: "growth was 6.2% in 2018 (stronger than
    in Germany)", "The modeled unemployment rate, well above Mexico's, was
    10.5%", "The Pacific nation, whose compact with the United States ...,
    saw real GDP growth of 5.5%")."""
    clause = _place_aside_free(clause, raw)
    found = set()
    for m in list(_COUNTRY_NAMES_RE.finditer(clause)) + list(_COUNTRY_ABBREV_RE.finditer(clause)):
        if _PLACE_COMPARED_RE.search(clause[max(0, m.start() - 60):m.start()]):
            continue
        c = m.group()
        found.add(_COUNTRY_CANONICAL.get(c, _COUNTRY_CANONICAL.get(c.title(), c.title())))
    return found


# A place the checker cannot read: a demonym-shaped word it does not know
# ("Palestinian", "Maldivian", "Bhutanese"), or a capitalized name after "in"
# or before "'s" ("in Gaza", "Nairobi's"). Known countries are removed first.
_UNREAD_PLACE_RE = re.compile(
    r"\b[A-Z][a-z]+(?:ian|ese|ean|ish|i)\b|"
    r"\b(?:in|for|of)\s+(?:the\s+)?[A-Z][a-z]{2,}\b|"
    r"\b[A-Z][a-z]{2,}'s\b")
_NOT_A_PLACE_RE = re.compile(
    r"^(?:January|February|March|April|May|June|July|August|September|October|November|"
    r"December|GDP|ILO|IMF|COVID|Covid|Real|Consumer|Its|It|The|This|That|Their|His|Her)$")


# Compared-with words, anywhere before the figure ("lower than Germany's
# 5.0%", "Compared with Germany's 5.0%, Peru's was 3.0%").
_PLACE_COMPARE_WORD_RE = re.compile(
    r"\b(?:than|above|below|beyond|behind|ahead\s+of|similar\s+to|like|unlike|"
    r"compared\s+(?:with|to)|versus|vs\.?|relative\s+to|against)\b", re.IGNORECASE)


def _compared_before(clause, raw):
    """A comparison word and a country stand between the clause's start and
    the figure: the figure may be the compared country's (review 2026-11-28:
    "Peru's inflation was lower than Germany's 5.0% in 2020")."""
    at = (clause or "").find(raw or "\0")
    if at < 0:
        return False
    head = clause[:at]
    words = list(_PLACE_COMPARE_WORD_RE.finditer(head))
    return bool(words) and bool(_countries_named(head[words[-1].end():]))


# Capitalized words that are not places: measures, fillers, sentence openers.
_NOT_A_PLACE_WORDS = frozenset("""
january february march april may june july august september october november
december gdp ilo imf covid real consumer inflation unemployment population life
growth prices price income output economy economic annual average total per
gross national domestic the it its this that these those their his her our we
in by on at after before since during from while although however and but
meanwhile over under between then still yet also even so as for of with
modeled modelled jobs work size scale people living standards health money
bottom line short answer overall today recently currently despite thanks
expectancy rate rates figure figures data year years capita dollars
""".split())


def _unread_place(clause):
    """The clause names a place the checker does not know (v31: "26.4% in
    2021 in the Palestinian territories" read as naming no country, so the
    paragraph's Pakistan took it). Fail closed: such a place is unsettled."""
    rest = _COUNTRY_NAMES_RE.sub(" ", _without_us_currency(clause or ""))
    for m in _UNREAD_PLACE_RE.finditer(rest):
        word = re.sub(r"^(?:in|for|of)\s+(?:the\s+)?|'s$", "", m.group())
        if not _NOT_A_PLACE_RE.match(word):
            return True
    # Review 2026-11-28: a bare place it cannot read ("Scotland recorded
    # 5.0%", "Northern Ireland saw", "New Mexico saw", in an answer naming
    # one country). Any capitalized word that is not a known measure or
    # filler leaves the place unsettled.
    for m in re.finditer(r"\b[A-Z][a-z]{2,}\b", rest):
        if m.group().lower() not in _NOT_A_PLACE_WORDS:
            return True
    return False


def _place_written(decomp, country):
    """The country is settled where the figure is written, so a source may
    call the figure wrong against it. A section labelled for another country
    rules it out. Otherwise the figure's own clause, asides and comparisons
    aside, names this country and no other; or, naming none, the section is
    labelled with this country, or the whole document names this country
    alone, or the paragraph names it alone and the document opens on it.

    Measured on the code each decision set was scored on, and on fresh sets
    built to break it (v30, v31); the record is in the maintainers' evaluation record.
    Errors came through headings, pronouns, the document's most-named
    country, a sentence naming two countries, a clause holding an aside, and
    a paragraph naming another country only to compare with it.
    """
    if decomp.place_paragraph is None:
        return True  # built without a document (a direct call): no evidence either way
    # v31: Djibouti's "population was 1.0 million in 2016" under "## Djibouti"
    # went to Bahrain, named in the paragraph only as "well below Bahrain's".
    if decomp.place_label and not _same_place(decomp.place_label, country):
        return False
    sentence = decomp.full_sentence or decomp.sentence
    clause = _place_clause(sentence, decomp.raw_value)
    named = _place_in_clause(clause, decomp.raw_value)
    if (_unread_place(_place_aside_free(clause, decomp.raw_value))
            or _compared_before(clause, decomp.raw_value)):
        return False
    if named:
        return _only_place(named, country)
    if decomp.place_label and _same_place(decomp.place_label, country):
        return True
    # v30/v31: "tracked Indian prices ..., and eased to 4.2%" (Bhutan's
    # figure), "3.0% in 2024, ..., and tied closely to demand in Germany"
    # (North Macedonia's), "26.4% in 2021 in the Palestinian territories,
    # whereas Pakistan's was": a country the sentence names outside the
    # figure's clause belongs to something else. Only a label settles it.
    if _countries_named(sentence):
        return False
    counts = decomp.doc_country_counts or {}
    most = max(counts.values()) if counts else 0
    # v31: North Macedonia's answer named Germany first, in an aside, and its
    # own name later and more often; the lead is the opening country only
    # when it is also the one named most.
    lead_holds = (_same_place(decomp.place_doc_lead, country)
                  and counts.get(country, 0) == most
                  and sum(1 for n in counts.values() if n == most) == 1)
    # v30: a paragraph of Namibia's answer named only Germany, in passing.
    return (_only_place(decomp.place_doc_countries, country)
            or (_only_place(_countries_named(decomp.place_paragraph), country) and lead_holds))


_COMPARE_WORD_RE = re.compile(
    r"\b(?:than(?:\s+in)?|compared\s+(?:with|to)|unlike|versus|vs\.?|relative\s+to|"
    r"behind|ahead\s+of|(?:the\s+)?same\s+(?:level|size|rate|pace|amount)\s+as|"
    r"as\s+(?:high|large|low|big|small|much|fast)\s+as)\s+(?:the\s+)?", re.IGNORECASE)


_FOR_COUNTRY_AFTER_RE = re.compile(
    r'(?:\s*\([^)]*\))?,?(?:\s+(?:in|as of)\s+(?:19|20)\d\d)?,?\s+for\s+(?:the\s+)?')


def _label_country(line):
    """The country a line is a label for: "**China.**", "China:", "## Peru",
    or the line "Bangladesh" alone; "" for a line of prose."""
    line = (line or "").strip()
    m = (re.match(r'(?:#+\s*)?\*\*\s*([^*\n]{2,45}?)\s*[.:]?\s*\*\*', line)
         or re.match(r'(?:#+\s*)?([A-Z][^.:\n]{1,45}?)\s*:(?:\s|$)', line)
         or re.fullmatch(r'(?:#+\s*)?([A-Z][^.:\n*]{1,45}?)\s*[.:]?', line))
    if not m:
        return ""
    # "## The Gambia", "**The Bahamas.**" (v29: the Gambia section went to
    # South Africa because the label kept its article).
    named = _COUNTRY_NAMES_RE.fullmatch(re.sub(r"^the\s+", "", m.group(1).strip(), flags=re.I))
    if not named:
        return ""
    return _COUNTRY_CANONICAL.get(named.group(1), _COUNTRY_CANONICAL.get(named.group(1).title(),
                                                                         named.group(1)))


def _section_country(doc_text, sentence):
    """The country labelling this sentence's paragraph, or the label line that
    is the paragraph just before it ("**Peru**" then a list)."""
    para = _paragraph_of(doc_text, sentence)
    if not para:
        return ""
    found = _label_country(para.lstrip().split("\n", 1)[0])
    if found:
        return found
    # Otherwise the nearest heading above runs the section, until the next.
    at = (doc_text or "").find((sentence or "")[:80])
    headings = re.findall(r'(?m)^#+\s*(.+)$', (doc_text or "")[:at]) if at > 0 else []
    return _label_country(headings[-1]) if headings else ""


def _paragraph_of(doc_text, sentence):
    """The paragraph (blank-line block) that holds this sentence, or ""."""
    at = (doc_text or "").find((sentence or "")[:80])
    if at < 0:
        return ""
    start = doc_text.rfind("\n\n", 0, at)
    end = doc_text.find("\n\n", at)
    return doc_text[start + 2 if start >= 0 else 0:end if end >= 0 else len(doc_text)]


def _opens_a_sentence(country, doc_text):
    """Some sentence opens with this country ("The United Arab Emirates is
    richer."): the answer is about it there, so it is no passing mention like
    "the war in neighboring Ukraine"."""
    for sentence in _SENTENCE_BREAK_RE.split(doc_text or ""):
        m = _COUNTRY_NAMES_RE.match(re.sub(r"^\W*(?:the\s+)?", "", sentence.strip(), flags=re.I))
        if m and _COUNTRY_CANONICAL.get(m.group(1), _COUNTRY_CANONICAL.get(m.group(1).title(), m.group(1))) == country:
            return True
    return False


def _compared_countries(sentence):
    """Countries named only as what a figure is set against: "than in
    Switzerland", "compared with Kenya"."""
    out = set()
    for m in _COMPARE_WORD_RE.finditer(sentence or ""):
        c = _COUNTRY_NAMES_RE.match(sentence, m.end())
        if c:
            out.add(_COUNTRY_CANONICAL.get(c.group(1), _COUNTRY_CANONICAL.get(c.group(1).title(), c.group(1))))
    return out


def _lead_country(doc_text):
    """(the country the document opens on, {country: mentions}).

    The lead is the subject of the first sentence that names a country, so
    "Mongolia, a landlocked country between China and Russia" leads with
    Mongolia however often China is named later. v20, 2026-11-26: with the
    reader down, Poland's figures took their subject from "war in
    neighboring Ukraine", "(ILO modeled)" and "Wages"."""
    text = _without_us_currency(doc_text)
    counts = {}
    for c in _COUNTRY_NAMES_RE.findall(text) + _COUNTRY_ABBREV_RE.findall(text):
        name = _COUNTRY_CANONICAL.get(c, _COUNTRY_CANONICAL.get(c.title(), c.title()))
        counts[name] = counts.get(name, 0) + 1
    for sentence in _SENTENCE_BREAK_RE.split(text):
        found = _COUNTRY_NAMES_RE.search(sentence)
        if found:
            # "Togo and Angola", "Egypt and the UAE": an answer that opens on a
            # pair is a comparison, and has no lead country.
            pair = re.match(r"\s*(?:and|or|&|versus|vs\.?)\s+(?:the\s+)?", sentence[found.end():])
            if pair and _COUNTRY_NAMES_RE.match(sentence, found.end() + pair.end()):
                return "", counts
            c = found.group()
            return _COUNTRY_CANONICAL.get(c, _COUNTRY_CANONICAL.get(c.title(), c.title())), counts
    return "", counts


def _doc_no_country(doc_text):
    """The document names no country, US or other."""
    text = _without_us_currency(doc_text)
    return bool(doc_text) and not _COUNTRY_NAMES_RE.search(text) and not _US_NAMED_RE.search(text)


def _doc_is_us(doc_text):
    """Whether a document is about the US economy: it points at US
    institutions or measures, and names no other country."""
    doc_text = _without_us_currency(doc_text)
    if not doc_text.strip() or not (_US_NAMED_RE.search(doc_text) or _US_MEASURES_RE.search(doc_text)):
        return False
    others = {
        _COUNTRY_CANONICAL.get(c, c) for c in _COUNTRY_NAMES_RE.findall(doc_text)
    } - {"United States", "U.S", "U.S.", "US", "USA", "America"}
    return not others


def _prepare_claims(claims, doc_text):
    """Give each claim the context it needs from the rest of the document."""
    _enrich_headings(claims, doc_text)
    us = _doc_is_us(doc_text)
    none = _doc_no_country(doc_text)
    for claim in claims:
        claim["doc_is_us"] = us
        claim["doc_no_country"] = none
    for claim in claims:
        if not _heading_names_something(claim.get("heading"), doc_text):
            claim["heading"] = ""
    return _apply_discourse_context(
        _split_multi_figure_claims(claims), doc_text,
    )


_EVENT_ASIDE_RE = re.compile(
    r'\([^()]*\b(?:before|after|since|following|prior\s+to|ahead\s+of|'
    r'pre-split|post-split)\b[^()]*\)',
    re.IGNORECASE,
)


def _without_compared_periods(sentence):
    """The sentence without what its figures are set against."""
    sentence = _COMPARED_QUARTER_RE.sub('', sentence)
    return _EVENT_DATE_RE.sub('', _AFTER_YEAR_RE.sub('', _COMPARED_YEAR_RE.sub(
        '', _PRIOR_FIGURE_RE.sub('', _AFTER_RATE_RE.sub('', sentence)))))


# The year right after a figure: "5.5% in 2022", "30.8% (2023)", "-0.4% 2023".
_OWN_YEAR_RE = re.compile(r'\s*(?:\(\s*)?(?:in\s+(?:fiscal\s+)?)?(20[0-3]\d)\b(?!\s*[-/]\s*\d)')
# A price basis or an annual-change label between the figure and "in 2023".
# "over 2023" is the year it is compared with, so it is not in this list.
_YEAR_ADJUNCT_RE = re.compile(
    r'\s*(?:in\s+(?:real|nominal|volume)\s+terms|year[- ]on[- ]year|year\s+over\s+year)\b',
    re.IGNORECASE,
)
_RATE_ASIDE_RE = re.compile(
    r'\bin\s+(?:real|nominal|volume)\s+terms\b|year[- ]on[- ]year|year\s+over\s+year',
    re.IGNORECASE,
)


def _own_year_after(sentence, cursor):
    """The year that belongs to the figure ending at cursor.

    "5.1% in real terms in 2023" and "5.1% year-on-year in 2023" are that
    figure's 2023. "5.1% in real terms over 2023" names no year of its own:
    "over 2023" is the comparison.
    """
    own = _OWN_YEAR_RE.match(sentence, cursor)
    if own:
        return own.group(1)
    for _ in range(2):
        adjunct = _YEAR_ADJUNCT_RE.match(sentence, cursor)
        if not adjunct:
            break
        cursor = adjunct.end()
    own = _OWN_YEAR_RE.match(sentence, cursor)
    return own.group(1) if own else None


_QUARTER_WORD_RE = re.compile(
    r'\b(first|second|third|fourth|1st|2nd|3rd|4th)[\s-]+quarter\b', re.IGNORECASE)
_QUARTER_NUMBER = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
                   "fourth": 4, "4th": 4}


_THREE_MONTHS_RE = re.compile(r'\b(?:three|3)\s+months\s+ended\b|\bquarter\s+ended\b',
                              re.IGNORECASE)
_FULL_YEAR_RE = re.compile(
    r'\b(?:full[\s-]+year|fiscal[\s-]+year|for\s+the\s+(?:full\s+)?year|annual|'
    r'twelve\s+months|12\s+months|year[\s-]+end(?:ed)?)\b', re.IGNORECASE)
# Part of a year: no single period a filing states.
_PART_YEAR_RE = re.compile(
    r'\b(?:nine|six)\s+months|\bfirst\s+(?:half|three\s+quarters)\b|'
    r'\bsecond\s+half\b|\byear[\s-]+to[\s-]+date\b|\bYTD\b', re.IGNORECASE)


_DECLARED_TICKER_RE = re.compile(
    r'\((?:NYSE|NASDAQ|Nasdaq|NasdaqGS|NasdaqGM|NYSE\s+American|NYSE\s+Arca|TSX)\s*:\s*'
    r'([A-Z][A-Z.]{0,5})\)')
_COMPARED_QUARTER_RE = re.compile(
    r'\b(?:compared\s+(?:to|with)|versus|vs\.?|from|up\s+from|down\s+from)\s+[^;]{0,60}?'
    r'\bin\s+the\s+(?:(?:first|second|third|fourth|prior[\s-]year|year[\s-]ago|same)\s+)?'
    r'(?:quarter|period)(?:\s+(?:of|in)\s+(?:fiscal\s+(?:year\s+)?|FY\s*)?(?:20)?[1-3]\d)?',
    re.IGNORECASE)
_QUARTERLY_DOC_RE = re.compile(
    r'\b(?:first|second|third|fourth)[\s-]+quarter\b|\bQ[1-4]\b|\bthree\s+months\s+ended\b',
    re.IGNORECASE)


def _quarter_in(text):
    """The quarter a text names, "fourth quarter" or "Q4", as a number."""
    found = _QUARTER_WORD_RE.search(text or "")
    if found:
        return _QUARTER_NUMBER[found.group(1).lower()]
    found = re.search(r'\bQ([1-4])\b', text or "")
    return int(found.group(1)) if found else None


def _full_year_in(text, heading=False):
    """Whether a text speaks of a whole year: "full year", "for the year",
    "twelve months". A bare "Fiscal 2026" or "FY26" is only a label: in a
    quarterly release's table "FY26" is the prior year's quarter. A heading
    joining a quarter "and Fiscal 2026" does name the year. Not "the fourth
    quarter of fiscal year 2026", which names a quarter."""
    text = re.sub(r'(quarter\s+(?:of\s+)?|Q[1-4]\s+)(?:fiscal[\s-]+(?:year\s+)?|FY\s?)',
                  r'\1', text or "", flags=re.IGNORECASE)
    if _FULL_YEAR_RE.search(text):
        return True
    return heading and bool(re.search(
        r'\band\s+(?:the\s+)?(?:fiscal|FY|full|year)\b', text, re.IGNORECASE))


def _with_quarter(time_period, sentence, heading):
    """The quarter a figure is for. The sentence's words decide first: a
    full year is the year, a quarter is that quarter. A heading naming a
    quarter alone gives it to its figures; one naming both a quarter and
    the full year ("Fourth Quarter and Fiscal 2026 Results") leaves a figure
    whose sentence names neither unknown, "Q? 2026", and an unknown period
    is never compared."""
    if re.search(r'\bQ[1-4?]\b', time_period or "", re.IGNORECASE):
        return time_period
    year = re.search(r'20[1-3]\d', time_period or "")
    if not year or _PART_YEAR_RE.search(sentence or ""):
        return time_period
    # "compared to $79.1 million in the fourth quarter of Fiscal 2025" is
    # the other figure's quarter.
    sentence = _COMPARED_QUARTER_RE.sub("", sentence or "")
    quarter = _quarter_in(sentence)
    if not quarter and _THREE_MONTHS_RE.search(sentence or ""):
        # "Three Months Ended October 31, 2025": a quarter, numbered by the
        # heading if it says which.
        named = _quarter_in(heading)
        return f"Q{named} {year.group()}" if named else f"Q? {year.group()}"
    full = _full_year_in(sentence)
    if quarter and full:
        return f"Q? {year.group()}"
    if quarter:
        return f"Q{quarter} {year.group()}"
    if full:
        return time_period
    quarter = _quarter_in(heading)
    if quarter:
        if _full_year_in(heading, heading=True):
            return f"Q? {year.group()}"
        return f"Q{quarter} {year.group()}"
    return time_period


def _subject_named_by_then(subject, sentence, doc_text):
    """A country the document first names after this sentence is not what the
    sentence is about: in a Q&A on the Dutch economy that ends "How does
    Ireland compare?", the Dutch answers are not Ireland's. The country named
    last before the sentence ("the Dutch economy") is, or else none."""
    if not subject or not doc_text or not _COUNTRY_NAMES_RE.fullmatch(subject):
        return subject
    if subject.lower() in (sentence or "").lower():
        return subject
    at = doc_text.find((sentence or "")[:40].strip())
    if at < 0:
        return subject
    first = doc_text.lower().find(subject.lower())
    if first < 0 or first < at:
        return subject
    before = list(_COUNTRY_NAMES_RE.finditer(doc_text[:at]))
    if not before:
        return ""
    named = before[-1].group()
    return _COUNTRY_CANONICAL.get(named, _COUNTRY_CANONICAL.get(named.title(), named))


_RANGE_RE = re.compile(
    r'(?<![\d.,])(?P<lo>[$\u20ac\u00a3]?\d[\d,]*(?:\.\d+)?)\s*(?P<lounit>%|percent)?\s*'
    r'(?:\u2013|\u2014|-|to)\s*(?P<hi>[$\u20ac\u00a3]?\d[\d,]*(?:\.\d+)?)'
    r'(?P<unit>\s*(?:%|percent|trillion|billion|million|thousand|bn|mn|tn)\b|\s*%)?',
    re.IGNORECASE,
)
_SCALES = {"trillion": 1e12, "tn": 1e12, "billion": 1e9, "bn": 1e9, "million": 1e6,
           "mn": 1e6, "thousand": 1e3}


def _value_range(sentence, raw_value):
    """(low, high) in base units when the figure is one end of a range:
    "~$121-127 billion" is $121 billion to $127 billion. None otherwise; a
    span of years ("from 2019 to 2024") is no range of values."""
    digits = re.search(r'\d[\d,]*(?:\.\d+)?', str(raw_value or ""))
    if not digits:
        return None
    want = digits.group().replace(",", "")
    for m in _RANGE_RE.finditer(sentence or ""):
        # "rose from 4.6% to 4.8%" is a change between two figures.
        if re.search(r'\bfrom\s*$', (sentence or "")[:m.start()], re.IGNORECASE):
            continue
        lo = re.sub(r'[^\d.]', '', m.group("lo"))
        hi = re.sub(r'[^\d.]', '', m.group("hi"))
        if want not in (lo, hi) or not lo or not hi:
            continue
        if re.fullmatch(r'(?:19|20)\d\d', lo) and re.fullmatch(r'(?:19|20)\d\d', hi):
            return None
        scale = _SCALES.get((m.group("unit") or "").strip().lower(), 1.0)
        low, high = float(lo) * scale, float(hi) * scale
        if low >= high:
            return None
        return (low, high)
    return None


def _judge_range(rng, source_results, unit):
    """A source's figure against a stated range. Inside it confirms; just
    outside is near; further out says nothing until it is clearly another
    figure. Text matches found the figure's own digits, so they only count
    when what they found lies inside the range."""
    low, high = rng
    out = []
    for r in source_results:
        sv = r.source_value
        if r.match_type not in ("exact", "close", "contradicted") or not sv:
            out.append(r)
            continue
        if low <= sv <= high:
            match = "exact"
        elif r.is_web_search or r.source_name == "Wikipedia":
            match = "no_data"
        else:
            edge = low if sv < low else high
            if unit == "percent":
                off = abs(sv - edge)
                match = "close" if off <= 0.15 else "no_data" if off <= 1.0 else "contradicted"
            else:
                off = abs(sv - edge) / max(abs(edge), 1e-10)
                match = "close" if off <= 0.025 else "no_data" if off <= 0.08 else "contradicted"
        out.append(_hold_unearned_refute(replace(r, match_type=match)))
    return out


def _split_series(claim):
    """Rates each given its own year, or else the earlier figures peeled off."""
    dated = _split_dated_series(claim)
    return dated if len(dated) > 1 else _split_prior_figures(claim)


def _split_dated_series(claim):
    """One claim per rate when a sentence gives each rate its own year:
    "Real GDP grew 11.4% in 2021, then 5.5% in 2022 and 5.1% in 2023". The
    sentence's first year went to all three."""
    numbers = [str(n) for n in claim.get("numbers") or []]
    sentence = claim.get("sentence") or ""
    if len(numbers) < 2:
        return [claim]
    dated, cursor = {}, 0
    for n in numbers:
        raw = n.strip()
        at = sentence.find(raw, cursor)
        if at < 0:
            return [claim]
        cursor = at + len(raw)
        own = _own_year_after(sentence, cursor)
        if raw.endswith("%") and own:
            dated[n] = own
    if len(dated) < 2 or len(set(dated.values())) < 2:
        return [claim]
    rest = [n for n in numbers if n not in dated]
    out = [{**claim, "numbers": rest}] if rest else []
    out += [{**claim, "numbers": [n], "own_year": dated[n]} for n in numbers if n in dated]
    return out


def _split_prior_figures(claim):
    """Peel "up from $620 million a year earlier" off as its own claim, so a
    second figure in the sentence gets compared, against the earlier year.
    "up 126% from $26.97 billion" stays: that figure is what the rate is of.
    """
    numbers = [str(n) for n in claim.get("numbers") or []]
    sentence = claim.get("sentence") or ""
    if len(numbers) < 2:
        return [claim]
    prior = {}
    for found in _PRIOR_FIGURE_RE.finditer(sentence):
        if (found.group("period") or found.group("before_figure")
                or found.group("lead").lower().startswith(("up", "down"))):
            year = found.group("year") or found.group("before_figure") or ""
            prior[found.group("figure").strip()] = year
            if found.group("approx"):
                # The figure as the text gives it: "about 8%".
                prior[(found.group("approx") + found.group("figure")).strip()] = year
    for found in _AFTER_RATE_RE.finditer(sentence):
        year = found.group("year") or ""
        prior[found.group("figure").strip()] = year
        if found.group("approx"):
            prior[(found.group("approx") + found.group("figure")).strip()] = year
    held =[n for n in numbers if n.strip() in prior]
    if not held or len(held) == len(numbers):
        return [claim]
    rest = [n for n in numbers if n not in held]
    out = [{**claim, "numbers": rest}]
    for n in held:
        # Its own clause, when the figure it is set against is there too: in
        # "GDP was $811 billion in 2023, but real growth slowed to 0.2% after
        # 5.3% in 2022", 5.3% is growth, and "World Bank" is not its subject.
        clause = _clause_holding(sentence, n)
        own = clause if any(r.strip() in clause for r in rest) else sentence
        out.append({
            **claim, "numbers": [n], "prior_figure": True,
            "prior_year": prior[n.strip()], "sentence": own,
            "full_sentence": claim.get("full_sentence") or sentence,
        })
    return out


# What the reader calls a metric, where the checkers use another name.
_READER_METRIC_WORDS = {
    "inflation": r'\b(?:inflation|consumer\s+prices|cpi)\b',
    "unemployment": r'\b(?:unemployment|jobless)',
    "life_expectancy": r'\blife\s+expectancy\b',
}


def _sentence_names_metric(sentence, reader_metric):
    """Whether the sentence's own words name the metric the reader gave."""
    words = _READER_METRIC_WORDS.get(reader_metric)
    if words:
        return bool(re.search(words, sentence, re.IGNORECASE))
    compiled = _METRIC_PATTERNS.get(reader_metric)
    return bool(compiled and compiled.search(sentence))


_PHYSICAL_METRICS = frozenset({"height", "length", "diameter", "weight", "area", "lifespan"})
_READER_METRIC_NAMES = {"life_expectancy": "lifespan"}
_READER_INDICATOR_WORDS = {
    "gdp_per_capita": "per capita", "inflation": "inflation",
    "unemployment": "unemployment", "life_expectancy": "life expectancy",
}


def _apply_reader(claims, doc_text, status=None):
    """Attach the model's reading of each figure to its claim, one figure to a
    claim, and add figures the rules missed. With no reading, nothing changes.
    """
    figures = read_figures(doc_text, status=status)
    if not figures:
        return claims
    by_key = {}
    for figure in figures:
        by_key.setdefault(figure_key(figure["figure"]), figure)
    seen = set()
    out = []
    for claim in claims:
        numbers = [str(n) for n in claim.get("numbers") or []]
        for number in numbers or [""]:
            reading = by_key.get(figure_key(number))
            if reading:
                seen.add(figure_key(number))
            out.append({**claim, "numbers": [number] if number else [], "reader": reading})
    for key, figure in by_key.items():
        if key in seen or figure["status"] == "not_a_fact":
            continue
        sentence = _own_sentence(doc_text, figure["figure"]) or figure["figure"]
        out.append({
            "sentence": sentence, "numbers": [figure["figure"]], "reader": figure,
            "doc_is_us": _doc_is_us(doc_text),
            "doc_no_country": _doc_no_country(doc_text),
        })
    return out


def _apply_discourse_context(claims, doc_text):
    """Attach the subject and year a sentence inherits from those before it.

    Prose names its subject once and then says "the company" or nothing:
    "Net income for the year came in at $5.7 billion." Taken alone that has no
    company and no year, so it could never be checked.
    """
    if not doc_text:
        return claims
    out = []
    for claim in claims:
        sentence = (claim.get("sentence") or "").strip()
        at = doc_text.find(sentence) if sentence else -1
        if at <= 0:
            out.append(claim)
            continue
        before = doc_text[:at]
        paragraph = before[before.rfind("\n\n") + 2:]
        # Walk forward keeping the current subject. An anaphoric sentence
        # keeps it whatever else it mentions, and a region only locates it:
        # "the largest economy in Southeast Asia".
        subject = ""
        named_so_far = set()
        for earlier in _SENTENCE_BREAK_RE.split(before):
            earlier = earlier.strip()
            if earlier.startswith('#'):
                if not _heading_names_something(earlier, doc_text):
                    continue
                earlier = re.split(r'[:(]', re.sub(r'^#+\s*', '', earlier))[0].strip()
                # A title is a name as written: "WD-40 Company".
                if earlier and is_likely_entity(earlier):
                    subject = earlier
                    named_so_far.add(earlier)
                    continue
            earlier = _without_lead_in(earlier)
            if not earlier or _ANAPHORIC_OPENING_RE.match(earlier):
                continue
            # "Rivals such as Arista", "pace with Samsung": mentioned in passing.
            named = extract_subject("", _PASSING_MENTION_RE.split(earlier)[0])
            # "Tesla sells cars in China and the US": the name that opens the
            # sentence with its verb is the subject; a country after "in" only
            # says where (the pinned xfail of 72186bc).
            opener = _NAME_OPENS_RE.match(earlier)
            if (opener and named and _COUNTRY_NAMES_RE.fullmatch(named)
                    and not _COUNTRY_NAMES_RE.search(opener.group(1))
                    and opener.group(1).split()[0].lower() not in _MEASURE_LABEL_WORDS
                    and re.search(r'\b(?:in|to|from|across|throughout|into)\s+(?:the\s+)?'
                                  + re.escape(named), earlier)):
                named = opener.group(1).strip()
            if named and named not in _REGIONS:
                subject = named
                named_so_far.add(named)
            for country in _COUNTRY_NAMES_RE.findall(earlier):
                named_so_far.add(_COUNTRY_CANONICAL.get(country, country))
        # This paragraph first, then the document: a list under "Balance
        # sheet" belongs to the year named at the top. An inherited year can
        # confirm a figure but never refute one.
        year = ""
        for scope in (paragraph, before):
            for earlier in reversed(_SENTENCE_BREAK_RE.split(scope)):
                found = _TIME_RE.findall(_without_compared_periods(earlier))
                if found:
                    last = found[-1]
                    year = last if isinstance(last, str) else last[0]
                    break
            if year:
                break
        out.append({
            **claim,
            "inherited_subject": subject,
            "inherited_year": year,
            "year_sole": len(set(
                re.findall(r'20[1-3]\d', _without_compared_periods(before))
            )) == 1,
            "subject_ambiguous": len(named_so_far) > 1,
        })
    return out


def _metric_beside(sentence, raw_value, before_only=False):
    """The metric named closest to the figure, so that in "GDP was $19 billion
    with a population of 3 million" each figure gets its own. A figure's
    specific name and a broad word inside it end at the same place, and the
    pattern order prefers the specific one.
    """
    at = sentence.find(str(raw_value).strip()) if raw_value else -1
    if at < 0:
        for name, pattern in _METRIC_PATTERNS.items():
            if pattern.search(sentence):
                return name
        return ""
    end = at + len(str(raw_value).strip())
    # "dividends of $1.60 per share" is a dividend, not earnings per share.
    if (re.match(r'\s*per\s+share', sentence[end:])
            and re.search(r'\bdividends?\b', sentence[:at], re.IGNORECASE)):
        return "dividends_paid"
    best, best_gap = "", None
    for name, pattern in _METRIC_PATTERNS.items():
        for found in pattern.finditer(sentence):
            if before_only and found.end() > at:
                continue
            # On a tie the name before the figure wins: "a net loss of $188M as
            # inventory piled up".
            gap = at - found.end() if found.end() <= at else found.start() - end + 1
            # "about" and "some" only say it is a count of something.
            if name == "count":
                gap += 10_000
            if best_gap is None or gap < best_gap:
                best, best_gap = name, gap
    return best


_ENTITY_FILLER = frozenset({
    "the", "and", "inc", "inc.", "corp", "corp.", "corporation", "company", "co.",
    "ltd", "ltd.", "plc", "group", "holdings", "republic", "of", "united", "states",
})


def _main_year(doc_text):
    """The year a document names most, or "" when none leads."""
    import collections
    counts = collections.Counter(re.findall(r'\b(?:19|20)\d\d\b', doc_text or "")).most_common(2)
    if not counts or (len(counts) > 1 and counts[0][1] == counts[1][1]):
        return ""
    return counts[0][0]


def _sentence_names_another(sentence, raw_value, entity, doc_text=""):
    """The sentence's own subject, when the reader's entity is nowhere in
    the sentence; else "". Only a name that opens the sentence and that the
    document names again counts: "Deere took the harder hit, with ... EPS
    falling to $22.05". A place ("in the US and Canada"), an adjective
    ("Martian") or a label ("Health:") leaves the reader's entity standing."""
    words = [w for w in re.findall(r"[A-Za-z][\w&.'-]{2,}", entity or "")
             if w.lower() not in _ENTITY_FILLER]
    if not words or any(re.search(r'\b' + re.escape(w) + r'\b', sentence, re.IGNORECASE)
                        for w in words):
        return ""
    at = sentence.find(str(raw_value).strip()) if raw_value else -1
    if at <= 0:
        return ""
    named = extract_subject("", sentence[:at])
    opens = re.match(r'\s*(?:The\s+)?' + re.escape(named) + r"(?:'s)?\s+[a-z]", sentence) \
        if named else None
    if (not opens or _COUNTRY_NAMES_RE.fullmatch(named)
            or len(re.findall(r'\b' + re.escape(named) + r'\b', doc_text or "")) < 2):
        return ""
    return named


def decompose_claim(claim, topic="", doc_text="", doc_primary_entity=""):
    """Decompose a claim dict (from analyze_claims) into structured parts.

    Returns ClaimDecomposition with subject, metric, value, time, type.

    The doc_primary_entity argument is the document's most-mentioned
    likely entity. It is used as a fallback subject for sentences that
    do not name their own entity (e.g., "Common side effects include
    nausea (44%)" in an Ozempic document).
    """
    sentence = claim.get("sentence", "")
    heading = claim.get("heading", "")
    numbers = claim.get("numbers", [])

    # When multiple numbers exist, prefer dollar amounts over percentages.
    # "Revenue of $391B, up 2%" -> primary is $391B, not 2%.
    # Dollar amounts are the verifiable data point. Percentages are derived.
    # A number that is part of a name is not the claim: Taipei 101 stands
    # 620 metres tall, and checking "101" found it in the building's article.
    if len(numbers) > 1:
        not_names = [
            n for n in numbers
            if not re.search(
                r'\b[A-Z][a-zA-Z]+\s+' + re.escape(str(n).strip()) + r'\b',
                sentence,
            )
        ]
        numbers = not_names or numbers

    raw_value = numbers[0] if numbers else ""
    if len(numbers) > 1:
        for n in numbers:
            if (
                any(n.startswith(sym) for sym in "$€£¥₹")
                or (n.endswith(("B", "M", "T")) and n[0].isdigit())
            ):
                raw_value = n
                break

    # Who an anaphoric sentence means comes from the sentences before it.
    # Otherwise its own words go first, then what precedes it.
    inherited = claim.get("inherited_subject", "")
    subject_ambiguous = False
    # "Its economy expanded 7.6% in 2021, while Nigeria grew 1.1%": the
    # pronoun opens the sentence, but a later clause that names its own
    # country is that country's (2026-11-27, the site's comparison example).
    _at = sentence.find(str(raw_value).strip()) if raw_value else -1
    _breaks = list(_CLAUSE_BREAK_RE.finditer(sentence[:_at])) if _at > 0 else []
    _own_place = (_COUNTRY_NAMES_RE.search(_without_us_currency(sentence[_breaks[-1].end():_at]))
                  if _breaks else None)
    if inherited and _ANAPHORIC_OPENING_RE.match(sentence) and _own_place:
        c = _own_place.group(1)
        subject = _COUNTRY_CANONICAL.get(c, _COUNTRY_CANONICAL.get(c.title(), c))
    elif inherited and _ANAPHORIC_OPENING_RE.match(sentence):
        subject = inherited
    else:
        # The name before the figure is what the figure is about: a name after
        # it, as in "$159B, a total that included SRS", is only mentioned.
        # Within the sentence, only its own clause: in "Chile had 19.7 million,
        # while Peru had 33.8 million" the second figure is Peru's.
        figure_at = sentence.find(str(raw_value).strip()) if raw_value else -1
        head = sentence[:figure_at] if figure_at > 0 else ""
        clause_breaks = list(_CLAUSE_BREAK_RE.finditer(head))
        if clause_breaks:
            head = head[clause_breaks[-1].end():]
        subject = extract_subject("", head) if head else ""
        # "Deere took the harder hit, with ... EPS falling to $22.05": a
        # clause that names nobody belongs to the sentence's own subject,
        # not to the one the sentence before it named.
        if clause_breaks and not subject:
            subject = extract_subject("", sentence[:figure_at])
        if head and not subject and heading:
            subject = extract_subject(heading, "")
        # "Austria 5.2% in 2020, Iceland 4.0% in 2015": a country right before
        # the figure owns it (2026-11-27).
        if figure_at > 0:
            right_before = re.search(r'(?:^|[,;:(]\s*|\band\s+)([A-Z][\w\'. -]{1,40}?)\s*:?\s*$',
                                     sentence[:figure_at])
            if right_before:
                named = _COUNTRY_NAMES_RE.fullmatch(right_before.group(1).strip())
                if named:
                    subject = _COUNTRY_CANONICAL.get(named.group(1), named.group(1))
        # "7.6 percent in Chile", "5.0% in 2018 in Malawi": a place right after
        # the figure owns it.
        if figure_at >= 0:
            after = sentence[figure_at + len(str(raw_value).strip()):]
            placed = re.match(
                r'\s*(?:in\s+(?:19|20)\d\d\s+)?(?:[a-z]+\s+){0,2}?in\s+(?:the\s+)?(.{0,40})', after,
            )
            country = placed and _COUNTRY_NAMES_RE.match(placed.group(1))
            if country:
                subject = _COUNTRY_CANONICAL.get(
                    country.group(), country.group(),
                )
        if subject in _REGIONS:
            subject = ""
        if not subject and inherited:
            subject_ambiguous = bool(claim.get("subject_ambiguous"))
        if not subject:
            subject = inherited or extract_subject(
                heading, sentence, topic,
                doc_text=doc_text, num_raw=raw_value,
                doc_primary_entity=doc_primary_entity,
            )
    value = normalize_value(raw_value, sentence)

    # "Bosnia and Herzegovina's economy": a subject that is one word of a longer
    # country name the document uses is that country (v27: "Herzegovina").
    if subject and " " not in subject and not _COUNTRY_NAMES_RE.fullmatch(subject):
        fulls = {_COUNTRY_CANONICAL.get(m.group(1), m.group(1))
                 for m in _COUNTRY_NAMES_RE.finditer(doc_text or sentence)
                 if " " in m.group(1) and re.search(rf"\b{re.escape(subject)}\b", m.group(1))}
        if len(fulls) == 1:
            subject = fulls.pop()

    # "compared with 15.7% in 2019 for Bosnia and Herzegovina": a country named
    # with "for" right after the figure is the figure's own (v27).
    at = sentence.find(raw_value) if raw_value else -1
    after = _FOR_COUNTRY_AFTER_RE.match(sentence, at + len(raw_value)) if at >= 0 else None
    named_after = _COUNTRY_NAMES_RE.match(sentence, after.end()) if after else None
    if named_after:
        c = named_after.group(1)
        subject = _COUNTRY_CANONICAL.get(c, _COUNTRY_CANONICAL.get(c.title(), c))
        subject_ambiguous = False

    # Detect metric type
    metric = _metric_beside(
        sentence, raw_value, before_only=bool(claim.get("prior_figure")),
    )

    # "Inflation has run hotter than in Switzerland, reaching 12.4%": a country
    # named only as the comparison is not the subject when the sentences before
    # named another (v25: Serbia's inflation was checked as Switzerland's).
    if (subject and inherited and subject != inherited
            and _COUNTRY_NAMES_RE.fullmatch(subject) and _COUNTRY_NAMES_RE.fullmatch(inherited)
            and _compared_countries(sentence)):
        compared = _compared_countries(sentence)
        named = {_COUNTRY_CANONICAL.get(c, _COUNTRY_CANONICAL.get(c.title(), c))
                 for c in _COUNTRY_NAMES_RE.findall(_without_us_currency(sentence))}
        if subject in compared and named <= compared:
            subject = inherited
    # "**China.** The economy was ...", "Bangladesh" on its own line above a
    # list: a section labelled with a country owns the figures in it that name
    # no country (v28: China's figures went to Macao, the answer's first
    # country; Bangladesh's bullets to the Maldives).
    section = _section_country(doc_text, sentence)
    section_bound = False
    if (section and subject != section
            and not _COUNTRY_NAMES_RE.search(_without_us_currency(sentence))):
        subject, subject_ambiguous, section_bound = section, False, True
    # A country's measure in a document about one country belongs to that
    # country when its own sentence names none.
    if (not section_bound
            and (_COUNTRY_MEASURE_RE.search(sentence) or _COUNTRY_MEASURE_EXTRA_RE.search(sentence))
            and not _COUNTRY_NAMES_RE.search(_without_us_currency(sentence))):
        lead, counts = _lead_country(doc_text)
        is_country = bool(_COUNTRY_NAMES_RE.fullmatch(subject or ""))
        own = bool(subject) and subject != inherited
        # "Jobless rate:", "Economic growth:", "Size of the economy" open a line
        # in an answer: a label, not what the figure is about (v22).
        label_word = bool(subject) and subject.split()[0].lower() in _MEASURE_LABEL_WORDS
        # "Incomes are rising too: GDP per capita reached $4,717": words before
        # a colon that comes ahead of the figure lead into it; they are not
        # what it is about (2026-11-27, the site's Vietnam example).
        at_fig = sentence.find(raw_value) if raw_value else -1
        lead_in = sentence[:at_fig].rsplit(":", 1)[0] if at_fig > 0 and ":" in sentence[:at_fig] else ""
        if subject and not is_country and lead_in and re.search(
                rf"\b{re.escape(subject)}\b", lead_in):
            label_word = True
        # A section heading ("**Jobs**", "## People") and an adjective
        # ("by northern European standards") are not what a figure is about
        # (2026-11-27: 173 true figures on v26-v27 had no country this way).
        # A word that never acts in the answer ("Real GDP rose", "Health
        # outcomes", "Remember that") is a modifier or a verb, not an entity:
        # "Nairobi has", "Safaricom's revenue" keep their own figures (v26-v28:
        # 231 true figures had no country, "Real" and "Remember" among them).
        if subject and not is_country and " " not in subject and not re.search(
                rf"\b{re.escape(subject)}(?:['\u2019]s\b|\s+(?:has|had|is|was|are|were|grew|rose|"
                rf"fell|saw|reported|recorded|posted|employs|counts|produced|exports|imports)\b)",
                doc_text or ""):
            label_word = True
        if subject and not is_country and " " not in subject and (
                re.search(rf"(?m)^[#*\s]*{re.escape(subject)}[*:\s]*$", doc_text or "")
                or (re.fullmatch(r"[A-Z][a-z]+(?:an|ean|ian|ese|ish|ic)", subject)
                    and re.search(rf"\b{re.escape(subject)}\s+(?!(?:has|had|is|was|are|were|"
                                  rf"grew|fell|rose|saw|says|said|reported|recorded)\b)[a-z]",
                                  sentence))):
            label_word = True
        # The lead country is only for an answer about one country: named at
        # least twice as often as every other. A comparison keeps each
        # country's own figures (v25: the UAE's life expectancy went to Egypt,
        # Angola's inflation to Togo on a tie).
        # _lead_country is "" for an answer that opens on two countries ("Togo
        # and Angola", v25), so a comparison keeps each country's figures. A
        # country that opens one of the sentences is never a passing mention.
        # The paragraph's country before the document's, whenever the figure's
        # own sentence names none and its subject is not named there either
        # ("Start with Greece. ... Inflation was -1.7% in 2015" went to
        # Germany, the answer's most-named country; v29).
        para = _paragraph_of(doc_text, sentence)
        para_country = _lead_country(para)[0] if para else ""
        # Only a subject from nowhere nearby gives way: one the paragraph
        # itself names ("Belize had ..., and income per person of $6,012")
        # is local evidence and keeps the figure (the gate caught 12).
        if (para_country and subject != para_country
                and not (subject and re.search(rf"\b{re.escape(subject)}\b", para))
                and (not subject or _COUNTRY_NAMES_RE.fullmatch(subject) or not own or label_word)):
            subject, subject_ambiguous = para_country, False
        elif lead and subject != lead:
            not_a_place = (not is_country
                           and (not own or subject in _DATA_PRODUCERS or label_word)
                           and all(n <= counts.get(lead, 0) for n in counts.values()))
            passing = (is_country and not own
                       and counts.get(lead, 0) >= 2 * counts.get(subject, 0)
                       and not _opens_a_sentence(subject, doc_text))
            # A passing mention gives way to the country its paragraph opens on,
            # before the document's (v26: Armenia's figures after "capital from
            # Russia" went to Finland, the answer's first country).
            # A country its own paragraph opens on is not passing there (v27:
            # "Taking the Bahamas up top." then Bahamas' figures went to Mexico).
            # A figure whose subject is not a place goes to the country its
            # paragraph opens on before the document's (v27: "(ILO modeled)" in
            # the Bahamas paragraph went to Mexico, the answer's first country).
            if passing or not_a_place:
                para = _paragraph_of(doc_text, sentence)
                para_lead = _lead_country(para)[0] if para else ""
                if passing and para_lead == subject:
                    passing = False
                elif para_lead:
                    lead = para_lead
            if not_a_place or passing:
                subject, subject_ambiguous = lead, False

    # Detect time period from sentence, then heading as fallback.
    # Claims under "NVIDIA Fiscal Year 2026 Financial Summary" inherit
    # FY2026 even when the sentence itself has no year.
    # "lower than in fiscal 2025" is what the figure is set against.
    # "(before the stock split in 2024)" dates an event, not the figure.
    time_match = _TIME_RE.search(
        _EVENT_ASIDE_RE.sub('', _without_compared_periods(sentence)),
    )
    if not time_match and heading:
        time_match = _TIME_RE.search(heading)
    time_period = time_match.group(1) if time_match else ""
    # "37.6 million in 2023, and GDP reached $812 billion in 2022": a year right
    # after the figure, in its own clause, is the figure's (v24 Poland, confirmed
    # against 2023's GDP). "in 2015 dollars" is a price base, not a year.
    if raw_value:
        at = sentence.find(str(raw_value).strip())
        if at >= 0:
            own = re.match(r'\s*(?:\w+\s+){0,3}?in\s+((?:19|20)\d\d)\b(?!\s*(?:dollars|prices|terms|'
                           r'constant|real|us\$|\$|euros?|pounds?|yen))',
                           sentence[at + len(str(raw_value).strip()):], re.IGNORECASE)
            # Only a plain year taken from an earlier clause is replaced: a
            # quarter, a half or a fiscal label is the existing logic's.
            earlier = sentence[:at]
            if (own and re.fullmatch(r'(?:19|20)\d\d', time_period or "")
                    and own.group(1) != time_period
                    and time_period in earlier
                    and re.search(r',\s*and\b|;|,\s*while\b|,\s*but\b',
                                  earlier[earlier.find(time_period):])):
                time_period = own.group(1)
    year_inherited = False
    if not time_period and claim.get("inherited_year"):
        time_period = claim["inherited_year"]
        year_inherited = True

    # Prior-year claims: when the sentence references "prior year" /
    # "previous year" / "last year" and this specific raw_value appears
    # right after that phrase, the claim is about the year BEFORE the
    # sentence/heading's main year. Decrement the year by 1 so SEC
    # EDGAR matches against the right period.
    # A figure set against the current one can confirm the earlier year, but a
    # phrase this loose is not enough to refute it.
    after_vs = bool(_FIGURE_AFTER_VS_RE.search(
        sentence[:max(sentence.find(str(raw_value).strip()), 0)],
    ))
    if after_vs:
        year_inherited = True
    year_shifted = False
    if claim.get("prior_figure"):
        base = re.search(r'20[1-3]\d', time_period)
        if claim.get("prior_year"):
            time_period = claim["prior_year"]
        else:
            time_period = str(int(base.group()) - 1) if base else ""
        year_inherited = True
    elif time_period and _is_prior_year_claim(sentence, raw_value):
        year_match = re.search(r'20[1-3]\d', time_period)
        year_shifted = bool(year_match)
        if year_match:
            old_year = int(year_match.group())
            time_period = re.sub(
                r'20[1-3]\d',
                str(old_year - 1),
                time_period,
                count=1,
            )

    # Detect claim type
    if claim.get("is_prediction") or _PROJECTION_RE.search(sentence):
        claim_type = "projection"
    elif _DERIVED_RE.search(sentence) and "%" in raw_value:
        claim_type = "derived"
    else:
        claim_type = "direct"

    # Detect unit. Values are dimensional categories (currency,
    # distance, mass, time, count, percent, other) rather than concrete
    # units (USD, EUR, m, kg). The dimensional enum matches
    # what the corpus monitoring pipeline records via the
    # SUBJECT_CLASSES enum in monitoring.py.
    # Detect currency: USD "$" and non-USD symbols (€, £, ¥, ₹).
    # Three detection layers because the raw_value from
    # claim_analysis may or may not carry the currency symbol:
    #   1. Symbol in raw_value ("$383B", "€30.9B").
    #   2. Non-USD symbol in the sentence (handles the common
    #      case where claim extraction strips the prefix and
    #      raw_value is "30.9" but the sentence has "€30.9").
    #      USD "$" is NOT checked in the sentence because "$"
    #      is too common as a formatting character; the
    #      raw_value check plus the keyword check cover USD.
    #   3. Currency keyword in the sentence ("dollar", "euro",
    #      "pound", "yen", "rupee", and their ISO codes).
    # The currency and percent words are read in the figure's own clause:
    # "The population was 0.4 million in 2017, and GDP in current US dollars
    # was $11.9 billion" is a head count, not dollars (2026-11-27: every
    # population figure sharing a sentence with a dollar figure went unchecked).
    own_clause = _clause_holding(sentence, raw_value)
    if (
        any(raw_value.startswith(sym) for sym in "$€£¥₹")
        or any(sym in own_clause for sym in "€£¥₹")
        or re.search(
            r'\b(?:dollars?|euros?|pounds?|yen|rupees?|usd|eur|gbp|jpy|inr)\b',
            own_clause, re.IGNORECASE,
        )
    ):
        unit = "currency"
    elif raw_value.endswith("%") or "percent" in own_clause.lower():
        unit = "percent"
    elif re.search(r'\b(km|km2|kilomet(?:er|re)s?|miles?|meters?|metres?|m|ft|feet)\b', sentence, re.IGNORECASE):
        unit = "distance"
    elif re.search(r'\b(kg|kilograms?|tonnes?|grams?|lbs?|pounds?)\b', sentence, re.IGNORECASE):
        unit = "mass"
    elif re.search(r'\b(years?|months?|weeks?|days?)\b', sentence, re.IGNORECASE) and metric == "lifespan":
        unit = "time"
    else:
        unit = "count"

    is_segment = _detect_segment_claim(sentence, heading, doc_text, raw_value)

    # The model's reading, already checked against the text, replaces the rules'.
    reading = claim.get("reader")
    metric_inferred = False
    if reading:
        own_name = _sentence_names_another(
            sentence, raw_value, reading["entity"], doc_text)
        if reading["entity"] and not own_name:
            subject = reading["entity"]
            subject_ambiguous = False
        elif reading["entity"]:
            # "Deere took the harder hit, with ... EPS falling to $22.05": the
            # model knew $22.05 was Caterpillar's, but the text says Deere,
            # and the text is what is being checked.
            subject = own_name
            subject_ambiguous = False
        # A word in the sentence naming what is measured ("radius") is more
        # exact than the model's broad label ("length").
        if reading["metric"] and metric not in _PHYSICAL_METRICS:
            metric_inferred = not metric and not _sentence_names_metric(
                sentence, reading["metric"],
            )
            metric = _READER_METRIC_NAMES.get(reading["metric"], reading["metric"])
            if metric not in _METRIC_PATTERNS:
                metric = ""
        if reading["period"]:
            time_period = reading["period"]
            year_inherited = not reading["period_in_sentence"]
        # The model's sense of what is future is not evidence: it called
        # reported FY2026 results a forecast. Only wording in the text counts.
        from claim_analysis import without_measured_estimates
        if (reading["status"] in ("forecast", "opinion")
                and _FORECAST_WORDING_RE.search(without_measured_estimates(sentence))):
            claim_type = "projection"
        # A series is chosen by the words in the sentence: give it the word.
        word = _READER_INDICATOR_WORDS.get(reading["metric"])
        if word and word not in sentence.lower():
            sentence = f"{sentence} ({word})"

    subject = _subject_named_by_then(subject, sentence, doc_text)
    time_period = _with_quarter(time_period, sentence, heading)
    # In a release that speaks of a quarter, a figure whose own words name
    # neither the quarter nor the whole year may be either: it can confirm
    # against the year, never refute.
    if (re.search(r'20[1-3]\d', time_period or "")
            and not re.search(r'\bQ[1-4?]\b', time_period, re.IGNORECASE)
            and doc_text and _QUARTERLY_DOC_RE.search(doc_text)
            and not _full_year_in(_COMPARED_QUARTER_RE.sub("", sentence))
            and not _PART_YEAR_RE.search(sentence)):
        found_year = re.search(r'20[1-3]\d', time_period).group()
        time_period = f"Q? {found_year}"

    # "After the fourth quarter of 2022, GDP grew 5.1% in 2023" is 2023.
    # The year has to be written on this figure, and the other year has to
    # be the leading quarter, half, or month. A year on the next figure,
    # and a year in parentheses, stay where the rest of the reading put them.
    year_own = bool(claim.get("own_year"))
    if year_own:
        time_period, year_inherited = claim["own_year"], False
    else:
        previous, own = _figure_clauses(sentence, raw_value)
        beside = _year_token(own)
        period_year = _year_token(time_period)
        if (beside and period_year and beside != period_year and previous
                and _year_token(previous) == period_year
                and (_quarter_in(previous) is not None
                     or _PART_OF_YEAR_FIGURE_RE.search(previous)
                     or _THREE_MONTHS_RE.search(previous)
                     or _MONTH_NAME_RE.search(previous))):
            time_period, year_inherited = beside, False

    return ClaimDecomposition(
        subject=subject,
        metric=metric,
        value=value,
        raw_value=raw_value,
        unit=unit,
        time_period=time_period,
        year_inherited=year_inherited,
        # A figure set against another is explicitly not this year's.
        full_sentence=claim.get("full_sentence", ""),
        doc_is_us=bool(claim.get("doc_is_us")),
        doc_no_country=bool(claim.get("doc_no_country")),
        doc_country_counts=_lead_country(doc_text)[1] if doc_text else {},
        place_paragraph=_paragraph_of(doc_text, sentence) if doc_text else None,
        place_label=_section_country(doc_text, sentence) if doc_text else "",
        place_doc_countries=frozenset(_countries_named(doc_text)) if doc_text else frozenset(),
        place_doc_lead=_lead_country(doc_text)[0] if doc_text else "",
        doc_about_economy=bool(doc_text and re.search(
            r'\b(?:gdp|economy|economic)\b', doc_text, re.IGNORECASE)),
        doc_says_averages=bool(doc_text and _DOC_AVERAGES_RE.search(doc_text)),
        metric_inferred=metric_inferred,
        year_own=year_own,
        doc_tickers=",".join(sorted(set(_DECLARED_TICKER_RE.findall(doc_text or "")))),
        # A year reached by counting back is not the label the text dated.
        fiscal_end="" if (claim.get("prior_figure") or year_shifted)
        else _fiscal_end(sentence, doc_text, time_period),
        year_sole=(bool(claim.get("year_sole")) and year_inherited
                   and not claim.get("prior_figure") and not after_vs),
        doc_main_year=_main_year(doc_text),
        subject_ambiguous=subject_ambiguous,
        claim_type=claim_type,
        sentence=sentence,
        heading=heading,
        is_segment=is_segment,
    )


# ================================================================
# Sources
# ================================================================

_HEADERS = {"User-Agent": "FrameCheck/0.1 (claim-verification; contact@clarethium.com)"}
# Per-operation socket timeout for outbound provider calls. Bumped
# from 5s to 8s on 2026-05-06 after production probe from Fly ORD
# measured a single Wikipedia query (api.php query + extract round
# trip) at ~4.16s. The 5s budget left no headroom for SSL handshake
# variance and produced intermittent
# `URLError: <urlopen error _ssl.c:993: The handshake operation
# timed out>` lines in production logs that mapped to 0-of-N
# verified-claims surfaces for users (the "0 verified" symptom the
# operator reported). 8s is the smallest value that absorbs the
# observed handshake variance without doubling the wait on real
# provider failures.
#
# Trade-off: slow providers fail 3s later than before. The outer
# SN_FETCH_JSON_DEADLINE_SECONDS (12s) and SN_BUDGET_SECONDS (25s)
# still bound the total per-comparison wait; bumping the per-op
# timeout only affects whether a single hung socket gets one more
# read attempt before the outer bound fires.
#
# Override via SN_PER_OP_TIMEOUT_SECONDS env var so the operator can
# tighten when production network paths improve, or further loosen
# during a transient routing problem to a specific provider.
def _read_float_env(name: str, default: float) -> float:
    """Read a float env var with a default. A malformed value (non-numeric
    or zero/negative) falls back to the default with a stderr log so the
    operator sees it; never raises at module import time. The default is
    the fallback for module-level constants that must initialize during
    `import`, where a raised ValueError would prevent the app from
    booting at all."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        print(
            f"[source-network] {name}={raw!r} is not numeric; "
            f"falling back to default {default}",
            file=sys.stderr,
        )
        return default
    if value <= 0:
        print(
            f"[source-network] {name}={value} must be positive; "
            f"falling back to default {default}",
            file=sys.stderr,
        )
        return default
    return value


_TIMEOUT = _read_float_env("SN_PER_OP_TIMEOUT_SECONDS", 8.0)

# Wall-clock budget (seconds) for the entire `verify_claims_source_network`
# call. Each per-claim provider call has its own _TIMEOUT (5s); the budget
# below caps the cumulative call to bound the user-facing wait when slow
# providers, rate-limited providers, or pathologically claim-heavy
# documents would otherwise stack up to many tens of seconds.
#
# Default 25s sits inside the outer `_structural` 35s budget at
# app.py:1729, which leaves ~10s headroom for the substrate work
# (detection, framing portrait, Brave fallback) plus render. Override
# via SN_BUDGET_SECONDS env when production monitoring shows the p95 has
# drifted (operator reads `[source-network] budget exhausted` log
# frequency to calibrate).
#
# Architectural compromise named explicitly: this is a BEST-EFFORT
# budget. Worker threads inside the per-claim ThreadPoolExecutor cannot
# be truly cancelled in Python; when budget is exhausted the orchestrator
# stops waiting and returns partial results, but background HTTP calls
# already in flight continue until their per-call _TIMEOUT or natural
# return. They do not extend the user-visible request time but do
# consume CPU/network until they finish. The proper fix is to migrate
# the SN call graph to asyncio with task cancellation, which is named
# in NEXT_STEPS.md as 1.0.0+ territory; until then the budget primitive
# below trades thread-cleanup precision for a bounded user wait, which
# is the trade the user-facing UX requires today.
#
# This module exists at TWO paths in the working tree right now:
# root-level source_network.py (this file; the active import target
# for the web app) and framecheck_mcp/source_network.py (operator's
# in-flight src-layout migration target). Both files MUST carry an
# equivalent SN_BUDGET_SECONDS + budget-tracking implementation so
# that whichever path resolves the import gets the budget. When the
# src-layout migration commits and removes this root-level file,
# only framecheck_mcp/source_network.py remains; the budget primitive
# travels with the code unchanged.
SN_BUDGET_SECONDS = float(os.environ.get("SN_BUDGET_SECONDS", "25"))


# ================================================================
# External-provider health tracking
# ================================================================
#
# Source Network calls out to ~10 external APIs (Brave, CoinGecko,
# Wikipedia, FRED, Alpha Vantage, World Bank,
# Wolfram, SEC EDGAR, Github) on every analysis with extractable
# claims. Pre-2026-04-30 the only signal that a provider was
# degraded was stderr log lines from _fetch_json; an operator had
# to grep `fly logs` to learn that CoinGecko had been 429-ing all
# afternoon. Verifications silently degraded.
#
# This tracker maintains an in-memory rolling-window error count
# per provider so /health can surface a structured snapshot.
# Window is 1 hour; older errors fall off. Thread-safe via a
# single lock. Memory-bounded by the number of providers (small)
# and the window length (~3600 entries per provider in the worst
# case of one error per second). Process-local: matches the
# existing monitoring patterns and does not need cross-machine
# aggregation for the operator-grep use case.

class _ProviderHealth:
    """In-memory rolling-window counter of provider errors.

    record_error(provider, error_kind) appends a timestamp.
    snapshot() returns a dict keyed by provider with the counts
    inside the window. trim() removes entries older than the
    window; called lazily on each record/snapshot to keep the
    structure bounded without a background thread.
    """

    def __init__(self, window_seconds: int = 3600):
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        # provider -> list of (timestamp, error_kind)
        self._events: dict = {}

    def record_error(self, provider: str, error_kind: str) -> None:
        if not provider:
            provider = "unknown"
        now = time.time()
        with self._lock:
            self._events.setdefault(provider, []).append((now, error_kind))
            self._trim_locked(now)

    def _trim_locked(self, now: float) -> None:
        cutoff = now - self._window_seconds
        for provider, events in list(self._events.items()):
            kept = [e for e in events if e[0] >= cutoff]
            if kept:
                self._events[provider] = kept
            else:
                del self._events[provider]

    def snapshot(self) -> dict:
        """Return per-provider error stats for the current window.

        Shape:
          {
            "window_seconds": int,
            "providers": {
              "<provider>": {
                "total": int,
                "by_kind": {
                  "rate_limited": int,    # 429 / quota errors
                  "auth": int,            # 401 / 403
                  "server_error": int,    # 5xx
                  "deadline": int,        # caller-side total deadline fired
                  "other": int,           # everything else (DNS, parse, etc.)
                },
                "rate_limited": int,      # backward-compat alias for
                                          # by_kind.rate_limited; pre-2026-05-03
                                          # /health consumers branched on this
                                          # field directly
                "last_error_age_s": int,
              },
              ...
            }
          }

        Empty providers dict means no errors in the window. The
        by_kind breakdown is the actionable surface: a high "deadline"
        count for one provider says "tighten that provider's per-op
        timeout or increase _FETCH_JSON_DEADLINE_SECONDS"; a high
        "rate_limited" count says "rotate keys / switch providers";
        a high "server_error" count says "the provider is down."
        Pre-2026-05-03 only rate_limited was surfaced, conflating
        deadline-fired with HTTP server errors with DNS failures
        under the catch-all "total" minus "rate_limited" inference.
        """
        now = time.time()
        with self._lock:
            self._trim_locked(now)
            providers_out = {}
            for provider, events in self._events.items():
                if not events:
                    continue
                total = len(events)
                # Pre-seed the documented kinds at zero so the
                # returned shape matches the docstring contract (5
                # fixed keys). Without this the dict is sparse and a
                # consumer that branches on by_kind["auth"] directly
                # (per the docstring) would KeyError when the provider
                # never had an auth error. Unknown kinds (future
                # categorization additions) still count under their
                # own key alongside the documented five.
                by_kind: dict = {
                    "rate_limited": 0,
                    "auth": 0,
                    "server_error": 0,
                    "deadline": 0,
                    "other": 0,
                }
                for _, kind in events:
                    by_kind[kind] = by_kind.get(kind, 0) + 1
                last_ts = max(ts for ts, _ in events)
                providers_out[provider] = {
                    "total": total,
                    "by_kind": by_kind,
                    # Backward-compat: pre-2026-05-03 the /health
                    # consumers (operator dashboards, fly logs greps)
                    # branched on `rate_limited` directly. Keep the
                    # alias so a redeploy of just the source-network
                    # module does not break those callers; they can
                    # migrate to by_kind on their own cadence.
                    "rate_limited": by_kind.get("rate_limited", 0),
                    "last_error_age_s": int(now - last_ts),
                }
            return {
                "window_seconds": self._window_seconds,
                "providers": providers_out,
            }

    def reset(self) -> None:
        """Clear all tracked events. Used by tests."""
        with self._lock:
            self._events.clear()


provider_health = _ProviderHealth()


def _provider_from_url(url: str) -> str:
    """Map a URL to a provider label. Best-effort: hostname-based
    string matching. Unknown hosts return the bare hostname."""
    try:
        host = urllib.parse.urlparse(url).hostname or "unknown"
    except Exception:
        return "unknown"
    host = host.lower()
    if "brave" in host:
        return "brave"
    if "coingecko" in host:
        return "coingecko"
    if "wikidata" in host:
        return "wikidata"
    if "wikipedia" in host:
        return "wikipedia"
    if "stlouisfed" in host or "fred" in host:
        return "fred"
    if "alphavantage" in host:
        return "alpha_vantage"
    if "worldbank" in host:
        return "world_bank"
    if "restcountries" in host:
        return "rest_countries"
    if "wolframalpha" in host:
        return "wolfram"
    if "sec.gov" in host:
        return "sec_edgar"
    if "github" in host:
        return "github"
    return host


# Hard upper bound on the wall-clock time _fetch_json can spend on a
# single HTTP request, regardless of the per-socket-operation _TIMEOUT
# parameter. urllib's `timeout` is per-operation (DNS, connect, TLS
# handshake, send, each read chunk separately); a server that dribbles
# bytes within the per-op window keeps urlopen alive indefinitely.
# Production observed 2026-05-02 19:20:53 (cold-start fabrication-
# profiler machine) showed a single Wikipedia _fetch_json blocking
# ~30s before urllib's per-op timeout finally fired, by which point
# SN's outer 35s wrapper had already returned to the user. The deadline
# below enforces a hard caller-side cap by running urlopen in a sub-
# thread and abandoning it if the deadline passes; the abandoned
# thread continues until urllib eventually times out at its per-op
# budget, but the caller is unblocked and can either move on to the
# next provider or exit voluntarily on the next in-worker budget poll.
#
# Default raised from 8s to 12s on 2026-05-06 after production logs
# (other-agent investigation report A2) showed Wikipedia and
# Alphavantage caller-side deadline trips at 8s, contributing to
# "0 verified claims" on prod. The 25s outer SN_BUDGET_SECONDS still
# bounds total per-comparison cost; raising the per-fetch deadline
# trades a slower-but-completing fetch for the prior fast-but-
# discarded one. Env-overridable for further operator tuning.
_FETCH_JSON_DEADLINE_SECONDS = float(
    os.environ.get("SN_FETCH_JSON_DEADLINE_SECONDS", "12")
)


def _urlopen_with_deadline(req, per_op_timeout, total_deadline=None):
    """urlopen with HARD caller-side total deadline + the existing
    per-socket-operation timeout.

    Returns the response BYTES (caller decodes / json.loads). Raises:
      - concurrent.futures.TimeoutError on caller-side deadline
        exhaustion (existing call-site try/except around urlopen
        catches generic Exception, so this propagates cleanly)
      - Whatever urlopen raises on per-op timeout / network error /
        HTTP error (preserved for existing call-site error handling)

    Closes the gap that _fetch_json's deadline addressed but only for
    the JSON-API path. The four direct urlopen sites (Wolfram Alpha,
    SEC EDGAR ticker file, SEC EDGAR XBRL, Brave Search) had urllib's
    per-op-only timeout, so a server that dribbles bytes within the
    per-op window could block any of them indefinitely. The cold-
    start architectural weakness is provider-agnostic; this helper
    bounds the wall-clock at every direct urlopen call site uniformly.

    Auto-records caller-side deadline exhaustion against
    provider_health (kind="deadline") via _provider_from_url, so
    /health surfaces per-provider deadline-fired counts the same way
    it surfaces 429 / auth / server-error counts from _fetch_json.
    """
    deadline = (
        total_deadline if total_deadline is not None
        else _FETCH_JSON_DEADLINE_SECONDS
    )

    def _do():
        # urlopen returns a response context manager; eagerly read the
        # body inside the worker so the deadline bounds both the
        # connect/handshake AND the read phase (returning the open
        # response to the caller would let body-reads happen outside
        # the deadline).
        with urllib.request.urlopen(req, timeout=per_op_timeout) as resp:
            return resp.read()

    # Per-call ThreadPoolExecutor (not shared) for the same reason
    # _fetch_json uses one: a hung urlopen does not leak slots against
    # a long-lived executor; pool.shutdown(wait=False) lets the
    # abandoned thread finish on urlopen's per-op timeout while the
    # caller has already returned.
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sn-urlopen")
    try:
        future = pool.submit(_do)
        try:
            return future.result(timeout=deadline)
        except _FuturesTimeoutError:
            # Diagnostics are best-effort; wrap them so a failure
            # inside _provider_from_url, a missing req.full_url
            # attribute (e.g. caller passed a string URL instead of
            # a Request), or a provider_health lock-contention raise
            # cannot suppress the original deadline exception. The
            # caller's try/except still catches generic Exception
            # either way, but this guard preserves the exception TYPE
            # so operator triage from fly logs sees
            # "_FuturesTimeoutError" not the suppressed diagnostic
            # exception class. getattr(req, "full_url", str(req))
            # also handles the string-URL case defensively.
            try:
                import sys
                full_url = getattr(req, "full_url", str(req))
                provider = _provider_from_url(full_url)
                provider_health.record_error(provider, "deadline")
                safe_url = full_url.split("?")[0] if "?" in full_url else full_url
                sys.stderr.write(
                    f"[source-network] urlopen({safe_url[:100]}...): "
                    f"caller-side deadline {deadline:.1f}s exceeded; "
                    f"thread continues in background\n"
                )
            except Exception:
                pass
            raise
    finally:
        pool.shutdown(wait=False)


def _fetch_json(url, total_deadline=None):
    """Fetch JSON from a URL with a HARD total-time deadline.

    Returns the parsed JSON dict on success, None on any error
    (including deadline exhaustion).

    The `total_deadline` parameter (default _FETCH_JSON_DEADLINE_SECONDS,
    env-overridable via SN_FETCH_JSON_DEADLINE_SECONDS) caps the caller-
    side wait. The underlying urlopen still uses the existing per-
    socket-operation `_TIMEOUT` for chunk-level timeouts; the total
    deadline is the additional outer bound that urllib alone cannot
    enforce.

    Logs network/parse errors to stderr so a systematic source
    outage (FRED 403, World Bank timeout, etc.) is visible in
    `fly logs`. Records errors against provider_health so /health
    can surface per-provider degradation. Rate-limit responses (429)
    are tagged as rate_limited specifically because 429 is the
    actionable operator signal. Caller-side deadline exhaustion is
    tagged separately as "deadline" so /health can distinguish "fast-
    fail caller-side bound" from "real provider error".
    """
    deadline = (
        total_deadline if total_deadline is not None
        else _FETCH_JSON_DEADLINE_SECONDS
    )

    def _do_fetch():
        # The original synchronous body. urllib's per-operation
        # _TIMEOUT still applies; the outer thread wrapper enforces
        # the additional total deadline.
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            resp = urllib.request.urlopen(req, timeout=_TIMEOUT)
            return ("ok", json.loads(resp.read()))
        except Exception as exc:
            return ("err", exc)

    # Per-call ThreadPoolExecutor (not shared) so a hung urlopen does
    # not leak slots against a long-lived shared executor;
    # pool.shutdown(wait=False) in the finally lets the abandoned
    # thread finish on its own urlopen-internal timeout while the
    # caller has already returned. Per-call pool overhead (~10ms in
    # CPython) is negligible compared to network latency.
    pool = ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="sn-fetch-json"
    )
    try:
        future = pool.submit(_do_fetch)
        try:
            kind, payload = future.result(timeout=deadline)
        except _FuturesTimeoutError:
            import sys
            provider = _provider_from_url(url)
            provider_health.record_error(provider, "deadline")
            safe_url = url.split("?")[0] if "?" in url else url
            sys.stderr.write(
                f"[source-network] _fetch_json({safe_url}...): "
                f"caller-side deadline {deadline:.1f}s exceeded; "
                f"urlopen continues in background\n"
            )
            return None

        if kind == "ok":
            return payload

        # kind == "err": replay the original error-handling block so
        # provider_health categorization stays consistent with the
        # pre-deadline behavior.
        exc = payload
        import sys
        provider = _provider_from_url(url)
        kind_label = "other"
        if isinstance(exc, urllib.error.HTTPError):
            try:
                if exc.code == 429:
                    kind_label = "rate_limited"
                elif exc.code in (403, 401):
                    kind_label = "auth"
                elif 500 <= exc.code < 600:
                    kind_label = "server_error"
            except Exception:
                pass
        provider_health.record_error(provider, kind_label)
        safe_url = url.split("?")[0] if "?" in url else url
        sys.stderr.write(
            f"[source-network] _fetch_json({safe_url}...): "
            f"{type(exc).__name__}: {exc}\n"
        )
        return None
    finally:
        # wait=False so an abandoned hung thread does not block the
        # caller's return. The thread will finish on urlopen's per-op
        # timeout and Python's GC will reclaim the pool when no
        # references remain.
        pool.shutdown(wait=False)


# ── Wikipedia ──

def _query_wikipedia(subject):
    """Search Wikipedia and return article text for the best match."""
    if not subject:
        return None, None, None

    # Search
    search_url = (
        "https://en.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={urllib.parse.quote(subject)}&format=json&srlimit=1"
    )
    data = _fetch_json(search_url)
    if not data or not data.get("query", {}).get("search"):
        return None, None, None

    result = data["query"]["search"][0]
    title = result["title"]
    pageid = result["pageid"]

    # Fetch article text
    text_url = (
        "https://en.wikipedia.org/w/api.php?action=query"
        f"&titles={urllib.parse.quote(title)}"
        "&prop=extracts&explaintext=true&format=json"
    )
    text_data = _fetch_json(text_url)
    if not text_data:
        return title, None, pageid

    pages = text_data.get("query", {}).get("pages", {})
    page = list(pages.values())[0] if pages else {}
    extract = page.get("extract", "")

    return title, extract, pageid


# What a passage must say for a number in it to be about the metric the
# claim names. "12 million ethnic Germans" is not a population figure
# for Germany, however exact the digits.
_METRIC_EVIDENCE = {
    "diameter": re.compile(r'\b(diameter|radius)\b', re.IGNORECASE),
    "population": re.compile(
        r'\b(population|populous|inhabitants|people\s+live)\b',
        re.IGNORECASE),
    "height": re.compile(
        r'\b(height|tall\w*|elevation|above\s+sea\s+level)\b',
        re.IGNORECASE),
    "area": re.compile(
        r'\b(area|square\s+(?:km|kilomet\w+|miles?|met\w+)|km2|km²|sq\s+km)\b',
        re.IGNORECASE),
    "weight": re.compile(
        r'\b(weigh\w*|mass|kg|kilograms?|tonnes?|tons?)\b', re.IGNORECASE),
    "length": re.compile(
        r'\b(length|long|span|runs?|km|kilomet\w+|miles?|met(?:re|er)s?)\b',
        re.IGNORECASE),
    "gdp": re.compile(
        r'\b(GDP|gross\s+domestic\s+product)\b', re.IGNORECASE),
    "lifespan": re.compile(
        r'\b(lifespan|life\s+span|life\s+expectancy|years?\s+old|longevity|'
        r'live\s+(?:up\s+to|for))\b', re.IGNORECASE),
}

_ONE_SEX_RE = re.compile(r'\b(?:males?|females?|men|women|boys|girls)\b', re.IGNORECASE)
_ONE_SEX_AFTER_RE = re.compile(
    r'[^.;()\d]{0,12}?\b(?:for|among|of)\s+(?:males?|females?|men|women|boys|girls)\b',
    re.IGNORECASE,
)

# A claimed rate of change, and a source figure that is a share of something.
_GROWTH_WORD_RE = re.compile(
    r'\b(grew|grow(?:s|ing|th)?|rose|rise[sn]?|fell|fall(?:s|en)?|'
    r'up\s+from|down\s+from|increas\w*|decreas\w*|declin\w*|expand\w*|'
    r'contract\w*|slow\w*|accelerat\w*)\b', re.IGNORECASE)
_SHARE_OF_RE = re.compile(r'\s*(?:%|percent|per\s+cent)?\s+of\s+(?:the\s+|its\s+|their\s+)?'
                          r'(?!growth\b|change\b)[a-z]', re.IGNORECASE)

# Astronomy and engineering prose lists several measurements per sentence:
# "(12 km in diameter), which orbit at 9,376 km". The word must sit in the
# number's own clause.
_CLAUSE_BOUND_METRICS = frozenset({"diameter"})
_VAGUE_HEIGHT_RE = re.compile(r'\b(altitude|high\w*)\b', re.IGNORECASE)

# Metrics too generic to say what a number measures. These claims have
# to share a content word with the passage instead.
_WEAK_METRICS = frozenset({"", "count", "growth", "price"})

_SCALE_AND_FILLER_WORDS = frozenset({
    "thousand", "million", "billion", "trillion", "roughly",
    "approximately", "nearly", "around", "some", "together",
})

_UNIT_FAMILIES = (
    # Areas first, so "square miles" is not read as miles.
    ("km2", r'km2|km\u00b2|sq\.?\s*km|square\s+kilomet(?:re|er)s?'),
    ("mi2", r'mi2|mi\u00b2|sq\.?\s*mi(?:les?)?|square\s+miles?'),
    ("m2", r'm2|m\u00b2|square\s+met(?:re|er)s?'),
    ("ft2", r'sq\.?\s*ft|square\s+(?:feet|foot)'),
    ("km", r'km|kilomet(?:re|er)s?'),
    ("cm", r'cm|centimet(?:re|er)s?'),
    ("m", r'm|met(?:re|er)s?'),
    ("ft", r'ft|feet|foot'),
    ("mi", r'mi|miles?'),
    ("kg", r'kg|kilograms?'),
    ("t", r'tonnes?|tons?'),
    ("lb", r'lbs?|pounds?'),
    ("fathom", r'fathoms?'),
    ("yd", r'yards?|yd'),
)
_UNIT_ALTERNATION = "|".join(pat for _, pat in _UNIT_FAMILIES)
_UNIT_TOKEN_RE = re.compile(r'\b(' + _UNIT_ALTERNATION + r')(?![a-z])', re.IGNORECASE)
# The unit directly after a number, reading through the far end of a
# range: "12,000 to 15,260 ft" is in feet.
_UNIT_AFTER_NUMBER_RE = re.compile(
    # "630-foot-tall" and "31,722 km2" carry their unit too.
    r'(?:\s*(?:to|-|\u2013)\s*[\d,.]+)?[\s-]*(' + _UNIT_ALTERNATION + r')(?![a-z])',
    re.IGNORECASE,
)
# "St. Louis" and "Acme Inc. reported" are one sentence.
_SENTENCE_BREAK_RE = re.compile(r'(?<=[.!?])(?<!\bSt\.)(?<!\bMt\.)(?<!\bFt\.)(?<!\bDr\.)(?<!\bMr\.)(?<!\bMs\.)(?<!\bMrs\.)(?<!\bJr\.)(?<!\bSr\.)(?<!\bCo\.)(?<!\bInc\.)(?<!\bLtd\.)(?<!\bCorp\.)(?<!\bNo\.)(?<!\bvs\.)(?<!\bGen\.)(?<!\bGov\.)(?<!\bSen\.)(?<!\bRep\.)(?<!\bProf\.)\s+(?=[A-Z(\[])|\n+')


def _unit_family(token):
    for family, pattern in _UNIT_FAMILIES:
        if re.fullmatch(pattern, token or "", re.IGNORECASE):
            return family
    return ""


# A number this share of something, or described by these words, counts
# part of a population rather than all of it.
_PART_OF_WHOLE_RE = re.compile(r'\d\s*%\s*(?:\(|or\s+)\s*[\d,.]*\s*$')
_SUBGROUP_RE = re.compile(
    r'\b(urban|rural|migrants?|immigrants?|foreign|muslims?|christians?|'
    r'working[- ]age|adults?|children|elderly|prisoners?|ethnic|citizens|'
    r'users?|customers?|subscribers?|employees?|speakers?|employed|self-employed|'
    r'unemployed|employment|workers?|jobs|labou?r\s+force|households?|visitors?|'
    r'tourists?|arrivals|students?|births|deaths|voters?)\b',
    re.IGNORECASE,
)
_METRIC_EVIDENCE_REACH = 60


def _is_subgroup_count(decomp):
    """"32,067 people were employed in Guernsey" counts some of its people,
    not all of them: no population figure can settle it."""
    return decomp.metric == "population" and bool(_SUBGROUP_RE.search(
        _figure_clause(decomp.sentence, decomp.raw_value) + " "
        + (decomp.sentence or "")[:200]))


def _sentence_bounds(text, start, end):
    """(left, right) of the sentence of `text` holding the span."""
    left = 0
    right = len(text)
    for m in _SENTENCE_BREAK_RE.finditer(text):
        if m.end() <= start:
            left = m.end()
        elif m.start() >= end:
            right = m.start()
            break
    return left, right


def _nearby(text, start, end):
    """Text close to the span, kept inside its sentence. A metric word
    elsewhere in a long sentence does not describe this number."""
    left, right = _sentence_bounds(text, start, end)
    return text[
        max(left, start - _METRIC_EVIDENCE_REACH):
        min(right, end + _METRIC_EVIDENCE_REACH)
    ]


def _own_clause(text, start, end):
    """The span between the punctuation either side of a number."""
    left, right = _sentence_bounds(text, start, end)
    before = max(text.rfind(c, left, start) for c in ",;()") + 1
    after = [i for i in (text.find(c, end, right) for c in ",;()") if i >= 0]
    return text[max(left, before):min(after) if after else right]


def _shares_content_word(claim_words, passage):
    """True when the passage uses a claim word, allowing for inflection
    (deliveries / delivered)."""
    passage_words = set(re.findall(r'\b[a-z]{3,}\b', passage.lower()))
    stems = {w[:5] for w in passage_words}
    return any(w[:5] in stems for w in claim_words)


_DIMENSION_WORDS = (
    (r'\b(?:deep|depth)\b', "depth"),
    (r'\b(?:across|wide|width|diameter|radius)\b', "breadth"),
    (r'\b(?:tall|height|elevation|altitude)\b', "height"),
    (r'\b(?:long|length)\b', "length"),
)
_EXCLUSIVE_QUALIFIERS = (
    re.compile(r'\b(radius|diameter)\b'),
    re.compile(r'\b(land|total|surface|water)\s+area\b'),
)
# A height to the tip needs a page that says tip; to the roof, roof.
_HEIGHT_POINTS = (("roof", r'\broof'), ("tip", r'\b(?:tip|spire|antenna|pinnacle)'),
                  ("architectural", r'\barchitectural'))
_MONTH_NAMES = (
    r'(?:January|February|March|April|May|June|July|August|September|October|'
    r'November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?'
)
_MONTH_AFTER_RE = re.compile(r'\s+' + _MONTH_NAMES + r'\b')
_MONTH_BEFORE_RE = re.compile(_MONTH_NAMES + r'\s+$')


# Each family is one kind of event, in its word forms.
_EVENT_FAMILIES = [re.compile(r'\b(?:' + f + r')\b', re.IGNORECASE) for f in (
    r'found(?:ed|ing|ation|er)', r'incorporat\w*', r'establish\w*',
    r'open(?:ed|ing|s)', r'complet(?:ed|ion)', r'built|construct\w*',
    r'discover\w*', r'born|birth', r'died|death', r'independen\w*',
    r'launch\w*', r'releas\w*', r'elect\w*', r'acqui\w*', r'merg\w*',
    r'renam\w*', r'settl\w*', r'charter\w*', r'dedicat\w*', r'inaugurat\w*',
    r'ratif\w*', r'sign(?:ed|ing)', r'declar\w*', r'abolish\w*', r'dissol\w*',
    r'annex\w*', r'host\w*', r'ascent|ascended|summit\w*',
)]


def _year_event_words(sentence, raw_value):
    """The kinds of event named in the clause just before a year, which the
    page has to name too: "incorporated as a city in 1884" needs the page's
    1884 to be an incorporation."""
    raw = str(raw_value or "").strip()
    at = sentence.find(raw) if raw else -1
    if at <= 0:
        return []
    clause = re.split(r'[,;:]|\band\b', sentence[max(0, at - 60):at])[-1]
    families = [f for f in _EVENT_FAMILIES if f.search(clause)]
    # "incorporated as a city" is not the year it became a town.
    kind = _PLACE_KIND_RE.search(clause)
    if families and kind:
        families.append(re.compile(r'\b' + kind.group(1) + r'\b', re.IGNORECASE))
        families = [_all_of(families)]
    return families


_PLACE_KIND_RE = re.compile(
    r'\bas\s+an?\s+(city|town|village|borough|county|state|province|republic|'
    r'kingdom|colony|territory|dominion)\b', re.IGNORECASE)


class _all_of:
    """Matches a passage only when every pattern does."""

    def __init__(self, patterns):
        self.patterns = patterns

    def search(self, text):
        return all(p.search(text) for p in self.patterns)


def _match_in_text(text, claim_value, claim_sentence, tolerance=0.05,
                   decomp=None):
    """Find the best number match in text with context scoring.

    When decomp (ClaimDecomposition) is provided, uses metric and
    time_period for stronger disambiguation beyond keyword overlap.

    Years (4-digit numbers 1800-2100) require exact match because
    1929 is NOT "close to" 1943. Fuzzy tolerance on years produces
    false positives that inflate verification counts.

    Returns (matched_value, context, confidence) or (None, None, 0).
    """
    if not text or claim_value == 0:
        return None, None, 0

    # Years require exact match. 2023 and 2024 are 0.05% apart by ratio
    # but are completely different years. Use absolute comparison.
    is_year = (1800 <= claim_value <= 2100 and claim_value == int(claim_value))
    if is_year:
        tolerance = 0.0002  # 2024 * 0.0002 = 0.4, so rejects +/- 1 year

    # Small integers (1-50) are too common in text to verify reliably.
    # "1%" matches "1" everywhere. "4% today" matches ISBN "4" in citations.
    is_small = (0 < claim_value <= 50 and claim_value == int(claim_value))
    if is_small:
        tolerance = 0.001  # exact match only for small integers

    # Percentages (values likely from a % claim): tighten tolerance.
    # "80%" matching "78" (2.5% diff) is too loose. Require near-exact.
    # Detect via decomp.unit or the claim sentence containing "percent"/"%".
    is_pct = False
    if decomp and decomp.unit == "percent":
        is_pct = True
    elif "percent" in claim_sentence.lower() or "%" in claim_sentence:
        is_pct = True
    if is_pct and not is_small:
        tolerance = 0.015  # +/- 1.5%: 80% matches 79-81, not 76-84

    # Measurements are published precisely, so 5% is another object entirely:
    # 457 m matched a 447 m observation deck.
    if decomp and (
        decomp.unit in ("distance", "mass")
        or decomp.metric in _WEAK_METRICS
        or decomp.metric == "lifespan"
    ):
        # And as precise as written: "7,611 m" is not a "7,650 metres" nearby,
        # unless the text hedges it ("about 384,400 km").
        hedged = _hedged(claim_sentence, decomp.raw_value)
        tolerance = min(tolerance, 0.02 if hedged else max(
            0.003, 2 * _rounding_room(decomp.raw_value)))
    # A count written to the last unit is a census figure, not a rounding:
    # 2,731,571 is the 2016 census, not "close" to 2021's 2,794,356.
    if (decomp and decomp.unit == "count" and not is_year
            and _rounding_room(decomp.raw_value) < 1e-4
            and not _hedged(claim_sentence, decomp.raw_value)):
        tolerance = min(tolerance, 0.005)

    # Extract all numbers with context windows.
    # Handle scale suffixes (B/billion, M/million, T/trillion, K/thousand)
    # common in web snippets: "$60.922B", "3.8M units", "$1.2T"
    _SCALE_SUFFIXES = {
        "t": 1e12, "trillion": 1e12,
        "b": 1e9, "bn": 1e9, "billion": 1e9,
        "m": 1e6, "mn": 1e6, "million": 1e6,
        "k": 1e3, "thousand": 1e3,
    }
    _NUM_RE = re.compile(
        # A lone letter scales only when attached: "$60.9B" but not
        # "3,776.24 m", which is metres and read as 3.7 billion.
        r'[\$]?\s*([\d,]+(?:\.\d+)?)'
        r'(\s*(?:trillion|billion|million|thousand|bn|mn)|[TBMKtbmk])?'
        r'(?:\b|(?=[\s,.\)\]]))'
    )

    candidates = []
    for m in _NUM_RE.finditer(text):
        try:
            raw_str = m.group(1).replace(",", "")
            num_val = float(raw_str)
        except ValueError:
            continue
        if num_val == 0:
            continue
        # "1\u20446 of the Moon's" is a fraction, and 6 is not one of its numbers.
        if (re.search(r'\d\s?[\u2044/]$', text[max(0, m.start(1) - 2):m.start(1)])
                or re.match(r'\s?[\u2044/]\s?\d', text[m.end(1):m.end(1) + 3])):
            continue
        # "6 March 2015" and "doi:10.1061/41173(414)200" are not measurements.
        if (_MONTH_AFTER_RE.match(text[m.end(1):m.end(1) + 12])
                or _MONTH_BEFORE_RE.search(text[max(0, m.start(1) - 11):m.start(1)])
                or re.search(r'\d\($', text[max(0, m.start(1) - 2):m.start(1)])
                or re.search(r'doi:\S*$', text[max(0, m.start(1) - 40):m.start(1)], re.I)):
            continue
        # A source that says "6" has not said "6.1".
        if (claim_value != int(claim_value) and abs(claim_value) < 100
                and "." not in m.group(1) and not m.group(2)):
            continue

        # Apply scale suffix
        suffix = m.group(2)
        if suffix:
            scale = _SCALE_SUFFIXES.get(suffix.strip().lower(), 1)
            num_val *= scale

        # Get context window (80 chars each side, snapped to word boundaries)
        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 80)
        # Snap start to next word boundary (don't start mid-word)
        if start > 0:
            space = text.find(' ', start)
            if space != -1 and space < m.start():
                start = space + 1
        # Snap end to previous word boundary
        if end < len(text):
            space = text.rfind(' ', m.end(), end)
            if space != -1:
                end = space
        context = text[start:end].strip()
        candidates.append((num_val, raw_str, context, m.start(), m.end()))

    if not candidates:
        return None, None, 0

    # Build scoring keywords from claim sentence + decomposition
    claim_keywords = set(re.findall(r'\b[a-z]{3,}\b', claim_sentence.lower()))
    _stopwords = {
        "the", "and", "for", "are", "was", "were", "has", "have",
        "had", "been", "will", "with", "that", "this", "from",
        "its", "than", "more", "also", "into", "over", "such",
        "per", "not", "but", "year", "total", "about", "which",
    }
    claim_keywords -= _stopwords

    # High-value keywords from decomposition (metric + subject terms)
    metric_keywords = set()
    subject_words = set()
    claim_unit = ""
    if decomp:
        # The unit after the claim's own figure, not the sentence's first one,
        # and whatever the figure was classed as: "about 780 ft" is in feet.
        raw = str(decomp.raw_value).strip()
        at = claim_sentence.find(raw) if raw else -1
        own = _UNIT_AFTER_NUMBER_RE.match(claim_sentence, at + len(raw)) if at >= 0 else None
        if not own and decomp.unit in ("distance", "mass"):
            own = _UNIT_TOKEN_RE.search(claim_sentence)
        claim_unit = _unit_family(own.group(1)) if own else ""
    if decomp:
        if decomp.metric:
            # Metric keywords score higher (revenue vs profit disambiguation)
            metric_keywords = set(
                re.findall(r'\b[a-z]{3,}\b', decomp.metric.lower())
            )
        if decomp.subject:
            subject_words = set(
                re.findall(r'\b[a-z]{3,}\b', decomp.subject.lower())
            ) - _stopwords
            claim_keywords |= subject_words

    best = None
    best_score = -1

    # What the claim says besides who it is about and how big it is.
    content_words = (
        claim_keywords - subject_words - _SCALE_AND_FILLER_WORDS
    )

    for num_val, raw_str, context, num_start, num_end in candidates:
        if claim_value == 0:
            continue
        ratio = num_val / claim_value if claim_value != 0 else 0
        if ratio == 0:
            continue
        diff = abs(ratio - 1.0)
        if diff > tolerance:
            continue
        value_score = 1.0 - (diff / tolerance)

        # Binding gates: equal digits are not the same claim. Only run
        # when a decomposition says what the claim is about.
        if decomp:
            if claim_unit:
                unit_after = _UNIT_AFTER_NUMBER_RE.match(text, num_end)
                candidate_unit = (
                    _unit_family(unit_after.group(1)) if unit_after else ""
                )
                if candidate_unit and candidate_unit != claim_unit:
                    continue
            elif (decomp.metric and decomp.metric not in _PHYSICAL_METRICS
                    and decomp.unit not in ("distance", "mass")):
                # "1,500 meters (4,900 ft)" is not $4,717 of GDP per head.
                unit_after = _UNIT_AFTER_NUMBER_RE.match(text, num_end)
                family = _unit_family(unit_after.group(1)) if unit_after else ""
                # "$4.7m" is millions; only a spaced "m" is metres.
                if family and not (family == "m" and not unit_after.group(0)[:1].isspace()):
                    continue
            # "76.7 years for males" is not everyone's life expectancy.
            if (_ONE_SEX_AFTER_RE.match(text, num_end)
                    and not _ONE_SEX_RE.search(claim_sentence)):
                continue
            left, right = _sentence_bounds(text, num_start, num_end)
            passage = text[left:right]
            # A radius is half a diameter, and land area is not total area.
            nearby = text[max(left, num_start - 60):min(right, num_end + 60)].lower()
            # Depth, width, height and length are different measurements:
            # "780 ft across" is not "790 ft deep".
            claim_dims = {d for w, d in _DIMENSION_WORDS if re.search(w, claim_sentence, re.IGNORECASE)}
            page_dims = {
                d for w, d in _DIMENSION_WORDS
                if re.search(w, text[max(left, num_start - 15):min(right, num_end + 25)], re.IGNORECASE)
            }
            if len(claim_dims) == 1 and page_dims and not (claim_dims & page_dims):
                continue
            # A claim about land area needs a page that says land.
            if (re.search(r'\bland\s+area\b', claim_sentence, re.IGNORECASE)
                    and not re.search(r'\bland\b', nearby)):
                continue
            claim_points = [w for name, w in _HEIGHT_POINTS
                            if re.search(w, claim_sentence, re.IGNORECASE)]
            if (len(claim_points) == 1 and decomp.metric in ("height", "")
                    and decomp.unit == "distance"
                    and not re.search(claim_points[0], nearby, re.IGNORECASE)):
                continue
            if any(
                (said := pattern.findall(claim_sentence.lower()))
                and (near := pattern.findall(nearby))
                and said[0] not in near
                for pattern in _EXCLUSIVE_QUALIFIERS
            ):
                continue
            # "900 steps" is a count; "(906 ft)" is a measurement.
            claim_raw = str(decomp.raw_value).strip()
            claim_at = claim_sentence.find(claim_raw) if claim_raw else -1
            claim_word = re.match(
                r'\s*([a-z]+)', claim_sentence[claim_at + len(claim_raw):]
            ) if claim_at >= 0 else None
            page_unit = _UNIT_AFTER_NUMBER_RE.match(text, num_end)
            if (claim_word and page_unit and not claim_unit
                    and not _unit_family(claim_word.group(1))
                    and claim_word.group(1) not in _SCALE_AND_FILLER_WORDS):
                continue
            # A dollar figure for a named year must be from that year. Filings
            # answer these claims; this only stops reference prose about some
            # other period confirming one when a filing could not be read.
            if decomp.unit == "currency" and decomp.time_period:
                claim_year = re.search(r'20[0-3]\d', decomp.time_period)
                if claim_year and claim_year.group() not in passage:
                    continue
            # A count for the year the claim names: "2,731,571 at the 2021
            # census" is not "its 2016 population of 2,731,571".
            if decomp.unit == "count" and not is_year and not decomp.year_inherited:
                claim_year = re.search(r'(?:19|20)\d\d', decomp.time_period or "")
                page_year = re.search(r'\b((?:19|20)\d\d)\b[^.\d]{0,30}$',
                                      text[max(left, num_start - 40):num_start])
                if claim_year and page_year and page_year.group(1) != claim_year.group():
                    continue
            # A year is confirmed by the event it dates: "incorporated as a
            # city in 1884" is not "In 1884, the HBC established a shop".
            if is_year:
                event = _year_event_words(claim_sentence, decomp.raw_value)
                if event and not any(f.search(passage) for f in event):
                    continue
            # A rate of change is not a share: "GDP grew ... up from 4.8%" is
            # not "allocated 4.8% of the national budget".
            _at = claim_sentence.find(str(decomp.raw_value))
            if (is_pct and _at >= 0 and _GROWTH_WORD_RE.search(
                    claim_sentence[max(0, _at - 40):_at])
                    and _SHARE_OF_RE.match(text, num_end)
                    and not _SHARE_OF_RE.search(claim_sentence)):
                continue
            evidence = _METRIC_EVIDENCE.get(decomp.metric)
            if evidence:
                nearby = _nearby(text, num_start, num_end)
                if decomp.metric in _CLAUSE_BOUND_METRICS:
                    nearby = _own_clause(text, num_start, num_end)
                # "up to 12,000 m altitude" may describe a balloon. Vaguer
                # height words count only when they name the subject too.
                vague_height = (
                    decomp.metric == "height"
                    and _VAGUE_HEIGHT_RE.search(nearby)
                    and _shares_content_word(subject_words, nearby)
                )
                if not evidence.search(nearby) and not vague_height:
                    continue
                if decomp.metric == "population" and (
                    _SUBGROUP_RE.search(nearby)
                    or _PART_OF_WHOLE_RE.search(text[:num_start])
                ):
                    continue
            if (decomp.metric in _WEAK_METRICS and not is_pct and content_words
                    and not _shares_content_word(content_words, passage)):
                continue

        # Context scoring with three dimensions
        ctx_lower = context.lower()
        ctx_words = set(re.findall(r'\b[a-z]{3,}\b', ctx_lower)) - _stopwords

        # Dimension 1: General keyword overlap
        if claim_keywords:
            keyword_overlap = len(claim_keywords & ctx_words) / len(claim_keywords)
        else:
            keyword_overlap = 0.5

        # Dimension 2: Metric alignment (higher weight)
        metric_score = 0.5  # neutral
        if metric_keywords:
            if metric_keywords & ctx_words:
                metric_score = 1.0  # metric terms found in context
            else:
                metric_score = 0.1  # metric terms NOT in context (penalty)

        # Dimension 3: Temporal alignment
        temporal_score = 0.5  # neutral
        if decomp and decomp.time_period:
            year_match = re.search(r'20[1-3]\d', decomp.time_period)
            if year_match:
                claim_year = year_match.group()
                if claim_year in context:
                    temporal_score = 1.0  # year matches
                elif re.search(r'20[1-3]\d', context):
                    temporal_score = 0.2  # different year in context

        # Combined score: value match + context + metric + temporal
        score = (value_score * 0.4 +
                 keyword_overlap * 0.25 +
                 metric_score * 0.2 +
                 temporal_score * 0.15)

        # For small numbers and percentages, require meaningful context.
        # Value-only matches on common numbers produce false positives.
        # "4" in "4 December" matching "4 percent" is wrong.
        # Exception: if both claim and source use %, that's a context signal.
        has_pct_in_source = bool(re.search(
            re.escape(raw_str) + r'\s*%', context
        )) if is_pct else False

        if (is_small or is_pct) and keyword_overlap < 0.15 and not has_pct_in_source:
            continue  # Skip: value matches but context doesn't

        # For percentages, require STRONGER context match.
        # "80%" is extremely common in text. "80% of AI accelerator market"
        # should not match "80% of stock market gains." Require multiple
        # keyword matches, not just one generic word like "market."
        # The has_pct_in_source exemption only applies to small/exact matches
        # where the % symbol disambiguates, NOT to common percentages with
        # generic keywords.
        if is_pct and keyword_overlap < 0.30:
            continue  # Percentage with weak context: skip

        # For large financial claims with an explicit metric (revenue,
        # profit, etc.), reject matches where the context has NO metric
        # keywords. "$40 billion" (Arm acquisition) should not match
        # "$39.3 billion" (revenue claim) just because the value is close
        # and the subject (NVIDIA) appears in both contexts.
        if (decomp and decomp.metric and metric_score <= 0.1
                and decomp.unit == "currency" and claim_value > 1e9):
            continue

        if score > best_score:
            best_score = score
            best = (num_val, context, score)

    if best:
        num_val, context, score = best
        confidence = min(0.95, score * 0.9)
        return num_val, context, confidence

    return None, None, 0


def verify_wikipedia(decomp, _cached_article=None):
    """Verify a claim against Wikipedia."""
    if _cached_article:
        title, article_text, pageid = _cached_article
    else:
        title, article_text, pageid = _query_wikipedia(decomp.subject)
    if not article_text:
        return SourceResult(source_name="Wikipedia", match_type="no_data")

    # Try matching at the raw scale first (e.g., 27.4 against 27.36 in text),
    # then at normalized scale (e.g., 27.4e12 against large numbers in text).
    # Wikipedia text usually has human-readable numbers matching the raw claim.
    raw_float = 0.0
    try:
        raw_cleaned = decomp.raw_value.strip().lstrip("$~").rstrip("%")
        raw_cleaned = re.sub(r'[TBMKk]$', '', raw_cleaned).replace(",", "")
        raw_float = float(raw_cleaned)
    except (ValueError, AttributeError):
        pass

    matched_val, context, confidence = None, None, 0
    compare_against = decomp.value  # which scale the match used
    if raw_float and raw_float != decomp.value:
        # Skip raw-scale match when the claim has a large scale factor.
        # "$39.3 billion" has raw_float=39.3 and value=39.3e9 (scale 1e9).
        # Matching 39.3 against article text matches unrelated small numbers
        # (employee counts, dates, page numbers). Only the normalized-scale
        # match (39.3e9) should run for billion/million-scale claims.
        scale_factor = decomp.value / raw_float if raw_float else 1
        if abs(scale_factor) < 1e3:
            # Small scale factor: raw and normalized are similar, try raw first
            matched_val, context, confidence = _match_in_text(
                article_text, raw_float, decomp.sentence, decomp=decomp
            )
            if matched_val:
                compare_against = raw_float
    if not matched_val:
        # Try normalized scale
        matched_val, context, confidence = _match_in_text(
            article_text, decomp.value, decomp.sentence, decomp=decomp
        )
        compare_against = decomp.value

    url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"

    if matched_val is None:
        return SourceResult(
            source_name="Wikipedia",
            source_url=url,
            match_type="no_data",
            source_text=f"Article found: {title}. No matching number.",
        )

    diff = abs(matched_val - compare_against) / max(abs(compare_against), 1e-10)
    if diff < 0.01:
        match_type = "exact"
    elif diff < 0.05:
        match_type = "close"
    else:
        match_type = "contradicted"

    return SourceResult(
        source_name="Wikipedia",
        source_url=url,
        source_value=matched_val,
        source_text=context[:200] if context else "",
        match_type=match_type,
        difference_pct=round(diff * 100, 1),
        confidence=confidence,
    )


# ── Country lookup ──

_COUNTRY_NAMES_RE = re.compile(
    # "New Guinea", "New Mexico" and "Northern Ireland" are not the country.
    r'\b(?<!\bNew\s)(?<!\bNorthern\s)(Afghanistan|Albania|Algeria|Andorra|Angola|Antigua and Barbuda|'
    r'Argentina|Armenia|Australia|Austria|Azerbaijan|'
    r'Bahamas|Bahrain|Bangladesh|Barbados|Belarus|Belgium|Belize|Benin|'
    r'Bhutan|Bolivia|Bosnia and Herzegovina|Bosnia-Herzegovina|Bosnia|Botswana|Brazil|Brunei|Bulgaria|'
    r'Burkina Faso|Burundi|'
    # The two Congos: the long names first, so neither collapses to bare "Congo" (v22).
    r'Democratic Republic of (?:the )?Congo|DR Congo|D\.R\. Congo|DRC|Congo-Kinshasa|'
    r'Republic of (?:the )?Congo|Congo-Brazzaville|'
    r'Cambodia|Cameroon|Canada|Cape Verde|Central African Republic|'
    r'Chad|Chile|China|Colombia|Comoros|Congo|Costa Rica|Croatia|Cuba|'
    r'Cyprus|Czechia|Czech Republic|Czech|'
    r'Denmark|Djibouti|Dominica|Dominican Republic|Dominican|'
    r'Ecuador|Egypt|El Salvador|Equatorial Guinea|Eritrea|Estonia|'
    r'Eswatini|Swaziland|Ethiopia|'
    r'Fiji|Finland|France|'
    r'Gabon|Gambia|Georgia|Germany|Ghana|Greece|Greenland|Grenada|'
    r'Guatemala|Guinea-Bissau|Guinea|Guyana|'
    r'Haiti|Honduras|Hong Kong|Hungary|'
    r'Iceland|India|Indonesia|Iran|Iraq|Ireland|Israel|'
    # Cote d'Ivoire: accepted in plain ASCII form matching the canonical
    # key stored in _COUNTRY_CANONICAL; the accented Côte d'Ivoire is
    # out of scope for this pass (would need Unicode normalisation).
    r"Italy|Ivory Coast|Cote d'Ivoire|"
    r'Jamaica|Japan|Jordan|'
    # Korea variants: North and South must come BEFORE bare "Korea" in
    # the alternation so search-based callers prefer the more specific
    # form when both appear. fullmatch callers (entity classifier) get
    # the right answer either way.
    r'Kazakhstan|Kenya|Kiribati|North Korea|South Korea|Korea|Kosovo|Kuwait|Kyrgyzstan|'
    r'Laos|Latvia|Lebanon|Lesotho|Liberia|Libya|Liechtenstein|'
    r'Lithuania|Luxembourg|'
    r'Macau|Madagascar|Malawi|Malaysia|Maldives|Mali|Malta|'
    r'Marshall Islands|Mauritania|Mauritius|Mexico|Micronesia|Moldova|'
    r'Monaco|Mongolia|Montenegro|Morocco|Mozambique|Myanmar|'
    r'Namibia|Nauru|Nepal|Netherlands|New Zealand|Nicaragua|Niger|'
    r'Nigeria|North Macedonia|Norway|'
    r'Oman|'
    r'Pakistan|Palau|Palestine|Panama|Papua New Guinea|Paraguay|Peru|'
    r'Philippines|Poland|Portugal|Puerto Rico|'
    r'Qatar|'
    r'Romania|Russia|Rwanda|'
    r'Saint Kitts and Nevis|Saint Lucia|Saint Vincent|Samoa|'
    r'San Marino|Saudi Arabia|Senegal|Serbia|Seychelles|Sierra Leone|'
    r'Singapore|Slovakia|Slovenia|Solomon Islands|Somalia|South Africa|'
    r'South Sudan|Spain|Sri Lanka|Sudan|Suriname|Sweden|Switzerland|'
    r'Syria|'
    r'Taiwan|Tajikistan|Tanzania|Thailand|Timor-Leste|East Timor|Togo|'
    r'Tonga|Trinidad and Tobago|Tunisia|Turkey|Turkmenistan|Tuvalu|'
    r'Uganda|Ukraine|United Arab Emirates|UAE|the Emirates|United Kingdom|United States|'
    r'Uruguay|Uzbekistan|'
    r'Vanuatu|Vatican City|Venezuela|Vietnam|'
    r'Western Sahara|Yemen|Zambia|Zimbabwe|'
    # The World Bank's own spellings (its API and its country pages use
    # them). v20 (2026-11-26): "Turkiye" was not a country, so an answer
    # about it that quoted US dollars read as American and FRED refuted
    # its figures with US series.
    r'T[uü]rkiye|Viet Nam|Slovak Republic|Kyrgyz Republic|Lao PDR|Cabo Verde|'
    r'Syrian Arab Republic|S[aã]o Tom[eé] and Pr[ií]ncipe|West Bank and Gaza|'
    r'St\. Kitts and Nevis|St\. Lucia|St\. Vincent|Cura[cç]ao|Aruba|Bermuda|'
    r'Cayman Islands|Gibraltar|Guam|Isle of Man|Faroe Islands|Faroes|Channel Islands|'
    r'New Caledonia|Turks and Caicos Islands|Northern Mariana Islands|C[oô]te d\'Ivoire|'
    # v22: Macao's figures went to China and Sint Maarten's to the Netherlands.
    # "Saint-Martin" is the French spelling (v21 under the trial: unread, its
    # life expectancy went to France via "ties to France").
    r'Macao|Sint Maarten|St\. Martin|Saint[- ]Martin|American Samoa|French Polynesia|'
    r'Virgin Islands|Kosovo|Montserrat|Greenland'
    # Demonyms that map unambiguously to a country
    r'|American|British|Chinese|French|German|Indian|Japanese|'
    r'Brazilian|Russian|Mexican|Canadian|Australian|Italian|Spanish|'
    r'Korean|Turkish|Indonesian|Saudi|Egyptian|Nigerian|South African|'
    r'Pakistani|Bangladeshi|Thai|Vietnamese|Colombian|Argentine|'
    r'Chilean|Peruvian|Venezuelan|Malaysian|Philippine|Singaporean|'
    r'Swedish|Norwegian|Danish|Finnish|Dutch|Swiss|Belgian|Austrian|'
    r'Polish|Czech|Hungarian|Romanian|Greek|Portuguese|Irish|'
    # v29: "Croatian inflation" went to North Macedonia, named just before.
    r'Cameroonian|Azerbaijani|Montenegrin|Costa Rican|Ecuadorian|Paraguayan|Lithuanian|Zimbabwean|Senegalese|Mozambican|Sri Lankan|Belarusian|Guatemalan|Salvadoran|Nicaraguan|Panamanian|Ukrainian|Bulgarian|Slovenian|Ethiopian|Jordanian|Mongolian|Uruguayan|Icelandic|Tanzanian|Cambodian|Croatian|Ghanaian|Moroccan|Algerian|Tunisian|Lebanese|Jamaican|Bolivian|Estonian|Namibian|Malawian|Armenian|Moldovan|Albanian|Honduran|Serbian|Israeli|Iranian|Emirati|Kuwaiti|Latvian|Cypriot|Maltese|Rwandan|Ugandan|Zambian|Angolan|Bosnian|Haitian|Kenyan|Qatari|Nepali|Kazakh|Fijian|Samoan|Iraqi|Omani|Cuban|Uzbek)\b',
    re.IGNORECASE
)

# Abbreviations checked separately (case-sensitive to avoid matching
# "us" as a pronoun, "eu" in "neurological", etc.)
_COUNTRY_ABBREV_RE = re.compile(r'\b(U\.?S\.?A?\.?|U\.?K\.?|EU)\b')


# Map abbreviations and demonyms to the canonical name that
# World Bank API expects.
_COUNTRY_CANONICAL = {
    # "for the Faroes" (v28 under the trial: the figure went to Italy).
    "Faroes": "Faroe Islands",
    "Bosnia": "Bosnia and Herzegovina", "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Democratic Republic of the Congo": "Democratic Republic of the Congo",
    "Democratic Republic of Congo": "Democratic Republic of the Congo",
    "DR Congo": "Democratic Republic of the Congo", "D.R. Congo": "Democratic Republic of the Congo",
    "DRC": "Democratic Republic of the Congo", "Congo-Kinshasa": "Democratic Republic of the Congo",
    "Republic of the Congo": "Republic of the Congo", "Republic of Congo": "Republic of the Congo",
    "Congo-Brazzaville": "Republic of the Congo",
    "UAE": "United Arab Emirates", "Uae": "United Arab Emirates",
    "the Emirates": "United Arab Emirates", "The Emirates": "United Arab Emirates",
    "US": "United States", "U.S.": "United States", "U.S.A.": "United States",
    "USA": "United States", "U.S.A": "United States",
    "UK": "United Kingdom", "U.K.": "United Kingdom",
    "EU": "European Union",
    "American": "United States", "British": "United Kingdom",
    "Chinese": "China", "French": "France", "German": "Germany",
    "Indian": "India", "Japanese": "Japan", "Brazilian": "Brazil",
    "Russian": "Russia", "Mexican": "Mexico", "Canadian": "Canada",
    "Australian": "Australia", "Italian": "Italy", "Spanish": "Spain",
    "Korean": "Korea", "Turkish": "Turkey", "Indonesian": "Indonesia",
    "Saudi": "Saudi Arabia", "Egyptian": "Egypt", "Nigerian": "Nigeria",
    "South African": "South Africa", "Pakistani": "Pakistan",
    "Bangladeshi": "Bangladesh", "Thai": "Thailand",
    "Vietnamese": "Vietnam", "Colombian": "Colombia",
    "Argentine": "Argentina", "Chilean": "Chile", "Peruvian": "Peru",
    "Venezuelan": "Venezuela", "Malaysian": "Malaysia",
    "Philippine": "Philippines", "Singaporean": "Singapore",
    "Swedish": "Sweden", "Norwegian": "Norway", "Danish": "Denmark",
    "Croatian": "Croatia", "Serbian": "Serbia", "Ukrainian": "Ukraine", "Bulgarian": "Bulgaria", "Slovenian": "Slovenia", "Kenyan": "Kenya", "Ghanaian": "Ghana", "Ethiopian": "Ethiopia", "Moroccan": "Morocco", "Algerian": "Algeria", "Tunisian": "Tunisia", "Israeli": "Israel", "Iranian": "Iran", "Iraqi": "Iraq", "Jordanian": "Jordan", "Lebanese": "Lebanon", "Qatari": "Qatar", "Emirati": "United Arab Emirates", "Kuwaiti": "Kuwait", "Omani": "Oman", "Nepali": "Nepal", "Mongolian": "Mongolia", "Cuban": "Cuba", "Jamaican": "Jamaica", "Bolivian": "Bolivia", "Ecuadorian": "Ecuador", "Uruguayan": "Uruguay", "Paraguayan": "Paraguay", "Icelandic": "Iceland", "Estonian": "Estonia", "Latvian": "Latvia", "Lithuanian": "Lithuania", "Cypriot": "Cyprus", "Maltese": "Malta", "Rwandan": "Rwanda", "Ugandan": "Uganda", "Tanzanian": "Tanzania", "Zambian": "Zambia", "Zimbabwean": "Zimbabwe", "Senegalese": "Senegal", "Cameroonian": "Cameroon", "Angolan": "Angola", "Mozambican": "Mozambique", "Namibian": "Namibia", "Malawian": "Malawi", "Sri Lankan": "Sri Lanka", "Cambodian": "Cambodia", "Kazakh": "Kazakhstan", "Uzbek": "Uzbekistan", "Armenian": "Armenia", "Azerbaijani": "Azerbaijan", "Belarusian": "Belarus", "Moldovan": "Moldova", "Albanian": "Albania", "Bosnian": "Bosnia and Herzegovina", "Montenegrin": "Montenegro", "Haitian": "Haiti", "Guatemalan": "Guatemala", "Honduran": "Honduras", "Salvadoran": "El Salvador", "Nicaraguan": "Nicaragua", "Costa Rican": "Costa Rica", "Panamanian": "Panama", "Fijian": "Fiji", "Samoan": "Samoa",
    "Finnish": "Finland", "Dutch": "Netherlands", "Swiss": "Switzerland",
    "Belgian": "Belgium", "Austrian": "Austria", "Polish": "Poland",
    "Czech": "Czechia", "Hungarian": "Hungary", "Romanian": "Romania",
    "Greek": "Greece", "Portuguese": "Portugal", "Irish": "Ireland",
    # Alternative country names to canonical World Bank names
    "Czech Republic": "Czechia", "Swaziland": "Eswatini",
    "East Timor": "Timor-Leste", "Ivory Coast": "Cote d'Ivoire",
    "Cape Verde": "Cabo Verde",
    "Guinea-Bissau": "Guinea-Bissau",  # prevent "Guinea" substring match
    # Korea disambiguation. The World Bank indexes these
    # separately; an unqualified "Korea" alone is ambiguous and should
    # stay as "Korea" so the verifier layer can decide how to resolve
    # it, but the explicit "North Korea" / "South Korea" forms must
    # pass through without collapsing.
    "North Korea": "North Korea",
    "South Korea": "South Korea",
    # Dominican Republic: the bare "Dominican" demonym already maps
    # to "Dominican Republic" (above in the demonym section; see
    # the entry below); the explicit country name must be present
    # here so fullmatch-based callers resolve it.
    "Dominican Republic": "Dominican Republic",
    # Cote d'Ivoire in its canonical form is self-mapping so callers
    # that pass the plain-ASCII country name straight through get
    # the same result as going via "Ivory Coast".
    "Cote d'Ivoire": "Cote d'Ivoire",
}


def _claim_country(decomp):
    """The country a claim is about: an inherited subject counts, since
    "Its GDP that year" names none of its own."""
    if decomp.subject and _COUNTRY_NAMES_RE.fullmatch(decomp.subject):
        # "Czech" is Czechia: the World Bank knows the country, not the word.
        return _COUNTRY_CANONICAL.get(
            decomp.subject, _COUNTRY_CANONICAL.get(decomp.subject.title(), decomp.subject))
    # "the Dutch economy" is the Netherlands; "Mexico City" is not Mexico.
    economy = re.fullmatch(r'(?:the\s+)?(.+?)\s+economy', decomp.subject or "", re.IGNORECASE)
    if economy and _COUNTRY_NAMES_RE.fullmatch(economy.group(1)):
        named = economy.group(1)
        return _COUNTRY_CANONICAL.get(named, _COUNTRY_CANONICAL.get(named.title(), named))
    return _detect_country(decomp.sentence, decomp.heading)


def _detect_country(sentence, heading):
    """Detect a country name in the claim context.

    Checks full country names (case-insensitive), common demonyms
    (case-insensitive), and abbreviations US/UK/EU (case-sensitive
    to avoid matching pronouns like 'us').
    Returns the canonical country name for API queries.
    """
    for text in [heading, sentence]:
        if not text:
            continue
        text = _DOLLAR_DENOMINATION_RE.sub('dollars', text)
        # Full names and demonyms (case-insensitive)
        m = _COUNTRY_NAMES_RE.search(text)
        if m:
            matched = m.group()
            return _COUNTRY_CANONICAL.get(matched, _COUNTRY_CANONICAL.get(matched.title(), matched))
        # Abbreviations (case-sensitive)
        m = _COUNTRY_ABBREV_RE.search(text)
        if m:
            return _COUNTRY_CANONICAL.get(m.group(), m.group())
    return None


# ── World Bank ──

_WORLDBANK_INDICATORS = {
    "gdp": "NY.GDP.MKTP.CD",
    "gdp_per_capita": "NY.GDP.PCAP.CD",
    "population": "SP.POP.TOTL",
    "life_expectancy": "SP.DYN.LE00.IN",
    "inflation": "FP.CPI.TOTL.ZG",
    "unemployment": "SL.UEM.TOTL.ZS",
    "poverty": "SI.POV.DDAY",
    "co2": "EN.ATM.CO2E.PC",
    "literacy": "SE.ADT.LITR.ZS",
    "internet": "IT.NET.USER.ZS",
}


def _detect_wb_indicator(sentence, metric):
    """Detect which World Bank indicator to query.

    Branch order matters: more-specific matches must run before
    broader ones. "GDP per capita" contains "gdp", so the per-capita
    branch MUST be checked first or every per-capita claim collapses
    to the total-GDP indicator (calibration finding B.2, 2026-04-16).
    """
    text = sentence.lower()
    # Named shares first: "58 percent of residents live in cities" is not a
    # head count, though "residents" reads like one.
    if re.search(r'\burbani[sz]ation\b|\blive\s+in\s+(?:cities|towns|urban)|'
                 r'\bliving\s+in\s+(?:cities|towns|urban)', text) or (
                     "urban population" in text and ("%" in text or "percent" in text)):
        return "SP.URB.TOTL.IN.ZS", "Urban population (% of total)"
    if "access to electricity" in text:
        return "EG.ELC.ACCS.ZS", "Access to electricity (% of population)"
    if re.search(r'\binternet\s+(?:use|users|penetration|access)\b', text):
        return "IT.NET.USER.ZS", "Internet users (% of population)"
    if re.search(r'\bunder[- ]five\s+mortality\b|\bchild\s+mortality\b', text):
        return "SH.DYN.MORT", "Under-five mortality (per 1,000 live births)"
    # A figure's own metric first: "a population of 2 million enjoys a life
    # expectancy of 82 years" mentions both.
    if metric == "population":
        return "SP.POP.TOTL", "Population"
    if metric == "lifespan":
        return "SP.DYN.LE00.IN", "Life expectancy"
    if re.search(r'\bexports?\b', text) and ("of gdp" in text or "share of" in text):
        return "NE.EXP.GNFS.ZS", "Exports of goods and services (% of GDP)"
    # The figure's own metric decides between the two GDP series: "$16bn,
    # putting GDP per head at $13,000" names both.
    # Gross domestic income shares the stem "gross domestic" with the
    # product. The product, and a sentence that still says GDP, stay.
    if ("gross domestic income" in text and "gross domestic product" not in text
            and not re.search(r"\bgdp\b", text)):
        return None, None
    if metric == "gdp_per_capita":
        return "NY.GDP.PCAP.CD", "GDP per capita"
    if metric == "gdp":
        return "NY.GDP.MKTP.CD", "GDP (current US$)"
    if ("per capita" in text or "gdp per head" in text or "income per person" in text
            or "gdp per person" in text or "per inhabitant" in text
            or "per person basis" in text or "per resident" in text):
        return "NY.GDP.PCAP.CD", "GDP per capita"
    if metric == "gdp" or "gdp" in text or "gross domestic" in text:
        return "NY.GDP.MKTP.CD", "GDP (current US$)"
    # "Total output came to $1.9 billion", "Size of the economy: $40.8 billion"
    # (v22): the economy's size in dollars.
    if "$" in text and re.search(
            r'\b(?:total|overall|economic)\s+output\b|\bsize\s+of\s+the\s+economy\b|'
            r'\beconomy\s+(?:size|was\s+worth|is\s+worth|worth)\b', text):
        return "NY.GDP.MKTP.CD", "GDP (current US$)"
    if metric == "population" or "population" in text:
        return "SP.POP.TOTL", "Population"
    if metric == "area":
        return "AG.SRF.TOTL.K2", "Surface area (sq. km)"
    if "life expectancy" in text or metric == "lifespan":
        return "SP.DYN.LE00.IN", "Life expectancy"
    if "inflation" in text or "cpi" in text or "consumer prices" in text:
        # "core inflation" and "core CPI" are another index. "the core of
        # the story is that inflation" is the headline rate: core has to
        # sit on the series word. PCE has no headline series here.
        if re.search(r'\b(?:pce|personal\s+consumption)\b', text):
            return None, None
        if re.search(
                r'\bcore\b[\w\s-]{0,12}(?:inflation|cpi|consumer\s+prices|rate)\b',
                text):
            return None, None
        return "FP.CPI.TOTL.ZG", "Inflation rate"
    if "unemployment" in text or "jobless" in text:
        return "SL.UEM.TOTL.ZS", "Unemployment rate"
    if "poverty" in text:
        return "SI.POV.DDAY", "Poverty rate"
    return None, None


# Words that make a head count a country's total. "12 million people in
# Germany use the service" has none of them.
_COUNTRY_TOTAL_RE = re.compile(
    r'\bpopulation\b|'
    r'\b(?:home\s+to|had|has)\s+[a-z\s]*?[\d.,]+\s*(?:million|billion)?\s+'
    r'(?:people|residents|inhabitants)\b(?!\s+(?:who|that|use|using))|'
    r'\b(?:people|residents|inhabitants)\s+lived\s+in\b|'
    # "32.4 million people lived there", "5.6 million people live in the country" (v21).
    r'\b(?:people|residents|inhabitants)\s+(?:lived|live|living)\s+(?:there|in\s+the\s+country)\b',
    re.IGNORECASE,
)

# Canonical names the World Bank spells differently.
_WB_COUNTRY_ALIASES = {
    "south korea": "KR", "korea": "KR", "north korea": "KP",
    "russia": "RU", "turkey": "TR", "egypt": "EG", "iran": "IR",
    "vietnam": "VN", "venezuela": "VE", "yemen": "YE", "syria": "SY",
    "laos": "LA", "slovakia": "SK", "czech republic": "CZ",
    "czechia": "CZ", "european union": "EU",
    "turkiye": "TR", "türkiye": "TR", "viet nam": "VN", "slovak republic": "SK",
    "kyrgyz republic": "KG", "lao pdr": "LA", "cabo verde": "CV",
    "syrian arab republic": "SY", "uae": "AE", "the emirates": "AE",
    "democratic republic of the congo": "CD", "republic of the congo": "CG",
    "macao": "MO", "macau": "MO", "sint maarten": "SX", "hong kong": "HK",
    "curacao": "CW", "curaçao": "CW", "west bank and gaza": "PS", "palestine": "PS",
    "st. martin": "MF", "saint martin": "MF", "saint-martin": "MF",
}
# Filled once per process from the World Bank's own country list.
_WB_COUNTRY_CODES = {}
_MONTH_NAME_RE = re.compile(
    r'\b(January|February|March|April|May|June|July|August|September|'
    r'October|November|December)\b'
)
# Bare "Congo" is two countries (v22: the Republic's figures were refuted with
# the DRC's): it may confirm, never refute.
_AMBIGUOUS_PLACE_NAMES = frozenset({"georgia", "jordan", "chad", "turkey", "congo"})
# Georgia is the one of those names whose other reading is itself a place
# with a population and an economy. Turkey, Jordan, and Chad are not:
# a bird, a person, and a given name have none of these series, and
# silencing them would drop true country confirms.
_GEORGIA_COUNTRY_RE = re.compile(
    r"\b(?:tbilisi|caucasus|sakartvelo|republic of georgia|"
    r"country of georgia|georgia the country|nation of georgia)\b",
    re.IGNORECASE,
)
_WB_TOTAL_INDICATORS = frozenset({
    "SP.POP.TOTL", "NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "AG.SRF.TOTL.K2",
})


def _wb_indicator_for(decomp):
    """The series the figure's own clause names: in "Inflation was ... and
    Colombia's unemployment rate of 10.2% was several times Mexico's 2.8%",
    2.8% is unemployment. With no series in the clause, the sentence decides.
    A percentage is never a head count, whatever metric it was given: "the
    urban share at roughly 24 percent" is not Malawi's population."""
    metric = "" if decomp.metric == "population" and decomp.unit == "percent" \
        else decomp.metric
    clause = _clause_holding(decomp.sentence, decomp.raw_value)
    if decomp.unit == "percent" and _is_real_growth(decomp.sentence, decomp.raw_value, clause):
        return "NY.GDP.MKTP.KD.ZG", "GDP growth (annual %)"
    # "Growth has been weak in normal years: 1.2% in 2016" in an answer about
    # a country's economy is GDP growth. A lone "Growth was 2.1%" can be
    # anything's, so this needs the document's context, and it only confirms
    # (2026-11-27: the largest class of unchecked true figures on v26-v27).
    head = _growth_head(decomp.sentence, decomp.raw_value).lower()
    if (decomp.unit == "percent" and decomp.doc_about_economy and _claim_country(decomp)
            and _BARE_GROWTH_RE.search(head)
            and not _GROWTH_OF_THING_RE.search(head)
            and not _OWN_MEASURE_RE.search(clause)):
        decomp.confirm_only = True
        return "NY.GDP.MKTP.KD.ZG", "GDP growth (annual %)"
    found = _detect_wb_indicator(clause, metric)
    if not found[0]:
        found = _detect_wb_indicator(decomp.sentence, metric)
    # "The economy grew from $250.1 billion to $301.0 billion": a dollar total
    # of the economy, named as such, with no series word of its own.
    if (not found[0] and decomp.unit == "currency" and abs(decomp.value or 0) >= 1e8
            and re.search(r"\b(?:economy|gdp|output)\b", clause, re.IGNORECASE)):
        found = ("NY.GDP.MKTP.CD", "GDP (current US$)")
    return _by_magnitude(decomp, found)


def _by_magnitude(decomp, found):
    """What a figure's size says it is, when the words chose another series
    (2026-11-27, the "far off" class: "$422.2 billion" checked as income per
    person, "$6,968" as total GDP, "11.8 million" people as income per
    person, each because another measure shared the sentence)."""
    indicator = found[0]
    value = abs(decomp.value or 0)
    if decomp.unit == "currency" and indicator in ("NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD"):
        if indicator == "NY.GDP.MKTP.CD" and 0 < value < 1e6:
            return "NY.GDP.PCAP.CD", "GDP per capita"
        # Per-person words in the figure's own clause with a national-size
        # number is a mismatch to decline, not a total to match ("GDP per
        # inhabitant was $4.5 trillion", pinned).
        own = _clause_holding(decomp.sentence, decomp.raw_value) if decomp.raw_value else ""
        if (indicator == "NY.GDP.PCAP.CD" and value >= 1e8 and own
                and not re.search(r"per\s*-?\s*(?:capita|head|person|inhabitant|resident)|income",
                                  own, re.IGNORECASE)):
            return "NY.GDP.MKTP.CD", "GDP (current US$)"
    if (decomp.unit == "count" and value >= 1e5 and indicator != "SP.POP.TOTL"
            and re.search(r"million|billion", decomp.raw_value or "", re.IGNORECASE)
            and re.search(r"\bpopulation\b", decomp.sentence or "", re.IGNORECASE)):
        return "SP.POP.TOTL", "Population"
    return found


def _growth_head(sentence, raw_value):
    """The words that say what a rate is: back to the figure before it, and
    past it when this one is only what that figure came after, as 5.3% in
    "slowed to 0.2% after 5.3% in 2022"."""
    return _growth_reading(sentence, raw_value)[0]


# Words between rates in a series that say nothing of what is measured:
# "in 2021, then", "and another", "after shrinking".
_SERIES_FILLER_RE = re.compile(
    r'(?:\s|%|[,;:()+\-\u2212>*]|\b20[0-3]\d\b|\b(?:in|after|from|up|down|compared|with|'
    r'to|vs|versus|then|and|another|a|an|further|followed|by|very|strong|weak|growing|'
    r'expanding|shrinking|contracting|rising|falling|before|that)\b|\.(?!\s*[A-Z]))*',
    re.IGNORECASE,
)


def _growth_reading(sentence, raw_value):
    """The head that says what a rate is, and the filler passed on the way
    back to it, nearest first."""
    sentence = sentence or ""
    raw = str(raw_value or "").strip()
    end = sentence.find(raw) if raw else -1
    leads = []
    if end < 0:
        # No figure to place: the whole sentence says what it is.
        return sentence, leads
    for _ in range(6):
        if end < 0:
            break
        head = _figure_clause(sentence[:end + len(raw)], raw)
        lead = head.removesuffix(raw)
        if not _SERIES_FILLER_RE.fullmatch(lead):
            return head, leads
        leads.append(lead)
        before = sentence[:end]
        prior = list(re.finditer(r'-?\d[\d,.]*\s?%', before))
        if not prior:
            return head, leads
        raw = prior[-1].group().strip()
        end = prior[-1].start()
    return "", leads


# A part of a year. Not "quarterly report", and not a bare "H1" heading.
# Digits, a hyphen, and "q/q" are the same observation as the words.
_PART_OF_YEAR_FIGURE_RE = re.compile(
    r"\b(?:nine|six|three|9|6|3)[\s-]+months\b|"
    r"\b(?:nine|six|9|6)[\s-]month\b|"
    r"\bfirst[\s-]+(?:half|three[\s-]+quarters)\b|"
    r"\bsecond[\s-]+half\b|"
    r"\bhalf[\s-]year\b|"
    r"\byear[\s-]+to[\s-]+date\b|\bYTD\b|"
    r"\b(?:H[12]|[12]H)\s*['\u2019]?\s*(?:20[0-3]\d|\d{2})\b|"
    r"\bon\s+a\s+quarterly\s+basis\b|"
    r"\bquarterly\s+(?:gdp|growth|rate|average|figure|basis)\b|"
    r"\bquarter[\s-]on[\s-]quarter\b|\bq/q\b|\bqoq\b|"
    r"\brun[\s-]rate\b|"
    r"\bseasonally\s+adjusted\s+annual\s+rate\b|"
    r"\bannuali[sz]ed\b|"
    # "in the quarter" and "in the past quarter" are not the year. "on the
    # quarter" is the same observation. "the fourth quarter" is already a
    # numbered quarter. "in the quarter before" is the comparison.
    # "quarter century" is not a quarter.
    r"\b(?:in|for|during|within|on)\s+the\s+"
    r"(?:(?:past|previous|prior|last|latest)\s+)?"
    r"quarter\b(?!\s+(?:before|earlier|prior|ago|century|of\s+a\s+century))|"
    # "in the month" and "for the week" are not the year. "in the month
    # before" is the comparison. "in the month of June" is that month.
    r"\b(?:in|for|during|within)\s+the\s+month\b(?!\s+(?:before|earlier|prior|ago|"
    r"of\s+(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)))|"
    r"\b(?:in|for|during|within)\s+the\s+week\b(?!\s+(?:before|earlier|prior|ago))|"
    # "month on month" and "from the prior month" are not the year.
    # "up from the prior month" is a comparison and is already stripped.
    # "mom" alone is not: it is a name.
    r"\bmonth[\s-]on[\s-]month\b|\bm/m\b|"
    # "m-o-m" and "m.o.m." are the same span. "Mom" has no separators.
    r"\bm[\s.\-]+o[\s.\-]+m\b|"
    r"\bfrom\s+the\s+(?:prior|previous)\s+month\b|"
    r"\btrailing\s+twelve[\s-]*months?\b|\bttm\b|"
    r"\btwelve[\s-]*months?\s+trailing\b",
    re.IGNORECASE,
)
# A later quarter, half, or month that names a different year.
_OTHER_YEAR_PERIOD_RE = re.compile(
    r"\b(?:(?:first|second|third|fourth|1st|2nd|3rd|4th)[\s-]+quarter|"
    r"Q[1-4]|(?:first|second)[\s-]+half|half[\s-]year|"
    r"(?:nine|six|three|9|6|3)[\s-]+months|"
    r"year[\s-]+to[\s-]+date|YTD|(?:H[12]|[12]H)|"
    r"January|February|March|April|May|June|July|August|September|"
    r"October|November|December)"
    r"\b(?:\s+of)?\s+['\u2019]?(20[0-3]\d)",
    re.IGNORECASE,
)
# Current-dollar GDP is not a constant-price level.
_REAL_LEVEL_RE = re.compile(
    r"\breal\s+(?:gdp|gross|output|terms)\b|"
    r"\bin\s+(?:real|volume)\s+terms\b|"
    # "constant 2015 prices" is still constant prices. The year sits
    # between the words. "at 2023 prices" is not this.
    r"\bconstant\s+(?:20[0-3]\d\s+)?(?:prices|dollars)\b|"
    r"\bchained\s+(?:20[0-3]\d\s+)?(?:dollars|prices)\b",
    re.IGNORECASE,
)
# Purchasing-power GDP is not the current-dollar series either.
_PPP_RE = re.compile(
    r"\bpurchasing[\s-]power(?:\s+parity)?\b|\bppp\b|"
    r"\binternational\s+dollars?\b",
    re.IGNORECASE,
)
# "at current prices" is nominal. "at market prices" is not: real growth
# at market prices is the headline real series.
_CURRENT_PRICES_RE = re.compile(
    r"\b(?:at|in)\s+current\s+prices\b|\bin\s+nominal\s+terms\b|\bnominal\b",
    re.IGNORECASE,
)
# "euro area" is a place. "euro GDP" and "in euros" are a currency.
_EURO_AREA_RE = re.compile(r"\beuro[\s-]?(?:area|zone)\b", re.IGNORECASE)
# A component index is not headline CPI. Same qualifiers FRED already uses.
# "underlying" counts only when it sits on the series word. "the underlying
# story of inflation" is still the headline rate.
_HEADLINE_PRICE_RE = re.compile(
    r"\b(?:inflation|cpi|consumer\s+prices)\b", re.IGNORECASE)
# A published price line. "all items" and "the services report" are not.
# "recreation of", "lodging a complaint", and "in communication with"
# are not the line. Bare "hospital" is a place. Bare "gas" is not.
_PRICE_LINE = (
    r"owners?'?\s+equivalent\s+rent|"
    r"household\s+furnishings|"
    r"alcoholic\s+beverages?|"
    r"airline\s+fares?|"
    r"utility\s+gas|"
    r"motor\s+fuel|"
    r"personal\s+care|"
    r"child\s+care|"
    r"hospital\s+services?|"
    r"prescription\s+drugs?|"
    r"used\s+cars?|"
    r"new\s+cars?|"
    r"house\s+prices?|"
    r"home\s+prices?|"
    r"recreation(?!\s+of\b)|"
    r"lodging(?!\s+a\b)|"
    r"communication(?!\s+with\b)|"
    r"tobacco|electricity|fuel|"
    r"apparel|clothing|transport(?:ation)?|gasoline|vehicles?|"
    r"education|tuition|airfares?|"
    # More published lines. A plain word between "for" and a line already
    # here ("public transportation", "fuel oil") was still the headline.
    # Bare information, hotels, gas, and prescription stay off: those
    # words are ordinary English. "furniture of", "parking a", and
    # "computers of" are not the line.
    r"food\s+away\s+from\s+home|motor\s+vehicle\s+insurance|"
    r"motor\s+vehicle\s+maintenance|car\s+insurance|household\s+energy|"
    r"fuel\s+oil|health\s+insurance|dental\s+services|physicians'?\s+services|"
    r"nursing\s+homes?|eye-?glasses|car\s+rental|sporting\s+goods|"
    r"club\s+membership|window\s+coverings|floor\s+coverings|major\s+appliances|"
    r"furniture(?!\s+of\b)|internet\s+services|wireless\s+telephone|"
    r"garbage\s+collection|tenants'?\s+rent|new\s+vehicles|footwear|"
    r"school\s+books|elder\s+care|home\s+health\s+care|funeral\s+expenses|"
    r"legal\s+services|financial\s+services|haircuts?|housekeeping\s+supplies|"
    r"admission\s+to\s+movies|full[\s-]service\s+meals|limited[\s-]service\s+meals|"
    r"nonprescription\s+drugs|public\s+transport(?:ation)?|delivery\s+services|"
    r"dry[\s-]cleaning|day[\s-]?care|parking(?!\s+a\b)|computers(?!\s+of\b)|"
    r"smartphones?|propane|postage"
)
_COMPONENT_PRICE_RE = re.compile(
    r"\b(?:food|energy|shelter|rent|services|goods|wage|producer|ppi|import|"
    r"export|medical|housing|median|trimmed|sticky|super-?core|"
    r"harmonis(?:ed|zed)|hicp|chained|breakeven|" + _PRICE_LINE + r")\b"
    r"[\w\s-]{0,12}$|"
    r"\bunderlying[\s-]*$|"
    # "C-CPI" is chained CPI. The letter sits on the series word.
    r"(?:^|[^A-Za-z])c[\s-]*$",
    re.IGNORECASE,
)
# A subset or a notional level is not national GDP. "a potential record"
# does not match: the word has to name the product.
_NOT_HEADLINE_GDP_RE = re.compile(
    r"\bnon[- ]oil\s+(?:gdp|gross|output|growth|economy)\b|"
    r"\bprivate[- ]sector\s+(?:gdp|output|growth)\b|"
    r"\bpotential\s+(?:gdp|gross|output|growth)\b",
    re.IGNORECASE,
)
# Basic prices and factor cost are not market-price GDP. Market prices stay.
# Producer prices are the other valuation. Purchaser's prices stay.
_BASIC_OR_FACTOR_RE = re.compile(
    r"\b(?:at\s+)?basic\s+prices?\b|\bfactor\s+costs?\b|"
    r"\b(?:at\s+)?producer(?:s'|\s*'s|s)?\s+prices?\b",
    re.IGNORECASE,
)
# A sector word on GDP is that sector's product. "Manufacturing rose,
# while GDP was" is the other clause, so the word has to sit on GDP.
# "nonfarm payrolls" is not this: nonfarm has to sit on GDP.
_SECTOR_ON_GDP_RE = re.compile(
    r"\b(?:manufactur\w*|industr\w*|oil|private|services?|construction|"
    r"agricultur\w*|mining|nonfarm(?:\s+business)?|market[\s-]sector|"
    r"household(?:\s+consumption)?|private\s+consumption|"
    r"government(?:\s+consumption)?|fixed\s+investment|consumption|investment)"
    r"(?:\s+sector)?\s+(?:gdp|gross)\b",
    re.IGNORECASE,
)
# "GDP in manufacturing" is the sector too. The sector word comes after
# GDP. "in the manufacturing report" and "in oil-importing terms" are not
# a sector. The word after the sector has to be the verb, or nothing.
_GDP_SECTOR = (
    r"(?:manufactur\w*\b|industr\w*\b|agricultur\w*\b|construction\b|mining\b|"
    r"services\b|household(?:\s+consumption)?\b|private\s+consumption\b|"
    r"government(?:\s+consumption)?\b|fixed\s+investment\b|consumption\b|"
    r"investment\b|oil(?!-)\b|private\s+sector\b)"
)
_GDP_SECTOR_FOLLOW = (
    r"(?:\s+sector\b)?(?!\s+(?!was\b|were\b|is\b|are\b|grew\b|growth\b|rose\b|"
    r"of\b|and\b|in\b|at\b|output\b)[A-Za-z])"
)
_GDP_IN_SECTOR_RE = re.compile(
    r"\bgdp\b(?:\s+[\w$.,%+-]+){0,10}\s+(?:in|from|of|for)\s+(?:the\s+)?"
    + _GDP_SECTOR + _GDP_SECTOR_FOLLOW,
    re.IGNORECASE,
)
# "contribution to GDP" is a sector's piece of the total, not the total.
_CONTRIBUTION_TO_GDP_RE = re.compile(
    r"\bcontribution\s+to\s+(?:the\s+)?(?:[A-Za-z.]+\s+){0,2}?"
    r"(?:gdp|gross\s+domestic)\b",
    re.IGNORECASE,
)
# "at 2023 prices" in 2023 is current prices. "in 2015 prices" is not.
# "in constant 2015 prices" and "in 2017 US dollars" name the base year
# with a word between the old pair. "(2015 prices)", "prices of 2015",
# "in 2017 USD", "in real 2015 dollars", and "chained (2017) dollars"
# are the same base. "on a 2015 basis" and "reference year 2015" are
# handled apart: with no other year they can be the observation year.
_PRICE_BASE_YEAR_RE = re.compile(
    r"\b(?:at|in)\s+(?:constant\s+|chained\s+|real\s+)?(20[0-3]\d)\s+"
    r"(?:us\s+|chained\s+)?prices\b|"
    r"\b(?:at|in)\s+prices\s+of\s+(20[0-3]\d)\b|"
    r"\(\s*(20[0-3]\d)\s+prices\s*\)|"
    r"\bin\s+(?:constant\s+|chained\s+|real\s+)?(20[0-3]\d)\s+"
    r"(?:us\s+|chained\s+)?(?:dollars|usd)\b|"
    r"\bchained\s*\(\s*(20[0-3]\d)\s*\)\s*dollars\b|"
    r"\bchained[\s-](20[0-3]\d)\s+dollars\b",
    re.IGNORECASE,
)
_AMBIGUOUS_PRICE_YEAR_RE = re.compile(
    r"\bon\s+a\s+(20[0-3]\d)\s+basis\b|"
    r"\breference\s+year\s+(20[0-3]\d)\b",
    re.IGNORECASE,
)
# "at previous year's prices" is last year's prices. "compared with last
# year's prices" is the comparison, and the tail is stripped first.
# Real growth at those prices is still real growth, so this is levels only.
_PRIOR_YEAR_PRICES_RE = re.compile(
    r"\b(?:at|in)\s+(?:the\s+)?(?:previous|prior|last)\s+year(?:['\u2019]s|s)?\s+prices\b|"
    r"\byear[\s-]earlier\s+prices\b",
    re.IGNORECASE,
)
# Chain-linked volumes are a constant-price level. Real growth "in
# chain-linked volumes" is still the growth series, and real GDP is GDPC1.
_CHAIN_VOLUME_RE = re.compile(
    r"\bchain[\s-]linked\b|\bchain[\s-]volume\b|\bchain[\s-]weighted\b",
    re.IGNORECASE,
)
# A run rate stated as "at an annual rate", without the word annualized.
# Inflation at an annual rate is still the year's inflation.
_ANNUAL_RATE_RE = re.compile(r"\bat\s+an\s+annual\s+rate\b", re.IGNORECASE)
# Pounds, sterling, and dollar-sign prefixes the filing reader does not use.
# "pounds of" is weight. "a sterling result" is not a currency.
_WB_OTHER_UNIT_RE = re.compile(
    r"\bpounds?\b(?!\s+of\b)|"
    r"\b(?:Canadian|Australian|Hong\s+Kong|New\s+Zealand|Singapore)\s+dollars?\b|"
    r"\bin\s+sterling\b|\bsterling\s+(?:gdp|gross)\b",
    re.IGNORECASE,
)
_US_DOLLAR_PREFIX_RE = re.compile(r"(?:^|[^A-Za-z])US$", re.IGNORECASE)
_OTHER_DOLLAR_PREFIX_RE = re.compile(
    r"(?:^|[^A-Za-z])(?:Can|HK|NZ|NT|CA|AU|[CARS])$", re.IGNORECASE)
# "in local currency" is not the World Bank's dollar series. The United
# States is the one country whose local currency is that series.
_LOCAL_CURRENCY_RE = re.compile(
    r"\bin\s+(?:local|national|domestic)[\s-]currency\b", re.IGNORECASE)
_DOLLAR_HOME_RE = re.compile(
    r"^(?:united states|us|usa|america)$", re.IGNORECASE)
# Youth, long-term, or U-6 unemployment is not the total rate. "the claim
# that unemployment" is the total rate. Claims count only beside the word.
_LABOR_BEFORE_RE = re.compile(
    r"\b(?:youth|teenage|teen|long[\s-]*term|female|male|u-?6|"
    r"prime[\s-]*age|black|insured)\b",
    re.IGNORECASE,
)
_LABOR_AFTER_RE = re.compile(
    r"\b(?:among\s+(?:youth|teens|women|men)|youth|teens|"
    r"long[\s-]*term|women|men|female|male|u-?6|"
    r"prime[\s-]*age|black|insured)\b",
    re.IGNORECASE,
)
# These have to sit on the word. "The White House said unemployment" and
# "after the Asian crisis, unemployment" are the total rate. U-3 stays.
_LABOR_TIGHT_BEFORE_RE = re.compile(
    r"\b(?:hispanic|latino|latina|asian|white|african[\s-]*american|"
    r"foreign[\s-]*born|native[\s-]*born|"
    r"college(?:[\s-]*educated|\s+graduate(?:s)?)?|"
    r"teenagers?'?|"
    r"25[\s-]*to[\s-]*54|25[\s-]54|"
    r"u-[1245]|registered|harmonis(?:ed|zed))\s+$",
    re.IGNORECASE,
)
# "unemployment rate for Hispanics", "was 3.7% for Hispanics", and
# "stood at 3.7% for Hispanics" are that group. "for the year" is the
# total: the word after for/among/of has to be the group. "because of
# the foreign-born" is not this shape.
_LABOR_TIGHT_AFTER_RE = re.compile(
    r"^\s*(?:rate\s+|(?:was|were|is|are|stood|reached)\s+(?:at\s+)?[\d.]+\s*%?\s+)?"
    r"(?:among|for|of)\s+(?:hispanics|latinos|asians|whites|teenagers|"
    r"college\s+graduates|the\s+foreign[\s-]*born|african[\s-]*americans|"
    r"veterans)\b|"
    r"^\s*(?:rate\s+|(?:was|were|is|are|stood|reached)\s+(?:at\s+)?[\d.]+\s*%?\s+)?"
    r"(?:aged\s+)?(?:25[\s-]*to[\s-]*54|25[\s-]54)\b",
    re.IGNORECASE,
)
# An education group on this rate. The comma footnote stays the total.
_LABOR_SCHOOL_RE = re.compile(
    r"without\s+a\s+high\s+school\s+diploma|"
    r"less\s+than\s+(?:a\s+)?high\s+school\b|"
    r"high\s+school\s+graduates?\b|"
    r"bachelor'?s\s+degree\b|"
    r"with\s+a\s+high\s+school\s+diploma\b|"
    r"with\s+some\s+college\b|"
    r"some\s+college\s+or\s+associate\b|"
    r"associate'?s?\s+degree\b|"
    r"master'?s\s+degree\b|"
    r"advanced\s+degree\b|"
    # "pages 16 to 19" has no age word. "ages" inside "pages" is not one.
    r"\b(?:aged|ages?)\s+16[\s-]*(?:to[\s-]*)?19\b|"
    r"16[\s-]*to[\s-]*19[\s-]*year|"
    r"part[\s-]time\s+workers?\b|"
    r"(?:among|for|of)\s+(?:people|persons|those|workers)\s+with\s+a\s+disability\b|"
    # A labor-force status, not the 16-and-over total. "and" opens the
    # next clause, so "aged 55 and over" arrives as "aged 55". 16 stays.
    r"job\s+losers?\b|job\s+leavers?\b|new\s+entrants?\b|\bre-?entrants?\b|"
    r"discouraged\s+workers?\b|marginally\s+attached\b|"
    r"\b(?:aged|ages?)\s+(?!16\b)\d+\b|"
    r"multiple\s+job-?holders?\b|self[\s-]employed\b|"
    r"part[\s-]time\s+for\s+economic\s+reasons\b|"
    r"(?:on\s+)?temporary\s+lay-?offs?\b",
    re.IGNORECASE,
)
# "CPI for food" and "inflation was 4.1% in services" are not headline
# CPI. "inflation was 4.1% in 2023", "CPI for all urban consumers",
# "in the services report", and "services-led" are. A decimal in the
# figure is not a sentence break.
_COMPONENT_NEXT_OK = (
    r"sector|prices?|index|category|component|care|services|goods|markets|"
    r"market|industr(?:y|ies)|"
    r"and|or|in|of|for|on|at|during|was|were|is|are|rose|fell"
)
_COMPONENT_AFTER_SERIES_RE = re.compile(
    r"\b(?:inflation|cpi|consumer\s+prices)\b"
    r"(?:(?!\b(?:while|whereas|but)\b)(?!\.\s+[A-Z])[^;]){0,120}?"
    r"\b(?:for|in|on)\s+(?:the\s+)?"
    r"(?:food|energy|shelter|rent|services(?!-)|goods|housing|medical|"
    + _PRICE_LINE + r")\b"
    r"(?!\s+(?!(?:" + _COMPONENT_NEXT_OK + r")\b)[A-Za-z])",
    re.IGNORECASE,
)
# "CPI excluding shelter was" is not the headline basket. "Excluding
# agriculture, GDP was" is not the national total. The next clause of
# this sentence counts when it is only a basket exclusion. A change,
# a strike, "not excluding", and "less than" stay. "ex-" only with a
# basket word, so "ex-president" is not a basket.
_EXCLUSION_RE = re.compile(
    r"(?<!not\s)\bexcluding\s+(?!nothing\b)(?:the\s+)?[A-Za-z]|"
    r"(?<!not\s)\bex-\s*(?:food|energy|shelter|rent|services|goods|housing|"
    r"medical|agricultur\w*|oil|fuel)\b|"
    r"\bless\s+(?!than\b)(?:the\s+)?"
    r"(?:food|energy|shelter|rent|services|goods|housing|medical|"
    r"agricultur\w*|oil)\b",
    re.IGNORECASE,
)
# After the figure, only a basket word is an exclusion. "excluding the
# effects of a strike" is not. "not excluding", "less than", and
# "ex-president" are not. The word after the basket has to be glue or
# the clause has to end, so "outside of the energy ministry" stays.
_BASKET = (
    r"(?:food|energy|shelter|rent|services|goods|housing|medical|"
    r"agricultur\w*|oil|fuel)"
)
_BASKET_FOLLOW = (
    r"(?!\s+(?!(?:in|of|for|on|at|during|and|or|sector|prices?|"
    r"was|were|is|are|grew|growth|rose|fell)\b)[A-Za-z])"
)
_BASKET_EXCLUSION_RE = re.compile(
    r"(?<!not\s)\bexcluding\s+(?:the\s+)?" + _BASKET + _BASKET_FOLLOW + r"|"
    r"(?<!not\s)\bex[-\s]+" + _BASKET + _BASKET_FOLLOW + r"|"
    r"\bless\s+(?!than\b)(?:the\s+)?" + _BASKET + _BASKET_FOLLOW + r"|"
    r"\bother\s+than\s+(?:the\s+)?" + _BASKET + _BASKET_FOLLOW + r"|"
    r"\boutside\s+of\s+(?:the\s+)?" + _BASKET + _BASKET_FOLLOW + r"|"
    r"\b" + _BASKET + r"\s+excluded\b" + _BASKET_FOLLOW,
    re.IGNORECASE,
)
# "from" stays out of the shared follow list, so "from Germany" and
# "from the total economy" stay. A footnote that names the total is
# still the basket. "less than" is not "less" plus a basket.
_FROM_THE_TOTAL_RE = re.compile(
    (
        r"(?<!not\s)\b(?:excluding\s+|ex[-\s]+|less\s+|other\s+than\s+|outside\s+of\s+)"
        r"(?:the\s+)?"
        + _BASKET
        + r"\s+from\s+(?:the\s+)?(?:total|figure|series|headline|number|aggregate)\b"
        r"(?!\s+(?!(?:was|were|is|are|in|of|at|a|an|the|and|or|rate)\b)[A-Za-z])"
    ),
    re.IGNORECASE,
)
# "net of agriculture" takes the basket out. "net of tax" and
# "net of the energy ministry" name something else.
_NET_OF_RE = re.compile(
    (
        r"(?<!not\s)\bnet\s+of\s+(?:the\s+)?"
        + _BASKET
        + r"(?:\s+from\s+(?:the\s+)?(?:total|figure|series|headline|number|aggregate)\b)?"
        r"(?!\s+(?!(?:was|were|is|are|in|of|at|a|an|the|and|or|rate)\b)[A-Za-z])"
    ),
    re.IGNORECASE,
)
# A span that is not the year, when it sits on this figure. "so far" alone
# is a story. "After four quarters" is not "over the past four quarters".
# "in the monthly report" is not "on a monthly basis". "in the quarterly
# report" is not "at a quarterly pace". These stay out of the part-of-year
# pattern: that one would silence a leading clause that only mentions them.
_SPAN_ON_FIGURE_RE = re.compile(
    r"\bso\s+far\s+this\s+(?:calendar\s+)?year\b|"
    r"\bso\s+far\s+in\s+20[0-3]\d\b|"
    r"\bin\s+the\s+year\s+so\s+far\b|"
    r"\b(?:over|in|for|during|across)\s+the\s+"
    r"(?:past|previous|prior|last|trailing|latest)\s+"
    r"(?:two|three|four|2|3|4)\s+quarters\b|"
    # "Trailing four quarters," names the span. "After four quarters" does not.
    r"\b(?:trailing|past|previous|prior|last)\s+"
    r"(?:two|three|four|2|3|4)\s+quarters\b|"
    r"\bon\s+a\s+monthly\s+basis\b|"
    r"\bat\s+a\s+monthly\s+(?:rate|pace)\b|"
    r"\bat\s+a\s+quarterly\s+pace\b|"
    r"\bon\s+a\s+(?:three|3)[\s-]month\s+basis\b|"
    r"\b(?:three|3)[\s-]month\s+(?:rate|basis|change|pace)\b|"
    r"\bq[\s.\-]*o[\s.\-]*q\b(?!\s+report\b)|"
    r"\bsequentially\b|"
    r"\bsequential\s+(?:growth|rate|gdp|increase|change|pace|basis)\b|"
    r"\b(?:versus|vs\.?)\s+the\s+(?:prior|previous|last|preceding)\s+quarter\b|"
    r"\bfrom\s+the\s+(?:prior|previous|last|preceding)\s+quarter\b|"
    # "quarter on quarter" is already a part of the year. "over" is the
    # other spelling. "in this quarter's report" is the report.
    r"\bquarter[\s-]over[\s-]quarter\b(?!\s+report\b)|"
    r"\bq[\s.\-]*on[\s.\-]*q\b(?!\s+report\b)|"
    r"\b(?:over|across|through)\s+the\s+quarter\b"
    r"(?!\s+(?:before|earlier|prior|ago|century)\b)|"
    r"\b(?:in|for|during)\s+this\s+quarter\b"
    r"(?!\s+(?:before|earlier|prior|ago|century|report)\b)(?!'s)|"
    # "four-quarter" is the span. "After four quarters" is not, and
    # "the four-quarter story" keeps a word that is not the subject.
    r"\b(?:four|4)[\s-]quarter\b(?!\s+report\b)|"
    # "over the latest quarter" has a word the shorter form does not.
    # "last quarter century" and "the ministry said" stay.
    r"\bquarter\s+to\s+quarter\b|"
    r"\b(?:over|across|through)\s+the\s+"
    r"(?:past|previous|prior|last|latest|preceding)\s+quarter\b"
    r"(?!\s+(?:before|earlier|prior|ago|century)\b)|"
    r"\blast\s+quarter\b(?!\s+(?:before|earlier|prior|ago|century)\b)",
    re.IGNORECASE,
)
_SPAN_FILLER = frozenset({
    "the", "a", "an", "its", "their", "of", "in", "at", "for", "and", "on",
    "gdp", "gross", "domestic", "product", "inflation", "cpi", "consumer",
    "prices", "price", "unemployment", "jobless", "economy", "economic",
    "output", "growth", "rate", "real", "nominal", "headline", "annual",
})
_SPAN_TRAIL_VERB = frozenset({
    "was", "were", "is", "are", "grew", "grown", "rose", "risen", "fell",
    "fallen", "increased", "decreased", "expanded", "contracted",
})
# "So far this year, the ministry said" is when they spoke. The figure
# can still be the year.
_SPAN_EVENT_VERB_RE = re.compile(
    r"\b(?:said|says|told|reported|announced|noted|estimated|warned|wrote|spoke)\b",
    re.IGNORECASE,
)
# "rose by $4.5 trillion" and "rose $4.5 trillion" are the change.
# "rose to $4.5 trillion" is the level. "grew by 5.5%" is a rate and
# never reaches this. "backed up by" is not "was up by".
_LEVEL_HEDGE = (
    r"(?:(?:about|nearly|roughly|around|almost|some|just|over|"
    r"more\s+than|approximately)\s+)?"
)
# "jumped" and "edged up" are the change. "jumped to" and "edged up to"
# are the level: "to" is not a hedge.
_LEVEL_VERBS = (
    r"rose|increased|grew|fell|dropped|declined|gained|lost|shrank|expanded|"
    r"climbed|added|jumped|surged|slipped|tumbled|sank|soared|plunged|shed|"
    r"advanced|retreated|narrowed|widened|contracted|"
    r"eased|rebounded|slid|rallied|ballooned|lifted|cut|swelled|doubled|"
    r"pared|shaved|revised"
)
_LEVEL_CHANGE_RE = re.compile(
    r"\b(?:" + _LEVEL_VERBS + r")\s+by\s+" + _LEVEL_HEDGE + r"$|"
    r"(?:was|were|is|are)\s+(?:up|down)\s+by\s+" + _LEVEL_HEDGE + r"$|"
    r"(?:increase|gain|decline|drop|fall|rise|jump|surge|addition|advance|"
    r"contraction)\s+of\s+" + _LEVEL_HEDGE + r"$|"
    r"\b(?:" + _LEVEL_VERBS + r")\s+" + _LEVEL_HEDGE + r"$|"
    r"edged\s+up\s+by\s+" + _LEVEL_HEDGE + r"$|"
    r"edged\s+up\s+" + _LEVEL_HEDGE + r"$|"
    r"(?:was|were|is|are)\s+(?:up|down)\s+(?!by\b|to\b)" + _LEVEL_HEDGE + r"$|"
    r"(?:was|were|is|are)\s+(?:higher|lower)\s+by\s+" + _LEVEL_HEDGE + r"$|"
    # "revised up by" is not "was up by": the verb sits in between.
    r"revised\s+up\s+by\s+" + _LEVEL_HEDGE + r"$",
    re.IGNORECASE,
)
# "a $4.5 trillion increase" names the change after the figure.
# The next clause ("$4.5 trillion, an increase of $200 billion") does not.
# "higher than France" and "more or less" are the level.
_CHANGE_NOUN_AFTER_RE = re.compile(
    r"\s+(?:increase|gain|decline|drop|fall|rise|jump|decrease|surge|addition|"
    r"advance)\b|"
    r"\s+(?:higher|lower|larger|smaller)\b(?!\s+than\b)|"
    r"\s+more\b(?!\s+(?:or\s+less|than)\b)",
    re.IGNORECASE,
)
# Per worker, per hour, per job. Not per capita, per head, or per person.
# A hyphen is the same as a space. "per person in work" is a job.
# "for every worker who asked" keeps the extra word, so it stays the total.
_PER_JOB_RE = re.compile(
    r"\bper[\s-]+(?:filled[\s-]+|full[\s-]time[\s-]+)?"
    r"(?:workers?|hours?|jobs?|employees?|ftes?)\b|"
    r"\bper\s+full[\s-]time\s+equivalents?\b|"
    r"\bper[\s-]+(?:person|head)\s+(?:employed|in\s+work|at\s+work)\b|"
    r"\bper\s+employed\s+(?:persons?|people|workers?)\b|"
    r"\bfor\s+(?:each|every)\s+(?:worker|employee|job|hour)\b|"
    r"\bfor\s+(?:each|every)\s+person\s+employed\b|"
    r"\bon\s+a\s+per[\s-]+(?:worker|employee|job|hour)\s+basis\b",
    re.IGNORECASE,
)
# "calendar-year" is the year. "seasonally adjusted" is often the headline.
# A trading day is the same adjustment as a working day.
_WORKING_SPAN_RE = re.compile(
    r"\bcalendar[\s-]adjusted\b|"
    r"\bworking[\s-]day[\s-]adjusted\b|"
    r"\btrading[\s-]day[\s-]adjusted\b|"
    r"\badjusted\s+for\s+(?:the\s+)?working\s+days?\b|"
    r"\badjusted\s+for\s+(?:the\s+)?trading\s+days?\b|"
    r"\badjusted\s+for\s+(?:the\s+)?calendar\b|"
    # SWDA and WDA are that adjustment when they sit on the series.
    # "The SWDA conference said GDP" does not.
    r"\b(?:swda|wda)\b[\w\s'()-]{0,16}\b(?:gdp|inflation|cpi|consumer)\b|"
    r"\b(?:gdp|inflation|cpi)\b[\w\s'()-]{0,16}\b(?:swda|wda)\b",
    re.IGNORECASE,
)
# "Not seasonally adjusted" GDP is not the seasonally adjusted level.
# The same words on inflation stay: that CPI series is not adjusted.
_NSA_RE = re.compile(r"\bnot\s+seasonally\s+adjusted\b", re.IGNORECASE)
# "expected inflation" and "inflation expectations" are not the outcome.
# "as expected" and "the expected path of inflation" are.
_EXPECTED_INFLATION_RE = re.compile(
    r"\bexpected\s+(?:rate\s+of\s+)?(?:inflation|cpi)\b|"
    r"\b(?:inflation|cpi)\s+expectations?\b|"
    r"\bexpectations?\s+(?:for|of)\s+(?:inflation|cpi)\b",
    re.IGNORECASE,
)
# Disposable income and GNI are not GDP per capita. "Income per capita" is.
_NOT_GDP_PCAP_RE = re.compile(
    r"\b(?:disposable|household)\s+income\b|\bgni\b|\bgross\s+national\b",
    re.IGNORECASE,
)
# Flows and rates. A month of these is not the year's figure. Population
# is a stock the series counts once; "84 million in June" can still be it.
_WB_MONTH_NOT_THE_YEAR = frozenset({
    "NY.GDP.MKTP.CD", "NY.GDP.MKTP.KD.ZG", "NY.GDP.PCAP.CD",
    "FP.CPI.TOTL.ZG", "SL.UEM.TOTL.ZS",
})


def _year_token(text):
    found = re.search(r"20[0-3]\d", text or "")
    return found.group() if found else ""


def _leading_period_belongs(previous, own):
    """The clause before the comma is this figure's period.

    "In the fourth quarter of 2023, GDP was" is that quarter. "After the
    fourth quarter of 2022, GDP was $4.5 trillion in 2023" is 2023. "In
    the fourth quarter of 2023, full-year GDP was" names the year. "In
    June, GDP was $4.5 trillion in 2023" names 2023; "in June 2023, GDP
    was $4.5 trillion" names June.
    """
    if not previous:
        return False
    if re.search(r"%|[$€£]|trillion|billion|million", previous, re.IGNORECASE):
        return False
    if re.match(
            r"\s*(?:compared\s+(?:to|with)|versus|vs\.?|up\s+from|down\s+from)\b",
            previous, re.IGNORECASE):
        return False
    if _FULL_YEAR_RE.search(own or ""):
        return False
    quarter = _quarter_in(previous) is not None
    part = _PART_OF_YEAR_FIGURE_RE.search(previous) is not None
    month = _MONTH_NAME_RE.search(previous) is not None
    if not quarter and not part and not month:
        return False
    prev_year, own_year = _year_token(previous), _year_token(own)
    if prev_year and own_year and prev_year != own_year:
        return False
    if month and not quarter and not part and own_year and prev_year != own_year:
        return False
    return True


def _figure_clauses(text, figure):
    """The clause before this figure, and the figure's own clause.

    A comma, "and", "while", or a semicolon starts another figure. The same
    digits later in the sentence are not this one. (None, None) when the
    figure is not in the text. The clause before is None in the first clause.
    """
    text = text or ""
    figure = str(figure or "").strip()
    if not figure or figure not in text:
        return None, None
    at = text.find(figure)
    start, previous = 0, None
    end = len(text)
    for found in _CLAUSE_OPEN_RE.finditer(text):
        if found.start() < at:
            previous = text[start:found.start()]
            start = found.end()
            continue
        if found.start() >= at + len(figure):
            end = found.start()
            break
    return previous, text[start:end]


def _clause_after(text, figure):
    """The clause that starts after this figure, or "" when there is none."""
    text = text or ""
    figure = str(figure or "").strip()
    at = text.find(figure) if figure else -1
    if at < 0:
        return ""
    for found in _CLAUSE_OPEN_RE.finditer(text):
        if found.start() >= at + len(figure):
            nxt = found.end()
            later = _CLAUSE_OPEN_RE.search(text, nxt)
            end = later.start() if later else len(text)
            return text[nxt:end]
    return ""


def _figure_span(text, figure):
    """The clause of the figure this claim checks, or None if it is not placed.

    A leading clause that names this figure's period is kept with it.
    """
    previous, own = _figure_clauses(text, figure)
    if own is None:
        return None
    if _leading_period_belongs(previous, own):
        return previous + " " + own
    return own


# "compared with the fourth quarter of 2022" is the other period.
# The quarter this figure is for stays.
_COMPARISON_TAIL_RE = re.compile(
    r"\b(?:compared\s+(?:to|with)|versus|vs\.?|up\s+from|down\s+from)\b.*"
    r"|\bfrom\s+(?:the\s+)?(?:(?:first|second|third|fourth|1st|2nd|3rd|4th)[\s-]+)?"
    r"(?:quarter|Q[1-4])\b.*"
    r"|\bfrom\s+(?:the\s+)?(?:(?:first|second)[\s-]+half|"
    r"(?:first\s+)?(?:nine|six|three|9|6|3)[\s-]+months|"
    r"year[\s-]+to[\s-]+date|YTD|"
    r"(?:H[12]|[12]H)\s*['\u2019]?(?:20[0-3]\d|\d{2}))\b.*",
    re.IGNORECASE,
)


def _without_comparison_tail(clause, figure=""):
    """Drop a comparison that follows the figure. One before it still counts."""
    clause = clause or ""
    figure = str(figure or "").strip()
    at = clause.find(figure) if figure else -1
    if at < 0:
        return _COMPARISON_TAIL_RE.sub("", clause)
    head, tail = clause[:at + len(figure)], clause[at + len(figure):]
    return head + _COMPARISON_TAIL_RE.sub("", tail)


def _without_other_year_period(clause, figure):
    """A later period that names another year is not this figure.

    "GDP was $4.5 trillion in 2023 after the fourth quarter of 2022" is
    2023. "in the fourth quarter of 2023" has no separate year beside the
    quarter, so that quarter stays.
    """
    clause = clause or ""
    figure = str(figure or "").strip()
    at = clause.find(figure) if figure else -1
    if at < 0:
        return clause
    own = _own_year_after(clause, at + len(figure))
    if not own:
        return clause
    head, tail = clause[:at + len(figure)], clause[at + len(figure):]

    def drop(match):
        return "" if match.group(1) != own else match.group(0)

    return head + _OTHER_YEAR_PERIOD_RE.sub(drop, tail)


def _names_real_level(decomp):
    """The figure is a constant-price level. A rate never reaches this."""
    figure = _figure_text(decomp)
    text = decomp.sentence or ""
    own = _figure_span(text, figure) or ""
    if _REAL_LEVEL_RE.search(_without_comparison_tail(own, figure) or ""):
        return True
    nxt = _clause_after(text, figure)
    if not nxt or not _REAL_LEVEL_RE.search(nxt) or re.search(r"\d", nxt):
        return False
    rest = _REAL_LEVEL_RE.sub(" ", nxt)
    rest = re.sub(r"20[0-3]\d|[^A-Za-z]+", " ", rest)
    return not [word for word in rest.split() if len(word) > 3]


def _same_sentence_aside(text, figure):
    """The next clause when it continues this sentence.

    "5.5%, at current prices" is this figure. "5.5%. At current prices, ..."
    is the next sentence, and its basis is not this figure's.
    """
    text = text or ""
    figure = str(figure or "").strip()
    at = text.find(figure) if figure else -1
    if at < 0:
        return ""
    for found in _CLAUSE_OPEN_RE.finditer(text):
        if found.start() < at + len(figure):
            continue
        if found.start() > 0 and text[found.start() - 1] == ".":
            return ""
        nxt = found.end()
        later = _CLAUSE_OPEN_RE.search(text, nxt)
        end = later.start() if later else len(text)
        return text[nxt:end]
    return ""


def _basis_text(decomp):
    """The figure's clause, a leading basis with no number, and a following
    aside with no number. "In euro terms, GDP was" is euros. "not PPP" is not
    a basis. The next sentence is not this figure."""
    text = decomp.sentence or ""
    figure = _figure_text(decomp)
    previous, own = _figure_clauses(text, figure)
    parts = [own or ""]
    # "In euro terms, GDP was" is a basis. "Nominal wages rose, while GDP
    # grew" is another claim: it has a verb of its own.
    if (previous and not re.search(r"\d", previous)
            and not _ASSIGN_VERB_RE.search(previous)
            and not _CONTINUATION_VERB_RE.search(previous)):
        parts.append(previous)
    nxt = _same_sentence_aside(text, figure)
    if (nxt and not re.search(r"\d", nxt)
            and not re.search(r"\b(?:not|rather|instead|unlike)\b", nxt, re.I)):
        parts.append(nxt)
    return " ".join(parts)


def _names_ppp(decomp):
    """Purchasing-power GDP, or GDP in international dollars."""
    return _PPP_RE.search(_basis_text(decomp)) is not None


def _names_current_prices(decomp):
    """Nominal growth, including when the basis is a comma aside.

    "at market prices" is not this: real growth at market prices is the
    headline real series. A current-dollar level is not this either.
    """
    return _CURRENT_PRICES_RE.search(_basis_text(decomp)) is not None


def _signed_dollar_is_foreign(text, figure):
    """C$, A$, HK$, and Can$ are not US dollars. US$ and a bare $ are.

    The figure token starts at the dollar sign, so the prefix sits just
    before it. Can$ needs four characters. A letter inside a longer word
    ("Canada$") is not a prefix.
    """
    if not figure or not str(figure).startswith("$"):
        return False
    at = (text or "").find(figure)
    if at <= 0:
        return False
    head = text[max(0, at - 4):at]
    if _US_DOLLAR_PREFIX_RE.search(head):
        return False
    return _OTHER_DOLLAR_PREFIX_RE.search(head) is not None


def _wb_figure_is_not_dollars(decomp):
    """Current-dollar World Bank series. The unit on this figure is not dollars.

    A dollar figure that also prints a euro equivalent still is dollars.
    "euro area" is a place, not a currency. "pounds of" is weight.
    "in local currency" is the country's own unit. For the United States
    that unit is the dollar series.
    """
    text = decomp.sentence or ""
    figure = _figure_text(decomp)
    if not figure:
        return False
    if _signed_dollar_is_foreign(text, figure):
        return True
    blob = _EURO_AREA_RE.sub(" ", _basis_text(decomp))
    if _LOCAL_CURRENCY_RE.search(blob):
        country = _claim_country(decomp) or ""
        if _DOLLAR_HOME_RE.fullmatch(country) is None:
            return True
    if "$" in figure or "$" in str(decomp.raw_value or ""):
        return False
    code, _ = _claim_currency(ClaimDecomposition(sentence=text, raw_value=figure))
    if code != "USD":
        return True
    if _FOREIGN_CURRENCY_RE.search(blob):
        return True
    return _WB_OTHER_UNIT_RE.search(blob) is not None


_COMPONENT_LABEL_RE = re.compile(
    r"\b(?:food|energy|shelter|rent|services|goods|wage|producer|ppi|import|"
    r"export|medical|housing|median|trimmed|sticky|super-?core|"
    r"harmonis(?:ed|zed)|hicp|underlying|" + _PRICE_LINE + r")\b",
    re.IGNORECASE,
)
_LABEL_FILLER_WORDS = frozenset({
    "in", "the", "a", "an", "of", "for", "on", "category", "component",
    "index", "prices", "price", "measure", "basis", "terms", "sector", "rate",
})


def _component_of_headline_prices(text):
    """Food, energy, or services inflation is not the headline index.

    Only the words in this figure's clause count. "Food inflation was 4%,
    while headline inflation was 6.2%" still checks the headline figure.
    "Inflation was sticky" stays: sticky follows the series word.
    """
    text = text or ""
    if _COMPONENT_AFTER_SERIES_RE.search(text):
        return True
    for found in _HEADLINE_PRICE_RE.finditer(text):
        before = text[max(0, found.start() - 40):found.start()]
        if _COMPONENT_PRICE_RE.search(before):
            return True
        # "CPI-W" is the wage-earner index. "CPI was" is the headline.
        if re.match(r"[\s-]*w\b", text[found.end():found.end() + 6], re.IGNORECASE):
            return True
    return False


def _pure_component_clause(previous):
    """The clause is a component and nothing else.

    A published line of more than one word ("financial services") is
    that line. A leftover word ("financial services report") is not.
    """
    if not previous or re.search(r"\d", previous):
        return False
    if _ASSIGN_VERB_RE.search(previous) or _CONTINUATION_VERB_RE.search(previous):
        return False
    if not _COMPONENT_LABEL_RE.search(previous):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", previous)
    leftover = [
        word for word in words
        if len(word) > 3 and word.lower() not in _LABEL_FILLER_WORDS
        and not _COMPONENT_LABEL_RE.fullmatch(word)
    ]
    if not leftover:
        return True
    kept = [
        word for word in words
        if len(word) > 3 and word.lower() not in _LABEL_FILLER_WORDS
    ]
    return _COMPONENT_LABEL_RE.fullmatch(" ".join(kept)) is not None


def _leading_price_component(decomp):
    """A leading label names the component, and the country token follows.

    "In the apparel category, US inflation" is apparel. "and" splits a
    list, so the leftover word "energy" in "including food and energy"
    is not a label. A bare "Food, inflation" still reaches the series
    word through the merged text.
    """
    text = decomp.sentence or ""
    figure = _figure_text(decomp)
    previous, _own = _figure_clauses(text, figure)
    if not _pure_component_clause(previous):
        return False
    return re.search(
        r"\b(?:in|for|on|of|category|component|index|sector)\b",
        previous, re.IGNORECASE) is not None


def _inflation_text(decomp):
    """The figure's clause, plus a leading label that is only a component.

    "In the food category, inflation was" is food inflation. "After food
    shortages" is not: shortages is its own word. A previous clause with a
    verb is the other claim.
    """
    text = decomp.sentence or ""
    figure = _figure_text(decomp)
    previous, own = _figure_clauses(text, figure)
    own = own or text
    if not _pure_component_clause(previous):
        return own
    return f"{previous} {own}"


def _figure_own_clause(decomp):
    text = decomp.sentence or ""
    _, own = _figure_clauses(text, _figure_text(decomp))
    return own or text


def _price_clause_names_a_base(clause):
    """A basis clause, not another figure. A year by itself is allowed."""
    if not clause:
        return False
    if not (_PRICE_BASE_YEAR_RE.search(clause) or _AMBIGUOUS_PRICE_YEAR_RE.search(clause)):
        return False
    if _ASSIGN_VERB_RE.search(clause) or _CONTINUATION_VERB_RE.search(clause):
        return False
    return re.search(r"%|[$€£]|trillion|billion|million", clause, re.I) is None


def _names_other_price_year(decomp):
    """A constant-price year that is not this figure's year.

    "GDP at 2023 prices ... in 2023" is current prices. "in 2015 prices"
    with no other year, or beside 2023, is a different level. "on a 2015
    basis" and "reference year 2015" count only beside a different year:
    with no other year they can be the year of the figure.
    """
    text = decomp.sentence or ""
    figure = _figure_text(decomp)
    previous, own = _figure_clauses(text, figure)
    parts = [own or ""]
    if _price_clause_names_a_base(previous):
        parts.append(previous)
    nxt = _same_sentence_aside(text, figure)
    if (nxt and _price_clause_names_a_base(nxt)
            and not re.search(r"\b(?:not|rather|instead|unlike)\b", nxt, re.I)):
        parts.append(nxt)
    blob = " ".join(parts)
    found = _PRICE_BASE_YEAR_RE.search(blob)
    if found:
        base = next(group for group in found.groups() if group)
        remaining = re.findall(r"20[0-3]\d", _PRICE_BASE_YEAR_RE.sub(" ", text))
        if not remaining:
            return True
        return any(year != base for year in remaining)
    found = _AMBIGUOUS_PRICE_YEAR_RE.search(blob)
    if not found:
        return False
    base = next(group for group in found.groups() if group)
    return any(year != base for year in re.findall(r"20[0-3]\d", text))


def _names_prior_year_prices(decomp):
    """Last year's prices on this level. A comparison tail does not count."""
    text = decomp.sentence or ""
    figure = _figure_text(decomp)
    previous, own = _figure_clauses(text, figure)
    parts = [_without_comparison_tail(own or "", figure)]
    if (previous and not re.search(r"\d", previous)
            and not _ASSIGN_VERB_RE.search(previous)
            and not _CONTINUATION_VERB_RE.search(previous)):
        parts.append(previous)
    return _PRIOR_YEAR_PRICES_RE.search(" ".join(parts)) is not None


def _names_chain_volume(decomp):
    """A chain-linked level. The next sentence is not this figure."""
    return _CHAIN_VOLUME_RE.search(_basis_text(decomp) or "") is not None


def _not_the_national_product(decomp):
    """This clause's GDP is a sector, or a contribution to the total."""
    clause = _figure_own_clause(decomp)
    return bool(
        _SECTOR_ON_GDP_RE.search(clause)
        or _GDP_IN_SECTOR_RE.search(clause)
        or _CONTRIBUTION_TO_GDP_RE.search(clause)
    )


def _leading_is_only(previous, pattern):
    """The previous clause is this label and nothing else."""
    if not previous or re.search(r"\d", previous):
        return False
    if _ASSIGN_VERB_RE.search(previous) or _CONTINUATION_VERB_RE.search(previous):
        return False
    if re.search(r"\b(?:not|rather|instead|unlike)\b", previous, re.I):
        return False
    if pattern.search(previous) is None:
        return False
    rest = pattern.sub(" ", previous)
    rest = re.sub(r"20[0-3]\d|[^A-Za-z]+", " ", rest)
    return not [word for word in rest.split() if len(word) > 3]


def _basket_note_on_figure(clause):
    """The figure's clause takes a basket from the total, or is net of one.

    Words after that phrase have to be glue or a year. "in the report"
    and "from the total economy" stay. The figure's own verb stays.
    """
    if not clause:
        return False
    if re.search(r"\b(?:not|rather|instead|unlike)\b", clause, re.I):
        return False
    match = _FROM_THE_TOTAL_RE.search(clause) or _NET_OF_RE.search(clause)
    if not match:
        return False
    rest = re.sub(r"20[0-3]\d|[^A-Za-z]+", " ", clause[match.end():])
    return not [word for word in rest.split() if len(word) > 3]


def _basket_taken_from_the_total(clause):
    """The clause takes a basket from the total, or is net of a basket.

    A year may sit in the clause. A verb, a denial, or another content
    word means the clause is a different claim. "from the total economy",
    "net of tax", and "not net of oil" stay.
    """
    if not clause:
        return False
    if re.search(r"\b(?:not|rather|instead|unlike)\b", clause, re.I):
        return False
    if _ASSIGN_VERB_RE.search(clause) or _CONTINUATION_VERB_RE.search(clause):
        return False
    if (_FROM_THE_TOTAL_RE.search(clause) is None
            and _NET_OF_RE.search(clause) is None):
        return False
    rest = _NET_OF_RE.sub(" ", _FROM_THE_TOTAL_RE.sub(" ", clause))
    rest = re.sub(r"20[0-3]\d|[^A-Za-z]+", " ", rest)
    return not [word for word in rest.split() if len(word) > 3]


def _exclusion_before_figure(decomp):
    """A basket taken out of this figure is not the headline series.

    Before the figure, "excluding" can name anything. After the figure,
    only a basket word counts, in this clause or in the next clause of
    this sentence when that clause is the exclusion and nothing else.
    The next sentence is not this figure. "not excluding", "excluding
    nothing", "less than", and "ex-president" stay. A following clause
    that takes a basket from the total, or is "net of" a basket and
    nothing else, is the same exclusion. The same words in this
    figure's own clause count too. A year in that clause does not
    make it a different claim.
    """
    text = decomp.sentence or ""
    figure = _figure_text(decomp)
    previous, own = _figure_clauses(text, figure)
    at = (own or "").find(figure) if figure else -1
    if at > 0 and _EXCLUSION_RE.search(own[:at]):
        return True
    if own and _BASKET_EXCLUSION_RE.search(own):
        return True
    # "net of energy in the report" names another claim after the basket.
    # "net of energy was 4.1%" does not: the verb belongs to the figure.
    if _basket_note_on_figure(own):
        return True
    # "GDP was $X, excluding agriculture" is the basket. "up by $200
    # billion" and "excluding the effects of a strike" are not.
    nxt = _same_sentence_aside(text, figure)
    if _leading_is_only(nxt, _BASKET_EXCLUSION_RE):
        return True
    if _leading_is_only(nxt, _FROM_THE_TOTAL_RE) or _leading_is_only(nxt, _NET_OF_RE):
        return True
    # "net of oil in 2023" still names the basket. The year is not
    # another claim. "net of oil in the report" is.
    if _basket_taken_from_the_total(nxt) or _basket_taken_from_the_total(previous):
        return True
    if not previous or re.search(r"\d", previous):
        return False
    if _ASSIGN_VERB_RE.search(previous) or _CONTINUATION_VERB_RE.search(previous):
        return False
    if re.search(r"\b(?:not|rather|instead|unlike)\b", previous, re.I):
        return False
    # "Excluding agriculture, GDP was" can carry more words. "Agriculture
    # excluded," has to be the whole clause, or a later verb is the story.
    if _EXCLUSION_RE.search(previous):
        return True
    return _leading_is_only(previous, _BASKET_EXCLUSION_RE)


# A fiscal year on a national account is not the calendar year. "FY" and
# "fiscal" stay in the parser: a filing still uses them. This check is
# local to the national series.
_FISCAL_YEAR_RE = re.compile(
    r"\b(?:FY\s*|fiscal(?:[\s-]+year)?\s+)(20[1-3]\d)\b",
    re.IGNORECASE,
)
# The adjusted word has to name the unadjusted index. "the seasonally
# adjusted story is that inflation" is the headline. A figure and "at a"
# may sit between the index and the same words. GDP is the adjusted series
# and never reaches this pattern.
# "path of inflation", "trajectory of inflation", "reading of inflation",
# "version of inflation", and "print of inflation" name the adjusted
# index. "story", "before", and "revision" do not.
_SA_FILLER = (
    r"the|a|an|us|u\.s\.|german|germany'?s|headline|annual|yearly|"
    r"core|all|items|urban|consumer|rate|index|price|prices|path|trajectory|"
    r"reading|version|print|of"
)
_SA_TOUCH_RE = re.compile(
    r"(?<!not\s)\bseasonally[\s-]adjusted\b"
    r"(?:\s+(?:" + _SA_FILLER + r")){0,4}\s+"
    r"(?:inflation|cpi|consumer\s+prices)\b"
    r"|(?:inflation|cpi|consumer\s+prices)\b"
    r"(?:[^.;]{0,16}?\d[\d.]*%?)?"
    r"(?:\s+(?:at|on|in|a|an|the|was|were|is|are|of|rate|basis|annual)){0,6}\s+"
    r"(?<!not\s)\bseasonally[\s-]adjusted\b",
    re.IGNORECASE,
)
_SA_ONLY_RE = re.compile(r"(?<!not\s)\bseasonally[\s-]adjusted\b", re.IGNORECASE)
_NOT_SA_RE = re.compile(r"\bnot\s+seasonally[\s-]adjusted\b", re.IGNORECASE)
# A footnote that is only the adjusted reading. "story", "revision",
# "minutes", and "showed" are a different claim. PCE never reaches this.
_SA_NOTE_WORD = {
    "seasonally", "adjusted", "reading", "version", "print", "path",
    "trajectory", "the", "a", "an", "on", "in", "of", "at", "rate",
    "index", "us", "and", "or", "inflation", "cpi", "consumer",
    "prices", "price", "core", "headline",
}
_SA_NAME = {"reading", "version", "print", "path", "trajectory"}
# Bare hospital, information, hotels, gas, and prescription are ordinary
# words. They count only when they sit on the price word itself.
_ADJACENT_PRICE_LINE_RE = re.compile(
    r"\b(?:hospitals?|information|hotels?|gas|prescription)\s+"
    r"(?:inflation|cpi|consumer\s+prices)\b"
    r"|\b(?:inflation|cpi)\s+(?:for|on)\s+"
    r"(?:hospitals?|information|hotels?|gas|prescription)\b",
    re.IGNORECASE,
)
# The bare word is ordinary English. It is a price line only when the
# leading clause is a category, a component, an index, or a sector.
_BARE_PRICE_WORD_RE = re.compile(
    r"\b(?:hospitals?|information|hotels?|gas|prescription)\b",
    re.IGNORECASE,
)
_PRICE_CUE_RE = re.compile(
    r"\b(?:category|component|index|sector)\b",
    re.IGNORECASE,
)
# "for the hospital" has a word the adjacent line does not allow.
# "for the hospital report" and "the hospital's board" stay.
_PRICE_FOR_THE_RE = re.compile(
    r"\b(?:inflation|cpi|consumer\s+prices)\s+(?:for|on)\s+the\s+"
    r"(?:hospitals?|information|hotels?|gas|prescription)\b"
    r"(?!['\w]|\s+(?!(?:was|were|is|are|in|of|at|a|an|the|and|or|rate)\b)[A-Za-z])",
    re.IGNORECASE,
)
# The category may follow the figure. "in the hospital" has no cue.
# "of the census" and "of the economy" name something else.
_OWN_PRICE_CATEGORY_RE = re.compile(
    r"\b(?:in|for|on)\s+(?:the\s+)?"
    r"(?:hospitals?|information|hotels?|gas|prescription)\s+"
    r"(?:category|component|index|sector)\b",
    re.IGNORECASE,
)
_PRICE_CATEGORY_TAIL = {
    "in", "the", "a", "an", "of", "for", "on", "at", "and", "or",
    "was", "were", "is", "are", "rate",
}
# A footnote can name the line without repeating the price word.
# "for the hospital report" and "the hospital's board" stay.
_PRICE_ASIDE_FOR_RE = re.compile(
    r"\b(?:for|on)\s+the\s+"
    r"(?:hospitals?|information|hotels?|gas|prescription)\b"
    r"(?!['\w])",
    re.IGNORECASE,
)


def _plain_calendar_years(text):
    """Years in the text that are not inside a fiscal label."""
    spans = [(m.start(1), m.end(1)) for m in _FISCAL_YEAR_RE.finditer(text or "")]
    found = []
    for match in re.finditer(r"20[1-3]\d", text or ""):
        if any(start <= match.start() < end for start, end in spans):
            continue
        found.append(match.group())
    return found


def _clause_is_only_fiscal_year(clause):
    """The clause is a fiscal year and no other claim.

    The year is a digit, so the usual label test cannot run.
    "In the FY2023 report" still has a word of its own.
    """
    if not clause:
        return False
    if _ASSIGN_VERB_RE.search(clause) or _CONTINUATION_VERB_RE.search(clause):
        return False
    if re.search(r"\b(?:not|rather|instead|unlike)\b", clause, re.I):
        return False
    if _FISCAL_YEAR_RE.search(clause) is None:
        return False
    rest = _FISCAL_YEAR_RE.sub(" ", clause)
    rest = re.sub(r"[^A-Za-z]+", " ", rest)
    return not [word for word in rest.split() if len(word) > 3]


def _figure_year_is_fiscal(decomp):
    """This figure's year is a fiscal year, or the label left no calendar year.

    A fiscal crisis and one calendar year on the figure stay. "In FY2023,
    GDP was" is the fiscal year. "Under the FY2024 framework" is the same
    when the figure names no calendar year. Two calendar years do not
    confirm the label. One calendar year stays that year.
    """
    figure = _figure_text(decomp)
    previous, own = _figure_clauses(decomp.sentence or "", figure)
    if own is None:
        return False
    checked = _without_comparison_tail(own, figure)
    fiscal = {match.group(1) for match in _FISCAL_YEAR_RE.finditer(checked)}
    plain = _plain_calendar_years(checked)
    if len(set(plain)) > 1 and _FISCAL_YEAR_RE.search(decomp.time_period or ""):
        return True
    if plain:
        return False
    if fiscal:
        return True
    if _clause_is_only_fiscal_year(previous):
        return True
    return _FISCAL_YEAR_RE.search(decomp.time_period or "") is not None


def _calendar_year_beside_a_fiscal_label(decomp):
    """The calendar year on this figure, when a fiscal label stole the parser.

    One plain year, different from the fiscal year the parser took.
    Two years, or the same year, stay with the parser. The decomposition
    is not changed: a filing still reads the fiscal year.
    """
    period = _FISCAL_YEAR_RE.search(decomp.time_period or "")
    if not period:
        return ""
    figure = _figure_text(decomp)
    _previous, own = _figure_clauses(decomp.sentence or "", figure)
    checked = _without_comparison_tail(own or "", figure)
    plain = _plain_calendar_years(checked)
    if len(set(plain)) != 1 or plain[0] == period.group(1):
        return ""
    return plain[0]


def _seasonally_adjusted_inflation(decomp):
    """Seasonally adjusted inflation is not the unadjusted index.

    The phrase has to sit on this figure. GDP and unemployment are the
    adjusted series and never reach here. "not seasonally adjusted" stays.
    """
    figure = _figure_text(decomp)
    text = decomp.sentence or ""
    previous, own = _figure_clauses(text, figure)
    if _NOT_SA_RE.search(own or "") or _NOT_SA_RE.search(previous or ""):
        return False
    nxt = _same_sentence_aside(text, figure)
    if _NOT_SA_RE.search(nxt or ""):
        return False
    if own and _SA_TOUCH_RE.search(own):
        return True
    if _leading_is_only(previous, _SA_ONLY_RE):
        return True
    if nxt and _leading_is_only(nxt, _SA_ONLY_RE):
        return True
    return _sa_reading_note(previous) or _sa_reading_note(nxt)


def _sa_reading_note(clause):
    """The clause is only a seasonally adjusted reading, version, print,
    path, or trajectory.

    "the seasonally adjusted story" and "before the revision" stay.
    """
    if not clause or _NOT_SA_RE.search(clause):
        return False
    if _ASSIGN_VERB_RE.search(clause) or _CONTINUATION_VERB_RE.search(clause):
        return False
    if re.search(r"\b(?:not|rather|instead|unlike)\b", clause, re.I):
        return False
    if _SA_ONLY_RE.search(clause) is None:
        return False
    words = re.findall(r"[A-Za-z]+", clause)
    if not any(word.lower() in _SA_NAME for word in words):
        return False
    return not [
        word for word in words
        if len(word) > 3 and word.lower() not in _SA_NOTE_WORD
    ]


def _adjacent_price_line(decomp):
    """Hospital, information, hotel, gas, or prescription on the price word.

    "in the hospital" is a place. "The information was that" is a clause.
    The words count only in this figure's own clause.
    """
    own = _figure_own_clause(decomp) or ""
    return _ADJACENT_PRICE_LINE_RE.search(own) is not None


def _bare_price_category(decomp):
    """The leading clause is only a hospital, information, hotel, gas,
    or prescription category.

    "In the hospital" is a place. "of the census" is another subject.
    The cue is category, component, index, or sector.
    """
    figure = _figure_text(decomp)
    previous, _own = _figure_clauses(decomp.sentence or "", figure)
    if not previous or re.search(r"\d", previous):
        return False
    if _ASSIGN_VERB_RE.search(previous) or _CONTINUATION_VERB_RE.search(previous):
        return False
    if re.search(r"\b(?:not|rather|instead|unlike)\b", previous, re.I):
        return False
    if _BARE_PRICE_WORD_RE.search(previous) is None or _PRICE_CUE_RE.search(previous) is None:
        return False
    rest = _PRICE_CUE_RE.sub(" ", _BARE_PRICE_WORD_RE.sub(" ", previous))
    rest = re.sub(r"[^A-Za-z]+", " ", rest)
    filler = {"in", "the", "a", "an", "of", "for", "on"}
    return not [word for word in rest.split() if len(word) > 3 and word.lower() not in filler]


def _price_line_aside(clause):
    """The clause is only "for the hospital", or the same line.

    "for the hospital report" and "the hospital's board" stay.
    """
    if not clause:
        return False
    if re.search(r"\b(?:not|rather|instead|unlike)\b", clause, re.I):
        return False
    if _ASSIGN_VERB_RE.search(clause) or _CONTINUATION_VERB_RE.search(clause):
        return False
    if _PRICE_ASIDE_FOR_RE.search(clause) is None:
        return False
    rest = _PRICE_ASIDE_FOR_RE.sub(" ", clause)
    rest = re.sub(r"20[0-3]\d|[^A-Za-z]+", " ", rest)
    return not [
        word for word in rest.split()
        if len(word) > 3 and word.lower() not in _PRICE_CATEGORY_TAIL
    ]


def _price_category_aside(clause):
    """The clause is only a hospital, information, hotel, gas, or
    prescription category. A year may sit in it.

    "of the census" and "of the economy" stay. "in the hospital" has
    no category word, so it stays.
    """
    if not clause:
        return False
    if re.search(r"\b(?:not|rather|instead|unlike)\b", clause, re.I):
        return False
    if _ASSIGN_VERB_RE.search(clause) or _CONTINUATION_VERB_RE.search(clause):
        return False
    match = _OWN_PRICE_CATEGORY_RE.search(clause)
    if not match:
        return False
    def content(text):
        return [
            word for word in re.sub(r"20[0-3]\d|[^A-Za-z]+", " ", text).split()
            if len(word) > 3 and word.lower() not in _PRICE_CATEGORY_TAIL
        ]
    return not content(clause[:match.start()]) and not content(clause[match.end():])


def _price_for_the_line(decomp):
    """Inflation for the hospital, in this figure's clause or the
    footnote that is only that line.

    "for the hospital report" and "the hospital's board" stay.
    """
    own = _figure_own_clause(decomp) or ""
    if _PRICE_FOR_THE_RE.search(own) is not None:
        return True
    figure = _figure_text(decomp)
    text = decomp.sentence or ""
    previous, _own = _figure_clauses(text, figure)
    nxt = _same_sentence_aside(text, figure)
    return _price_line_aside(previous) or _price_line_aside(nxt)


def _price_category_on_figure(decomp):
    """A hospital, information, hotel, gas, or prescription category
    on this figure.

    The category may follow the number, lead the sentence, or be the
    whole footnote. "in the hospital" is a place. "of the census" and
    "of the economy" stay.
    """
    own = _figure_own_clause(decomp) or ""
    match = _OWN_PRICE_CATEGORY_RE.search(own)
    if match:
        tail = re.sub(r"20[0-3]\d|[^A-Za-z]+", " ", own[match.end():])
        if not [
            word for word in tail.split()
            if len(word) > 3 and word.lower() not in _PRICE_CATEGORY_TAIL
        ]:
            return True
    figure = _figure_text(decomp)
    text = decomp.sentence or ""
    previous, _own = _figure_clauses(text, figure)
    nxt = _same_sentence_aside(text, figure)
    return _price_category_aside(previous) or _price_category_aside(nxt)


def _subject_side(text):
    """A name, the series, and one trailing verb. Not another event."""
    text = re.sub(r"'s\b", "", text or "")
    words = re.findall(r"[A-Za-z0-9]+", text)
    if words and words[-1].lower() in _SPAN_TRAIL_VERB:
        words = words[:-1]
    for word in words:
        if word.lower() in _SPAN_FILLER or re.fullmatch(r"20[0-3]\d", word):
            continue
        if word[:1].isupper() or len(word) == 1:
            continue
        return False
    return True


def _period_on_this_figure(decomp):
    """So far this year, the past four quarters, or a monthly rate.

    The phrase counts after the figure, or before it when the words on
    both sides are only the subject. A leading clause counts when it
    says nothing else. "The story so far" and "the ministry said" stay.
    "full-year" on this figure stays.
    """
    text = decomp.sentence or ""
    figure = _figure_text(decomp)
    previous, own = _figure_clauses(text, figure)
    if own and figure and figure in own:
        at = own.find(figure)
        if _SPAN_ON_FIGURE_RE.search(own[at + len(figure):]):
            return True
        before = own[:at]
        for found in _SPAN_ON_FIGURE_RE.finditer(before):
            if (_subject_side(before[:found.start()])
                    and _subject_side(before[found.end():])):
                return True
    if _FULL_YEAR_RE.search(own or "") or _SPAN_EVENT_VERB_RE.search(own or ""):
        return False
    return _leading_is_only(previous, _SPAN_ON_FIGURE_RE)


def _level_is_a_change(decomp):
    """A currency change is not the level it changed from.

    "Not seasonally adjusted" on a currency level is the other series.
    A rate does not reach this: the CPI series is already unadjusted.
    The comma footnote stays, and so does "the ministry said".
    """
    if getattr(decomp, "unit", "") != "currency":
        return False
    text = decomp.sentence or ""
    figure = _figure_text(decomp)
    previous, own = _figure_clauses(text, figure)
    if not own or not figure or figure not in own:
        return False
    at = own.find(figure)
    if _LEVEL_CHANGE_RE.search(own[:at]):
        return True
    if _CHANGE_NOUN_AFTER_RE.match(own[at + len(figure):]):
        return True
    if _NSA_RE.search(own):
        return True
    if _SPAN_EVENT_VERB_RE.search(own):
        return False
    return _leading_is_only(previous, _NSA_RE)


def _figure_is_in_points(decomp):
    """The unit on this figure is points. A later point change is not."""
    figure = _figure_text(decomp)
    text = decomp.sentence or ""
    at = text.find(figure) if figure else -1
    if at < 0:
        return False
    return _POINTS_AFTER_RE.match(text[at + len(figure):]) is not None


def _output_per_job(decomp):
    """Per worker, per hour, or per job. Per person stays."""
    text = decomp.sentence or ""
    figure = _figure_text(decomp)
    previous, own = _figure_clauses(text, figure)
    if own and _PER_JOB_RE.search(own):
        return True
    return _leading_is_only(previous, _PER_JOB_RE)


def _calendar_or_working_day(decomp):
    """A calendar-adjusted or working-day-adjusted total.

    "and" splits a clause, so "Calendar and seasonally adjusted" arrives
    as the word calendar and then "seasonally adjusted". Bare "seasonally
    adjusted" on this total is the headline and stays. The unadjusted
    price index checks those words on its own.
    """
    text = decomp.sentence or ""
    figure = _figure_text(decomp)
    previous, own = _figure_clauses(text, figure)
    if own and _WORKING_SPAN_RE.search(own):
        return True
    if _leading_is_only(previous, _WORKING_SPAN_RE):
        return True
    if not previous or not own or re.search(r"\d", previous):
        return False
    # "trading" is also a price verb, so a verb check cannot run first.
    # Only an exact label, then "seasonally adjusted", counts.
    words = [word.lower() for word in re.findall(r"[A-Za-z]+", previous)]
    if words in (["calendar"], ["working", "day"], ["trading", "day"]):
        return re.match(
            r"\s*seasonally\s+adjusted\b", own, re.IGNORECASE) is not None
    return False


def _narrow_unemployment_at(text, start, end):
    """This mention of unemployment is not the total rate."""
    before = text[max(0, start - 20):start]
    after = text[end:end + 24]
    cut = _CLAUSE_OPEN_RE.search(after)
    if cut:
        after = after[:cut.start()]
    if _LABOR_BEFORE_RE.search(before) or _LABOR_AFTER_RE.search(after):
        return True
    # The group may follow "rate" or the figure. The loose window stays
    # short so "women" later in the sentence is not this rate. "White
    # House" and "Asian crisis" are not the group.
    tight_before = text[max(0, start - 40):start]
    tight_after = text[end:end + 48]
    cut = _CLAUSE_OPEN_RE.search(tight_after)
    if cut:
        tight_after = tight_after[:cut.start()]
    if (_LABOR_TIGHT_BEFORE_RE.search(tight_before)
            or _LABOR_TIGHT_AFTER_RE.search(tight_after)):
        return True
    # The diploma sits past the short window. The next clause is not this rate.
    school = text[end:]
    cut = _CLAUSE_OPEN_RE.search(school)
    if cut:
        school = school[:cut.start()]
    if _LABOR_SCHOOL_RE.search(school):
        return True
    window = text[max(0, start - 16):end + 16]
    return re.search(r"\bclaims\b", window, re.IGNORECASE) is not None


def _narrow_unemployment(clause):
    clause = clause or ""
    return any(
        _narrow_unemployment_at(clause, found.start(), found.end())
        for found in re.finditer(
            r"\b(?:unemployment|jobless)\b", clause, re.IGNORECASE)
    )


def _figure_is_part_of_a_year(decomp, month_is_its_period=False, month_blocks=False):
    """The figure being checked is not a whole year.

    World Bank series here are annual. FRED, with no month named, is the
    year's average. A quarter, a half, nine months, a year to date, or an
    annualized rate is a different observation. A named month is the
    period FRED asks for. It is not the year's GDP or the year's inflation.
    "Q4 2023" on a later figure is that figure's quarter.
    """
    figure = _figure_text(decomp)
    own = _figure_span(decomp.sentence, figure)
    if own is None:
        return False
    clause = _without_other_year_period(_without_comparison_tail(own, figure), figure)
    quarter = _quarter_in(clause) is not None or bool(_THREE_MONTHS_RE.search(clause))
    part = _PART_OF_YEAR_FIGURE_RE.search(clause) is not None
    # SAAR is the run rate. "Saar" is a place, so the letters keep their case.
    # Lower case "saar" is the same rate. "Saar" still is not.
    if re.search(r"\b(?:SAAR|saar)\b", clause):
        part = True
    # "so far this year" and "over the past four quarters" are not the
    # year when they sit on this figure. "The story so far" stays.
    if _period_on_this_figure(decomp):
        part = True
    # "4.1% in December" is that month. "three months ended December" and
    # "the first half, in June" are not December's figure.
    if (month_is_its_period and _MONTH_NAME_RE.search(clause)
            and not quarter and not part):
        return False
    if quarter or part:
        return True
    return bool(month_blocks and _MONTH_NAME_RE.search(clause))


_GDP_SHARE_RE = re.compile(
    r'(?:%|percent)\s+of\s+(?:the\s+)?gdp|\bto[-\s]gdp\b|/\s*gdp\b|'
    r'\b(?:debt|deficit)\b', re.IGNORECASE)


def _is_real_growth(sentence, raw_value, clause, _depth=0):
    # "Government debt, % of GDP: 98%" is a share, not growth (review, 2026-11-27).
    if _GDP_SHARE_RE.search(clause or sentence or ""):
        return False
    head = _growth_head(sentence, raw_value).lower()
    # A quarter, or "nominal", on the other figure is not this rate.
    # "5.5% in 2022 and 5.1% in the fourth quarter" is still 2022's growth.
    own = _figure_span(sentence, raw_value)
    checked = _without_comparison_tail(own, raw_value) if own is not None else clause
    checked = _without_other_year_period(checked or "", raw_value)
    if _NOT_REAL_GROWTH_RE.search((checked or "").lower()):
        return False
    if _REAL_GROWTH_RE.search(head):
        return True
    # "Its GDP was $335 billion in 2023, and growth was nearly flat at 0.2%":
    # growth that nothing qualifies, in a sentence about GDP.
    # "Economic growth was 10.1%" names the economy (v22). Bare "Growth was
    # 2.1%" stays unread unless the sentence is about GDP: a pinned choice
    # (tests/test_gdp_growth.py), since bare growth can be anything's.
    if re.search(r'\b(?:economic|output)\s+growth\b', head):
        return True
    # "Grenada grew 6.4% in 2015", "Eswatini grew only 0.1%": a country that
    # grows or shrinks is its economy. Only adverbs may stand between the verb
    # and the figure, so "Kenya grew its exports 8%" is not (2026-11-27).
    if _country_grew(sentence, raw_value):
        return True
    if (_BARE_GROWTH_RE.search(head)
            and re.search(r'\b(?:gdp|economy)\b', (sentence or "").lower())):
        return True
    return _continues_real_growth(sentence, raw_value, head, _depth)


# "Real GDP grew 7.4% in 2019, slowed to 2.9% in 2020, and bounced back to
# 8.5% in 2022": a bare change verb with no measure of its own continues the
# rate before it in the sentence (2026-11-27, the site's own Vietnam example).
_CONTINUING_VERB_RE = re.compile(
    r'\b(?:slowed|eased|cooled|picked\s+up|bounced\s+back|rebounded|recovered|'
    r'accelerated|rose|fell|dropped|climbed|jumped|dipped|edged\s+(?:up|down)|'
    r'returned|grew|expanded|contracted|shrank)\b[^.;%]{0,20}$', re.IGNORECASE)
_OWN_MEASURE_RE = re.compile(
    r'\b(?:inflation|prices?|cpi|unemploy\w*|jobless|debt|deficit|exports?|imports?|'
    r'revenue|sales|population|wages?|income|earnings|profit|rates?|yield|share)\b',
    re.IGNORECASE)


def _country_grew(sentence, raw_value):
    raw = str(raw_value or "").strip()
    at = (sentence or "").find(raw) if raw else -1
    if at <= 0:
        return False
    m = _COUNTRY_GREW_RE.search(sentence[max(0, at - 80):at])
    return bool(m and _COUNTRY_NAMES_RE.fullmatch(m.group(1)))


_COUNTRY_GREW_RE = re.compile(
    r"([A-Z][\w'.-]*(?:\s+(?:and\s+)?[A-Z][\w'.-]*){0,3})(?:'s\s+economy)?\s+"
    r"(?:grew|expanded|contracted|shrank)"
    r"(?:\s+(?:by|only|just|about|around|roughly|nearly|a|an|modest(?:ly)?|strongly|solidly|briskly))*"
    r"\s*$")


_CHAIN_LIMIT = 4  # links walked back; a pasted wall of rates stays linear
_CHAIN_FILLER_RE = re.compile(
    r'(?i)\b(?:in|by|and|then|but|before|after|it|its|the|real|economy|output|growth|gdp|'
    r'later|again|only|just|further|sharply|briefly|year|that|this|(?:19|20)\d\d)\b|[\s,;()*-]+')


def _continues_real_growth(sentence, raw_value, head, depth=0):
    if depth >= _CHAIN_LIMIT:
        return False
    sentence = sentence or ""
    raw = str(raw_value or "").strip()
    at = sentence.find(raw) if raw else -1
    if at <= 0:
        return False
    window = sentence[max(0, at - 200):at]
    earlier = list(re.finditer(r'-?\d[\d.,]*\s*%', window))
    if not earlier:
        return False
    # "3.9% in 2019 and 4.1% in 2024", "3.2% in 2023, but only 0.8% in 2024":
    # nothing but filler between two rates is the same series, verb or not.
    if not re.sub(_CHAIN_FILLER_RE, " ", window[earlier[-1].end():]).strip():
        prev = earlier[-1].group(0).replace(" ", "")
        return _is_real_growth(sentence, prev, _clause_holding(sentence, prev), depth + 1)
    words = (head or "").replace(raw, "") if raw else (head or "")
    if not _CONTINUING_VERB_RE.search(words.rstrip()) or _OWN_MEASURE_RE.search(words):
        return False
    # Only filler may sit between the rate before and this one's verb: "in
    # 2019, slowed to". A noun of its own is another measure, whatever it is:
    # "and investment rose 8%" is not GDP growth (review 2026-11-27; a list of
    # other measures could never be complete, so this is an allow-list).
    between = window[earlier[-1].end():]
    verb = _CONTINUING_VERB_RE.search(between.rstrip())
    lead = between[:verb.start()] if verb else between
    if re.sub(_CHAIN_FILLER_RE, " ", lead).strip():
        return False
    prev = earlier[-1].group(0).replace(" ", "")
    return _is_real_growth(sentence, prev, _clause_holding(sentence, prev), depth + 1)


# "the growth in tourism", "growth of consumption": that thing's growth, not
# the economy's (review 2026-11-27). "growth in 2019" names only a year.
_GROWTH_OF_THING_RE = re.compile(
    r'\bgrowth\s+(?:of|in)\s+(?!(?:19|20)\d\d\b|the\s+(?:economy|gdp)\b|gdp\b|real\b)[a-z]')

# "growth was", "and growth": not "revenue growth" or "population growth".
_BARE_GROWTH_RE = re.compile(
    r'(?:^|\b(?:and|but|while|its|the|annual|overall|economic)\s+|[,;:*]\s*)growth\b')


def _growth_sign(sentence, raw_value):
    """-1 when the words say the economy shrank: "contracted 2.0%", "after
    shrinking 0.6%", "and another 0.2%" after "shrank 0.3%", or "-0.4%"."""
    raw = str(raw_value or "").strip()
    if raw.startswith(("-", "\u2212")):
        return 1
    if _minus_before(sentence, raw):
        return -1
    head, leads = _growth_reading(sentence, raw_value)
    # The figure's own clause decides: in "growth was -1.8% in 2020, a
    # contraction; and output expanded 1.0% in 2024" the contraction is 2020's
    # (v22 Israel and Syria, refuted with the sign of the clause before).
    # The direction word nearest the figure is its own: "grew 1.1% in 2024
    # after shrinking 0.6%" makes the 0.6% a contraction.
    token = re.search(r'(?<![\d.,])' + re.escape(raw) + r'(?!\d)', sentence) if raw else None
    at = token.start() if token else -1
    own = re.split(r"[;:]", sentence[:at])[-1] if at >= 0 else ""
    words = list(re.finditer(
        r'\b(?:expanded|expanding|grew|growing|rose|rising|increased|rebounded|recovered|'
        r'contract\w*|shr[aiu]nk\w*|fell|falling|declin\w*|dropp\w*)\b', own, re.IGNORECASE))
    if words and re.match(r'(?:expand|grew|grow|rose|rising|increas|rebound|recover)',
                          words[-1].group(0), re.IGNORECASE):
        return 1
    # "then shrank 2%", "and fell 0.3%": the nearest word is a contraction.
    # "growth fell to 0.2%" is slower growth, so a fall on "growth" is not.
    if words and not re.search(r'\bgrowth\s+(?:\w+\s+){0,2}$',
                               own[:words[-1].start()], re.IGNORECASE):
        return -1
    for lead in leads:
        if re.search(r'\b(?:shrinking|contracting|falling)\b', lead, re.IGNORECASE):
            return -1
        if re.search(r'\b(?:growing|expanding|rising)\b|\+', lead, re.IGNORECASE):
            return 1
    return -1 if _CONTRACTION_RE.search(head.rsplit(";", 1)[-1].lower()) else 1


def _minus_before(sentence, raw):
    """"-0.4%" read as "0.4%": the sign is still in the text."""
    raw = str(raw or "").strip()
    # The minus touches the number. "growth - 2.0%" is a label dash and
    # "2.1% - 3.4%" a range (fresh-eyes review, 2026-11-27).
    return bool(raw) and bool(re.search(
        r'(?<![\w.%])[-\u2212]' + re.escape(raw), sentence or ""))


# A year's real growth: "GDP grew 5.3%", "real growth slowed to 0.2%", "the
# economy contracted 2.0%". Not per head, not nominal, not a quarter's.
_REAL_GROWTH_RE = re.compile(
    r'\breal\s+(?:gdp\s+)?growth\b|'
    r'\b(?:gdp|economy|economic|output)\b[^.;]{0,40}?\b(?:grew|grow(?:s|th|ing)?|expan(?:ded|ds|sion)|'
    r'contract(?:ed|s|ion)|shr[au]nk|slowed|rebounded|increased|rose|fell|declined|dropped)\b|'
    r'\b(?:grew|growth|expanded|contracted|shrank)\b[^.;]{0,25}?\b(?:gdp|economy)\b|'
    r'\bgdp\s*:?\s*[-+\u2212]?\s*\d[\d.]*\s?%',
)
_NOT_REAL_GROWTH_RE = re.compile(
    # A sector's growth is not the economy's: "growth in agriculture ... 3.6%".
    r'\b(?:agricultur\w*|forestry|fisher\w*|manufactur\w*|industr\w*|construction|'
    r'mining|services?\s+sector|sector\w*|retail|tourism|output\s+of)\b|'
    r'\bper\s+(?:capita|head|person)\b|\bnominal\b|'
    r'\b(?:at|in)\s+current\s+prices\b|'
    r'\bpurchasing[\s-]power(?:\s+parity)?\b|\bppp\b|'
    r'\bquarter(?:ly)?\b|\bq[1-4]\b|'
    r'\bannuali[sz]ed\b|\bmonth\b|\bexports?\b|\bimports?\b|\bforecasts?\b|\bprojected\b|'
    r'\bdeflator\b|\bat\s+an\s+annual\s+rate\b|'
    r'\bpotential\s+(?:gdp|growth|output)\b|'
    r'\b(?:at\s+)?basic\s+prices\b|\bfactor\s+cost\b',
)
# "contracted 2.0%" and "GDP fell 2.0%" are growth of -2.0%; "growth fell to
# 0.2%" is still growth.
_CONTRACTION_RE = re.compile(
    r'\b(?:contract(?:ed|s|ion)|shr[au]nk|shrinks?)\b|'
    r'^(?!.*\bgrowth\b).*\b(?:fell|declined|dropped)\b')


def _clause_holding(sentence, raw_value):
    """The clause of the sentence that holds this figure."""
    raw = str(raw_value or "").strip()
    sentence = sentence or ""
    if not raw or raw not in sentence:
        return sentence
    for clause in _CLAUSE_BREAK_RE.split(sentence):
        if raw in clause:
            return clause.strip()
    return sentence


def _place_key(name):
    """A country name as a lookup key: lower case, accents and a leading
    "the" dropped ("Côte D'Ivoire" from title-casing, "The Bahamas")."""
    import unicodedata
    key = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"^the\s+", "", key.strip().lower())


def _same_place(a, b):
    """Two names for one country: equal, or the same World Bank code
    ("Türkiye" and "Turkey"). Never fetches; the World Bank path has loaded
    the codes by the time a refutation is weighed."""
    if a == b:
        return True
    def code(name):
        key = _place_key(name)
        return (_WB_COUNTRY_ALIASES.get((name or "").lower()) or _WB_COUNTRY_ALIASES.get(key)
                or _WB_COUNTRY_CODES.get(key, ""))
    ca = code(a)
    return bool(ca) and ca == code(b)


def _only_place(named, country):
    """Every name in the set is this country."""
    return bool(named) and all(_same_place(n, country) for n in named)


def _wb_country_code(country):
    """ISO2 code for a country, from the World Bank itself.

    This used to come from restcountries.com. When that retired v1-v4,
    every World Bank check silently returned no_data with it.
    """
    raw, name = country.lower(), _place_key(country)
    if raw in _WB_COUNTRY_ALIASES or name in _WB_COUNTRY_ALIASES:
        return _WB_COUNTRY_ALIASES.get(raw) or _WB_COUNTRY_ALIASES[name]
    if not _WB_COUNTRY_CODES:
        listing = _fetch_json(
            "https://api.worldbank.org/v2/country?format=json&per_page=400"
        )
        if not listing or len(listing) < 2 or not listing[1]:
            return ""
        for row in listing[1]:
            if row.get("iso2Code") and row.get("name"):
                # "Egypt, Arab Rep." is also reachable as "egypt".
                full = _place_key(row["name"])
                _WB_COUNTRY_CODES[full] = row["iso2Code"]
                _WB_COUNTRY_CODES.setdefault(
                    full.split(",")[0], row["iso2Code"]
                )
    return _WB_COUNTRY_CODES.get(name, "")


_SUBNATIONAL_RE = re.compile(
    r"\b(?:city|cities|metro(?:politan)?|urban|capital|province|provincial|state|"
    r"county|region(?:al)?|municipal(?:ity)?|district|town|island)\b", re.I)


def _subnational(decomp):
    """The figure's own words name a place smaller than a country."""
    words = _clause_of(decomp)
    return bool(_SUBNATIONAL_RE.search(words))


# What a figure's own words say when it is this World Bank indicator.
# A tick needs them too. Real growth is the exception: its selector already
# walked back to the words, and a later rate in the same sentence does not
# repeat them.
_WB_INDICATOR_WORDS = {
    "SP.POP.TOTL": r"popul|people|inhabitants|residents|citizens",
    "NY.GDP.MKTP.CD": r"\bgdp\b|gross domestic|economy|output",
    "NY.GDP.PCAP.CD": r"per\s+(?:capita|head|person)|\bgdp\b|income",
    # "slowed" and "grew" carry growth in a chain ("grew 7.4%, slowed to 2.9%").
    # "rebound" and "recovered" do not: inflation clauses use them too ("rose
    # 2.5% as activity recovered"), and the gate lost two confirmations.
    "NY.GDP.MKTP.KD.ZG": r"grow|grew|growth|expan|contract|shr[iu]nk|slowed|\bgdp\b|economy",
    "FP.CPI.TOTL.ZG": r"inflation|prices|\bcpi\b|consumer price",
    "SL.UEM.TOTL.ZS": r"unemploy|jobless",
    "SP.DYN.LE00.IN": r"life\s+expectancy|lifespan|live",
    "NE.EXP.GNFS.ZS": r"export",
    "AG.SRF.TOTL.K2": r"area|square|km|sq\b|size",
    "SP.URB.TOTL.IN.ZS": r"urban|cities|towns",
    "SI.POV.DDAY": r"poverty|poor",
    "IT.NET.USER.ZS": r"internet|online",
    "SH.DYN.MORT": r"mortality|deaths|die",
    "SE.ADT.LITR.ZS": r"litera",
    "EN.ATM.CO2E.PC": r"co2|carbon|emission",
    "EG.ELC.ACCS.ZS": r"electric",
}


# Other measures a sentence about a country may name beside an indicator.
_WB_OTHER_MEASURES = r"median\s+age|fertility|birth|death\s+rate|density|literacy|debt|deficit|reserves|interest\s+rate"

# The same sectors whose growth is not the economy's growth. Their output
# is not the size of the economy either. "economic output" still is: it
# names the economy, and the word "output" stays in the GDP list.
_SECTOR_OUTPUT_RE = re.compile(
    r"\b(?:agricultur\w*|forestry|fisher\w*|manufactur\w*|industr\w*|construction|"
    r"mining|services?\s+sector|sector\w*|retail|tourism)\b",
    re.IGNORECASE,
)
_NATIONAL_ECONOMY_RE = re.compile(
    r"\bgdp\b|gross domestic|\beconom",
    re.IGNORECASE,
)


def _wb_series_unbound(decomp, indicator_id, country):
    """The figure is not this country series, so the number is not compared.

    Checked before a tick. A city, a different measure, or a different
    subject can share the country's digits. That is not a match.
    Every indicator with a word list is held to those words. The urban
    share is the one series the word "city" names, so that word does not
    throw it out.
    """
    if indicator_id not in _WB_INDICATOR_WORDS:
        return False
    if indicator_id != "SP.URB.TOTL.IN.ZS" and _subnational(decomp):
        return True
    subject = decomp.subject or ""
    if (subject and not _COUNTRY_NAMES_RE.fullmatch(subject)
            and not _COUNTRY_ABBREV_RE.fullmatch(subject)
            and country.lower() not in subject.lower()):
        return True
    if indicator_id == "NY.GDP.MKTP.CD" and decomp.unit not in ("currency", ""):
        return True
    if indicator_id == "NY.GDP.MKTP.CD" and _sector_output(decomp):
        return True
    if indicator_id == "NY.GDP.MKTP.KD.ZG" and decomp.unit not in ("percent", ""):
        return True
    # "Real GDP grew 11.4% in 2021, then 5.5% in 2022": the later rate's
    # own clause is only the rate and the year. The growth selector already
    # walked back through the filler to the words that name the series.
    # Requiring those words again in the later clause drops the true confirms.
    # A later clause that names a different measure never reaches this series.
    if indicator_id == "NY.GDP.MKTP.KD.ZG":
        return False
    return not _names_indicator(decomp, indicator_id)


def _sector_output(decomp):
    """A sector's output shares the word, and sometimes the digits, of GDP."""
    clause = _clause_of(decomp)
    if _NATIONAL_ECONOMY_RE.search(clause):
        return False
    return bool(_SECTOR_OUTPUT_RE.search(clause))


def _georgia_unresolved(decomp, country):
    """Bare Georgia is a US state and a country. Both have these figures."""
    if (country or "").lower() != "georgia":
        return False
    text = f"{decomp.sentence or ''} {decomp.subject or ''}"
    return _GEORGIA_COUNTRY_RE.search(text) is None


def _names_indicator(decomp, indicator_id):
    """The figure's own clause names this indicator; or, when it names none, its
    sentence names this indicator and no other measure ("Real GDP grew 5.05% in
    2023 after a very strong 8.0% in 2022" is all growth)."""
    pattern = _WB_INDICATOR_WORDS.get(indicator_id)
    if not pattern:
        return True  # an indicator without a word list keeps its own guards
    others = [p for i, p in _WB_INDICATOR_WORDS.items() if i != indicator_id] + [_WB_OTHER_MEASURES]
    return _names_measure(decomp, pattern, others)


def _names_measure(decomp, pattern, others):
    """The rule every refuting source shares: the figure's clause names this
    measure and no other; or names none, in a sentence about this measure alone."""
    clause = _clause_of(decomp)
    if re.search(pattern, clause, re.I):
        return True
    if any(re.search(p, clause, re.I) for p in others):
        return False  # the clause names another measure
    sentence = decomp.sentence or ""
    return bool(re.search(pattern, sentence, re.I)) and not any(
        re.search(p, sentence, re.I) for p in others)


# A new clause: a comma before a word, a conjunction, a semicolon, or a new
# sentence. A comma inside a number ("1,451") has no space after it, so it stays.
_CLAUSE_OPEN_RE = re.compile(
    r", (?=[A-Za-z])|\b(?:while|whereas|but|and)\b|; |(?<=\.)\s+(?=[A-Z])",
    re.IGNORECASE,
)
# A verb that gives the figure to the noun in front of it. "fell", "averaged"
# and "peaked" are not here: those continue the series already named.
_ASSIGN_VERB_RE = re.compile(
    r"\b(?:was|were|is|are|came|total(?:ed|led)|stood|reached|hit|numbered|"
    r"amounted|registered|posted|printed|clocked|counted|ran|sat)\b",
    re.IGNORECASE,
)
# "peaked at 9.1%", "topping out at 4.94%": the verb carries the series.
# "the import bill of $27.7 trillion" does not.
_ASSIGN_MARK_RE = re.compile(r"\b(?:at|of)\b|:", re.IGNORECASE)
_CONTINUATION_VERB_RE = re.compile(
    r"(?:peaked|peaking|topped|topping|bottomed|bottoming|fell|falling|"
    r"rose|rising|grew|growing|averaged|averaging|slowed|slowing|"
    r"dropped|dropping|declined|declining|increased|increasing|"
    r"ended|ending|closed|closing|finished|finishing|climbed|climbing|"
    r"eased|easing|slipped|hovering|trading)",
    re.IGNORECASE,
)
_MARK_PARTICLE_RE = re.compile(r"(?:out|up|down|back|off)", re.IGNORECASE)
# "and it was 4.0%", "which was 4.0%": the same measure, said again.
_PRONOUN_HEAD_RE = re.compile(
    r"(?:the\s+same|it|that|this|which|there|these|those|they|he|she|its)",
    re.IGNORECASE,
)
_HEAD_LEAD_RE = re.compile(
    r"^(?:\s|,|\b(?:and|while|whereas|but|with|then|also)\b)+",
    re.IGNORECASE,
)
# Words that carry a number and do not name a measure: "then 5.5% in 2022",
# "averaged 3.7% for the year", "fell to 4.48% by December". A leftover word
# ("imports", "membership", "herd") is the measure the clause is about.
_NON_MEASURE_RE = re.compile(
    r"a|an|the|of|at|to|in|on|by|for|from|with|and|or|but|while|whereas|"
    r"then|also|about|around|roughly|nearly|almost|approximately|"
    r"its|it|that|this|which|there|these|those|they|he|she|"
    r"be|been|being|"
    r"year|years|earlier|ago|late|early|through|during|over|since|until|"
    r"after|before|into|per|up|down|back|out|off|still|only|"
    r"much|more|most|less|very|same|other|another|"
    r"comparison|instance|example|context|contrast|"
    r"percent|percentage|points|point|pct|"
    r"dollar|dollars|usd|million|billion|trillion|thousand|bn|mn|"
    r"january|february|march|april|may|june|july|august|september|"
    r"october|november|december",
    re.IGNORECASE,
)
_PREPOSITION_RE = re.compile(
    r"\b(?:in|on|at|for|from|with|after|before|during|through|by|of|to|into|"
    r"over|under|about|around|across|between|among|without|within|upon|"
    r"despite|following|including)\b",
    re.IGNORECASE,
)
# "After a long expansion, at 3.6%" is time. "for union membership, at 4.1%"
# is the measure. A verb in that clause is neither: the measure was already stated.
_TEMPORAL_PREP_RE = re.compile(
    r"\b(?:after|before|during|since|until|following|between|through|over)\b",
    re.IGNORECASE,
)
_LABEL_PREP_RE = re.compile(r"\b(?:for|with|of)\b", re.IGNORECASE)


def _figure_offsets(text, figure):
    """Every place this figure is written. The same digits twice are two
    clauses, and the first one must not bless the second."""
    if not figure:
        return []
    offsets, start = [], 0
    while True:
        at = text.find(figure, start)
        if at < 0:
            return offsets
        offsets.append(at)
        start = at + max(len(figure), 1)


def _content_nominals(text):
    """Words in this span that can name a measure.

    "in real terms" and "year-on-year" say how the rate is measured, not
    which rate it is. Private consumption in real terms is still consumption.
    """
    text = _RATE_ASIDE_RE.sub(" ", text)
    found = []
    for word in re.findall(r"[A-Za-z][A-Za-z'-]*", text):
        if _NON_MEASURE_RE.fullmatch(word):
            continue
        if _CONTINUATION_VERB_RE.fullmatch(word):
            continue
        if _ASSIGN_VERB_RE.fullmatch(word):
            continue
        if _MARK_PARTICLE_RE.fullmatch(word):
            continue
        found.append(word)
    return found


def _previous_label_is_another(text, start, pattern):
    """", at 4.1%" takes the bare noun in front of the comma.

    "union membership, at 4.1%" names membership. "Unemployment, at 3.6%"
    names unemployment. "After a long expansion, at 3.6%" does not: a
    preposition is not a label, and the measure may still follow the number.
    """
    prev_at = 0
    for found in _CLAUSE_OPEN_RE.finditer(text, 0, start):
        prev_at = found.end()
    previous = text[prev_at:start]
    if re.search(pattern, previous, re.I):
        return False
    if _ASSIGN_VERB_RE.search(previous) or _CONTINUATION_VERB_RE.search(previous):
        return False
    if _TEMPORAL_PREP_RE.search(previous):
        return False
    # "in 2023" and "in real terms" are not labels. "for union membership" is.
    if _PREPOSITION_RE.search(previous) and not _LABEL_PREP_RE.search(previous):
        return False
    return bool(_content_nominals(previous))


# A reason after the figure is its own clause: "rose to 8.8% in 2021 as
# pandemic restrictions bit" states no second measure (v21 Sweden). "as a
# share of GDP" does name one, so it stays inside the clause.
_REASON_OPEN_RE = re.compile(
    r"\b(?:as(?!\s+(?:a|an)\s+(?:share|percent(?:age)?|proportion|fraction|ratio)\b)|"
    r"because|amid|when|after|since|following|despite|due\s+to|thanks\s+to)\b",
    re.IGNORECASE,
)


def _clause_states_another(text, figure, at, pattern):
    start = 0
    for found in _CLAUSE_OPEN_RE.finditer(text):
        if found.start() < at:
            start = found.start()
        else:
            break
    end = len(text)
    for found in _CLAUSE_OPEN_RE.finditer(text, at + len(figure)):
        end = found.start()
        break
    reason = _REASON_OPEN_RE.search(text, at + len(figure), end)
    if reason:
        end = reason.start()
    if re.search(pattern, text[start:end], re.I):
        return False
    before = text[start:at]
    verb = None
    for found in _ASSIGN_VERB_RE.finditer(before):
        verb = found
    if verb is not None:
        kind, found = "verb", verb
    else:
        mark = None
        for found in _ASSIGN_MARK_RE.finditer(before):
            mark = found
        if mark is None:
            # No verb and no "at"/"of": a headline still names its measure.
            # "goods imports $27.7 trillion". A bare rate does not.
            return bool(_content_nominals(text[start:end]))
        kind, found = "mark", mark
    head = _HEAD_LEAD_RE.sub("", before[:found.start()]).strip()
    # "whereas Nigeria's reached 24.7%": a country's possessive alone stands
    # for the measure the sentence just named; it states no new one.
    bare = re.sub(r"['\u2019]s$", "", head)
    if bare != head and _COUNTRY_NAMES_RE.fullmatch(bare):
        return False
    if not head or _PRONOUN_HEAD_RE.fullmatch(head):
        # "at 4.1% for union membership": the measure is after the number.
        if _content_nominals(text[start:end]):
            return True
        if kind == "mark" and _previous_label_is_another(text, start, pattern):
            return True
        return False
    if kind == "mark":
        words = head.split()
        last = words[-1]
        if _MARK_PARTICLE_RE.fullmatch(last) and len(words) >= 2:
            last = words[-2]
        if _CONTINUATION_VERB_RE.fullmatch(last):
            # "peaked at 9.1% in June" carries the series. "peaked at 4.1%
            # for union membership" names a different one.
            return bool(_content_nominals(text[start:end]))
    return True


def _figure_states_another_measure(decomp, pattern):
    """The clause holding this figure states a measure of its own, and that
    measure is not the series a tick would use.

    A match is the source's figure for this clause. "goods imports were
    $27.7 trillion" is not a GDP match, and neither is "the import bill came
    to $27.7 trillion" or the headline "goods imports $27.7 trillion". A
    union share is not an inflation match, including "union membership, at
    4.1%", "for union membership, at 4.1%", and "at 4.1% for union
    membership". A later reading of the same series states no new measure: "then
    fell to 4.48%", "and averaged 3.7% for the year", "from 6.7% a year
    earlier", "peaked at 9.1%", "and 4.0% in 2024", "Unemployment, at 3.6%".
    A clause that names the series is that series, including "the US 2-year
    Treasury yield". The same digits written twice are not a match when one
    of those clauses states another measure.
    """
    if not pattern:
        return False
    text = decomp.full_sentence or decomp.sentence or ""
    figure = _figure_text(decomp)
    offsets = _figure_offsets(text, figure)
    if not offsets:
        return False
    return any(
        _clause_states_another(text, figure, at, pattern) for at in offsets
    )


# Wikidata's measurements, as a figure's own words name them.
_WD_METRIC_WORDS = {
    "length": r"\blong\b|length|span|stretch|runs|flows|course",
    "area": r"\barea\b|square|\bsq\b|km\u00b2|km2|acres|hectares|covers|surface",
    "height": r"tall|height|\bhigh\b|elevation|altitude|rises|summit|\bpeak\b|towers|"
              r"\breaches?\b|roof|\btip\b|stands|soars|climbs",
    "population": r"popul|people|inhabitants|residents|home\s+to|citizens",
    "diameter": r"diameter|radius|radii|across|\bwide\b|width",
    "employees": r"employ|staff|workers|workforce|headcount|people",
    "weight": r"weigh|\bmass\b",
    "depth": r"\bdeep\b|depth",
}


def _wd_names_metric(decomp):
    pattern = _WD_METRIC_WORDS.get(decomp.metric or "")
    if not pattern:
        return True
    others = [p for m, p in _WD_METRIC_WORDS.items() if m != decomp.metric
              and not (decomp.metric == "employees" and m == "population")]
    return _names_measure(decomp, pattern, others)


_FIGURE_TOKEN_RE = re.compile(
    r"[$\u20ac\u00a3]?\d[\d,]*(?:\.\d+)?(?:\s?(?:trillion|billion|million|thousand|bn|mn|[BMK]\b))?")
_TOKEN_SCALE = {"trillion": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6,
                "mn": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}


def _figure_text(decomp):
    """The figure as the sentence writes it: raw_value, or else the token whose
    value is the decomposition's (a hand-built or reader-built claim may carry
    only the value)."""
    text = decomp.full_sentence or decomp.sentence or ""
    raw = str(decomp.raw_value or "").strip()
    if raw and raw in text:
        return raw
    value = getattr(decomp, "value", 0) or 0
    for m in _FIGURE_TOKEN_RE.finditer(text):
        tok = m.group().strip()
        num = re.search(r"\d[\d,]*(?:\.\d+)?", tok).group().replace(",", "")
        word = re.search(r"[A-Za-z]+$", tok)
        scale = _TOKEN_SCALE.get(word.group().lower(), 1) if word else 1
        if value and abs(float(num) * scale - value) <= abs(value) * 1e-6:
            return tok
    return raw


def _clause_of(decomp):
    """The figure's own words on both sides: back to the previous figure, and on to
    the next punctuation ("1.46 million people in the city itself")."""
    from identity_path import own_words
    text = decomp.full_sentence or decomp.sentence or ""
    figure = _figure_text(decomp)
    at = text.find(figure) if figure else -1
    if at < 0:
        return text
    after = re.split(r"[,;:()]|\.(?:\s|$)", text[at + len(figure):], maxsplit=1)[0]
    return own_words(text, at, figure) + " " + after


def _fred_names_series(decomp, spec):
    pattern = spec[0]
    others = [s[0] for s in _FRED_SPECS if s[0] != pattern]
    # A figure inside a sentence about one series ("core CPI ... and headline CPI")
    # may name the general word of another: "inflation" covers CPI and PCE alike.
    return _names_measure(decomp, pattern, others)


def _trailing_year_differs(decomp):
    """The words right after the figure name a year other than the claim's."""
    years = re.findall(r"(?:19|20)\d\d", decomp.time_period or "")
    text = decomp.full_sentence or decomp.sentence or ""
    figure = _figure_text(decomp)
    at = text.find(figure) if figure else -1
    if at < 0:
        return False
    after = re.split(r"[,;:()]|\.(?:\s|$)", text[at + len(figure):], maxsplit=1)[0]
    found = re.findall(r"(?:19|20)\d\d", after)
    return bool(found) and any(y not in years for y in found)


def _year_is_its_own(decomp):
    """The year a refutation compares is written in the figure's own words, or
    before the sentence's first figure ("In 2023, revenue was $X and net income $Y").
    In "about $4.53 billion, up from $4.39 billion ... fiscal 2022's $4.10 billion"
    fiscal 2022 belongs to the last figure, not the first."""
    years = re.findall(r"(?:19|20)\d\d", decomp.time_period or "")
    if not years:
        return True
    text = decomp.full_sentence or decomp.sentence or ""
    if not any(y in text for y in years):
        return True  # inherited from a heading: the inherited-year rules decide
    figures = [m.start() for m in re.finditer(r"[$\u20ac\u00a3]?\d[\d,.]*", text)
               if not re.fullmatch(r"(?:19|20)\d\d", m.group().strip("$\u20ac\u00a3,."))]
    first = min(figures) if figures else len(text)
    # The words after the figure name another year: "had come down to around 2.5
    # percent by late 2024" is late 2024's, whatever year came before (v18).
    figure = _figure_text(decomp)
    at = text.find(figure) if figure else -1
    if at >= 0:
        after = re.split(r"[,;:()]|\.(?:\s|$)", text[at + len(figure):], maxsplit=1)[0]
        if any(y not in years for y in re.findall(r"(?:19|20)\d\d", after)):
            return False
    if any(y in text[:first] for y in years):
        return True
    return any(y in _clause_of(decomp) for y in years)


def verify_world_bank(decomp):
    """Verify economic indicators against World Bank API."""
    country = _claim_country(decomp)
    if not country:
        return SourceResult(source_name="World Bank", match_type="no_data")

    indicator_id, indicator_name = _wb_indicator_for(decomp)
    if not indicator_id:
        return SourceResult(source_name="World Bank", match_type="no_data")
    # A part of the year is not the year's observation. Nothing is compared.
    if _figure_is_part_of_a_year(
            decomp, month_blocks=indicator_id in _WB_MONTH_NOT_THE_YEAR):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # A fiscal year is not the calendar year these series use. A calendar
    # year written on the figure stays that year.
    if indicator_id in (
            "NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "NY.GDP.MKTP.KD.ZG",
            "FP.CPI.TOTL.ZG", "SL.UEM.TOTL.ZS") and _figure_year_is_fiscal(decomp):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # Constant-price GDP is not the current-dollar series.
    if indicator_id in ("NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD") and _names_real_level(decomp):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # Purchasing-power GDP is a different series from current dollars,
    # and from constant-local-currency growth.
    if indicator_id in ("NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "NY.GDP.MKTP.KD.ZG") and _names_ppp(decomp):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # Nominal growth is not constant-price growth. The basis may follow
    # the figure in a comma aside. The next sentence does not.
    if indicator_id == "NY.GDP.MKTP.KD.ZG" and _names_current_prices(decomp):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # The current-dollar series is in dollars. A euro figure is not it.
    if indicator_id.endswith((".CD", ".KD")) and _wb_figure_is_not_dollars(decomp):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # Basic prices and factor cost are not the market-price series.
    # A growth rate at those prices is not constant-price growth either.
    if indicator_id in ("NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "NY.GDP.MKTP.KD.ZG") and (
            _BASIC_OR_FACTOR_RE.search(_basis_text(decomp))):
        return SourceResult(source_name="World Bank", match_type="no_data")
    if indicator_id in ("NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD") and _names_other_price_year(decomp):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # Previous year's prices, and chain-linked volumes, are a constant-price
    # level. Real growth at those prices stays the growth series.
    if indicator_id in ("NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD") and (
            _names_prior_year_prices(decomp) or _names_chain_volume(decomp)):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # Disposable income and GNI share "per capita" with GDP per head.
    if indicator_id == "NY.GDP.PCAP.CD" and _NOT_GDP_PCAP_RE.search(
            _figure_own_clause(decomp)):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # "at an annual rate" on a level or on real growth is a run rate.
    # The same words on inflation are still the year's rate.
    if indicator_id in (
            "NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "NY.GDP.MKTP.KD.ZG") and (
            _ANNUAL_RATE_RE.search(_basis_text(decomp))):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # Non-oil, private-sector, or potential GDP is not the national total.
    # The same compounds on a growth rate are not the economy's growth.
    if indicator_id in ("NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "NY.GDP.MKTP.KD.ZG") and (
            _NOT_HEADLINE_GDP_RE.search(_basis_text(decomp))):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # "manufacturing GDP" is the sector. "Manufacturing rose, while GDP was"
    # is the national total: the sector word is in the other clause.
    if indicator_id in ("NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "NY.GDP.MKTP.KD.ZG") and (
            _not_the_national_product(decomp)):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # "GDP excluding agriculture was" is not the national total. A basket
    # after the figure in this clause is the same exclusion. The next
    # clause counts only when it is a basket exclusion and nothing else.
    if indicator_id in (
            "NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "NY.GDP.MKTP.KD.ZG",
            "FP.CPI.TOTL.ZG") and _exclusion_before_figure(decomp):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # "rose by $4.5 trillion" is the change, not the level.
    if indicator_id in ("NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD") and (
            _level_is_a_change(decomp)):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # Per worker is not the national total. A working-day adjustment is
    # not the unadjusted year. Per person and a calendar year stay.
    if indicator_id in (
            "NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "NY.GDP.MKTP.KD.ZG") and (
            _output_per_job(decomp) or _calendar_or_working_day(decomp)):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # A working-day adjustment of inflation is not the headline rate.
    # Seasonally adjusted inflation is not this unadjusted index.
    if indicator_id == "FP.CPI.TOTL.ZG" and (
            _calendar_or_working_day(decomp) or _seasonally_adjusted_inflation(decomp)):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # "4.1 percentage points" is not the rate. "3.7% (up 0.2 percentage
    # points)" still is: the points belong to the other number.
    if indicator_id in (
            "NY.GDP.MKTP.KD.ZG", "FP.CPI.TOTL.ZG", "SL.UEM.TOTL.ZS") and (
            _figure_is_in_points(decomp)):
        return SourceResult(source_name="World Bank", match_type="no_data")
    if indicator_id == "SL.UEM.TOTL.ZS" and _narrow_unemployment(_figure_own_clause(decomp)):
        return SourceResult(source_name="World Bank", match_type="no_data")
    if indicator_id == "FP.CPI.TOTL.ZG" and (
            _component_of_headline_prices(_inflation_text(decomp))
            or _leading_price_component(decomp)
            or _adjacent_price_line(decomp)
            or _bare_price_category(decomp)
            or _price_for_the_line(decomp)
            or _price_category_on_figure(decomp)):
        return SourceResult(source_name="World Bank", match_type="no_data")
    # Expected inflation is not this year's outcome. The other clause's
    # expectations do not silence the outcome beside them.
    if indicator_id == "FP.CPI.TOTL.ZG" and _EXPECTED_INFLATION_RE.search(
            _figure_own_clause(decomp)):
        return SourceResult(source_name="World Bank", match_type="no_data")

    # "a fiscal surplus of $372.9 million, equal to 2.4 percent of GDP": an
    # amount stated as a share of GDP is never GDP itself.
    if indicator_id == "NY.GDP.MKTP.CD" and re.search(
            r'(?:percent|per\s+cent|%)\s+of\s+(?:the\s+)?(?:nominal\s+)?GDP\b',
            _clause_holding(decomp.sentence, decomp.raw_value), re.IGNORECASE):
        return SourceResult(source_name="World Bank", match_type="no_data")

    # A dollar figure is not a head count, whatever words sit beside it.
    if indicator_id == "SP.POP.TOTL" and decomp.unit == "currency":
        return SourceResult(source_name="World Bank", match_type="no_data")

    # A country's population figure, not a count of people in it who do
    # something: "12 million people in Germany use the service" is true
    # or false independently of how many people live there.
    if indicator_id == "SP.POP.TOTL" and (
        not _COUNTRY_TOTAL_RE.search(decomp.sentence)
        or _SUBGROUP_RE.search(decomp.sentence)
    ):
        return SourceResult(source_name="World Bank", match_type="no_data")

    # A rate against a total: "GDP grew 0.3%" is not a $0.3 economy.
    if decomp.unit == "percent" and indicator_id in _WB_TOTAL_INDICATORS:
        return SourceResult(source_name="World Bank", match_type="no_data")

    iso2 = _wb_country_code(country)
    if not iso2:
        return SourceResult(source_name="World Bank", match_type="no_data")

    # Query World Bank for the most recent data
    year = ""
    if decomp.time_period:
        year_match = re.search(r'20[1-3]\d', decomp.time_period)
        if year_match:
            year = year_match.group()
    # A fiscal label earlier in the sentence can be the year the parser
    # kept. This series uses the calendar year written on the figure.
    # The decomposition is left as it was.
    calendar = _calendar_year_beside_a_fiscal_label(decomp)
    if calendar:
        year = calendar

    date_param = f"date={year}" if year else "date=2020:2025"
    wb_url = (
        f"https://api.worldbank.org/v2/country/{iso2}/indicator/{indicator_id}"
        f"?{date_param}&format=json&per_page=5"
    )
    wb_data = _fetch_json(wb_url)
    if not wb_data or len(wb_data) < 2 or not wb_data[1]:
        return SourceResult(source_name="World Bank", match_type="no_data")

    growth = indicator_id == "NY.GDP.MKTP.KD.ZG"
    claim_value = decomp.value * (
        _growth_sign(decomp.sentence, decomp.raw_value) if growth else 1)

    # Find the most recent non-null observation
    for obs in wb_data[1]:
        if obs.get("value") is not None:
            source_val = obs["value"]
            obs_year = obs.get("date", "")

            # World Bank GDP is in raw dollars. Normalize claim value
            # was already done by normalize_value().
            diff = abs(source_val - claim_value) / max(abs(claim_value), 1e-10)

            # Neighbouring years, read only when this one disagrees: whether one
            # of them could explain it, and which one this figure really is.
            near_another_year = False
            stale_year = ""
            if diff >= max(0.05, _rounding_room(decomp.raw_value)) and year:
                window = _fetch_json(
                    f"https://api.worldbank.org/v2/country/{iso2}/indicator/"
                    f"{indicator_id}?date={int(year) - 2}:{int(year) + 2}"
                    f"&format=json&per_page=5"
                )
                for other in (window[1] or []) if window and len(window) > 1 else []:
                    if other.get("value") is None or other.get("date") == year:
                        continue
                    gap = abs(other["value"] - claim_value) / max(abs(claim_value), 1e-10)
                    if indicator_id not in _WB_TOTAL_INDICATORS:
                        # A rate is near in points: 0.2% against 0.25 is
                        # that year's figure, not 25% off.
                        points_off = abs(other["value"] - claim_value)
                        near_another_year = near_another_year or points_off <= max(
                            0.15, _rate_room(decomp.raw_value))
                        if points_off <= 0.05:
                            stale_year = other.get("date", "")
                        continue
                    near_another_year = near_another_year or gap < 0.10
                    if gap < 0.01:
                        stale_year = other.get("date", "")
            inherited_cannot_refute = (
                decomp.year_inherited
                and not _YEAR_REFERENCE_RE.search(decomp.sentence)
                and near_another_year
                and not (stale_year and decomp.year_sole
                         and not _POINTS_ELSEWHERE_RE.search(decomp.sentence))
            )

            # "3.39 million" is stated to the nearest ten thousand: 3.7% off is
            # another country's figure, not this one rounded. Between that and
            # 5% the data's own revisions could explain it, so it says nothing.
            band = _wb_match_type(diff, decomp.raw_value, source_val)
            if (band == "exact" and decomp.year_inherited and decomp.doc_main_year
                    and year and year != decomp.doc_main_year):
                # "Population: about 278.8 million" names no year, and the
                # document is mainly about 2023: matching it to 2022 is a
                # guess, and a guess can say near, not equal.
                band = "close"
            is_close, is_exact, is_gray = (
                band is not None, band == "exact", diff < 0.05,
            )
            if indicator_id not in _WB_TOTAL_INDICATORS:
                # A rate or a life expectancy is compared in points: 83.2 years
                # against 84.04 is a different country's figure, not 1% off.
                points = abs(source_val - claim_value)
                near = max(0.15, _rate_room(decomp.raw_value))
                is_close, is_exact = points <= near, points <= 0.05
                # Growth is revised by up to about a point after the first
                # estimate: inside that it may be the figure first published.
                # Inflation too: a CPI and the EU's harmonised index (HICP) differ
                # by up to about a point (France 2022: 5.9 HICP, 5.22 CPI).
                is_gray = points <= max(1.0 if growth or indicator_id == "FP.CPI.TOTL.ZG"
                                        else 0.5, 2 * near)
            if is_close and (
                _wb_series_unbound(decomp, indicator_id, country)
                or _georgia_unresolved(decomp, country)
                or _figure_states_another_measure(
                    decomp, _WB_INDICATOR_WORDS.get(indicator_id, ""))
            ):
                # The digits match a series this figure does not name,
                # or a place the sentence does not settle.
                # No tick, and no "another figure": nothing was compared.
                return SourceResult(source_name="World Bank", match_type="no_data")
            if is_close:
                match_type = "exact" if is_exact else "close"
            elif indicator_id == "AG.SRF.TOTL.K2":
                # This series put Canada at 15.6M square km against a true
                # 9.98M. It may confirm; it is not reliable enough to refute.
                match_type = "no_data"
            elif decomp.subject_ambiguous or inherited_cannot_refute:
                match_type = "no_data"
            elif indicator_id == "SL.UEM.TOTL.ZS" and (
                    decomp.year_inherited
                    or abs(source_val - claim_value) < max(2.0, 0.2 * abs(source_val))):
                # The World Bank's unemployment rate is the ILO's modeled
                # estimate; a country's own survey defines it differently
                # (Serbia 9.4% against 8.27). Only a figure far beyond that
                # gap, for a year the sentence names, is another number.
                match_type = "no_data"
            elif indicator_id == "FP.CPI.TOTL.ZG" and _TWELVE_MONTH_RE.search(decomp.sentence):
                # "27% year on year" is one month's 12-month rate, not the
                # year's average.
                match_type = "no_data"
            elif (_MONTH_NAME_RE.search(decomp.sentence)
                  or (len(set(re.findall(r'20[0-3]\d', decomp.sentence))) > 1
                      and not decomp.year_own)):
                # A rate for one month against an annual average.
                match_type = "no_data"
            elif not year and indicator_id != "SP.POP.TOTL":
                # With no period named, a moving figure that disagrees
                # may just be another year's. Population moves slowly
                # enough to be wrong regardless.
                match_type = "no_data"
            elif (decomp.subject and not _COUNTRY_NAMES_RE.fullmatch(decomp.subject)
                  and not _COUNTRY_ABBREV_RE.fullmatch(decomp.subject)
                  and country.lower() not in decomp.subject.lower()):
                # "Phoenix ... the fifth-largest city in the US" is about
                # Phoenix: the country's figure says nothing against it.
                match_type = "no_data"
            elif not _names_indicator(decomp, indicator_id):
                # "Life expectancy is roughly 74 years, the median age is about
                # 41": the 41 is the median age, not life expectancy, though the
                # sentence names life expectancy first (v17).
                match_type = "no_data"
            elif _subnational(decomp):
                # "Guatemala City metro population: roughly 3 million" is the
                # city's figure, not the country's.
                match_type = "no_data"
            elif country.lower() in _AMBIGUOUS_PLACE_NAMES:
                # Georgia the state has about three times the people.
                match_type = "no_data"
            elif (indicator_id.startswith("NY.GDP") and not growth
                  and decomp.unit != "currency"):
                # "the economy added 3 million jobs" beside the word GDP is
                # not a figure for GDP. Only money can disagree with it.
                match_type = "no_data"
            elif indicator_id.endswith((".ZS", ".ZG")) and decomp.unit != "percent":
                # A rate cannot disagree with a count: "payrolls grew by 6.7
                # million" against the unemployment rate.
                match_type = "no_data"
            elif is_gray:
                # Every guard above passed, so this is the same country, series
                # and year, and the figure is a little off: an AI near miss
                # ("3.2%" growth for 3.33). Revisions could explain it, so it
                # does not refute; it is shown as near but not equal, with the
                # World Bank's figure. Before, it read "no source could check".
                match_type = "close"
            elif not _country_settled(decomp, country):
                # v23 Mexico: "tied to the US", named once in passing, made the
                # US the subject. A country the text never settles is not one
                # to call a figure wrong against.
                match_type = "no_data"
            elif not _place_written(decomp, country):
                # The country is not settled where the figure is written
                # (proposal 13, pre-registered on v30): confirm, never refute.
                match_type = "no_data"
            elif (indicator_id in _WB_TOTAL_INDICATORS or diff < 1.0
                  or (growth and abs(source_val - claim_value) < 15)):
                match_type = "contradicted"
            else:
                # A rate this far off is usually a misparsed number.
                match_type = "no_data"
            if match_type == "contradicted" and decomp.confirm_only:
                match_type = "no_data"

            return _hold_unearned_refute(SourceResult(
                source_name="World Bank",
                source_url=f"https://data.worldbank.org/indicator/{indicator_id}?locations={iso2}",
                source_value=source_val,
                source_text=(
                    f"{country}, {indicator_name} ({obs_year}): "
                    f"{source_val:,.0f}" if abs(source_val) >= 1000
                    else f"{country}, {indicator_name} ({obs_year}): {source_val:,.2f}"
                ) + (
                    f". That is the {stale_year} figure."
                    if stale_year and match_type == "contradicted" else ""
                ),
                match_type=match_type,
                difference_pct=round(diff * 100, 1),
                confidence=0.9 if match_type == "exact" else 0.75 if match_type == "close" else 0.6,
            ))

    return SourceResult(source_name="World Bank", match_type="no_data")


# ── CoinGecko ──

_CRYPTO_NAMES = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana",
    "cardano": "cardano", "ada": "cardano",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "ripple": "ripple", "xrp": "ripple",
    "polkadot": "polkadot", "dot": "polkadot",
    "avalanche": "avalanche-2", "avax": "avalanche-2",
    "litecoin": "litecoin", "ltc": "litecoin",
    "chainlink": "chainlink", "link": "chainlink",
}

_CRYPTO_RE = re.compile(
    r'\b(bitcoin|btc|ethereum|eth|solana|sol|cardano|ada|'
    r'dogecoin|doge|ripple|xrp|polkadot|dot|avalanche|avax|'
    r'litecoin|ltc|chainlink|link|crypto(?:currency)?)\b',
    re.IGNORECASE
)


def _detect_crypto(sentence, heading):
    """Detect cryptocurrency from claim context."""
    for text in [heading, sentence]:
        if text:
            m = _CRYPTO_RE.search(text)
            if m:
                token = m.group().lower()
                return _CRYPTO_NAMES.get(token)
    return None


def verify_coingecko(decomp):
    """Verify crypto prices/market caps against CoinGecko."""
    coin_id = _detect_crypto(decomp.sentence, decomp.heading)
    if not coin_id:
        return SourceResult(source_name="CoinGecko", match_type="no_data")

    url = (
        f"https://api.coingecko.com/api/v3/simple/price"
        f"?ids={coin_id}&vs_currencies=usd"
        f"&include_market_cap=true&include_24hr_vol=true"
    )
    data = _fetch_json(url)
    if not data or coin_id not in data:
        return SourceResult(source_name="CoinGecko", match_type="no_data")

    coin_data = data[coin_id]
    price = coin_data.get("usd", 0)
    market_cap = coin_data.get("usd_market_cap", 0)

    # Try matching against price or market cap
    for label, source_val in [("price", price), ("market cap", market_cap)]:
        if source_val == 0:
            continue
        diff = abs(source_val - decomp.value) / max(abs(decomp.value), 1e-10)
        if diff < 0.10:  # 10% tolerance for crypto (volatile)
            match_type = "exact" if diff < 0.02 else "close"
            return SourceResult(
                source_name="CoinGecko",
                source_url=f"https://www.coingecko.com/en/coins/{coin_id}",
                source_value=source_val,
                source_text=f"{coin_id} {label}: ${source_val:,.2f}" if source_val < 100000 else f"{coin_id} {label}: ${source_val:,.0f}",
                match_type=match_type,
                difference_pct=round(diff * 100, 1),
                confidence=0.8 if match_type == "exact" else 0.65,
            )

    return SourceResult(
        source_name="CoinGecko",
        source_url=f"https://www.coingecko.com/en/coins/{coin_id}",
        source_text=f"{coin_id}: ${price:,.2f} (market cap: ${market_cap:,.0f})",
        match_type="no_data",
    )


# ── FRED (Federal Reserve Economic Data) ──

# What each phrase means in FRED: series, scale to units, whether the figure
# is a rate compared in points, and extra query parameters. Phrases are
# matched nearest to the figure first.
_FRED_SPECS = (
    (r"real\s+(?:gdp|gross\s+domestic\s+product)", "GDPC1", 1e9, False, {},
     "billions of chained 2017 dollars"),
    (r"gdp|gross\s+domestic\s+product|economic\s+output", "GDP", 1e9, False, {}, "billions of dollars"),
    (r"unemployment|jobless", "UNRATE", 1, True, {}, "percent"),
    # Core and PCE are other indexes: "core CPI ended 2023 at 3.9%" against
    # the headline series read 3.4% and contradicted a true figure.
    (r"core\s+pce|core\s+personal\s+consumption", "PCEPILFE", 1, True, {"units": "pc1"},
     "percent change from a year earlier"),
    (r"\bpce\b|personal\s+consumption\s+expenditures?", "PCEPI", 1, True, {"units": "pc1"},
     "percent change from a year earlier"),
    (r"core\s+(?:cpi|consumer\s+prices?(?:\s+index)?)", "CPILFENS", 1, True, {"units": "pc1"},
     "percent change from a year earlier"),
    # The unadjusted index is the one behind the published headline figure:
    # 9.1% in June 2022, against 8.9% on the seasonally adjusted series.
    (r"inflation|consumer\s+prices|\bcpi\b", "CPIAUCNS", 1, True, {"units": "pc1"},
     "percent change from a year earlier"),
    (r"federal\s+funds|fed\s+funds|(?:effective\s+)?funds\s+rate|policy\s+rate|interest\s+rates?",
     "FEDFUNDS", 1, True, {}, "percent"),
    (r"mortgage\s+(?:interest\s+)?rates?|30-year\s+fixed", "MORTGAGE30US", 1, True, {}, "percent"),
    (r"2-year\s+(?:treasury|yield|note)", "DGS2", 1, True, {}, "percent"),
    (r"5-year\s+(?:treasury|yield|note)", "DGS5", 1, True, {}, "percent"),
    (r"30-year\s+(?:treasury|bond)", "DGS30", 1, True, {}, "percent"),
    (r"10-year\s+(?:treasury|yield|note)|treasury\s+(?:yield|rate)", "DGS10", 1, True, {}, "percent"),
    (r"national\s+debt|federal\s+debt|public\s+debt", "GFDEBTN", 1e6, False,
     {"aggregation_method": "eop"}, "millions of dollars"),
)
# Words just before a series' name that make it another measure: "core
# inflation", "credit card interest rate", "15-year mortgage rate", "the
# 7-year Treasury yield". The general series must not answer for them.
_FRED_QUALIFIED = {
    "CPIAUCNS": re.compile(
        r'\b(?:core|pce|personal\s+consumption|food|energy|shelter|rent|services|goods|'
        r'wage|producer|ppi|import|export|medical|housing|chained|super-?core|'
        r'median|trimmed|sticky|harmonis(?:ed|zed)|hicp|breakeven)\b'
        r'[\w\s-]{0,12}$|\bunderlying[\s-]*$|(?:^|[^A-Za-z])c[\s-]*$',
        re.IGNORECASE),
    "PCEPI": re.compile(r'\bcore\b[\w\s-]{0,6}$', re.IGNORECASE),
    "FEDFUNDS": re.compile(
        r'\b(?:credit[\s-]+card|card|auto|car|student|loan|mortgage|deposit|savings?|'
        r'account|prime|bank|cd|personal|real|neutral|lending|borrowing|consumer)\b'
        r'[\w\s-]{0,12}$', re.IGNORECASE),
    "MORTGAGE30US": re.compile(
        r'\b(?:15-year|20-year|5/1|adjustable|arm|jumbo|fha|va)\b[\w\s-]{0,12}$', re.IGNORECASE),
    "DGS10": re.compile(r'\b(?!10-)\d+-(?:year|month|week)\b[\w\s-]{0,4}$', re.IGNORECASE),
    # "real GDP" is the chained series. "real" has to sit on the word:
    # "Real wages rose, while GDP was" is still the nominal level.
    "GDP": re.compile(r'\breal\b[\w\s-]{0,6}$', re.IGNORECASE),
}
_FRED_RANGE_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*%?\s*(?:-|to|\u2013)\s*(\d+(?:\.\d+)?)\s*%')
_FRED_PART_OF_YEAR_RE = re.compile(
    r'\b(?:that|same|this|the)\s+(?:same\s+)?(?:month|week|day|quarter)\b|'
    r'\b(?:briefly|intraday|daily|weekly|reached|hit|topped|touched|spiked|surged\s+to)\b',
    re.IGNORECASE)
_FRED_MONTH_NAMES = (r'January|February|March|April|May|June|July|August|September|'
                     r'October|November|December')
# A month, with its year when the text gives one: "December 2021", "in December".
_FRED_ANY_MONTH_RE = re.compile(
    r'\b(' + _FRED_MONTH_NAMES + r')\b(?!\s+\d{1,2}\b)(?:\s+(20[0-3]\d))?')
_FRED_YEAR_END_CUE_RE = re.compile(
    r'\b(?:end(?:ed|ing|s)?(?:\s+of)?|close\s+of|closed\s+out|finish(?:ed|ing)?)\s+'
    r'(?:the\s+year|(20[0-3]\d))|\byear[- ]end\b', re.IGNORECASE)
_FRED_ANNUAL_CUE_RE = re.compile(
    r'\baverag\w*|\bannual[- ]average|\bfor\s+the\s+(?:full\s+|whole\s+)?year\b|'
    r'\bfull[- ]year\b|\bon\s+an\s+annual\b', re.IGNORECASE)
_FRED_EXTREME_RE = re.compile(
    r'\b(?:peak(?:ed|ing)?|topp(?:ed|ing)\s+out|top(?:s|ped)?\s+out|bottom(?:ed|ing)?|'
    r'record\s+(?:low|high)|(?:low|high)\s+of|lows?|highs?|'
    # A move within the period: "briefly dropped to roughly 1.4% in July 2016" is
    # a day's yield, not July's average (v18).
    r'briefly|dropped\s+to|dipped\s+to|sank\s+to|plunged\s+to|fell\s+as\s+low|'
    r'spiked\s+to|surged\s+to|jumped\s+to|touched)\b', re.IGNORECASE)


_DOC_AVERAGES_RE = re.compile(
    r'\b(?:annual|yearly|full[- ]year)\s+averages\b|\baverages\s+for\s+(?:the|each)\s+year\b',
    re.IGNORECASE)


def _fred_period_cue(sentence, at, raw):
    """The period cue nearest a figure: ("month", name, year or None),
    ("year_end", "December", year or None) or ("annual", None, None). A cue
    after the figure is preferred at equal distance: "rose 7.0% in December"."""
    if at < 0:
        return None
    end = at + len(raw)
    found = []
    for m in _FRED_ANY_MONTH_RE.finditer(sentence):
        found.append((m, ("month", m.group(1), m.group(2))))
    for m in _FRED_YEAR_END_CUE_RE.finditer(sentence):
        found.append((m, ("year_end", "December", m.group(1))))
    for m in _FRED_ANNUAL_CUE_RE.finditer(sentence):
        found.append((m, ("annual", None, None)))
    if not found:
        return None

    def distance(item):
        m = item[0]
        if m.start() >= end:
            return m.start() - end
        if m.end() <= at:
            return at - m.end() + 5
        return 0
    return min(found, key=distance)[1]


def _fred_december(params, year, scale):
    """December of the year, for a rate whose text names no period."""
    query = {k: v for k, v in params.items() if k != "aggregation_method"}
    query.update(frequency="m", observation_start=f"{year}-12-01",
                 observation_end=f"{year}-12-01")
    data = _fetch_json(
        "https://api.stlouisfed.org/fred/series/observations?"
        + urllib.parse.urlencode(query)
    )
    rows = [
        (o["date"], float(o["value"]) * scale)
        for o in (data or {}).get("observations", [])
        if o.get("value") not in (None, "", ".")
    ]
    return rows[0] if rows else None


_MONTH_ALT = (r'(?:January|February|March|April|May|June|July|August|September|'
              r'October|November|December)')
_MONTH_NUMBERS = {
    m: i for i, m in enumerate((
        "January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December"), start=1)
}


def _figure_sentence(sentence, raw):
    """The sentence holding the figure, when several were joined: a flattened
    table row, or a label appended after the full stop."""
    at = sentence.find(raw) if raw else -1
    if at < 0:
        return sentence
    start = max(sentence.rfind(". ", 0, at), sentence.rfind("; ", 0, at))
    end = min((i for i in (sentence.find(". ", at), sentence.find("; ", at)) if i >= 0),
              default=len(sentence))
    return sentence[start + 2 if start >= 0 else 0:end + 1]


def _fred_spec(decomp):
    """The series named closest to the figure, in the figure's own sentence
    if it names one."""
    raw = str(decomp.raw_value).strip()
    own = _figure_sentence(decomp.sentence, raw)
    for sentence in ((own, decomp.sentence) if own != decomp.sentence else (own,)):
        found = _fred_spec_in(sentence, raw)
        if found:
            return found
    return None


def _fred_spec_in(sentence, raw):
    at = sentence.find(raw) if raw else -1
    best, best_gap = None, None
    for spec in _FRED_SPECS:
        qualified = _FRED_QUALIFIED.get(spec[1])
        for found in re.finditer(spec[0], sentence, re.IGNORECASE):
            if qualified and qualified.search(sentence[max(0, found.start() - 40):found.start()]):
                continue
            # "jobless claims" is not the unemployment rate. "jobless rate" is.
            # Claims more than a few words away belong to the other clause.
            if spec[1] == "UNRATE" and _narrow_unemployment_at(
                    sentence, found.start(), found.end()):
                continue
            # "CPI-W" is not the headline index. The W sits after the word.
            if spec[1] == "CPIAUCNS" and re.match(
                    r"[\s-]*w\b", sentence[found.end():found.end() + 6], re.IGNORECASE):
                continue
            gap = abs(found.start() - at) if at >= 0 else 0
            if best_gap is None or gap < best_gap:
                best, best_gap = spec, gap
    return best


_US_NAMED_RE = re.compile(
    r'\b(?:U\.\s?S\.?(?:\s|$)|US\b|USA\b|United\s+States|America(?:n|\'s)?\b|'
    r'federal\s+(?:reserve|funds|debt|government)|the\s+Fed\b|Freddie\s+Mac|Fannie\s+Mae|'
    r'Treasury|Bureau\s+of\s+(?:Labor|Economic)|\bBLS\b|\bBEA\b|FRED\b)',
)


def _fred_applies(decomp):
    """FRED's series are American. A figure that does not say so may be any
    country's: Rwanda's GDP was once checked against the US."""
    if not _fred_spec(decomp):
        return False
    country = _claim_country(decomp)
    is_us = country in ("United States", "U.S", "U.S.", "US", "USA", "America")
    if country and not is_us:
        return False
    return bool(is_us or _US_NAMED_RE.search(_without_us_currency(decomp.sentence))
                or _US_NAMED_RE.search(_without_us_currency(decomp.heading)) or decomp.doc_is_us
                or (decomp.doc_no_country and not country))


def _fred_us_stated(decomp):
    """The figure is the US's by the text itself, not by default: only then may FRED refute."""
    country = _claim_country(decomp)
    return bool(country in ("United States", "U.S", "U.S.", "US", "USA", "America")
                or _US_NAMED_RE.search(_without_us_currency(decomp.sentence)) or _US_NAMED_RE.search(_without_us_currency(decomp.heading))
                or decomp.doc_is_us)


def _rate_room(raw_value):
    """Half the last stated decimal, in points: "3.6%" covers 3.55 to 3.65."""
    digits = re.search(r'\d+(?:\.(\d+))?', str(raw_value))
    places = len(digits.group(1)) if digits and digits.group(1) else 0
    return max(0.05, 0.5 * 10 ** -places)


def verify_fred(decomp):
    """US macroeconomic figures against FRED, for the period the claim names:
    the year's average, or a named month. Rates are compared in points."""
    api_key = os.environ.get("FRED_API_KEY", "")
    spec = _fred_spec(decomp) if api_key else None
    is_range = bool(re.search(r'\d\s*%?\s*(?:-|to|\u2013)\s*\d', str(decomp.raw_value)))
    if not spec or not (decomp.value or is_range):
        return SourceResult(source_name="FRED", match_type="no_data")
    _, series_id, scale, is_rate, extra, unit_desc = spec
    # "raised rates 11 times" is a count, not a rate.
    if is_rate and decomp.unit != "percent" and not is_range:
        return SourceResult(source_name="FRED", match_type="no_data")
    # No month named: FRED is asked for the year's average. A quarter, a
    # half, or a year to date is not that average. "4.1% in December" is.
    if _figure_is_part_of_a_year(decomp, month_is_its_period=True):
        return SourceResult(source_name="FRED", match_type="no_data")
    # GDP at an annual rate is a run rate, not the year's level. Inflation
    # at an annual rate is still the year's inflation.
    if series_id in ("GDP", "GDPC1") and _ANNUAL_RATE_RE.search(_basis_text(decomp)):
        return SourceResult(source_name="FRED", match_type="no_data")
    # "in real terms" and "constant prices" are not the nominal level.
    # "real GDP" never reaches this: that phrase selects the chained series.
    if series_id == "GDP" and _names_real_level(decomp):
        return SourceResult(source_name="FRED", match_type="no_data")
    # "in 2015 prices" and "in 2017 US dollars" are a different level.
    # "at 2023 prices" in 2023 stays the current-dollar series.
    if series_id == "GDP" and _names_other_price_year(decomp):
        return SourceResult(source_name="FRED", match_type="no_data")
    # Real GDP stays on GDPC1, including when the sentence names the
    # chain year. These two are the nominal level only.
    if series_id == "GDP" and (
            _names_prior_year_prices(decomp) or _names_chain_volume(decomp)):
        return SourceResult(source_name="FRED", match_type="no_data")
    if series_id in ("GDP", "GDPC1") and (
            _BASIC_OR_FACTOR_RE.search(_basis_text(decomp))):
        return SourceResult(source_name="FRED", match_type="no_data")
    if series_id in ("GDP", "GDPC1") and _not_the_national_product(decomp):
        return SourceResult(source_name="FRED", match_type="no_data")
    # "CPI excluding shelter was" is not headline CPI, and "GDP excluding
    # agriculture was" is not the national total. A basket in this clause
    # after the figure is the same exclusion. The next clause counts only
    # when it is a basket exclusion and nothing else.
    if series_id in (
            "GDP", "GDPC1", "CPIAUCNS", "CPILFENS", "PCEPI", "PCEPILFE"
            ) and _exclusion_before_figure(decomp):
        return SourceResult(source_name="FRED", match_type="no_data")
    if series_id in ("GDP", "GDPC1") and (
            _level_is_a_change(decomp) or _output_per_job(decomp)
            or _calendar_or_working_day(decomp)):
        return SourceResult(source_name="FRED", match_type="no_data")
    # A working-day adjustment is not the unadjusted CPI headline.
    # Seasonally adjusted inflation, including core CPI, is the other index.
    # Nominal GDP and unemployment are already seasonally adjusted.
    if series_id == "CPIAUCNS" and _calendar_or_working_day(decomp):
        return SourceResult(source_name="FRED", match_type="no_data")
    if series_id in ("CPIAUCNS", "CPILFENS") and _seasonally_adjusted_inflation(decomp):
        return SourceResult(source_name="FRED", match_type="no_data")
    if series_id in (
            "GDP", "GDPC1", "CPIAUCNS", "CPILFENS", "UNRATE",
            "PCEPI", "PCEPILFE") and _figure_year_is_fiscal(decomp):
        return SourceResult(source_name="FRED", match_type="no_data")
    if is_rate and _figure_is_in_points(decomp):
        return SourceResult(source_name="FRED", match_type="no_data")
    # "CPI for food" and "inflation expectations" are not headline CPI.
    # The check is this figure's clause, so the headline beside them stays.
    if series_id == "CPIAUCNS" and (
            _component_of_headline_prices(_inflation_text(decomp))
            or _leading_price_component(decomp)
            or _adjacent_price_line(decomp)
            or _bare_price_category(decomp)
            or _price_for_the_line(decomp)
            or _price_category_on_figure(decomp)
            or _EXPECTED_INFLATION_RE.search(_figure_own_clause(decomp))):
        return SourceResult(source_name="FRED", match_type="no_data")
    # Core CPI is not a component of the headline. A hospital category,
    # or inflation for the hospital, is still a different line.
    if series_id == "CPILFENS" and (
            _bare_price_category(decomp) or _price_for_the_line(decomp)
            or _price_category_on_figure(decomp)):
        return SourceResult(source_name="FRED", match_type="no_data")
    # PCE is already seasonally adjusted, so that phrase stays. A hospital
    # line is still a different index, including core PCE.
    if series_id in ("PCEPI", "PCEPILFE") and (
            _bare_price_category(decomp) or _price_for_the_line(decomp)
            or _price_category_on_figure(decomp)):
        return SourceResult(source_name="FRED", match_type="no_data")

    year_match = re.search(r'20[0-3]\d', decomp.time_period or "")
    # A fiscal label earlier in the sentence can be the year the parser
    # kept. This series uses the calendar year written on the figure.
    calendar = _calendar_year_beside_a_fiscal_label(decomp)
    if calendar:
        year_match = re.match(r"20[0-3]\d", calendar)
    raw_text = str(decomp.raw_value)
    # Basis points are a change or a restatement; they are not the rate.
    if re.search(r'basis\s+points?|\bbps?\b', decomp.sentence[
            decomp.sentence.find(raw_text.strip()):][:len(raw_text) + 20], re.IGNORECASE):
        return SourceResult(source_name="FRED", match_type="no_data")
    span = re.search(r'(\d+(?:\.\d+)?)\s*%?\s*(?:-|to|\u2013)\s*(\d+(?:\.\d+)?)\s*%', raw_text)
    at = decomp.sentence.find(raw_text.strip())
    if not span and at >= 0:
        # One end of a range the sentence states: "a target range of 5.25% to
        # 5.50%" split into two figures is still a range.
        span = next((m for m in _FRED_RANGE_RE.finditer(decomp.sentence)
                     if m.start() <= at < m.end()), None)
    # The period cue nearest the figure decides: "5.33% through August 2024,
    # then 4.48% by December 2024" puts 4.48 in December; "3.6% in December
    # 2019 and averaged 3.7% for the year" makes 3.7 the year's average.
    full = decomp.full_sentence or decomp.sentence
    cue = _fred_period_cue(decomp.sentence, at, raw_text.strip())
    if not cue and full != decomp.sentence:
        cue = _fred_period_cue(full, full.find(raw_text.strip()), raw_text.strip())
    # "0.8% from December 2013 to December 2014" is the change to the later
    # month: December 2014's figure against a year earlier.
    span_to = at >= 0 and re.match(
        r'[^.;]{0,15}?\bfrom\s+(' + _MONTH_ALT + r')\s+(20[0-3]\d)\s+(?:to|through)\s+'
        r'(' + _MONTH_ALT + r')\s+(20[0-3]\d)\b',
        decomp.sentence[at + len(raw_text.strip()):], re.IGNORECASE)
    if span_to:
        if (span_to.group(1).lower() != span_to.group(3).lower()
                or int(span_to.group(4)) - int(span_to.group(2)) != 1):
            # "averaged 5.0% from January 2010 to December 2012" is no one
            # month's figure, and no annual average either.
            return SourceResult(source_name="FRED", match_type="no_data")
        cue = ("month", span_to.group(3).capitalize(), span_to.group(4))
    year = year_match.group() if year_match else None
    month, year_end, annual = None, False, False
    if not cue and decomp.doc_says_averages:
        cue = ("annual", None, None)
    if cue:
        kind, name, cue_year = cue
        if kind == "annual":
            annual = True
        elif cue_year or year:
            # "up 7.0% in December" is December of the figure's own year.
            month = (name, cue_year or year)
            # "Core CPI ended 2023 at 3.9%" is December's figure, but the last
            # day may differ from December's average: it can confirm, not refute.
            year_end = kind == "year_end"
            # "from 6.7% a year earlier" is the month a year before.
            # Only when the figure is that base: "up 2.1% in December 2016 from a
            # year earlier" is December 2016's change, not December 2015's (v18).
            if cue_year and at >= 0 and re.search(
                    r'\b(?:from|compared\s+(?:with|to)|versus|vs\.?)\s+(?:about\s+|around\s+|roughly\s+)?$',
                    decomp.sentence[max(0, at - 30):at]) and re.match(
                    r'[^.;]{0,25}?\ba\s+year\s+(?:earlier|before|ago)\b',
                    decomp.sentence[at + len(raw_text.strip()):]):
                month = (name, str(int(cue_year) - 1))
    # A figure for part of the year ("reached 7.79% that same month") is not
    # refuted by the year's average.
    part_of_year = year_end or bool(_FRED_PART_OF_YEAR_RE.search(full))
    # A peak or a record low is one week's or one day's figure: no average
    # refutes it. "topping out at 4.94% in November".
    extreme = at >= 0 and bool(_FRED_EXTREME_RE.search(
        decomp.sentence[max(0, at - 45):at]))
    # No cue: "the PCE price index rose 5.8%" may be December's rate or the
    # year's average; either confirms it, and only missing both refutes it.
    either = is_rate and not month and not annual and bool(year)
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json", **extra}
    if month:
        first = f"{month[1]}-{_MONTH_NUMBERS[month[0]]:02d}-01"
        params.update(frequency="m", observation_start=first, observation_end=first)
    else:
        params.setdefault("aggregation_method", "avg")
        params["frequency"] = "a"
        if year_match:
            target = int(year_match.group())
            params.update(observation_start=f"{target - 2}-01-01",
                          observation_end=f"{target + 2}-12-31")
        else:
            now = datetime.date.today().year
            params.update(observation_start=f"{now - 2}-01-01",
                          observation_end=f"{now}-12-31")
    data = _fetch_json(
        "https://api.stlouisfed.org/fred/series/observations?"
        + urllib.parse.urlencode(params)
    )
    rows = [
        (o["date"], float(o["value"]) * scale)
        for o in (data or {}).get("observations", [])
        if o.get("value") not in (None, "", ".")
    ]
    if not rows:
        return SourceResult(source_name="FRED", match_type="no_data")

    if month:
        own = rows[0]
        others = []
    elif year_match:
        named = [r for r in rows if r[0].startswith(year_match.group())]
        if not named:
            return SourceResult(source_name="FRED", match_type="no_data")
        own = named[0]
        others = [r for r in rows if r is not own]
    else:
        own = rows[-1]
        others = []

    if span and is_rate:
        # A target range: a rate inside it confirms; outside, the range may be
        # a target rather than the effective rate, so it proves nothing.
        low, high = sorted((float(span.group(1)), float(span.group(2))))
        inside = low - 0.005 <= own[1] <= high + 0.005
        if inside and _figure_states_another_measure(decomp, spec[0]):
            return SourceResult(source_name="FRED", match_type="no_data")
        return SourceResult(
            source_name="FRED",
            source_url=f"https://fred.stlouisfed.org/series/{series_id}",
            source_value=own[1],
            source_text=f"{series_id} {own[0][:7]}: {own[1]:,.2f} {unit_desc}",
            match_type="close" if inside else "no_data",
            confidence=0.8 if inside else 0.0,
        )

    def gap(value):
        if is_rate:
            return abs(value - decomp.value)
        return abs(value - decomp.value) / max(abs(decomp.value), 1e-10)

    room = _rate_room(decomp.raw_value) if is_rate else max(0.02, _rounding_room(decomp.raw_value))
    if is_rate and not month:
        # FRED's computed annual average carries its rounding: the annual average of UNRATE
        # for 2021 comes back as 5.4 (the mean is 5.35), so "averaged 5.3%" is a
        # match at both figures' precision (v18). A month's figure is the
        # published one, exact as it stands.
        shown_digits = repr(round(float(own[1]), 6)).split(".")
        decimals = len(shown_digits[1].rstrip("0")) if len(shown_digits) > 1 else 0
        if decimals <= 1:
            room += 0.5 * 10 ** -max(decimals, 1) + 1e-9  # 5.4 - 5.3 is 0.1000000000000005
    diff = gap(own[1])
    if either and diff > room:
        december = _fred_december(params, year, scale)
        if december and gap(december[1]) <= room:
            own, diff, month = december, gap(december[1]), ("December", year)
    stale = [r[0][:4] for r in others if gap(r[1]) <= room]
    if diff <= room:
        # Inside rounding used to tick before the series was checked, so a
        # union share in an inflation sentence matched CPI. A later reading
        # of the same series still matches. A clause that states its own
        # measure does not.
        if _figure_states_another_measure(decomp, spec[0]):
            return SourceResult(source_name="FRED", match_type="no_data")
        match_type = "exact" if diff <= room / 2 else "close"
    elif not year_match and not month:
        # With no period named, another year may be the one meant.
        match_type = "no_data"
    elif part_of_year and (year_end or not month):
        match_type = "no_data"
    elif extreme:
        match_type = "no_data"
    elif (decomp.year_inherited and not _YEAR_REFERENCE_RE.search(decomp.sentence)
          and any(gap(r[1]) <= 2 * room for r in others)):
        match_type = "no_data"
    elif not is_rate and diff < max(0.05, 2 * room):
        match_type = "no_data"
    elif not is_rate and not 0.25 <= own[1] / decomp.value <= 4:
        # Orders of magnitude off is another economy or a misread scale.
        match_type = "no_data"
    elif not _fred_names_series(decomp, spec):
        # The rule every refuting source shares: the figure's own clause names
        # this measure and no other (or its sentence is about this one alone).
        match_type = "no_data"
    elif _trailing_year_differs(decomp):
        # "peaked at 7.0 percent in June 2022 and had come down to around 2.5
        # percent by late 2024": the words after it name its year (v18). A year
        # stated once for two figures ("averaged 4.6% for 2024, and the mortgage
        # rate averaged 4.21%") still covers both.
        match_type = "no_data"
    elif year_match and own[0][:4] != year_match.group():
        # The period compared is not the claim's year: "around 2.5 percent by late
        # 2024" was compared with June 2022, another figure's month (v18).
        match_type = "no_data"
    elif decomp.doc_no_country and not _fred_us_stated(decomp):
        # A document that names no country may be about any: confirm only.
        match_type = "no_data"
    else:
        match_type = "contradicted"

    shown = own[1] / scale
    period = own[0][:7] if month else own[0][:4]
    text = f"{series_id} {period}: {shown:,.2f} {unit_desc}"
    if match_type == "contradicted" and stale:
        text += f". That is the {stale[-1]} figure."
    return _hold_unearned_refute(SourceResult(
        source_name="FRED",
        source_url=f"https://fred.stlouisfed.org/series/{series_id}",
        source_value=own[1],
        source_text=text,
        match_type=match_type,
        difference_pct=round(
            (abs(own[1] - decomp.value) / max(abs(decomp.value), 1e-10)) * 100, 1),
        confidence=0.95 if match_type == "exact" else 0.85,
    ))


# ── Wikidata (structured measurements) ──

_WIKIDATA_API = "https://www.wikidata.org/w/api.php"
# Wikidata unit item -> (dimension, factor to the base unit).
_WD_UNITS = {
    "Q11573": ("m", 1.0), "Q828224": ("m", 1000.0), "Q174728": ("m", 0.01),
    "Q3710": ("m", 0.3048), "Q253276": ("m", 1609.344), "Q482798": ("m", 0.9144),
    "Q712226": ("m2", 1e6), "Q25343": ("m2", 1.0), "Q232291": ("m2", 2589988.110336),
    "Q35852": ("m2", 1e4), "Q81292": ("m2", 4046.8564224), "Q857027": ("m2", 0.09290304),
    "Q11570": ("kg", 1.0), "Q191118": ("kg", 1000.0), "Q100995": ("kg", 0.45359237),
}
# A claim's unit family -> (dimension, factor, name for messages).
_UNIT_FAMILY_BASE = {
    "km": ("m", 1000.0, "kilometres"), "m": ("m", 1.0, "metres"),
    "cm": ("m", 0.01, "centimetres"), "ft": ("m", 0.3048, "feet"),
    "mi": ("m", 1609.344, "miles"), "yd": ("m", 0.9144, "yards"),
    "fathom": ("m", 1.8288, "fathoms"),
    "km2": ("m2", 1e6, "square kilometres"), "m2": ("m2", 1.0, "square metres"),
    "mi2": ("m2", 2589988.110336, "square miles"), "ft2": ("m2", 0.09290304, "square feet"),
    "kg": ("kg", 1.0, "kilograms"), "t": ("kg", 1000.0, "tonnes"), "lb": ("kg", 0.45359237, "pounds"),
}
_WD_METRIC_PROPERTIES = {
    # Height counts elevation too: a mountain's height is its elevation.
    "height": ("P2048", "P2044"), "length": ("P2043",), "area": ("P2046",),
    "weight": ("P2067",), "population": ("P1082",), "employees": ("P1128",),
}
_WD_COUNTS = frozenset({"population", "employees"})
# Definitions differ between sources for lakes, rivers and coastlines, so a
# measurement has to be this far off before it is called wrong.
_WD_REFUTE_GAP = 0.15


_DEPTH_RE = re.compile(r'\b(?:depths?|deep(?:er|est)?)\b', re.IGNORECASE)


# Wikidata's height of a tower runs to the tip; the roof, the top floor or the
# deck is lower and has no value of its own there.
_BELOW_TIP_RE = re.compile(
    r'\b(?:roof|top\s+floor|occupied|observation|deck)\b', re.IGNORECASE,
)
# Which point a tower's height runs to. Wikidata's single height runs to the
# roof for some towers (Willis, 442 m) and to the tip for others (Burj, 828 m),
# so it confirms none of these.
_HEIGHT_POINT_RE = re.compile(
    r'\b(roof|tip|spire|antenna|pinnacle|architectural|top\s+floor|occupied|'
    r'observation|deck)\b', re.IGNORECASE,
)


def _wd_properties(decomp):
    sentence = decomp.sentence.lower()
    # "a maximum depth of 1,332 feet" is neither a length nor a height.
    if decomp.metric in ("length", "height") and _DEPTH_RE.search(sentence):
        return ()
    # A bridge's "main span of 4,200 ft" is its longest span, not its length;
    # "a central span of 1,991 ft and a total length of 3,911 m" has both.
    if decomp.metric == "length" and re.search(
            r'\bspan\b', _figure_clause(decomp.sentence, decomp.raw_value)):
        return ("P2787",)
    # Wikidata's area is the total, water included; land area is another figure.
    if decomp.metric == "area" and re.search(r'\b(?:land|water)\s+area\b', sentence):
        return ()
    if decomp.metric == "diameter":
        if "radius" in sentence:
            return ("P2120",)
        if "diameter" in sentence:
            return ("P2386",)
        return ()
    return _WD_METRIC_PROPERTIES.get(decomp.metric, ())


def _claim_unit_family(decomp):
    """The unit written after the claim's own figure."""
    sentence = decomp.sentence
    raw = str(decomp.raw_value).strip()
    at = sentence.find(raw) if raw else -1
    if at >= 0:
        after = re.sub(
            r'^\s*(?:thousand|million|billion)\b', '', sentence[at + len(raw):],
            flags=re.IGNORECASE,
        )
        own = _UNIT_AFTER_NUMBER_RE.match(after)
        if own:
            return _unit_family(own.group(1))
    return ""


def _wikidata_applies(decomp):
    if not decomp.subject or not _wd_properties(decomp):
        return False
    # The World Bank answers a country's population, and a filing a company's.
    if decomp.metric == "population" and _COUNTRY_NAMES_RE.fullmatch(decomp.subject):
        return False
    return True


# Subject -> (candidate ids, entities). A document names the same thing in
# several sentences, and Wikidata rate-limits searches. Only successful
# lookups are kept, so a timeout is retried next time.
_WIKIDATA_CACHE = {}
_WIKIDATA_CACHE_LIMIT = 512
_WIKIDATA_CACHE_LOCK = threading.Lock()


def _wikidata_lookup(subject):
    key = subject.lower()
    with _WIKIDATA_CACHE_LOCK:
        if key in _WIKIDATA_CACHE:
            return _WIKIDATA_CACHE[key]
    found = _fetch_json(
        f"{_WIKIDATA_API}?" + urllib.parse.urlencode({
            "action": "wbsearchentities", "search": subject, "language": "en",
            "type": "item", "limit": 5, "format": "json",
        })
    )
    if found is None:
        return [], {}
    ids = [hit["id"] for hit in found.get("search", [])][:5]
    entities = {}
    if ids:
        fetched = _fetch_json(
            f"{_WIKIDATA_API}?" + urllib.parse.urlencode({
                "action": "wbgetentities", "ids": "|".join(ids),
                "props": "claims|labels|aliases", "languages": "en", "format": "json",
            })
        )
        if fetched is None:
            return ids, {}
        entities = fetched.get("entities", {})
    with _WIKIDATA_CACHE_LOCK:
        if len(_WIKIDATA_CACHE) >= _WIKIDATA_CACHE_LIMIT:
            _WIKIDATA_CACHE.clear()
        _WIKIDATA_CACHE[key] = (ids, entities)
    return ids, entities


def _wd_year(statement):
    for qualifier in statement.get("qualifiers", {}).get("P585", []):
        time = qualifier.get("datavalue", {}).get("value", {}).get("time", "")
        found = re.match(r'[+-]?(\d{4})', time)
        if found:
            return int(found.group(1))
    return None


def verify_wikidata(decomp):
    """Measurements, city populations and headcounts against Wikidata's
    typed values, converted to the claim's unit."""
    properties = _wd_properties(decomp)
    if _is_subgroup_count(decomp):
        return SourceResult(source_name="Wikidata", match_type="no_data")
    subject = re.sub(r'^(?:The|A|An)\s+', '', decomp.subject or "")
    # "Willis Tower (Chicago)": the aside is not part of the name.
    subject = re.sub(r'\s*\([^)]*\)', '', subject).strip()
    if not properties or not subject or not decomp.value:
        return SourceResult(source_name="Wikidata", match_type="no_data")
    is_count = decomp.metric in _WD_COUNTS
    family = "" if is_count else _claim_unit_family(decomp)
    if not is_count and family not in _UNIT_FAMILY_BASE:
        return SourceResult(source_name="Wikidata", match_type="no_data")
    if is_count:
        dimension, claim_base = None, decomp.value
    else:
        dimension, factor, _ = _UNIT_FAMILY_BASE[family]
        claim_base = decomp.value * factor

    ids, entities = _wikidata_lookup(subject)
    if not ids:
        return SourceResult(source_name="Wikidata", match_type="no_data")

    # The first match that holds the property, preferring one named exactly:
    # "Mercury" the element has no radius.
    chosen, named = None, False
    for qid in ids:
        entity = entities.get(qid) or {}
        statements = [
            st for prop in properties
            for st in entity.get("claims", {}).get(prop, [])
            if st.get("rank") != "deprecated"
        ]
        if not statements:
            continue
        names = {entity.get("labels", {}).get("en", {}).get("value", "").lower()}
        names |= {a.get("value", "").lower() for a in entity.get("aliases", {}).get("en", [])}
        exact = subject.lower() in names
        if chosen is None or (exact and not named):
            chosen, named = (qid, entity, statements), exact
        if exact:
            break
    if not chosen:
        return SourceResult(source_name="Wikidata", match_type="no_data")
    qid, entity, statements = chosen

    values = []
    for statement in statements:
        value = statement.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        try:
            amount = float(str(value.get("amount", "")).lstrip("+"))
        except ValueError:
            continue
        if is_count:
            values.append((amount, _wd_year(statement)))
            continue
        unit = _WD_UNITS.get(str(value.get("unit", "")).rsplit("/", 1)[-1])
        if unit and unit[0] == dimension:
            values.append((amount * unit[1], None))
    if not values:
        return SourceResult(source_name="Wikidata", match_type="no_data")

    year_match = re.search(r'20[0-3]\d|19\d\d', decomp.time_period or "")
    # Refuting needs the thing named in this very sentence: "Ganymede: radius
    # of 2,631 km" was once checked against Pluto from the line before.
    # Named in its own sentence, it is not the ambiguous inherited kind.
    in_sentence = bool(re.search(
        r'(?<!\w)' + re.escape(subject) + r'(?!\w)', decomp.sentence, re.IGNORECASE,
    ))
    can_refute = named and not is_count and in_sentence
    same_year = False
    pool = values
    if is_count:
        dated = [v for v in values if v[1]]
        if year_match and dated:
            same = [v for v in dated if v[1] == int(year_match.group())]
            if same:
                pool, can_refute = same, named and in_sentence
                same_year = True
            else:
                nearest = min(dated, key=lambda v: abs(v[1] - int(year_match.group())))
                pool = [nearest]
        elif dated:
            latest = max(v[1] for v in dated)
            pool = [v for v in dated if v[1] == latest]

    def gap(value):
        return abs(value - claim_base) / max(abs(claim_base), 1e-10)

    best = min(pool, key=lambda v: gap(v[0]))
    diff = gap(best[0])
    # A count for the year it names, or a measurement, is as precise as it is
    # written: "2.79 million" in 2021 is not 2,751,862.
    room = max(0.005 if (same_year or not is_count) else 0.02,
               _rounding_room(decomp.raw_value))
    stated = _rounding_room(decomp.raw_value)
    if (not is_count and stated < 0.001 and max(0.001, 3 * stated) <= diff < room
            and not _hedged(decomp.sentence, decomp.raw_value)):
        # "4,487 m" is stated to the metre. Surveys differ by a few metres
        # (Mont Blanc 4,808 against 4,805.6), not by nine: that is a slip
        # (the Matterhorn is 4,478). Too close to refute, too far to confirm.
        match_type = "no_data"
    elif diff < 0.005:
        match_type = "exact"
    elif diff < room:
        match_type = "close"
    elif (diff > _WD_REFUTE_GAP and can_refute
          and 0.25 <= best[0] / claim_base <= 4):
        # Beyond the largest unit slip (feet for metres is 3.3x), a gap means
        # another thing was measured: Peru's area for Lake Titicaca's.
        match_type = "contradicted"
    else:
        match_type = "no_data"
    if match_type == "contradicted" and not _wd_names_metric(decomp):
        # The rule SEC and World Bank refutations follow (v17): the figure's own
        # words name the measure compared.
        match_type = "no_data"
    # A roof is below the tip Wikidata measures, and seldom below half of it:
    # the tip cannot confirm a roof, only refute one far outside that range.
    silent = False
    if decomp.metric == "height" and _HEIGHT_POINT_RE.search(decomp.sentence):
        # Roof and tip differ by up to half the height (the Burj's spire is
        # 29% of it); only a gap past that range, like a unit slip, refutes.
        if match_type in ("exact", "close") or 0.5 <= claim_base / best[0] <= 2.0:
            match_type, silent = "no_data", True
    if match_type in ("exact", "close") and (
        not in_sentence or not _wd_names_metric(decomp)
        or _figure_states_another_measure(
            decomp, _WD_METRIC_WORDS.get(decomp.metric or "", ""))
    ):
        # A tick needs the figure's own words to name this thing and this
        # measure. "Ganymede: radius of 1,188 km" against Pluto, a length
        # that shares a mountain's elevation, or a count beside a height,
        # was not compared.
        return SourceResult(source_name="Wikidata", match_type="no_data")

    label = entity.get("labels", {}).get("en", {}).get("value", subject)
    if is_count:
        shown = f"{best[0]:,.0f}" + (f" ({best[1]})" if best[1] else "")
    else:
        shown = f"{best[0] / factor:,.1f} {_UNIT_FAMILY_BASE[family][2]}"
    text = f"{label} on Wikidata: {shown}"
    if match_type == "contradicted" and not is_count:
        for other, (dim, other_factor, other_name) in _UNIT_FAMILY_BASE.items():
            if dim == dimension and other != family and any(
                abs(decomp.value * other_factor - v[0]) / max(v[0], 1e-10) < 0.01
                for v in pool
            ):
                text += f". The figure is right in {other_name}, not {_UNIT_FAMILY_BASE[family][2]}."
                break
    return _hold_unearned_refute(SourceResult(
        source_name="Wikidata",
        source_url=f"https://www.wikidata.org/wiki/{qid}",
        source_value=best[0],
        source_text=text,
        match_type=match_type,
        difference_pct=round(diff * 100, 1),
        confidence=0.85 if match_type == "exact" else 0.75,
        disagrees=match_type == "no_data" and not silent,
    ))


# ── Alpha Vantage (company financials) ──

def _resolve_ticker(company_name):
    """Resolve a company name to a stock ticker via Alpha Vantage search."""
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    if not api_key or not company_name:
        return None

    url = (
        f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH"
        f"&keywords={urllib.parse.quote(company_name)}&apikey={api_key}"
    )
    data = _fetch_json(url)
    if not data or "bestMatches" not in data or not data["bestMatches"]:
        return None

    return data["bestMatches"][0].get("1. symbol")


def verify_alpha_vantage(decomp):
    """Verify company financial claims against Alpha Vantage."""
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    if not api_key:
        return SourceResult(source_name="Alpha Vantage", match_type="no_data")

    # Need a company name to look up
    subject = decomp.subject
    if not subject:
        return SourceResult(source_name="Alpha Vantage", match_type="no_data")

    # OVERVIEW only carries current figures, so it can speak to a claim
    # that names one of them and no period. Net income is deliberately
    # absent: the closest field here is gross profit, a different number.
    metrics = {
        "revenue": ("RevenueTTM", "Revenue TTM"),
        "market_cap": ("MarketCapitalization", "Market Cap"),
        "price": ("AnalystTargetPrice", "Target Price"),
    }
    if decomp.time_period or decomp.metric not in metrics:
        return SourceResult(source_name="Alpha Vantage", match_type="no_data")

    # Resolve to ticker
    ticker = _resolve_ticker(subject)
    if not ticker:
        return SourceResult(source_name="Alpha Vantage", match_type="no_data")

    # Get company overview (revenue, market cap, etc.)
    url = (
        f"https://www.alphavantage.co/query?function=OVERVIEW"
        f"&symbol={ticker}&apikey={api_key}"
    )
    data = _fetch_json(url)
    if not data or "Note" in data or "Symbol" not in data:
        return SourceResult(source_name="Alpha Vantage", match_type="no_data")

    # Only the metric the claim names. Trying every field would "verify"
    # a market cap claim against revenue when the digits happen to agree.
    for field_name, label in (metrics[decomp.metric],):
        if field_name not in data or data[field_name] in ("None", "0", ""):
            continue
        try:
            source_val = float(data[field_name])
        except (ValueError, TypeError):
            continue
        if source_val == 0:
            continue

        diff = abs(source_val - decomp.value) / max(abs(decomp.value), 1e-10)
        if diff < 0.05:
            match_type = "exact" if diff < 0.01 else "close"
            return SourceResult(
                source_name="Alpha Vantage",
                source_url=f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}",
                source_value=source_val,
                source_text=f"{ticker} {label}: ${source_val:,.0f}",
                match_type=match_type,
                difference_pct=round(diff * 100, 1),
                confidence=0.9 if match_type == "exact" else 0.75,
            )

    return SourceResult(
        source_name="Alpha Vantage",
        source_url=f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}",
        source_text=f"{ticker}: found but no matching metric",
        match_type="no_data",
    )


# ── Wolfram Alpha (computational/physical facts) ──

def verify_wolfram(decomp):
    """Verify computational or physical facts against Wolfram Alpha."""
    app_id = os.environ.get("WOLFRAM_APP_ID", "")
    if not app_id:
        return SourceResult(source_name="Wolfram Alpha", match_type="no_data")

    # Build a query from the subject + metric
    query_parts = []
    if decomp.subject:
        query_parts.append(decomp.subject)
    if decomp.metric and decomp.metric not in ("count",):
        query_parts.append(decomp.metric)

    if not query_parts:
        return SourceResult(source_name="Wolfram Alpha", match_type="no_data")

    query = " ".join(query_parts)
    url = (
        f"https://api.wolframalpha.com/v2/result"
        f"?appid={app_id}&i={urllib.parse.quote(query)}"
    )

    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        # Caller-side deadline + per-op timeout. The except below
        # catches both _FuturesTimeoutError (deadline) and any urlopen
        # error (HTTPError, URLError, etc.) and returns no_data; the
        # deadline-fired path also tags provider_health for /health
        # observability via _urlopen_with_deadline's auto-tracking.
        result = _urlopen_with_deadline(req, per_op_timeout=_TIMEOUT).decode()
    except Exception:
        return SourceResult(source_name="Wolfram Alpha", match_type="no_data")

    if not result or "did not understand" in result.lower():
        return SourceResult(source_name="Wolfram Alpha", match_type="no_data")

    # Extract numbers from the Wolfram response
    matched_val, context, confidence = _match_in_text(
        result, decomp.value, decomp.sentence, decomp=decomp
    )

    if matched_val is None:
        # Also try raw float match
        raw_float = 0.0
        try:
            raw_cleaned = decomp.raw_value.strip().lstrip("$~").rstrip("%")
            raw_cleaned = re.sub(r'[TBMKk]$', '', raw_cleaned).replace(",", "")
            raw_float = float(raw_cleaned)
        except (ValueError, AttributeError):
            pass
        if raw_float and raw_float != decomp.value:
            matched_val, context, confidence = _match_in_text(
                result, raw_float, decomp.sentence, decomp=decomp
            )

    if matched_val is None:
        return SourceResult(
            source_name="Wolfram Alpha",
            source_text=f"Response: {result[:120]}",
            match_type="no_data",
        )

    compare_val = decomp.value
    diff = abs(matched_val - compare_val) / max(abs(compare_val), 1e-10)
    match_type = "exact" if diff < 0.01 else "close" if diff < 0.05 else "contradicted"

    return _hold_unearned_refute(SourceResult(
        source_name="Wolfram Alpha",
        source_url="https://www.wolframalpha.com/input?i=" + urllib.parse.quote(query),
        source_value=matched_val,
        source_text=f"Wolfram: {result[:150]}",
        match_type=match_type,
        difference_pct=round(diff * 100, 1),
        confidence=0.9 if match_type == "exact" else 0.75,
    ))


# ── SEC EDGAR (definitive US company financials from regulatory filings) ──

# Cache the company tickers file (loaded once, ~2MB).
# Protected by _SEC_TICKERS_LOCK because verify_sec_edgar runs
# on a ThreadPoolExecutor (source_network.py:2477) and multiple
# threads can call _get_sec_tickers concurrently on the first
# request. Without the lock, thread A could be mid-populate
# (entries A through M inserted) while thread B reads the
# partially-filled dict and falsely classifies a ticker N-Z as
# "not found in SEC". After initialization the lock is never
# contended because the fast path short-circuits on the
# `is not None` check before acquiring.
_SEC_TICKERS = None
_SEC_TICKERS_LOCK = threading.Lock()
_SEC_TICKERS_FAIL_AT = 0.0
# How long to skip retry after a failed tickers download. Operator-
# overridable via SN_SEC_TICKERS_RETRY_AFTER_SECONDS. The default
# balances two costs: too-short retries hammer SEC after a flaky
# cold-start, too-long retries lock SEC verification out of the
# worker for an excessive window after the upstream recovers. 60s
# is a long-enough cool-down to absorb a typical CDN hiccup and a
# short-enough one that the operator does not see "0 verified" on
# repeated user requests after the network heals.
_SEC_TICKERS_RETRY_AFTER = float(
    os.environ.get("SN_SEC_TICKERS_RETRY_AFTER_SECONDS", "60")
)
_SEC_HEADERS = {"User-Agent": "FrameCheck/1.0 (hello@clarethium.com)"}


def _get_sec_tickers():
    """Load SEC company tickers (cached after first call).

    Thread-safe: the first caller holds _SEC_TICKERS_LOCK while
    fetching and populating the dict. Subsequent callers see the
    fully populated dict without hitting the lock.

    Returns a tuple of (titles_dict, tickers_dict). Tickers and
    titles must be kept in separate dicts because tickers are
    matched exactly (case-insensitive) while titles are matched
    by substring. Mixing them would let single-letter tickers like
    "V" (Visa) or "F" (Ford) substring-match any subject containing
    that letter, causing wildly wrong CIK lookups.

    Failure handling: if the tickers file fetch raises (cold-start
    8s deadline blown, SEC CDN timeout, network unreachable), we do
    NOT poison _SEC_TICKERS with an empty tuple. The previous shape
    cached the empty result for the life of the worker, locking SEC
    verification out of every subsequent request. The current shape
    leaves _SEC_TICKERS as None and records the failure timestamp;
    callers within the retry-after window get an empty tuple without
    a fresh fetch attempt, callers past the window retry. SEC
    verification can recover within one cool-down window of an
    upstream recovery.
    """
    global _SEC_TICKERS, _SEC_TICKERS_FAIL_AT
    if _SEC_TICKERS is not None:
        return _SEC_TICKERS
    if _SEC_TICKERS_FAIL_AT and (
        time.time() - _SEC_TICKERS_FAIL_AT
    ) < _SEC_TICKERS_RETRY_AFTER:
        return ({}, {})
    with _SEC_TICKERS_LOCK:
        # Double-check after acquiring the lock: another thread
        # may have populated or failed while we waited.
        if _SEC_TICKERS is not None:
            return _SEC_TICKERS
        if _SEC_TICKERS_FAIL_AT and (
            time.time() - _SEC_TICKERS_FAIL_AT
        ) < _SEC_TICKERS_RETRY_AFTER:
            return ({}, {})

        # Bundled-file primary path (since 2026-05-06). Production
        # observation: Fly ORD egress to www.sec.gov is too slow to
        # download the ~10MB tickers file within the caller-side
        # deadline (>71s read times observed). The Dockerfile bakes
        # the file into the image at /app/data/sec_company_tickers.json
        # during build (Fly's builder has different network paths
        # and the build is one-time-per-deploy). Reading the bundled
        # file makes SEC verification work on prod cold-start without
        # any network call. Updates land via redeploys; SEC ticker
        # churn is roughly weekly so a daily-to-weekly deploy cadence
        # keeps the cache acceptably fresh.
        bundled_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "sec_company_tickers.json",
        )
        data = None
        try:
            if os.path.isfile(bundled_path):
                with open(bundled_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"[source-network] bundled SEC tickers unreadable "
                f"({type(exc).__name__}: {exc}); falling back to "
                f"runtime fetch",
                file=sys.stderr,
            )

        try:
            if data is None:
                url = "https://www.sec.gov/files/company_tickers.json"
                req = urllib.request.Request(url, headers=_SEC_HEADERS)
                # SEC ticker file is ~10MB; per-op timeout 10s for
                # the download phase, total deadline at the module
                # default bounds the cold-start case where SEC's CDN
                # dribbles the response within the per-op window.
                # Reached only when the build-time bundle is missing
                # (see Dockerfile RUN curl block; --fail-with-body
                # exits the build on SEC error but skips the bundle
                # on transient curl failures).
                data = json.loads(
                    _urlopen_with_deadline(req, per_op_timeout=10)
                )
            # Build local dicts first, then assign to the global in
            # one shot so no reader ever sees a partial dict. The
            # global assignment itself is atomic in CPython
            # (GIL protects pointer swap).
            titles = {}
            ticker_index = {}
            for entry in data.values():
                title = entry.get("title", "").upper()
                cik = str(entry.get("cik_str", "")).zfill(10)
                ticker = entry.get("ticker", "")
                if title:
                    titles[title] = (cik, ticker)
                if ticker:
                    ticker_index[ticker.upper()] = (cik, ticker)
            _SEC_TICKERS = (titles, ticker_index)
            _SEC_TICKERS_FAIL_AT = 0.0
            return _SEC_TICKERS
        except Exception:
            _SEC_TICKERS_FAIL_AT = time.time()
            return ({}, {})


# Words of a results release's tables and headings, never a company alone.
_REPORT_WORDS = frozenset({
    "consolidated", "reported", "adjusted", "organic", "segment", "segments", "total",
    "operations", "operating", "homebuilding", "as", "net", "results", "quarter",
    "quarterly", "annual", "fiscal", "year", "full", "continuing", "discontinued",
    "corporate", "other", "and", "the", "of", "sales", "revenue", "revenues", "income",
})
_COMMON_NOUN_BLACKLIST = frozenset({
    # First words of several companies: which one is a guess, and a wrong
    # guess passes off another company's filings as this claim's check.
    "delta", "united", "american", "national", "general", "first", "chase",
    "johnson", "all", "one", "now", "key",
    # Common English nouns that title-case in headings ("Semiconductor",
    # "Technology", "Industry") but are not company names. Without
    # this gate the SEC ticker substring match (step 4 below) maps
    # them to whichever real company contains the noun in its title:
    # "SEMICONDUCTOR" -> "NXP SEMICONDUCTORS" / "LATTICE SEMICONDUCTOR"
    # / "SKYWORKS SOLUTIONS" depending on iteration order. The
    # resulting CIK lookup runs against a wrong entity and produces
    # either no match (best case) or a false-positive contradiction
    # (worst case, the wrong company's revenue). Discovered
    # 2026-05-06 on the NVIDIA example: "Semiconductor fabrication
    # costs ... $20 billion" classified subject="Semiconductor",
    # canonical="NXPI". Generic nouns return UNKNOWN earlier so the
    # pipeline can surface unverifiable instead of inventing a match.
    "semiconductor", "semiconductors", "technology", "technologies",
    "industry", "industries", "company", "companies", "corporation",
    "corporations", "group", "groups", "holdings", "service",
    "services", "financial", "bank", "banks", "manufacturing",
    "partners", "partnership", "international", "global", "regional", "investment", "investments", "capital", "fund",
    "funds", "trust", "ventures", "consulting", "solutions", "systems",
    "growth", "challenges", "outlook", "findings",
})


_CIK_MEMO = {}
_CIK_MEMO_OWNER = [None]
_CIK_MEMO_LOCK = threading.Lock()


def _find_cik(subject):
    """_find_cik_uncached, remembered per ticker list.

    The substring scan compiles a pattern per SEC title, which overflows re's
    cache: about 1.2 s a call, paid per claim and twice per identity figure (a
    14 s document on v11). The answer depends only on the subject and the
    ticker list, so it is kept until the list object changes.
    """
    cache = _get_sec_tickers()
    with _CIK_MEMO_LOCK:
        if _CIK_MEMO_OWNER[0] is not cache:
            _CIK_MEMO.clear()
            _CIK_MEMO_OWNER[0] = cache  # held, so a new list can never reuse its id
        if subject in _CIK_MEMO:
            return _CIK_MEMO[subject]
    found = _find_cik_uncached(subject)
    with _CIK_MEMO_LOCK:
        if len(_CIK_MEMO) >= 4096:
            _CIK_MEMO.clear()
        _CIK_MEMO[subject] = found
    return found


def _find_cik_uncached(subject):
    """Find SEC CIK for a company name or ticker.

    Lookup order:
      1. Exact ticker match (case-insensitive). Single-letter and
         short tickers are accepted only here, never via substring.
      2. Exact title match.
      3. Suffix-stripped exact title match (Apple -> APPLE INC).
      4. Substring match on titles, requiring at least 3 characters
         in the subject so common short words don't match arbitrary
         titles. Single-word subjects that match the common-noun
         blacklist short-circuit before the substring scan to prevent
         false-positive matches against real company titles that
         happen to contain the noun.
    """
    cache = _get_sec_tickers()
    if not cache:
        return None, None
    titles, ticker_index = cache
    if not subject:
        return None, None

    subject_upper = subject.upper().strip().rstrip(".").rstrip(",")

    # 1. Exact ticker match (handles "AAPL", "NVDA", "BRK.B" etc.)
    # As written, not case-folded: "Now" and "Key" are words, NOW and KEY are
    # tickers.
    if subject_upper in ticker_index and subject.strip() == subject_upper:
        return ticker_index[subject_upper]

    # SEC titles spell "COCA COLA CO" where prose says "Coca-Cola", and
    # "TRACTOR SUPPLY CO" where it says "Tractor Supply Company".
    subject_upper = re.sub(
        r'[,\s]+(?:COMPANY|CORPORATION|INCORPORATED|INC)$', '', subject_upper,
    )
    spellings = [subject_upper]
    if "-" in subject_upper:
        spellings.append(subject_upper.replace("-", " "))

    for spelling in spellings:
        # 2. Exact title match
        if spelling in titles:
            return titles[spelling]

        # 3. Try common suffixes for exact title match
        for suffix in [" INC", " CORP", " LTD", " LLC", " CO", " PLC",
                       " HOLDINGS", " GROUP"]:
            if spelling + suffix in titles:
                return titles[spelling + suffix]

    # 4. Substring match on titles only (never tickers). Require
    # at least 3 characters in the subject so we don't match
    # arbitrary single letters. Common-noun gate: a single-word
    # subject that is a generic English noun is not allowed to
    # substring-match a real company title; the false-positive cost
    # (wrong company's data passed off as the claim's subject)
    # outweighs the rare case where a common-noun-looking word is
    # actually a brand.
    if len(subject_upper) >= 3:
        is_single_word = " " not in subject_upper
        if is_single_word and subject_upper.lower() in _COMMON_NOUN_BLACKLIST:
            return None, None
        # "Financial Services", "As Reported", "Consolidated": words from a
        # results table, which a substring search turns into some company.
        words = re.findall(r"[a-z]+", subject_upper.lower())
        if words and all(w in _COMMON_NOUN_BLACKLIST or w in _REPORT_WORDS for w in words):
            return None, None
        # Whole words only, so "Ford" is not Oxford and "Meta" is not Metals.
        # The first hit wins: SEC lists companies by market value, so that is
        # the parent rather than a spinoff with a shorter name.
        # An optional S: "Lowe's" arrives as Lowe, and SEC lists LOWES.
        word = re.compile(r'\b' + re.escape(subject_upper) + r'S?\b')
        for title, (cik, ticker) in titles.items():
            if word.search(title) or (
                len(title) >= 3 and re.search(
                    r'\b' + re.escape(title) + r'\b', subject_upper,
                )
            ):
                return cik, ticker

    return None, None


# Revenue concept names in priority order (most common first)
_REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
]

# Metric -> XBRL concept mapping.
# Keys MUST match _METRIC_PATTERNS keys exactly (dict lookup, not substring).
_METRIC_CONCEPTS = {
    "eps": ["EarningsPerShareDiluted"],
    "operating_income": ["OperatingIncomeLoss"],
    "gross_profit": ["GrossProfit"],
    "research_development": ["ResearchAndDevelopmentExpense"],
    "revenue": _REVENUE_CONCEPTS,
    "profit": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "operating_expenses": ["OperatingExpenses", "CostsAndExpenses"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsAndShortTermInvestments"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "total_assets": ["Assets"],
    "stockholders_equity": ["StockholdersEquity"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "dividends_paid": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "inventory": ["InventoryNet"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
}


# Words broad enough to match inside a more specific figure: "earnings" in
# "earnings per share". Named figures have their own concept above.
_SEC_BROAD_METRICS = frozenset(
    {"revenue", "profit", "operating_expenses", "cash", "dividends_paid"}
)
_SEC_UNIT_KEYS = {"eps": "USD/shares"}
# Foreign private issuers file 20-F reports under IFRS, in their own currency
# (ASML and Ferrari in euros, Toyota in yen). Named with their taxonomy.
_IFRS_CONCEPTS = {
    "revenue": ["Revenue", "RevenueFromContractsWithCustomers"],
    "profit": ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"],
    "eps": ["DilutedEarningsPerShare"],
    "operating_income": ["ProfitLossFromOperatingActivities"],
    "gross_profit": ["GrossProfit"],
    "research_development": ["ResearchAndDevelopmentExpense"],
    "operating_cash_flow": ["CashFlowsFromUsedInOperatingActivities"],
    "total_assets": ["Assets"],
    "cash": ["CashAndCashEquivalents"],
    "stockholders_equity": ["EquityAttributableToOwnersOfParent"],
    "dividends_paid": ["DividendsPaidClassifiedAsFinancingActivities"],
    "capex": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"],
}
_CURRENCY_OF = (
    (re.compile(r'\u20ac|\bEUR\b|\beuros?\b', re.IGNORECASE), "EUR", "\u20ac"),
    (re.compile(r'\u00a3|\bGBP\b|\bpounds?\s+sterling\b', re.IGNORECASE), "GBP", "\u00a3"),
    (re.compile(r'\u00a5|\bJPY\b|\byen\b', re.IGNORECASE), "JPY", "\u00a5"),
    (re.compile(r'\bCHF\b|\bSwiss\s+francs?\b', re.IGNORECASE), "CHF", "CHF "),
)
_ANNUAL_FORMS = ("10-K", "20-F", "40-F")


_TWELVE_MONTH_RE = re.compile(
    r'\b(?:year[\s-]+on[\s-]+year|y/y|yoy|12-month|twelve-month|annual\s+rate\s+in)\b',
    re.IGNORECASE)
# "a $6.4 billion tax benefit" is one item inside net income, not net income.
_COMPONENT_AFTER_RE = re.compile(
    r'\s*(?:of\s+)?(?:one-time\s+|non-?cash\s+|pre-?tax\s+)?(?:tax\s+)?(?:benefits?|charges?|'
    r'gains?|impairments?|write-?(?:downs?|offs?)|settlements?|provisions?|reserves?|refunds?)\b',
    re.IGNORECASE)


_COMPONENT_BEFORE_RE = re.compile(
    r'\b(?:benefits?|charges?|gains?|impairments?|write-?(?:downs?|offs?)|settlements?|'
    r'refunds?|provisions?)\s+of\s+[^.;]*$|\bincluded\s+in\b[^.;]*$', re.IGNORECASE)
# Measures a results release states that no filed total is: "deferred
# revenue", "remaining performance obligations", bookings, billings, ARR.
_NOT_A_FILED_TOTAL_RE = re.compile(
    r'\b(?:deferred\s+revenues?|performance\s+obligations|RPO|backlog|bookings|billings|'
    r'ARR|annual(?:ized)?\s+recurring|recurring\s+revenues?)\b', re.IGNORECASE)
# "an average price of $228.76 per share" is a price, not earnings.
_SHARE_PRICE_RE = re.compile(
    r'\b(?:average|purchase|share|stock|offering|exercise|target|closing)\s+price\b|'
    r'\bprice\s+(?:of|per)\b|\brepurchas', re.IGNORECASE)
# "cash and cash equivalents, short-term investments and restricted cash"
_WIDER_CASH_RE = re.compile(
    r'\b(?:short-term\s+investments|marketable\s+securities|restricted\s+cash|'
    r'(?:total\s+)?liquidity)\b', re.IGNORECASE)
# Words before "revenue" that do not name a part of the company.
_REVENUE_QUALIFIERS = frozenset({
    "total", "net", "consolidated", "gaap", "reported", "organic", "operating", "fiscal",
    "full", "year", "quarter", "quarterly", "annual", "the", "its", "our", "company",
    "group", "first", "second", "third", "fourth", "record", "adjusted", "comparable",
    "highlights", "include", "q1", "q2", "q3", "q4", "fy", "and", "of", "for"})


def _names_a_segment(decomp):
    """"Management Solutions revenue" in a Paychex release names one segment."""
    head = _text_before_figure(decomp)
    found = re.findall(r"((?:[A-Z][\w&'\u2019()-]*\s+){1,4})(?:net\s+)?(?:revenues?|sales)\b", head)
    if not found:
        return False
    words = [re.sub(r"['\u2019]s$", "", w.lower().strip("()"))
             for w in re.split(r"[\s-]+", found[-1].strip()) if w]
    own = re.sub(r"['\u2019]s\b", "", (decomp.subject or "").lower())
    named = [w for w in words if w not in _REVENUE_QUALIFIERS and not re.search(r'\d', w)]
    return bool(named) and not any(w in own or own.split()[0:1] == [w] for w in named)


def _text_before_figure(decomp):
    """The sentence up to the figure, its last 120 characters."""
    raw = str(decomp.raw_value or "").strip()
    sentence = decomp.sentence or ""
    at = sentence.find(raw) if raw else -1
    return sentence[max(0, at - 120):at] if at >= 0 else sentence


def _claim_currency(decomp):
    """The currency a figure is written in: ("EUR", "\u20ac") for "\u20ac28.3 billion",
    "EUR 28.3 billion" or "28.3 billion euros"; ("USD", "$") otherwise. Only the
    figure's own symbol, a code right before it or a word right after it count:
    in "$28.3 billion, or \u20ac26 billion" the first figure is in dollars."""
    raw = str(decomp.raw_value or "").strip()
    sentence = decomp.sentence or ""
    at = sentence.find(raw) if raw else -1
    before = sentence[max(0, at - 5):at] if at >= 0 else ""
    after = sentence[at + len(raw):] if at >= 0 else ""
    after = re.sub(r'^\s*(?:thousand|million|billion|trillion|bn|mn)\b', '', after,
                   flags=re.IGNORECASE)
    if "$" in raw:
        return "USD", "$"
    if at < 0:
        # The figure cannot be placed: one currency named, and no dollars.
        named = [(code, symbol) for pattern, code, symbol in _CURRENCY_OF
                 if pattern.search(sentence)]
        return named[0] if len(named) == 1 and "$" not in sentence else ("USD", "$")
    for pattern, code, symbol in _CURRENCY_OF:
        if (pattern.search(raw) or pattern.search(before)
                or re.match(r'\s*(?:' + pattern.pattern + r')', after, re.IGNORECASE)):
            return code, symbol
    return "USD", "$"


_SEC_METRIC_LABELS = {
    "profit": "net income", "eps": "diluted EPS",
    "research_development": "R&D", "operating_cash_flow": "operating cash flow",
    "total_assets": "total assets", "capex": "capital expenditures",
    "long_term_debt": "long-term debt", "dividends_paid": "dividends paid",
    "stockholders_equity": "stockholders' equity",
}
_SEC_OTHER_FIGURE_RE = re.compile(
    r'\b(per[\s-]+share|EPS|EBITDA|margins?|gross\s+(?:profit|income)|'
    r'operating\s+(?:profit|income|margin)|cost\s+of\s+(?:goods|revenue|sales)|'
    r'SG&A|selling,?\s+general|general\s+and\s+administrative|of\s+(?:net\s+)?sales)\b',
    re.IGNORECASE,
)


# Flows that add up over a year. A per-share figure or a balance does not:
# Q4 EPS is not the year's EPS less nine months'.
_ADDITIVE_METRICS = frozenset({
    "revenue", "profit", "operating_income", "gross_profit", "research_development",
    "operating_expenses", "operating_cash_flow", "capex", "dividends_paid",
})


def _derived_fourth_quarters(units):
    """Fourth quarters no filing states: a 10-K's year less the Q3 10-Q's nine
    months that began the same day. Clorox's fiscal 2024 net sales of $7,093
    million less $5,190 million for July to March is Q4's $1,903 million."""
    nine = {}
    for u in units:
        if u.get("form") == "10-Q" and u.get("start") and _days(u) and 250 <= _days(u) <= 290:
            nine.setdefault(u["start"], u)
    out, seen = [], set()
    for year in units:
        if (year.get("form") != "10-K" or year.get("fp") != "FY" or not year.get("start")
                or not _spans_a_year(year) or year.get("end") in seen):
            continue
        part = nine.get(year["start"])
        if part is None or part.get("val") is None or year.get("val") is None:
            continue
        seen.add(year["end"])
        out.append({**year, "fp": "Q4", "derived": True,
                    "val": year["val"] - part["val"]})
    return out


def _days(filing):
    try:
        return (datetime.date.fromisoformat(filing.get("end", ""))
                - datetime.date.fromisoformat(filing.get("start", ""))).days
    except ValueError:
        return 0


def _spans_a_quarter(filing):
    """False for a year-to-date row, which also carries fp=Q2 or Q3."""
    start, end = filing.get("start"), filing.get("end")
    if not start or not end:
        return True
    try:
        days = (
            datetime.date.fromisoformat(end)
            - datetime.date.fromisoformat(start)
        ).days
    except ValueError:
        return True
    return 70 <= days <= 110


def _spans_a_year(filing):
    """False for a quarter reported inside a 10-K. A balance-sheet figure
    has no start date and is fine."""
    start, end = filing.get("start"), filing.get("end")
    if not start or not end:
        return True
    try:
        days = (
            datetime.date.fromisoformat(end)
            - datetime.date.fromisoformat(start)
        ).days
    except ValueError:
        return True
    return 300 <= days <= 400


_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december"]
_FISCAL_END_RE = re.compile(
    r'\bfiscal\s+(?:year\s+)?(?P<fy>20[1-3]\d)\b[^.;\n\d]{0,20}?\b(?:ended|ending|closed)\s+'
    r'(?:on\s+)?(?P<month>' + '|'.join(_MONTHS) + r')\s+(?P<day>\d{1,2}),?\s+(?P<year>20[1-3]\d)\b',
    re.IGNORECASE,
)


def _fiscal_end(sentence, doc_text, time_period):
    """The end date the text gives the claim's fiscal year, as "fy|date"."""
    want = re.search(r'20[1-3]\d', time_period or "")
    if not want:
        return ""
    for text in (sentence, doc_text):
        for found in _FISCAL_END_RE.finditer(text or ""):
            if found.group("fy") == want.group():
                month = _MONTHS.index(found.group("month").lower()) + 1
                return (f"{found.group('fy')}|{found.group('year')}-"
                        f"{month:02d}-{int(found.group('day')):02d}")
    return ""


def _ends_near(filing, iso):
    """Whether a period ends within a week of a date."""
    import datetime
    try:
        end = datetime.date.fromisoformat(filing.get("end", "")[:10])
        return abs((end - datetime.date.fromisoformat(iso)).days) <= 7
    except ValueError:
        return False


def _starts_early_in(filing, year):
    """A fiscal year named for the year it begins in starts in its first half:
    Target's fiscal 2023 ran February 2023 to February 2024. A period starting
    on 2024-12-29 is not fiscal 2024, whatever its tag says."""
    start = filing.get("start", "")
    if len(start) < 7 or not start[:4].isdigit():
        return True
    return int(start[:4]) == year and start[5:7] <= "06"


def _end_year(filing):
    """Extract the calendar year of an XBRL entry's end date.

    Returns int year or None if the end field is missing or malformed.
    Used to match SEC EDGAR entries by actual data period rather than
    by the filing's fy field (which can include comparative data from
    prior years).
    """
    end = filing.get("end", "")
    if len(end) >= 4 and end[:4].isdigit():
        # A 52/53-week year ending in the first days of January is the year
        # before: Wolverine's fiscal 2025 ended 2026-01-03.
        if end[4:8] == "-01-" and end[8:10].isdigit() and int(end[8:10]) <= 7:
            return int(end[:4]) - 1
        return int(end[:4])
    return None


def _figure_clause(sentence, raw_value):
    """The words leading up to a figure, back to the previous figure or
    comparison: in "income of $63M, compared with a net loss of $119M" the
    loss belongs to the second figure, and in "a central span of 1,991 ft and
    a total length of 3,911 m" the span belongs to the first."""
    raw = str(raw_value or "").strip()
    sentence = sentence or ""
    at = sentence.find(raw) if raw else -1
    if at < 0:
        return sentence
    head = sentence[:at]
    cut = max(
        [m.end() for m in re.finditer(r'\d[\d,.]*\s*(?:million|billion|bn|m|M|B)?\b', head)]
        + [m.end() for m in re.finditer(r'\b(?:compared|versus|vs\.?|from|while|whereas)\b', head)]
        + [0]
    )
    return head[cut:] + raw


def _is_loss_per_share(sentence, raw_value):
    """"a net loss of $200 million, or $1.14 per share" is a loss per share."""
    raw = str(raw_value).strip()
    at = sentence.find(raw) if raw else -1
    if at < 0:
        return False
    head = sentence[:at]
    tail = sentence[at + len(raw):at + len(raw) + 30]
    if re.match(r'\s*(?:net\s+)?loss\s+per', tail, re.IGNORECASE):
        return True
    # "Loss per share: around $10.73."
    if re.search(r'\bloss\s+per\s+(?:diluted\s+|basic\s+)?share\b[^.;$]{0,25}$', head, re.IGNORECASE):
        return True
    loss = list(re.finditer(r'\b(?:net\s+)?loss\b', head, re.IGNORECASE))
    if not loss:
        return False
    between = head[loss[-1].end():]
    # The loss is this figure's when nothing else is named between them.
    return (bool(re.search(r',\s*or\s*$|\bof\s*$', between))
            and not re.search(r'\b(?:income|profit|earnings|earned)\b', between, re.IGNORECASE))


_ADJUSTED_FIGURE_RE = re.compile(
    r'\b(?:adjusted|non[- ]gaap|pro\s+forma|excluding|ex-items|organic|underlying|'
    r'normali[sz]ed|like[- ]for[- ]like|constant[- ]currency|run[- ]rate|trailing|ttm|'
    r'annuali[sz]ed|combined|backlog)\b',
    re.IGNORECASE,
)
_POINTS_ELSEWHERE_RE = re.compile(
    r'\b(?:last\s+year|a\s+year\s+(?:ago|earlier|before)|the\s+(?:prior|previous)\s+year|'
    r'year\s+before|previously|earlier|at\s+the\s+time|back\s+then|in\s+those\s+days|'
    r'decade|was\s+once|since|historically|prior\s+year|peak|record)\b',
    re.IGNORECASE,
)


_FOREIGN_CURRENCY_RE = re.compile(
    '[\u20ac\u00a3\u00a5\u20b9\u20a9]|\\b(?:EUR|GBP|JPY|CNY|RMB|INR|CHF|CAD|AUD|'
    'euros?|pounds?\\s+sterling|yen|yuan|rupees?|francs?)\\b')


def _with_unit_after(decomp):
    """The figure with the word written right after it: "23,300 euros"."""
    raw = str(decomp.raw_value or "").strip()
    sentence = decomp.sentence or ""
    at = sentence.find(raw) if raw else -1
    if at < 0:
        return raw
    return sentence[at:at + len(raw) + 16]


def _in_parentheses(sentence, raw_value):
    """True for "(1.51)" or "$(52.5)", how a statement writes a negative."""
    digits = re.search(r'\d[\d,]*(?:\.\d+)?', str(raw_value))
    if not digits:
        return False
    return bool(re.search(r'\(\s*\$?\s*' + re.escape(digits.group()) + r'\s*\)',
                          sentence))


def _is_a_ratio(sentence, raw_value):
    """A split or a ratio, "50-for-1" or "3:1", names no amount to check."""
    digits = re.search(r'\d[\d,]*(?:\.\d+)?', str(raw_value))
    if not digits:
        return False
    d = re.escape(digits.group())
    # "about 2.2 times the size of Korea's", "3x", "a 4-fold rise".
    if (not str(raw_value).lstrip().startswith(tuple("$\u20ac\u00a3\u00a5\u20b9"))
            and re.search(r'(?<![\d.,])' + d + r'\s*(?:times\b|x\b|-?fold\b)',
                          sentence, re.IGNORECASE)):
        return True
    return bool(re.search(
        r'(?<![\d.])' + d + r'\s*(?:-\s*for\s*-\s*|\s+for\s+|:)\s*\d+(?!\.\d)|'
        r'(?<![\d.])\d+\s*(?:-\s*for\s*-\s*|:)\s*' + d + r'(?![\d.])',
        sentence, re.IGNORECASE,
    ) and re.search(r'\bsplit|\bratio|-for-|\d\s*:\s*\d', sentence, re.IGNORECASE))


_HEDGE = (r'\b(?:about|around|roughly|approximately|nearly|almost|some|close\s+to|'
          r'over|more\s+than|under|less\s+than)\s+')


def _hedged(sentence, raw_value):
    """Whether the text loosens the figure: "about 384,400 km"."""
    raw = str(raw_value).strip()
    at = sentence.find(raw) if raw else -1
    if at > 0:
        return bool(re.search(_HEDGE + r'$', sentence[max(0, at - 25):at], re.IGNORECASE))
    return bool(re.search(_HEDGE + r'[$\d]', sentence, re.IGNORECASE))


def _rounding_room(raw_value):
    """How far a figure can sit from the truth and still be correctly rounded:
    "$4 billion" covers 3.5 to 4.5, "$4.0 billion" only 3.95 to 4.05.
    """
    digits = re.search(r'\d[\d,]*(?:\.\d+)?', str(raw_value))
    if not digits:
        return 0.0
    text = digits.group().replace(",", "")
    try:
        value = float(text)
    except ValueError:
        return 0.0
    if not value:
        return 0.0
    if "." in text:
        step = 10 ** -len(text.split(".")[1])
    else:
        trailing = len(text) - len(text.rstrip("0"))
        step = 10 ** trailing
    return 0.5 * step / value


def _source_room(source_value):
    """The rounding a source's own figure carries: Wikipedia's "290 million" is
    good to 5 million, the World Bank's 4.97865959 to nothing at all."""
    try:
        value = float(source_value)
    except (TypeError, ValueError):
        return 0.0
    if not value:
        return 0.0
    return _rounding_room(f"{int(value)}" if value.is_integer() else repr(value))


def _settle_close(results):
    """Split the close band by the figure's own precision.

    Close used to mean "within a few percent", shown with a tick. On the open
    sets that band held 30 true and 25 false figures, nearly all AI near misses
    ("5.05%" for 4.98, "223.8 million" for 213.4). Within the rounding of the
    figure as written, or of a rounded source, it is a match: 11 of the true
    ones, none of the false. Beyond that it stays close, which every view shows
    as near but not equal, with the source's own figure, and never as a match.
    Verified is left alone: 0 false figures there sat outside their rounding.
    """
    for r in results:
        if r.verdict != "close":
            continue
        claim = getattr(r.decomposition, "value", None)
        supporting = [s for s in r.source_results
                      if s.match_type in ("exact", "close") and s.source_value]
        if not claim or not supporting:
            continue
        best = min(supporting, key=lambda s: abs(claim - s.source_value))
        if not 0.8 <= claim / best.source_value <= 1.25:
            continue  # compared in other units; the band's own reading stands
        diff = abs(claim - best.source_value) / abs(best.source_value)
        # Only a text source's figure is itself rounded ("290 million" on a page);
        # a filed or statistical value (Nucor's EPS $18.00) is exact.
        source_room = _source_room(best.source_value) if best.source_name == "Wikipedia" else 0.0
        room = max(_rounding_room(r.decomposition.raw_value), source_room)
        if diff <= room * 1.0001:
            r.verdict = "verified"
            r.detail = (f"Matches {best.source_name} within the figure's own rounding.")
    return results


_BIND_STOP = frozenset("""about around roughly nearly almost over under some more less than
was were is are been the a an of in on at to for and or with by from its their this that
year years total about which while per cent percent million billion thousand""".split())


_STRUCTURED = ("World Bank", "SEC Filing", "FRED", "Wikidata")


def _structured_precedence(results):
    """A Wikipedia text match does not outrank an official series on the same
    figure. When a structured source answered only close (differs past the
    figure's rounding) and the match rests on Wikipedia alone, the figure is
    near, shown with the structured source's value (v17: Myanmar GDP "76
    billion" green on a page's 76.09 while the World Bank says 75.07).

    The combined verdict may already have left the verdict at close, with the page
    still marked exact. The page has to leave before _settle_close, or the
    closer page number is promoted back to a match."""
    for r in results:
        if r.verdict not in ("verified", "close"):
            continue
        exact = [s for s in r.source_results if s.match_type == "exact"]
        close = [s for s in r.source_results if s.match_type == "close"
                 and s.source_name in _STRUCTURED]
        if exact and close and all(s.source_name == "Wikipedia" for s in exact):
            # The page's number leaves the comparison; the series decides, and
            # _settle_close (next) still confirms it if it is within rounding.
            for s in exact:
                s.match_type = "no_data"
            if r.verdict == "verified":
                r.verdict = "close"
                r.best_source = close[0].source_name
                r.detail = (f"Near {close[0].source_name}'s figure; a page's matching number "
                            f"does not outweigh the series.")
            elif (r.best_source or "Wikipedia") == "Wikipedia":
                r.best_source = close[0].source_name
    return results


def _bind_text_confirmations(results):
    """A Wikipedia confirmation of a percentage must be about this measure: its
    passage shares a word with the figure's own clause. "Unemployment was 4.0%" is not confirmed by
    "About 4% of the Republic..." (v15 x13). Only Wikipedia's text matches are
    held to it; structured sources match on the measure already."""
    for r in results:
        if r.verdict != "verified":
            continue
        # Percentages only: a bare "4%" occurs on any page. On the open sets the
        # rule held to every figure cost 29 true confirmations for 1 false green.
        if getattr(r.decomposition, "unit", "") != "percent":
            continue
        supporting = [s for s in r.source_results if s.match_type in ("exact", "close")]
        if not supporting or any(s.source_name != "Wikipedia" for s in supporting):
            continue
        entity = set(re.findall(r"[a-z]{3,}", (r.decomposition.subject or "").lower()))
        words = {w for w in re.findall(r"[a-z]{4,}", _clause_of(r.decomposition).lower())
                 if w not in _BIND_STOP and w not in entity}
        if not words:
            continue  # nothing beside the figure to test against
        if not any(_shares_content_word(words, s.source_text or "") for s in supporting):
            r.verdict = "unverifiable"
            r.detail = "A page shows this number, but not as this measure."
    return results


def _sec_match_type(diff, raw_value):
    """A filed figure is exact only to the precision the claim was written
    at: "$8.53" for a filed $8.51 is two cents off, which is close, not
    exact. The 3% band for close is unchanged."""
    room = _rounding_room(raw_value)
    exact_band = min(0.005, room * 1.0001) if room else 0.005
    if diff <= exact_band:
        return "exact"
    if diff < max(0.03, room):
        return "close"
    return "contradicted"


_POINTS_AFTER_RE = re.compile(
    r'\s*%?\s*(?:percentage[- ]points?|points?|pp|ppt|pts?|basis\s+points?|bps?)\b',
    re.IGNORECASE,
)
_PER_PERIOD_AFTER_RE = re.compile(
    # "$94.9 billion quarterly revenue" is a filed level; "per quarter" is a rate.
    r'\s*(?:per|a|each|every)\s+(?:quarter|month|week|day)\b',
    re.IGNORECASE,
)


def _not_a_level(decomp):
    """Why no source's level can check this figure, or "". "up 20.0
    percentage points" is a change, and "$0.61 per quarter" is one payment,
    not the year's total that a filing reports."""
    raw = str(decomp.raw_value or "").strip()
    sentence = decomp.sentence or ""
    at = sentence.find(raw) if raw else -1
    if at < 0:
        return ""
    after = sentence[at + len(raw):]
    if _POINTS_AFTER_RE.match(after):
        return "A change in points, not a level a source can check."
    if decomp.unit == "currency" and _PER_PERIOD_AFTER_RE.match(after):
        return "An amount per period, not a total a source can check."
    return ""


def _wb_match_type(diff, raw_value, source_value=None):
    """A World Bank total is exact only to the precision of the coarser of
    the two figures: "about 277.5 million" against 278,830,529 is 1.3
    million off, which is close, not exact, while "38,394" against a series
    rounded to 38,390 is as exact as the source can say. The 2% band for
    close is unchanged. None when it is not close either."""
    room = _rounding_room(raw_value)
    claim_room = room
    if room and source_value is not None and float(source_value).is_integer():
        room = max(room, _rounding_room(f"{float(source_value):.0f}"))
    if diff <= min(0.01, room * 1.0001 if room else 0.01):
        return "exact"
    # A coarse source widens what counts as exact, never what counts as near.
    if diff < max(0.02, claim_room):
        return "close"
    return None


def _scale_slip(claim_value, source_value):
    """The right digits at the wrong scale: $4.2 million for $4.2 billion."""
    if not claim_value or not source_value:
        return False
    ratio = abs(source_value / claim_value)
    return any(abs(ratio / f - 1) < 0.02 for f in (1e3, 1e6, 1e9, 1e-3, 1e-6, 1e-9))


def _sec_other_metric(cik, metric_lower, claim_value, target_fy):
    """Which other filed figure of that year this number is, if any."""
    for name, concepts in _METRIC_CONCEPTS.items():
        if name == metric_lower or name == "eps":
            continue
        for concept in concepts[:3]:
            url = (
                f"https://data.sec.gov/api/xbrl/companyconcept/"
                f"CIK{cik}/us-gaap/{concept}.json"
            )
            try:
                data = _sec_concept_data(
                    cik, concept, urllib.request.Request(url, headers=_SEC_HEADERS),
                )
            except Exception:
                continue
            for filing in data.get("units", {}).get("USD", []):
                if (filing.get("form") == "10-K" and _spans_a_year(filing)
                        and _end_year(filing) == target_fy and filing.get("val")
                        and abs(filing["val"] / claim_value - 1) < 0.005):
                    return _SEC_METRIC_LABELS.get(name, name.replace("_", " "))
    return ""


_SEC_TO_MEASURE = {"eps": "eps_diluted", "profit": "net_income"}


def _own_words_name(decomp, metric):
    """identity_path.document_names on the claim's sentence: the words the text
    puts beside this figure name `metric` and nothing else. It only ever
    withholds a refutation."""
    from identity_path import document_names
    text = decomp.full_sentence or decomp.sentence or ""
    figure = _figure_text(decomp)
    try:
        return document_names({"figure": figure, "entity": decomp.subject or ""},
                              _SEC_TO_MEASURE.get(metric, metric), text)
    except Exception:
        return False


_FRACTION_QUARTER_RE = re.compile(
    r'\b(?:a|one|three|nearly\s+a|almost\s+a|over\s+a|than\s+a|about\s+a)\s+quarters?\s+of\s+'
    r'(?!(?:the\s+)?(?:19|20)\d\d\b|(?:the\s+|its\s+)?(?:fiscal\s+)?year\b)',
    re.IGNORECASE)


def verify_sec_edgar(decomp):
    """Verify company financials against SEC EDGAR filings.

    The most authoritative source for US public company data.
    Returns the value the company actually reported to the SEC.
    """
    if not decomp.subject or not decomp.value:
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # A filing can only speak to a metric the claim names. Treating an
    # unnamed dollar figure as revenue is how "Apple paid a $394 billion
    # fine" came to be confirmed by Apple's fiscal 2022 revenue.
    metric_lower = (decomp.metric or "").lower()
    concepts_to_try = _METRIC_CONCEPTS.get(metric_lower)
    if not concepts_to_try:
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # Only the level figure a concept holds. A growth rate, a per-share
    # number or gross profit against net income would "contradict" a true
    # claim by nine orders of magnitude.
    if decomp.unit == "percent" or (
        metric_lower in _SEC_BROAD_METRICS
        and _SEC_OTHER_FIGURE_RE.search(decomp.sentence)
    ):
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # Part of a year matches no filed figure. An unknown period ("Q? 2026")
    # is compared with the year: it may confirm, never refute.
    if _PART_YEAR_RE.search(decomp.sentence or ""):
        return SourceResult(source_name="SEC Filing", match_type="no_data")
    confirm_only = str(decomp.time_period or "").startswith("Q?")

    # "for the quarter" with no quarter named: a quarter's figure, which a
    # year's filing must never contradict.
    # "a quarter of every dollar" is a fraction, not a period (2026-11-27:
    # the site's own Apple example went unchecked on it).
    period_words = _FRACTION_QUARTER_RE.sub("", decomp.sentence or "")
    if (re.search(r'\bquarter\b', period_words, re.IGNORECASE)
            and not re.search(r'\bQ[1-4]\b', decomp.time_period or "", re.IGNORECASE)
            and getattr(decomp, "time_period_type", "") != "quarterly"):
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    if (_NOT_A_FILED_TOTAL_RE.search(_text_before_figure(decomp))
            or (metric_lower == "eps" and _SHARE_PRICE_RE.search(
                _text_before_figure(decomp)[-60:] + (decomp.sentence or "")[
                    (decomp.sentence or "").find(str(decomp.raw_value))
                    + len(str(decomp.raw_value)):][:20]))
            or (metric_lower == "revenue" and (_names_a_segment(decomp) or re.search(
                r'\b(?:acquired|acquisitions?|divest\w*|business(?:es)?\s+(?:generate|generated|'
                r'had|have|with))\b', _text_before_figure(decomp), re.IGNORECASE)))):
        return SourceResult(source_name="SEC Filing", match_type="no_data")
    if metric_lower == "cash" and _WIDER_CASH_RE.search(decomp.sentence or ""):
        confirm_only = True
    # Cash returned, generated or used is a flow, not the cash balance.
    if metric_lower == "cash" and re.search(
            r'\b(?:returned|flows?|used|paid|generated|provided|spent|dividends|repurchases)\b',
            _text_before_figure(decomp), re.IGNORECASE):
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    raw_text = str(decomp.raw_value or "").strip()
    at = (decomp.sentence or "").find(raw_text) if raw_text else -1
    if at >= 0 and _COMPONENT_AFTER_RE.match(decomp.sentence[at + len(raw_text):]):
        return SourceResult(source_name="SEC Filing", match_type="no_data")
    # "included a benefit of $28 million, net of tax, or $0.08 per diluted
    # share": both figures are the item's.
    whole = decomp.full_sentence or decomp.sentence or ""
    at_whole = whole.find(raw_text) if raw_text else -1
    if at_whole >= 0 and _COMPONENT_BEFORE_RE.search(whole[max(0, at_whole - 90):at_whole]):
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # A figure in euros is checked only against facts filed in euros, which
    # only IFRS filers have; the same digits in dollars never confirm it.
    currency, symbol = _claim_currency(decomp)
    if currency == "USD" and _FOREIGN_CURRENCY_RE.search(
            _figure_clause(decomp.sentence, decomp.raw_value) or str(decomp.raw_value)):
        return SourceResult(source_name="SEC Filing", match_type="no_data")
    ifrs = [f"ifrs-full/{c}" for c in _IFRS_CONCEPTS.get(metric_lower, [])]
    concepts_to_try = (ifrs if currency != "USD"
                       else list(concepts_to_try) + ifrs)
    if not concepts_to_try:
        return SourceResult(source_name="SEC Filing", match_type="no_data")
    unit_key = (f"{currency}/shares" if metric_lower == "eps" else currency) \
        if currency != "USD" else _SEC_UNIT_KEYS.get(metric_lower, "USD")

    cik, ticker = _find_cik(decomp.subject)
    if not cik:
        return SourceResult(source_name="SEC Filing", match_type="no_data")
    # A release names its own ticker: "MSC" in an "(NYSE: MSM)" release is
    # another company's ticker.
    declared = [t for t in (decomp.doc_tickers or "").split(",") if t]
    if declared and ticker and ticker.upper() not in declared:
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # Extract target fiscal year and quarter from claim context
    target_fy = None
    target_quarter = None

    if decomp.time_period:
        fy_match = re.search(r'20[1-3]\d', decomp.time_period)
        if fy_match:
            target_fy = int(fy_match.group())
        q_match = re.search(r'Q([1-4])', decomp.time_period, re.IGNORECASE)
        if q_match:
            target_quarter = f"Q{q_match.group(1)}"

    # Also check the claim sentence for year and quarter references
    if not target_fy:
        fy_match = re.search(
            r'(?:fiscal\s+(?:year\s+)?|FY\s*)?(20[1-3]\d)',
            decomp.sentence, re.IGNORECASE
        )
        if fy_match:
            target_fy = int(fy_match.group(1))
    if not target_quarter:
        q_match = re.search(r'Q([1-4])', decomp.sentence, re.IGNORECASE)
        if q_match:
            target_quarter = f"Q{q_match.group(1)}"

    # Filings report a net loss as a negative net income.
    claim_value = decomp.value
    if metric_lower == "profit" and re.search(
        r'\b(?:net\s+loss|loss\s+of)\b', _figure_clause(decomp.sentence, decomp.raw_value),
        re.IGNORECASE,
    ) or re.search(
        re.escape(str(decomp.raw_value).strip()) + r'\s*\(a loss\)', decomp.sentence,
    ):
        # "$(52.5)M" is how a statement writes a loss.
        claim_value = -abs(decomp.value)
    elif metric_lower == "eps" and _is_loss_per_share(
        decomp.full_sentence or decomp.sentence, decomp.raw_value,
    ):
        claim_value = -abs(decomp.value)
    elif _in_parentheses(decomp.sentence, decomp.raw_value):
        # "Diluted EPS (1.51)": a statement's parentheses are a minus sign.
        claim_value = -abs(decomp.value)

    # Query XBRL for each concept, find the best match
    best_val = None
    best_diff = float("inf")
    best_filing = None
    # Claim with no year: only the latest period can confirm it. Scanning
    # every year for the nearest value would confirm almost any figure
    # for a company with a long filing history. Gathered across concepts
    # because a retired concept's newest row is years out of date.
    yearless_rows = []
    # Every annual figure read, whatever its year: the evidence for whether
    # another year could explain a mismatch, and for naming it.
    annual_rows = []

    gaap_filer = False
    for concept in concepts_to_try:
        taxonomy, _, name = concept.rpartition("/")
        # A us-gaap filer's figures are all in us-gaap: no IFRS requests.
        if taxonomy and gaap_filer:
            continue
        url = (
            f"https://data.sec.gov/api/xbrl/companyconcept/"
            f"CIK{cik}/{taxonomy or 'us-gaap'}/{name}.json"
        )
        req = urllib.request.Request(url, headers=_SEC_HEADERS)
        try:
            # Caller-side deadline + per-op timeout. The except
            # catches both _FuturesTimeoutError and any urlopen
            # error and continues to the next concept; same
            # iteration-skipping behavior as before.
            data = _sec_concept_data(cik, concept, req)
        except Exception:
            continue

        units = data.get("units", {}).get(unit_key, [])
        if taxonomy:
            units = [{**u, "ifrs": True} for u in units]
        if not taxonomy and data.get("units"):
            gaap_filer = True
        if not units:
            continue

        # Filter filings by type. When the claim references a quarter
        # (Q1-Q4), prefer 10-Q filings for that quarter.
        #
        # NO FALLBACK to 10-K for quarterly claims. Before the
        # TimeContext integration this fell back to annual 10-K
        # data when no 10-Q existed; that caused FINDINGS.md B.1
        # (Tesla Q4 2023 claim verified against Tesla FY23 annual
        # revenue, producing a 284% diff and a false
        # `contradicted` verdict). Honest `no_data` from SEC here
        # lets the the combined verdict mechanism fall through to Wikipedia
        # and other verifiers, or return `unverifiable` if none
        # match; both better than inventing a contradiction.
        #
        # The decision to use quarterly filtering is driven by the
        # typed TimeContext (decomp.time_period_type) when
        # available, with target_quarter as the legacy fallback
        # for callers that haven't been through _classify_and_route.
        is_quarterly_claim = (
            getattr(decomp, "time_period_type", "") == "quarterly"
            or target_quarter is not None
        )
        if is_quarterly_claim:
            filtered = [
                u for u in units
                if u.get("form") == "10-Q" and u.get("fp") == target_quarter
                and _spans_a_quarter(u)
            ]
            if target_quarter == "Q4" and metric_lower in _ADDITIVE_METRICS:
                filtered = _derived_fourth_quarters(units)
            # Do NOT fall back to 10-K. Honest no_data beats a
            # confident contradiction computed against the wrong
            # period.
        else:
            filtered = [
                u for u in units
                if u.get("form") in _ANNUAL_FORMS and u.get("fp") == "FY"
                and _spans_a_year(u)
            ]
            annual_rows.extend(filtered)

        # Sort by recency (most recent first)
        filtered.sort(key=lambda x: x.get("end", ""), reverse=True)

        # Match by END DATE YEAR, not by filing fy. Each XBRL filing
        # contains 2-3 years of comparative data, all tagged with the
        # filing's fy field. The end date is the actual data period.
        #
        # Concrete example: NVIDIA's FY2024 actual revenue ($60.92B,
        # end=2024-01-28) appears as a fy=2024 entry in the FY2024 10-K,
        # AND as a fy=2025 entry in the FY2025 10-K's comparative section,
        # AND as a fy=2026 entry in the FY2026 10-K's comparative section.
        # All three entries have end=2024-01-28. Filtering by filing fy
        # mixes data from different periods; filtering by end year does
        # not.
        #
        # The conventional fiscal year label matches the end date year
        # for all major US public companies (Apple FY2024 ends Sept 2024,
        # NVIDIA FY2026 ends Jan 2026, Microsoft FY2026 ends June 2026).
        # SEC EDGAR's fy field is the FILING year, not the data period.
        if target_fy:
            # Two readings of "fiscal 2023". By the filing's own fy tag: its
            # newest row, which is how Target's year ending February 2024
            # counts. By end date: how Salesforce's fiscal 2025 ending January
            # 2025 counts, tagged fy=2024. Companies differ, and nothing here
            # says which applies, so the claim is compared with both and only
            # contradicted if it matches neither.
            # A filing's year tag can be wrong (Wolverine tags its year ending
            # 2026-01-03 as 2024), so it only counts for a period that ends in
            # that year or early in the next.
            own_year = [
                f for f in filtered if f.get("fy") == target_fy
                and _starts_early_in(f, target_fy)
            ]
            newest = max((f.get("end", "") for f in own_year), default="")
            exact_year_entries = [
                f for f in filtered
                if _end_year(f) == target_fy
                or (f.get("fy") == target_fy and f.get("end", "") == newest)
            ]
            dated_fy, _, dated_end = (decomp.fiscal_end or "").partition("|")
            if dated_end and dated_fy == str(target_fy):
                # The text says when this fiscal year ended: that period only.
                exact_year_entries = [f for f in filtered if _ends_near(f, dated_end)]
            if exact_year_entries:
                filtered = exact_year_entries
            else:
                # The filings have no such year. A neighbouring year can
                # neither confirm this claim nor contradict it.
                filtered = []

        if not target_fy:
            yearless_rows.extend(filtered)
            continue

        for filing in filtered:
            val = filing.get("val", 0)
            if val == 0:
                continue
            diff = abs(val - claim_value) / max(abs(claim_value), 1e-10)

            # Wrong values for the right period are how we catch
            # contradictions.
            if diff < best_diff:
                best_diff = diff
                best_val = val
                best_filing = filing

        # If we found an exact or close match, stop trying other concepts
        if best_diff < 0.03:
            break

    if yearless_rows:
        latest_end = max(f.get("end", "") for f in yearless_rows)
        for filing in yearless_rows:
            val = filing.get("val", 0)
            if filing.get("end", "") != latest_end or val == 0:
                continue
            diff = abs(val - claim_value) / max(abs(claim_value), 1e-10)
            # Agreeing confirms. Disagreeing proves nothing: the claim
            # may well be about a year it did not name.
            if diff < 0.03 and diff < best_diff:
                best_diff = diff
                best_val = val
                best_filing = filing

    if best_val is None or best_filing is None:
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # Determine match quality. When a fiscal-year-matched filing exists,
    # any diff above the "close" threshold is a genuine contradiction
    # (same company, same year, different number). The prior 30% cap
    # let grossly wrong claims (82% off) slip through as no_data.
    match_type = _sec_match_type(best_diff, decomp.raw_value)
    if confirm_only and match_type == "contradicted":
        return SourceResult(source_name="SEC Filing", match_type="no_data")
    # Paths added after 5562eaa may confirm, never refute, until a fresh
    # sealed set validates them: a derived fourth quarter, IFRS facts, and a
    # quarter the figure's own sentence does not name.
    if match_type == "contradicted" and (
            best_filing.get("derived") or best_filing.get("ifrs")
            or (best_filing.get("form") == "10-Q"
                and not _quarter_in(_COMPARED_QUARTER_RE.sub("", decomp.sentence or ""))
                and not re.search(r'\bQ[1-4]\b', decomp.sentence or ""))):
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # A bare figure off by exactly a power of a thousand is a table "in
    # thousands" whose caption was not read, not a wrong number.
    if (match_type == "contradicted" and _scale_slip(claim_value, best_val)
            and not re.search(r'[$\u20ac\u00a3]|\b(?:thousand|million|billion|trillion|bn|mn)\b|\d[MBKmbk]\b',
                              str(decomp.raw_value))):
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # An adjusted figure is a different number from the reported one.
    # The clause may have lost its sentence's "non-GAAP" when it was split off.
    if match_type == "contradicted" and (
            _ADJUSTED_FIGURE_RE.search(decomp.sentence)
            or _ADJUSTED_FIGURE_RE.search(decomp.full_sentence or "")):
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # The figure's own words must name the metric compared, and nothing more:
    # "free cash flow was around $1.5 billion" or "Gross merchandise sales were
    # around $13.2 billion" is not revenue because "revenue" appears in the
    # sentence. On open set v17, 7 of 9 true figures contradicted were this.
    if match_type == "contradicted" and (not _own_words_name(decomp, metric_lower)
                                         or not _year_is_its_own(decomp)):
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # What another year or metric would explain, stated with the finding.
    diagnosis = ""
    other_years = sorted({
        _end_year(f) for f in annual_rows
        if _end_year(f) and target_fy and abs(_end_year(f) - target_fy) <= 2
        and _end_year(f) != target_fy and f.get("val")
        and abs(f["val"] - claim_value) / max(abs(claim_value), 1e-10) < 0.01
    })
    if match_type == "contradicted":
        if _scale_slip(claim_value, best_val):
            diagnosis = "The digits match at a different scale."
        elif other_years:
            diagnosis = f"That is the FY{other_years[-1]} figure."
        elif target_fy and metric_lower != "eps":
            other_metric = _sec_other_metric(cik, metric_lower, claim_value, target_fy)
            if other_metric:
                diagnosis = f"That is the company's {other_metric}."

    # With two years in the sentence we cannot tell which one this number
    # belongs to, so a mismatch proves nothing. A true claim contradicted
    # is the worst error this tool can make.
    if (match_type == "contradicted"
            and len(set(re.findall(r'20[1-3]\d', decomp.sentence))) > 1):
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # A year carried over from an earlier sentence may not be the one meant, so
    # it only refutes when no neighbouring year fits either. A figure that is
    # exactly another year's is stale when the text has named just one year and
    # nothing here points elsewhere.
    if (match_type == "contradicted" and decomp.year_inherited
            and not _YEAR_REFERENCE_RE.search(decomp.sentence)):
        near_another_year = any(
            _end_year(f) and abs(_end_year(f) - target_fy) <= 2
            and f.get("val")
            and abs(f["val"] - claim_value) / max(abs(claim_value), 1e-10) < 0.10
            for f in annual_rows
        ) if target_fy else True
        stale = (
            other_years and decomp.year_sole
            and not _POINTS_ELSEWHERE_RE.search(decomp.sentence)
        )
        if near_another_year and not stale:
            return SourceResult(source_name="SEC Filing", match_type="no_data")
    if match_type == "contradicted" and decomp.subject_ambiguous:
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # Same for two figures and two metrics: "$4.3 billion in net income on
    # revenue of $176 billion" cannot say which metric the first one is.
    named_metrics = sum(
        1 for name in _METRIC_CONCEPTS
        if _METRIC_PATTERNS[name].search(decomp.sentence)
    )
    if (match_type == "contradicted" and named_metrics > 1
            and len(re.findall(r'[$€£]\s*\d', decomp.sentence)) > 1):
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # The year the number describes. XBRL's fy field is the filing's year,
    # and a 10-K carries comparatives: Apple's FY2016 revenue also appears
    # in its FY2018 10-K, tagged fy=2018.
    fy = best_filing.get("fy", "")
    data_year = target_fy or fy or _end_year(best_filing)
    metric_label = _SEC_METRIC_LABELS.get(
        metric_lower, metric_lower.replace("_", " "),
    )
    fp = best_filing.get("fp", "FY")
    form = best_filing.get("form", "10-K")
    filed = best_filing.get("filed", "")
    if abs(best_val) >= 1e9:
        val_display, val_unit = best_val / 1e9, "B"
    elif abs(best_val) >= 1e6:
        val_display, val_unit = best_val / 1e6, "M"
    else:
        val_display, val_unit = best_val, ""

    if best_filing.get("derived"):
        figure = f"{symbol}{val_display:,.1f}{val_unit}" if val_unit else f"{symbol}{val_display:,.2f}"
        filing_label = (f"{ticker} Q4 FY{data_year} {metric_label}, the 10-K year less the "
                        f"Q3 10-Q nine months, filed {filed}: {figure}")
        filing_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K"
    elif form == "10-Q":
        figure = f"{symbol}{val_display:,.1f}{val_unit}" if val_unit else f"{symbol}{val_display:,.2f}"
        filing_label = f"{ticker} {fp} FY{fy} {metric_label}, 10-Q filed {filed}: {figure}"
        filing_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-Q"
    else:
        figure = f"{symbol}{val_display:,.1f}{val_unit}" if val_unit else f"{symbol}{val_display:,.2f}"
        filing_label = f"{ticker} FY{data_year} {metric_label}, {form} filed {filed}: {figure}"
        filing_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K"

    result = SourceResult(
        source_name="SEC Filing",
        source_url=filing_url,
        source_value=best_val,
        source_text=f"{filing_label}. {diagnosis}" if diagnosis else filing_label,
        match_type=match_type,
        difference_pct=round(best_diff * 100, 1),
        confidence=0.95 if match_type == "exact" else 0.85,
    )
    # Rules on the filing text called true figures wrong, and the guard
    # fitted to that open set did not carry. The filed figure stays. The
    # identity path writes its own SEC Filing row when the figure's
    # identity is known, and that row may still accuse.
    if result.match_type == "contradicted":
        return _withhold_refute(result)
    return result


# ── Brave Web Search (fallback for unverifiable claims) ──

def _build_search_query(decomp):
    """Build an effective search query from a claim decomposition.

    Web search understands natural language. When the decomposition is
    strong (subject + metric extracted), build a targeted query. When
    it's weak (missing subject or metric), fall back to the claim
    sentence itself, which is what the user would type into Google.
    """
    has_subject = bool(decomp.subject)
    has_metric = bool(decomp.metric and decomp.metric not in ("count", "revenue"))

    if has_subject and has_metric:
        # Strong decomposition: targeted query
        parts = [decomp.subject, decomp.metric]
        if decomp.time_period:
            parts.append(decomp.time_period)
        if decomp.raw_value:
            parts.append(decomp.raw_value)
        return " ".join(parts)

    # Weak decomposition: use the claim sentence (truncated, cleaned)
    # Strip markdown/formatting, keep first 120 chars
    sentence = decomp.sentence
    if sentence:
        sentence = re.sub(r'[#*_\[\]()]', '', sentence).strip()
        # Remove "approximately", "roughly" etc. that add noise to search
        sentence = re.sub(
            r'\b(approximately|roughly|about|around|nearly|over|more than)\b',
            '', sentence, flags=re.IGNORECASE
        ).strip()
        sentence = re.sub(r'\s+', ' ', sentence)
        return sentence[:150]

    # Last resort: subject + raw value
    parts = []
    if decomp.subject:
        parts.append(decomp.subject)
    if decomp.raw_value:
        parts.append(decomp.raw_value)
    return " ".join(parts) if parts else ""


def verify_brave_search(decomp):
    """Verify a claim via Brave Web Search.

    Fallback source: only called when structured APIs return no data.
    Searches the web for the claim's subject + metric + value, extracts
    numbers from result snippets, and compares against the claim.

    Entity gate: requires a real entity subject. Without a named entity,
    Brave's snippets match on number coincidence alone (e.g., a generic
    "Customer satisfaction is 98.7%" matches LG's "98% customer satisfaction").
    For anonymous claims we return no_data rather than risk false positives.
    """
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        return SourceResult(source_name="Web Search", match_type="no_data")

    # Entity gate: refuse to verify claims without a real entity subject.
    # Generic words like "Customer", "Revenue", "Our" cannot be validated
    # against web search results because the subject keyword will appear
    # on any topically related page regardless of company.
    if not is_likely_entity(decomp.subject):
        return SourceResult(source_name="Web Search", match_type="no_data")

    query = _build_search_query(decomp)
    if not query or len(query) < 5:
        return SourceResult(source_name="Web Search", match_type="no_data")

    url = (
        "https://api.search.brave.com/res/v1/web/search?"
        + urllib.parse.urlencode({
            "q": query,
            "count": 5,
            "text_decorations": False,
            "search_lang": "en",
        })
    )

    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        })
        # Caller-side deadline + per-op timeout. The except below
        # catches both _FuturesTimeoutError and any urlopen error
        # and returns no_data; deadline-fired path tags
        # provider_health for /health observability.
        raw = _urlopen_with_deadline(req, per_op_timeout=8)
        # Handle gzip
        try:
            import gzip
            data = json.loads(gzip.decompress(raw))
        except Exception:
            data = json.loads(raw)
    except Exception as exc:
        # A spent budget (402) or a bad key answered nothing, silently, for a
        # whole month in 2026-11: count it where /health can show it.
        code = getattr(exc, "code", None)
        provider_health.record_error(
            "brave", "auth" if code in (401, 402, 403) else
            "rate_limited" if code == 429 else "other")
        return SourceResult(source_name="Web Search", match_type="no_data")

    web_results = data.get("web", {}).get("results", [])
    if not web_results:
        return SourceResult(source_name="Web Search", match_type="no_data")

    # Build subject keywords for context validation.
    # A web result must mention the claim's subject to count as verification.
    # Without this, GE Healthcare's investor page can "verify" Tesla claims
    # just because a matching number appears somewhere on the page.
    subject_words = set()
    if decomp.subject:
        # Split subject into words, keep significant ones
        for w in re.findall(r'\b[a-zA-Z]{3,}\b', decomp.subject):
            if w.lower() not in {
                "the", "and", "for", "inc", "corp", "ltd", "llc",
                "company", "group", "total", "global", "average",
            }:
                subject_words.add(w.lower())

    # Collect all text from snippets for number matching
    best_match = None
    best_diff = float("inf")
    best_source_url = ""
    best_source_text = ""
    best_source_name = ""

    for wr in web_results[:5]:
        title = wr.get("title", "")
        snippet = wr.get("description", "")
        extras = wr.get("extra_snippets", [])
        result_url = wr.get("url", "")

        # Combine all text for this result
        all_text = f"{title} {snippet} {' '.join(extras[:3])}"

        # Context validation: if we have a specific subject,
        # the web result must mention it. Prevents cross-context matches
        # (e.g., GE Healthcare page "verifying" Tesla claims).
        if subject_words:
            page_text_lower = all_text.lower()
            subject_found = any(w in page_text_lower for w in subject_words)
            if not subject_found:
                # Also check the URL (sometimes subject is in the domain)
                url_lower = result_url.lower()
                subject_found = any(w in url_lower for w in subject_words)
            if not subject_found:
                continue  # Skip this result entirely

        matched_val, context, confidence = _match_in_text(
            all_text, decomp.value, decomp.sentence, decomp=decomp
        )

        if matched_val is not None:
            diff = abs(matched_val - decomp.value) / max(abs(decomp.value), 1e-10)
            if diff < best_diff:
                best_diff = diff
                best_match = matched_val
                # Extract domain for display
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(result_url).netloc
                except Exception:
                    domain = result_url[:50]
                best_source_url = result_url
                best_source_text = (context or snippet)[:200]
                best_source_name = domain

    if best_match is None:
        return SourceResult(
            source_name="Web Search",
            source_text=web_results[0].get("description", "")[:150] if web_results else "",
            match_type="no_data",
        )

    # Tighter thresholds for web search than structured APIs.
    # Web snippets are noisier: numbers from different contexts appear
    # in the same result. A 5% tolerance catches cross-context matches.
    # Confirm only. A number in a search snippet is often another year's or
    # another measure's, and this path has never been scored against the
    # blind sets: until it is, it may not tell a reader a figure is wrong.
    match_type = (
        "exact" if best_diff < 0.01
        else "close" if best_diff < 0.025
        else "no_data"
    )

    if match_type == "no_data":
        return SourceResult(source_name="Web Search", match_type="no_data")

    # Lower confidence for web search than structured sources.
    # Web results are useful but less authoritative than government databases.
    return SourceResult(
        source_name=best_source_name or "Web Search",
        source_url=best_source_url,
        source_value=best_match,
        source_text=best_source_text,
        match_type=match_type,
        difference_pct=round(best_diff * 100, 1),
        confidence=0.75 if match_type == "exact" else 0.6 if match_type == "close" else 0.45,
        is_web_search=True,
    )


# ================================================================
# Source Router
# ================================================================

def _classify_and_route(decomp):
    """Classify claim type and return list of verify functions to call.

    The subject-entity classification (entity_classifier.classify_subject)
    is consulted once at the top and used to GATE company-focused
    verifiers. This is the structural fix for calibration FINDINGS.md
    B.3: country subjects like "United States" no longer leak into
    SEC EDGAR routing because the capitalization regex that used to
    drive `has_company` cannot override an explicit COUNTRY or
    CRYPTO_ASSET classification. The classifier's result is also
    attached to the decomp so downstream display and monitoring paths
    can surface it without re-classifying.
    """
    from entity_classifier import classify_subject, EntityType
    from time_context import classify_time

    sentence_lower = decomp.sentence.lower()

    classification = classify_subject(decomp.subject)
    # Attach to decomp so downstream consumers (the SourceNetworkResult
    # builder, the display formatter, the corpus event builder) can
    # read the entity type without redoing the work.
    decomp.entity_type = classification.entity_type.value
    decomp.entity_canonical = classification.canonical
    decomp.entity_classification_reason = classification.reason

    # Time-context classification. The router uses it only to
    # attach to the decomp; verifiers consult the decomp fields
    # directly when deciding gate behaviour (SEC EDGAR quarterly,
    # historical claims). Keeping the classifier call
    # here rather than inside each verifier means each claim is
    # classified once per analysis, not once per verifier.
    tc = classify_time(decomp.sentence, decomp.time_period)
    decomp.time_period_type = tc.period_type.value
    decomp.time_year = tc.year
    decomp.time_quarter = tc.quarter
    decomp.time_year_range = tc.year_range
    decomp.time_classification_reason = tc.reason

    sources = []

    # Always try Wikipedia (broadest coverage)
    sources.append(verify_wikipedia)

    # Country statistics
    if _claim_country(decomp):
        # The verifier's own indicator detector decides, so the router and the
        # verifier cannot drift: a keyword list here once skipped "income per
        # person" and "consumer prices", which the verifier reads (2026-11-27:
        # 98 true figures on v26-v27 were never sent; the World Bank matched
        # every one when asked).
        if decomp.metric in ("gdp", "population", "lifespan") or \
           any(kw in sentence_lower for kw in ["gdp", "population", "life expectancy",
               "unemployment", "inflation", "poverty", "literacy"]) or (
               decomp.unit == "percent" and _is_real_growth(
                   decomp.sentence, decomp.raw_value,
                   _clause_holding(decomp.sentence, decomp.raw_value))) or \
           _wb_indicator_for(decomp)[0]:
            sources.append(verify_world_bank)
        # restcountries.com retired v1-v4, so the World Bank answers area too.
        if decomp.metric == "area":
            sources.append(verify_world_bank)

    # Crypto
    if _detect_crypto(decomp.sentence, decomp.heading):
        sources.append(verify_coingecko)

    # Macroeconomic (FRED) - US economic indicators
    # US series only: asking FRED about Spain's unemployment compared it with
    # the US rate and marked a true figure as disputed.
    if os.environ.get("FRED_API_KEY") and _fred_applies(decomp):
        sources.append(verify_fred)

    # Measurements, city populations and headcounts (Wikidata)
    if _wikidata_applies(decomp):
        sources.append(verify_wikidata)

    # Company financials: SEC EDGAR (definitive) + Alpha Vantage (fallback).
    #
    # Gated on two conditions, in strict order:
    #
    #   (a) The subject is NOT explicitly classified as a non-company
    #       entity type. A COUNTRY or CRYPTO_ASSET subject must never
    #       reach company-financial verifiers, no matter what the
    #       sentence's capitalization or keywords look like. This is
    #       the structural guard for FINDINGS.md B.3 (the "US national
    #       debt" case that used to hit SEC and produce a false
    #       disputed verdict from an unrelated filing).
    #
    #   (b) The claim is not a segment / sub-component claim, whose
    #       consolidated-API verification would falsely contradict a
    #       correct segment number against the company total.
    #       Pre-existing guard, unchanged.
    #
    # UNKNOWN subjects still flow through the keyword heuristic below
    # so non-US-listed companies (European names, private companies
    # with Wikipedia presence) that don't resolve to a SEC CIK still
    # get the historical opportunity to hit SEC (which will return
    # no_data honestly) before falling back to Brave.
    has_financial_kw = any(kw in sentence_lower for kw in [
        "revenue", "earnings", "profit", "market cap", "valuation",
        "sales", "income", "fiscal", "quarterly", "annual report",
        "cash", "operating expenses", "opex",
    ])
    has_company = bool(
        re.search(r'\b[A-Z][A-Za-z]+\b', decomp.subject)
    ) if decomp.subject else False

    entity_type = classification.entity_type
    is_non_company_entity = entity_type in (
        EntityType.COUNTRY, EntityType.CRYPTO_ASSET,
    )

    if not decomp.is_segment and not is_non_company_entity:
        # SEC EDGAR: highest authority for US company filings
        # A figure filings hold by name goes there at any size: earnings per
        # share is a few dollars.
        if (has_financial_kw or decomp.metric in _METRIC_CONCEPTS
                or (decomp.unit == "currency" and has_company and decomp.value > 1e8)):
            sources.append(verify_sec_edgar)

        # Alpha Vantage: stock data, broader coverage
        if os.environ.get("ALPHA_VANTAGE_API_KEY"):
            if has_financial_kw:
                sources.append(verify_alpha_vantage)
            elif decomp.unit == "currency" and has_company:
                sources.append(verify_alpha_vantage)

    # Computational/physical (Wolfram Alpha)
    if os.environ.get("WOLFRAM_APP_ID"):
        if decomp.metric in ("height", "weight", "length", "area") or \
           decomp.unit in ("distance", "mass") or \
           any(kw in sentence_lower for kw in ["meters", "metres", "kilometers",
               "miles", "feet", "kg", "tonnes", "speed", "temperature",
               "diameter", "altitude", "elevation"]):
            sources.append(verify_wolfram)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for s in sources:
        if s.__name__ not in seen:
            seen.add(s.__name__)
            unique.append(s)

    return unique[:3]  # Max 3 sources per claim


# ================================================================
# The combined verdict
# ================================================================

_BOUND_WORDS = (
    r'(?:exceed\w*|over|above|past|more\s+than|at\s+least|beyond|topp\w+|'
    r'under|below|less\s+than|at\s+most|up\s+to)'
)


def _states_a_bound(sentence, raw_value):
    """True for "exceeded $34 trillion": a limit, not a value."""
    if not raw_value:
        return False
    return bool(re.search(
        r'\b' + _BOUND_WORDS + r'\s+(?:about\s+|roughly\s+)?'
        + re.escape(raw_value.strip()),
        sentence, re.IGNORECASE,
    ))


def _consensus_for(decomp, results):
    """_consensus, knowing the claim. A figure different from a stated bound
    may satisfy it, so a bound is never contradicted."""
    verdict, confidence, detail = _consensus(results)
    # A metric the sentence never names can confirm a figure, not refute it:
    # "Drinkware did $1.09 billion" read as revenue is a segment, not a total.
    # A peak or a low is one month or one week; a source's figure for the
    # period is an average. It may confirm, never refute.
    raw = str(decomp.raw_value).strip()
    at = decomp.sentence.find(raw) if raw else -1
    near = decomp.sentence[max(0, at - 60):at + len(raw) + 30] if at >= 0 else decomp.sentence
    if verdict in ("contradicted", "disputed") and _EXTREME_RE.search(near):
        return "unverifiable", 0.0, (
            "The text states a peak or a low, which a period figure cannot refute."
        )
    if verdict in ("contradicted", "disputed") and decomp.metric_inferred:
        return "unverifiable", 0.0, (
            "The sentence does not say what this figure measures, so a "
            "different figure for the metric it was read as does not refute it."
        )
    confirming = [r for r in results if r.match_type in ("exact", "close")]
    dissent = next((r for r in results if r.withheld_refute and (r.source_text or r.source_value)), None)
    if (verdict in ("verified", "close")
            and any(r.disagrees for r in results)
            and all(r.source_name == "Wikipedia" or r.is_web_search for r in confirming)):
        dissent = next(r for r in results if r.disagrees)
        return "unverifiable", 0.0, (
            f"{dissent.source_name} gives a different value: {dissent.source_text}"
        )
    # No earned source took a side. A withheld figure is still the source's
    # figure: say it, and do not say the look found nothing.
    if verdict == "unverifiable" and dissent is not None:
        shown = dissent.source_text or dissent.source_value
        return "unverifiable", 0.0, (
            f"{dissent.source_name} gives a different value: {shown}"
        )
    if verdict == "contradicted" and _states_a_bound(
        decomp.sentence, decomp.raw_value or "",
    ):
        return "unverifiable", 0.0, (
            "The text states a limit, not a value, so a different figure "
            "does not contradict it."
        )
    return verdict, confidence, detail


def _consensus(results):
    """Determine verdict from multiple source results.

    Returns (verdict, confidence, detail_text).
    """
    for r in results:
        _hold_unearned_refute(r)
    # Filter to results that found data. A web snippet never decides a
    # verdict in either direction: the audit that prompted this found
    # $187.4 billion "Checked" against best-of-gaming.be. It is reported
    # as a lead the reader can follow.
    # Wikipedia alone never decides either. A page that contains the
    # same digits is how false figures came back green. When a
    # structured source has already answered, Wikipedia does not get
    # to turn that answer into a new accusation: a page that agrees
    # with the text keeps a refutation from being announced.
    recorded = [
        r for r in results
        if r.match_type != "no_data" and not r.is_web_search
    ]
    wiki = [r for r in recorded if r.source_name == "Wikipedia"]
    other = [r for r in recorded if r.source_name != "Wikipedia"]
    if wiki and not other:
        return "unverifiable", 0.0, "Wikipedia is not a check on its own."
    if wiki and other:
        verdict, confidence, detail = _consensus(other)
        if verdict == "contradicted" and any(
            r.match_type in ("exact", "close") for r in wiki
        ):
            return "unverifiable", 0.0, (
                f"{detail} Wikipedia also has a figure, so this is not called wrong."
            )
        return verdict, confidence, detail
    with_data = recorded

    if not with_data:
        web = [
            r for r in results
            if r.is_web_search and r.match_type != "no_data"
        ]
        if web:
            return "unverifiable", 0.0, (
                f"Mentioned on {web[0].source_name}. A web page is a lead "
                "to follow, not an authoritative source."
            )
        return "unverifiable", 0.0, "No authoritative source found."

    # Check for agreement
    exact = [r for r in with_data if r.match_type == "exact"]
    close = [r for r in with_data if r.match_type == "close"]
    contradicted = [r for r in with_data if r.match_type == "contradicted"]

    # Mixed signals: check before pure-exact so contradictions
    # are not silenced by a single exact match from a lower-tier source.
    if exact and contradicted:
        return "disputed", 0.6, (
            f"Sources disagree. {exact[0].source_name} confirms, "
            f"{contradicted[0].source_name} contradicts."
        )

    if close and contradicted:
        return "disputed", 0.5, (
            f"Sources disagree. {close[0].source_name} is close, "
            f"{contradicted[0].source_name} contradicts."
        )

    # Unanimous or uncontested results
    if exact:
        names = ", ".join(r.source_name for r in exact)
        confidence = max(r.confidence for r in exact)
        if len(exact) >= 2:
            confidence = min(0.98, confidence + 0.05)
        return "verified", confidence, f"Confirmed by {names}."

    if close:
        names = ", ".join(r.source_name for r in close)
        confidence = max(r.confidence for r in close)
        return "close", confidence, f"Close match in {names}."

    if contradicted:
        r = contradicted[0]
        return "contradicted", r.confidence, (
            f"{r.source_name}: {r.source_text}"
        )

    return "unverifiable", 0.0, "Inconclusive results from sources."


def _best_display_source(source_results):
    """The source named on a match. Wikipedia does not get the name
    when another source already matched: a page that contains the
    same digits is not the check."""
    matched = [r for r in source_results if r.match_type in ("exact", "close")]
    deciding = [r for r in matched if r.source_name != "Wikipedia"]
    best = None
    for r in deciding or matched:
        if best is None or r.confidence > best.confidence:
            best = r
    return best


# ================================================================
# Main entry point
# ================================================================

# ================================================================
# Derivation checking (Step 4)
# ================================================================

_GROWTH_RE = re.compile(
    r'(?:grew|growth|increase[ds]?|decline[ds]?|rose|fell|'
    r'change[ds]?|up|down)\s+'
    r'(?:by\s+|of\s+)?'
    r'(\d+(?:\.\d+)?)\s*%',
    re.IGNORECASE
)

_SHARE_RE = re.compile(
    r'(?:account(?:s|ed)?\s+for|represent(?:s|ed)?|'
    r'compris(?:es?|ed|ing)|held?|captured?)\s+'
    r'(?:approximately\s+|about\s+|roughly\s+|nearly\s+)?'
    r'(\d+(?:\.\d+)?)\s*%',
    re.IGNORECASE
)


# Growth of a subset or a restated base, which the reported totals cannot test.
_SUBSET_GROWTH_RE = re.compile(
    r'\b(?:comparable|same[- ]store|like[- ]for[- ]like|comps?|system[- ]?wide|organic|'
    r'constant[- ]currency|segment|retail\s+sales)\b', re.IGNORECASE)


def _confirm_growth_by_arithmetic(results):
    """"Revenue of $60.9 billion, up 126% from $26.97 billion": when a source
    confirmed both figures in the rate's own sentence, the rate is arithmetic
    on them. It can confirm the rate; it never refutes one, since the two
    figures may not be the pair the rate was computed from."""
    figures = {}
    for r in results:
        d = r.decomposition
        if r.verdict in ("verified", "close") and getattr(d, "unit", "") == "currency":
            figures.setdefault(d.sentence, []).append(r)
    for r in results:
        d = r.decomposition
        if (r.verdict in ("verified", "close", "contradicted")
                or getattr(d, "unit", "") != "percent" or not d.value):
            continue
        found = [m for m in _GROWTH_RE.finditer(d.sentence or "")
                 if abs(float(m.group(1)) - d.value) < 1e-9]
        pool = figures.get(d.sentence) or []
        if not found or len(pool) < 2:
            continue
        falling = re.match(r'(?:decline|fell|down)', found[0].group(0), re.IGNORECASE)
        stated = found[0].group(1)
        decimals = len(stated.split(".")[1]) if "." in stated else 0
        room = max(0.5, 0.5 * 10 ** -decimals)
        for a in pool:
            for b in pool:
                if a is b or not b.decomposition.value:
                    continue
                pct = (a.decomposition.value - b.decomposition.value) / abs(b.decomposition.value) * 100
                if (pct < 0) != bool(falling) or abs(abs(pct) - d.value) > room:
                    continue
                source = a.best_source or "a public source"
                shown = [x.decomposition.raw_value or f"{x.decomposition.value:,.0f}"
                         for x in (a, b)]
                r.verdict = "verified"
                r.confidence = 0.8
                r.best_source = f"{source} (arithmetic)"
                r.best_url = getattr(a, "best_url", "") or ""
                r.detail = (f"Arithmetic on two figures {source} confirmed: "
                            f"{shown[0]} against {shown[1]} is {pct:+.1f}%.")
                break
            if r.verdict == "verified":
                break


def check_derivations(results):
    """Post-process Source Network results to flag fabricated derivations.

    For growth rate claims: finds base values in the same document section,
    recomputes the growth rate, and flags if the claimed rate doesn't match.

    Mutates results in place (updates verdict and detail for caught derivations).
    """
    _confirm_growth_by_arithmetic(results)
    # Build a lookup of verified values by heading
    verified_values = {}  # heading -> [(value, source_name)]
    for r in results:
        # A base for a growth rate is a level a source matched: never a near
        # figure, and never a percentage. Turkey's 5.5% and 5.1% growth (shown
        # as "6 and 5") once "refuted" its 11.4% growth as a +7.8% change.
        if (r.verdict == "verified" and r.decomposition.heading
                and getattr(r.decomposition, "unit", "") != "percent"):
            heading = r.decomposition.heading
            if heading not in verified_values:
                verified_values[heading] = []
            verified_values[heading].append(
                (r.decomposition.value, getattr(r.decomposition, "metric", "") or "")
            )

    for r in results:
        if r.decomposition.claim_type != "derived":
            continue
        # A source that confirmed the figure outranks arithmetic on figures
        # that may be another measure.
        if r.verdict in ("verified", "close"):
            continue

        sentence = r.decomposition.sentence
        # Check for growth rate claims
        gm = _GROWTH_RE.search(sentence)
        if not gm:
            continue
        claimed_pct = float(gm.group(1))
        heading = r.decomposition.heading
        metric = getattr(r.decomposition, "metric", "") or ""
        # Only two figures of the growth claim's own metric can test it. Any
        # pair in the section used to do, so a true 7.9% rise in comparable
        # sales was refuted by revenue against net income.
        if (not metric or not _sentence_names_metric(sentence, metric)
                or _SUBSET_GROWTH_RE.search(sentence)):
            continue
        values = [v for v, m in verified_values.get(heading, []) if m == metric]
        pairs = [(c, p) for i, c in enumerate(values) for j, p in enumerate(values)
                 if i != j and p]
        if not pairs:
            continue
        changes = [(c, p, (c - p) / abs(p) * 100) for c, p in pairs]
        if any(abs(pct - claimed_pct) <= 2.0 for _, _, pct in changes):
            continue
        current, prior, actual_pct = min(changes, key=lambda x: abs(x[2] - claimed_pct))
        r.verdict = "contradicted"
        r.confidence = 0.8
        r.detail = (
            f"Claimed {claimed_pct}% growth. "
            f"Based on verified values "
            f"({current:,.0f} and {prior:,.0f}), "
            f"actual change is {actual_pct:+.1f}%."
        )
        return  # One derivation contradiction is enough


# ================================================================
# Confidence Decomposition
# ================================================================

_AUTHORITY_SCORES = {
    "FRED": 0.95,
    "World Bank": 0.9,
    "Wolfram Alpha": 0.85,
    "Alpha Vantage": 0.75,
    "Wikipedia": 0.7,
    "REST Countries": 0.65,
    "CoinGecko": 0.6,
}


def decompose_confidence(source_results):
    """Decompose verification confidence into 4 transparent dimensions.

    Returns dict with authority, precision, context, corroboration,
    each as {score: 0-1, label: str}.
    """
    with_data = [r for r in source_results if r.match_type != "no_data"]

    if not with_data:
        return {
            "authority": {"score": 0, "label": "no source"},
            "precision": {"score": 0, "label": "no match"},
            "context": {"score": 0, "label": "no context"},
            "corroboration": {"score": 0, "label": "0 sources"},
        }

    # 1. Authority: best source tier
    best_authority = 0
    best_source_name = ""
    for r in with_data:
        score = _AUTHORITY_SCORES.get(r.source_name, 0.5)
        if score > best_authority:
            best_authority = score
            best_source_name = r.source_name

    authority_label = best_source_name
    if best_authority >= 0.9:
        authority_label += " (institutional)"
    elif best_authority >= 0.7:
        authority_label += " (reference)"
    else:
        authority_label += " (aggregator)"

    # 2. Precision: best match quality
    best_precision = 0
    precision_label = "no match"
    for r in with_data:
        if r.match_type == "exact":
            p = 1.0
            precision_label = "exact"
        elif r.match_type == "close":
            p = 0.7
            diff_str = f"{r.difference_pct}% diff" if r.difference_pct > 0 else "close"
            precision_label = diff_str
        elif r.match_type == "contradicted":
            p = 0.0
            precision_label = "contradicted"
        else:
            p = 0.3
            precision_label = r.match_type
        if p > best_precision:
            best_precision = p

    # 3. Context: confidence from matching (already captures metric+temporal alignment)
    best_context = max((r.confidence for r in with_data), default=0)
    if best_context >= 0.8:
        context_label = "strong"
    elif best_context >= 0.5:
        context_label = "moderate"
    else:
        context_label = "weak"

    # 4. Corroboration: how many sources found data
    matches = [r for r in with_data if r.match_type in ("exact", "close")]
    n_corroborating = len(matches)
    if n_corroborating >= 3:
        corr_score = 1.0
    elif n_corroborating == 2:
        corr_score = 0.8
    elif n_corroborating == 1:
        corr_score = 0.5
    else:
        corr_score = 0.2
    corr_label = f"{n_corroborating} source{'s' if n_corroborating != 1 else ''}"

    return {
        "authority": {"score": round(best_authority, 2), "label": authority_label},
        "precision": {"score": round(best_precision, 2), "label": precision_label},
        "context": {"score": round(best_context, 2), "label": context_label},
        "corroboration": {"score": round(corr_score, 2), "label": corr_label},
    }


@dataclass
class SourceNetworkResult:
    """Result for a single claim from the Source Network."""
    claim_numbers: list         # The display numbers from the claim
    claim_sentence: str         # Full sentence
    decomposition: ClaimDecomposition
    source_results: list        # List[SourceResult]
    verdict: str                # "verified", "close", "contradicted", "disputed", "unverifiable", "projection"
    confidence: float
    detail: str                 # Human-readable explanation
    best_source: str = ""       # Name of the source that resolved it
    best_url: str = ""          # URL of the best source
    confidence_dimensions: dict = field(default_factory=dict)  # From decompose_confidence


def _enrich_headings(claims, doc_text):
    """Enrich claims that lack headings by finding where each number
    appears in the original document and looking up which heading
    was active at that position.

    Many claims come from the bullet/number extractor which doesn't
    carry heading context. This recovers it using position-based
    heading assignment, which handles truncated sentences, mid-word
    fragments, and coreference ("It spans 4.3m") correctly.
    """
    if not doc_text:
        return

    # Build a position-to-heading map from the document.
    # Walk through lines: when a heading is found, all subsequent
    # text falls under that heading until the next heading.
    heading_ranges = []  # [(start_pos, end_pos, heading_text)]
    current_heading = ""
    current_start = 0
    pos = 0
    for line in doc_text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('#'):
            # Close the previous heading range
            if current_heading:
                heading_ranges.append((current_start, pos, current_heading))
            current_heading = re.sub(r'^#+\s*', '', stripped).strip()
            current_start = pos + len(line) + 1  # after this heading line
        pos += len(line) + 1  # +1 for newline

    # Close the final heading range
    if current_heading:
        heading_ranges.append((current_start, len(doc_text), current_heading))

    for claim in claims:
        if claim.get("heading"):
            continue

        # Find this claim's number in the original document text
        numbers = claim.get("numbers", [])
        sent = claim.get("sentence", "")

        # Try each number to find its position in the document
        found_heading = ""
        for num_raw in numbers:
            # Search for the number in the doc_text
            for m in re.finditer(re.escape(str(num_raw)), doc_text):
                num_pos = m.start()
                # Look up which heading range contains this position
                for range_start, range_end, heading in heading_ranges:
                    if range_start <= num_pos < range_end:
                        found_heading = heading
                        break
                if found_heading:
                    break
            if found_heading:
                break

        # Fallback: try matching a distinctive phrase from the claim sentence
        if not found_heading and sent:
            # Use the longest clean word sequence from the sentence
            # Skip the first few chars which may be truncated
            clean = sent[3:] if len(sent) > 10 and sent[2:3] == ')' else sent
            # Find a 15+ char unique substring
            for chunk_len in [25, 20, 15]:
                for start in range(0, max(1, len(clean) - chunk_len)):
                    chunk = clean[start:start + chunk_len]
                    if chunk in doc_text:
                        chunk_pos = doc_text.index(chunk)
                        for range_start, range_end, heading in heading_ranges:
                            if range_start <= chunk_pos < range_end:
                                found_heading = heading
                                break
                        if found_heading:
                            break
                if found_heading:
                    break

        if found_heading:
            claim["heading"] = found_heading


# One document often makes many claims about one company. Concepts fetched
# during a request are kept until the last request in flight ends, so SEC is
# asked once for each and its rate limit is not spent on repeats.
_SEC_CACHE_GUARD = threading.Lock()
_sec_cache = {}
_sec_cache_locks = {}
_sec_cache_users = 0


def _sec_concept_data(cik, concept, request):
    if not _sec_cache_users:
        return json.loads(_urlopen_with_deadline(request, per_op_timeout=8))
    key = (cik, concept)
    with _SEC_CACHE_GUARD:
        lock = _sec_cache_locks.setdefault(key, threading.Lock())
    with lock:
        if key not in _sec_cache:
            try:
                data = json.loads(
                    _urlopen_with_deadline(request, per_op_timeout=8)
                )
            except Exception:
                data = {}
            _sec_cache[key] = data
        return _sec_cache[key]


def verify_claims_source_network(
    claims,
    topic="",
    max_claims=30,
    doc_text="",
    out_state: Optional[dict] = None,
):
    """Verify claims, sharing SEC lookups for the length of the request."""
    global _sec_cache_users
    with _SEC_CACHE_GUARD:
        _sec_cache_users += 1
    try:
        return _verify_claims_source_network(
            claims, topic=topic, max_claims=max_claims, doc_text=doc_text,
            out_state=out_state,
        )
    finally:
        with _SEC_CACHE_GUARD:
            _sec_cache_users -= 1
            if not _sec_cache_users:
                _sec_cache.clear()
                _sec_cache_locks.clear()


def _verify_claims_source_network(
    claims,
    topic="",
    max_claims=30,
    doc_text="",
    out_state: Optional[dict] = None,
):
    """Verify claims against the Source Network.

    Takes a list of claim dicts from analyze_claims() output.
    Returns a list of SourceNetworkResult.

    out_state: optional dict the function fills with per-call
    operational counters. Currently populated keys:
      - "brave_query_count": int, the number of Brave Search
        queries submitted during this call (always written,
        even when zero, so the caller can read unconditionally).

    Callers that need the Brave query count for monitoring pass
    an empty dict and read the value after the call returns.
    Callers that do not need it omit the parameter.
    """
    # Phase 1.5: record the Brave query count via the out_state
    # dict so the caller observes it on the same execution
    # context that issued the verification call. See module
    # docstring for the threading.local issue this replaced.
    if out_state is not None:
        out_state["brave_query_count"] = 0
        out_state["readers_down"] = []
    # Readers that were on and did not answer for this document. The check
    # still runs on the rules; the page says so (out_state["readers_down"]).
    reader_status = {}

    if not claims:
        return []

    # The identity reader quotes figures from the text as pasted, before
    # plain_prose rewrites it.
    raw_doc_text = doc_text
    doc_text = plain_prose(doc_text)
    from identity_path import apply_identity, start_reading
    identity_reading = start_reading(raw_doc_text, reader_status)

    # Compute the document's primary entity once. Sentences that lack
    # their own entity name will inherit this as a fallback subject,
    # so claims like "Common side effects include nausea (44%)" in an
    # Ozempic document get verified as Ozempic claims instead of being
    # rejected as anonymous.
    # The budget starts before the reader, so a slow model call cannot push
    # the whole check past the caller's own limit.
    sn_orchestrator_start = time.monotonic()
    claims = _apply_reader(_prepare_claims(claims, doc_text), doc_text, status=reader_status)
    doc_primary_entity = extract_doc_primary_entity(doc_text, topic=topic)

    results = []

    # Article cache: same heading = one Wikipedia fetch for all claims
    _article_cache = {}

    # Cooperative cancellation: capture the SN deadline origin HERE
    # (above the nested function definitions) so each worker thread
    # can poll the cumulative elapsed time against SN_BUDGET_SECONDS
    # without depending on the as_completed loop yielding. Python
    # threads cannot be cancelled externally; the workers cooperate
    # by checking the deadline themselves before each provider hop.
    # The orchestrator's in-loop budget check (line ~3500) only fires
    # when as_completed yields a completed future; under the cold-
    # start scenario observed 2026-05-02 19:20:53 (all workers stalled
    # in a single Wikipedia urlopen for 30+s), no future yielded
    # within budget, so the orchestrator could not engage. The in-
    # worker poll is the cooperative-cancellation half of the budget
    # primitive; combined with the _fetch_json caller-side total
    # deadline added the same day, it bounds the worker's wall-clock
    # in two ways: (a) workers exit voluntarily at provider boundaries
    # when they observe budget exhausted, (b) urlopen calls themselves
    # cannot block past the per-call deadline. The clock started above, before
    # the claim reader.

    def _budget_exhausted_in_worker():
        """Return True when the SN_BUDGET_SECONDS deadline has elapsed.
        Polled by _verify_one before each provider boundary so workers
        exit voluntarily when the orchestrator cannot reach them via
        the as_completed loop."""
        return (time.monotonic() - sn_orchestrator_start) > SN_BUDGET_SECONDS

    def _get_cached_article(subject):
        """Fetch Wikipedia article once per unique subject."""
        if not subject:
            return None, None, None
        cache_key = subject.lower().strip()
        if cache_key not in _article_cache:
            _article_cache[cache_key] = _query_wikipedia(subject)
        return _article_cache[cache_key]

    def _budget_marked_result(claim, decomp):
        """Synthesize the unverifiable-with-budget-marker result that
        downstream code keys off (sn_status="partial" detection in
        app.py reads detail.lower() for "budget"). Used by the in-
        worker early-exit paths so the output shape matches the post-
        loop synthesis path at the bottom of
        verify_claims_source_network.

        decomp is REQUIRED: the HTML render at app.py:2222 reads
        decomp.subject unconditionally and crashes on None. Every
        in-worker exit site must call decompose_claim first and pass
        the result here. comparison.py:955 happens to be defensive,
        but relying on each downstream consumer to add a None-check
        would be fragile; the decomp-required signature pins the
        invariant at the producer."""
        return SourceNetworkResult(
            claim_numbers=claim.get("numbers", []),
            claim_sentence=claim.get("sentence", ""),
            decomposition=decomp,
            source_results=[],
            verdict="unverifiable",
            confidence=0.0,
            detail="Verification budget exhausted; worker exited before provider attempts.",
        )

    def _verify_one(claim):
        # decompose_claim runs unconditionally as the worker's first
        # step. It is a microseconds-scale regex pass; an entry-time
        # budget poll skipping it would shave essentially nothing off
        # the request and would force _budget_marked_result to accept
        # decomp=None which crashes the HTML render at app.py:2222.
        # Doing decomposition first means every in-worker exit below
        # carries a valid decomp into _budget_marked_result.
        decomp = decompose_claim(
            claim,
            topic=topic,
            doc_text=doc_text,
            doc_primary_entity=doc_primary_entity,
        )

        # Skip projections
        if decomp.claim_type == "projection":
            return SourceNetworkResult(
                claim_numbers=claim.get("numbers", []),
                claim_sentence=claim.get("sentence", ""),
                decomposition=decomp,
                source_results=[],
                verdict="projection",
                confidence=0.0,
                detail="Projection. Cannot be verified against current data.",
            )

        # A split ratio is not an amount: "50-for-1" was compared as EPS.
        if _is_a_ratio(decomp.sentence, decomp.raw_value):
            return SourceNetworkResult(
                claim_numbers=claim.get("numbers", []),
                claim_sentence=claim.get("sentence", ""),
                decomposition=decomp,
                source_results=[],
                verdict="unverifiable",
                confidence=0.0,
                detail="A ratio, not an amount a source can check.",
            )
        not_a_level = _not_a_level(decomp)
        if not_a_level:
            return SourceNetworkResult(
                claim_numbers=claim.get("numbers", []),
                claim_sentence=claim.get("sentence", ""),
                decomposition=decomp,
                source_results=[],
                verdict="unverifiable",
                confidence=0.0,
                detail=not_a_level,
            )

        # Skip if no subject or value
        if not decomp.subject or decomp.value == 0:
            return SourceNetworkResult(
                claim_numbers=claim.get("numbers", []),
                claim_sentence=claim.get("sentence", ""),
                decomposition=decomp,
                source_results=[],
                verdict="unverifiable",
                confidence=0.0,
                detail="Could not extract subject or value from claim.",
            )

        # Budget poll BEFORE Wikipedia. The expensive provider work
        # starts here; bailing now saves the most CPU/network when
        # budget is already exhausted.
        if _budget_exhausted_in_worker():
            return _budget_marked_result(claim, decomp=decomp)

        # Route to sources
        source_fns = _classify_and_route(decomp)

        # Query sources (Wikipedia uses cache, others in parallel)
        source_results = []
        non_wiki_fns = []
        for fn in source_fns:
            # Per-provider budget poll: workers exit voluntarily at
            # every provider boundary, not just the first. Without
            # this, a worker past budget after one slow provider
            # would still iterate through every other source listed
            # in source_fns. Symmetric coverage with the pre-Wikipedia
            # poll above.
            if _budget_exhausted_in_worker():
                return _budget_marked_result(claim, decomp=decomp)
            if fn is verify_wikipedia:
                # Time the full wiki path: the cache fetch
                # (network I/O on miss, ~0ms on hit) and the
                # match step together, because Section 5.3's
                # per-source histogram is about "cost of hitting
                # the wiki source for this claim", not "cost of
                # the matcher alone". Phase 1.6e item 4.
                wiki_start = time.perf_counter()
                try:
                    cached = _get_cached_article(decomp.subject)
                    result = verify_wikipedia(decomp, _cached_article=cached)
                except Exception as exc:  # noqa: BLE001 - any bug costs one source, not the claim
                    # One source's bug costs that source's answer, not the
                    # claim: the other sources still run.
                    import sys
                    sys.stderr.write(
                        f"[source-network] verify_wikipedia raised "
                        f"{type(exc).__name__}: {exc}\n"
                    )
                    result = None
                if result is not None:
                    result.query_latency_ms = int(
                        (time.perf_counter() - wiki_start) * 1000
                    )
                    source_results.append(result)
            else:
                non_wiki_fns.append(fn)

        # Budget poll BEFORE the non-Wikipedia sub-pool. Without it, a
        # worker that completed Wikipedia within budget but is past
        # budget by the time it reaches this branch would still spin
        # up to 3 sub-workers (each making blocking provider calls)
        # past the deadline. Symmetric with the pre-Wikipedia poll.
        if non_wiki_fns and _budget_exhausted_in_worker():
            return _budget_marked_result(claim, decomp=decomp)
        if non_wiki_fns:
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {
                    pool.submit(_timed_verify, fn, decomp): fn.__name__
                    for fn in non_wiki_fns
                }
                for future in as_completed(futures):
                    fn_name = futures[future]
                    try:
                        result = future.result()
                        if result:
                            source_results.append(result)
                    except Exception as exc:
                        # Log but do not crash. A systematic API
                        # failure (all FRED queries timing out, SEC
                        # returning 403) would otherwise produce
                        # zero verifications with no operator
                        # visibility. The verifier name is included
                        # so the operator can identify which source
                        # is failing from `fly logs`.
                        import sys
                        sys.stderr.write(
                            f"[source-network] {fn_name} raised "
                            f"{type(exc).__name__}: {exc}\n"
                        )

        # A range is right if the source lies inside it, whatever either end says.
        value_range = _value_range(decomp.sentence, decomp.raw_value)
        if value_range:
            source_results = _judge_range(value_range, source_results, decomp.unit)

        # The combined verdict
        verdict, confidence, detail = _consensus_for(decomp, source_results)

        # Find best source for display. A page match does not take
        # the name when a structured source also matched.
        best = _best_display_source(source_results)

        # Compute confidence dimensions
        conf_dims = decompose_confidence(source_results)

        return SourceNetworkResult(
            claim_numbers=claim.get("numbers", []),
            claim_sentence=claim.get("sentence", ""),
            decomposition=decomp,
            source_results=source_results,
            verdict=verdict,
            confidence=confidence,
            detail=detail,
            best_source=best.source_name if best else "",
            best_url=best.source_url if best else "",
            confidence_dimensions=conf_dims,
        )

    # Process claims (parallel at the claim level).
    #
    # Wall-clock budget: capture start_time and stop accepting new
    # results when SN_BUDGET_SECONDS is exhausted. Unprocessed claims
    # become unverifiable results (verdict pinned to existing vocab so
    # template + aggregation paths are unchanged); the user-facing
    # impact is "verification incomplete on N of M claims" rather than
    # "Analysis timed out" at the outer _structural budget. See module
    # constant comment for the architectural compromise.
    claim_list = claims[:max_claims]
    sn_start_time = time.monotonic()
    budget_exhausted = False

    def _log_budget_exhausted(elapsed_s, indexed_count):
        import sys
        print(
            f"[source-network] budget exhausted at "
            f"{elapsed_s:.1f}s; {indexed_count} of "
            f"{len(claim_list)} claims processed; "
            f"{len(claim_list) - indexed_count} marked "
            f"unverifiable (budget)",
            file=sys.stderr, flush=True,
        )

    # Fast-fail short-circuit. Budgets under 100ms are debug / test
    # configurations: production is 25s, no realistic operator
    # configuration sub-100ms returns useful provider results. Without
    # this guard, the in-loop budget check races against per-claim
    # workers; on fast systems with already-failing workers (e.g.
    # malformed claim shapes raising AttributeError on submit), the
    # workers complete and the loop's exception handler runs BEFORE
    # the budget check fires, silently disengaging the budget primitive.
    # Bypassing pool creation entirely under sub-100ms budget makes the
    # fast-fail path deterministic across system speeds and tightens
    # behavior under operator debugging without changing production.
    if SN_BUDGET_SECONDS < 0.1:
        budget_exhausted = True
        _log_budget_exhausted(0.0, 0)
        # Skip the pool path; jump straight to the post-loop budget-
        # marked synthesis below. ThreadPoolExecutor still needs to be
        # exited cleanly via the existing try / finally for parity with
        # the normal-budget path, so create + shutdown an empty pool.
        pool = ThreadPoolExecutor(max_workers=1)
        futures = {}
        indexed_results = {}
        failed = set()
    else:
        pool = ThreadPoolExecutor(max_workers=5)
    try:
        if not budget_exhausted:
            futures = {pool.submit(_verify_one, c): i for i, c in enumerate(claim_list)}
            indexed_results = {}
            failed = set()

        for future in as_completed(futures):
            elapsed = time.monotonic() - sn_start_time
            if elapsed > SN_BUDGET_SECONDS:
                # Budget exhausted: stop collecting more results,
                # do not wait for in-flight workers. Cancel pending
                # (best-effort; running workers continue until their
                # per-call _TIMEOUT, but their results are discarded).
                budget_exhausted = True
                for f in futures:
                    if not f.done():
                        f.cancel()
                _log_budget_exhausted(elapsed, len(indexed_results))
                break
            idx = futures[future]
            try:
                indexed_results[idx] = future.result()
            except Exception as e:
                failed.add(idx)
                # Tolerated by design: per-claim verification
                # failures MUST NOT block the rest of the claim
                # pool. The "Return in original order" loop below
                # only emits results for indices that resolved;
                # claims that failed simply do not appear in the
                # downstream verification list and the caller sees
                # the verified subset. Log to stderr so the
                # operator can investigate without breaking the
                # JSON-RPC channel on stdout.
                import sys
                print(
                    f"[source_network.verify_claims] "
                    f"per-claim verification failed at idx {idx}: "
                    f"{type(e).__name__}: {e}",
                    file=sys.stderr,
                )
    finally:
        # shutdown(wait=False) returns immediately; running workers
        # finish on their own per-call _TIMEOUT. They do not extend
        # the user-visible request time but they do continue consuming
        # CPU/network until they finish. The proper fix is asyncio
        # task cancellation; see SN_BUDGET_SECONDS module comment.
        pool.shutdown(wait=False)

    # Return in original order. Unprocessed claims (cancelled or
    # not-yet-started when budget exhausted) get a synthetic
    # unverifiable result so the caller's claim-count semantics
    # ("M of N source-verified") still align with the input claims.
    for i, claim in enumerate(claim_list):
        if i in indexed_results:
            results.append(indexed_results[i])
        elif i in failed or budget_exhausted:
            # Construct a minimal unverifiable result so downstream
            # rendering treats this claim as "not verified" rather
            # than "absent." Decomposition is required for the
            # rendering path to extract sentence + heading; build it
            # the same way _verify_one does (no provider calls, just
            # decomposition).
            try:
                decomp = decompose_claim(
                    claim, topic=topic, doc_text=doc_text,
                    doc_primary_entity=doc_primary_entity,
                )
                results.append(SourceNetworkResult(
                    claim_numbers=claim.get("numbers", []),
                    claim_sentence=claim.get("sentence", ""),
                    decomposition=decomp,
                    source_results=[],
                    verdict="unverifiable",
                    confidence=0.0,
                    # A check that raised says so: a figure that vanished
                    # from the list read as if it had never been there.
                    detail=("Checking this figure failed, so it was not checked."
                            if i in failed else
                            "Verification budget exhausted before this claim was processed."),
                ))
            except Exception:
                # Defensive: if decomposition itself fails on this
                # claim, omit silently rather than raising. The
                # behavior matches the existing per-claim exception
                # handler above.
                pass

    # Step 4: Check derivations using verified base values
    # (in-process computation; cheap; runs even when budget exhausted)
    check_derivations(results)

    # Step 4b: the figure-identity path (IDENTITY_PATH=on): a figure's measure,
    # period, basis and scope against the company's own filings. Off, it is a no-op.
    # The reading started with the request; this waits only for what is left of
    # the budget, and the comparisons stop at the same deadline.
    results = apply_identity(results, raw_doc_text, reading=identity_reading,
                             deadline=sn_orchestrator_start + SN_BUDGET_SECONDS,
                             status=reader_status)
    if out_state is not None:
        out_state["readers_down"] = sorted(reader_status)

    # Step 4c: a close match within the figure's own rounding is a match; the
    # rest of the close band stays near, which the page shows as not equal.
    results = _structured_precedence(results)
    results = _settle_close(results)
    results = _bind_text_confirmations(results)

    # Step 5: Brave Search fallback for unverifiable claims.
    # Only attempt for claims with a real entity subject. Anonymous claims
    # ("Our platform", "Customer satisfaction") will produce false positives
    # because Brave matches on number coincidence across unrelated companies.
    #
    # Skip Brave entirely if the per-claim budget was exhausted: the user
    # is already past the wall-clock target, and Brave (5 sequential
    # network calls in a small thread pool) would extend the wait
    # further. The unverifiable claims stay unverifiable; the caller
    # renders the partial result as "incomplete verification" via the
    # existing decision_readiness pipeline.
    if budget_exhausted:
        import sys
        print(
            "[source-network] Brave Search fallback skipped: "
            "per-claim budget already exhausted",
            file=sys.stderr, flush=True,
        )
    if os.environ.get("BRAVE_API_KEY") and not budget_exhausted:
        unverified_indices = [
            i for i, r in enumerate(results)
            if r.verdict == "unverifiable"
            and is_likely_entity(r.decomposition.subject)
            and r.decomposition.value != 0
        ]
        # Cap Brave queries per request (cost control)
        brave_limit = min(len(unverified_indices), 5)
        if brave_limit > 0:
            brave_targets = unverified_indices[:brave_limit]
            # Phase 1.5: record the actual count of Brave
            # queries issued so the corpus monitoring path can
            # populate verification.brave_queries_used
            # correctly. The count is the SUBMITTED query count,
            # which equals the number of futures created below;
            # we record it before the executor runs so a partial
            # failure (some queries time out) still produces the
            # right "intent" count.
            if out_state is not None:
                out_state["brave_query_count"] = brave_limit
            with ThreadPoolExecutor(max_workers=3) as pool:
                brave_futures = {
                    pool.submit(
                        _timed_verify, verify_brave_search, results[i].decomposition
                    ): i
                    for i in brave_targets
                }
                for future in as_completed(brave_futures):
                    idx = brave_futures[future]
                    try:
                        sr = future.result()
                        if sr and sr.match_type != "no_data":
                            r = results[idx]
                            r.source_results.append(sr)
                            # Re-compute the combined verdict with the new source
                            verdict, confidence, detail = _consensus_for(
                                r.decomposition, r.source_results,
                            )
                            r.verdict = verdict
                            r.confidence = confidence
                            r.detail = detail
                            r.confidence_dimensions = decompose_confidence(
                                r.source_results
                            )
                    except Exception as e:
                        # Tolerated by design: Brave Search fallback
                        # is best-effort enrichment for claims the
                        # primary providers could not verify. A Brave
                        # API failure leaves the claim's verdict as
                        # whatever the primary providers established
                        # (typically "unverifiable"); the existing
                        # source_results stay intact. Log to stderr
                        # so the operator can investigate without
                        # breaking the JSON-RPC channel on stdout.
                        import sys
                        print(
                            f"[source_network.verify_claims] "
                            f"Brave fallback failed at idx {idx}: "
                            f"{type(e).__name__}: {e}",
                            file=sys.stderr,
                        )

    return results
