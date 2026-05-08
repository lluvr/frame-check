# Temporal Anchoring

**FVS entry:** FVS-014
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** temporal_orientation in framing.py, EXP-094 (training-cutoff confabulation regimes), the Observatory cadence design
**Status:** v1, single-curator, reviewers wanted

## Identification

A document anchors the reader's perception of time by choosing which temporal orientation to emphasize. Past-anchored documents present historical data as the lens for understanding the present. Future-projected documents present forecasts as the lens for understanding the present. Present-focused documents treat the current moment as if it were the complete picture. Each orientation hides the others: a future-projected document about AI makes the history of technology hype invisible; a past-anchored document about market performance makes the structural changes that break historical patterns invisible.

**What this frame makes visible:**
- How temporal orientation shapes which conclusions feel natural (past data supports trend extrapolation; future data supports optimism or fear; present data supports urgency)
- Why AI output has systematic temporal biases (training data is historical; models extrapolate from what was, not from what is changing)
- How documents that claim to be "comprehensive" often have a single dominant temporal orientation that shapes all their conclusions

**What this frame makes invisible:**
- Whichever temporal orientation is absent. Future-projected documents hide historical base rates. Past-anchored documents hide structural discontinuities. Present-focused documents hide trajectory.
- The training-cutoff effect: AI models present pre-cutoff data as current, making the temporal orientation partially a function of when the model was trained, not of what is actually happening

**Positive examples:** An economic outlook report with explicit temporal structure: "Historical trend (2010-2024): X. Current conditions (2025): Y. Forward projection (2026-2030): Z. Assumptions underlying the projection: A, B, C." Each temporal orientation is named and gets substantive analysis.

**Negative examples:** An AI-generated industry analysis where all data points are from 2022-2023 training data but the document uses present tense ("the market IS worth $X") without acknowledging that the numbers are 2-3 years old. The temporal anchoring is in the training data, not in the current reality.

**Adjacent frames:** Growth Frame (FVS-008, typically future-projected with growth assumptions), Uncertainty Frame (FVS-012, future projections always carry uncertainty that temporal anchoring may hide), Oracle Frame (FVS-013, oracle mode accepts the temporal orientation without checking against current data)

**When this frame is appropriate:** Any document that presents time-varying information: market analysis, economic assessment, technology trends, demographic projections, scientific findings that evolve. Particularly important for AI-generated content where training-cutoff effects create invisible temporal distortion.

**When this frame is misleading:** Timeless factual content (mathematical constants, geographical facts that change slowly, established scientific laws). Temporal anchoring analysis adds noise where the content is not time-dependent.

**Honest limits:** The temporal orientation detector in framing.py measures past/present/future sentence ratios via regex patterns (PAST_RE, FUTURE_RE). This captures explicit temporal language but misses implicit temporal framing (a document using present tense for historical data). The training-cutoff detection is not automated; it requires the reader to know when the model's training data ends and compare against the document's claimed recency.

## Decision-readiness implication

**Direct readiness implication.**

When a document over-anchors to one temporal orientation, it crowds out the others. Affects:

- **Coverage** ([methodology](/corpus/decision-readiness/)) indirectly: a single temporal frame is structurally narrow on what perspectives a reader can consider.
- **Counterfactual**: a future-projected document hides historical disconfirmations; a past-anchored document hides structural changes that break historical patterns.

Frame Check's temporal distribution signal (in the Document Structure card) is the direct measurement.

## Generation affordances

**Rewrite prompt structure:** "Identify this document's temporal center of gravity: is it primarily past-anchored, present-focused, or future-projected? Then rewrite the analysis from the ABSENT temporal orientation. If the document is future-projected, rewrite anchored in historical base rates. If past-anchored, rewrite with current conditions and forward projections."

**Counter-document prompt:** "This analysis was produced by an AI model with training data through [date]. Identify every claim that might be stale: numbers that could have changed, rankings that could have shifted, trends that could have reversed. Annotate each with: 'verified current as of [date]' or 'potentially stale (training data vintage).'"

**Salient questions under this frame:**
- What is this document's temporal center of gravity?
- Are the numbers current, or are they from the model's training data presented as current?
- What would this analysis look like if anchored in a different time period?
- Does the future projection account for structural changes, or does it extrapolate the past?

## Worked example

**Document excerpt:** "AI is transforming healthcare. Machine learning applications in diagnostics achieved 95% accuracy in clinical trials. Telemedicine adoption reached 38% during the pandemic and continues to grow."

**Frame present:** Past-anchored with present-tense framing. "Achieved 95% accuracy" is a past result. "Reached 38% during the pandemic" is 2020-2021 data. "Continues to grow" is an extrapolation from past trend.

**Frame absent:** Current conditions (has telemedicine adoption continued growing post-pandemic, or has it plateaued?), future uncertainty (what are the barriers to continued AI adoption in healthcare?), structural changes (how has regulation changed since the clinical trials?).

**How to read past it:** Check the vintage of each claim. "95% accuracy in clinical trials" from when? "38% adoption" measured when? If the model's training data ends in early 2025, these numbers are 3-5 years old. Present tense makes them feel current when they may not be.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected via temporal_orientation output. Dominant past or dominant future orientation with low coverage of the opposite is the signal. Also detectable when the document uses present tense for claims that are likely from training data (requires cross-checking against known training cutoffs).
**Branch B:** The user can anchor their own temporal orientation in the pre-commit: "I am thinking about this topic as of [today]. What is my current understanding?" This creates a temporal reference point that makes the AI's potentially stale training data visible.

## Vocabulary connections

- **The amplification thesis** (HI-062): temporal orientation amplifies across a session. A past-anchored first response sets the temporal frame for every subsequent response.
- **Source conditioning** (T-351): providing current source material is the antidote to training-data-vintage temporal anchoring. The source material sets the temporal frame, not the model's training data.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md. The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.587** (tier: **moderate**), per fvs_eval/v4/library_v4_reliability.json. Per-corpus reproducible values (regen: fvs_eval/v4/compute_per_corpus_reliability.py; artifact: fvs_eval/v4/library_v4_per_corpus_reliability.json): MG_v3=0.446 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.77 (3-family partial; Anthropic queued). Historical: MG2_v1=0.581 (library_v1), MG2_v2=0.501 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md; rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **0.946** across n=41 docs at temp=0 (2 verdict flip(s); per fvs_eval/v4/grok_intra_rater_ac1.json). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/Clarethium/frame-check/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.446, kappa 0.106, union 15/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): +0.24.
- **library_v2 (earlier variant):** Gwet's AC1 0.159, kappa 0.003, union 15/15.

See fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md §3 for library-wide tier context and fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: fvs_eval/mixed_genre_v1 n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.685 |
| Cohen's kappa (pairwise mean) | 0.351 |
| Raw agreement (pairwise mean) | 0.789 |
| Union prevalence | 15/15 = 100% |
| Intersection (all 4 agree positive) | 9/15 |

Per-family positives (of 15 docs): Claude 11, Gemini 10, Grok 14, GPT 12.
