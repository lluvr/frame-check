# Contributing to Frame Check

Frame Check is a personal project by Lovro Lucic. The repository is private
and not currently taking outside contributions. This document records how
the codebase is laid out, how its parts are extended, and the conventions
and tests that keep it consistent, for anyone (including future me) working
in it.

For who decides what and where decisions are recorded, see `GOVERNANCE.md`
and `data/frame_library/INDEX.md`.

---

## Repository layout

```
frame-check/
├── data/frame_library/          # 20-entry FVS markdown catalog + INDEX + VERSION
├── data/worked_examples/        # Published worked examples (multi-LLM comparisons)
├── data/transmissions/          # Frame Check transmissions (research pieces)
├── calibration/                 # Calibration corpus + results
├── validation/                  # Decision-readiness validation runs
├── framecheck_mcp/              # Wheel-bundle data carrier (data populated at build time)
├── scripts/                     # Build + release infrastructure
├── *.py                         # MCP server + framing detectors (flat-modules wheel layout)
├── tests/test_*.py              # Tests
└── mcp_server.py                # MCP protocol server entry point
```

The flat-modules layout at root is the wheel-bundle convention named in
`pyproject.toml [tool.setuptools] py-modules`: each *.py at root ships
as a top-level import on the installed wheel. The `framecheck_mcp/`
package exists as the data-carrier subdirectory (wheel installs the
data files under `framecheck_mcp/data/...` so MCP server code resolves
them via `_DATA_ROOT` lookup). The 1.0.0 release will migrate to a
src-layout package per `framecheck_mcp/__init__.py` docstring;
0.8.x preserves the flat layout for stability.

---

## Before you start

1. **Read `data/frame_library/INDEX.md`.** It is the source of truth
   for which frames exist, their stability status, and the promotion
   criteria. All other surfaces derive from it.
2. **Read `GOVERNANCE.md`.** It states who decides what and where
   decisions are recorded (single author; private project).
3. **Run the full test suite before opening a PR:**
   ```bash
   python3 -m pytest -q --ignore=test_source_latency.py --ignore=test_phase1_load.py
   ```
   The suite must stay green.

---

## Contribution types

### Proposing a new FVS library entry

1. Reserve the next free `FVS-XXX` ID in `data/frame_library/INDEX.md`
   with status `aspirational` and a one-line description. This stakes
   the ID so two contributors do not draft the same frame concurrently.
2. Create `data/frame_library/FVS-XXX_<snake_name>.md`. Use an existing
   entry (e.g. `FVS-008_growth_frame.md`) as the template. All sections
   are required:
   - `# Frame Name`
   - **FVS entry / Version / Curator / Curated / Source / Status**
     metadata
   - `## Identification`
   - What this frame makes visible / invisible
   - Positive / negative examples
   - Adjacent frames (new contributions must be reciprocal: if you
     list FVS-008 as adjacent, FVS-008's entry must also list yours.
     If the frame you are adjacent-to has a non-reciprocal edge to a
     third frame, flag that as a separate item in the PR rather than
     propagating it.)
   - When appropriate / when misleading
   - Honest limits (required: name what the frame does not cover)
   - `## Generation affordances` with rewrite + counter prompts and
     salient questions
   - `## Worked example`
3. Run `python3 run_tests.py` to verify all canonical-runner suites
   pass, including the discipline-boundary tests in
   `test_v4_2_discipline_boundary.py`. The new entry is auto-discovered
   by these tests and must comply.
4. What a sound entry needs: reciprocity, an honest-limits section, a
   worked example that actually exhibits the claimed frame, and the
   post-stress-test paragraphs in the Cross-family reliability section.

### Contributing a detection rule

A text-side FVS entry with `detection: gap` in INDEX.md is a wiring
target. To add a rule:

1. Verify the signal exists in `framing.py` (`detect_coverage`,
   `detect_voice`, `temporal_orientation`, `detect_epistemic_basis`).
   If the signal does not yet exist, that is a separate PR against
   `framing.py` with its own tests.
2. Add the rule in `frame_library.py::suggest_frames`. Follow the
   existing pattern: conditional on signal strength, then `_add(...)`
   with `fvs_id`, display name, signal description, teaching question.
3. Add the one-paragraph definition to `_DEFINITIONS` at the top of
   the file.
4. Add tests in `test_frame_library.py`. Minimum:
   - **Positive:** the rule fires under the intended condition
   - **Negative:** the rule does not fire when the signal is absent
     or below threshold
   - **Voice gate (if applicable):** the rule's voice restrictions work
5. Update `INDEX.md`: change `detection` from `gap` to `yes`. Update
   the curated date.

### Contributing calibration data

Reliability tiers come from `calibration/run_calibration.py` applied
to the claim corpus. To contribute:

1. **New claims** go into `calibration/source_network_corpus.yaml`
   with `as_of_date` populated so stale-claim detection works. The
   file is YAML grouped by provider; each claim carries a stable
   `id` (`provider-NNN`), a `primary_source_url` for independent
   verification, and an `expected_verdict` the harness grades
   against. The full per-field schema (id, claim, primary_source,
   primary_source_url, as_of_date, primary_verifier, category,
   expected_verdict, rationale) is documented in
   `calibration/README.md` "How to extend."
2. **Re-running the harness** produces a new dated directory under
   `calibration/results/`. Runs are **immutable once published**:
   rerunning creates a new dated directory, never overwrites.
3. If a canonical tier changes (e.g., FRED `weak` → `moderate`), note
   it in the run's `REPORT.md` and bump the library VERSION patch
   number to flag the update.

### Contributing a worked example

Worked examples demonstrate Frame Check's analysis applied to a
specific, citable public document. They live in
`data/worked_examples/` (markdown source) and render at
`corpus_site/worked-examples/` (static HTML). To contribute:

1. Pick a public document where the structural analysis produces a
   non-obvious observation (frame shift, under-detected dimension,
   voice-borderline call, etc.). Worked examples should teach, not
   simply demonstrate.
2. Run Frame Check on the document. Capture the portrait, coverage,
   voice, temporal, and any FVS matches.
3. Create `data/worked_examples/<slug>.md`. Follow an existing entry
   (e.g., `fomc-statement-march-2026.md`) for structure. Cite the
   source document with URL and date of retrieval.
4. Name the frame lens. Worked examples are not "here is what the
   tool said"; they are "here is what this document makes visible
   once the tool is applied and here is what the reader should do
   with that." Honest limits section is required (what the tool
   missed, what a careful reader could add).
5. A sound worked example actually teaches (it does not just
   demonstrate) and its citations resolve.

### Contributing documentation

Documentation PRs (README, governance, privacy, corpus site prose)
follow the same mechanical process as code PRs with one addition:
if the document carries an honest-limits section, updates must
update the limits too. A limits section that does not reflect the
current document is worse than no limits section because it signals
false assurance.

### Contributing to the MCP server

The MCP server (`mcp_server.py`) is the distribution surface for
external agents. New tools must:

1. Preserve the three-section epistemic payload: **analysis +
   agent_guidance + provenance**. No tool may return measurements
   without guidance on how to cite them.
2. Be deterministic (no LLM in the tool path). If a tool requires an
   LLM, it does not belong in the MCP server as it is today.
3. Be covered in `test_mcp_server.py` across all three layers
   (payload builder, dispatch, subprocess roundtrip).
4. Be documented in `MCP_SERVER.md`.

---

## Test requirements

Every PR must:

- Leave the full test suite green (see command above).
- Add positive and negative tests for any new detection or measurement.
- Not regress any existing boundary test in `test_documented_boundaries.py`.
  Those pin known detection boundaries; updating them requires a
  corresponding detection change, not just a test tweak.
- Not degrade the calibration F1 for any provider in the most recent
  run (see `calibration/results/<latest>/REPORT.md`).

---

## Style conventions

- Python: existing style wins. No external linter is enforced; follow
  surrounding code.
- No AI-attribution commit tags (no `Generated with Claude`, no
  `Co-Authored-By: Claude`). Lovro Lucic is the named author.
- No em-dashes or smart quotes in any committed file (code, markdown,
  HTML). Grep with `grep -n '—\|“\|”\|‘\|’\|…'` before committing.
- Markdown entries use plain ASCII. HTML entity escapes in templates
  are fine.

---

## How changes land

This is a single-author private project; there is no external pull-request
or RFC process. Commits carry a `Signed-off-by:` trailer (`git commit -s`,
Developer Certificate of Origin v1.1) and no AI-attribution.

Two conventions worth keeping if the project is ever public again: do not
change the meaning of an existing FVS ID (create a new ID instead), and do
not introduce a hosted MCP server or any surface that sends document text to
a third-party LLM by default.

## Contact

Author: Lovro Lucic. See `CITATION.cff` for contact.

Licensed: code Apache-2.0, corpus CC-BY-4.0.
