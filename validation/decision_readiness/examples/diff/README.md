# Annotated transformation-diff interpretations

Pedagogical material for reading the
`corpus/{slug}/diff_with_{partner}.json` outputs produced by
`compute_pair_diffs.py`. Same convention as the rating
examples: ILLUSTRATIVE annotations that show how to interpret
the diff artifact, NOT consumed by any harness.

## Why annotated diff examples exist

A researcher landing on a `diff_with_*.json` file for the first
time sees per-dimension change_text and a synthesized narrative.
They know what each FIELD means (the methodology page documents
the schema). What they do not know yet is how to READ the diff
substantively: which findings are load-bearing, which are
artifacts of the curation method, which are interpretively
ambiguous.

The annotated examples teach this. A new researcher reads the
annotation, then opens the actual diff file, and learns to read
the artifact for themselves.

## Example: NVIDIA press release -> Grok summary

The first transformation pair in the corpus is the NVIDIA Q4
FY2024 earnings press release as the source and Grok 4.1 Fast's
200-word summary as the derived. The annotation lives at
`nvidia-grok-summary.md`. It walks the diff field by field and
explains:

- What the per-dimension change_text means in plain language
- Which findings reflect substantive transformation effects
- Which findings reflect curation-method limitations (no Source
  Network, so robustness is not measurable)
- What a researcher would write up about this transformation
- Where the diff is silent and why

A reader who understands this example can then read any other
source-vs-summary diff in the corpus.

## What a "good" diff interpretation looks like

- Names specific numbers from the diff (not "calibration
  changed" but "hedge ratio went 0.00 -> 0.00 but claim count
  fell 12 -> 9")
- Distinguishes substantive movement from non-comparable
  dimensions
- Connects the structural finding to the underlying
  methodology (Confidence Imbalance pattern is FVS-002; here is
  why it fired here)
- Acknowledges what the diff cannot tell us (e.g., whether
  the dropped claims were the most important ones)
- Points the reader at the source documents so they can
  verify the structural finding against the actual texts

## What a "bad" diff interpretation looks like

- Treats the synthesized narrative as a verdict ("Grok degraded
  the document")
- Generalizes from one pair to all LLMs ("LLMs always introduce
  Confidence Imbalance when summarizing")
- Skips the non-comparable dimensions silently
- Re-paraphrases what the change_text already says without
  adding interpretation
