# Uncertainty Frame

**FVS entry:** FVS-012
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** detect_coverage uncertainty dimension in framing.py, EXP-094 confound audit (the evidence discipline IS uncertainty framing applied to research claims)
**Status:** v1, single-curator, reviewers wanted

## Identification


**Uncertainty Frame fires when the document structurally organizes its analysis around what is unknown, contested, or assumption-dependent. The frame must be the ORGANIZING PRINCIPLE of the analysis, not a surface feature.**

The uncertainty frame asks: what do we not know? Most AI-generated analysis presents conclusions with high confidence even when the underlying evidence is thin, assumptions are untested, or expert consensus does not exist. Documents that surface the gap between confidence of presentation and confidence of evidence exhibit this frame.

The frame fires when the document:
- Explicitly names sources of uncertainty and weighs each (not just "there is uncertainty" but "uncertainty comes from: sources X, Y, Z, each weighted differently")
- Presents claims as ranges or point-estimates-with-error-bars as the primary evidential form, not as occasional hedges
- Surfaces expert disagreement or contested evidence as a structural element (a section or recurring move, not one mention in passing)
- Treats "what we don't know" as a primary section, argumentative move, or conclusion

The frame does NOT fire when:
- The document uses hedging language ("may," "could," "approximately," "likely") without treating uncertainty as the organizing principle
- Open questions or speculative phrasing appear in a document whose actual claims are presented confidently
- The document merely includes some uncertainty acknowledgments as politeness or genre convention; it must ORGANIZE around them
- A single hedged paragraph is embedded in an otherwise confident argument

**What this frame makes visible:**
- Claims presented as facts that are actually projections, estimates, or contested
- Assumptions underlying specific conclusions that have not been tested
- Error bars, confidence intervals, and ranges where the document presents point estimates
- Disagreement among experts or sources that the document does not mention
- The difference between "this is true" and "this is our best current estimate"

**What this frame makes invisible:**
- Action readiness (the uncertainty frame can produce paralysis if applied without context about what level of certainty is sufficient for the decision at hand)
- Relative confidence (not all uncertainties are equal; some are minor and some are decision-critical)
- Whether the uncertainty has practical implications for the specific decision being made

**Positive examples:** A climate science summary that presents temperature projections as ranges (1.5-4.5C by 2100) with named sources of uncertainty (climate sensitivity, emissions pathway, feedback loops) as an organizing structure. Each projection carries its evidence quality. Uncertainty IS the frame.

**Negative examples:** An AI-generated market analysis that says "the AI market will reach $500 billion by 2028" without any qualifier, source, confidence interval, or acknowledgment. A document with occasional "perhaps" and "may" hedges in otherwise confident prose does NOT fire; uncertainty language alone isn't the frame, structural organization around uncertainty is.

**Adjacent frames:** Risk Frame (FVS-009, addresses what could go wrong, while uncertainty addresses what is unknown), Failure Framing (FVS-007, specifies what would make claims wrong, while uncertainty names what cannot yet be known), Completeness Illusion (FVS-010, uncertainty dimension may be mentioned briefly without analysis)

**When this frame is appropriate:** Scientific analysis, investment decisions, policy assessment, any context where the reader needs to distinguish between what is known with confidence and what is estimated, projected, or contested.

**When this frame is misleading:** Stable factual domains where uncertainty is negligible (the speed of light, the population of France, the boiling point of water). Applying uncertainty framing to well-established facts produces false balance. Also misleading when used to delay action on claims that are sufficiently certain for practical purposes.

**Honest limits:** The detection heuristic (presence of uncertainty-dimension markers) catches explicit uncertainty language (hedging, ranges, "may," "approximately," "estimated") but misses cases where uncertainty is high but the document presents false precision. A claim like "$500 billion by 2028" has enormous uncertainty but uses no uncertainty language. Under the revised (Phase 1C) definition, hedging language alone does NOT fire the frame; structural organization does. The detector can identify surface uncertainty language; whether the document's STRUCTURE is organized around uncertainty remains an interpretive judgment.

**Revision note (2026-04-23, Phase 1C):** Revised from v1 to require structural organization around uncertainty as the primary analytical frame, not mere surface hedging. v1 permitted narrow and broad readings that produced low cross-family agreement (v2 mean AC1 0.359). The revised definition tightens toward the narrow reading, excluding cases where uncertainty language appears but does not organize the analysis. Predicted cross-family Gwet's AC1 lift: 0.359 → approximately 0.55-0.65.

## Decision-readiness implication

**Direct readiness implication.**

When this frame fires, the document explicitly names what is unknown, contested, or assumption-dependent. Affects:

- **Calibration** ([methodology](/corpus/decision-readiness/)): the document hedges where uncertainty warrants it. The methodology page's Calibration dimension is the formal structural proxy for what this frame qualitatively names.
- **Counterfactual**: alternative interpretations are surfaced.

Absence of this frame in contexts where uncertainty is real is a structural overconfidence signal.

## Generation affordances

**Rewrite prompt structure:** "For each projection, estimate, or forward-looking claim in this document, add an uncertainty annotation: what is the evidence quality (measured, estimated, projected, speculated)? What is the range of plausible values? What assumptions does this depend on? What do experts disagree about?"

**Counter-document prompt:** "This document presents its conclusions with high confidence. Rewrite with honest uncertainty: for each point estimate, provide a range. For each projection, name the assumptions. For each 'experts say,' name the disagreements. The goal is not to undermine the analysis but to make the reader aware of where the floor might give way."

**Salient questions under this frame:**
- Is this a fact, an estimate, or a projection?
- What is the range of plausible values, not just the point estimate?
- What assumptions does this projection depend on, and have they been tested?
- If I came back to this analysis in 2 years, which claims would still hold?

## Worked example

**Document excerpt:** "Global semiconductor revenue will exceed $1 trillion by 2030. Artificial intelligence will drive 40% of this growth, with data center chips accounting for the largest share."

**Frame present:** Confident projection. "$1 trillion by 2030" and "40% of this growth" are presented as facts.

**Frame absent:** Any uncertainty signal. Questions not addressed: whose projection? What is the confidence interval? ($800B to $1.2T? $600B to $1.5T?) What are the assumptions about AI adoption rates? What happens if there is a recession, a trade war, or a technology plateau? What was the accuracy of similar projections made 5 years ago?

**How to read past it:** For each number, ask: "is this a measurement or a guess?" $1 trillion by 2030 is a guess (projection). 40% AI-driven is a guess within a guess. Neither is wrong per se, but presenting them without uncertainty framing implies a precision that does not exist.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected via coverage analysis. Presence of uncertainty markers indicates the document acknowledges its own limits. ABSENCE of uncertainty markers in a document that makes forward-looking claims or uses point estimates is the actionable signal.
**Branch B:** The user can apply the uncertainty frame in pre-commit: "What am I uncertain about in my own assessment?" before seeing AI's confident answer. The pre-commit makes the user's own uncertainty visible as a comparison point.

## Vocabulary connections

- **The construction trace** (T-356): generating your own estimate before reading the AI's projection creates the comparison point that reveals when the AI's confidence exceeds the evidence.
- **The fluency-quality illusion** (FVS-002): confident, fluent presentation of uncertain claims is how the illusion operates on projections specifically.

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.463 |
| Gwet's AC1 (pairwise mean) | 0.456 |
| Raw agreement (pairwise mean) | 0.722 |
| Union prevalence (all families) | 45% |

Per-family positives (of 15 docs): Claude 10, Gemini 6, Grok 6, GPT-5 5.

**V4 detection mode:** default

**Interpretation:** Moderate cross-family agreement.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-13; revised Phase 1C 2026-04-23 (structural-organization tightening per Revision note above); grounded-authorship retrofit 2026-04-25 per FRAME_DIVERGENCE_v2.md §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04 measured pre-Phase 1C revision; post-revision re-measurement pending)
- `detect_coverage` uncertainty dimension in `framing.py` (rule-based detector)
- EXP-094 confound audit (evidence discipline as applied Uncertainty Frame on Frame Check's own research claims)
- MCP integration as canonical absent-frame in `_PROMPT_AI_RESPONSE_AUDIT` and `_PROMPT_CHALLENGE_DOCUMENT`
- Phase 1C revision artifact (2026-04-23): tightened from "presence of hedging language" to "structural organization around uncertainty"
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Phase 1C-pre kappa paradox at moderate prevalence. v1 definition (mere hedging-language presence fires) showed AC1 0.359 across families - low for a primary frame. The narrow-vs-broad reading variance was the cause. Phase 1C revision (2026-04-23) tightened to require structural organization around uncertainty as the organizing principle. Predicted AC1 lift to 0.55-0.65; post-revision re-measurement is pending.
2. Detection catches surface hedging, misses false precision. A claim like "$500B by 2028" carries enormous uncertainty but uses no uncertainty language. Rule-based detection misses these false-precision cases entirely. V4.2 LLM judge partially addresses but the construct boundary (organizing-principle vs surface-hedging) is interpretive and remains a known under-detection failure mode.
3. Uncertainty paralysis as misuse. When applied to stable factual domains (speed of light, well-established constants, narrowly factual claims), the Uncertainty Frame produces false balance: hedging the unhedgeable. The frame is also misleading when used to delay action on claims that are sufficiently certain for practical purposes. Construct boundaries are documented in honest_limits but detection has no domain-context awareness.

**Success record.** Two operationalized cases:
1. Evidence discipline at Frame Check (EXP-094 confound audit). The audit IS the Uncertainty Frame applied to Frame Check's own research claims: detection limitations named explicitly, evidence quality stated per claim, contested-experts surfacing, quarterly retro audits calendared. Uncertainty Frame as methodology practice rather than as document analysis target. Operationalized in [METHODOLOGY.md](https://github.com/Clarethium/frame-check/blob/master/METHODOLOGY.md) §6 evidence discipline.
2. MCP integration as canonical absent-frame. FVS-012 cited in MCP prompts as one of the canonical absent-frames for divergence: "FVS-012 (Uncertainty Frame) absent leads to question 'What would have to be true for the conclusion to be wrong?'" (Note: this question is shared with FVS-007 Failure Framing in MCP prompts; the two frames are distinct - FVS-012 names what is unknown; FVS-007 names what would falsify; the shared question form crosses both.) Embedded in agent-facing surface as high-leverage divergence target.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where applying the Uncertainty Frame to a confidently-presented projection or estimate revealed false precision or hidden assumption-dependence; (2) the difference between the point-estimate-as-fact reading and the uncertainty-framed reading is concrete (specific numbers, ranges, or assumptions); (3) outcome differential observed (decision deferred for evidence, hedge introduced, claim re-scoped); (4) concrete first-person recall. Held open per FRAME_DIVERGENCE_v2.md P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application (no tools, experienced reader): ~30-60 seconds to ask "is this a fact or a guess; what is the range; what assumptions does this depend on"
- V4.2 LLM judge invocation: ~$0.0008/document
- Branch B pre-commit (user states own uncertainty before consulting AI): 1-2 minutes
- One-pass detection: appropriate for any forward-looking document, projection, or estimate
- Deep-dive engagement: appropriate when document drives high-stake decision and contains point estimates that may be guesses

**Applicability metadata.**
- Domains: scientific analysis (high stake-relevance), investment decisions (high), policy assessment (high), AI-generated forecasting (high), strategy with projections (high), regulatory analysis (medium-high)
- Decision types: any with forward-looking claim, projection, or contested-evidence component
- Stake levels: low to high. Low-stake casual reading benefits less; high-stake forward-looking claims always benefit.
- Inappropriate contexts: stable factual domains (well-established constants); narrowly factual claims; claims sufficiently certain for practical purposes; cases where invoking uncertainty produces false balance

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027 v1 baseline): kappa 0.463, AC1 0.456 (moderate), raw 0.722, union prevalence 45% (Claude 10, Gemini 6, Grok 6, GPT-5 5 of 15)
- Phase 1C revision (2026-04-23): predicted AC1 lift from 0.359 to 0.55-0.65; post-revision re-measurement pending
- EXP-094 confound audit: ongoing application as methodology practice
- MCP integration: operationally embedded as canonical absent-frame
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
