# Prompt Attribution Error

**FVS entry:** FVS-003
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** HI-054 (The Prompt Attribution Error), T-422 (The Four Layers), M-002 (The 60-Second Pause extending to fifth layer)
**Status:** v1, single-curator. Withdrawn from v1 publication per [INDEX.md](https://github.com/Clarethium/frame-check-mcp/blob/master/data/frame_library/INDEX.md) "v1 publication state" table (superseded by FVS-005, which carries the same four-layer attribution mechanism with broader scope). Source markdown preserved for citation continuity; the FVS-003 ID is reserved and will not be reused.

## Identification

When people say "Claude is thoughtful" or "Grok is direct" or "Gemini is cautious," they are attributing prompt effects to model identity. Four layers sit between the user and the output: the company's system prompt (invisible to the user), the user's accumulated context (custom instructions, memory, project files), the current prompt, and the model itself. The system prompt determines WHETHER a behavior occurs. The model determines HOW it manifests. Users see only the model and attribute everything to it.

**What this frame makes visible:**
- How model comparisons are confounded with system prompt differences (comparing Claude to Grok is comparing Anthropic's harness to xAI's harness as much as comparing models)
- Why assigning a persona or role in a prompt produces effects that feel like model properties (the persona IS a prompt-level intervention, not a model-level one)
- The leverage of prompt architecture over model selection (changing the system prompt often produces larger behavioral shifts than changing the model)

**What this frame makes invisible:**
- What the raw model can do in isolation from its harness (never observed by end users)
- The user's own accumulated context as a contributor to output quality (custom instructions, memory entries, project files all shape every response but the user rarely examines them as a system)
- When observed model differences are actually differences between company deployment choices, not model capabilities

**Positive examples:** A user compares Gemini and Claude on a market analysis task, finds Claude more nuanced, and concludes "Claude is better at analysis." In reality, Anthropic's system prompt may include instructions about considering multiple perspectives, while Google's system prompt may prioritize directness. The perceived analysis quality difference is (partly or entirely) a prompt difference, not a model difference.

**Negative examples:** A controlled experiment that strips system prompts and runs both models on the same input with the same context would NOT exhibit this error because the confound has been removed. The prompt attribution error requires the system prompt to be invisible.

**Adjacent frames:** System Attribution Error (HI-063, the broader version including the user's own system), Frame Amplification (FVS-001, what happens after the attributed-as-capable model locks into a frame), Fluency-Quality Illusion (FVS-002, the surface signal that makes the attribution feel justified)

**When this frame is appropriate:** Any time someone makes claims about what a model "is like" or "is good at" based on end-user interaction. Model selection decisions. AI procurement. Model comparisons in blog posts, reviews, social media. Any context where the user has not controlled for system prompt differences.

**When this frame is misleading:** When discussing capabilities that are genuinely model-specific (context window size, multilingual ability, specific domain training). Some properties ARE model properties. The error is in defaulting to model attribution when prompt attribution is more likely, not in claiming that models have no properties.

**Honest limits:** The Prompt Attribution Error is grounded in EXP-077/b (HI-054: "Prompt = WHETHER, Model = HOW"). The evidence is from controlled experiments comparing conditions within and across models. The magnitude of the attribution error in real user behavior (how much of perceived model difference is actually prompt difference) has not been measured in a population study. The claim is structurally sound but the practical impact on real procurement decisions is unmeasured.

## Generation affordances

**Rewrite prompt structure:** "Rewrite this comparison between AI models by separating observable behavior from attributed capability. For each claim ('Model X is good at Y'), restate as: 'When run with [prompt architecture], Model X produced [specific output]. This could reflect model capability, system prompt design, or interaction effects between them. To isolate model capability, the comparison would need to [specify what controlled test would be required].'"

**Counter-document prompt:** "This document attributes capabilities to AI models. Rewrite it from the perspective that every observed behavior is jointly produced by four layers (company harness, user context, current prompt, model) and that attributing to any single layer without controlling for the others is an attribution error. Name the specific confounds for each capability claim."

**Salient questions under this frame:**
- When I say "this model is good at X," have I controlled for the system prompt?
- Would the same model with a different system prompt produce different behavior?
- Is the behavior I value a model property or a deployment choice?
- Have I examined my own accumulated context (custom instructions, project files) as a contributor?

## Worked example

**Document excerpt:** "In our testing, Gemini demonstrated superior analytical reasoning on financial documents, producing more structured output with clearer section headings. Claude, by contrast, tended toward conversational analysis with more hedging and uncertainty language. For financial reporting tasks, we recommend Gemini."

**Frame present:** Model attribution. "Gemini demonstrated superior analytical reasoning" and "Claude tended toward conversational analysis" attribute behavior to the models.

**Frame absent:** Layer attribution. Google may have designed Gemini's system prompt to produce structured, heading-based output for analytical queries. Anthropic may have designed Claude's system prompt to include uncertainty hedging as a safety measure. The "superior reasoning" may be a heading format, not a reasoning improvement. The "conversational" tendency may be a safety guardrail, not a capability gap.

**How to read past it:** For each attributed capability, ask: "What would happen if I gave both models the exact same system prompt?" If the behavior persists, it is more likely model-specific. If it changes, it was prompt-specific. Most end users cannot run this test because system prompts are not exposed. Frame Check can detect the attribution pattern by identifying capability claims that lack controlled comparisons.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected when a document makes capability attributions to named AI models without naming the system prompt or comparing under controlled conditions. High assertion density about model properties with low epistemic sourcing is the detection signal.
**Branch B:** In the pre-commit intervention, the prompt attribution error surfaces when the user pre-commits "I think Claude will be better at this" and then sees a frame delta showing the observed difference may not be model-specific.

## Vocabulary connections

- **The four layers** (T-422, CLARETHIUM_VOCABULARY): the structural model. Wrapper (company system), context (user system), prompt (current), model. The attribution error is misattributing the wrapper or context layer's effects to the model layer.
- **The first read** (M-002, CLARETHIUM_VOCABULARY): M-002 extends the four layers to add a fifth (the body). The prompt attribution error is compounded by the first read: the body responds to the output's style (which is prompt-driven) as if it were evidence of the model's capability.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md. The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.990** (tier: **strong**), per fvs_eval/v4/library_v4_reliability.json. Per-corpus reproducible values (regen: fvs_eval/v4/compute_per_corpus_reliability.py; artifact: fvs_eval/v4/library_v4_per_corpus_reliability.json): MG_v3=1.0 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.945 (3-family partial; Anthropic queued). Historical: MG2_v1=0.98 (library_v1), MG2_v2=1.0 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md; rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **1.000** across n=41 docs at temp=0 (0 verdict flip(s); per fvs_eval/v4/grok_intra_rater_ac1.json). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/Clarethium/frame-check-mcp/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 1.000, kappa n/a, union 0/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): +0.00.
- **library_v2 (earlier variant):** Gwet's AC1 1.000, kappa n/a, union 0/15.

See fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md §3 for library-wide tier context and fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: fvs_eval/mixed_genre_v1 n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 1.000 |
| Cohen's kappa (pairwise mean) | n/a |
| Raw agreement (pairwise mean) | 1.000 |
| Union prevalence | 0/15 = 0% |
| Intersection (all 4 agree positive) | 0/15 |

Per-family positives (of 15 docs): Claude 0, Gemini 0, Grok 0, GPT 0.
