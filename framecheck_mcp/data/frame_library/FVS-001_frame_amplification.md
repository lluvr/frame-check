# Frame Amplification

**FVS entry:** FVS-001
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12

## Identification

When AI converges on a frame, each iteration produces more sophisticated analysis within that frame. The analysis gets sharper. The conclusions get more confident. The frame itself goes unexamined. The sophistication makes the error harder to see, not easier.

**What this frame makes visible:**
- How refinement within a frame can serve wrong conclusions (correct analysis, wrong frame = wrong outcome)
- Why long AI sessions lock frames harder (accumulated context reinforces the frame through semantic neighborhood activation)
- Why the moment of highest analytical confidence is often the moment of deepest frame lock

**What this frame makes invisible:**
- Which frame is wrong when the analysis looks increasingly refined
- Variables that were excluded from the search space by the initial frame selection
- The AI's inability to detect its own frame (it generates within frames, not about them)

**Positive examples:** A 5-hour session refining a market entry strategy that gets progressively more detailed and convincing, but operates entirely from a growth frame without ever examining whether growth is the right lens. Each iteration strengthens the case for growth because growth is the frame; alternatives are not in the search space.

**Negative examples:** A document that names its own frame explicitly ("This analysis takes a growth perspective; a risk analysis would surface different factors") is not exhibiting frame amplification because the frame is visible. Frame amplification requires the frame to be invisible.

**Adjacent frames:** Fluency-Quality Illusion (FVS-002, the surface mechanism that makes amplified content feel true), Default Geometry (FVS-004, why the frame defaults exist in the first place; FVS-004 withdrawn per INDEX.md "v1 publication state"), The Amplification Thesis (, the broader claim that AI amplifies all patterns, not just frames), Failure Framing (FVS-007, the technique for breaking frame amplification; concrete failure conditions interrupt how amplification compounds across iterations), Oracle Frame (FVS-013, the reader posture that lets amplification proceed unchecked; oracle mode never interrupts the frame, which is what amplification needs to compound)

**When this frame is appropriate:** Any extended AI-assisted analysis session where the question has multiple valid framings. Strategy, policy, investment, hiring, product decisions. Any context where the question itself can be asked from different angles.

**When this frame is misleading:** Narrow technical questions with one correct answer ("what is the boiling point of water"). Frame amplification is about interpretive questions, not factual ones. The frame is also less relevant in short, single-turn interactions where accumulation has not had time to compound.

**Honest limits:** The five-hour session evidence (: "5 hours of analysis within a wrong frame killed 90% of 406 proposals") is N=1. The mechanism (semantic neighborhood activation causing self-reinforcing context) is grounded in how transformer models work but the magnitude of the effect in typical user sessions has not been measured. The claim "sophistication makes the error harder to see" is directionally supported but the causal chain (amplification leads to worse outcomes) has not been validated in a controlled experiment with real decisions.

## Decision-readiness implication

**Direct readiness implication.**

When this frame fires, the document amplifies one frame at the expense of others. Affects:

- **Coverage** ([methodology](/corpus/decision-readiness/)): single-frame amplification structurally narrows the analytical perspectives a reader receives.
- **Counterfactual**: the amplified frame goes unexamined; alternative interpretations are obscured. Sophistication of the amplified frame can mask both deficits because readers see depth and infer breadth.

## Generation affordances

**Rewrite prompt structure:** "Rewrite this analysis from a frame that explicitly names and challenges its own assumptions. For each claim, add a parenthetical noting what the claim would look like under an alternative frame. The goal is to make the current frame visible, not to replace it."

**Counter-document prompt:** "This document concentrates its analysis on one dominant dimension while other perspectives are absent or thin. Rewrite the same data with equal analytical depth across all perspectives. Every number from the original should appear. The dimensions the original neglects (risks, stakeholders, uncertainty, causes, or trends) should receive the same depth as the original's strongest section. Write as the same genre, not as a critique."

**Salient questions under this frame:**
- What frame is this document operating from?
- Has this frame been chosen deliberately or inherited from the first prompt?
- What would change if the same question were asked from a different starting point?
- Is the increasing sophistication of the analysis evidence of quality, or evidence of frame lock?

## Worked example

**Document excerpt:** "NVIDIA's data center revenue reached $47.5 billion in fiscal 2024, up 217% year-over-year. The company now dominates the AI accelerator market with approximately 80% market share. Cloud providers have committed over $190 billion to AI infrastructure. The AI infrastructure market is projected to reach $500 billion by 2028. NVIDIA's competitive moat continues to strengthen through CUDA ecosystem lock-in and next-generation chip architectures."

**Frame present:** Growth and market dominance. Every data point is selected to support the narrative that NVIDIA is winning and will continue to win. The framing treats growth as the natural lens.

**Frame absent:** Risk and vulnerability. The document does not address: what happens when competitors ship viable alternatives, whether the $190B commitment is sustainable or a bubble, what NVIDIA's concentration risk means for customers, whether the 80% market share attracts regulatory attention, or what the historical pattern is for companies with "unassailable" market positions.

**How to read past it:** Ask "what would a risk analyst say about this same data?" The numbers themselves are presumably accurate (fact-check floor). The frame selection is where the bias lives. A risk frame would use the same numbers to argue: extreme concentration, bubble-level spending commitments, competitive alternatives emerging, and historical pattern of dominant positions being disrupted.

## Branch applicability

**Primary branch:** Both A (document analysis) and B (interaction intervention)
**Branch A:** Detected when a document shows high coverage of one analytical dimension (e.g., trends, growth) and low coverage of others (risks, stakeholders, uncertainty). The framing portrait's coverage analysis is the primary detection surface.
**Branch B:** In the pre-commit intervention, frame amplification is the thing the write-first step is designed to prevent. By committing to a frame before AI responds, the user creates a comparison point that makes amplification visible if it occurs.
