# Scope Narrowing

**FVS entry:** FVS-018
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13

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

**Revision note (2026-04-23, Phase 1C):** Revised from v1 to explicitly distinguish covert narrowing (frame fires) from acknowledged analytical scaffolding (frame does not fire). v1's broad reading fired on nearly every analytical essay (Claude 17/22, GP.1 19/22 on v2); the narrow reading fired almost never (Gemini 1/22, Grok 5/22, GP 5/22). v2 tightens toward narrow reading, requiring the absence of narrowing markers for the frame to fire. Predicted cross-family Gwet's AC1 lift: 0.094 → approximately 0.55-0.65.

## Generation affordances

**Rewrite prompt structure:** "The original question was [X]. This document primarily addresses [Y], which is a subset. List 3-5 other aspects of [X] that received little or no coverage. For each, write one paragraph of analysis at the same depth as the [Y] coverage."

**Salient questions under this frame:**
- Is the document answering the question I asked, or a narrower question?
- What parts of my original question were silently dropped?
- If I asked the same broad question to a different model, would it narrow to the same sub-question?
- Does the narrowing follow training-data density or analytical relevance?

## Branch applicability

**Primary branch:** Both A and B
**Branch A:** Not directly detectable from the document alone. Requires comparison between the user's original question (the topic field in Framecheck) and the document's actual coverage. When coverage analysis shows narrow focus (1-2 dimensions) on a topic that should be broad, scope narrowing is possible.
**Branch B:** The pre-commit step is the most direct detection: the user writes their broad-scope answer first, then sees AI's narrow-scope answer, and the comparison reveals the narrowing.
