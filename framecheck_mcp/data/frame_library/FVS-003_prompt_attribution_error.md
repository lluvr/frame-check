# Prompt Attribution Error

**FVS entry:** FVS-003
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12

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

**Adjacent frames:** System Attribution Error (, the broader version including the user's own system), Frame Amplification (FVS-001, what happens after the attributed-as-capable model locks into a frame), Fluency-Quality Illusion (FVS-002, the surface signal that makes the attribution feel justified)

**When this frame is appropriate:** Any time someone makes claims about what a model "is like" or "is good at" based on end-user interaction. Model selection decisions. AI procurement. Model comparisons in blog posts, reviews, social media. Any context where the user has not controlled for system prompt differences.

**When this frame is misleading:** When discussing capabilities that are genuinely model-specific (context window size, multilingual ability, specific domain training). Some properties ARE model properties. The error is in defaulting to model attribution when prompt attribution is more likely, not in claiming that models have no properties.

**Honest limits:** The Prompt Attribution Error is grounded in /b (: "Prompt = WHETHER, Model = HOW"). The evidence is from controlled experiments comparing conditions within and across models. The magnitude of the attribution error in real user behavior (how much of perceived model difference is actually prompt difference) has not been measured in a population study. The claim is structurally sound but the practical impact on real procurement decisions is unmeasured.

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

**How to read past it:** For each attributed capability, ask: "What would happen if I gave both models the exact same system prompt?" If the behavior persists, it is more likely model-specific. If it changes, it was prompt-specific. Most end users cannot run this test because system prompts are not exposed. Framecheck can detect the attribution pattern by identifying capability claims that lack controlled comparisons.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected when a document makes capability attributions to named AI models without naming the system prompt or comparing under controlled conditions. High assertion density about model properties with low epistemic sourcing is the detection signal.
**Branch B:** In the pre-commit intervention, the prompt attribution error surfaces when the user pre-commits "I think Claude will be better at this" and then sees a frame delta showing the observed difference may not be model-specific.
