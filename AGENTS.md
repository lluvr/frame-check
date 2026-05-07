# AGENTS.md

Guidance for AI coding agents (Claude Code, Cursor, Codex, Aider,
etc.) working in this repository.

This file is loaded by most agent runtimes the same way `CLAUDE.md`
or `.cursorrules` is. Agents should read it before making changes.

## What this repo is

`Clarethium/frame-check-mcp` is the public canonical repo for the
Frame Check structural-framing analyzer plus its MCP server. The
analyzer modules at the repo root are the load-bearing
implementation; the MCP plumbing (`mcp_server.py`,
`mcp_compose.py`, etc.) and the wheel-staged copies under
`framecheck_mcp/` ship the analyzer as the `frame-check-mcp` PyPI
package.

The MCP surface delegates V4.2 judgment to the caller's agent
model; Frame Check itself spends zero LLM cost per query. See
`SECURITY.md` "Security-sensitive surfaces" for the wire and
input-shape contracts.

## Public-canon discipline

This repo is one of several public Clarethium artifacts. The
operator maintains a separate, private working set of strategic
memos, audit deliverables, methodology drafts, outreach lists,
calibration sets, engine-tier strategy notes, and similar
artifacts. Those **never** enter this repo, regardless of how
relevant they feel to the change in front of you.

If you are tempted to commit a file with any of these shapes:

- An audit of leakage, security, methodology gaps, or publication
  readiness (e.g. `LEAKAGE_AUDIT_*.md`, `REMEDIATION_LOG_*.md`,
  `PUBLISH_READINESS_VERDICT_*.md`).
- An engine-tier strategy or recommendations memo.
- A methodology paper outline, methodology-version candidates list,
  or anchor-authorship draft.
- A conformance report, integrator outreach plan, or reviewer
  outreach template.
- A construct-honesty / engine-gap inventory.
- Anything mentioning the operator's secrets vault, claude memory
  layout, or absolute paths into the operator's home directory
  (`/home/<operator>/...`).

Stop. That belongs in the operator's private workspace, not here.
Either drop the change, or write a generalized public-canon version
that documents the *outcome* (what shipped, what is verifiable)
without the maintainer-internal *reasoning* (why specifically, who
else is involved, what is queued).

## How this is enforced

Three layers of enforcement, each independent of the others:

1. **`.gitignore`** at repo root carries patterns for the
   internal-doc artifact families (`*_INVENTORY_v*.md`,
   `*_AUDIT_v*.md`, `*_VERDICT_v*.md`, `*_REMEDIATION_LOG_v*.md`,
   `*_OUTREACH_v*.md`, `*_PROMOTION.md`, `EXTRACT_POLICY.md`,
   `PUBLICATION_STATE_v*.md`, `RELEASE_PREP_v*.md`,
   `ENGINE_TIER_*.md`, `METHODOLOGY_PAPER_*.md`,
   `METHODOLOGY_V*_CANDIDATES_*.md`,
   `TRACK_*_INFORMAL_STUDY_*.md`, `verify_publication_state.sh`,
   `docs/internal/`, plus a catch-all `*maintainer-internal*`).

2. **`.gitleaks.toml`** at repo root carries rules that refuse
   commits matching the maintainer-internal artifact path patterns,
   absolute operator-workspace paths, and operator-vault component
   names by name. Run `gitleaks detect` locally before committing
   if you are unsure about a change.

3. **Branch protection ruleset** on the `master` branch blocks
   force-push, deletion, and non-linear history. History rewrite
   to clean up a leak is an maintainer-side recovery operation,
   not part of normal flow.

## When you find an existing leak

If you discover that the public history contains maintainer-internal
content (rare, but happens), do not silently delete it in a
forward-only commit. Instead:

1. Open an issue describing what you found, where, and the rough
   shape of the content (do not paste the leak itself into the
   issue).
2. Wait for maintainer-side acknowledgment before any history
   rewrite. History rewrite breaks external references, requires
   coordinated PyPI yanks if the affected wheel was published, and
   may invalidate cached references in dependent tools.

## Commit-message hygiene

A commit that removes leaked content should not narrate the leak
in its own message. The diff shows what was removed; the message
should not re-narrate it. If you must reference what was removed,
use a generic descriptor like "an maintainer-internal artifact"
rather than the document name or content category.

## Engineering norms

- DCO sign-off is required (`git commit -s ...`). The `DCO`
  workflow blocks merges of unsigned commits.
- Tests live alongside the modules (`test_*.py` at repo root) and
  in `tests/`. The CI matrix runs Python 3.10 / 3.11 / 3.12.
  Adversarial harness in `test_mcp_adversarial.py` (61 tests
  across 7 attack classes) is the security-relevant pin; do not
  weaken it.
- Style: no em-dashes, en-dashes, smart quotes, or curly
  apostrophes anywhere in committed content (prose, code,
  commit messages). `scripts/check_no_em_dashes.py` enforces
  this if invoked locally.
- No AI attribution in commit messages. No "Generated with
  Claude Code" footer. No `Co-Authored-By: Claude`. The work is
  the operator's regardless of which tool produced the diff.
- The wheel content is gated by `setup.py`'s `_stage_package_data`
  + `_should_skip` logic. Adding files to the wheel goes through
  `_DATA_CARRIERS`; bundling decisions are commit-reviewable.

## Pointers for further reading

- `README.md`: what Frame Check is and how to use it.
- `docs/METHODOLOGY.md`: v0.2 methodology paper (canonical).
- `docs/FRAME_DIVERGENCE_v1.md` + `docs/FRAME_DIVERGENCE_CONTRACT_v1.md`:
  the c1.0 interface contract; load-bearing for callers.
- `CONTRIBUTING.md`: PR flow, sign-off, style.
- `SECURITY.md`: vulnerability disclosure and verifiable-audit
  reproduction steps.
- `docs/MCP_SERVER.md`: MCP tools, resources, prompts reference.
