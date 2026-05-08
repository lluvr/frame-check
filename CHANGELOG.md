# Changelog

All notable changes to the Frame Check MCP server are documented here, in reverse chronological order. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [semantic versioning](https://semver.org/).

This changelog covers the public release line beginning with `0.8.0` (2026-04-27). Earlier development history is not part of the public canon. The Zenodo concept-DOI ([10.5281/zenodo.19888849](https://doi.org/10.5281/zenodo.19888849)) auto-resolves to the latest release for citation.

## [Unreleased]

## [0.8.10] - 2026-05-07

### Changed

- `mcp_compose.py` `PRODUCTION_STATUS` flipped from `"paused"` to `"active"`. The hosted web surface at `frame.clarethium.com` is live again; every MCP response now reports the current status via `provenance.production_status` and `provenance.production_status_note`.
- `CITATION.cff` top-level `version` reset to `"1.0.0"` to match the methodology brand-version axis (independent of the wheel patch version).
- `README.md` and `docs/MCP_SERVER.md` updated to reflect the live web surface.

## [0.8.9] - 2026-05-07

### Fixed

- Bundled documentation (frame catalog, worked examples, wheel-bundled docs) no longer carries broken links to a non-public host. Links that resolve to publicly-bundled paths are rewritten to the canonical `Clarethium/frame-check-mcp` URL; links that do not are dropped from the prose.

### Changed

- CI workflows narrowed to pull-request, schedule, and manual dispatch triggers. Push-on-master triggers were duplicating work and burning CI minutes. The release pipeline (`scripts/release.py`) runs preflight gates locally before any tag push.

## [0.8.8] - 2026-05-07

### Fixed

- `manifest.py` is now bundled in the wheel. Releases 0.8.6 and 0.8.7 omitted it, causing `ModuleNotFoundError` for adopters running `frame_check` or `frame_compare` against the installed wheel. Conformance driver against the new wheel passes 32/32.

### Process

- Pytest-against-source is no longer sufficient as a release gate. The conformance driver in `scripts/mcp_conformance_driver.py` imports against an installed wheel via a fresh venv and is the gate that catches missing-from-wheel modules. Future releases run the driver as part of `lift_dry_run` preflight.

## [0.8.7] - 2026-05-07

### Fixed

- `pyproject.toml [project.urls]` re-pointed at canonical `Clarethium/frame-check-mcp` URLs so PyPI page links resolve directly. `Homepage` moved to `blog.clarethium.com/frame-check`.
- `METHODOLOGY.md` §9 citation block: corrected the `master` branch reference (the public mirror's default branch is `master`, not `main`).
- 45 source files plus 29 generated artifacts: legacy `lluvr/frame-check-mcp` references replaced with direct `Clarethium/frame-check-mcp` URLs so adopters do not follow a redirect chain to land at the canonical home.

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

- Republished from the public split repo `Clarethium/frame-check-mcp` to fix the dead Project-URL surface that shipped in 0.8.0.

## [0.8.0] - 2026-04-27

### Added

- First public PyPI release. The `frame-check-mcp` package ships the analyzer modules (`framing.py`, `frame_library.py`, `claim_analysis.py`, `comparison.py`, `source_network.py`, `decision_readiness.py`, `frame_deepening.py`, `frame_opportunities.py`, `frame_patterns.py`, `entity_classifier.py`, `time_context.py`, `corpus_intelligence.py`, `genre_classifier.py`, `user_goals.py`) plus the MCP plumbing (`mcp_server.py`, `mcp_compose.py`, `mcp_resources.py`, `mcp_schema.py`, `mcp_log.py`).
- The Frame Vocabulary Standard catalog (20 entries under `data/frame_library/` and `data/frame_library_v3/`) and worked examples under `data/worked_examples/` ship with the wheel.
- The divergence-block API contract (`docs/FRAME_DIVERGENCE_CONTRACT_v1.md` c1.0) and MCP server reference (`docs/MCP_SERVER.md`) ship as adopter-facing canonical references.
- Default-on frame-divergence block: agents passing the analysis to the user without attribution are flagged. Per the contract, divergence-block emission is mandatory unless the caller explicitly opts out.
- MCP surface delegates V4.2 judgment to the caller's agent model. Frame Check itself spends zero LLM cost per query.
