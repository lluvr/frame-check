# Prompt Attribution Error

**FVS entry:** FVS-003
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** HI-054 (The Prompt Attribution Error), T-422 (The Four Layers), M-002 (The 60-Second Pause extending to fifth layer)
**Status:** v1, single-curator, reviewers wanted

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

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | undefined |
| Gwet's AC1 (pairwise mean) | 1.000 |
| Raw agreement (pairwise mean) | 1.000 |
| Union prevalence (all families) | 0% |

Per-family positives (of 15 docs): Claude 0, Gemini 0, Grok 0, GPT-5 0.

**V4 detection mode:** meta (not present in mixed_genre_v1)

**Interpretation:** Frame absent from this corpus; reliability undefined by lack of variability.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-12; grounded-authorship retrofit 2026-04-25 per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04; frame absent from corpus, prevalence 0 percent)
- HI-054 The Prompt Attribution Error case study (origin)
- T-422 The Four Layers vocabulary (wrapper, context, prompt, model)
- M-002 The 60-Second Pause (fifth layer extension; the body)
- EXP-077/b prompt-vs-model attribution controlled experiment ("Prompt = WHETHER, Model = HOW")
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Frame absent from F-2026-027 mixed_genre_v1. Cross-family AC1 1.000, prevalence 0 percent - the frame did not fire on any document in the test corpus. mixed_genre_v1 contains general business and analytical content; FVS-003 specifically targets AI-model-commentary content (model comparisons, AI procurement reviews, capability blog posts). Detection requires a corpus containing AI-model-attribution content. Reliability is structurally undefined by lack of variability in the wrong corpus.
2. Magnitude unmeasured in real user behavior. EXP-077/b establishes "Prompt = WHETHER, Model = HOW" structurally. The fraction of perceived model differences that are actually prompt differences in real procurement and reviewer behavior is unmeasured. The claim is structurally sound; population-level impact is open empirical work.
3. Detection cannot run controlled comparison. Frame Check can detect the attribution PATTERN (capability claims about named models without controlled-comparison framing) but cannot itself run the controlled comparison to confirm whether observed difference is model-specific or prompt-specific. Maintainer-side controlled testing is the verification path; Frame Check is the prompt-to-test, not the test.

**Success record.** Two operationalized cases:
1. Worked example: Gemini-vs-Claude analytical reasoning attribution (v1 Identification). Document attributed "superior analytical reasoning" to Gemini and "conversational analysis with hedging" to Claude. Attribution-error counter-frame surfaced: heading-format choices may be system-prompt directives (Google's harness designs structured output for analytical queries); hedging may be safety-guardrail design (Anthropic's harness includes uncertainty acknowledgment). The "what would happen with the same system prompt" question is the operational diagnostic.
2. Branch B pre-commit operational concept. Pre-commit step makes attribution error surface when the user names model-level expectations and the frame delta reveals the difference may be system-level not model-level. Operationalized in Frame Check methodology as the four-layer attribution discipline; user pre-writes own assessment which then anchors the comparison.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where the operator caught themselves attributing AI behavior to model identity when the actual cause was prompt or context layer; (2) controlled-comparison reasoning applied (asked "what would happen with the same system prompt"); (3) outcome differential observed (procurement decision adjusted, capability claim retracted, comparison revised); (4) concrete first-person recall. Held open per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application: ~30-60 seconds per attribution claim ("have I controlled for the system prompt")
- V4.2 LLM judge invocation: limited applicability (frame requires AI-model-commentary corpus; rule-based detection looks for capability-claim patterns without controlled-comparison framing)
- Controlled-comparison test (verification of suspected attribution error): requires API access to both models with identical system prompts; substantial setup; out of scope for casual readers
- Use depth: any model-comparison content; AI-procurement decision-making

**Applicability metadata.**
- Domains: AI procurement (high stake-relevance), model comparison reviews (high), AI-product strategy documents (medium-high), blog posts and social media about model capabilities (medium)
- Decision types: model selection, AI vendor evaluation, capability assessment for AI integration
- Stake levels: medium to high (model selection decisions can be substantive at organizational scale)
- Inappropriate contexts: discussions of genuinely model-specific properties (context window size, multilingual ability, specific domain training data, architecture differences)

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa undefined, AC1 1.000, raw 1.000, prevalence 0 percent (frame absent from corpus; reliability undefined by lack of variability)
- HI-054 The Prompt Attribution Error origin study (EXP-077/b)
- T-422 Four Layers vocabulary
- M-002 fifth-layer extension (body as additional layer)
- V4 detection mode: meta (not present in mixed_genre_v1; testing requires AI-model-commentary corpus)
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
