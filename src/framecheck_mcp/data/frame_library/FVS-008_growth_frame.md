# Growth Frame

**FVS entry:** FVS-008
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12

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
