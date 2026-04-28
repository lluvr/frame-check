# Frame Library Index

Canonical reference for the FrameCheck Frame Vocabulary System (FVS). This index is the source of truth for which frames exist, their stability status, and how to cite them.

**Library version:** 0.1.0 (see `VERSION`)
**Status:** Pre-stable. No frame has been promoted to `canon` yet (see Promotion Criteria below).

## Two tracked states

The library tracks **two orthogonal states per entry**:

1. **Canon trajectory** (this INDEX): `canon` / `draft` / `aspirational` / `retired`. Governs promotion to citable-in-published-work status.
2. **v1 publication state** (managed in `build_corpus_site.py:_WITHDRAWN`): `published` / `withdrawn`. Governs what renders as an active entry in the rendered library pages. Withdrawn entries retain their URL and ID (with withdrawal banner + `noindex`) so external references do not break.

Currently all 20 entries are `draft` on the canon trajectory. Four are `withdrawn` from v1 publication (FVS-003, 004, 018, 019) with rationales documented in `_WITHDRAWN`. Withdrawal is a v1-scoping decision; it does not foreclose future canon promotion if the rationale is revisited.

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

1. **Coverage complete.** Markdown entry has all standard sections (Identification, what-it-makes-visible/invisible, examples, generation affordances, worked example, branch applicability, vocabulary connections, honest limits). For text-side frames, a detection rule exists in `frame_library.py:suggest_frames` and has at least one test.
2. **External review.** At least two reviewers outside the curator have signed off. Review must surface failure modes, not just agreement. Reviewer names and dates recorded in the entry.
3. **Worked example validated.** At least one worked example has been independently confirmed to exhibit the frame (not just plausibly described).
4. **Adjacent frames mutual.** Relationships to other FVS entries stated and reciprocal (if FVS-001 lists FVS-002 as adjacent, FVS-002 lists FVS-001 back).
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
Lucic, L. (2026). FVS-008 Growth Frame, v1. FrameCheck Frame Library 0.1.0.
(production paused)
```

Cite the library as a whole as:

```
Lucic, L. (2026). FrameCheck Frame Library, v0.1.0.
(production paused)
```

Citation form will stabilize when the first `canon` frame is promoted.

## Open questions for resolution

These block this index from becoming operational. Each needs a decision:

1. **Class assignments.** Are the text-side / meta-side splits above correct? FVS-019 (Narrative Coherence) is borderline (coherence is partly a reader perception, partly a text property). FVS-006 (Identity Framing Asymmetry) might be partly text-detectable (asymmetric language about model identities). A curator pass over all 20 is the simplest fix.
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
