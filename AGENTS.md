# AGENTS.md

Guidance for AI coding agents (Claude Code, Cursor, Codex, Aider,
etc.) working in this repository.

This file is loaded by most agent runtimes the same way `CLAUDE.md`
or `.cursorrules` is. Read it before making changes.

## What this repo is

`Clarethium/frame-check-mcp` is the public canonical repository for
the Frame Check structural-framing analyzer plus its MCP server.
The analyzer modules at the repo root are the load-bearing
implementation; the MCP plumbing (`mcp_server.py`, `mcp_compose.py`,
`mcp_resources.py`, `mcp_schema.py`, `mcp_log.py`) and the
wheel-staged copies under `framecheck_mcp/` ship the analyzer as
the `frame-check-mcp` PyPI package.

The MCP surface delegates V4.2 judgment to the caller's agent
model; Frame Check itself spends zero LLM cost per query. See
`SECURITY.md` "Security-sensitive surfaces" for the wire and
input-shape contracts.

## What goes in this repo

This repository ships only what an adopter needs to install, run,
extend, and audit Frame Check. The scope is fixed:

- The analyzer modules at the repo root and their `framecheck_mcp/`
  wheel-staged copies.
- Tests under `tests/`.
- The frame catalog under `data/frame_library/` and
  `data/frame_library_v3/`, the worked examples under
  `data/worked_examples/`, and the validation corpus under
  `validation/decision_readiness/corpus/`.
- The divergence-block API contract (`docs/FRAME_DIVERGENCE_CONTRACT_v1.md`)
  and the MCP server reference (`docs/MCP_SERVER.md`).
- Adopter-facing docs: `docs/ANTICIPATED_CRITIQUES.md`,
  `docs/VALIDATION_PROGRAM.md`, `docs/RATERS.md`, `docs/README.md`.
- Root files: `README.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`,
  `SECURITY.md`, `CHANGELOG.md`, `LICENSE`, `NOTICE`, `CITATION.cff`,
  `pyproject.toml`, `setup.py`, `requirements.txt`, `pytest.ini`,
  `run_tests.py`.
- Pre-commit + secret-detection: `.pre-commit-config.yaml`,
  `.gitleaks.toml`.
- AGENTS.md (this file).

Anything outside that scope does not enter the repository. The
following content shapes are **never** committed here, regardless of
how relevant they feel to the change in front of you:

- Strategy memos, roadmap drafts, "what we are betting on"
  documents, positioning analyses.
- Audit deliverables: leakage audits, security audits, methodology
  audits, publication-readiness verdicts, gap inventories,
  remediation logs.
- Reviewer outreach lists, recruitment templates, methodology
  paper outlines or candidate-version drafts.
- Drafts of the methodology paper or Lodestone canon in this repo.
  Adopter-facing methodology lives at `Clarethium/lodestone`; this
  repo is the analyzer + MCP server only.
- Anything that names a private workspace, secrets vault, claude
  memory layout, or absolute path into a contributor's home
  directory.

Construction discipline: when public content is needed on a subject
that touches one of those shapes, write the public version from
scratch for the adopter audience. Do not paraphrase from a private
draft. If a paragraph reads naturally only to a reader who already
knows what is private, rewrite or remove it. Never substitute a
placeholder marker like "(see upstream development tree)" or "maintainer-side
X" for a removed reference; the marker itself reveals that a
private counterpart exists. Subtract over substitute: delete the
sentence and rewrite the surrounding paragraph to stand without
the citation.

## How this is enforced

Three layers, each independent:

1. **`.gitignore`** carries shape-based patterns that match common
   strategic-memo and audit-deliverable filenames so files of those
   shapes do not stage by accident.

2. **`.gitleaks.toml`** carries shape-based rules that refuse
   commits matching contributor-workspace absolute paths and the
   filename shapes in §2 above. Specific filename enumerations are
   loaded from a maintainer-side config file (not in this repo) so
   the public source code does not catalogue what it detects. Run
   `gitleaks detect` locally before committing if you are unsure.

3. **Branch protection ruleset** on the default branch blocks
   force-push, deletion, and non-linear history. History rewrite to
   clean a leak is a maintainer-led recovery operation, not part of
   normal flow.

## When you find an existing leak

If you discover that the public history contains content that
should not be there:

1. Open an issue describing the location and the rough shape of the
   content. Do not paste the leak itself into the issue.
2. Wait for maintainer acknowledgment before any history rewrite.
   History rewrite invalidates Zenodo DOIs, breaks external
   references, and may require coordinated PyPI yanks.

## Commit-message hygiene

A commit that removes leaked content should not narrate the leak in
its own message. The diff shows what was removed; the message should
not re-narrate it. If you are tempted to write "removed X", drop
the sentence; the diff is already authoritative.

## Engineering norms

- DCO sign-off required (`git commit -s ...`). The `dco-check`
  workflow blocks merges of unsigned commits.
- Tests run via `python3 run_tests.py` at the repo root, or directly
  via `python3 -m pytest -q`. All shipped tests must pass before
  merging.
- Style: no em-dashes, en-dashes, smart quotes, or curly apostrophes
  anywhere in committed content (prose, code, commit messages). Use
  straight quotes and rewrite sentences rather than reaching for an
  em-dash. The `check-no-em-dashes` pre-commit hook enforces this.
- No AI attribution in commit messages. No "Generated with Claude
  Code" footer. No `Co-Authored-By: Claude`. The work belongs to
  the human committer regardless of which tool produced the diff.

## Pointers for further reading

- `README.md`: what Frame Check is and how to use it.
- `docs/MCP_SERVER.md`: MCP server reference.
- `docs/FRAME_DIVERGENCE_CONTRACT_v1.md`: the divergence-block API
  contract.
- `docs/ANTICIPATED_CRITIQUES.md`: self-enumerated adversarial
  readings of the methodology.
- `docs/VALIDATION_PROGRAM.md`: observational + formal validation
  plans.
- `CONTRIBUTING.md`: PR flow, sign-off, style.
- `SECURITY.md`: vulnerability disclosure.
