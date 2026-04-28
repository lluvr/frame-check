# Detector v2 promotion playbook

**Purpose:** turn the current "v2 exists as a research artifact;
nobody knows what to do with it" state into a pre-registered,
executable path. Any future agent (human or AI) picking up this
work should be able to read this single document and know
precisely: what exists today, what must be true before v2 ships
to production, what steps to execute when those conditions are
met, what must not be touched, and how to roll back if promotion
regresses anything.

**Status:** v0.1, drafted 2026-04-18 as a scoping artifact.
Activation criteria (§2) are drafted, not ratified. The curator
must lock or revise them before any promotion attempt. This
document is itself pre-registered discipline: the cost of
deciding criteria post-hoc is goodharting; the value of deciding
them in advance is prevention.

**Not a commitment to ship v2.** v1 continues to run in
production and continues to be the citable baseline for every
worked example, every MCP resource, and every external
reference. This document exists to make the path to v2
legible, not to commit to travelling it.

---

## 1. Current state snapshot (as of 2026-04-18)

Precise state of every surface a v2 promotion would touch. A
future agent should use this as the diff base: anything not
named here is out of scope.

### 1.1 Code surfaces

| Surface | State | Detector version |
|---------|-------|------------------|
| `frame_library.py` | Production | v1 |
| `fvs_eval/validation_study/frame_library_v2.py` | Research artifact | v2 |
| `mcp_server.py` | Imports `frame_library.suggest_frames` | v1 (transitively) |
| `app.py` | Imports `frame_library` for framing matches | v1 (transitively) |
| `build_corpus_site.py` | Renders library entries | independent of detector |

### 1.2 Documentation surfaces

| Surface | State |
|---------|-------|
| `METHODOLOGY.md` | v0.3 draft; §2.4.1 names v2 results and pauses production integration |
| `data/frame_library/INDEX.md` | Reflects v2 rule retirements via Detection column state `retired` for FVS-001/008/015; frame Class stays text-side |
| `fvs_eval/validation_study/REPORT.md` | v1 canonical report; H3 falsification result |
| `fvs_eval/validation_study/REPORT_V2.md` | v2 post-audit measurement report |
| `fvs_eval/validation_study/RULE_AUDIT.md` | Per-frame audit that produced v2 |
| `SESSION_STATE.md` | Names v2 work under FVS External Validation Study section |

### 1.3 Test surfaces

| Surface | Pins to | Status |
|---------|---------|--------|
| `test_worked_example_reproduces_from_captured_payload` | v1 `build_epistemic_payload` output, byte-identical to Grok-on-NVIDIA data.json | Will fail under v2 because captured frames include FVS-001, FVS-008 which v2 retires |
| `test_every_resource_has_stable_matching_hash` | Current 51-resource set with content hashes | Independent of detector version |
| `test_mcp_server.py` other tests | Various; most independent of detector output specifics | Would need review before promotion |
| `fvs_eval/validation_study/04_compute_metrics.py` | Computes metrics against labels | Already runs against both v1 and v2 detector outputs |

### 1.4 Captured artifacts

| Artifact | Captured under | Reproducibility contract |
|----------|----------------|-------------------------|
| `data/worked_examples/grok-on-nvidia-earnings-2026/data.json` | v1 detector | SHA-256 hashes on source + summary; full payload including v1 frame matches |
| Other worked examples (Altman, FOMC, four-llms, ai-on-life-decisions) | v1 detector | No captured payload JSON; frames named in frontmatter |
| `fvs_eval/validation_study/labels/labels_detector.json` | v1 | Research artifact |
| `fvs_eval/validation_study/labels/labels_detector_v2.json` | v2 | Research artifact |

### 1.5 The one structural inconsistency that v2 promotion must resolve

`test_worked_example_reproduces_from_captured_payload` compares
fresh `build_epistemic_payload` output against the captured
payload in data.json. If `frame_library.suggest_frames` starts
returning v2 output, the captured v1 frames (FVS-001, FVS-008,
FVS-002, FVS-007) will not match the fresh v2 frames (expected:
FVS-002 only, others retired or differently-triggered).

**Three resolution paths exist**; exactly one must be chosen
before v2 promotes:

- **Path A: Version-scope the test.** Parametrise the test with
  an explicit detector version. Capture v2 output as a parallel
  `data_v2.json` alongside `data.json`. Test asserts both
  reproduce under their respective detector versions.
- **Path B: Re-capture under v2; mark v1 payload as archival.**
  Replace data.json with v2 output. Keep v1 data at
  `data_v1.json` with a README pointer for historical citations.
  Update the worked-example writeup to reference v2 measurements.
- **Path C: Pin the test to v1 detector explicitly** via a
  `detector_version="v1"` argument on `build_epistemic_payload`
  (does not currently exist; would need to be added).

Each has trade-offs named in §4. Whichever is chosen must be
named in the promotion commit.

---

## 2. Activation criteria (pre-registered)

v2 does not promote to production unless **all** of the
following are true at the time of promotion. This section is
the pre-registration: set these thresholds now, before running
additional measurement, so that hitting them cannot be the
result of threshold revision.

**Drafted, awaiting curator ratification.** Each criterion has
a default value and (for C1) a weaker alternative and a
declare-insufficient-power third option the curator may
instead lock. The default values are conservative; the
alternatives ship earlier but on weaker evidence.

**Track A and Track B are separate promotion surfaces, run
concurrently (Decision 2 locked 2026-04-19).** The criteria
below (C1-C6) gate Track A: the classifier-level promotion
from v1 rules to v2 (or v3) rules, measured by F1 and per-frame
metrics against external labelers. Track B is a parallel
surface that gates a system-level ship-decision: whether Frame
Check's output demonstrably helps users in a specific use case
(Decision 1 locked 2026-04-19 as reader-aid first; self-audit
deferred). The pre-registered design for Track B reader-aid
lives at `fvs_eval/reader_aid_study/DESIGN.md`. Anti-pattern
#7 in §4 (no-self-scoring) applies to both tracks.

**Decision 3 reframed (locked 2026-04-19 as internal-first).**
The prior three options (default expand-to-n30-with-external-
annotators / weaker-alternative-n12-directional /
declare-insufficient-power) are replaced by a sequenced
internal-first approach:

1. **v0: internal pilot phase.** Exhaust what curator plus
   the collaborating agent pool can produce before external
   recruitment: instrument-validation agent-pilots for Track
   B, new-signal engineering work for Track A, rubric
   calibration, protocol de-risking. Output: evidence that
   the protocols work mechanically, that the rubrics code
   reliably on agent-generated responses, that the Track A
   signal additions move the predicted per-frame F1 numbers.
   No external recruitment.
2. **v1: external expansion phase.** Triggered when internal
   evidence is exhausted. Signals that trigger external: Track
   A has hit its predicted per-frame F1 gains (so external
   corpus can confirm generalization) OR Track B agent-pilot
   has validated the rubric and protocol (so external reader
   study adds the human-population evidence). Until a trigger
   fires, external recruitment is paused.

The reframe preserves the three prior options as phases, not
as mutually-exclusive choices: declare-insufficient-power
remains the posture at v0 stage (we have not yet measured at
sufficient power for a publishable claim); expand-to-n30
remains the v1 phase target; directional-at-n12 is not a
separate option but the default honest framing of the v0
stage's measurement scope.

### Criterion C1: Replicated F1 improvement

**Default:** v2 macro-F1 ≥ 0.4 (the pre-registered useful-floor
from v1 DESIGN.md) on an expanded corpus of at least 30
documents labeled by at least two independent annotators who
are not part of the Frame Check project. Paid platform
annotators (Prolific or equivalent) are acceptable; the paused
canon-review reviewer outreach is a different recruitment
channel and is not a prerequisite for this criterion.

**Weaker alternative:** v2 macro-F1 ≥ 0.35 on the existing
12-document corpus, replicated by a second independent
execution of `04_compute_metrics.py` against fresh detector
runs on a fixed corpus snapshot. Shipping under this alternative
commits METHODOLOGY.md to carrying a "directional, n=12, CIs
wide" caveat next to the reported number in perpetuity.

**Third option: declare insufficient statistical power.**
Publish the v2 result at n=12 as diagnostic evidence only,
explicitly state that the evidence is insufficient to support
a production promotion, and defer classifier ship-decision
until either the default criterion or an expanded corpus lets
us report a power-adequate number. This preserves
METHODOLOGY.md credibility by not carrying a weak number with
a permanent footnote; the cost is that the product does not
get a shipping classifier-update via this path.

**Signal-engineering discipline commitments (added 2026-04-19).**
The six-rule discipline codified in
`fvs_eval/validation_study/RESULTS_SIGNAL_1.md §13` applies to
all Track A signal work subsequent to Signal 1: range-bound
targets (not floors), target-setter separated from
implementing agent, prior-sourcing must cite specific prior
measurements, bootstrap CI required on every reported F1,
out-of-distribution validation on ≥5 held-out documents
before claiming generalization, tuning-set F1 framed as upper
bound, and vocabulary-density-as-proxy acknowledged on every
per-frame result. These six rules are ADDITIVE to C1 and
apply to Signal 2 (growth-vocabulary), Signal 3 (named-
author-citation), and any later signal work. Signal 1 itself
failed several of these retroactively; §13's recap documents
the failures and the corrections for future discipline.

**Per-frame pre-registration requirement (upgrade 2026-04-19).**
The macro-F1 gate is necessary but not sufficient. A v3
promotion additionally requires per-frame pre-registered
predictions for every rule whose status the promotion changes.
Predictions must be calibrated against the v1→v2 observed
effects as empirical prior: threshold loosening on a frame
with coverage-reachable signals produced +0.511 at the high
end (FVS-009); regex-level work blocked by an upstream coverage
gate produced 0 (FVS-012); retirement of a rule with zero true
positives on detectable cases produced 0 (FVS-001, 008, 015).
A v3 prediction such as "expanded uncertainty regex in
`framing.py` moves FVS-012 from 0.182 to ≥0.30" is falsifiable,
grounded in prior, and scoped to a specific change. Direction-
only predictions ("F1 should improve") are not accepted; they
are unfalsifiable. Range-bound predictions ("[0.10, 0.25] lift
expected") are accepted when no prior exists for the specific
change type.

**Rationale.** The current v2 macro-F1 of 0.274 is below both
the default and weaker thresholds. v1 pre-registered 0.4 as
useful-floor, so shipping below 0.4 on the default criterion
would violate that pre-registration. The weaker alternative is
available but carries the perpetuity caveat. The third option
(declare insufficient power) is the honest path when neither
the default nor the weaker is defensible.

### Criterion C2: No per-frame regression

**Default:** for every frame that v1 detects at F1 ≥ 0.5, v2's
F1 on the same frame is not worse by more than 0.05. (Today:
only FVS-011 qualifies; v2 F1 is 0.667 vs v1 0.727, a -0.061
loss, which slightly exceeds this threshold.)

**Weaker alternative:** per-frame F1 drops of up to 0.10
tolerated if compensated by at least +0.20 on a different
frame.

**Rationale:** prevents v2 from being a net improvement that
hides per-frame losses. The default is a no-regression floor;
the alternative allows trades.

### Criterion C3: Reproducibility-test path chosen

One of Path A, B, or C from §1.5 is chosen and executable in
the same commit as v2 promotion. The commit must demonstrate
the test passes under the chosen path.

### Criterion C4: INDEX.md retirement policy

INDEX.md Detection states are updated to match the v2 detector
behavior. Either:
- Retired rules stay `retired` in INDEX (v2 promotion only
  promotes the framework, not new rules), or
- A new `yes` Detection state appears for any v2 rule that has
  been redesigned beyond retirement (not currently the case;
  v2 retires and tunes but does not add new rules).

The three rows FVS-001/008/015 must have Detection value
matching the production detector state.

### Criterion C5: Methodology document version bump

METHODOLOGY.md version increments to 0.4.0 or later, with §2.4.1
updated to name v2 as the production detector and a new §2.4.2
or equivalent section naming what triggered promotion.

### Criterion C6: Not-blocked-on-worked-example-citations

If Path B (§1.5) is chosen, any external document or publication
that cites v1 detector output by specific frame IDs for the
Grok-on-NVIDIA worked example must either:
- Still resolve (via archival data_v1.json), or
- Be re-written against v2 output before the promotion commit.

If zero external citations exist at promotion time, this
criterion is trivially met.

---

## 3. Promotion steps (executable sequence)

When the curator has locked activation criteria and all are
met, an agent executes these steps in order. Each step is
self-contained; each ends with a verification.

### Step 1: Pre-promotion audit

1. Confirm `frame_library_v2.suggest_frames_v2` exists and
   passes its own module-level sanity (import, signature match
   with `suggest_frames`).
2. Confirm `labels_detector_v2.json` exists and the macro-F1
   computed from it against the current labels matches the
   number in REPORT_V2.md.
3. Confirm the activation criteria table (§2) is all
   green-checked in a curator-signed commit or comment.

Verification: running `python3 -c "from
fvs_eval.validation_study.frame_library_v2 import
suggest_frames_v2"` succeeds. REPORT_V2.md's macro-F1 reproduces.

### Step 2: Move v2 to production path

1. Move or copy the contents of
   `fvs_eval/validation_study/frame_library_v2.py`
   (specifically the `suggest_frames_v2` function and its
   dependencies) into `frame_library.py`.
2. Replace the existing `suggest_frames` implementation with
   the v2 implementation. Preserve the function signature so
   callers do not break.
3. Keep the v2 module in `fvs_eval/validation_study/` for
   historical reference; do not delete.

Verification: `python3 -c "from frame_library import
suggest_frames; print(suggest_frames.__doc__)"` emits the v2
docstring. No other module's imports need to change.

### Step 3: Resolve the reproducibility test

Execute the chosen Path (A, B, or C) from §1.5:

- **Path A:** add a v2 parameter to the test; capture a
  `data_v2.json` alongside `data.json`; assert both reproduce.
- **Path B:** regenerate `data.json` by re-running
  `build_epistemic_payload` under the new detector; move v1
  data to `data_v1.json`; add README note.
- **Path C:** add an optional `detector_version` argument to
  `build_epistemic_payload` and its callers; pin the test to
  `detector_version="v1"` against the archived v1 implementation.

Verification: `python3 test_mcp_server.py` exits 0.

### Step 4: Update INDEX.md

If any v2 rule has been redesigned to `yes` state (not
currently the case), update the Detection value accordingly.
Otherwise, confirm the INDEX still reflects the three retired
rules as `retired` and add a note that the production detector
implements the retirement.

Verification: `grep -E "FVS-(001|008|015)" data/frame_library/INDEX.md`
shows `retired` for all three.

### Step 5: Update METHODOLOGY.md

1. Bump version to 0.4.0.
2. Move §2.4.1 content: v2 is no longer "post-audit result" but
   "current production detector."
3. Add §2.4.2 naming the activation criteria that triggered
   promotion and the specific evidence each was met with.
4. Update the document-head construct-honesty note to reflect
   that production now runs v2.

Verification: `grep "^\*\*Version:\*\*" METHODOLOGY.md` shows
0.4.0 or later.

### Step 6: Update SESSION_STATE.md

Add a new entry under §1 "What shipped recently" naming the
promotion commit, the activation criteria met, the paths taken
(§1.5 resolution), and the effective date. Move the v2
research-artifact description to a new "historical" subsection.

### Step 7: Full test suite + corpus build

1. `python3 run_tests.py` must exit 0 with all 19 suites
   passing.
2. If the corpus site build runs as part of deploy,
   `python3 build_corpus_site.py` must succeed and produce
   the same resource count (51 currently).

### Step 8: Commit and tag

Single commit containing all of the above. Commit message names
the activation criteria each met, the §1.5 path chosen, and a
pointer to this document. Tag the commit
`detector-v2-promotion-<date>`.

---

## 4. What must NOT be done

Anti-patterns the promotion must avoid:

1. **Do not delete `frame_library_v2.py` from `fvs_eval/validation_study/`.**
   It remains the historical record of the research-artifact
   state that produced the promotion.
2. **Do not re-capture `data.json` without updating
   `test_worked_example_reproduces_from_captured_payload`.**
   If Path B is chosen, the test must be updated in the same
   commit that replaces the captured data.
3. **Do not reclassify FVS-001, FVS-008, or FVS-015 from
   text-side to meta-side.** The frame concepts are text-side.
   The rules are retired. These are different axes. Reclassifying
   on implementation failure would poison IDX-1's precedent.
4. **Do not promote v2 without ratified activation criteria.**
   Running the steps above with unratified criteria is the
   exact goodharting pattern the pre-registration discipline
   prevents.
5. **Do not delete REPORT.md or REPORT_V2.md.** They are the
   citable evidence for why v2 promotion happened.
6. **Do not adjust the pre-registered 0.4 threshold in v1
   DESIGN.md after the fact.** The threshold was pre-registered.
   If the curator wants a different threshold for v2
   specifically, it must be registered separately in this
   document, not retconned into v1's design.
7. **Do not use Frame Check as its own scorer in any
   promotion test.** A promotion criterion that measures Frame
   Check's outputs with Frame Check's metrics cannot falsify;
   the instrument and the scoring apparatus must be independent.
   Labelers, evaluators, or external rubrics must provide the
   scoring. This rule applies to both Track A (classifier F1
   against external labelers) and Track B (system-level value
   scored by external evaluators). A test that violates this
   constraint is unfalsifiable by construction and its results
   cannot support promotion.
8. **Do not retroactively rewrite worked-example captures
   under a new detector version.** Captured `data.json`
   payloads pin to the detector version that produced them.
   If v3 ships to production, the v1-captured Grok-on-NVIDIA
   payload remains pinned to v1 and continues to reproduce
   against a v1 code path (retained via `detector_version`
   parameter per §1.5 Path C, or archived as `data_v1.json`
   per Path B). A v3 promotion does not rewrite history; it
   adds to it. External citations of v1 frame matches remain
   resolvable after any future promotion.

---

## 4.1 Retirement decision criteria (FP/FN asymmetry)

A rule's retirement decision should split by its failure mode,
not be categorical on "rule failed." The two failure types have
different user-experience consequences and warrant different
treatment.

**High FP / low FN (rule over-fires, rarely misses).** The rule
flags documents where the frame is not present, but when the
frame IS present the rule usually catches it. User experience:
reader sees some false flags. Each false flag arrives paired
with a teaching question. Teaching questions retain reader
value even on false flags ("what would a risk analyst say
about this data?" is a useful prompt regardless of whether
the document technically exhibits Growth Frame). Appropriate
response: retain with a **low-confidence marker** in the UI
("this rule has a high false-positive rate; treat the suggestion
as a prompt, not a classification"), not retirement.

**Low FP / high FN (rule rarely fires, misses cases).** The rule
silently misses frames actually present. User experience: reader
does not see a teaching question they would have benefited
from. No teaching question is delivered, so there is no
reader-value fallback. Appropriate response: **retire pending
rule redesign or new signal dimensions**. Silent failure is
worse than loud imprecision.

**High FP / high FN.** Rule fires often, misses often, does not
correlate with the frame. Appropriate response: **retire
unconditionally**. No evidence it detects what it names.

**Low FP / low FN.** Rule works as designed. Keep.

**Retroactive consequence for FVS-001, FVS-008, FVS-015 (flagging,
not acting):** under this framework, their v1 profiles are high-FP
low-FN on the 12-document corpus (v1 fired 4, 3, 2 times
respectively on detectable cases; curator true positives on
detectable cases: zero; curator flagged FVS-001 once on the
Altman essay which is captured but not detectable by the
digit-level measure). The v2 retirement decision already
happened and stands. A future curator reconsideration could
restore these three at a low-confidence tier rather than keep
them retired, because their failure mode is the less-bad of
the two. **Not acting today; surfacing for curator when v3
planning begins.**

**How this interacts with activation criteria C1 and C2:**
C2's per-frame regression threshold applies to the macro-F1
scoring path. The FP/FN split applies to the retirement-
decision path. A v3 that restores FVS-001 at a low-confidence
tier may produce a different macro-F1 profile than a v3 that
leaves it retired; pre-registration per the upgrade in C1
would name the expected F1 under each choice.

## 5. Rollback plan

If the v2 promotion commit passes tests at merge time but later
causes regressions (in production usage, in external citations,
in the corpus site build):

1. Revert the promotion commit: `git revert <sha>`.
2. Production returns to v1. `frame_library.suggest_frames`
   returns to its pre-promotion behavior.
3. Test suite returns to passing.
4. Add a rollback-note entry to SESSION_STATE.md naming what
   regressed, when, and what the investigation path is.
5. v2 returns to research-artifact state in
   `fvs_eval/validation_study/`.

The promotion commit should be single-commit specifically to
make this revert clean. Multi-commit promotions are harder to
revert.

---

## 6. Ownership and decision authority

| Role | Authority |
|------|-----------|
| **Curator (BDFL)** | Ratifies activation criteria (§2). Signs off on promotion commit. Decides §1.5 path. Authorises rollback. |
| **Agent executing promotion** | Runs Steps 1-8 mechanically. Does not decide any criterion or path. Reports deviations; does not resolve them. |
| **Reviewer (when one exists per REVIEWERS.md)** | Optional sign-off on promotion notes. Not blocking. |
| **Future agent picking up from zero context** | Reads this document. Determines current state via §1 against the live tree. If criteria met and curator signed off, executes Steps 1-8. |

The agent-vs-curator separation is the key structural element:
any AI agent or contributor can execute Steps 1-8 deterministically
once the criteria are ratified. Deciding the criteria requires
the curator. This is the "predictable for any new agent" property
the document exists to provide.

---

## 7. Known calibration-of-calibration questions

The activation criteria in §2 rest on assumptions that may
themselves need revision. Surfaced explicitly so future agents
do not mistake these for settled:

- **The 0.4 useful-floor** was pre-registered in v1 DESIGN.md
  as one of four zones (state-of-art ≥ 0.7, useful 0.6-0.7,
  partial 0.4-0.6, falsification < 0.4). The specific number
  0.4 has not been empirically validated against what users
  find useful. It may be too high (discouraging ship of a
  genuinely-useful-but-imperfect tool) or too low (shipping at
  0.4 may produce output users do not trust). **A user-study
  calibration of the threshold itself is unclaimed work.**
- **n=12 confidence intervals are wide.** The +0.118 v1-to-v2
  delta is directionally real but the CI on a sample-of-12
  could include zero at some tests. Default C1 requires n≥30;
  the weaker alternative requires independent replication on
  the existing 12. Neither is ideal. **A power analysis for
  detecting a 0.05 macro-F1 delta at 80% power is unclaimed
  work** and would name the right n.
- **The curator-plus-LLM-judge majority-union** is the label
  universe. The LLM-judge is instructed with the FVS library
  reference, so it is not an independent test of the taxonomy.
  A label universe with human annotators trained from scratch
  may produce different labels, possibly different F1 ceilings.
  **A bootstrapped label-reliability test is unclaimed work.**
- **Per-frame F1 variance is high.** Only FVS-011 cleared
  F1 ≥ 0.5 at v1; three cleared that threshold at v2. Per-frame
  F1 ranges 0.00 to 0.875 at v2. A macro-F1 summary number
  obscures this. **A per-frame shipping policy** (ship frame X
  to production if its own F1 is ≥ Y, regardless of other
  frames) is an alternative to macro-F1 gating and is not yet
  considered.
- **Corpus genre-sensitivity.** v2 macro-F1 is 0.622 on Stratum
  A (human-authored public), 0.310 on Stratum B (AI-generated),
  0.434 on Stratum C (Wikipedia). A user pasting a document on
  the live site is approximately Stratum-A or Stratum-B;
  calibration of the shipping threshold by genre is unclaimed
  work.

These questions do not block promotion; they inform how to
interpret whatever promotion evidence accumulates. The curator
may decide to ship on a lower threshold if the per-genre or
per-frame evidence is strong in the specific subset of usage
the live site serves.

---

## 8. Historical artifacts to preserve

After v2 promotes, these remain in place:

- `fvs_eval/validation_study/frame_library_v2.py` (historical
  source of the promoted rules)
- `fvs_eval/validation_study/RULE_AUDIT.md` (the analysis that
  produced v2)
- `fvs_eval/validation_study/REPORT_V2.md` (the measurement that
  justified promotion)
- `fvs_eval/validation_study/labels/labels_detector.json` and
  `labels_detector_v2.json` (the per-corpus detector outputs
  under v1 and v2 respectively)
- `fvs_eval/validation_study/DESIGN.md` and `REPORT.md` (v1
  study, pre-registration, canonical)
- `data/worked_examples/grok-on-nvidia-earnings-2026/` (or its
  archived v1 equivalent per §1.5 path choice)

Preserving these lets a future reader trace: what the detector
used to do, why it changed, what the change was measured
against, what evidence justified promotion.

---

## 9. How to use this document

For a curator deciding whether to promote v2:

1. Read §1 to confirm current state matches your mental model.
2. Read §2 and lock the activation criteria (ratify defaults or
   substitute values).
3. Evaluate whether the criteria are met today. If yes, proceed
   to Step 1 of §3. If no, queue the work that would meet them
   (expanded corpus, redesigned rules, etc).
4. When promoting: execute §3 in order. Do not skip steps. Do
   not mix in unrelated work.
5. When rolling back: execute §5.

For an agent picking up this work from zero context:

1. Read this document top to bottom.
2. Check §1 against the live tree for divergence.
3. If divergence exists, surface it to the curator; do not
   resolve unilaterally.
4. If activation criteria in §2 are ratified and met, propose
   executing §3; get curator sign-off; execute.
5. If activation criteria are unratified or unmet, the
   appropriate action is to work on closing the gaps (expanded
   corpus, redesigned rules, new measurement cycle), not to
   promote.

For a contributor proposing a v3 detector cycle:

1. This document describes the v1-to-v2 promotion playbook.
2. A v2-to-v3 cycle would produce a parallel document
   (`DETECTOR_V3_PROMOTION.md`) or extend §2 with a separate
   criteria block for the v3 step.
3. Do not overwrite §2 with v3 criteria; preserve the
   pre-registration discipline across versions.

---

## 10. One-sentence summary

v2 remains a research artifact; v1 remains production; promotion
is gated on pre-registered activation criteria (§2) that the
curator must ratify and evidence must then satisfy; when both
conditions hold, any agent executes the deterministic step
sequence in §3 and a rollback is a single `git revert` away.
