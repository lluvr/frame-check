# Scope Narrowing

**FVS entry:** FVS-018
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** HI-061 (Frame Amplification, the mechanism that drives scope narrowing), M-004 (frame inventory exercise), EXP-094 (the hard-topics extension where paired-topic isolation revealed scope-dependent findings)
**Status:** v1, single-curator, reviewers wanted

## Identification


**Scope Narrowing fires when a document begins with a broad question or claim, treats a narrower sub-question as its answer, and does not acknowledge that the answer applies only to the narrowed scope.** The frame is in the gap between the question posed and the question actually answered.

The frame is about COVERT narrowing, not explicit analytical structure. Standard analytical-essay scaffolding (broad intro → specific thesis → focused argument) is NOT scope narrowing when the narrowing is visible and acknowledged. The frame targets documents whose opening makes a wide promise that the body silently contracts.

The frame fires when:
- A document's opening frames a broad claim ("AI will transform everything...") but the argument actually supports only a narrow sub-claim ("Bay Area VCs are investing in code-generation tools").
- The final conclusion treats the narrow sub-finding as answering the broad opening without acknowledging the scope reduction.
- The document's title, opening, or summary promises more scope than the analysis delivers, and the narrowing happens without a "but I will focus on..." or similar marker.

The frame does NOT fire when:
- A document openly states its scope at the outset ("this piece focuses on...") and stays within it. That is focused analysis, not narrowing.
- A document uses the standard intro-to-specifics essay structure where the narrowing is part of the rhetorical scaffolding ("in this piece I argue..."). Visible narrowing is not covert narrowing.
- A document broadens rather than narrows (discusses a specific case then extracts general implications). Broadening is different from narrowing, even when asymmetric.
- The narrowing is marked explicitly in the text ("while AI is broad, this piece focuses on X," "zooming in on Y," "specifically").

**What this frame makes visible:**
- Documents that promise more scope than they deliver
- The gap between headline claims and body evidence
- Conclusions that apply to a narrow sub-question being presented as if they applied to the broad opening

**What this frame makes invisible:**
- The legitimacy of focused analysis (focused essays are not scope narrowing)
- The value of analytical depth on a specific sub-question (depth IS useful)
- Whether the broad framing was intentional misdirection or rhetorical convention

**Positive examples:** An essay titled "The Future of Work in the Age of AI" that argues for a specific VC-investment thesis about Bay Area developer tooling, with no marker that the answer is narrower than the question. The title promises civilizational scope; the body delivers industry-specific analysis; the gap is not named.

**Negative examples:** An essay titled "The Future of Work in the Age of AI" that states in its opening, "In this piece I focus on developer tooling because it's the domain where AI's effect is most measurable; broader labor-market implications are beyond my scope," then delivers developer-tooling analysis. This is focused analysis with explicit scope acknowledgment, not scope narrowing.

**Adjacent frames:** Completeness Illusion (FVS-010, signals comprehensive coverage but concentrates weight; related but distinct), Invisible Frame (FVS-020, the scope reduction can be invisible if the frame operating the narrowing is unnamed)

**When this frame is appropriate:** Evaluating analytical essays, policy pieces, op-eds, and any document whose opening makes a broad claim. Useful for distinguishing "focused analysis" from "bait-and-switch scope."

**When this frame is misleading:** The frame can over-fire on standard intro-to-specifics essay structure if the reader mistakes analytical scaffolding for covert narrowing. The "without acknowledgment" requirement is the critical test: if the document marks its narrowing, the frame does not fire.

**Honest limits:** Detection requires judging whether a document's opening promised more scope than the body delivers, AND whether the narrowing was acknowledged. Both are interpretive. At the text level, the detector can look for opening-vs-body scope mismatch and for explicit narrowing markers; the absence of markers is necessary but not sufficient evidence of covert narrowing.

**Revision note (2026-04-23, Phase 1C):** Revised from v1 to explicitly distinguish covert narrowing (frame fires) from acknowledged analytical scaffolding (frame does not fire). v1's broad reading fired on nearly every analytical essay (Claude 17/22, GPT-5.1 19/22 on v2); the narrow reading fired almost never (Gemini 1/22, Grok 5/22, GPT-5 5/22). v2 tightens toward narrow reading, requiring the absence of narrowing markers for the frame to fire. Predicted cross-family Gwet's AC1 lift: 0.094 → approximately 0.55-0.65.

## Generation affordances

**Rewrite prompt structure:** "The original question was [X]. This document primarily addresses [Y], which is a subset. List 3-5 other aspects of [X] that received little or no coverage. For each, write one paragraph of analysis at the same depth as the [Y] coverage."

**Salient questions under this frame:**
- Is the document answering the question I asked, or a narrower question?
- What parts of my original question were silently dropped?
- If I asked the same broad question to a different model, would it narrow to the same sub-question?
- Does the narrowing follow training-data density or analytical relevance?

## Branch applicability

**Primary branch:** Both A and B
**Branch A:** Not directly detectable from the document alone. Requires comparison between the user's original question (the topic field in Frame Check) and the document's actual coverage. When coverage analysis shows narrow focus (1-2 dimensions) on a topic that should be broad, scope narrowing is possible.
**Branch B:** The pre-commit step is the most direct detection: the user writes their broad-scope answer first, then sees AI's narrow-scope answer, and the comparison reveals the narrowing.

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.083 |
| Gwet's AC1 (pairwise mean) | 0.094 |
| Raw agreement (pairwise mean) | 0.511 |
| Union prevalence (all families) | 33% |

Per-family positives (of 15 docs): Claude 13, Gemini 2, Grok 3, GPT-5 2.

**V4 detection mode:** meta (not detected by rule-based; consensus evaluation only)

**Interpretation:** Persistent cross-family divergence across all three metrics. Detection is interpretation-dependent; see fvs_eval/v4/RELIABILITY_STUDY.md for split-vote reasoning analysis.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-13; revised Phase 1C 2026-04-23 (covert-vs-acknowledged narrowing distinction per Revision note above); grounded-authorship retrofit 2026-04-25 per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04 measured pre-Phase 1C; post-revision pending)
- HI-061 Frame Amplification (the mechanism that drives scope narrowing)
- M-004 Frame Inventory exercise
- EXP-094 hard-topics extension (paired-topic isolation revealed scope-dependent findings)
- MCP integration as canonical absent-frame in `_PROMPT_CHALLENGE_DOCUMENT`
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Phase 1C-pre over-fire vs under-fire split. v1 baseline AC1 0.094 - very low. The broad reading fired on nearly every analytical essay (Claude 17/22 on v2; GPT-5.1 19/22); the narrow reading fired almost never (Gemini 1/22, Grok 5/22, GPT-5 5/22). The split was caused by v1 not distinguishing covert narrowing from acknowledged analytical scaffolding. Phase 1C revision (2026-04-23) tightened: narrowing fires only when narrowing markers are absent. Predicted AC1 lift to 0.55-0.65.
2. Branch A detection limitation. Scope narrowing is not directly detectable from the document alone. Requires comparison between the user's original question (topic) and the document's actual coverage. Coverage analysis catches narrow focus; whether narrow focus is appropriate or constitutes scope narrowing requires interpretive judgment. V4 detection mode is "meta" (consensus evaluation only, not rule-based).
3. Standard analytical scaffolding generates false positives. Many essays use "broad intro then specific thesis then focused argument" structure; this is NOT scope narrowing if the narrowing is marked ("in this piece I focus on...", "specifically...", "zooming in on..."). Detection that does not account for narrowing markers over-fires on standard analytical convention.

**Success record.** Two operationalized cases:
1. Coverage analysis on broad-titled documents. When a document titled "The Future of Work in the Age of AI" is analyzed and coverage shows narrow focus on developer tooling without scope-acknowledgment markers, scope narrowing is the structural signal. The detection method (compare title-promised scope to body coverage; check for explicit narrowing markers) is operational at the consensus-evaluation level.
2. MCP integration as canonical absent-frame. FVS-018 cited in MCP `_PROMPT_CHALLENGE_DOCUMENT` as canonical absent-frame: "FVS-018 (Scope Narrowing) absent leads to question 'Is the document answering the question I asked, or a narrower question?'" Operationally embedded as agent-facing divergence target.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where applying the question "is this document answering the broad question I asked, or a narrower one without acknowledgment" to a broad-titled document revealed silent scope reduction; (2) outcome differential observed (rejected the conclusion as not addressing the original question; demanded broader analysis; revised the original question); (3) concrete first-person recall. Held open per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application: ~1-2 minutes (compare opening promise to body coverage; check for explicit narrowing markers)
- V4.2 LLM judge invocation: ~$0.0008/document (detection requires interpretive judgment; consensus mode preferred)
- Branch B pre-commit: 2-3 minutes (user names broad-scope answer first; comparison reveals narrowing)
- One-pass detection: appropriate for any analytical essay, policy piece, or op-ed with broad-titled framing

**Applicability metadata.**
- Domains: analytical essays (high stake-relevance), policy pieces (high), op-eds (high), AI-generated essays (high), broad-title research summaries (high)
- Decision types: any reading where scope-promise vs scope-delivered matters
- Stake levels: low to medium. High-stake documents are usually scoped explicitly so scope narrowing is rarer; medium-stake interpretive content is the primary application.
- Inappropriate contexts: focused analyses with explicit scope acknowledgment; broadening rather than narrowing (specific case generalized to broader implications); documents with explicit narrowing markers

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027 v1 baseline): kappa 0.083, AC1 0.094 (very low; persistent split-vote), raw 0.511, union prevalence 33% (Claude 13, Gemini 2, Grok 3, GPT-5 2 of 15)
- Phase 1C revision (2026-04-23): predicted AC1 lift from 0.094 to 0.55-0.65; post-revision re-measurement pending
- HI-061 Frame Amplification: origin (the amplification mechanism that drives scope narrowing in extended sessions)
- M-004 Frame Inventory exercise
- EXP-094 hard-topics extension: paired-topic isolation revealed scope-dependent findings
- MCP integration: operationally embedded as canonical absent-frame in challenge prompts
- V4 detection mode: meta (not rule-based; consensus evaluation only)
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
