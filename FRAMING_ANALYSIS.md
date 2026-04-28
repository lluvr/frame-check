# Framing Analysis: Design Specification

Not "which AI is better." Not even "what is each AI hiding." The deeper question: what frame is your AI putting around reality, and what would you see outside it?

---

## The Core Insight

Every model makes structural choices about what to emphasize, what to omit, what to assert confidently, what to hedge, what time frame to orient toward. These choices are invisible when you read one output. They become partially visible when you compare two. They become fully visible when the structure itself is measured.

This is not a benchmark. Benchmarks compare accuracy. This measures the shape of the reality the AI constructs. Different shape, different decisions downstream.

## Why This Gets More Valuable Over Time

Better models produce MORE persuasive framing, not less biased framing. More fluent. More confident. Harder to see through. Framing detection becomes MORE necessary as models improve.

AGI doesn't fix this. An AGI trained on data emphasizing one narrative will still frame through that lens. Framing analysis is orthogonal to capability. It measures the shape of the output, not the quality.

Zero-LLM analysis is less capable than LLM-powered comparison but more trustworthy. Using an LLM to evaluate other LLMs has the circular evaluation problem (EXP-078). The tool doesn't judge. It makes the invisible visible.

---

## Architecture: Three Layers

### Layer A: Framing Detection (single output)

Works on ANY text. No comparison needed. The foundation everything else builds on.

**A1: Category Coverage**

Five structural categories that apply to any analytical response. These are properties of analytical writing, not topic-specific content expectations.

| Category | What it covers | Marker language |
|----------|---------------|-----------------|
| Causes | Why things happen | "because," "due to," "driven by," "caused by," "as a result," "led to," "attributed to," "resulting from," "stems from" |
| Risks | What could go wrong | "risk," "threat," "challenge," "concern," "vulnerability," "downside," "obstacle," "barrier," "limitation," "however," "despite," "caveat" |
| Stakeholders | Who's affected | "affects," "impacts," "benefits," "harms," "stakeholders," "population," "workforce," "residents," "displaced." Entity nouns (consumers, workers, investors) only counted when near action verbs. |
| Trends | What's changing | "growing," "declining," "shifting," "emerging," "transitioning," "increasingly," "trend," "trajectory," "momentum," "evolution" |
| Uncertainty | What's unclear | "unclear," "uncertain," "debated," "contested," "depends," "varies," "unpredictable," "unknown," "remains to be seen," "not yet determined" |

"Facts" excluded from coverage tracking: any analytical text with numbers covers facts. Including it creates a category that's always present, adding noise to the coverage profile.

Implementation reports **density** (markers per 1000 words), not just presence/absence. Density matters because a 2000-word analysis that mentions "challenge" once in paragraph 8 FEELS comprehensive. The density ratio (14 growth markers vs 1 risk marker) reveals what the reader's impression hides.

The inter-category ratio is interpretable without baselines. "14 trend markers, 1 risk marker" tells a clear story. No need to know what's "normal" to see the imbalance.

```python
ANALYTICAL_CATEGORIES = {
    "causes": re.compile(
        r'\b(because|due\s+to|driven\s+by|caused\s+by|as\s+a\s+result|led\s+to|'
        r'attributed\s+to|resulting\s+from|stems?\s+from|owing\s+to)\b',
        re.IGNORECASE
    ),
    "risks": re.compile(
        r'\b(risk|threat|challenge|concern|vulnerab|downside|'
        r'obstacle|barrier|limitation|constraint|danger|warning|caveat|drawback)\b',
        re.IGNORECASE
    ),
    "stakeholders": re.compile(
        r'\b(affects?|impacts?|benefits?|harms?|stakeholders?|'
        r'population|workforce|residents|displaced|'
        r'(?:consumers?|workers?|investors?|patients?)\s+'
        r'(?:are|were|will\s+be|face|benefit|suffer|experience))\b',
        re.IGNORECASE
    ),
    "trends": re.compile(
        r'\b(growing|declining|shifting|emerging|transitioning|increasingly|'
        r'trend|trajectory|momentum|acceleration|evolution|transformation)\b',
        re.IGNORECASE
    ),
    "uncertainty": re.compile(
        r'\b(unclear|uncertain|debated|contested|depends|varies|unpredictable|'
        r'unknown|open\s+question|remains\s+to\s+be\s+seen|'
        r'not\s+(?:yet|fully)\s+(?:clear|understood|determined))\b',
        re.IGNORECASE
    ),
}


def detect_coverage(text):
    """Detect which analytical categories a document covers, with density.

    Returns per-category marker count, density per 1Kw, and coverage summary.
    """
    MIN_MARKERS = 2
    word_count = len(re.findall(r'\b\w+\b', text))
    kw = max(word_count / 1000, 0.1)

    categories = {}
    covered = set()

    for cat, pattern in ANALYTICAL_CATEGORIES.items():
        matches = pattern.findall(text)
        count = len(matches)
        density = round(count / kw, 1)
        categories[cat] = {
            "count": count,
            "density_per_1kw": density,
            "covered": count >= MIN_MARKERS,
        }
        if count >= MIN_MARKERS:
            covered.add(cat)

    all_cats = set(ANALYTICAL_CATEGORIES.keys())
    missing = all_cats - covered

    return {
        "categories": categories,
        "covered": sorted(covered),
        "missing": sorted(missing),
        "coverage_count": len(covered),
        "total_categories": len(all_cats),
        "word_count": word_count,
    }
```

**A2: Temporal Orientation**

What time frame does the response orient you toward? A response that's 55% past-oriented reads as "here's what happened." A response that's 45% future-oriented reads as "here's what's coming." Same topic. Different frame. Different decisions.

```python
PAST_RE = re.compile(
    r'\b(was|were|had|did|grew|declined|fell|rose|reached|'
    r'exceeded|dropped|increased|decreased|experienced|'
    r'in\s+20[01]\d|in\s+201\d|in\s+202[0-6]|last\s+year|previously|'
    r'historically|traditionally)\b',
    re.IGNORECASE
)

FUTURE_RE = re.compile(
    r'\b(will|shall|projected|forecast|expected\s+to|anticipated|'
    r'predicts?|estimates?\s+(?:that|a)|by\s+202[7-9]|by\s+20[3-9]\d|'
    r'going\s+forward|in\s+the\s+(?:coming|next)|outlook|'
    r'poised\s+to|set\s+to|on\s+track)\b',
    re.IGNORECASE
)


def temporal_orientation(text):
    """Compute past/present/future orientation ratio."""
    sentences = split_sentences(text)
    past = sum(1 for s in sentences if PAST_RE.search(s))
    future = sum(1 for s in sentences if FUTURE_RE.search(s))
    # "Present" is the residual bucket: sentences with no past/future markers.
    # Includes definitions, methodology, structural sentences. Not a clean
    # temporal classification. Interpret as "non-temporal" when dominant.
    present = len(sentences) - past - future
    total = max(len(sentences), 1)
    return {
        "past_pct": round(past / total * 100),
        "present_pct": round(present / total * 100),
        "future_pct": round(future / total * 100),
        "dominant": (
            "past" if past > future and past > present
            else "future" if future > past and future > present
            else "present"
        ),
    }
```

**A3: Framing Summary**

Descriptive, not evaluative. Combines category coverage, temporal orientation, and existing claim_analysis signals into a human-readable summary.

No labels like "OPTIMISTIC-FORWARD." Those are editorial. The summary describes what the document covers and doesn't cover, and lets the user judge whether the gaps matter for their use case.

```python
def framing_summary(coverage, temporal, claim_stats):
    """Generate a descriptive framing summary. No evaluative labels."""
    parts = []

    # Coverage
    if coverage["missing"]:
        parts.append(
            f"Covers: {', '.join(coverage['covered'])}. "
            f"Low structural coverage: {', '.join(coverage['missing'])}."
        )
    else:
        parts.append(
            "Covers all five analytical dimensions "
            "(causes, risks, stakeholders, trends, uncertainty)."
        )

    # Density imbalance (if one covered category dominates another)
    cats = coverage["categories"]
    densities = {k: v["density_per_1kw"] for k, v in cats.items() if v["covered"]}
    if len(densities) >= 2:
        max_cat = max(densities, key=densities.get)
        min_cat = min(densities, key=densities.get)
        # Require the dominant category to have meaningful density (>2.0/1Kw)
        # and be 3x+ the weakest. Avoids flagging tiny differences.
        if densities[max_cat] > 2.0 and densities[min_cat] > 0 and \
           densities[max_cat] > 3 * densities[min_cat]:
            parts.append(
                f"Emphasis skew: {max_cat} ({densities[max_cat]}/1Kw) "
                f"vs {min_cat} ({densities[min_cat]}/1Kw)."
            )

    # Temporal
    parts.append(f"Temporal orientation: {temporal['dominant']} "
                 f"({temporal[temporal['dominant'] + '_pct']}%).")

    # Confidence (from claim_analysis)
    total = claim_stats.get("total_claims", 0)
    unhedged = claim_stats.get("unhedged_count", 0)
    if total >= 5 and unhedged / total > 0.8:
        parts.append(
            f"{unhedged} of {total} claims stated as definitive fact "
            "with no qualifying language."
        )

    return " ".join(parts)
```

Output example: "Covers: causes, trends. Low structural coverage: risks, uncertainty, stakeholders. Emphasis skew: trends (8.2/1Kw) vs causes (1.4/1Kw). Temporal orientation: future (61%). 14 of 17 claims stated as definitive fact with no qualifying language."

**Construct note.** "Low structural coverage" is a lower-bound claim about what the vocabulary-based detector found, not an upper-bound claim about what the document discusses. A document may address a dimension with language the detector does not recognize. The honest framing is "markers not found" rather than "not addressed."

---

### Layer B: Framing Comparison (two outputs)

Extends Layer A to two responses. Requires both outputs to have been analyzed with Layer A first.

**B1: Convergence Score (context setter)**

Displayed first. Tells the user how much the responses overlap.

```python
def framing_convergence(text_a, text_b):
    """How similar are these responses? 0.0 = completely different, 1.0 = identical."""
    words_a = set(re.findall(r'\b[a-z]{4,}\b', text_a.lower()))
    words_b = set(re.findall(r'\b[a-z]{4,}\b', text_b.lower()))

    stops = {
        "that", "this", "with", "from", "have", "been", "were", "will",
        "more", "than", "also", "into", "over", "such", "which", "their",
        "about", "would", "other", "these", "could", "being", "after",
        "before", "between", "through", "should", "where", "while",
        "during", "including", "because",
    }
    words_a -= stops
    words_b -= stops

    if not words_a or not words_b:
        return {"score": 0.0, "label": "insufficient data"}

    jaccard = len(words_a & words_b) / len(words_a | words_b)

    if jaccard > 0.6:
        label = "high"
        note = "These models largely agree. Differences below are subtle."
    elif jaccard > 0.35:
        label = "moderate"
        note = "Meaningful framing differences. The analysis below highlights them."
    else:
        label = "low"
        note = "These models frame this topic very differently. Pay close attention."

    return {
        "score": round(jaccard, 2),
        "label": label,
        "note": note,
        "unique_a": len(words_a - words_b),
        "unique_b": len(words_b - words_a),
        "shared": len(words_a & words_b),
    }
```

Known limitation: Jaccard on content words is crude. Synonyms ("growth" vs "expansion") reduce measured convergence even when the meaning is the same. Acceptable for v1 because the thresholds are conservative and the score is context-setting, not definitive.

**B2: Shared Blind Spots (the headline)**

Categories missing from BOTH responses. Uses Layer A coverage detection on each text, then computes the intersection of gaps.

```python
def detect_blind_spots(coverage_a, coverage_b):
    """Find analytical categories missing from BOTH responses.

    Takes the output of detect_coverage() for each response.
    """
    missing_a = set(coverage_a["missing"])
    missing_b = set(coverage_b["missing"])
    shared_blind = sorted(missing_a & missing_b)
    only_a_missing = sorted(missing_a - missing_b)  # A misses, B covers
    only_b_missing = sorted(missing_b - missing_a)  # B misses, A covers

    return {
        "blind_spots": shared_blind,
        "only_a_missing": only_a_missing,
        "only_b_missing": only_b_missing,
    }
```

Output when blind spots found: "Neither response addresses risks or uncertainty. Both present the topic without downside scenarios. Whichever AI you used, the risk dimension is invisible."

Output when no blind spots: "Both models address all five analytical dimensions. No structural gaps. The value of this comparison is in the confidence and temporal differences below."

**B3: Confidence Divergence (the sharpest finding)**

Where one model asserts what the other hedges. Surfaces the SINGLE most revealing case.

```python
def find_confidence_divergence(claims_a, claims_b, model_a_name, model_b_name):
    """Find claims where one model hedges and the other asserts.

    Returns the single most interesting divergence, or None.
    """
    divergences = []

    def _scan(asserting_claims, hedging_claims, asserting_name, hedging_name):
        for ca in asserting_claims:
            if ca["framing"] != "stated_as_fact":
                continue
            for cb in hedging_claims:
                if cb["framing"] != "hedged":
                    continue
                if _claims_overlap(ca, cb):
                    divergences.append({
                        "asserting_model": asserting_name,
                        "hedging_model": hedging_name,
                        "asserting_claim": ca["sentence"][:150],
                        "hedging_claim": cb["sentence"][:150],
                        "hedge_words": cb["hedge_words"],
                        "numbers_a": ca["numbers"],
                        "numbers_b": cb["numbers"],
                    })

    _scan(claims_a, claims_b, model_a_name, model_b_name)
    _scan(claims_b, claims_a, model_b_name, model_a_name)

    if not divergences:
        return None

    # Prioritize divergences with numerical claims (more concrete, more shareable)
    divergences.sort(
        key=lambda d: len(d.get("numbers_a", [])) + len(d.get("numbers_b", [])),
        reverse=True,
    )
    return divergences[0]


def _claims_overlap(claim_a, claim_b):
    """Check if two claims are about the same topic via keyword overlap.

    Known limitation: domain-specific topics (semiconductors, healthcare)
    produce false positives because both claims share domain vocabulary
    regardless of specific sub-topic. The 0.3 threshold is a calibration
    point. Validation: manual review on 3 comparisons; adjust if FPR > 30%.
    """
    words_a = set(re.findall(r'\b[a-z]{4,}\b', claim_a["sentence"].lower()))
    words_b = set(re.findall(r'\b[a-z]{4,}\b', claim_b["sentence"].lower()))
    stops = {
        "that", "this", "with", "from", "have", "been", "were", "will",
        "more", "than", "also", "into", "over", "such", "which",
    }
    words_a -= stops
    words_b -= stops
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
    return overlap > 0.3
```

**B4: Temporal Divergence**

Uses Layer A temporal_orientation on each text. Reports the difference.

```python
def temporal_divergence(temporal_a, temporal_b, model_a_name, model_b_name):
    """Compare temporal orientation between two responses."""
    diff_past = abs(temporal_a["past_pct"] - temporal_b["past_pct"])
    diff_future = abs(temporal_a["future_pct"] - temporal_b["future_pct"])
    max_diff = max(diff_past, diff_future)

    if max_diff < 10:
        note = "Similar temporal framing."
    else:
        if temporal_a["dominant"] != temporal_b["dominant"]:
            note = (
                f"{model_a_name} orients toward the {temporal_a['dominant']} "
                f"({temporal_a[temporal_a['dominant'] + '_pct']}%). "
                f"{model_b_name} orients toward the {temporal_b['dominant']} "
                f"({temporal_b[temporal_b['dominant'] + '_pct']}%)."
            )
        else:
            note = (
                f"Both orient toward the {temporal_a['dominant']}, "
                f"but {model_a_name} ({temporal_a[temporal_a['dominant'] + '_pct']}%) "
                f"more so than {model_b_name} ({temporal_b[temporal_b['dominant'] + '_pct']}%)."
            )

    return {
        "diff_past": diff_past,
        "diff_future": diff_future,
        "max_diff": max_diff,
        "meaningful": max_diff >= 10,
        "note": note,
    }
```

Validation required: do Gemini and Grok actually differ on temporal orientation? If differences are within 10pp on most topics, this layer produces "Similar temporal framing" consistently and should be visually de-emphasized.

---

### Layer C: Framing Intelligence (future, compound data)

**Status: UNVALIDATED TERRITORY.** These are directions the detection layers could go, not designed features. Each requires significant scale and/or research before committing. Documented here so the direction is visible, not to imply they're planned.

**C1: Model Framing Fingerprints.** After 1000+ comparisons, per-model framing patterns by domain emerge. "Gemini emphasizes regulatory framing on financial topics. Grok emphasizes competitive framing." Requires scale the tool doesn't have yet.

**C2: Prompt-Response Frame Analysis.** Does the prompt's frame shape the response's blind spots? "Your question framed this as a growth inquiry. The AI responded within that frame. The blind spot started with you." Connects to vault insight HI-062 (AI amplifies the operator's patterns). Requires research on whether prompt framing measurably predicts response framing.

**C3: Institutional Monitoring.** Aggregate framing bias across an organization's AI usage. "Your team's AI outputs systematically underweight risk." Requires enterprise product, API integration, and continuous monitoring infrastructure.

**C4: Real-Time Detection.** Browser extension or API integration that annotates AI responses as you read them. Same detection logic, different delivery. Requires distribution (extension store, API partners) and architectural changes (the detection must run client-side or via lightweight API).

None of these are in scope for v1. They're the territory that opens if v1 proves the detection layers work.

---

## Output Architecture

### Single-Output Profile (in the profiler)

**Integration point:** The framing profile appears AFTER the structural analysis (risk level, claim analysis) and BEFORE the annotated document. Rationale: the structural analysis tells you WHAT the claims are. The framing profile tells you what the DOCUMENT is doing with those claims. The annotated document is the detail view. The flow is: overview > framing > detail.

Added to every profile result:

```
FRAMING PROFILE

Analytical coverage:
  Covered: causes, trends (2 of 5)
  Not addressed: risks, uncertainty, stakeholders

  Density: trends 8.2/1Kw, causes 1.4/1Kw
  Emphasis toward trends over causal explanation.

Temporal orientation: future (61%)

Confidence: 14 of 17 claims stated as definitive fact.

Summary: Covers causes and trends. Low structural coverage of
risks, uncertainty, and stakeholders. 61% future-oriented. Most
claims presented as definitive without qualifying language.
```

### Comparison Output

Displayed in this order:

```
1. FRAMING CONVERGENCE
   Score + label + note. Sets context.

2. SHARED BLIND SPOTS
   Categories missing from BOTH. The mirror moment.
   Or: "Both models are structurally complete."

3. BIGGEST CONFIDENCE GAP
   The single most revealing divergence.
   Or: "No confidence divergences detected."

4. TEMPORAL DIVERGENCE
   How each model orients you in time.
   Or: "Similar temporal framing."

--- existing comparison below ---
5. Numerical agreement/disagreement
6. Per-model structural profiles
7. Near-matches
```

The framing analysis is the primary output. The numerical comparison becomes supporting detail.

---

## Share Card Content

The share card features ONE finding:
- Blind spot: "Both AIs missed [category]. Your analysis has a shared gap."
- Confidence gap: "One AI says 'approximately.' The other says '$697.4B.' Same claim."
- Convergence: "Framing convergence: 38%. These AIs see this topic very differently."

Default: blind spot if found, otherwise convergence score. Override by data: whichever type generates the most shares after 100 comparisons becomes the default.

---

## Known Limitations (v1)

1. **Two models only.** Framing comparison reflects Gemini vs Grok. Broader model coverage (Claude, GPT) in future versions. Adding each model adds API cost per comparison.

2. **Convergence score is crude.** Jaccard on content words misses synonyms. "Growth" and "expansion" are the same concept but reduce measured convergence. Conservative thresholds (0.35/0.6) mitigate false signals.

3. **Claims overlap matching has false positives.** On domain-specific topics, two claims about different sub-topics share domain vocabulary and match incorrectly. The 0.3 threshold is a calibration point to be adjusted based on validation.

4. **Category detection is keyword-based.** Complex risk language ("the trajectory depends heavily on supply chain stability, which has shown fragility in recent quarters") may not trigger the risk regex despite clearly discussing risk. Keyword-based detection catches explicit markers, not semantic meaning. Acceptable for structural screening, not for definitive classification.

5. **Temporal classification assigns each sentence to exactly one bucket.** A sentence with both past and future markers ("revenues grew 40% and are expected to reach $500B") gets counted once, whichever regex matches first. Edge cases exist.

6. **No baselines for density.** "8.2 risk markers per 1Kw" has no reference point. Is that high or low? Inter-category ratios are interpretable without baselines, but absolute density is not. Baselines accumulate from usage data over time.

7. **Single-output framing is less impactful on short texts.** A reader can manually assess the framing of a 500-word response. The tool adds most value on longer documents (1500+ words) where category ratios are invisible to casual reading.

---

## Implementation Priority

### Phase 1: Single-Output Framing Profile (add to profiler)

| Component | Effort | Dependencies |
|-----------|--------|-------------|
| detect_coverage() | 2-3 hours | None |
| temporal_orientation() | 1-2 hours | split_sentences from clarethium_measure |
| framing_summary() | 1 hour | detect_coverage + temporal + claim_analysis |
| Profiler template updates | 1-2 hours | framing_summary output |

Total: 5-8 hours. Adds framing profile to every profiler result.

### Phase 2: Comparison Framing Analysis (add to comparison tab)

| Component | Effort | Dependencies |
|-----------|--------|-------------|
| framing_convergence() | 1-2 hours | None |
| detect_blind_spots() | 1 hour | detect_coverage from Phase 1 |
| temporal_divergence() | 30 min | temporal_orientation from Phase 1 |
| find_confidence_divergence() | 3-4 hours | claim_analysis output from both models |
| Comparison template updates | 2-3 hours | All comparison outputs |

Total: 8-11 hours. Requires Phase 1 complete.

### Phase 3: Validation

Run before shipping comparison features:

1. **Blind spot variance.** 5 diverse topics. Do blind spots vary or are they always the same categories?
2. **Temporal differentiation.** 10 comparisons. Do models actually differ by 10pp+?
3. **Confidence matching accuracy.** 3 comparisons, manual review. FPR of _claims_overlap.
4. **Convergence score validity.** 5 comparisons, manual similarity rating vs Jaccard.

Document results. Adjust thresholds. De-emphasize layers that produce null results consistently.

---

## What This Connects To

- **comparison.py:** extends compare_responses() with Layer B functions
- **app.py:** profile endpoint adds Layer A framing output; comparison endpoint adds Layer B
- **formatter.py:** new display sections for framing profile and comparison framing
- **templates/:** profiler and comparison templates need framing sections
- **clarethium_measure.py:** split_sentences used by temporal_orientation (already imported)
- **claim_analysis.py:** claim output used by confidence_divergence and framing_summary
- **DECISIONS.md:** framing analysis resolves Decision 4 and shapes Decisions 1-3

---

## Data Capture (for compound)

Every profile and comparison stores anonymized framing data. No document content stored. Only structural signals.

**Per-profile capture (Layer A):**
```python
{
    "timestamp": "2026-04-02T...",
    "word_count": 1847,
    "coverage": {"causes": 3.2, "risks": 0.5, "stakeholders": 0.0,
                 "trends": 8.1, "uncertainty": 0.0},
    "covered": ["causes", "trends"],
    "missing": ["risks", "stakeholders", "uncertainty"],
    "temporal": {"past_pct": 22, "present_pct": 17, "future_pct": 61},
    "confidence_uniformity": 0.82,
    "total_claims": 17,
    # No document text. No topic. No user identity.
}
```

**Per-comparison capture (Layer B):**
```python
{
    "timestamp": "2026-04-02T...",
    "topic_hash": "sha256(topic)[:16]",  # For grouping, not identifying
    "convergence_score": 0.38,
    "blind_spots": ["risks", "uncertainty"],
    "confidence_divergence_found": True,
    "temporal_diff_past": 29,
    "temporal_diff_future": 22,
    "model_a": "gemini",
    "model_b": "grok",
    # No response text. No topic text.
}
```

Storage: append-only JSON lines file on the server. Lightweight. No database needed for v1. Migrate to proper storage if volume exceeds 10K entries.

**What compounds from this data:**
- Category coverage distributions across all profiles (which categories are most commonly missing?)
- Per-model temporal patterns (does Gemini consistently orient differently than Grok?)
- Convergence score distributions by topic domain (which topics produce the most divergence?)
- Confidence divergence frequency (how often do models disagree on certainty?)

These aggregate findings become transmissions. The transmissions drive traffic. The traffic drives profiles and comparisons. The data compounds.

The detection layers are the foundation. Everything else is built on top of them.
