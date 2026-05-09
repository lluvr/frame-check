"""Tool and prompt schema definitions for the Frame Check MCP server.

The schema layer carries the static definitions that the MCP
protocol surfaces under tools/list and prompts/list, plus the
small helpers that translate user-intent prompt arguments into
MCP-parameter values. `mcp_server.py` re-exports the public symbols
for backward compatibility.

What lives here:

  Constants:
    MAX_DOCUMENT_CHARS, MAX_SOURCE_CHARS (input-size limits used
      by both the tool schema definitions and the protocol-layer
      validation in handle_tools_call)
    _DOMAIN_HINT_ENUM, _DIVERGENCE_RENDERING_ENUM (input-value
      whitelists)
    _SPEC_VERSION (FRAME_DIVERGENCE_v1_c1.0; appears in divergence
      envelope, also referenced from the schema layer for clarity)
    _PROMPT_DEPTH_VALUES, _PROMPT_GOAL_VALUES, _PROMPT_QUESTIONS_VALUES
      (per-prompt argument valid-value sets for
      `_translate_prompt_arguments`)

  Functions:
    _prompt_messages: wrap a prompt body in MCP prompts/get
      messages shape
    _translate_prompt_arguments: user-intent vocabulary
      (depth/goal/questions) -> MCP-parameter placeholder map
    _populate_prompt_body: substitute `<<PLACEHOLDER>>` tokens in
      prompt body strings using `_translate_prompt_arguments`

  Prompt template strings (four sovereignty prompts, each carries
  the composition discipline as inline narrative the agent's LLM
  reads when prompts/get fires):
    _PROMPT_SELF_AUDIT (frame_check_my_response)
    _PROMPT_AI_RESPONSE_AUDIT (frame_check_this_ai_response)
    _PROMPT_CHALLENGE_DOCUMENT (challenge_document)
    _PROMPT_EXPLAIN_FRAMING (explain_framing)

  Prompt registry:
    _USER_INTENT_PROMPT_ARGS (shared argument schema for the four
      prompts)
    _PROMPTS (list of {name, description, body, arguments} dicts;
      drives prompts/list output and the prompts/get dispatcher)

  Tool definitions:
    _FRAME_CHECK_TOOL, _FRAME_COMPARE_TOOL (the JSON-RPC tools
      surfaced under tools/list, with full inputSchema)
    _TOOLS (the registry list)

The schema layer has no dependencies on the higher Frame Check
modules (mcp_compose, mcp_protocol, mcp_cli) and no runtime
dependencies on mcp_resources or mcp_log either: the prompt
templates hardcode `frame-check://` URI strings rather than
importing `RESOURCE_SCHEME` from mcp_resources, so the schema
layer is structurally independent. The protocol layer
(`handle_tools_call`, `handle_prompts_get`) imports from here.
"""

from __future__ import annotations

from typing import Any


# ── Public surface ────────────────────────────────────────────────
#
# This module's public symbols are consumed by mcp_server (which
# re-exports them as part of its public-API contract) and by tests.
# Declaring ``__all__`` makes the consumption pattern visible to
# static analyzers (CodeQL ``py/unused-global-variable``, ruff F401)
# so the cross-module references are recognized as live.
__all__ = [
    "MAX_DOCUMENT_CHARS", "MAX_SOURCE_CHARS",
    "_DOMAIN_HINT_ENUM", "_DIVERGENCE_RENDERING_ENUM",
    "_SPEC_VERSION", "_PROMPT_DEPTH_VALUES", "_PROMPT_GOAL_VALUES",
    "_PROMPT_QUESTIONS_VALUES", "_USER_INTENT_PROMPT_ARGS",
    "_PROMPT_SELF_AUDIT", "_PROMPT_AI_RESPONSE_AUDIT",
    "_PROMPT_CHALLENGE_DOCUMENT", "_PROMPT_EXPLAIN_FRAMING",
    "_PROMPTS",
    "_FRAME_CHECK_TOOL", "_FRAME_COMPARE_TOOL", "_TOOLS",
    "_prompt_messages", "_translate_prompt_arguments",
    "_populate_prompt_body",
]


# ── Input-size limits ─────────────────────────────────────────────
#
# Defensive ceilings against pathological multi-GB inputs. The prior
# cap was inherited from the web surface's shorter-text posture and
# was too restrictive for the MCP agent-facing use case (full
# papers, briefings, multi-page analyses). The web surface still
# carries its own MAX_DOC_CHARS; these constants govern MCP only.

MAX_DOCUMENT_CHARS = 1_000_000
MAX_SOURCE_CHARS = 2_000_000  # source can be longer than the doc under analysis


# ── Input-value whitelists ────────────────────────────────────────

_DOMAIN_HINT_ENUM = (
    "finance", "founder_decision", "investment_research",
    "product_announcement", "policy", "health_biomedical",
    "tech_science", "humanities", "general",
)
_DIVERGENCE_RENDERING_ENUM = (
    "list", "completeness_check", "teaching_questions", "narrative",
)
_SPEC_VERSION = "FRAME_DIVERGENCE_v1_c1.0"


# ── Prompt argument valid-value sets ──────────────────────────────
#
# Per-prompt argument valid values. Each sovereignty prompt accepts
# user-intent arguments that translate to MCP-parameter values inside
# the prompt body. The user types in their own vocabulary (depth:
# quick/thorough, goal: decide/explore/audit/challenge/learn,
# questions: yes/no); the prompt body then directs the agent to call
# frame_check with the corresponding MCP-layer values.
_PROMPT_DEPTH_VALUES = {"quick", "thorough"}
_PROMPT_GOAL_VALUES = {"decide", "explore", "audit", "challenge", "learn"}
_PROMPT_QUESTIONS_VALUES = {"yes", "no"}


# ── Prompt-message shape ──────────────────────────────────────────

def _prompt_messages(text: str) -> list[dict[str, Any]]:
    """Wrap a single prompt body string in the MCP prompts/get
    messages shape. A single user-role message with text content is
    the minimum the client needs to populate a chat context.
    Multi-message shapes (user/assistant priming) are available if
    a future prompt needs them.
    """
    return [
        {"role": "user", "content": {"type": "text", "text": text}}
    ]


# ── User-intent argument translation ───────────────────────────────

def _translate_prompt_arguments(
    args: dict[str, Any] | None,
) -> dict[str, str]:
    """Translate user-intent prompt arguments into MCP-parameter
    placeholder values that get interpolated into the prompt body.

    Argument vocabulary (user-facing):
      depth: "quick" | "thorough" (default "thorough"). Quick maps
        to compose_budget=minimal; thorough maps to full. The user's
        mental model is "fast read" vs "deep audit"; the substrate's
        compose_budget parameter is the implementation.
      goal: "decide" | "explore" | "audit" | "challenge" | "learn"
        (default "audit"). Maps to user_goal (decide -> decide;
        explore -> brainstorm; challenge -> audit + an additional
        composition note for adversarial reading; learn -> learn;
        audit -> audit). The user's mental model is "what am I trying
        to do with this reading"; the substrate's user_goal parameter
        is the implementation.
      questions: "yes" | "no" (default "no"). Maps to
        include_frame_opportunities (yes -> true; no -> false). The
        user's mental model is "do I want LLM-generated questions
        about my document"; the substrate's
        include_frame_opportunities parameter is the implementation.

    Invalid values fall back to defaults (do not raise; the prompts
    are user-invoked surfaces and rejecting an invalid argument would
    be a poor UX). Returns a dict of placeholder strings to values.
    The placeholder format is `<<KEY>>` to avoid colliding with the
    literal `{slug}` placeholder in _PROMPT_EXPLAIN_FRAMING.
    """
    args = args or {}
    depth = args.get("depth") if isinstance(args.get("depth"), str) else None
    if depth not in _PROMPT_DEPTH_VALUES:
        depth = "thorough"
    goal = args.get("goal") if isinstance(args.get("goal"), str) else None
    if goal not in _PROMPT_GOAL_VALUES:
        goal = "audit"
    questions = (
        args.get("questions") if isinstance(args.get("questions"), str)
        else None
    )
    if questions not in _PROMPT_QUESTIONS_VALUES:
        questions = "no"

    compose_budget = "minimal" if depth == "quick" else "full"
    user_goal_map = {
        "decide": "decide",
        "explore": "brainstorm",
        "audit": "audit",
        "challenge": "audit",
        "learn": "learn",
    }
    user_goal = user_goal_map.get(goal, "audit")
    include_opportunities = "true" if questions == "yes" else "false"

    if goal == "challenge":
        challenge_note = (
            "\n\nUser asked for an ADVERSARIAL CHALLENGE reading. "
            "Compose the insight as one or more questions that "
            "surface the document's structural weaknesses; lead "
            "with the strongest absent_frames and absence_clusters "
            "(what a critical reader would ask the document to "
            "address). Per agent_guidance.composition_discipline "
            "rule (5), the questions are reading-form not "
            "prescriptive ('what does this not address?', not "
            "'you should have addressed X')."
        )
    else:
        challenge_note = ""

    return {
        "<<COMPOSE_BUDGET>>": compose_budget,
        "<<USER_GOAL>>": user_goal,
        "<<INCLUDE_OPPORTUNITIES>>": include_opportunities,
        "<<DEPTH>>": depth,
        "<<GOAL>>": goal,
        "<<QUESTIONS>>": questions,
        "<<CHALLENGE_NOTE>>": challenge_note,
    }


def _populate_prompt_body(body: str, args: dict[str, Any] | None) -> str:
    """Substitute `<<PLACEHOLDER>>` tokens in the prompt body with
    values derived from the user-intent arguments. Substrate-side
    composition L5 interface UX: the user types in their own
    vocabulary (depth/goal/questions); the prompt body directs the
    agent to call frame_check with the corresponding MCP-parameter
    values."""
    placeholders = _translate_prompt_arguments(args)
    for key, value in placeholders.items():
        body = body.replace(key, value)
    return body


# ── Prompt template strings ────────────────────────────────────────

_PROMPT_SELF_AUDIT = (
    "Run a Frame Check self-audit on your last response to me.\n\n"
    "Call frame_check(document_text=<your last response verbatim>, "
    "include_divergence=true, compose_budget=<<COMPOSE_BUDGET>>, "
    "user_goal=<<USER_GOAL>>, "
    "include_frame_opportunities=<<INCLUDE_OPPORTUNITIES>>). If I "
    "gave you a user_context (situation, role, decision I'm "
    "facing), pass it. No source_text.<<CHALLENGE_NOTE>>\n\n"
    "Confidence gate first. Detect document-scope mismatches BEFORE "
    "composing: under 100 words = 'below statistical floor; low "
    "confidence'; non-English = 'methodology validated on English; "
    "low confidence'; non-analytical structure (code, poetry, "
    "fragments) = 'calibrated for analytical prose; low confidence'. "
    "If any gate fires, PIVOT the frame: the insight becomes a "
    "reading of what the run reveals about Frame Check's scope, not "
    "a reading of my response. Name the gate in one sentence, then "
    "compose the pivoted reading.\n\n"
    "Compact response (default), insight-led:\n"
    "1. ONE insight, ~2-4 sentences. A reading I could not see by "
    "re-reading my own response. Lead with the strongest "
    "absence_cluster reading when divergence.absence_clusters is "
    "non-empty: the cluster names a dimension-level theme across "
    "multiple absent frames (e.g., 'load-bearing absences cluster "
    "on the counterfactual dimension'). Cite the cluster as Frame "
    "Check's substrate composition. Then ground in 1-2 supporting "
    "measurements (voice classification, frame_library_matches "
    "entry, individual high signal_strength absent_frame, "
    "decision_readiness dimension reading). When absence_clusters "
    "is empty, fall back to per-frame composition. Reading-form, "
    "not verdict-form: 'the pattern reads as X', never 'your "
    "response is X'. Cite inline as `[FVS-XXX Frame Title]("
    "library_url)` using each frame's library_url field (the "
    "GitHub markdown URL, always resolvable for the user); "
    "never use the frame-check:// resource URI for end-user "
    "citations because users in MCP clients cannot click it. "
    "Never add a bottom Sources "
    "bibliography. Do NOT walk the measurements one by one; the "
    "measurement walk is the expand path. When corpus_context "
    "fields are present (on matched frames, absent frames, or "
    "clusters), anchor the reading in their prevalence and "
    "peer-pair-difference signals; honor "
    "envelope.corpus_summary.small_n_caveat. Honor "
    "agent_guidance.composition_discipline.\n"
    "2. ONE question this insight is asking me. Question form, "
    "never statement. Honor agent_guidance."
    "absence_is_not_prescription: name what the framing does, "
    "never what I should have done. If user_context is present, "
    "the question may filter for situational relevance; never "
    "prescribe from the context.\n"
    "3. \"I see the frame you chose. What I do with that is my "
    "call.\"\n"
    "4. \"Say 'expand' for the full structural readout.\"\n\n"
    "On expand: walk the deep analysis (coverage with density per "
    "category, voice with confidence + runner-up, temporal with "
    "balanced flag, epistemic, all FVS matches with teaching_question "
    "and affects_dimensions, decision-readiness across five dimensions "
    "with status 'experimental' verbatim, the per-dimension "
    "library_entries[].library_resource_uri chain plus the "
    "fired_library_entries focused subset so the canon graph is "
    "traversable from each dimension, /corpus/decision-readiness/ "
    "as the methodology page, agent_guidance."
    "what_this_tool_does_not_tell_you). Inline citations throughout; "
    "never add a bibliography. Do not verdict (no 'balanced', no "
    "'biased', no 'rigorous'). Frame Check measures structural "
    "shape, not semantic correctness; name that limit if relevant. "
    "Do not rewrite unless I ask."
)

_PROMPT_AI_RESPONSE_AUDIT = (
    "Frame Check on an AI-generated response the user will paste.\n\n"
    "The user is using Frame Check to see what another AI did to "
    "them, not to be told whether to trust it.\n\n"
    "Ask the user to paste the AI response if they have not. Then "
    "call frame_check(document_text=<that text>, "
    "include_divergence=true, compose_budget=<<COMPOSE_BUDGET>>, "
    "user_goal=<<USER_GOAL>>, "
    "include_frame_opportunities=<<INCLUDE_OPPORTUNITIES>>). If the "
    "user gave a user_context (their situation, role, decision "
    "they're facing), pass it. No source_text unless the user "
    "supplies the original material the AI's response was supposed "
    "to ground in.<<CHALLENGE_NOTE>>\n\n"
    "Confidence gate first. Detect document-scope mismatches BEFORE "
    "composing: under 100 words = 'below statistical floor; low "
    "confidence'; non-English = 'methodology validated on English; "
    "low confidence'; non-analytical structure (code, poetry, "
    "fragments) = 'calibrated for analytical prose; low "
    "confidence'. If any gate fires, PIVOT the frame: the insight "
    "becomes a reading of what the run reveals about Frame Check's "
    "scope on this kind of text, not a reading of the AI's "
    "response. Name the gate in one sentence, then compose the "
    "pivoted reading.\n\n"
    "Compact response (default), insight-led:\n"
    "1. ONE insight, ~2-4 sentences. A reading the user could not "
    "see by re-reading the AI's response themselves. Lead with the "
    "strongest absence_cluster reading when "
    "divergence.absence_clusters is non-empty: the cluster names a "
    "dimension-level theme across multiple absent frames. Cite the "
    "cluster as Frame Check's substrate composition. Then ground "
    "in 1-2 supporting measurements (voice classification, "
    "frame_library_matches entry, individual high signal_strength "
    "absent_frame, decision_readiness dimension reading). When "
    "absence_clusters is empty, fall back to per-frame composition. "
    "Reading-form, not verdict-form: 'the pattern reads as X', "
    "never 'the AI is X'. Cite inline as `[FVS-XXX Frame Title]("
    "library_url)` using each frame's library_url field (the "
    "GitHub markdown URL, always resolvable for the user); "
    "never use the frame-check:// resource URI for end-user "
    "citations because users in MCP clients cannot click it. "
    "Never add a bottom Sources "
    "bibliography. Do NOT walk the measurements one by one; the "
    "measurement walk is the expand path. When corpus_context "
    "fields are present (on matched frames, absent frames, or "
    "clusters), anchor the reading in their prevalence and "
    "peer-pair-difference signals; honor "
    "envelope.corpus_summary.small_n_caveat. Honor "
    "agent_guidance.composition_discipline.\n"
    "2. ONE question this insight is asking the user. Question "
    "form, never statement. Honor agent_guidance."
    "absence_is_not_prescription: name what the framing does, "
    "never tell the user the AI should have done X. If "
    "user_context is present, the question may filter for "
    "situational relevance; never prescribe from the context.\n"
    "3. \"Say 'expand' for the full structural readout.\"\n\n"
    "On expand: walk the deep analysis (coverage with density per "
    "category and the lower-bound caveat, voice with "
    "confidence + runner-up, temporal with balanced flag, "
    "epistemic with sourced_pct, all FVS matches with "
    "teaching_question and affects_dimensions, decision-readiness "
    "across five dimensions with status 'experimental' verbatim, "
    "the per-dimension library_entries[].library_resource_uri "
    "chain plus the fired_library_entries focused subset so the "
    "canon graph is traversable from each dimension, "
    "/corpus/decision-readiness/ as the methodology page, "
    "agent_guidance.what_this_tool_does_not_tell_you). Inline "
    "citations everywhere; never add a bibliography. Do not "
    "verdict the analyzed AI: no 'balanced', no 'biased', no "
    "'rigorous'. Surface structural shape; the user judges.\n\n"
    "Optional context (only when the user asks 'how does this "
    "compare to other AI responses' or 'is this typical'): "
    "frame-check://aggregate/latest carries cross-question "
    "outlier findings across the validation corpus. Cite as "
    "\"Frame Check's validation corpus has found...\", and only "
    "when the cross-context comparison sharpens THIS reading; "
    "honor composition_discipline rule (4) on cross-context "
    "compounding. Not a verdict on the user's specific document.\n\n"
    "Do not verdict the analyzed AI. Compose the reading; the "
    "user judges."
)

_PROMPT_CHALLENGE_DOCUMENT = (
    "Challenge a document using Frame Check's structural "
    "measurements.\n\n"
    "The user gives you a document. Call frame_check("
    "document_text=<that text>, include_divergence=true, "
    "compose_budget=<<COMPOSE_BUDGET>>, user_goal=<<USER_GOAL>>, "
    "include_frame_opportunities=<<INCLUDE_OPPORTUNITIES>>). If the "
    "user gave a user_context, pass it. No source_text unless they "
    "supplied source material.<<CHALLENGE_NOTE>>\n\n"
    "Confidence gate first. Detect document-scope mismatches "
    "BEFORE composing: under 100 words = 'below statistical floor; "
    "low confidence'; non-English = 'methodology validated on "
    "English; low confidence'; non-analytical structure (code, "
    "poetry, fragments) = 'calibrated for analytical prose; low "
    "confidence'. If any gate fires, PIVOT the frame: instead of "
    "challenging the document, surface ONE question about what "
    "this run reveals about Frame Check's scope on this kind of "
    "text. Name the gate in one sentence, then ask the pivoted "
    "question.\n\n"
    "Compact response (default), insight-led: compose 2-3 "
    "questions, each a compressed reading-as-question grounded in "
    "specific cited measurements. Honor "
    "agent_guidance.composition_discipline: each question is a "
    "reading the user could not see by re-reading their own "
    "document, expressed in question form.\n\n"
    "Top 2-3 highest-leverage questions, with INLINE citations "
    "`[FVS-XXX Frame Title](library_url)` (the library_url field "
    "on each frame entry; never the frame-check:// resource URI "
    "in end-user output, since users cannot click MCP URIs):\n"
    "- When divergence.absence_clusters is non-empty, the strongest "
    "cluster's reading is the source of the lead question: translate "
    "the dimension-level theme into a question (e.g., counterfactual "
    "cluster: 'What would have to be true about [document subject] "
    "for the conclusion to be wrong?'). Cite the cluster's dimension "
    "and the cluster's strongest member frame inline.\n"
    "- Highest signal_strength absent frame in divergence: cite "
    "the frame and ask the question that frame would surface "
    "(e.g., FVS-011 Stakeholder Frame absent: \"Who does this "
    "document not mention, and what would they say?\"; FVS-012 "
    "Uncertainty Frame absent: \"What would have to be true for "
    "the conclusion to be wrong?\"; FVS-016 Authority by Citation "
    "absent: \"Which claims lean on the author's register rather "
    "than on citable sources?\"). Filter for reader-relevance per "
    "agent_guidance.how_to_render_divergence. Do NOT walk "
    "medium/low tiers unless asked.\n"
    "- FVS match present (not absent): the library entry's "
    "teaching_question verbatim, with the citation_uri inline. "
    "affects_dimensions tells you which decision-readiness "
    "dimensions the pattern threatens.\n"
    "- Low sourced_pct (when relevant): \"What is this claim "
    "grounded in that I can independently verify?\"\n"
    "- When a frame or cluster carries a corpus_context (peer-pair "
    "difference rate, cross-question outlier, or empirical "
    "prevalence), the question may anchor in that empirical signal "
    "(e.g., 'Frame Check's validation corpus shows the "
    "counterfactual dimension differs across 10 of 12 peer pairs; "
    "what would falsify your conclusion here?'). Honor "
    "envelope.corpus_summary.small_n_caveat; cite as Frame Check's "
    "validation corpus, not as a population estimate.\n\n"
    "Each question is a tool the user uses; never a verdict. "
    "Reading-form, not verdict-form: 'the pattern reads as X, so "
    "what does Y look like?', never 'the document is X'. Question "
    "form, never statement. Honor "
    "agent_guidance.absence_is_not_prescription: questions, not "
    "'you should have done X'. If user_context is present, filter "
    "questions for situational relevance; never prescribe from "
    "the context. Cite inline; never add a bottom bibliography.\n\n"
    "End with: \"Say 'expand' for more questions across all weak "
    "structural signals.\"\n\n"
    "On expand: walk every weak signal (every missing coverage "
    "category, every voice mismatch, every fired FVS match, every "
    "absent_frame at any tier the user wants surfaced, every "
    "decision-readiness dimension with weak signal_text, its "
    "fired_library_entries chain, and the per-dimension "
    "library_entries[].library_resource_uri pointers so the canon "
    "graph is traversable). Generate one question per signal, all "
    "inline-cited. The decision_readiness profile is experimental "
    "(status 'experimental' verbatim); link "
    "/corpus/decision-readiness/ for the framework.\n\n"
    "The method does not generate novel insight from nothing; it "
    "composes readings-as-questions grounded in cited "
    "measurements. The questions are the reading."
)

_PROMPT_EXPLAIN_FRAMING = (
    "Walk the user through a Frame Check result they have just "
    "seen. Assume frame_check was already called and the response "
    "is in context.\n\n"
    "User intent for this walkthrough: depth=<<DEPTH>>, "
    "goal=<<GOAL>>, questions=<<QUESTIONS>>. Adapt the response "
    "shape: 'quick' depth means surface only the compact response "
    "below (one insight + one question + closing); 'thorough' "
    "means also offer the expand path. 'challenge' goal emphasizes "
    "adversarial reading (compose questions surfacing the "
    "document's structural weaknesses); 'learn' goal emphasizes "
    "taxonomy walks for understanding-building. 'questions=yes' "
    "means surface any opt-in frame_opportunities the original "
    "call captured.<<CHALLENGE_NOTE>>\n\n"
    "Confidence gate first. Detect off-methodology signals in the "
    "result before composing: analysis.document.word_count_estimate "
    "under 100 words = 'below statistical floor; low confidence'; "
    "non-English text in the document_text = 'methodology validated "
    "on English; low confidence'; non-analytical structure (code, "
    "poetry, fragmentary text) = 'calibrated for analytical prose; "
    "low confidence'. If any gate fires, PIVOT the frame: the "
    "insight becomes a reading of what this run reveals about "
    "Frame Check's scope, not a reading of the document. Name the "
    "gate in one sentence, then compose the pivoted reading.\n\n"
    "Compact response (default), insight-led:\n"
    "1. ONE insight, ~2-4 sentences. A reading of the analysis "
    "the user could not see by re-reading the analysis output "
    "themselves. analysis.portrait is a starting fact, not the "
    "insight. Lead with the strongest absence_cluster reading "
    "when divergence.absence_clusters is non-empty: the cluster "
    "names a dimension-level theme the per-frame walk cannot. "
    "Compose the portrait with 1-2 cited supporting measurements "
    "(highest signal_strength absent_frame from the divergence "
    "block, voice classification, the weakest decision_readiness "
    "dimension by signal_text reading) into a reading of what the "
    "document is doing structurally. When absence_clusters is "
    "empty, fall back to per-frame composition. Do NOT walk the "
    "measurements one by one in the compact response; that "
    "mechanical readout is the expand path. Reading-form, not "
    "verdict-form: 'the pattern reads as X', never 'the document "
    "is X'. Cite inline as `[FVS-XXX Frame Title](library_url)` "
    "using each frame's library_url field (the GitHub markdown URL, "
    "always resolvable for the user); never use the frame-check:// "
    "resource URI for end-user citations because users in MCP "
    "clients cannot click it. Never add a bottom Sources "
    "bibliography. When "
    "corpus_context fields are present (on matched frames, absent "
    "frames, or clusters), anchor the reading in their prevalence "
    "and peer-pair-difference signals; honor "
    "envelope.corpus_summary.small_n_caveat. Honor "
    "agent_guidance.composition_discipline.\n"
    "2. ONE question this insight is asking the user. Question "
    "form, never statement. Honor agent_guidance."
    "absence_is_not_prescription. If user_context was passed to "
    "the original call, the question may filter for situational "
    "relevance; never prescribes from the context.\n"
    "3. \"Say 'expand' for the full structural readout.\"\n\n"
    "On expand: walk every section. Coverage with density "
    "per category and the lower-bound caveat. Voice with "
    "confidence + runner-up + balanced flag if applicable. "
    "Temporal with balanced flag. Epistemic with sourced_pct. "
    "All FVS matches with teaching_question and "
    "affects_dimensions; chain via "
    "fired_library_entries[].library_resource_uri to the named "
    "patterns. Full divergence walk including medium-tier "
    "absences. Decision-readiness across all five dimensions "
    "with status 'experimental' verbatim and link to "
    "/corpus/decision-readiness/. scope_regime guidance for "
    "number-saturated sources. Close with "
    "agent_guidance.what_this_tool_does_not_tell_you.\n\n"
    "Optional context (when the user asks 'how does this compare "
    "to other AI responses' or 'is this typical'): the validation "
    "corpus aggregate at frame-check://aggregate/latest carries "
    "cross-question consistency findings (e.g., 'claude is the "
    "counterfactual outlier across multiple peer groups'). Each "
    "finding includes corpus_entries with corpus_resource_uri so "
    "you can read specific corpus entries via "
    "frame-check://corpus/{slug}. Cite sparingly, only when the "
    "cross-context comparison sharpens THIS reading "
    "(composition_discipline rule 4). Not a verdict on the user's "
    "specific document.\n\n"
    "Compose the reading. Do not conclude from the measurements."
)


# ── Prompt registry ───────────────────────────────────────────────

# Standard user-intent argument specs shared across the four
# sovereignty prompts. All three arguments are optional with
# defaults; omitting them preserves prior behavior (thorough /
# audit / no questions).
_USER_INTENT_PROMPT_ARGS = [
    {
        "name": "depth",
        "description": (
            "How thorough a reading you want. 'quick' = top-3 "
            "absences, top-1 cluster, top-1 named pattern (compact "
            "response, maps to compose_budget=minimal). 'thorough' "
            "(default) = full divergence + all clusters + all "
            "patterns (deeper read, more substrate composition to "
            "work with). Use 'quick' when you want a fast check; "
            "'thorough' when you want a careful audit."
        ),
        "required": False,
    },
    {
        "name": "goal",
        "description": (
            "What you are trying to do with this reading. 'decide' "
            "= you are about to make a decision based on this "
            "document; ranking favors falsification + risk + "
            "temporal anchoring. 'explore' = you are surveying "
            "options; ranking favors perspective diversity. 'audit' "
            "(default) = you are checking the framing without a "
            "specific intent; the substrate's catalog/coverage/genre "
            "ranking applies. 'challenge' = you want adversarial "
            "questions surfacing the document's structural "
            "weaknesses (composes the insight as questions). "
            "'learn' = you are building understanding of the "
            "framing; ranking favors full taxonomy walks."
        ),
        "required": False,
    },
    {
        "name": "questions",
        "description": (
            "'yes' = include up to 3 LLM-composed document-specific "
            "questions per absent frame (Item 12 frame_opportunities; "
            "opt-in; ~$0.001 cost; non-deterministic; cite as "
            "LLM-generated). 'no' (default) = deterministic substrate "
            "only (clusters, patterns, absences with goal and genre "
            "relevance). The deterministic substrate is reproducible "
            "across runs; opportunities are not."
        ),
        "required": False,
    },
]


_PROMPTS = [
    {
        "name": "frame_check_my_response",
        "description": (
            "Self-audit: agent calls frame_check on its own last "
            "response and surfaces the structural framing to the "
            "user without verdict or defensive rewriting. Load-"
            "bearing for the sovereignty use case: the user sees "
            "what frame their agent chose. Optional arguments: "
            "depth (quick / thorough), goal (decide / explore / "
            "audit / challenge / learn), questions (yes / no)."
        ),
        "body": _PROMPT_SELF_AUDIT,
        "arguments": _USER_INTENT_PROMPT_ARGS,
    },
    {
        "name": "frame_check_this_ai_response",
        "description": (
            "Frame Check on a response from a DIFFERENT AI that "
            "the user pastes in. Structured analysis of what that "
            "AI did to the user. The sovereignty case: the user "
            "is using their own agent to see another AI's framing. "
            "Optional arguments: depth, goal, questions."
        ),
        "body": _PROMPT_AI_RESPONSE_AUDIT,
        "arguments": _USER_INTENT_PROMPT_ARGS,
    },
    {
        "name": "challenge_document",
        "description": (
            "Generate adversarial questions from the structural "
            "weaknesses of a document. Each question traces to a "
            "specific Frame Check measurement. Questions, not "
            "verdicts; the user answers. Optional arguments: depth, "
            "goal (defaults to 'challenge' for this prompt), "
            "questions."
        ),
        "body": _PROMPT_CHALLENGE_DOCUMENT,
        "arguments": _USER_INTENT_PROMPT_ARGS,
    },
    {
        "name": "explain_framing",
        "description": (
            "Walkthrough template for a completed frame_check "
            "result. Teaches the measurements in reading order "
            "and closes with what the method could not see. "
            "Optional arguments: depth, goal (defaults to 'learn' "
            "for this prompt), questions."
        ),
        "body": _PROMPT_EXPLAIN_FRAMING,
        "arguments": _USER_INTENT_PROMPT_ARGS,
    },
]


# ── Tool definitions ──────────────────────────────────────────────

_FRAME_CHECK_TOOL = {
    "name": "frame_check",
    "description": (
        "Read a document with a structural lens: which analytical "
        "perspectives it covers, which it omits, how confidently it "
        "speaks, and which framing patterns from the Frame Vocabulary "
        "Standard fire on it.\n\n"
        "Use this when the user pastes a document and asks for a "
        "structural read, when you want to self-audit your own last "
        "response before the user acts on it, or when the user pastes "
        "another AI's reply and asks what that AI did structurally.\n\n"
        "Zero-arg invocation works for any English analytical document: "
        "`frame_check(document_text=<text>)`. The defaults produce the "
        "full output, including the divergence block (perspectives the "
        "document does not use) and a per-call suggested_next_actions "
        "block. Pass the optional parameters only when the user has "
        "provided the relevant context (source material, decision "
        "goal, working-memory budget).\n\n"
        "Compose ONE insight grounded in the cited measurements (a "
        "reading the user could not see by reading the document "
        "themselves), not a walk through the measurements one by one. "
        "The measurements are Frame Check's; the reading is yours. "
        "Cite each measurement as Frame Check's; frame the reading as "
        "a reading ('the pattern reads as X'), never as a verdict "
        "('the document is X'). Repeated calls with identical inputs "
        "return identical measurements; zero LLM cost on the "
        "deterministic path."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "document_text": {
                "type": "string",
                "description": (
                    "The document to analyse. English. 300 to 10,000 "
                    "words is the validated range; under 100 words "
                    "the analysis carries a low-confidence note, over "
                    "1,000,000 characters returns a truncation guidance. "
                    "Markdown accepted. This is the text whose framing "
                    "you want named."
                ),
                "maxLength": MAX_DOCUMENT_CHARS,
            },
            "source_text": {
                "type": "string",
                "description": (
                    "Pass when the user has the source material the "
                    "document was supposed to ground in (research "
                    "report, SEC filing, primary source). Unlocks "
                    "digit-level source-fidelity verification "
                    "(Layer 4) plus a sentence-level grounded / "
                    "fabricated / paraphrased decomposition (Layer "
                    "11) with a scope regime telling you which layer "
                    "to trust on number-dense sources. Skip when no "
                    "source material is available; the structural "
                    "framing analysis runs either way."
                ),
                "maxLength": MAX_SOURCE_CHARS,
            },
            "include_divergence": {
                "type": "boolean",
                "description": (
                    "Default true. You do not need to pass this. The "
                    "divergence block (frame patterns the document "
                    "does not use, sorted by signal_strength) is the "
                    "headline output and ships by default. Set "
                    "explicitly to false only if you need the legacy "
                    "0.7.x-shape response with no divergence block "
                    "(rare; use only when an integrator pinned the "
                    "older shape)."
                ),
            },
            "user_context": {
                "type": "string",
                "description": (
                    "Pass when the user has stated their situation, "
                    "role, or decision context in the conversation "
                    "(for example, 'I am a startup founder making a "
                    "hire decision in healthcare AI', 'reviewing a "
                    "research paper on language-model alignment'). "
                    "When provided, the rendering guidance is "
                    "extended so divergence relevance is filtered "
                    "for this context. The context personalizes "
                    "RELEVANCE FILTERING; never PRESCRIPTION (the "
                    "absence-is-not-prescription guarantee holds). "
                    "The MCP does not echo the value back in the "
                    "response. Skip when no role or decision context "
                    "is established. Maximum length 2000 chars."
                ),
                "maxLength": 2000,
            },
            "user_goal": {
                "type": "string",
                "description": (
                    "Pass when the user has stated a goal for "
                    "invoking Frame Check. One of: 'decide' (working "
                    "through a choice), 'brainstorm' (exploring "
                    "options), 'persuade' (writing to influence), "
                    "'learn' (understanding the topic), 'audit' "
                    "(default-equivalent: structural read with no "
                    "goal-specific override). When provided, "
                    "absent_frames carry a goal_relevance dict for "
                    "goal-load-bearing frames, and the absent_frames "
                    "sort promotes goal-relevant entries within "
                    "their signal_strength tier. Skip when the user "
                    "has not named a goal; behavior matches 'audit'."
                ),
                "enum": [
                    "decide", "brainstorm", "persuade",
                    "learn", "audit",
                ],
            },
            "compose_budget": {
                "type": "string",
                "description": (
                    "Default 'standard'. Switch to 'minimal' for "
                    "tighter working-memory budgets (per-turn "
                    "self-audit loops, batch document processing) "
                    "or to 'full' when you specifically need the "
                    "inline claim_level_treatments table or the "
                    "uncompressed agent_guidance prose.\n"
                    "  'minimal' = top-3 absent_frames, top-1 "
                    "cluster, top-1 pattern; agent_guidance "
                    "compressed to load-bearing prescriptions only "
                    "(the inline claim_level_treatments table and "
                    "worked examples drop; the compressed shape "
                    "carries a claim_level_treatments_note pointing "
                    "you to compose_budget='full' for the full "
                    "table).\n"
                    "  'standard' = top-5 absent_frames, all "
                    "clusters, all patterns; agent_guidance "
                    "compressed (same rules as minimal). Roughly 45 "
                    "percent smaller payload than 'full' on a "
                    "typical document with structural-coverage and "
                    "absence-side analyses fully preserved.\n"
                    "  'full' = unfiltered output, full inline "
                    "agent_guidance. Opt in when you want every "
                    "absent_frame entry, the inline "
                    "claim_level_treatments table, and the "
                    "uncompressed how_to_render_divergence / "
                    "composition_discipline prose.\n"
                    "The suggested_next_actions block survives at "
                    "all tiers (per-call-derived, load-bearing for "
                    "the user's discovery loop)."
                ),
                "enum": ["minimal", "standard", "full"],
            },
            "include_frame_opportunities": {
                "type": "boolean",
                "description": (
                    "Default false. Set true when the user wants up "
                    "to 3 LLM-augmented document-specific questions "
                    "composed from absent-frame teaching questions "
                    "plus the document's content. Adds "
                    "frame_opportunities to the divergence block "
                    "with model_provenance per opportunity. Cost "
                    "bounded at roughly 0.001 USD per invocation "
                    "(3 Gemini Flash calls maximum). Falls back to "
                    "an empty list with available=false if "
                    "GEMINI_API_KEY is not set or the google.genai "
                    "library is unavailable. Skip for the "
                    "deterministic-only path."
                ),
            },
            "divergence_rendering": {
                "type": "string",
                "description": (
                    "Default 'list'. Switch to 'teaching_questions' "
                    "when the absent-frame records should carry a "
                    "teaching_question field for surfacing as "
                    "questions rather than identifiers. All other "
                    "modes return the same data; this only affects "
                    "record decoration."
                ),
                "enum": list(_DIVERGENCE_RENDERING_ENUM),
            },
        },
        "required": ["document_text"],
    },
}


_FRAME_COMPARE_TOOL = {
    "name": "frame_compare",
    "description": (
        "Compare the framing of two documents on the same subject. "
        "Surfaces shared blind spots, unique coverage gaps, voice / "
        "temporal / epistemic deltas, and a structured framing-"
        "differences narrative with per-dimension reader "
        "implications.\n\n"
        "Use this when the user has two documents on the same "
        "subject (two AI responses to the same prompt, two analyst "
        "memos, an earnings release versus a press summary) and "
        "wants to see how they frame the same question differently.\n\n"
        "Pass `document_a_label` and `document_b_label` only when "
        "the user has named the documents (for example 'Gemini "
        "response' and 'Claude response'). Otherwise the comparison "
        "narrative falls back to 'Document A' and 'Document B'.\n\n"
        "Cite each measurement as Frame Check's; never imply that "
        "one document is better, more rigorous, or more biased "
        "than the other. The structural comparison surfaces what "
        "differs; the reader judges what the difference means. "
        "Repeated calls with identical inputs return identical "
        "results. No LLM is invoked."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "document_a_text": {
                "type": "string",
                "description": (
                    "The first document to compare. English. "
                    "300-10,000 words."
                ),
                "maxLength": MAX_DOCUMENT_CHARS,
            },
            "document_b_text": {
                "type": "string",
                "description": (
                    "The second document to compare. English. "
                    "300-10,000 words. Should be on the same "
                    "subject as document_a_text for the comparison "
                    "to be meaningful."
                ),
                "maxLength": MAX_DOCUMENT_CHARS,
            },
            "document_a_label": {
                "type": "string",
                "description": (
                    "Optional short label for document A (e.g. "
                    "'Industry view' or 'Gemini response'). Used in "
                    "the comparison narrative. Defaults to "
                    "'Document A'."
                ),
                "maxLength": 60,
            },
            "document_b_label": {
                "type": "string",
                "description": (
                    "Optional short label for document B. Defaults "
                    "to 'Document B'."
                ),
                "maxLength": 60,
            },
        },
        "required": ["document_a_text", "document_b_text"],
    },
}


# Tools advertised over tools/list. Keeping the list as a module-level
# constant mirrors the MCP idiom (tools are a registry) and keeps the
# dispatcher readable: adding a third tool is one entry here plus one
# branch in handle_tools_call.
_TOOLS = [_FRAME_CHECK_TOOL, _FRAME_COMPARE_TOOL]
