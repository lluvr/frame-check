# Frame Check Source Network Calibration

**Purpose.** Measure per-provider precision/recall so Frame Check can
report calibrated confidence per claim, not opaque "this source said
verified" output. Without this discipline the UI's trust meter is
uncalibrated: a "verified" from Wikipedia and a "verified" from SEC
EDGAR have very different prior likelihoods of being correct, and the
user has no way to know.

This is the research-grade calibration work named in
`REFINEMENT_AUDIT.md:113-137` as the single most valuable next move
after construct honesty: "Source Network has zero validation against
an external corpus. clarethium_measure has the 171-test suite plus
the hard-topics corpus run. Source Network has neither."

## Contents

- `source_network_corpus.yaml`; seed test set. Per-provider claims
  with primary-source citations, expected verdicts, ground-truth
  rationale. Structured for machine-parseable harness runs.
- `run_calibration.py`; harness that loads the YAML, submits each
  claim through the live Source Network, compares observed verdict
  to expected, and emits a per-provider confusion matrix with
  precision, recall, and F1. A side-by-side stale-excluded view
  separates "ground truth has drifted" from "verifier genuinely
  missed".
- `results/`; dated output directories. Each run writes a human
  report (`REPORT.md`), the raw verdict JSON (`raw_verdicts.json`),
  and optionally a `FINDINGS.md` companion for operator-authored
  decomposition of non-matches.

## Relationship to other calibration artifacts

`source_network_corpus.yaml` (this directory) is a **precision/recall
test set**: claims designed to exercise each verifier on its own
boundary (positive cases, negative cases, out-of-coverage cases). It
is read by `run_calibration.py` and produces numbers.

Both exist. Neither replaces the other.

## Methodology

For each provider, the corpus seeds three categories:

1. **KNOWN_TRUE.** Claim text matches a primary source within the
   provider's tight-match band. Expected verdict: `verified`.
2. **KNOWN_FALSE.** Claim text differs from the primary source by a
   margin the provider's thresholds should catch. Expected verdict:
   `contradicted`.
3. **OUT_OF_COVERAGE.** Claim is true but the provider has no data
   for it (wrong country for World Bank, private company for SEC,
   etc.). Expected verdict: `unverifiable`.

Edge cases (`SCALE_EDGE`, `TEMPORAL_EDGE`, `ROUTING_TEST`) sit outside
the three-category grid and are used to probe specific failure modes.
They do not count toward the primary precision/recall numbers, only
toward a separate "edge-case survival" report.

Every claim cites a primary source URL and an as-of-date. Ground
truth can be independently re-derived by any reader.

## Current coverage

This is a **seed corpus**. Initial seed covers the strict-API
providers (SEC EDGAR, FRED, REST Countries) where primary-source
verification is unambiguous. Providers with ambiguous ground-truth
(Wikipedia, Brave Search) or high volatility (CoinGecko) are queued
for subsequent passes with category-specific methodology.

Provider status:

| Provider | Seed claims | Status |
|---|---|---|
| SEC EDGAR | see YAML | seeded |
| FRED | see YAML | seeded |
| REST Countries | see YAML | seeded |
| World Bank | see YAML | seeded |
| Alpha Vantage | see YAML | seeded |
| Wolfram Alpha | see YAML | seeded |
| Wikipedia | 0 | queued (high ambiguity; methodology TBD) |
| CoinGecko | 0 | queued (high volatility; as-of-date protocol TBD) |
| Brave Search | 0 | queued (fallback only; tested via cross-provider cases) |

## How to extend

Every new claim needs:

- A stable `id` (`provider-NNN`).
- `claim` text: a single sentence as a user would paste.
- `primary_source` and `primary_source_url`: how the ground truth is
  established.
- `as_of_date`: when the primary source was consulted.
- `primary_verifier`: the provider this claim targets.
- `category`: one of `KNOWN_TRUE`, `KNOWN_FALSE`, `OUT_OF_COVERAGE`,
  `SCALE_EDGE`, `TEMPORAL_EDGE`, `ROUTING_TEST`.
- `expected_verdict`: one of `verified`, `close`, `contradicted`,
  `disputed`, `unverifiable`.
- `rationale`: one-sentence explanation that would convince a
  reviewer the ground truth is correct.

Open a PR with the new claim. The harness will pick it up on the
next run.

## Run history

- **2026-04-16 first run**; seeded baseline. 27 claims across 6
  providers. Three providers (FRED, Alpha Vantage, Wolfram Alpha)
  ran their key-missing code path and did not produce calibrated
  numbers. Surfaced three real bugs and one seed-expectation error;
  see `results/2026-04-16-first-run/FINDINGS.md` for the
  decomposition. Two of the four surfaced issues landed fixes in
  the same commit cycle (World Bank GDP-per-capita routing; bare
  single-digit scale-word extraction); the remaining two (SEC
  quarterly disambiguation, SEC country-subject false positive)
  are queued as product-behavior changes with their own regression
  coverage.

  **Next run should produce different F1 numbers** from this
  baseline because of the landed fixes. The FINDINGS companion
  explicitly names which claims should move from FAIL to PASS on
  re-run. Running with `FRED_API_KEY`, `ALPHA_VANTAGE_API_KEY`,
  and `WOLFRAM_APP_ID` set in the environment replaces the
  absent-key rows with calibrated numbers.
