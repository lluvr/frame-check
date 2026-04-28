# Contributing to Frame Check

Frame Check is part of a public research program on framing and
verification. Contributions are welcome on the corpus (frame library,
methodology, calibration data), the detection engine, the MCP server,
and the documentation surface.

This document covers **how** contributions happen mechanically: file
layouts, test requirements, PR process, and what a reviewer will check.
For **who** decides and **when** a contribution becomes canon, see
`GOVERNANCE.md` and `data/frame_library/INDEX.md`.

---

## Repository layout

```
frame-check/
├── data/frame_library/          # FVS markdown entries + INDEX + VERSION
├── corpus_site/                 # Generated static site (do not edit by hand)
├── templates/ static/           # Live web surface
├── calibration/                 # Calibration corpus + results
├── *.py                         # App and measurement code
├── test_*.py                    # Tests
├── mcp_server.py                # MCP protocol server
└── build_corpus_site.py         # Corpus site builder
```

The live web surface (`app.py`, `templates/`, `static/`) is Flask +
Jinja. The corpus surface (`corpus_site/`) is a static build of the
markdown in `data/frame_library/` plus the methodology paper. Run
`python3 build_corpus_site.py` to regenerate after any library change.

---

## Before you start

1. **Read `data/frame_library/INDEX.md`.** It is the source of truth
   for which frames exist, their stability status, and the promotion
   criteria. All other surfaces derive from it.
2. **Read `STRATEGY.md` §6 Durable Decisions.** Contributions that
   require overturning a durable decision need an explicit proposal,
   not a silent PR.
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
     The existing library has 49 known non-reciprocal edges being
     reconciled per-edge in `data/frame_library/ADJACENCY_RECONCILIATION_v1.md`;
     do not treat the existing one-way edges as precedent for
     unilateral additions. If the frame you are adjacent-to has a
     non-reciprocal edge to a third frame, that is a separate
     reconciliation item and should be flagged in the PR, not
     propagated.)
   - When appropriate / when misleading
   - Honest limits (required: name what the frame does not cover)
   - `## Generation affordances` with rewrite + counter prompts and
     salient questions
   - `## Worked example`
   - `## Cross-family reliability` with the four post-stress-test
     paragraphs in this order: ratification framing line ("Engine-
     canonical reading (library_v4 ratified...)"), engine-emit
     disclosure, intra-rater stability paragraph, construct-validity
     caveat. Discipline tests in `test_v4_2_discipline_boundary.py`
     enforce all four. For a new frame whose reliability is not yet
     measured under Step 4, the engine-emit disclosure says "pending
     Step 4 measurement" verbatim (the discipline test accepts this
     as an honest acknowledgment until reliability is measured at the
     next ratification).
3. Update `INDEX.md`:
   - Promote your row from `aspirational` to `draft`
   - Set `class` (text-side / meta-side) and `detection` (yes / gap /
     n/a) correctly
4. Run `python3 build_corpus_site.py` to verify the page renders.
5. Run `python3 run_tests.py` to verify all 46+ canonical-runner
   suites pass, including the 8 discipline-boundary tests in
   `test_v4_2_discipline_boundary.py` that protect the library_v4
   ratification (engine-LLM-facing boundary, framing-line presence,
   engine-emit disclosure consistency, intra-rater disclosure
   presence, construct-validity caveat presence, VERSION sync,
   per-corpus reliability supplement reproducibility, Generation-
   affordances byte-equivalence). The new entry is auto-discovered
   by these tests and must comply.
6. If your edit changes `## Identification` for any existing entry
   (separate workflow), run a section 2.4.3 ablation per
   `METHODOLOGY.md` before merging. If your edit changes `## Generation
   affordances`, run a reframe-behavior smoke test via
   `scripts/reframe_smoke_test.py` before merging (METHODOLOGY section
   2.4.4 corollary).
7. Open a PR. Reviewers will check the reciprocity, the honest-limits
   section, whether the worked example actually exhibits the
   claimed frame, and the four post-stress-test paragraphs in the
   Cross-family reliability section.

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
5. Run `python3 build_corpus_site.py` to generate the HTML.
6. Open a PR. Reviewers check that the example actually teaches
   and that citations resolve.

### Contributing an Observatory topic

`observatory_topics.yaml` is the curated list of topics the
Observatory cycles through. Adding a topic requires that the
topic has at least two independent, Source-Network-queryable
ground-truth signals (see `STRATEGY.md §5` "Remaining 9 have low
Source Network confidence" for why the current list is bounded).
Propose topic additions via issue with `[FVS proposal]` analog:

1. Name the topic and the ground-truth signals.
2. Verify Source Network coverage on a sample claim about the
   topic in the last 30 days.
3. If coverage is thin, the topic is not yet Observatory-ready;
   leave it on the issue for future consideration rather than
   committing it to the yaml.

### Contributing documentation

Documentation PRs (README, methodology, governance, privacy,
corpus site prose) follow the same mechanical process as code
PRs with one addition: if the document carries a honest-limits
section (see `METHODOLOGY.md §6` pattern), updates must update
the limits too. A limits section that does not reflect the
current document is worse than no limits section because it
signals false assurance.

Documentation changes that affect a `STRATEGY.md §6` durable
decision require an `[RFC]` (see below). Small copy-edits, typo
fixes, and clarifications do not.

### Contributing to the MCP server

The MCP server (`mcp_server.py`) is the distribution surface for
external agents. New tools must:

1. Preserve the three-section epistemic payload: **analysis +
   agent_guidance + provenance**. No tool may return measurements
   without guidance on how to cite them.
2. Be deterministic (no LLM in the tool path). If a tool requires an
   LLM, it does not belong in the MCP server as it is today; open an
   RFC first.
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

## Developer Certificate of Origin (DCO)

Every commit to this repository must carry a `Signed-off-by:` trailer
attesting to the Developer Certificate of Origin v1.1
(https://developercertificate.org/). Frame Check uses DCO instead of
a Contributor License Agreement (CLA) so that contributing requires
no paperwork, just a per-commit certification that you have the right
to submit the work under the project's existing license (Apache-2.0
for code, CC-BY-4.0 for corpus and methodology).

**Mechanically:** every commit message ends with one line:

```
Signed-off-by: Your Real Name <your.email@example.com>
```

`git commit -s` adds the line automatically using your configured
`user.name` and `user.email`. The name must be your real name (or a
real persistent identity); pseudonyms unconnected to a verifiable
identity break the chain DCO is meant to establish.

**What you certify when you sign off** (the full DCO 1.1 text):

> Developer Certificate of Origin
> Version 1.1
>
> By making a contribution to this project, I certify that:
>
> (a) The contribution was created in whole or in part by me and I
>     have the right to submit it under the open source license
>     indicated in the file; or
>
> (b) The contribution is based upon previous work that, to the best
>     of my knowledge, is covered under an appropriate open source
>     license and I have the right under that license to submit that
>     work with modifications, whether created in whole or in part by
>     me, under the same open source license (unless I am permitted
>     to submit under a different license), as indicated in the file;
>     or
>
> (c) The contribution was provided directly to me by some other
>     person who certified (a), (b) or (c) and I have not modified
>     it.
>
> (d) I understand and agree that this project and the contribution
>     are public and that a record of the contribution (including all
>     personal information I submit with it, including my sign-off)
>     is maintained indefinitely and may be redistributed consistent
>     with this project or the open source license(s) involved.

**Enforcement:** PRs without sign-off on every commit are not merged.
There is no GitHub Action enforcing this yet (small contributor
count); a reviewer checks during PR review. If you forget, the fix
is `git commit --amend -s` for the latest commit or
`git rebase --signoff <base>` for a series.

**Why DCO and not CLA:** CLAs require a one-time signed agreement,
typically over a web form, that grants the project broad rights and
sometimes copyright assignment. DCO is per-commit, no central
collection, no copyright transfer, just an attestation that the
contributor has the right to submit. The Linux kernel uses DCO; so
do the Docker, Chef, GitLab, and Node.js projects. It is the
lower-friction path that preserves the same legal substrate for the
project owner: a clean provenance trail for every line of code.

---

## Pull request process

1. Fork, branch, commit. Branch name is free-form. **Every commit
   must carry a `Signed-off-by:` trailer (DCO; see preceding
   section).** Use `git commit -s`.
2. Open a PR against `master`. PR description must:
   - Name the FVS IDs, files, or modules touched.
   - State explicitly if it overturns anything in STRATEGY.md §6
     Durable Decisions.
   - Link the relevant issue or discussion, if any.
3. A reviewer (initially: Lovro) evaluates against the promotion
   criteria (for library entries) or against the detection-rule /
   test / MCP requirements (for code), and verifies DCO sign-off
   on every commit in the series.
4. Merge is at reviewer discretion. No external CI enforces promotion;
   review is human. PRs missing DCO sign-off are not merged; the fix
   is `git commit --amend -s` (single commit) or
   `git rebase --signoff <base>` (series).

---

## What a contribution cannot do without an RFC

- Overturn a durable decision from `STRATEGY.md` §6.
- Change the meaning of an existing FVS ID (create a new ID instead).
- Retire a `canon` entry (retirement is a separate governance path).
- Introduce a hosted MCP server or any surface that sends document
  text to a third-party LLM by default.
- Change the license of any existing file.

Open an issue with `[RFC]` in the title for these. A governance
decision (see `GOVERNANCE.md`) is required before code can land.

---

## Getting help

- **Issues:** open on GitHub for bugs, feature ideas, or questions.
- **Strategic alignment:** STRATEGY.md is the canonical direction
  document. PRs that conflict with it will stall.
- **Reviewing frames for canon promotion:** a different role from
  contributing via PR. See `REVIEWERS.md` at repo root for the open
  invitation, terms, deliverable shape, and how to engage. Reviewers
  evaluate existing library entries against the five promotion
  criteria; contributors (this document) add or modify library
  entries, detection rules, calibration data, or MCP tools.
- **Author:** Lovro Lucic. See CITATION.cff for contact.

Licensed: code Apache-2.0, corpus CC-BY-4.0.
