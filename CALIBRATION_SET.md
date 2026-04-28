# Source Network Calibration Set

**Purpose:** Measure the end-to-end accuracy of the claim extraction + verification pipeline. Each claim has a known ground truth, expected routing, and a specific construct question it answers.

**How to run:** Submit each claim as a single-sentence document through `/api/profile` (JSON API). Record the verdict, the sources queried, and the value the source network compared against. Compare against the ground truth column.

**What this measures:** The combined accuracy of: number extraction (NUMERICAL_PATTERNS), claim decomposition (decompose_claim), value normalization (normalize_value), source routing (_classify_and_route), per-source verification (verify_*), and consensus (_consensus).

---

## Section A: Format Sensitivity (same truth, different formats)

Tests whether the same claim produces the same verdict regardless of number formatting.
Ground truth: Apple FY2024 revenue was approximately $383 billion (SEC EDGAR).

| ID | Claim text | Expected verdict | Construct question |
|----|-----------|-----------------|-------------------|
| A1 | Apple reported revenue of $383 billion in fiscal 2024. | verified | Baseline: spelled-out scale word |
| A2 | Apple reported revenue of $383B in fiscal 2024. | verified | Single-char uppercase suffix |
| A3 | Apple reported revenue of $383bn in fiscal 2024. | verified | Lowercase "bn" abbreviation |
| A4 | Apple reported revenue of $383 bn in fiscal 2024. | verified | "bn" with space |
| A5 | Apple reported revenue of $383,000,000,000 in fiscal 2024. | verified | Fully expanded with commas |
| A6 | Apple's FY2024 revenue reached $383.0 billion. | verified | Decimal with trailing zero |

If any of A1-A6 produce different verdicts, the pipeline has a format sensitivity bug. Known risk: A3 and A4 may fail because "bn" alternation in NUMERICAL_PATTERNS is shadowed by case-insensitive "B" match.

## Section B: Scale/Unit Ambiguity

Tests whether scale suffixes and unit context are handled correctly.

| ID | Claim text | Ground truth | Expected verdict | Construct question |
|----|-----------|-------------|-----------------|-------------------|
| B1 | NVIDIA reported revenue of $60.9 billion in fiscal 2024. | ~$60.9B (SEC) | verified | Standard billion claim |
| B2 | Tesla's annual revenue reached $97 billion in 2024. | ~$97B (SEC) | verified or close | Close but imprecise |
| B3 | The US national debt exceeds $34 trillion. | ~$34T (FRED GFDEBTN) | verified or close | Trillion scale (rare in NUMERICAL_PATTERNS) |
| B4 | France's GDP was $3.05 trillion in 2023. | ~$3.0T (World Bank) | verified or close | Non-US, trillion |
| B5 | Bitcoin's market cap is approximately $1.2 trillion. | varies (CoinGecko) | close or contradicted | Crypto spot price volatility |

## Section C: Temporal Alignment

Tests whether the source network detects or mishandles temporal mismatches.

| ID | Claim text | Ground truth | Expected verdict | Construct question |
|----|-----------|-------------|-----------------|-------------------|
| C1 | US unemployment was 3.7% in 2023. | 3.6% (FRED UNRATE, Dec 2023) | close | Current year, small diff |
| C2 | US unemployment was 10.0% in 2020. | 14.7% peak, ~6.7% Dec 2020 (FRED) | contradicted | Historical year: does FRED return 2020 data or current? |
| C3 | France's GDP was $2.6 trillion in 2018. | ~$2.8T (World Bank 2018) | close | 6-year-old claim: does World Bank return 2018 or recent? |
| C4 | India's population was 1.2 billion in 2010. | ~1.23B (REST Countries returns CURRENT ~1.44B) | contradicted | REST Countries has no temporal data: 2010 claim vs 2024 data |

If C2 and C3 produce "verified" or "close" against CURRENT data (not the claimed year), the temporal alignment gap is confirmed.

## Section D: Routing Accuracy

Tests whether claims reach the right sources.

| ID | Claim text | Expected sources | Construct question |
|----|-----------|-----------------|-------------------|
| D1 | Apple's quarterly revenue was $124.3 billion. | SEC EDGAR, Alpha Vantage, Wikipedia | Financial claim: does unit="currency" route to SEC? |
| D2 | Mount Everest is 8,849 meters tall. | Wolfram Alpha, Wikipedia | Physical fact routing |
| D3 | Germany's population is 84 million. | REST Countries, World Bank, Wikipedia | Country statistic routing |
| D4 | The federal funds rate is 5.33%. | FRED, Wikipedia | US macro routing |
| D5 | Ethereum's price is approximately $3,400. | CoinGecko, Wikipedia | Crypto routing |

If D1 does not route to SEC EDGAR, the unit mismatch bug (unit="currency" vs check for "USD") is confirmed in practice.

## Section E: Known Bug Validation

Claims specifically designed to trigger the 3 confirmed bugs.

| ID | Claim text | Bug tested | Expected behavior (current) | Expected behavior (fixed) |
|----|-----------|-----------|---------------------------|--------------------------|
| E1 | US inflation was 3.4% in 2023. | FRED CPIAUCSL maps to CPI index, not rate | FRED returns ~307 (index), diff=8900%, "no_data" or "contradicted". World Bank returns ~3.4% (rate), "close". Consensus: "disputed" (close + contradicted). | FRED returns annual CPI change ~3.4%, "exact". Both sources agree. Consensus: "verified". |
| E2 | Apple reported $124 billion in quarterly revenue. | Unit mismatch: unit="currency", SEC checks "USD" | SEC routes via keyword "revenue" (not via unit check). Verify: does SEC actually receive this claim? | Unit check also triggers: unit="currency" matches. |
| E3 | World Bank says France GDP was $3 trillion. Wikipedia says $2.8 trillion. | Dead consensus code: exact + contradicted unreachable | If WB returns exact and Wiki returns contradicted, verdict is "verified" (exact wins, contradicted silenced). The "disputed" path at lines 2144-2148 never executes. | Verdict: "disputed" with explanation that sources disagree. |

## Section F: Edge Cases

| ID | Claim text | Ground truth | Expected verdict | Construct question |
|----|-----------|-------------|-----------------|-------------------|
| F1 | The company's gross profit margin was 45.2%. | Depends on company | unverifiable | No subject: does the SN handle missing entities gracefully? |
| F2 | Revenue grew 126% year over year. | NVIDIA FY2024 | unverifiable or verified | Derived claim: does the derivation checker catch this? |
| F3 | Approximately 80% of the AI accelerator market. | No authoritative source | unverifiable | Market share: no structured API has this data |
| F4 | The regulatory framework will reduce investment by 8-15%. | Future projection | projection | Prediction: does the SN correctly classify projections? |

---

## Scoring

For each claim, record:
- **Extraction**: Did claim_analysis extract the right number? (Y/N, actual value)
- **Normalization**: Did normalize_value produce the correct numeric value? (Y/N, actual vs expected)
- **Routing**: Which sources were selected? (list)
- **Verdict**: What verdict was produced? (verified/close/contradicted/disputed/unverifiable)
- **Correct**: Is the verdict defensible given the ground truth? (Y/N)
- **Sources queried but returned no_data**: (list, for transparency gap analysis)

Aggregate metrics:
- **Precision**: Of claims marked "verified," what fraction are actually correct?
- **False-verified rate**: Of claims marked "verified," what fraction are wrong?
- **False-unverifiable rate**: Of claims that SHOULD be verifiable (ground truth exists), what fraction got "unverifiable"?
- **Format consistency**: Do A1-A6 all produce the same verdict?
- **Temporal accuracy**: Do C1-C4 compare against the correct year's data?

## What the results tell you

- If **format consistency fails**: extraction/normalization is the bottleneck. Fix parsing before fixing verification.
- If **temporal accuracy fails**: verification logic is the bottleneck. Add temporal alignment checking.
- If **false-unverifiable rate is high**: routing or decomposition is the bottleneck. Claims are not reaching the right sources.
- If **false-verified rate is high**: consensus logic is the bottleneck. Exact matches from noisy sources are overriding contradictions.
- If **precision is high and false-unverifiable is high**: the system is conservative (when it verifies, it is right, but it fails to verify things it should). The transparency gap matters most here.
