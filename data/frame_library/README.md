# Frame Library (living working library)

This directory is the **living working library**: the FVS entries reviewers
read, that `build_corpus_site.py` renders to corpus pages, and where
ongoing editorial work accumulates between ratification events.

This is NOT what the V4.2 engine reads. The engine reads the frozen
snapshot at `../frame_library_v4/` (Identification sections only).

## What lives where

| Artifact | Path | Role |
|---|---|---|
| Living library (this directory) | `data/frame_library/` | Reviewer-facing prose. Edits accumulate continuously. Renders to corpus pages. |
| Frozen snapshot | `data/frame_library_v4/` | Ratified library_v4 snapshot. Engine reads `## Identification` sections from here. Never edited post-ratification (see snapshot's POST_RATIFICATION_DIVERGENCE.md). |
| Per-entry status | [INDEX.md](https://github.com/Clarethium/frame-check/blob/master/data/frame_library/INDEX.md) (this directory) | Canonical status, citation rules, detection class for each FVS-XXX. |
| Engine reliability values | fvs_eval/v4/library_v4_reliability.json | Per-frame `library_consensus_ac1` that the engine emits in V4.2 results. |
| Library version | `VERSION` (this directory) | SemVer of the living library. Bumped at ratification time. |
| Canon-promotion dossiers | `promotions/FVS-XXX_v1.md` | Reviewer-engagement packages for canon-candidate frames. |

## Discipline (METHODOLOGY section 2.4.4)

The V4.2 engine has two LLM-facing read paths into a library entry:

1. **Labeling judge** (`fvs_eval/v4/v4_2_engine.py::_extract_identification`)
   reads ONLY the `## Identification` section. Cross-family AC1 reliability
   is a property of this content. Identification edits require section
   2.4.3 ablation before merge.

2. **Reframe** (`reframe.py::load_affordances`) reads the
   `## Generation affordances` section and feeds the
   `**Counter-document prompt:**` into a Grok call to produce the
   reframed document. Generation-affordances edits require a reframe-
   behavior smoke test.

All other sections (`## Cross-family reliability`, `## Adjacent frames`,
`## Honest limits`, `## Worked examples`, `## Decision-readiness implication`)
are reviewer-facing only and do not require LLM-behavior checks.

## Engine-canonical numbers per frame

Each entry's `## Cross-family reliability` section carries a top-of-block
ratification framing line that names library_v4 = library_v3 byte-equivalent
on Identifications. The engine-canonical reliability number for each frame
is in fvs_eval/v4/library_v4_reliability.json (`frames[FVS-XXX].ac1_avg`)
and matches what V4.2 emits as `library_consensus_ac1` in its results.

The `## Cross-family reliability` block in each entry presents engine-
canonical (library_v3 = library_v4) numbers as primary, with library_current
(working-library state immediately prior to library_v4 ratification) and
library_v2 (earlier variant) as historical comparisons.

## Drift-prevention tests

Two structural tests in test_v4_2_discipline_boundary.py enforce
the discipline:

- `test_v4_2_labeling_prompt_only_uses_identification_sections`: catches
  any future engine refactor that silently feeds non-Identification content
  to the labeling judge.
- `test_every_entry_has_post_ratification_framing_line`: catches any edit
  that removes the post-2026-04-24-stress-test ratification framing from
  an entry's Cross-family block.
- `test_generation_affordances_byte_equivalent_v3_to_v4`: catches drift on
  the section that the reframe LLM call reads.

These tests are part of the canonical runner (`python3 run_tests.py`).

## How to add or revise an entry

1. Edit the entry markdown in this directory.
2. If the edit touches `## Identification`, run a section 2.4.3 ablation
   before merging. Reference harnesses from the library_v4 ratification:
   fvs_eval/v4_2/measure_ablation.py (general per-frame ablation
   loop) and fvs_eval/v4_2/measure_ablation_cur_v4_cand.py
   (mixed-genre n=15 measurement against a candidate library directory).
   Worked example of a passing ablation: the FVS-007 result at
   fvs_eval/v4_2/FVS_007_ABLATION_RESULTS_v1.md. Worked example
   of a section 2.4.3-blocked revision and how it was resolved by
   composition: the library_v3 → library_v4 ratification at
   fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md.
3. If the edit touches `## Generation affordances`, run a reframe-behavior
   smoke test before merging via [scripts/reframe_smoke_test.py](https://github.com/Clarethium/frame-check/blob/master/scripts/reframe_smoke_test.py)
   (single-frame manual recipe currently runnable; see file-top docstring
   for what "passing" means and for the full-sweep TODO).
4. If the edit touches any other section, no LLM-behavior check is required.
5. Run `python3 ../../run_tests.py` to confirm the discipline-boundary
   tests in test_v4_2_discipline_boundary.py still pass; in
   particular the engine-emit disclosure test catches drift between this
   directory's entries and the engine's reliability artifact.
6. If the edit changes which library variant is engine-canonical,
   coordinate the change with a new ratification (METHODOLOGY section
   2.4.3 + 2.4.4) and bump VERSION in lockstep with the snapshot at
   `../frame_library_v4/VERSION` (or whatever the next snapshot
   directory is).

## How to ratify a new library version

See METHODOLOGY section 2.4.3 (revision discipline) and section 2.4.4
(engine pinning + Generation-affordances corollary) for full procedure.
The 2026-04-24 library_v3 → library_v4 ratification at
fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md serves as the
reference worked example, including the post-ratification stress-test
pass documented in section 8b.
