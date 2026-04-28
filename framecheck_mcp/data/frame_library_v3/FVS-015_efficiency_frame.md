# Efficiency Frame

**FVS entry:** FVS-015
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** the sovereignty thesis (the dangerous case is "good outputs that erode capability"), the value test (does it increase autonomy or create dependency), FVS-011 (stakeholder frame as the counter-perspective)
**Status:** v1, single-curator, reviewers wanted

## Identification

Organizes information around cost reduction, optimization, speed, throughput, and doing more with less. The efficiency frame treats every situation as an optimization problem and every outcome as measurable in units of productivity. AI-generated content defaults to the efficiency frame because AI is itself positioned as an efficiency technology, and the training data overwhelmingly frames AI in terms of cost savings, speed improvements, and productivity gains.

**What this frame makes visible:**
- Cost savings, time savings, throughput improvements, headcount reductions
- Process optimization and automation opportunities
- Comparative metrics (before/after, manual/automated, old/new)
- ROI calculations and payback periods

**What this frame makes invisible:**
- Who bears the cost of the efficiency gain (the stakeholder perspective)
- Whether the thing being optimized should exist at all (the strategic perspective)
- What capabilities are lost when a process is automated (the sovereignty perspective)
- Quality dimensions that efficiency metrics do not capture (creativity, resilience, adaptability, human judgment)
- The difference between efficiency and effectiveness (doing things right vs doing the right things)

**Positive examples:** An operations review that examines process efficiency with specific metrics (cycle time reduced from 14 days to 3, error rate from 5% to 0.3%) in a context where efficiency IS the relevant question and the metrics ARE the right ones.

**Negative examples:** An AI-generated analysis of a school's teaching practices that frames everything in terms of "student throughput," "learning efficiency," and "cost per outcome" without addressing educational quality, student wellbeing, teacher autonomy, or the difference between measurable learning and meaningful learning.

**Adjacent frames:** Growth Frame (FVS-008, shares the optimization orientation but focuses on expansion rather than efficiency), Stakeholder Frame (FVS-011, asks who is affected by the efficiency gains), Oracle Frame (FVS-013, efficiency claims from AI are often accepted without questioning whether efficiency is the right lens)

**When this frame is appropriate:** Operations management, process improvement, cost analysis, performance benchmarking. Any context where the question genuinely IS "how do we do this better/faster/cheaper" and the "this" has already been validated as worth doing.

**When this frame is misleading:** Strategic decisions about WHAT to do (efficiency assumes the activity should continue; strategy questions whether it should). Creative work (efficiency metrics destroy the exploratory waste that produces breakthroughs). Human development (efficiency framing applied to learning, therapy, or growth reduces these to transactions). AI deployment decisions (the question "how much does AI save" hides the question "what does AI cost in human capability").

**Honest limits:** The efficiency frame is pervasive enough that detecting it requires measuring what is ABSENT (stakeholder, strategic, quality, sovereignty dimensions) rather than what is present. The coverage detector can identify when stakeholders, uncertainty, or risks are missing, but it cannot distinguish between "efficiency frame" and "any narrow analytical frame" without semantic understanding of whether the content is specifically about optimization. This entry names the efficiency frame as a specific instance of narrow framing that is especially common in AI-generated content about AI.

## Decision-readiness implication

**Direct readiness implication.**

Like the Growth Frame ([FVS-008](/corpus/library/FVS-008.html)), the Efficiency Frame is a narrow lens. Affects:

- **Coverage** ([methodology](/corpus/decision-readiness/)): efficiency-dominant + other-dimensions-thin produces a structurally narrow profile. AI-generated content defaults to this frame because AI is positioned as an efficiency technology in training data. A document optimized for efficiency commentary is structurally weak on coverage of human/social/risk consequences.

## Generation affordances

**Rewrite prompt structure:** "This analysis frames the situation as an optimization problem. Rewrite from the question: should this be optimized at all? What is lost in the optimization? Who bears the cost? What capabilities are being traded for efficiency? Is the activity being optimized the right activity in the first place?"

**Counter-document prompt:** "This document measures success in efficiency metrics. Produce the version that measures success in: human capability preservation, creative capacity, resilience to unexpected situations, quality of outcomes as judged by the people affected (not by the people measuring). Use the same data points but different success criteria."

**Salient questions under this frame:**
- Is efficiency the right lens for this situation, or has it been applied by default?
- What is being optimized, and should it be?
- What is lost in the optimization that is not captured by the efficiency metrics?
- Does this efficiency gain create a dependency that is worse than the cost it saves?

## Worked example

**Document excerpt:** "Implementing AI-powered document review reduces legal review time by 85% and cuts per-document costs from $150 to $22. The system processes 10,000 documents per hour compared to 40 per hour for human reviewers."

**Frame present:** Pure efficiency. Time savings, cost savings, throughput comparison. Every metric is a ratio of before/after.

**Frame absent:** What errors does the AI make that humans do not? What types of documents require human judgment that the AI cannot replicate? What happens to the legal team's expertise when they stop reading documents? What is the liability exposure when the AI misses a critical clause? Does the 85% time reduction include the time spent correcting AI errors?

**How to read past it:** The efficiency frame says "85% faster." The sovereignty frame says "what legal judgment capability is eroded when lawyers stop reading documents?" Per the sovereignty thesis: the most dangerous failure mode is good outputs that erode human capability.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected when a document has high trends/causes coverage (optimization metrics, productivity comparisons) with absent stakeholders and uncertainty dimensions. The combination of optimization language with missing "who is affected" and "what could go wrong" signals is the detection heuristic.
**Branch B:** In the pre-commit intervention, the user can challenge their own efficiency default: "Am I asking AI to help me optimize, or am I asking AI what I should do?" These are different questions with different frames.

## Vocabulary connections

- **The sovereignty thesis**: the efficiency frame is directly relevant to the sovereignty thesis because efficiency gains from AI can erode the human capability that sovereignty depends on.
- **The amplification thesis** (HI-062): the efficiency frame amplifies especially strongly because AI IS an efficiency technology. Asking an efficiency tool about efficiency produces the most deeply locked amplification loop.
- **The construction trace** (T-356): the efficiency frame erodes the construction trace by definition. If the human stops doing the work because AI does it faster, the construction trace for that domain disappears.

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.456 |
| Gwet's AC1 (pairwise mean) | 0.802 |
| Raw agreement (pairwise mean) | 0.856 |
| Union prevalence (all families) | 15% |

Per-family positives (of 15 docs): Claude 1, Gemini 2, Grok 3, GPT-5 3.

**V4 detection mode:** default

**Interpretation:** Substantial cross-family agreement.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-13; grounded-authorship retrofit 2026-04-25 per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04; prevalence 15 percent)
- sovereignty-thesis source: "the dangerous case is good outputs that erode capability"
- value-test source: does the change increase autonomy or create dependency
- `detect_coverage` in `framing.py` (rule-based detector; partial signal via absence of stakeholders and uncertainty)
- AI-powered legal document review worked example (v1 Identification)
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Detection requires measuring what is ABSENT not what is present. The efficiency frame is so pervasive in AI-generated content that detecting it requires identifying what is missing (stakeholder, strategic, quality, sovereignty dimensions) rather than what is present. The coverage detector can identify when stakeholders/uncertainty/risks are absent, but distinguishing "efficiency frame" specifically from "any narrow analytical frame" requires semantic understanding.
2. Cross-family agreement moderate at moderate prevalence. F-2026-027 showed kappa 0.456, AC1 0.802 (substantial), prevalence 15 percent (Claude 1, Gemini 2, Grok 3, GPT-5 3). Cross-family agreement is reasonable when the frame fires; detection is consistent across families.
3. Sovereignty-thesis claim is structural argument. "Efficiency gains from AI can erode the human capability that sovereignty depends on" is grounded in the sovereignty thesis. Direct empirical measurement of capability erosion from AI-driven efficiency gains is open work; the claim is structurally argued but not quantified.

**Success record.** Two operationalized cases:
1. AI-powered legal document review worked example (v1 Identification). Document presented "85 percent time reduction" plus "10,000 documents per hour" as pure-efficiency framing. Counter-frame surfaced: what AI errors does it make; what types require human judgment AI cannot replicate; what happens to legal team expertise when they stop reading documents; liability exposure from missed clauses; whether 85 percent reduction includes time spent correcting AI errors. Per the sovereignty thesis: most dangerous failure mode is good outputs that erode human capability.
2. Sovereignty-thesis operational integration. Efficiency frame is structurally connected to the sovereignty thesis. The "what capabilities are lost" question is the operational diagnostic for distinguishing efficiency-as-acceptable-tradeoff from efficiency-as-capability-erosion. Embedded in Frame Check methodology as part of the broader sovereignty discipline.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where the operator caught themselves accepting an efficiency framing that hid a capability cost (AI did the work; the operator's own capability for that work atrophied); (2) the sovereignty-frame counter-question applied ("what capability is being traded for this efficiency"); (3) outcome differential observed (decision adjusted, AI use rebalanced, capability preserved through deliberate practice); (4) concrete first-person recall. Held open per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application: ~30-60 seconds per efficiency claim ("what capability is lost; who bears the cost")
- V4.2 LLM judge invocation: ~$0.0008/document
- Sovereignty-frame counter-rewrite: 5-10 minutes for substantive analysis
- Use depth: any document framing AI deployment as efficiency win; high-leverage on AI procurement and AI workflow design

**Applicability metadata.**
- Domains: AI deployment decisions (high stake-relevance), operations management (medium-high; efficiency IS often appropriate but capability cost matters), process improvement (medium-high), automation strategy (high), AI procurement (high)
- Decision types: AI workflow design, automation deployment, capability-vs-efficiency tradeoffs
- Stake levels: medium to high; capability erosion compounds with deployment scale and time
- Inappropriate contexts: pure operations management where the activity has been validated as worth doing AND efficiency is the relevant question AND the metrics are right; execution-focused work where capability is not the variable

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa 0.456, AC1 0.802 (substantial), raw 0.856, union prevalence 15 percent (Claude 1, Gemini 2, Grok 3, GPT-5 3 of 15)
- The sovereignty thesis origin
- the autonomy-vs-dependency value test
- AI legal document review worked example
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
