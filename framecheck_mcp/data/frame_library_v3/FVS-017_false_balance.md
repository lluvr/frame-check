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

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Structural signal only. When coverage analysis shows multiple dimensions with similar density AND the voice is analytical (not promotional), false balance is POSSIBLE but not confirmed. Confirmation requires domain knowledge about the evidence distribution. Frame Check can flag the structural pattern; the reader must assess the epistemic pattern.

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.089 |
| Gwet's AC1 (pairwise mean) | 0.866 |
| Raw agreement (pairwise mean) | 0.889 |
| Union prevalence (all families) | 7% |

Per-family positives (of 15 docs): Claude 3, Gemini 0, Grok 1, GPT-5 0.

**V4 detection mode:** meta (not detected by rule-based; consensus evaluation only)

**Interpretation:** Kappa paradox pattern (low Cohen's kappa due to prevalence extreme 7%, but Gwet's AC1 shows substantial cross-family agreement). Reliable under prevalence-robust metrics.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-13; grounded-authorship retrofit 2026-04-25 per FRAME_DIVERGENCE_v2.md §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04; prevalence 7 percent)
- FVS-010 Completeness Illusion (related pattern)
- `detect_coverage` in `framing.py`
- PROTOCOL_ARCHITECTURE.md CHD curation meta-frame
- Climate science worked example (v1 Identification)
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Kappa paradox at low prevalence. F-2026-027 showed kappa 0.089 (very low) but AC1 0.866 (substantial). Union prevalence 7 percent (Claude 3, Gemini 0, Grok 1, GPT-5 0 of 15). The frame fires rarely; kappa paradox-distorted; AC1 carries actual agreement signal under prevalence robustness.
2. Detection cannot assess epistemic balance. The coverage detector identifies multiple perspectives with similar depth (structural signal) but cannot assess whether depth is proportionate to evidence (epistemic signal). Knowing the actual evidence distribution requires domain knowledge that Frame Check does not have. The coverage_balance signal partially detects this; per-perspective evidentiary weighting is a known missing dimension.
3. Frame applies only to empirical claims. The frame targets questions where evidence can be weighed; not to normative claims where balance reflects legitimate pluralism (political opinions, value judgments, aesthetic preferences). Detection has no domain-context awareness for the empirical-vs-normative distinction; reader judgment is required.

**Success record.** Two operationalized cases:
1. Climate science worked example (v1 Identification). Document gave "equal paragraphs" to the scientific consensus (over 97 percent of published climate science) and to fringe questioning of human contribution (under 3 percent). Equal treatment misrepresents the field. Operational diagnostic: ask "if I removed the minority position, would the analysis be more accurate" - for false balance the answer is yes; for genuine debate the answer is no.
2. Calibration dimension partial signal. coverage_balance partially detects false balance through structural balance vs evidentiary-weight gap. Per-perspective evidentiary weighting is the missing dimension and is named as v0 limitation. Operational integration point with decision-readiness Calibration dimension; calibration failure is bidirectional (overconfidence in lower-supported view; under-confidence in better-supported view).

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where the operator caught a "balanced" presentation that gave equal weight to unequally-supported empirical claims; (2) the evidence-distribution check applied (what is the actual proportion of expert opinion or evidence behind each perspective); (3) outcome differential observed (presentation re-weighted to evidence; minority position scoped to its actual evidence base; conclusion re-anchored on consensus); (4) concrete first-person recall. Held open per FRAME_DIVERGENCE_v2.md P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application: ~1-2 minutes per balanced-looking analysis (assess evidence distribution per perspective)
- V4.2 LLM judge invocation: limited applicability (detects structural balance; cannot assess epistemic balance)
- Domain-knowledge verification: variable cost depending on domain familiarity; for unfamiliar domains, requires expert consultation or substantive literature review
- Use depth: any "balanced" analysis on empirically-weighable topic; especially valuable on AI-generated science reporting and policy analysis

**Applicability metadata.**
- Domains: science reporting (high stake-relevance), policy analysis (high), health information (high), historical interpretation with established consensus (medium), educational content (medium-high)
- Decision types: any decision based on perspective-weighted analysis; any inference about expert consensus
- Stake levels: medium to high; epistemic miscalibration at health/policy stakes is costly
- Inappropriate contexts: genuine debates with approximately even evidence; political opinions; value judgments; aesthetic preferences; normative claims where balance reflects legitimate pluralism

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa 0.089 (paradox-distorted), AC1 0.866 (substantial), raw 0.889, union prevalence 7 percent (Claude 3, Gemini 0, Grok 1, GPT-5 0 of 15)
- FVS-010 Completeness Illusion as related pattern
- PROTOCOL_ARCHITECTURE CHD section: curation meta-frame concern
- Climate science worked example
- V4 detection mode: meta (not detected by rule-based; consensus evaluation only)
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
