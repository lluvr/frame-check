---
transmission_id: T-415
display_title: "The Most-Cited Finding Was Wrong"
type: ARC
summary: "The most-cited effect across 80+ experiments was three effects stacked. Honest magnitude: 40% smaller."
published: 2026-03-23
models: "xAI / Gemini"
source_url: https://blog.clarethium.com/catching-your-own-overclaim
---

# Catching Your Own Overclaim

The most-cited effect across 80+ experiments was wrong.

Not the direction. The direction was right. Specific instructions produce more specific output than vague instructions. That replicated across evaluators, across models, across tasks. The direction survived everything.

The magnitude was wrong. d=2.34. Cited in seven pieces of writing. Referenced in thirty framework documents. Built into the theory of how specificity constrains AI output. The foundation number for the most-cited claim across all the work.

It was actually three effects stacked on top of each other, reported as one.

The original experiment compared a 22-word specific instruction against a 2-word vague instruction. "Do not produce a recommendation that could apply to any B2B SaaS company. Every point must be grounded in Northvane's specific situation" versus "Be specific." Twenty runs. Large effect. Replicated.

The obvious interpretation: specificity is the mechanism. But the comparison confounded specificity content with instruction length. 22 words versus 2. Any effect could be the extra instruction text, not the specificity within it.

A length-controlled replication added two conditions: a short specific instruction (8 words) and a long vague instruction (22 words with quality demands like "detailed, thorough, comprehensive"). Raw scores showed the long vague instruction beating the short specific one. First interpretation: length is the mechanism. The specificity claim collapses.

But that interpretation was also wrong. The long vague instruction produced 48 percent more words. More words produce more specificity markers mechanically. At density (markers per thousand words) the specific instruction was MORE specific per word. Length inflated the raw score. Specificity was real underneath. And the "long vague" instruction contained quality demands that could independently drive the effect.

Three confounded variables across the two replications. A clean decomposition required separating all of them.

A 2x2 factorial. Specificity: present or absent. Quality demands: present or absent. All instructions matched at 19 words. Output length constrained. Forty outputs. One generator.

Specificity: d=1.37 raw score (shorter output, more markers). Quality demands: d=0.11 at raw score, near zero. Both together: additive. The mechanism is specificity, not quality demands, not length. But the magnitude is d=1.37, not d=2.34.

The tool that caught the confound came from the measurement infrastructure I'd already built. Density analysis (dividing total markers by word count) was developed for fabrication measurement. Applied to the specificity experiment, it separated what raw scores had conflated. The system caught its own error using its own tools.

The measurement tool built for one problem (fabrication detection) revealed a confound in a different problem (specificity measurement). Density analysis isn't novel methodology. It's basic normalization that any researcher would apply. What made it possible here was having the measurement infrastructure already built and the habit of applying it reflexively. The confound led to a cleaner experiment. The cleaner experiment confirmed the mechanism at a smaller, more honest magnitude. The overclaim was replaced by a better-supported claim.

Then a domain expert evaluated the outputs blind. Couldn't tell which were produced with specific instructions and which with generic ones. Picked specific 3 out of 5 times, chance level. Both conditions produce the same analytical conclusions. The specificity instruction changes what the output LOOKS LIKE (more data references, more grounded language), not what it SAYS.

The direction held. The magnitude shrank. And the mechanism turned out to be about verifiability, not quality. Specific outputs can be checked, generic ones can't, but the analysis is the same either way. Three corrections deep. Each one more interesting than the finding it replaced.

What survived testing:
- Specificity as mechanism (confounds controlled, confidence interval excludes zero)
- The decomposition methodology (density analysis catches confounds raw scores miss)
- The self-correction trajectory (own tools caught own overclaim)

What didn't survive:
- The original inflated effect size (specificity + length stacked; honest range roughly 40% smaller)
- "Strongest effect in 80+ experiments" (large, but not as large as claimed)
- Clean separation at density level: quality demands show a large density effect vs near-zero raw effect (density partially conflates specificity with shorter output length)

Honest limits:
- Clean 2x2 originally single generator. Cross-generator confirmed on a second model family with virtually identical effect size.
- Specificity heuristic validated against domain expert at chance level. Expert couldn't distinguish specific from generic on quality, only on style. Specificity changes form (verifiable references), not substance (same conclusions).
- 10 outputs per condition. Effect sizes directional with confidence intervals that exclude zero.
- "Write exactly 500 words" did not fully control output length (368-443 words).
