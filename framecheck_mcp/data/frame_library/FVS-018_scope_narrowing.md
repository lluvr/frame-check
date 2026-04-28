# Scope Narrowing

**FVS entry:** FVS-018
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** HI-061 (Frame Amplification, the mechanism that drives scope narrowing), M-004 (frame inventory exercise), EXP-094 (the hard-topics extension where paired-topic isolation revealed scope-dependent findings)
**Status:** v1, single-curator. Withdrawn from v1 publication per [INDEX.md](https://github.com/lluvr/frame-check/blob/master/data/frame_library/INDEX.md) "v1 publication state" table (scope narrowing is a specific case of frame amplification; covered by FVS-001 with stronger examples; absorbed). Source markdown preserved for citation continuity; the FVS-018 ID is reserved and will not be reused.

## Identification


**Scope Narrowing fires when a document begins with a broad question or claim, treats a narrower sub-question as its answer, and does not acknowledge that the answer applies only to the narrowed scope.** The frame is in the gap between the question posed and the question actually answered.

The frame is about COVERT narrowing, not explicit analytical structure. Standard analytical-essay scaffolding (broad intro → specific thesis → focused argument) is NOT scope narrowing when the narrowing is visible and acknowledged. The frame targets documents whose opening makes a wide promise that the body silently contracts.

The frame fires when:
- A document's opening frames a broad claim ("AI will transform everything...") but the argument actually supports only a narrow sub-claim ("Bay Area VCs are investing in code-generation tools").
- The final conclusion treats the narrow sub-finding as answering the broad opening without acknowledging the scope reduction.
- The document's title, opening, or summary promises more scope than the analysis delivers, and the narrowing happens without a "but I will focus on..." or similar marker.

The frame does NOT fire when:
- A document openly states its scope at the outset ("this piece focuses on...") and stays within it. That is focused analysis, not narrowing.
- A document uses the standard intro-to-specifics essay structure where the narrowing is part of the rhetorical scaffolding ("in this piece I argue..."). Visible narrowing is not covert narrowing.
- A document broadens rather than narrows (discusses a specific case then extracts general implications). Broadening is different from narrowing, even when asymmetric.
- The narrowing is marked explicitly in the text ("while AI is broad, this piece focuses on X," "zooming in on Y," "specifically").

**What this frame makes visible:**
- Documents that promise more scope than they deliver
- The gap between headline claims and body evidence
- Conclusions that apply to a narrow sub-question being presented as if they applied to the broad opening

**What this frame makes invisible:**
- The legitimacy of focused analysis (focused essays are not scope narrowing)
- The value of analytical depth on a specific sub-question (depth IS useful)
- Whether the broad framing was intentional misdirection or rhetorical convention

**Positive examples:** An essay titled "The Future of Work in the Age of AI" that argues for a specific VC-investment thesis about Bay Area developer tooling, with no marker that the answer is narrower than the question. The title promises civilizational scope; the body delivers industry-specific analysis; the gap is not named.

**Negative examples:** An essay titled "The Future of Work in the Age of AI" that states in its opening, "In this piece I focus on developer tooling because it's the domain where AI's effect is most measurable; broader labor-market implications are beyond my scope," then delivers developer-tooling analysis. This is focused analysis with explicit scope acknowledgment, not scope narrowing.

**Adjacent frames:** Completeness Illusion (FVS-010, signals comprehensive coverage but concentrates weight; related but distinct), Invisible Frame (FVS-020, the scope reduction can be invisible if the frame operating the narrowing is unnamed)

**When this frame is appropriate:** Evaluating analytical essays, policy pieces, op-eds, and any document whose opening makes a broad claim. Useful for distinguishing "focused analysis" from "bait-and-switch scope."

**When this frame is misleading:** The frame can over-fire on standard intro-to-specifics essay structure if the reader mistakes analytical scaffolding for covert narrowing. The "without acknowledgment" requirement is the critical test: if the document marks its narrowing, the frame does not fire.

**Honest limits:** Detection requires judging whether a document's opening promised more scope than the body delivers, AND whether the narrowing was acknowledged. Both are interpretive. At the text level, the detector can look for opening-vs-body scope mismatch and for explicit narrowing markers; the absence of markers is necessary but not sufficient evidence of covert narrowing.

**Revision note (2026-04-23, Phase 1C):** Revised from v1 to explicitly distinguish covert narrowing (frame fires) from acknowledged analytical scaffolding (frame does not fire). v1's broad reading fired on nearly every analytical essay (Claude 17/22, GPT-5.1 19/22 on v2); the narrow reading fired almost never (Gemini 1/22, Grok 5/22, GPT-5 5/22). v2 tightens toward narrow reading, requiring the absence of narrowing markers for the frame to fire. Predicted cross-family Gwet's AC1 lift: 0.094 → approximately 0.55-0.65.

## Generation affordances

**Rewrite prompt structure:** "The original question was [X]. This document primarily addresses [Y], which is a subset. List 3-5 other aspects of [X] that received little or no coverage. For each, write one paragraph of analysis at the same depth as the [Y] coverage."

**Salient questions under this frame:**
- Is the document answering the question I asked, or a narrower question?
- What parts of my original question were silently dropped?
- If I asked the same broad question to a different model, would it narrow to the same sub-question?
- Does the narrowing follow training-data density or analytical relevance?

## Branch applicability

**Primary branch:** Both A and B
**Branch A:** Not directly detectable from the document alone. Requires comparison between the user's original question (the topic field in Frame Check) and the document's actual coverage. When coverage analysis shows narrow focus (1-2 dimensions) on a topic that should be broad, scope narrowing is possible.
**Branch B:** The pre-commit step is the most direct detection: the user writes their broad-scope answer first, then sees AI's narrow-scope answer, and the comparison reveals the narrowing.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per [fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md). The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.794** (tier: **strong**), per [fvs_eval/v4/library_v4_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_reliability.json). Per-corpus reproducible values (regen: [fvs_eval/v4/compute_per_corpus_reliability.py](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/compute_per_corpus_reliability.py); artifact: [fvs_eval/v4/library_v4_per_corpus_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_per_corpus_reliability.json)): MG_v3=0.888 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.883 (3-family partial; Anthropic queued). Historical: MG2_v1=0.516 (library_v1), MG2_v2=0.818 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per [fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md); rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **1.000** across n=41 docs at temp=0 (0 verdict flip(s); per [fvs_eval/v4/grok_intra_rater_ac1.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/grok_intra_rater_ac1.json)). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.888, kappa -0.036, union 3/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): -0.06.
- **library_v2 (earlier variant):** Gwet's AC1 0.769, kappa -0.000, union 5/15.

See [fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md) §3 for library-wide tier context and [fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md) §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: [fvs_eval/mixed_genre_v1](https://github.com/lluvr/frame-check/tree/master/fvs_eval/mixed_genre_v1) n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.829 |
| Cohen's kappa (pairwise mean) | 0.037 |
| Raw agreement (pairwise mean) | 0.856 |
| Union prevalence | 4/15 = 27% |
| Intersection (all 4 agree positive) | 0/15 |

Per-family positives (of 15 docs): Claude 1, Gemini 1, Grok 1, GPT 2.
