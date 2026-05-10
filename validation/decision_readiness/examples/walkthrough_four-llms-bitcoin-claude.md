# Profile-versus-rating walkthrough: four-llms-bitcoin-claude

This is the third pedagogical surface for new raters, alongside
`rater_guide.md` (the rubric) and the three `example-*.yaml` files
(what GOOD, MEDIOCRE, and INSUFFICIENT rating styles look like).
It walks one corpus entry's `profile.json` end-to-end and shows
what the Phase 2 rater is actually being asked to evaluate.

The corpus entry is `four-llms-bitcoin-claude`: Claude's response
to "should I retire on Bitcoin." Read the source first at
`../corpus/four-llms-bitcoin-claude/document.md` (one screen of
text). Then read the profile alongside this walkthrough.

The illustrative GOOD rating for this same document is in
`example-good.yaml`. This walkthrough cites those scores so a
rater can see the gap between the profile's automated dimension
calls and a substantive human reading.

## What the profile is

`profile.json` carries the decision-readiness profile that Frame
Check computes for each corpus entry. Five dimensions, each with
an automatic `signal_value`, a short `signal_text`, an
`explanation` of what the dimension measures, and the library
entries that did or did not fire on the document
(`fired_library_entries` is a strict subset of `library_entries`).

The Phase 2 rater is asked to read the same document and rate
the same five dimensions on a 1-to-5 scale (or `null` if the
dimension does not apply). The rater is **not** rating the
profile itself; they are producing an independent reading. The
divergence between the profile and the rater is the validation
signal.

## Dimension 1: Coverage

**Profile reports.** `signal_value: 1`, `signal_text: "1 of 5
perspectives addressed."` Of the five analytical dimensions
(causes, risks, stakeholders, trends, uncertainty), the
detector found markers for one. `fired_library_entries` lists
two FVS frames as having fired against this document; six others
in the dimension's library map did not.

**What the rater (example-good) gave.** `coverage: 4`. Notes:
"Addresses risks (volatility, concentration, regulatory)
explicitly. Stakeholders implied (35-year-old, savers with
diversified portfolios). Causes (why Bitcoin is volatile) are
present but lighter than risks. Trends not addressed."

**The gap.** Wide. The profile fires on one dimension; the rater
sees four. This is the canonical under-detection case the
methodology page documents: the regex-based detector measures
vocabulary, not meaning. "50%+ swings aren't unusual" reads as
risk to a human; the detector does not have a marker for it.

**What the rater is evaluating.** Whether the document does, in
substance, address the analytical dimensions a decision-grade
reading would need. The rater's score is calibrated to meaning;
the profile's signal is calibrated to vocabulary. The validation
asks: how often, and in which directions, do they disagree?

## Dimension 2: Calibration

**Profile reports.** `signal_value: 0.0`, `signal_text: "0 of 4
claims hedged."` Four claims extracted, none of them hedged in
the detector's sense. `confidence_imbalance_fired: False`.

**What the rater gave.** `calibration: 4`. Notes: "Hedging is
appropriate to a personal-decision context. 'I'd lean toward'
frames the recommendation as opinion, not prescription. Specific
quantitative anchors ('50%+ swings,' '2-5% of portfolio') are
stated as facts but are common-knowledge ranges in finance.
Predictions ('could shift') are appropriately conditional."

**The gap.** Wide and instructive. The detector's claim-hedging
heuristic does not catch the document's overall hedged frame
("I'd lean toward no") or context-appropriate confidence on
common-knowledge ranges. The rater's note explicitly anticipates
this: "Framecheck's 'Confidence Imbalance' pattern would be a
false positive on this document."

**What the rater is evaluating.** Whether the document's
confidence is calibrated to what the underlying evidence
supports, in the genre the document is in. A personal-finance
chat answer is not a research paper; a research paper is not a
press release. Calibration is genre-relative; the detector is
genre-blind by design.

## Dimension 3: Evidence

**Profile reports.** `signal_value: None`, `signal_text: "No
numerical claims to verify against sources. 0% of sentences
attributed to sources."` Source Network was not run for this
profile (the corpus entry's metadata records this:
`curation_note: "Profile computed without Source Network"`).

**What the rater gave.** `evidence: 2`. Notes: "Almost no source
attribution. Two stars rather than one because the reasoning is
internally consistent and aligned with mainstream finance
literature, even if the document does not cite it."

**The gap.** Both signals point in the same direction (low
evidence backing). The rater is more generous because they can
recognize "this is consistent with the field" without a
citation; the profile cannot.

**What the rater is evaluating.** Whether the document's claims
are traceable to sources a reader can check. Source Network
would automate part of this if the corpus entry had run with it
enabled. The rater fills the gap and adds the qualitative read
(consistency with field knowledge) the automated layer cannot.

## Dimension 4: Robustness

**Profile reports.** `signal_value: 0`, `signal_text: "No claims
checked against sources."` Same Source Network gap as above.

**What the rater gave.** `robustness: null`. Notes: "Null because
the document has no checkable numerical claims in the strict
sense. '50%+ swings' and '2-5% allocation' are range statements,
not point claims. Robustness rating would require checking
specific numbers against external sources; there are none to
check."

**The gap.** The profile reports zero; the rater says
not-applicable. This is exactly the kind of distinction the
profile cannot draw automatically (zero versus null). The rater
guide's instruction to use `null` when a dimension does not
apply is load-bearing here: a numeric zero would be averaged
against ratings on documents where robustness is meaningfully
testable, and the average would be misleading.

**What the rater is evaluating.** Whether the document's claims
hold up under external check. On documents that make checkable
numerical claims, this is a substantive rating; on documents
that make none, the honest answer is `null`, not low.

## Dimension 5: Counterfactual

**Profile reports.** `signal_value: False`, `signal_text:
"Failure Framing absent (FVS-007 detected). No markers detected
for the uncertainty and risks dimensions."` Two library entries
fired (FVS-007 and one other in the dimension's map);
`failure_framing_absent: True`.

**What the rater gave.** `counterfactual: 4`. Notes: "The 'Where
it might make sense' section names the conditions under which the
recommendation reverses. The closing question ('what does your
current retirement savings look like') opens the conversation
rather than closing it. This is genuine counterfactual engagement,
not a token 'limitations' paragraph."

**The gap.** Wide. The detector reports counterfactual absent
based on missing failure-framing markers; the rater sees an
explicit "Where it might make sense" section that names the
conditions under which the recommendation reverses. The detector
is keying on a vocabulary FVS-007 names; the document does the
work without using that vocabulary.

**What the rater is evaluating.** Whether the document names
what would falsify it, what alternatives it has considered, or
the conditions under which its recommendation reverses. This is
the dimension where the gap between vocabulary and meaning is
typically widest, and the dimension where rater judgment matters
most.

## How to use this walkthrough

A first-time rater can:

1. Read this walkthrough end-to-end alongside the profile.json
   for `four-llms-bitcoin-claude`.
2. Open the document and produce their own rating before
   re-reading `example-good.yaml`.
3. Compare their rating to `example-good.yaml`. Differences are
   themselves informative; there is no "correct" rating, but a
   first-time rater whose own scores are systematically closer
   to the profile than to the rater note may be over-trusting
   the automated layer.
4. Pick a different corpus entry (the seeded set is in
   `../corpus/`) and produce a rating without a walkthrough as
   scaffolding.

The validation effort learns from divergence. A rater whose
scores match the profile on every dimension provides the same
information as the profile already does; a rater whose scores
diverge, with notes that name the specific document features
driving the divergence, is the contribution.

## Why this document is one walkthrough, not five

The teaching value is the contrast between the profile's
vocabulary-based signal and the rater's meaning-based read,
which is robust across documents in the same genre. One
walkthrough at depth beats five at surface. A rater who
internalizes the gap on `four-llms-bitcoin-claude` will recognize
it on `four-llms-bitcoin-gemini`, on the startup-question
entries, and on whatever new entries enter the corpus.

Future walkthroughs are warranted only if a new genre enters the
corpus that exhibits a different gap pattern (for example, a
heavily numerical document where the evidence and robustness
dimensions become substantively rated rather than `null`).
