# Growth Frame

**FVS entry:** FVS-008
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** M-004 (Frame Inventory, named as example), HI-061 (Frame Amplification case study), EXP-094 (NVIDIA analysis), detect_coverage in framing.py
**Status:** v1, single-curator, reviewers wanted; v1 detection rule retired 2026-04-18 per [INDEX.md](https://github.com/lluvr/frame-check-mcp/blob/master/data/frame_library/INDEX.md) "Detection state taxonomy" (external validation study found unsustainable false-positive rate; frame concept retained; V4.2 LLM-judge replaces v1 rule per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) §2.4.1).

## Identification

The default analytical frame for most AI-generated business content. Organizes information around growth metrics, market expansion, competitive positioning, and upward trajectory. The frame is not wrong per se: growth IS relevant to many business questions. It becomes problematic when it is invisible, when it excludes competing perspectives by default rather than by choice, and when every data point is selected to serve the growth narrative without the reader being told that this is what happened.

**What this frame makes visible:**
- Revenue growth, market expansion, adoption rates, competitive advantages
- Upward trajectories and trend extrapolation
- Opportunities and positive catalysts

**What this frame makes invisible:**
- Risks, vulnerabilities, and what could go wrong
- Who is affected by the growth (stakeholders beyond shareholders)
- What is unknown or uncertain about the trajectory
- Historical precedents where similar growth trajectories reversed
- Whether the growth itself is desirable (growth of what, for whom, at what cost)

**Positive examples:** A corporate earnings report that presents Q3 revenue growth, year-over-year improvement, new market entries, and product pipeline expansion. Appropriate because the audience (investors) expects growth metrics. The frame serves its intended purpose.

**Negative examples:** An AI-generated "comprehensive market analysis" that presents only growth metrics, market size projections, and adoption curves without addressing risks, regulatory headwinds, or competitive threats. The word "comprehensive" claims breadth that the growth frame does not deliver.

**Adjacent frames:** Risk Frame (FVS-009, the explicit counter-frame), Failure Framing (FVS-007, what the growth frame lacks), Frame Amplification (FVS-001, growth framing is a specific form of frame amplification: growth narratives compound through extended sessions because growth is the training-data default in business analysis; the inverse is not symmetric), Default Geometry (FVS-004, growth is the default for most AI-generated business analysis; FVS-004 withdrawn per INDEX.md "v1 publication state"), Stakeholder Frame (FVS-011, the counter-frame that names who-is-affected; growth framing typically omits stakeholders entirely while stakeholder framing re-introduces them), Temporal Anchoring (FVS-014, growth-framed content typically projects future; the temporal orientation and the growth assumptions co-occur in business AI content)

**When this frame is appropriate:** Investor presentations, sales collateral, product launch communications, fundraising materials. Any context where the audience expects growth narrative and the growth narrative is clearly labeled.

**When this frame is misleading:** Strategic decision-making where alternatives to growth exist (consolidation, cost reduction, divestiture). Risk assessment. Due diligence. Any context where the reader needs a complete picture rather than a growth picture. Most AI-generated "analysis" that claims to be analytical rather than promotional.

**Honest limits:** "Growth frame" is a label the curator applied, not a term from a specific research tradition. The category is broad enough to contain many sub-frames (market growth, revenue growth, capability growth, user growth) that might deserve separate entries in a more mature library. The detection heuristic (high trends/causes coverage with low risks/stakeholders/uncertainty) is a proxy that works for typical documents but can be fooled by documents that mention risks briefly then dismiss them.

## Decision-readiness implication

**Direct readiness implication.**

When this frame fires, the document is heavy on growth/trends signals and thin on risks. Affects:

- **Coverage** ([methodology](/corpus/decision-readiness/)) via the coverage_balance signal: trends-dominant + risks-thin produces a high coverage_count but low balance, the structural signature of the Completeness Illusion ([FVS-010](/corpus/library/FVS-010.html)) applied through the growth lens specifically. A reader using the document to decide whether to act receives a structurally optimistic frame.

## Generation affordances

**Rewrite prompt structure:** "This analysis operates from a growth frame. Rewrite the same data from a risk frame: for each growth metric cited, name the vulnerability it depends on. For each projection, name the assumption. For each competitive advantage, name the counter-move."

**Counter-document prompt:** "Produce the strongest possible argument against the growth narrative in this document, using only the same data points. Every number cited in the original should appear in the counter-document, reframed as evidence for a different conclusion."

**Salient questions under this frame:**
- What would a risk analyst say about this exact data?
- What is the growth narrative assuming will NOT happen?
- Who benefits from this growth and who does not?
- Is the absence of risk discussion a deliberate editorial choice or an invisible frame default?

## Worked example

**Document excerpt:** "The global AI market reached $196 billion in 2023, representing 50% year-over-year growth. Enterprise AI adoption accelerated with 73% of companies deploying at least one AI application. Investment in AI startups exceeded $50 billion for the third consecutive year."

**Frame present:** Pure growth. Every sentence serves an upward-trajectory narrative: market size, growth rate, adoption rate, investment level.

**Frame absent:** No risks (what if AI investment is a bubble?), no stakeholders (who is displaced by enterprise AI adoption?), no uncertainty (what are the error bars on "$196 billion"?), no causes (what is driving the growth, and are those drivers sustainable?), no comparison (how does this growth rate compare to previous technology cycles that later corrected?).

**How to read past it:** Take each number and ask "what would this look like in a risk frame?" $196B market = concentration risk if dominated by 3-4 vendors. 50% YoY growth = unsustainable at this rate for more than 2-3 years historically. 73% adoption = shallow integration in many cases (adopting AI for one function is not transformation). $50B investment = potential overcapacity if ROI does not materialize at scale.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected via coverage analysis. High coverage of trends and causes with low or absent coverage of risks, stakeholders, and uncertainty is the primary signal. Voice classification (promotional or advisory) strengthens the detection. Temporal orientation skewed toward future strengthens it further.
**Branch B:** In the pre-commit intervention, the user's own default may be a growth frame: "I expect the AI to tell me this market is growing." The pre-commit makes this visible.

## Vocabulary connections

- **The amplification thesis** (HI-062): the growth frame is the most commonly amplified frame in business AI interaction because growth is the training-data default for business analysis.
- **The default geometry** (FVS-004): growth IS the default geometry for most AI-generated business content. Counter-default framing (risk, stakeholder, uncertainty) requires explicit intervention.

## Cross-family reliability

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### V4.2 NEW panel (2026-04-24, library_v4 ratified; stable across all library states)

**library_v4 ratification note (2026-04-24).** Engine canonical is now library_v4 (VERSION 0.2.0), composed as library_v3 Identifications + library_current non-Identifications per fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md. FVS-008's Identification in library_v4 is byte-equivalent to library_v3. **Under library_v4, FVS-008 cross-family AC1 equals library_v3 values: MG 4-family 0.862.** FVS-008 is the library's most stable frame across all measured library states (v2 0.854, v3 0.862, current 0.854, all Tier 1); ratification moves the citation basis but not the strength claim.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.785** (tier: **strong**), per fvs_eval/v4/library_v4_reliability.json. Per-corpus reproducible values (regen: fvs_eval/v4/compute_per_corpus_reliability.py; artifact: fvs_eval/v4/library_v4_per_corpus_reliability.json): MG_v3=0.862 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.954 (3-family partial; Anthropic queued). Historical: MG2_v1=0.812 (library_v1), MG2_v2=0.768 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md; rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **0.891** across n=41 docs at temp=0 (3 verdict flip(s); per fvs_eval/v4/grok_intra_rater_ac1.json). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

FVS-008 achieves the strongest V4.2-era cross-family reliability in the 20-entry library per the library-wide baseline at fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md §2-§3 Tier 1. Panel: Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Measured against `data/frame_library/` (working library, matches library_v4 content at ratification).

**Mixed-genre baseline (n=15)** on fvs_eval/mixed_genre_v1:

| Metric | library_v3 (engine-canonical under library_v4 by Identification byte-equivalence) | library_current (working-library state pre-ratification, historical) | library_v2 (archived earlier) |
|---|---|---|---|
| Gwet's AC1 (pairwise mean) | **0.86** | 0.85 | 0.85 |
| Cohen's kappa (pairwise mean) | **0.66** | 0.53 | 0.53 |
| Raw agreement (pairwise mean) | **0.90** | 0.90 | 0.89 |
| Union prevalence | 4/15 = 27% | 4/15 = 27% | 4/15 = 27% |
| Intersection (all 4 agree positive) | 1/15 | 1/15 | 1/15 |

Per-family positives on library_current historical (of 15 docs): Claude 1, Gemini 3, Grok 2, GPT 2. Library_v3 (engine-canonical under library_v4) per-family positives are not separately recorded in this entry; library_v3 4-family AC1 0.862 is sourced from fvs_eval/v4/library_v4_reliability.json (averaged over MG and MG2) and the library-wide baseline at fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md. **FVS-008 is remarkably stable across all three library states (AC1 range 0.854 to 0.862, prevalence fixed at 4/15 union).** No library revision materially moves FVS-008 reliability, including the library_v4 ratification: engine-canonical numbers under library_v4 differ from library_current historical by less than measurement noise.

**Target-scope corpus (n=4 worked-examples).** Multi-LLM analytical comparisons on finance and founder-decision questions; unanimous agreement across all four families on library_v3 (4-family complete). Library_current target-scope measurement is 3-family partial (Claude pending credit replenishment); the 3 measured families (Gemini, Grok, GPT) all show unanimous positive across all 4 documents. Based on library-version stability observed on mixed-genre, Claude is expected to complete unanimous upon credit replenishment:

| Metric | library_v3 (4-fam complete; engine-canonical under library_v4) | library_current (3-fam partial; pre-ratification historical) |
|---|---|---|
| Gwet's AC1 | 1.00 | n/a (all-positive, prevalence degeneracy) |
| Union prevalence | 100% (4/4) | 100% (4/4) |
| Intersection (all measured agree positive) | 4/4 (4-fam) | 4/4 (3-fam) |

**Construct-validity corroboration.** Per fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md §2.6, FVS-008 achieves Level A construct validity on library_v3 (engine-canonical under library_v4 by Identification byte-equivalence): within-frame reasoning coherence ratio 3.5× over cross-frame baseline on mixed-genre. Library_current historical measured 4.3× on the same construct (a marginal improvement that did not survive cross-frame protection requirements at ratification). Judges agreeing on FVS-008 label also agree on reasoning content across library variants. FVS-008 has strong evidence on both cross-family label agreement and reasoning coherence across both corpora; the metric is stable across library revisions including the library_v4 ratification.

### V4 OLD panel (historical, preserved for generation comparison)

Measured on fvs_eval/mixed_genre_v1 n=15 across the OLD-panel LLM families (Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5) per `F-2026-027`:

| Metric | V4 OLD panel value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.467 |
| Gwet's AC1 (pairwise mean) | 0.733 |
| Raw agreement (pairwise mean) | 0.822 |
| Union prevalence | 20% |

Per-family positives (of 15 docs) on V4 OLD panel: Claude 5, Gemini 2, Grok 4, GPT-5 1.

**Generation comparison** on the same mixed-genre corpus with library_v2: V4 AC1 0.733 → V4.2 NEW panel AC1 0.854 (+0.121); kappa 0.467 → 0.531 (+0.064). Generation-to-generation improvement is material; V4.2 is the canonical detector going forward.

**Latest-model discipline:** periodic re-calibration is operational doctrine across V4 and V4.2 generations. See fvs_eval/v4/MODEL_PANEL.md for panel pinning policy, fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome on the V4 baseline.
