# Growth Frame

**FVS entry:** FVS-008
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** M-004 (Frame Inventory, named as example), HI-061 (Frame Amplification case study), EXP-094 (NVIDIA analysis), detect_coverage in framing.py
**Status:** v1, single-curator, reviewers wanted

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

**Adjacent frames:** Risk Frame (FVS-009, the explicit counter-frame), Failure Framing (FVS-007, what the growth frame lacks), Frame Amplification (FVS-001, growth frame compounds through extended sessions), Default Geometry (FVS-004, growth is the default for most AI-generated business analysis)

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

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.467 |
| Gwet's AC1 (pairwise mean) | 0.733 |
| Raw agreement (pairwise mean) | 0.822 |
| Union prevalence (all families) | 20% |

Per-family positives (of 15 docs): Claude 5, Gemini 2, Grok 4, GPT-5 1.

**V4 detection mode:** default

**Interpretation:** Substantial cross-family agreement.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-12; grounded-authorship retrofit 2026-04-25 per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04)
- EXP-094 NVIDIA fiscal-2024 analysis case study (HI-061 Frame Amplification deep dive)
- M-004 Frame Inventory corpus (multiple business-content samples)
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22 per Option D ratification; aggregate fire rates pending Tier A quarterly export)

**Failure record.** Three failure modes observed in operation:
1. Known false positives in metaphorical-growth contexts. Rule-based detector fires on figurative growth language ("the city's heartbeat grew louder") without genre context. V4.2 LLM judge usually catches; rule-only mode does not.
2. Dismissive-mention bypass (mitigated 2026-04). Documents mentioning risks briefly then dismissing them ("there are some risks, but they are largely overblown") historically passed through as Growth-Frame-without-risk-balance. Sentence-bounded bidirectional diminisher filter shipped per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) §3.5; three new tests cover the regression.
3. Cross-family variance on implicit growth framing. Documents where growth is embedded in enabling-infrastructure narrative rather than explicit growth language produce per-family disagreement (F-2026-027: Claude 5/15, GPT-5 1/15; 5x family-disagreement gap on subtle growth). Documented sensitivity, not yet resolved.

**Success record.** Two operationalized cases with traceable outcome:
1. NVIDIA fiscal-2024 analysis (EXP-094, HI-061). Document presented market dominance + sustained growth without risk discussion. Growth Frame fired. Counter-frame rewrite (Risk Frame application via L2 reframe) surfaced concentration risk, $190B-bubble scenario, regulatory exposure (80% market share threshold), historical-pattern reversal. Material additions a strategic reader would want before commitment.
2. L2 reframe controlled-transformation study. Growth-to-Risk pair scored 5/5 on coverage shift, 5/5 on density shift, 5/5 on suggestion shift across two documents and frame-pairs (per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) §5.2). One of the cleanest reframe operations in the L2 study; structural validation that Growth and Risk are operationally distinct counters, not nominal opposites.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment from business or strategy work where Growth Frame (FVS-008) was operative whether visible or invisible at the time; (2) the contrast between the Growth-framed reading and a counter-frame reading on the same data (typically Risk Frame FVS-009, Stakeholder Frame FVS-011, or Failure Framing FVS-007 applied as the canonical counter); (3) the outcome differential that recognition produced (or that non-recognition cost); (4) concrete first-person recall. Held open per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application (no tools, experienced reader): ~30-60 seconds to recognize "growth language without risk balance" in a document of 500-2000 words
- V4.2 LLM judge invocation: ~$0.0008/document (Grok 4.1 fast non-reasoning per fvs_eval/v4/MODEL_PANEL.md NEW panel; web production target)
- One-pass detection: appropriate for any business-strategy reading
- Deep-dive engagement: appropriate when the document drives a high-stake decision; L2 counter-frame rewrite adds ~$0.010/invocation

**Applicability metadata.**
- Domains: business strategy (high stake-relevance), startup pitch decks (high), product launches (high), financial outlooks (high), market analyses (medium), AI-assisted business analysis (high)
- Decision types: investment, hiring, market entry, fundraising, product roadmap, strategic-partnership evaluation
- Stake levels: medium to high. Low-stake casual reading does not require this analysis.
- Inappropriate contexts: poetry, art criticism, technical documentation, scientific peer review, narrow factual queries, journalism style guides

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa 0.467, AC1 0.733, raw agreement 0.822, union prevalence 20% (Claude 5, Gemini 2, Grok 4, GPT-5 1 of 15)
- L2 reframe study: 5/5 on Growth-to-Risk transitions across two documents and one consistency check
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work, contingent on production resume per the release-arc commitments)
