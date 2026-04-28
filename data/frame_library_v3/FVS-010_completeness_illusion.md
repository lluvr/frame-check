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

**Adjacent frames:** Growth Frame (FVS-008, the frame most commonly concealed by completeness illusion), Fluency-Quality Illusion (FVS-002, the surface quality that makes performative coverage feel sufficient), Failure Framing (FVS-007, the antidote: concrete failure conditions expose performative risk sections)

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

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.227 |
| Gwet's AC1 (pairwise mean) | 0.349 |
| Raw agreement (pairwise mean) | 0.633 |
| Union prevalence (all families) | 65% |

Per-family positives (of 15 docs): Claude 11, Gemini 9, Grok 14, GPT-5 5.

**V4 detection mode:** honest-limit

**Interpretation:** Persistent cross-family divergence across all three metrics. Detection is interpretation-dependent; see fvs_eval/v4/RELIABILITY_STUDY.md for split-vote reasoning analysis.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-12; grounded-authorship retrofit 2026-04-25 per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04)
- HI-048 The Depth Illusion case study
- `detect_coverage` 5-category system in `framing.py` (rule-based detector)
- M-004 omission mechanism
- EXP-096 CHD pilot validation (9 documents scored 2026-04-14; vault internal scoring artifact (EXP-096))
- Tesla market analysis worked example (v1 Identification)
- AI safety evaluation worked example (124-page frontier-lab eval)
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Detection challenge: density vs presence. The 5-binary-category coverage detector measures presence/absence, not depth per category. The completeness illusion fires when dimensions are PRESENT but unevenly weighted. Density measurement (markers per 1K words) is a better proxy but still does not distinguish genuine analysis from keyword presence. Detection solution is incomplete; entry names the problem honestly per honest_limits.
2. Persistent split-vote at moderate prevalence. F-2026-027 v1 baseline showed AC1 0.349 - low for a prevalent frame (65% union). Cross-family divergence is structural: distinguishing "performative mention" from "substantive analysis" requires interpretive judgment beyond coverage detection. V4 detection mode is "honest-limit" acknowledging interpretive nature.
3. Meta-recursive nature. The completeness illusion is a frame about frames, which makes it potentially circular. Detection needs a baseline of what would constitute substantive coverage, which itself depends on the frame applied. The strip-the-mention test (would the document's argument change if the brief mention were removed) is the operational diagnostic; automating it is open work.

**Success record.** Two operationalized cases:
1. Tesla market analysis worked example (v1 Identification). Document scored 4/5 categories present but analytical weight was approximately 70% growth, 5% risk, 5% stakeholders, 15% trends, 5% uncertainty. Single-sentence "regulatory challenges exist" was performative not analytical. Strip-the-mention test confirmed: removing the risk mention does not change the document's argument; the mention is cosmetic.
2. EXP-096 CHD pilot validation (2026-04-14). 124-page frontier-lab AI safety evaluation scored 6/18 (33%) on a 9-point evaluation honesty checklist. Coverage of 12+ safety categories was extraordinary; reflection on what evaluation methodology cannot detect was zero. Highest-scoring document in pilot (11/18, 61%) had explicit "what is missing" section structured by the benchmark's own taxonomy. Demonstrates the completeness illusion operating at the highest-stakes level: deployment decisions made on the impression that evaluation was thorough.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where applying the strip-the-mention or density-not-presence test to a "comprehensive" analysis revealed weighted concentration on one frame; (2) the contrast between the surface-comprehensive reading and the density-weighted reading is concrete; (3) outcome differential observed (claim re-scoped, additional analysis demanded, conclusion downgraded in confidence); (4) concrete first-person recall. Held open per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application: ~2-5 minutes (read, identify dimensions, estimate per-dimension weight, run strip-the-mention test on thin sections)
- V4.2 LLM judge invocation: ~$0.0008/document (detection is interpretive; honest-limit mode)
- Density measurement (per-1K-word marker count): tooling-side, no per-invocation cost
- One-pass detection: appropriate for any document claiming comprehensive or balanced analysis
- Deep-dive engagement: appropriate for high-stake documents (EXP-096 demonstrates AI-safety-evaluation stake level)

**Applicability metadata.**
- Domains: market analysis (high stake-relevance), due diligence (high), policy assessment (high), AI safety evaluations (very high; EXP-096 evidence), investment analysis (high), comprehensive-titled research summaries (high)
- Decision types: any decision based on documents claiming balanced or comprehensive coverage
- Stake levels: medium to high; AI safety evaluations are the highest-stakes case
- Inappropriate contexts: genuinely-balanced documents (false-positive risk if reader applies excessive skepticism); narrowly-scoped focused analyses; documents that openly state their scope as narrow

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa 0.227, AC1 0.349 (low; persistent split-vote), raw 0.633, union prevalence 65% (Claude 11, Gemini 9, Grok 14, GPT-5 5 of 15)
- EXP-096 CHD pilot (2026-04-14): 9 documents scored on evaluation honesty (range 2/18 to 11/18); demonstrates the frame at frontier-AI-safety-evaluation stake level
- HI-048 The Depth Illusion origin study
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
