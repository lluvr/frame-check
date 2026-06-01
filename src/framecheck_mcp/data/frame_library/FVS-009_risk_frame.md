# Risk Frame

**FVS entry:** FVS-009
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12

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
