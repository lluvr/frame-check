---
transmission_id: T-311
display_title: "Most AI Numbers Are Fabricated"
type: EVIDENCE
summary: "77 to 100 percent of AI-generated numbers are temporally unstable. Source material fixes it. Prompts don't."
published: 2026-03-23
models: "xAI / Gemini"
source_url: https://blog.clarethium.com/blog/fabrication-architecture
---

# The Fabrication Architecture

AI output looks specific. Confident. Well-structured. Twelve percentages. Eight claims. Three named benchmarks.

Two of the numbers don't exist.

Not wrong. Fabricated. The model didn't look them up. It made them up. As far as we can tell from behavior, there's no reliable internal distinction between "I know this" and "I made this up": though mechanistic interpretability research may eventually find one.

The natural assumption is better prompts fix this. Three prompt architectures, three model families, multiple experiments. Prompts control how MUCH the model fabricates. They don't control WHETHER it fabricates.

Take any analytical topic. Ask three different AI models to write about it. Count the numbers. Now run the same model, same prompt, same topic three more times. Count how many numbers appear in all versions.

20 topics on one generator. Replicated across three generators with 10 topics. 77 to 100 percent of model-generated numbers changed between runs. On two generators, none survived. On the third, roughly a quarter did, mostly round numbers reused across different claims. The model isn't recalling facts. It's generating plausible-looking results.

77 to 100 percent of model-originated numbers change when you regenerate the same prompt. They're temporally unstable. Temporal instability is a proxy for fabrication, not identical to it. A number could be unstable AND correct (sampled differently each time from genuine knowledge), or stable AND wrong (a memorized falsehood). In one controlled comparison, nearly half the model-generated numbers coincidentally matched real sources. The problem isn't that they're all wrong. It's that from the output alone, you can't tell which are real.

So you add constraints. Require evidence. Demand sourcing. Specify epistemic standards. Three levels tested. BASIC: "analyze this topic." STANDARD: structural constraints requiring shaped, specific output. PROTOCOL: the full system built over 50 experiments, every claim constrained for honesty, evidence, and falsifiability.

BASIC: 85.8 percent fabrication. STANDARD, with structural constraints: 78.4. Slightly better. PROTOCOL, with full epistemic constraints demanding evidence and sourcing: 90.7. Worse than unconstrained. On this generator (xAI), structural constraints helped modestly and epistemic constraints pushed fabrication up. Template slots demanding specificity got filled with fabrication.

On a different generator (Gemini Flash), the direction reversed. Constraints increased fabrication instead of reducing it. On one topic, the unconstrained version produced zero numbers at all. Constraints forced the model to generate claims it wouldn't have made unprompted, and all were fabricated. The condition gradient is generator-specific. The aggregate rate (majority fabrication regardless of constraints or generator) is robust.

What prompts DID change was volume. PROTOCOL produced roughly a third the numerical claims of STANDARD (10.0 per thousand words versus 32.8). The constraints made the model claim less, not claim better. Net fabricated numbers per document went down: not because accuracy improved, but because the model generated fewer claims total. A system that demands honesty produces fewer lies, each one more elaborate. The rate is structural. The volume is prompt-controllable.

The mechanism: demanding specificity narrows what the model can produce. It needs things that look like real numbers, real benchmarks. If it has that knowledge, it retrieves it. If it doesn't, it generates something that looks right. As far as we can tell from behavior, the model doesn't know the difference. Neither do you.

Other AI models rate the constrained output as higher quality 75 percent of the time (LLM-judged; human domain expert agreement: 0/5 on holistic quality). The evaluators reward the performance of specificity, not its truth. How much maps to actual academic research? BASIC: 33 percent grounded. STANDARD: 6.7 percent. Five times less grounded, five times more precise-sounding.

Then real data gets added to the prompt. Same models. Same topics. Same prompts. But this time, actual source material in context.

BASIC went from 85.8 percent temporal instability to 1.7 percent unsourced (self-verified, programmatic matching shows 2-10 percent range). STANDARD from 78.4 to 2.6. PROTOCOL from 90.7 to 3.4.

Source material moved the needle 46 percentage points. Prompt architecture moved it 6. Different measurement constructs from different experiments, so the ratio is an ordering indicator, not a precise multiple. But the ordering is clear: source material is the dominant variable. The coupling that survived 30 experiments broke the moment the model had something real to build from. It was never about how models generate. It was about generating without anything real to ground against.

Months went into building PROTOCOL. The entire constraint architecture was solving the wrong problem.

Presence alone isn't enough. The model needs explicit instruction, not just data nearby. Monitoring ("flag unsourced numbers") versus prohibition ("use only numbers from the source"). Prohibition was five times better. 1.6 percent versus 7.7. And it cost nothing. The model compensated by extracting more and writing more, not less.

Three steps. Put real data in the prompt. Add one line: "Use only numbers from the source material above. If the source doesn't contain a relevant number, make the analytical point without inventing numbers." After the output, match the numbers against the source.

This isn't a prompt trick. It's a workflow change. The variable that matters most isn't how you ask. It's whether you provide something real to work from.

One thing source grounding does NOT change: how the output reads. In a blinded comparison, a domain expert rated source-present and source-absent output as equivalent. The fabricated version was rated more trustworthy in some cases because it cited more sources, used more specific numbers, and asserted with more confidence. The sourced version acknowledged limitations and had fewer citations because it only cited what was actually provided. The trust signals are inverted: the less reliable output has more of the markers humans use to assess authority. Source grounding doesn't make the output LOOK better. It makes the output CHECKABLE. The third step (match the numbers against the source) is where the value lives. Without that step, the fabricated version wins on perceived authority.

The measurement approach: regenerate and count what changes: converges with academic methods. A head-to-head against SelfCheckGPT (Manakul et al., 2023), which uses LLM sentence-level consistency checking, produced the same directional result on the same documents: both methods detect fabrication in source-absent output, both show near-zero in source-present. The programmatic approach costs nothing after generation. The LLM approach requires hundreds of API calls. Same signal.

A direct verification check tested it from a different angle. Twenty-three claims citing named sources (McKinsey, BCG, Gallup, Gartner, Standish Group) were checked against the cited sources' actual publications. Two of twenty-three verified correct. Both are among the most widely-cited statistics in their domains: Gartner's $15 million data quality cost and the Standish Group's 29 percent project success rate. Essentially common knowledge. The other twenty-one were assembled: real components, fabricated binding.

The model doesn't just generate unstable numbers. It fabricates the source attribution through five distinct mechanisms. It takes a real number from a real source and attaches it to a different claim (McKinsey's "45%" is about cumulative profit impact over a decade; the model wrote "45% of firms experienced disruptions lasting more than one month"). It performs a correct calculation on real data and presents the result as a direct finding (Gallup: 45% vs 39% stress = 15% relative increase, presented as "Gallup reports 15% higher burnout"). It generates domain-appropriate components and combines them ("BCG analysis of 1,500 firms" when BCG studied 150). It attaches a real statistic to the wrong source ("85% of analytics projects fail" is Gartner, not McKinsey). It applies real data to a broader scope than the original (Standish CHAOS report on all IT projects, presented as specifically about migrations).

Each component is plausible. Each passes a fact-check that only verifies individual parts. The fabrication is in the binding: this source says this number about this topic.

Numbers that don't change across regenerations aren't necessarily right. The same "70%" shows up in three versions attached to three unrelated claims: revenue concentration, stall rates, headcount allocation. Not the same assertion recurring. Just a common number in business contexts. The regeneration test catches more than chance would. But verification against the source catches what the test can't.

One limit: the measurement tools (temporal consistency, number matching) tested reformulation. They measure the fabrication layer. Vocabulary and causal framing stay at baseline across regenerations. The tools solve one layer, the most measurable, most verifiable. The layers above it are yours.

But source grounding itself reaches further than its measurement. On reasoning tasks with known ground truth (medical diagnosis, financial forensics, architecture decisions, legal review, root cause analysis), source-present output found the correct answer 75 percent of the time versus 38 percent without source. Fewer wrong conclusions. More appropriate confidence. Source-absent output was overconfident, making strong claims without backing. Three of five tasks showed source-present dramatically outperforming (financial analysis, architecture decisions, root cause analysis). One was moderately better (legal review). One was tied (medical diagnosis). Source material doesn't just stabilize numbers. It improves correctness on reasoning tasks with verifiable answers. The output with source is actionable because the claims are checkable AND more likely correct.

What survived testing:
- 77-100% of model-originated numbers are temporally unstable across all generators
- Epistemic constraints increase fabrication rate. Condition gradient is generator-specific. Direction consistent across topics.
- Source material reduces fabrication from majority rates to single-digit percentages. Source effect is roughly an order of magnitude larger than prompt effect.
- Prohibition outperforms monitoring by a factor of five
- Format-robust, density-robust
- Ground-truth check: 2 of 23 named-source citations verified correct. Both correct claims are widely-cited common knowledge. Five fabrication mechanisms confirmed.
- Unconstrained output is 5x more grounded in real academic knowledge than constrained output

What didn't survive:
- "100% fabrication is universal" killed. One generator shows 77% with topic-dependent retrieval
- "PROTOCOL fixes fabrication" killed. Highest fabrication rate of all conditions
- "Source grounding fixes everything above data" partially killed. Vocabulary and causal framing stay at baseline for same-topic regeneration. But on reasoning tasks with ground truth, source-present output finds the correct answer roughly twice as often as source-absent. Source grounding improves correctness on reasoning tasks, not just reformulation.

Honest limits:
- N=1 practitioner. Zero external replication
- Fabrication measurement tested reformulation only. Source grounding's correctness benefit tested on 5 reasoning domains. Strategy, creative untested.
- Source size 600 characters to 4KB tested. Larger untested
- Conflicting sources untested. Qualitative-only sources untested
- "Fabrication rate" uses temporal instability as proxy. Roughly half of temporally unstable numbers coincidentally match real sources. The rate measures unverifiability, not wrongness
- Condition gradient is generator-specific. Practical advice on constraint effects should be generator-scoped.
- Domain expert cannot distinguish sourced from fabricated by reading, even in own deep domain
