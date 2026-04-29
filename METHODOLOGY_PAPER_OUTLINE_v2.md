# Methodology paper outline v2

**Status**: outline v2, 2026-04-27. Supersedes METHODOLOGY_PAPER_OUTLINE_v1.md (2026-04-20). v1 is preserved for diff inspection; this v2 incorporates infrastructure shipped between 2026-04-20 and 2026-04-27 (L5 per-level claim treatment, adversarial fixture suite, construct-validity audit v1).

**Submission gating** (unchanged from v1): submission gated on (a) curator venue decision, (b) Track B reader-aid study results if the paper claims reader-aid value rather than methodology alone, (c) curator editorial review.

**What changed in v2** (read this first):

1. **The methodological centerpiece shifts from "construct-honesty posture across 5 signals" to "per-level claim discipline (L5) across N constructs at 4 epistemic strata."** The L5 framework is a more general contribution that subsumes v1's framing and applies uniformly to constructs added after the original 5 (frame_patterns, decision_readiness_dims, frame_deepening, absence_clusters, frame_opportunities).

2. **Adversarial fixtures become a third evidence type alongside the N=28 validation corpus and Track B reader-aid study.** Each fixture pins the substrate's behavior on a deliberately-composed motivated-writer document; the suite is regression infrastructure with stronger discipline than the corpus (the substrate is NOT iterated against fixtures to defeat them).

3. **The construct-validity audit (CONSTRUCT_VALIDITY_AUDIT_v1.md) becomes the §4 spine.** It walks 13 substrate constructs (12 in v1.0; construct #13 V4.2 LLM-judge FVS detection added in v1.1 on 2026-04-27) through five evaluator questions (validity, honesty, calibration, failure modes, reproducibility). v1's §4 walks 5 signals; v2's §4 walks 13 constructs at 5 claim levels using the audit as the canonical reference. The audit's v1.1 surfaced an L5 framework gap (V4.2 binary judgments without confidence/runner-up structure fit none of the four original claim levels cleanly); v1.2 (2026-04-28) resolves the gap by adding a fifth claim level `llm_classifier_output` per Proposal A. v2 §4 frames the surfacing-and-resolution as load-bearing evidence the framework is honest about its own limits AND can extend to accommodate new evidentiary shapes without collapsing per-level clarity.

4. **Honest limits section grows.** Three new limits enter from the post-v1 infrastructure: cascade-error inheritance in composed_pattern constructs; adversarial-fixture-suite-as-not-representative-sample; LLM-augmented-construct nondeterminism.

5. **Curator decisions that v2 leaves open** (same as v1, plus one new): venue choice, authorship shape, Track B sequencing, agent-attribution; new in v2: whether to cite the L5 framework as a contribution distinct from construct-honesty posture, or as its operationalization.

---

## 1. Target contribution (v2 restatement)

**Primary claim (revised).** Structural framing analysis tools emit signals at heterogeneous epistemic strata (regex match counts, deterministic classification cascades, LLM-judge classifications, multi-signal compositions, language-model interpretations) and conflate them into a single "result" surface that readers systematically over-interpret. We introduce a per-level claim discipline (L5) that tags every emitted construct with one of five claim levels (`detector_measurement`, `classifier_output`, `llm_classifier_output`, `composed_pattern`, `agent_generated`), pairs each construct with a construct-honesty posture (signal_type + statement + how_to_serialize), and validates the discipline with two evidence streams: (a) a stratified N=28 validation corpus measuring construct prevalence and (b) an adversarial fixture suite pinning the substrate's behavior on motivated-writer documents that target known operationalization gaps. The fifth level (`llm_classifier_output`) was added 2026-04-28 in audit v1.2 to accommodate LLM-judge binary classifications (V4.2 FVS detection) without forcing them into the deterministic-cascade `classifier_output` level; the surfacing-and-resolution arc (v1.0 four levels; v1.1 surfaces gap; v1.2 resolves with addition not retrofit) is itself evidence that the L5 discipline is honest about its own limits.

**Structural novelty (v2 expansion).** No prior structural-framing tool ships per-level epistemic-status tagging on every emitted entity. The combination of (i) 4-level claim discipline across 12+ constructs, (ii) construct-validity audit as living regression artifact, and (iii) adversarial fixture suite as construct-stress-testing infrastructure is, to the best of the authors' knowledge, novel.

**Empirical contribution (v2 additions).**
- N=28 validation corpus: under-detection prevalence per signal (unchanged from v1: coverage 36%, epistemic 11%, claims 1/18).
- Adversarial fixture suite (N=2 as of 2026-04-27): each fixture pins the substrate's reading on a motivated-writer document; fixtures expose specific operationalization gaps with per-level diagnosis (sales_pitch_as_analysis exposed narrative misclassification on `in YYYY` patterns, since fixed; instruction_without_troubleshooting exposes recommendation-regex over-match and instruction-regex markdown-header gap, currently open).
- Construct-validity audit v1.2 (as of 2026-04-28; v1.1 superseded same-week): 13 constructs audited through 5 evaluator questions at 5 claim levels (v1.0 had 12 constructs at 4 levels; v1.1 added construct #13 V4.2 LLM-judge FVS detection and surfaced the L5 framework gap; v1.2 resolves the gap by adding `llm_classifier_output` as the fifth claim level per Proposal A); 5 known residual cases enumerated; cross-surface alignment matrix (template / portrait / MCP / comparison / LLM context) per construct; the resolution narrative shows the framework can extend to new evidentiary shapes without collapsing per-level clarity.

---

## 2. Proposed structure (v2 revision)

Eight sections (length targets unchanged from v1: ~8-10k words for CSCW/CHI; ~5-7k for arXiv; 12-15k for journal).

### §1 Introduction (~800 words)

- Problem (revised): structural framing tools report at heterogeneous epistemic strata without distinguishing them; readers cannot tell which claims are mechanical surface evidence vs cascade classification vs multi-signal composition vs language-model interpretation. The conflation produces over-interpretation in both directions (false confidence in pattern matches; false skepticism of well-supported compositions).
- Concrete failure motivation: the VISITOR_AUDIT semiconductor-essay case (unchanged) PLUS the adversarial fixtures' headline finding (genre misclassification cascading into wrong frame_pattern firing in instruction_without_troubleshooting, demonstrating per-level visibility of cascade errors).
- Contribution summary (three bullets, mapping to §3-§4-§5 plus §6 evidence streams).
- Paper structure preview.

Source material: `VISITOR_AUDIT.md §4 Failure 1, §4 Failure 3`; `data/adversarial_fixtures/instruction_without_troubleshooting/audit.md`; `CONSTRUCT_VALIDITY_AUDIT_v1.md §1`.

### §2 Related work (~700 words; unchanged from v1)

Anchors unchanged. v2 may add measurement-validity literature anchored on Cronbach and Meehl 1955 (construct validity foundational) and Adcock and Collier 2001 (measurement validity in qualitative-quantitative bridge) since the L5 framework operationalizes construct-validity discipline at the per-emit level.

### §3 The Frame Vocabulary Standard (~900 words; unchanged from v1)

Library structure, governance, co-activation, audit. Unchanged from v1 §3.

### §4 The L5 per-level claim discipline (~2000 words; major revision)

**Core methodological contribution.** v2's §4 replaces v1's "construct-honesty posture across 5 signals" with the more general L5 framework. The five signals from v1 become specific cases of the broader discipline.

#### §4.1 The five claim levels

Tabulate the five claim_level values with epistemic status and treatment (v1.2 update: a fifth level `llm_classifier_output` was added 2026-04-28 per CONSTRUCT_VALIDITY_AUDIT_v1.md v1.2 to resolve the L5 framework gap that V4.2 LLM-judge FVS detection exposed in v1.1):

| Level | Epistemic status | Treatment |
|---|---|---|
| `detector_measurement` | Mechanical surface evidence (regex/heuristic match) | Cite by count and surface; do not infer reasoning. |
| `classifier_output` | Decision over surfaces with confidence + runner-up (deterministic cascade) | Restate per construct.how_to_serialize; surface confidence and runner-up explicitly. |
| `llm_classifier_output` | LLM-judge binary or categorical classification with curated definition + reasoning text but WITHOUT per-emission confidence/runner-up structure | Cite as engine-judged classification with macro-F1 and per-frame reliability tier evidence; the borderline-vs-decisive distinction is a property of the macro aggregate, not the per-emission. |
| `composed_pattern` | Derived from upstream constructs; inherits cascade errors | Cite the composition; if upstream is uncertain, inherit that uncertainty. |
| `agent_generated` | LLM reasoning over substrate output | Cite as agent reading; not substrate measurement. |

The L5 framework's purpose is per-level visibility: an evaluator can read claim_level on any emitted entity and immediately know what kind of evidence backs it. v1.2 distinguishes `classifier_output` from `llm_classifier_output` because their evidentiary shapes differ in a load-bearing way: the deterministic cascade produces per-emission confidence + runner-up structure, while LLM-judge classification produces binary outputs with reasoning text and macro-aggregate reliability evidence. Conflating them would let a reader treat an LLM-judge binary as if it carried per-emission confidence, which it does not.

#### §4.2 The construct-honesty mechanism (signal_type + statement + how_to_serialize)

Each construct emits a `construct` block with three keys. signal_type names the construct's shape (vocabulary_and_pattern_detector / cascade_classification / distribution_with_dominant / scoring_with_runner_up / composed_dimension / llm_judge_binary_classification). statement defines the construct in operational terms and names what the construct does NOT measure. how_to_serialize instructs the agent on correct restatement form. The construct-honesty mechanism unifies the 13 substrate constructs under a single discipline; CONSTRUCT_VALIDITY_AUDIT_v1.md (v1.2 as of 2026-04-28) is the canonical per-construct walk and includes the 13th construct (V4.2 LLM-judge FVS detection, evaluation-engine-only) at the new fifth claim level `llm_classifier_output`. The L5 framework gap v1.1 surfaced (V4.2's binary-without-confidence-or-runner-up shape fitting none of the original four levels) is resolved in v1.2 by the addition of the fifth level rather than a forced retrofit, preserving per-level epistemic clarity.

#### §4.3 Per-claim-level worked examples

Four worked examples, one per level (skip agent_generated; nondeterministic):

- **detector_measurement**: FVS-007 Failure Framing detection on instruction_without_troubleshooting (regex fires correctly; the substrate emits the count and matched_spans; no reasoning claim is made).
- **classifier_output**: voice cascade on sales_pitch_as_analysis (cascade fires `promotional` HIGH; margin_to_threshold and runner_up emitted; how_to_serialize requires "classified as promotional" not "the document is promotional").
- **llm_classifier_output**: V4.2 LLM-judge binary FVS detection on a per-document per-frame emission. The on-disk shape (engine-internal, evaluation-only as of 2026-04-28) carries `{fvs_id, exhibits, reasoning, reliability, honest_limit}`. The wire-shipping shape (when V4.2 first lands on MCP) carries the same fields plus `claim_level: "llm_classifier_output"` and a `construct` block with `signal_type: "llm_judge_binary_classification"`. The reasoning text is the engine's per-emission rationale, not a confidence proxy; the reliability tier carries the macro-aggregate evidence. Contrasting with classifier_output (the v1.1 PROVISIONAL disposition v1.2 supersedes) makes the per-level distinction load-bearing for the reader. CONSTRUCT_VALIDITY_AUDIT v1.2 carries the full worked example.
- **composed_pattern**: recommendation-without-falsification firing on instruction_without_troubleshooting (composed from upstream genre + FVS-007 + falsification_count; inherits genre misclassification; the L5 framework makes the cascade visible per-layer).

#### §4.4 The five v1 signals as instances of the L5 framework

Subsections covering coverage, epistemic, claims (under detector_measurement composed into composed_pattern), voice and temporal (under classifier_output). v1 §4.1-§4.5 content compresses into this section as L5-framework instances. Empirical prevalence numbers (36%, 11%, 1/18; voice and temporal threshold-coupling qualifiers from THRESHOLD_SENSITIVITY_v1.md) preserved.

#### §4.5 The constructs added since v1

frame_library_matches (20 FVS frames at detector_measurement); frame_deepening (3 sub-constructs at detector_measurement); frame_patterns (8 patterns at composed_pattern); decision_readiness_dims (5 dimensions at composed_pattern); absence_clusters (composed from frame matches and dimensions); frame_opportunities (opt-in agent_generated); V4.2 LLM-judge FVS detection (construct #13 at the new llm_classifier_output level, evaluation-engine-only as of 2026-04-28; first MCP wheel that ships V4.2 emissions on the wire MUST tag them with the new claim_level per the v1.2 wire-shipping discipline). Each gets a paragraph with construct, claim_level, what-it-measures, what-it-does-NOT-measure. CONSTRUCT_VALIDITY_AUDIT_v1.md (v1.2) is the canonical reference.

### §5 Measurement and reproducibility (~800 words; v2 additions)

v1 content (deterministic scripts, MCP contract versioning, test coverage, data availability) preserved. v2 additions:

- **Adversarial fixture suite** as regression infrastructure: each fixture has document.md (the input), expected.json (the substrate's pinned reading), audit.md (per-level catch-vs-miss). Test runner auto-discovers fixtures from `data/adversarial_fixtures/`. Substrate is NOT iterated against the fixture (the fixture stays the regression bar; substrate evolves and the expected.json updates).
- **Construct-validity audit** as living artifact: version increments on construct changes; prior versions retained; fixture suite re-run on increment.
- **Test coverage updated**: 229 tests on test_mcp_server.py + test_adversarial_fixtures.py; 47/47 project suites passing (as of 2026-04-27).

### §6 Validation (v2: three evidence streams)

v1 had two paths (Track A classifier validation; Track B reader-aid). v2 expands to three.

#### §6a Classifier validation (Track A; unchanged from v1)

Pre-registered, F1=0.36 on N=28, framed as motivating the construct-honest pivot. Unchanged from v1 §6a.

#### §6b Reader-aid validation (Track B; unchanged from v1)

Pre-registered, awaiting execution; the paper draft sequencing depends on whether Track B runs pre-submission. Unchanged from v1 §6b.

#### §6c Adversarial fixture suite (Track C; new in v2)

Each fixture composes a motivated-writer document targeting a specific operationalization gap, captures the substrate's reading as expected.json, and audits per-level catch-vs-miss. The discipline holds: compose once, capture, audit honestly; substrate evolves separately, fixture stays the regression bar.

Status at v2 outline-write time (2026-04-27): N=2 fixtures committed (sales_pitch_as_analysis, instruction_without_troubleshooting). Each exposed specific gaps with per-level diagnosis. The first fixture's gap (narrative misclassification on `in YYYY`) was fixed via genre-classifier tightening; the second's gaps (recommendation regex over-match; instruction regex markdown-header miss) are documented as Move A and Move B; tightening commits separate from the fixture commit, per discipline.

Track C contribution: it complements Track A's representativeness-bound F1 measurement with motivated-writer worst-case stress testing. Together with the construct-validity audit (which enumerates known residuals), Track C makes the substrate's failure modes inspectable rather than buried.

### §7 Limitations and honest limits (~700 words; v2 expansions)

v1 honest-limits preserved (corpus N=28; stratification; candidate-vs-primary not equivalent; voice/temporal threshold-coupling; library single-curator; Track B under-powered; English-only). v2 additions:

- **Cascade errors in composed_pattern**: composed constructs inherit upstream errors. The L5 framework makes the cascade auditable per layer but does not eliminate it. instruction_without_troubleshooting is the worked-example evidence: bad genre at classifier_output drove wrong frame_pattern at composed_pattern.
- **Adversarial fixture suite is not representative**: N=2 fixtures as of 2026-04-27 are a regression bar, not a representative sample of failure modes. Fixture composition is operator-driven (motivated-writer scenarios the curator chose to test); generalization to all motivated-writer styles requires more fixtures.
- **LLM-augmented constructs are nondeterministic**: frame_opportunities (agent_generated) requires fixing model version, prompt, temperature for reproducibility. The substrate does not version-pin the model on the user's behalf. Graceful degradation contract: empty result is a valid output state.
- **Substrate measures STRUCTURE, not TRUTH**: every construct in the L5 framework operationalizes a structural property. Documents with high coverage / calibration / balanced voice / rich frame patterns can still be wrong; documents with low scores can still be correct. The substrate surfaces structure as a reading aid, not as a quality verdict.

### §8 Conclusion (~400 words; v2 reframing)

v1's restatement compresses to a paragraph; v2 emphasizes the L5 framework as a generalizable contribution applicable beyond Frame Check (any structural-analysis tool that emits at heterogeneous epistemic strata can adopt per-level claim discipline). Future work: Track B execution (unchanged from v1); fixture suite expansion; construct-validity audit version increments; cross-tool L5 adoption (the framework as a methodological template for structural-analysis tooling generally).

---

## 3. Key figures (v2 revisions)

v1 had six candidates; v2 keeps F1-F4, revises F5, replaces F6, adds F7-F8.

**F1. L5 framework table.** Replaces v1's "construct-honesty posture across five signals" with the five-claim-level table from CONSTRUCT_VALIDITY_AUDIT_v1.md (v1.2 update: fifth level `llm_classifier_output` added 2026-04-28). Shows the framework spine. Drafted 2026-04-27 in `METHODOLOGY_PAPER_v2_FIGURES_v1.md`; the v1.1 footer that carried the L5 framework gap as a load-bearing caveat is superseded by v1.2's resolution narrative (the gap is closed by the addition of the fifth level, not by retrofitting an existing one).

**F2. Coverage candidate-miss per-dimension.** Unchanged from v1.

**F3. Epistemic candidate-attribution scatter.** Unchanged from v1.

**F4. FVS co-activation matrix.** Unchanged from v1.

**F5. Voice-confidence histogram with claim_level overlay.** v1's distribution of margin_to_threshold values, plus a claim_level annotation showing how voice classification (classifier_output) relates to its downstream composed_pattern usage.

**F6. Per-level cascade trace.** Replaces v1's before/after posture example. Shows the instruction_without_troubleshooting case across all four claim levels: detector layer (FVS-007 fires correctly); classifier layer (genre misclassified as recommendation HIGH); composed_pattern layer (recommendation-without-falsification fires for the wrong reason); agent layer (would inherit the misreading if asked to interpret without claim_level visibility). The figure makes the L5 framework's value concrete. Drafted 2026-04-27 in `METHODOLOGY_PAPER_v2_FIGURES_v1.md` with pre/post-tightening 4-column table sourced from the fixture audit's post-tightening section (Moves A+B closed via classifier-layer regex tightening, demonstrating the per-level discipline scoping fixes to the right layer).

**F7. Construct-validity audit five-question matrix.** A 13-row by 5-column matrix from CONSTRUCT_VALIDITY_AUDIT_v1.md v1.1 (constructs by validity / honesty / calibration / failure modes / reproducibility). Shows which constructs have full coverage and which have known gaps. Drafted 2026-04-27 in `METHODOLOGY_PAPER_v2_FIGURES_v1.md`; 6 of 65 cells carry ⚠ marks (4 open with named resolution paths, 2 mixed ✓+⚠), 59 cells fully ✓ or (✓). Construct #13 row added per audit v1.1 (was 12-by-5 in audit v1.0).

**F8. Adversarial fixture per-level diagnosis schema.** A diagram showing the structure of an adversarial fixture (document.md + expected.json + audit.md) and how the audit walks the four claim levels. Anchors §6c. Drafted 2026-04-27 in `METHODOLOGY_PAPER_v2_FIGURES_v1.md`; includes the 3-rule discipline (compose ONCE; per-level reading; tightening moves shipped separately) + the fixture-suite state table (paper-submission-readiness MET at 5 fixtures + 1 dual-purpose; paper-revision-readiness 7/10 closed as of 2026-04-27).

Source data: F1, F7 from CONSTRUCT_VALIDITY_AUDIT_v1.md; F6, F8 from `data/adversarial_fixtures/`; others unchanged from v1.

---

## 4. Venue options (unchanged from v1)

arXiv preprint (cs.CL or cs.HC); CHI; CSCW; JASIST; ACL/EMNLP; ICLR Socially Responsible ML workshop. Recommendation unchanged: arXiv preprint first; CSCW or JASIST for peer-reviewed validation; CHI only if Track B runs pre-submission.

v2 note: the L5 framework's general-applicability framing may extend the venue list to ICSE (software engineering, methodology contribution) or FAccT (responsible-ML conference), if the paper emphasizes the framework's adoption potential beyond Frame Check. Curator-gated.

---

## 5. Authorship shape (unchanged from v1)

Solo-curator vs co-authored with reviewers; collaborating-agent attribution. Curator decision required.

v2 note: the post-v1 infrastructure (L5 framework, adversarial fixtures, construct-validity audit) was composed in collaboration with the AI agent. If agent-attribution is co-authorship, the contribution boundary is per-section (which agent contributed which sections) and curator-decided.

---

## 6. Dependencies and sequence (v2 updates)

- **arXiv preprint**: no dependencies beyond curator commit; v2 outline ready.
- **CSCW/JASIST/CHI**: require Track B results for the strongest claim. Paper can draft before Track B but submission should wait.
- **Figures F1-F4**: drafted from existing scripts (unchanged from v1).
- **Figures F5-F8**: F5 requires rerunning measurement with claim_level overlay; F6 requires fixture-trace diagram (substrate output already has the per-level data); F7 from CONSTRUCT_VALIDITY_AUDIT_v1.md (table extraction); F8 conceptual diagram.
- **Related-work section**: 2-4 hours of literature collection (unchanged from v1) plus 2-3 hours for measurement-validity anchors (Cronbach and Meehl, Adcock and Collier).

---

## 7. Honest limits of this outline (v2)

v1 limits preserved. v2 additions:

- **L5 framework as paper centerpiece is curator-gated**: the framework is shipped infrastructure but its framing-as-contribution is editorial. Curator decides whether L5 leads, whether it complements construct-honesty, or whether the paper retains v1's 5-signal frame.
- **Fixture suite Track C threshold** *(updated 2026-04-27)*: paper-submission-readiness target is 5 fixtures with structural coverage of all 4 claim levels (MET as of 2026-04-27 per `data/adversarial_fixtures/README.md` strategic gap-closure plan). Paper-revision-readiness target is 10 fixtures with explicit residual-case coverage. Below 5: Track C is "infrastructure exists, instances pending"; at 5: Track C is "real, structurally-grounded, sample-small-but-defensible"; at 10: Track C is "substantive empirical claim defensible against hostile reviewer". Curator decides drafting timing relative to the 10-fixture target.
- **Construct-validity audit v1.2 (2026-04-28) supersedes v1.1**. v1.0 covered 12 substrate constructs at 4 claim levels; v1.1 added construct #13 (V4.2 LLM-judge FVS detection) and surfaced an L5 framework gap; v1.2 resolves the gap by adopting Proposal A (fifth claim level `llm_classifier_output`). The version-tracking discipline is operationally proven (v1.0 -> v1.1 -> v1.2 over a single week, each version pinning its construct count and claim-level table). The paper snapshots v1.2 with the surfacing-and-resolution arc as part of the §4 narrative; the discipline is "frame the surfacing AND the resolution as load-bearing evidence the framework is honest about its own limits AND can extend without collapsing per-level clarity."
- **Agent-rendering quality is NOT validated**: the substrate emits with claim_level discipline; how agents render that output (sovereignty prompts → user-facing response) is the AGENT's responsibility per the absence-is-not-prescription discipline. The paper should NOT claim agent-rendering quality without a separate evaluation methodology (involves measuring agent behavior on canonical substrate outputs across model versions; pre-registered or fixed-seed). This is a different research project from substrate methodology and is curator-gated for post-publication study. Naming this gap honestly in §7 prevents an external reviewer asking "how do you know agents render this responsibly?" from receiving a hand-wave answer.

---

## 8. What this outline unlocks (v2)

- **Curator venue decision**: the option space is unchanged; v2's L5 framing may extend the venue list (ICSE, FAccT). Curator picks.
- **Figure drafting**: F1, F6, F7, F8 are new in v2; F1 and F7 are immediately draftable from CONSTRUCT_VALIDITY_AUDIT_v1.md.
- **Related-work expansion**: literature anchors named here can be expanded; v2 adds 2-3 hours for measurement-validity anchors.
- **Full draft readiness**: when curator approves outline + venue + L5-framing decision, the eight-section drafting becomes a scoped 15-25 hour work block (estimate unchanged from v1).

---

## 9. Cross-references (v2 additions in **bold**)

- `METHODOLOGY.md`: long-form methodology reference; the paper compresses this to §3-§5.
- **`CONSTRUCT_VALIDITY_AUDIT_v1.md`**: §4 spine in v2; per-construct measurement-gap mapping with five-evaluator-question structure.
- **`data/adversarial_fixtures/sales_pitch_as_analysis/audit.md`**: §6c first-fixture worked example.
- **`data/adversarial_fixtures/instruction_without_troubleshooting/audit.md`**: §6c second-fixture worked example; also §1 motivation and §4.3 composed_pattern worked example.
- `VISITOR_AUDIT.md §7 Fix A`: posture-shift grounding §1 and §4.4.
- `CANDIDATE_MISS_REPORT.md`: empirical spine for §4.4 under-detection numbers.
- `fvs_eval/CORRESPONDENCE_STUDY_v1.md`: AI-coder correspondence rates qualifying §4.4.
- `fvs_eval/CONSTRUCT_EMPIRICS_REPORT.md`: five-signal construct empirics; auto-generated from corpus.
- `fvs_eval/CONSTRUCT_HONESTY_AUDIT_v1.md`: voice-residual audit; predecessor to CONSTRUCT_VALIDITY_AUDIT_v1.
- `fvs_eval/THRESHOLD_SENSITIVITY_v1.md`: voice-borderline and temporal-balanced threshold sensitivity.
- `FVS_COACTIVATION_REPORT.md`: empirical spine for §3.
- `MCP_CONTRACT_V2_PROPOSAL.md`: contract design (§5).
- `fvs_eval/reader_aid_study/DESIGN_v1.1.md`: Track B pre-registration (§6b).
- `fvs_eval/validation_study/REPORT_V3_TRACK_A.md`: Track A results (§6a).
- `DETECTION_RULE_AUDIT_v1.md`: library detection-state audit (§3).
- `ADJACENCY_RECONCILIATION_v1.md`: reconciliation proposal (§3).
- `OSF_SUBMISSION.md`: pre-registration submission content.
- **`mcp_server.py` `_CLAIM_LEVEL_TREATMENTS`**: the canonical claim-level treatment dict cited in every MCP payload; §4.1 reference.

---

*v2. 2026-04-27. Outline by collaborating agent. Curator review required before drafting begins. On approval + venue pick + L5-framing decision: full draft estimated 15-25 hours. v2 preserves the evidence discipline at outline level: every change from v1 is named explicitly, honest-limits sections track the new infrastructure's limits, curator gates are surfaced rather than bypassed.*
