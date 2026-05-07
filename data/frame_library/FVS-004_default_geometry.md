# Default Geometry

**FVS entry:** FVS-004
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** HI-027 (The Default Geometry), EXP-064 (cross-evaluator compression), EXP-077/b (prompt attribution)
**Status:** v1, single-curator. Withdrawn from v1 publication per [INDEX.md](https://github.com/Clarethium/frame-check-mcp/blob/master/data/frame_library/INDEX.md) "v1 publication state" table (bilateral-reinforcement mechanism not grounded in cited experimental evidence). Source markdown preserved for citation continuity; the FVS-004 ID is reserved and will not be reused.

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

**Honest limits:** The bilateral default coupling is a structural argument from how transformers work (semantic neighborhood activation) combined with how human cognition works (satisficing under uncertainty). The specific claim "defaults from both sides reinforce each other" has not been tested in a controlled experiment measuring the coupling directly. Model-specific default profiles (Claude convergent, etc.) are directional observations from the upstream's cross-model experiments, not rigorously measured personality profiles.

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

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md. The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.355** (tier: **weak**), per fvs_eval/v4/library_v4_reliability.json. Per-corpus reproducible values (regen: fvs_eval/v4/compute_per_corpus_reliability.py; artifact: fvs_eval/v4/library_v4_per_corpus_reliability.json): MG_v3=0.477 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.354 (3-family partial; Anthropic queued). Historical: MG2_v1=0.289 (library_v1), MG2_v2=0.422 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md; rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **0.967** across n=41 docs at temp=0 (1 verdict flip(s); per fvs_eval/v4/grok_intra_rater_ac1.json). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/Clarethium/frame-check-mcp/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.477, kappa 0.216, union 8/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): -0.17.
- **library_v2 (earlier variant):** Gwet's AC1 0.676, kappa 0.196, union 6/15.

See fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md §3 for library-wide tier context and fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: fvs_eval/mixed_genre_v1 n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.306 |
| Cohen's kappa (pairwise mean) | 0.017 |
| Raw agreement (pairwise mean) | 0.589 |
| Union prevalence | 11/15 = 73% |
| Intersection (all 4 agree positive) | 0/15 |

Per-family positives (of 15 docs): Claude 6, Gemini 3, Grok 1, GPT 7.
