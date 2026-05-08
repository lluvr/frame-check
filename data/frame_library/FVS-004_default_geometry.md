# Default Geometry

**FVS entry:** FVS-004
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12

## Identification

Human cognitive defaults and AI training defaults share behavioral geometry. Both settle into familiar, locally safe patterns when unconstrained. Human defaults encode a limited search space into prompts. AI defaults activate within that space. Outputs reinforce the human's starting position, narrowing prompts further. The loop is bilateral: comfort meets compliance, and the result is called "good enough." The intervention that defeats both is the same: name the specific default, make it expensive to follow, reward the alternative.

**What this frame makes visible:**
- How defaults from both sides reinforce each other without either side recognizing the coupling
- Why generic instruction ("be creative," "think outside the box") fails because it does not touch the mechanism (specific defaults)
- The operational principle: name it, cost it, escape it (applies to human and AI simultaneously)
- Model-specific default profiles (Claude convergent, GPT expansive, Gemini balancing)

**What this frame makes invisible:**
- What the specific defaults ARE (requires deliberate diagnosis, not generic awareness)
- The distinction between genuine exploration and constrained exploration that feels open
- That state management (being calm, being curious) is necessary but not sufficient because defaults persist across states

**Positive examples:** A team brainstorming with AI that keeps producing variations of the same three themes. Nobody notices the repetition because each variation is different on the surface. The underlying frames (all three themes are within the same problem space) are invisible until someone names them: "every suggestion assumes the current business model continues."

**Negative examples:** A document produced by someone who explicitly named and challenged their default ("my default frame here is growth. Here is the risk frame. Here is the stakeholder frame. The growth frame hides X.") is not exhibiting default geometry because the defaults have been surfaced.

**Adjacent frames:** Frame Amplification (FVS-001, what happens when defaults are not interrupted), Fluency-Quality Illusion (FVS-002, defaults are fluent by definition), Prompt Attribution Error (FVS-003, users attribute default behavior to the model rather than to the default structure)

**When this frame is appropriate:** Any AI interaction where the user has not explicitly diagnosed what their own default frame is for this kind of problem. Strategy sessions, brainstorming, analysis, any open-ended task.

**When this frame is misleading:** Narrowly scoped technical tasks where the "default" is the correct answer (calculating tax, formatting data, translating text). Default geometry matters when interpretation is required, not when execution is required.

**Honest limits:** The bilateral default coupling is a structural argument from how transformers work (semantic neighborhood activation) combined with how human cognition works (satisficing under uncertainty). The specific claim "defaults from both sides reinforce each other" has not been tested in a controlled experiment measuring the coupling directly. Model-specific default profiles (Claude convergent, etc.) are directional observations from cross-model experiments, not rigorously measured personality profiles.

## Generation affordances

**Rewrite prompt structure:** "Identify the default this document operates from. Name it in one sentence. Then rewrite the analysis with that default made expensive: any conclusion that could be reached through the default must be justified against a specific alternative, not just asserted."

**Counter-document prompt:** "This document follows a default pattern. Name the default. Then write the version that would emerge if the user had started from the opposite default: different entry question, different assumptions, different search space."

**Salient questions under this frame:**
- What is my default frame for this type of problem?
- If I asked the same question starting from a different assumption, would the AI produce the same answer?
- Is this output "good enough" because it is good, or because it matches my comfort zone?
- What would make the default path expensive here?

## Worked example

**Document excerpt:** "Expanding into the European market presents significant opportunities. Market research indicates growing demand for sustainable technology solutions, with projected annual growth of 12%. Our competitive advantages in AI-powered supply chain optimization position us well for European enterprise clients."

**Frame present:** Growth default. Every sentence serves the assumption that expansion is the right move. "Significant opportunities," "growing demand," "competitive advantages," "position us well" all reinforce.

**Frame absent:** The default itself is invisible. No sentence asks: should we expand at all? What are the costs of expansion vs deepening in existing markets? What does "12% projected growth" mean in terms of our capacity to capture it? What happens if we expand and fail? The document treats expansion as the starting point, not as a hypothesis to be tested.

**How to read past it:** Name the default: "this document assumes expansion is the right move." Cost the default: "what would have to be true for NOT expanding to be the better decision?" The answer to the second question is the analysis this document should have included.

## Branch applicability

**Primary branch:** Both A and B
**Branch A:** Detected when a document operates from a single dominant frame without naming it. High coverage in one analytical dimension (e.g., trends/growth) with low coverage in competing dimensions (risks, alternatives) is the signal.
**Branch B:** The pre-commit intervention forces the user to name their default before AI responds. This is the diagnostic step for default geometry: you cannot escape a default you have not named.
