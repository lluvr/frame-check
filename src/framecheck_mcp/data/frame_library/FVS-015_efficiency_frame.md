# Efficiency Frame

**FVS entry:** FVS-015
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13

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

**Adjacent frames:** Growth Frame (FVS-008, shares the optimization orientation but focuses on expansion rather than efficiency; efficiency frames often embed growth assumptions, the inverse is not required), Stakeholder Frame (FVS-011, asks who is affected by the efficiency gains; efficiency framing usually suppresses stakeholder view, the asymmetry the catalog records), Oracle Frame (FVS-013, efficiency claims from AI are often accepted without questioning whether efficiency is the right lens)

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
