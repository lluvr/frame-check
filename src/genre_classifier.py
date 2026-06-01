"""Structural genre classification for the MCP analysis surface.

Foundational primitive that per-genre absence ranking and pattern
composition build on. The classifier emits a genre with confidence
and runner-up using the same shape as voice: bounded label set,
deterministic features, margin-aware confidence reporting.

Genre set (bounded, structural):
  - recommendation: gives a pick or suggests action
  - analysis: investigates without committing to a recommendation
  - narrative: tells a story or sequence of events
  - advocacy: argues for a position with persuasive force
  - exploration: surveys options without committing
  - instruction: explains how to do something

The classifier composes existing analyzer outputs (voice, claim
distribution, hedge ratio) with text-feature regexes (recommendation
markers, instruction markers, alternative-surveying markers, etc.)
into a per-genre score. Top score is the classification; runner-up
margin drives the confidence label, mirroring voice.

The substrate stays deterministic: regex matching plus arithmetic
over existing structural measurements. No LLM is invoked. Genre is
not a verdict on the document; it is a structural reading of how
the document positions its content. Agents surfacing genre should
name it as Frame Check's reading and surface the runner-up when
confidence is borderline (the cascade hesitated between two
positionings).
"""

from __future__ import annotations

import re
from typing import Optional


# Bounded genre set. Adding a new genre requires:
#   1. Adding it here (the canonical label).
#   2. Adding its scoring contributions in _score_genres.
#   3. Adding its construct-honest description in _GENRE_CONSTRUCTS.
#   4. (For Item 3) Adding a per-genre load-bearing-absence map.
_GENRES = (
    "recommendation",
    "analysis",
    "narrative",
    "advocacy",
    "exploration",
    "instruction",
)

# Confidence is "borderline" when the runner-up margin (top score
# minus second score, normalized) falls under this threshold. Mirrors
# voice's borderline reporting: the agent surfacing genre should name
# the runner-up when borderline so the user sees the cascade's
# hesitation rather than a single-label verdict.
_BORDERLINE_MARGIN = 0.10

# Recommendation markers: phrases that explicitly name a pick or
# suggest action. Word boundaries to avoid false positives.
# Coverage includes contractions ("I'd recommend", "I'd lean
# toward") and common LLM-output patterns ("lean toward", "core
# holding", "would advise").
#
# `you\s+should` carries a perception-verb negative lookahead so
# descriptive UI-affordance constructions ("you should see X happen",
# "you should notice Y") are NOT counted as recommendations. Without
# the lookahead, a single false-positive triggers the +5.0 categorical
# bonus and produces HIGH-confidence misclassification of instruction
# documents (see data/adversarial_fixtures/instruction_without_
# troubleshooting/audit.md, Move A). Excluded perception verbs:
# see, notice, observe, hear (unambiguously perceptual). Ambiguous
# verbs (expect, find, feel, get) are NOT excluded; they remain
# matched.
_RECOMMENDATION_RE = re.compile(
    r"(i\s+recommend|my\s+pick|i\s+would\s+(?:pick|choose|go\s+with)|"
    r"i'd\s+(?:recommend|suggest|lean\s+toward|advise|pick|choose|"
    r"go\s+with)|"
    r"the\s+best\s+(?:option|pick|choice|bet)|"
    r"you\s+should(?!\s+(?:see|notice|observe|hear)\b)|"
    r"you'd\s+want\s+to|"
    r"my\s+choice|if\s+i\s+were|i\s+suggest|i\s+would\s+suggest|"
    r"my\s+vote|if\s+i\s+had\s+to\s+pick|putting\s+my\s+money|"
    r"i\s+am\s+picking|"
    r"i'd\s+lean\s+toward|"
    r"i\s+would\s+lean\s+toward|"
    r"my\s+(?:answer|recommendation|view)\s+is|"
    r"my\s+(?:direct\s+)?recommendation|"
    r"(?:should|could)\s+be\s+considered|"
    r"as\s+a\s+core\s+(?:holding|investment|position))",
    re.IGNORECASE,
)

# Instruction markers: imperative + procedural patterns.
#
# Markdown-header step formatting (`## Step N:` or `### Step N:`)
# is a common shape for setup guides, how-to docs, and runbooks; the
# bare-line alternative requires whitespace-only prefix and would
# miss those documents. The header alternative is structurally
# specific (header level + "step" + number + colon/period + space)
# and low false-positive risk (see data/adversarial_fixtures/
# instruction_without_troubleshooting/audit.md, Move B).
_INSTRUCTION_RE = re.compile(
    r"(?:^|\n)\s*(?:step\s+\d+[:.]\s|first[,]\s|next[,]\s|"
    r"then[,]\s|finally[,]\s|\d+\.\s+[A-Z])"
    r"|(?:^|\n)#{1,6}\s+step\s+\d+[:.]\s",
    re.IGNORECASE,
)

# Alternative-surveying markers: phrasing that names options without
# committing. Drives exploration vs analysis distinction.
_ALTERNATIVES_RE = re.compile(
    r"\b(options?\s+(?:include|are|to\s+consider)|"
    r"alternatives?\b|consider\s+(?:also|too)|"
    r"on\s+(?:one|the\s+one)\s+hand|on\s+the\s+other\s+hand|"
    r"either\s+\w+\s+or\s+\w+|several\s+options|"
    r"three\s+(?:opportunities|options|alternatives|approaches))\b",
    re.IGNORECASE,
)

# Advocacy markers: assertive + persuasive language.
_ADVOCACY_RE = re.compile(
    r"\b(must\b|essential\b|imperative\b|critical(?:ly)?\b|"
    r"obviously\b|clearly\b|undeniably\b|without\s+doubt|"
    r"the\s+only\s+(?:way|answer|solution)|unstoppable\b)\b",
    re.IGNORECASE,
)

# Narrative markers: temporal anchors, named past events.
_NARRATIVE_RE = re.compile(
    r"\b(in\s+(?:19|20)\d{2}|last\s+(?:year|month|week|quarter)|"
    r"yesterday|years\s+ago|decades\s+ago|once\s+upon|when\s+\w+\s+(?:was|were|did))\b",
    re.IGNORECASE,
)


def _per_kw(count: int, word_count: int) -> float:
    """Density per 1000 words. Returns 0 for empty text."""
    if word_count <= 0:
        return 0.0
    return count * 1000.0 / word_count


def _word_count(text: str) -> int:
    return len(text.split())


def _score_genres(
    text: str,
    voice: Optional[dict],
    claims: Optional[dict],
) -> dict[str, float]:
    """Return raw genre scores in [0, +inf). Caller normalizes."""
    wc = _word_count(text)
    if wc <= 0:
        return {g: 0.0 for g in _GENRES}

    rec_count = len(_RECOMMENDATION_RE.findall(text))
    inst_count = len(_INSTRUCTION_RE.findall(text))
    alt_count = len(_ALTERNATIVES_RE.findall(text))
    adv_count = len(_ADVOCACY_RE.findall(text))
    narr_count = len(_NARRATIVE_RE.findall(text))

    rec_density = _per_kw(rec_count, wc)
    inst_density = _per_kw(inst_count, wc)
    alt_density = _per_kw(alt_count, wc)
    adv_density = _per_kw(adv_count, wc)
    narr_density = _per_kw(narr_count, wc)

    # Hedge ratio from claim analysis. High hedge ratio favors
    # analysis and exploration; low favors advocacy and instruction.
    hedge_ratio = 0.0
    if claims and claims.get("total_claims"):
        total = claims["total_claims"]
        hedged = claims.get("hedged_count", 0)
        hedge_ratio = (hedged / total) if total > 0 else 0.0

    # Voice signal. Each voice classification contributes weight to
    # specific genres. None when voice unavailable.
    voice_label = voice.get("voice") if voice else None

    scores = {g: 0.0 for g in _GENRES}

    # recommendation: rec markers strong, advocacy markers contribute
    # half-weight (overlap with advisory persuasion).
    scores["recommendation"] = rec_density * 2.0 + adv_density * 0.5
    if voice_label == "advisory":
        scores["recommendation"] += 1.0
    # Recommendation-marker categorical bonus: when explicit pick
    # markers fire at all, recommendation gets a +5.0 categorical
    # bonus on top of the density scoring. Pick markers are high-
    # precision evidence that the document positions itself to name
    # a pick; the categorical bonus prevents competing genres'
    # density signals (narrative density from "in YYYY" sentence-
    # internal date references, alternative-surveying density from
    # one-hand/other-hand framing) from overriding when the document
    # explicitly states a pick. The density component still rewards
    # documents with multiple pick markers more highly; the
    # categorical component says presence-at-all is meaningful.
    #
    # Calibrated against the sales_pitch_as_analysis adversarial
    # fixture (data/adversarial_fixtures/), where 2 narrative-anchor
    # matches pushed narrative score to ~9.3 and overrode an
    # explicit pick marker scoring ~6.2; the +5.0 floor brings
    # recommendation to ~11.2, restoring correct classification
    # without lowering the narrative weight (which would mis-
    # classify legitimate narrative documents).
    if rec_count > 0:
        scores["recommendation"] += 5.0

    # analysis: hedge ratio + analytical voice; alt markers contribute
    # half-weight (analyses survey alternatives but commit to a
    # reading).
    scores["analysis"] = hedge_ratio * 5.0 + alt_density * 0.5
    if voice_label == "analytical":
        scores["analysis"] += 2.0

    # narrative: temporal markers dominate; advisory voice contributes
    # nothing here (narratives are descriptive, not prescriptive).
    scores["narrative"] = narr_density * 1.5

    # advocacy: advocacy markers + low hedge + (advisory or
    # promotional voice). Distinguished from recommendation by lack
    # of explicit pick markers AND high advocacy-marker density.
    # The low-hedge-ratio bonus applies only when there are claims;
    # otherwise an empty / featureless document would default to
    # "advocacy" simply because hedge_ratio defaults to 0 (no
    # claims means no claims hedged means 1.0 unhedged-fraction is
    # an artifact, not evidence).
    has_claims = bool(claims and claims.get("total_claims", 0) > 0)
    scores["advocacy"] = adv_density * 2.0
    if has_claims:
        scores["advocacy"] += (1.0 - hedge_ratio) * 1.5
    if voice_label in ("advisory", "promotional"):
        scores["advocacy"] += 0.5
    # Penalize advocacy if explicit recommendation markers fired
    # (those steer the document into recommendation rather than
    # advocacy).
    scores["advocacy"] -= rec_density * 0.5

    # exploration: alternative markers + hedging without committing
    # to a pick. Penalized by recommendation markers.
    scores["exploration"] = alt_density * 2.0 + hedge_ratio * 1.5
    scores["exploration"] -= rec_density * 0.7

    # instruction: instruction markers + imperative voice. Distinct
    # from advocacy by procedural shape (numbered lists, step
    # markers).
    scores["instruction"] = inst_density * 3.0
    if voice_label == "advisory":
        scores["instruction"] += 0.5

    # Floor at 0 (negative scores from penalties don't carry
    # forward).
    for g in _GENRES:
        if scores[g] < 0:
            scores[g] = 0.0

    return scores


# Per-genre load-bearing absence maps. For each structural genre,
# an ordered list of FVS IDs (most load-bearing first) plus a
# curated one-sentence reason naming the structural relevance.
# When a document classifies into a genre, absences that are load-
# bearing for that genre rise to the top of the divergence reading;
# absences that are catalog-canon but not load-bearing for THIS
# genre stay below.
#
# The reasons are reading-form, not verdict-form: they describe what
# the framing fails to do at the structural level, not what the
# document is.
#
# Adding a new genre requires updating this map (paired with the
# scoring function and construct text above).
_GENRE_LOAD_BEARING_ABSENCES = {
    "recommendation": [
        ("FVS-007", "Recommendations without falsification conditions cannot be stress-tested by the reader."),
        ("FVS-009", "A recommendation without a Risk Frame foregrounds upside while leaving downside unnamed."),
        ("FVS-014", "Time-bounded recommendations need temporal anchoring; without it, the pick may already be expired."),
        ("FVS-012", "Recommendations without uncertainty markers commit confidence the underlying evidence may not support."),
    ],
    "analysis": [
        ("FVS-016", "Analysis without citable authority is ungrounded; the reader cannot verify the claims."),
        ("FVS-012", "Analysis that does not signal where confidence is provisional reads as more decisive than the evidence supports."),
        ("FVS-017", "Analysis that surfaces only one side of a contested question is structurally one-sided regardless of its prose."),
        ("FVS-011", "Analysis that omits the stakeholder map cannot test its conclusions against affected parties."),
    ],
    "narrative": [
        ("FVS-011", "Narrative without a stakeholder frame leaves the reader unable to identify whose voice the story carries and whose is missing."),
        ("FVS-014", "Narrative without temporal anchoring cannot situate its events; the reader sees a sequence but not a position in time."),
        ("FVS-007", "Narrative without failure framing presents a single outcome path; the reader cannot see what would have made the story end differently."),
        ("FVS-001", "Narrative without naming the frame it amplifies surfaces a single reading as natural rather than chosen."),
    ],
    "advocacy": [
        ("FVS-017", "Advocacy without alternative perspectives is structurally one-sided; the reader is asked to take a position without seeing what would oppose it."),
        ("FVS-009", "Advocacy without naming the risks of its own position foregrounds upside while leaving downside unnamed."),
        ("FVS-011", "Advocacy that does not name whose interests it serves leaves stakeholder accountability ambiguous."),
        ("FVS-007", "Advocacy without falsification conditions positions itself as not testable; the reader cannot find what would change the position."),
    ],
    "exploration": [
        ("FVS-007", "Exploration that does not test its options against falsification conditions surveys without stress-testing."),
        ("FVS-014", "Exploration without temporal anchoring leaves option viability unbounded in time."),
        ("FVS-009", "Exploration without naming risks per option leaves the comparison surface incomplete."),
        ("FVS-012", "Exploration that does not signal where confidence is provisional reads as decisive when it should be tentative."),
    ],
    "instruction": [
        ("FVS-015", "Instruction without an efficiency frame leaves resource use, time cost, and trade-offs unspecified."),
        ("FVS-016", "Instruction without citable authority leaves the reader unable to verify the procedure against an authoritative source."),
        ("FVS-009", "Instruction without naming what can go wrong leaves failure modes invisible at the procedural level."),
    ],
}


def get_genre_load_bearing_absences(genre: str) -> list[tuple[str, str]]:
    """Return the ordered list of (fvs_id, reason) tuples for a
    classified genre's load-bearing absences. Returns an empty list
    when the genre is unknown or None (the substrate stays honest:
    no genre means no per-genre re-ranking)."""
    if not genre:
        return []
    return list(_GENRE_LOAD_BEARING_ABSENCES.get(genre, []))


def get_genre_relevance(fvs_id: str, genre: str) -> dict | None:
    """Return per-frame genre relevance for an FVS ID under the
    classified genre. None when:
      - genre is None or unknown
      - fvs_id is not in the genre's load-bearing list

    Output:
      {
        "relevant_for_genre": True,
        "priority": int (1 = most load-bearing),
        "reason": str,
      }
    """
    if not fvs_id or not genre:
        return None
    bearings = _GENRE_LOAD_BEARING_ABSENCES.get(genre)
    if not bearings:
        return None
    for idx, (canon_id, reason) in enumerate(bearings, start=1):
        if canon_id == fvs_id:
            return {
                "relevant_for_genre": True,
                "priority": idx,
                "reason": reason,
            }
    return None


_GENRE_CONSTRUCTS = {
    "recommendation": (
        "Document positions itself to name a pick or suggest an "
        "action. Detected via recommendation-marker density "
        "(\"my pick\", \"I recommend\", \"the best option\", "
        "etc.) plus advisory voice."
    ),
    "analysis": (
        "Document investigates without committing to a "
        "recommendation. Detected via hedge ratio, analytical "
        "voice, and alternative-surveying markers without an "
        "explicit pick."
    ),
    "narrative": (
        "Document tells a story or sequence of events. Detected "
        "via temporal-anchor density (named past dates, event "
        "chains)."
    ),
    "advocacy": (
        "Document argues for a position with persuasive force. "
        "Detected via assertive-marker density (\"must\", "
        "\"essential\", \"obviously\"), low hedge ratio, and "
        "advisory or promotional voice without explicit pick "
        "markers."
    ),
    "exploration": (
        "Document surveys options without committing. Detected "
        "via alternative-surveying markers and hedging without "
        "explicit recommendation markers."
    ),
    "instruction": (
        "Document explains how to do something procedurally. "
        "Detected via instruction-marker density (numbered "
        "steps, \"first\", \"next\", procedural lists)."
    ),
}


def classify_genre(
    text: str,
    voice: Optional[dict] = None,
    claims: Optional[dict] = None,
) -> dict:
    """Return the structural genre classification.

    Output (matches voice's classification-confidence shape):
      {
        "genre": one of _GENRES,
        "confidence": "borderline" or absent (confident),
        "runner_up": second-highest genre or None,
        "runner_up_margin": float (top - runner_up, normalized),
        "score_distribution": {genre: score, ...},
        "construct": construct-honest description for the chosen genre,
      }

    Inputs:
      text: the analyzed document text
      voice: output of framing.detect_voice(text), or None when
             the caller does not have voice data
      claims: claim_analysis output dict (must carry total_claims +
              hedged_count), or None
    """
    if not text or not text.strip():
        return {
            "genre": None,
            "confidence": "low",
            "runner_up": None,
            "runner_up_margin": None,
            "score_distribution": {g: 0.0 for g in _GENRES},
            "construct": (
                "No genre classification: empty document. The "
                "classifier requires text to extract structural "
                "features."
            ),
        }

    # Construct-honest evidence gate: feature regex evidence is
    # required for classification. The previous gate only abstained
    # when no features AND no claims; that left a hole where docs
    # with claims but zero feature matches scored advocacy by
    # default (because `(1.0 - hedge_ratio) * 1.5` adds 1.5
    # baseline to advocacy whenever has_claims is True, regardless
    # of whether advocacy markers fired). The substrate cannot
    # honestly classify a document into a genre on hedge ratio +
    # voice alone; explicit feature markers are required.
    rec_count = len(_RECOMMENDATION_RE.findall(text))
    inst_count = len(_INSTRUCTION_RE.findall(text))
    alt_count = len(_ALTERNATIVES_RE.findall(text))
    adv_count = len(_ADVOCACY_RE.findall(text))
    narr_count = len(_NARRATIVE_RE.findall(text))
    feature_total = (
        rec_count + inst_count + alt_count + adv_count + narr_count
    )
    if feature_total == 0:
        return {
            "genre": None,
            "confidence": "low",
            "runner_up": None,
            "runner_up_margin": None,
            "score_distribution": {g: 0.0 for g in _GENRES},
            "construct": (
                "No genre classification: no feature-marker regex "
                "matched. Voice classification + claim hedge ratio "
                "alone are not sufficient evidence for structural "
                "genre; the classifier abstains rather than label "
                "off-methodology text or content using vocabulary "
                "the regex set does not recognize."
            ),
        }

    raw = _score_genres(text, voice, claims)
    total = sum(raw.values())
    if total <= 0:
        # No score above zero even with feature evidence (rare; can
        # happen if features fired but all scoring contributions
        # cancelled to zero through penalties). Classifier abstains.
        return {
            "genre": None,
            "confidence": "low",
            "runner_up": None,
            "runner_up_margin": None,
            "score_distribution": raw,
            "construct": (
                "No genre classification: feature signals fired but "
                "all per-genre scores resolved to zero through "
                "penalty interactions. The classifier abstains "
                "rather than guess."
            ),
        }

    # Normalize to [0, 1] so the runner-up margin is comparable
    # across documents of different size.
    normalized = {g: (raw[g] / total) for g in _GENRES}
    sorted_genres = sorted(normalized.items(), key=lambda kv: -kv[1])
    top_genre, top_score = sorted_genres[0]
    runner_up, runner_up_score = sorted_genres[1]
    margin = round(top_score - runner_up_score, 3)

    confidence = "borderline" if margin < _BORDERLINE_MARGIN else "high"
    construct = _GENRE_CONSTRUCTS.get(top_genre)

    return {
        "genre": top_genre,
        "confidence": confidence,
        "runner_up": runner_up,
        "runner_up_margin": margin,
        "score_distribution": {
            g: round(s, 3) for g, s in normalized.items()
        },
        "construct": construct,
    }
