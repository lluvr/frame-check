# Annotated peer-comparison interpretations

Pedagogical material for reading the
`corpus/{slug}/peer_with_{partner}.json` outputs produced by
`compute_peer_comparisons.py`. Same convention as the diff
examples and the rating examples: ILLUSTRATIVE, not consumed
by any harness.

## Why annotated peer examples exist

Peer comparison answers a question no other tool publishes:
how do four different LLMs differ structurally on the SAME
question? But the per-pair outputs are easy to misread:

- A reader might see "differs on calibration" as a verdict
  ("one peer is better than the other")
- A reader might over-generalize from one pair to claims about
  the LLM in general ("Claude is more hedged than Grok")
- A reader might miss what the dimensions DO NOT capture
  (the comparison is structural, not semantic)

The annotated examples teach how to read a peer comparison
HONESTLY: as a structural snapshot of two specific responses
to one specific question, not as a model verdict.

## Example: Claude vs Grok on the bitcoin retirement question

The first peer comparison annotation is at
`claude-vs-grok-bitcoin.md`. It walks the comparison field by
field, distinguishes substantive findings from artifacts of
the comparison method, and shows what a researcher would
write up.

A reader who understands this example can then read any other
peer comparison in the corpus and the aggregate findings.

## What a "good" peer interpretation looks like

- Names the comparison's specific subject (this question, this
  prompt, these two specific LLM responses)
- Reads each per-dimension comparison_text in plain language
- Distinguishes "differs because data not available" from
  "differs because peers measurably disagree"
- Names what the comparison cannot tell us (one pair, one
  question, no ground truth)
- Connects to aggregate findings when relevant ("calibration
  differs in this pair AND in 12 of 12 pairs across the corpus,
  so this is a robust corpus-level pattern")

## What a "bad" peer interpretation looks like

- Treats the comparison as a model verdict ("Claude is better
  than Grok at retirement advice")
- Generalizes from one pair to claims about LLM behavior
  ("Claude consistently hedges more than Grok")
- Conflates "non-comparable" with "agrees" (e.g., "robustness
  agrees" when actually robustness was not measured)
- Skips the dimensions the comparison says are non-comparable
  without noting why
