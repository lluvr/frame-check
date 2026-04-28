---
transmission_id: T-351
display_title: "How to Stop AI from Making Up Numbers"
type: RECIPE
summary: "Source material drops AI fabrication from 85% to single digits. Three steps."
published: 2026-03-23
models: "xAI / Gemini"
source_url: https://blog.clarethium.com/blog/source-conditioning
---

# Source Conditioning

77 to 100 percent of AI-generated numbers are temporally unstable. Regenerate the same prompt and they change. Better prompts reduce how many claims the model makes, but not how often those claims are fabricated. Here's what actually fixes it.

Put real data in the prompt. Unsourced numbers drop dramatically. From roughly half the output to under 10 percent with source material, single digits with prohibition.

Not moderation. Replacement. When the model has real numbers in context, it uses them instead of inventing. Without source material, the model generates from parametric memory, which is unreliable. With source material, it draws from what's in front of it: your data.

Tested across three model families, three topics, eight sub-experiments, roughly 100 documents. Source material moved source-attribution rate 46 percentage points. Prompt architecture moved the unsourced rate 6. Different measurement constructs, but the ordering is clear: source material is the dominant variable, and the variable almost nobody provides.

Three steps.

Paste real data before your instruction. A report, a dataset summary, specific numbers you trust. A paragraph is enough. A page works better. This isn't optional context. This determines whether the output contains real information or invented information.

Add one line: "Use only numbers from the source material above. If the source doesn't contain a relevant number, make the analytical point without inventing numbers."

That's prohibition, not monitoring. The distinction matters. Monitoring asks the model to flag its own unsourced claims. Prohibition tells it not to generate them. Five times better. 1.6 percent versus 7.7. In testing, the model couldn't reliably evaluate its own output. The same process that generated the token is the process evaluating it.

After the output, match the numbers against the source. Most flags will be legitimate arithmetic on your data. Review the rest.

Prohibition costs nothing. The model compensates by extracting more from the source and writing more, not less. The output doesn't get shorter or less detailed. It gets differently detailed: grounded in the data you provided instead of inventing specifics to fill slots.

Even partial sources work. Tested what happens when key sections are removed from the source material. Fabrication stayed near zero (0.4 percent with partial source versus 3.7 percent with very sparse source). When data was incomplete, the model adapted by writing qualitative analysis instead of fabricating numbers. It didn't try to fill the gap with invented data. It adjusted the analysis to match what was available.

The graceful degradation is important. It means you don't need perfect source material. A rough summary with key numbers is enough. A paragraph from a report works. A table from a dataset works. You don't need to provide everything. You need to provide enough that the model has real data to work from instead of generating from parametric memory.

What source material changes beyond the numbers: epistemic stance. In testing (5 domain tasks, N=1 domain expert), both source-present and source-absent outputs reached similar high-level conclusions. The difference was HOW they got there. Without source, the model makes strong claims immediately: premature convergence with overconfidence. With source, the model states what it knows and grounds its confidence in specific data. Same conclusion, different reliability. The source-present version is actionable because the claims are verifiable. The source-absent version requires trusting the model's parametric memory, which is the thing that fabricates.

Two things this doesn't fix. It works for reformulation: source material present, analysis requested. For reasoning, strategy, creative exploration, the source material may not exist. The recipe doesn't apply there. And it reaches the data layer only. Numbers stabilize. Vocabulary, conclusions, causal reasoning stay at baseline. One layer solved. Everything above it still requires your judgment.

What survived testing:
- Source material reduces unsourced numbers from majority to single digits across all tested generators
- Prohibition outperforms monitoring 5x (1.6% vs 7.7%)
- Cross-generator confirmed, with even larger effect on Gemini
- Partial sources work (0.4% fabrication with key sections removed)
- Model compensates with more extraction, not less output
- Source grounding improves epistemic calibration: both conditions reach similar conclusions, but source-present is appropriately confident while source-absent is overconfident

What didn't survive:
- "Source material fixes everything" killed. Vocabulary, conclusions, reasoning stay at baseline.
- "Source format matters" killed. Structured and narrative produce equivalent results (0.7% vs 0.9%).

Honest limits:
- All reformulation tasks. Reasoning, creative, strategic untested.
- Source size 600 chars to 4KB tested. Larger untested.
- March 2026 models. As models improve retrieval, the gap may narrow.
