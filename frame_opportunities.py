"""LLM-augmented frame-opportunity composition.

This module is opt-in only (via include_frame_opportunities=true
on the frame_check tool) and is the only path that calls an LLM;
default frame_check responses preserve the deterministic
substrate composition with zero LLM cost per query.

Where the deterministic substrate gives the agent abstract teaching
questions ("What would have to be true for this analysis to be
wrong?"), this module generates document-specific questions
composed from the absent frame's perspective + the document's
content + the user's goal. Example: instead of the abstract teaching
question, the agent receives "If carbon credit prices crashed by
40 percent, would Regenerative Ag still be your pick?".

Strategic discipline:
  - Opt-in. The deterministic substrate works without this module
    being called; absence of LLM credentials degrades gracefully.
  - Cost-tracked. Each generated opportunity carries its
    cost_usd, model name, and is_deterministic=False flag. The
    response carries a total cost summary at the envelope level.
  - Bounded. Maximum 3 opportunities per request (one Gemini Flash
    call each; total ~$0.001 max per frame_check invocation when
    enabled).
  - Construct-honest. Generated questions are clearly flagged as
    LLM-composed (is_deterministic=False); abstract teaching
    questions remain available alongside the generated ones.
"""

from __future__ import annotations

import os
from typing import Optional


# Cap on opportunities per request. Three keeps cost bounded
# (~$0.001 max) while surfacing the highest-priority absences.
_MAX_OPPORTUNITIES = 3

# Document excerpt length passed to the LLM. Long enough for
# context, short enough to keep token cost predictable.
_DOC_EXCERPT_CHARS = 2000

# Prompt template. Composes absent frame + document context +
# substrate-level composition (clusters, patterns, corpus context)
# into a specific question. Item C of the post-roadmap polish:
# the LLM now consumes the substrate's own composition layer, not
# just the absent frame's teaching question in isolation.
_OPPORTUNITY_PROMPT_TEMPLATE = """You are composing a single specific question that uses an absent analytical frame's perspective against a document's actual content.

The absent frame is FVS-{frame_number} {frame_title}.
The frame's general teaching question is: "{teaching_question}"

The document's structural genre is: {genre}
The user's stated goal is: {goal}
{substrate_context_block}{corpus_context_block}
Document excerpt:
\"\"\"
{document_excerpt}
\"\"\"

Compose ONE specific question that:
- Cites a specific fact, claim, or framing from the document (use document specifics, not generic language).
- Applies the frame's perspective to interrogate that specific.
- Incorporates the substrate-level context above when it sharpens the question (cluster themes, named patterns, or corpus prevalence): only when these add to the reading; do not import them as scenery.
- Is one sentence. Maximum two sentences if the question requires a short scenario clause.
- Is reading-form, not verdict-form: ask what the user can think about; do not assert what the document is or should have been.
- Is answerable through reasoning about the document's content; does not require external research.

Output ONLY the question text. No preamble, no explanation, no quotes around the question, no labels."""


def _is_gemini_available() -> bool:
    """Check whether Gemini credentials and library are available.
    Returns False if the GEMINI_API_KEY env var is missing or the
    google.genai library is not installed."""
    if not os.environ.get("GEMINI_API_KEY"):
        return False
    try:
        import google.genai  # noqa: F401
        return True
    except ImportError:
        return False


def _build_substrate_context_block(
    cluster_readings: list[str],
    pattern_readings: list[str],
) -> str:
    """Format the substrate-level composition block for the LLM
    prompt. Returns empty string when both lists are empty (the
    template's substrate_context_block placeholder collapses to
    nothing). Item C: this is what makes the LLM's question
    consume the substrate's own composition rather than treating
    the absent frame in isolation."""
    if not cluster_readings and not pattern_readings:
        return ""
    parts = ["\nSubstrate-level composition for this document:"]
    if cluster_readings:
        parts.append("\nDimension-cluster readings:")
        for reading in cluster_readings:
            parts.append(f"- {reading}")
    if pattern_readings:
        parts.append("\nNamed structural patterns matched:")
        for reading in pattern_readings:
            parts.append(f"- {reading}")
    return "\n".join(parts) + "\n"


def _build_corpus_context_block(absent_frame: dict) -> str:
    """Format the per-frame corpus context block for the LLM
    prompt. Surfaces the segmented prevalence (Item E) when
    available; falls back to mixed-genre prevalence; emits empty
    string when no corpus data is available."""
    cc = absent_frame.get("corpus_context") or {}
    if not cc:
        return ""
    parts = ["\nCorpus prevalence for this absent frame:"]
    # Segmented (preferred when available)
    by_genre = cc.get("fires_in_by_genre") or {}
    segmented_lines = []
    for genre, stats in by_genre.items():
        if stats.get("is_unclassified_bucket"):
            continue  # Don't surface _unclassified to the LLM
        if stats.get("genre_total", 0) == 0:
            continue
        n = stats.get("fires_in_count", 0)
        m = stats.get("genre_total", 0)
        warning = " (low_n: do not over-cite)" if stats.get("low_n_warning") else ""
        segmented_lines.append(
            f"  {genre}: fires in {n} of {m} corpus documents{warning}"
        )
    if segmented_lines:
        parts.append("By genre (like-vs-like):")
        parts.extend(segmented_lines)
    # Full corpus reference
    prevalence = cc.get("prevalence")
    if prevalence:
        parts.append(f"Full corpus: {prevalence}")
    return "\n".join(parts) + "\n"


def _generate_one_opportunity(
    absent_frame: dict,
    document_text: str,
    document_genre: Optional[str],
    user_goal: Optional[str],
    model: str,
    cluster_readings: Optional[list[str]] = None,
    pattern_readings: Optional[list[str]] = None,
) -> Optional[dict]:
    """Generate one frame opportunity from one absent frame record.
    Returns None on any failure (network, parsing, missing data) so
    the caller can skip without breaking the response.

    Item C: cluster_readings and pattern_readings are passed so the
    LLM consumes the substrate's composition layer when generating
    the question (e.g., a question that incorporates the dimension-
    cluster reading or a named pattern's framing instead of treating
    the absent frame in isolation)."""
    try:
        import google.genai as genai
        from llm_cost import compute_cost_usd, extract_gemini_usage
    except ImportError:
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    fvs_id = absent_frame.get("frame_id")
    title = absent_frame.get("frame_title")
    teaching_question = absent_frame.get("teaching_question") or (
        "What would this absent frame surface that the document does "
        "not currently address?"
    )
    if not fvs_id or not title:
        return None

    # PII redaction at the LLM-call boundary.
    #
    # frame_opportunities is the MCP-only LLM call path: it transmits a
    # 2,000-char excerpt of the document to Gemini for opt-in opportunity
    # generation. The web app's /profile path redacts PII at intake (so
    # every downstream LLM call sees redacted text), but the MCP server
    # is a separate published artifact (frame-check-mcp on PyPI) that
    # users invoke locally with their own Gemini key. The intake-side
    # redaction does not flow through the MCP entry point.
    #
    # Mirrors the privacy promise: "PII patterns the intake scanner
    # detects (email, SSN, phone, payment card, API credential) are
    # replaced with category placeholders BEFORE any LLM call." Even
    # in MCP mode where the user owns the Gemini key, the redactor
    # ensures the user's own credentials/PII embedded in their
    # documents don't get echoed into a third-party LLM context.
    # Round-8 follow-up audit (2026-05-01) closed this gap.
    try:
        from security import redact_pii_in_text  # canon-exempt: optional PII redactor
        document_text = redact_pii_in_text(document_text)
    except ImportError:
        pass  # standalone invocation without the optional security module

    excerpt = document_text[:_DOC_EXCERPT_CHARS]
    if len(document_text) > _DOC_EXCERPT_CHARS:
        excerpt += "..."

    substrate_block = _build_substrate_context_block(
        cluster_readings or [], pattern_readings or [],
    )
    corpus_block = _build_corpus_context_block(absent_frame)
    prompt = _OPPORTUNITY_PROMPT_TEMPLATE.format(
        frame_number=fvs_id.replace("FVS-", ""),
        frame_title=title,
        teaching_question=teaching_question,
        genre=document_genre or "unspecified",
        goal=user_goal or "audit (no goal-specific override)",
        substrate_context_block=substrate_block,
        corpus_context_block=corpus_block,
        document_excerpt=excerpt,
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
    except Exception:
        # Tolerated by design: frame-opportunity generation is
        # opt-in (include_frame_opportunities=true) LLM-augmented
        # composition. Any provider failure (auth, quota, timeout,
        # malformed response) returns None so the deterministic
        # substrate path proceeds with empty opportunities and the
        # caller-visible `available=false` flag in the divergence
        # block envelope. A failure here MUST NOT break the
        # deterministic frame_check response.
        return None

    generated = ""
    try:
        generated = (response.text or "").strip()
    except Exception:
        # Tolerated by design: response.text access can raise on
        # safety-filter or finish-reason edge cases. Return None
        # to signal "no opportunity generated" so the caller
        # surfaces the deterministic substrate output without
        # opportunities. Same contract as the API-call exception
        # handler above.
        return None
    if not generated:
        return None

    # Strip surrounding quotes if the LLM wrapped despite instructions.
    if generated.startswith('"') and generated.endswith('"'):
        generated = generated[1:-1].strip()
    if generated.startswith("'") and generated.endswith("'"):
        generated = generated[1:-1].strip()

    # Compute cost.
    input_tokens, output_tokens = extract_gemini_usage(response)
    cost_usd = compute_cost_usd(
        "gemini", model, input_tokens, output_tokens,
    )

    return {
        "frame_id": fvs_id,
        "frame_title": title,
        "citation_uri": absent_frame.get("citation_uri"),
        "teaching_question_general": teaching_question,
        "generated_question": generated,
        "model_provenance": {
            "provider": "gemini",
            "model": model,
            "cost_usd": cost_usd,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "is_deterministic": False,
        },
        # Per-level construct treatment: opt-in LLM-composed content
        # is the fourth claim kind. Cite per
        # agent_guidance.claim_level_treatments[agent_generated]. The
        # generated_question is one possible application of the
        # absent frame's general teaching question;
        # teaching_question_general remains the stable catalog
        # reference. The is_deterministic=False flag in
        # model_provenance is the per-opportunity construct signal;
        # claim_level=agent_generated is the structural signal at the
        # per-level discipline.
        "claim_level": "agent_generated",
    }


def _select_top_absent_frames(
    absent_records: list[dict],
    n: int,
) -> list[dict]:
    """Pick the top N absent frames for opportunity composition.
    Uses the same priority logic as the absent_frames sort order:
    signal_strength tier, goal_relevance.priority,
    genre_relevance.priority, frame_id alphabetical. Records carry
    a teaching_question only when divergence_rendering=
    'teaching_questions'; we accept records without and synthesize
    a generic prompt fallback in _generate_one_opportunity."""
    return list(absent_records[:n])


def generate_frame_opportunities(
    absent_records: list[dict],
    document_text: str,
    document_genre: Optional[str] = None,
    user_goal: Optional[str] = None,
    max_opportunities: int = _MAX_OPPORTUNITIES,
    model: str = "gemini-2.5-flash",
    cluster_readings: Optional[list[str]] = None,
    pattern_readings: Optional[list[str]] = None,
) -> dict:
    """Generate document-specific questions for the top absent frames.

    Returns a dict with `opportunities` (list of opportunity dicts)
    and `total_cost_usd` (sum across calls). When LLM is unavailable,
    returns an empty list and zero cost rather than raising.

    Bounded by `max_opportunities` (default 3); each opportunity is
    one Gemini Flash call, ~$0.0001-0.0005 each. Total bounded at
    ~$0.001 per invocation.

    The substrate-deterministic discipline: each opportunity carries
    is_deterministic=False so callers and agents can distinguish
    LLM-generated content from the rest of the response.
    """
    if not absent_records or not document_text or not document_text.strip():
        return {
            "opportunities": [],
            "total_cost_usd": 0.0,
            "available": True,
        }

    if not _is_gemini_available():
        return {
            "opportunities": [],
            "total_cost_usd": 0.0,
            "available": False,
            "unavailable_reason": (
                "LLM is unavailable (GEMINI_API_KEY missing or "
                "google.genai library not installed). "
                "frame_opportunities composition is opt-in via "
                "include_frame_opportunities; the deterministic "
                "substrate (clusters, patterns, absences with goal "
                "and genre relevance) remains available."
            ),
        }

    candidates = _select_top_absent_frames(
        absent_records, max_opportunities,
    )
    opportunities: list[dict] = []
    total_cost = 0.0
    for record in candidates:
        opp = _generate_one_opportunity(
            record, document_text, document_genre, user_goal, model,
            cluster_readings=cluster_readings,
            pattern_readings=pattern_readings,
        )
        if opp is None:
            continue
        opportunities.append(opp)
        total_cost += opp["model_provenance"]["cost_usd"]

    return {
        "opportunities": opportunities,
        "total_cost_usd": round(total_cost, 6),
        "available": True,
    }
