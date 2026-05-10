# Validation program design

**Status:** reframed 2026-04-18. Formal evaluator program v1
is deferred. Observational v1 is the active plan: ship Frame
Check as a developer tool, watch organic adoption, and
reactivate formal validation only when a named trigger fires.
The stress-test analysis that identified the three durable
claims remains load-bearing and is preserved below; the
formal v1 workstream design is preserved as the blueprint
for when a trigger fires.

## Active plan: observational v1

The developer-tool path is validating the compound claims in
a stronger form than a paid evaluator study would. The
primary audience is builders of AI-agent experiences (Claude
Desktop users, Cursor users, agent framework authors). That
audience validates the sovereignty case by adopting the tool
or not, by citing Framecheck in their own work or not, by
building integrations or not. Each of those behaviors is
stronger evidence than a 30-participant controlled study
because it is real use, not paid attention.

The observational program is simply: ship the MCP server,
publish the corpus, watch the signals below, engage people
who approach the research rather than recruiting before
anyone has approached.

### Signals to watch

- Install counts on the MCP server once npm distribution is
  live.
- Unsolicited inquiries from academics, journalists, or
  practitioners who have found Framecheck on their own.
- Third-party citations of the methodology, worked examples,
  or Frame Vocabulary Standard entries.
- Integrations: somebody ships a product or agent pipeline
  that incorporates frame_check or frame_compare.
- Replication signals: somebody publishes their own framing
  measurement using the library taxonomy or reproduces a
  worked example against different models or documents.

### Triggers for formal validation reactivation

If any of the following fires, the formal v1 workstreams (in
the preserved blueprint section below) become active. Until
one fires, the formal program is paper design, not fieldwork.

- **Three or more unsolicited academic inquiries** (from
  distinct researchers, in distinct institutions) within any
  rolling 90-day window.
- **First third-party citation of Framecheck methodology in
  published work** (peer-reviewed journal, preprint, book,
  conference paper, or substantive industry report).
- **Competitor tool publishes a sovereignty-adjacent
  measurement** that contradicts or relativises Framecheck's
  claims, creating a market pressure to respond with
  empirical evidence rather than narrative.
- **Internal forcing function:** Lovro decides formal
  validation is warranted on strategic grounds regardless of
  signal (this is the BDFL override; use sparingly, document
  the reasoning).

## Decision-readiness profile: separate validation track

The decision-readiness profile is a per-document construct (five
dimensions: coverage, calibration, evidence, robustness,
counterfactual) that ships under the methodology but is **labelled
experimental and gated** out of the live UI until external raters
have evaluated it. This validation runs in parallel to the
observational/formal-v1 split above and has a different shape:
the gate is a product behavior (whether profile output appears in
`/result/`), not a strategic decision about the whole program.

### Gate

A live-UI test (`test_decision_readiness_not_in_result_page_ui`)
pins the gate as a code-level invariant: the profile is **not**
surfaced in the result page until the gate lifts. The gate lifts
when the Phase 2 rater study described in `RATERS.md` reports
agreement above the threshold defined there.

### What counts as Phase 2 ready

The criteria below have to be met before the gate-lift conversation
starts. Until they are met, the profile remains a researcher-facing
artifact reachable through the corpus_site
(`/corpus/decision-readiness/`) and through MCP
(`frame-check://corpus/{slug}/profile`,
`frame-check://aggregate/latest`) but does not appear in the live
analysis flow.

1. **Worked example pedagogically sufficient.** A rater landing on
   `RATERS.md` cold should be able to follow one corpus entry's
   profile end-to-end. Either an existing corpus entry's profile
   is the example (pointed at from `RATERS.md`), or a paired
   walkthrough document exists in `data/worked_examples/` that
   names a corpus entry, walks through each of the five
   dimensions, and shows what disagreement would look like.
2. **Rater contract complete.** `RATERS.md` defines what counts
   as agreement (per-dimension scoring rubric, agreement
   threshold, what to do when raters disagree among themselves
   versus disagree with the profile).
3. **Three independent raters complete a calibration round.**
   Same corpus entries, blinded to the profile output. Their
   agreement with each other establishes the human ceiling
   (inter-rater reliability) before profile-vs-rater agreement is
   meaningful.
4. **Profile-vs-rater agreement reported per dimension.** Each
   of the five dimensions is reported separately. Dimensions
   below the threshold get targeted detector review the same
   way Workstream 1 in the formal v1 blueprint handles
   below-threshold dimensions; passing dimensions advance.

### Trigger to lift the live-UI gate

All four conditions above met **and** at least three rated corpus
entries with results documented (date, rater identifiers, per-dimension
agreement, dimension-level pass/fail). When the trigger fires, the
gate-lift work is: remove the gate test (or invert it to assert
profile output appears), update the corpus_site experimental badge,
update README + METHODOLOGY to remove the experimental qualifier
on the public methodology link, update `RATERS.md` to record the
calibration round as the closing of Phase 2.

### Relationship to observational / formal v1

This is a **third validation track**, not a substitute for either
side of the observational/formal v1 split. The observational
program watches for unsolicited adoption of Framecheck overall;
the formal v1 blueprint validates the three durable compound
claims (structural-frame invariant, sovereignty case,
measurement-transparency) when a trigger fires. The
decision-readiness gate validates one specific measurement
construct's reliability against external rater judgment, with the
live-UI surfacing as the concrete consequence. The three tracks
can fire independently.

## Why this document exists

The compound claims Framecheck is built on (the sovereignty
case, the prompt-quality gap, the operating-manual moat, the
structural-frame invariant) have zero external coverage as of
today. Internal iteration and private testing cannot close the
credibility gap that an external evaluator program would. The
memory pointer on this is explicit: *"Different class of work
required: external evaluators + actual users."*

But external validation is expensive, and the wrong question
to validate is worse than no validation. A program anchored on
a claim that dies in 2 years consumes evaluator time, produces
literature that ages badly, and commits the research program to
a frame that is not invariant under AI advancement.

This document exists so the first cohort is pointed at durable
claims.

## Stress test: what dies, what survives

The operating question for every candidate claim and program
element: given the trajectory of AI over 2 years and 5 years,
does this survive, reshape, or die? The discipline is to avoid
anchoring on claims that die.

### The "prompt > model" gap

This is the claim my earlier reasoning used as a central
anchor. It does not survive stress-testing.

- **2-year horizon.** Models internalize prompting. A 2028 model
  asked "is Bitcoin a good investment" does, internally, what a
  2026 researcher had to do with a carefully-crafted prompt:
  decompose the question, construct the analytical frame,
  surface the constraints, acknowledge the uncertainty.
  External prompting becomes a residual degree of freedom; the
  dominant variable is the model's internal prompting quality.
- **5-year horizon.** The prompt-model distinction collapses
  entirely. Models that can construct their own scaffolding do
  not see a meaningful difference between "the user's prompt"
  and "the cognitive operations the model runs on itself."
  The question "is prompt quality > model quality" stops being
  a valid question because the referent ("prompt") no longer
  names a distinct variable.
- **What the claim was really proxying for.** "Prompt quality
  matters more than model choice" was a measurable shorthand
  for the deeper claim: *the structural shape of AI output is
  controllable, and the lever is external to the model
  parameters.* That deeper claim dies too: the structural
  shape becomes shaped by the model's own internal operations,
  not an external prompt.

A validation program anchored on the prompt-model gap is
anchored on a disappearing distinction.

### What survives

Framecheck measures the **structural frame of final output**.
The measurement is:

- Agnostic to whether the frame came from a prompt, from the
  model's intrinsic capability, from an agentic workflow, from
  internal prompting, or from any future combination we have
  not named.
- Deterministic and language-layer. The measurement is of the
  text the user sees, not the pipeline that produced it.
- Citation-grade: the same text produces the same measurement,
  forever, regardless of what model generated it when.

This is the invariant. Any validation program that anchors on
this invariant survives the prompt-model gap's collapse.

### The claims that remain durable

Three claims survive stress-testing; these are what the
validation program should test.

**Claim 1: The structural-frame invariant.**
> *The structural frame of a document (voice, coverage,
> temporal orientation, epistemic basis, FVS matches) is a
> property of the text, independent of its production pipeline,
> and is reliably measured by Framecheck.*

Validation question: do independent evaluators, shown Frame
Check's measurements on a corpus, agree the measurements
describe the structural frame they also perceive in the text?
Disagree-rate per dimension is the outcome variable.

Durability: durable. This is a claim about text, not about
model generation.

**Claim 2: The sovereignty-case behavioural claim.**
> *Surfacing Framecheck's measurements to a reader at the
> moment of an AI conversation changes what the reader does
> with the AI's response, compared to reading the AI's
> response alone.*

Validation question: A/B test. Group A sees an AI response
alone; Group B sees the same response plus Framecheck's
measurements and agent_guidance. Measure decision outcomes,
confidence, follow-up question quality, or self-reported
"did I inherit the AI's frame."

Durability: durable, possibly strengthening over time. As AI
gets more capable, the asymmetry between what the AI generates
and what the reader can independently evaluate grows. The
sovereignty case becomes MORE relevant, not less.

**Claim 3: The measurement-transparency claim.**
> *An AI agent that cites Framecheck faithfully (using the
> agent_guidance contract) produces responses that readers
> can evaluate with more precision than an AI agent that does
> not cite a structural measurement substrate.*

Validation question: agents using the MCP server vs agents
not using it, on matched prompts. Measure evaluator ability
to identify where the agent's analysis is grounded vs
generated.

Durability: durable. As agents become more autonomous, the
question "how do I know what's grounded in this response" gets
harder, not easier. Citation substrates matter more, not less.

### Stress test on the remaining program elements

Applying the same 2-year / 5-year lens to the other candidate
elements.

**Live Claude Desktop MCP validation.**
- Survives. The specific MCP protocol may be replaced in 5
  years, but the practice of validating an agentic interface
  against a declared contract is timeless. If MCP is
  replaced, the validation re-runs on the successor protocol.
- Durable payoff: the agent_guidance contract respect, voice
  discipline, tool-call correctness. These are durable tests
  of the Framecheck design, not the protocol.

**External evaluator pilot (2-3 researchers).**
- Survives and strengthens. Evaluator-based validation is the
  scientific standard; it does not age.
- Durable payoff: a corpus of evaluator reactions becomes
  primary research evidence for Claims 1, 2, 3.
- Risk: the specific worked examples the evaluators review
  may become dated. Mitigation: refresh the evaluation corpus
  annually.

**Calibration re-run with current models.**
- Survives mechanically; the practice of re-calibrating as the
  source-network landscape changes is permanent maintenance.
- Durable payoff: the reliability-tiers resource stays
  load-bearing.
- Risk: if comprehensive AI-native verification becomes the
  norm, the specific provider set (SEC EDGAR, FRED, Wolfram,
  etc.) may be subsumed by better coverage. The calibration
  methodology itself still matters.

**Three more worked examples (not yet written).**
- Worked examples as a corpus survives. Specific examples age.
- Durable payoff: range demonstration of method applicability.
- Risk: time investment per example is high. A fixed cadence
  (one per quarter) with deliberate genre variety beats
  sporadic burst-writing.

**frame_verify standalone Layer 4 tool.**
- Mixed. The specific tool may be absorbed into the main
  frame_check surface over time. The CAPABILITY (source-fidelity
  verification against supplied material) is durable.
- 5-year read: source verification becomes table-stakes for
  agentic work. A deterministic, digit-level, citation-grade
  baseline still matters for high-stakes citations even when
  models self-verify by default.
- Durable payoff: the deterministic baseline.

**FVS v2.0 refinement.**
- Mixed. If the vocabulary is widely adopted, it calcifies
  (good). If not, it stays a private taxonomy (also fine as a
  research instrument).
- 5-year read: depends entirely on external adoption. Without
  citations from outside the project, FVS is one researcher's
  taxonomy. With citations, it becomes shared infrastructure.
- Durable payoff: research-community shared vocabulary IFF
  adoption materialises. This is one of the compound claims
  with zero coverage today.

**Frame-shift detection within a single document.**
- Survives. Multi-frame documents will remain common; the
  ability to detect frame shift is a capability extension.
- 2-year risk: models detect frame shift natively. The
  deterministic measurement still has citation-grade value
  (same-input, same-output).

**Registry submission (MCP ecosystems).**
- Ecosystem-dependent. Registries may consolidate or
  fragment. The practice of discoverability is durable.

## Formal v1 blueprint (preserved for trigger activation)

The sections below were the original formal v1 design. They
remain the blueprint for when a trigger fires. The design is
intact; the decision to execute is paused.

Scoped to what would be executable in one quarter once a
trigger activates it.

### v1 scope

Three workstreams, executed sequentially, each feeding the next.

**Workstream 1: Claim 1 anchor (structural-frame invariant).**

- Corpus: 10 documents (the 5 existing worked examples + 5
  new unseen documents of varied genre).
- Procedure: 3 independent evaluators (researchers, not part
  of the Framecheck program) read each document and produce
  their own structural-frame reading (voice, coverage,
  temporal, epistemic) without seeing Framecheck's output.
  Each evaluator then compares their reading to Framecheck's.
- Outcome variable: agree-disagree rate per dimension.
  Dimensions with >70% evaluator agreement with Framecheck
  are considered validated. Dimensions below 70% trigger a
  targeted detector review.
- Timeline: one month including recruitment.

**Workstream 2: Claim 2 anchor (sovereignty-case behavioural
claim).**

- Setup: 30 participants, between-subjects design.
- Group A (control): sees 3 AI responses to life questions
  ("is X a good investment," "should I do Y," "what should I
  tell my Z"). Reports: what they would do, how confident
  they are, what they would ask the AI next.
- Group B (treatment): sees the same AI responses plus Frame
  Check's measurements and the agent_guidance block
  surfaced to them.
- Outcome variables: decision diversity (do Group B people
  diverge MORE from the AI's recommendation?), confidence
  calibration (do they hedge more appropriately?), follow-up
  question quality (do they ask more substantive questions?).
- Timeline: 6 weeks including recruitment + analysis.

**Workstream 3: Claim 3 anchor (measurement-transparency).**

- Setup: paired agent evaluation. Same 5 prompts run against
  Claude Desktop with Framecheck MCP installed (agents that
  have access to the sovereignty prompts) vs without.
- 10 evaluators read both the with-MCP and without-MCP
  responses for each prompt.
- Outcome variable: evaluator-identified grounding precision.
  "This specific claim is grounded in X" - can they point at
  the grounding with more precision when the MCP agent cites
  Framecheck?
- Timeline: 1 month after Workstream 1 completes (the
  evaluators can be the same cohort).

### What's out of v1 scope

- A/B test on the hosted app (complicated by consent and
  sample bias; later).
- Longitudinal study of whether the sovereignty effect
  persists over repeated use (v2).
- Cross-model generalization study (does the effect replicate
  when the AI under test is GPT-5, Gemini, etc., not just
  Claude). High value but adds evaluator burden.
- Publication-quality paper write-up (the v1 outputs are
  internal evidence; publication is v2 after replication).

### Budget envelope

- Evaluator compensation: 13 evaluators × $200 honorarium =
  $2,600.
- IRB/ethics review (if pursuing publication): $500-2,000
  depending on institution.
- Fieldwork tooling (survey platform, response collection):
  $0-$500 for a 30-participant study.
- Total: $3,000-5,000 for v1.

### What proceeds before v1 begins

Three dependencies have to be met:

1. **Live Claude Desktop MCP validation** (human-only step in
   the current roadmap). Workstream 3 specifically requires
   the MCP server to be running reliably in Claude Desktop
   with real users.
2. **TypeScript MCP v1 (Option B)** is not blocking. Workstream
   3 can run on the Python MCP server; the TypeScript path is
   a distribution question, not an evaluation question.
3. **Evaluator recruitment protocol.** Need 13 external
   evaluators without conflict of interest (not users of the
   hosted app, not collaborators on the research program). The
   recruitment channel and screening criteria are open.

## What this program does not promise

- It does not promise that any of the three claims will
  validate at the threshold named. They might not. That is
  what validation means.
- It does not promise the sovereignty case is the "right" or
  "most useful" framing of Framecheck's contribution. It
  tests whether the specific claim made in public copy
  replicates under independent measurement.
- It does not promise that the prompt-model gap is untestable.
  It argues that the gap is a disappearing variable, and that
  anchoring validation on it is a bet on a disappearing claim.
  A skeptic who wants the gap tested can commission a study;
  this program will not prioritise it.

## Open decisions (activate on trigger)

These five questions do not need answers today. They need
answers when a trigger fires and formal v1 activates. Recording
them here means the activation conversation starts from the
right place rather than rebuilding context.

1. **Evaluator recruitment channel.** Academic networks,
   Twitter/Bluesky calls, paid-platform (Prolific, UserTesting),
   snowball from reviewer cohort? Different channels produce
   different selection biases. The trigger that activates v1
   often tells you which channel is right: an unsolicited
   academic inquiry suggests snowball from that academic; a
   citation in a published paper suggests the author's
   research network; a market-pressure event suggests
   practitioner recruitment via Prolific-style platforms.
2. **Honorarium amount.** $200 per evaluator baseline for
   multi-hour structured review; practice varies by field.
   Decide when the recruitment channel is chosen (academic
   salaried evaluators may decline payment in favor of
   co-authorship; independent scholars need meaningful
   compensation for the time).
3. **IRB posture.** Skip for v1. If v1 outputs might be
   published beyond a research blog post, IRB approval is
   needed upfront. For internal evidence that triggers
   publication preparation, retroactive IRB is not available;
   make the pre-registration + IRB decision when v1 activates,
   not when results land.
4. **Pre-registration.** Should v1 be pre-registered (e.g., on
   OSF) before recruitment? Pre-registration strengthens the
   credibility of any reported null result but adds setup
   overhead. Default: yes if the program produces a null result
   that would be cited defensively; no otherwise.
5. **Timing.** v1 takes roughly 3 months end-to-end. Does the
   broader research program calendar have space for it at the
   time the trigger fires, or does activating v1 require
   pausing other work?

## Why the observational plan is the right v1

Because the tool's primary audience (agent builders,
AI-literate practitioners) validates the compound claims in a
stronger form than a paid evaluator study. Real adoption is
real evidence. Formal validation in an artificial setting
before organic adoption exists is literature that is
interesting-inside-the-project and uncited-outside-it.

Because the opportunity cost of running a $3,000-5,000 study
for 3 months before the tool has ship-time in the wild is
high. The same budget can fund five more worked examples, the
flagship integration named in the canon-play memo, or
honoraria for the first academic collaborators who approach
the research on their own initiative.

Because the stress-test analysis above remains intact. The
three durable Claims (1, 2, 3) are what a formal v1 should
measure when it activates. Pausing execution does not pause
the thinking. The blueprint is ready to ship on trigger.

The discipline memory flag ("Compound claims have zero
coverage") is acknowledged by the observational program:
coverage begins to accrue as soon as the tool ships and real
users engage. Formal v1 validation adds a second evidence
type on top of observational evidence once a trigger says the
timing is right.
