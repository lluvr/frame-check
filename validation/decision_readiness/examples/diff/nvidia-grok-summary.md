# Annotated interpretation: NVIDIA press release -> Grok summary

This is an illustrative reading of
`corpus/grok-nvidia-q4-fy24-summary/diff_with_nvidia-q4-fy24-press-release.json`.
The diff is computed automatically; this file teaches how to
READ it.

## The pair

- **Source** (`nvidia-q4-fy24-press-release`): the actual NVIDIA
  Q4 FY2024 earnings press release, 1847 characters, financial
  genre. Authoritative source for its own numbers.
- **Transformed** (`grok-nvidia-q4-fy24-summary`): Grok 4.1 Fast
  Reasoning's 200-word "neutral business-news register" summary
  of that press release, 1160 characters, ai_response genre.

The transformation kind is `llm_summary`. The diff measures what
Grok did to decision-readiness when compressing the press
release into a summary.

## Reading the diff field by field

### Coverage: 2/5 -> 2/5, same dimensions present

Both source and summary address two of five analytical
perspectives (stakeholders + trends). The summary did NOT drop
any dimension the source had. Coverage held steady.

**Substantive read:** Grok preserved the press release's
structural coverage. This is not surprising for a summary that
keeps to the source's scope; it would be a finding if a summary
LOST coverage (e.g., "Grok dropped the stakeholders dimension
when compressing"). Here, coverage is not the load-bearing
finding of the diff.

**Why coverage is only 2/5 in both:** earnings press releases
are by genre narrow. Causes (why), risks (what could go wrong),
uncertainty (what is unknown) are typically absent from a
release whose job is to communicate facts about a quarter. This
is not a Grok problem; the source itself addresses 2 of 5.

### Calibration: hedge ratio 0.00 -> 0.00, claim count 12 -> 9, Confidence Imbalance pattern emerged

This is the load-bearing finding of the diff. Three things to
read:

1. **Hedge ratio is 0.00 on both sides.** Neither the press
   release nor the summary hedges its numerical claims. This is
   genre-appropriate for a press release (record revenue,
   reaching a record, etc.) and replicated faithfully by the
   summary.

2. **Claim count fell 12 -> 9.** The summary dropped three
   numerical claims in compression. The diff does not tell us
   WHICH three; a researcher writing this up would need to
   read both texts to identify the dropped claims and assess
   whether they were load-bearing.

3. **Confidence Imbalance pattern emerged in transformation.**
   This is the key finding. The press release did NOT trigger
   FVS-002 (Confidence Imbalance); the summary did. Grok's
   summary, by compressing 12 unhedged claims into 9 unhedged
   claims, crossed the structural threshold for the pattern.
   The pattern is the canon entry teaching that confident
   prose with no hedging signals overconfidence; the SUMMARY
   reads as more overconfident than the SOURCE on this
   structural measure.

**Substantive read:** the LLM summary is structurally MORE
overconfident than the source it summarized. Not because Grok
added confident claims; because compression dropped enough
claims to cross a density threshold. A reader using the summary
for a decision would receive a structurally more decisive read
than the original source supports.

### Evidence: sentence-attribution 0% -> 10%

Sentence-attribution is the share of sentences carrying an
explicit source reference. The press release, written by NVIDIA
about itself, attributes nothing externally. The summary
attributes 10%, likely sentences that mention "NVIDIA reported"
or similar, where the LLM added attribution language that the
source did not have.

**Substantive read:** the summary is MORE attributed than the
source. A summary should not normally invent attribution; this
is worth a closer look. A researcher writing this up would
check whether Grok's added attribution is faithful (the source
IS NVIDIA) or invented (Grok wrote "according to NVIDIA" where
the source had no explicit attribution).

### Robustness: neither side had claims checked against external sources

This dimension is non-comparable for THIS PAIR. The corpus
profiles were computed without Source Network (offline curation
for reproducibility), so neither side has verification data.
The diff field is honest about this: "neither side had claims
checked."

**Substantive read:** robustness is a corpus gap, not a
finding. A future Phase 2.5 corpus refresh with Source Network
enabled would fill this in. A researcher should NOT report
"robustness held steady" for this pair; they should report
"robustness not measured."

### Counterfactual: neither side engages with counterfactual thinking

Both source and summary lack failure-framing markers and the
uncertainty dimension. Neither press releases nor LLM summaries
of them typically engage with counterfactuals; the genre
expectation is forward-looking optimism for the press release
and faithful compression for the summary.

**Substantive read:** counterfactual is held steady because both
sides have the same gap. Not a finding about the
transformation; a finding about the genre. A researcher
writing this up would not lead with "Grok lost counterfactual
engagement" because Grok had nothing to lose.

## Synthesizing the diff

What Grok did to decision-readiness when summarizing the NVIDIA
press release:

1. **Compressed the claim set** (12 -> 9 numerical claims),
   crossing the structural threshold for Confidence Imbalance.
   The summary reads as MORE overconfident than the source on
   the structural measure.

2. **Added attribution** (0% -> 10% sentence-attribution).
   Worth verifying whether the added attribution is faithful or
   invented.

3. **Preserved coverage** (2/5 in both). Compression did not
   drop a dimension the source had.

4. **No information** about robustness (corpus profiles
   computed offline) or counterfactual differences (genre-
   shared gap).

This is one pair, with one model, summarizing one source.
Generalizing to "Grok summaries always introduce overconfidence"
would be a sample-size error. The aggregate findings page
will accumulate signal across more pairs as the corpus grows.

## What this diff does NOT tell us

- Whether the THREE DROPPED CLAIMS were the most important
  ones for decision-making (the diff is dimension-level, not
  claim-level)
- Whether the ADDED ATTRIBUTION is faithful or invented (would
  require comparing the surfaced attribution against the source
  text)
- Whether Grok's summary is "good" or "bad"; the diff is
  structural; quality is a reader judgment
- Whether OTHER models would produce similar diffs on this
  source (would require more transformation pairs in the
  corpus)

The diff is a starting point for research on LLM summary
behavior, not an answer.

## What a writeup of this diff would say

> Grok 4.1 Fast Reasoning's 200-word summary of NVIDIA's Q4
> FY2024 earnings press release shows a structural shift in
> calibration not visible in the source. The press release
> contains 12 unhedged numerical claims; Grok's summary
> compresses to 9 unhedged claims, crossing the density
> threshold for the Confidence Imbalance pattern (FVS-002).
> Coverage of analytical perspectives held steady (2 of 5 on
> both sides, both addressing only stakeholders and trends).
> Sentence-level attribution increased from 0% to 10%; whether
> the added attribution language is faithful to the source or
> introduced by the model is a follow-up investigation.
> Robustness and counterfactual dimensions are not informative
> for this pair (robustness pending Source Network re-run;
> counterfactual is genre-absent on both sides).
>
> Cited from the Frame Check decision-readiness corpus,
> revision `70e2a95a9d1f`.
