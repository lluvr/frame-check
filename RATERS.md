# Becoming a Frame Check Phase 2 Rater

**Status:** Open invitation. v0 shipped 2026-04-20.
**Curator:** Lovro Lucic (curator@frame-check; contact details at bottom).
**Companion documents:** `REVIEWERS.md` (library canon promotion review,
distinct from rating), `validation/decision_readiness/rater_guide.md`
(operational guide once you accept), `validation/decision_readiness/`
(scaffolding tree).

---

## What this document is

An open invitation and a contract-in-plain-prose for the Phase 2
expert validation of Frame Check's decision-readiness profile. The
profile lives at https://frame.clarethium.com/corpus/decision-readiness/
with explicit `experimental` status pending Phase 2 results. Without
external raters, the profile stays experimental indefinitely and the
methodology cannot be cited as validated.

**Phase 2 ratings are different from library canon review.**
`REVIEWERS.md` describes review of individual library entries
(FVS-XXX) for canon promotion: prose review, 12-20 hours per entry.
**This document describes per-document rating for the
decision-readiness profile validation:** YAML scores on five
dimensions, 30-60 minutes per document. Different review target,
different deliverable shape. The same person can do both at
different times; commitments are independent.

This document describes what a rater is signing up for, the honest
state of what they would be rating against, the deliverable shape,
the terms, and what changes after Phase 2 ships.

**Rating target.** Frame Check's per-document decision-readiness
profile, computed from existing structural signals and composed
into five dimensions (coverage, calibration, evidence, robustness,
counterfactual). The methodology page describes each dimension
with operational definitions and 1-5 anchor descriptions. The
rater scores each dimension 1-5 against those anchors, blind to
the profile's computed values.

---

## The honest state of what you would be rating against

The profile is **methodology published, computation shipping in
JSON-only mode, validation pending.** You should know what is and
is not validated before you sign on:

- **Methodology validity:** The five dimensions are documented in
  the methodology page, grounded in decision-theory literature
  (Kahneman, Tversky; calibration corpus; confirmation bias
  literature). The choice of dimensions is curatorial and
  reviewable; alternative decompositions are possible.
- **Per-dimension signals:** Computed from existing Frame Check
  measurements (perspective coverage, claim hedging, source
  verification, contradictions, named structural patterns from
  the Frame Vocabulary Standard library). Each dimension's
  signal is a proxy. The methodology page documents the proxy
  chain explicitly.
- **What Phase 2 measures:** Spearman rank correlation between
  expert-mean ratings and the profile's computed signals, per
  dimension, across the rated corpus. ICC across raters per
  document. Per-genre breakdown.
- **Threshold for "validated":** Per-dimension Spearman >= 0.6
  averaged across genres, with no individual genre below 0.4.
  The thresholds are explicit choices documented on the
  methodology page; they are revisable in light of Phase 2
  results.
- **What happens if validation fails:** A dimension that does
  not correlate with expert judgment is either rewritten (proxy
  chain revised), demoted (kept as a sub-signal but not surfaced
  as a dimension), or removed. Phase 2 results are published
  regardless of outcome. The negative result is informative.

Rating is therefore a real epistemic act. A rater who gives 5/5
on every dimension regardless of document substance is not
helpful; a rater who finds the documents genuinely uneven on the
dimensions, and whose ratings differ from Frame Check's profile,
is exactly what the validation needs.

---

## What a rating is for

The deliverable is one YAML file per document, scoring each of
the five dimensions on a 1-5 scale with per-dimension notes.

The aggregate purpose of a rating is to test whether Frame
Check's structural signals correlate with expert judgment about
the same documents on the same dimensions. A rater is providing
the human-judgment ground truth that the structural proxy is
being calibrated against.

The shape of the deliverable is structured (1-5 ordinal, per
dimension, per document) so the cross-rater aggregate produces
a number Spearman can consume. Notes are required because the
notes are how the validation effort learns where the profile
and the rater diverge: a divergence with a note ("the document
addresses risks but only at the very end, after pages of
growth-only framing") is far more informative than a bare
divergence.

---

## Candidate profile

A useful Phase 2 rater satisfies most of:

- **Domain expertise in at least one of the rated genres.** The
  v1 corpus spans AI responses, financial analysis, and policy
  briefs (with planned expansion to journalism and academic
  essays). A rater is not expected to be expert in every genre;
  ratings are filtered to the rater's declared expertise.
- **Comfort with structured rating.** A rater who can read the
  rater_guide, rate three documents in one sitting, and produce
  consistent ratings across them is doing the job. The work is
  repeatable rather than essayistic.
- **Tolerance for the methodology's limitations.** The profile
  is structural, not predictive. A rater who insists Frame Check
  should rate the document's CONCLUSIONS rather than its
  STRUCTURE is not aligned with the methodology and will produce
  noise.
- **Willingness to disagree with the profile.** The validation
  is informative when raters and the profile diverge. A rater
  who tries to "match" the profile (which they should not see
  before rating, but might guess) is not helpful.
- **Time for 5-10 documents minimum** at 30-60 min each. Enough
  documents per rater to produce a meaningful per-rater
  consistency check.

Anti-pattern raters:

- A rater who would refuse to rate any document below 3 because
  the document "isn't bad" (confuses ratings with verdicts).
- A rater who would rate every dimension based on a single
  reading-impression rather than scoring per the operational
  definitions.
- A rater whose per-rating notes are 1-2 words. Notes are how
  the validation effort learns; sparse notes break the learning.

---

## What a rating deliverable looks like

```yaml
doc_id: four-llms-bitcoin-claude
rater_id: jdoe-acad
rated_at: 2026-05-15T14:30:00Z
genre_expertise:
  - ai_response
  - financial
ratings:
  coverage: 3
  calibration: 4
  evidence: 2
  robustness: null   # null when the dimension does not apply
                     # (e.g., no numerical claims to source-verify)
  counterfactual: 2
notes:
  coverage: |
    Addresses growth and risks but treats stakeholders only as
    a one-line aside. Trends absent. Causes covered tangentially.
    3/5 reflects two perspectives substantively addressed; the
    others are nominal.
  calibration: |
    Hedge usage is appropriate to the speculative nature of the
    bitcoin question. The few unhedged claims (e.g., "bitcoin is
    digital gold") are genre-appropriate metaphor rather than
    overconfidence. 4/5.
  evidence: |
    Cites no specific sources. The claims are presented as the
    LLM's analysis without source attribution. 2/5; would be 1
    if the LLM had cited fabricated sources.
  robustness: null   # see above
  counterfactual: |
    Does not engage with the case where bitcoin retirement
    fails. Mentions risks once but does not develop them into
    counterfactual scenarios. 2/5.
  overall: |
    Document is a typical LLM advisory response: structured,
    confident, narrow in framing. The dimensions land
    consistently on the medium-low end except calibration.
```

Each rating file is a YAML document the harness consumes via
`run_validation.py`. The template is at
`validation/decision_readiness/rating_template.yaml`. Sample
annotated examples are at
`validation/decision_readiness/examples/example-good.yaml` etc.

The deliverable is one file per document. A rater committing to
five documents produces five files, named
`ratings/{doc_id}/{rater_id}.yaml`.

---

## Terms

The terms a rater agrees to when starting a rating commitment.

**Time commitment.** Estimated 30-60 minutes per document for
first-pass rating, plus 5-10 minutes review of the rater_guide
before starting. A rater committing to 5 documents commits 3-6
hours total, concentrated as the rater chooses (one sitting or
spread). Most raters will do one document, then a batch of 4-9
once the rater_guide patterns are internalized.

**Scope.** A rater commits per-batch (typically 5-10 documents).
A rater can accept a second batch; declining the second does
not unwind the first. A rater is not committing to rate every
document in the corpus; the corpus exceeds any individual
rater's bandwidth.

**Compensation.** The Phase 2 effort uses the same compensation
options REVIEWERS.md describes for canon review, scaled to the
rating commitment shape:

- *Volunteer with named attribution.* Zero cash. Rater's name
  and rating dates recorded in the corpus's rater registry.
  Cited in the v1 validation paper as a contributing rater.
  Fits open-source convention.
- *Per-batch honorarium.* Flat fee per batch of 5-10 documents,
  $200-$500 range. Signals the project takes the rater's time
  seriously.
- *Co-authorship on v1 validation paper.* Raters who
  substantively shape the validation work (e.g., contribute
  20+ ratings, contribute a per-genre breakdown analysis, or
  identify a methodology issue that revises the profile) are
  named as co-authors on the validation paper.
- *Hybrid.* Honorarium plus paper acknowledgment for first-wave
  raters; volunteer with named attribution for subsequent
  raters once the validation paper is published.

Recommendation: hybrid for the first 8-12 raters whose ratings
anchor the per-genre Spearman estimates; volunteer with named
attribution for subsequent raters. The curator decides.

**Attribution.** The rater's name and the rating dates are
recorded in the corpus's rater registry. Academic affiliation
may be included at the rater's option. Anonymous ratings are
NOT accepted: the validation effort relies on the rater being
identifiable as an expert in the declared genre, and the
correlation analysis would be uninterpretable without rater
identity.

**Editorial independence.** The rater's deliverable is theirs.
The curator does not edit substantive ratings; the curator may
ask for clarification (e.g., a rating with insufficient notes)
or request additional context (e.g., rating a 1 without
explaining why). If the rater and the profile disagree, both
are published; the divergence is the most informative result.

**Public exposure.** Ratings and rater identity are published
publicly with the validation results. A rater who later wants
their ratings removed is asking to retract published research;
the ratings can be anonymized but not deleted (the validation
paper cites the aggregate).

**Non-exclusivity.** A rater is not committing to future
batches. Each engagement is per-batch.

**IP.** Ratings are CC-BY-4.0 (same as the corpus). The rater
retains copyright in their own name with the CC-BY license
granted to the project and to the public.

**Quality expectations.** A rating with sparse notes (less than
1-2 sentences per dimension) is incomplete. The curator can ask
for revision. If the rater finds the document genuinely
uniform across dimensions and gives the same score to all five,
the uniform-rating finding is publishable as the rating, with
the rater's argument for why.

**Blinding.** The rater MUST NOT read Frame Check's computed
profile for the document before rating. The profile lives in
`corpus/{doc_id}/profile.json`. Reading it before rating
invalidates the rating for correlation purposes (the rater is
no longer providing independent ground truth). After rating,
the rater is welcome to compare their ratings to the profile
and contribute observations (e.g., "I rated coverage 3 but the
profile signal is 4; the difference is that the profile counts
markers and I count substance").

---

## What this offer is NOT

- **Not a job.** This is a research collaboration with named
  attribution, optionally compensated. Not employment.
- **Not a free certification of Frame Check.** A rater's
  participation does not endorse the profile. The validation
  result publishes whether the dimensions correlated with
  expert judgment; that result is the endorsement (or the
  retraction).
- **Not a peer review of a journal submission.** Phase 2
  validation produces data; the validation paper is written
  AFTER Phase 2 ships. A rater who wants to be involved in
  drafting the paper itself can opt in; that is a separate
  commitment shape.
- **Not a binding judgment on AI quality.** Frame Check rates
  STRUCTURAL signals in documents (which may or may not be AI
  output). The rater is not endorsing or rejecting any specific
  AI provider.

---

## How to engage

1. **Read the methodology page** at
   https://frame.clarethium.com/corpus/decision-readiness/
   to confirm the framework matches what you are willing to rate
   against.
2. **Read this document** (RATERS.md) in full for the contract.
3. **Read** `validation/decision_readiness/rater_guide.md`
   for the operational rating guide.
4. **Read** at least one annotated example at
   `validation/decision_readiness/examples/example-good.yaml`
   so you see what a rated YAML looks like. The companion
   walkthrough at
   `validation/decision_readiness/examples/walkthrough_four-llms-bitcoin-claude.md`
   reads the same document's profile.json dimension-by-dimension
   alongside the example-good rating, showing what the profile
   reports versus what a rater would evaluate.
5. **Pick a batch size** (5-10 documents) and a genre focus
   (AI responses, financial analysis, policy, journalism,
   academic essay, mixed).
6. **Contact the curator** (see below) with: your name, your
   genre expertise, your committed batch size, your preferred
   compensation option from "Terms" above.
7. **The curator responds within one week** with the assigned
   document set and the agreed compensation. If the curator
   declines (e.g., rater profile mismatch or current batch
   capacity reached), the curator says so explicitly with a
   reason.
8. **Rate one document first** to validate the workflow before
   committing to the full batch. The first rating has a 1-week
   feedback turnaround from the curator (style notes, missing
   context). The rest of the batch follows once the workflow
   is settled.
9. **Submit ratings** as a GitHub pull request adding your
   YAML files to `validation/decision_readiness/ratings/`.
   Public-facing repository: https://github.com/lluvr/frame-check.

---

## What declining looks like

A rater who reads this document and decides not to engage is
welcome to:

- Decline silently (no action required).
- Send a brief decline note with reasons. The reasons are
  informative even when negative; they help the curator improve
  this invitation document and the methodology page.
- Recommend alternative candidates. The curator gratefully
  accepts pointers to potential raters; recommendations are
  not attributed unless the recommender wants to be named.

Declining one batch does not preclude future engagement. The
invitation remains open.

---

## What changes after Phase 2 ships

When Phase 2 reaches the per-dimension Spearman thresholds
documented on the methodology page, the profile transitions
from `status: experimental` to `status: validated`. At that
point:

- The decision-readiness profile becomes a live signal in the
  product UI surface (currently JSON-only per the methodology
  page's UI gate).
- The validation paper is written and submitted (the rater
  registry is the contributor list).
- The rater registry becomes a permanent citable record. New
  raters joining post-validation are working on the v2 corpus
  expansion (60-100 documents) toward tighter per-genre
  confidence intervals.

A rater who joined Phase 2 is a contributor to the validation
paper. A rater who joins post-validation is a contributor to
the v2 expansion.

---

## How to reach the curator

GitHub: open an issue at
https://github.com/lluvr/frame-check/issues with the title
prefix `[phase-2-rating]` and a brief expression of interest.
The curator monitors this label.

Email: curator@frame.clarethium.com (curator monitors weekly).

For sensitive context (e.g., rater preferring to discuss
compensation privately before the public PR), email is the
right channel. For everything else, the GitHub issue is
preferable because it creates a public record of the
recruitment funnel that other prospective raters can read.

---

## Honest limits of this document

This is a v0 invitation contract. It is the curator's best
attempt at the contract shape; it has not been reviewed by
external raters. The compensation options are the curator's
proposal; the actual recommendation depends on what
prospective raters say is fair.

If you read this document and find a term confusing or
inadequate, telling the curator is the highest-value
contribution before any rating begins. The contract evolves
in response to what raters say it needs.

The curator will revise this document in response to:

- The first 2-4 raters' feedback on terms, deliverable shape,
  and compensation calibration.
- Any rater who declines and explains why.
- Methodology revisions in light of Phase 2 results that
  require rating-shape changes (e.g., a dimension demoted or
  rewritten changes the rater_guide and therefore this
  document).

Each revision is dated at the top. The current version is v0
(2026-04-20).
