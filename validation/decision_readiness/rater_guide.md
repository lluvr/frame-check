# Rater guide: decision-readiness profile

You are rating a document on five dimensions of decision support.
Each dimension is rated on a 1-5 scale. Read the methodology page
at /corpus/decision-readiness/
for the underlying framework; this guide gives you the operational
definitions and anchor descriptions you use while rating.

**Do not read Frame Check's computed profile for the document
before you rate.** The profile lives in `corpus/{doc_id}/profile.json`;
your ratings must be blind to it for the validation to be
informative.

## How to rate one document

1. Open `corpus/{doc_id}/document.md` and read the document in full.
2. For each of the five dimensions below, score 1-5 against the
   anchor descriptions.
3. Write notes per dimension explaining your reasoning. The notes
   are how the validation effort learns where the profile and
   raters diverge.
4. Save your ratings as `ratings/{doc_id}/{your_rater_id}.yaml`
   using the template in `rating_template.yaml`.

If a dimension does not apply to a document (e.g., a poetry
excerpt has no numerical claims to source-verify), use the
sentinel value `null` rather than guessing. The harness handles
nulls correctly; guessing pollutes the correlation.

---

## Dimension 1: Coverage of perspectives

**What you are judging:** Does the document address the perspectives
that matter for the kind of decision someone might make based on it?
Five general analytical perspectives anchor the dimension: causes
(why), risks (what could go wrong), stakeholders (who is affected),
trends (what is changing), uncertainty (what is unknown).

**Anchor descriptions:**

- **5: Comprehensive.** Addresses all five general perspectives
  with substantive content per perspective. A reader leaves with
  a multi-faceted picture suitable for considering most relevant
  factors before deciding.
- **4: Broad.** Addresses 4 of 5 perspectives with substantive
  content. The missing perspective is named or its absence is not
  load-bearing.
- **3: Partial.** Addresses 3 of 5 perspectives with substantive
  content, OR addresses all 5 but with very uneven depth (one or
  two perspectives carry most of the analysis; others are token
  mentions).
- **2: Narrow.** Addresses 2 of 5 perspectives with substantive
  content. A reader would need additional sources to consider the
  decision adequately.
- **1: Single-perspective.** Addresses 1 of 5 perspectives, or
  effectively none in substantive depth.

**Common confusions:** Length is not a proxy for coverage. A short
document can cover all five perspectives concisely; a long
document can dwell on one perspective. Coverage is about whether
the perspectives are substantively present, not how many words
are devoted to them.

---

## Dimension 2: Claim calibration

**What you are judging:** Are the claims in the document hedged
appropriately given their epistemic status? Statements about
uncertain matters that are stated as facts are mis-calibrated
upward; statements about well-established facts that are
unnecessarily hedged are mis-calibrated downward.

**Anchor descriptions:**

- **5: Well-calibrated.** Claims about established facts are
  stated cleanly; claims about uncertain matters carry hedges
  appropriate to the uncertainty (e.g., "may," "approximately,"
  "in some cases," "if X, then Y").
- **4: Mostly calibrated.** Most claims are appropriately hedged;
  one or two over-confident assertions about uncertain matters,
  or a handful of unnecessarily hedged established facts.
- **3: Mixed.** Roughly half the calibration is appropriate; the
  other half mis-calibrates in either direction.
- **2: Mis-calibrated upward.** Many claims about uncertain matters
  are stated as facts. Predictions are stated without
  conditional language. The reader cannot tell from the prose
  which claims are well-supported and which are speculative.
- **1: Severely overconfident.** Almost all claims are stated
  with the same confident voice regardless of underlying
  certainty. The Confidence Imbalance pattern is unmistakable.

**Common confusions:** Genre matters. A grant proposal SHOULD be
hedged (forward-looking, uncertain). A historical analysis
should NOT be heavily hedged on established events. Use your
judgment about what calibration is APPROPRIATE for the genre,
not a fixed hedge ratio.

---

## Dimension 3: Evidence backing

**What you are judging:** Are the document's claims supported by
sources, or are they floating assertions? Numerical claims and
factual claims need different things: numerical claims need a
source; factual claims need either a source or established
common knowledge.

**Anchor descriptions:**

- **5: Fully sourced.** Every numerical claim has a source.
  Factual claims are either sourced or clearly common knowledge.
  The reader can trace any specific claim to its origin.
- **4: Mostly sourced.** Most numerical claims have sources; a
  handful of asserted numbers without attribution. Factual
  backing is otherwise solid.
- **3: Mixed.** Roughly half the numerical claims are sourced;
  the others are stated without attribution. The reader has to
  trust the author on a meaningful share of the content.
- **2: Limited sourcing.** Most numerical claims are stated
  without attribution. The document is interpretation-heavy
  with thin evidentiary backing.
- **1: Floating.** No source attribution for numerical claims.
  The document asserts numbers without showing where they come
  from. The reader cannot verify any specific claim.

**Common confusions:** "Evidence backing" is about the document's
internal sourcing discipline, not about whether the sources
themselves are correct. A document that cites an unreliable
source still rates higher on this dimension than one that
asserts the same number with no source. Source CORRECTNESS is
captured by the Robustness dimension when Frame Check verifies
against authoritative providers.

---

## Dimension 4: Robustness

**What you are judging:** Does the document hold up under scrutiny?
Specifically: do its claims survive checking against external
sources? Does the internal logic hold together?

**Anchor descriptions:**

- **5: Robust.** Numerical claims that you spot-check against
  external sources hold up. Internal logic is consistent. No
  obvious load-bearing claim turns out to be wrong.
- **4: Mostly robust.** Spot-checks reveal one or two minor
  errors (rounding, dated figures) but no load-bearing claim
  fails. Internal logic is consistent.
- **3: Some erosion.** Spot-checks reveal a handful of
  claim-source mismatches, including at least one that bears
  on the document's main argument. Internal logic has at least
  one questionable link.
- **2: Brittle.** Multiple load-bearing claims fail spot-checking.
  Internal logic has gaps that affect the conclusion.
- **1: Fails under scrutiny.** Load-bearing claims contradict
  external sources. The document's main argument relies on
  unsupportable assertions.

**Common confusions:** Robustness assumes you spot-check at least
a few of the document's specific numerical or factual claims. If
you cannot spot-check at all (the document is purely
interpretive with no checkable claims), use `null` for this
dimension.

---

## Dimension 5: Counterfactual thinking

**What you are judging:** Does the document name what would
falsify it? Does it consider alternative explanations or
opposing views? Does it engage with how it might be wrong?

**Anchor descriptions:**

- **5: Engaged.** The document explicitly names what would falsify
  its main claims. Alternative interpretations are considered and
  addressed. Limitations are acknowledged in proportion to the
  confidence of the conclusions.
- **4: Mostly engaged.** Limitations are acknowledged. At least
  one alternative interpretation is considered. The reader sees
  the author has thought about how the analysis could be wrong.
- **3: Token engagement.** A "limitations" paragraph exists but
  is generic. Alternatives are mentioned but not engaged with.
  The author signals counterfactual thinking without practicing
  it.
- **2: Light.** No limitations section; no consideration of
  alternatives. The document presents one interpretation as if
  it were the only one.
- **1: Absent.** No counterfactual engagement at all
  (corresponds to the named pattern
  FVS-007: Failure Framing absent
  in the Frame Vocabulary Standard).
  The document makes confident claims with no engagement with how
  it might be wrong, what would change the conclusion, or what
  alternative interpretations exist.

**Common confusions:** This is the dimension most affected by
genre. Editorials and op-eds are expected to be one-sided; a
strong op-ed scoring 1 here is not necessarily a bad op-ed. Use
the genre context (in `corpus/{doc_id}/metadata.yaml`) to
calibrate your rating.

---

## Time budget

A rating session takes 15-30 minutes per document for an
experienced rater. Longer for the first few documents while you
calibrate against the anchors; faster once you have done 3-5.
Record `time_spent_minutes` in your rating file so the validation
effort can publish realistic time estimates for future raters.

## When in doubt

- Prefer `null` over guessing
- Prefer the lower score when a document is between two anchors
  (calibration biases tend to be upward; conservative rating
  helps the validation)
- Add notes explaining your reasoning so divergence cases are
  informative

The validation harness reports cases where Frame Check and
expert raters diverge sharply. These are the most useful
documents for methodology revision; your notes are what makes
the divergence interpretable.
