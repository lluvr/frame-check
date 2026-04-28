# False Balance

**FVS entry:** FVS-017
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** FVS-010 (Completeness Illusion, a related pattern), detect_coverage in framing.py, the curation meta-frame concern from PROTOCOL_ARCHITECTURE.md CHD section
**Status:** v1, single-curator, reviewers wanted

## Identification

A document presents multiple perspectives with equal weight regardless of whether the perspectives have equal evidentiary support. When AI is asked to "consider all sides," it produces balanced-looking output where a well-established scientific consensus and a fringe position receive the same analytical depth. False balance is the frame that treats all perspectives as equally valid because they exist, not because they are equally supported.

**What this frame makes visible:**
- How "balance" can be manufactured by giving equal space to unequal evidence bases
- Why AI defaults to false balance (the training objective rewards covering multiple perspectives, not weighing them by evidence)
- The gap between structural balance (equal word count per perspective) and epistemic balance (weight proportional to evidence)

**What this frame makes invisible:**
- The actual evidence distribution (one position may have 95% of the evidence; false balance makes it look like 50/50)
- Expert consensus (when nearly all qualified experts agree, presenting "both sides" misrepresents the state of knowledge)
- That the act of presenting a fringe position alongside a mainstream one elevates the fringe position's apparent credibility

**Positive examples:** An AI summary of climate science that gives equal paragraphs to "the scientific consensus that human activities cause warming" and "some researchers question the extent of human contribution." The second position exists but represents < 3% of published climate science. Equal treatment misrepresents the field.

**Negative examples:** A genuine academic debate where two well-supported positions have roughly equal evidence bases and the document fairly represents both with appropriate citations. This is real balance, not false balance.

**Adjacent frames:** Completeness Illusion (FVS-010, false balance is one specific form of performative completeness), Uncertainty Frame (FVS-012, false balance creates artificial uncertainty by elevating minority positions), Authority by Citation (FVS-016, false balance often cites fringe sources alongside mainstream ones)

**When this frame is appropriate:** Evaluating any "balanced" analysis of a topic where the evidence is NOT evenly distributed. Science reporting, policy analysis, health information, any domain where expert consensus exists.

**When this frame is misleading:** Genuine debates where the evidence IS approximately evenly distributed. Political opinions, value judgments, aesthetic preferences. The frame applies to EMPIRICAL claims where evidence can be weighed, not to normative claims where balance reflects legitimate pluralism.

**Honest limits:** False balance is extremely difficult to detect automatically because it requires knowing the actual evidence distribution for the topic under discussion. The coverage detector can identify when multiple perspectives are present with similar depth (the structural signal) but cannot assess whether the depth is proportionate to the evidence (the epistemic signal). This entry names the pattern for human recognition, not for automated detection.

## Decision-readiness implication

**Direct readiness implication.**

When this frame fires, the document gives equal weight to perspectives with unequal evidentiary support. Affects:

- **Calibration** ([methodology](/corpus/decision-readiness/)): overconfidence in the lower-supported perspective; under-confidence in the better-supported one. Both are calibration failures, in opposite directions.
- **Coverage**: technically broad on perspective count but structurally misleading on how each perspective is weighted.

The methodology page's coverage_balance signal partially detects this; per-perspective evidentiary weighting is a known missing dimension.

## Generation affordances

**Rewrite prompt structure:** "This document presents multiple perspectives on [topic]. For each perspective, annotate: (a) the approximate proportion of expert opinion supporting it, (b) the quality and quantity of evidence behind it, (c) whether equal treatment is proportionate to the evidence. Reweight the analysis so each perspective receives space proportional to its evidence base."

**Salient questions under this frame:**
- Are these perspectives actually equally supported, or does one have vastly more evidence?
- If I removed the minority position, would the analysis be more accurate?
- Is the "balanced" presentation a genuine reflection of the field, or is it manufactured?
- What would an expert in this field say about the balance of this presentation?

## Worked example

Two examples covering structurally distinct mechanisms of the frame: quantitative expert-distribution asymmetry, and qualitative evidence-quality asymmetry.

### Example 1: AI safety discourse (quantitative expert-distribution asymmetry)

**Document excerpt:** "Researchers are split on whether advanced AI systems pose existential risk. Some leading figures including Geoffrey Hinton, Yoshua Bengio, and Stuart Russell have argued near-term frontier AI development carries non-trivial probability of catastrophic outcomes within decades. Other prominent researchers including Yann LeCun and Andrew Ng have argued these concerns are overblown, that current architectures are far from systems capable of existential threat, and that the discourse distracts from concrete present harms such as bias and labor displacement. The truth likely lies somewhere between these positions; informed citizens should weigh both views when forming their stance on AI policy."

**Frame present:** Structural balance with two named camps. Three figures on one side, two on the other (rough parity). The phrasing parallels itself ("some... argued / others... argued"), and a closing synthesis sentence ("the truth likely lies somewhere between") treats the two named positions as if they bracket the discourse. The document reads as even-handed.

**Frame absent:** What the actual distribution of researcher views looks like. Surveys (AI Impacts, ML researcher polls, structured probability elicitations) typically show a non-bimodal distribution: most active researchers assign meaningful but not majority probability to catastrophic outcomes. The "doomer" pole and the "dismissive" pole are both vocal minorities; the median researcher sits somewhere uncertain in between, with substantial probability mass on neither extreme. Presenting two extremes as the discourse's brackets removes the median from view. The named figures are real researchers with real positions, but they are not representative of the distribution they are made to bracket.

**How to read past it:** For any "two-camp" presentation in technical or research discourse, ask who is in the middle. If the document only names the poles, it has quietly removed the median. When a document says "some argue X, others argue Y, the truth lies between" but doesn't name where the typical or median expert sits, that's false balance applied to expert distribution. Ask what the survey, poll, or elicitation data show about distribution shape, not just about the named poles. When that data exists and the document doesn't engage with it, the frame is at work.

### Example 2: AI infrastructure investment (qualitative evidence-quality asymmetry)

**Document excerpt:** "AI infrastructure investment outlook offers competing perspectives. **Bull case:** continued hyperscaler capex commitments through 2028 (over $190B committed in 2024 alone), with leading chipmakers maintaining 80% market share through CUDA ecosystem moat and architectural roadmap visibility. **Bear case:** AI capital expenditure may face sustainability pressure if monetization disappoints, with risks including custom-silicon competition (Google TPUs, AWS Trainium), export-control headwinds, and the historical pattern of dominant chip companies losing position in subsequent technology cycles. The truth likely lies between these scenarios; readers should weight both when forming their position."

**Frame present:** Structural balance. The two perspectives have comparable analytical depth and similar word counts, the structure parallels itself ("bull case" / "bear case"), and a closing synthesis sentence ("the truth likely lies between") treats both as equally plausible. The document looks even-handed on the surface.

**Frame absent:** What the actual evidence distribution looks like. At the time of writing, near-term hyperscaler capex commitments were documented in 10-K filings and earnings calls. The bear case's specific risks (custom silicon at scale, export-control catastrophe, capex collapse) had no comparable evidence for near-term materialization. The bull case rested on signed contracts and disclosed commitments; the bear case rested on possibilities, historical analogies, and unrealized risks. Treating them as 50/50 hides the asymmetry: one side has committed capital behind it, the other has narrative argument. The document doesn't name that asymmetry.

**How to read past it:** For any "balanced" presentation, ask what would change if you weighted each position by the quantity and quality of its evidence. In this case the bull-bear split isn't 50/50 over a 12-to-24-month horizon (the bear case's specific failure modes have no near-term precipitants), but it might approach 50/50 over a 5-to-10-year horizon (capex sustainability is genuinely contested at that horizon). Presenting both as equally weighted across all horizons flattens a horizon-dependent asymmetry into a flat ambivalence. Ask: what timeframe does this analysis cover, and does the evidence asymmetry change by timeframe? When the document gives parallel structure to two positions whose underlying evidence has asymmetric quality (signed-versus-speculative, documented-versus-historical-analogy), the frame is at work.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Structural signal only. When coverage analysis shows multiple dimensions with similar density AND the voice is analytical (not promotional), false balance is POSSIBLE but not confirmed. Confirmation requires domain knowledge about the evidence distribution. Frame Check can flag the structural pattern; the reader must assess the epistemic pattern.

## Vocabulary connections

- **The evidence discipline** ([METHODOLOGY.md](https://github.com/lluvr/frame-check/blob/master/METHODOLOGY.md) §6): false balance does the opposite of what construct-honesty asks for. Construct-honesty makes evidence asymmetry visible by naming what the detector measures and what it does not. False balance papers over evidence asymmetry by making the unequal look equal.
- **The amplification thesis** (HI-062, CLARETHIUM_VOCABULARY): false balance gets stronger when the same two-camp framing repeats across many sources. After enough repetition, the two camps start to look like the whole discourse, and the median view quietly drops out of public awareness.
- **The fluency-quality illusion** (FVS-002, HI-012): false balance often travels with fluency-quality illusion. A document with parallel structure and named-figure citations on each side reads as analytical and well-sourced; the polished form carries weight the underlying evidence does not earn.
- **Authority by citation** (FVS-016): false balance often uses authority by citation to make each side feel solid. Naming prominent figures on each side gives an authority signal, and the reader translates that into evidence weight, even though counting authorities is not the same as weighing evidence.
- **The completeness illusion** (FVS-010): false balance is a particular form of completeness illusion. The "completeness" the document performs is across opinion camps, not across the analytical dimensions a real complete analysis would cover.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per [fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md). The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.782** (tier: **strong**), per [fvs_eval/v4/library_v4_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_reliability.json). Per-corpus reproducible values (regen: [fvs_eval/v4/compute_per_corpus_reliability.py](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/compute_per_corpus_reliability.py); artifact: [fvs_eval/v4/library_v4_per_corpus_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_per_corpus_reliability.json)): MG_v3=0.841 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.883 (3-family partial; Anthropic queued). Historical: MG2_v1=0.789 (library_v1), MG2_v2=0.815 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per [fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md); rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **1.000** across n=41 docs at temp=0 (0 verdict flip(s); per [fvs_eval/v4/grok_intra_rater_ac1.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/grok_intra_rater_ac1.json)). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.841, kappa -0.031, union 4/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): -0.00.
- **library_v2 (earlier variant):** Gwet's AC1 0.927, kappa -0.014, union 2/15.

See [fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md) §3 for library-wide tier context and [fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md) §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: [fvs_eval/mixed_genre_v1](https://github.com/lluvr/frame-check/tree/master/fvs_eval/mixed_genre_v1) n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.837 |
| Cohen's kappa (pairwise mean) | -0.022 |
| Raw agreement (pairwise mean) | 0.867 |
| Union prevalence | 4/15 = 27% |
| Intersection (all 4 agree positive) | 0/15 |

Per-family positives (of 15 docs): Claude 3, Gemini 0, Grok 0, GPT 1.
