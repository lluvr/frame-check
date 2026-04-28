---
transmission_id: T-350
display_title: "The Model Is Rarely the Variable"
type: EVIDENCE
summary: "The prompt determined whether behaviors existed at all. The model adjusted the volume."
published: 2026-03-24
models: "xAI / Gemini"
source_url: https://blog.clarethium.com/blog/attribution-error
---

# The Attribution Error

Was working with multiple models on the same tasks. Same instruction, wildly different results. Assumed model differences.

The prompt mattered dramatically more than the model.

Two models. Same prompt. Same topic. Same length constraint. The prompt explained the dominant difference in behavior. The model explained near-zero. This wasn't a vague comparison. Two personas tested at controlled length. One that challenged assumptions and commented on the user's patterns. One that supported and built on what the user said. Both say "150 to 200 words." Only the persona differs.

Under the challenging persona, 38.9 percent of responses included meta-calling, the model commenting on the human's own patterns. Under the supportive persona: zero. Not less. Zero. Same model, same length, same topic. The behavior is entirely prompt-determined.

Confrontation followed the same pattern. The challenging persona produced escalating pushback over the course of the conversation. The supportive persona produced none. Not reduced confrontation. No confrontation. The prompt didn't adjust the model's behavior. It determined whether the behavior existed at all.

Scope caveat, because this matters before reading further: this pattern is demonstrated for persona-driven behaviors (meta-calling, confrontation, format preferences). Whether the prompt-over-model ratio holds for capability-dependent tasks (mathematical reasoning, code generation, factual recall) is untested and likely different. The attribution error applies strongest where behavior is prompt-configurable. Where model capability is the bottleneck, the model matters more than the prompt.

The part that matters: the confrontational behavior was originally attributed to Grok's character. "That's just how Grok is." Then the same challenging prompt was tested on Gemini. In the initial small sample, Gemini appeared to confront harder than Grok. At scale (6 topics, 144 responses), the ratio reversed: Grok meta-called more often than Gemini (55.6% vs 44.4%). The relative intensity is unstable across samples. But the binary finding held perfectly: the prompt determines WHETHER the behavior exists. Both models went from 0% to 40-56% under the same persona change. The attribution was backwards.

This is the AI version of the Fundamental Attribution Error. In psychology, that's when you attribute someone's behavior to their personality instead of their situation. "She's rude" instead of "she's having a terrible day." With AI, the structure is identical. The model name is visible. The system prompt is invisible. Attribution follows salience. The visible label captures the credit for behavior driven by the invisible configuration.

The pattern repeated across three different experiments.

In the first, model switches got credit for behavior changes that prompt architecture produced. The large ratio. In the second, framing changes seemed powerful, but controlled decomposition showed specificity underneath was the actual lever. What looked like the frame doing the work was the specificity within the frame. In the third, vocabulary bans looked like quality control, but the real mechanism was output compression. Banning words didn't improve quality. It shortened the output, and shorter output has higher density by default.

In each case, the visible change co-varies with something less visible. Practitioners credit the visible change. Controlled tests show the mechanism underneath. The surface looks like the explanation. It isn't.

The practical implications follow directly. When a model "doesn't work" for what you need, change the prompt before changing the model. The behavior you want may already be available under a different prompt configuration. When comparing models for a task, run them under the same prompt first. Most model comparisons in practice use different system prompts, different default configurations, different temperature settings. That means they're comparing prompts and calling it a model comparison.

The model determines intensity and format: how direct, how structured, how detailed, whether it prefers lists or prose. These are real model-level properties. They persist across prompts. But they're continuous, not binary. The prompt determines whether behaviors occur at all. That's the binary distinction. A model that never meta-calls under a supportive prompt meta-calls 38.9 percent of the time under a challenging prompt. The prompt turns behaviors on and off. The model adjusts the volume.

Both matter. The ratio of importance is what people get backwards.

What survived testing:
- Prompt determines WHETHER behaviors occur (binary difference, replicated at scale)
- Model determines HOW behaviors express (continuous difference)
- Prompt architecture dominated model choice at format level
- Attributed behavior was not even model-preferring

What didn't survive:
- "Universal ratio": the specific ratio is experiment-specific. The ordering (prompt > model) is robust.
- "Model doesn't matter at all": model determines format preferences independently of prompt.

Honest limits:
- Two model families tested. Claude untested in this specific experiment.
- Persona was the prompt variable. Other prompt dimensions tested in separate experiments with consistent direction.
- March 2026 models. The ordering is likely structural. The specific ratios will shift.
