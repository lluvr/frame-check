# Risk Frame

**FVS entry:** FVS-009
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** M-004 (Frame Inventory, named as alternative frame), detect_coverage risks dimension in framing.py, FVS-001 worked example (risk as the absent frame), EXP-094 (Mauna Loa analysis)
**Status:** v1, single-curator, reviewers wanted

## Identification

Organizes information around what could go wrong, what is vulnerable, what depends on assumptions that might not hold, and what the consequences of failure look like. The counter-default to the growth frame in most AI-generated business analysis. The risk frame is not pessimism: it is the systematic examination of the conditions under which the primary narrative breaks.

**What this frame makes visible:**
- Vulnerabilities, failure modes, and what could go wrong
- Dependencies and assumptions underlying positive projections
- Historical precedents where similar situations deteriorated
- Concentration risk, regulatory risk, competitive risk, execution risk
- Who bears the cost if the positive scenario does not materialize

**What this frame makes invisible:**
- Opportunities and upside potential
- Why the positive case might be correct despite the risks
- Innovation and adaptation capacity that might address the risks
- That naming a risk is not the same as quantifying its probability (risk frames can over-weight low-probability scenarios)

**Positive examples:** A due diligence report that systematically examines each growth claim in a target company's pitch and names the conditions under which each claim would fail. Appropriate because due diligence exists to protect the buyer.

**Negative examples:** A risk analysis that lists every conceivable risk without assessing probability, severity, or mitigation. A document that uses the risk frame to justify inaction when action would be the correct call. Risk frame as cover for fear rather than as a tool for judgment.

**Adjacent frames:** Growth Frame (FVS-008, the explicit counter-frame), Failure Framing (FVS-007, the technique for making risk concrete; risk framing can operate without failure framing, the inverse is not always true), Frame Amplification (FVS-001, risk framing is a specific form of frame amplification that narrows onto downside scenarios; a session that starts from risk gets progressively more pessimistic; the inverse is not true), Stakeholder Frame (FVS-011, risk framing names what-could-go-wrong; stakeholder framing names who-is-affected; together they partition the risk dimension), Uncertainty Frame (FVS-012, risk framing states outcomes; uncertainty framing states their probability; both are needed to read a claim's epistemic weight)

**When this frame is appropriate:** Due diligence, investment analysis, regulatory assessment, safety evaluation, any context where understanding failure modes is the primary goal. Counter-reading any document that operates from a pure growth frame.

**When this frame is misleading:** When risk identification becomes risk paralysis. When every risk is given equal weight regardless of probability. When the risk frame is used to avoid decisions rather than to inform them. When naming risks feels like analysis but no probability assessment or mitigation planning follows.

**Honest limits:** "Risk frame" is a broad label containing many sub-frames (market risk, execution risk, regulatory risk, tail risk, systemic risk). Each sub-frame deserves its own analysis in a more mature library. The detection heuristic (high risks coverage in the coverage analysis) catches explicit risk discussion but misses documents that address risks euphemistically ("challenges" instead of "risks," "headwinds" instead of "threats"). The risk frame can itself amplify: a session that starts from risk generates progressively darker analysis, subject to the same frame amplification as the growth frame.

## Decision-readiness implication

**Direct readiness implication.**

When this frame fires, the document is organized around what could go wrong. Structural counterpart to the Growth Frame ([FVS-008](/corpus/library/FVS-008.html)):

- **Coverage** ([methodology](/corpus/decision-readiness/)): strengthens coverage on the risks dimension.
- **Counterfactual**: supports engagement (the frame asks 'what would falsify the recommendation').

A risk-frame-only document is still narrow; multi-frame coverage is the goal.

## Generation affordances

**Rewrite prompt structure:** "Rewrite this analysis from a risk frame. For each positive claim, name the specific condition under which it fails. For each projection, name the assumption it depends on and what happens if the assumption is wrong. For each competitive advantage, name the most likely competitive response."

**Counter-document prompt:** "This document organizes information around what could go wrong. Rewrite the same data from an opportunity perspective: for each risk cited, name the growth trajectory it depends on. For each vulnerability, name the defensive advantage already in place. For each uncertain assumption, name the evidence it will hold. Every number from the original should appear, reframed as evidence for opportunity rather than risk."

**Salient questions under this frame:**
- What would have to go wrong for this analysis to be incorrect?
- What assumptions is this projection based on, and are they testable?
- What is the historical base rate for outcomes this positive?
- Who has incentive to present this data in this frame, and what would they not show me?

## Worked example

**Document excerpt:** "Cloud infrastructure spending grew 28% in 2024, with the three major providers capturing 67% of the market. AI workload migration is accelerating."

**Growth frame reading:** Market growing fast, consolidation favors the leaders, AI is the driver.

**Risk frame reading:** 67% concentration means three companies control critical infrastructure. 28% growth rate is unsustainable long-term and may indicate over-provisioning. "AI workload migration is accelerating" is unquantified and could mask low-ROI deployments. What happens when the growth rate normalizes to 8-12%? What happens to the providers who built capacity for 28% growth?

**How the risk frame changes the decision:** Under the growth frame, the decision is "invest in cloud infrastructure companies." Under the risk frame, the decision is "invest selectively, hedge against concentration risk, verify that AI workload migration translates to sustainable revenue rather than trial deployments."

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected via coverage analysis. High coverage of risks dimension, especially when combined with other analytical dimensions (causes, uncertainty), signals a risk-aware document. ABSENCE of risk coverage in a document that claims analytical depth is the more common and more useful signal.
**Branch B:** The risk frame is one of the alternative frames the user can name in the pre-commit step: "I am approaching this question from a risk perspective."

## Vocabulary connections

- **The amplification thesis** (HI-062): the risk frame amplifies just as the growth frame does. Extended risk analysis produces progressively darker conclusions. The cure is the same: frame breaks via library alternatives.
- **Source conditioning** (T-351): grounding in source data is especially important under the risk frame because ungrounded risk analysis generates plausible-sounding threats that may not exist.
- **Failure Framing** (FVS-007, HI-016): risk framing names what could go wrong; failure framing makes the what-could-go-wrong specific enough to mitigate against. Risk frame without failure framing tends to produce fear rather than judgment; risk identification becomes risk paralysis.
- **The evidence discipline** ([METHODOLOGY.md](https://github.com/lluvr/frame-check/blob/master/METHODOLOGY.md) §6): risk framing without ground truth generates plausible-sounding threats that may not exist. Evidence discipline asks how the reader would know if a risk is real, and what evidence would distinguish a real risk from a manufactured one.
- **The fluency-quality illusion** (FVS-002, HI-012): risk frame can produce fluent-but-thin output where every conceivable risk is listed without probability or severity assessment. Fluent risk catalogs feel analytically thorough; without quantification they often serve avoidance rather than judgment.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per [fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md). The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.528** (tier: **moderate**), per [fvs_eval/v4/library_v4_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_reliability.json). Per-corpus reproducible values (regen: [fvs_eval/v4/compute_per_corpus_reliability.py](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/compute_per_corpus_reliability.py); artifact: [fvs_eval/v4/library_v4_per_corpus_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_per_corpus_reliability.json)): MG_v3=0.395 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.656 (3-family partial; Anthropic queued). Historical: MG2_v1=0.593 (library_v1), MG2_v2=0.605 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per [fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md); rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **0.909** across n=41 docs at temp=0 (2 verdict flip(s); per [fvs_eval/v4/grok_intra_rater_ac1.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/grok_intra_rater_ac1.json)). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.395, kappa 0.415, union 12/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): -0.04.
- **library_v2 (earlier variant):** Gwet's AC1 0.342, kappa 0.306, union 11/15.

See [fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md) §3 for library-wide tier context and [fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md) §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: [fvs_eval/mixed_genre_v1](https://github.com/lluvr/frame-check/tree/master/fvs_eval/mixed_genre_v1) n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.352 |
| Cohen's kappa (pairwise mean) | 0.347 |
| Raw agreement (pairwise mean) | 0.656 |
| Union prevalence | 13/15 = 87% |
| Intersection (all 4 agree positive) | 4/15 |

Per-family positives (of 15 docs): Claude 5, Gemini 7, Grok 13, GPT 8.
