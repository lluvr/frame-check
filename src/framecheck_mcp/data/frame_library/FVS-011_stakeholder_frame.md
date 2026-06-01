# Stakeholder Frame

**FVS entry:** FVS-011
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13

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
