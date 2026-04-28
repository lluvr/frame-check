# Stakeholder Frame

**FVS entry:** FVS-011
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** detect_coverage stakeholders dimension in framing.py, FVS-008 (Growth Frame as typical counter)
**Status:** v1, single-curator, reviewers wanted

## Identification

Organizes information around who is affected by the subject under discussion, who benefits, who bears costs, and whose perspective is represented or excluded. The stakeholder frame asks: for whom? Most AI-generated business analysis defaults to the shareholder/company perspective without naming it as a perspective. The stakeholder frame makes the "for whom" question explicit and reveals whose interests the analysis serves.

**What this frame makes visible:**
- Who benefits from the described outcome and who bears the cost
- Which populations are represented in the analysis and which are absent
- Power dynamics: who has agency in the described situation and who is acted upon
- Second-order effects: how the subject impacts people beyond the primary actors

**What this frame makes invisible:**
- Technical mechanisms and market dynamics (the "how" behind the impact)
- Quantitative scale and trajectory (the "how much" and "how fast")
- Strategic positioning and competitive advantage (the "what should the company do")
- Whether the stakeholder impact is intended, incidental, or avoidable

**Positive examples:** An AI safety report that examines how a proposed regulation affects: model developers (compliance costs), application builders (deployment constraints), end users (access changes), affected communities (protection improvements), researchers (access to model weights). Each stakeholder group gets substantive analysis.

**Negative examples:** A corporate social responsibility section that lists "our employees, our communities, and the environment" without analyzing specific impacts, tradeoffs, or unintended consequences for any of them. Performative stakeholder mention without analysis.

**Adjacent frames:** Growth Frame (FVS-008, typically omits stakeholders entirely), Completeness Illusion (FVS-010, may mention stakeholders briefly without analysis), Risk Frame (FVS-009, shares the "what could go wrong" dimension but from a different entry point)

**When this frame is appropriate:** Impact assessment, policy analysis, corporate governance, social impact evaluation, any context where the reader needs to understand who wins, who loses, and whose voice is absent.

**When this frame is misleading:** Pure technical documentation (API references, mathematical proofs, data specifications). The stakeholder frame adds noise where the question is "how does this work" rather than "who does this affect." Also misleading when applied without specificity: "stakeholders include everyone" is vacuous.

**Honest limits:** "Stakeholder frame" is a common concept in business and policy analysis but is not a formal category from a specific research tradition in this usage. The detection heuristic (presence/absence of stakeholders-dimension markers in coverage analysis) catches explicit stakeholder language but misses implicit stakeholder concerns expressed without the vocabulary (e.g., "3,000 jobs lost" is a stakeholder impact without using stakeholder language). The current detector has no way to assess whether stakeholder mentions are substantive or performative; that distinction requires the density analysis from FVS-010.

## Decision-readiness implication

**Direct readiness implication.**

When this frame fires, the document explicitly organizes around who is affected, who benefits, who bears costs. Affects:

- **Coverage** ([methodology](/corpus/decision-readiness/)): strengthens coverage on the stakeholders dimension. Absence of the frame in a context where stakeholders matter is a Coverage gap; presence indicates the document has done the 'for whom' work.

## Generation affordances

**Rewrite prompt structure:** "For each claim or recommendation in this document, add a stakeholder annotation: who benefits, who bears the cost, whose perspective is represented, and whose is absent. If the document cannot answer these for a given claim, that claim has an unnamed stakeholder gap."

**Counter-document prompt:** "Rewrite this analysis from the perspective of the stakeholder group whose interests are LEAST served by the current framing. If the document analyzes market growth, rewrite from the perspective of the community displaced by that growth. If it analyzes cost reduction, rewrite from the perspective of the workers whose roles are being eliminated."

**Salient questions under this frame:**
- For whom is this analysis written? Whose interests does it serve by default?
- Which groups are affected but not discussed?
- If the recommendations were implemented, who benefits and who bears the cost?
- Is the stakeholder mention substantive or performative?

## Worked example

**Document excerpt:** "The AI-powered automation platform reduces operational costs by 40% and increases throughput by 3x. Implementation requires a 6-month transition period with full ROI achieved within 18 months."

**Frame present:** Company/efficiency perspective. Costs and throughput are measured from the company's position.

**Frame absent:** Stakeholder perspective. What happens to the people whose work is being automated? What is the employment impact? Do customers experience service quality changes during the transition? Are there supplier relationships affected? The 40% cost reduction is someone's eliminated role.

**How to read past it:** Ask "whose 40% is being reduced?" and "who experiences the transition period?" The cost reduction is not neutral; it is a transfer from labor costs to technology costs. The stakeholder frame makes the transfer visible.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected via coverage analysis. Presence of stakeholders-dimension markers indicates stakeholder framing is active. ABSENCE of stakeholders markers in a document that discusses outcomes, impacts, or changes is the more actionable signal: the analysis has stakeholder implications it does not name.
**Branch B:** In the pre-commit intervention, the user can name whose perspective they are evaluating from before consulting AI: "I am approaching this from the company's perspective. What would the employee perspective reveal?"

## Vocabulary connections

- **The amplification thesis** (HI-062): when the default perspective is the company/shareholder, AI amplifies that perspective across the session without surfacing alternative stakeholder views.
- **The construction trace** (T-356): stakeholder analysis requires generating the list of affected parties before reading the document. Without this generation step, the user accepts whatever stakeholders the document names (or omits) without noticing the gaps.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per [fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md). The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.493** (tier: **moderate**), per [fvs_eval/v4/library_v4_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_reliability.json). Per-corpus reproducible values (regen: [fvs_eval/v4/compute_per_corpus_reliability.py](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/compute_per_corpus_reliability.py); artifact: [fvs_eval/v4/library_v4_per_corpus_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_per_corpus_reliability.json)): MG_v3=0.451 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.458 (3-family partial; Anthropic queued). Historical: MG2_v1=0.56 (library_v1), MG2_v2=0.532 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per [fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md); rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **0.882** across n=41 docs at temp=0 (3 verdict flip(s); per [fvs_eval/v4/grok_intra_rater_ac1.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/grok_intra_rater_ac1.json)). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.451, kappa 0.429, union 13/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): -0.10.
- **library_v2 (earlier variant):** Gwet's AC1 0.454, kappa 0.404, union 10/15.

See [fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md) §3 for library-wide tier context and [fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md) §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: [fvs_eval/mixed_genre_v1](https://github.com/lluvr/frame-check/tree/master/fvs_eval/mixed_genre_v1) n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.353 |
| Cohen's kappa (pairwise mean) | 0.335 |
| Raw agreement (pairwise mean) | 0.656 |
| Union prevalence | 13/15 = 87% |
| Intersection (all 4 agree positive) | 4/15 |

Per-family positives (of 15 docs): Claude 5, Gemini 8, Grok 13, GPT 9.
