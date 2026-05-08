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

**Adjacent frames:** Prompt Attribution Error (FVS-003, the narrower version focused on prompts rather than the full four-layer stack; FVS-003 withdrawn per INDEX.md "v1 publication state"), Default Geometry (FVS-004, the defaults come from ALL four layers, not just the model; FVS-004 withdrawn per INDEX.md "v1 publication state"), Oracle Frame (FVS-013, the reader posture that produces system attribution error; without independent evaluation, the reader misattributes 4-layer effects to the model alone)

**When this frame is appropriate:** Any time someone makes claims about model capability, model personality, model improvement, or model degradation based on end-user interaction. Model selection decisions. AI vendor evaluations. Any "model X is better than model Y" claim that was not made under controlled conditions.

**When this frame is misleading:** When discussing properties that genuinely ARE model-specific: context window size, language coverage, base training data, architecture differences. Some properties are model properties. The error is in the default attribution, not in the claim that models have properties.

**Honest limits:** The four-layer model is structural and well-supported by the Claude Code leak evidence and by controlled experiments (same model, different system configuration, deterministic behavioral change). The specific claim about how much end-user perception is model-layer vs other-layer has not been quantified in a population study. "Most of what users attribute to the model is not the model" is directionally supported but the fraction is unmeasured.

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

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md. The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.990** (tier: **strong**), per fvs_eval/v4/library_v4_reliability.json. Per-corpus reproducible values (regen: fvs_eval/v4/compute_per_corpus_reliability.py; artifact: fvs_eval/v4/library_v4_per_corpus_reliability.json): MG_v3=1.0 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.973 (3-family partial; Anthropic queued). Historical: MG2_v1=0.98 (library_v1), MG2_v2=1.0 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md; rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **1.000** across n=41 docs at temp=0 (0 verdict flip(s); per fvs_eval/v4/grok_intra_rater_ac1.json). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/Clarethium/frame-check/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

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
