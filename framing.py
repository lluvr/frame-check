"""
Framing detection layer (Layer A).

Detects the structural frame a document puts around reality:
what it covers, how it makes its case, and what it leaves invisible.

Zero LLM. All regex/text computation. Zero additional cost per profile.

Seven components:
  detect_coverage()        - 5 analytical categories, density per 1K words
  temporal_orientation()   - past/present/future sentence ratio
  detect_voice()           - prescriptive/promotional/descriptive/analytical voice
  detect_epistemic_basis() - how claims are supported (sourced vs unsourced)
  framing_portrait()       - the synthesis: what the document does to your perception
  framing_headline()       - single most important finding for the annotated doc
  framing_summary()        - backward-compatible descriptive summary
"""

import re

from clarethium_measure import split_sentences


# ================================================================
# Category patterns
# ================================================================

ANALYTICAL_CATEGORIES = {
    # Causal language detection. The prior version only caught
    # passive/prepositional forms ("driven by", "caused by",
    # "due to") and missed active voice ("is driving", "causes",
    # "leading to", "contributing to"). Real LLM text uses
    # active voice at least as often as passive.
    "causes": re.compile(
        r'\b(because|due\s+to|driven\s+by|caused?\s+by|as\s+a\s+result|led\s+to|'
        r'attributed\s+to|resulting\s+from|stems?\s+from|owing\s+to|'
        r'fueled\s+by|spurred\s+by|triggered\s+by|enabled\s+by|'
        r'on\s+the\s+back\s+of|thanks\s+to|a\s+result\s+of|'
        # Active voice forms
        r'driv(?:ing|es?)|caus(?:ing|es)|lead(?:ing|s)\s+to|'
        r'contribut(?:ing|es?)\s+to|result(?:ing|s)\s+(?:in|from)|'
        r'explains?\s+(?:why|how)|accounts?\s+for|'
        r'responsible\s+for|plays?\s+a\s+(?:role|part)\s+in)\b',
        re.IGNORECASE
    ),
    "risks": re.compile(
        r'\b(risks?|threats?|challenges?|concerns?|vulnerab\w*|downsides?|'
        r'obstacles?|barriers?|limitations?|constraints?|dangers?|warnings?|'
        r'caveats?|drawbacks?|disruptions?|headwinds?|pressure[ds]?|declin(?:e[ds]?|ing)|'
        r'fragil\w*|expos\w+\s+to|bottlenecks?|'
        # Common LLM phrasings for risk-adjacent concepts
        r'adverse\s+(?:events?|effects?|reactions?|outcomes?)|'
        r'shortages?|side\s+effects?|complications?|'
        r'discontinued|discontinuation|recalls?|failures?)\b',
        re.IGNORECASE
    ),
    # Stakeholder detection. Two tiers:
    #   Tier 1: action verbs (affects, impacts, benefits, harms)
    #           that inherently imply someone is affected.
    #   Tier 2: named stakeholder groups as standalone nouns.
    #           The prior version required a following verb
    #           ("patients are/face/suffer"), which missed
    #           natural constructions like "7% of participants
    #           discontinued" and "lower-income populations."
    #           Standalone nouns are less precise but catch
    #           the real-world phrasings that LLMs produce.
    "stakeholders": re.compile(
        r'\b(affects?|impacts?|benefits?|harms?|stakeholders?|'
        r'populations?|workforce|residents|displaced|communities|'
        r'consumers?|workers?|investors?|patients?|participants?|'
        r'employees?|taxpayers?|households?|citizens?|users?|'
        r'regulators?|insurers?|payers?|physicians?|customers?|shareholders?|analysts?|'
        r'(?:lower|low|high|middle)[- ]income|'
        # Industry participant roles
        r'providers?|suppliers?|manufacturers?|competitors?|'
        r'partners?|vendors?|clients?|subscribers?)\b',
        re.IGNORECASE
    ),
    "trends": re.compile(
        r'\b(grow(?:ing|th|n|s)?|grew|decline[ds]?|declining|'
        r'increas(?:e[ds]?|ing|ingly)|decreas(?:e[ds]?|ing)|'
        r'r(?:ising|ose|isen)|f(?:alling|ell|allen)|'
        r'surg(?:e[ds]?|ing)|expand(?:ed|ing|s)?|expansion|'
        r'shrink(?:ing|s)?|shrank|contract(?:ed|ing|ion)|'
        r'shift(?:ing|ed|s)?|emerg(?:ing|ed|ence)|'
        r'transitioning|increasingly|'
        r'trends?|trajectory|momentum|acceleration|'
        r'evolution|transformation|'
        r'projected|forecast(?:ed)?|outlook)\b',
        re.IGNORECASE
    ),
    "uncertainty": re.compile(
        r'\b(unclear|uncertain(?:ty)?|debated|contested|depends|varies|'
        r'unpredictable|unknown|estimated|'
        # "approximately" and "roughly" only count when NOT followed by
        # a number or currency symbol. "approximately $180B" is a
        # precision qualifier, not uncertainty analysis. Without this
        # guard, financial documents that qualify numbers with
        # "approximately" score false uncertainty coverage.
        r'approximate(?:ly)?(?!\s*[\d$%])|roughly(?!\s*[\d$%])|'
        r'open\s+question|remains\s+to\s+be\s+seen|'
        r'not\s+(?:yet|fully)\s+(?:clear|understood|determined)|'
        # Hedged concern phrases (more specific than bare "however")
        r'concerns?\s+(?:about|over|remain|that)|'
        r'questions?\s+(?:about|whether|remain)|'
        r'remains?\s+(?:unclear|uncertain|to\s+be\s+seen|limited|insufficient|incomplete|open)|'
        # Data limitation markers common in LLM health/science text
        r'limited\s+(?:data|evidence|research)|insufficient\s+(?:data|evidence)|'
        r'long[- ]term\s+(?:safety|outcomes?|effects?|data|implications?)|'
        r'preliminary|inconclusive|unresolved|tentative|'
        # Eight additional terms/phrases targeting hedge and
        # time-distance phrasing the prior regex missed on
        # analytical-text uncertainty framing.
        r'undemonstrated|unproven|theoretically\s+promising|'
        r'years\s+or\s+decades|no\s+credible\s+signs?|'
        r'not\s+yet\s+clear|far\s+from\s+settled)\b',
        re.IGNORECASE
    ),
}


# Hand-curated representative samples of each category's vocabulary,
# surfaced to MCP v2 consumers so the detector's lens is visible in
# the response. Keep these in sync with ANALYTICAL_CATEGORIES regexes;
# they are samples, not exhaustive lists. The vocabulary_source field
# in the MCP v2 response points agents to the full regex.
ANALYTICAL_VOCAB_SAMPLES = {
    "causes": [
        "because", "due to", "driven by", "caused by", "as a result",
        "led to", "stems from", "attributed to", "resulting from",
        "explains why", "accounts for", "responsible for",
    ],
    "risks": [
        "risks", "threats", "challenges", "concerns", "vulnerabilities",
        "downsides", "obstacles", "barriers", "dangers", "warnings",
        "caveats", "drawbacks", "headwinds",
    ],
    "stakeholders": [
        "affects", "impacts", "benefits", "harms", "stakeholders",
        "populations", "consumers", "workers", "investors", "patients",
        "communities", "employees", "customers",
    ],
    "trends": [
        "growing", "decline", "increasing", "rising", "surging",
        "expanding", "shrinking", "shifting", "emerging", "transitioning",
        "trajectory", "momentum", "acceleration", "evolution",
    ],
    "uncertainty": [
        "unclear", "uncertain", "debated", "contested", "depends",
        "unpredictable", "unknown", "estimated", "approximately", "roughly",
        "open question", "remains to be seen", "preliminary", "inconclusive",
    ],
}


# ================================================================
# Temporal patterns
# ================================================================

PAST_RE = re.compile(
    # Auxiliaries and common copulas
    r'\b(was|were|had|did|'
    # Financial/analytical past tense (the original list)
    r'grew|declined|fell|rose|reached|'
    r'exceeded|dropped|increased|decreased|experienced|'
    # Common business/event verbs in past tense
    r'started|launched|announced|released|reported|disclosed|filed|'
    r'published|stated|confirmed|completed|finished|achieved|'
    r'acquired|divested|merged|sold|bought|invested|spent|'
    r'hired|fired|retired|joined|departed|resigned|named|appointed|'
    r'closed|opened|expanded|contracted|shifted|moved|relocated|'
    r'followed|preceded|occurred|happened|took\s+place|'
    r'went|came|saw|made|took|gave|found|knew|became|said|told|'
    r'introduced|unveiled|debuted|'
    # Time references
    r'in\s+20[01]\d|in\s+201\d|in\s+202[0-6]|last\s+year|previously|'
    r'historically|traditionally|formerly|originally|initially|earlier)\b',
    re.IGNORECASE
)

FUTURE_RE = re.compile(
    r'\b(will|shall|projected|forecast|expected\s+to|anticipated|'
    r'predicts?|estimates?\s+(?:that|a)|by\s+202[7-9]|by\s+20[3-9]\d|'
    r'going\s+forward|in\s+the\s+(?:coming|next)|outlook|'
    r'poised\s+to|set\s+to|on\s+track)\b',
    re.IGNORECASE
)


# ================================================================
# detect_coverage
# ================================================================

# Diminishing modifiers that weaken risk/uncertainty markers.
# "Minimal risks" and "concerns are overblown" use risk vocabulary
# but dismiss the risk rather than analyze it. Counting these as
# "covered" produces a false negative on the most important signal.
# Applied only to "risks" and "uncertainty" categories.
#
# Checks BOTH directions: "minimal risks" (diminisher before) and
# "risks are minimal" (diminisher after). The post-match check is
# bounded by the current sentence to avoid false suppression from
# unrelated diminishers in adjacent sentences.
_DIMINISHER_RE = re.compile(
    r'\b(minimal|negligible|minor|few|limited|overblown|'
    r'unlikely|manageable|low|slight|marginal|trivial|'
    r'insignificant|immaterial|modest|remote|hypothetical|'
    r'overstated|exaggerated|'
    # "No + adjective" dismissal compounds. These adjectives
    # almost exclusively appear before risk/uncertainty nouns in
    # dismissal constructions ("no meaningful risks", "no
    # elevated risk profiles", "no unresolved challenges").
    # They do NOT appear in "no [adj] that [noun]" structures
    # that would indicate legitimate discussion.
    r'no\s+(?:real|significant|major|meaningful|known|identified|'
    r'material|apparent|notable|elevated|unresolved|remaining|'
    r'critical|substantive|credible|immediate|direct|evident)|'
    # Elimination verbs that assert all risk has been removed.
    # "Without any" is NOT here: it's in the tight negation
    # regex instead, because "without any doubt, the risks..."
    # has "without any" 30+ chars from "risks" in the 60-char
    # window and would false-filter legitimate discussion.
    r'eliminat\w*\s+(?:all|any|every))\b',
    re.IGNORECASE,
)

_DIMINISHER_PRE_WINDOW = 60  # chars before the match to check

# Sentence-ending punctuation. The post-window check stops at
# the first sentence boundary so a diminisher in the NEXT sentence
# does not suppress a genuine match in the current sentence.
_SENTENCE_END_RE = re.compile(r'[.!?]\s')

# Direct negation that denies existence of the keyword's referent.
# Separate from the diminisher because it uses a TIGHT window (20
# chars) anchored to the match position ($). This catches "no
# risks", "zero threats", "without any concerns" but NOT "no
# doubt that risks exist" (where "no" modifies "doubt").
#
# Two tiers of negation tightness:
#   Tier 1 (allows 1 adjective): "no", "zero", "without any",
#     "free of/from", "absence of", "lack of". These are
#     unambiguously negation phrases. "No meaningful risks" (1
#     adjective between) matches. "No doubt that risks" (2 words)
#     does not, preventing false filters.
#   Tier 2 (zero intervening words): bare "without" alone.
#     "Without risks" = negation. "Without obesity remains
#     insufficient" has "without" modifying "obesity", not the
#     keyword. Requiring 0 words prevents this false filter.
_NEGATION_RE = re.compile(
    r'(?:'
    r'\b(?:no|zero|without\s+any|free\s+(?:of|from)|'
    r'absence\s+of|lack\s+of)(?:\s+\w+){0,1}'
    r'|'
    r'\bwithout'
    r')\s*$',
    re.IGNORECASE,
)
_NEGATION_PRE_WINDOW = 20  # chars: tight to avoid false filters


def _list_substantive_matches(text, pattern, apply_diminisher=False):
    """Return the list of substantive pattern matches as lowercased strings.

    When apply_diminisher is True, matches are filtered for:
      1. Diminishing modifiers (minimal, negligible, overblown, etc.):
         - Pre-match: 60-char window, no sentence boundary restriction
         - Post-match: to end of current sentence, up to 80 chars
      2. Direct negation (no, zero, without, etc.):
         - Pre-match only: 20-char window, anchored to end (the
           negation must be the last phrase before the keyword)
         - Catches "no risks" without catching "no doubt that risks"

    The returned list preserves match order for reproducibility; consumers
    needing deduplication should apply it downstream. Backs the
    MCP contract v2 markers_matched field.
    """
    if not apply_diminisher:
        return [_normalize_marker(m.group(0)) for m in pattern.finditer(text)]

    matches = []
    for m in pattern.finditer(text):
        # Check backward window for diminishing modifiers.
        # Bounded by sentence end: a diminisher in the previous
        # sentence ("risks are minimal.") must not filter a keyword
        # in the current sentence ("However, threats persist.").
        pre_start = max(0, m.start() - _DIMINISHER_PRE_WINDOW)
        pre_window = text[pre_start:m.start()]
        last_sent = max(
            pre_window.rfind(". "),
            pre_window.rfind(".\n"),
            pre_window.rfind("? "),
            pre_window.rfind("! "),
        )
        if last_sent >= 0:
            pre_window = pre_window[last_sent + 2:]
        if _DIMINISHER_RE.search(pre_window):
            continue
        # Check forward window for diminishing modifiers
        post_text = text[m.end():]
        sent_end = _SENTENCE_END_RE.search(post_text)
        if sent_end:
            post_window = post_text[:sent_end.start()]
        else:
            post_window = post_text[:80]
        if _DIMINISHER_RE.search(post_window):
            continue
        # Check tight backward window for direct negation
        neg_start = max(0, m.start() - _NEGATION_PRE_WINDOW)
        neg_window = text[neg_start:m.start()]
        if _NEGATION_RE.search(neg_window):
            continue
        matches.append(_normalize_marker(m.group(0)))
    return matches


def _count_substantive_matches(text, pattern, apply_diminisher=False):
    """Backwards-compatible wrapper around _list_substantive_matches.

    Retained because external callers may have taken a dependency on the
    count-returning name. New internal code uses _list_substantive_matches
    and computes len() locally where needed.
    """
    return len(_list_substantive_matches(text, pattern, apply_diminisher=apply_diminisher))


def _normalize_marker(raw):
    """Normalize a captured marker to its sentence-space form.

    Matches may span newlines in the original text (e.g., a line-wrapped
    "due\nto"). The sentence-level attribution path joins multi-line
    paragraphs with single spaces, so the marker must be normalized to
    match: lowercase + any run of whitespace (including newlines,
    tabs, multi-space) collapsed to a single space.

    Normalized at capture time so every downstream consumer
    (markers_matched, sentence_preview center, MCP v2 payload) sees
    the same sentence-space form. A marker that cannot be located in
    the whitespace-normalized sentence text would otherwise break
    preview-centering.
    """
    return re.sub(r'\s+', ' ', raw.lower())


def _list_substantive_spans(text, pattern, apply_diminisher=False):
    """Return list of (match_text_lower, start, end) for substantive matches.

    Sentence-level attribution needs char offsets so a match can be mapped
    back to the sentence containing it. Functionally identical filtering
    to _list_substantive_matches; adds position information. Separate
    function rather than dual-return so the cheap string-only call path
    (MCP v2 markers_matched) does not pay the span-building cost.

    Markers are whitespace-normalized via _normalize_marker so downstream
    preview-centering works on multi-line matches.
    """
    if not apply_diminisher:
        return [
            (_normalize_marker(m.group(0)), m.start(), m.end())
            for m in pattern.finditer(text)
        ]

    spans = []
    for m in pattern.finditer(text):
        pre_start = max(0, m.start() - _DIMINISHER_PRE_WINDOW)
        pre_window = text[pre_start:m.start()]
        last_sent = max(
            pre_window.rfind(". "),
            pre_window.rfind(".\n"),
            pre_window.rfind("? "),
            pre_window.rfind("! "),
        )
        if last_sent >= 0:
            pre_window = pre_window[last_sent + 2:]
        if _DIMINISHER_RE.search(pre_window):
            continue
        post_text = text[m.end():]
        sent_end = _SENTENCE_END_RE.search(post_text)
        if sent_end:
            post_window = post_text[:sent_end.start()]
        else:
            post_window = post_text[:80]
        if _DIMINISHER_RE.search(post_window):
            continue
        neg_start = max(0, m.start() - _NEGATION_PRE_WINDOW)
        neg_window = text[neg_start:m.start()]
        if _NEGATION_RE.search(neg_window):
            continue
        spans.append((_normalize_marker(m.group(0)), m.start(), m.end()))
    return spans


# Candidate-miss patterns. These fire on syntactic/semantic hints that
# a dimension may be covered by vocabulary the primary ANALYTICAL_CATEGORIES
# regex does not recognize. Used with include_candidates=True on
# detect_coverage to surface under-detection sentences the reader can
# inspect. The construct is: "the primary detector found no marker, but
# this sentence looks adjacent to the dimension; reader judgement on
# whether the document substantively covers it."
#
# Derived from a semiconductor-essay failure case where the primary
# causes-regex missed "rationale centers on," "given," and implicit
# causal reasoning. Candidate patterns target those specific
# structural hints. Kept conservative; false positives on candidate
# patterns are a tolerable cost because they are surfaced with an
# explicit "possibly missed" caveat, not as detections.
CANDIDATE_PATTERNS = {
    "causes": re.compile(
        r'\b(rationale|motivation|reason\s+(?:for|why|that)|'
        r'centers?\s+on|given\s+(?:that|the)|in\s+light\s+of|'
        r'why\s+this|the\s+(?:driver|motive|impetus)\s+of|'
        r'underpin(?:s|ning|ned)|undergirds?)\b',
        re.IGNORECASE
    ),
    "risks": re.compile(
        r'\b(worries|tensions|caution(?:ary)?|doubtful|'
        r'questionable|ambiguit(?:y|ies)|uncertainty\s+about\s+'
        r'(?:safety|stability|outcomes))\b',
        re.IGNORECASE
    ),
    "stakeholders": re.compile(
        # Tightened to stakeholder-specific constructions. Earlier draft
        # included bare "people" and "groups" which fired on nearly any
        # paragraph discussing any topic; dilutes the candidate-miss
        # signal's usefulness. All retained forms require a specific
        # stakeholder-direction construction (who/affected/involved/
        # impacted) or a named stakeholder category (the public,
        # members of a group, individuals-who-do-X).
        #
        # R2 refinement: exclude adjectival "the public <noun>" forms
        # (the public web, the public sector, etc.) which are
        # rhetorical rather than stakeholder-referring. Verified
        # against a 48-sentence candidate corpus; removes 1 false
        # positive while preserving genuine stakeholder uses.
        r'\b(people\s+who|groups\s+(?:who|affected)|'
        r'those\s+(?:who|affected|involved|impacted)|'
        r'anyone\s+who|'
        r'the\s+public\b(?!\s+(?:web|domain|sphere|record|opinion|'
        r'sector|health|good|interest|eye|face|library|school|'
        r'transport|transit|safety))|'
        r'members\s+of|individuals?\s+who)\b',
        re.IGNORECASE
    ),
    "trends": re.compile(
        r'\b(restructuring|consolidation|diversification|maturation|'
        r'shift(?:ing)?\s+in|mov(?:ed|ing|ement)\s+(?:toward|away)|'
        r'develop(?:ed|ing|ment)\s+(?:into|of|toward)|'
        r'outlast(?:ing|ed)?|endur(?:e[ds]?|ing|ance))\b',
        re.IGNORECASE
    ),
    "uncertainty": re.compile(
        # R1 refinement: exclude rhetorical "perhaps the [superlative]"
        # constructions (perhaps the most, a defining, the best). These
        # are stylistic flourishes rather than epistemic hedges and
        # inflated the uncertainty candidate rate on the validation
        # corpus (6 of 9 perhaps-triggered rows were rhetorical).
        # Verified against a 48-sentence candidate corpus; removes 3
        # false positives while preserving all 3 genuine hedge uses.
        r'\b(might\s+(?:be|have)|'
        r'perhaps(?!\s+(?:the|a|an)\s+(?:most|least|best|worst|first|'
        r'last|defining|leading|dominant|primary|central|key|main|chief|'
        r'top|greatest))|'
        r'possibly|conceivably|'
        r'some\s+doubt|open\s+to\s+(?:debate|question|interpretation)|'
        r'it\s+is\s+(?:possible|plausible)\s+that)\b',
        re.IGNORECASE
    ),
}


def _compute_sentence_spans(text):
    """Locate each sentence from split_sentences inside the original text.

    Returns list of dicts with sentence_index (0-based), text, heading,
    start (char offset in `text`), and end (char offset). Sentences that
    cannot be located (rare: probe too short to disambiguate on repeated
    content, or sentence-splitter returns a sentence whose 60-char prefix
    matches no occurrence at or after search_from) are stored with None
    start/end; such sentences will not be mapped to any attribution.

    Important whitespace-tolerance detail: split_sentences joins
    consecutive non-heading lines with spaces (the ' '.join(pending)
    step), which turns "Meanwhile, TSMC\\nretains" in the original text
    into "Meanwhile, TSMC retains" in the sentence. A literal text.find
    with the joined probe would miss. We search with a regex that
    tolerates any whitespace sequence wherever the probe has a space.
    This preserves correctness across line-wrapped source documents
    while keeping the mapping deterministic.

    Used by sentence-level attribution in detect_coverage when
    include_attribution=True or include_candidates=True.

    Performance discipline (2026-04-30 fix). The pre-fix shape had
    two pathologies on long documents:

      1. Slicing cost. `re.search(flexible, text[search_from:])`
         allocated a new string of size O(text_len) on every
         sentence. At ~500 sentences in a 100K-char doc, that was
         50M chars of redundant copying. Replaced with
         `pattern.search(text, search_from)` on a compiled
         pattern; the regex engine handles the start position
         internally with no copy.

      2. Wrong-and-slow fallback. When the windowed search
         missed, the pre-fix code re-ran the search across the
         full text from offset 0 (`re.search(flexible, text)`).
         The intent was to recover from sentences that
         split_sentences saw in a different order than the text;
         the actual behaviour on real documents was: when a
         probe matched an earlier identical sentence (repeated
         section, boilerplate, list-item refrain), the fallback
         found the FIRST occurrence and produced a wrong span,
         pointing attribution at the wrong instance. The
         fallback was both slow (O(text_len) per miss; on tiled
         content it fired on most sentences) and incorrect
         (claimed attribution that pointed elsewhere).

         Replaced with: if the windowed search misses, mark the
         sentence as unlocated (start=None, end=None) and do
         not advance search_from. An unattributed sentence is
         strictly better than a wrongly-attributed sentence
         because the UI surfaces "no markers found" rather
         than "the marker for X is at this other place that
         is actually a different sentence."

    Combined effect on the worked-examples corpus tiled to size:
      40K  529ms -> 5ms
      50K  695ms -> 6ms
      100K 747ms -> 11ms
    """
    sentences = split_sentences(text)
    spans = []
    search_from = 0
    for idx, (heading, sent, para_idx) in enumerate(sentences):
        probe = sent[:60] if len(sent) > 60 else sent
        pos = -1
        length = 0
        if probe:
            # Build whitespace-tolerant pattern. The probe comes from
            # split_sentences, which joins consecutive non-heading
            # lines with single spaces; the original text may have
            # \n / multi-space sequences where the joined sentence
            # has a single space. Convert each escaped-space (or run
            # of escaped-spaces in a row) to a single \s+ so the
            # regex matches whatever whitespace shape the original
            # text uses.
            #
            # The (?:\\\s)+ run-collapsing form is load-bearing: a
            # markdown table joined by split_sentences produces a
            # probe with long runs of consecutive spaces (column
            # padding). The pre-2026-04-30 substitution emitted one
            # \s+ per escaped-space individually, so a 30-space run
            # produced 30 consecutive \s+ in the pattern. Each run
            # was an independent quantifier and the regex engine
            # backtracked exponentially on partial matches; on a
            # 60-char table-header probe the search took 5ms per
            # 200-char text scan, and across the full document the
            # one slow sentence dominated _compute_sentence_spans
            # at 678ms despite the fast windowed-search refactor.
            # Collapsing runs into a single \s+ keeps semantic
            # whitespace tolerance and removes the backtracking.
            escaped = re.escape(probe)
            flexible = re.sub(r'(?:\\\s)+', r'\\s+', escaped)
            pattern = re.compile(flexible)
            m = pattern.search(text, search_from)
            if m is not None:
                pos = m.start()
                length = m.end() - m.start()
        if pos < 0:
            spans.append({
                "sentence_index": idx,
                "text": sent,
                "heading": heading,
                "start": None,
                "end": None,
            })
            continue
        # The sentence spans from `pos` through approximately pos+len(sent),
        # but because the original text may have whitespace of different
        # width than the joined sentence, we extend the end to match the
        # sentence length in the sentence-space plus the whitespace delta
        # discovered in the probe. A small over-estimation is tolerable
        # for attribution purposes (the end is used only to check
        # containment of a char offset).
        delta = length - len(probe)  # extra chars from flex whitespace
        end = pos + len(sent) + delta
        spans.append({
            "sentence_index": idx,
            "text": sent,
            "heading": heading,
            "start": pos,
            "end": end,
        })
        search_from = pos + 1
    return spans


def _offset_to_sentence_index(offset, sentence_spans):
    """Return the sentence_index containing char offset, or None."""
    for span in sentence_spans:
        if span["start"] is None:
            continue
        if span["start"] <= offset < span["end"]:
            return span["sentence_index"]
    return None


def _sentence_preview(sent_text, marker=None, window=80):
    """Return a short preview of a sentence, optionally centered on marker."""
    if marker and marker in sent_text.lower():
        idx = sent_text.lower().find(marker)
        half = window // 2
        start = max(0, idx - half)
        end = min(len(sent_text), idx + len(marker) + half)
        preview = sent_text[start:end]
        if start > 0:
            preview = "..." + preview
        if end < len(sent_text):
            preview = preview + "..."
        return preview
    if len(sent_text) <= window:
        return sent_text
    return sent_text[:window] + "..."


def detect_coverage(text, include_attribution=False, include_candidates=False):
    """Detect which analytical categories a document covers, with density.

    Returns per-category marker count, density per 1Kw, and coverage summary.

    Optional sentence-level extensions (opt-in; legacy callers unaffected):
      include_attribution=True: each category gets a `sentence_matches`
        list: [{sentence_index, sentence_preview, marker_text}], one entry
        per substantive match, mapping back to the sentence containing it.
      include_candidates=True: for categories with status 'not_detected',
        each gets a `candidate_sentences` list: sentences where
        CANDIDATE_PATTERNS fire, surfacing possible under-detection cases.
        Detected categories receive empty candidate_sentences (by design;
        candidate_miss is only meaningful for not-detected dimensions).
    """
    MIN_MARKERS = 2
    word_count = len(re.findall(r'\b\w+\b', text))
    kw = max(word_count / 1000, 0.1)

    categories = {}
    covered = set()

    # Pre-compute sentence spans once when attribution is requested;
    # used for both matched-marker attribution and candidate-miss
    # surfacing. Keep as None when not requested to avoid the cost.
    sentence_spans = None
    if include_attribution or include_candidates:
        sentence_spans = _compute_sentence_spans(text)

    for cat, pattern in ANALYTICAL_CATEGORIES.items():
        use_diminisher = cat in ("risks", "uncertainty")
        if include_attribution:
            spans = _list_substantive_spans(text, pattern,
                                            apply_diminisher=use_diminisher)
            matches = [m for m, _, _ in spans]
        else:
            spans = None
            matches = _list_substantive_matches(
                text, pattern, apply_diminisher=use_diminisher)
        count = len(matches)
        density = round(count / kw, 1)
        # Deduplicated, sorted sample of matched tokens for display and for
        # MCP contract v2's markers_matched field. Capped at 20 tokens to
        # bound payload size on very-high-density documents.
        unique_matches = sorted(set(matches))[:20]
        cat_entry = {
            "count": count,
            "density_per_1kw": density,
            "covered": count >= MIN_MARKERS,
            "markers_matched": unique_matches,
            "markers_matched_truncated": len(set(matches)) > 20,
        }
        # For diminisher-eligible categories, compute how many keywords
        # were dismissed (negated or diminished). A document that mentions
        # "risks" 5 times but negates 4 of them is doing something
        # different from a document that never mentions risks.
        #
        # When dismissed keywords outnumber surviving ones, the category
        # is reclassified as NOT covered: the document is actively denying
        # this dimension rather than analyzing it. A document with
        # dismissed=7, count=3 is using risk vocabulary to dismiss risks,
        # not to discuss them.
        if use_diminisher:
            raw = len(pattern.findall(text))
            dismissed = raw - count
            cat_entry["dismissed"] = dismissed
            if dismissed > count and count < MIN_MARKERS * 3:
                cat_entry["covered"] = False

        # Sentence-level attribution: map each matched span to the
        # sentence containing it so a reader can see WHERE the detector
        # fired. Deduplicated by sentence_index: each sentence appears
        # at most once; markers that fired in the sentence are
        # aggregated into a list. Capped at 20 distinct sentences per
        # dimension to bound payload size on repetition-heavy documents.
        # distinct_sentences_detected reports the full count
        # pre-truncation for honest reporting.
        if include_attribution and spans is not None:
            sentence_markers: dict[int, list[str]] = {}
            sentence_order: list[int] = []
            for marker, start, _end in spans:
                s_idx = _offset_to_sentence_index(start, sentence_spans)
                if s_idx is None:
                    continue
                if s_idx not in sentence_markers:
                    sentence_markers[s_idx] = []
                    sentence_order.append(s_idx)
                if marker not in sentence_markers[s_idx]:
                    sentence_markers[s_idx].append(marker)
            total_distinct = len(sentence_order)
            capped_order = sentence_order[:20]
            sentence_matches = []
            for s_idx in capped_order:
                sent_span = sentence_spans[s_idx]
                markers_here = sentence_markers[s_idx]
                sentence_matches.append({
                    "sentence_index": s_idx,
                    "sentence_preview": _sentence_preview(
                        sent_span["text"], marker=markers_here[0],
                    ),
                    "markers_in_sentence": markers_here,
                })
            cat_entry["sentence_matches"] = sentence_matches
            cat_entry["distinct_sentences_detected"] = total_distinct
            cat_entry["sentence_matches_truncated_at_20"] = total_distinct > 20

        categories[cat] = cat_entry
        if cat_entry["covered"]:
            covered.add(cat)

    # Candidate-miss surfacing: only meaningful for NOT-detected
    # dimensions. For detected dimensions the reader already has
    # matched-marker evidence; candidate-miss there would be noise.
    # For not-detected dimensions, a candidate match is a reader-inspectable
    # hint that the primary regex may have missed vocabulary the reader
    # would recognize. Construct-honest: caveat attached.
    if include_candidates and sentence_spans is not None:
        for cat, cat_entry in categories.items():
            if cat_entry.get("covered"):
                cat_entry["candidate_sentences"] = []
                continue
            candidate_re = CANDIDATE_PATTERNS.get(cat)
            if candidate_re is None:
                cat_entry["candidate_sentences"] = []
                continue
            candidate_sentences = []
            seen_indices = set()
            for m in candidate_re.finditer(text):
                s_idx = _offset_to_sentence_index(m.start(), sentence_spans)
                if s_idx is None or s_idx in seen_indices:
                    continue
                seen_indices.add(s_idx)
                sent_span = sentence_spans[s_idx]
                candidate_sentences.append({
                    "sentence_index": s_idx,
                    "sentence_preview": _sentence_preview(
                        sent_span["text"], marker=m.group(0).lower()
                    ),
                    "candidate_marker": m.group(0).lower(),
                    "caveat": (
                        "Candidate pattern fired; primary detector did "
                        "not. Reader judges whether this sentence "
                        "substantively covers the dimension."
                    ),
                })
                if len(candidate_sentences) >= 10:
                    break
            cat_entry["candidate_sentences"] = candidate_sentences

    all_cats = set(ANALYTICAL_CATEGORIES.keys())
    missing = all_cats - covered

    # Coverage balance: how evenly are the ADDRESSED categories covered?
    # min(densities) / max(densities) for addressed categories.
    # A document with risks at 2.8/1Kw and trends at 13.0/1Kw has
    # balance 0.15; meaning the thinnest addressed category has 15%
    # the density of the thickest. This is the quantitative signal
    # behind the Completeness Illusion pattern: presence is not depth.
    #
    # Only computed when >=2 categories are addressed (a single
    # addressed category has no reference point for imbalance).
    addressed_densities = [
        c["density_per_1kw"] for c in categories.values() if c["covered"]
    ]
    if len(addressed_densities) >= 2 and max(addressed_densities) > 0:
        coverage_balance = round(
            min(addressed_densities) / max(addressed_densities), 2
        )
    else:
        coverage_balance = None

    return {
        "categories": categories,
        "covered": sorted(covered),
        "missing": sorted(missing),
        "coverage_count": len(covered),
        "total_categories": len(all_cats),
        "word_count": word_count,
        "coverage_balance": coverage_balance,
    }


# ================================================================
# temporal_orientation
# ================================================================

def temporal_orientation(text):
    """Compute past/present/future orientation ratio.

    Uses split_sentences from clarethium_measure to get sentence-level
    granularity. "Present" is the residual bucket: sentences with no
    past/future markers. Includes definitions, methodology, structural
    sentences. Interpret as "non-temporal" when dominant.

    Construct extension (added 2026-04-20 Phase B temporal construct):
      dominant_margin: dominant_pct - runner_up_pct. Large margin =
        genuinely time-anchored; small margin = narrowly won. A
        reader interpreting "dominant: past" should weight the margin.
      balanced: True when no tense is >= 50% AND dominant_margin < 10.
        Indicates the document's tenses are roughly even; the "dominant"
        label should not be read as time-anchoring. Reader-aid
        complement to the percentage bars that already appear in the UI.

    Parallels the voice construct extension: classification signals
    emit margin + borderline state; the reader sees both the label AND
    the confidence behind it.
    """
    raw_sentences = split_sentences(text)
    # split_sentences returns (heading, sentence, para_idx) tuples
    sentences = [sent for _heading, sent, _idx in raw_sentences]

    past = sum(1 for s in sentences if PAST_RE.search(s))
    future = sum(1 for s in sentences if FUTURE_RE.search(s))
    present = len(sentences) - past - future
    total = max(len(sentences), 1)

    # Largest Remainder method on the percentage triad. Independent
    # round() per bucket can produce sums of 99 or 101 on real
    # documents (verified 2026-04-28 by mcp_quality_driver against
    # worked_examples/ai-on-life-decisions and worked_examples/fomc-
    # statement-march-2026). LR floors each bucket then distributes
    # the residue (100 - sum_of_floors) one percentage point at a
    # time to the buckets with the largest fractional parts. Result
    # always sums to exactly 100. Residue is bounded by the math:
    # three fractional parts each in [0, 1) sum to < 3, so residue
    # in {0, 1, 2}. Tiebreaker on equal fractional parts is
    # alphabetical on the bucket-name string ('future' < 'past' <
    # 'present'), set by Python's stable sort on the (-fractional,
    # name) tuple; the choice does not bias the substrate, only
    # makes the output reproducible. Edge case: zero-sentence
    # document (past = present = future = 0); skip the redistribution
    # and return zero pcts so the residue does not get spuriously
    # assigned to a bucket.
    if past == 0 and present == 0 and future == 0:
        past_pct = present_pct = future_pct = 0
    else:
        exact = {
            "past": past / total * 100,
            "present": present / total * 100,
            "future": future / total * 100,
        }
        floored = {k: int(v) for k, v in exact.items()}
        residue = 100 - sum(floored.values())
        # Sort by fractional part descending, then lexical for ties.
        order = sorted(
            ("past", "present", "future"),
            key=lambda k: (-(exact[k] - floored[k]), k),
        )
        result = dict(floored)
        for i in range(residue):
            result[order[i]] += 1
        past_pct = result["past"]
        present_pct = result["present"]
        future_pct = result["future"]
    dominant = (
        "past" if past > future and past > present
        else "future" if future > past and future > present
        else "present"
    )

    # Construct: dominant_margin is the lead over the second-place tense.
    # Sorting the three tense percentages and subtracting gives the
    # margin regardless of which tense leads. When two tenses tie, the
    # margin is 0 (dominant pick is arbitrary; reader should see
    # balanced).
    tense_pcts = sorted(
        [past_pct, present_pct, future_pct], reverse=True,
    )
    dominant_margin = tense_pcts[0] - tense_pcts[1]
    balanced = (
        tense_pcts[0] < 50 and dominant_margin < 10
    )

    return {
        "past_pct": past_pct,
        "present_pct": present_pct,
        "future_pct": future_pct,
        "dominant": dominant,
        "dominant_margin": dominant_margin,
        "balanced": balanced,
    }


# ================================================================
# Voice detection
# ================================================================

# Who is acting in this document? The voice reveals the document's
# relationship to the reader: are you being analyzed to, sold to,
# instructed, or shown a reference?
_YOU_RE = re.compile(r'\byou(?:r|rs?)?\b', re.IGNORECASE)
_WE_RE = re.compile(r'\b(?:we|our|us)\b', re.IGNORECASE)
_IMPERATIVE_RE = re.compile(
    r'^(?:use|try|test|start|stop|wait|check|avoid|apply|ensure|'
    r'verify|compare|review|monitor|scroll|pause|log|look|act|'
    r'buy|sell|invest|allocate|consider|evaluate|assess|focus|'
    r'pivot|read|switch|move|add|remove|choose|pick|get|take|'
    r'do not|don\'t|never|always|make sure|be sure)\b',
    re.IGNORECASE
)
# Structured data patterns: labels/specifications typical of reference documents
_SPEC_RE = re.compile(
    r'(?:size|weight|length|height|lifespan|habitat|distribution|'
    r'attributes?|range|depth|diameter|density|capacity|speed)\s*[:/]',
    re.IGNORECASE
)
# Promotional sentiment markers. A document that uses third-person
# voice but is saturated with positive superlatives is promotional
# even without "we/our" language. The threshold is deliberate:
# a single "unprecedented" is reporting; five superlatives in 14
# sentences is a pattern. The markers are positive-valence words
# that signal boosting or hype when clustered.
_PROMO_RE = re.compile(
    r'\b(unprecedented|extraordinary|exceptional|remarkable|'
    r'transformative|revolutionary|game[- ]chang\w+|'
    r'substantial\s+opportunit\w+|tremendous|massive\s+opportunit\w+|'
    r'bullish|exciting|impressive|robust\s+growth|'
    r'record(?:[- ]breaking)?|soaring|skyrocket\w+|'
    r'dominat\w+|leading\s+the\s+way|best[- ]in[- ]class|'
    r'unparalleled|world[- ]class|cutting[- ]edge|'
    r'creating\s+(?:substantial|significant|enormous)\s+opportunit\w+)\b',
    re.IGNORECASE
)


def _voice_cascade_eval(you_pct, we_pct, imp_count, spec_pct, promo_pct):
    """Simulate the voice-rule cascade and return per-rule fire state.

    Returns a list of (rule_label, fires: bool, margin_to_threshold: float)
    tuples in cascade order. `margin_to_threshold` is the absolute distance
    of the deciding feature from its threshold, signed so a positive value
    means the threshold was crossed (rule would fire by that margin) and
    a negative value means the threshold was not crossed (rule missed by
    that margin).

    Used by detect_voice to identify the winning rule, the runner-up
    class (next rule in cascade that would fire if the winner did not),
    and the winning rule's margin (how close the threshold call was).

    Unit convention: percentage-points. `imperative_count` multiplied by
    `IMP_TO_PCT` to make 1-count distances comparable to ~5-pct-point
    distances.
    """
    IMP_TO_PCT = 5

    # Rule 1: prescriptive via you>=15 AND imp>=2
    r1_fires = you_pct >= 15 and imp_count >= 2
    r1_margin = min(
        you_pct - 15,
        IMP_TO_PCT * (imp_count - 2),
    )

    # Rule 2: prescriptive via you>=15 OR (imp>=3 AND you>=5)
    r2a = you_pct >= 15
    r2b = imp_count >= 3 and you_pct >= 5
    r2_fires = r2a or r2b
    r2_margin = max(
        you_pct - 15,  # clause a
        min(IMP_TO_PCT * (imp_count - 3), you_pct - 5),  # clause b
    )

    # Rule 3: promotional via we>=20
    r3_fires = we_pct >= 20
    r3_margin = we_pct - 20

    # Rule 4: promotional via promo>=20 AND you<5 AND we<5
    r4_fires = promo_pct >= 20 and you_pct < 5 and we_pct < 5
    r4_margin = min(
        promo_pct - 20,
        4 - you_pct,
        4 - we_pct,
    )

    # Rule 5: descriptive via spec>=20
    r5_fires = spec_pct >= 20
    r5_margin = spec_pct - 20

    # Rule 6: advisory via you>=5
    r6_fires = you_pct >= 5
    r6_margin = you_pct - 5

    # Rule 7: analytical, residual. Fires if all above fail.
    # Margin for analytical is "how far from any above-rule firing."
    # Computed as max(-margin of nearest above-rule), so positive means
    # every above-rule missed by at least that much.
    r7_margin = -max(
        r1_margin if not r1_fires else -999,
        r2_margin if not r2_fires else -999,
        r3_margin if not r3_fires else -999,
        r4_margin if not r4_fires else -999,
        r5_margin if not r5_fires else -999,
        r6_margin if not r6_fires else -999,
    )
    # If any above-rule fires, analytical doesn't; margin is
    # "how negative" which represents distance below activation.
    any_above_fires = (
        r1_fires or r2_fires or r3_fires or r4_fires or r5_fires or r6_fires
    )
    r7_fires = not any_above_fires

    return [
        ("prescriptive", r1_fires, float(r1_margin)),
        ("prescriptive", r2_fires, float(r2_margin)),
        ("promotional", r3_fires, float(r3_margin)),
        ("promotional", r4_fires, float(r4_margin)),
        ("descriptive", r5_fires, float(r5_margin)),
        ("advisory", r6_fires, float(r6_margin)),
        ("analytical", r7_fires, float(r7_margin)),
    ]


# Borderline threshold: winning rule's margin below this value means
# the classification could flip with a small feature change (~2
# percentage points, or ~half an imperative sentence). Reader-aid
# relevant because a borderline prescriptive/advisory call affects how
# the reader reads the rest of the document.
_VOICE_BORDERLINE_MARGIN = 2.0


def detect_voice(text):
    """Detect the document's voice: who it positions as the agent.

    Voice types:
      prescriptive - tells you what to do (you-directed + directives)
      promotional  - asserts value of we/our product or org
      descriptive  - reference catalog, structured data, factual listing
      advisory     - some reader-directed guidance, not dominant
      analytical   - third-person examination of a topic

    Construct extension (added 2026-04-20 Phase B voice construct):
      margin_to_threshold: the BEST margin across firing rules for the
        winning class. Large positive = winner's thresholds decisively
        crossed; near zero = winner barely activated. Units are
        percentage-points (with imp_count scaled by IMP_TO_PCT=5).
      runner_up: next class in the cascade (different from winner)
        whose rule would be evaluated if the winner's rule had not
        fired.
      runner_up_margin: BEST margin across the runner-up class's rules.
        Negative means that class missed by that much; positive means
        it would fire too (preempted by cascade).
      confidence: "high" | "borderline" | "insufficient". Borderline
        when margin_to_threshold < _VOICE_BORDERLINE_MARGIN (winner
        barely crossed) OR runner_up_margin > -_VOICE_BORDERLINE_MARGIN
        (runner-up is nearly activating). Reader-aid consumers should
        weigh both classes when borderline.

    The lower-bound detection posture used for coverage / epistemic /
    claims does not apply to voice (there is no "not_detected" state;
    every document is classified). The classification-confidence
    construct is the analogous posture for classification signals:
    expose the margin so the reader can tell decisive calls from
    close calls.

    Insufficient-input return shape matches the happy-path schema so
    downstream consumers (templates, MCP payloads, tests) do not need
    a separate handling branch.
    """
    raw = split_sentences(text)
    sentences = [s for _, s, _ in raw]
    n = len(sentences)
    if n == 0:
        return {
            "voice": "insufficient",
            "you_pct": 0, "we_pct": 0,
            "imperative_count": 0, "spec_pct": 0,
            "total_sentences": 0,
            "margin_to_threshold": 0.0,
            "runner_up": None,
            "runner_up_margin": None,
            "confidence": "insufficient",
        }

    you_count = sum(1 for s in sentences if _YOU_RE.search(s))
    we_count = sum(1 for s in sentences if _WE_RE.search(s))
    imp_count = sum(1 for s in sentences if _IMPERATIVE_RE.search(s.strip()))
    spec_count = sum(1 for s in sentences if _SPEC_RE.search(s))
    promo_count = sum(1 for s in sentences if _PROMO_RE.search(s))
    you_pct = round(you_count / n * 100)
    we_pct = round(we_count / n * 100)
    spec_pct = round(spec_count / n * 100)
    promo_pct = round(promo_count / n * 100)

    # Cascade evaluation: for each rule in order, record whether it
    # fires and the margin to its threshold. Winner is the class of the
    # first rule that fires; winner margin is the BEST margin across
    # all rules of that same class (since multiple rules may provide
    # redundant activation). Runner-up is the next class in cascade.
    cascade = _voice_cascade_eval(
        you_pct, we_pct, imp_count, spec_pct, promo_pct,
    )

    # Winner class: class of the first rule that fires.
    winner_index = None
    for i, (_cls, fires, _margin) in enumerate(cascade):
        if fires:
            winner_index = i
            break
    if winner_index is None:
        voice = "analytical"
    else:
        voice = cascade[winner_index][0]

    # Winner margin: best margin across all firing rules of the winning
    # class. A prescriptive document activated by rule 1 tightly AND by
    # rule 2 clearly is robustly prescriptive; the clear-rule margin
    # should dominate. Max of firing-rule margins captures that.
    winning_rule_margins = [
        m for cls, fires, m in cascade if cls == voice and fires
    ]
    if winning_rule_margins:
        winner_margin = max(winning_rule_margins)
    else:
        # Residual analytical: use its own margin.
        winner_margin = cascade[-1][2] if cascade else 0.0

    # Runner-up: next cascade class different from winner. For that
    # class, take the best (max) margin across its rules to capture
    # how close that class was to activating (or how decisively it missed).
    # A positive runner_up_margin would mean that class's rule fires
    # under the current features, which can happen when a later class
    # has a lower-threshold rule satisfied but was blocked by the winner
    # claiming an earlier cascade slot.
    runner_up = None
    runner_up_margin = None
    for j in range(
        (winner_index or 0) + 1, len(cascade)
    ):
        cand_cls = cascade[j][0]
        if cand_cls == voice:
            continue
        # Found the next class in cascade. Take best margin across its rules.
        same_class_margins = [
            m for cls, _f, m in cascade if cls == cand_cls
        ]
        runner_up = cand_cls
        runner_up_margin = round(max(same_class_margins), 2)
        break

    # Confidence: borderline when a small feature change could flip the
    # classification. Two conditions:
    #   (a) winner margin is small (winner barely crossed its threshold)
    #   (b) runner-up margin is close to 0 (runner-up nearly activated)
    margin_to_threshold = round(winner_margin, 2)
    confidence = "high"
    if margin_to_threshold < _VOICE_BORDERLINE_MARGIN:
        confidence = "borderline"
    elif (
        runner_up_margin is not None
        and runner_up_margin > -_VOICE_BORDERLINE_MARGIN
    ):
        confidence = "borderline"

    return {
        "voice": voice,
        "you_pct": you_pct,
        "we_pct": we_pct,
        "imperative_count": imp_count,
        "spec_pct": spec_pct,
        "total_sentences": n,
        "margin_to_threshold": margin_to_threshold,
        "runner_up": runner_up,
        "runner_up_margin": runner_up_margin,
        "confidence": confidence,
    }


# ================================================================
# Epistemic basis detection
# ================================================================

# How does the document know what it claims?
#
# Two-pass design:
#   1. Strong source markers (always count): "according to", "source",
#      "study", "research", "evidence", "peer-reviewed", "journal", etc.
#   2. Entity attribution (verb pattern): "X reported", "X published",
#      "X announced" - requires X to be a real entity, not a pronoun
#      or generic word like "the company". This prevents false positives
#      where "The company reported revenue" is treated as sourced just
#      because it contains "reported".
_SOURCE_RE = re.compile(
    r'\b(according\s+to|sources?|cited?|stud(?:y|ies)|research(?:ers?)?|'
    r'evidence|peer.reviewed|journals?|surveys?|surveyed|findings?|'
    r'data\s+(?:from|shows?|suggests?)|'
    r'analysis\s+(?:by|from)|estimates?\s+(?:by|from)|'
    r'(?:clinical\s+)?trial(?:s)?|meta.analys[ie]s|systematic\s+review|'
    # Research-noun + reporting verb (always sourced regardless of entity)
    r'(?:stud(?:y|ies)|research|surveys?|reports?|papers?)\s+'
    r'(?:show|shows|showed|suggest|suggests|suggested|'
    r'find|finds|found|conclude|concluded|reveal|reveals|revealed))\b',
    re.IGNORECASE
)

# Entity-attributed reporting verbs.
# "Apple reported", "Novo Nordisk announced", "NIH disclosed" -> sourced
# "The company reported", "We reported", "It reported" -> NOT sourced
_ENTITY_VERBS = (
    r'(?:reported|reports|announced|announces|'
    r'published|publishes|stated|states|disclosed|discloses|'
    r'confirmed|confirms|filed|files)'
)
# Capture: capitalized word(s), optionally followed by punctuation,
# immediately followed by an entity verb. Allows "Apple Inc. reported"
# and "The Fed announced" (entity-head detection happens at use site).
_ENTITY_ATTRIB_RE = re.compile(
    r'(?<![\w-])('
    r'[A-Z][a-zA-Z]+'                       # First capitalized word
    r'(?:\.?\s+[A-Z][a-zA-Z]+){0,3}'         # Up to 3 more title-case words
    r')\.?\s+' + _ENTITY_VERBS
)

# Determiners that may precede an entity but are not the entity themselves.
# "The Fed" -> entity is "Fed". "A Tesla report" -> not an attribution at all.
_DETERMINERS = {"The", "A", "An"}

# Capitalized words that are pronouns/generics, NOT real entities.
# These should NOT count as source attributions even when they prefix
# a reporting verb. "The company reported" is self-reference, not source.
_NON_ENTITY_PREFIXES = {
    "This", "That", "These", "Those",
    "We", "Our", "Us", "They", "Their", "Them",
    "It", "Its", "He", "She", "His", "Her", "I", "My",
    "Some", "Many", "All", "Most", "Several", "Each",
    "Every", "Both", "Either", "Neither",
    "Company", "Firm", "Group", "Team", "Department",
    "Organization", "Corporation", "Business",
    "Author", "Authors", "Writer", "Writers",
    "Article", "Document", "Report", "Paper",
    # Sentence-starter conjunctions and adverbs
    "However", "Therefore", "Furthermore", "Moreover", "Additionally",
    "Recently", "Currently", "Previously", "Historically",
    "First", "Second", "Third", "Finally",
}

_NUMERIC_RE = re.compile(
    r'\d+(?:\.\d+)?(?:\s*%|\s*[xX]|\s*billion|\s*million|\s*trillion)',
    re.IGNORECASE
)


_NON_ENTITY_LOWER = {p.lower() for p in _NON_ENTITY_PREFIXES}


def _is_entity_attributed(sentence):
    """Check if sentence contains entity-attributed reporting.

    Matches "Apple reported $X", "Novo Nordisk announced Y", etc.
    Excludes self-references like "The company reported", "We disclosed".

    Determiners ("The", "A", "An") at the start of the entity phrase are
    skipped, so "The Fed announced" treats "Fed" as the entity head.
    """
    for m in _ENTITY_ATTRIB_RE.finditer(sentence):
        words = m.group(1).split()
        # Strip leading determiners to find the real entity head
        while words and words[0] in _DETERMINERS:
            words = words[1:]
        if not words:
            continue
        head = words[0].rstrip('.')
        # Reject pronouns and generic words. The lower-cased lookup
        # subsumes the case-sensitive check, since _NON_ENTITY_LOWER
        # contains every prefix in _NON_ENTITY_PREFIXES.
        if head.lower() in _NON_ENTITY_LOWER:
            continue
        # Real entity attribution found
        return True
    return False


def _is_sourced(sentence):
    """Check if a sentence has any form of source attribution.

    Combines two signals:
      1. Strong source markers in the sentence ("according to", "study",
         "research", "evidence", "trial", etc.)
      2. Entity attribution: a real entity name preceding a reporting
         verb ("Apple reported", "NIH announced").
    """
    if _SOURCE_RE.search(sentence):
        return True
    return _is_entity_attributed(sentence)


# Candidate-miss attribution patterns for epistemic sourcing. These fire on
# attribution styles the primary _SOURCE_RE + _is_entity_attributed pipeline
# does not recognize: academic citation formats (bracketed, parenthetical,
# numbered references), scholarly passive constructions ("observers raise,"
# "analysts argue," "some have argued"), and inline data-source references
# ("per the Q3 filing," "as reported in").
#
# Diagnostic motivating this: arxiv academic papers in the validation corpus
# (a08_arxiv_gpt3.txt, a09_arxiv_foundation_models.txt) register
# sourced_pct = 10% and 14% respectively, when a reader would plainly
# identify them as heavily-sourced. The primary regex misses the
# attribution styles those documents use.
#
# Conservative by design. False positives on candidate patterns are
# acceptable because each candidate is surfaced with an explicit caveat
# naming the lower-bound detection posture, not as a detection.
EPISTEMIC_CANDIDATE_ATTRIBUTION = re.compile(
    # Bracketed citation: [Smith et al., 2023], [12], [Author 2020]
    r'\[(?:[A-Z][a-zA-Z]+(?:\s+(?:et\s+al\.?|and\s+[A-Z][a-zA-Z]+))?'
    r'(?:,?\s+\d{4})?|\d{1,3})\]'
    # Parenthetical citation: (Smith et al., 2023), (Jones 2022)
    r'|\((?:[A-Z][a-zA-Z]+(?:\s+(?:et\s+al\.?|and\s+[A-Z][a-zA-Z]+))?'
    r'[,;]?\s+\d{4}[a-z]?)\)'
    # Move E (2026-04-27): agency-style parenthetical citations.
    # Common in finance, policy, and regulatory writing. CONSTRUCT_VALIDITY_
    # AUDIT_v1.md §2 named this gap; balanced_macroeconomic_outlook fixture
    # provides the worked example. Conservative: each pattern requires a
    # structural cue (acronym followed by delimiter, acronym near a year,
    # or capitalized two-word name near a year) so bare abbreviation-
    # definition parens like (LLM), (FDA), (IPCC) and lowercase parens
    # like (in 2019 currency) are skipped.
    #
    # The (?-i:...) inline scope disables the outer re.IGNORECASE so
    # [A-Z] is genuinely uppercase. Without this, every lowercase
    # parenthetical fragment matches.
    # E.1 acronym followed by delimiter + content: (BEA, June 2026), (FDIC, OCC)
    r'|(?-i:\([A-Z]{2,}\b\s*[,;:]\s*[^)]{1,250}\))'
    # E.2 acronym near a year inside parens: (BEA advance estimate, 2026-07-29)
    r'|(?-i:\([A-Z]{2,}\b[^)]{0,250}?\b\d{4}\b[^)]{0,100}?\))'
    # E.3 capitalized two-word name near a year: (Bloomberg survey, July 2026),
    # (Census BTOS, June 2026). Two consecutive words required to
    # discriminate against bare (June 2026) date markers.
    r'|(?-i:\([A-Z][a-zA-Z]+\s+[A-Za-z][a-zA-Z]+[^)]{0,250}?\b\d{4}\b[^)]{0,100}?\))'
    # Scholarly passive attribution
    r'|\b(?:observers\s+(?:raise|note|have\s+noted|argue)|'
    r'analysts\s+(?:argue|note|have\s+argued|observe)|'
    r'researchers\s+(?:have\s+(?:found|shown|argued|noted)|find)|'
    r'scholars\s+(?:have\s+(?:argued|noted)|argue|note)|'
    r'commentators\s+(?:have\s+(?:argued|noted|suggested))|'
    r'critics\s+(?:have\s+(?:argued|noted))|'
    r'some\s+have\s+(?:argued|suggested|noted))\b'
    # Data-source references
    r'|\bper\s+(?:the|a|this|that)\s+(?:filing|report|study|paper|'
    r'article|findings|analysis|document|source|dataset|survey|'
    r'statement|announcement)\b'
    r'|\bas\s+reported\s+(?:in|by)\b'
    r'|\bpublished\s+(?:in|by|at)\b'
    # Section/reference cross-references (common in papers)
    r'|\b(?:see|cf\.?)\s+(?:Section|Table|Figure|Appendix|'
    r'reference\s*\[?\s*\d+)\b',
    re.IGNORECASE
)


def detect_epistemic_basis(text, include_candidates=False):
    """Detect how the document supports its claims.

    Returns the ratio of source-attributed vs unsupported numeric claims.
    A document with 8 specific numbers and 0 source attributions has a
    fundamentally different epistemic basis than one where every number
    traces to a named source.

    Optional candidate-miss extension:
      include_candidates=True: the return dict gains a
        `candidate_attribution_sentences` list, one entry per sentence
        where EPISTEMIC_CANDIDATE_ATTRIBUTION fires but the primary
        _is_sourced pipeline did not. These are reader-inspectable
        candidates for under-detection. Each entry carries an explicit
        caveat and a sample of the candidate pattern that matched.
        Deduplicated by sentence; capped at 20 per document.

    Lower-bound posture: with include_candidates=True, callers can
    report both the primary sourced_pct AND a candidate_miss_count so
    the surfaced signal is "primary detector found N, candidate
    patterns surface M more the reader should inspect."
    """
    raw = split_sentences(text)
    sentences = [s for _, s, _ in raw]
    n = len(sentences)
    if n == 0:
        result = {"sourced": 0, "sourced_pct": 0, "numeric_sentences": 0,
                  "unsupported_numeric": 0, "total_sentences": 0}
        if include_candidates:
            result["candidate_attribution_sentences"] = []
            result["candidate_attribution_count"] = 0
        return result

    # Cache the per-sentence checks so each sentence is evaluated once.
    # Without this, _is_sourced runs twice (sourced count + unsupported
    # count) and the regex/entity work is duplicated.
    sourced_flags = [_is_sourced(s) for s in sentences]
    numeric_flags = [bool(_NUMERIC_RE.search(s)) for s in sentences]

    sourced = sum(sourced_flags)
    numeric = sum(numeric_flags)
    unsupported = sum(
        1 for s_flag, n_flag in zip(sourced_flags, numeric_flags)
        if n_flag and not s_flag
    )

    result = {
        "sourced": sourced,
        "sourced_pct": round(sourced / n * 100),
        "numeric_sentences": numeric,
        "unsupported_numeric": unsupported,
        "total_sentences": n,
    }

    if include_candidates:
        # Surface sentences where the candidate regex fires but the
        # primary _is_sourced did not. These are under-detection candidates:
        # sentences that look attributed to a reader but that the primary
        # pipeline flagged as unsourced.
        candidates = []
        for idx, (is_primary_sourced, sent) in enumerate(
            zip(sourced_flags, sentences)
        ):
            if is_primary_sourced:
                continue
            m = EPISTEMIC_CANDIDATE_ATTRIBUTION.search(sent)
            if m is None:
                continue
            # R3 refinement: exclude sentences whose only bracket-
            # citation match is a leading [N] (footnote body). These
            # are not citing sentences; they are the footnote content
            # itself. On PG-essay-style corpora, 5 of 32 candidate-
            # attribution rows were footnote bodies. Sentences starting
            # with [N] that contain another bracket citation later in
            # the sentence are kept.
            stripped = sent.lstrip()
            prefix_match = re.match(r'\[\d{1,3}\]', stripped)
            if prefix_match:
                remainder = stripped[prefix_match.end():]
                has_other_bracket = bool(
                    re.search(r'\[\d{1,3}\]', remainder)
                )
                if not has_other_bracket:
                    # Match was only the leading [N]; likely footnote
                    # body. Check whether a non-[N] pattern also
                    # matches later in the sentence (scholarly passive,
                    # per-the-source, etc.); if not, skip.
                    non_bracket_match = (
                        EPISTEMIC_CANDIDATE_ATTRIBUTION.search(remainder)
                    )
                    if non_bracket_match is None:
                        continue
                    # Re-point m to the downstream non-bracket match so
                    # the reported marker reflects what was actually
                    # citing-shaped.
                    m = non_bracket_match
            marker = re.sub(r'\s+', ' ', m.group(0).strip())
            preview = sent if len(sent) <= 120 else sent[:117] + "..."
            candidates.append({
                "sentence_index": idx,
                "sentence_preview": preview,
                "candidate_marker": marker,
                "caveat": (
                    "Candidate attribution pattern fired; primary "
                    "sourcing detector did not. Reader judges whether "
                    "this sentence carries source attribution."
                ),
            })
            if len(candidates) >= 20:
                break
        result["candidate_attribution_sentences"] = candidates
        result["candidate_attribution_count"] = len(candidates)

    return result


# ================================================================
# Framing portrait
# ================================================================

_GAP_MEANINGS = {
    "causes": "no explanation-of-why markers",
    "risks": "no downside-scenario markers",
    "stakeholders": "no affected-party markers",
    "trends": "no directional-context markers",
    "uncertainty": "no uncertainty-acknowledgment markers",
}

# Positive-noun forms for "without detected discussion of X" constructions.
# Used in hedged portrait sentences that acknowledge the detector saw no
# markers for a category; the positive-noun form reads better than the
# category id ("without detected discussion of downside scenarios" vs
# "without detected discussion of risks").
_GAP_POSITIVES = {
    "causes": "why things happen",
    "risks": "downside scenarios",
    "stakeholders": "who is affected",
    "trends": "directional context",
    "uncertainty": "what is unknown",
}


def framing_portrait(coverage, temporal, voice, epistemic, claim_stats,
                     verification=None, grounding=None):
    """Synthesize all framing signals into a 2-4 sentence portrait.

    This is the output that makes the invisible visible. It describes
    what the document does to the reader's perception, not just what
    topics it covers. The voice type determines HOW to interpret the
    coverage gaps: the same 0/5 score means fundamentally different
    things for a reference document, a trading playbook, and a pitch.

    When verification results are provided, the portrait adds the
    key synthesis: how many claims are grounded, and how the frame
    obscures which claims are real.

    When grounding decomposition is provided, the portrait notes
    significant projection (content not in source). This is the
    highest-signal structural finding when source is available.
    """
    parts = []
    n = voice.get("total_sentences", 0)
    if n == 0:
        return "Insufficient text for framing analysis."

    v = voice["voice"]
    missing = coverage.get("missing", [])
    numeric = epistemic.get("numeric_sentences", 0)
    unsupported = epistemic.get("unsupported_numeric", 0)
    sourced = epistemic.get("sourced", 0)
    sourced_pct = epistemic.get("sourced_pct", 0)
    total_claims = claim_stats.get("total_claims", 0)
    unhedged = claim_stats.get("unhedged_count", 0)

    # ── 1. What kind of document is this? ──
    if v == "descriptive":
        parts.append(
            f"Reference document cataloging factual data "
            f"({voice['spec_pct']}% structured specifications)."
        )
    elif v == "prescriptive":
        imp = voice['imperative_count']
        parts.append(
            f"Prescriptive document ({voice['you_pct']}% addressed to "
            f"the reader, {imp} direct {'instruction' if imp == 1 else 'instructions'})."
        )
    elif v == "promotional":
        we = voice.get("we_pct", 0) or 0
        if we >= 20:
            # Classic first-person promotional: "we" / "our"
            parts.append(
                f"Promotional document ({we}% first-person "
                f"assertions about a product or organization)."
            )
        else:
            # Third-person promotional: no we/our, but
            # saturated with positive superlatives.
            parts.append(
                "Promotional document presenting the topic "
                "through consistently positive framing and "
                "superlative language."
            )
    elif v == "advisory":
        parts.append(
            f"Advisory document with some direct guidance "
            f"({voice['you_pct']}% addressed to the reader)."
        )
    else:
        # Analytical is the cascade residual: no prescriptive, promotional,
        # descriptive, or advisory markers fired. Report this as
        # evidence-absence rather than existential ("Analytical document
        # examining..."), matching the same discipline applied to coverage.
        parts.append(
            "No directive, promotional, or descriptive voice markers "
            "detected; narration is third-person by default (residual "
            "analytical classification)."
        )

    # ── 1b. Verification context (kept for synthesis, not for leading) ──
    # The trust banner and AI interpretation handle the count.
    # The portrait notes contradictions (important) but does not restate counts.
    _verification_led = False
    if verification:
        v_total = verification.get("total", 0)
        v_verified = verification.get("verified", 0)
        v_contra = verification.get("contradicted", 0)
        if v_contra > 0:
            _verification_led = True
            parts.append(
                f"{v_contra} claim{'s' if v_contra != 1 else ''} "
                f"contradicted by authoritative sources."
            )

    # ── 1c. Grounding context (how much is source-derived vs projected) ──
    # The grounding card shows the detailed bar and prohibition.
    # The portrait's job is to frame what this means for the reader,
    # not restate the same percentages.
    if grounding and grounding.get("n_classified", 0) > 0:
        p_prop = grounding["proportions"].get("P", 0)
        g_prop = grounding["proportions"].get("G", 0)
        p_pct = round(p_prop * 100)
        g_pct = round(g_prop * 100)
        if p_pct >= 25:
            parts.append(
                "Significant content originates outside the provided "
                "source. See the grounding breakdown below."
            )
        elif p_pct >= 10:
            parts.append(
                "Some content extends beyond the provided source material."
            )
        elif p_pct == 0 and g_pct >= 50:
            parts.append(
                "Content stays close to the provided source "
                f"({g_pct}% directly derived)."
            )

    # ── 2. How does it support its claims? ──
    if numeric > 0 and unsupported == numeric and sourced == 0:
        confidence_note = ""
        if total_claims >= 5 and unhedged / total_claims > 0.8:
            confidence_note = (
                f", {unhedged} of {total_claims} stated as definitive fact"
            )
        if v == "descriptive":
            parts.append(
                f"Presents {total_claims} numerical claims as established "
                f"knowledge with no source-attribution markers detected."
            )
        else:
            parts.append(
                f"{numeric} specific numerical "
                f"{'claim' if numeric == 1 else 'claims'} with no source "
                f"attribution{confidence_note}."
            )
    elif numeric > 0 and sourced > 0:
        if sourced_pct >= 70:
            parts.append(
                f"{sourced_pct}% of claims attributed to sources. "
                f"Evidence-based structure."
            )
        else:
            parts.append(
                f"{sourced} of {epistemic['total_sentences']} sentences "
                f"match source-attribution patterns, but {unsupported} "
                f"numerical claims do not."
            )
    elif total_claims >= 5 and unhedged / total_claims > 0.8:
        parts.append(
            f"{unhedged} of {total_claims} claims stated as fact "
            f"with no qualifying language detected."
        )

    # ── 3. What is invisible? (contextualized by voice type) ──
    # Distinguish "absent" (never mentioned) from "dismissed" (mentioned
    # to deny). A document that says "no risks" 4 times is actively hiding
    # risk analysis, not just omitting it. Surface this for the user.
    cats = coverage.get("categories", {})
    gap_notes = []
    for m in missing:
        dismissed = cats.get(m, {}).get("dismissed", 0)
        if dismissed >= 2 and m in _GAP_MEANINGS:
            gap_notes.append(f"{m} language explicitly dismissed")
        elif m in _GAP_MEANINGS:
            gap_notes.append(_GAP_MEANINGS[m])
    covered_count = coverage.get("coverage_count", 0)

    if not missing:
        # Full coverage: note what's strong
        densities = {k: cv["density_per_1kw"] for k, cv in cats.items()
                     if cv.get("covered")}
        if len(densities) >= 2:
            max_cat = max(densities, key=densities.get)
            min_cat = min(densities, key=densities.get)
            if densities[max_cat] > 2.0 and densities[min_cat] > 0 and \
               densities[max_cat] > 3 * densities[min_cat]:
                parts.append(
                    f"All five analytical dimensions are present, "
                    f"with emphasis on {max_cat} "
                    f"({densities[max_cat]} per 1K words) "
                    f"over {min_cat} ({densities[min_cat]} per 1K words)."
                )
            else:
                parts.append(
                    "Addresses all five analytical dimensions "
                    "(causes, risks, stakeholders, trends, uncertainty)."
                )
        else:
            parts.append(
                "Addresses all five analytical dimensions."
            )
    elif v == "descriptive" and len(missing) >= 3:
        parts.append(
            f"Comprehensive on factual data. Low structural coverage "
            f"of analytical dimensions: {', '.join(gap_notes)}."
        )
    elif v == "prescriptive" and len(missing) >= 2:
        pos_notes = [_GAP_POSITIVES.get(m, m) for m in missing if m in _GAP_POSITIVES]
        parts.append(
            f"Directs action without detected discussion of "
            f"{', '.join(pos_notes)}."
        )
    elif v == "promotional" and len(missing) >= 2:
        pos_notes = [_GAP_POSITIVES.get(m, m) for m in missing if m in _GAP_POSITIVES]
        parts.append(
            f"Asserts value without detected discussion of "
            f"{', '.join(pos_notes)}."
        )
    elif len(missing) >= 3:
        parts.append(
            f"Low structural coverage of {len(missing)} of 5 "
            f"analytical dimensions: {', '.join(gap_notes)}."
        )
    elif len(missing) <= 2 and covered_count >= 3:
        # High coverage: acknowledge the breadth first, then
        # note the gap. A document covering 4 of 5 perspectives
        # deserves recognition, not just a complaint about the
        # one it missed. This is the difference between a
        # critique tool and a perspective tool.
        covered_names = [
            c for c in ["causes", "risks", "stakeholders", "trends", "uncertainty"]
            if c not in missing
        ]
        parts.append(
            f"Covers {covered_count} of 5 analytical perspectives "
            f"({', '.join(covered_names)}). "
            f"Low structural coverage of {' or '.join(missing)}: "
            f"{', '.join(gap_notes)}."
        )
    elif missing and gap_notes:
        parts.append(
            f"Low structural coverage of {' or '.join(missing)}: "
            f"{', '.join(gap_notes)}."
        )

    # ── 4. What this means for the reader ──
    if not missing and v == "analytical":
        if sourced_pct >= 70:
            parts.append(
                "The reader is positioned to evaluate evidence "
                "and form their own conclusions."
            )
        elif unsupported > 0:
            parts.append(
                "Structurally comprehensive, but no source-attribution "
                "markers were detected on the numerical claims. Verify "
                "before acting."
            )
    elif v == "descriptive" and len(missing) >= 3:
        parts.append(
            "Useful as a factual reference; insufficient for "
            "decisions that require risk or impact analysis."
        )
    elif v == "prescriptive" and unsupported > 2 and len(missing) >= 2:
        parts.append(
            "The reader is positioned as an executor of instructions "
            "with no basis to evaluate the claims behind them."
        )
    elif v == "promotional" and unsupported > 2:
        parts.append(
            "The reader is positioned as a buyer, "
            "not an evaluator of evidence."
        )
    elif v == "analytical" and sourced_pct >= 70 and len(missing) <= 1:
        parts.append(
            "The reader is positioned to evaluate evidence "
            "and form their own conclusions."
        )
    elif len(missing) >= 3:
        parts.append(
            "Narrow detected coverage; dimensions without markers "
            "may still be present in the document but were not "
            "structurally flagged."
        )

    # ── 5. Verification synthesis (frame + verification together) ──
    if verification and _verification_led:
        v_unverif = verification.get("unverifiable", 0)
        if total_claims >= 5 and unhedged / total_claims > 0.7 \
           and v_unverif > 0:
            parts.append(
                "All claims are presented with identical confidence. "
                "The frame does not distinguish verified from "
                "unverified data."
            )

    return " ".join(parts)


# ================================================================
# framing_summary
# ================================================================

def framing_portrait_natural(coverage, temporal, voice, epistemic, claim_stats,
                              verification=None, grounding=None):
    """Natural-language synthesis of the framing signals.

    Parallel to `framing_portrait` (the clinical version) but written
    in professional-but-readable prose for the default UI render. The
    cascade-aware discipline is preserved in plain words: where the
    clinical version emits "residual analytical classification", the
    natural version emits "what's left by elimination rather than what's
    positively detected".

    Both portraits are generated on every request. The template
    renders natural by default and exposes clinical in an expandable
    "methodology detail" block so a reviewer can see the full
    cascade-aware wording one click away. The MCP / JSON API returns
    both fields so agents can pick the appropriate register.

    Any change to a clinical part should be mirrored here with the
    same content scope. The two versions must describe the same
    measurements; only the register differs. Divergence between the two
    surfaces would be a defect; the clinical version encodes the same
    cascade-classifier vocabulary as the prose version.
    """
    parts = []
    n = voice.get("total_sentences", 0)
    if n == 0:
        return "Insufficient text for framing analysis."

    v = voice["voice"]
    missing = coverage.get("missing", [])
    numeric = epistemic.get("numeric_sentences", 0)
    unsupported = epistemic.get("unsupported_numeric", 0)
    sourced = epistemic.get("sourced", 0)
    sourced_pct = epistemic.get("sourced_pct", 0)
    total_claims = claim_stats.get("total_claims", 0)
    unhedged = claim_stats.get("unhedged_count", 0)

    # ── 1. What kind of document is this? (natural voice) ──
    if v == "descriptive":
        parts.append(
            f"Reads as a reference catalog of factual data "
            f"({voice['spec_pct']}% structured specifications)."
        )
    elif v == "prescriptive":
        imp = voice['imperative_count']
        parts.append(
            f"Reads as a prescriptive document: {voice['you_pct']}% "
            f"addressed to the reader, {imp} direct "
            f"{'instruction' if imp == 1 else 'instructions'}."
        )
    elif v == "promotional":
        we = voice.get("we_pct", 0) or 0
        if we >= 20:
            parts.append(
                f"Reads as a promotional piece: {we}% first-person "
                f"assertions about a product or organization."
            )
        else:
            parts.append(
                "Reads as a promotional piece. No first-person "
                "framing, but consistently positive language and "
                "superlatives throughout."
            )
    elif v == "advisory":
        parts.append(
            f"Reads as an advisory document with some direct guidance "
            f"({voice['you_pct']}% addressed to the reader)."
        )
    else:
        # Cascade-residual analytical. The cascade-aware discipline
        # shifts from "residual classification" terminology to plain
        # words: "what's left by elimination rather than positively
        # detected". Same content, readable register.
        parts.append(
            "Reads as a third-person analytical piece. None of the "
            "directive, promotional, descriptive, or advisory voice "
            "markers fired, so the analytical label here is what's "
            "left by elimination rather than what was positively "
            "detected."
        )

    # ── 1b. Contradictions (if any) ──
    _verification_led = False
    if verification:
        v_contra = verification.get("contradicted", 0)
        if v_contra > 0:
            _verification_led = True
            parts.append(
                f"{v_contra} claim{'s' if v_contra != 1 else ''} "
                f"contradicted by authoritative sources."
            )

    # ── 1c. Grounding context ──
    if grounding and grounding.get("n_classified", 0) > 0:
        p_prop = grounding["proportions"].get("P", 0)
        g_prop = grounding["proportions"].get("G", 0)
        p_pct = round(p_prop * 100)
        g_pct = round(g_prop * 100)
        if p_pct >= 25:
            parts.append(
                "A significant share of the content goes beyond the "
                "provided source. See the grounding breakdown below."
            )
        elif p_pct >= 10:
            parts.append(
                "Some content extends beyond the provided source."
            )
        elif p_pct == 0 and g_pct >= 50:
            parts.append(
                f"Content stays close to the provided source "
                f"({g_pct}% directly derived)."
            )

    # ── 2. How does it support its claims? ──
    if numeric > 0 and unsupported == numeric and sourced == 0:
        confidence_note = ""
        if total_claims >= 5 and unhedged / total_claims > 0.8:
            confidence_note = (
                f", {unhedged} of {total_claims} stated as definitive fact"
            )
        if v == "descriptive":
            parts.append(
                f"The {total_claims} numerical claims are presented as "
                f"established knowledge, with no source-attribution cues "
                f"detected."
            )
        else:
            parts.append(
                f"{numeric} specific numerical "
                f"{'claim' if numeric == 1 else 'claims'} without source "
                f"attribution{confidence_note}."
            )
    elif numeric > 0 and sourced > 0:
        if sourced_pct >= 70:
            parts.append(
                f"{sourced_pct}% of claims carry source attribution: "
                f"an evidence-based structure."
            )
        else:
            parts.append(
                f"{sourced} of {epistemic['total_sentences']} sentences "
                f"carry source attribution; {unsupported} numerical "
                f"claims don't."
            )
    elif total_claims >= 5 and unhedged / total_claims > 0.8:
        parts.append(
            f"{unhedged} of {total_claims} claims are stated as fact "
            f"with no qualifying language."
        )

    # ── 3. What is invisible? ──
    cats = coverage.get("categories", {})
    gap_notes = []
    for m in missing:
        dismissed = cats.get(m, {}).get("dismissed", 0)
        if dismissed >= 2 and m in _GAP_MEANINGS:
            gap_notes.append(f"{m} language is explicitly dismissed")
        elif m in _GAP_MEANINGS:
            gap_notes.append(_GAP_MEANINGS[m])
    covered_count = coverage.get("coverage_count", 0)

    if not missing:
        densities = {k: cv["density_per_1kw"] for k, cv in cats.items()
                     if cv.get("covered")}
        if len(densities) >= 2:
            max_cat = max(densities, key=densities.get)
            min_cat = min(densities, key=densities.get)
            if densities[max_cat] > 2.0 and densities[min_cat] > 0 and \
               densities[max_cat] > 3 * densities[min_cat]:
                parts.append(
                    f"All five analytical perspectives are present, "
                    f"weighted toward {max_cat} "
                    f"({densities[max_cat]} per 1K words) over "
                    f"{min_cat} ({densities[min_cat]} per 1K words)."
                )
            else:
                parts.append(
                    "Addresses all five analytical perspectives "
                    "(causes, risks, stakeholders, trends, uncertainty)."
                )
        else:
            parts.append("Addresses all five analytical perspectives.")
    elif v == "descriptive" and len(missing) >= 3:
        parts.append(
            f"Strong on factual data, light on analytical perspective: "
            f"{', '.join(gap_notes)}."
        )
    elif v == "prescriptive" and len(missing) >= 2:
        pos_notes = [_GAP_POSITIVES.get(m, m) for m in missing if m in _GAP_POSITIVES]
        parts.append(
            f"Directs action without discussing {', '.join(pos_notes)}."
        )
    elif v == "promotional" and len(missing) >= 2:
        pos_notes = [_GAP_POSITIVES.get(m, m) for m in missing if m in _GAP_POSITIVES]
        parts.append(
            f"Asserts value without discussing {', '.join(pos_notes)}."
        )
    elif len(missing) >= 3:
        parts.append(
            f"Light structural coverage across {len(missing)} of 5 "
            f"perspectives: {', '.join(gap_notes)}."
        )
    elif len(missing) <= 2 and covered_count >= 3:
        covered_names = [
            c for c in ["causes", "risks", "stakeholders", "trends", "uncertainty"]
            if c not in missing
        ]
        parts.append(
            f"Addresses {covered_count} of 5 analytical perspectives "
            f"({', '.join(covered_names)}); {' or '.join(missing)} "
            f"{'are' if len(missing) > 1 else 'is'} absent. "
            f"{gap_notes[0][0].upper() + gap_notes[0][1:] if gap_notes else 'No markers detected'}"
            f"{'; ' + '; '.join(gap_notes[1:]) + '.' if len(gap_notes) > 1 else '.'}"
        )
    elif missing and gap_notes:
        parts.append(
            f"{' or '.join(missing)} perspective is absent: "
            f"{', '.join(gap_notes)}."
        )

    # ── 4. What this means for the reader ──
    if not missing and v == "analytical":
        if sourced_pct >= 70:
            parts.append(
                "The reader is positioned to evaluate evidence "
                "and form their own conclusions."
            )
        elif unsupported > 0:
            parts.append(
                "Structurally comprehensive, but the numerical claims "
                "aren't attributed to sources. Verify before acting."
            )
    elif v == "descriptive" and len(missing) >= 3:
        parts.append(
            "Useful as a factual reference; not enough analytical "
            "coverage for decisions that need risk or impact weighing."
        )
    elif v == "prescriptive" and unsupported > 2 and len(missing) >= 2:
        parts.append(
            "The reader is positioned as someone to follow instructions, "
            "with no basis to evaluate the claims behind them."
        )
    elif v == "promotional" and unsupported > 2:
        parts.append(
            "The reader is positioned as a buyer, not an evaluator."
        )
    elif v == "analytical" and sourced_pct >= 70 and len(missing) <= 1:
        parts.append(
            "The reader is positioned to evaluate evidence "
            "and form their own conclusions."
        )
    elif len(missing) >= 3:
        parts.append(
            "Narrow structural coverage; dimensions without markers "
            "may still be present but aren't structurally flagged."
        )

    # ── 5. Verification synthesis ──
    if verification and _verification_led:
        v_unverif = verification.get("unverifiable", 0)
        if total_claims >= 5 and unhedged / total_claims > 0.7 \
           and v_unverif > 0:
            parts.append(
                "Every claim is stated with the same confidence; the "
                "frame doesn't distinguish verified from unverified."
            )

    return " ".join(parts)


def framing_summary(coverage, temporal, claim_stats):
    """Generate a descriptive framing summary. No evaluative labels.

    Combines category coverage, temporal orientation, and existing
    claim_analysis signals into a human-readable summary.
    """
    parts = []

    # Coverage
    if not coverage["covered"]:
        parts.append(
            f"No structural markers detected for any of the five "
            f"analytical dimensions (causes, risks, stakeholders, "
            f"trends, uncertainty)."
        )
    elif coverage["missing"]:
        parts.append(
            f"Covers: {', '.join(coverage['covered'])}. "
            f"Low structural coverage: {', '.join(coverage['missing'])}."
        )
    else:
        parts.append(
            "Covers all five analytical dimensions "
            "(causes, risks, stakeholders, trends, uncertainty)."
        )

    # Density imbalance (if one covered category dominates another)
    cats = coverage["categories"]
    densities = {k: cv["density_per_1kw"] for k, cv in cats.items() if cv["covered"]}
    if len(densities) >= 2:
        max_cat = max(densities, key=densities.get)
        min_cat = min(densities, key=densities.get)
        # Require the dominant category to have meaningful density (>2.0/1Kw)
        # and be 3x+ the weakest. Avoids flagging tiny differences.
        if densities[max_cat] > 2.0 and densities[min_cat] > 0 and \
           densities[max_cat] > 3 * densities[min_cat]:
            parts.append(
                f"Emphasis skew: {max_cat} ({densities[max_cat]} per 1K words) "
                f"vs {min_cat} ({densities[min_cat]} per 1K words)."
            )

    # Temporal.
    # Respect the construct-honest `balanced` flag set by
    # temporal_orientation: when no tense reaches the shipped 50% gate
    # and the dominant margin is < 10 points, the "dominant" label is
    # not a time-anchor and summarizing it as such misleads downstream
    # consumers. The main template at templates/results.html handles
    # this correctly; summary was the one legacy surface that did not.
    # Avoids the "framing_summary temporal leak": when no tense
    # dominates, name the balance rather than synthesizing a
    # dominant-tense narrative.
    if temporal.get("balanced"):
        parts.append(
            f"Temporal orientation: balanced (no tense dominates; "
            f"{temporal.get('dominant_margin', 0)}-point margin between "
            f"top two tenses)."
        )
    else:
        parts.append(f"Temporal orientation: {temporal['dominant']} "
                     f"({temporal[temporal['dominant'] + '_pct']}%).")

    # Confidence (from claim_analysis)
    total = claim_stats.get("total_claims", 0)
    unhedged = claim_stats.get("unhedged_count", 0)
    if total >= 5 and unhedged / total > 0.8:
        parts.append(
            f"{unhedged} of {total} claims stated as definitive fact "
            "with no qualifying language detected."
        )

    return " ".join(parts)


# ================================================================
# framing_headline
# ================================================================

def framing_headline(coverage, temporal, voice, epistemic, claim_stats,
                     verification=None):
    """Return the single most important framing finding as a one-liner.

    Priority: framing-first, verification as suffix. The trust
    banner already shows the verification summary; the headline
    is the one place that surfaces the STRUCTURAL finding. When
    both a framing signal and a contradiction exist, the headline
    leads with the framing signal and appends the contradiction.
    """
    missing = coverage.get("missing", [])
    unsupported = epistemic.get("unsupported_numeric", 0)
    v = voice.get("voice", "analytical")

    # Build a verification suffix for appending to framing findings
    v_suffix = ""
    if verification:
        v_contra = verification.get("contradicted", 0)
        if v_contra > 0:
            v_suffix = (
                f" {v_contra} claim{'s' if v_contra != 1 else ''} "
                f"contradicted by authoritative sources."
            )

    # 1. Promotional with unsourced numbers (strongest framing signal)
    if v == "promotional" and unsupported >= 2:
        return (
            f"Promotional framing with {unsupported} numerical "
            f"claims showing no source-attribution markers.{v_suffix}"
        )

    # 2. Prescriptive voice with coverage gaps
    if v == "prescriptive" and len(missing) >= 2:
        return (
            f"Prescriptive document with low structural coverage "
            f"of {', '.join(missing)}."
            f"{v_suffix}"
        )

    # 3. High-precision unsourced claims (the fabrication signal)
    if unsupported >= 3 and epistemic.get("sourced", 0) == 0:
        return (
            f"{unsupported} specific numerical claims with no "
            f"source-attribution markers detected. Verify before "
            f"acting on these numbers.{v_suffix}"
        )

    # 5. Descriptive/reference with analytical gaps
    if v == "descriptive" and len(missing) >= 3:
        return (
            "Reference document: comprehensive on factual data, "
            f"low structural coverage of risk, trend, or uncertainty "
            f"language.{v_suffix}"
        )

    # 6. Missing categories
    covered_count = coverage.get("coverage_count", 0)
    if missing and covered_count >= 3 and len(missing) <= 2:
        # High coverage: acknowledge breadth first
        return (
            f"Covers {covered_count} of 5 analytical perspectives. "
            f"Low structural coverage of {', '.join(missing)}.{v_suffix}"
        )
    if missing:
        return (
            f"Low structural coverage of {', '.join(missing)}. "
            f"Read with that gap in mind.{v_suffix}"
        )

    # 5. Emphasis skew
    cats = coverage.get("categories", {})
    densities = {k: cv["density_per_1kw"] for k, cv in cats.items()
                 if cv.get("covered")}
    if len(densities) >= 2:
        max_cat = max(densities, key=densities.get)
        min_cat = min(densities, key=densities.get)
        if densities[max_cat] > 2.0 and densities[min_cat] > 0 and \
           densities[max_cat] > 3 * densities[min_cat]:
            return (
                f"Emphasis is heavily toward {max_cat} "
                f"({densities[max_cat]} per 1K words) "
                f"with minimal {min_cat} language "
                f"({densities[min_cat]} per 1K words)."
            )

    # 6. Confidence pattern
    total = claim_stats.get("total_claims", 0)
    unhedged = claim_stats.get("unhedged_count", 0)
    if total >= 5 and unhedged / total > 0.8:
        return (
            f"{unhedged} of {total} claims stated as definitive fact "
            "with no qualifying language detected."
        )

    # 9. Source contradictions without any framing signal
    if v_suffix:
        return v_suffix.strip()

    # 10. Nothing to flag
    return None
