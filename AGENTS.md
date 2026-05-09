# AGENTS.md

Guidance for AI coding agents (Claude Code, Cursor, Codex, Aider,
and similar) working in this repository.

This file is loaded by most agent runtimes the same way CLAUDE.md
or `.cursorrules` is. Read it before making changes.

## What this repo is

`Clarethium/frame-check` is the public canonical repository for the
**Frame Check MCP server**: a structural framing analysis tool
distributed as the PyPI package `frame-check-mcp`. The MCP server
gives any MCP-compatible AI client (Claude Desktop, Cursor, Cline,
Continue.dev, etc.) deterministic structural framing analysis as a
tool, with $0.00 per query at the server (no LLM calls server-side;
optional caller-side LLM judgment for V4.2 capability).

The repository ships the source the wheel is built from, the
adopter-facing documentation, the calibration corpus, the worked
examples, and the validation harness scaffold.

## What goes in this repo

This repository ships only what an adopter needs to install, run,
extend, and verify Frame Check. The scope is fixed:

- Python source at the repo root (`mcp_server.py`, `framing.py`,
  `comparison.py`, `frame_library.py`, etc.) and the `framecheck_mcp/`
  package wrapper.
- Tests under `tests/`.
- Build + lift infrastructure under `scripts/` (`canon_audit.sh`,
  `lift_dry_run.py`, `mcp_conformance_driver.py`,
  `_release_lib/`).
- Adopter-facing documentation: `README.md`, `CONTRIBUTING.md`,
  `GOVERNANCE.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  `RELEASING.md`, `ROADMAP.md`, `CHANGELOG.md`, `LICENSE`,
  `NOTICE`, `CITATION.cff`, `AGENTS.md` (this file), and the `docs/` tree
  (MCP_SERVER, COOKBOOK, FRAME_DIVERGENCE_CONTRACT, RATERS, VALIDATION_PROGRAM).
- The Frame Vocabulary Standard catalog at `data/frame_library/`,
  the worked examples at `data/worked_examples/`, the transmissions
  at `data/transmissions/`, and calibration corpora.

Anything outside that scope does not enter the repository. The
following content shapes are **never** committed here, regardless of
how relevant they feel to the change in front of you:

- Strategy memos, roadmap drafts, positioning analyses.
- Audit deliverables: leakage audits, methodology audits, gap
  inventories, publication-readiness verdicts.
- Internal evaluation trees, ratification logs, library-
  version trajectory exposition.
- Personal context, working notes, session state, vault references.
- Files whose presence on the public surface is itself a signal of
  internal state.

If a change feels valuable but does not match an adopter need on a
shipped artifact, it does not belong here. The right place for it is
the operator's upstream development tree.

## Public canon discipline

This repository follows a strict construction-not-redaction
discipline: public canon is authored for the adopter audience from
scratch, never produced by sanitizing internal sources.

Concrete rules for agents:

1. **Do not paste internal vocabulary.** Phrases like
   "internal X", "the operator's strategy", "construct-honesty
   discipline", "named-authorship curation", "publication-quality", "the
   bet", "(see upstream development tree)" do not belong in this repository
   under any circumstance.

2. **Do not reference operator-only documents.** Files like
   METHODOLOGY.md, FRAME_DIVERGENCE_v1.md, V4_2_GAP_INVENTORY_v1.md,
   MCP_CONTRACT_V2_PROPOSAL.md, LEAKAGE_AUDIT_v1.md,
   REMEDIATION_LOG_v1.md, RULE_AUDIT.md, LIBRARY_V3_TO_V4_RATIFICATION_v1.md,
   `fvs_eval/*` paths do not exist on this surface. If a change
   would benefit from citing one, it instead needs adopter-facing
   prose authored from scratch.

3. **Do not reference operator library-version trajectory.** Bare
   token `library_v3` is acceptable as a catalog version label
   adopters see in MCP responses. Phrases like "library_v4 ratified
   2026-04-24", "byte-equivalence to library_v3", "library_current
   historical", "Step 4 ratification" are internal canon-
   development context and do not belong here.

4. **The audit is at `scripts/canon_audit.sh`.** The CI runs it on
   every push. A failing audit is a leak; the recovery is to
   subtract the leak content, not to expand the allowlist.

5. **For absences.** If you notice an apparent regression (a file
   missing, a resource not advertised, a test relaxed), the default
   reading is intentional cleanup, not a defect. Run
   `bash scripts/canon_audit.sh` against the file under
   consideration before assuming a fix is needed; if the audit
   would flag the would-be-restored content, the absence is
   intentional.

## What changes belong here

- Adopter-relevant bug fixes in the wheel-bundled modules.
- Documentation improvements (README, CONTRIBUTING, MCP_SERVER, etc.).
- Test additions covering shipped behavior.
- New worked examples authored for the adopter audience.
- Pre-commit + CI hardening (em-dash discipline, gitleaks, canon
  audit).
- Wheel build + lift infrastructure improvements.

## What changes do NOT belong here

- Any of the internal content shapes named above.
- Tests pinning internal behavior or test fixtures
  containing operator vault references (the existing fixtures are
  marked `# canon-exempt:` for the leak-detection assertions; add
  new ones the same way only when the test is genuinely about
  redaction or leak detection, never as a workaround for a leak).
- Internal release-tooling secrets, deploy targets, vault keys, or
  cloud-account specifics.

## Pull request workflow

1. Read `CONTRIBUTING.md` for the mechanical PR process.
2. Read `GOVERNANCE.md` for the durable decisions a PR would need
   to address explicitly.
3. Run the canon audit locally: `bash scripts/canon_audit.sh`.
   It must exit 0 before the PR opens.
4. Run the full test suite: `python3 run_tests.py` (or
   `python3 -m pytest -q`). It must stay green.
5. Open the PR with sign-off-by-DCO. Reviewers will check the canon
   discipline, the test coverage, and the documentation
   coherence.

## Issues + reports

- Bugs, feature requests, library proposals: GitHub Issues with the
  templates under `.github/ISSUE_TEMPLATE/`.
- Security: see `SECURITY.md` for the disclosure process.
- Press, partnership, sensitive reports: `hello@clarethium.com`.

## When in doubt

If a change feels like it might cross the public-canon boundary,
default to NOT committing it here. The cost of a leak is much
higher than the cost of asking. Open a discussion on the PR; a
maintainer will route the work to the right surface.
