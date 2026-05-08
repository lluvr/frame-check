# Default Geometry

**FVS entry:** FVS-004
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** HI-027 (The Default Geometry), EXP-064 (cross-evaluator compression), EXP-077/b (prompt attribution)
**Status:** v1, single-curator, reviewers wanted

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

## Vocabulary connections

- **The amplification thesis** (HI-062, CLARETHIUM_VOCABULARY): defaults are the pattern AI amplifies. The default geometry describes the shape of the starting pattern.
- **The construction trace** (T-356): generating your own analysis forces you to confront your own defaults because you have to choose a starting point. Without generation, defaults are invisible.

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

**Authorship.** Lovro Lucic. v1 curated 2026-04-12; grounded-authorship retrofit 2026-04-25 per FRAME_DIVERGENCE_v2.md §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04; frame absent from corpus, prevalence 0 percent)
- HI-027 The Default Geometry case study (origin)
- EXP-064 cross-evaluator compression
- EXP-077/b prompt attribution controlled experiment
- Cross-model default-profile observations from controlled experiments (Claude convergent, GPT expansive, Gemini balancing)
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Frame absent from F-2026-027 mixed_genre_v1. Cross-family AC1 1.000, prevalence 0 percent - frame did not fire on any document. mixed_genre_v1 contains executed content; default-geometry detection requires AI-interaction-pattern content (brainstorming sessions, strategy iteration logs, exploratory dialogue). Detection is meta-level; mixed_genre_v1 is not the appropriate corpus.
2. Bilateral coupling claim is structural argument, not empirical. "Defaults from both sides reinforce each other without either side recognizing the coupling" is grounded in transformer mechanism (semantic neighborhood activation) plus human cognition (satisficing under uncertainty). Direct controlled measurement of the bilateral coupling has not been run. Claim is plausible; empirical anchor is open.
3. Model-specific default profiles are directional, not measured. "Claude convergent, GPT expansive, Gemini balancing" are observational from cross-model experiments, not rigorously measured personality profiles with effect sizes. The directional claim is supported by repeated observation; quantified profiling is open work.

**Success record.** Two operationalized cases:
1. European-expansion worked example (v1 Identification). Document operated from "expansion is the right move" default. Default-geometry counter-frame surfaced the unasked questions: should we expand at all; what are the costs of expansion vs deepening existing markets; what does 12 percent projected growth mean for our capacity to capture it; what happens if we expand and fail. The diagnostic: name the default ("this document assumes expansion is the right move") and cost the default ("what would have to be true for NOT expanding to be the better decision").
2. Branch B pre-commit as default-naming step. The pre-commit intervention forces the user to name their default before AI responds. Operational principle: "you cannot escape a default you have not named." Operationalized across Frame Check methodology as the default-diagnostic step preceding any open-ended AI consultation.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where the operator caught a default frame in their own thinking that AI was about to amplify; (2) the name-it-and-cost-it procedure applied; (3) outcome differential observed (default abandoned, alternative pursued, decision reframed; or default confirmed but with explicit awareness of the alternative); (4) concrete first-person recall. Held open per FRAME_DIVERGENCE_v2.md P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application: ~1-2 minutes (identify default; cost it; explore alternative briefly)
- V4.2 LLM judge invocation: limited applicability (corpus mismatch; detection requires AI-interaction-pattern content)
- Branch B pre-commit (name default before AI consultation): 2-5 minutes user-side
- Use depth: any open-ended interpretive AI consultation; particularly at the start of an extended session

**Applicability metadata.**
- Domains: strategy sessions (high stake-relevance), brainstorming (high), open-ended AI consultations (high), exploratory analysis (medium-high), iterated creative work (medium)
- Decision types: any interpretive or open-ended decision
- Stake levels: medium to high; default-amplification effect compounds with session length and stakes
- Inappropriate contexts: narrowly scoped technical tasks (calculation, formatting, translation); execution-focused work where the "default" answer is the correct answer

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa undefined, AC1 1.000, raw 1.000, prevalence 0 percent (frame absent from corpus)
- HI-027 The Default Geometry origin study
- EXP-064 cross-evaluator compression
- EXP-077/b prompt attribution
- Cross-model default-profile observations: directional from controlled experiments (rigorous quantification open)
- V4 detection mode: meta (not present in mixed_genre_v1)
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
