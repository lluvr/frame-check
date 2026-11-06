"""
Source Network: Multi-source claim verification.

Tier 1 of the FrameCheck verification cascade. Routes claims to
authoritative data sources (Wikipedia, World Bank,
CoinGecko), matches claim values against source data with context
awareness, and produces consensus verdicts.

Zero LLM. All computational. Free or near-free API calls.

Architecture:
  1. Decompose the claim (subject, metric, value, time, type)
  2. Route to 2-3 sources in parallel
  3. Context-aware matching against source data
  4. Consensus across sources -> verdict
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
from dataclasses import dataclass, field
from typing import Optional
import contextlib

from prose import plain_prose


# ================================================================
# Per-request operational counters
# ================================================================
#
# A counter is needed for the actual number of Brave Search queries
# issued during a verification run for the corpus telemetry path.
# The previous implementation used a
# threading.local sidecar, which broke under FastAPI's async
# dispatch: verify_claims_source_network runs on the analysis
# thread pool worker, but the corpus telemetry read happens on
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
    # caller worker reads this field directly off each
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


def _timed_verify(fn, decomp):
    """Run a per-source verifier and stamp the wall-clock
    latency on the returned SourceResult.

    Phase 1.6e item 4. The caller worker reads
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
    r'(?:(?:\s+(?:of|the|and|de|von|van|&))?\s+[A-Z][a-zA-Z]*[a-z])*)\b'
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
    r',\s+(?:and|while|but|with)\s+|;\s+|'
    r',\s+or\s+(?=[$€£¥₹])|'
    r'\s+and\s+(?:generated|spent|reported|posted|earned|had|made)\b|'
    r'\s+and\s+(?=(?:its\s+|the\s+)?(?:net\s+income|net\s+loss|revenues?|sales|'
    r'operating\s+\w+|gross\s+\w+|total\s+\w+|GDP|population)\b)|'
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
    "balance", "capex", "cash", "consumer", "density", "diluted", "eps",
    "exports", "full-year", "gravity", "headline", "highlights", "imports", "inflation", "internet", "inventory", "life",
    "literacy", "per", "population", "temperature", "unemployment",
    "urbanisation", "urbanization",
    # People and things a company answers to: "Shareholders received"
    "dividends", "employees", "engineers", "investors", "shareholders", "staff",
    # Stock exchanges, named beside a company: "(NYSE: ROL)"
    "nasdaq", "nyse",
})

# Words that make a heading a section label rather than a name.
_SECTION_WORDS = frozenset({
    "balance", "basics", "cash", "flow", "for", "full", "half", "headline",
    "highlights", "immediate", "inflation", "income", "metrics", "numbers",
    "release", "sheet",
    "snapshot", "standards", "statement", "year",
})
_HEADING_FILLER = frozenset({"a", "an", "and", "at", "for", "of", "the", "my", "our"})


# Followed by one of these, or by a word ending like a verb, a capitalized word
# opening a sentence is doing something, so it can be a name. "Apple reported"
# can; "Around $4 billion", "Rev $4 billion" and "How big" cannot.
_AFTER_A_NAME = frozenset({
    "is", "was", "are", "were", "has", "had", "have", "at", "will", "would",
    "made", "spent", "sold", "paid", "held", "stood", "saw", "lost", "grew",
    "rose", "fell", "ran", "said", "kept", "took", "built", "drew", "won",
})
_NOT_VERB_ENDING_S = frozenset({"this", "its", "his", "us", "plus", "less", "across"})


def _reads_as_a_name(word, sentence):
    """Whether a capitalized word opening a sentence is used as a name."""
    rest = sentence.lstrip()[len(word):]
    # "Toro's" and "Starbucks'" own something.
    if rest[:1] in ("'", "\u2019", ",", ":"):
        return True
    if word.endswith("ness"):
        return False
    following = re.match(r'\s+([a-z]+)', rest)
    if not following:
        return False
    next_word = following.group(1)
    return (
        next_word in _AFTER_A_NAME
        or next_word.endswith("ed")
        or (next_word.endswith("s") and next_word not in _NOT_VERB_ENDING_S)
    )


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
    # 1. Heading (best signal, but only if it names a specific entity)
    if heading:
        clean = re.sub(r'^#+\s*', '', heading).strip()
        clean = re.sub(r'^\d+\.\s*', '', clean).strip()
        clean = clean.split(':')[0].strip()
        if len(clean) >= 3 and clean.lower() not in _GENERIC_HEADINGS:
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
        acronyms = re.findall(r'\b([A-Z]{2,}(?:\s+[A-Z][a-z]+)*)\b', sentence)
        for a in acronyms:
            if (a not in _SENTENCE_STARTERS
                    and len(a) >= 2
                    and is_likely_entity(a)):
                return a

    # 4. Proper nouns in the sentence (Title Case words)
    if sentence:
        matches = [
            re.sub(r'^(?:The|A|An)\s+', '', found)
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
        r'\b(earnings\s+per\s+share|EPS|per\s+diluted\s+share)\b', re.IGNORECASE,
    ),
    "operating_income": re.compile(
        r'\b(operating\s+(?:income|profit)|income\s+from\s+operations)\b',
        re.IGNORECASE,
    ),
    "gross_profit": re.compile(r'\b(gross\s+profit)\b', re.IGNORECASE),
    "research_development": re.compile(
        r'\b(research\s+and\s+development|R&D)\b', re.IGNORECASE,
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
    "area": re.compile(r'\b(area|square\s+(?:km|miles?|kilomet(?:er|re)s?)|sq\s+km)\b', re.IGNORECASE),
    "height": re.compile(r'\b(height|tall|elevation|altitude)\b', re.IGNORECASE),
    "diameter": re.compile(r'\b(diameter|radius)\b', re.IGNORECASE),
    "weight": re.compile(r'\b(weight|mass|weighs?|kg|kilograms?|tonnes?)\b', re.IGNORECASE),
    "length": re.compile(r'\b(length|long|span|arm\s+span|mantle|runs?\s+for|stretch(?:es)?\s+for)\b', re.IGNORECASE),
    "lifespan": re.compile(r'\b(lifespan|life\s+span|life\s+expectancy|years?\s+old|longevity)\b', re.IGNORECASE),
    "price": re.compile(
        r'\b(price|cost|priced?\s+at|trading\s+at|(?<!economy\sis\s)(?<!economy\swas\s)worth)\b',
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

_COMPARED_YEAR_RE = re.compile(
    r'\b(?:than|compared\s+(?:to|with)|versus|vs\.?)\s+(?:in\s+|the\s+|fiscal\s+|'
    r'year\s+|FY\s*)*20[1-3]\d\b',
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
    return False


def _split_multi_figure_claims(claims):
    """One claim per clause when a sentence states figures in separate
    clauses: "Gross profit was $27B, while assets were $38B". Only one figure
    per claim is ever compared, so the other went unchecked. A comparison like
    "$60.9 billion, up 126% from $26.97 billion" stays one claim.
    """
    out = []
    for claim in claims:
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
            out.append({**claim, "sentence": clause.strip(), "numbers": held})
    return out


def _heading_names_something(heading, doc_text):
    """False for "Balance sheet" or "Full-Year 2025 Highlights", which label
    a section. Reading one as a name checks the figures against nothing, or
    against whatever page happens to carry those words.
    """
    clean = re.sub(r'^#+\s*', '', heading or "").split(':')[0].strip()
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


def _prepare_claims(claims, doc_text):
    """Give each claim the context it needs from the rest of the document."""
    _enrich_headings(claims, doc_text)
    for claim in claims:
        if not _heading_names_something(claim.get("heading"), doc_text):
            claim["heading"] = ""
    return _apply_discourse_context(
        _split_multi_figure_claims(claims), doc_text,
    )


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
                earlier = re.sub(r'^#+\s*', '', earlier).split(':')[0]
            if not earlier or _ANAPHORIC_OPENING_RE.match(earlier):
                continue
            named = extract_subject("", earlier)
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
                found = _TIME_RE.findall(earlier)
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
            "subject_ambiguous": len(named_so_far) > 1,
        })
    return out


def _metric_beside(sentence, raw_value):
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
    best, best_gap = "", None
    for name, pattern in _METRIC_PATTERNS.items():
        for found in pattern.finditer(sentence):
            gap = at - found.end() if found.end() <= at else found.start() - end
            # "about" and "some" only say it is a count of something.
            if name == "count":
                gap += 10_000
            if best_gap is None or gap < best_gap:
                best, best_gap = name, gap
    return best


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
    if inherited and _ANAPHORIC_OPENING_RE.match(sentence):
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
        if head and not subject and heading:
            subject = extract_subject(heading, "")
        # "7.6 percent in Chile": a place right after the figure owns it.
        if figure_at >= 0:
            after = sentence[figure_at + len(str(raw_value).strip()):]
            placed = re.match(
                r'\s*(?:[a-z]+\s+){0,2}?in\s+(?:the\s+)?(.{0,40})', after,
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

    # Detect metric type
    metric = _metric_beside(sentence, raw_value)

    # Detect time period from sentence, then heading as fallback.
    # Claims under "NVIDIA Fiscal Year 2026 Financial Summary" inherit
    # FY2026 even when the sentence itself has no year.
    # "lower than in fiscal 2025" is what the figure is set against.
    time_match = _TIME_RE.search(_COMPARED_YEAR_RE.sub('', sentence))
    if not time_match and heading:
        time_match = _TIME_RE.search(heading)
    time_period = time_match.group(1) if time_match else ""
    year_inherited = False
    if not time_period and claim.get("inherited_year"):
        time_period = claim["inherited_year"]
        year_inherited = True

    # Prior-year claims: when the sentence references "prior year" /
    # "previous year" / "last year" and this specific raw_value appears
    # right after that phrase, the claim is about the year BEFORE the
    # sentence/heading's main year. Decrement the year by 1 so SEC
    # EDGAR matches against the right period.
    if time_period and _is_prior_year_claim(sentence, raw_value):
        year_match = re.search(r'20[1-3]\d', time_period)
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
    # what the corpus telemetry pipeline records via the
    # SUBJECT_CLASSES enum in telemetry.py.
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
    if (
        any(raw_value.startswith(sym) for sym in "$€£¥₹")
        or any(sym in sentence for sym in "€£¥₹")
        or re.search(
            r'\b(?:dollars?|euros?|pounds?|yen|rupees?|usd|eur|gbp|jpy|inr)\b',
            sentence, re.IGNORECASE,
        )
    ):
        unit = "currency"
    elif raw_value.endswith("%") or "percent" in sentence.lower():
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

    return ClaimDecomposition(
        subject=subject,
        metric=metric,
        value=value,
        raw_value=raw_value,
        unit=unit,
        time_period=time_period,
        year_inherited=year_inherited,
        subject_ambiguous=subject_ambiguous,
        claim_type=claim_type,
        sentence=sentence,
        heading=heading,
        is_segment=is_segment,
    )


# ================================================================
# Sources
# ================================================================

_HEADERS = {"User-Agent": "FrameCheck/1.0 (contact@clarethium.com)"}
# Per-operation socket timeout for outbound provider calls. Bumped
# from 5s to 8s on 2026-05-06 after production probe from Fly ORD
# measured a single Wikipedia query (api.php query + extract round
# trip) at ~4.16s. The 5s budget left no headroom for SSL handshake
# variance and produced intermittent
# `URLError: <urlopen error _ssl.c:993: The handshake operation
# timed out>` lines in production logs that mapped to 0-of-N
# verified-claims surfaces for users (the "0 verified" symptom the
# builder reported). 8s is the smallest value that absorbs the
# observed handshake variance without doubling the wait on real
# provider failures.
#
# Trade-off: slow providers fail 3s later than before. The outer
# SN_FETCH_JSON_DEADLINE_SECONDS (12s) and SN_BUDGET_SECONDS (25s)
# still bound the total per-comparison wait; bumping the per-op
# timeout only affects whether a single hung socket gets one more
# read attempt before the outer bound fires.
#
# Override via SN_PER_OP_TIMEOUT_SECONDS env var so you can
# tighten when production network paths improve, or further loosen
# during a transient routing problem to a specific provider.
def _read_float_env(name: str, default: float) -> float:
    """Read a float env var with a default. A malformed value (non-numeric
    or zero/negative) falls back to the default with a stderr log so you
    see it; never raises at module import time. The default is
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
# via SN_BUDGET_SECONDS env when production telemetry shows the p95 has
# drifted (you read `[source-network] budget exhausted` log
# frequency to calibrate).
#
# Architectural compromise named explicitly: this is a BEST-EFFORT
# budget. Worker threads inside the per-claim ThreadPoolExecutor cannot
# be truly cancelled in Python; when budget is exhausted the orchestrator
# stops waiting and returns partial results, but background HTTP calls
# already in flight continue until their per-call _TIMEOUT or natural
# return. They do not extend the user-visible request time but do
# consume CPU/network until they finish. The proper fix is to migrate
# the SN call graph to asyncio with task cancellation (post-1.0.0
# work); until then the budget primitive
# below trades thread-cleanup precision for a bounded user wait, which
# is the trade the user-facing UX requires today.
SN_BUDGET_SECONDS = float(os.environ.get("SN_BUDGET_SECONDS", "25"))


# ================================================================
# External-provider health tracking
# ================================================================
#
# Source Network calls out to ~10 external APIs (Brave, CoinGecko,
# Wikipedia, FRED, Alpha Vantage, World Bank,
# Wolfram, SEC EDGAR, Github) on every analysis with extractable
# claims. Pre-2026-04-30 the only signal that a provider was
# degraded was stderr log lines from _fetch_json; you had
# to grep `fly logs` to learn that CoinGecko had been 429-ing all
# afternoon. Verifications silently degraded.
#
# This tracker maintains an in-memory rolling-window error count
# per provider so /health can surface a structured snapshot.
# Window is 1 hour; older errors fall off. Thread-safe via a
# single lock. Memory-bounded by the number of providers (small)
# and the window length (~3600 entries per provider in the worst
# case of one error per second). Process-local: matches the
# existing telemetry patterns and does not need cross-machine
# aggregation for the log-grep use case.

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
                    # consumers (dashboards, fly logs greps)
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


_PROVIDER_DOMAINS = (
    ("brave.com", "brave"),
    ("coingecko.com", "coingecko"),
    ("wikipedia.org", "wikipedia"),
    ("stlouisfed.org", "fred"),
    ("alphavantage.co", "alpha_vantage"),
    ("worldbank.org", "world_bank"),
    ("restcountries.com", "rest_countries"),
    ("wolframalpha.com", "wolfram"),
    ("sec.gov", "sec_edgar"),
    ("github.com", "github"),
)


def _provider_from_url(url: str) -> str:
    """Map a URL to a provider label by hostname suffix match.

    Returns one of the eleven closed-enum values: the ten provider
    labels declared in ``_PROVIDER_DOMAINS`` (``brave`` /
    ``coingecko`` / ``wikipedia`` / ``fred`` / ``alpha_vantage`` /
    ``world_bank`` / ``rest_countries`` / ``wolfram`` / ``sec_edgar`` /
    ``github``) or ``"unknown"``. Strict suffix match (``host ==
    domain`` or ``host.endswith('.' + domain)``) so an attacker-
    controlled hostname such as ``alphavantage.evil.com`` cannot be
    misclassified as the legitimate provider. The closed-enum return
    contract is load-bearing for log sanitation: callers pass the
    return value to ``sys.stderr.write`` for ops diagnostics, and
    the closed enum guarantees no URL-derived material (path, query
    string, basic-auth credentials) reaches the log.
    """
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except Exception:
        return "unknown"
    host = host.lower()
    for domain, label in _PROVIDER_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return label
    return "unknown"


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
# discarded one. Env-overridable for further tuning.
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
            # so triage from fly logs sees
            # "_FuturesTimeoutError" not the suppressed diagnostic
            # exception class. getattr(req, "full_url", str(req))
            # also handles the string-URL case defensively.
            with contextlib.suppress(Exception):
                import sys
                full_url = getattr(req, "full_url", str(req))
                provider = _provider_from_url(full_url)
                provider_health.record_error(provider, "deadline")
                sys.stderr.write(
                    f"[source-network] urlopen({provider}): "
                    f"caller-side deadline {deadline:.1f}s exceeded; "
                    f"thread continues in background\n"
                )
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
    actionable signal. Caller-side deadline exhaustion is
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
            sys.stderr.write(
                f"[source-network] _fetch_json({provider}): "
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
            with contextlib.suppress(Exception):
                if exc.code == 429:
                    kind_label = "rate_limited"
                elif exc.code in (403, 401):
                    kind_label = "auth"
                elif 500 <= exc.code < 600:
                    kind_label = "server_error"
        provider_health.record_error(provider, kind_label)
        sys.stderr.write(
            f"[source-network] _fetch_json({provider}): "
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
    ("km", r'km|kilomet(?:re|er)s?'),
    ("cm", r'cm|centimet(?:re|er)s?'),
    ("m", r'm|met(?:re|er)s?'),
    ("ft", r'ft|feet|foot'),
    ("mi", r'mi|miles?'),
    ("kg", r'kg|kilograms?'),
    ("t", r'tonnes?|tons?'),
    ("lb", r'lbs?|pounds?'),
)
_UNIT_ALTERNATION = "|".join(pat for _, pat in _UNIT_FAMILIES)
_UNIT_TOKEN_RE = re.compile(r'\b(' + _UNIT_ALTERNATION + r')\b', re.IGNORECASE)
# The unit directly after a number, reading through the far end of a
# range: "12,000 to 15,260 ft" is in feet.
_UNIT_AFTER_NUMBER_RE = re.compile(
    r'\s*(?:(?:to|-|\u2013)\s*[\d,.]+\s*)?(' + _UNIT_ALTERNATION + r')\b',
    re.IGNORECASE,
)
_SENTENCE_BREAK_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z(\[])|\n+')


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
    r'users?|customers?|subscribers?|employees?|speakers?)\b',
    re.IGNORECASE,
)
_METRIC_EVIDENCE_REACH = 60


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
        tolerance = min(tolerance, 0.02)

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
    if decomp and decomp.unit in ("distance", "mass"):
        unit_token = _UNIT_TOKEN_RE.search(claim_sentence)
        claim_unit = _unit_family(unit_token.group(1)) if unit_token else ""
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
        # claim_value == 0 was guarded at function entry (see early
        # return above); ratio == 0 only when num_val == 0, which the
        # candidate-extraction layer filters before this loop.
        ratio = num_val / claim_value
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
            left, right = _sentence_bounds(text, num_start, num_end)
            passage = text[left:right]
            # A dollar figure for a named year must be from that year. Filings
            # answer these claims; this only stops reference prose about some
            # other period confirming one when a filing could not be read.
            if decomp.unit == "currency" and decomp.time_period:
                claim_year = re.search(r'20[0-3]\d', decomp.time_period)
                if claim_year and claim_year.group() not in passage:
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
    try:
        raw_cleaned = decomp.raw_value.strip().lstrip("$~").rstrip("%")
        raw_cleaned = re.sub(r'[TBMKk]$', '', raw_cleaned).replace(",", "")
        raw_float = float(raw_cleaned)
    except (ValueError, AttributeError):
        raw_float = 0.0
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
#
# The country regexes and canonical map live in entity_data.py (shared
# with entity_classifier.py). Hosting them in a third module breaks
# what would otherwise be a bidirectional import cycle between
# source_network and entity_classifier. Re-imported here so existing
# call sites that read these names from source_network keep resolving
# without an attribute migration.
from entity_data import (  # noqa: E402
    _COUNTRY_NAMES_RE,
    _COUNTRY_ABBREV_RE,
    _COUNTRY_CANONICAL,
)


def _claim_country(decomp):
    """The country a claim is about: an inherited subject counts, since
    "Its GDP that year" names none of its own."""
    if decomp.subject and _COUNTRY_NAMES_RE.fullmatch(decomp.subject):
        return decomp.subject
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

def _detect_wb_indicator(sentence, metric):
    """Detect which World Bank indicator to query.

    Branch order matters: more-specific matches must run before
    broader ones. "GDP per capita" contains "gdp", so the per-capita
    branch MUST be checked first or every per-capita claim collapses
    to the total-GDP indicator (calibration finding B.2, 2026-04-16).
    """
    text = sentence.lower()
    # A figure's own metric first: "a population of 2 million enjoys a life
    # expectancy of 82 years" mentions both.
    if metric == "population":
        return "SP.POP.TOTL", "Population"
    if metric == "lifespan":
        return "SP.DYN.LE00.IN", "Life expectancy"
    if "per capita" in text or "gdp per head" in text:
        return "NY.GDP.PCAP.CD", "GDP per capita"
    if metric == "gdp" or "gdp" in text or "gross domestic" in text:
        return "NY.GDP.MKTP.CD", "GDP (current US$)"
    if metric == "population" or "population" in text:
        return "SP.POP.TOTL", "Population"
    if metric == "area":
        return "AG.SRF.TOTL.K2", "Surface area (sq. km)"
    if "life expectancy" in text or metric == "lifespan":
        return "SP.DYN.LE00.IN", "Life expectancy"
    if "inflation" in text or "cpi" in text:
        return "FP.CPI.TOTL.ZG", "Inflation rate"
    if "unemployment" in text:
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
    r'\b(?:people|residents|inhabitants)\s+lived\s+in\b',
    re.IGNORECASE,
)

# Canonical names the World Bank spells differently.
_WB_COUNTRY_ALIASES = {
    "south korea": "KR", "korea": "KR", "north korea": "KP",
    "russia": "RU", "turkey": "TR", "egypt": "EG", "iran": "IR",
    "vietnam": "VN", "venezuela": "VE", "yemen": "YE", "syria": "SY",
    "laos": "LA", "slovakia": "SK", "czech republic": "CZ",
    "czechia": "CZ", "european union": "EU",
}
# Filled once per process from the World Bank's own country list.
_WB_COUNTRY_CODES = {}
_MONTH_NAME_RE = re.compile(
    r'\b(January|February|March|April|May|June|July|August|September|'
    r'October|November|December)\b'
)
_AMBIGUOUS_PLACE_NAMES = frozenset({"georgia", "jordan", "chad", "turkey"})
_WB_TOTAL_INDICATORS = frozenset({
    "SP.POP.TOTL", "NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "AG.SRF.TOTL.K2",
})


def _wb_country_code(country):
    """ISO2 code for a country, from the World Bank itself.

    This used to come from restcountries.com. When that retired v1-v4,
    every World Bank check silently returned no_data with it.
    """
    name = country.lower()
    if name in _WB_COUNTRY_ALIASES:
        return _WB_COUNTRY_ALIASES[name]
    if not _WB_COUNTRY_CODES:
        listing = _fetch_json(
            "https://api.worldbank.org/v2/country?format=json&per_page=400"
        )
        if not listing or len(listing) < 2 or not listing[1]:
            return ""
        for row in listing[1]:
            if row.get("iso2Code") and row.get("name"):
                # "Egypt, Arab Rep." is also reachable as "egypt".
                full = row["name"].lower()
                _WB_COUNTRY_CODES[full] = row["iso2Code"]
                _WB_COUNTRY_CODES.setdefault(
                    full.split(",")[0], row["iso2Code"]
                )
    return _WB_COUNTRY_CODES.get(name, "")


def verify_world_bank(decomp):
    """Verify economic indicators against World Bank API."""
    country = _claim_country(decomp)
    if not country:
        return SourceResult(source_name="World Bank", match_type="no_data")

    indicator_id, indicator_name = _detect_wb_indicator(
        decomp.sentence, decomp.metric
    )
    if not indicator_id:
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

    date_param = f"date={year}" if year else "date=2020:2025"
    wb_url = (
        f"https://api.worldbank.org/v2/country/{iso2}/indicator/{indicator_id}"
        f"?{date_param}&format=json&per_page=5"
    )
    wb_data = _fetch_json(wb_url)
    if not wb_data or len(wb_data) < 2 or not wb_data[1]:
        return SourceResult(source_name="World Bank", match_type="no_data")

    # Find the most recent non-null observation
    for obs in wb_data[1]:
        if obs.get("value") is not None:
            source_val = obs["value"]
            obs_year = obs.get("date", "")

            # World Bank GDP is in raw dollars. Normalize claim value
            # was already done by normalize_value().
            diff = abs(source_val - decomp.value) / max(abs(decomp.value), 1e-10)

            if diff < 0.05:
                match_type = "exact" if diff < 0.01 else "close"
            elif indicator_id == "AG.SRF.TOTL.K2":
                # This series put Canada at 15.6M square km against a true
                # 9.98M. It may confirm; it is not reliable enough to refute.
                match_type = "no_data"
            elif decomp.subject_ambiguous or (
                decomp.year_inherited and not _YEAR_REFERENCE_RE.search(
                    decomp.sentence,
                )
                # A country's headcount does not move this far between years,
                # so the year cannot explain the gap.
                and not (indicator_id == "SP.POP.TOTL" and diff > 0.15)
            ):
                match_type = "no_data"
            elif (_MONTH_NAME_RE.search(decomp.sentence)
                  or len(set(re.findall(r'20[0-3]\d', decomp.sentence))) > 1):
                # A rate for one month against an annual average.
                match_type = "no_data"
            elif not year and indicator_id != "SP.POP.TOTL":
                # With no period named, a moving figure that disagrees
                # may just be another year's. Population moves slowly
                # enough to be wrong regardless.
                match_type = "no_data"
            elif country.lower() in _AMBIGUOUS_PLACE_NAMES:
                # Georgia the state has about three times the people.
                match_type = "no_data"
            elif indicator_id in _WB_TOTAL_INDICATORS or diff < 1.0:
                match_type = "contradicted"
            else:
                # A rate this far off is usually a misparsed number.
                match_type = "no_data"

            return SourceResult(
                source_name="World Bank",
                source_url=f"https://data.worldbank.org/indicator/{indicator_id}?locations={iso2}",
                source_value=source_val,
                source_text=f"{indicator_name} ({obs_year}): {source_val:,.0f}",
                match_type=match_type,
                difference_pct=round(diff * 100, 1),
                confidence=0.9 if match_type == "exact" else 0.75 if match_type == "close" else 0.6,
            )

    return SourceResult(source_name="World Bank", match_type="no_data")


# ── CoinGecko ──
#
# _CRYPTO_NAMES lives in entity_data.py (shared with entity_classifier).
# Re-imported here so existing reads of ``source_network._CRYPTO_NAMES``
# keep resolving.
from entity_data import _CRYPTO_NAMES  # noqa: E402

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

_FRED_SERIES = {
    "gdp": ("GDP", "billions", 1e9),
    "gross domestic product": ("GDP", "billions", 1e9),
    "real gdp": ("GDPC1", "billions_chained_2017", 1e9),
    "unemployment": ("UNRATE", "percent", 1),
    "unemployment rate": ("UNRATE", "percent", 1),
    "inflation": ("FPCPITOTLZGUSA", "percent", 1),
    "inflation rate": ("FPCPITOTLZGUSA", "percent", 1),
    "cpi": ("CPIAUCSL", "index", 1),
    "consumer price index": ("CPIAUCSL", "index", 1),
    "federal funds rate": ("FEDFUNDS", "percent", 1),
    "interest rate": ("FEDFUNDS", "percent", 1),
    "fed funds": ("FEDFUNDS", "percent", 1),
    "national debt": ("GFDEBTN", "millions", 1e6),
    "debt": ("GFDEBTN", "millions", 1e6),
    "population": ("POPTHM", "thousands", 1e3),
    "housing starts": ("HOUST", "thousands", 1e3),
    "industrial production": ("INDPRO", "index", 1),
    "retail sales": ("RSXFS", "millions", 1e6),
    "trade balance": ("BOPGSTB", "millions", 1e6),
    "money supply": ("M2SL", "billions", 1e9),
    "m2": ("M2SL", "billions", 1e9),
}


def verify_fred(decomp):
    """Verify macroeconomic claims against FRED."""
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        return SourceResult(source_name="FRED", match_type="no_data")

    # Find the matching FRED series
    sentence_lower = decomp.sentence.lower()
    series_id = None
    unit_desc = ""
    unit_scale = 1

    for keyword, (sid, udesc, uscale) in _FRED_SERIES.items():
        if keyword in sentence_lower or keyword in decomp.metric:
            series_id = sid
            unit_desc = udesc
            unit_scale = uscale
            break

    if not series_id:
        return SourceResult(source_name="FRED", match_type="no_data")

    # Query FRED for the most recent observation
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={api_key}"
        f"&file_type=json&sort_order=desc&limit=5"
    )
    data = _fetch_json(url)
    if not data or "observations" not in data:
        return SourceResult(source_name="FRED", match_type="no_data")

    # Find the most recent non-null observation
    for obs in data["observations"]:
        if obs.get("value") and obs["value"] != ".":
            source_val_raw = float(obs["value"])
            source_val = source_val_raw * unit_scale
            obs_date = obs.get("date", "")

            diff = abs(source_val - decomp.value) / max(abs(decomp.value), 1e-10)
            if diff < 0.01:
                match_type = "exact"
            elif diff < 0.05:
                match_type = "close"
            elif diff < 0.15:
                match_type = "close"
            else:
                match_type = "contradicted" if diff < 2.0 else "no_data"

            return SourceResult(
                source_name="FRED",
                source_url=f"https://fred.stlouisfed.org/series/{series_id}",
                source_value=source_val,
                source_text=f"{series_id} ({obs_date}): {source_val_raw:,.1f} {unit_desc}",
                match_type=match_type,
                difference_pct=round(diff * 100, 1),
                confidence=0.95 if match_type == "exact" else 0.8,
            )

    return SourceResult(source_name="FRED", match_type="no_data")


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
        try:
            raw_cleaned = decomp.raw_value.strip().lstrip("$~").rstrip("%")
            raw_cleaned = re.sub(r'[TBMKk]$', '', raw_cleaned).replace(",", "")
            raw_float = float(raw_cleaned)
        except (ValueError, AttributeError):
            raw_float = 0.0
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

    compare_val = decomp.value if abs(matched_val - decomp.value) < abs(matched_val) * 0.1 else decomp.value
    diff = abs(matched_val - compare_val) / max(abs(compare_val), 1e-10)
    match_type = "exact" if diff < 0.01 else "close" if diff < 0.05 else "contradicted"

    return SourceResult(
        source_name="Wolfram Alpha",
        source_url="https://www.wolframalpha.com/input?i=" + urllib.parse.quote(query),
        source_value=matched_val,
        source_text=f"Wolfram: {result[:150]}",
        match_type=match_type,
        difference_pct=round(diff * 100, 1),
        confidence=0.9 if match_type == "exact" else 0.75,
    )


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
# How long to skip retry after a failed tickers download.
# Overridable via SN_SEC_TICKERS_RETRY_AFTER_SECONDS. The default
# balances two costs: too-short retries hammer SEC after a flaky
# cold-start, too-long retries lock SEC verification out of the
# worker for an excessive window after the upstream recovers. 60s
# is a long-enough cool-down to absorb a typical CDN hiccup and a
# short-enough one that you do not see "0 verified" on
# repeated user requests after the network heals.
_SEC_TICKERS_RETRY_AFTER = float(
    os.environ.get("SN_SEC_TICKERS_RETRY_AFTER_SECONDS", "60")
)
_SEC_HEADERS = {"User-Agent": "FrameCheck/1.0 (contact@clarethium.com)"}


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
        # Probe both layouts: top-level (the Docker image bakes the file
        # at /app/data next to a top-level module) and src-layout dev
        # (this module lives under src/, so data/ is one level up at the
        # repo root). First existing candidate wins; absent on the MCP
        # wheel, which falls through to the runtime fetch below.
        _here = os.path.dirname(os.path.abspath(__file__))
        bundled_path = os.path.join(_here, "data", "sec_company_tickers.json")
        if not os.path.isfile(bundled_path):
            bundled_path = os.path.join(
                os.path.dirname(_here), "data", "sec_company_tickers.json",
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


_COMMON_NOUN_BLACKLIST = frozenset({
    # First words of several companies: which one is a guess, and a wrong
    # guess passes off another company's filings as this claim's check.
    "delta", "united", "american", "general", "first", "chase",
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
    "partners", "partnership", "international", "global", "national",
    "regional", "investment", "investments", "capital", "fund",
    "funds", "trust", "ventures", "consulting", "solutions", "systems",
    "growth", "challenges", "outlook", "findings",
})


def _find_cik(subject):
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
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsAndShortTermInvestments"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "total_assets": ["Assets"],
    "inventory": ["InventoryNet"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
}


# Words broad enough to match inside a more specific figure: "earnings" in
# "earnings per share". Named figures have their own concept above.
_SEC_BROAD_METRICS = frozenset(
    {"revenue", "profit", "operating_expenses", "cash"}
)
_SEC_UNIT_KEYS = {"eps": "USD/shares"}
_SEC_METRIC_LABELS = {
    "profit": "net income", "eps": "diluted EPS",
    "research_development": "R&D", "operating_cash_flow": "operating cash flow",
    "total_assets": "total assets", "capex": "capital expenditures",
}
_SEC_OTHER_FIGURE_RE = re.compile(
    r'\b(per[\s-]+share|EPS|EBITDA|margins?|gross\s+(?:profit|income)|'
    r'operating\s+(?:profit|income|margin)|cost\s+of\s+(?:goods|revenue|sales))\b',
    re.IGNORECASE,
)


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


def _end_year(filing):
    """Extract the calendar year of an XBRL entry's end date.

    Returns int year or None if the end field is missing or malformed.
    Used to match SEC EDGAR entries by actual data period rather than
    by the filing's fy field (which can include comparative data from
    prior years).
    """
    end = filing.get("end", "")
    if len(end) >= 4 and end[:4].isdigit():
        return int(end[:4])
    return None


def verify_sec_edgar(decomp):
    """Verify company financials against SEC EDGAR filings.

    The most authoritative source for US public company data.
    Returns the value the company actually reported to the SEC.
    """
    if not decomp.subject:
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

    cik, ticker = _find_cik(decomp.subject)
    if not cik:
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
        r'\bnet\s+loss\b', decomp.sentence, re.IGNORECASE,
    ):
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

    for concept in concepts_to_try:
        url = (
            f"https://data.sec.gov/api/xbrl/companyconcept/"
            f"CIK{cik}/us-gaap/{concept}.json"
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

        units = data.get("units", {}).get(
            _SEC_UNIT_KEYS.get(metric_lower, "USD"), [],
        )
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
        # lets the consensus mechanism fall through to Wikipedia
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
            # Do NOT fall back to 10-K. Honest no_data beats a
            # confident contradiction computed against the wrong
            # period.
        else:
            filtered = [
                u for u in units
                if u.get("form") == "10-K" and u.get("fp") == "FY"
                and _spans_a_year(u)
            ]

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
            own_year = [f for f in filtered if f.get("fy") == target_fy]
            newest = max((f.get("end", "") for f in own_year), default="")
            exact_year_entries = [
                f for f in filtered
                if _end_year(f) == target_fy
                or (f.get("fy") == target_fy and f.get("end", "") == newest)
            ]
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
    match_type = (
        "exact" if best_diff < 0.005
        else "close" if best_diff < 0.03
        else "contradicted"
    )

    # With two years in the sentence we cannot tell which one this number
    # belongs to, so a mismatch proves nothing. A true claim contradicted
    # is the worst error this tool can make.
    if (match_type == "contradicted"
            and len(set(re.findall(r'20[1-3]\d', decomp.sentence))) > 1):
        return SourceResult(source_name="SEC Filing", match_type="no_data")

    # A year carried over from an earlier sentence can confirm, but only a
    # sentence pointing back at it can refute.
    if (match_type == "contradicted" and decomp.year_inherited
            and not _YEAR_REFERENCE_RE.search(decomp.sentence)):
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

    if form == "10-Q":
        figure = f"${val_display:,.1f}{val_unit}" if val_unit else f"${val_display:,.2f}"
        filing_label = f"{ticker} {fp} FY{fy} {metric_label}, 10-Q filed {filed}: {figure}"
        filing_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-Q"
    else:
        figure = f"${val_display:,.1f}{val_unit}" if val_unit else f"${val_display:,.2f}"
        filing_label = f"{ticker} FY{data_year} {metric_label}, 10-K filed {filed}: {figure}"
        filing_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K"

    return SourceResult(
        source_name="SEC Filing",
        source_url=filing_url,
        source_value=best_val,
        source_text=filing_label,
        match_type=match_type,
        difference_pct=round(best_diff * 100, 1),
        confidence=0.95 if match_type == "exact" else 0.85,
    )


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
    except Exception:
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
    match_type = (
        "exact" if best_diff < 0.01
        else "close" if best_diff < 0.025
        else "contradicted" if best_diff < 0.25
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
    attached to the decomp so downstream display and telemetry paths
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
        if decomp.metric in ("gdp", "population", "lifespan") or \
           any(kw in sentence_lower for kw in ["gdp", "population", "life expectancy",
               "unemployment", "inflation", "poverty", "literacy"]):
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
    if (os.environ.get("FRED_API_KEY")
            and _claim_country(decomp) in (None, "United States")):
        if decomp.metric in ("gdp",) or \
           any(kw in sentence_lower for kw in ["gdp", "unemployment", "inflation",
               "cpi", "interest rate", "federal funds", "money supply",
               "national debt", "industrial production", "retail sales"]):
            sources.append(verify_fred)

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
# Consensus
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
    # Filter to results that found data. A web snippet never decides a
    # verdict in either direction: any page repeating the digits would
    # confirm a false figure. It is reported as a lead the reader can
    # follow.
    with_data = [
        r for r in results
        if r.match_type != "no_data" and not r.is_web_search
    ]

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


def check_derivations(results):
    """Post-process Source Network results to flag fabricated derivations.

    For growth rate claims: finds base values in the same document section,
    recomputes the growth rate, and flags if the claimed rate doesn't match.

    Mutates results in place (updates verdict and detail for caught derivations).
    """
    # Build a lookup of verified values by heading
    verified_values = {}  # heading -> [(value, source_name)]
    for r in results:
        if r.verdict in ("verified", "close") and r.decomposition.heading:
            heading = r.decomposition.heading
            if heading not in verified_values:
                verified_values[heading] = []
            verified_values[heading].append(
                (r.decomposition.value, r.best_source)
            )

    for r in results:
        if r.decomposition.claim_type != "derived":
            continue

        sentence = r.decomposition.sentence
        # Check for growth rate claims
        gm = _GROWTH_RE.search(sentence)
        if gm:
            claimed_pct = float(gm.group(1))
            # Find two base values in the same section that could be
            # current and prior period values
            heading = r.decomposition.heading
            if heading and heading in verified_values:
                values = [v for v, _ in verified_values[heading]]
                # Try all pairs as (current, prior)
                for i, current in enumerate(values):
                    for j, prior in enumerate(values):
                        if i == j or prior == 0:
                            continue
                        actual_pct = (current - prior) / abs(prior) * 100
                        if abs(actual_pct - claimed_pct) > 2.0:
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

    Callers that need the Brave query count for telemetry pass
    an empty dict and read the value after the call returns.
    Callers that do not need it omit the parameter.
    """
    # Phase 1.5: record the Brave query count via the out_state
    # dict so the caller observes it on the same execution
    # context that issued the verification call. See module
    # docstring for the threading.local issue this replaced.
    if out_state is not None:
        out_state["brave_query_count"] = 0

    if not claims:
        return []

    doc_text = plain_prose(doc_text)

    # Compute the document's primary entity once. Sentences that lack
    # their own entity name will inherit this as a fallback subject,
    # so claims like "Common side effects include nausea (44%)" in an
    # Ozempic document get verified as Ozempic claims instead of being
    # rejected as anonymous.
    claims = _prepare_claims(claims, doc_text)
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
    # cannot block past the per-call deadline.
    sn_orchestrator_start = time.monotonic()

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
                cached = _get_cached_article(decomp.subject)
                result = verify_wikipedia(decomp, _cached_article=cached)
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
                        # zero verifications with no
                        # visibility. The verifier name is included
                        # so you can identify which source
                        # is failing from `fly logs`.
                        import sys
                        sys.stderr.write(
                            f"[source-network] {fn_name} raised "
                            f"{type(exc).__name__}: {exc}\n"
                        )

        # Consensus
        verdict, confidence, detail = _consensus_for(decomp, source_results)

        # Find best source for display
        best = None
        for r in source_results:
            if r.match_type in ("exact", "close"):
                if best is None or r.confidence > best.confidence:
                    best = r

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
    # configurations: production is 25s, no realistic
    # configuration sub-100ms returns useful provider results. Without
    # this guard, the in-loop budget check races against per-claim
    # workers; on fast systems with already-failing workers (e.g.
    # malformed claim shapes raising AttributeError on submit), the
    # workers complete and the loop's exception handler runs BEFORE
    # the budget check fires, silently disengaging the budget primitive.
    # Bypassing pool creation entirely under sub-100ms budget makes the
    # fast-fail path deterministic across system speeds and tightens
    # behavior under debugging without changing production.
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
    else:
        pool = ThreadPoolExecutor(max_workers=5)
    try:
        if not budget_exhausted:
            futures = {pool.submit(_verify_one, c): i for i, c in enumerate(claim_list)}
            indexed_results = {}

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
                # Tolerated by design: per-claim verification
                # failures MUST NOT block the rest of the claim
                # pool. The "Return in original order" loop below
                # only emits results for indices that resolved;
                # claims that failed simply do not appear in the
                # downstream verification list and the caller sees
                # the verified subset. Log to stderr so you
                # can investigate without breaking the
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
        elif budget_exhausted:
            # Construct a minimal unverifiable result so downstream
            # rendering treats this claim as "not verified" rather
            # than "absent." Decomposition is required for the
            # rendering path to extract sentence + heading; build it
            # the same way _verify_one does (no provider calls, just
            # decomposition).
            with contextlib.suppress(Exception):
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
                    detail="Verification budget exhausted before this claim was processed.",
                ))
    # Step 4: Check derivations using verified base values
    # (in-process computation; cheap; runs even when budget exhausted)
    check_derivations(results)

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
            # queries issued so the corpus telemetry path can
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
                            # Re-compute consensus with the new source
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
                        # so you can investigate without
                        # breaking the JSON-RPC channel on stdout.
                        import sys
                        print(
                            f"[source_network.verify_claims] "
                            f"Brave fallback failed at idx {idx}: "
                            f"{type(e).__name__}: {e}",
                            file=sys.stderr,
                        )

    return results
