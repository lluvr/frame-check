# Frame Library Index

Canonical reference for the FrameCheck Frame Vocabulary System (FVS). This index is the source of truth for which frames exist, their stability status, and how to cite them.

**Library version:** 0.2.0 (see `VERSION`)
**Status:** Pre-stable. No frame has been promoted to `canon` yet (see Promotion Criteria below).

## Two tracked states

The library tracks **two orthogonal states per entry**:

1. **Canon trajectory** (this INDEX): `canon` / `draft` / `aspirational` / `retired`. Governs promotion to citable-in-published-work status.
2. **v1 publication state** (managed in `build_corpus_site.py:_WITHDRAWN`): `published` / `withdrawn`. Governs what renders as an active entry in the rendered library pages. Withdrawn entries retain their URL and ID (with withdrawal banner + `noindex`) so external references do not break.

Currently all 20 entries are `draft` on the canon trajectory. Four are `withdrawn` from v1 publication (FVS-003, 004, 018, 019) with rationales documented in `_WITHDRAWN`. Withdrawal is a v1-scoping decision; it does not foreclose future canon promotion if the rationale is revisited.

## Parallel directory: v2 §11 grounded-authorship retrofit

A v2 §11 grounded-authorship retrofit shipped 2026-04-25 in a parallel directory at `../frame_library_v3/`. That directory carries the FVS entries (FVS-001 through FVS-019; FVS-020 retained at v1 form) with v2 §11 grounded-authorship sections appended (eight fields per entry: authorship dated, context of testing, failure record, success record, lived-experience anchor, applicability metadata, empirical track record, plus internal-operational friction-cost estimate). Lived-experience anchors are uniformly held "Open" with entry-specific criteria pending curator authorship per [ANCHOR_AUTHORSHIP_METHODOLOGY_v1.md](https://github.com/lluvr/frame-check-mcp/blob/master/ANCHOR_AUTHORSHIP_METHODOLOGY_v1.md).

The two directories serve different layers of catalog discipline:

| Directory | Role |
|---|---|
| `data/frame_library/` (this directory) | Canon-promotion track. Detailed measurement evidence (cross-family reliability, generation comparison, target-scope construct validity). Source for the `build_corpus_site.py` rendered library pages. The directory the canon-promotion review process operates on per the criteria below. |
| `data/frame_library_v3/` | v2 architectural surface. v2 §11 grounded-authorship sections appended to entries; structural-grade across all 19 active entries; full-grade requires authored anchors. Cross-curator practitioners apply the anchor methodology against these entries. |

Citation discipline: cite the canon-promotion entry from `data/frame_library/`; cite the v2 §11 retrofit from `data/frame_library_v3/`. The two are not competing; they sit at different layers of the same catalog. See [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) §16 for the v2 spec implementation status.

### Library version landscape (for reading cross-family reliability tables)

Entry-level "Cross-family reliability" sections cite multiple library version states. Glossary:

| Name | Path | Role |
|---|---|---|
| `library_current` | `data/frame_library/` (this directory) | Working library; reviewer-facing source. Renders to `corpus_site/library/`. |
| `library_v2` | `data/frame_library_v2/` | Archived earlier baseline; cited for historical reliability comparison. |
| `library_v3` | `data/frame_library_v3/` | Step-4 detection-testing variant (commit `9abeb3d`, 2026-04-18) plus v2 §11 grounded-authorship retrofit (2026-04-25). Engine-canonical Identifications under library_v4 by byte-equivalence. |
| `library_v4` | `data/frame_library_v4/` | Frozen ratified snapshot (2026-04-24 per fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md). Engine reads `## Identification` sections from here. Composed as library_v3 Identifications + library_current non-Identifications. POST_RATIFICATION_DIVERGENCE.md explains where the snapshot's reviewer-facing prose lags. |

When an entry reports `MG_v3 0.86` and `MG_cur 0.85`, that means: mixed-genre cross-family AC1 measured against library_v3 entries was 0.86; against library_current entries was 0.85. Engine-canonical numbers are library_v3 (= library_v4 by byte-equivalence on Identifications); library_current numbers are pre-ratification working-library state preserved for transparency.

**2026-04-27 Identification drift note.** Adjacency reconciliation work 2026-04-26 to 2026-04-27 (per ADJACENCY_RECONCILIATION_v1.md Groups A/B/C closure) modified `## Identification` content in the living library by extending Adjacent frames lines with Group A reciprocate, Group B directionalize, Group C reciprocate, and active-to-withdrawn disclosure parentheticals. The frozen `data/frame_library_v4/` snapshot was not modified; the V4.2 engine continues to read v4 snapshot Identifications without change. Living library Identifications and v4 snapshot Identifications now differ. Future re-ratification (creating a v5 snapshot) will require section 2.4.3 ablation testing to characterize the drift before promoting the living-library Identifications to engine-canonical. Cross-family reliability numbers cited in entries (library_v3 = library_v4 by Identification byte-equivalence) remain accurate for the engine's current Identification reads; they do not reflect the living library's post-drift state.

## Purpose

The Frame Library names recurring framing failures so they can be discussed, detected, and avoided. Each FVS entry is an attempt to name something that already exists in AI output but has no shared vocabulary. The library is the canonical artifact; this index is the map.

## Status taxonomy

Each frame carries one of four statuses:

| Status | Meaning | Stability guarantee |
|--------|---------|---------------------|
| `canon` | Promoted via review process. Citable in published work. | ID, name, and core identification stable indefinitely. Refinements ship as new versions. |
| `draft` | Single-curator entry, internal use, "reviewers wanted". | ID stable. Name and identification may change. |
| `aspirational` | Frame is named in the index but no entry exists yet. | Reserved ID only. Nothing else stable. |
| `retired` | Was canon, then withdrawn. Marker preserved for citation continuity. | ID never reused. Documentation remains for historical reference. |

## Coverage class

Frames divide into two classes based on whether automated detection from text is possible:

| Class | Meaning | Detection expectation |
|-------|---------|----------------------|
| `text-side` | Frame manifests as patterns in document text. | Should have detection rule in `frame_library.py`. |
| `meta-side` | Frame describes reader/system/causal mechanism, not text properties. | Documentation only; detection not applicable. |

This distinction matters: a `meta-side` frame without detection is complete; a `text-side` frame without detection is incomplete.

## Detection state taxonomy

The Detection column records the state of the frame's detection
rule (not the frame concept). Values:

| Detection | Meaning |
|-----------|---------|
| `yes` | Detection rule exists and fires on the frame's patterns. |
| `gap` | Text-side frame; detection rule planned but not yet implemented. |
| `retired` | Text-side frame; detection rule existed but has been retired after validation evidence showed it failed its design intent. The frame concept stands; the rule does not. Pending redesign or replacement. |
| `n/a` | Meta-side frame; detection not applicable by class. |

A rule is moved to `retired` when it fires on cases it should not flag and misses cases it should, such that its output is not a credible signal for the frame it names. Retirement is a rule-state change, not a concept change; the frame's library entry remains in place and a future detection redesign can restore the rule to `yes`.

## The Frames

**Format note:** the six-column order below (`ID | Name | Class | Detection | Status | Curated`) is parsed by `frame_library_index.py` for citation blocks and MCP responses. Column reorder, column addition, or `Status` field value changes require coordinated updates to `frame_library_index.py`, `test_frame_library_index.py`, and downstream consumers (`build_corpus_site.py`, `mcp_server.py`). See [CONTRIBUTING.md](https://github.com/lluvr/frame-check-mcp/blob/master/CONTRIBUTING.md) for the contribution workflow; DR-1 in SESSION_STATE.md §3 names this as a tracked drift risk.

| ID | Name | Class | Detection | Status | Curated |
|----|------|-------|-----------|--------|---------|
| FVS-001 | Frame Amplification | text-side | retired | draft | 2026-04-18 |
| FVS-002 | Fluency-Quality Illusion | text-side | yes | draft | 2026-04-12 |
| FVS-003 | Prompt Attribution Error | meta-side | n/a | draft | 2026-04-12 |
| FVS-004 | Default Geometry | meta-side | n/a | draft | 2026-04-12 |
| FVS-005 | System Attribution Error | meta-side | n/a | draft | 2026-04-12 |
| FVS-006 | Identity Framing Asymmetry | meta-side | n/a | draft | 2026-04-12 |
| FVS-007 | Failure Framing | text-side | yes | draft | 2026-04-12 |
| FVS-008 | Growth Frame | text-side | retired | draft | 2026-04-18 |
| FVS-009 | Risk Frame | text-side | yes | draft | 2026-04-12 |
| FVS-010 | Completeness Illusion | text-side | yes | draft | 2026-04-12 |
| FVS-011 | Stakeholder Frame | text-side | yes | draft | 2026-04-17 |
| FVS-012 | Uncertainty Frame | text-side | yes | draft | 2026-04-17 |
| FVS-013 | Oracle Frame | meta-side | n/a | draft | 2026-04-13 |
| FVS-014 | Temporal Anchoring | text-side | yes | draft | 2026-04-13 |
| FVS-015 | Efficiency Frame | text-side | retired | draft | 2026-04-18 |
| FVS-016 | Authority by Citation | text-side | yes | draft | 2026-04-13 |
| FVS-017 | False Balance | meta-side | n/a | draft | 2026-04-18 |
| FVS-018 | Scope Narrowing | meta-side | n/a | draft | 2026-04-18 |
| FVS-019 | Narrative Coherence | meta-side | n/a | draft | 2026-04-18 |
| FVS-020 | The Invisible Frame | meta-side | n/a | draft | 2026-04-13 |

### v1 publication state

Four entries are held back from v1 publication. Their library pages render with withdrawal banners and `noindex`; IDs are preserved so external references resolve.

| ID | Disposition | Replaced by | Reason (summary) |
|----|-------------|-------------|------------------|
| FVS-003 | superseded | FVS-005 | Redundant with FVS-005 (same four-layer attribution mechanism, broader scope) |
| FVS-004 | unsupported | n/a | Bilateral-reinforcement mechanism not grounded in cited experimental evidence |
| FVS-018 | absorbed | FVS-001 | Narrowing is a specific case of frame amplification; covered by FVS-001 with stronger examples |
| FVS-019 | absorbed | FVS-002 | Narrative coherence is one form of fluency-quality illusion; covered by FVS-002 |

Full rationales in `build_corpus_site.py._WITHDRAWN`. Withdrawal decisions are revisitable if evidence changes; the ID preservation makes that safe.

**Coverage summary:**
- 20 entries total. Canon trajectory: all 20 `draft`. v1 publication: 16 published, 4 withdrawn.
- 11 text-side / 9 meta-side (class assignments curator-reviewed
  2026-04-18; see note below).
- Detection column by state: 8 text-side `yes` (FVS-002, 007,
  009, 010, 011, 012, 014, 016), 3 text-side `retired`
  (FVS-001, 008, 015), 9 meta-side `n/a`. Zero outstanding
  `gap` entries.
- The three `retired` rules were retired 2026-04-18 after the
  external validation study (fvs_eval/validation_study) found
  their v1 implementations failed their design intent (false-
  positive rates high, zero true positives on the detectable
  cases across the 12-document corpus). The frame concepts
  remain text-side and the library entries remain in place; the
  detection rules are pending redesign. See
  [METHODOLOGY.md §2.4.1](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) for the full v1-to-v2 measurement
  comparison and the audit that led to the retirements.

**Class-assignment curator pass (2026-04-18).** FVS-017, FVS-018,
and FVS-019 were reclassified from `text-side` to `meta-side`.
The distinguishing criterion: a frame is text-side only if the
frame itself (the reader-judgment or phenomenon it names) is
detectable from document text alone. Structural text signals
the frames lean on (balance patterns, coverage gaps, narrative
coherence) are detectable, but in each case the frame's core
claim requires off-text reference:
- **FVS-017 (False Balance):** balance is detectable; *false*
  balance requires the reader's knowledge of the real evidence
  distribution. Off-text.
- **FVS-018 (Scope Narrowing):** narrowing is only visible when
  the reader knows what the original scope should have been.
  Off-text relative to the document under analysis. (Withdrawn
  from v1 as absorbed by FVS-001.)
- **FVS-019 (Narrative Coherence):** coherence is a measurable
  text property; *narrative coherence as a frame that deceives*
  is the reader's judgment that fluency is being confused with
  accuracy. Off-text. (Withdrawn from v1 as absorbed by FVS-002.)

Two known schema limits surfaced by the 2026-04-18 passes
(class-review and detection-retirement):

- The binary `text-side` / `meta-side` does not distinguish
  single-document detection from multi-document (document +
  source_text) detection. FVS-018 in particular is detectable
  if the original question is supplied as source material. A
  future INDEX schema may refine this with a third category
  (`text-side-with-source` or equivalent).
- The single `Curated` date column mixes two distinct events
  (entry curation and rule-state change). For the three
  `retired` rows, Curated = 2026-04-18 marks the rule-state
  change; the entry content has not been revised since its
  original curation. A future schema may split these into
  separate fields (`Curated` and `Rule-state-changed`) for
  clarity.

Both are tracked as open questions for INDEX v2.

## Promotion criteria (PROPOSAL)

A frame moves from `draft` to `canon` when ALL of:

1. **Coverage complete.** Markdown entry has all standard sections (Identification, what-it-makes-visible/invisible, examples, generation affordances, worked example, branch applicability, vocabulary connections, honest limits). Worked example structure adapts to frame nature: text-side document-content frames typically use the standard four subsections (document excerpt, frame present, frame absent, how to read past it); meta-side reader-posture frames and counter-default-application frames may use alternate structures with explicit acknowledgment of the structure choice (see FVS-009 Risk Frame for counter-default application structure, FVS-013 Oracle Frame for reader-posture detection structure, and FVS-020 Invisible Frame for self-referential meta-meta-frame structure). For text-side frames, detection approach for the current detector generation is documented with operational reliability measurement on a target-scope corpus. Current detector at library version v0.2.0 is V4.2 LLM-judge per the project's release-arc commitments; legacy rule-based detection in `frame_library.py:suggest_frames` remains citable in historical context. A `retired` rule-state under the detection taxonomy is compatible with the criterion as long as the current-generation detection approach is characterized; canon promotion of a frame whose v1 rule is retired proceeds on V4.2 reliability evidence or on explicit vocabulary-only promotion with detection status flagged.
2. **External review.** At least two reviewers outside the curator have signed off. Review must surface failure modes, not just agreement. Reviewer names and dates recorded in the entry.
3. **Worked example validated.** At least one worked example has been independently confirmed to exhibit the frame (not just plausibly described). "Independently confirmed" means external party verification; curator self-validation and curator-approved AI-generated drafts are not sufficient. Worked examples in entries may be curator-authored from lived practice OR constructed illustrations drawing on real public material; both require the independent-confirmation step before satisfying this criterion. The construction status (lived vs constructed) is honest scope and does not by itself disqualify the example, but curator approval of an agent-drafted constructed example does not substitute for independent confirmation.
4. **Adjacent frames mutual.** Relationships to other FVS entries stated and reciprocal (if FVS-001 lists FVS-002 as adjacent, FVS-002 lists FVS-001 back). Mutual reciprocity applies among active entries.

   **Three principled-asymmetric exceptions satisfy this criterion** (each must be explicit in the entry's parenthetical, not implicit):
   - **Specific-form-of-Y asymmetry** (per ADJACENCY_RECONCILIATION_v1.md Group B directionalize style). When X is structurally a specific form of Y (e.g., risk framing as a specific form of frame amplification, growth framing as a specific form of frame amplification), the edge from X listing Y is documented one-way with explicit "the inverse is not symmetric" wording in X's parenthetical.
   - **Precondition-for-Y asymmetry**. When X is one precondition for Y to operate but Y can operate without X (e.g., identity-aligned-with-default as precondition for frame amplification), the edge from X listing Y is documented one-way with explicit precondition-asymmetry wording.
   - **Withdrawn-target documentation**. When the listed entry is withdrawn from v1 publication (per "v1 publication state" table), the active entry's parenthetical notes the withdrawal status. Withdrawn entries carry their own Adjacent frames lines as historical-conceptual record and do not require reciprocity in the active-entries criterion.
5. **Honest limits stated.** What the frame does not cover, where it misleads, what evidence is missing.

A frame moves from `canon` to `retired` when the curator plus at least one external reviewer determines the frame was wrong, has been subsumed by another frame, or has been refined to the point where the original definition is misleading.

## Versioning policy (PROPOSAL)

**Stable identifier guarantee:** FVS IDs never change meaning. Once assigned, the ID refers to the same conceptual frame indefinitely. Refinements increment version. Retirements preserve the ID. Retired IDs are never reused.

**Entry version semantics:**
- `v1` → `v2`: identification or worked examples changed materially
- Patch updates (typos, small clarifications): not versioned, recorded in a changelog at the bottom of the file
- New frame: new FVS ID

**Library version (`VERSION` file):** SemVer.
- Major bump: any `canon` frame retired or substantively changed
- Minor bump: new `canon` frame added
- Patch: documentation refinement, no canonical changes

## Citation form

Cite a specific frame entry as:

```
Lucic, L. (2026). FVS-008 Growth Frame, v1. FrameCheck Frame Library 0.2.0.
(production paused)
```

Cite the library as a whole as:

```
Lucic, L. (2026). FrameCheck Frame Library, v0.2.0.
(production paused)
```

Citation form will stabilize when the first `canon` frame is promoted.

## Open questions for resolution

These block this index from becoming operational. Each needs a decision:

1. ~~**Class assignments.**~~ **RESOLVED 2026-04-23** (IDX-1 library audit). FVS-019 reclassified to meta-side in the 2026-04-18 curator pass (absorbed by FVS-002). FVS-006 verified as meta-side: its core claim is prompt-technique efficacy (counter-default identity shifts behavior, matching-default identity does not), which requires measuring output variance across prompts and is therefore off-text. Surface mentions of identity language in documents are orthogonal to what FVS-006 actually claims. FVS-001 text-side classification is generation-dependent: at v1 signal substrate the frame is not text-decidable (hence rule retirement 2026-04-18); at V4.2 LLM-judge it is text-decidable per measured cross-family data in fvs_eval/v4_2/FVS_001_CROSS_FAMILY_v1.md. FVS-007 text-side classification rests on the document-side reading of the frame (does the document make its evaluative criteria visible?) rather than the prompt-technique reading; a scope note has been added to the entry. All 20 class assignments are now verified consistent with the class-assignment criterion named above.
2. **External reviewer count.** Two reviewers is the minimum that prevents single-curator drift. Higher (3-5) gives more confidence but slows promotion. What threshold survives "we want canon to mean something" without becoming "nothing ever promotes"?
3. **Detection gap policy.** In the v1-published set, only FVS-017 (False Balance) lacks a suggestion rule. FVS-017's own Honest Limits section acknowledges it is not fully detectable automatically ("requires knowing the actual evidence distribution for the topic"). Does the library treat FVS-017 as Class B (structural signal + reader judgment) and allow canon promotion on that basis, or hold it at `draft` until stronger detection ships?
4. **First promotion candidate.** FVS-001 has the deepest evidence (HI-061, EXP-094, worked example, detection). FVS-008 has the most worked examples. FVS-002 has the most cross-references. Picking a first promotion validates the criteria against a real case.
5. **Reviewer recruitment path.** "Reviewers wanted" is currently a status, not an action. Where do reviewers come from (academic network? open call from observatory? specific invited group)?

## Next-state targets

When this index is operational:
- All 20 frames have curator-confirmed class and explicit status
- Citation form is linked from every FVS entry header
- Promotion criteria are agreed and at least one frame has been promoted to `canon`
- VERSION file rules are enforced (e.g., a check that fails if `canon` frame changes without VERSION bump)
- `data/frame_library/` README points new readers at this INDEX as the entry point

[CONTRIBUTING.md](https://github.com/lluvr/frame-check-mcp/blob/master/CONTRIBUTING.md) already exists at the repo root with per-contribution-type instructions for new FVS entries, detection rules, calibration data, and MCP server additions.
