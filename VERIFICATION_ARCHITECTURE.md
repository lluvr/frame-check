# FrameCheck Verification Architecture

The current verification system outsources judgment to Gemini. We send a claim, Gemini searches the web, Gemini decides if the claim is true. We are a wrapper around an LLM grounding call.

The architecture described here replaces that with multi-source primary verification with framing-aware synthesis.

## The Core Insight

FrameCheck does not ask an AI if another AI is telling the truth. It goes to the source.

"Here is the SEC filing. Here is what it says. Here is what the AI told you. They do not match. And the framing analysis shows you WHY you could not tell: because the AI wrote the verified facts and the fabricated numbers in the exact same voice, with the exact same confidence."

The synthesis of framing analysis + primary-source verification reveals the MECHANISM of AI deception, not just its presence.

---

## Architecture: Cascading Tiers + 5-Step Mechanism

Two systems unified: the existing multi-stage pipeline (user source, Gemini, xAI) and the new Source Network (decompose, route, match, derive, synthesize). Each tier is a verification layer. Each claim cascades through tiers until resolved or exhausted. The 5-step mechanism runs within the Source Network tier and enhances every tier below it with better claim context.

### The Complete Flow

```
TIER 0: USER SOURCE (existing, free, strongest signal)
  0a. Exact match against user-provided source text
  0b. Fuzzy match (7 types: precision, range, approx, rounded, midpoint...)
  -> Claims exit if matched. Ground truth from user.

TIER 1: SOURCE NETWORK (new, free, deterministic)
  Step 1. DECOMPOSE claim (subject, metric, value, time period, type)
  Step 2. ROUTE to 2-3 authoritative APIs in parallel
  Step 3. CONTEXT-AWARE MATCH (value + metric + temporal + entity)
  Step 4. DERIVATION CHECK (recompute growth rates from source base values)
  -> Claims exit with primary source citations.

TIER 2: WEB SEARCH (new, free/cheap, we own it)
  - Brave Search (free 2K/mo)
  - Our code extracts numbers from snippets
  - Context-aware matching on results
  -> Claims exit with web citations (not authoritative but evidence).

TIER 3: LLM GROUNDING (existing Stage 2, repositioned)
  - Gemini with google_search tool ($0.014/claim)
  - Better context from Tier 1 decomposition
  - For claims that resisted all deterministic verification
  -> Safety net, not engine.

TIER 4: CROSS-MODEL (existing Stage 3, last resort)
  - Grok parametric memory (~$0.001/claim)
  - Weak signal, final check before UNVERIFIABLE

TIER 5: SYNTHESIS (runs on ALL claims)
  Step 5. Connect verification results to framing profile
  - Which claims are grounded? Which are fabricated?
  - How does the frame hide the difference?
  - The portrait output.
```

**Cascading rule:** Claims exit the pipeline at the first tier that produces a definitive verdict. Tiers are ordered by trust (user source > primary API > web > LLM > parametric memory) and cost (free > free > free > $0.014 > $0.001). Most claims resolve at Tier 0-1 for $0. Only the hardest claims reach Tier 3.

**What each tier catches that the previous cannot:**
- Tier 0 catches claims grounded in the user's own source material
- Tier 1 catches claims verifiable against authoritative databases
- Tier 1 Step 4 catches fabricated DERIVATIONS from real numbers (the growth rate lie)
- Tier 2 catches claims that appear on the web but not in structured databases
- Tier 3 catches claims that require reading and interpreting web pages
- Tier 4 catches claims that exist in model training data but not on the current web
- Tier 5 catches the META-PATTERN: how the frame obscures which claims are real

### The 5-Step Mechanism (operates within Tier 1, enhances Tiers 2-4)

```
1. DECOMPOSE   What exactly is being claimed?
                (subject, metric, value, time period, type)

2. ROUTE        Where does the authoritative answer live?
                (Source Router -> 2-3 APIs in parallel)

3. MATCH        Does the source confirm the specific claim?
                (value + metric + temporal + entity context)

4. DERIVE       Are computed claims mathematically valid?
                (recompute growth rates, ratios from source base values)

5. SYNTHESIZE   What does this mean for the reader?
                (connect verification to framing profile)
```

Step 1 (decomposition) enhances ALL downstream tiers: Tier 2 gets better search queries, Tier 3 gets better Gemini prompts, Tier 4 gets better Grok questions. The mechanism is not isolated to Tier 1.

**Example of what Step 4 catches that Steps 1-3 miss:**

Claim: "Apple revenue grew 24.3% year-over-year"
- Step 1 decomposes: subject=Apple, metric=revenue growth, value=24.3%, type=DERIVED
- Step 2 routes to: Wikipedia + Alpha Vantage
- Step 3 finds: FY2023 revenue $383.3B, FY2022 revenue $394.3B. Both confirmed.
- Step 4 recomputes: (383.3 - 394.3) / 394.3 = **-2.8%** (decline, not growth)
- Step 5 synthesizes: "The base revenue ($383B) is correct. The growth claim is fabricated. Actual change was -2.8%. The document frames a revenue decline as growth."

Steps 1-3 would say "revenue number confirmed." Step 4 catches the lie.

---

### Step 1: Claim Decomposition

A claim is not a number. "Apple revenue was $383 billion in fiscal 2023" is an assertion about a subject, a metric, a time period, and a value.

**Decomposition output:**
```
{
    subject: "Apple Inc.",
    metric: "revenue",
    metric_type: "absolute",    // vs "growth_rate", "ratio", "count"
    value: 383000000000,
    unit: "USD",
    time_period: "fiscal 2023",
    claim_type: "direct",       // vs "derived", "projection"
    qualifier: "stated_as_fact"  // from claim_analysis
}
```

**For derived claims:**
```
{
    subject: "Apple Inc.",
    metric: "revenue growth",
    metric_type: "growth_rate",
    value: 0.243,
    claim_type: "derived",
    base_metric: "revenue",
    comparison_type: "year-over-year",
    requires: ["current_revenue", "prior_year_revenue"]
}
```

**Implementation:** Regex patterns extending claim_analysis.py.
- Subject: from heading (Layer 0 enrichment) or proper nouns in sentence
- Metric type: keyword detection ("revenue", "profit", "population", "height", "price")
- Time period: year/quarter patterns already detected by TEMPORAL_RE
- Claim type: "grew X%", "increased by", "declined to" = derived. Raw number = direct.
- Unit: dollar signs, %, "million", "billion", "metres", "kg"

### Step 1b: Unit Normalization

Claims use human-readable units. APIs return raw numbers.

```
"$27.4 trillion" -> 27,400,000,000,000
"$383B"          -> 383,000,000,000
"68 million"     -> 68,000,000
"24.3%"          -> 0.243
```

Each source parser declares its unit context. The normalizer handles the claim side. Matching operates on base-unit floats.

### Step 1c: Claim Context Enrichment

**The prerequisite for everything.** The Hyperion tree failure was not a search failure. It was a context failure. The claim sentence was "California, USA. It measures 116.07-116.22 m" with no subject.

**Subject extraction fallback chain:**
1. Section heading (best). "## Giant Pacific Octopus (Enteroctopus dofleini)"
2. Proper nouns in the claim sentence. Regex: consecutive capitalized words.
3. Proper nouns in the previous sentence. For coreference ("It measures...").
4. User-provided topic from the input form.
5. No subject found. Skip structured verification, fall through to web search.

### Step 2: Source Routing (the Source Network)

#### Tier 1 Sources (build first, all tested and working, no API keys)

| # | Source | Domain | API | Status | Key? |
|---|---|---|---|---|---|
| 1 | **Wikipedia** | Entity facts, measurements, dates, counts, company data, everything | `en.wikipedia.org/w/api.php` | TESTED: returns article text with matchable numbers | No |
| 2 | **World Bank** | GDP, economic indicators, development data, 16K+ series, all countries | `api.worldbank.org/v2` | TESTED: returns exact GDP values | No |
| 3 | **REST Countries** | Country population, area, capitals, currencies, ISO codes | `restcountries.com/v3.1` | TESTED: returns population + area (NOT GDP) | No |
| 4 | **CoinGecko** | Crypto prices, market caps, volumes, historical data | `api.coingecko.com/api/v3` | TESTED: returns exact BTC price + market cap | No |

**What Tier 1 covers:** Entity facts (Wikipedia), country data (REST Countries + World Bank), economic indicators (World Bank), crypto (CoinGecko). Wikipedia alone covers 30-40% of claims. All four together: estimated 50-60%.

**What Tier 1 cannot cover:** Company financials (revenue, earnings), US-specific macro detail (CPI components, unemployment by state), computational facts, health statistics, and anything not in a structured API.

**Important corrections from testing:**
- REST Countries returns population + area only, NOT GDP. GDP comes from World Bank.
- Yahoo Finance fundamentals endpoint returns 401 Unauthorized. Dropped from Tier 1.
- Entity resolution: Wikipedia takes natural language. REST Countries takes names. World Bank needs ISO codes (chain from REST Countries). CoinGecko has search endpoint.

#### Tier 2 Sources (build next, require free API key registration)

| # | Source | Domain | API | Cost | Notes |
|---|---|---|---|---|---|
| 5 | **FRED** | US macro: GDP, CPI, unemployment, interest rates, 800K+ series | `api.stlouisfed.org/fred` | Free (key) | Keyword-to-series mapping table for ~20 common indicators |
| 6 | **Wolfram Alpha** | Computational facts, conversions, physical constants | `api.wolframalpha.com/v2` | Free 2K/mo | Short answer API returns plain text with numbers |
| 7 | **Brave Search** | Web search fallback for unresolved claims | `api.search.brave.com` | Free 2K/mo | Replaces some Gemini grounding queries at $0 cost |
| 8 | **Alpha Vantage** | Company fundamentals: revenue, earnings, cash flow | `alphavantage.co/query` | Free 25/day | Replaces Yahoo Finance for company financials |

#### Premium Pipeline Sources (build later, unlockable)

| # | Source | Domain | Why premium | Complexity |
|---|---|---|---|---|
| 9 | **SEC EDGAR** | US public company filings (10-K, 10-Q, XBRL) | Complex XBRL parsing, highest authority for US financials | High |
| 10 | **BLS** | Detailed US labor: employment by sector, wages, occupational data | Granular beyond FRED summaries | Medium |
| 11 | **WHO GHO** | Disease burden, mortality, vaccination, health expenditure | Specialized health domain | Medium |
| 12 | **NASA/NOAA** | Temperature records, CO2 levels, sea level, climate data | Specialized environmental domain | Medium |
| 13 | **US Census** | Demographics at state/county level, housing, income | Granular US demographics | Medium |
| 14 | **PubMed/CrossRef** | Academic citation verification (paper exists, author, year, journal) | Verifies "according to study X" claims | Medium |
| 15 | **Eurostat** | EU economic and demographic statistics | European complement to FRED/World Bank | Medium |
| 16 | **IMF Data** | Global economic outlook, fiscal forecasts | Authoritative macro projections | Medium |
| 17 | **OpenAlex** | 250M+ scholarly works, citation counts, impact metrics | Academic claim verification at scale | Medium |

**Premium model:** Free tier queries Tier 1 + 2 sources. Premium unlocks pipeline sources as domain packs:
- **Finance Pack:** SEC EDGAR + Alpha Vantage enhanced + BLS
- **Health Pack:** WHO GHO + PubMed + CDC
- **Science Pack:** NASA/NOAA + CrossRef + OpenAlex
- **Global Pack:** Eurostat + IMF + UN Data

### Claim Type Router

Regex-based classification. Each claim routes to 2-3 sources in parallel.

| Claim type | Detection signals | Sources queried |
|---|---|---|
| Entity facts (heights, dates, counts) | Named entity + measurement/count | Wikipedia + Wolfram Alpha |
| Country statistics | Country name + population/area/demographic terms | REST Countries + World Bank + Wikipedia |
| Macroeconomic (GDP, CPI, rates) | Country/economy + economic indicator terms | World Bank + FRED + Wikipedia |
| Crypto data | Coin names (BTC, ETH, etc.), "crypto", "blockchain" | CoinGecko + Wikipedia |
| Company financials | Company name + dollar amount + revenue/earnings | Wikipedia + Alpha Vantage |
| Computational/physical | Units, constants, "how many", conversions | Wolfram Alpha + Wikipedia |
| Development indicators | Country + poverty/literacy/life expectancy | World Bank + Wikipedia |
| General/unclassified | No strong signal for any domain | Wikipedia + Brave Search |

**Entity resolution per source:**
- Wikipedia: natural language search (takes anything)
- REST Countries: accepts country names directly
- World Bank: needs ISO code. Chain from REST Countries response.
- CoinGecko: has `/search` endpoint for coin name to ID
- FRED: keyword-to-series mapping table (~20 common indicators)
- Alpha Vantage: has symbol search endpoint for company names

### Step 3: Context-Aware Matching

Not just: does the number appear in the source? But: does the number appear in the source FOR THE SAME THING?

**Matching dimensions:**
- **Value match** (within tolerance): already have this
- **Metric match**: source number is about the same metric (revenue vs profit vs market cap)
- **Temporal match**: source number is from the same period (2023 vs 2024 vs Q3)
- **Entity match**: source is about the same entity (Apple Inc vs Apple Records)

**Matching score** = value_proximity * context_relevance

Where context_relevance is keyword overlap between the claim decomposition (subject, metric, time) and the source context window (20 words around the matched number).

**For text-based sources (Wikipedia, Brave):**
1. Extract all numbers from source text with 20-word context windows
2. For each candidate number match, score context similarity to claim
3. Candidate with highest context overlap wins

Example: Claim "300 known living species of octopus."
- Article: "...consists of some 300 species and is grouped..." (overlap: species) -> HIGH
- Article: "...found at depths up to 300 meters..." (overlap: none) -> LOW

**For structured APIs (FRED, World Bank, CoinGecko):**
Context matching is implicit. The API query already specifies the indicator/entity/date. If FRED returns a GDP value for the US for 2023, the context IS the query parameters. Value match is sufficient.

### Step 4: Derivation Checking

The most powerful step. Catches fabricated interpretations built on real numbers.

**Derived claim types:**
- Growth rates: "grew 24.3%"
- Ratios: "accounted for 58% of market"
- Differences: "increased by $50B"
- Aggregates: "total of $574B" (sum of components)

**Mechanism:**
1. Step 1 identifies claim as DERIVED and extracts `requires` (base values needed)
2. Steps 2-3 verify the base values against sources
3. Step 4 recomputes the derivation from verified base values
4. Compare recomputed value to the claimed derived value

**Example:**
```
Claim: "Revenue grew 24.3% year-over-year"
Step 1: type=DERIVED, requires=[current_revenue, prior_revenue]
Step 3: SEC/Wikipedia confirms FY2023=$383.3B, FY2022=$394.3B
Step 4: recompute (383.3-394.3)/394.3 = -2.8%
Verdict: CONTRADICTED. Claimed +24.3%, actual -2.8%.
The AI used real revenue numbers to construct a false growth narrative.
```

**Integration with existing code:** The consistency checker (`consistency.py`) already detects internal mathematical contradictions (percentage sums, part-whole, growth rates). Step 4 extends this with SOURCE-VERIFIED base values. Same math engine, external data.

### Step 5: Verification-Framing Synthesis

Connect verification results to the framing profile. This is the output that no one else produces.

**The synthesis answers:** "Which claims are grounded? Which are fabricated? And how does the document's frame hide the difference?"

**Example outputs:**

For a promotional document:
"This document presents Apple's $383B revenue correctly (confirmed: SEC filing). However, the claimed 24.3% growth is fabricated: actual change was -2.8%. The document frames a revenue decline as growth. Both numbers are presented with identical confidence. The prescriptive voice positions the reader to act on a false growth narrative."

For a reference document:
"15 of 22 factual claims confirmed against Wikipedia and World Bank. 3 values are close but not exact (within 5%). 4 claims have no authoritative source. The descriptive voice does not distinguish verified from unverified data."

For an analytical document:
"88% of claims attributed to named sources. All source-attributed claims verified. 2 unsourced numerical claims could not be confirmed. The analytical voice and evidence-based structure support reader evaluation."

**Implementation:** `framing_portrait()` gains a `verification` parameter with counts and notable findings. The portrait template adds a verification paragraph after the framing paragraph.

---

### Fallback: Gemini Grounding

Claims that complete Steps 1-4 with no source resolution fall through to Gemini. This is the current system, repositioned as the safety net for the hardest claims: market forecasts, niche domain facts, ambiguous contextual claims.

Better claim context (Step 1) means better Gemini queries. Fewer claims reach Gemini (Step 2-3 resolves 50-60%). Cost drops proportionally.

### Future: Verified Fact Cache

Build AFTER Steps 1-5 prove quality. Every verification creates a cacheable record. Repeat claims resolve instantly.

Cache policy: physical facts never expire. Financial data expires quarterly. Statistical data expires annually. Only cache 2+ source confirmed results.

---

## Consensus Logic

| Scenario | Verdict | Display |
|---|---|---|
| 2+ sources agree with claim | **VERIFIED** | "Wikipedia and World Bank both confirm" |
| 1 source agrees, others no data | **VERIFIED** (single) | "Wikipedia confirms. Others: no data." |
| Sources agree with each other but not claim | **CONTRADICTED** | "Claim: $384.7B. Wikipedia: $383B. World Bank: $383.3B." |
| Sources disagree with each other | **DISPUTED** | "Sources disagree. Range: $200B-$279B" |
| Source has close but not exact value | **CLOSE** | "Wikipedia: 116.07m (claim: 116.22m, 0.1% diff)" |
| Source confirms historical, not current | **OUTDATED** | "Correct in 2022. Current value: X" |
| No source found | **UNVERIFIABLE** | "No authoritative source found" |

The **DISPUTED** verdict is novel. No existing tool shows "sources disagree, here are all the values."

---

## Product Model

### Free Tier (Source Network Tier 1 + 2, zero/near-zero marginal cost)
- Full structural analysis (clarethium_measure, 10 layers)
- Framing profile (voice, epistemic, coverage, portrait)
- ALL claims verified against Tier 1 + 2 sources (Wikipedia, World Bank, REST Countries, CoinGecko, FRED, Wolfram, Brave Search, Alpha Vantage)
- Multi-source consensus verdicts with source attribution
- Framing-verification synthesis

### Premium Tier
- Pipeline sources unlocked (SEC EDGAR, WHO, PubMed, NASA, Census)
- Domain source packs (Finance, Health, Science, Global)
- Gemini web grounding for unresolved claims
- Automated Diff on Compare tab (number stability)
- Verified Fact Cache (instant repeat resolution)

### Conversion trigger
"15 claims verified against Wikipedia, World Bank, CoinGecko. 7 claims unresolved. Unlock SEC filings, WHO health data, and deep web verification."

---

## Build Sequence

### Phase 1: Steps 1-2 (Decompose + Route + Tier 1 Sources)

The foundation: claim decomposition, unit normalization, context enrichment, and the first 4 sources.

1. `decompose_claim(claim)`: extract subject, metric, time_period, claim_type, unit from claim sentence + heading. Regex patterns extending claim_analysis.py.
2. `normalize_value(raw, context)`: detect T/B/M/K/% scale suffixes and convert to base units.
3. `_extract_subject()`: heading/proper-noun/previous-sentence fallback chain.
4. `SourceRouter` class: claim type classification (regex), parallel dispatch to 2-3 sources.
5. `WikipediaSource`: search + article fetch + context-aware number matching.
6. `WorldBankSource`: ISO code resolution (via REST Countries) + indicator query.
7. `RESTCountriesSource`: country name lookup + population/area extraction.
8. `CoinGeckoSource`: coin search + price/market cap extraction.
9. Article cache: same heading = one fetch, many matches.
10. Pipeline integration: Source Router as new stage before Gemini.
11. Consensus logic: combine results from multiple sources per claim.

### Phase 2: Step 3 (Context-Aware Matching + Tier 2 Sources)

Matching that goes beyond "number found" to "number found in the same context."

12. Context-aware matching with metric/temporal/entity scoring.
13. FRED integration (API key + keyword-to-series mapping table).
14. Wolfram Alpha integration (short answer API + number extraction).
15. Brave Search integration (web fallback with snippet matching).
16. Alpha Vantage integration (company fundamentals).
17. Evidence cards redesigned: per-source values, context, match quality, links.
18. DISPUTED verdict display: multi-source value comparison.

### Phase 3: Step 4 (Derivation Checking)

Catching fabricated interpretations built on real numbers.

19. Derived claim detection: "grew X%", "increased by", "accounted for X%".
20. Base value extraction: identify the two numbers a growth rate depends on.
21. Source-verified recomputation: use Step 2-3 verified values to recompute.
22. Derivation verdict: CONFIRMED (math checks out) or CONTRADICTED (fabricated derivation).
23. Extend consistency.py with source-verified external contradictions.

### Phase 4: Step 5 (Synthesis + Compare Tab)

The output no one else produces.

24. Framing portrait gains verification statistics and notable findings.
25. Headline integrates verification-aware insights.
26. Annotated document highlights show source-verified vs unverified status.
27. Automated Diff on Compare tab (background SSE, number stability).

### Phase 5: Premium Pipeline + Cache

28. SEC EDGAR integration (XBRL parsing, premium).
29. WHO GHO integration (premium Health Pack).
30. PubMed/CrossRef integration (premium Science Pack).
31. Premium gate UX: domain source pack selection.
32. Verified Fact Cache with expiry policy and confidence thresholds.

---

## Success Criteria

**Step 1-2 (Decompose + Route):**
1. Hyperion tree (116.22m) resolves via Wikipedia in <500ms for $0
2. "300 octopus species" resolves via Wikipedia with correct disambiguation for $0
3. "US GDP $27.4 trillion" resolves via World Bank (with unit normalization) for $0
4. "BTC price $97,000" resolves via CoinGecko for $0
5. "France population 68 million" resolves via REST Countries for $0
6. 50%+ of claims in typical AI docs resolve via Source Network without Gemini

**Step 3 (Context-Aware Matching):**
7. "Apple revenue $383B (2023)" matches SEC/Wikipedia revenue figure, NOT profit or market cap
8. "300 species" matches species count in octopus article, NOT depth in meters
9. Multi-source consensus: claims checked by 2+ sources show all values
10. DISPUTED verdict displays when sources disagree

**Step 4 (Derivation Checking):**
11. "Grew 24.3% YoY" is recomputed from source-verified base values and flagged if wrong
12. Percentage claims ("58% market share") are checked against sum-of-parts from source

**Step 5 (Synthesis):**
13. Framing portrait includes: "X verified, Y disputed, Z unverifiable"
14. Synthesis connects verification results to voice/epistemic framing findings
15. The reader can see HOW the frame obscures which claims are grounded

**Economics:**
16. Average cost per profile drops from $0.042 to <$0.010

---

## What Is Not Obvious Now But Will Be in 5 Years

**1. Citation verification replaces claim verification.**

AI outputs are already starting to include inline citations (Gemini, Perplexity, Grok with sources). In 5 years, every AI output will cite its sources. The question shifts from "is this number real?" to "does the cited source actually say this?" FrameCheck should follow AI-provided citations and verify the claim against the cited source. "The AI says this comes from WHO. We checked. WHO says a different number." The Source Network infrastructure does this naturally: if the AI cites WHO, Tier 1 fetches WHO and compares.

**2. Framing becomes MORE valuable as fabrication decreases.**

Better models will get simple facts right more often. Fabrication moves from wrong numbers to wrong interpretation: correct numbers, false narrative. "Revenue grew 24.3%" using real base numbers when the actual change was -2.8%. Step 4 (derivation) and Step 5 (synthesis) become the core value proposition. The Source Network (Step 2) becomes table stakes that every tool has. The framing analysis is what no one else builds.

**3. Regulatory demand for AI output audit trails.**

EU AI Act. Corporate AI governance. Financial compliance. SEC disclosure rules for AI-generated content. Organizations will need a third-party audit trail for AI-generated documents. The evidence chain (which tiers were checked, what each found, the full cascade) becomes a compliance artifact. FrameCheck as the auditor, not just the profiler.

**4. Multi-modal verification.**

AI generates charts, tables, infographics with embedded numbers. Verifying a number in a generated chart requires image understanding + verification. The Source Network + matching infrastructure extends to numbers extracted from images. The framing profile extends to visual framing: what does the chart emphasize, what does it hide, what scale distortions exist.

**5. Continuous organizational monitoring.**

Not one-off profiles. Continuous monitoring of AI outputs across an organization. "Your team's AI outputs had a 34% unsourced claim rate this month, up from 28%. Marketing department has 73% prescriptive voice. Legal department has 91% sourced claims." The Source Network + Cache make this economically viable (most claims resolve from cache at zero cost). The framing profile produces organizational intelligence.

**6. The Source Network becomes a platform.**

Third-party developers add domain-specific sources. A financial services firm adds their internal data API as a verification source. A pharmaceutical company adds their drug trial database. The Source Router accepts custom sources. FrameCheck becomes the verification platform, not just the verification tool.

---

## Risks and Mitigations

**API instability.** Yahoo Finance fundamentals already failed (401). Any API can change. Mitigation: graceful degradation. If a source is down, claims fall through to the next source or Gemini. The system never fails, only degrades.

**False positives in text matching.** "300" in Wikipedia matches species count but also depth in meters. Mitigation: context-aware matching with proximity scoring. Claim context keywords disambiguate.

**Unit mismatch.** "$27.4T" vs 27293689000000. Mitigation: unit normalizer converts both sides to base units before comparison.

**Entity ambiguity.** "Apple" could be Apple Inc or Apple Records. Mitigation: claim context (heading, surrounding text) disambiguates. Wikipedia search returns the most likely article.

**Rate limits.** CoinGecko: 10-30 calls/min (free). REST Countries: no documented limit. World Bank: no documented limit. Wikipedia: 200 req/s with polite User-Agent. All adequate for 20-30 claims per profile.

**Coverage gaps.** Market size forecasts (Gartner/IDC paywalled), niche domain facts, derived statistics. These fall through to Gemini. The Source Network does not eliminate the need for LLM verification. It handles the 50-60% of claims that have structured authoritative sources.
