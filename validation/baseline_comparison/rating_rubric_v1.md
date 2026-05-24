# Rating rubric v1 (baseline-comparison protocol)

Pre-registered before pilot. Locked when authorization for main-study execution is granted.

## Per-document, per-rater scoring

For each document, the rater reads:
1. The document itself.
2. (When applicable) The paired source text.
3. The Frame Check payload (rendered as a markdown summary the rater can read without parsing JSON).
4. The LLM baseline output.

Then scores the dimensions below. Raters are blinded to which output is from Frame Check vs. the LLM (outputs are anonymized as "Output A" and "Output B" with random assignment per document).

## H1: named-absence scoring (per document)

For each "absent framing pattern" Output A names:
- **Valid (1).** The pattern is genuinely absent from the document AND a comparable document on the same topic would address it. Rater can name a concrete example of comparable document that does.
- **Invalid-Hallucinated (0).** The pattern is named but is not coherently absent (e.g., it is present in the document; the pattern itself does not exist as a recognizable framing pattern).
- **Invalid-Present (0).** The pattern is named as absent but is actually present in the document.
- **Ambiguous (0.5).** Rater cannot reach a confident judgment; flag for adjudication.

For each "absent framing pattern" Output B names: same scoring.

Per-document H1 metrics:
- valid_count(A), valid_count(B)
- invalid_count(A), invalid_count(B)
- precision(A) = valid_count(A) / (valid_count(A) + invalid_count(A))
- precision(B) = same for B

## H2: source-fidelity scoring (per paired document)

For each numerical value Output A claims is "not in source":
- **True-positive (1).** The value is not in the source text by literal substring search (you compute this mechanically; raters do not score this — the literal-substring test is the ground truth).
- **False-positive (0).** The value IS in the source text by literal substring search.

For each numerical value Output A claims IS in source:
- **True-positive.** Value is in source.
- **False-negative (counts against A on H2).** Value is in document, A says it's in source, but it's not actually in source.

Same for B. Both ground-truths are computable from source text alone, so rater is not scoring on H2 — this dimension is mechanical. Rater only flags edge cases (e.g., rounded values; the protocol's pre-registered call is that "rounded" counts as NOT in source — only literal substring matches).

## H3: reproducibility scoring (per document)

Mechanical. For each side (A, B), compute Jaccard distance on the named-frame sets across runs 1-5. Frame Check is pre-registered to score 0 (identical runs); LLM is pre-registered to score >= 0.1 (materially different).

No rater action on H3. The dimension is structural.

## Overall response shape (qualitative, optional)

Rater names one observation per output per document:
- A pattern Output A surfaced that Output B did not.
- A pattern Output B surfaced that Output A did not.
- A pattern both surfaced but framed differently.

This is qualitative texture, not scored. Feeds into the writeup if the main study fires.

## Adjudication

Disagreements between raters on H1 (valid vs. invalid-hallucinated) are adjudicated by a third rater (you or a designated tiebreaker). Cohen's kappa is computed across the two-rater pool before adjudication; the kappa figure is reported in the results writeup whether or not adjudication is triggered.

## Output

`validation/baseline_comparison/results/<doc_slug>/rater_scores.json`:
```json
{
  "rater_id": "...",
  "rated_at_utc": "...",
  "blinding_seed": "...",
  "h1": {
    "output_a_valid": [...],
    "output_a_invalid": [...],
    "output_a_ambiguous": [...],
    "output_b_valid": [...],
    "output_b_invalid": [...],
    "output_b_ambiguous": [...]
  },
  "h3_observations": [
    "Output A surfaced X that B did not.",
    "Output B surfaced Y that A did not."
  ]
}
```
