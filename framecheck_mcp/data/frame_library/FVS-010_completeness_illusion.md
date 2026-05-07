# Completeness Illusion

**FVS entry:** FVS-010
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** HI-048 (The Depth Illusion), detect_coverage 5-category system in framing.py, M-004 (the omission mechanism), FVS-001 (frame amplification within an apparently complete frame)
**Status:** v1, single-curator, reviewers wanted

## Identification

A document that addresses all expected analytical dimensions (causes, risks, stakeholders, trends, uncertainty) can still operate from a single dominant frame. Breadth of coverage is not the same as breadth of perspective. A document that mentions risks in one sentence but spends ten paragraphs on growth is technically complete but practically dominated by the growth frame. The completeness illusion is the assumption that covering all categories means the analysis is balanced.

**What this frame makes visible:**
- How documents can use coverage breadth as a shield against frame criticism ("we addressed risks") while the actual analytical weight is concentrated in one frame
- The difference between mentioning a dimension and actually analyzing it (one sentence on risks is not risk analysis)
- How density per dimension matters more than presence: a document that mentions stakeholders once is not the same as one that dedicates a section to stakeholder analysis

**What this frame makes invisible:**
- The balance of analytical weight across dimensions (which dimensions get paragraphs vs which get sentences)
- Whether the brief mentions of non-dominant dimensions are substantive or performative
- That "comprehensive" is a coverage claim, not a perspective claim: you can comprehensively analyze from a single frame

**Positive examples:** A 10-page market analysis that mentions risks in a half-paragraph "Risk Factors" section at the end, discusses causes and trends for 7 pages, and notes stakeholders in one sentence. The coverage detector might show 4/5 categories present, but the analytical weight is 70% growth, 5% risk, 5% stakeholders, 15% trends, 5% uncertainty.

**Negative examples:** A document with genuinely balanced analytical weight across dimensions (2 pages each on growth, risks, stakeholders, trends, and uncertainty, with each section receiving the same level of evidence and reasoning) does NOT exhibit the completeness illusion because the coverage is substantive, not performative.

**Adjacent frames:** Growth Frame (FVS-008, the frame most commonly concealed by completeness illusion; growth framing does not require completeness illusion to operate, the inverse is not symmetric), Fluency-Quality Illusion (FVS-002, the surface quality that makes performative coverage feel sufficient), Failure Framing (FVS-007, concrete failure conditions expose performative risk sections; completeness illusion can coexist with unspecified failure criteria without either causing the other), False Balance (FVS-017, a specific form of completeness illusion in which the "completeness" the document performs is across opinion camps rather than across analytical dimensions), Stakeholder Frame (FVS-011, the counter-frame that exposes performative stakeholder mentions; completeness illusion's stakeholder dimension typically gets brief mention without analysis, while stakeholder framing asks for per-group impact analysis), Uncertainty Frame (FVS-012, the counter-frame that exposes performative uncertainty mentions; completeness illusion's uncertainty dimension typically gets brief hedging without probability analysis, while uncertainty framing asks for real probability assessment)

**When this frame is appropriate:** Evaluating any document that claims to be comprehensive, balanced, or analytical. Due diligence review. Investment analysis. Policy assessment. Any context where the reader needs to distinguish between breadth of coverage and depth of perspective.

**When this frame is misleading:** When a document genuinely IS balanced but triggers the completeness illusion detector because the reader applies excessive skepticism. Not every comprehensive document is performing completeness. The illusion exists when breadth substitutes for depth, not when breadth coexists with depth.

**Honest limits:** The completeness illusion is a frame about frames, which makes it meta and potentially circular. The detection challenge is real: distinguishing "performative mention" from "substantive analysis" in a one-sentence section requires understanding the section's depth relative to the document's overall analytical investment. The current coverage detector (5 binary categories: present/absent) does not measure density per category. The density measurement (markers per 1K words) is a better proxy but still does not distinguish genuine analysis from keyword presence. This entry names the problem. The detection solution is incomplete.

## Decision-readiness implication

**Direct readiness implication.**

When this frame fires, the document covers many analytical perspectives at very different depths. Affects:

- **Coverage** ([methodology](/corpus/decision-readiness/)) specifically the balance signal: high coverage_count + low coverage_balance is the structural signature. Presence is the strongest indicator that count-only coverage measures are misleading; balance must be read alongside count to distinguish substantive from nominal coverage.

## Generation affordances

**Rewrite prompt structure:** "This document claims to be comprehensive. For each analytical dimension (risks, stakeholders, causes, trends, uncertainty), measure the proportion of the document dedicated to that dimension. Then for any dimension receiving less than 10% of the document's analytical weight, expand it to match the depth given to the dominant dimension."

**Counter-document prompt:** "This document covers multiple analytical dimensions but with uneven depth. Rewrite it so that every dimension present receives equal analytical depth. The thinnest dimensions should be expanded to match the document's strongest section in data points, reasoning, and evidence standard. Do not add new data or perspectives. Redistribute the existing analytical depth evenly across the dimensions already present."

**Salient questions under this frame:**
- Does this document MENTION all dimensions or ANALYZE all dimensions?
- How many words/sentences does each analytical dimension receive relative to the total?
- If I removed the one-sentence mentions of risk/stakeholders/uncertainty, would the document's argument change at all?
- Is the "Risk Factors" section substantive or performative?

## Worked example

**Document excerpt:** "This comprehensive analysis examines Tesla's market position. Revenue grew 19% to $96.8 billion. The company's Full Self-Driving technology continues to advance, with the supervised FSD user base expanding rapidly. Vehicle deliveries increased across all markets. While some regulatory challenges exist and competition is intensifying, Tesla's brand strength and vertical integration provide durable competitive advantages. The outlook remains positive with new model launches planned for 2025-2026."

**Coverage analysis:** Causes (2: FSD technology, vertical integration), Trends (3: revenue growth, delivery growth, model launches), Risks (1: "regulatory challenges exist"), Stakeholders (0), Uncertainty (1: "competition is intensifying"). Score: 4/5 categories present.

**Completeness illusion:** The document appears to cover 4 of 5 dimensions. But the analytical weight is approximately: growth/trends 70%, competitive advantages 20%, risks 8%, uncertainty 2%. The single sentence "while some regulatory challenges exist and competition is intensifying" is a performative mention, not analysis. It does not name which regulations, which competitors, what the timeline is, or what the impact would be.

**How to read past it:** Strip the risk mention and see if the document's argument changes. It does not. The mention is cosmetic. A document with substantive risk analysis would change its conclusions (or at least its confidence) when the risk section is weighted equally.

## Worked example 2: AI safety evaluation

**Document profile:** A 124-page AI safety evaluation from a frontier lab. Covers alignment assessment, model welfare, reward hacking, biological risk, cybersecurity, agentic safety, bias evaluation, child safety, jailbreak resistance, and third-party assessments. The evaluation is extraordinarily thorough by any existing standard.

**Coverage analysis (CHD pilot, 9 documents scored):** The document covers 12+ safety evaluation categories with detailed results, comparison tables, and specific metrics. It scores 6/18 (33%) on a 9-point evaluation honesty checklist that asks whether the document is honest about what its evaluations measure and where they are blind.

**Completeness illusion:** The document covers every major safety evaluation category. But it never asks whether its evaluation metrics measure what they claim to measure. "Harmless response rate: 98.43%" is defined operationally (auto-grader classification rate) but the gap between what the auto-grader classifies and what "harmless" means in context is not named. Zero pages of a 124-page document reflect on confounds in the evaluation methodology, what the evaluation cannot detect, or what findings were tested and overturned. The coverage of many evaluation CATEGORIES substitutes for honesty about evaluation METHODOLOGY.

**How to read past it:** Ask: does this document tell me what its evaluations CANNOT detect? A 124-page evaluation with no section on what the evaluations miss is structurally identical to the Tesla analysis that mentions risks in one sentence. The measurement breadth creates the impression that the evaluation is complete. Applying the same density test: evaluation category depth is extraordinary, evaluation methodology critique is zero. The ratio is effectively infinite.

**What makes this higher-stakes than market analysis:** When the completeness illusion operates in a market analysis, investors may over-allocate capital. When it operates in an AI safety evaluation, deployment decisions are made based on the impression that the evaluation was thorough. The structural completeness of the safety card may be the evaluation surface where the completeness illusion matters most.

**Source:** CHD pilot validation (EXP-096, 9 documents, 2026-04-14). Vault: internal scoring artifact (EXP-096). The highest-scoring document (11/18, 61%) was a benchmark methodology paper that dedicated a multi-page section to "What is missing," structured by the benchmark's own taxonomy. The lowest-scoring non-marketing document (2/18, 11%) was the most-cited AI benchmark, which presents evaluation results without reflecting on the evaluation instrument.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected via coverage density analysis (not just presence/absence). When the coverage detector shows 4-5 categories present but the density per 1K words for risks, stakeholders, or uncertainty is below a threshold (e.g., <2 markers per 1K words when trends is >10 markers per 1K words), the completeness illusion is flagged. This is the diagnostic that distinguishes "mentions risks" from "analyzes risks."
**Branch B:** In the pre-commit intervention, the user can name their own completeness expectation: "I expect the AI to produce a balanced analysis that weighs risks equally with growth." The pre-commit makes the expectation explicit so the user can check whether the output met it or performed it.

## Vocabulary connections

- **The construction trace** (T-356): without generating your own balanced analysis, you cannot detect when AI has performed balance rather than achieved it. The construction trace is what makes you notice "wait, the risk section is one sentence."
- **The first read** (M-002): the first read processes the document holistically. A document that hits all major keywords triggers a "complete" first read even if the analytical weight is heavily skewed. The conscious evaluation has to override the first read to notice the imbalance.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md. The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.373** (tier: **weak**), per fvs_eval/v4/library_v4_reliability.json. Per-corpus reproducible values (regen: fvs_eval/v4/compute_per_corpus_reliability.py; artifact: fvs_eval/v4/library_v4_per_corpus_reliability.json): MG_v3=0.422 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.452 (3-family partial; Anthropic queued). Historical: MG2_v1=0.336 (library_v1), MG2_v2=0.38 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md; rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **0.905** across n=41 docs at temp=0 (3 verdict flip(s); per fvs_eval/v4/grok_intra_rater_ac1.json). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/Clarethium/frame-check-mcp/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.422, kappa 0.228, union 9/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): -0.12.
- **library_v2 (earlier variant):** Gwet's AC1 0.372, kappa 0.022, union 11/15.

See fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md §3 for library-wide tier context and fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: fvs_eval/mixed_genre_v1 n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.302 |
| Cohen's kappa (pairwise mean) | 0.194 |
| Raw agreement (pairwise mean) | 0.611 |
| Union prevalence | 11/15 = 73% |
| Intersection (all 4 agree positive) | 1/15 |

Per-family positives (of 15 docs): Claude 5, Gemini 3, Grok 1, GPT 10.
