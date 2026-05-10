# Changelog

All notable changes to the Frame Check MCP server are documented here, in reverse chronological order. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [semantic versioning](https://semver.org/).

This changelog covers the public release line beginning with `0.8.0` (2026-04-27). Earlier development history is not part of the public canon. The Zenodo concept-DOI ([10.5281/zenodo.19888849](https://doi.org/10.5281/zenodo.19888849)) auto-resolves to the latest release for citation.

## [Unreleased]

## [0.9.4] - 2026-05-09

### Public canon: residual operator-document citations scrubbed

Closes the cleanup arc that began with 0.9.0 retiring the in-tree methodology document and the engine gap-inventory file from the wheel. Several adopter-facing surfaces still cited those documents as load-bearing references and the publish-time CI gate still required one of them. Adopters reading the citable artifacts found dead links and false claims; the publish workflow failed at every tag push.

- `CITATION.cff`: drop the dead URL pointing at a methodology file no longer in the public repo, and the false "bundled with the wheel" claim. Point the methodology citation at `github.com/Clarethium/lodestone` (the published methodology canon under CC-BY-4.0).
- `.github/workflows/publish.yml`: drop the methodology file from the required-files post-build gate. The wheel has not bundled it since 0.9.0; the gate had been failing CI on every tag push (v0.9.1, v0.9.2, v0.9.3 all failed at this step).
- `schemas/attribution-1.0.0.json`, `mcp_server.py`, `tests/test_mcp_server.py`: drop the "documented in §9.1" citations of the retired methodology document. The attribution schema's authoring home is the JSON file itself; its versioning policy is documented inline.
- `docs/FRAME_DIVERGENCE_CONTRACT_v1.md`: drop the versioned methodology resource URI (no implementation; the methodology resource auto-deregisters when the file is absent) and the engine gap-inventory citation in the engine-manifest description.
- `mcp_compose.py`: drop the gap-inventory citation comment on the engine_status assignment.
- `.github/ISSUE_TEMPLATE/feature_request.md`: rephrase the methodology checkbox to reference the empirical-studies / calibration-data surface adopters can actually inspect.
- `data/worked_examples/*` (markdown + JSON): drop the per-bundle citations of the engine gap-inventory and methodology sections in payload metadata and adopter-facing prose.

No code-behaviour change; no test-shape change. The MCP surface continues to advertise `frame-check://methodology` only when the file is present (and gracefully returns the standard 404-style error otherwise). 660 tests pass.

## [0.9.3] - 2026-05-09

### Source comment + docstring cleanup

Docstrings and comments inside shared MCP modules and several test files are rewritten to describe the engineering reality directly. The cleanup removes references to internal-only labels (cross-module composition step numbers, structural-rule revision tags) and a handful of paragraph-level phrases that signaled an internal counterpart. Each occurrence is rewritten in place; no vocabulary swap. After the pass, the extracted public tree audits clean.

### Wheel-build per-card cleanup

The 0.9.3 lift surfaced a parallel gap: wheel-bundled FVS-NNN library cards still carried `## Cross-family reliability` and `## Vocabulary connections` sections (operator-research version trajectory, evaluation paths, ratification narrative). The public extract pipeline already stripped these via `_clean_library_card`; the wheel-build hook applied only the literal canon-substitution map. The two surfaces had drifted. The hook now runs `_clean_library_card` on every wheel-bundled card, replaces `INDEX.md` with the public adopter index, and drops `README.md` (curator-discipline guide). RECORD regeneration handles the dropped paths so pip install verifies the post-cleanup file set.

### README adopter-pass

`README.md` is rewritten to describe the actual 0.9.x wheel content. The Documentation section lists what ships in the wheel today (`MCP_SERVER.md`, `FRAME_DIVERGENCE_CONTRACT_v1.md`, the FVS catalog under `data/frame_library/`, `data/worked_examples/`, governance / contributing / security / citation files) and points at `Clarethium/lodestone` for methodology canon. The repo-only web-app section is removed; the wheel's `METADATA` field is generated from `README.md`, so the README is part of the adopter surface.

### Wire-text rename in candidate surfacing

The reader-inspectable candidate-attribution layer in coverage / epistemic / claims is now named the "lower-bound detection posture" in adopter-facing surfaces. The interface is unchanged: `candidate_sentences[]` continues to surface where the primary detector did not fire but secondary patterns did, and the caveat language in MCP responses ("primary detector found N; candidate patterns surface M more the reader should inspect") is unchanged. Only the prose label moved.

### Audit pattern coverage extended

The `canon_audit.sh` RIGID family is extended to catch composition-step references, decomposition-step labels, structural-rule revision labels, and a small set of internal-vocabulary phrases that the prior pattern set missed. The audit run on a fresh extract returns zero hits.

### Test relaxation: methodology resource is optional

`test_resources_list_includes_library_and_docs` no longer requires `frame-check://methodology` in the resources/list response. The wheel does not bundle the methodology document; the resource auto-deregisters when the file is absent. The frame catalog and calibration tiers remain mandatory advertised resources.

### Note on prior versions

- 0.9.2 will be deleted from PyPI following the same policy as 0.8.x and 0.9.0/0.9.1: the wheel content is immutable, the construction pass landed in 0.9.3, and the version number is burned. Pin `>=0.9.3`.

## [0.9.2] - 2026-05-08

### Public canon discipline: residual cleanup + audit pattern extension

A fresh-eyes audit on the published 0.9.1 wheel surfaced two gap classes that the prior pattern set missed:

1. **Residual internal references in shipped Python source and one adopter doc.** Comments in shared MCP modules and several test files named internal audit documents, used sanitization markers, or carried catalog-versioning narrative (commit hash, ratification dates, version-trajectory exposition). Each occurrence has been rewritten to describe the engineering reason directly. The 14-line "Catalog stability and library_v4" block in `docs/MCP_SERVER.md` was rewritten to a 3-line statement: contract pin, future minor-version pin-option path, FVS-020 retirement from detection scope.

2. **Substitution-map shape was wrong.** `scripts/_release_lib/canon_replacements.txt` swapped one sanitization marker for another rather than removing it. Per FM-PCD-2 of the canon discipline, a sanitization marker is itself a leak: the marker reveals an internal counterpart exists. The fix is construction-not-redaction: rewrite each occurrence in the source to be context-neutral, do not swap one marker for another. The map now collapses both forms to a neutral term as a tripwire; the source rewrites are the load-bearing fix.

### Audit pattern coverage extended

`canon_audit.sh` PRIVATE_FILES and RIGID families were extended to catch the audit-document filename shapes, sanitization markers, and ratification-narrative phrasing that slipped through. The audit run on a fresh extract now catches what the prior pattern set missed.

### Note on prior versions

- 0.8.0-0.8.11 and 0.9.0 were deleted from PyPI (not yanked). The version numbers are burned forever. Pinned installs to those versions fail to resolve (404 from the simple-index). Adopters who pinned to a deleted version must upgrade to 0.9.2.
- 0.9.1 remains on PyPI but is superseded by 0.9.2 and may be deleted following the same policy. Pin `>=0.9.2`.
- The 0.9.1 CHANGELOG section below carries a now-inaccurate narrative because the deletion happened after 0.9.1 shipped. The wheel content is immutable; this entry supersedes that narrative.

## [0.9.1] - 2026-05-08

### Public canon discipline: comprehensive cleanup

This release replaces 0.9.0 (which itself superseded the 0.8.x line) as the first wheel that ships construction-clean public canon: documentation, frame catalog, source-comments, and tests have been authored for the adopter audience rather than redacted from internal sources. 0.9.0 was yanked because it still carried operator-research vocabulary in shipped FVS cards and worked-example narrative.

### Catalog: per-card cleanup

- `data/frame_library/INDEX.md` is rewritten as an adopter-facing data table: the 20 entries with their class, detection state, status, and curation date, plus column semantics. The earlier file additionally carried canon-trajectory rationale and library-version landscape exposition that was not adopter-facing.
- Per-card `## Cross-family reliability` and `## Vocabulary connections` sections are stripped from the public extract. The numerical reliability values continue to ship live in MCP responses (`library_consensus_ac1` field on each frame match); the per-card prose carrying the operator-research version trajectory does not.
- Worked-example markdowns (`data/worked_examples/*.md`) had internal "Note on detection state" blockquotes scrubbed; the adopter-facing teaching points remain.

### Wheel: scope unchanged from 0.9.0

The wheel bundles the MCP server contract (`docs/MCP_SERVER.md`), the Frame Divergence interface contract (`docs/FRAME_DIVERGENCE_CONTRACT_v1.md`), the FVS catalog (`data/frame_library/`), and the worked-examples corpus. The MCP resource registry auto-deregisters resources whose underlying files are absent. The Frame Vocabulary Standard methodology canon lives at `github.com/Clarethium/lodestone`.

### Engine: divergence catalog fallback

- `mcp_resources._library_v3_entries()` now falls back to `data/frame_library/` (excluding FVS-020) when `data/frame_library_v3/` is absent. The public extract drops the v3 directory because it duplicates the v4 catalog content; without this fallback the divergence engine returned an empty absence catalog and named-pattern triggers (`recommendation-without-falsification`, `growth-without-risk`, etc.) could not fire. The 0.9.0 wheel exhibited this regression for adopters whose deployment used the orchestrator-built wheel rather than the dev-tree wheel.

### Pipeline: extract-time + wheel-time guardrails

- `scripts/_release_lib/extract.py` runs nine phases. The canon-substitution phase applies a literal before-to-after map (`scripts/_release_lib/canon_replacements.txt`); the new card-cleanup phase truncates each FVS card at the first of `## Cross-family reliability` or `## Vocabulary connections` and replaces `data/frame_library/INDEX.md` with adopter-facing content; the canon-audit phase runs `scripts/canon_audit.sh` against the extracted tree and halts the release on any non-zero exit.
- `scripts/release.py` orchestrator's `_step_extract_public_tree` now invokes the same phases (`clean_library_cards`, `write_clean_run_tests`, full `.gitignore` including `framecheck_mcp/` build-staging excludes). Earlier the orchestrator had a stripped-down extract path that skipped FVS card cleaning and INDEX.md replacement; releases driven through it would have shipped a leaky wheel even when the standalone path was clean. Both paths now share the same phase set.
- `setup.py` registers a `bdist_wheel` hook that runs the canon-substitution map against the built wheel before it leaves the build directory; the same substitution map governs both the public-extract tree and the wheel content.
- New lift gate (`Canon audit on wheel content`): extracts the wheel and runs `canon_audit.sh` against the contents.
- The `framecheck_mcp/` build-staging tree (data files reconstructed from elsewhere on every wheel build) is now gitignored except for the two tracked source files (`__init__.py`, `source_network.py`). Earlier extracts left the staging tree visible in the public repo.

### Adopter-facing surface

- `AGENTS.md` added at the repo root: guidance for AI coding agents (Claude Code, Cursor, Codex, Aider) that work in the repository, with explicit canon-discipline rules.
- `README.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `SECURITY.md`, `docs/README.md`, `docs/MCP_SERVER.md`, `docs/FRAME_DIVERGENCE_CONTRACT_v1.md`, `docs/RATERS.md`, `NOTICE`, `.github/ISSUE_TEMPLATE/*` rewritten to remove dead-link surface and operator vocabulary.
- The cleaning replaced `evidence discipline` (operator phrasing) with adopter-facing phrasing throughout.

### Note on prior versions

- The 0.8.x line and 0.9.0 are yanked from PyPI. They shipped working code but bundled documentation and per-card content that mixed adopter-facing prose with internal vocabulary. 0.9.1 is the first construction-clean release. Existing pinned installs continue to work; new installs should pin to `>=0.9.1`.

## [0.9.0] - 2026-05-08

Yanked from PyPI; superseded by 0.9.1. The release renamed the public repository (`Clarethium/frame-check-mcp` → `Clarethium/frame-check`) and tightened the wheel-bundle scope, but per-card content in the FVS catalog and worked-example markdowns still carried internal vocabulary. Adopters who pinned to 0.9.0 should upgrade to 0.9.1.

## [0.8.10] - 2026-05-07

### Changed

- `mcp_compose.py` `PRODUCTION_STATUS` flipped from `"paused"` to `"active"`. The hosted web surface at `frame.clarethium.com` is live again; every MCP response now reports the current status via `provenance.production_status` and `provenance.production_status_note`.
- `CITATION.cff` top-level `version` reset to `"1.0.0"` to match the methodology brand-version axis (independent of the wheel patch version).
- `README.md` and `docs/MCP_SERVER.md` updated to reflect the live web surface.

## [0.8.9] - 2026-05-07

### Fixed

- Bundled documentation (frame catalog, worked examples, wheel-bundled docs) no longer carries broken links to a non-public host. Links that resolve to publicly-bundled paths are rewritten to the canonical `Clarethium/frame-check` URL; links that do not are dropped from the prose.

### Changed

- CI workflows narrowed to pull-request, schedule, and manual dispatch triggers. Push-on-master triggers were duplicating work and burning CI minutes. The release pipeline (`scripts/release.py`) runs preflight gates locally before any tag push.

## [0.8.8] - 2026-05-07

### Fixed

- `manifest.py` is now bundled in the wheel. Releases 0.8.6 and 0.8.7 omitted it, causing `ModuleNotFoundError` for adopters running `frame_check` or `frame_compare` against the installed wheel. Conformance driver against the new wheel passes 32/32.

### Process

- Pytest-against-source is no longer sufficient as a release gate. The conformance driver in `scripts/mcp_conformance_driver.py` imports against an installed wheel via a fresh venv and is the gate that catches missing-from-wheel modules. Future releases run the driver as part of `lift_dry_run` preflight.

## [0.8.7] - 2026-05-07

### Fixed

- `pyproject.toml [project.urls]` re-pointed at canonical `Clarethium/frame-check` URLs so PyPI page links resolve directly. `Homepage` moved to `blog.clarethium.com/frame-check`.
- METHODOLOGY.md §9 citation block: corrected the `master` branch reference (the public mirror's default branch is `master`, not `main`).
- 45 source files plus 29 generated artifacts: legacy `lluvr/frame-check-mcp` references replaced with direct `Clarethium/frame-check` URLs so adopters do not follow a redirect chain to land at the canonical home.

## [0.8.6] - 2026-05-07

### Changed

- Repository organization: 9 substantive docs moved from repo root to `docs/`. Public-mirror root drops to a smaller canonical primary set (`README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `SECURITY.md`, `LICENSE`, `NOTICE`, `CITATION.cff`). Wheel runtime URI resolution unchanged.
- New `docs/README.md` is the adopter-facing navigation index for the doc set, organized by intent (install + use, evaluate the methodology, validate the substrate, read the worked examples).

### CI

- Test matrix expanded from `["3.12"]` to `["3.10", "3.11", "3.12"]` to match the wheel's `requires-python = ">=3.10"`.
- `.github/workflows/codeql.yml` (new) wires GitHub-provided static security analysis (Python). Findings publish to the repo Security tab.
- `pytest-cov` line-coverage report wired into the `pytest-smoke` CI job.

### Build + test config

- `pytest.ini` consolidated into `pyproject.toml [tool.pytest.ini_options]` per the modern PEP 518 location. Settings preserved verbatim.
- `pyproject.toml [project.optional-dependencies] test` extras now include `pytest-cov`.

### Documentation

- README "Worked example" section added between "Approach" and "Documentation". The four-LLM Bitcoin retirement comparison is the load-bearing demonstration of what Frame Check does.
- README "Running tests" install command changed from `pip install -r requirements.txt` to `pip install -e .[test]`. The pyproject test extras (pytest, pytest-timeout, pytest-cov) plus the wheel dependency (PyYAML) are all an adopter actually needs.

### MCP citation surface: attribution schema 1.0.0

- Per-resource `_meta` block on every `resources/list` entry under reverse-DNS prefix `clarethium.com/` (per MCP spec 2025-06-18 _meta key naming rules). Standard fields: `license`, `license-uri`, `author`, `year`. Researchers and other tools that consume the canon programmatically have an in-band attribution chain.
- `frame-check://corpus/<slug>` URIs (bundled documents) carry `content-type: bundled-document` and `license-note` instead of CC-BY-4.0 attribution, so attribution is not over-claimed over verbatim third-party content.
- `resources/list` envelope carries `_meta.clarethium.com/attribution-schema-version: "1.0.0"` for evolution negotiation.

### Web app

- Layer A split into substrate (mandatory) + Source Network (best-effort) so SN failures degrade to a quiet banner instead of dropping the user's input. Always-render contract pinned by behavioral tests.
- Cloudflare Turnstile widget hardening: `data-refresh-expired="auto"` made explicit on every instance to avoid expired-token rejections on long-idle pages.
- CSS design system: `--bg-warn`, `--accent-warn`, `--bg-muted` tokens defined for both light and dark mode.

### Source Network: env knobs

- `SN_BUDGET_SECONDS` (default `25`): per-claim budget for SN verification across all providers.
- `SN_FETCH_JSON_DEADLINE_SECONDS` (default `8`): hard caller-side deadline on a single provider call.
- `SN_SEC_TICKERS_RETRY_AFTER_SECONDS` (default `60`): cool-down between SEC tickers JSON fetch retries.

## [0.8.5] - 2026-05-01

### Security and privacy

- Nonce-based CSP for inline scripts. The previous CSP allowed `'unsafe-inline'` for script-src; nonce-based CSP gives the browser a second filter against a future template addition that forgets Jinja2 autoescape on a user-controlled field.
- PII redaction now flows through the MCP server's `include_frame_opportunities` LLM path. Pre-fix, the web app's intake-side redaction did not flow through this entry point; closure routes the MCP-side LLM call through the same redactor stack the web endpoints use.
- Redactor unit tests added (`test_pii_redactor.py`, 28 tests) pinning the primitive `redact_pii_in_text` and `redact_pii_in_obj` surfaces.

### Documentation

- README: PyPI / license / Python-versions / methodology / CHANGELOG badges added to the generated header.
- `pyproject.toml` setuptools deprecations resolved (PEP 621 SPDX-string license form).

## [0.8.4] - 2026-05-01

### Fixed

- Public mirror CI restored to green. The mirror's tests workflow had been failing since v0.8.3; v0.8.4 audit fixed three classes of issue: stale test inventory, surgical `pytest.importorskip` gates on test files that exercise both the wheel-bundled subset and a small upstream-only piece, and a `run_tests.py` SKIP-vs-FAIL accounting fix.
- `llm_client.py` added to `pyproject.toml` py-modules; was previously untracked despite being lazy-imported by `comparison.py:154`.

### Changed

- 25 supporting documents moved out of the public-repo root to `docs/internal/` to clean up the surface. (Note: the `docs/internal/` subtree was removed entirely in a later release; this entry is preserved for historical accuracy.)

### Source Network

- Six `except Exception: pass` blocks in `comparison.py` and `source_network.py` now log to stderr on failure with the failing model / claim index and exception type. Sentinel-return contracts retained.

## [0.8.3] - 2026-04-28

### Changed

- Release orchestrator (`scripts/release.py`) introduced. Drives wheel build, lift gates, twine upload, public-repo sync, tag push, GitHub release creation, Zenodo poll, and CITATION back-fill inside its lock + state machine.
- `close_out` now bumps `mcp_server.py` `SERVER_VERSION` alongside `pyproject.toml [project] version` so the upstream tree's two version axes stay coherent across the release cycle.

## [0.8.2] - 2026-04-28

### Fixed

- 0.8.1 PyPI artifact had dead URLs in its Project-URL surface. 0.8.2 republishes from the public split repo with all six Project-URLs resolving.

## [0.8.1] - 2026-04-28

### Fixed

- Republished from the public split repo `Clarethium/frame-check` to fix the dead Project-URL surface that shipped in 0.8.0.

## [0.8.0] - 2026-04-27

### Added

- First public PyPI release. The `frame-check-mcp` package ships the analyzer modules (`framing.py`, `frame_library.py`, `claim_analysis.py`, `comparison.py`, `source_network.py`, `decision_readiness.py`, `frame_deepening.py`, `frame_opportunities.py`, `frame_patterns.py`, `entity_classifier.py`, `time_context.py`, `corpus_intelligence.py`, `genre_classifier.py`, `user_goals.py`) plus the MCP plumbing (`mcp_server.py`, `mcp_compose.py`, `mcp_resources.py`, `mcp_schema.py`, `mcp_log.py`).
- The Frame Vocabulary Standard catalog (20 entries under `data/frame_library/`) and worked examples under `data/worked_examples/` ship with the wheel.
- The divergence-block API contract (`docs/FRAME_DIVERGENCE_CONTRACT_v1.md` c1.0) and MCP server reference (`docs/MCP_SERVER.md`) ship as adopter-facing canonical references.
- Default-on frame-divergence block: agents passing the analysis to the user without attribution are flagged. Per the contract, divergence-block emission is mandatory unless the caller explicitly opts out.
- MCP surface delegates V4.2 judgment to the caller's agent model. Frame Check itself spends zero LLM cost per query.
