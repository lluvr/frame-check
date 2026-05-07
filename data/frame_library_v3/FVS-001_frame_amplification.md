# Frame Amplification

**FVS entry:** FVS-001
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** HI-061 (Frame Amplification), EXP-094 confound audit, M-004 (Frame Inventory)
**Status:** v1, single-curator, reviewers wanted

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

**Adjacent frames:** Fluency-Quality Illusion (FVS-002, the surface mechanism that makes amplified content feel true), Default Geometry (FVS-004, why the frame defaults exist in the first place), The Amplification Thesis (HI-062, the broader claim that AI amplifies all patterns, not just frames)

**When this frame is appropriate:** Any extended AI-assisted analysis session where the question has multiple valid framings. Strategy, policy, investment, hiring, product decisions. Any context where the question itself can be asked from different angles.

**When this frame is misleading:** Narrow technical questions with one correct answer ("what is the boiling point of water"). Frame amplification is about interpretive questions, not factual ones. The frame is also less relevant in short, single-turn interactions where accumulation has not had time to compound.

**Honest limits:** The five-hour session evidence (HI-061: "5 hours of analysis within a wrong frame killed 90% of 406 proposals") is N=1. The mechanism (semantic neighborhood activation causing self-reinforcing context) is grounded in how transformer models work but the magnitude of the effect in typical user sessions has not been measured. The claim "sophistication makes the error harder to see" is directionally supported but the causal chain (amplification leads to worse outcomes) has not been validated in a controlled experiment with real decisions.

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

## Vocabulary connections

- **The amplification thesis** (HI-062, CLARETHIUM_VOCABULARY): the broader claim that AI amplifies all patterns. Frame amplification is one instance.
- **The construction trace** (T-356, CLARETHIUM_VOCABULARY): without generating your own analysis first, you cannot evaluate whether the AI's frame is the right one. Frame amplification exploits the absence of construction trace.
- **The first read** (M-002, CLARETHIUM_VOCABULARY): the somatic response to AI output before conscious evaluation. Frame-amplified content triggers a strong first read (it feels good because it is refined) which makes the frame harder to challenge.

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.066 |
| Gwet's AC1 (pairwise mean) | 0.699 |
| Raw agreement (pairwise mean) | 0.778 |
| Union prevalence (all families) | 13% |

Per-family positives (of 15 docs): Claude 0, Gemini 2, Grok 2, GPT-5 4.

**V4 detection mode:** default (sparse-consensus note)

**Interpretation:** Moderate cross-family agreement.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-12; grounded-authorship retrofit 2026-04-25 per FRAME_DIVERGENCE_v2.md §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04)
- HI-061 Frame Amplification 5-hour session case study (foundational, N=1)
- EXP-094 confound audit (April 2026 Source Network coverage improvements)
- M-004 Frame Inventory corpus
- FVS-001 cross-family targeted measurement (fvs_eval/v4_2/FVS_001_CROSS_FAMILY_v1.md)
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Low Cohen's kappa despite moderate AC1. F-2026-027 showed kappa 0.066 (near-zero) while AC1 reached 0.699. The kappa-AC1 divergence indicates per-family bias in what counts as amplification: prevalence-based correction in kappa exposes disagreement that AC1's paradox-resistant calculation absorbs. The frame is operationally fuzzy across families. The fvs_eval/v4_2/FVS_001_CROSS_FAMILY_v1.md targeted-scope study examines this directly.
2. N=1 origin claim. The "5 hours of analysis killed 90% of 406 proposals" finding (HI-061) is from a single curator session. Magnitude of the effect in typical user sessions has not been measured; the causal chain (amplification leads to worse outcomes) has not been validated in a controlled experiment with real decisions. Stated in honest_limits; surfaced here because the entry's foundational evidence is anecdotal.
3. Detector cannot detect itself. Frame amplification operates within AI-generated content; the detector inspects that content. The detector cannot verify whether IT ITSELF has been amplified during multi-document analysis. Self-detection is structurally precluded by the architecture (v1 detector is rule-based; V4.2 LLM judge has the same issue at LLM scale). Branch B (pre-commit intervention) is the architectural workaround.

**Success record.** Two operationalized cases:
1. NVIDIA fiscal-2024 analysis (EXP-094, HI-061). Identified frame-amplified document; counter-frame rewrite preserved data points but reframed as risk evidence; demonstrated that sophistication of the original analysis did not equal completeness. Material additions a strategic reader would want.
2. Branch B (pre-commit intervention) operational concept. The "write your own analysis first before consulting AI" pattern is in active use as the primary preventive against frame amplification. Concept is shipped via methodology and outreach materials (FVS_001_OUTREACH_EMAIL_SHORT_v1.md); quantified outcomes pending.

**Lived-experience anchor.** Authored 2026-04-26 per the maintainer-side anchor-authorship methodology.

Late March 2026, approximately one month before the v2 architectural work landed. A four-hour continuous session with Claude as primary interlocutor (ChatGPT secondary), building proposals for new app projects with all proposals coupling tightly to the curator's existing measurement, evaluation, and vault-experiment work. Claude converged hard on the curator's existing context across the full session: whatever new direction the curator probed, Claude pattern-matched the response back to the curator's known repertoire and built proposals adjacent to it. The frame held for four hours.

The convergence was, partly, deliberately driven. The curator was probing how AGI might evolve and what gives a human edge in deciding what is worth building, and chose to enter the frame deeply in order to feel it from inside rather than detect it from outside. The frame-lock that followed reproduced canonical FVS-001 dynamics under deliberate-immersion conditions: sustained convergence across iterations; sophistication of the analysis tracking depth of frame-lock; curator complicity in driving the convergence. The frame broke not via external reality test but via the curator's own pattern-matching against history: humans will fight to maintain decision-making power; brains atrophy if not used; businesses will remain human-owned even with AGI doing the labor.

Outcome differential. The product orientation shifted from intelligence-edge framing ("build something only this curator can build") toward problem-solving infrastructure framing ("build what solves a real problem"). Within roughly a month, this landed as a specific concrete project unrelated to the curator's existing Frame Check research work: a fitness app for trainers (lesson recording, video, personalization for clients, booking), originally proposed by a trainer approximately one year earlier and dismissed at the time. The earlier dismissal happened under the prior frame; the proposal landed when the frame shifted.

**Anchor strength.** Approximate date late March 2026, before the 2026-04-25 v2 architectural work. Session length (four hours) and primary AI interlocutor (Claude) firmly recalled. Conversation log is in principle retrievable via Claude's conversation persistence. The trainer's proposal from approximately one year earlier (early 2025) is a separate verifiable trace in the curator's contact and message archives. Honest qualification: this is not naive frame-lock but deliberate frame-immersion that reproduced FVS-001 dynamics under intentional probing. v2 of the FVS-001 entry may want to distinguish naive-frame-lock from deliberate-frame-immersion as separate sub-modes. The internal-stance commitment ("use brain 10,000 times more") is recall-firm; the causal chain to the fitness-app-for-trainers project landing is curator-traceable but the precise timing of the project landing relative to the frame shift is approximate.

**Friction-cost estimate** (operator-validation pending):
- Manual application (extended-session retrospective): ~5-10 minutes to scan back through a session and identify whether the frame was operative; not invocable in real-time during AI use because the frame is invisible to the user mid-session
- V4.2 LLM judge invocation: ~$0.0008/document on terminal-state document; the harder problem is detecting amplification-in-progress which is not yet operationalized
- Branch B pre-commit cost: 5-10 minutes of user pre-writing time before AI consultation; structural rather than per-invocation
- Appropriate use depths: high-stake extended sessions; not necessary for short single-turn factual interactions

**Applicability metadata.**
- Domains: AI-assisted strategy (high stake-relevance), policy analysis (high), investment research (high), hiring decisions (medium), product decisions (high), any extended interpretive AI session
- Decision types: any decision that admits multiple valid framings
- Stake levels: medium to high; low-stake interactions do not accumulate enough context for amplification to compound
- Inappropriate contexts: short single-turn factual queries, technical documentation generation, narrow API consumption, mathematical proofs

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa 0.066 (near-zero), AC1 0.699 (moderate), raw 0.778, union prevalence 13% (Claude 0, Gemini 2, Grok 2, GPT-5 4 of 15)
- FVS-001 cross-family targeted measurement: see fvs_eval/v4_2/FVS_001_CROSS_FAMILY_v1.md
- HI-061 case study: 5-hour session N=1; foundational but not generalizable
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
