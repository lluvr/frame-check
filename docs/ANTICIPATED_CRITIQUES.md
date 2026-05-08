# Anticipated Critiques

**Status:** v1, 2026-04-21. Consolidates the adversarial readings surfaced across STRESS_TEST_ASSESSMENT_v1.md, PUBLISH_READINESS_ASSESSMENT_v1.md, CONSTRUCT_HONESTY_AUDIT_v1.md, `CORRESPONDENCE_STUDY_v1.md §5`, `THRESHOLD_SENSITIVITY_v1.md §3`, and `METHODOLOGY.md`. Written so a reviewer landing cold sees the project's own enumeration of what it expects to be attacked on, and the project's prepared defenses, rather than having to excavate them across twelve documents.

**Audience.** Peer reviewers, skeptical practitioners, adversarial readers, future curators. A reviewer's job is easier when the project has already named the attacks; a curator's job is easier when the defense surface is one page rather than distributed.

**Discipline.** Each critique below is named as it would appear from an attacker's voice. The response is not defensive; it cites the specific artifact that answers (or, where the attack lands, acknowledges the gap and names what would close it). Where the defense relies on work that has not yet happened, the critique is flagged with `[OPEN]`.

---

## 1. Methodology critiques

### C1.1 "Regex is 1990s; where's the ML model?"

**Attack.** Structural detection with handcrafted regex is pre-modern. A contemporary tool would use a trained classifier, ideally fine-tuned on an annotated framing corpus.

**Response.** The construct-honesty posture is the contribution, and it requires deterministic reproducibility at the measurement layer. An ML classifier would add opacity without closing the reader-aid question Track B actually tests. AI-assisted interpretation is shipped as separately-labeled enrichment (`framing_ai.py`, documented in `/privacy` and `METHODOLOGY.md §1.1`). The project's rejection list at `fvs_eval/SPEC.md §14` names "trained classifier" as an explicit non-goal and explains why.

**Where it would land.** If the project positions itself as "state-of-the-art framing detection," the attack lands. The project positions itself as "construct-honest structural framing with reproducible measurement," which is a different claim.

---

### C1.2 "F1 = 0.36 means your detector does not work."

**Attack.** The pre-registered validation produced macro-F1 = 0.36 against the union of two labelers, below the pre-registered 0.4 useful-floor. The detector failed its own test.

**Response.** Per pre-registration, verdicts do not retroactively re-scope; the project did not rescue the result by lowering the threshold. What the F1 measures is detector-vs-labeler classification; what the project ships measures reader-aid (surfacing the detector's own limits to the reader rather than asserting labels with false confidence). These are orthogonal questions. The pivot from F1-as-target to reader-aid-as-posture is documented; Track B (reader-aid) is separately pre-registered with its own falsifiable threshold.

**Where it lands partially.** Until Track B runs, the pivot is aesthetically coherent but functionally unvalidated. Track B execution is the definitive answer. `[OPEN]`

---

### C1.3 "Construct-honesty is just new words for uncertainty quantification."

**Attack.** Naming a posture "construct-honest" does not make it new. Measurement theory has addressed validity, reliability, and lower-bound claims for decades.

**Response.** The novelty claim is narrow: no prior structural-framing tool ships real-time sentence-level attribution paired with per-signal reader-aid surfacing in an MCP contract with `how_to_serialize` agent guidance. Each piece has precedent; the combination at the system-contract level does not (to the best of the authors' knowledge). The defense rests on the COMBINATION being novel, not the individual primitives.

**Where it lands.** If a reviewer produces prior work that ships the same combination at the system-contract level, the novelty claim needs revision. The project's obligation is to cite that work, not to withdraw the posture.

---

### C1.4 "You can Goodhart by writing text that avoids your regex."

**Attack.** A motivated writer can produce prose that systematically avoids the Frame Check vocabulary list while still framing adversarially. The detector can be gamed.

**Response.** True and deliberate. `METHODOLOGY.md §1` and `FRAMING_ANALYSIS.md` honest-limits name this. Semantic framing detection would close the Goodhart surface but is held against per `STRATEGY.md §6` durable decision "Minimize LLM calls." The construct-honest posture is the mitigation: the detector surfaces what it measures (vocabulary-based markers) AND what it does not (semantic intent), so a reader of Frame Check's output knows the Goodhart boundary rather than being told "the document is balanced."

**Where it lands.** If the project claims adversarial robustness, the attack lands. The project does not.

---

### C1.5 "AI-coder correspondence study is circular."

**Attack.** CORRESPONDENCE_STUDY_v1.md used two AI coders from the same model family, with the rubric author also being the pattern author. Correlated errors + author-rubric overlap means the 50%/78% correspondence rates are inflated by construction.

**Response.** Named in `CORRESPONDENCE_STUDY_v1.md §5` (`What this study does NOT establish`) and in `DR-12` of `SESSION_STATE.md §3`. The study is framed explicitly as "AI-coder correspondence pilot," not "validated reader-correspondence measurement." The mitigation: human-coder replication (`E-1` per `PUBLISH_READINESS_ASSESSMENT_v1.md §3.2`) at 2-3 grad student coders, $200-400 budget. Until executed, this attack lands on any claim that cites the rates as validation rather than pilot. `[OPEN]`

---

### C1.6 "N=28 corpus is too small to generalize."

**Attack.** Every empirical rate in the project (71% residual-analytical, 50% coverage correspondence, 78% epistemic correspondence, 0% temporal balanced, 3.6% voice borderline) is conditional on the 28-document validation corpus. Population-level behavior is unmeasured.

**Response.** True and consistently qualified. Every reporting artifact includes the "on the N=28 validation corpus, stratified, not representative" caveat. The corpus composition (human-authored / AI-generated / Wikipedia strata) is documented in `fvs_eval/validation_study/DESIGN.md`. Corpus expansion is an `[E-3]` gap flagged at `PUBLISH_READINESS_ASSESSMENT_v1.md §3.2`; 5-15 hours of editorial curation to test construct-honesty transfer.

**Where it lands.** The attack always lands at publication level and is always ceded. The project's obligation is to disclose N=28 everywhere and to expand when external engagement justifies the editorial time. `[OPEN]`

---

## 2. Library / taxonomy critiques

### C2.1 "Single-curator taxonomy is just your opinion."

**Attack.** 20 FVS entries, all `draft`, authored by one person. There is no inter-rater reliability data, no second curator, no external review. The library is the project's opinion, not a consensus artifact.

**Response.** Accurate as stated. `GOVERNANCE.md §canon-promotion` names this directly. Zero entries are `canon`; every published entry carries the DRAFT marker. The first canon promotion (`data/frame_library/promotions/FVS-001_v1.md`) requires 2-3 external reviewers per `REVIEWERS.md v0.1`. The opinion nature is not hidden; the DRAFT marker is the evidence.

**Where it lands.** If the project cites FVS entries as authoritative, the attack lands. The project cites them as DRAFT-grade candidates for external review. The attack and the defense agree on the facts; they disagree on whether this is acceptable. It is acceptable for a v0 research artifact; it is not acceptable for a consensus reference. The project claims the former, not the latter. Until first promotion, this honest claim holds; after first promotion, the claim upgrades to "one entry consensus-validated by three external reviewers."

---

### C2.2 "11 of 20 FVS entries never activate on the validation corpus."

**Attack.** `FVS_COACTIVATION_REPORT.md §6` shows more than half the library is inert on the test corpus. The "citable vocabulary" claim rests on 9 active entries; the other 11 are conceptual placeholders at best.

**Response.** Named with specific taxonomy at DETECTION_RULE_AUDIT_v1.md: 3 entries are intentional-no-rule (metaframes / interaction-only patterns that text-alone cannot detect); 6 have missing rules that were proposed but reverted due to canon conflicts (INDEX.md classifies them meta-side-n/a); 2 have thresholds exceeding any corpus document's reach. The inertness is diagnosed, not hidden. A decision surface exists (reclassify meta-side, expand corpus, deprecate) and is flagged at `PUBLISH_READINESS_ASSESSMENT_v1.md §2.10 CAN-2` as curator-strategic.

**Where it lands.** The attack correctly names a fragility: if the 9 active entries fail to promote and the 11 inert entries are not resolved, the library's citable-vocabulary claim collapses to a small set. The defense is that the diagnosis is public and the decision surface is named; the attack is that diagnosis alone is not progress.

---

### C2.3 "Voice construct-honesty took four self-audit passes to enumerate five surfaces."

**Attack.** The construct-honesty audit v1 (2026-04-20) named 3 violation surfaces. v1.1 (2026-04-21 fresh-eyes) added a 4th. v1.2 (2026-04-21 exhaustive grep) added a 5th. The progression is empirical evidence that self-audit cannot be trusted to enumerate surfaces.

**Response.** Correct. Explicitly acknowledged at `CONSTRUCT_HONESTY_AUDIT_v1.md §6` and as a §5.1 discipline-drift observation. The defense is not "we got it right on the first try"; the defense is "we named when we got it wrong, we shipped the fix (L3a across all five surfaces, 2026-04-21), and we documented the pattern as grounds for independent review." An external reviewer may surface a sixth surface; the project's obligation is to ship a fix and document the re-pass.

**Where it lands.** Fully. Self-audit is lower-grade than independent audit. The project does not claim otherwise.

---

## 3. Strategic critiques

### C3.1 "Zero external engagement in six weeks of work."

**Attack.** The project has shipped substantial internal work. Zero reviewers engaged. Zero papers submitted. Zero citable canon promotions. Zero measurable user base. Zero agent framework MCP integrations. Internal work without external engagement is shelf-ware.

**Response.** Exact diagnosis. `STRESS_TEST_ASSESSMENT_v1.md §2.1` names "zero external engagement is the rate-limiter on everything." The project's response is (a) ready the infrastructure so when engagement arrives it has a target to land on (governance, dossiers, REVIEWERS.md v0.1, CITATION.cff, licensing, publish-readiness assessment), and (b) surface the gap explicitly rather than pretending internal completeness equals external validation. `PUBLISH_READINESS_ASSESSMENT_v1.md §2.9 Scenario B` explicitly names the failure mode: "infrastructure became the product." Zone 2 and Zone 3 of that assessment are entirely external-engagement moves; all are curator-relational or curator-strategic.

**Where it lands.** Fully and unavoidably until the first external engagement lands. The project's obligation is to position for that moment, not to manufacture it from internal work alone.

---

### C3.2 "MCP contract is aspirational; zero agent frameworks have adopted."

**Attack.** The "MCP-first distribution" thesis per STRATEGY.md depends on agent framework adoption. Zero adopters exist. The contract is designed; the market has not responded.

**Response.** True. `STRESS_TEST_ASSESSMENT_v1.md §3` names it as load-bearing empirical question #3. The project ships the contract on the thesis that an agent framework will encounter structural-framing-analysis as a capability worth integrating. Specific outreach (`D-1` per `PUBLISH_READINESS_ASSESSMENT_v1.md §3.2`) to framework authors is Zone 3. The contract itself is designed to minimize friction for adopters (MCP resources addressable by stable URI; `how_to_serialize` instructs agents on faithful restatement; `provenance.analysis_timestamp_utc` makes citations reproducible), but design alone does not produce adoption. `[OPEN]`

---

### C3.3 "Sovereignty and canon-play framings are internal conviction."

**Attack.** The "sovereignty instrument" and "canon play" language in STRATEGY.md and memory notes is internal strategic framing. External academic reviewers read "sovereignty instrument" differently than the project's internal meaning. Some internal strategic language does not travel.

**Response.** Correct. `STRESS_TEST_ASSESSMENT_v1.md §2.10` names this explicitly. The public-facing surface (`frame.clarethium.com`, README.md, methodology paper outline) uses external-audience-calibrated language ("structural framing analysis tool," "public research program," "construct-honest detection"). The strategic-internal language lives in STRATEGY.md and SESSION_STATE.md where its audience is self and future-self. An external reviewer who reads the internal-strategic language and interprets it at face value is reading an internal document; the obligation is to be coherent across registers, not to flatten the internal register.

---

## 4. Operational critiques

### C4.1 "Observatory has run-pause-run-pause cadence."

**Attack.** Tier B observatory has a stop-resume cadence on record. A longitudinal corpus with undocumented operational gaps is not a citation-grade corpus.

**Response.** Fully acknowledged. The cadence is logged in the observatory state record; no artifact cites observatory continuity without the reliability caveat. Four options (repair / retire / reframe-Tier-A-as-primary / hybrid) are named with trade-offs; decision pending.

**Where it lands.** The longitudinal-corpus claim carries a reliability caveat now and will either be validated (repair + diagnosis) or reframed. Until one path ships, citations to the observatory as a continuous asset should be qualified.

---

### C4.2 "Detector construct-honesty surfaces shipped are not the same as user-facing help."

**Attack.** Track B was designed to measure whether construct-honest prose actually helps readers. Track B has not run. The project has shipped construct-honest prose across five voice surfaces (L3a, 2026-04-21); the user-aid claim that motivated the posture remains untested.

**Response.** Correct. `CONSTRUCT_HONESTY_AUDIT_v1.md §6` names "no user-study evidence" explicitly. The defense is two-layered: the prose change is a construct-honesty alignment (making the instrument internally consistent; answering the self-audit pattern), and Track B (`fvs_eval/reader_aid_study/DESIGN_v1.1.md`) is the pre-registered measurement of whether the user-aid claim holds. Track B execution is Zone 3 per the publish-readiness assessment. `[OPEN]`

---

## 5. Legal / compliance critiques

### C5.1 "No formal Terms of Service for a public-facing tool."

**Attack.** The site is public and accepts user text submissions. A ToS surface is legally customary and, in some jurisdictions, near-required for a free public service.

**Response.** Privacy page (`/privacy`) exists and names the data-handling contract. A ToS skeleton is drafted at TERMS_OF_SERVICE_DRAFT.md (2026-04-21, pending curator ratification); if ratified, it ships at `/terms` with a parallel route. The decision to ship or not to ship is curator-scope.

**Where it lands.** The attack lands on the public-surface gap until the skeleton is either ratified or explicitly retired with a curator decision recorded.

---

### C5.2 "User text transits to Grok/Gemini when AI interpretation is on."

**Attack.** The privacy page says "Frame Check does not store document text," but the AI interpretation flow sends user text to third-party LLMs. An inattentive reader sees only the "does not store" claim and misses the transit.

**Response.** Covered at `/privacy §"Third-party services"`. The 2026-04-21 re-read (L-3 per `PUBLISH_READINESS_ASSESSMENT_v1.md §4 Zone 1`) tightened the wording to specify that full text is sent for documents ≤ 3,000 characters and an excerpt (first 2,000 + last 1,000) for longer documents. Users who prefer no LLM-side processing can use the structural layer without configuring AI keys.

**Where it lands.** Privacy-conscious users who skim the page may still miss the notice. A more prominent placement (above the fold on the /privacy surface, or a flag on the analysis page itself) would reduce this risk further. Not blocking, but an improvement surface.

---

## 6. Publishing / research-output critiques

### C6.1 "No arXiv preprint, no published paper, no citations."

**Attack.** The project has a detailed methodology paper outline, a working instrument, and a six-week audit trail. It does not have a single publication external to the project's own self-references. Citation graph is empty.

**Response.** Intentional and strategic. `SESSION_STATE.md §4` (ED-1 entry) names the decision: methodology paper v2 is curator-owned, co-authored with the first engaged academic reader. Drafting the paper solo before the first reader engages would overspecify against imagined reviewers. The short-form arXiv preprint (`P-3` per `PUBLISH_READINESS_ASSESSMENT_v1.md §3.2`) is named as Zone 3; the ED-1 sovereignty manifesto (`P-1`, curator-owned draft) is a public-audience piece on a faster timeline.

**Where it lands.** The one-year test at `SESSION_STATE.md §6` is explicit: ≥ 1 publication live, externally cited, within one year. The gap is real and is the correct kind of gap (external-dependent, not internal-deferrable). The project's obligation is to execute the publications when the engagement unlocks, not to manufacture citations from internal work. `[OPEN]`

---

## 7. Ethical / dual-use critiques

### C7.1 "Agent integrations could suppress minority framings."

**Attack.** An agent using Frame Check as an "editor" could flag diverse framings as deficient (low coverage, borderline voice, missing stakeholders). The construct-honesty posture mitigates this in principle, but integrators can override.

**Response.** Named as a dual-use concern at `PUBLISH_READINESS_ASSESSMENT_v1.md §2.6`. The MCP contract `agent_guidance.dual_use_note` (added 2026-04-21 per `ET-1`) explicitly tells integrators that coverage gaps and voice classifications must not be reduced to quality scores or editing rules. Construct-honest phrasing ("no directive markers detected" rather than "lacks directive content") is the instrument-level mitigation; agent integrators who restate in existential terms are outside the tool's design scope.

**Where it lands.** If an agent integration ignores the dual_use_note and ships "this document is biased" from Frame Check output, the harm is real. The tool's obligation is to make the misuse pattern harder (documentation + contract text). It cannot prevent integrators from ignoring the guidance.

---

### C7.2 "Reader construct served by 'construct-honest' prose is literature-informed, not general-audience."

**Attack.** Readers who understand why "no directive/promotional/descriptive voice markers detected" is more honest than "analytical voice" are already measurement-theory-literate. For general audiences, the evidence-absence phrasing reads as obfuscated or hedged.

**Response.** Track B's question. `CONSTRUCT_HONESTY_AUDIT_v1.md §6` names "no user-study evidence" as a limit; the audit is an internal consistency check, not a reader-comprehension check. Track B is the measurement that would answer the critique directly. `[OPEN]`

---

## 8. Honest limits of this document

- **This document is itself a self-audit.** The critiques below are the ones the project sees; an external reviewer reading the full repo would surface different (and likely sharper) ones. The v1.0 → v1.3 progression of CONSTRUCT_HONESTY_AUDIT_v1.md is evidence that self-audits miss surfaces; the pattern generalizes.
- **The defenses cite the project's own documents.** That is appropriate where the defense is about how the project positions a claim; it is circular where the defense is about whether the claim holds. `[OPEN]` flags mark the places where the defense depends on external work not yet executed.
- **Jurisdiction-specific and domain-specific critiques are missing.** A reviewer specific to (e.g.) legal tech, medical AI, or financial advisory would produce critiques this document does not enumerate. Frame Check is domain-neutral by design; the critiques above are domain-neutral too.
- **Framing of the research program evolves.** A critique-response pair that is appropriate at v0.3.1 methodology may not hold at v1.0 if the research program reframes. This document should re-run at each methodology version bump.

---

## 9. Cross-references

- `docs/VALIDATION_PROGRAM.md`: the full validation program (Track A F1 result, Track B pre-registration, observational + formal plans).
- `docs/RATERS.md`: reviewer terms and first-promotion target.
- `GOVERNANCE.md` "Canon promotion": canon-trajectory taxonomy and zero-promotions acknowledgment.

---

*v1. 2026-04-21. Written so a reviewer sees the project's self-enumerated attack surface on one page. Complements but does not replace the methodology-paper §7 limitations section that will emerge from co-authorship with the first engaged academic reader.*
