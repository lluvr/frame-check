---
transmission_id: T-392
display_title: "Stop Polishing, Start Switching"
type: MECHANISM
summary: "The ceiling is per generation mode. Switch modes to access territory that iteration can't reach."
models: "Multiple models"
source_url: https://blog.clarethium.com/blog/ceiling-switch
---

# The Ceiling Switch

Polishing doesn't work past a point. The output hits a ceiling and more iteration produces diminishing returns. The first response isn't the best but the fifth response isn't much better than the third.

The ceiling is per generation mode. Not per model. Not per session. Per mode.

When you ask the model to analyze, it generates in analytical mode. Each iteration within analytical mode improves the analysis marginally. The structure tightens. The language gets cleaner. The coverage gets more complete. But the analytical depth doesn't increase because the model is iterating within the same semantic region. It's polishing, not discovering.

Switch to a different mode: ask for critique, ask for the opposite argument, ask it to find what's wrong: and the output jumps to a different region. Not because the model got smarter. Because it accessed a different part of representation space. The ceiling in analytical mode doesn't apply in critical mode. Each mode has its own ceiling.

The practical version: when output stops improving, don't ask for another iteration in the same mode. Switch modes. "Now critique what you just produced." "What's wrong with this analysis?" "Argue the opposite." "What did this miss?" The mode switch accesses territory that iteration within a single mode can't reach.

This connects to why self-critique circles instead of improving. When you ask the model to critique its own output in the same generation context, it's often still in the original mode. The "critique" activates a critique-flavored version of the same semantic neighborhood, not a genuinely different critical perspective. A fresh prompt with an explicitly different mode produces better critique than "now review what you just wrote."

Three mode switches that break ceilings in practice (the first is tested at scale, the other two are consistent observations). Analytical to critical: "What's wrong with this?" Generative to evaluative: "Score each option against these criteria." Convergent to divergent: "What's a completely different approach?" Each switch accesses a different region. The output after the switch contains information that wasn't accessible from the previous mode.

A non-adversarial mode switch test resolved the one confound in the original experiment. The original switched analytical to critical, which introduces contrary vocabulary by design. The follow-up switched analytical to evaluative (scoring options against criteria). No adversarial content. The evaluative switch produced more novelty than continued iteration on all 5 topics tested, and exceeded fresh context on all 5. The novelty boost comes from the mode switch itself, not from the adversarial vocabulary the critical mode introduces.

What survived testing:
- Iteration within a mode produces diminishing returns
- Self-critique in the same context circles
- Mode switch produces more novel vocabulary than continued iteration, winning on all topics tested across two generators. Density-normalized to control for length.
- Mode switch exceeds fresh context. The conversation provides material to push against, producing more novelty than starting fresh.
- Cross-generator: both models show the effect. Larger on one.
- Non-adversarial switch (analytical to evaluative) confirms mechanism: the novelty boost comes from the mode switch itself, not adversarial vocabulary.

What didn't survive:
- "Always switch modes" too prescriptive. Sometimes iteration within a mode is what you need.
- "Three switches are exhaustive" too strong. Other mode switches exist.
- "Adversarial mode switch confound" resolved: non-adversarial switch produces same pattern.

Honest limits:
- Two mode-switch directions tested at scale (analytical to critical, analytical to evaluative). Non-adversarial follow-up resolved the original confound: novelty comes from the mode switch itself, not adversarial vocabulary. Generative to evaluative and convergent to divergent remain observational.
- "Per generation mode" is an explanatory model. The actual representation space dynamics are more complex.
- March 2026 models. Future models may have less pronounced mode boundaries.
