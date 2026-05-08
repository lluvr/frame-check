"""
Frame library suggestions based on framing analysis output.

Maps the structural signals from framing.py (coverage, voice, temporal,
epistemic) to FVS library entries. Each suggestion names the frame,
gives a one-sentence explanation of why it was detected, and provides
a teaching prompt that helps the reader see past the frame.

Construct honesty: this function detects STRUCTURAL PATTERNS that
correlate with known frames. It does not detect semantic framing.
A document that structurally matches the Growth Frame pattern
(high trends, absent risks) might actually be a balanced analysis
of a growing market. The suggestions are hypotheses, not verdicts.
"""

import re
from typing import Any


# Growth-context vocabulary discriminator for FVS-008 (Growth Frame)
# detection. Move D-FVS-008 (2026-04-27): the structural signal alone
# (trends/causes covered + risks missing + voice not descriptive) over-fires
# on analytical documents that use directional-change vocabulary in
# non-business contexts (e.g., "scaling laws" in a literature review,
# "evolution" in institutional governance analysis, "growth" of a population
# or field). The frame's CONSTRUCT is business-growth framing specifically
# (organizing information around growth metrics, market expansion, upward
# trajectory). This regex requires explicit business-growth vocabulary
# alongside the structural signal so the rule fires only when the document
# is substantively about business growth.
#
# Conservative scope: business-growth markers (revenue, sales, earnings,
# market share/expansion/opportunity, customer/user/subscriber growth,
# adoption metrics, TAM, top-line, commercialization) plus quantified-growth
# patterns (X grew by $Y, N percent growth/annualized). Excludes bare
# "grow" / "expansion" / "scale" used generically in non-business contexts.
#
# Cross-fixture evidence: epistemic_via_paraphrased_sourcing (literature
# review on language-model interpretability) and cross_domain_stakeholder
# (Antarctic Treaty governance) both produced FVS-008 over-fire under the
# pre-Move-D rule and both correctly suppress under this discriminator.
# Validation-corpus check: 9 of 28 docs over-fire pre-Move-D; all 9 lack
# business-growth vocabulary and correctly suppress post-Move-D.
_FVS_008_GROWTH_CONTENT_RE = re.compile(
    r'\b('
    r'revenue|sales|earnings|profits?|TAM|top.line|bottom.line|'
    r'market\s+(?:share|growth|expansion|opportunity|size|cap)|'
    r'addressable\s+market|'
    r'customer\s+(?:growth|adoption|acquisition|base)|'
    r'user\s+(?:growth|adoption|acquisition|base)|'
    r'subscriber\s+(?:growth|adoption|base)|'
    r'installed\s+base|commercialization|monetization|'
    r'(?:grew|growth|growing|grow)\s+(?:by|to|from|at|of|its)\s+'
    r'(?:[\$\d]|the\s+market|customer|the\s+business)|'
    r'\d+\s*(?:percent|%)\s+(?:growth|annualized|grew|growing)'
    r')\b',
    re.IGNORECASE,
)


# Identity marker patterns for FVS-006 Identity Framing Asymmetry detection.
# The rule fires when the text uses role-claim language at meaningful density.
# Honest-limits note: this regex detects the STRUCTURAL signal (identity claim
# density), not the SEMANTIC signal (whether the claimed identity produced
# behavioral shift). Teaching question frames the gap explicitly.
IDENTITY_MARKERS_RE = re.compile(
    r'\b(as\s+an?\s+(?:expert|analyst|professional|specialist|authority|'
    r'consultant|researcher|practitioner|scientist|economist|strategist)|'
    r'from\s+the\s+perspective\s+of\s+an?|'
    r'speaking\s+as|in\s+my\s+role|playing\s+the\s+role\s+of|'
    r'act(?:ing)?\s+as|my\s+(?:role|perspective|expertise|experience))\b',
    re.IGNORECASE,
)

# Human-readable names for FVS IDs. Used by the mirror template
# to show "Growth Frame" instead of "FVS-008" in session cards.
FVS_NAMES: dict[str, str] = {
    "FVS-001": "Frame Amplification",
    "FVS-002": "Fluency-Quality Illusion",
    "FVS-003": "Prompt Attribution Error",
    "FVS-004": "Default Geometry",
    "FVS-005": "System Attribution Error",
    "FVS-006": "Identity Framing Asymmetry",
    "FVS-007": "Failure Framing",
    "FVS-008": "Growth Frame",
    "FVS-009": "Risk Frame",
    "FVS-010": "Completeness Illusion",
    "FVS-011": "Stakeholder Frame",
    "FVS-012": "Uncertainty Frame",
    "FVS-013": "Oracle Frame",
    "FVS-014": "Temporal Anchoring",
    "FVS-015": "Efficiency Frame",
    "FVS-016": "Authority by Citation",
    "FVS-017": "False Balance",
    "FVS-018": "Scope Narrowing",
    "FVS-019": "Narrative Coherence",
    "FVS-020": "The Invisible Frame",
}

# Canonical teaching questions per FVS entry. Mirrors the questions
# the firing rules in suggest_frames() emit when a frame matches;
# extracted here as a lookup so absent_frames (which never fire and
# therefore never get a question via _add) can be paired with their
# canonical teaching question for documentation, agent_guidance,
# and frame_opportunities composition.
#
# TODO(operator-authorship): 8 of 20 entries lack a teaching question
# (FVS-003, 004, 005, 006, 013, 018, 019, 020; all meta-side frames,
# 3 of 8 are withdrawn from v1 publication: FVS-003, 004, 018, 019).
# Authoring queue + per-entry construct-hint context lives in
# OPERATOR_AUTHORING_QUEUE.md. Per the project's "no LLM drafting of
# substantive content" discipline, teaching questions are operator-
# authored. The harness L7 FAIL is the visible gate that holds until
# the queue is closed; do not paper over it with placeholder questions.
# See get_teaching_question() below: it returns None for unauthored
# IDs and call sites must handle that path explicitly.
TEACHING_QUESTIONS: dict[str, str] = {
    "FVS-001": (
        "What is the framing this analysis is amplifying, and what "
        "would change if the frame itself were named explicitly?"
    ),
    "FVS-002": (
        "If this were written in rough notes instead of polished "
        "prose, would you still accept the claims?"
    ),
    "FVS-007": (
        "What would have to be true for this analysis to be wrong?"
    ),
    "FVS-008": (
        "What would a risk analyst say about this same data?"
    ),
    "FVS-009": (
        "Is the risk analysis proportionate, or is it overweighting "
        "worst-case scenarios?"
    ),
    "FVS-010": (
        "Does this document MENTION all perspectives or ANALYZE all "
        "perspectives?"
    ),
    "FVS-011": (
        "Is the stakeholder analysis substantive (specific impacts "
        "per group, tradeoffs named) or performative (stakeholder "
        "groups mentioned without analyzing who wins and who loses)?"
    ),
    "FVS-012": (
        "Is the uncertainty named substantively (ranges, assumptions, "
        "expert disagreement) or merely hedged (language softened "
        "without specifics)?"
    ),
    "FVS-014": (
        "What has changed since this data was current? Is the "
        "document presenting historical data as if it were the "
        "present?"
    ),
    "FVS-015": (
        "Is efficiency the right lens here, or has it been applied "
        "by default?"
    ),
    "FVS-016": (
        "Can you look up the specific sources cited? Would the "
        "argument survive if the citations were removed?"
    ),
    "FVS-017": (
        "What perspective is being excluded by this framing's "
        "balance? Is the balance structural or rhetorical?"
    ),
}


def get_teaching_question(fvs_id: str) -> str | None:
    """Return the canonical teaching question for an FVS ID, or None
    when no question is curated for that entry. Used by
    frame_opportunities to pair absent frames with their general
    teaching question before LLM composition."""
    return TEACHING_QUESTIONS.get(fvs_id)


# Operator-authored takeaway entries per FVS. When an entry is present
# here, the FVS surfaces as a button in the takeaway palette on the
# /check results page (live and saved). Each button drops the user into
# Claude / GPT with a per-document prompt that reads the user's document
# through this lens. When TAKEAWAY_ENTRIES is empty, the palette section
# is hidden entirely.
#
# The palette is the multi-frame surface: detected frames the document
# IS using AND divergent frames the document is NOT using both surface
# here, distinguished by the kind tag composed at render time. The
# user picks the angle they want to take further; each click is one
# lens applied to their document. Frame Check's value as a divergence
# instrument against AGI's convergent default lives in this surface.
#
# Schema per entry:
#   button_label:    short user-voice label for the button (no FVS
#                    jargon; the user does not know what an FVS is)
#   prompt_template: the prompt that opens in the user's LLM. Free-form
#                    text with str.format-style placeholders for
#                    substrate variables (see below)
#
# Prompt template substrate variables, filled at render time. Variables
# that have no value for THIS document fall back to "" so a template
# that references a missing variable does not crash:
#   {frame_name}        FVS human-readable name (e.g., "Failure Framing")
#   {fvs_id}            FVS-NNN identifier (rarely useful in user copy)
#   {teaching_question} TEACHING_QUESTIONS[fvs_id] when authored, else ""
#   {detected_frames}   comma-joined names of frames detected on this doc
#   {absent_dimensions} comma-joined names of coverage dimensions absent
#   {v4_2_reasoning}    V4.2 per-document reasoning text when available
#
# Per the "no LLM drafting of substantive content" discipline, every
# entry is operator-authored. The empty default state is a feature; a
# half-authored palette is worse than none. Adding one entry lights up
# the palette section live; the operator iterates from there.
TAKEAWAY_ENTRIES: dict[str, dict[str, str]] = {
    # FVS-NNN: {
    #     "button_label": "...",
    #     "prompt_template": "...",
    # },
}


class _EmptyDefault(dict):
    """dict subclass that returns "" for missing keys.

    Used by compose_takeaway_palette so a prompt template referencing a
    substrate variable Frame Check did not provide for THIS document
    silently empties out instead of raising KeyError. Keeps prompt
    authoring forgiving: the operator can reference {v4_2_reasoning} or
    {blind_spots} without having to guard every reference for the case
    where that piece of substrate did not run.
    """

    def __missing__(self, key):
        return ""


def _derive_ac1_tier(ac1_score) -> str:
    """Map a V4.2 AC1 inter-rater agreement score to a reliability
    tier label. Mirrors the cutoffs used elsewhere in results.html
    (strong >= 0.8, moderate >= 0.4, weak >= 0). Returns empty string
    when the score is None or non-numeric so the operator's prompt
    template can reference {ac1_tier} without a crash on documents
    where V4.2 did not run.
    """
    try:
        score = float(ac1_score)
    except (TypeError, ValueError):
        return ""
    if score >= 0.8:
        return "strong"
    if score >= 0.4:
        return "moderate"
    return "weak"


def _v4_2_entry_for_fvs(v4_2_result, fvs_id: str) -> dict | None:
    """Return the V4.2 per-frame entry for an FVS ID, or None when
    V4.2 did not run / did not include this FVS. v4_2_result is the
    same dict the templates and JSON API consume; it carries
    `entries` keyed by fvs_id when meta.framing_engine == "v4_2".
    """
    if not isinstance(v4_2_result, dict):
        return None
    meta = v4_2_result.get("meta") or {}
    if meta.get("framing_engine") != "v4_2":
        return None
    for entry in v4_2_result.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("fvs_id") == fvs_id:
            return entry
    return None


def compose_takeaway_palette(
    framing: dict | None,
    coverage: dict | None = None,
    v4_2_result: dict | None = None,
    voice: dict | None = None,
    epistemic: dict | None = None,
    claim_stats: dict | None = None,
) -> list[dict]:
    """Build the takeaway palette for one document.

    Iterates TAKEAWAY_ENTRIES in dict-insertion order. For every entry
    with both fields authored, composes the prompt by templating the
    entry's prompt_template with this document's enriched substrate.
    Each entry is tagged "detected" (its FVS appears in
    framing.frame_suggestions for this document) or "divergent" (its
    FVS does not appear in detected frames).

    The substrate carries per-FVS analysis findings (V4.2 per-frame
    reasoning, AC1 score and tier, Layer A signal text, importance,
    pattern_kind) plus cross-frame state (voice, claim density,
    sourced percentage, detected/absent FVS lists) so an
    operator-authored prompt template can weave document-specific
    findings INTO the prompt body. Without this depth of substrate
    the prompts collapse to slot-filled boilerplate.

    Args:
      framing:      the document's framing dict (with frame_suggestions)
      coverage:     the document's coverage dict (covered/missing)
      v4_2_result:  the V4.2 result dict (meta + entries) when V4.2 ran
      voice:        the document's voice dict (voice classification, etc.)
      epistemic:    the document's epistemic dict (sourced_pct, etc.)
      claim_stats:  per-document claim density / count dict

    Substrate variables exposed to operator prompt templates:
      Per-frame (filled from the matching frame_suggestion +
      V4.2 entry for THIS FVS):
        frame_name, fvs_id, teaching_question
        signal             Layer A's reason for firing
        importance         rank_frame_suggestions priority
        pattern_kind       present_detected | absent_pattern
        ac1_score          float as string ("" when V4.2 did not run)
        ac1_tier           strong | moderate | weak ("" when no score)
        v4_2_reasoning     V4.2's per-frame reasoning text
        v4_2_exhibited     "true" | "false" | "" (V4.2's verdict)

      Cross-frame (same on every entry for this document):
        detected_frames    comma-joined names of detected frames
        detected_fvs_ids   comma-joined FVS IDs of detected frames
        absent_dimensions  comma-joined absent coverage dimensions
        voice              voice classification
        claim_density      numerical claims per 1K words (string)
        sourced_pct        percent sentences sourced (string)

    Missing values fall through _EmptyDefault to "" so the operator's
    template can reference any variable without crashing on documents
    where the substrate is partial.

    Returns:
      Empty list when TAKEAWAY_ENTRIES is empty (section hidden).
      Otherwise a list of dicts, one per authored entry, each:
        fvs_id, frame_name, button_label, prompt, kind

      Half-authored entries (one of the two fields empty) are silently
      skipped: a partial entry surfacing as a broken button is worse
      than the entry not surfacing at all.
    """
    if not TAKEAWAY_ENTRIES:
        return []

    framing = framing or {}
    suggestions = framing.get("frame_suggestions") or []
    coverage = coverage or {}
    voice = voice or {}
    epistemic = epistemic or {}
    claim_stats = claim_stats or {}

    # Index frame_suggestions by fvs_id for per-frame lookup.
    suggestions_by_id = {
        s.get("fvs_id"): s for s in suggestions if s.get("fvs_id")
    }
    detected_ids = list(suggestions_by_id.keys())
    detected_names = [
        s.get("name") or s.get("fvs_id") or ""
        for s in suggestions
    ]

    # Cross-frame substrate (computed once; same for every palette entry).
    cross_frame = {
        "detected_frames": ", ".join(n for n in detected_names if n),
        "detected_fvs_ids": ", ".join(detected_ids),
        "absent_dimensions": ", ".join(coverage.get("missing") or []),
        "voice": voice.get("voice", ""),
        "claim_density": (
            str(claim_stats.get("numerical_per_1kw", ""))
            if claim_stats.get("numerical_per_1kw") is not None else ""
        ),
        "sourced_pct": (
            str(epistemic.get("sourced_pct", ""))
            if epistemic.get("sourced_pct") is not None else ""
        ),
    }

    palette: list[dict] = []
    for fvs_id, entry in TAKEAWAY_ENTRIES.items():
        button_label = (entry.get("button_label") or "").strip()
        template = entry.get("prompt_template") or ""
        if not button_label or not template:
            continue

        suggestion = suggestions_by_id.get(fvs_id) or {}
        v4_2_entry = _v4_2_entry_for_fvs(v4_2_result, fvs_id) or {}

        # V4.2 entries place AC1 + tier inside a nested `reliability`
        # dict (per templates/_v4_2_results.html); reading flat
        # `ac1_score` off the entry returns None silently. `exhibits`
        # is the verb-form field on the entry root.
        rel = v4_2_entry.get("reliability") or {}
        ac1_score = rel.get("library_consensus_ac1")
        ac1_tier = rel.get("reliability_tier") or ""
        v4_2_exhibits_raw = v4_2_entry.get("exhibits")
        v4_2_exhibited = (
            "true" if v4_2_exhibits_raw is True
            else ("false" if v4_2_exhibits_raw is False else "")
        )

        substrate = {
            # Per-frame
            "frame_name": FVS_NAMES.get(fvs_id) or fvs_id,
            "fvs_id": fvs_id,
            "teaching_question": get_teaching_question(fvs_id) or "",
            "signal": suggestion.get("signal") or "",
            "importance": (
                str(suggestion.get("_priority", ""))
                if suggestion.get("_priority") is not None else ""
            ),
            "pattern_kind": suggestion.get("pattern_kind") or "",
            "ac1_score": str(ac1_score) if ac1_score is not None else "",
            "ac1_tier": ac1_tier,
            "v4_2_reasoning": v4_2_entry.get("reasoning") or "",
            "v4_2_exhibited": v4_2_exhibited,
            # Cross-frame
            **cross_frame,
        }
        try:
            prompt = template.format_map(_EmptyDefault(substrate))
        except (IndexError, ValueError):
            # Malformed format spec inside the operator's template
            # (e.g., a stray `{` they did not intend as a placeholder).
            # Surface the raw template so the entry still appears; the
            # operator catches the bug on first use rather than the
            # whole palette disappearing.
            prompt = template

        palette.append({
            "fvs_id": fvs_id,
            "frame_name": FVS_NAMES.get(fvs_id) or fvs_id,
            "button_label": button_label,
            "prompt": prompt,
            "kind": "detected" if fvs_id in suggestions_by_id else "divergent",
        })
    return palette


# Canonical coverage-dimension questions. Mirrors the perspective_desc
# Jinja set in templates/results.html (line ~412); centralized here so
# the takeaway composer can reach the same questions without re-parsing
# template source. Five fixed dimensions are Frame Check's structural
# coverage contract.
COVERAGE_QUESTIONS: dict[str, str] = {
    "causes": "Why is this happening?",
    "risks": "What could go wrong?",
    "stakeholders": "Who is affected?",
    "trends": "What is changing?",
    "uncertainty": "What is unknown?",
}


def compose_takeaway_questions(
    framing: dict | None,
    v4_2_result: dict | None = None,
    sn_results: list | None = None,
    ai_interpret: dict | None = None,
    doc_text: str | None = None,
    *,
    max_frames: int = 5,
    max_unverified: int = 5,
) -> dict:
    """Deterministically compose the takeaway questions from existing
    analysis substrate. Zero new LLM calls; everything below is
    composed from data Frame Check already produced.

    The takeaway is the user's path from the analysis to a decision.
    It surfaces:
      - Frames the document is doing structural work through, with
        per-frame reasoning and the operator-curated question
      - Dimensions the document does not engage with their canonical
        question
      - Concerns Frame Check flagged (AI-interpret blind_spots; empty
        until that async stage resolves on live view)
      - Claims Frame Check could not verify externally
      - A bundled prompt the user can take to their LLM, structurally
        composed from the substrate above (no LLM-authored content)

    Source-of-truth selection for frames_in_use:
      1. V4.2 entries with exhibits == True, sorted ac1_score desc,
         capped at max_frames. V4.2 sees semantic frames Layer A's
         conservative regex detection misses; on a typical document
         V4.2 confirms 3-5 frames where Layer A emits 1-2.
      2. Fallback: framing.frame_suggestions (Layer A) capped at 3
         when V4.2 did not run (meta.framing_engine != "v4_2").

    Args:
      framing:       framing analysis dict (frame_suggestions + coverage)
      v4_2_result:   V4.2 result dict (meta + entries) when V4.2 ran
      sn_results:    list of SourceNetworkResult instances
      ai_interpret:  AI-interpret response dict (blind_spots, etc.) when
                     available; on live view first paint this is None
                     and concerns are empty until the JS async upgrades
      doc_text:      full document text (for bundling into llm_prompt)

    Returns:
      Dict with keys frames_in_use, absent_dimensions, concerns,
      unverified_claims, llm_prompt. Empty / partial when substrate
      is partial (no V4.2, no sn_results, no AI-interpret yet); the
      template gates each section on truthiness so empty sections
      hide cleanly.
    """
    framing = framing or {}
    coverage = framing.get("coverage") or {}
    suggestions = framing.get("frame_suggestions") or []

    # ── frames_in_use ──
    frames_in_use: list[dict] = []
    v4_2_engine = (v4_2_result or {}).get("meta", {}).get("framing_engine")
    if v4_2_result and v4_2_engine == "v4_2":
        # V4.2 path: rank exhibited entries by cross-family AC1, take
        # top-N. V4.2 carries semantic detection + per-frame reasoning
        # that Layer A's structural regexes do not produce.
        #
        # The canonical V4.2 entry schema (per templates/_v4_2_results.
        # html:81-110) places AC1 + tier inside a nested `reliability`
        # dict, not on the entry root. The first cut read `ac1_score`
        # off the entry (no such field), which silently returned None
        # everywhere: sort key was always 0 (entries appeared in
        # FVS-ID order, not AC1 desc), and ac1_tier was always empty
        # (no badge rendered). Reading from reliability matches what
        # the existing _v4_2_results.html partial does.
        exhibited = [
            e for e in (v4_2_result.get("entries") or [])
            if isinstance(e, dict) and e.get("exhibits") is True
        ]

        def _ac1_for_sort(entry):
            rel = entry.get("reliability") or {}
            score = rel.get("library_consensus_ac1")
            try:
                return -float(score)
            except (TypeError, ValueError):
                # Unmeasured entries sort last among exhibited rather
                # than crashing the whole sort.
                return 0.0

        exhibited.sort(
            key=lambda e: (_ac1_for_sort(e), e.get("fvs_id") or "")
        )

        for entry in exhibited[:max_frames]:
            fvs_id = entry.get("fvs_id") or ""
            rel = entry.get("reliability") or {}
            ac1 = rel.get("library_consensus_ac1")
            tier = rel.get("reliability_tier") or ""
            frames_in_use.append({
                "fvs_id": fvs_id,
                "frame_name": FVS_NAMES.get(fvs_id) or fvs_id,
                "ac1_tier": tier,
                "ac1_score": ac1,
                "reasoning": (entry.get("reasoning") or "").strip(),
                "question": (
                    get_teaching_question(fvs_id)
                    or _question_from_suggestion(suggestions, fvs_id)
                    or ""
                ),
                "library_url": f"/corpus/library/{fvs_id}.html" if fvs_id else "",
            })
    else:
        # Layer A fallback: V4.2 didn't run (skipped, fallback, blocked).
        # frame_suggestions carries name + signal + question; reasoning
        # field absent (the signal text serves as the rough equivalent).
        for s in suggestions[:3]:
            fvs_id = s.get("fvs_id") or ""
            frames_in_use.append({
                "fvs_id": fvs_id,
                "frame_name": s.get("name") or FVS_NAMES.get(fvs_id) or fvs_id,
                "ac1_tier": "",
                "ac1_score": None,
                "reasoning": (s.get("signal") or "").strip(),
                "question": (
                    s.get("question")
                    or get_teaching_question(fvs_id)
                    or ""
                ),
                "library_url": f"/corpus/library/{fvs_id}.html" if fvs_id else "",
            })

    # ── absent_dimensions ──
    absent_dimensions: list[dict] = []
    for dim in coverage.get("missing") or []:
        question = COVERAGE_QUESTIONS.get(dim, "")
        absent_dimensions.append({
            "name": dim,
            "question": question,
        })

    # ── concerns (AI-interpret blind_spots, when present) ──
    concerns: list[str] = []
    if ai_interpret and isinstance(ai_interpret, dict):
        for s in (ai_interpret.get("blind_spots") or []):
            if isinstance(s, str) and s.strip():
                concerns.append(s.strip())

    # ── contradicted_claims (from sn_results) ──
    # The takeaway's job is to surface what's actionable. Contradicted
    # claims (an external source SAYS the document is wrong about
    # value X) are actionable; unverifiable claims (out of Frame
    # Check's verification network coverage) are not, so flagging
    # them as "worth verifying" creates noise that misframes
    # methodology gap as document-quality concern. This filter keeps
    # only verdicts where the source disagrees, which is the rare
    # high-signal case the takeaway should pull up.
    #
    # claim_sentence on the underlying SourceNetworkResult sometimes
    # carries a tight 30+30 char window (claim_analysis.py:171) rather
    # than a clean sentence; the bullet-list path through
    # claim_analysis stores tight_context as the "sentence" field. To
    # avoid mid-word truncation in the rendered display, the composer
    # re-extracts a clean sentence excerpt from doc_text around each
    # value and falls back to the raw field only when extraction can't
    # find the value in the document.
    contradicted_claims: list[dict] = []
    for r in (sn_results or []):
        if len(contradicted_claims) >= max_unverified:
            break
        verdict = _read_sn_field(r, "verdict")
        if verdict != "contradicted":
            continue
        claim_numbers = _read_sn_field(r, "claim_numbers") or []
        raw_sentence = (_read_sn_field(r, "claim_sentence") or "").strip()
        detail = (_read_sn_field(r, "detail") or "").strip()
        primary_value = claim_numbers[0] if claim_numbers else ""
        clean_sentence = _clean_excerpt_around_value(
            doc_text or "", primary_value, raw_sentence,
        )
        contradicted_claims.append({
            "value": ", ".join(claim_numbers) if claim_numbers else "",
            "sentence": clean_sentence,
            "reason": detail,
        })

    # ── llm_prompt: structural bundle, no LLM-authored content ──
    llm_prompt = _compose_takeaway_llm_prompt(
        frames_in_use=frames_in_use,
        absent_dimensions=absent_dimensions,
        concerns=concerns,
        contradicted_claims=contradicted_claims,
        doc_text=doc_text or "",
    )

    return {
        "frames_in_use": frames_in_use,
        "absent_dimensions": absent_dimensions,
        "concerns": concerns,
        "contradicted_claims": contradicted_claims,
        "llm_prompt": llm_prompt,
    }


def _clean_excerpt_around_value(
    doc_text: str,
    value: str,
    fallback: str = "",
    *,
    max_back: int = 200,
    max_forward: int = 200,
) -> str:
    """Find `value` in doc_text and return a clean sentence-bounded
    excerpt around it. Used by the takeaway composer because
    SourceNetworkResult.claim_sentence sometimes carries a tight
    30+30 char window (claim_analysis.py:171, the bullet-list
    extraction path) rather than a clean sentence; that window
    starts and ends mid-word, which renders as garbage in the UI.

    Walks doc_text from the value's index outward to the nearest
    sentence terminator (`.`, `!`, `?`, newline) on each side,
    capped at max_back/max_forward chars to bound the excerpt
    length on table-formatted text without sentence boundaries.
    Falls back to `fallback` (or empty string) when value is not
    found in doc_text or doc_text is empty.
    """
    if not doc_text or not value:
        return (fallback or "").strip()
    idx = doc_text.find(value)
    if idx < 0:
        return (fallback or "").strip()

    end_value = idx + len(value)
    start = max(0, idx - max_back)
    for i in range(idx - 1, max(-1, idx - max_back - 1), -1):
        if i < 0:
            break
        if doc_text[i] in ".!?\n":
            start = i + 1
            break
    end = min(len(doc_text), end_value + max_forward)
    for i in range(end_value, min(len(doc_text), end_value + max_forward)):
        if doc_text[i] in ".!?\n":
            end = i + 1
            break

    excerpt = doc_text[start:end].strip()
    return excerpt or (fallback or "").strip()


def _read_sn_field(obj, name: str):
    """Read a field from a SourceNetworkResult that may arrive either
    as a dataclass instance (live /check path) or as a dict (saved
    view path, where the result was JSON-deserialized from disk).
    Returns None when the field is absent or the object is neither
    shape; callers handle the None.
    """
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _question_from_suggestion(suggestions, fvs_id: str) -> str | None:
    """Lookup a question for an FVS in framing.frame_suggestions; used
    when V4.2 lists an FVS that has no TEACHING_QUESTIONS entry but
    Layer A also emitted it. Returns None when no match.
    """
    for s in suggestions or []:
        if s.get("fvs_id") == fvs_id:
            return s.get("question")
    return None


def _compose_takeaway_llm_prompt(
    *,
    frames_in_use: list,
    absent_dimensions: list,
    concerns: list,
    contradicted_claims: list,
    doc_text: str,
) -> str:
    """Bundle the takeaway substrate into a single prompt the user can
    take to their LLM. Pure structural composition: every line of
    substantive content (frame names, reasoning, questions, blind
    spots, claims) comes from operator-curated or LLM-pre-computed
    sources. The wrapping prose ("Frame Check analyzed...", "Apply
    these to the document.") is structural format only.

    The output is plain text suitable for URL-encoding into a
    Claude / GPT chat link or copy-pasting into any LLM.
    """
    parts: list[str] = []
    parts.append("Frame Check has analyzed the document below. Findings:")
    parts.append("")

    if frames_in_use:
        parts.append("Frames doing structural work in the document:")
        for f in frames_in_use:
            tier = f" ({f['ac1_tier']})" if f.get("ac1_tier") else ""
            line = f"- {f['frame_name']}{tier}"
            if f.get("reasoning"):
                line += f": {f['reasoning']}"
            parts.append(line)
            if f.get("question"):
                parts.append(f"  Question to consider: {f['question']}")
        parts.append("")

    if absent_dimensions:
        parts.append("What the document does not engage:")
        for d in absent_dimensions:
            line = f"- {d['name']}"
            if d.get("question"):
                line += f": {d['question']}"
            parts.append(line)
        parts.append("")

    if concerns:
        parts.append("Specific concerns Frame Check flagged in this document:")
        for c in concerns:
            parts.append(f"- {c}")
        parts.append("")

    if contradicted_claims:
        parts.append("Claims sources contradict in this document:")
        for u in contradicted_claims:
            value = u.get("value") or ""
            sentence = u.get("sentence") or ""
            if value and sentence:
                parts.append(f"- {value} in: {sentence}")
            elif sentence:
                parts.append(f"- {sentence}")
            elif value:
                parts.append(f"- {value}")
        parts.append("")

    parts.append("Apply these questions and concerns to the document.")
    parts.append("Walk through each one with specific evidence from the text.")
    parts.append("Identify the strongest counter-position to the document's conclusion.")
    parts.append("")
    parts.append("Document:")
    parts.append(doc_text)

    return "\n".join(parts)


_DEFINITIONS: dict[str, str] = {
    "FVS-001": (
        "When AI converges on a frame, each iteration produces more "
        "sophisticated analysis within that frame. The analysis gets "
        "sharper. The conclusions get more confident. The frame itself "
        "goes unexamined."
    ),
    "FVS-002": (
        "Both humans and LLMs treat fluency as a proxy for quality. "
        "Smooth delivery, confident tone, and polished language make "
        "content feel correct whether or not it is. Errors hide in "
        "plain sight because the output feels good."
    ),
    "FVS-007": (
        "Specifying what counts as failure constrains output more "
        "sharply than specifying what success looks like. This document "
        "makes claims without naming what would make them wrong."
    ),
    "FVS-008": (
        "The default analytical frame for most AI-generated business "
        "content. Organizes information around growth metrics, market "
        "expansion, and upward trajectory while omitting risks, "
        "stakeholders, and uncertainty."
    ),
    "FVS-010": (
        "A document that addresses all expected dimensions can still "
        "operate from a single dominant frame. Breadth of coverage is "
        "not breadth of perspective. One sentence on risks is not "
        "risk analysis."
    ),
    "FVS-009": (
        "Organizes information around what could go wrong, what is "
        "vulnerable, and what depends on assumptions that might not hold. "
        "The counter-default to the growth frame. Risk analysis, not pessimism."
    ),
    "FVS-014": (
        "A document anchors the reader's perception of time by "
        "choosing which temporal orientation to emphasize. Past-anchored, "
        "future-projected, or present-focused: each hides the others."
    ),
    "FVS-015": (
        "Organizes information around cost reduction, optimization, "
        "and doing more with less. AI defaults to the efficiency "
        "frame because AI is itself positioned as an efficiency "
        "technology."
    ),
    "FVS-016": (
        "A document establishes credibility by citing sources. When "
        "citations are fabricated, misattributed, or real but not "
        "supporting the specific claim, the appearance of evidence "
        "substitutes for evidence."
    ),
    "FVS-011": (
        "Organizes information around who is affected, who benefits, "
        "who bears costs, and whose perspective is represented or "
        "excluded. The stakeholder frame asks 'for whom' and reveals "
        "whose interests the analysis serves by default."
    ),
    "FVS-012": (
        "Organizes information around what is unknown, contested, or "
        "dependent on assumptions that might not hold. The uncertainty "
        "frame surfaces the gap between confidence of presentation and "
        "confidence of evidence."
    ),
}


def rank_frame_suggestions(suggestions):
    """Sort suggestions by structural importance, highest first.

    Used when one frame must be picked from many: the structural-
    takeaway synthesizer's fallback question, or any future surface
    that elevates a "primary" frame card. Importance is the
    `_priority` field set by ``_add()`` inside :func:`suggest_frames`;
    the rule encoded there is:

    - **absence-pattern frames score higher than presence-pattern
      frames** (base 2.0 vs 1.0). Rationale: an absent-frame
      detection (e.g. FVS-007 Failure Framing absent) flags what
      the document is NOT doing. Reader-facing leverage is high
      because absences are difficult to spot manually; a ranking
      rule that ignored this would consistently surface the most
      common (presence) patterns and bury the diagnostically
      sharper ones.
    - **Marker-density bonus** when the signal text encodes a
      ``(X/1Kw)`` figure: ``priority += X * 0.1``. Higher density
      means stronger structural evidence within the same pattern
      kind. The coefficient is small enough that no plausible
      density value flips an absence-pattern below a presence-
      pattern.

    Stable sort: ties (same priority) preserve source-code firing
    order, so a future regression in priority computation does not
    randomly reshuffle the rest of the list. Returns a NEW list;
    does not mutate the input. Suggestions without a ``_priority``
    field default to 1.0 so legacy callers (or future detector
    rules that forget the field) do not crash.
    """
    indexed = list(enumerate(suggestions or []))
    indexed.sort(
        key=lambda iv: (-float(iv[1].get("_priority", 1.0)), iv[0])
    )
    return [iv[1] for iv in indexed]


def suggest_frames(
    coverage: dict[str, Any],
    voice: dict[str, Any],
    temporal: dict[str, Any],
    epistemic: dict[str, Any],
    text: str | None = None,
) -> list[dict[str, str]]:
    """Suggest FVS library entries that match the framing analysis output.

    Returns a list of dicts, each with:
      fvs_id:      stable identifier (e.g., "FVS-008")
      name:        human-readable frame name
      signal:      which detection outputs triggered this suggestion
      question:    one teaching question the reader should ask
      definition:  one-paragraph explanation of the frame

    Optional `text` parameter enables text-dependent rules that cannot
    operate on structural dicts alone (FVS-006 Identity Framing
    Asymmetry's identity-marker density). Non-breaking: when text is
    None, text-dependent rules simply do not fire. Existing callers
    unaffected; new callers that want full detection coverage pass the
    raw document.
    """
    suggestions = []
    cats = coverage.get("categories", {})
    covered = set(coverage.get("covered", []))
    missing = set(coverage.get("missing", []))
    voice_type = voice.get("voice", "")
    sourced_pct = epistemic.get("sourced_pct", 100)
    total_sentences = voice.get("total_sentences", 0)

    # Guard: suppress suggestions on very short documents (<5 sentences).
    # Detection is unreliable on short text because a single keyword
    # match triggers coverage and the frame suggestions become noise.
    if total_sentences < 5:
        return suggestions

    def _add(fvs_id, name, signal, question, pattern_kind="present_detected"):
        # `pattern_kind` encodes the V1-detector emission convention as a
        # structured enum field. Five values correspond to the five suffix
        # conventions historically encoded in `name`:
        #   "present_detected"  positive present-pattern detection
        #                       (FVS-002, FVS-008, FVS-009, FVS-010,
        #                        FVS-011, FVS-012, FVS-015, FVS-016 sites)
        #   "absence_detected"  absence-pattern detection (FVS-007 site)
        #   "present_past"      directional past-anchored present
        #                       (FVS-014 past site)
        #   "present_future"    directional future-anchored present
        #                       (FVS-014 future site)
        # The legacy suffix in `name` is preserved for backward compat with
        # hand-authored test fixtures at `test_decision_readiness.py:407,
        # 1095` that pin the literal "Failure Framing (absent)" name
        # shape. Future cleanup that strips the suffix is a separate
        # decision; this change is purely additive at the wire surface.
        # Importance score consumed by rank_frame_suggestions when one
        # frame must be chosen from many. Two components: an absence-
        # vs-presence base (2.0 / 1.0) and a marker-density bonus
        # extracted from the signal text. See rank_frame_suggestions
        # for the rationale and tradeoffs.
        priority = 2.0 if pattern_kind == "absence_detected" else 1.0
        density_match = re.search(r'\(([\d.]+)/1Kw\)', signal)
        if density_match:
            try:
                priority += float(density_match.group(1)) * 0.1
            except ValueError:
                pass
        suggestions.append({
            "fvs_id": fvs_id,
            "name": name,
            "signal": signal,
            "question": question,
            "definition": _DEFINITIONS.get(fvs_id, ""),
            "url": f"/corpus/library/{fvs_id}.html",
            "pattern_kind": pattern_kind,
            "_priority": priority,
        })

    # ── Growth Frame (FVS-008) ──
    # Move D-FVS-008 (2026-04-27): the structural signal alone (trends/causes
    # covered + risks missing + voice not descriptive) is too coarse: it fires
    # on any analytical document with directional-change vocabulary (trends
    # regex matches "evolution", "shift", "emerging", "transformation",
    # "expand" generically). Two adversarial fixtures provided cross-domain
    # worked examples of the over-fire (epistemic_via_paraphrased_sourcing
    # and cross_domain_stakeholder); validation corpus showed 9 of 28 docs
    # with the same over-fire signature, none of them substantively about
    # business growth. The frame's CONSTRUCT is business-growth framing
    # specifically (frame_library.py::_DEFINITIONS["FVS-008"]: "Organizes
    # information around growth metrics, market expansion, and upward
    # trajectory while omitting risks, stakeholders, and uncertainty"); the
    # fix is a content discriminator requiring growth-context vocabulary
    # alongside the structural signal. When text is None, FVS-008 falls
    # through per the standing "text-dependent rules don't fire when text
    # is None" discipline (see function docstring).
    has_growth_signal = (
        ("trends" in covered or "causes" in covered)
        and "risks" in missing
        and voice_type not in ("descriptive", "insufficient")
        and text is not None
        and bool(_FVS_008_GROWTH_CONTENT_RE.search(text))
    )
    if has_growth_signal:
        _add(
            "FVS-008", "Growth Frame",
            "High trends/causes coverage with risks absent and "
            "growth-context vocabulary present",
            "What would a risk analyst say about this same data?",
        )

    # ── Fluency-Quality Illusion (FVS-002) ──
    if voice_type == "promotional" and sourced_pct < 30:
        _add(
            "FVS-002", "Fluency-Quality Illusion",
            "Promotional voice with few sourced claims",
            "If this were written in rough notes instead of polished prose, would you still accept the claims?",
        )

    # ── Completeness Illusion (FVS-010) ──
    if coverage.get("coverage_count", 0) >= 4:
        densities = [
            cats[c]["density_per_1kw"]
            for c in covered
            if cats.get(c, {}).get("density_per_1kw", 0) > 0
        ]
        if len(densities) >= 2:
            max_d = max(densities)
            min_d = min(d for d in densities if d > 0)
            if max_d / min_d > 3:
                _add(
                    "FVS-010", "Completeness Illusion",
                    f"Covers {coverage['coverage_count']} dimensions but density is {max_d / min_d:.0f}x skewed",
                    "Does this document MENTION all perspectives or ANALYZE all perspectives?",
                )

    # ── Frame Amplification (FVS-001) ── RETIRED 2026-04-18.
    # Rule removed from production. The v1 signal substrate
    # (coverage/voice/temporal/epistemic density) cannot distinguish
    # FVS-001 target cases from similarly-shaped non-cases: the rule
    # labels vocabulary-distribution patterns as amplification. The
    # frame concept stands as a
    # library entry; detection is pending richer signals (V4.2 LLM-judge
    # or new signals in framing.py). See test_frame_library.py
    # TestFrameAmplificationRetired for the sentinel test guarding against
    # unintentional resurrection.

    # ── Failure Framing absence (FVS-007) ──
    if "risks" in missing and "uncertainty" in missing:
        unhedged_pct = 100 - sourced_pct
        if unhedged_pct > 60:
            _add(
                "FVS-007", "Failure Framing (absent)",
                "No risk or uncertainty coverage, high unsupported assertion rate",
                "What would have to be true for this analysis to be wrong?",
                pattern_kind="absence_detected",
            )

    # ── Efficiency Frame (FVS-015) ──
    has_efficiency_signal = (
        ("trends" in covered or "causes" in covered)
        and "stakeholders" in missing
        and "uncertainty" in missing
        and voice_type not in ("descriptive", "insufficient")
    )
    if has_efficiency_signal and not has_growth_signal:
        _add(
            "FVS-015", "Efficiency Frame",
            "Optimization metrics present, stakeholder impact and uncertainty absent",
            "Is efficiency the right lens here, or has it been applied by default?",
        )

    # ── Risk Frame (FVS-009, positive detection) ──
    # Signal: risks covered with substantive density (>5/1Kw),
    # analytical voice, and the document also covers uncertainty.
    # This is a POSITIVE frame identification, not a problem.
    # The teaching question acknowledges the risk frame while
    # asking whether it is overweighted.
    risks_density = cats.get("risks", {}).get("density_per_1kw", 0)
    if (
        "risks" in covered
        and risks_density > 5
        and "uncertainty" in covered
        and voice_type == "analytical"
    ):
        _add(
            "FVS-009", "Risk Frame (active)",
            f"Substantive risk analysis ({risks_density}/1Kw) with uncertainty acknowledged",
            "Is the risk analysis proportionate, or is it overweighting worst-case scenarios?",
        )

    # ── Stakeholder Frame (FVS-011, positive detection) ──
    # Signal: stakeholders covered with substantive density, analytical
    # or advisory voice. Mirrors the FVS-009 pattern for positive frame
    # identification. The teaching question asks the substantive-vs-
    # performative distinction the entry names as its honest limit:
    # the detector cannot distinguish specific impact analysis from
    # vacuous "stakeholders include everyone" phrasing.
    stakeholder_density = cats.get("stakeholders", {}).get("density_per_1kw", 0)
    if (
        "stakeholders" in covered
        and stakeholder_density > 5
        and voice_type in ("analytical", "advisory")
    ):
        _add(
            "FVS-011", "Stakeholder Frame (active)",
            f"Stakeholder coverage present ({stakeholder_density}/1Kw) in analytical voice",
            "Is the stakeholder analysis substantive (specific impacts per group, tradeoffs named) or performative (stakeholder groups mentioned without analyzing who wins and who loses)?",
        )

    # ── Uncertainty Frame (FVS-012, positive detection) ──
    # Signal: uncertainty covered with meaningful density. Lower density
    # threshold than risks/stakeholders because uncertainty markers are
    # naturally sparser (hedges and qualifiers live in fewer sentences
    # than risk or stakeholder nouns do). Voice gate excluded: uncertainty
    # coverage is interesting in any voice type, not only analytical.
    uncertainty_density = cats.get("uncertainty", {}).get("density_per_1kw", 0)
    if "uncertainty" in covered and uncertainty_density > 3:
        _add(
            "FVS-012", "Uncertainty Frame (active)",
            f"Uncertainty coverage present ({uncertainty_density}/1Kw)",
            "Is the uncertainty named substantively (ranges, assumptions, expert disagreement) or merely hedged (language softened without specifics)?",
        )

    # ── Temporal Anchoring (FVS-014) ──
    # Signal: one temporal orientation dominates heavily (>70%).
    # The document anchors the reader in one time perspective.
    past_pct = temporal.get("past_pct", 0)
    future_pct = temporal.get("future_pct", 0)
    if past_pct >= 70:
        _add(
            "FVS-014", "Temporal Anchoring (past)",
            f"Past-oriented language in {past_pct}% of sentences",
            "What has changed since this data was current? Is the document presenting historical data as if it were the present?",
            pattern_kind="present_past",
        )
    elif future_pct >= 60:
        _add(
            "FVS-014", "Temporal Anchoring (future)",
            f"Future-oriented language in {future_pct}% of sentences",
            "What is the historical base rate for projections like these? How accurate have similar forecasts been?",
            pattern_kind="present_future",
        )

    # ── Authority by Citation (FVS-016) ──
    # Signal: high sourced_pct (many claims use citation language) in
    # any voice. The original rule only fired on promotional/advisory
    # voice. Adversarial testing (ADV-07) showed that fabricated
    # citations in analytical voice were undetected. Broadened: the
    # rule now fires when sourced_pct >= 50% regardless of voice,
    # because high citation density in any voice warrants the question
    # "can you look up these sources?" The threshold is raised from
    # 40% to 50% to compensate for the broader voice scope.
    if sourced_pct >= 50:
        _add(
            "FVS-016", "Authority by Citation",
            f"High citation density ({sourced_pct}% of claims source-attributed)",
            "Can you look up the specific sources cited? Would the argument survive if the citations were removed?",
        )

    # FVS-006, FVS-017, FVS-019 do not have active detection rules.
    # `IDENTITY_MARKERS_RE` and the `text` kwarg on `suggest_frames`
    # are retained for future activation once curator decisions on
    # class reclassification and detection scope land. Neither is
    # load-bearing for any currently active rule.

    return suggestions
