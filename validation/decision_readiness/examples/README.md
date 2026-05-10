# Annotated rating examples

Illustrative rating files showing what GOOD, MEDIOCRE, and
INSUFFICIENT rater submissions look like for the SAME corpus
document. The contrast is the teaching: same document, three
rating styles, different validation value.

These are NOT real ratings. They are not consumed by
`run_validation.py`; they live in `examples/` deliberately so the
harness's `ratings/` directory only contains submissions from
actual raters. Each example file's `rater_id` starts with
`example-` so a future contributor copying-and-pasting would have
to consciously rename it before submitting.

## Why they exist

A new rater asks "what does a good rating actually look like?"
The README's worked example shows ONE filled file. These three
files show CONTRAST: same document, three quality levels, with
notes explaining what makes the difference.

A pedagogue teaching from this material can use the three
examples to anchor a class discussion ("which of these is more
useful for the validation effort, and why?").

## The three examples (rating the same corpus document)

All three rate `four-llms-bitcoin-claude` (Claude's response to
the question "should I retire on Bitcoin"). The document is in
the seeded corpus; raters can read it at
`../corpus/four-llms-bitcoin-claude/document.md`.

### `example-good.yaml`: what good looks like

- Numeric ratings on every dimension (no `null`s when the
  dimension applies)
- Notes per dimension that name SPECIFIC observations from the
  document (quoted phrases or numerical references)
- Overall note synthesizes across dimensions
- Time spent reflects substantive engagement (15-30 minutes)
- Self-confidence honest about ambiguous dimensions

The validation effort learns the most from this kind of rating.
Divergence cases between Frame Check's profile and a good
rater's scores are interpretable because the notes explain the
rater's reasoning.

### `example-mediocre.yaml`: common shortfall

- Numeric ratings on every dimension
- Notes are present but generic ("the document is unclear")
- No specific observations tied to the document
- Time spent is low (5-10 minutes)
- Self-confidence high, suggesting the rater did not notice
  ambiguities

This contributes to per-dimension means but is uninterpretable
on divergence. The validation effort cannot tell whether the
rater agreed with Frame Check by accident or by analysis.

### `example-insufficient.yaml`: what to avoid

- Some ratings are extreme (1 or 5) without justification
- Notes are empty strings or one word
- Time spent is unrealistically low (1-2 minutes)
- Dimensions where the rater should use `null` (e.g., evidence
  on a heavily interpretive document) instead get a guess

This degrades the validation: it adds noise to per-dimension
means, undermines ICC, and provides nothing for divergence
analysis. The harness still ingests it; the results page should
flag insufficient submissions if patterns emerge.

## How to use these for rater calibration

Before submitting their first real rating, a new rater can:

1. Read the rater_guide.md anchors
2. Read `walkthrough_four-llms-bitcoin-claude.md` (the
   profile-versus-rating walkthrough; reads the same document's
   profile.json dimension-by-dimension alongside example-good)
3. Read all three rating examples here
4. Try to articulate WHY each example illustrates its label
5. Open `corpus/four-llms-bitcoin-claude/document.md` and
   produce their own rating
6. Compare their rating against `example-good.yaml`. Differences
   are themselves informative; there is no "correct" rating,
   but there are recognizable signs of substantive engagement.

A first-time rater whose own attempt is closer to
`example-mediocre` than to `example-good` should re-read the
specific dimension anchors that they scored most superficially.
A first-time rater whose scores match the profile on every
dimension is over-trusting the automated layer; the walkthrough
shows where the gap typically falls.

## Why examples are NOT in `ratings/`

The `ratings/` directory is consumed by the validation harness.
Mixing illustrative files with real submissions would:

- Skew per-document means by my fictional ratings
- Inflate ICC by counting illustrative agreement as inter-rater
  agreement
- Make it impossible to tell from the directory contents which
  files are real

Hence `examples/` is a sibling directory the harness ignores.
The convention `rater_id: example-*` makes accidental copying
into `ratings/` more visible (a real rater_id would not start
with the literal string "example-").
