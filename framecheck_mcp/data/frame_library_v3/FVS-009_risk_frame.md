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

**Adjacent frames:** Growth Frame (FVS-008, the explicit counter-frame), Failure Framing (FVS-007, the technique for making risk concrete), Frame Amplification (FVS-001, risk frame also amplifies: a session that starts from risk gets progressively more pessimistic)

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

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.685 |
| Gwet's AC1 (pairwise mean) | 0.735 |
| Raw agreement (pairwise mean) | 0.856 |
| Union prevalence (all families) | 65% |

Per-family positives (of 15 docs): Claude 9, Gemini 10, Grok 11, GPT-5 9.

**V4 detection mode:** default

**Interpretation:** Substantial cross-family agreement.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-12; grounded-authorship retrofit 2026-04-25 per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04)
- M-004 Frame Inventory corpus
- EXP-094 Mauna Loa analysis case study
- `detect_coverage` risks dimension in `framing.py` (rule-based detector)
- L2 reframe study Growth-to-Risk pair (per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) §5.2)
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Risk Frame amplifies just like Growth Frame. A session that starts from risk generates progressively darker analysis (HI-062 amplification thesis applies symmetrically). Risk amplification produces risk paralysis: every conceivable risk listed without probability assessment, severity ranking, or mitigation planning. The cure is the same as for Growth Frame: frame breaks via library alternatives.
2. Detection misses euphemized risks. Documents that say "challenges" instead of "risks," "headwinds" instead of "threats," or "considerations" instead of "vulnerabilities" pass through detection at lower fire rates. The euphemism class is a known under-detection failure mode; partial mitigation by V4.2 LLM judge but rule-based detection misses these.
3. Risk-frame-only document is still narrow. A document with high risks coverage but absent growth, stakeholder, or uncertainty framing exhibits Risk Frame but is structurally single-frame. Multi-frame coverage is the goal; per-frame detection is necessary but not sufficient.

**Success record.** Two operationalized cases:
1. Cloud infrastructure worked example (v1 Identification). Document presented growth-only reading: 28% growth, 67% concentration favoring leaders, AI workload migration accelerating. Risk Frame counter-frame surfaced: 67% concentration is critical-infrastructure risk for three companies; 28% growth rate is unsustainable long-term; AI workload migration is unquantified. Decision changed from "invest in cloud infrastructure companies" to "invest selectively, hedge against concentration risk, verify AI workload migration translates to sustainable revenue."
2. L2 reframe controlled-transformation study. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) §5.2, Growth-to-Risk pair scored 5/5 on coverage shift, 5/5 on density shift, 5/5 on suggestion shift across two documents and frame-pairs. One of the cleanest reframe operations in the L2 study; structural validation that Risk and Growth are operationally distinct counters, not nominal opposites.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where applying the Risk Frame to an opportunity-framed or growth-framed analysis surfaced a vulnerability that was not visible from inside the original frame; (2) outcome differential observed (decision adjusted, position rebalanced, exposure reduced); (3) the contrast between the original frame's reading and the risk-framed reading is concrete; (4) concrete first-person recall. Held open per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application (no tools, experienced reader): ~30-60 seconds to ask "what could go wrong here; what assumptions does this depend on"
- V4.2 LLM judge invocation: ~$0.0008/document
- L2 reframe (Growth-to-Risk counter-rewrite): ~$0.010/invocation
- One-pass detection: appropriate for any business decision document
- Deep-dive engagement: appropriate when document drives high-stake decision; counter-frame rewrite is the operational tool

**Applicability metadata.**
- Domains: due diligence (high stake-relevance), investment analysis (high), regulatory assessment (high), safety evaluation (high), strategic decisions (high), AI-generated business content (high counter-frame)
- Decision types: investment, partnership, hiring, market entry, strategic positioning, M&A
- Stake levels: medium to high. Low-stake casual reading does not require Risk Frame counter-reading.
- Inappropriate contexts: when used as cover for fear (risk-listing not risk-analysis); when probability assessment is absent; when applied to questions where action is the correct call but Risk Frame is invoked to justify inaction

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa 0.685, AC1 0.735 (substantial), raw 0.856, union prevalence 65% (Claude 9, Gemini 10, Grok 11, GPT-5 9 of 15) - one of the highest-agreement frames in the library
- L2 reframe study: 5/5 on Growth-to-Risk transitions across two documents and one consistency check
- EXP-094 Mauna Loa: applied as counter-frame in scientific-claim adversarial reading
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
