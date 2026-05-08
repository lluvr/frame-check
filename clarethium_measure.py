#!/usr/bin/env python3
"""
Clarethium Measure: AI Output Measurement Tool (v1.5.0)

Decomposes AI-generated text into 10 measurable properties (~6-7 effective
dimensions; 3 pairs share constructs). 9/10 layers are zero-LLM (pure regex
+ string matching). See module docstring for field positioning
against SelfCheckGPT, FActScore, MiniCheck, RAGAS.
Gate 0 (Layer 1a) requires Gemini API and is non-deterministic.

VERSION HISTORY:

  v1.5.0 (2026-04-17)
    - Layer 11: scope_assessment dict added to grounding_decomposition
      return. Reports derivation_regime (diagnostic/transition/saturated)
      based on source_num_count, with note_user_facing for UI display.
      Addresses Monte-Carlo-verified saturation of _gfp_is_derivable on
      number-dense sources. See LAYER_11_SCOPE_BOUNDARY.md.
    - interpretation_note updated to reference derivation_regime.

  v1.4 (2026-04-11)
    - source_fidelity: key rename from fabrication_rate to instability_rate.
    - Multi-currency regex ([$€£¥₹]) for dollar/euro/yen/pound/rupee.
    - Scaled-integer extraction pattern ("6 million" outside currency).
    - Paragraph-aware sentence splitter (joins wrapped lines).

CONSTRUCT DEFINITIONS (what each layer actually measures):
  1. Structural Profile. How much the document's surface structure deviates from
     the model's default generation pattern. NOT quality. Style classification.
  2. Claim Density. Count of sentences containing specific numbers or causal assertions.
     Measures claim VOLUME, not claim accuracy.
  3. Temporal Instability. Fraction of numbers that change between independent
     generations of the same prompt. Instability implies generation, not retrieval.
     Cannot detect fixed-point confabulation (stable wrong numbers).
  4. Source Fidelity. Fraction of digit-formatted numbers not found via string
     search in provided source material. Measures SOURCE FIDELITY for formatted numbers.
  5. Entity Provenance. Proper nouns, org names, and citations not found in source.
     Measures whether named entities come from source or model training data.
  6. Vocabulary Proximity. Fraction of content words in each sentence that also
     appear in source. Measures LANGUAGE overlap, not factual accuracy.
  7. Presentation Features. Surface formatting characteristics (vocabulary diversity,
     readability, assertiveness, formatting density).
  8. Epistemic Calibration. For assertive sentences, whether grounding evidence
     exists (sourced number, entity, or vocabulary overlap). Cross-layer metric.
  9. Information Novelty. Per-sentence fraction of content words not seen in prior
     sentences. Measures information density vs repetition.
 10. Quality Profile. Composite substance index (fidelity layers) vs presentation
     index (surface layers). Gap = overclaiming signal.

SCOPE:
  Primary: Markdown analytical documents (strategic analysis). 2-3 generators
  (Gemini, xAI/Grok, GPT). English only.
  Cross-domain tested (v1.2): Product specs, research summaries, code documentation.
  Source matching and temporal consistency transfer. Structural profile reference
  distributions may not apply. Entity provenance low-N across all types.
  NOT validated on: non-English, non-markdown formats, conversational text.

WHAT THIS TOOL CANNOT DETECT:
  - Causal/interpretive fabrication (invisible to all layers)
  - Stable fabrication (consistently wrong numbers that repeat across generations)
  - Content depth or reasoning quality (partially addressed by epistemic
    calibration and information novelty: surface proxies, not semantic)
  - Human-perceived quality (structural layers are orthogonal: r≈0.1)
  - Numbers expressed as words ("fifty percent"), relative claims ("doubled")

API:
  measure(doc, source=None, comparisons=None, topic=None) → dict
  Each layer also callable independently.

CLI:
  python clarethium_measure.py --doc file.md [--source ref.md] [--compare v2.md v3.md] [--topic "..."]
"""

__version__ = "1.5.0"

import argparse
import json
import math
import re
import statistics
import sys
import os
import time


# ================================================================
# REFERENCE DATA (from 240 validated documents, 5 conditions)
# ================================================================
# Corpus: FPR estimation (70), cross-generator (120), refined corpus (90)
# All markdown analytical documents, generators: Gemini, xAI, GPT

REFERENCE = {
    "mechanism_ratio": {
        "BASIC":    {"mean": 0.861, "sd": 0.194, "N": 60},
        "STANDARD": {"mean": 0.884, "sd": 0.163, "N": 110},
        "PROTOCOL": {"mean": 0.817, "sd": 0.267, "N": 30},
        "GAMING_V2": {"mean": 0.976, "sd": 0.029, "N": 20},
    },
    "assertion_ratio": {
        "BASIC":    {"mean": 0.409, "sd": 0.161, "N": 60, "mean_matches": 11},
        "STANDARD": {"mean": 0.559, "sd": 0.283, "N": 110, "mean_matches": 7},
        "PROTOCOL": {"mean": 0.397, "sd": 0.292, "N": 30, "mean_matches": 4},
        "GAMING_V2": {"mean": 0.873, "sd": 0.116, "N": 20, "mean_matches": 29},
    },
    "source_matching": {
        # Source-matching study, N=24, grok-4-1-fast, 3 topics
        "T1_BASIC":   {"mean_unsourced": 0.018, "N": 6, "mean_numbers": 79},
        "T2_STANDARD": {"mean_unsourced": 0.025, "N": 6, "mean_numbers": 76},
        "T3_REFINED":  {"mean_unsourced": 0.113, "N": 6, "mean_numbers": 86},
        "T4_AGENTIC":  {"mean_unsourced": 0.095, "N": 6, "mean_numbers": 83},
    },
    "thresholds_note": (
        "All thresholds below are EXPLORATORY. Calibrated on the same data used "
        "for discovery. mechanism_ratio cross-validated on 3 datasets. "
        "Gate 0 and assertion_ratio thresholds are post-hoc. "
        "Use reference distributions for interpretation, not thresholds."
    ),
}


# ================================================================
# STOP WORDS (shared across layers)
# ================================================================

STOP_WORDS = set("""
a an the and or but if in on at to for of with by from as is are was were
be been being have has had do does did will would shall should can could
may might must need not no nor so yet also just only even still already
than then that this these those it its he she they them their his her we
our you your i me my which what when where who whom how why all each
every any some most more less much many few several both either neither
into onto upon about above below between through during before after
since until while however therefore moreover furthermore although because
versus via per etc vs often very quite rather too such like
""".split())


# ================================================================
# LAYER 1: STRUCTURAL PROFILE
# ================================================================
# Construct: Surface structure deviation from model defaults.
# NOT a quality measure. Orthogonal to fabrication (r≈0.1).

# --- Gate 0: Heading defaultness ---

def extract_headings_simple(text):
    """Extract ## and ### headings from markdown."""
    headings = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("## ") or line.startswith("### "):
            h = re.sub(r'^#+\s*', '', line).strip()
            h = re.sub(r'\*+', '', h).strip()
            if h:
                headings.append(h)
    return headings


def gate_0(doc_text, topic_task, gem_client=None, n_baselines=3):
    """Heading-baseline Jaccard overlap. Lower = more non-default.

    Requires Gemini API for baseline generation (~$0.01/doc).
    Returns None if API unavailable.

    NON-DETERMINISTIC: Uses temperature=1.0 for baseline generation.
    Repeated calls produce different baselines and different scores.
    This is the only non-deterministic layer in the tool.
    """
    try:
        from _config import get_gemini_client, gemini_evaluate
    except ImportError:
        import warnings
        warnings.warn(
            "gate_0 requires _config module with Gemini API access. "
            "Skipping baseline generation.", UserWarning
        )
        return None

    doc_headings = extract_headings_simple(doc_text)
    if not doc_headings:
        return None

    if gem_client is None:
        gem_client = get_gemini_client()

    gen_model = "gemini-3.1-flash-lite-preview"
    prompt = (
        f"Write a thorough analysis of: {topic_task}\n\n"
        f"Write 600-800 words with 5-7 sections (## headings)."
    )

    baseline_heading_lists = []
    for _ in range(n_baselines):
        text = gemini_evaluate(
            prompt, model=gen_model, client=gem_client,
            max_output_tokens=4096, temperature=1.0, max_retries=3,
        )
        if text:
            baseline_heading_lists.append(extract_headings_simple(text))
        time.sleep(0.3)

    if not baseline_heading_lists:
        import warnings
        warnings.warn(
            "gate_0: Gemini API calls failed; no baselines generated. "
            "Skipping gate_0.", UserWarning
        )
        return None

    all_baseline_words = set()
    for bh in baseline_heading_lists:
        for h in bh:
            all_baseline_words.update(
                re.sub(r'[\*\d\.\s]+', ' ', h).lower().split()
            )

    matches = 0
    for h in doc_headings:
        hw = set(re.sub(r'[\*\d\.\s]+', ' ', h).lower().split())
        if hw:
            overlap = len(hw & all_baseline_words) / len(hw)
            if overlap > 0.5:
                matches += 1

    return round(matches / len(doc_headings), 4)


# --- Mechanism Ratio ---

MECHANISM_PATTERNS = [
    r"\bbecause\b", r"\bcauses\b", r"\bleads?\s+to\b",
    r"\bresults?\s+in\b", r"\bdue\s+to\b", r"\bdriven\s+by\b",
    r"\bmediated\s+by\b", r"\bthrough\s+the\s+mechanism\b",
    r"\bcontributes?\s+to\b", r"\bstems?\s+from\b",
    r"\bconsequently\b", r"\btherefore\b", r"\bthus\b",
    r"\bcreates?\s+(?:a|an|the)\b",
    r"\bprevents?\s+(?:a|an|the|this|that)\b",
    r"\bundermines?\b", r"\breinforces?\b", r"\bexacerbates?\b",
    r"\btriggers?\b",
    r"\breduces?\s+(?:a|an|the|this|that)\b",
    r"\bincreases?\s+(?:a|an|the|this|that)\b",
    r"\bdepends?\s+on\b", r"\bin\s+response\s+to\b",
]

BUZZWORD_PATTERNS = [
    r"\bfundamentally\b", r"\binherently\b", r"\bexponentially\b",
    r"\btransformative\b", r"\bparadigm\b", r"\bsynerg(?:y|istic)\b",
    r"\bholistically\b",
    r"\bleverage\b(?=\s+(?:the|this|that|our|their|your|its|a|an|existing|new|current|available|key|core|unique|critical|strategic|digital|modern|data|technology|AI|cloud))",
    r"\bosmosis\b",
    r"\bseamlessly\b",
    r"\brobust\b(?=\s+(?:framework|solution|approach|system))",
    r"\bcomprehensive\b(?=\s+(?:framework|solution|approach|strategy))",
    r"\bcritical(?:ly)?\s+important\b",
    r"\bgame.?changer\b", r"\bpivotal\b",
]

_MECH_RE = re.compile("|".join(MECHANISM_PATTERNS), re.IGNORECASE)
_BUZZ_RE = re.compile("|".join(BUZZWORD_PATTERNS), re.IGNORECASE)


def mechanism_ratio(text):
    """Causal reasoning / buzzword density ratio.

    Construct: Ratio of causal language to filler language.
    Measures reasoning STYLE, not reasoning quality.
    """
    mech = len(_MECH_RE.findall(text))
    buzz = len(_BUZZ_RE.findall(text))
    total = mech + buzz
    ratio = mech / max(total, 1)
    return {
        "score": round(ratio, 4),
        "mechanism_count": mech,
        "buzzword_count": buzz,
        "total_matches": total,
        "exploratory_threshold": 0.80,
        "reference": REFERENCE["mechanism_ratio"],
    }


# --- Assertion Ratio ---

REGISTER_PATTERNS = {
    "ASSERTION": [
        r"\bmust\b", r"\balways\b", r"\bnever\b", r"\bundeniably\b",
        r"\bclearly\b", r"\bobviously\b", r"\bensures?\b", r"\bguarantees?\b",
        r"\brequires?\b", r"\bwill\s+(?:lead|result|cause|create|produce)\b",
        r"\bis\s+essential\b", r"\bis\s+critical\b", r"\bis\s+(?:the\s+)?key\b",
    ],
    "QUALIFIED": [
        r"\btends?\s+to\b", r"\bin\s+many\s+cases\b", r"\bevidence\s+suggests?\b",
        r"\boften\b", r"\btypically\b", r"\bgenerally\b", r"\busually\b",
        r"\bfrequently\b", r"\bcan\s+(?:lead|result|cause|help)\b",
        r"\bmay\s+(?:lead|result|cause|help|be|not)\b",
        r"\blikely\b", r"\bprobably\b",
    ],
    "CONDITIONAL": [
        r"\bwhen\s+\w+\s+(?:is|are|do|does|have|has)\b",
        r"\bif\s+(?:the|this|a|an|these|those)\b",
        r"\bdepending\s+on\b", r"\bassuming\b",
        r"\bin\s+(?:cases|situations|contexts)\s+where\b",
        r"\bprovided\s+that\b",
        r"\bunder\s+(?:conditions|circumstances)\b",
        r"\bwhether\b",
    ],
    "EVIDENCED": [
        r"\bstudies?\s+(?:show|indicate|suggest|find|found|demonstrate)\b",
        r"\bresearch\s+(?:show|indicate|suggest|find|found|demonstrate)s?\b",
        r"\bdata\s+(?:show|indicate|suggest|reveal)s?\b",
        r"\baccording\s+to\b", r"\bempirical(?:ly)?\b",
        r"\bobserved\b", r"\bmeasured\b",
        r"\bevidence\s+(?:from|shows?|indicates?|suggests?)\b",
    ],
    "SPECULATIVE": [
        r"\bmight\b", r"\bcould\s+(?:be|lead|result|have|create|potentially)\b",
        r"\bpossibly\b", r"\bperhaps\b",
        r"\bremains?\s+to\s+be\s+seen\b",
        r"\bit\s+is\s+(?:possible|plausible|conceivable)\b",
        r"\bspeculat(?:e|ive|ion)\b", r"\bhypothes(?:is|ize|etical)\b",
    ],
}

_REG_COMPILED = {
    r: re.compile("|".join(p), re.IGNORECASE)
    for r, p in REGISTER_PATTERNS.items()
}

MIN_RELIABLE_MATCHES = 10


def extract_section_bodies(text):
    """Extract section body text only (excludes headings)."""
    sections = []
    lines = text.split("\n")
    current_heading = None
    current_body = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            if current_heading is not None:
                sections.append("\n".join(current_body).strip())
            current_heading = stripped
            current_body = []
        elif current_heading is not None:
            current_body.append(line)
    if current_heading is not None:
        sections.append("\n".join(current_body).strip())
    return sections


def assertion_ratio(text):
    """Epistemic assertion fraction of total register matches.

    Construct: Proportion of epistemic language that is assertive vs
    qualified/conditional/evidenced/speculative.
    Validated on section bodies only. Falls back to full text if no sections found
    (note: this changes measurement properties, so interpret with caution).
    """
    section_bodies = extract_section_bodies(text)
    used_sections = bool(section_bodies)
    body_text = "\n".join(section_bodies) if section_bodies else text

    counts = {}
    for register, compiled in _REG_COMPILED.items():
        counts[register] = len(compiled.findall(body_text))
    total = sum(counts.values())

    if total == 0:
        return {"score": 0.0, "register_counts": counts, "total_matches": 0,
                "exploratory_threshold": 0.35, "precision": "no_data",
                "used_section_bodies": used_sections,
                "reference": REFERENCE["assertion_ratio"]}

    ratio = counts["ASSERTION"] / total
    precision = "low" if total < MIN_RELIABLE_MATCHES else "adequate"

    return {
        "score": round(ratio, 4),
        "register_counts": counts,
        "total_matches": total,
        "exploratory_threshold": 0.35,
        "precision": precision,
        "used_section_bodies": used_sections,
        "reference": REFERENCE["assertion_ratio"],
    }


def structural_profile(doc_text, topic=None):
    """All structural layers. Gate 0 only if topic provided."""
    profile = {}

    if topic:
        g0 = gate_0(doc_text, topic)
        if g0 is not None:
            profile["gate_0"] = {
                "score": g0,
                "exploratory_threshold": 0.40,
            }

    profile["mechanism_ratio"] = mechanism_ratio(doc_text)
    profile["assertion_ratio"] = assertion_ratio(doc_text)
    return profile


# ================================================================
# LAYER 2: CLAIM DENSITY
# ================================================================
# Construct: Count of sentences containing digit-formatted numbers
# or causal language markers. Measures claim VOLUME, not accuracy.

NUMERICAL_PATTERNS = [
    (r'(?:~|approximately |about |roughly |nearly |over |under )?(\d+(?:\.\d+)?)\s*%',
     'percentage'),
    (r'(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*%', 'pct_range'),
    # USD and non-USD currency symbols. The character class
    # [$€£¥₹] captures all five; the "$" does not need escaping
    # inside a character class. Before Phase 1.6e this only
    # matched "$", so "€30.9B" in an ASML response was not
    # extracted as a monetary claim and fell through to the
    # bare-decimal pattern, losing the currency context.
    (r'[$€£¥₹]\s*(\d+(?:[.,]\d+)*)\s*(billion|million|thousand|bn|mn|B|M|K)?', 'dollar'),
    (r'(\d+(?:\.\d+)?)\s*[x×](?:\s|$|,)', 'multiplier'),
    (r'(\d+(?:\.\d+)?)\s*-?\s*fold', 'multiplier'),
    (r'(\d+(?:,\d{3})*)\s+(?:companies|firms|teams|organizations|employees|'
     r'engineers|developers|users|customers|tools|platforms|products|projects|'
     r'systems|failures|incidents|outages|services|applications|repositories|'
     r'modules|microservices|endpoints|APIs?|databases?|clusters?|regions?)',
     'entity_count'),
    (r'(\d+(?:\.\d+)?)\s*[-–]?\s*(?:\d+(?:\.\d+)?\s*)?'
     r'(?:days?|weeks?|months?|years?|hours?|minutes?|quarters?|sprints?)',
     'duration'),
]

CAUSAL_MARKERS = [
    r'\bbecause\b', r'\bsince\b(?!\s+\d)', r'\bdue to\b', r'\bowing to\b',
    r'\bas a result of\b', r'\bcaused? by\b', r'\bdriven by\b',
    r'\bleads? to\b', r'\bresults? in\b', r'\bcauses?\b', r'\bproduces?\b',
    r'\bgenerates?\b', r'\btriggers?\b', r'\bconsequently\b',
    r'\btherefore\b', r'\bthus\b', r'\bhence\b',
    r'\bthe (?:primary|main|key|root|fundamental|core|underlying|central) '
    r'(?:cause|reason|driver|factor|mechanism|force)\b',
    r'\b(?:directly|indirectly) (?:causes?|leads? to|results? in|drives?)\b',
    r'\bis responsible for\b', r'\baccounts? for\b',
    r'\benables?\b', r'\bprevents?\b', r'\binhibits?\b',
    r'\bfacilitates?\b', r'\bexacerbates?\b',
    r'\bcompounds?\b(?:\s+the)', r'\bamplifies?\b',
    r'\breinforces?\b', r'\bundermines?\b', r'\berodes?\b',
]


def split_sentences(text):
    """Split markdown into (heading, sentence, para_idx) tuples.

    Joins consecutive non-heading, non-list-item lines into paragraphs
    before splitting by sentence boundary, so sentences that wrap across
    lines are preserved rather than split at line breaks. List items
    (lines starting with -, *, or a number) are processed independently.
    """
    _LIST_MARKER = re.compile(r'^[-*•]\s+|\d+\.\s+')
    _SENT_BOUNDARY = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')

    results = []
    current_heading = ""
    para_idx = 0
    pending = []

    def _flush():
        nonlocal para_idx
        if not pending:
            return
        _collect(' '.join(pending))
        pending.clear()
        para_idx += 1

    def _collect(block):
        cleaned = re.sub(r'^[-*•]\s+', '', block)
        cleaned = re.sub(r'^\d+\.\s+', '', cleaned)
        for sent in _SENT_BOUNDARY.split(cleaned):
            sent = sent.strip()
            if len(sent) > 30:
                results.append((current_heading, sent, para_idx))

    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped:
            _flush()
            continue
        if stripped.startswith('#'):
            _flush()
            current_heading = re.sub(r'^#+\s*', '', stripped)
            continue
        if _LIST_MARKER.match(stripped):
            _flush()
            _collect(stripped)
            para_idx += 1
        else:
            pending.append(stripped)

    _flush()
    return results


def extract_numerical_claims(text):
    """Extract sentences with digit-formatted numbers. Zero LLM.
    Note: misses numbers expressed as words or relative claims."""
    sentences = split_sentences(text)
    claims = []
    for heading, sent, pos in sentences:
        numbers = []
        for pattern, num_type in NUMERICAL_PATTERNS:
            for m in re.finditer(pattern, sent, re.IGNORECASE):
                raw = m.group(0).strip()
                try:
                    val = float(m.group(1).replace(',', ''))
                except (ValueError, IndexError):
                    val = None
                numbers.append({'type': num_type, 'value': val, 'raw': raw})
        if numbers:
            claims.append({'sentence': sent, 'heading': heading,
                           'numbers': numbers, 'position': pos})
    return claims


def extract_causal_claims(text):
    """Extract sentences with causal assertions. Zero LLM."""
    sentences = split_sentences(text)
    combined = '|'.join(CAUSAL_MARKERS)
    claims = []
    for heading, sent, pos in sentences:
        found = re.findall(combined, sent, re.IGNORECASE)
        if found:
            claims.append({
                'sentence': sent, 'heading': heading,
                'markers': [m.strip().lower() for m in found if isinstance(m, str)],
                'position': pos,
            })
    return claims


def claim_density(text):
    """Numerical + causal claim density per 1K words."""
    words = len(re.findall(r'\b\w+\b', text))
    numerical = extract_numerical_claims(text)
    causal = extract_causal_claims(text)

    k_words = max(words / 1000, 0.1)
    return {
        "numerical_claims": len(numerical),
        "causal_claims": len(causal),
        "numerical_per_1kw": round(len(numerical) / k_words, 1),
        "causal_per_1kw": round(len(causal) / k_words, 1),
        "word_count": words,
        "recall_caveat": "Recall: 97% on digit-formatted numbers (3 doc types). Misses word-form and relative claims.",
    }


# ================================================================
# LAYER 3: TEMPORAL INSTABILITY (MULTI-SAMPLE REGENERATION)
# ================================================================
# Construct: Fraction of numbers unstable across independent generations.
# Instability is a PROXY for fabrication, not a direct measurement.
# Returned key "instability_rate" is the honest label (v1.4).
# Legacy alias "fabrication_rate" removed in v1.4.
# Cannot detect stable fabrication (consistently wrong numbers).
# EXP-081c showed ~46% of unstable numbers coincidentally match source
# material: parametric-memory overlap, not retrieval. Instability
# overcounts true fabrication by approximately half.
# See module docstring for the under-detection discipline.

def extract_numbers_for_matching(text):
    """Extract all numbers with type for temporal/source matching."""
    numbers = []
    seen = set()

    # Scale-word multipliers. Keyed lowercase so the regex match
    # group can be looked up directly after `.lower()`. Kept local
    # to this function because extract_numerical_claims does not
    # currently handle scale words in NUMERICAL_PATTERNS and the
    # Phase 1.6e construct audit flagged a separate fix there as
    # out of scope; the calibration-surfaced bug (2026-04-16
    # FINDINGS.md Category C) is specifically about number
    # extraction failing on "6 million" because no pattern below
    # accepted the digit-plus-spelled-scale shape outside a
    # currency context. Scaled-integer is added with higher
    # priority than the bare integer pattern so claimed_ranges
    # (below) prevents the digit alone from being re-matched.
    _SCALE_MULTIPLIERS = {
        "thousand": 1_000, "million": 1_000_000,
        "billion": 1_000_000_000, "trillion": 1_000_000_000_000,
    }

    patterns = [
        (r'(\d+(?:\.\d+)?)\s*%', "percentage"),
        (r'[$€£¥₹](\d+(?:\.\d+)?(?:,\d{3})*)', "dollar"),
        (r'[$€£¥₹](\d+(?:\.\d+)?(?:,\d{3})*)\s*[-–]\s*[$€£¥₹]?(\d+(?:\.\d+)?(?:,\d{3})*)\s*([MBKmillion|billion|thousand]*)', "dollar_range"),
        (r'(\d+(?:\.\d+)?)[xX]\b', "multiplier"),
        # Scaled integers in the digit + spelled-scale shape, e.g.
        # "6 million", "3.5 billion", "500 thousand". Must come
        # before the decimal / comma-integer / bare-integer patterns
        # so claimed_ranges blocks them from stealing the digit half.
        # The negative lookbehinds prevent matching inside a currency
        # context ("$6 million" is still captured by the dollar
        # pattern above) and inside a larger number ("166 million"
        # must not match as "66 million"). The \b after the scale
        # word prevents "million-dollar" from bleeding into a plural
        # or compound form.
        (r'(?<![$€£¥₹])(?<!\d)(?<!\.)(\d+(?:\.\d+)?)\s+(thousand|million|billion|trillion)\b',
         "scaled_integer"),
        (r'(?<![$€£¥₹])(?<!\d)(\d+\.\d+)(?!%)', "decimal"),
        (r'(?<![$€£¥₹])(?<!\d)(?<!\.)(\d{1,3}(?:,\d{3})+)(?!\.\d)(?!%)(?!\d)', "integer_comma"),
        (r'(?<![$€£¥₹])(?<!\d)(?<!\.)(\d+)\s*[MBK]\b', "integer_suffix"),
        (r'(?<![$€£¥₹])(?<!\d)(?<!\.)(\d{2,6})(?!\.\d)(?!%)(?!\d)(?!,\d{3})', "integer"),
    ]

    # Track character ranges claimed by earlier (higher-priority) patterns
    # to prevent decimal/integer patterns from extracting sub-tokens of
    # already-captured percentages/dollars (e.g., "2.58%" -> phantom "2.5")
    claimed_ranges = []

    for pattern, num_type in patterns:
        for m in re.finditer(pattern, text):
            # Skip if this match overlaps a range already claimed
            match_start, match_end = m.start(), m.end()
            if any(cs <= match_start < ce or cs < match_end <= ce
                   for cs, ce in claimed_ranges):
                continue

            val = m.group(1) if m.lastindex else m.group(0)
            if num_type in ("dollar", "integer_comma", "dollar_range"):
                val = val.replace(",", "")
            if num_type == "scaled_integer":
                # Apply the scale multiplier so downstream
                # source matching compares real magnitudes.
                # "6 million" -> value "6000000", raw retains
                # the original "6 million" text for display.
                scale = m.group(2).lower() if m.lastindex and m.lastindex >= 2 else ""
                multiplier = _SCALE_MULTIPLIERS.get(scale, 1)
                try:
                    scaled = float(val) * multiplier
                    # Render integers without a trailing .0 so the
                    # downstream claimed_values normalisation in
                    # analyze_claims treats "6000000.0" and "6000000"
                    # as the same key.
                    val = str(int(scaled)) if scaled == int(scaled) else str(scaled)
                except (ValueError, TypeError):
                    pass
            effective_type = num_type
            if num_type == "integer_comma":
                effective_type = "integer"
            elif num_type == "integer_suffix":
                effective_type = "integer"
            elif num_type == "scaled_integer":
                effective_type = "integer"
            elif num_type == "dollar_range":
                effective_type = "dollar"
            key = (val, effective_type, m.start())
            if key not in seen:
                seen.add(key)
                claimed_ranges.append((match_start, match_end))
                ctx_start = max(0, m.start() - 50)
                ctx_end = min(len(text), m.end() + 50)
                context = re.sub(r'\s+', ' ', text[ctx_start:ctx_end].strip())
                numbers.append({
                    "value": val, "raw": m.group(0),
                    "context": context, "type": effective_type,
                })
    return numbers


# Year range for filtering: numbers in this range treated as years, not data
YEAR_RANGE = (1990, 2035)


def _is_year(val):
    try:
        n = int(val)
        return YEAR_RANGE[0] <= n <= YEAR_RANGE[1]
    except ValueError:
        return False


def _is_word_count(num, text):
    for m in re.finditer(re.escape(num["raw"]), text):
        start = max(0, m.start() - 60)
        context = text[start:m.end() + 20].lower()
        if "word count" in context or "total words" in context:
            return True
    return False


def _filter_numbers(numbers, text):
    """Filter years and word counts from number list."""
    return [n for n in numbers
            if not _is_year(n["value"]) and not _is_word_count(n, text)]


def temporal_consistency(doc_text, comparison_texts):
    """Cross-version number stability.

    Construct: Fraction of unique numbers that appear in only SOME versions
    (instability rate). Instability is a proxy for fabrication, not a
    direct measurement. EXP-081c showed ~46% of unstable numbers
    coincidentally match source material (parametric-memory overlap), so
    instability overcounts true fabrication by approximately half.

    See module docstring for the under-detection discipline. for the audit record.

    Args:
        doc_text: Primary document
        comparison_texts: List of 1+ comparison versions
    """
    all_texts = [doc_text] + comparison_texts
    all_num_sets = []

    for t in all_texts:
        nums = _filter_numbers(extract_numbers_for_matching(t), t)
        num_set = set((n["value"], n["type"]) for n in nums)
        all_num_sets.append(num_set)

    all_nums = set().union(*all_num_sets)
    n_versions = len(all_texts)

    stable = set(v for v in all_nums
                 if sum(v in s for s in all_num_sets) == n_versions)
    variable = all_nums - stable

    total = len(all_nums)
    instability_rate = len(variable) / total if total > 0 else None

    primary_nums = _filter_numbers(extract_numbers_for_matching(doc_text), doc_text)
    stable_examples = [n for n in primary_nums
                       if (n["value"], n["type"]) in stable][:5]
    unstable_examples = [n for n in primary_nums
                         if (n["value"], n["type"]) in variable][:5]

    precision = "low" if total < 10 else "adequate" if total < 30 else "good"

    return {
        "instability_rate": round(instability_rate, 3) if instability_rate is not None else None,
        "stable_count": len(stable),
        "unstable_count": len(variable),
        "total_unique": total,
        "n_versions": n_versions,
        "precision": precision,
        "stable_examples": [{"value": n["value"], "type": n["type"],
                             "context": n["context"]} for n in stable_examples],
        "unstable_examples": [{"value": n["value"], "type": n["type"],
                               "context": n["context"]} for n in unstable_examples],
    }


# ================================================================
# LAYER 4: SOURCE FIDELITY (NUMBER PROVENANCE)
# ================================================================
# Construct: Fraction of digit-formatted numbers not found via exact
# string search in source material. Measures source fidelity (source
# presence of emitted numbers), not fabrication. A correctly-derived
# number (e.g., gross profit = revenue × margin computed from sourced
# components) is flagged as unsourced because the literal string is not
# in the source. See module docstring for the under-detection discipline. for failure
# modes and valid uses.

def _add_commas(val):
    """Re-insert commas into a plain integer string: 2000 -> 2,000."""
    if '.' in val or len(val) <= 3:
        return None
    try:
        return f"{int(val):,}"
    except ValueError:
        return None


def _number_in_source(num, source_text):
    """Check if a number appears in source text."""
    val = num["value"]
    ntype = num["type"]

    if ntype == "percentage":
        if re.search(re.escape(val) + r'\s*(?:%|percent)', source_text, re.IGNORECASE):
            return True
        if "." in val:
            int_val = val.split(".")[0]
            if re.search(re.escape(int_val) + r'\s*(?:%|percent)', source_text, re.IGNORECASE):
                return True
        return False
    elif ntype == "dollar":
        if re.search(r'\$' + re.escape(val), source_text):
            return True
        # Try comma-formatted: $45000 -> $45,000
        comma_val = _add_commas(val)
        if comma_val and re.search(r'\$' + re.escape(comma_val), source_text):
            return True
        return False
    elif ntype == "multiplier":
        return bool(re.search(re.escape(val) + r'[xX]', source_text))
    else:
        # Try raw value first
        if re.search(r'(?<!\d)' + re.escape(val) + r'(?!\d)', source_text):
            return True
        # Try comma-formatted: 2000 -> 2,000
        comma_val = _add_commas(val)
        if comma_val and re.search(r'(?<!\d)' + re.escape(comma_val) + r'(?!\d)', source_text):
            return True
        return False


def source_matching(doc_text, source_text):
    """Programmatic number-to-source matching. Zero LLM."""
    numbers = _filter_numbers(extract_numbers_for_matching(doc_text), doc_text)

    in_source = []
    not_in_source = []

    for num in numbers:
        if _number_in_source(num, source_text):
            in_source.append(num)
        else:
            not_in_source.append(num)

    total = len(in_source) + len(not_in_source)
    unsourced_rate = len(not_in_source) / total if total > 0 else 0
    precision = "low" if total < 10 else "adequate" if total < 30 else "good"

    return {
        "unsourced_rate": round(unsourced_rate, 3),
        "in_source": len(in_source),
        "not_in_source": len(not_in_source),
        "total_numbers": total,
        "precision": precision,
        "unsourced_details": [
            {"value": n["value"], "type": n["type"], "context": n["context"]}
            for n in not_in_source
        ],
        "reference": REFERENCE["source_matching"],
    }


# ================================================================
# LAYER 5: ENTITY PROVENANCE
# ================================================================
# Construct: Named entities (persons, orgs, citations) present in
# generated text but absent from source material.
# STATUS: DIRECTIONAL (N=18 docs). Needs wider validation.

def extract_entities(text):
    """Extract named entities from generated text. Zero LLM."""
    entities = []
    seen = set()

    body = re.sub(r'^#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
    body = re.sub(r'\|[^\n]+\|', '', body)

    # Person names
    for m in re.finditer(
            r"(?:(?:['s]\s+)|(?:according to\s+)|(?:by\s+)|(?:,\s+)"
            r"|(?:—\s*)|(?:\.\s+))([A-Z][a-z]{2,15}\s+"
            r"(?:[A-Z]\.?\s+)?[A-Z][a-z]{2,15})", body):
        name = m.group(1).strip()
        if any(w in name.lower() for w in ["source", "extends", "mechanism", "falsifier", "section"]):
            continue
        key = ("PERSON", name)
        if key not in seen:
            seen.add(key)
            ctx_start = max(0, m.start() - 20)
            ctx_end = min(len(body), m.end() + 30)
            entities.append({"type": "PERSON", "value": name,
                             "context": body[ctx_start:ctx_end].strip()})

    # Organizations
    for m in re.finditer(
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*'
            r'(?:\s+(?:Labs|Corp|Inc|Foundation|University|Institute'
            r'|Survey|Report|Association|Group|Research)))', body):
        name = m.group(1).strip()
        key = ("ORG", name)
        if key not in seen:
            seen.add(key)
            ctx_start = max(0, m.start() - 20)
            ctx_end = min(len(body), m.end() + 30)
            entities.append({"type": "ORG", "value": name,
                             "context": body[ctx_start:ctx_end].strip()})

    # Attributions
    for m in re.finditer(
            r'(?:according to|per|cited by|reported by)\s+'
            r'([A-Z][a-zA-Z]+(?:[\s/][A-Z]?[a-zA-Z]+){0,4})', body):
        name = m.group(1).strip()
        if name.lower() in ("source", "the", "this", "one"):
            continue
        key = ("ATTRIBUTED", name)
        if key not in seen:
            seen.add(key)
            ctx_start = max(0, m.start() - 10)
            ctx_end = min(len(body), m.end() + 30)
            entities.append({"type": "ATTRIBUTED", "value": name,
                             "context": body[ctx_start:ctx_end].strip()})

    # Parenthetical citations
    for m in re.finditer(
            r'\(([A-Z][a-zA-Z/]+(?:\s+[A-Z]?[a-zA-Z]+)*)'
            r'[,\s]+(\d{4})\)', body):
        cite = f"{m.group(1)} {m.group(2)}"
        if "source" in cite.lower():
            continue
        key = ("CITATION", cite)
        if key not in seen:
            seen.add(key)
            ctx_start = max(0, m.start() - 30)
            ctx_end = min(len(body), m.end() + 30)
            entities.append({"type": "CITATION", "value": cite,
                             "context": body[ctx_start:ctx_end].strip()})

    # CamelCase org names
    for m in re.finditer(r'(?<!\w)([A-Z][a-z]+[A-Z][a-zA-Z]+)(?!\w)', body):
        name = m.group(1)
        key = ("ORG_CAMEL", name)
        if key not in seen:
            seen.add(key)
            ctx_start = max(0, m.start() - 20)
            ctx_end = min(len(body), m.end() + 30)
            entities.append({"type": "ORG", "value": name,
                             "context": body[ctx_start:ctx_end].strip()})

    return entities


def _entity_in_source(entity, source_text):
    """Check if entity appears in source text."""
    val = entity["value"]
    if val.lower() in source_text.lower():
        return True
    words = [w for w in val.split() if len(w) > 3 and w.lower() not in STOP_WORDS]
    if words and all(w.lower() in source_text.lower() for w in words):
        return True
    return False


def entity_provenance(doc_text, source_text):
    """Entity detection + source matching. Zero LLM.
    STATUS: DIRECTIONAL (N=18 docs). English-centric patterns."""
    entities = extract_entities(doc_text)
    in_source = [e for e in entities if _entity_in_source(e, source_text)]
    not_in_source = [e for e in entities if not _entity_in_source(e, source_text)]

    total = len(entities)
    unsourced_rate = len(not_in_source) / total if total > 0 else 0
    precision = "low" if total < 5 else "adequate" if total < 15 else "good"

    return {
        "unsourced_rate": round(unsourced_rate, 3),
        "in_source": len(in_source),
        "not_in_source": len(not_in_source),
        "total_entities": total,
        "precision": precision,
        "status": "DIRECTIONAL",
        "unsourced_details": [
            {"type": e["type"], "value": e["value"], "context": e["context"][:80]}
            for e in not_in_source
        ],
    }


# ================================================================
# LAYER 6: VOCABULARY PROXIMITY
# ================================================================
# Construct: Fraction of content words per sentence that also appear
# in source text. Measures LANGUAGE overlap, not factual accuracy.
# Low score can mean original analysis (good) or fabrication (bad).
# STATUS: DIRECTIONAL (N=18 docs).

def _content_words(text):
    """Extract content words (non-stop, 3+ chars)."""
    words = re.findall(r'[a-z]{3,}', text.lower())
    return [w for w in words if w not in STOP_WORDS]


_ABBREV_RE = re.compile(
    r'\b(?:U\.S|vs|Dr|Mr|Mrs|Ms|Jr|Sr|Inc|Ltd|Corp|etc|approx|est'
    r'|i\.e|e\.g|Prof|Gen|Gov|Sen|Rep|Sgt|Rev|Vol|No|Fig|Eq'
    r'|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.'
)


def _split_sentences_simple(text):
    """Split text into sentences for grounding and vocabulary analysis."""
    clean = re.sub(r'^#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
    clean = re.sub(r'\|[^\n]+\|', '', clean)
    clean = re.sub(r'\*+', '', clean)
    clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)
    # Protect abbreviation periods from triggering sentence splits.
    # Without this, "U.S. economy" splits into fragments.
    protected = _ABBREV_RE.sub(lambda m: m.group().replace('.', '\x00'), clean)
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', protected)
    return [s.strip().replace('\x00', '.') for s in sentences
            if len(s.strip().split()) >= 5 and "word count" not in s.lower()]


def vocabulary_proximity(doc_text, source_text):
    """Content word overlap between generated sentences and source.

    Construct: What fraction of the generated vocabulary comes from the source?
    High = close paraphrase or summary. Low = novel vocabulary (could be
    original analysis OR fabricated content). Requires human interpretation.
    STATUS: DIRECTIONAL (N=18 docs).
    """
    sentences = _split_sentences_simple(doc_text)
    src_words = set(_content_words(source_text))

    scores = []
    low_proximity = []

    for s in sentences:
        s_words = _content_words(s)
        if not s_words:
            continue
        grounded = sum(1 for w in s_words if w in src_words)
        score = grounded / len(s_words)
        scores.append(score)
        if score < 0.5:
            low_proximity.append({"sentence": s[:100], "score": round(score, 3)})

    if not scores:
        return {"mean_proximity": 0, "total_sentences": 0,
                "status": "DIRECTIONAL"}

    return {
        "mean_proximity": round(statistics.mean(scores), 3),
        "median_proximity": round(statistics.median(scores), 3),
        "total_sentences": len(sentences),
        "low_proximity_count": len(low_proximity),
        "low_proximity_rate": round(len(low_proximity) / len(sentences), 3),
        "low_proximity_examples": low_proximity[:5],
        "status": "DIRECTIONAL",
        "interpretation_note": (
            "Low proximity = novel vocabulary. Could be original analysis "
            "(desirable) or fabricated content (undesirable). "
            "Distinguish using Layers 4-5, not this layer alone."
        ),
    }


# ================================================================
# LAYER 7: PRESENTATION FEATURES
# ================================================================
# Construct: Surface formatting characteristics. Descriptive, not evaluative.

HEDGE_RE = re.compile(
    r'\b(?:perhaps|maybe|possibly|might|could|seems?|appears?|'
    r'suggest(?:s|ed|ing)?|indicate(?:s|d)?|tend(?:s|ed)?|'
    r'somewhat|relatively|generally|often|usually|typically|'
    r'in some cases|to some extent|it (?:is|seems) (?:possible|likely))\b',
    re.IGNORECASE
)

ASSERT_RE = re.compile(
    r'\b(?:always|never|must|requires?|demands?|guarantees?|ensures?|'
    r'proves?|demonstrates?|establishes?|confirms?|definitively|'
    r'inevitably|invariably|necessarily|fundamentally|critically|'
    r'the (?:key|core|essential|primary|fundamental|root|central) '
    r'(?:issue|problem|cause|reason|driver|mechanism|factor))\b',
    re.IGNORECASE
)

NAMING_RE = re.compile(
    r'(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s*(?:Effect|Trap|Paradox|Principle|'
    r'Syndrome|Pattern|Loop|Cycle|Model|Framework|Law|Rule|Fallacy|Bias|'
    r'Gap|Problem|Phenomenon|Spiral|Ceiling|Floor|Threshold))',
)


def _count_syllables(word):
    word = word.lower().strip()
    if len(word) <= 3:
        return 1
    count = 0
    prev_vowel = False
    for char in word:
        is_vowel = char in 'aeiouy'
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith('e') and count > 1:
        count -= 1
    return max(1, count)


def _tokenize(text):
    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return re.findall(r"[a-zA-Z']+", text.lower())


def presentation_features(text):
    """Surface presentation characteristics. Descriptive, not evaluative."""
    words = _tokenize(text)
    sents = _split_sentences_simple(text)
    headings = extract_headings_simple(text)

    n_words = len(words)
    ttr = len(set(words)) / n_words if n_words > 0 else 0.0

    sent_lengths = [len(_tokenize(s)) for s in sents]
    mean_sent_len = statistics.mean(sent_lengths) if sent_lengths else 0.0

    syllable_counts = [_count_syllables(w) for w in words if w.isalpha()]
    total_syllables = sum(syllable_counts)
    n_sents = max(len(sents), 1)
    if n_words > 0:
        fk_grade = 0.39 * (n_words / n_sents) + 11.8 * (total_syllables / n_words) - 15.59
    else:
        fk_grade = 0.0

    n_bold = len(re.findall(r'\*\*[^*]+\*\*', text))
    n_list_items = len(re.findall(r'^[-*•]\s+', text, re.MULTILINE))
    n_list_items += len(re.findall(r'^\d+\.\s+', text, re.MULTILINE))
    formatting_density = (n_bold + n_list_items + len(headings)) / max(n_words / 100, 1)

    n_hedges = len(HEDGE_RE.findall(text))
    n_asserts = len(ASSERT_RE.findall(text))
    assertiveness = n_asserts / (n_asserts + n_hedges) if (n_asserts + n_hedges) > 0 else 0.5

    named_concepts = NAMING_RE.findall(text)

    return {
        "word_count": n_words,
        "type_token_ratio": round(ttr, 4),
        "mean_sentence_length": round(float(mean_sent_len), 1),
        "fk_grade_level": round(fk_grade, 1),
        "formatting_density": round(formatting_density, 2),
        "assertiveness_ratio": round(assertiveness, 4),
        "n_hedges": n_hedges,
        "n_asserts": n_asserts,
        "n_named_concepts": len(named_concepts),
        "named_concepts": named_concepts[:10],
    }


# ================================================================
# LAYER 8: EPISTEMIC CALIBRATION
# ================================================================
# Construct: Cross-layer metric. For each sentence with ASSERTION markers,
# checks whether grounding evidence exists (sourced number, sourced entity,
# or high vocabulary overlap with source).
# STATUS: EXPERIMENTAL (v1.3). No external validation.

# Broader assertion detection than REGISTER_PATTERNS["ASSERTION"].
# Includes the original patterns PLUS additional high-confidence phrases
# that the structural assertion_ratio intentionally omits (to preserve
# its validated reference distributions).
_CALIBRATION_ASSERTION_PATTERNS = [
    # --- Original REGISTER_PATTERNS["ASSERTION"] (preserved exactly) ---
    r"\bmust\b", r"\balways\b", r"\bnever\b", r"\bundeniably\b",
    r"\bclearly\b", r"\bobviously\b", r"\bensures?\b", r"\bguarantees?\b",
    r"\brequires?\b", r"\bwill\s+(?:lead|result|cause|create|produce)\b",
    r"\bis\s+essential\b", r"\bis\s+critical\b", r"\bis\s+(?:the\s+)?key\b",
    # --- Expanded patterns (v1.3 calibration-only) ---
    r"\bit\s+is\s+clear\s+that\b",
    r"\bthere\s+is\s+no\s+doubt\b",
    r"\bwithout\s+(?:question|doubt|exception)\b",
    r"\bproves?\s+(?:that|beyond)\b",
    r"\bindisputabl[ye]\b",
    r"\bconclusivel[ye]\b",
    r"\bunambiguous(?:ly)?\b",
    r"\bdefinitiv(?:e|ely)\b",
    r"\binevitabl[ye]\b",
    r"\bunquestionabl[ye]\b",
    r"\bcertainly\b",
    r"\bdemonstrates?\s+(?:that|the|a|an)\b",
    r"\bwill\s+(?:always|never|inevitably|certainly)\b",
    r"\bno\s+(?:question|doubt|exception)\b",
    r"\bcannot\s+(?:fail|be\s+denied|be\s+disputed)\b",
    r"\bis\s+(?:undeniable|indisputable|certain|inevitable)\b",
    r"\bwill\s+(?:definitely|undoubtedly|surely)\b",
    r"\bproven\s+(?:to|that|by)\b",
]

_CALIBRATION_ASSERTION_RE = re.compile(
    "|".join(_CALIBRATION_ASSERTION_PATTERNS), re.IGNORECASE
)


def epistemic_calibration(doc_text, source_text):
    """Per-sentence assertion grounding check.

    Construct: For each sentence containing assertion markers (expanded set),
    check whether it has grounding evidence (sourced number, sourced entity,
    or vocabulary overlap >50% with source). Measures calibration between
    epistemic confidence and evidence support.

    Uses _CALIBRATION_ASSERTION_RE (broader than REGISTER_PATTERNS["ASSERTION"])
    to catch phrases like "it is clear that", "there is no doubt", "inevitably",
    "conclusively", etc. that the structural assertion_ratio intentionally omits.

    STATUS: EXPERIMENTAL (v1.3). No external validation.
    """
    sentences = _split_sentences_simple(doc_text)
    source_lower = source_text.lower()
    src_word_set = set(_content_words(source_text))
    assertion_re = _CALIBRATION_ASSERTION_RE

    total_assertions = 0
    grounded_assertions = 0
    overclaiming = []
    grounded_details = []

    for sent in sentences:
        matches = assertion_re.findall(sent)
        if not matches:
            continue

        total_assertions += 1
        grounds = []

        # Ground 1: sourced number in sentence
        sent_numbers = _filter_numbers(extract_numbers_for_matching(sent), sent)
        for num in sent_numbers:
            if _number_in_source(num, source_text):
                grounds.append(f"sourced_number:{num['value']}")
                break

        # Ground 2: sourced entity (capitalized multi-word phrase in source)
        for m in re.finditer(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', sent):
            if m.group(1).lower() in source_lower:
                grounds.append(f"sourced_entity:{m.group(1)}")
                break

        # Ground 3: high vocabulary overlap with source
        s_words = _content_words(sent)
        if s_words:
            grounded_count = sum(1 for w in s_words if w in src_word_set)
            vocab_score = grounded_count / len(s_words)
            if vocab_score > 0.5:
                grounds.append(f"vocab_proximity:{vocab_score:.2f}")

        markers = [m.strip().lower() for m in matches[:3]]

        if grounds:
            grounded_assertions += 1
            grounded_details.append({
                "sentence": sent[:100],
                "grounds": grounds,
                "markers": markers,
            })
        else:
            overclaiming.append({
                "sentence": sent[:100],
                "markers": markers,
            })

    calibration = grounded_assertions / total_assertions if total_assertions > 0 else None
    overclaim_rate = len(overclaiming) / total_assertions if total_assertions > 0 else None
    precision = "low" if total_assertions < 5 else "adequate" if total_assertions < 15 else "good"

    return {
        "calibration_score": round(calibration, 3) if calibration is not None else None,
        "overclaiming_rate": round(overclaim_rate, 3) if overclaim_rate is not None else None,
        "grounded_assertions": grounded_assertions,
        "total_assertions": total_assertions,
        "precision": precision,
        "status": "EXPERIMENTAL",
        "overclaiming_details": overclaiming[:5],
        "grounded_details": grounded_details[:3],
        "interpretation_note": (
            "Calibration = grounded assertions / total assertions. "
            "Grounding = sourced number, sourced entity, or >50% vocabulary overlap. "
            "Low calibration + high assertion ratio = overclaiming signal. "
            "Surface-level only: cannot verify semantic accuracy."
        ),
    }


# ================================================================
# LAYER 9: INFORMATION NOVELTY
# ================================================================
# Construct: Per-sentence cumulative vocabulary novelty. Measures
# information density vs repetition patterns.
# STATUS: EXPERIMENTAL (v1.3). No external validation.

def information_novelty(doc_text):
    """Per-sentence novelty via cumulative vocabulary tracking.

    Construct: For each sentence, fraction of content words not seen in any
    previous sentence. Measures information density and repetition patterns.
    Negative decay is natural (later sentences reuse vocabulary). Steep
    negative decay + high repetition = padding/filler.

    STATUS: EXPERIMENTAL (v1.3). No external validation.
    """
    sentences = _split_sentences_simple(doc_text)

    cumulative_vocab = set()
    novelty_scores = []

    for sent in sentences:
        words = _content_words(sent)
        if not words:
            continue
        novel = [w for w in words if w not in cumulative_vocab]
        novelty = len(novel) / len(words)
        novelty_scores.append(novelty)
        cumulative_vocab.update(words)

    n = len(novelty_scores)
    if not novelty_scores:
        return {"mean_novelty": 0, "total_sentences": 0, "status": "EXPERIMENTAL"}

    mean_nov = statistics.mean(novelty_scores)

    # Repetition rate: sentences with <20% novel content
    repetitive = sum(1 for s in novelty_scores if s < 0.2)
    repetition_rate = repetitive / n

    # Information decay: OLS slope of novelty over sentence position
    decay_slope = 0.0
    if n > 2:
        x_mean = (n - 1) / 2
        cov_xy = sum((i - x_mean) * (y - mean_nov)
                      for i, y in enumerate(novelty_scores))
        var_x = sum((i - x_mean) ** 2 for i in range(n))
        if var_x > 0:
            decay_slope = cov_xy / var_x

    # First vs last quartile
    q_size = max(n // 4, 1)
    first_q = statistics.mean(novelty_scores[:q_size])
    last_q = statistics.mean(novelty_scores[-q_size:])

    return {
        "mean_novelty": round(mean_nov, 3),
        "repetition_rate": round(repetition_rate, 3),
        "information_decay": round(decay_slope, 4),
        "first_quarter_novelty": round(first_q, 3),
        "last_quarter_novelty": round(last_q, 3),
        "total_sentences": n,
        "total_unique_words": len(cumulative_vocab),
        "status": "EXPERIMENTAL",
        "interpretation_note": (
            "Novelty = fraction of content words not seen in previous sentences. "
            "Negative decay = natural (later sentences reuse vocabulary). "
            "Steep negative decay + high repetition = padding/filler. "
            "Flat decay = diverse content throughout."
        ),
    }


# ================================================================
# LAYER 10: QUALITY PROFILE (COMPOSITE)
# ================================================================
# Construct: Substance index (fidelity layers) vs presentation index
# (surface layers). Gap = overclaiming signal.
# STATUS: EXPERIMENTAL (v1.3). Composite metrics inherit component limitations.

def quality_profile(profile):
    """Composite substance vs presentation index.

    Construct: Aggregates fidelity layers into substance index and surface
    layers into presentation index. Positive gap = surface exceeds substance
    (overclaiming risk). Negative gap = substance exceeds surface.

    STATUS: VALIDATED (v1.3). Four validation studies:
    (1) Source present vs absent: d=-5.78, N=24.
    (2) Faithful vs embellished on xAI: d=-5.43, N=12.
    (3) Faithful vs embellished on Gemini: d=-2.28, N=12.
    (4) 4-dose gradient on Gemini: monotonic, endpoint d=-2.13, N=24.
    Cross-generator + dose-response gradient confirm construct validity.
    Low-N calibration gated by precision (≥5 assertions required).
    """
    substance = {}
    presentation = {}
    precision_excluded = []

    # Substance: fidelity/grounding signals (higher = better grounded)
    if "source_fidelity" in profile:
        src = profile["source_fidelity"]
        if src.get("precision") == "low":
            precision_excluded.append("source_fidelity")
        else:
            substance["source_fidelity"] = 1 - src["unsourced_rate"]

    if "temporal_instability" in profile:
        tmp = profile["temporal_instability"]
        rate = tmp.get("instability_rate")
        if rate is not None:
            if tmp.get("precision") == "low":
                precision_excluded.append("temporal_stability")
            else:
                substance["temporal_stability"] = 1 - rate

    if "entity_provenance" in profile:
        ent = profile["entity_provenance"]
        if ent.get("precision") == "low":
            precision_excluded.append("entity_grounding")
        else:
            substance["entity_grounding"] = 1 - ent["unsourced_rate"]

    if "epistemic_calibration" in profile:
        cal = profile["epistemic_calibration"]
        score = cal["calibration_score"]
        # Only include calibration when precision is adequate (≥5 assertions).
        # Low-N calibration (1-4 assertions) is too noisy for a composite;
        # one coincidental number match on one assertion inflates substance.
        if score is not None and cal.get("precision") != "low":
            substance["epistemic_calibration"] = score

    # NOTE: information_novelty is intentionally NOT folded into substance
    # or presentation. Novelty measures vocabulary diversity (information
    # density), which is orthogonal to both fidelity and surface polish.
    # It is reported as a standalone companion metric in the profile.

    # Presentation: surface/formatting signals (higher = more polished surface)
    if "structural" in profile:
        s = profile["structural"]
        if "gate_0" in s:
            presentation["structural_effort"] = 1 - s["gate_0"]["score"]

    if "presentation" in profile:
        p = profile["presentation"]
        presentation["assertiveness"] = p["assertiveness_ratio"]
        presentation["formatting_intensity"] = min(p["formatting_density"] / 3, 1.0)
        presentation["vocabulary_diversity"] = p["type_token_ratio"]

    # Compute indices
    sub_idx = statistics.mean(substance.values()) if substance else None
    pres_idx = statistics.mean(presentation.values()) if presentation else None

    gap = None
    if sub_idx is not None and pres_idx is not None:
        gap = pres_idx - sub_idx

    return {
        "substance_index": round(sub_idx, 3) if sub_idx is not None else None,
        "presentation_index": round(pres_idx, 3) if pres_idx is not None else None,
        "gap": round(gap, 3) if gap is not None else None,
        "gap_direction": (
            "overclaiming" if gap is not None and gap > 0.1
            else "understated" if gap is not None and gap < -0.1
            else "balanced" if gap is not None
            else "insufficient_data"
        ),
        "substance_components": {k: round(v, 3) for k, v in substance.items()},
        "presentation_components": {k: round(v, 3) for k, v in presentation.items()},
        "n_substance_layers": len(substance),
        "n_presentation_layers": len(presentation),
        "precision_excluded": precision_excluded,
        "status": "VALIDATED",
        "interpretation_note": (
            "Composite of individual layer scores. Only as valid as its components. "
            "Minimum 2 substance layers recommended for meaningful index. "
            "Gap > 0.1 = overclaiming risk. Gap < -0.1 = understated quality. "
            "4 validation studies: d=-5.78 source, d=-5.43 xAI, d=-2.28 Gemini, "
            "monotonic 4-dose gradient. Entity grounding most sensitive component."
        ),
    }


# ================================================================
# LAYER 11: GROUNDING DECOMPOSITION (COMPOSITE, v1.4)
# ================================================================
# Construct: Per-sentence classification into Grounded (G), Framed (F),
# or Projected (P) based on information provenance. G = source-derived,
# F = interpretive/evaluative, P = external data or projection.
# STATUS: EXPERIMENTAL (v1.4). Validated on N=90 outputs, 3 frontier models,
# 3 topics, default + prohibition conditions. P-detection is most accurate.
# G/F boundary is fuzzy on mixed sentences (classifies by number presence,
# not primary function). The rule set encoded below in
# _GFP_EXTERNAL_ENTITIES, _GFP_PROJECTION_VERBS, etc. is the
# load-bearing operational definition.

# External entity patterns (P-markers: names/concepts not typically in
# analytical source documents). Extend this list for domain coverage.
_GFP_EXTERNAL_ENTITIES = [
    r'\bSTEP\s+\d\b', r'\bSURMOUNT\b', r'\bSELECT\b',
    r'\bRybelsus\b', r'\borforglipron\b', r'\btirzepatide\b', r'\bZepbound\b',
    r'\bphentermine\b', r'\borlistat\b',
    r'\bHuawei\b', r'\bSamsung\b', r'\bLilly\b',
    r'\biPhone\s*1[5-9]\b', r'\bVision\s*Pro\b', r'\bSiri\b',
    r'\bApple\s*Intelligence\b', r'\bM-series\b',
    r'\bISM\b', r'\bADP\b',
    r'\bOkun\b', r'\bNAIRU\b',
    r'\bDMA\b', r'\bNovo\s*Nordisk\b',
]


def _gfp_is_derivable(value, source_floats, tolerance=0.02):
    """Check if a number is derivable from source numbers by arithmetic.

    Handles: A/B, A*B, A+B, A-B, A/100 (percentage to decimal),
    A*100 (decimal to percentage), two-step derivations where an
    intermediate result is combined with a source number, and
    percentage application ((A/100) * B, e.g. Revenue * Margin%).
    """
    if not source_floats:
        return False

    src = list(source_floats)

    def close(derived, target):
        if abs(target) < 0.001:
            return abs(derived) < 0.001
        return abs(derived - target) / abs(target) < tolerance

    def close_tight(derived, target):
        if abs(target) < 0.001:
            return abs(derived) < 0.001
        return abs(derived - target) / abs(target) < 0.01  # 1% not 2%

    # Single-number derivations
    for a in src:
        if close(a / 100, value) or close(a * 100, value):
            return True

    # Two-number derivations. A*B and A/B*100 use tight tolerance (1%)
    # because with 6+ source numbers, 2% on ~30 products matches ~24%
    # of integers by coincidence (e.g. 30.8/94.0*100 = 32.77 falsely
    # matches 33). A/B (raw ratio, typically < 10) keeps 2%.
    for a in src:
        if a == 0:
            continue
        for b in src:
            if b == 0:
                continue
            if close_tight(a / b * 100, value) or close(a / b, value):
                return True
            if close_tight(a * b, value):
                return True

    for i in range(len(src)):
        for j in range(i, len(src)):
            a, b = src[i], src[j]
            if close(a + b, value):
                return True
            for diff in [a - b, b - a]:
                if abs(diff) > 0.001 and close(diff, value):
                    return True

    # Two-step: ADDITION/SUBTRACTION intermediates only (v1.4.1).
    # Sums and differences of source numbers, then combined with another source
    # number via division or percentage. This handles: sum of 3+ segments,
    # share-of-total after subtraction (non-iPhone/total = 41%).
    #
    # Division/multiplication intermediates (rates, ratios) are excluded because
    # they produce coincidental matches on small-number sources (BLS: 4.3, 0.2,
    # 3.5 combine to match external values). Domain-specific formulas using source
    # inputs (labor_force = unemployed / unemployment_rate) are P: the formula is
    # external knowledge even though the inputs are from source.
    add_sub_intermediates = set()
    for i in range(len(src)):
        for j in range(i, len(src)):
            a, b = src[i], src[j]
            add_sub_intermediates.add(a + b)
            if a != b:
                add_sub_intermediates.add(a - b)
                add_sub_intermediates.add(b - a)

    # Two-step direct: check if an add/sub intermediate itself
    # matches the target (e.g. revenue - datacenter = other_segment).
    # The inter/s and inter/s*100 paths are excluded: with ~28
    # intermediates and 6 source numbers, they match 62-78% of
    # integers at any reasonable tolerance, effectively disabling
    # P-detection for numbers. The basic A/B and A/B*100 paths
    # already cover legitimate ratio derivations.
    for inter in add_sub_intermediates:
        if close_tight(inter, value):
            return True

    # Percentage application: (a/100) * b catches Revenue * Margin%,
    # Total * Share%, Base * Rate%. Only percentage-to-decimal intermediates
    # participate in multiplication to avoid false positives from the
    # much larger set of ratio/difference/sum intermediates.
    #
    # Two guards against false positives (v1.4.2):
    #   1. a must be a plausible percentage (0 < a <= 100). Revenue in
    #      billions (e.g., 383, 215) should not participate as percentages.
    #   2. Tight tolerance (1%) since with 3-4 plausible percentage
    #      values and 7 source numbers, 2% tolerance still matches too
    #      many integers by coincidence.
    for a in src:
        if 0 < a <= 100:
            pct = a / 100
            for b in src:
                if close_tight(pct * b, value):
                    return True

    return False


# Regime boundaries for the Layer 11 primary P-detection signal
# (unsourced_numbers via _gfp_is_derivable). The derivation checker's
# false-positive rate rises monotonically with the count of unique
# source numbers; Monte Carlo measurements: ~4% at N=2, ~68% at N=10,
# ~97% by N=20. See LAYER_11_SCOPE_BOUNDARY.md and the regression
# tests in test_grounding.py (TestScopeAssessment). Changing these
# constants requires re-measuring against the Monte Carlo harness.
_DERIVATION_REGIME_DIAGNOSTIC_MAX = 10   # N < this -> diagnostic
_DERIVATION_REGIME_TRANSITION_MAX = 15   # N < this -> transition, else saturated


def grounding_decomposition(doc_text, source_text):
    """Per-sentence Grounded/Framed/Projected decomposition.

    For each sentence, classifies the primary information provenance:
      G (Grounded): restates or mechanically derives from source data.
      F (Framed): interprets, evaluates, or assigns significance to source.
      P (Projected): introduces external data, predictions, or unsourced specifics.

    P-detection uses sentence-level unsourced number detection (primary signal)
    plus external entity pattern matching (secondary). G-detection uses sourced
    number/entity presence + vocabulary overlap. F is the residual.

    STATUS: EXPERIMENTAL (v1.4).
    Validated on 90 outputs (3 frontier models, 3 topics, default + prohibition).
    P-detection: accurate on frontier models (binary: 0% vs ~10%).
    G/F boundary: fuzzy on mixed sentences (source number + interpretation).
    Prohibition collapses P to 0% and increases G by 9-22pp.
    Known limitation: derivation checker handles two-step arithmetic but may
    miss three-step derivations. External entity list is fixed (extendable).
    The operational definition lives in the module's _GFP_* constant
    tables.
    """
    sentences = _split_sentences_simple(doc_text)

    # Extract source numbers as floats for derivation checking
    src_nums_raw = extract_numbers_for_matching(source_text)
    src_nums_filtered = _filter_numbers(src_nums_raw, source_text)
    source_floats = set()
    for nd in src_nums_filtered:
        val = nd.get("value") if isinstance(nd, dict) else None
        if val is not None:
            try:
                source_floats.add(float(val))
            except (ValueError, TypeError):
                pass

    # Extract source years from FULL source text (not just data section).
    # Two passes: standalone years (\b2025\b) and prefixed years
    # (FY2025, CY2025) where the \b before the digits falls inside a
    # word and the standalone pattern misses them.
    source_years = set()
    for m in re.finditer(r'\b((?:19|20)\d{2})\b', source_text):
        source_years.add(int(m.group(1)))
    for m in re.finditer(r'(?:FY|CY)((?:19|20)\d{2})\b', source_text):
        source_years.add(int(m.group(1)))

    classified = []
    for sent in sentences:
        clean = re.sub(r'[#*|_\-]', '', sent).strip()
        if len(clean) < 20:
            classified.append({"classification": "SKIP"})
            continue

        # --- P detection: unsourced numbers (primary) ---
        sent_nums = _filter_numbers(extract_numbers_for_matching(sent), sent)

        sourced = []
        unsourced = []
        derived = []

        for nd in sent_nums:
            if _number_in_source(nd, source_text):
                sourced.append(nd)
            else:
                val = nd.get("value") if isinstance(nd, dict) else None
                raw = nd.get("raw", "") if isinstance(nd, dict) else str(nd)
                if val is not None:
                    try:
                        fval = float(val)
                        if _gfp_is_derivable(fval, source_floats):
                            derived.append(nd)
                        else:
                            unsourced.append(nd)
                    except (ValueError, TypeError):
                        unsourced.append(nd)
                else:
                    unsourced.append(nd)

        # Filter non-statistical numbers (small integers 1-10, age ranges)
        filtered_unsourced = []
        for nd in unsourced:
            val = nd.get("value") if isinstance(nd, dict) else None
            raw = nd.get("raw", "") if isinstance(nd, dict) else str(nd)
            try:
                fval = float(val) if val else float(raw.replace(',', '').replace('$', ''))
            except (ValueError, TypeError):
                filtered_unsourced.append(nd)
                continue
            if fval == int(fval) and 1 <= fval <= 10:
                continue
            if re.search(r'\b' + re.escape(str(raw)) + r'\s*[-]\s*\d+\b', sent):
                continue
            filtered_unsourced.append(nd)
        unsourced = filtered_unsourced

        # External entity detection (secondary P signal)
        ext_entities = []
        for pat in _GFP_EXTERNAL_ENTITIES:
            for m in re.finditer(pat, sent, re.IGNORECASE):
                ext_entities.append(m.group())

        # Unsourced year detection (standalone and FY/CY-prefixed)
        sent_years = set(int(m.group(1)) for m in re.finditer(r'\b((?:19|20)\d{2})\b', sent))
        sent_years.update(int(m.group(1)) for m in re.finditer(r'(?:FY|CY)((?:19|20)\d{2})\b', sent))
        unsourced_yrs = sent_years - source_years

        # P decision
        is_p = False
        p_reason = []
        if unsourced:
            is_p = True
            p_reason.append("unsourced_numbers")
        if ext_entities:
            is_p = True
            p_reason.append("external_entities")
        if unsourced_yrs and (unsourced or len(clean) > 50):
            is_p = True
            p_reason.append("unsourced_years")

        if is_p:
            # Truncate at word boundary for clean display
            truncated = sent if len(sent) <= 120 else sent[:120].rsplit(' ', 1)[0]
            classified.append({
                "classification": "P",
                "reason": "+".join(p_reason),
                "sentence": truncated,
            })
            continue

        # --- G detection: grounding score ---
        has_sourced = len(sourced) > 0 or len(derived) > 0
        sent_words = set(_content_words(sent))
        src_words = set(_content_words(source_text))
        vocab_overlap = len(sent_words & src_words) / len(sent_words) if sent_words else 0

        grounding = 0.0
        if has_sourced:
            grounding += 0.5
        grounding += vocab_overlap * 0.3
        # Bonus for all numbers being sourced
        total_nums = len(sourced) + len(derived) + len(unsourced)
        if total_nums > 0 and len(unsourced) == 0 and (len(sourced) + len(derived)) > 0:
            grounding += 0.2

        if grounding >= 0.4:
            classified.append({"classification": "G"})
            continue

        # --- F detection: residual ---
        classified.append({"classification": "F"})

    # Aggregate
    counts = {"G": 0, "F": 0, "P": 0}
    p_sentences = []
    n_skip = 0
    for c in classified:
        cat = c["classification"]
        if cat == "SKIP":
            n_skip += 1
        else:
            counts[cat] += 1
            if cat == "P":
                p_sentences.append(c)

    total = sum(counts.values())
    proportions = {k: round(v / total, 3) if total > 0 else 0.0 for k, v in counts.items()}

    # Prohibition recommendation
    has_projection = counts["P"] > 0
    recommendation = None
    if has_projection:
        recommendation = (
            "Do not use any numbers that are not in the provided source."
        )

    # Scope assessment. The primary P-detection signal (unsourced_numbers)
    # tests N*(N-1) arithmetic combinations of source numbers against each
    # doc number at 2% tolerance. Monte Carlo shows the false-positive rate
    # rises sharply with N: ~4% at N=2, ~68% at N=10, ~97% by N=20. On
    # number-dense sources the check saturates and classifies fabricated
    # numbers as "derived" via coincidental arithmetic match.
    #
    # Regime boundaries from Monte Carlo + pilot corpus:
    #   N < 10:  diagnostic    (primary signal is reliable)
    #   10-14:   transition    (primary signal is noisy)
    #   N >= 15: saturated     (primary signal is effectively disabled;
    #                           cross-reference source_fidelity (Layer 4)
    #                           which uses digit-level matching without
    #                           derivation tolerance).
    source_num_count = len(source_floats)
    if source_num_count < _DERIVATION_REGIME_DIAGNOSTIC_MAX:
        derivation_regime = "diagnostic"
    elif source_num_count < _DERIVATION_REGIME_TRANSITION_MAX:
        derivation_regime = "transition"
    else:
        derivation_regime = "saturated"
    primary_signal_diagnostic = (derivation_regime == "diagnostic")
    cross_reference_layer_4_for_numbers = (derivation_regime == "saturated")

    if derivation_regime == "saturated":
        note = (
            f"Source has {source_num_count} unique numerical values. "
            "Derivation checker saturates: fabricated numbers classify as "
            "'derived' via coincidental arithmetic match, suppressing the "
            "unsourced_numbers P-signal. Trust Layer 4 source_fidelity for "
            "numerical claims on this document."
        )
        note_user_facing = (
            "Sentence-level grounding is supplemental on number-dense sources. "
            "For numerical claims, the source-fidelity match is authoritative."
        )
    elif derivation_regime == "transition":
        note = (
            f"Source has {source_num_count} unique numerical values. "
            "Derivation checker false-positive rate is elevated; cross-"
            "reference Layer 4 for numerical claims."
        )
        note_user_facing = (
            "Sentence-level grounding is a supporting signal here. The "
            "source-fidelity match is more reliable for numerical claims."
        )
    else:
        note = (
            f"Source has {source_num_count} unique numerical values. "
            "Derivation checker operates in a reliable regime; the "
            "unsourced_numbers signal is the primary P-detection."
        )
        note_user_facing = (
            "Sentence-level grounding is the primary signal here."
        )

    scope_assessment = {
        "source_num_count": source_num_count,
        "derivation_regime": derivation_regime,
        "primary_signal_diagnostic": primary_signal_diagnostic,
        "cross_reference_layer_4_for_numbers": cross_reference_layer_4_for_numbers,
        "note": note,
        "note_user_facing": note_user_facing,
    }

    return {
        "proportions": proportions,
        "counts": counts,
        "n_classified": total,
        "n_skipped": n_skip,
        "has_projection": has_projection,
        "p_sentences": [{"sentence": p["sentence"], "reason": p["reason"]}
                        for p in p_sentences[:10]],
        "recommendation": recommendation,
        "scope_assessment": scope_assessment,
        "status": "EXPERIMENTAL",
        "interpretation_note": (
            "G = source-grounded, F = interpretive framing, P = projected/external. "
            "P-detection accuracy depends on scope_assessment.derivation_regime: "
            "reliable in diagnostic regime, noisy in transition, effectively "
            "disabled in saturated (cross-reference Layer 4 source_fidelity). "
            "Prohibition ('Do not use numbers not in the source') collapses P to 0% "
            "and increases G by 9-22pp across all tested models."
        ),
    }


# ================================================================
# UNIFIED MEASUREMENT API
# ================================================================

def measure(doc_text, source=None, comparisons=None, topic=None):
    """Full measurement profile for an AI-generated document.

    Args:
        doc_text: The document text to analyze
        source: Optional source material the doc was generated from
        comparisons: Optional list of comparison versions (for temporal consistency)
        topic: Optional topic description (for Gate 0, requires Gemini API)

    Returns dict with all applicable measurement layers + metadata.
    """
    # Scope check: warn if document lacks markdown structure
    _has_md = bool(extract_headings_simple(doc_text))
    if not _has_md:
        import warnings
        warnings.warn(
            "No markdown headings found (## or ###). "
            "Clarethium Measure is validated on markdown analytical documents. "
            "Results may not be meaningful for unstructured text.",
            UserWarning
        )

    profile = {
        "metadata": {
            "version": "1.4",
            "has_markdown_structure": _has_md,
            "layers_run": [],
            "scope": (
                "Primary: markdown analytical docs. Cross-domain tested (v1.2): "
                "product specs, research summaries, code docs. "
                "2-3 generators (Gemini, xAI/Grok, GPT), English."
            ),
            "cannot_detect": [
                "Causal/interpretive errors (invisible to all layers)",
                (
                    "Fixed-point confabulation: stable wrong numbers that "
                    "repeat identically across regenerations. Temporal "
                    "consistency detects generation noise, not deterministic "
                    "errors. A model can produce the same wrong number in "
                    "every regeneration with zero variance."
                ),
                "Reasoning quality (epistemic calibration is surface proxy only)",
                "Human-perceived quality (structural layers orthogonal: r≈0.1)",
                "Numbers as words, relative claims ('doubled', 'nearly half')",
                (
                    "Numeric claims beyond the first 25 per document. "
                    "Source-network verification is capped at 25 claims "
                    "for cost-efficiency; longer documents have "
                    "additional numeric claims that are not individually "
                    "verified against external sources."
                ),
            ],
            "thresholds_note": REFERENCE["thresholds_note"],
        },
    }

    # Layer 1: Structural Profile (always)
    profile["structural"] = structural_profile(doc_text, topic)
    profile["metadata"]["layers_run"].append("structural")

    # Layer 2: Claim Density (always)
    profile["claim_density"] = claim_density(doc_text)
    profile["metadata"]["layers_run"].append("claim_density")

    # Layer 3: Temporal Consistency (if comparisons provided)
    if comparisons:
        profile["temporal_instability"] = temporal_consistency(doc_text, comparisons)
        profile["metadata"]["layers_run"].append("temporal_instability")

    # Layer 4: Source Matching (if source provided)
    if source:
        profile["source_fidelity"] = source_matching(doc_text, source)
        profile["metadata"]["layers_run"].append("source_fidelity")

    # Layer 5: Entity Provenance (if source provided)
    if source:
        profile["entity_provenance"] = entity_provenance(doc_text, source)
        profile["metadata"]["layers_run"].append("entity_provenance")

    # Layer 6: Vocabulary Proximity (if source provided)
    if source:
        profile["vocabulary_proximity"] = vocabulary_proximity(doc_text, source)
        profile["metadata"]["layers_run"].append("vocabulary_proximity")

    # Layer 7: Presentation Features (always)
    profile["presentation"] = presentation_features(doc_text)
    profile["metadata"]["layers_run"].append("presentation")

    # Layer 8: Epistemic Calibration (if source provided)
    if source:
        profile["epistemic_calibration"] = epistemic_calibration(doc_text, source)
        profile["metadata"]["layers_run"].append("epistemic_calibration")

    # Layer 9: Information Novelty (always)
    profile["information_novelty"] = information_novelty(doc_text)
    profile["metadata"]["layers_run"].append("information_novelty")

    # Layer 10: Quality Profile (always, computed from other layers)
    profile["quality_profile"] = quality_profile(profile)
    profile["metadata"]["layers_run"].append("quality_profile")

    # Layer 11: Grounding Decomposition (if source provided)
    if source:
        profile["grounding_decomposition"] = grounding_decomposition(doc_text, source)
        profile["metadata"]["layers_run"].append("grounding_decomposition")

    return profile


# ================================================================
# DISPLAY
# ================================================================

def _range_label(score, ref_dict):
    """Place a score within reference distribution ranges."""
    labels = []
    for cond, stats in sorted(ref_dict.items()):
        m, s = stats["mean"], stats["sd"]
        if abs(score - m) < s:
            labels.append(f"~{cond}")
        elif score > m + s:
            labels.append(f">{cond}")
    return ", ".join(labels[:2]) if labels else "outside reference range"


def print_profile(profile):
    """Human-readable profile output."""
    meta = profile["metadata"]
    print(f"\n{'=' * 64}")
    print(f"  CLARETHIUM MEASURE v{meta['version']}: AI Output Profile")
    print(f"  Layers: {', '.join(meta['layers_run'])}")
    print(f"  Scope: {meta['scope'][:70]}...")
    print(f"{'=' * 64}")

    # Structural
    s = profile["structural"]
    print(f"\n  STRUCTURAL PROFILE (style classification, not quality)")
    print(f"  {'─' * 58}")
    if "gate_0" in s:
        g0 = s["gate_0"]
        print(f"  Gate 0 (heading defaultness):    {g0['score']:.4f}  "
              f"(exploratory threshold: ≤{g0['exploratory_threshold']})")
    mr = s["mechanism_ratio"]
    mr_label = _range_label(mr["score"], mr["reference"])
    print(f"  Mechanism ratio:                 {mr['score']:.4f}  "
          f"(mech={mr['mechanism_count']}, buzz={mr['buzzword_count']})  [{mr_label}]")
    ar = s["assertion_ratio"]
    ar_label = _range_label(ar["score"], {k: v for k, v in ar["reference"].items()})
    prec = f"  precision: {ar['precision']}" if ar["precision"] != "adequate" else ""
    sections = "" if ar.get("used_section_bodies", True) else "  (no sections found; full text)"
    print(f"  Assertion ratio:                 {ar['score']:.4f}  "
          f"(total={ar['total_matches']}){prec}{sections}  [{ar_label}]")

    # Claim density
    cd = profile["claim_density"]
    print(f"\n  CLAIM DENSITY ({cd['word_count']} words)")
    print(f"  {'─' * 58}")
    print(f"  Numerical: {cd['numerical_per_1kw']}/1Kw ({cd['numerical_claims']} total)")
    print(f"  Causal:    {cd['causal_per_1kw']}/1Kw ({cd['causal_claims']} total)")
    print(f"  Note: {cd['recall_caveat']}")

    # Temporal instability (proxy for fabrication, not direct measurement)
    if "temporal_instability" in profile:
        ft = profile["temporal_instability"]
        print(f"\n  TEMPORAL INSTABILITY ({ft['n_versions']} versions, "
              f"precision: {ft['precision']})")
        print(f"  {'─' * 58}")
        rate = ft.get("instability_rate")
        if rate is not None:
            print(f"  Instability rate: {rate:.1%}  "
                  f"({ft['unstable_count']} unstable / {ft['total_unique']} unique numbers)")
            print(f"  Stable: {ft['stable_count']}  "
                  f"(may include fixed-point confabulation; unknown fraction)")
        else:
            print(f"  No numbers found.")

    # Source fidelity
    if "source_fidelity" in profile:
        fs = profile["source_fidelity"]
        print(f"\n  SOURCE FIDELITY ({fs['total_numbers']} numbers, "
              f"precision: {fs['precision']})")
        print(f"  {'─' * 58}")
        print(f"  Unsourced: {fs['unsourced_rate']:.1%}  "
              f"({fs['not_in_source']}/{fs['total_numbers']})")
        ref = fs["reference"]
        print(f"  Reference: T1={ref['T1_BASIC']['mean_unsourced']:.1%}, "
              f"T2={ref['T2_STANDARD']['mean_unsourced']:.1%}, "
              f"T3={ref['T3_REFINED']['mean_unsourced']:.1%}, "
              f"T4={ref['T4_AGENTIC']['mean_unsourced']:.1%}")
        if fs["unsourced_details"]:
            for d in fs["unsourced_details"][:5]:
                print(f"    {d['value']:>8s} ({d['type']})  ...{d['context'][:50]}...")

    # Entity provenance
    if "entity_provenance" in profile:
        ep = profile["entity_provenance"]
        print(f"\n  ENTITY PROVENANCE ({ep['total_entities']} entities, "
              f"precision: {ep['precision']}) [{ep['status']}]")
        print(f"  {'─' * 58}")
        print(f"  Unsourced: {ep['not_in_source']}/{ep['total_entities']}  "
              f"({ep['unsourced_rate']:.1%})")
        if ep["unsourced_details"]:
            for d in ep["unsourced_details"][:5]:
                print(f"    [{d['type']:>10s}] {d['value']}")

    # Vocabulary proximity
    if "vocabulary_proximity" in profile:
        vp = profile["vocabulary_proximity"]
        print(f"\n  VOCABULARY PROXIMITY ({vp['total_sentences']} sentences) "
              f"[{vp['status']}]")
        print(f"  {'─' * 58}")
        print(f"  Mean: {vp['mean_proximity']:.3f}  "
              f"Low (<0.5): {vp['low_proximity_count']}/{vp['total_sentences']}")
        print(f"  Note: {vp['interpretation_note'][:80]}...")

    # Epistemic calibration
    if "epistemic_calibration" in profile:
        ec = profile["epistemic_calibration"]
        print(f"\n  EPISTEMIC CALIBRATION ({ec['total_assertions']} assertions, "
              f"precision: {ec['precision']}) [{ec['status']}]")
        print(f"  {'─' * 58}")
        if ec["calibration_score"] is not None:
            print(f"  Calibration: {ec['calibration_score']:.1%}  "
                  f"({ec['grounded_assertions']}/{ec['total_assertions']} grounded)")
            print(f"  Overclaiming: {ec['overclaiming_rate']:.1%}")
        else:
            print(f"  No assertion sentences found.")
        if ec.get("overclaiming_details"):
            for d in ec["overclaiming_details"][:3]:
                print(f"    UNGROUNDED [{', '.join(d['markers'])}]: "
                      f"{d['sentence'][:60]}...")

    # Information novelty
    inv = profile.get("information_novelty")
    if inv and inv.get("total_sentences"):
        print(f"\n  INFORMATION NOVELTY ({inv['total_sentences']} sentences) "
              f"[{inv['status']}]")
        print(f"  {'─' * 58}")
        print(f"  Mean novelty: {inv['mean_novelty']:.3f}  "
              f"Repetition: {inv['repetition_rate']:.1%}  "
              f"Decay: {inv['information_decay']:+.4f}")
        print(f"  First quarter: {inv['first_quarter_novelty']:.3f}  "
              f"Last quarter: {inv['last_quarter_novelty']:.3f}")

    # Presentation
    pf = profile["presentation"]
    print(f"\n  PRESENTATION FEATURES (descriptive)")
    print(f"  {'─' * 58}")
    print(f"  TTR: {pf['type_token_ratio']:.3f}    "
          f"FK grade: {pf['fk_grade_level']:.1f}    "
          f"Assertiveness: {pf['assertiveness_ratio']:.3f}")
    print(f"  Hedges: {pf['n_hedges']}  Asserts: {pf['n_asserts']}  "
          f"Named concepts: {pf['n_named_concepts']}  "
          f"Format density: {pf['formatting_density']:.2f}")

    # Quality Profile
    if "quality_profile" in profile:
        qp = profile["quality_profile"]
        print(f"\n  QUALITY PROFILE [{qp['status']}]")
        print(f"  {'─' * 58}")
        if qp["substance_index"] is not None:
            comps = ', '.join(f'{k}={v:.2f}'
                              for k, v in qp['substance_components'].items())
            print(f"  Substance:    {qp['substance_index']:.3f}  "
                  f"({qp['n_substance_layers']} layers: {comps})")
        else:
            print(f"  Substance:    insufficient data (need source material)")
        if qp["presentation_index"] is not None:
            comps = ', '.join(f'{k}={v:.2f}'
                              for k, v in qp['presentation_components'].items())
            print(f"  Presentation: {qp['presentation_index']:.3f}  "
                  f"({qp['n_presentation_layers']} layers: {comps})")
        if qp["gap"] is not None:
            print(f"  Gap:          {qp['gap']:+.3f}  ({qp['gap_direction']})")

    # Limits
    print(f"\n  {'─' * 58}")
    print(f"  CANNOT DETECT:")
    for limit in meta["cannot_detect"]:
        print(f"    - {limit}")
    print(f"\n  {meta['thresholds_note'][:80]}...")
    print(f"{'=' * 64}\n")


# ================================================================
# CLI
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Clarethium Measure: AI Output Measurement Profile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python clarethium_measure.py --doc output.md\n"
            "  python clarethium_measure.py --doc output.md --source ref.md\n"
            "  python clarethium_measure.py --doc v1.md --compare v2.md v3.md\n"
            "  python clarethium_measure.py --doc output.md --source ref.md --compare v2.md\n"
            "  python clarethium_measure.py --doc output.md --topic 'market analysis' --json\n"
        ),
    )
    parser.add_argument("--doc", "-d", required=True, help="Document to analyze")
    parser.add_argument("--source", "-s", help="Source/reference material")
    parser.add_argument("--compare", "-c", nargs="+", help="Comparison versions")
    parser.add_argument("--topic", "-t", help="Topic (enables Gate 0, requires Gemini API)")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    with open(args.doc) as f:
        doc_text = f.read()

    source_text = None
    if args.source:
        with open(args.source) as f:
            source_text = f.read()

    comparison_texts = None
    if args.compare:
        comparison_texts = []
        for path in args.compare:
            with open(path) as f:
                comparison_texts.append(f.read())

    profile = measure(doc_text, source=source_text,
                      comparisons=comparison_texts, topic=args.topic)

    if args.json:
        print(json.dumps(profile, indent=2, default=str))
    else:
        print_profile(profile)


if __name__ == "__main__":
    main()
