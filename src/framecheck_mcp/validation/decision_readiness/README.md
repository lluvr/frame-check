# Decision-readiness validation

Validation harness for the Frame Check decision-readiness profile
(see [/corpus/decision-readiness/](https://frame.clarethium.com/corpus/decision-readiness/)
for the methodology). Phase 2 of the validation work, per that page.

## What's in here

```
validation/decision_readiness/
├── README.md                  this file
├── rater_guide.md             per-dimension operational definitions for raters
├── rating_template.yaml       the form a rater fills in for one document
├── run_validation.py          correlation harness (Spearman + ICC + per-genre)
├── corpus/                    rated documents (with metadata + Frame Check profile)
│   └── {doc_id}/
│       ├── document.md        the text being rated
│       ├── metadata.yaml      genre, source, date, etc.
│       └── profile.json       Frame Check's computed decision-readiness profile
├── ratings/                   per-rater submissions
│   └── {doc_id}/
│       └── {rater_id}.yaml    one rater's scores for one document
└── results/                   correlation outputs by run date
    └── {date}/
        ├── correlations.json  per-dimension Spearman + ICC + per-genre
        └── divergence.md      documents where profile and raters diverge
```

## Why this exists

The decision-readiness methodology page makes claims about which
structural signals correspond to decision support. Those claims
are not credible without external validation.

This validation harness collects expert ratings on a curated
corpus, compares them against Frame Check's computed profile, and
publishes per-dimension correlations. The profile becomes a live
signal in the product surface only when correlations clear the
thresholds documented on the methodology page (Spearman >= 0.6
averaged across genres, no genre below 0.4).

## Phase 2 status

| Task                                | Status                              |
|-------------------------------------|-------------------------------------|
| Methodology published               | Done (Phase 1)                      |
| Backend computation                 | Done (Phase 1.5; JSON-only exposure)|
| Validation directory + harness      | Done (this scaffolding)             |
| Rater guide                         | Done (`rater_guide.md`)             |
| Rating template                     | Done (`rating_template.yaml`)       |
| Corpus curation (target 20-30 docs) | In progress (initial set TBD)       |
| Rater recruitment (3+ per genre)    | In progress                         |
| First validation run                | Pending                             |
| Methodology page status update      | Pending Phase 2 results             |

## How a rater contributes

1. Read `rater_guide.md` for the operational definitions of each
   of the five dimensions and the 1-5 anchor descriptions.
2. Pick a document from `corpus/`. Open `document.md` and read it
   in full. Do NOT read `profile.json` first — ratings must be
   blind to Frame Check's computed profile.
3. Copy `rating_template.yaml` to
   `ratings/{doc_id}/{your_rater_id}.yaml` and fill in your scores.
4. Open a pull request with your rating file.

The blinding requirement is load-bearing for validation integrity.
A rater who has read Frame Check's profile cannot un-read it; their
ratings are no longer independent ground truth.

### What makes a good rater

The validation effort wants raters who can apply the dimensional
anchors consistently across documents. In practice this means:

- **Genre familiarity** with at least one of the corpus genres
  (financial analysis, policy briefs, journalism, AI responses to
  life questions). Domain knowledge calibrates expectations
  about what coverage / hedging / sourcing look like in that
  genre.
- **Comfort with ambiguity**. Some documents fall between anchors;
  the guide says "prefer the lower score when a document is between
  two anchors" but rating still requires judgment.
- **Willingness to leave free-text notes**. Notes are how the
  validation effort interprets divergence cases. A rater who
  scores quickly and skips notes contributes less than one who
  scores slower and explains their reasoning.

Academic credentialing is not required. A practitioner with
sustained engagement in one of the genres is as useful as a
PhD researcher; both are useful in different ways.

### Worked examples (calibrate before submitting)

For a side-by-side contrast of GOOD vs MEDIOCRE vs INSUFFICIENT
rating styles on the same corpus document, see `examples/`. The
three files there rate `four-llms-bitcoin-claude` at three
quality levels with notes explaining what makes the difference.
Reading them before producing your own first rating is the
fastest way to calibrate against what the validation effort
actually needs.

The contracted form below is the minimum useful shape:

```yaml
doc_id: "example-doc"
rater_id: "alice"
rated_at: "2026-04-19"

ratings:
  coverage: 3
  calibration: 2
  evidence: 4
  robustness: 4
  counterfactual: 1

notes:
  coverage: "Addresses causes, trends, and stakeholders. Risks and uncertainty are absent."
  calibration: "Many predictions stated as facts ('will reach $500B'). Confidence Imbalance pattern is clear."
  evidence: "Most numerical claims are sourced to SEC filings or analyst reports."
  robustness: "Spot-checked three numbers; all matched sources within tolerance."
  counterfactual: "No mention of what would falsify the thesis. No alternative interpretations considered."
  overall: "Strong evidence backing carries an otherwise overconfident piece. A reader with no domain knowledge could not distinguish the well-supported claims from the speculation."

time_spent_minutes: 22
secondary_genres: []
self_confidence: 4
```

The notes here are short but specific. They name what the rater
saw at each dimension. When Frame Check's computed profile and
the expert mean diverge, the notes are what makes the divergence
interpretable for methodology revision.

### License

Rating files contributed to this validation effort are released
under
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/),
matching the rest of the Frame Check corpus. Submitting a rating
PR implies acceptance of this license. Raters are credited by
`rater_id` in the published validation results unless they
request anonymization, in which case ratings are aggregated
under an anonymous slug.

## Adding new corpus entries from external text

When you have captured the verbatim text of an external document
(FOMC statement, news article, published essay), use:

```
python3 validation/decision_readiness/add_external_corpus_entry.py \
    --slug {your-slug} \
    --text-file {path-to-text} \
    --genre {financial|policy|journalism|ai_response|other} \
    --title "{title}" \
    --source "{URL or attribution}"
```

For a transformation pair (e.g., LLM summary of an existing
source), pass `--paired-with {source_slug}` and
`--transformation-kind llm_summary`. For a peer group entry,
pass `--peer-group {group_name}`. After adding paired or grouped
entries, re-run `compute_pair_diffs.py` and/or
`compute_peer_comparisons.py` so the comparison files refresh.

See `CORPUS_GENRE_GAPS.md` for which genres need entries and
suggested public sources.

## Aggregate corpus findings

Beyond the rating-based validation harness, a separate
`aggregate_corpus_findings.py` tool produces descriptive
statistics across the curated corpus (per-dimension peer
divergence rates, per-LLM participation in differing pairs,
per-transformation-kind movement signatures). Output is markdown
+ JSON, written to `results/{date}-{corpus_hash}/`. The corpus
state hash in the directory name disambiguates aggregate runs
across corpus revisions.

The aggregate findings are explicitly DESCRIPTIVE of the corpus
state, not inference about LLM populations. Every claim names
its N inline. As the corpus grows, the same tool produces
increasingly meaningful output; the aggregate at N=12 is a
small-sample description, the aggregate at N=200 is a real
research finding. The tool is the durable artifact.

```
python3 validation/decision_readiness/aggregate_corpus_findings.py
```

## Cross-check: aggregate vs expert outliers

Once expert ratings start arriving, the cross-check harness
compares the aggregate's structural outlier identifications
against expert-derived outliers (median-distance on expert mean
ratings). Agreement between the two is the validation signal
that turns the descriptive aggregate into an inferentially
supported finding.

```
python3 validation/decision_readiness/cross_check_aggregate.py
```

The cross-check writes `cross_check.json` and `cross_check.md`
into the same `results/{date}-{corpus_hash}/` directory the
aggregate writes to. With zero ratings present the harness still
runs cleanly — every cell is reported as non-comparable. When
ratings exist for at least three members of a peer group on at
least one dimension, agreement computation begins.

## How to run the harness

```bash
python3 validation/decision_readiness/run_validation.py
```

The harness:
1. Loads all rating files from `ratings/`
2. Loads Frame Check profiles from `corpus/{doc_id}/profile.json`
3. Computes per-document expert mean per dimension
4. Computes Spearman correlation between expert means and Frame
   Check signals across all rated documents
5. Computes ICC across raters per dimension (inter-rater reliability)
6. Writes `results/{date}/correlations.json` and a divergence note

The harness runs cleanly with zero ratings (prints a status message
and exits). It validates pipeline plumbing before any rating data
exists.

## Seeded corpus

The initial corpus is seeded from documents already in
`data/worked_examples/`. Run `python3 curate_corpus.py
--all-defaults` to (re)generate the seeded entries. Initial set:

| slug                                | genre        | source                                                |
|-------------------------------------|--------------|-------------------------------------------------------|
| grok-nvidia-q4-fy24-summary         | ai_response  | Grok 4.1 Fast summary of NVIDIA Q4 FY24 earnings      |
| ai-on-life-decisions-startup        | ai_response  | AI response to "should I take this startup offer"     |
| four-llms-bitcoin-claude            | ai_response  | Claude on "should I retire on Bitcoin"                |
| four-llms-bitcoin-openai            | ai_response  | OpenAI GPT on "should I retire on Bitcoin"            |
| four-llms-bitcoin-grok              | ai_response  | Grok on "should I retire on Bitcoin"                  |
| four-llms-bitcoin-gemini            | ai_response  | Gemini on "should I retire on Bitcoin"                |
| four-llms-startup-claude            | ai_response  | Claude on "should I take this startup offer"          |
| four-llms-startup-grok              | ai_response  | Grok on "should I take this startup offer"            |
| four-llms-startup-gemini            | ai_response  | Gemini on "should I take this startup offer"          |
| nvidia-q4-fy24-press-release        | financial    | NVIDIA Q4 FY2024 earnings press release (source)      |

The seeded corpus is intentionally biased toward `ai_response`
(9 entries) because that genre is the lead use case per the
methodology page AND has 4 paired same-question / different-LLM
sub-groupings that give within-genre variance for free. Plus
one financial document that pairs with its LLM summary
(grok-nvidia-q4-fy24-summary) for source-vs-summary
comparison.

**Cross-genre gaps remain.** The methodology page commits to
per-genre Spearman thresholds; with policy / journalism / other
empty, those thresholds cannot be evaluated. See
`CORPUS_GENRE_GAPS.md` for what's needed and how to add it.

## Profile generation note

Corpus profiles are computed by `curate_corpus.py` using the
structural Frame Check analyzers (coverage, voice, temporal,
epistemic, claim extraction, frame suggestions) WITHOUT invoking
the Source Network. This keeps curation offline and reproducible
without API keys, but means:

- The **evidence** dimension reports `signal_value: null` for the
  source-verification ratio. The sentence-attribution percentage
  (`signal_secondary`) still populates from the structural
  analyzer.
- The **robustness** dimension reports zero contradictions
  because no claims were checked against external sources.

A future Phase 2.5 corpus refresh will re-run the profiles with
Source Network enabled to populate the evidence + robustness
dimensions fully. For initial validation, the partial profile is
sufficient because raters score the dimensions independently of
Frame Check's signal; correlations on the missing-signal
dimensions simply have fewer data points until the refresh.

## Adding a document to the corpus

1. Create `corpus/{doc_id}/document.md` with the document text.
2. Create `corpus/{doc_id}/metadata.yaml` with at minimum:
   - `title`
   - `genre` (one of: financial, policy, journalism, ai_response, other)
   - `source`
   - `published_date`
   - `excerpt_chars` (the character range used if the doc is long)
3. Run Frame Check on the document text and save the resulting
   `display.decision_readiness` field to `corpus/{doc_id}/profile.json`.
4. Open a pull request with the new corpus entry.

Corpus entries are CC-BY-4.0 along with the rest of the Frame
Check corpus; document text excerpts are quoted under fair use.

## Inter-rater reliability

ICC (intra-class correlation) is computed across raters per
dimension. Three raters per document is the floor for measurable
ICC; more is better. When a document has fewer than three
ratings, that document contributes to per-document mean estimates
but not to ICC.

## Ground truth and limits

Expert ratings are the BEST ground truth available short of
outcome tracking. They are not perfect ground truth: experts can
disagree systematically on what decision-readiness means in their
genre. The harness reports per-genre ICC alongside per-dimension
correlation so the reader can see where rater consensus is high
versus low.

Outcome tracking (Phase 3 per the methodology page) is the longer-
term complement to expert ratings. Phase 2 ships first because the
feedback loop closes within the methodology's publication cycle;
Phase 3 takes years for outcome data to accumulate.
