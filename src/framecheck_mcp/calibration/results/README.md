# Calibration run results

Each subdirectory is a single run of `run_calibration.py`, named by
its UTC date. When a run completes it writes:

- `raw_verdicts.json`: one record per claim, with full verifier detail.
- `REPORT.md`: human-readable per-provider confusion matrix with
  precision, recall, and F1.

The seed corpus at `calibration/source_network_corpus.yaml` contains
27 claims across 6 providers (SEC EDGAR, FRED, REST Countries, World
Bank, Alpha Vantage, Wolfram Alpha). Three providers remain queued
for calibration methodology (Wikipedia, CoinGecko, Brave Search)
because their ground-truth characteristics require category-specific
handling before calibration is meaningful.

## First committed run: 2026-04-16

`2026-04-16-first-run/` is the first baseline. It covers all six
seed-corpus providers. The run was executed with only `GEMINI_API_KEY`
set in the environment; `FRED_API_KEY`, `ALPHA_VANTAGE_API_KEY`, and
`WOLFRAM_APP_ID` were absent, so those verifiers exercised their
key-missing code path rather than their nominal verified vs
contradicted path. That is intentionally committed: the honest
record of what happens in the absence of a key is itself calibration
signal, and re-running with full keys produces a second baseline to
compare against. See `REPORT.md` for per-provider numbers.

**Keyed providers (nominal code path):**
- SEC EDGAR: precision 1.00, recall 0.67, F1 0.80
- REST Countries: precision 0.67, recall 1.00, F1 0.80
- World Bank: precision 1.00, recall 0.50, F1 0.67

**Key-missing providers (not yet calibrated):**
- FRED, Alpha Vantage, Wolfram Alpha: F1 values reflect the
  absent-key code path, not calibrated reliability.

Re-run with all keys set in the environment to replace these rows
with calibrated numbers. The confusion matrix format does not
change between runs, so the followup diff is mechanical.

## Second committed run: 2026-04-17 (full keys)

`2026-04-17-full-keys/` is the second baseline. All 6 provider
API keys set. All 11 stale claims refreshed (0 stale). All session
fixes landed (EntityType classifier, TimeContext classifier, WB
per-capita routing, scaled-integer extraction, multi-word country
regex).

| Provider | F1 | Tier | vs first run |
|---|---|---|---|
| SEC EDGAR | 1.00 | strong | +0.20 (TimeContext fix) |
| REST Countries | 0.86 | strong | +0.06 |
| World Bank | 0.67 | moderate | unchanged (API timeouts) |
| Alpha Vantage | 0.67 | moderate | first calibrated |
| FRED | 0.50 | weak | first calibrated |
| Wolfram Alpha | 0.50 | weak | first calibrated |

SEC EDGAR's jump from 0.80 to 1.00 is the TimeContext quarterly
guard: Tesla Q4 2023 now verifies via cross-provider fallback
instead of falsely contradicting against annual data. That was
the headline fix of the session.

10 misses remain, categorized:
- 5 API timeouts/errors (WB, AV, Wolfram): infrastructure, not logic
- 2 Brave false positives on "Wakanda" (fictional entity verified via Reddit)
- 2 FRED cross-source disputes (CPIAUCSL index vs rate confusion)
- 1 FRED silent failure (no sources returned)

`reliability_tiers.json` is committed. The app loads the latest
tiers at startup and renders per-provider badges on SN
verification cards.

## Protocol on follow-up

If precision or recall for a provider is low (e.g. F1 < 0.6 on the
keyed code path), the remaining misses should be decomposed before
shipping the tier as authoritative. FRED (0.50) and Wolfram (0.50)
are "weak" in part due to API reliability, not just verifier logic;
a re-run on a day with clean API responses would produce a more
honest measurement. The "weak" tier badge is itself honest: it
means "we measured this and the result was below the strong/moderate
threshold." That is more informative than no badge at all.
