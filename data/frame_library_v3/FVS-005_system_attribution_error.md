# System Attribution Error

**FVS entry:** FVS-005
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** HI-063 (The System Attribution Error), T-422 (The Four Layers), M-002 (fifth layer)
**Status:** v1, single-curator, reviewers wanted

## Identification

Users attribute AI behavior to "the model" when four invisible layers jointly produce every output: the company's system prompt and harness infrastructure (wrapper), the user's accumulated context (custom instructions, memory, project files), the current prompt, and the model itself. The model is the only layer with a name. The user's own accumulated system is the most dangerous blind spot because it was built gradually, never examined as a system, and contributes to every response without acknowledgment.

**What this frame makes visible:**
- How model comparisons confound at least four variables (comparing "Claude vs Gemini" compares harness + context + prompt + model simultaneously)
- Why "AI improved over time" when model weights are frozen: the user's accumulated context deepened invisibly
- The scale of the invisible layers (the Claude Code source leak revealed 512K lines of harness code shaping behavior)
- Negative-space behaviors (what the AI is told NOT to do) are most invisible because they prevent behaviors the user never sees

**What this frame makes invisible:**
- Which layer is the actual variable in any given output (requires controlled experiments to isolate)
- The user's own system as a contributor (project files, memory entries, configured standards: the user created all of it but never audits it)
- How the company harness changes over time without notice (system prompt updates, feature flags, safety filters)

**Positive examples:** A user says "Claude got worse at coding after the last update" when the actual change was a system prompt revision that increased safety hedging. The model weights may be identical. The perceived regression is a wrapper change, not a model change.

**Negative examples:** A controlled benchmark where the same prompt is run on the raw model API without a system prompt, across model versions, IS isolating the model layer. This does not exhibit the system attribution error because the confounding layers are removed.

**Adjacent frames:** Prompt Attribution Error (FVS-003, the narrower version focused on prompts rather than the full four-layer stack), Default Geometry (FVS-004, the defaults come from ALL four layers, not just the model)

**When this frame is appropriate:** Any time someone makes claims about model capability, model personality, model improvement, or model degradation based on end-user interaction. Model selection decisions. AI vendor evaluations. Any "model X is better than model Y" claim that was not made under controlled conditions.

**When this frame is misleading:** When discussing properties that genuinely ARE model-specific: context window size, language coverage, base training data, architecture differences. Some properties are model properties. The error is in the default attribution, not in the claim that models have properties.

**Honest limits:** The four-layer model is structural and well-supported by the Claude Code leak evidence and by the upstream's controlled experiments (same model, different system configuration, deterministic behavioral change). The specific claim about how much end-user perception is model-layer vs other-layer has not been quantified in a population study. "Most of what users attribute to the model is not the model" is directionally supported but the fraction is unmeasured.

## Decision-readiness implication

**Meta-side frame.**

About attribution of behavior to 'the model' when invisible system layers contribute. Not a structural document property. The [decision-readiness profile](/corpus/decision-readiness/) measures the document the agent produces; this entry names the upstream conditions that shape what the document looks like.

## Generation affordances

**Rewrite prompt structure:** "For each capability claim in this document ('Model X is good at Y'), rewrite as a four-layer attribution: 'When run with [harness] by a user with [context] using [prompt], Model X produced [output]. Which layer contributed most is unknown without controlled comparison.'"

**Counter-document prompt:** "This document attributes behavior to AI models. Rewrite from the perspective of each of the four layers: how would the company harness produce this behavior? How would the user's context? How would the prompt? Only after eliminating these, what remains as genuinely model-specific?"

**Salient questions under this frame:**
- When I say "this model does X," have I controlled for the other three layers?
- Have I examined my own accumulated context as a contributor to output quality?
- Is the behavior I am evaluating a model property or a deployment configuration?
- If I stripped the system prompt, would the model still behave this way?

## Worked example

**Document excerpt:** "After extensive testing, we found that Claude produces more nuanced, balanced analysis than GPT-4o for strategic consulting documents. Claude considers multiple perspectives and includes appropriate caveats, while GPT-4o tends toward more direct, assertive recommendations."

**Frame present:** Model attribution. "Claude produces more nuanced analysis" attributes a behavior to the model.

**Frame absent:** Anthropic may have designed Claude's system prompt to include multi-perspective analysis and uncertainty hedging. OpenAI may have designed GPT-4o's system prompt to prioritize directness and actionability. The "nuance" may be a safety feature, not a reasoning capability. The "directness" may be a UX choice, not a limitation.

**How to read past it:** "What would happen if both models ran on the exact same system prompt, with the same user context, on the same task?" If the behavior persists, it is more likely model-specific. If it changes, the attribution was wrong. Most end users cannot run this test, which is exactly why the error persists.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected when a document makes capability attributions to named AI models without acknowledging the confounding layers. High assertion density about model properties with no mention of system prompts, user context, or controlled comparisons.
**Branch B:** Surfaces when a user's pre-commit contains model-level expectations ("I think Claude will do X") that the frame delta reveals are actually system-level properties.

## Vocabulary connections

- **The four layers** (T-422, CLARETHIUM_VOCABULARY): the structural model this entry is built on. M-002 adds the fifth layer (the body).
- **The first read** (M-002): the somatic response to output style is attributed to the model when it may be a harness property.

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
- HI-063 The System Attribution Error case study (origin)
- T-422 The Four Layers (wrapper, context, prompt, model)
- M-002 fifth layer (the body)
- Claude Code source leak evidence (512K lines of harness code shaping behavior)
- Vault controlled experiments (same model, different system configuration, deterministic behavioral change)
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Frame absent from F-2026-027 mixed_genre_v1. Cross-family AC1 1.000, prevalence 0 percent - same as FVS-003 and FVS-004; frame requires AI-model-commentary content not present in mixed_genre_v1. Detection requires appropriate corpus (model comparisons, AI capability reviews, AI vendor evaluations). Reliability undefined by lack of variability in wrong corpus.
2. Quantified end-user attribution fraction unmeasured. "Most of what users attribute to the model is not the model" is directionally supported by controlled vault experiments and the Claude Code source leak (512K lines of harness evidence). The specific fraction (how much of perceived model behavior is harness vs context vs prompt vs model) has not been quantified in a population study. Direction is well-supported; magnitude is open.
3. User's own context is the deepest blind spot. Custom instructions, memory entries, project files all shape every response but the user rarely audits these as a system. The user CREATED their accumulated context but does not examine it. Detection of self-system contribution requires introspective discipline; Frame Check can prompt the question but cannot run the audit on the user's behalf.

**Success record.** Two operationalized cases:
1. Claude Code source leak quantitative evidence. The leak revealed 512K lines of harness code shaping behavior. Quantitative anchor for "the wrapper layer is enormous and largely invisible." Negative-space behaviors (what the AI is told NOT to do) are most invisible because they prevent behaviors users never see; the source leak made these visible at scale. Foundation evidence for the four-layer model.
2. Worked example: Claude vs GPT-4o consulting attribution (v1 Identification). Document attributed "more nuanced analysis" to Claude and "more direct" to GPT-4o. System-attribution counter-frame surfaced: nuance may be Anthropic harness design (multi-perspective + hedging instructions); directness may be OpenAI UX choice (priority on actionability). The "controlled comparison with same system prompt" is the verification path; most end users cannot run this test, which is exactly why the error persists at population scale.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where the operator caught themselves attributing AI behavior to "the model" when investigation revealed harness, context, or prompt was the actual cause; (2) four-layer attribution analysis applied (which layer is the actual variable); (3) outcome differential observed (capability claim corrected, procurement decision adjusted, debugging path redirected); (4) concrete first-person recall. Held open per FRAME_DIVERGENCE_v2.md P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application: ~30-60 seconds per attribution claim
- V4.2 LLM judge invocation: limited applicability (corpus-mismatch; detection requires AI-model-commentary content)
- Four-layer attribution audit: 5-10 minutes per major capability claim (which layer is the variable; can the layer be controlled)
- User-system audit (custom instructions, memory, project files): 30-60 minutes one-time per user, with periodic re-audit; this is the rarely-done step

**Applicability metadata.**
- Domains: AI procurement (high stake-relevance), model comparisons (high), AI vendor evaluations (high), AI capability reviews (medium-high), debugging "AI got worse" or "AI improved" claims (high)
- Decision types: any with model-specific capability attribution; any model-version-comparison claim
- Stake levels: medium to high; misattribution at procurement scale is costly
- Inappropriate contexts: genuinely model-specific properties (context window size, multilingual ability, base architecture differences, training-data domain coverage)

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa undefined, AC1 1.000, raw 1.000, prevalence 0 percent (frame absent from corpus)
- HI-063 The System Attribution Error origin study
- T-422 Four Layers structural model
- Claude Code source leak: 512K lines of harness evidence (quantitative anchor)
- Vault controlled experiments: same model, different system configuration, deterministic behavioral change
- V4 detection mode: meta (not present in mixed_genre_v1)
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
