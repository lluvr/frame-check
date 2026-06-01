# First-run findings: what the calibration data revealed

**Run:** 2026-04-16 (commit `a1914d9`).
**Corpus:** 27 seed claims, 6 providers.
**Companion:** `REPORT.md` carries the confusion matrix; this document
is the structured read of WHY the matrix looks the way it does.

The raw F1 numbers in the report table are the literal truth about
what happened when the harness ran, but taken alone they would
misrepresent the product's reliability. This file decomposes every
non-match into one of five categories so the next run is measurable
against cleaner signal and the real bugs are separated from
confounders.

---

## Category A: Absent-key artifacts (6 items)

The dev machine that ran this calibration had only `GEMINI_API_KEY`
set. The verifiers that require their own API key ran their
key-missing code path and returned `unverifiable` for every claim
they would otherwise have handled.

| Claim | Provider | Expected | Observed |
|---|---|---|---|
| fred-001 | FRED | verified | unverifiable (no key) |
| fred-003 | FRED | contradicted | unverifiable (no key) |
| fred-005 | FRED | verified | unverifiable (no key) |
| av-001 | Alpha Vantage | verified | unverifiable (no key) |
| av-002 | Alpha Vantage | contradicted | unverifiable (no key) |
| wa-002 | Wolfram Alpha | verified | unverifiable (no key) |
| wa-003 | Wolfram Alpha | contradicted | unverifiable (no key) |

**Status:** Not a verifier finding. The "F1" rows for FRED, Alpha
Vantage, and Wolfram Alpha in `REPORT.md` reflect this code path,
not calibrated reliability. Re-run with all three keys in the
environment to produce nominal rows for these providers.

---

## Category B: Real routing and filter bugs (3 items)

These are genuine findings: the verifiers behaved correctly for
their intended inputs but the routing or filtering logic delivered
the wrong inputs.

### B.1 SEC EDGAR quarterly-filter bypass; `sec-005`

**Claim:** "Tesla reported Q4 2023 revenue of $25.167 billion."
**Observed:** SEC returned `$96,773,000,000`; Tesla's ANNUAL FY23
revenue, not Q4. Verdict: `contradicted` (diff 284.5%).

**Root cause:** `source_network.py:666-672` (`_TIME_RE`). The regex
captures literal `Q[1-4]` tokens but no spelled-out equivalents and
no year-disambiguated combinations in all formats. When the
claim's `time_period` doesn't capture a quarter, the SEC filter
falls through to 10-K annual filings at `source_network.py:2189-2192`
rather than the intended 10-Q quarterly filter at `:2181`.

**Impact (first run):** Every quarterly revenue claim phrased
with "Q4" followed by a year in certain shapes fell into this
bucket and got matched against annual revenue numbers. Users
pasted "Tesla reported Q4 2023 revenue of $25.2B" and received
a `contradicted` verdict from SEC because the annual figure
didn't match. False negative on a correct claim.

**Deeper root cause surfaced during the fix:** even with the
regex broadened, the SEC filter FELL BACK from 10-Q to 10-K
when no quarterly data existed (US-listed companies typically
don't file 10-Q for Q4; Q4 is rolled into the 10-K). That
fallback silently used annual data as a contradiction target
against a claim that was specifically about a quarter. That
is false authority. Honest "no_data" beats confident wrong.

**Fix landed:** New module `time_context.py` with
`classify_time(sentence, time_period_hint) -> TimeContext(
period_type, period_value, year, quarter, year_range, reason)`.
Parallel structural move to the entity classifier. Priority
order: quarterly (Q-notation, spelled-out), range, annual
(FY/bare/month), current-markers, historical (year older than
`HISTORICAL_CUTOFF_YEARS` from `reference_year`), fallback
UNKNOWN. 35 tests lock in priority order and reason-slug
contract stability.

The router attaches the classification to `ClaimDecomposition`
(five new fields: `time_period_type`, `time_year`, `time_quarter`,
`time_year_range`, `time_classification_reason`). Two verifiers
consume them:

- **SEC EDGAR quarterly guard** (`source_network.verify_sec_edgar`):
  when `time_period_type == "quarterly"`, filter 10-Q only. Do
  NOT fall back to 10-K. If no 10-Q data exists, return no_data
  from that concept. This is the specific fix for Bug B.1.

- **REST Countries historical guard** (`verify_rest_countries`):
  when `time_period_type == "historical"`, short-circuit to
  no_data without hitting the API. REST Countries is
  current-only, so matching current population against a
  historical claim produces coincidental verifications that
  look real but aren't (e.g. Japan 2010 ≈ Japan 2026 is close
  by coincidence only).

**Regression coverage:** 11 integration tests in
`test_routing_by_time_context.py` verifying the decomposition
fields populate correctly for each time shape, the SEC filter
sees the right flags for quarterly vs annual claims, and the
REST Countries historical short-circuit returns no_data
without a network call.

**Corpus telemetry:** `verification.by_time_context` histogram
now in Tier A `analysis_completed` event schema with fixed keys
`{annual, quarterly, range, current, historical, unknown}`.
Parallel to `verification.by_entity_type`. Enables corpus queries
like "what is Source Network's F1 on QUARTERLY claims vs
HISTORICAL claims?"; per-time-scope calibration the corpus
previously could not answer.

### B.2 World Bank GDP-per-capita collapse; `wb-002`

**Claim:** "Germany's GDP per capita was $50,000 in 2022."
**Observed:** WB returned Germany TOTAL GDP ~$4.2T.

**Root cause:** `source_network.py:1549-1566` in `_detect_wb_indicator`.
The function checks `"gdp" in sentence` (line 1552) BEFORE checking
`"per capita" in sentence` (line 1554), and each check returns
independently. A sentence containing "GDP per capita" matches "gdp"
first and returns `NY.GDP.MKTP.CD` (total GDP) without ever
reaching the per-capita branch that would have routed to
`NY.GDP.PCAP.CD`.

**Impact:** Every per-capita claim is verified against the total
GDP indicator. The numeric diff (~$50K vs ~$4.2T) is so large that
the verdict comes back `no_data`, which cascades to `unverifiable`.
The user sees "unverifiable" on a claim the World Bank genuinely
has data for.

**Scope:** Reorder the two checks OR convert the if-chain to elif
so the more specific branch runs first. Two-line fix. Safe.

### B.3 SEC EDGAR false positive on country subjects; FIXED via entity classifier

**Claim:** "US national debt exceeded $34 trillion in January 2024."
**Observed (first run):** SEC returned `$243,169,142`; a tiny number
from some US-related filing. Verdict: `contradicted`.

**Root cause:** `source_network.py:352-442` (subject extraction) plus
`:2561-2563` (has_company routing gate). The extractor at line
434-442 maps "US" → `_COUNTRY_CANONICAL["US"]` → "United States".
The routing then applies the permissive regex
`\b[A-Z][A-Za-z]+\b` to check for company-like capitalization
(`:2561-2563`); "United" satisfies it. Combined with a financial
keyword ("debt") and a large currency value, the claim is routed
to `verify_sec_edgar`. `_find_cik` then returns `None` for "United
States" but the downstream query still hits SEC's fulltext search
and returns an arbitrary matching number.

**Impact:** Country macroeconomic claims containing "US" or "United
States" got cross-matched against unrelated SEC filings, producing
spurious `contradicted` or `disputed` verdicts. Broke the consensus
mechanism: when Wikipedia matched correctly and SEC falsely
contradicted, the result was `disputed` even though the user claim
was true.

**Fix landed:** New module `entity_classifier.py` with
`classify_subject(subject) -> Classification(entity_type, canonical,
reason)`. Priority order (most specific first): crypto, country,
company (via SEC CIK resolution), else UNKNOWN. The router in
`source_network._classify_and_route` consults the classifier once
at the top, attaches `entity_type` to `ClaimDecomposition`, and
GATES the SEC EDGAR and Alpha Vantage branches on
`entity_type not in {COUNTRY, CRYPTO_ASSET}`. Country and crypto
subjects can never reach company-financial verifiers regardless of
capitalization or financial keywords, by construction. The direct
`_find_cik` gate approach originally scoped here is superseded by
the classifier because the structural fix prevents the same class
of bug in every future verifier added to the router.

**Regression coverage:** 46 tests across
`test_entity_classifier.py` (21) and `test_routing_by_entity_type.py`
(15 passing + 1 FRED-key-gated skip + 2 asymmetry tests), plus 9
multi-word country tests (North Korea, South Korea, Cote d'Ivoire,
Dominican Republic, Guinea-Bissau, United Arab Emirates) that the
initial classifier version missed and were fixed in the same
commit cycle.

**Corpus telemetry:** `verification.by_entity_type` histogram now
in Tier A `analysis_completed` event schema with fixed keys
`{company, country, crypto_asset, unknown}`. Enables per-entity-type
calibration queries against the corpus NDJSON ("what is Source
Network's F1 on COUNTRY claims vs COMPANY claims?"); a question
the corpus previously could not answer.

---

## Category C: Claim-extraction failure on spelled-out scales (2 items); FIXED

**Claims:** `rc-005` and `wa-004`, both "Wakanda has a population of
6 million."
**Observed (first run):** `no_claim_extracted`; `analyze_claims`
returned zero numerical claims from the sentence.

**Root cause:** Not `NUMERICAL_PATTERNS` in `clarethium_measure.py`
(which `extract_numerical_claims` uses) but the companion
`extract_numbers_for_matching`: the bare-integer pattern at
`clarethium_measure.py:566` required 2-6 digits, so "6" alone was
not captured. No pattern in either extractor handled the
digit+spelled-scale shape outside a currency context.

**Why "500 million" extracted but "6 million" did not** (a puzzle
the first-run data surfaced): the multi-digit bare integer "500"
was caught by the `integer` pattern and promoted to a synthetic
claim via `analyze_claims`'s uncovered-number path; "6" fell
below the 2-digit minimum and was never extracted.

**Fix landed:** New `scaled_integer` pattern in
`extract_numbers_for_matching` that captures
`\d+(\.\d+)?\s+(thousand|million|billion|trillion)` with a
multiplier applied so "6 million" becomes value `6000000` (not
bare `6`). Placed ahead of the bare-integer pattern so the
existing `claimed_ranges` overlap-prevention blocks the digit
half from re-matching, avoiding duplicate claims. Regression
tests in `test_numerical_extraction.py` cover: the spelled-out
scale shape for all four multipliers, decimal-prefixed scales,
mid-number digit sequences ("166 million" extracts as
166_000_000, not as "66 million"), the existing dollar pattern
still winning for currency-prefixed claims (`$60.9 billion`
extracts once as dollar, not twice), and false-positive
resistance ("millions of readers", "A million years ago",
"millennium", "millionaire" all correctly produce no
scaled_integer match).

**Round-trip validation:** The calibration corpus Wakanda claims
(`rc-005`, `wa-004`) were reverted from the digit-grouped
workaround `6,000,000` back to the natural `6 million`. They
are now exercising the new pattern and will extract correctly
on the next run.

**Impact resolved:** Documents using natural spelled-out scales
(populations, distances, counts) now produce extractable claims,
a verification attempt, and a populated trust meter. The silent
breakage class is closed.

**What the pattern still does NOT cover** (out of scope for this
fix, queued for a separate phase): spelled-out numerals like
"three million" or "one billion", hyphenated compounds
("six-million-strong"), range forms with scale words
("between 5 and 10 million"). These are tracked as a known
limitation rather than a regression.

---

## Category D: Seed corpus expectation wrong (1 item)

### D.1 India historical population; `rc-004`

**Claim:** "India had a population of 1.2 billion in 2010."
**Expected:** `contradicted` (reasoning: REST Countries returns
current data ~1.44B, so a 2010 claim against current data should
contradict).
**Observed:** `verified`. Wikipedia matched `1,210,193,422` (0.8%
diff) because the historical 2010 figure is IN the article.

**Status:** The verifier behaved correctly. The seed expectation
was wrong. My assumption that the temporal blindspot would drive
REST Countries to contradict did not account for Wikipedia having
historical data on the same claim. Wikipedia's article on India
includes census data by year, and the 2010 figure was returned
directly.

**Corpus correction:** Update `rc-004` expected verdict to
`verified`, rewrite the rationale to acknowledge that Wikipedia's
historical coverage can correctly answer historical claims that
REST Countries alone cannot. A separate TEMPORAL_EDGE test should
use a claim that is specifically NOT in Wikipedia historical
coverage.

---

## Category E: Stale ground-truth (11 items)

11 of 27 claims have `as_of_date` older than 90 days. The harness
flags them in `REPORT.md § Stale` but still runs them; their
verdicts contribute to the F1 numbers alongside the fresh claims.
Re-verifying each against its primary source before the next run
would sharpen the signal; until then, stale claims should be
excluded when computing a clean per-provider reliability number.

**Follow-up (shipped in this same commit cycle):** the harness now
computes an additional `F1 (stale-excluded)` column per provider
so the two views are visible side by side.

---

## What this means for the product's public reliability claim

The `METHODOLOGY.md §7.2` claim that per-provider reliability tiers
will surface in the UI "once the first measurement run lands"
needs one more qualifier. The first run has landed. The numbers
are not yet clean enough to publish per-provider tiers without
qualifiers:

- Three providers (FRED, Alpha Vantage, Wolfram Alpha) ran a
  key-missing path and have no calibrated reliability yet.
- Three real verifier/routing bugs are known (B.1-B.3). Running
  the corpus against the unfixed code measures those bugs, not
  provider reliability.
- The corpus itself has one seed error (D.1) and a
  claim-extraction failure that masks coverage (Category C).

**Honest position until the next run:** the methodology paper
and the calibration directory name the discipline; the UI does
NOT yet ship per-provider badges. The "first run" published here
is the baseline that exposes what has to be fixed before a
calibration-driven tier can be shown to a reader in good faith.

The next run, after the fixes in this commit cycle land and the
seed corpus is refreshed, should be the one whose numbers go into
the UI.

---

## Summary of action items produced by this document

| # | Item | Scope | Where |
|---|---|---|---|
| 1 | Fix `rc-004` expected verdict | corpus edit | landed |
| 2 | Rewrite `rc-005` / `wa-004` (initially to digit-grouped, then restored to natural spelled-out form after item 6 landed) | corpus edit | landed |
| 3 | Reorder `_detect_wb_indicator` per-capita/total GDP branches | 2-line fix + 9 tests | landed |
| 4 | SEC quarterly disambiguation | **superseded by time_context classifier, landed** (see B.1) |
| 5 | Gate SEC routing away from country/crypto subjects | **superseded by entity classifier, landed** (see B.3) |
| 6 | Add spelled-out scale words to number extraction (`scaled_integer` pattern in `extract_numbers_for_matching`) | 1 pattern + multiplier + 16 tests | landed |
| 7 | Re-run calibration with all API keys set | builder action | queued |
| 8 | Refresh 11 stale corpus entries | manual review | queued |
| 9 | Add `verification.by_entity_type` to Tier A event schema | schema addition + 2 tests | landed (alongside classifier) |
| 10 | Extend country regex to include multi-word forms (`North Korea`, `South Korea`, `Cote d'Ivoire`, `Dominican Republic`) | regex + 9 tests | landed (post-classifier audit) |
| 11 | TimeContext classifier + SEC quarterly guard + REST Countries historical guard | new module + integration + 46 tests | landed |
| 12 | Add `verification.by_time_context` to Tier A event schema | schema addition + 2 tests | landed (alongside time classifier) |

Items 1–3, 5, 6, 9–12 have landed. Items 7 and 8 remain queued
as actions that consume API budget or manual
verification time.
