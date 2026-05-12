# H3 reproducibility — N=1 pre-registered measurement

**Pre-registered protocol:** [`PROTOCOL_v1.md`](../PROTOCOL_v1.md), §"Hypothesis" H3
**Pre-registered claim:** Frame Check returns byte-identical structured output for byte-identical input across runs (deterministic). LLM-baseline returns materially-different framing analyses across runs at temperature > 0 (Jaccard distance > 0).
**Date executed:** 2026-05-12
**Spend:** ~$0.18 (5 LLM calls × ~$0.036 average; Frame Check side has zero LLM cost)
**Methodologically valid without independent raters:** the H3 measurement is mechanical (Jaccard distance on extracted named-pattern sets); no human judgment in the scoring loop.

## Configuration

- **Document:** `h3-mcp-stdio-overview` — synthetic technical-descriptive prose about how MCP stdio transports work (~480 words). Doc selection rationale: H3 reproducibility requires only that the document produce non-trivial LLM analysis output. Doc choice is methodologically neutral for H3 (the measurement is reproducibility-of-the-analyzer, not quality-of-the-analysis). Technical descriptive content avoids the positioning-leak risk that surfaced for the wedge_behavior pilot.
- **Frame Check side:** 5 runs of `mcp_server.build_epistemic_payload` with `include_divergence=True, domain_hint="finance"` (the protocol-pre-registered defaults).
- **LLM-baseline side:** 5 runs of Anthropic `claude-sonnet-4-6` at temperature 0.7, system prompt `"You are a helpful assistant."`, locked prompt template per [`PROTOCOL_v1.md`](../PROTOCOL_v1.md). max_tokens = 4000 (no truncation observed).
- **Measurement:** Jaccard distance on the union of {voice classification, addressed perspectives, detected pattern names, absent pattern names} extracted from each run's structured output. Pairwise distance across the 5 runs of each side; mean reported.

## Findings

| Side | Runs | Distinct outputs (after stripping timestamps + latency) | Mean pairwise Jaccard distance | Min | Max | Named-pattern set size per run |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Frame Check | 5 | 1 (byte-identical) | **0.0000** | 0.0 | 0.0 | 25 |
| LLM baseline (Sonnet 4.6 @ T=0.7) | 5 | 5 (no two runs identical) | **0.6643** | 0.5217 | 0.8148 | 17, 17, 17, 15, 12 |

**Pre-registered direction confirmed.** Frame Check distance = 0 (deterministic). LLM distance > 0 (66% mean pairwise; 81% maximum on this corpus). Two LLM runs of the same document with the same prompt + model + temperature produced named-pattern sets that disagreed on roughly two-thirds of items.

The variance is concentrated in the *detected pattern names* axis — the LLM invented different free-text pattern labels each run ("Mechanism Explanation Frame", "Naturalization Frame", "Authoritative Specification Frame" in one run; different labels in others). The *voice classification* and *perspectives present/absent* axes are more stable across runs but still varied non-trivially.

## What this measurement supports

- **The reproducibility component of the deterministic-substrate claim is empirically demonstrated on N=1.** Frame Check's byte-equality guarantee holds end-to-end through the public API surface. The same input on the same wheel produces the same payload, modulo timestamps + latency that legitimately vary.
- **The LLM-as-analyzer baseline produces materially-different framing analyses on identical input.** The 66% mean pairwise Jaccard distance is high enough that an integrator depending on LLM-prompted framing analysis would see meaningful variation between runs of the same document. For workflows that need stable structural output (audit trails, regression tests on AI behavior, citation-grounded analysis), the LLM baseline is structurally unsuited regardless of how good the prompt is.

## What this measurement does NOT support

- **N=1.** A single document. Pattern generalizes structurally (Frame Check determinism is by-design; LLM variance at T>0 is the basic property of stochastic decoding) but the specific 0.66 distance number is doc-dependent.
- **Single LLM, single temperature.** Sonnet 4.6 at T=0.7 only. Other model families or temperatures may produce different variance magnitudes.
- **No information-quality comparison.** H3 measures reproducibility, not whether either side's analysis is *correct* or *useful*. H1 (named-absence reliability advantage) and H2 (source-fidelity precision advantage) are the protocol's quality hypotheses; both require independent raters and are not addressed here.
- **The pattern-name axis is dominated by free-text variance.** LLM responses generated different label phrasings for similar-sounding concepts; Jaccard treats "Mechanism Explanation Frame" and "Mechanism Walkthrough Frame" as fully distinct items. A semantic-clustering metric would yield lower distance numbers but at the cost of measurement objectivity. The pre-registered metric is exact-string Jaccard; that is what this report uses.

## Reproducibility

Anyone with `ANTHROPIC_API_KEY` can reproduce this measurement:

```bash
ANTHROPIC_API_KEY=$(your-vault-decrypt) python3 \
    validation/baseline_comparison/run_baseline.py \
    --corpus validation/baseline_comparison/h3_corpus.json \
    --results-dir /tmp/baseline-h3 \
    --runs-per-side 5 \
    --call-llm

python3 validation/baseline_comparison/analyze_h3.py \
    --results-dir /tmp/baseline-h3
```

Frame Check side reproduces byte-identically across re-runs by design. LLM side will produce different specific responses each invocation (stochastic decoding); the EXPECTED PATTERN — Frame Check distance = 0, LLM distance > 0 — should hold across runs.

The captured `data.json` from the 2026-05-12 execution is bundled in this directory for direct inspection without needing to re-run.

## Status

H3 reproducibility hypothesis: **measurement consistent with pre-registered direction at N=1**. Pattern is structural (deterministic substrate vs. stochastic LLM) so generalization is structural; numerical magnitude is doc-dependent and would benefit from a wider sample if the operator wants tighter confidence intervals.

H1 (named-absence reliability advantage) and H2 (source-fidelity precision advantage) remain pending — they require externally-sourced documents + independent raters per the methodological constraints documented at `validation/wedge_behavior/STATUS.md`.
