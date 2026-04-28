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

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.395 |
| Gwet's AC1 (pairwise mean) | 0.403 |
| Raw agreement (pairwise mean) | 0.689 |
| Union prevalence (all families) | 57% |

Per-family positives (of 15 docs): Claude 6, Gemini 12, Grok 9, GPT-5 7.

**V4 detection mode:** default

**Interpretation:** Moderate cross-family agreement.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-13; grounded-authorship retrofit 2026-04-25 per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04)

- `detect_coverage` stakeholders dimension in `framing.py` (rule-based detector)
- L2 reframe study (Growth-to-Stakeholder pair tested per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) §5.2)
- MCP integration: cited as canonical absent-frame in `_PROMPT_CHALLENGE_DOCUMENT` (`mcp_server.py` line ~3426)
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused)

**Failure record.** Three failure modes observed in operation:
1. Implicit stakeholder language missed by rule-based detector. Documents mentioning "3,000 jobs lost" or "communities impacted" without using stakeholder-vocabulary keywords slip through detection. The detector catches explicit stakeholder language but misses substantive stakeholder concerns expressed in concrete-impact terms. The honest_limits section names this; the failure record adds: this is the dominant under-detection failure mode for this frame.
2. Performative-mention false positive. A CSR section listing "our employees, our communities, and the environment" without analysis fires stakeholder-frame detection but is performative not substantive. The detector has no mechanism to distinguish substantive from performative; that distinction requires the density analysis from FVS-010 (Completeness Illusion).
3. Highest cross-family prevalence (57% union) with lowest AC1 (0.403) of the three retrofitted entries. The frame fires often but families disagree on the threshold for what counts (Claude 6/15, Gemini 12/15; 2x prevalence spread). Disagreement reflects the substantive-vs-performative ambiguity directly: families weight performative mention differently. Not noise; substantive cross-family interpretation gap.

**Success record.** Two operationalized cases:
1. Automation-platform worked example. The 40%-cost-reduction document presented company perspective as default; stakeholder-frame counter-frame surfaced "whose 40% is being reduced." The labor-to-technology cost transfer became visible. Demonstrates the operational value of perspective-shift even on a short document.
2. MCP `divergence` block integration. Stakeholder Frame is one of the canonical absent-frames cited in MCP prompts. The mapping `FVS-011 absent -> "Who does this recommendation affect differently that the document does not surface?"` is operationally embedded in the agent-facing surface as a high-leverage divergence target. Confirms the frame is useful to AI agents calling Frame Check via MCP, not only to direct readers.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific decision or analysis where the for-whom question was missing or wrong; (2) recognizing the stakeholder frame produced a different conclusion or surfaced a stakeholder you would not have considered; (3) the contrast between the company-default (or whoever-default) perspective and the stakeholder-shifted perspective is concrete, not generic; (4) concrete first-person recall. Held open per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application (no tools, experienced reader): ~30-60 seconds to scan a document for stakeholder presence/absence; substantive re-imagining from a specific stakeholder perspective takes longer (3-10 minutes depending on document complexity)
- V4.2 LLM judge invocation: ~$0.0008/document
- Branch B pre-commit (maintainer-side-named perspective before AI consultation): 1-2 minutes
- Appropriate use depths: any decision document affecting more than the immediate decision-maker

**Applicability metadata.**
- Domains: corporate decisions (high stake-relevance), policy analysis (high), product decisions (high), strategic-partnership evaluation (high), social impact assessment (high), ethics review (high), AI safety research (high)
- Decision types: any decision with externalities; any analysis of impact, transition, or change
- Stake levels: low to high. Even small decisions can have stakeholder implications worth surfacing.
- Inappropriate contexts: pure technical documentation (API references, mathematical proofs), data specifications, narrow factual queries, internal-only style guides

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa 0.395, AC1 0.403 (moderate), raw 0.689, union prevalence 57% (Claude 6, Gemini 12, Grok 9, GPT-5 7 of 15)
- L2 reframe study: tested in Growth-to-Stakeholder pair (per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) §5.2; coverage and density shifts confirmed)
- MCP integration: operationally embedded in `_PROMPT_CHALLENGE_DOCUMENT` as canonical absent-frame
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
