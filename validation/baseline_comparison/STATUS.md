# Baseline-comparison study — status

**Pre-registered protocol:** [`PROTOCOL_v1.md`](PROTOCOL_v1.md)
**H3 (reproducibility):** measurement complete on N=1, results published at [`results_h3/REPORT.md`](results_h3/REPORT.md)
**H1, H2:** pending external-document sourcing + independent rater pool (same constraints as `validation/wedge_behavior/STATUS.md` — methodologically credible H1/H2 measurement requires raters; H3 is mechanically testable without rater confound)

## What ships in this directory

- [`PROTOCOL_v1.md`](PROTOCOL_v1.md) — pre-registered hypotheses (H1 named-absence advantage, H2 source-fidelity advantage, H3 reproducibility advantage), sample-selection criteria, treatment design, locked LLM prompt template.
- [`run_baseline.py`](run_baseline.py) — harness. Frame Check side runs deterministically (no LLM cost). LLM-baseline side runs via Anthropic API when `--call-llm` is passed (operator-authorized) or produces placeholder records otherwise.
- [`analyze_h3.py`](analyze_h3.py) — mechanical Jaccard-distance analyzer for the H3 reproducibility measurement. No human rater required.
- [`rating_rubric_v1.md`](rating_rubric_v1.md) — per-rater rubric for H1 + H2 (when raters are available).
- [`h3_corpus.json`](h3_corpus.json) — single neutral technical-descriptive document used for the H3 measurement.
- [`results_h3/`](results_h3/) — captured H3 data + REPORT.md.

## Why H3 published, H1/H2 deferred

**H3 is mechanical.** The hypothesis is structural: deterministic substrate produces byte-identical output across runs; stochastic LLM produces materially different output across runs. The measurement is exact-string Jaccard on extracted named-pattern sets — no human judgment in the loop. An agent (me) running this measurement produces the same result anyone with the same docs + API key would produce. No rater confound; methodologically valid even when I'm the executor.

**H1 and H2 require raters.** "Did the with-tool agent name a structural absence the without-tool didn't?" — that's a human-judgment scoring task. Same for H2's source-fidelity precision question (per-claim true positive / false positive / false negative classification). When I am both the agent producing responses and the agent scoring them, the result is pipeline verification at best, not validation evidence. Same problem the wedge_behavior pilot surfaced.

The deferral is not engineering; it's methodological. Building parallel infrastructure for me to run H1/H2 anyway would compound the demo-not-evidence concern. The right wait is for externally-sourced documents + independent raters (or multi-model rater triangulation as a weak-but-cheap mitigation).

## H3 finding (summary; full report at [`results_h3/REPORT.md`](results_h3/REPORT.md))

| Side | Mean pairwise Jaccard distance | Distinct outputs |
|---|:-:|:-:|
| Frame Check | 0.0000 | 1 of 5 (byte-identical after stripping timestamps) |
| LLM baseline (Sonnet 4.6 @ T=0.7) | 0.6643 | 5 of 5 (no two runs identical) |

Pre-registered H3 direction confirmed: Frame Check distance = 0; LLM distance > 0. The 0.66 mean pairwise distance means roughly two-thirds of named patterns are NOT shared between any two LLM runs of the same input.

Honest scope: N=1 document, single LLM, single temperature. The pattern (deterministic substrate vs. stochastic LLM) generalizes structurally; the specific numerical magnitude is doc-dependent.

## What's needed to close H1, H2

Same constraints as `validation/wedge_behavior/STATUS.md`:
1. Externally-sourced documents (public LLM-output corpora, random op-eds, Wikipedia featured articles) — eliminates operator-authoring confound.
2. Independent raters with Gwet's AC1 reported per item.
3. PROTOCOL_v2 with rubric refinements applied if the wedge_behavior calibration findings carry over.

The harness is ready. The protocols are pre-registered. The methodologically credible main study awaits human-driven sourcing + rater pool.
