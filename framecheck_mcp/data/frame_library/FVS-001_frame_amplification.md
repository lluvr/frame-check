# Frame Amplification

**FVS entry:** FVS-001
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** HI-061 (Frame Amplification), EXP-094 confound audit, M-004 (Frame Inventory)
**Status:** v1, single-curator, reviewers wanted; v1 detection rule retired 2026-04-18 per [INDEX.md](https://github.com/Clarethium/frame-check-mcp/blob/master/data/frame_library/INDEX.md) "Detection state taxonomy" (external validation study found unsustainable false-positive rate; frame concept retained; V4.2 LLM-judge replaces v1 rule per [METHODOLOGY.md](https://github.com/Clarethium/frame-check-mcp/blob/master/METHODOLOGY.md) §2.4.1).

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

**Adjacent frames:** Fluency-Quality Illusion (FVS-002, the surface mechanism that makes amplified content feel true), Default Geometry (FVS-004, why the frame defaults exist in the first place; FVS-004 withdrawn per INDEX.md "v1 publication state"), The Amplification Thesis (HI-062, the broader claim that AI amplifies all patterns, not just frames), Failure Framing (FVS-007, the technique for breaking frame amplification; concrete failure conditions interrupt how amplification compounds across iterations), Oracle Frame (FVS-013, the reader posture that lets amplification proceed unchecked; oracle mode never interrupts the frame, which is what amplification needs to compound)

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

## Cross-family reliability

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/Clarethium/frame-check-mcp/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### V4.2 NEW panel (2026-04-24, library_v4 ratified; library_current historical)

**library_v4 ratification note (2026-04-24).** Engine canonical is now library_v4 (VERSION 0.2.0), composed as library_v3 Identifications + library_current non-Identifications per fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md and METHODOLOGY §2.4.4. FVS-001's Identification in library_v4 is byte-equivalent to library_v3. **Under library_v4, FVS-001 cross-family AC1 equals library_v3 values: MG 4-family 0.566, TS 4-family 0.55 (the `library_v3` columns below).** library_current AC1 values are retained as historical evidence of pre-ratification working-library state; they describe a library variant that was measured and FOUND REGRESSIVE on Identification domain per §2.4.3 Step 4 + Step 5 (FVS-001 itself improved under library_current, but library-wide FVS-016 protection failed, requiring composition ratification).

**Engine-emit disclosure.** `library_consensus_ac1` = **0.620** (tier: **moderate**), per fvs_eval/v4/library_v4_reliability.json. Per-corpus reproducible values (regen: fvs_eval/v4/compute_per_corpus_reliability.py; artifact: fvs_eval/v4/library_v4_per_corpus_reliability.json): MG_v3=0.566 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.643 (3-family partial; Anthropic queued). Historical: MG2_v1=0.488 (library_v1), MG2_v2=0.587 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md; rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **1.000** across n=41 docs at temp=0 (0 verdict flip(s); per fvs_eval/v4/grok_intra_rater_ac1.json). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

Measured across four LLM families matching the V4.2 canonical detector pin. See fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md for library-wide context and fvs_eval/v4_2/FVS_001_CROSS_FAMILY_v1.md for earlier FVS-001-specific analysis. Panel: Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Measured against canonical library at `data/frame_library/` (working library, currently matches library_v4 content at ratification time).

**Mixed-genre baseline (n=15)** on fvs_eval/mixed_genre_v1:

| Metric | library_v3 (engine-canonical under library_v4 by Identification byte-equivalence) | library_current (working-library state pre-ratification, historical) | library_v2 (archived earlier) |
|---|---|---|---|
| Gwet's AC1 (pairwise mean) | **0.57** | 0.65 | 0.80 |
| Cohen's kappa (pairwise mean) | **0.25** | 0.13 | 0.27 |
| Raw agreement (pairwise mean) | 0.79 | 0.76 | 0.84 |
| Union prevalence | 8/15 = 53% | 7/15 = 47% | 4/15 = 27% |

Per-family positives on library_v3 / library_v4 engine-canonical (of 15 docs): Claude 4, Gemini 6, Grok 0, GPT 5. On library_current historical: Claude 2, Gemini 3, Grok 0, GPT 5. The 2026-04-23/24 session's Identification refinements (softening, scope-narrowing, adjacency reciprocity) raised FVS-001-only library_current MG AC1 to 0.65 from library_v3's 0.57. The same Identification edits produced library-wide regression including a 0.293 AC1 drop on canon-protected FVS-016, failing METHODOLOGY §2.4.3 Step 5; library_v4 ratification reverted the session Idents and engine-canonical AC1 returns to 0.57 per byte-equivalence. The library_current 0.65 documents the FVS-001-isolated improvement that did not survive cross-frame protection requirements.

**Target-scope corpus (n=4 worked-examples).** Multi-LLM analytical comparisons closer to FVS-001's stated scope ("extended AI-assisted analysis sessions"). Library_current 3-family partial measurement (Claude pending credit replenishment); library_v3 4-family complete for comparison:

| Metric | library_v3 (4-family complete; engine-canonical under library_v4) | library_current (3-family partial; pre-ratification historical) |
|---|---|---|
| Intersection (all measured agree positive) | 2/4 (Claude+Gemini+Grok+GPT mixed) | 3/4 (Gemini+Grok+GPT unanimous on 3 docs; GPT false on altman) |
| Union prevalence | 4/4 | 4/4 |
| Gwet's AC1 | 0.55 | n/a (prevalence degeneracy) |

Per-family positives on library_v3 4-family complete (engine-canonical under library_v4): Claude 4, Gemini 4, Grok 2, GPT 3. On library_current 3-family partial (historical, Claude pending credit replenishment): Gemini 4, Grok 3, GPT 4.

**Key observation.** FVS-001 target-scope construct validity is strong under engine-canonical (library_v3 = library_v4) measurement: 4-family intersection 2/4, union 4/4, AC1 0.55 on n=4 worked-examples. Library_current 3-family partial showed intersection 3/4 on the 3 measured families (one frame's local improvement). Both library states show FVS-001 unanimous-positive across all measured families on the multi-LLM curator essays (bitcoin, startup, nvidia). The library_v4 ratification preserves the strong target-scope construct validity that library_v3 originally established.

**Construct-validity evidence.** Per fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md §2.6, FVS-001 had mixed-genre construct-validity ratio 3.0× on n=4 under library_v3 (engine-canonical under library_v4 by Identification byte-equivalence) and 2.5× on n=2 under library_current historical. Target-scope construct validity remains primary canon-candidacy evidence given the mixed-genre sample limitation, and is unchanged by the ratification (library_v3 numbers carry through).

**Generation comparison.** V4 (OLD panel, previous detector generation) → V4.2 (NEW panel, current) on the same mixed-genre corpus with library_v2: kappa 0.066 → 0.269, AC1 0.699 → 0.797. Generation-to-generation improvement is material. Engine-canonical (library_v3 / library_v4) MG AC1 0.57 sits below library_v2's 0.80 because library_v3 broadened FVS-001's detection surface (fires on more documents); the session's library_current edits raised AC1 to 0.65 by re-tightening but were reverted under library_v4 because the same edits regressed FVS-016 cross-family agreement library-wide (METHODOLOGY §2.4.3 Step 5).

**Interpretation notes (for a non-specialist reader).**
- FVS-001 detection is substantially more reliable on target-scope documents (multi-LLM comparisons of analytical responses) than on mixed-genre text. Scope-matched data shows unanimous cross-family agreement on the clearest target-scope cases (bitcoin and startup multi-LLM essays).
- Grok 4.1 fast (the V4.2 production detector) is the panel's conservative pole: zero positives on mixed-genre and two of four target-scope. Users running V4.2 in production will see this conservatism, not the cross-family mean. Canon-status and production disclosures should name this explicitly.
- Cohen's kappa is undefined when prevalence hits 0% or 100% for either rater; AC1 and raw agreement remain informative. See fvs_eval/v4_2/FVS_001_CROSS_FAMILY_v1.md §3.2 for the metric-degeneracy discussion.

### V4 OLD panel (historical, preserved for comparison)

Measured on fvs_eval/mixed_genre_v1 n=15 across OLD-panel LLM families (Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5) per `F-2026-027`:

| Metric | V4 value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.066 |
| Gwet's AC1 (pairwise mean) | 0.699 |
| Raw agreement (pairwise mean) | 0.778 |
| Union prevalence | 13% |

Per-family positives (of 15 docs): Claude 0, Gemini 2, Grok 2, GPT-5 4.

**Latest-model discipline:** periodic re-calibration is operational doctrine across V4 and V4.2 generations. See fvs_eval/v4/MODEL_PANEL.md for panel pinning policy, fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.
