# Source Network Calibration Corpus: Expansion Survey

**Author:** Lovro Lucic (Frame Check)
**Survey date:** 2026-05-03
**Subject:** `calibration/source_network_corpus.yaml` v0.1 (seeded 2026-04-16)
**Latest measurement:** `calibration/results/2026-04-17-full-with-wiki/reliability_tiers.json`
**Status:** SURVEY (analysis output, not corpus content). Operator authors the candidate claims listed below; this document only names where coverage is thin and what kinds of claims would close the gap.

---

## Why this survey exists

The provenance manifest now shipping on every Frame Check result (manifest.py, merged 2026-05-03) surfaces per-provider F1 scores inline, with the corpus reference (`name`, `version=0.1`, `size=33`, `seeded_at=2026-04-16`) named alongside. A hostile reviewer landing on any saved analysis can trace the `F1 0.74 moderate` pill on a Wikipedia-verified claim back to this corpus in two clicks.

The 2027-citation-pattern stress test predicts the dominant critique on those numbers will be **n**:

> "Frame Check claims F1 0.86 on REST Countries, but the corpus has 5 claims for that provider. The 95% Wilson interval on F1=0.86 with n=5 is approximately [0.42, 0.99]. The number isn't wrong; it's just statistically uninformative."

This survey identifies which extensions to v0.1 would move that confidence interval most per claim added, given operator authoring time is the bottleneck (per `feedback_no_llm_drafting_substantive_content.md`: claims are operator-authored, never LLM-drafted).

---

## v0.1 baseline

**Total claims: 33** across 7 providers.

| Provider | Claims | F1 | Tier | Categories on disk |
|---|---|---|---|---|
| SEC EDGAR | 5 | 1.00 | strong | KNOWN_TRUE 3, KNOWN_FALSE 1, OUT_OF_COVERAGE 1 |
| FRED | 5 | 0.50 | weak | KNOWN_TRUE 3, KNOWN_FALSE 1, OUT_OF_COVERAGE 1 |
| REST Countries | 5 | 0.86 | strong | KNOWN_TRUE 2, KNOWN_FALSE 1, TEMPORAL_EDGE 1, OUT_OF_COVERAGE 1 |
| World Bank | 4 | 1.00 | strong | KNOWN_TRUE 2, KNOWN_FALSE 1, OUT_OF_COVERAGE 1 |
| Alpha Vantage | 4 | 0.67 | moderate | KNOWN_TRUE 2, KNOWN_FALSE 1, OUT_OF_COVERAGE 1 |
| Wolfram Alpha | 4 | 0.50 | weak | KNOWN_TRUE 2, KNOWN_FALSE 1, OUT_OF_COVERAGE 1 |
| Wikipedia | 6 | 0.89 | strong | KNOWN_TRUE 4, KNOWN_FALSE 2 |

**Date range:** all 33 claims have `as_of_date` in {`2026-04-16`, `2026-04-17`} (a 2-day window).

**Verdict distribution:** verified 17, contradicted 8, unverifiable 6, close 2.

---

## Five gaps the hostile reviewer would flag

### Gap 1: small per-provider n (load-bearing, weak providers most affected)

F1 is a ratio of two ratios (precision and recall), so a single closed-form CI does not exist; rigorous bounds typically come from bootstrap resampling over the (TP, FP, FN, TN) outcome counts. The basic problem is visible without resampling, though: at n=4-6 outcomes per provider, **either** precision or recall is being estimated from a handful of samples, and Wilson's standard 95% interval for a single proportion at n=4 with p=0.5 is roughly [0.15, 0.85], a band wider than the gap between every adjacent tier boundary (strong ≥ 0.8, moderate 0.6-0.8, weak < 0.6) that the reliability_tiers table assigns labels to.

The hostile reviewer reads "F1 0.50 weak" and says "you cannot distinguish a true 0.50 from a true 0.30 or 0.70 with this many samples; the tier label is doing analytical work the data cannot support." That critique lands whether the underlying CI is from Wilson on a component proportion or bootstrap on F1 itself. The question this survey answers is not "what is the precise CI on F1" but "how many additional claims close the smallest tier gap to within roughly one standard error".

Adding **5 claims per provider** roughly doubles n on the smallest providers and meaningfully narrows the precision/recall component intervals (Wilson at n=10 with p=0.5 is roughly [0.24, 0.76]). It does not turn the per-provider F1 into a research-grade measurement, but it does let the strong/moderate/weak tier label have a non-trivial probability of being the same label a 10x corpus would assign.

**Cost:** ~30 claims of operator authoring time. **Highest leverage of all five gaps** because it directly addresses what the manifest exposes inline. A proper bootstrap-based F1 CI calculation belongs in `calibration/run_calibration.py` itself; not in scope for this survey.

### Gap 2: single 2-day temporal window

Every claim in v0.1 dates to 2026-04-16 or 2026-04-17. Two consequences:

1. **Stale-claim refresh is untested.** The seed YAML's own comment says "the harness flags claims whose as_of_date exceeds 90 days". With every claim dated 2026-04-16, that gate fires on **all 33 claims simultaneously** at 2026-07-15. The harness has never been exercised against a partial-stale corpus where some claims need re-verification and some don't.

2. **API state at-time-of-call is uncontrolled.** A claim verified on 2026-04-17 against FRED's 2026-04-17 API state is a single sample from the joint distribution of (claim correctness × API state × network conditions). Spread across multiple dates, the sample becomes meaningfully independent.

**Cost:** No new claims required for Gap 2's first axis (just re-run on a future date). Second axis closes by adding ~5 claims with `as_of_date` spread across the past 6-12 months, anchored to data points known to be stable that long.

### Gap 3: TEMPORAL_EDGE category undersampled (n=1 across all providers)

REST Countries is the only provider with a `TEMPORAL_EDGE` claim. The category is meant to test claims-near-the-data-cutoff: "OpenAI revenue in Q3 2024" when the API only has Q2 2024 data, or "Botswana population in 2025" when the latest UN release is 2023. These are the claims most likely to produce silent unverifiable verdicts that look like coverage failures.

**Cost:** ~1-2 claims per provider, each anchored to a known data-cutoff edge for that source. SEC EDGAR's 10-K/10-Q lag, FRED's BLS release schedule, World Bank's annual rollup. Each claim should have an `as_of_date` within 30 days of the source's last-known-update for that data point.

### Gap 4: Wikipedia has no OUT_OF_COVERAGE claim

Every other provider tests the unverifiable verdict (the `unverifiable` row in the verdict distribution). Wikipedia does not. Wikipedia's coverage is broad enough that "no article exists" is rare, but the failure modes that produce unverifiable on Wikipedia are real:

- Disambiguation pages (search returns a list, not a fact)
- Numerical claims with no infobox row
- Claims-about-the-future (every "by 2030 the market will reach X" claim should hit unverifiable on Wikipedia)

**Cost:** ~2 claims. Adding these closes the matrix gap and, more importantly, lets the Wikipedia F1 number include a recall component on the unverifiable category instead of the current implicit-100%.

### Gap 5: Domain skew (corporate finance overweights)

By eyeball:

- Corporate finance: ~12 claims (SEC EDGAR, Alpha Vantage, FRED-equity)
- Country statistics: ~7 claims (REST Countries, World Bank)
- Macroeconomic time series: ~3 claims (FRED-macro)
- Science/computational: ~4 claims (Wolfram Alpha)
- Encyclopedic: ~6 claims (Wikipedia)
- Crypto: 0 claims (CoinGecko is in `_RELIABILITY_TIERS` source map but has no calibration entry)
- Health/medicine: 0 claims (no provider, but worked-examples include AI-on-life-decisions which would benefit)

Frame Check's worked-example corpus (six published as of 2026-05-03) skews heavily toward LLM-output checking: Bitcoin retirement, FOMC statements, AI manifestos. The calibration corpus does not need to mirror that exactly, but the **CoinGecko gap is concrete:** several worked examples touch crypto numbers that would route to CoinGecko, and the manifest currently shows that provider as "uncalibrated" with no F1.

**Cost:** ~5 claims for CoinGecko (Bitcoin/ETH market cap, ATH dates, supply schedules), ~3 health-ish claims testable via Wikipedia or REST Countries (life expectancy by country, vaccination coverage, etc.).

---

## Ranked recommendations

The five gaps are not equally important. Ranked by **(impact on manifest defensibility) ÷ (operator authoring hours)**:

| Rank | Gap | Claims to add | Why this rank |
|---|---|---|---|
| 1 | Gap 1 (per-provider n) | ~30 (5 per provider × 6 weak/moderate providers) | Directly attacks the dominant 2027-citation critique. Lowers the F1 confidence interval enough to make tier boundaries meaningful. |
| 2 | Gap 5a: CoinGecko coverage | ~5 | Closes the "uncalibrated" pill on a provider users actively hit (worked-examples include crypto). |
| 3 | Gap 4: Wikipedia OUT_OF_COVERAGE | ~2 | One missing category breaks the symmetric testing matrix. Cheap to close. |
| 4 | Gap 3: TEMPORAL_EDGE coverage | ~7 (1-2 per provider × 7) | The category exists in v0.1 schema; expanding it tests the data-cutoff failure mode that real LLM-output checking hits constantly. |
| 5 | Gap 2: temporal-window spread | ~5 (cross-provider, varied as_of_date) | Lowest-leverage on F1 numbers but closes the stale-claim-refresh untested-path. |

**Total to v1.0:** ~49 claims (approximately doubling the corpus from 33 to 80-85). Per-provider n moves from 4-6 to 9-12; weak-tier intervals tighten enough to defend the labels. Each addition is an independent unit so this can be done in increments rather than a single sprint.

---

## What this survey explicitly does NOT do

- **Does not draft candidate claims.** Per `feedback_no_llm_drafting_substantive_content.md`: taxonomy entries, calibration claims, and methodology are operator-authored. Bad/mediocre compounds negatively. This survey identifies categories and counts; the operator writes the claim text, names the primary source, and chooses the `expected_verdict` based on the source state at `as_of_date`.

- **Does not propose a schema change.** v0.1 schema (id / claim / primary_source / primary_source_url / as_of_date / primary_verifier / category / expected_verdict / rationale) is sufficient for all five gaps. No new fields needed.

- **Does not pre-judge the calibration outcome.** The intent is not to bring weak providers up to strong; it's to produce confidence intervals tight enough that whatever F1 each provider lands at, that number can be defended against the n=5 critique.

- **Does not propose retiring v0.1.** The 33 claims are good claims. v1.0 is v0.1 + additions, not a replacement.

---

## Operator next step (when ready)

For each ranked gap above, the operator's authoring template is the existing v0.1 entry shape:

```yaml
- id: <provider-prefix>-NNN
  claim: "<single-sentence claim with the numerical assertion>"
  primary_source: "<authoritative document or API endpoint>"
  primary_source_url: "<verifiable URL>"
  as_of_date: "<YYYY-MM-DD when the operator last verified the source state>"
  primary_verifier: <provider_key from _RELIABILITY_TIERS>
  category: <KNOWN_TRUE | KNOWN_FALSE | TEMPORAL_EDGE | OUT_OF_COVERAGE>
  expected_verdict: <verified | close | contradicted | unverifiable>
  rationale: "<why this expected_verdict, naming the threshold that should fire>"
```

Existing entries in `calibration/source_network_corpus.yaml` are the reference template. Run `python3 calibration/run_calibration.py` after each batch to update `reliability_tiers.json`; the manifest reads the latest result automatically.

---

*This survey is a measurement-defensibility document, not a corpus-content document. The corpus stays operator-authored; the survey just names where the operator's hours land highest leverage.*
