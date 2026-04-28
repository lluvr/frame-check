# MCP Package Design v1: `frame-check-mcp` on PyPI

> **PUBLISH HOLD (operator directive, 2026-04-23).** Do not upload to PyPI. Do not upload to TestPyPI. Do not publish. Design work, src-layout refactor, local `pip install -e .` validation, and wheel-build-to-dist/ may proceed. Any step that pushes bytes to a public index is blocked until the operator explicitly lifts this hold. The `0.7.1rc1` timing in §7.3 and the release flow in §9 assume the hold is lifted; until then, treat them as "ready to run, not yet run."

**Status:** proposal v1, 2026-04-23. Not implemented. Not approved. **Publish explicitly held per operator directive above.** Operator review before any packaging work begins; operator explicit lift before any public upload.
**Author:** collaborating agent (under curator review).
**Purpose:** enumerate what `frame-check-mcp` as a PyPI-distributable package should contain, how it should be shaped, and what decisions the operator needs to make before implementation. This document is a companion to `MCP_SERVER.md` (current state), `MCP_CONTRACT_V2_PROPOSAL.md` (payload-shape proposal), and `MCP_TYPESCRIPT_SCOPE.md` (out-of-scope reference). It is a scope proposal, not a ratified plan.
**Relationship to NEXT_STEPS Move 5:** this document's approval is the prerequisite for Move 5 execution. Implementing before approval is premature convergence.

---

## 1. Why package on PyPI

The repo currently installs by clone:

```json
{"mcpServers": {"frame-check": {"command": "python3", "args": ["/absolute/path/to/mcp_server.py"]}}}
```

Stress test §2.2 in `PUBLISH_READINESS_ASSESSMENT_v1.md` named "zero production integrations of the MCP contract" as the adoption rate-limiter. Two structural reasons and a behavioral one:

- **Discoverability.** `pip install frame-check-mcp` is a single command an agent-framework author can run. Cloning a 200-file repo to wire up one MCP server is a much bigger ask.
- **Versioning.** A PyPI version (0.7.1, 0.8.0, 1.0.0) is a citation artifact. `SERVER_VERSION` in `mcp_server.py` is internal; the pip version is what external consumers pin against.
- **Isolation.** A pip package with declared dependencies does not pollute the user's environment with web-app-only libraries (fastapi, pillow, duckdb, boto3, google-genai, openai). Claude Desktop users who install the MCP server get a clean 8-dep footprint, not the full 10+ deps of the web service.

The PyPI package is ALSO a forcing function on the v2 contract decision: once a `frame-check-mcp==1.0.0` is out, any v2 contract change is an explicit major-version bump with a migration window, not a perpetual proposal.

---

## 2. Package identity

| Field | Value | Rationale |
|---|---|---|
| PyPI name | `frame-check-mcp` | Available (404 on PyPI as of 2026-04-23). Hyphenated per PEP 508. Disambiguates from a possible future broader `frame-check` package. |
| Python module | `framecheck_mcp` | Underscore per PEP 8. Clear distinction from any `framing` or `framecheck` collision. `framecheck` (no dash) is taken on PyPI by a different project. |
| First version | `0.7.1` | Matches the existing `SERVER_VERSION = "0.7.1"` in `mcp_server.py:221`. Preserves continuity; no renumbering for the pip release. |
| License (code) | Apache-2.0 | Matches the repo's `LICENSE`. |
| License (data) | CC-BY-4.0 | Frame library / worked examples / transmissions / methodology markdown, per `NOTICE`. Both licenses ship in the wheel. Package README must direct consumers to `NOTICE` so the data-license split is clear. |
| Author | Lovro Lucic | Per `CITATION.cff`. |
| Keywords | `mcp`, `model-context-protocol`, `framing`, `text-analysis`, `agents`, `claude-desktop`, `cursor` | Standard MCP ecosystem discovery surface. |

Python version constraint: `>=3.10`. `mcp_server.py` uses `from __future__ import annotations` and PEP 604 union types in sibling modules; 3.10 is the documented floor.

---

## 3. Scope: what ships, what does not

### 3.1 In scope (Python modules)

The full transitive closure from `mcp_server.py` at runtime. Top-level imports use `sys.path.insert(0, _SCRIPT_DIR)` and lazy imports inside functions (confirmed by audit 2026-04-23). Minimum set:

- `mcp_server.py`: the MCP server itself
- `frame_library_index.py`: small adapter (175 lines); top-level import
- `decision_readiness.py`: decision-readiness profile builder (721 lines); top-level import
- `framing.py`: coverage/voice/temporal/epistemic detectors; lazy-imported
- `frame_library.py`: frame-matching rules; lazy-imported
- `claim_analysis.py`: claim extraction and hedging analysis; lazy-imported
- `comparison.py`: structural diff layer; lazy-imported (for `frame_compare` tool)
- `clarethium_measure.py`: measurement substrate providing `measure()` and `split_sentences()`
- `pipeline.py`: source-fidelity and grounding layers (for MCP's `verification` block when `source_text` supplied)
- `source_network.py`: fact verification dispatch (same as pipeline)
- `claim_selector.py`: claim selection logic
- `llm_cost.py`: cost constants (provenance block pins `$0.00` for the deterministic layer)
- `tier_a_event.py`: telemetry envelope helpers
- `model_registry.py`: model lineage stamping (used by tier_a_event)
- `telemetry.py`: may be needed transitively; to confirm by test-import during scaffolding

Size estimate: ~13-15 Python files, combined ~700KB source (mostly `mcp_server.py` itself at 172KB, then `source_network.py` at 136KB, `clarethium_measure.py` at 91KB, `framing.py` at 81KB). Total wheel likely ~300-400KB after byte-compile.

### 3.2 Explicitly out of scope

Not shipped with the package:

- `app.py` (212KB): the web app; MCP server does not touch it.
- `build_corpus_site.py` (298KB): corpus site generator; build tool only.
- `observatory.py` (73KB): scheduled topic daemon; Option D paused, not in MCP.
- `export_corpus.py` (37KB): R2 corpus export; operator-only.
- `security.py` (38KB): web-app middleware; MCP has no HTTP surface.
- `og_image.py`: OG card generator; web-only.
- `formatter.py`: web-UI HTML formatter; web-only.
- `test_*.py`: all test files. Tests can ship in an `sdist` but not in the `wheel`. Running tests on an installed package uses a separate `[test]` extra with pytest pinned.
- Dockerfile, fly.toml, entrypoint.sh, litestream.yml: deployment infrastructure; not consumer-facing.

### 3.3 Package data (non-Python files)

`mcp_server.py` reads filesystem paths at runtime via `_SCRIPT_DIR`. All must ship as `package_data`:

| Path (relative to package root) | Source in repo | Purpose |
|---|---|---|
| `data/frame_library/**/*.md` | `data/frame_library/` | Frame library entries + INDEX.md + AUDIT.md |
| `data/frame_library/VERSION` | same | Version string for `_install_version_info` |
| `data/worked_examples/**/*.md` | `data/worked_examples/` | Applied analyses surfaced as `frame-check://worked-examples/...` |
| `data/worked_examples/**/data.json` | same | Reproducibility fixtures for worked-example regression test |
| `data/transmissions/**/*.md` | `data/transmissions/` | Curated research pieces |
| `METHODOLOGY.md` | repo root | The methodology spec (51KB) |
| `calibration/results/*/` | `calibration/results/` | Reliability calibration artifacts |
| `validation/decision_readiness/results/*/aggregate.{json,md}` | same | Decision-readiness aggregate |
| `validation/decision_readiness/corpus/*/` | same | Per-slug corpus entries (10 slugs currently) |
| `pipeline_version.txt` | generated at build | Git SHA bake-time (see §10) |

Data size estimate: ~1-2MB compressed, dominated by METHODOLOGY.md and frame library markdown.

**Design constraint:** `mcp_server.py`'s `_SCRIPT_DIR` must resolve to a location where `data/frame_library/` and the other paths are reachable. This shapes the layout decision in §4.

---

## 4. Layout decision (the biggest open question)

Three options, with real trade-offs. I recommend option B but name the cost.

### Option A: flat-layout with `py-modules` declaration

```toml
[tool.setuptools]
py-modules = ["mcp_server", "frame_library_index", "decision_readiness", ...]

[tool.setuptools.package-data]
"*" = ["data/**/*.md", "METHODOLOGY.md", ...]
```

Each `.py` file installs as a top-level module. `import mcp_server` works after `pip install frame-check-mcp`.

- **Pro:** zero refactor to the repo. Existing `sys.path.insert(0, _SCRIPT_DIR)` and lazy imports continue to work because all modules land as peers.
- **Pro:** web app and MCP package share identical source paths; no duplicate-source risk.
- **Con:** **namespace pollution.** After `pip install`, the user's Python environment has top-level names `mcp_server`, `framing`, `clarethium_measure`, `pipeline`, etc. Any collision with another package (`pip install framing`? `pip install pipeline`?) is undefined. This is real risk, not theoretical; `pipeline` is a common package name.
- **Con:** not idiomatic; PyPI convention is namespaced packages.

### Option B: src-layout with namespace package (`src/framecheck_mcp/`)

```
src/framecheck_mcp/
    __init__.py
    mcp_server.py
    frame_library_index.py
    decision_readiness.py
    ...
    data/
        frame_library/
        worked_examples/
        ...
    pipeline_version.txt
```

All modules become `framecheck_mcp.X`. Clean namespace, conventional, no collision risk.

- **Pro:** proper Python packaging. `import framecheck_mcp` imports the server; `from framecheck_mcp import mcp_server` is the idiomatic entry.
- **Pro:** data files are a sub-package resource; `pkgutil.get_data()` or `importlib.resources` can address them cleanly (though `_SCRIPT_DIR` approach still works since `__file__` resolves correctly).
- **Con:** **requires the refactor** of every intra-repo import. `from framing import ...` becomes `from framecheck_mcp.framing import ...` OR `from .framing import ...` (relative). `sys.path.insert(0, _SCRIPT_DIR)` (line 73 of `mcp_server.py`) becomes harmless but useless; the line still executes on import but the directory is already on sys.path via the package mechanism. Best to remove it during the refactor to avoid reader confusion.
- **Con:** `test_mcp_server.py` also refactors. Every `import mcp_server` call site in the test file becomes `from framecheck_mcp import mcp_server` (or the test file itself moves under `src/framecheck_mcp/tests/`). 3,900+ lines; the change is mechanical but large. Also: `REPO_ROOT` references that spawn subprocess `python3 mcp_server.py` need to change to `python3 -m framecheck_mcp.mcp_server` OR the subprocess tests call the installed `frame-check-mcp` binary.
- **Con:** the web app (`app.py` at repo root) imports the same modules. The refactor forces the web app to either (a) also import via `framecheck_mcp.X` (awkward because app.py is NOT in the package), (b) depend on `frame-check-mcp` as a pip dependency even in dev, or (c) run with both paths on sys.path (fragile).
- **Con:** substantial 1-2-day refactor; touches every `.py` file in the in-scope set.

### Option C: flat-layout with `package_dir={"framecheck_mcp": "."}` mapping

```toml
[tool.setuptools]
package-dir = {"framecheck_mcp" = "."}
packages = ["framecheck_mcp"]
```

Same physical files at repo root; setuptools presents them to the installed environment under the `framecheck_mcp` namespace.

- **Pro:** no refactor; modules stay at repo root; web app continues to work with flat-layout imports.
- **Con:** **doesn't actually work** with internal imports. Once installed, `from framing import X` inside the installed package fails because the installed namespace is `framecheck_mcp.framing`, not `framing`. The `sys.path.insert(0, _SCRIPT_DIR)` trick at import time would try to re-add a nonexistent repo path.
- **Verdict:** option C looks appealing on paper but breaks on first `pip install` test. Rejected.

### Recommendation: Option B with a phased refactor

Accept the src-layout refactor cost. It is the only durable layout. Mitigate the dual-entry concern (package + web app) by:

1. Phase 1: relocate modules to `src/framecheck_mcp/`, refactor imports to relative (`from .framing import ...`), keep a shim `mcp_server.py` at repo root that does `from framecheck_mcp.mcp_server import main; main()` so existing Claude Desktop configs with absolute paths continue to work.
2. Phase 2: update `app.py` to either depend on `frame-check-mcp` as a pip dep in dev OR keep a parallel flat layout via a dev-only `pip install -e ./src/framecheck_mcp`. Decision deferred; app.py is NOT in this package's scope, but its dependency posture changes.
3. Phase 3: publish to TestPyPI, validate, publish to PyPI.

The 1-2-day refactor cost is real but one-time. Option A's collision risk is present forever.

---

## 5. Runtime dependencies

`requirements.txt` covers the full web-app stack. The MCP package subset is much smaller. Proposal for `[project].dependencies` in `pyproject.toml`:

```toml
[project]
dependencies = [
    "PyYAML>=6.0,<7.0",
]
```

**Rationale for exclusions:**

- `fastapi`, `uvicorn`, `jinja2`, `python-multipart`: web app only. MCP server uses JSON-RPC over stdio; no HTTP framework.
- `pillow`: og_image.py only. MCP has no image surface.
- `google-genai`, `openai`: LLM clients for web app's AI interpretation layer. **MCP's deterministic contract** (`analysis_cost_usd == 0.0`, per `MCP_SERVER.md` "Exercised contracts") explicitly forbids LLM calls. These packages MUST NOT be installed by the MCP package, or the contract is falsifiable.
- `duckdb`, `boto3`: corpus export pipeline; not MCP.
- `PyYAML`: used by `model_registry.py` to load `model_registry.yaml`. MCP's provenance block references model lineage; needed.

Verification TODO before release: scaffold a fresh venv with `pip install PyYAML`, then attempt to import every in-scope module. Any `ImportError` reveals an additional transitive dep.

**Optional extras:**

- `[test]`: pytest, pytest-timeout. Used by `test_mcp_server.py`; not needed by consumers.
- `[dev]`: pylint or ruff, mypy. Optional.

---

## 6. Entry point

```toml
[project.scripts]
frame-check-mcp = "framecheck_mcp.mcp_server:main"
```

After `pip install frame-check-mcp`, the `frame-check-mcp` command is on PATH. Claude Desktop config becomes:

```json
{"mcpServers": {"frame-check": {"command": "frame-check-mcp"}}}
```

No absolute path. No Python invocation. Works in any venv the user happens to be in when Claude Desktop launches.

`mcp_server.py`'s existing `if __name__ == "__main__": main()` stays. The `main()` function (line ~3920) is the entry. No code change.

---

## 7. Version and release strategy

> **SUPERSEDED by `STRATEGY.md §14` (2026-04-23 late-late evening).** The three-milestone arc below (`0.7.1` → `0.8.0` → `1.0.0`) was retired in favor of a two-milestone arc (`0.8.0` → `1.0.0`) per V4.2-first launch discipline. The `0.7.1` V1-only name-reservation release does NOT happen; the first public PyPI release is `0.8.0` with V4.2 by default. The text below is preserved as historical reasoning. Canonical release commitments live in `STRATEGY.md §14` and `MCP_SERVER.md` "Release arc." When those disagree with the text below, they win.

**Release plan per ENGINE_TIER_RECOMMENDATIONS_v1 Rec III (operator-approved 2026-04-23 afternoon).** Three milestones, each with a clear content commitment. The middle release is additive-enhancement of `frame_check` output, NOT a new tool (Rec II revision: divergence is an output-shape enhancement, not a separate `frame_divergence` tool).

### 7.1 First release: `0.7.1` (V1-only, reserves name)

Matches `SERVER_VERSION = "0.7.1"` in `mcp_server.py:221`. `frame_check` + `frame_compare` as they are today on the live surface. Zero LLM deps. v1 contract shape. Reserves `frame-check-mcp` PyPI name with a usable package. Install flow validated. Claude Desktop smoke transcript archived. Does NOT include divergence capability.

### 7.2 Middle release: `0.8.0` (divergence-capable, additive to v1 contract)

Enhances `frame_check` output with an optional `divergence` block (absent frames + domain-relevance filter + faithfulness notes per FRAME_DIVERGENCE_v1 §5.1) plus `agent_guidance.how_to_render_divergence` instructing the caller's model to complete the V4.2 judge composition. Requires:
- Library ratified (DONE 2026-04-23 as library_v3 at `data/frame_library_v3/`, commit `9abeb3d`)
- FRAME_DIVERGENCE Parts 2-4 landed (Part 2 defines block shape)

Backwards-compatible with 0.7.x consumers: v1-contract clients ignore the new `divergence` field. v2-ready clients use it. MCP surface stays at two tools.

### 7.3 Stable release: `1.0.0` (API freeze, v2 contract shape)

Adopts MCP_CONTRACT_V2_PROPOSAL construct-carrying shape. Breaking change: `coverage.missing` array replaced by per-dimension `status`/`markers_matched`/`vocabulary_searched` objects. `missing` key retired. This is the API-freeze line; external adopters pin `frame-check-mcp>=1.0,<2.0` from this point. The `divergence` block composes cleanly with the construct-carrying shape at this release.

Publishing 1.0.0 is a commitment: API freeze, deprecation cycle for breaking changes. `0.x.x` releases can break minor things with a CHANGELOG note; `1.x.x` cannot.

Semver summary going forward:
- `0.7.x` bug fixes and doc polish
- `0.8.x` additive enhancements to `frame_check` output (e.g., the divergence block shape refinements between 0.8.0 and 0.9.0 if needed)
- `1.0.0` breaking move to v2 contract shape
- `1.x.x` additive enhancements that respect the v2 shape
- `2.0.0` any future breaking change

### 7.4 Pre-release dry-run workflow (TestPyPI before real PyPI)

Before the real PyPI publish:

```bash
python3 -m build
python3 -m twine upload --repository testpypi dist/*
# in fresh venv:
pip install --index-url https://test.pypi.org/simple/ frame-check-mcp==0.7.1rc1
frame-check-mcp --version  # must report git_sha, corpus_hash, etc.
# add to Claude Desktop, test a frame_check call
```

Only after TestPyPI smoke passes does the real PyPI upload happen.

### 7.5 Name reservation pattern (why rc over placeholder)

An earlier draft of this doc proposed publishing a `0.0.0` placeholder wheel to reserve the name. That is the wrong pattern: PyPI treats persistently-empty packages as squatting under its acceptable-use policy, and a broken-on-install artifact harms the package's first impressions with `pip install` users.

Refined recommendation: when implementation reaches a basic-working state (the src-layout refactor compiles, `--version` works, one tool call succeeds), publish `0.7.1rc1` directly to **real PyPI** (not TestPyPI). `rc` (release-candidate) versions are accepted by PyPI and are NOT installed by default `pip install` (users need `--pre` or a pinned version). This simultaneously (a) reserves the name with a usable package, (b) starts the pre-release validation window, (c) avoids the "upload a broken placeholder" anti-pattern.

If the window between design-approval and implementation stretches past two weeks, a 10-minute defensive `0.7.1rc0` upload (exposing just the CLI entry with a "not ready" banner) is acceptable since `rc0` clearly communicates unreleased state.

---

## 8. Version + git-SHA bake pattern (separate concerns)

Version and git-SHA are two different things with different update cadences. The design keeps them separated in the build.

**Package version** (`0.7.1`, `0.8.0`, etc.) is stable across builds within a release and is hardcoded in `pyproject.toml`:

```toml
[project]
name = "frame-check-mcp"
version = "0.7.1"
```

No dynamic-version machinery. The version bumps when the operator bumps it and commits; it does not vary between builds of the same source revision.

**Git SHA** varies per-build and is baked at wheel-build time into a `_version.py` written by the build backend:

```python
# src/framecheck_mcp/_version.py  (generated)
__git_sha__ = "9079eb5"
__build_date__ = "2026-04-23T05:12:34Z"
```

Build script (invoked by `python -m build`):

```bash
GIT_SHA=$(git rev-parse --short HEAD)
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
cat > src/framecheck_mcp/_version.py <<EOF
__git_sha__ = "${GIT_SHA}"
__build_date__ = "${BUILD_DATE}"
EOF
```

The existing `_install_version_info` detection chain in `mcp_server.py` (git subprocess → `pipeline_version.txt` → "unknown") gets a fourth lookup inserted between steps 1 and 2: `try: from . import _version; info["git_sha"] = _version.__git_sha__`. On a pip-installed package, `_version.py` is the bake-time source of truth; git subprocess and `pipeline_version.txt` don't exist on the consumer's machine.

The Dockerfile's existing `pipeline_version.txt` mechanism (lines 67-75) remains untouched for the web-app container build. It is independent of the pip-package build.

---

## 9. Release verification plan

> **Scoped to the retired 0.7.1 release.** See §7 supersession note. The verification-step pattern (fresh-venv install, test-suite import, real-client smoke, subprocess roundtrip) applies to any PyPI release; the specific version pins and expected fingerprint values below are not current. For the canonical release arc, see `STRATEGY.md §14` and `MCP_SERVER.md` "Release arc."

After PyPI publish of 0.7.1:

1. **Fresh-venv install test** (autonomous): `python3 -m venv /tmp/fcmcp && /tmp/fcmcp/bin/pip install frame-check-mcp==0.7.1 && /tmp/fcmcp/bin/frame-check-mcp --version`. Must report server_version matching the published pin, git_sha=<actual>, corpus_hash=<actual>, frame_library_version matching the shipped library (0.2.0 as of 2026-04-24).
2. **Test-suite import test** (autonomous): clone the repo at the tagged version, install the published package, run `python3 -m pytest test_mcp_server.py` against the installed package. All 110 tests pass.
3. **Claude Desktop smoke** (operator): install in a real Claude Desktop config, restart the app, ask "can you frame-check this document?" with a canned paragraph. Record the transcript as `docs/mcp_real_client_smoke/2026-XX-XX-claude-desktop.txt`. This is the Move 4 deferred item; Move 5 picks it up.
4. **Subprocess roundtrip against installed binary**: `echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' | frame-check-mcp`. Must return a valid JSON-RPC response.

All four must pass before the release is declared stable.

---

## 10. What this design does NOT decide

- **Whether to adopt the src-layout refactor (§4 Option B).** Recommended, but the operator must weigh the 1-2-day cost and the downstream effect on `app.py` plus `test_mcp_server.py`.
- **Whether to ship `0.7.1rc1` for early reservation vs waiting for `0.7.1` final.** Recommended: publish `rc1` when basic-working, then iterate `rc2`, `rc3` as issues emerge, then cut final.
- **Whether v2 contract (from `MCP_CONTRACT_V2_PROPOSAL.md`) lands as `1.0.0` or is shipped in a `0.x` breaking release with a CHANGELOG warning.** Depends on adoption velocity between now and v2's readiness.
- **Whether `telemetry.py` belongs in the MCP package.** Needs a scaffolding import test; I did not confirm the transitive dependency in this pass.
- **Whether the Claude Desktop smoke is a blocker on the release announcement.** I think yes; operator confirms.

### Prerequisites the operator must arrange (blocking on implementation)

- **PyPI account + API token.** The maintainer identity (Lovro Lucic / `lluvr`) needs a PyPI account and a project-scoped API token configured in `~/.pypirc` or via environment (`TWINE_USERNAME=__token__` / `TWINE_PASSWORD=<pypi-...>`). TestPyPI needs a separate account + token. Without these, neither upload works.
- **ORCID (optional but recommended).** Linking PyPI to ORCID makes the package's provenance more legible for academic citation. Matches `CITATION.cff` posture.
- **`twine` + `build` installed locally.** `pip install --upgrade build twine`. One-time setup on the operator's build host.
- **`frame-check-mcp` name verified still-available the day of reservation publish.** `pip index versions frame-check-mcp` should 404 immediately before the first `twine upload`. I verified availability on 2026-04-23; stale by the implementation day.

---

## 11. Honest limits of this design

- **Transitive-import closure is estimated, not verified.** I enumerated in-scope modules from a grep + lazy-import inspection. An actual `python -c "import framecheck_mcp"` in a clean environment might reveal additional transitive imports I missed. The scaffolding phase (before TestPyPI upload) must confirm.
- **Data size estimates are rough.** 1-2MB is a band, not a hard number. The actual wheel size depends on byte-compile, package-data compression, and whether calibration/validation subsets are included or excluded.
- **Option B's phased refactor is described at the shape level, not the commit level.** The actual refactor likely uncovers edge cases (circular imports, absolute-path assumptions, `_SCRIPT_DIR` dependencies in downstream modules) that this doc does not enumerate.
- **PyPI's `frame-check-mcp` availability was checked on 2026-04-23.** Could be claimed between now and the actual publish. Reservation placeholder mitigates.
- **No load-testing.** The MCP server runs under stdio with one client at a time; a PyPI-packaged version does not change that. But any agent framework that invokes it differently (connection pooling, long-lived sessions across many docs) might surface issues not caught by the 50-request rapid-fire test.
- **Security posture unchanged.** The package inherits the MCP server's zero-HTTP attack surface. But `pip install` from PyPI introduces a supply-chain trust surface that the cloning model did not have. Recommendation: sign releases with sigstore once PyPI supports it universally, and publish a `SECURITY.md` reference in the package README.

---

## 12. Proposed next move

If the operator approves Option B with the phased refactor:

1. **Week 1 day 1-2:** src-layout refactor. Relocate in-scope modules to `src/framecheck_mcp/`. Convert imports to relative. Keep `mcp_server.py` at repo root as a thin shim. Keep web-app imports working via dev install `pip install -e src/framecheck_mcp`. Tests must still pass.
2. **Week 1 day 2-3:** `pyproject.toml`, `MANIFEST.in`, build-time `_version.py` generator. Publish `0.0.0` placeholder to claim the name. Publish `0.7.1rc1` to TestPyPI. Fresh-venv install test. All 110 MCP tests pass against the installed package.
3. **Week 1 day 3-4:** publish `0.7.1` to PyPI. Update `MCP_SERVER.md` install docs (new `pip install frame-check-mcp` flow as primary; absolute-path stays as a dev fallback). Update `STRATEGY.md §11` Frame Check row to note the PyPI distribution.
4. **Week 2 day 1:** operator runs the Claude Desktop smoke per §9.3, archives the transcript under `docs/mcp_real_client_smoke/`, and announces the release through whatever channel §9.3's transcript justifies.

If the operator rejects Option B and prefers Option A, the work compresses to ~1 day but carries the namespace-pollution risk for the life of the package.

---

*v1. 2026-04-23. Pre-implementation scope proposal for Move 5 (NEXT_STEPS). Written against the state of the repo at commit `9079eb5` after the Fly redeploy completed at 04:40Z. Implementation does not begin until this document is approved or explicitly rejected in favor of a specific alternative.*
