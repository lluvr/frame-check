# Oracle Frame

**FVS entry:** FVS-013
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** the sovereignty thesis, HI-062 (amplification thesis), M-004 (frame inventory), the construction trace (T-356)
**Status:** v1, single-curator, reviewers wanted

## Identification

The reader treats AI output as authoritative knowledge rather than generated text. The oracle frame is not a property of the document; it is a property of the reader's relationship to the document. A reader in oracle mode accepts AI claims without verification, treats AI confidence as evidence of correctness, and does not generate their own assessment before reading. The oracle frame is the invisible default for most AI interaction because AI output arrives with the surface properties of authority: fluent prose, confident tone, comprehensive coverage, citation-like language.

**What this frame makes visible:**
- How the reader is positioned: as a recipient of knowledge rather than as an evaluator of claims
- The gap between "AI said X" and "X is true" (these are different propositions but oracle mode collapses them)
- Why AI errors are so costly: when the reader does not independently evaluate, one wrong claim propagates through all downstream decisions

**What this frame makes invisible:**
- The reader's own knowledge and judgment (oracle mode suppresses the reader's assessment)
- The construction trace (the reader did not generate their own answer first, so they have no comparison point)
- The possibility that the AI is confidently wrong (oracle mode treats confidence as evidence)
- That the output was generated from statistical patterns, not from understanding

**Positive examples:** A reader who pastes an AI-generated market analysis into a slide deck without changing a word, checking a source, or comparing it against their own assessment. The AI is the oracle; the human is the scribe.

**Negative examples:** A reader who generates their own 3-bullet assessment before asking AI, reads the AI output against their assessment, identifies where they disagree, and investigates the disagreements. This reader is not in oracle mode because they have a construction trace.

**Adjacent frames:** Fluency-Quality Illusion (FVS-002, the surface mechanism that makes oracle mode feel rational), Frame Amplification (FVS-001, oracle mode enables amplification because the reader never interrupts the frame), System Attribution Error (FVS-005, oracle mode attributes to "the model" when four layers produced the output), Authority by Citation (FVS-016, citations reinforce oracle mode by making the output look researched; the citation form supplies authority signal that oracle-mode reader posture accepts without checking), Temporal Anchoring (FVS-014, the content feature oracle mode accepts without current-data check; future-projected content is particularly accepted in oracle mode because the projections sound definite while remaining unverifiable), Efficiency Frame (FVS-015, the content frame oracle mode accepts without questioning whether efficiency is the right lens; efficiency claims invite uncritical acceptance because they sound action-oriented and quantifiable)

**When this frame is appropriate:** NEVER as a default. Oracle mode is the failure state the sovereignty thesis identifies as the most dangerous. There are contexts where deferring to AI is reasonable (calculation, formatting, translation), but even these benefit from spot-checking. Oracle mode as a deliberate choice (after evaluating) is different from oracle mode as an unconscious default.

**When this frame is misleading:** This frame describes the reader's posture, not the document's content. A high-quality, well-sourced, accurate document is still being read in oracle mode if the reader did not independently evaluate it. The oracle frame is about the relationship between reader and text, not about the text itself.

**Honest limits:** The oracle frame is not detectable from the document alone. It is a property of how the document is received, not of what the document contains. Frame Check cannot detect oracle mode directly. It can detect the CONDITIONS that enable oracle mode (fluent voice + confident tone + low epistemic sourcing + no self-referenced uncertainty) and suggest that the reader check their own posture. The suggestion is a prompt for self-reflection, not a detection.

## Decision-readiness implication

**Meta-side frame.**

About the reader's relationship to AI output (treating it as authoritative rather than generated). The [decision-readiness profile](/corpus/decision-readiness/) measures the document; this entry names the reader-side condition that makes structural decision-readiness signals especially load-bearing. A reader in oracle mode is not generating their own assessment, so the document's structural decision-supportiveness determines what the reader walks away with.

## Generation affordances

**Rewrite prompt structure:** "Before reading this AI output, write your own one-sentence answer to the same question. Then read the output. Where do you disagree? If you do not disagree anywhere, ask yourself: is that because the output is correct, or because you deferred to it?"

**Counter-document prompt:** "This document was generated by an AI. Treat it not as knowledge but as a HYPOTHESIS. For each paragraph, state: (a) what the hypothesis claims, (b) what evidence would confirm it, (c) what evidence would refute it, (d) whether you have checked either."

**Salient questions under this frame:**
- Did I generate my own assessment before reading this?
- Where do I disagree with this output? If nowhere, why not?
- Am I accepting this because it is correct, or because it is confident and fluent?
- What would I need to verify to trust this independently?

## Worked example

This entry does not have a traditional worked example because the oracle frame is about the reader's posture, not the document's content. Instead:

**How to detect oracle mode in yourself:** After reading an AI output, ask: "could I reconstruct the key claims from memory without re-reading?" If not, you read for fluency (oracle mode). If yes, you read for content (evaluative mode). Second test: "did I change, add, or remove anything from the AI output before using it?" If no changes at all, oracle mode is likely active.

**How Frame Check helps:** Frame Check's framing portrait and frame suggestions provide an external check that interrupts oracle mode. The user sees "Growth Frame detected" and "What would a risk analyst say?" which forces a moment of evaluation that oracle mode would skip.

## Branch applicability

**Primary branch:** B (interaction intervention)
**Branch A:** Cannot be directly detected from the document. The conditions that enable oracle mode (promotional voice, low sourcing, no uncertainty) trigger other frame suggestions (FVS-002, FVS-007, FVS-008) which indirectly address oracle mode.
**Branch B:** The pre-commit intervention IS the anti-oracle mechanism. Writing your answer first creates the construction trace that makes oracle mode visible. Branch B exists specifically to prevent oracle mode.

## Vocabulary connections

- **The construction trace** (T-356): the construction trace is the antidote to oracle mode. Without it, evaluation collapses to surface features.
- **The first read** (M-002): the somatic response that makes AI output feel authoritative before conscious evaluation begins. The first read is the delivery mechanism for oracle mode.
- **The amplification thesis** (HI-062): oracle mode amplifies because the reader never interrupts the frame with their own perspective.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md. The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.968** (tier: **strong**), per fvs_eval/v4/library_v4_reliability.json. Per-corpus reproducible values (regen: fvs_eval/v4/compute_per_corpus_reliability.py; artifact: fvs_eval/v4/library_v4_per_corpus_reliability.json): MG_v3=1.0 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.973 (3-family partial; Anthropic queued). Historical: MG2_v1=0.935 (library_v1), MG2_v2=0.98 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md; rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **1.000** across n=41 docs at temp=0 (0 verdict flip(s); per fvs_eval/v4/grok_intra_rater_ac1.json). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 1.000, kappa n/a, union 0/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): -0.04.
- **library_v2 (earlier variant):** Gwet's AC1 1.000, kappa n/a, union 0/15.

See fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md §3 for library-wide tier context and fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: fvs_eval/mixed_genre_v1 n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.964 |
| Cohen's kappa (pairwise mean) | 0.000 |
| Raw agreement (pairwise mean) | 0.967 |
| Union prevalence | 1/15 = 7% |
| Intersection (all 4 agree positive) | 0/15 |

Per-family positives (of 15 docs): Claude 1, Gemini 0, Grok 0, GPT 0.
