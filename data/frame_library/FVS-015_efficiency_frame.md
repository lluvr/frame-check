# Efficiency Frame

**FVS entry:** FVS-015
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** the sovereignty thesis (the dangerous case is "good outputs that erode capability"), the value test (does it increase autonomy or create dependency), FVS-011 (stakeholder frame as the counter-perspective)
**Status:** v1, single-curator, reviewers wanted; v1 detection rule retired 2026-04-18 per [INDEX.md](https://github.com/lluvr/frame-check-mcp/blob/master/data/frame_library/INDEX.md) "Detection state taxonomy" (external validation study found unsustainable false-positive rate; frame concept retained; V4.2 LLM-judge replaces v1 rule per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) §2.4.1).

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

## Vocabulary connections

- **The sovereignty thesis**: the efficiency frame is directly relevant to the sovereignty thesis because efficiency gains from AI can erode the human capability that sovereignty depends on.
- **The amplification thesis** (HI-062): the efficiency frame amplifies especially strongly because AI IS an efficiency technology. Asking an efficiency tool about efficiency produces the most deeply locked amplification loop.
- **The construction trace** (T-356): the efficiency frame erodes the construction trace by definition. If the human stops doing the work because AI does it faster, the construction trace for that domain disappears.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md. The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.583** (tier: **moderate**), per fvs_eval/v4/library_v4_reliability.json. Per-corpus reproducible values (regen: fvs_eval/v4/compute_per_corpus_reliability.py; artifact: fvs_eval/v4/library_v4_per_corpus_reliability.json): MG_v3=0.619 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.419 (3-family partial; Anthropic queued). Historical: MG2_v1=0.543 (library_v1), MG2_v2=0.642 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md; rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **1.000** across n=41 docs at temp=0 (0 verdict flip(s); per fvs_eval/v4/grok_intra_rater_ac1.json). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.619, kappa 0.034, union 7/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): +0.05.
- **library_v2 (earlier variant):** Gwet's AC1 0.837, kappa 0.237, union 4/15.

See fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md §3 for library-wide tier context and fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: fvs_eval/mixed_genre_v1 n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.667 |
| Cohen's kappa (pairwise mean) | 0.323 |
| Raw agreement (pairwise mean) | 0.778 |
| Union prevalence | 7/15 = 47% |
| Intersection (all 4 agree positive) | 1/15 |

Per-family positives (of 15 docs): Claude 1, Gemini 4, Grok 3, GPT 4.
