---
title: Grok summarises NVIDIA earnings: what Layer 4 verification shows when an LLM paraphrases a source
slug: grok-on-nvidia-earnings-2026
author: Lovro Lucic
published: 2026-04-18
source_document_url: https://github.com/lluvr/frame-check/tree/master/data/worked_examples/grok-on-nvidia-earnings-2026
source_document_title: Grok 4.1 Fast Reasoning summary of NVIDIA Q4 FY2024 earnings press release (2026-04-18)
source_document_author: xAI Grok 4.1 Fast Reasoning (`grok-4-1-fast`)
source_document_type: LLM summary of a public financial press release, analysed against the original source material as source_text
ground_truth_source_url: https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-fourth-quarter-and-fiscal-2024
ground_truth_source_title: NVIDIA Announces Financial Results for Fourth Quarter and Fiscal 2024 (press release, 2024-02-21)
ground_truth_source_author: NVIDIA Corporation
frames_detected: [FVS-008, FVS-002, FVS-001, FVS-007]
featured: true
domain: finance
verification_summary: "Layer 4 source_fidelity ratio 92 percent (23 of 25 numbers appear as literal digit substrings in the source). Two numbers did not literal-match, both fiscal-year labels that paraphrase 'a year ago' as 'Q4 of fiscal 2023'. Grounding decomposition: 80 percent grounded, 10 percent fabricated, 10 percent projection; scope_assessment regime saturated, so the source-fidelity rate is the authoritative reading on numerical claims and sentence-level grounding is supplemental."
hook: The sovereignty instrument's distinguishing capability is that it checks a document against the source it should be grounded in. This is the first worked example to use that capability end-to-end, on an LLM summary of a real public press release.
---

## Context

The existing worked examples (life decisions, institutional policy,
AI-company manifesto) all analyse a document as a self-contained
artifact. None of them uses Frame Check's `source_text` argument,
which unlocks the Layer 4 source-fidelity verification and the
Layer 11 grounding decomposition. Those two layers are the
capability that separates Frame Check from framing-only tools:
other instruments can tell you a document reads as promotional;
Frame Check can also tell you whether the numbers in a document
literal-match the source those numbers were supposed to come from.

This example runs that end-to-end. A real public press release
(NVIDIA's Q4 fiscal 2024 earnings announcement, 2024-02-21) was
captured verbatim. An LLM (xAI Grok 4.1 Fast Reasoning) was
asked, using a deliberately plain prompt ("Write a 200-word
news-style summary of this press release for a general business
audience. Stick to the numbers in the source. Use a neutral
business-news register."), to produce a summary of that release.
Frame Check's deterministic engine was then invoked with the
Grok summary as `document_text` and the captured press release
as `source_text`.

The full exchange, the captured source bytes, the SHA-256
content hashes of both, the invocation timestamp, and the
Frame Check payload are stored as
`data/worked_examples/grok-on-nvidia-earnings-2026/data.json`
alongside this writeup. A reader can load that file, re-run
Frame Check's deterministic layer against the stored bytes,
and reproduce the measurements exactly.

## What Frame Check saw

The Grok summary is 184 words, 10 sentences. The structural
signature from the deterministic detectors:

- **Voice: promotional.** The prompt asked for a "neutral
  business-news register." The detector flagged the result as
  promotional anyway, because the summary inherits the press
  release's own vocabulary ("record," "reached a record," "hit
  a record," "surging demand") and amplifies it. This is the
  teaching point of FVS-001 and FVS-008 together: the opening
  frame of the source becomes the opening frame of the summary,
  and the summary extends rather than audits that frame.

- **Analytical coverage: 2 of 5.** Stakeholders (density 9.8 per
  1,000 words) and trends (density 9.8) are addressed. Causes,
  risks, and uncertainty are absent. A press-release summary is
  inherently event-reporting, not analysis, so the coverage
  footprint is genre-appropriate. A reader should not expect
  risk coverage from a company's earnings announcement and
  should not expect its summary to add risk where the source
  contained none.

- **Temporal orientation: 50 percent past, 50 percent present,
  zero percent future (dominant: present).** The register of
  quarterly reporting: past-tense facts about what was earned,
  present-tense statements about what is recorded.

- **Sourcing: 10 percent.** One of ten sentences carries an
  explicit attribution ("CEO Jensen Huang stated"). The other
  seven numerical sentences assert figures without naming them
  as NVIDIA's own reporting; the reader has to infer the
  attribution from the first sentence.

### Source fidelity: what Layer 4 sees

The novel surface for this example. The deterministic verifier
compared every number in the Grok summary against the captured
source material:

- **Total numbers in summary: 25.**
- **In source: 23.** Each of these numbers appears as a literal
  digit substring in the press release.
- **Not in source: 2.** These do not match any digit substring
  in the source.
- **`unsourced_rate: 0.08`** (8 percent). Inverted: 92 percent
  of the numeric claims in the LLM summary pass a digit-level
  fidelity check against the source.

Reading by eye, the two non-matching numbers are both fiscal-year
labels that paraphrase the source's "a year ago" as "Q4 of
fiscal 2023." The literal string "2023" does not appear in the
source. This is an honest limit of the digit-level match: a
legitimate paraphrase ("a year ago" becoming "fiscal 2023") can
fail the match even when the summary's claim is correct in
substance. The method's note says this explicitly: "A number
'not_in_source' does not appear as an exact digit substring in
the source. Those claims may be derived, rounded, or fabricated."
`unsourced_rate` is a conservative floor on drift, not a verdict.

The Layer 11 grounding decomposition returns `G=0.80, F=0.10,
P=0.10`: 80 percent of sentences read as grounded, 10 percent
as fabricated, 10 percent as projection. The `scope_assessment`
reports `derivation_regime: "saturated"` with a user-facing note:
*"Sentence-level grounding is supplemental on number-dense
sources. For numerical claims, the source-fidelity match is
authoritative."* That is the measurement layer telling the
reader which of its own signals to trust here. Press releases
are number-saturated; Layer 11's sentence-level signal is
noisy in that regime; the source-fidelity rate is the reading
to carry into the writeup.

## Frame detections

Four frames from the Frame Vocabulary Standard flagged by the
library matcher:

- [FVS-008 Growth Frame](/corpus/library/FVS-008.html). The
  document reasons within growth vocabulary (record, reached a
  record, surging, up 265 percent, tipping point). The library
  entry's teaching question: *"What would a risk analyst say
  about this same data?"* The Grok summary stayed inside the
  press release's growth frame and did not ask that question.

- [FVS-002 Fluency-Quality Illusion](/corpus/library/FVS-002.html).
  The polished prose ("hit a record," "soared 409 percent,"
  "stood at") reads as authoritative. The library entry's
  teaching question: *"If this were written in rough notes
  instead of polished prose, would you still accept the frame?"*
  The Grok summary is polished; the frame would be less
  convincing without the fluency.

- [FVS-001 Frame Amplification](/corpus/library/FVS-001.html).
  The summary opens with "Record Q4 Revenue of $22.1 Billion,
  Up 265% Year-Over-Year" and every subsequent section extends
  that frame. The library entry asks: *"Is the increasing
  detail evidence of quality, or evidence that the analysis is
  locked in one frame?"* The Grok summary never steps outside
  the revenue-growth frame.

- [FVS-007 Failure Framing (absent)](/corpus/library/FVS-007.html).
  The summary asserts records and growth without addressing
  what would make the interpretation wrong. The library entry
  asks: *"What would have to be true for this analysis to be
  wrong?"* Candidate answers the summary does not touch: a
  demand cycle turning, concentration risk among a small set of
  cloud customers, supply-chain exposure, export-control shock,
  the arithmetic of year-over-year comparisons on a low base.
  None of these are hidden; the source itself omits them, so
  the summary inherits the omission and the detector flags the
  pattern.

## What is visible in the summary that the measurements point at

The measurements point at structure; the reader reads the text
against the structure. Three specific patterns:

- **The summary inherits the source's frame wholesale.** The
  prompt asked for a "neutral business-news register." The
  result carries every superlative in the source ("record,"
  "surging") and adds one of its own ("hit a record"). An LLM
  summarising a promotional document without an explicit counter-
  frame in the prompt will, by default, echo the promotional
  voice. Frame Check's voice classification catches the echo;
  the reader sees that the prompt's asked-for neutrality did
  not survive.

- **Numerical fidelity is high but not perfect.** 92 percent
  grounded is a strong number. It is not 100 percent. On a
  financial summary where the entire point is the numbers, the
  reader should know what drifted and why, even if "drifted"
  here means "legitimate paraphrase that fails a literal string
  match." The source-fidelity rate names the boundary; the
  reader does the forensics.

- **Coverage absence is genre-determined, not LLM-failure.** A
  press release does not discuss causes, risks, or uncertainty.
  The summary does not either. Frame Check flags the absence
  structurally; the reader distinguishes "absent because the
  source omitted it" from "absent because the summariser
  dropped it." Here, it is the former. That is a distinction
  the detector cannot make; the worked example makes it for
  the reader.

## What the method caught and what the method missed

- **Caught: voice drift under a neutrality prompt.** The prompt
  explicitly asked for a neutral register. The result was
  promotional. The voice classifier, a deterministic detector
  with no knowledge of the prompt, flagged the register
  honestly.

- **Caught: frame amplification and growth framing.** Four
  frame matches is a strong signal set; each carries a
  teaching question that generalises beyond the specific
  document.

- **Caught at scope level, read with care: source fidelity
  regime.** The scope_assessment block explicitly warned that
  the source is number-dense ("saturated" regime) and that
  sentence-level grounding should be treated as supplemental.
  The authoritative reading on numbers is the 92 percent
  source-fidelity rate, not the 80 percent sentence-level
  grounding rate. A reader ignoring the regime note and citing
  the grounding rate alone would overstate fabrication.

- **Missed at detector resolution: the two non-matching numbers
  are paraphrases, not fabrications.** The digit-match is
  literal. "Fiscal 2023" is a correct paraphrase of "a year
  ago" in the context of fiscal 2024 reporting. The detector
  flags it as non-matching because "2023" is not in the source.
  A human reviewer restores the correct reading. `unsourced_rate`
  is a conservative floor on drift, not a verdict; the worked
  example exists partly to name that boundary explicitly.

- **Missed by definition: whether the source itself is
  accurate.** Frame Check's Layer 4 asks only "does the document
  match the source?" not "is the source truthful?" A false
  press release summarised faithfully produces a high
  source-fidelity score. That is the intended scope: Frame
  Check audits fidelity to source, not source itself. The
  corpus's calibration evidence pages document this boundary
  for cited use.

## Why this example is worth publishing

Because source fidelity is the capability no other framing tool
has, and the worked-example corpus did not previously demonstrate
it. An agent calling `frame_check` with a `source_text` argument
gets a reading that framing-only tools cannot produce. This
example is the first worked walkthrough of that reading.

The sovereignty case carries through. An agent summarising a
document the user pasted in, or paraphrasing a source it
retrieved, can invoke `frame_check(document_text=summary,
source_text=original)` on its own output and surface a
source-fidelity rate to the user. The user sees what share of
the numbers in the agent's summary literal-match the material
the agent claimed to ground in. If the rate is high, the
summary is faithful; if low, the summary drifted. The user
decides what to do with the seeing, same as in the life-decision
worked examples; the measurement substrate is different.

The compounding path: the next worked examples in this strand
would apply the same pattern to cases where an LLM summary
actually drifts substantively from the source. The NVIDIA case
is a near-best-case scenario (92 percent fidelity) that
establishes the baseline reading; cases with lower fidelity
would test what the surface looks like when the summary and
source diverge.

## Reproducing this analysis

The captured source bytes, the captured Grok summary bytes,
the SHA-256 hashes of both, the invocation timestamp, the
model ID, the summarization prompt verbatim, and the full
Frame Check payload are in
`data/worked_examples/grok-on-nvidia-earnings-2026/data.json`.
A reader can run Frame Check's deterministic layer against
the stored source and summary texts and reproduce the
measurements exactly.

Re-running the same summarization prompt against Grok six
months from now will produce different summary text; the
model drifts, the measurements against today's captured
summary do not. This is the reproducibility contract the
content-hash field supports.

## Citation

Lucic, L. (2026). *Grok summarises NVIDIA earnings: what Layer
4 verification shows when an LLM paraphrases a source*. Frame
Check Worked Examples.
frame.clarethium.com/corpus/worked-examples/grok-on-nvidia-earnings-2026/

Licensed CC-BY-4.0. The press release analysed is the public
property of NVIDIA Corporation. The Grok summary is the output
of a third-party system (xAI Grok 4.1 Fast Reasoning). Both
are reproduced here for structural analysis and fall under
fair-use / fair-dealing provisions for research and criticism.
Only the Frame Check analysis is open-licensed.
