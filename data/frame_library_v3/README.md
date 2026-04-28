# Frame library v3 (Step 4 ratified, 2026-04-23)

This is the current authoritative FVS library following Step 4
library-revision test ratification. Differences from v1:

| Frame | Change | Source |
|---|---|---|
| FVS-010 Completeness Illusion | unchanged (v2 revision rejected — no reliability improvement) | library_v1 |
| **FVS-012 Uncertainty Frame** | **revised** (structural-organization requirement) | library_v2 |
| **FVS-016 Authority by Citation** | **revised** (3-case fire + 3-case exclude) | library_v2 |
| **FVS-018 Scope Narrowing** | **revised** (covert vs explicit narrowing) | library_v2 |
| **FVS-020 Invisible Frame** | **retired from detection** (Path B); `vocabulary_only` | library_v1 content + retirement banner |
| All 15 other frames | unchanged | library_v1 |

## Ratification evidence

Step 4 D3 library revision test (fvs_eval/v4/step4_library_v2_summary.md):
- Adopted revisions showed cross-family Gwet AC1 lifts of +0.04 to +0.34
  under new panel (Haiku 4.5 / Gemini 3.1 flash lite / Grok 4.1 fast /
  GPT-5.4 mini) on v1 + v2 corpora (n=41 docs, 328 API calls)
- Rejected revision (FVS-010) showed no improvement
- Retired frame (FVS-020) showed REGRESSION under Path A; retirement
  path (Path B) chosen instead of further revision attempts

## Forward evolution

library_v3 is the current target for V4.2 detector engine. Future
revisions should be informed by:
1. Curator ground truth (F-2026-017 pending) anchoring cross-family
   metrics to non-LLM truth
2. User feedback telemetry from V4.2 in production (real usage data
   for frame utility assessment)
3. Adversarial robustness testing (can AI systems evade detection?)

## Files

20 FVS entries (same layout as v1/v2) + INDEX.md. FVS-020 carries a
retirement banner in its Identification section; detector
implementations should exclude FVS-020 from emission while keeping
it in the library for vocabulary reference.
