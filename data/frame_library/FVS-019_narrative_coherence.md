# Narrative Coherence

**FVS entry:** FVS-019
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** HI-012 (Fluency-Quality Illusion, narrative coherence is one form of fluency), EXP-094 (the confound where correct analysis within a wrong frame produces a coherent but wrong narrative)
**Status:** v1, single-curator. Withdrawn from v1 publication per [INDEX.md](https://github.com/lluvr/frame-check/blob/master/data/frame_library/INDEX.md) "v1 publication state" table (narrative coherence is one form of fluency-quality illusion; covered by FVS-002; absorbed). Source markdown preserved for citation continuity; the FVS-019 ID is reserved and will not be reused.

## Identification

A document tells a coherent story. The data points connect. The logic flows. The conclusions follow from the premises. This coherence feels like evidence of correctness because humans are wired to trust narratives. But narrative coherence is independent of factual accuracy: a completely fabricated story can be perfectly coherent, and a collection of accurate facts can be incoherent. AI systems produce highly coherent narratives by default because transformer models are trained to produce text where each token is conditioned on all preceding tokens, creating maximum local coherence. The coherence is an architectural property, not an epistemic one.

**What this frame makes visible:**
- How story structure makes claims feel true regardless of their factual basis
- Why a document that "makes sense" is not necessarily a document that is correct
- The distinction between logical coherence (the argument follows from its premises) and empirical coherence (the premises are true)

**What this frame makes invisible:**
- Data points that do not fit the narrative (they were omitted to maintain coherence)
- Alternative narratives that explain the same data differently
- The difference between "this story is well-told" and "this story is true"

**Positive examples:** An AI-generated analysis of a company's decline that constructs a compelling narrative: "rising costs led to margin pressure, which caused reduced investment, which led to competitive weakness, which accelerated the decline." Each step follows logically. The narrative is coherent. But: did rising costs actually cause margin pressure, or did management decisions cause both? The narrative picks ONE causal chain and tells it coherently, hiding the alternatives.

**Negative examples:** A document that explicitly presents competing narratives for the same data ("Narrative A: the decline was cost-driven. Narrative B: the decline was management-driven. The data is consistent with both.") is not operating from the narrative coherence frame because it makes the multiplicity of narratives visible.

**Adjacent frames:** Frame Amplification (FVS-001, narrative coherence deepens with each iteration as the story gets more detailed and more convincing), Fluency-Quality Illusion (FVS-002, narrative coherence is the macro version of fluency), Growth Frame (FVS-008, growth narratives are among the most coherent because growth is a simple story)

**When this frame is appropriate:** Evaluating any analytical document that tells a story: market analyses, case studies, strategic recommendations, historical accounts, investigative reports. Any context where the reader should ask "is this coherent because it is true, or because it is well-constructed?"

**When this frame is misleading:** Purely factual content that does not tell a story (data tables, specifications, reference material). Also misleading when applied to genuinely coherent truthful narratives: not every coherent story is fabricated.

**Honest limits:** Narrative coherence is not automatically detectable. The current detectors can identify: voice (analytical vs promotional), coverage breadth, temporal orientation, and epistemic basis. None of these directly measures narrative coherence vs factual accuracy. This entry names the pattern for reader awareness. Automated detection would require comparing the document's causal claims against verified causal relationships, which is an unsolved problem.

## Generation affordances

**Rewrite prompt structure:** "This document tells a coherent story. Identify the causal chain: A caused B caused C caused D. Then produce two alternative causal chains that explain the same data points differently. Name which data points are consistent with all three narratives and which are consistent with only one."

**Salient questions under this frame:**
- Is this coherent because it is true, or because it is well-constructed?
- What data points were omitted to make the story work?
- What alternative narratives could explain the same data?
- If one fact in the narrative turned out to be wrong, would the whole story collapse?

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Not directly detectable as a single signal. The combination of analytical voice + high coverage in one dimension + low uncertainty language + high fluency produces conditions where narrative coherence is most likely to be operating unchallenged.
**Branch B:** The pre-commit intervention disrupts narrative coherence by forcing the user to articulate their OWN narrative before reading AI's. The comparison reveals whether the user adopted AI's narrative or maintains their own.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per [fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md). The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.838** (tier: **strong**), per [fvs_eval/v4/library_v4_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_reliability.json). Per-corpus reproducible values (regen: [fvs_eval/v4/compute_per_corpus_reliability.py](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/compute_per_corpus_reliability.py); artifact: [fvs_eval/v4/library_v4_per_corpus_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_per_corpus_reliability.json)): MG_v3=0.638 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.811 (3-family partial; Anthropic queued). Historical: MG2_v1=0.806 (library_v1), MG2_v2=0.622 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per [fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md); rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **1.000** across n=41 docs at temp=0 (0 verdict flip(s); per [fvs_eval/v4/grok_intra_rater_ac1.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/grok_intra_rater_ac1.json)). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.638, kappa 0.023, union 15/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): +0.04.
- **library_v2 (earlier variant):** Gwet's AC1 0.757, kappa 0.308, union 15/15.

See [fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md) §3 for library-wide tier context and [fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md) §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: [fvs_eval/mixed_genre_v1](https://github.com/lluvr/frame-check/tree/master/fvs_eval/mixed_genre_v1) n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.673 |
| Cohen's kappa (pairwise mean) | 0.271 |
| Raw agreement (pairwise mean) | 0.778 |
| Union prevalence | 15/15 = 100% |
| Intersection (all 4 agree positive) | 9/15 |

Per-family positives (of 15 docs): Claude 10, Gemini 10, Grok 14, GPT 14.
