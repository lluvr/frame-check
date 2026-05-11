# Changelog

All notable changes to the Frame Check MCP server are documented here, in reverse chronological order. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [semantic versioning](https://semver.org/).

This changelog covers the public release line beginning with `0.8.0` (2026-04-27). Earlier development history is not part of the public canon. The Zenodo concept-DOI ([10.5281/zenodo.19888849](https://doi.org/10.5281/zenodo.19888849)) auto-resolves to the latest release for citation.

## [Unreleased]

## [1.0.3] - 2026-05-11

### publish.yml: pass release notes via env var (not direct expression substitution)

`gh release create --notes "${{ steps.notes.outputs.notes }}"` lets
GitHub Actions substitute the notes content directly into the bash
script string. Bash then performs command substitution on any
backticks in the value. The CHANGELOG `[1.0.2]` section included
the literal text `` `git tag -l --format='%(contents)'` `` in a
backtick code span — bash ran that as an actual command, the
output (every tag's annotation, concatenated) got spliced into
the release body, and other backticked code spans (e.g.
`` `actions/checkout@v4` ``) returned empty (not a real command),
which left holes in the prose.

Surfaced at the v1.0.2 cut. Recovery: one-shot `gh release edit
--notes`. Real fix: pass the notes via an env var so bash treats
them as literal characters:

```yaml
env:
  NOTES: ${{ steps.notes.outputs.notes }}
run: |
  gh release create ... --notes "$NOTES" ...
```

`"$NOTES"` is variable expansion only; bash does not perform
command substitution on the value. Backticks inside the
CHANGELOG annotation now reach `gh release create` as literal
characters and render as Markdown code spans on the release page.

This is the third release-body recurrence in the v1.0.x line
(v1.0.0 commit-message fallthrough, v1.0.1 annotation overwrite,
v1.0.2 backtick command substitution). Each cut surfaced a
different load-bearing detail of the release-notes-extraction
path; v1.0.3 is the live test that the env-var fix carries
through.

## [1.0.2] - 2026-05-11

### publish.yml: re-fetch annotated tag after actions/checkout overwrites it

`actions/checkout@v4` with `fetch-tags: true` does TWO fetches: the
first (`+refs/tags/*:refs/tags/*`) gets the annotated tag object;
the second (`--no-tags ... +<commit-sha>:refs/tags/<tag>`)
OVERWRITES the tag ref to point directly at the commit, replacing
the annotated form with a lightweight one. After that overwrite,
`git tag -l --format='%(contents)'` falls through to the commit's
message instead of the annotation.

Surfaced at the v1.0.1 cut even with the v1.0.0 fetch-tags fix
applied: the release body still shipped as the commit message.
Recovery for v1.0.1 was a one-shot `gh release edit --notes`. The
real fix in `publish.yml` is a new step before the extract that
explicitly re-fetches the tag, restoring the annotated object that
checkout's second fetch dropped:

```yaml
- name: Re-fetch annotated tag (work around actions/checkout overwrite)
  run: |
    git fetch origin --force "+refs/tags/${GITHUB_REF_NAME}:refs/tags/${GITHUB_REF_NAME}"
```

Verified locally by replaying the actions/checkout double-fetch
sequence and confirming the re-fetch step restores the annotation.

## [1.0.1] - 2026-05-11

### Per-module 80% coverage on the wheel surface (v1.0 contract closed)

The v1.0 ROADMAP committed each of the seven wheel-surface modules
to 80% production-code coverage; v1.0.0 deferred this because four
modules were below target. The deferral closes at v1.0.1:

| Module                  | At v1.0.0 | At v1.0.1 |
|-------------------------|-----------|-----------|
| `comparison`            |  20.9%    | 86.5%     |
| `clarethium_measure`    |  62.6%    | 84.4%     |
| `framing`               |  69.5%    | 82.6%     |
| `mcp_server`            |  69.4%    | 81.5%     |
| `mcp_resources`         |  90.3%    | 90.3%     |
| `mcp_compose`           |  94.9%    | 94.9%     |
| `mcp_schema`            | 100.0%    | 100.0%    |

Three new test files land alongside the close-out:

- `tests/test_comparison.py` (124 tests): pure-function core +
  provider-mock harness for `generate_gemini`, `generate_grok`,
  `generate_responses`, `generate_stability_check`,
  `stability_n3_check`. The harness seeds `sys.modules` with a
  stub `google.genai` and patches `llm_client.xai_openai_client`
  so the LLM-network entry points exercise without touching any
  external service.
- `tests/test_framing_synthesis.py` (20 tests): targets
  `framing_summary`, `framing_portrait_natural`, and
  `framing_headline` (the synthesis layer the prior surface only
  ran indirectly through the MCP composer).
- `tests/test_mcp_server_cli.py` (29 tests): targets `cli()`
  argv dispatch, `_cli_help`, `_cli_version`,
  `_install_version_info` (including three fallback-path tests),
  the `main()` JSON-RPC stdio loop driven by `io.StringIO`
  patching, the `__getattr__` proxy to `mcp_resources` cache
  state, and the `dispatch()` unhandled-exception branch.
- `tests/test_clarethium_measure_top_level.py` (42 tests):
  `measure()` orchestrator, the layer-function leaves
  (`source_matching`, `entity_provenance`, `vocabulary_proximity`,
  `epistemic_calibration`, `information_novelty`,
  `quality_profile`, `grounding_decomposition`,
  `temporal_consistency`), helper functions, `print_profile`,
  and the `main()` argparse CLI entry.

`scripts/check_per_module_coverage.py` enforces the per-module
floor in CI: it loads the .coverage file produced by
`pytest --cov` and exits non-zero if any of the seven modules
falls below 80%. The new `Per-module 80% floor (v1.0 wheel-
surface contract)` step in `tests.yml` runs this script as
strict-blocking on the 3.12 matrix row. Total tests in the
suite: 666 -> 882 (+216).

### Manifest payload: `frame_check_version` is the canonical field name

The `frame_check` and `frame_compare` MCP tool responses include an
`analysis.manifest` block whose version field was historically
emitted as `framecheck_version` (no underscore between `frame` and
`check`). That was a typo introduced in v0.9.1 (commit `12cb0e29`,
2026-05-07) — every other surface in the codebase (the sibling
`provenance.frame_check_version` field, the
`FRAME_CHECK_VERSION` Python constant, all worked-example fixtures,
the version-coherence test) uses the underscore-separated form.

The manifest now emits **both** keys carrying the same value:

```json
"manifest": {
  "frame_check_version": "1.0.1",   // canonical
  "framecheck_version": "1.0.1",    // deprecated, removed at v2.0
  ...
}
```

Adopters who parsed the legacy `framecheck_version` keep working;
new integrations should read `frame_check_version` (which matches
the documented field everywhere else). The deprecated key is
scheduled for removal at the next major version (v2.0). Test
`test_manifest_emits_canonical_and_legacy_version_keys` locks the
additive contract.

### publish.yml: github-release annotation extraction

`actions/checkout@v4` in the `github-release` job uses
`fetch-tags: true`. Without it the runner has the commit history
but not tag *objects*, so the release-body extraction step's
`git tag -l --format='%(contents)'` falls through to the tagged
commit's message instead of the annotation. Surfaced during the
v1.0.0 cut when the GitHub release body shipped as a commit
message; recovered for that release with a one-shot
`gh release edit --notes`; this gate prevents the recurrence in
v1.0.1+.

### publish.yml: workflow_dispatch hardening

The publish-to-pypi, publish-to-testpypi, and github-release jobs
now require `github.event_name == 'push'` in addition to the
existing `startsWith(github.ref, 'refs/tags/v')` gate. Without it,
`gh workflow run publish.yml --ref v<existing-tag>` would build
the wheel and try to publish, fail at PyPI duplicate-version
rejection, and leave noisy failed-run history. Tag pushes still
fire normally; workflow_dispatch (the manual-verification path)
runs only preflight + build.

### Test quality: silent-pass bug surfaced + closed across 125 tests

The `check()` helper at `tests/test_mcp_server.py:47` appends to a
module-level `_FAILURES` list but does not raise. Tests that used
`check()` and didn't snapshot `_FAILURES` plus call
`_assert_no_new_failures` at the end *silently passed under
pytest* even when `check()` had recorded failures. The helper's
docstring documented this gap (lines 56-75); only ~half the file's
tests had adopted the helper pattern.

The 1.0.1 cut surfaced the gap via mutation testing: dropping
`"analysis": analysis,` from the MCP epistemic payload assembly
(a fundamental contract break) caused `test_payload_has_three_sections`
to silently report PASS. Audit found 125 of 244 test functions in
the file with the same shape.

A mechanical retrofit applied the helper pattern to all 125
functions. The retrofit then surfaced **five pre-existing latent
defects** that were silently passing on real regressions:

1. `test_coverage_v2_shape` required `len(construct[field]) > 50`
   for the `reference` URL, which is exactly 48 characters.
   Threshold dropped to `> 40` (still catches missing/empty fields,
   accepts the legitimate URL).
2. `test_mcp_voice_carries_classification_confidence_construct`:
   same `> 50` threshold, same URL, same fix.
3. `test_mcp_temporal_carries_distribution_construct`: same.
4. `test_epistemic_candidate_attribution_surfaces_agency_parentheticals`
   used `(Bloomberg survey, July 2026)` to test the E.3 detector,
   but `survey` matches the primary `_SOURCE_RE` so the sentence
   was correctly classified as primary-sourced and excluded from
   the under-detection candidate list. Replaced fixture with
   `(Census BTOS, June 2026)` (the canonical E.3 example named in
   the detector's own docstring).
5. `test_lift_dry_run_gate_10_matches_rewriter_policy` tested two
   gate patterns. The `paused_pat` for `frame.clarethium.com` was
   removed from `lift.py` at the 0.8.8 cleanup; the test was also
   asserting that URL-prefixed forms match the gate, but the
   gate's intentional `/` lookbehind exclusion delegates URL-
   prefixed forms to the rewriter. Rewrote the test to mirror
   what `lift.py` gate 10 actually catches (bare-host occurrences),
   with explicit property pins for the lookbehind exclusions.

Total tests stay at 882; the behavior change is that 125 tests
that silently passed now actually verify what they claim, and the
five latent defects are caught + fixed.

### Documentation cold-read: stale references

- `docs/MCP_SERVER.md` "Exercised contracts": pointed at
  `test_canon_graph_consistency.py` which doesn't exist; the
  canon-graph assertions live in `tests/test_frame_library_index.py`
  and `tests/test_decision_readiness.py`. Reference updated.
- `docs/MCP_SERVER.md` "Tests" section: the bare
  `python3 test_mcp_server.py` invocation was wrong (no test file
  at repo root). Replaced with the pytest invocation; added the
  full-suite invocation alongside.
- `README.md`: bumped test-file count (21 → 25) reflecting the
  four new test files; named the per-module 80% gate and the
  cookbook-recipe contract suite explicitly.

### Branch protection on master

`master` is now protected via `gh api PUT /repos/.../branches/.../
protection`: force-push blocked, branch deletion blocked, linear
history required. Operator (admin) keeps bypass for emergency
recovery (`enforce_admins: false`). No required status checks at
this posture (lightweight for solo development); raise to
PR-required-checks when an external contributor lands.

## [1.0.0] - 2026-05-10

### v1.0 ROADMAP contract: status

The 0.9.x stabilization arc closes.

**Met at v1.0.0:**

- **Strict typing on the public wheel surface.** The seven modules
  (`mcp_server`, `mcp_compose`, `mcp_resources`, `mcp_schema`,
  `framing`, `comparison`, `clarethium_measure`) pass `mypy --strict`
  with zero errors. The strict-blocking matrix job in the PR-time
  quality gate enforces it on every push. Lenient `mypy` and `ruff`
  continue to pass.
- **Adopter-contract test coverage.** `tests/test_cookbook_recipes.py`
  exercises the cookbook claims and the README "Why this and not
  just an LLM" positioning claims against the running API at PR
  time.
- **Conformance driver gate.** `scripts/mcp_conformance_driver.py`
  speaks JSON-RPC over stdio to the freshly-built wheel on every tag
  push and validates every primitive (initialize, tools/list,
  tools/call for `frame_check` and `frame_compare`, resources/list,
  resources/read, prompts/list, prompts/get, ping, error handling).
  30/30 PASS at the v1.0.0 cut.
- **Methodology citation paths.** `CITATION.cff` resolves to the
  Zenodo concept-DOI ([10.5281/zenodo.19888849](https://doi.org/10.5281/zenodo.19888849));
  the methodology canon at `Clarethium/lodestone` is reachable; the
  README detector-F1 number cites a study artifact reproducible from
  corpus + harness.
- **CI-driven publish.** v1.0.0 is the first release cut entirely
  from CI on this repository alone (see "CI-driven publish from
  this repository" below).
- **Engine V4.2 capability decision.** The named-pattern detector
  reports F1 = 0.36 against expert labelers (pre-registered, below
  the 0.4 useful threshold). v1.0 ships the under-detection-marker
  pivot (per README "Approach") as the load-bearing claim rather
  than waiting for the engine to cross threshold. The MCP response
  field `engine_status: "beta"` and the README + ROADMAP statements
  about detector F1 carry the honest position forward.

**Deferred to a tracked v1.0.x follow-up** (ROADMAP carries the
explicit lines):

- **Per-module 80% coverage on the wheel surface.** The 65% global
  production-code floor stays in place. Of the seven modules, three
  are already above target (`mcp_schema` 100.0%, `mcp_compose`
  94.9%, `mcp_resources` 90.3%); four are below
  (`framing` 69.5%, `mcp_server` 69.4%, `clarethium_measure` 62.6%,
  `comparison` 20.9%). The `comparison.py` gap is the largest and
  needs provider-mocked test infrastructure for the
  LLM-network-dependent paths (`generate_gemini`, `generate_grok`,
  `analyze_model`) that does not exist yet.
- **Validation pre-registration first execution.** The behavior-change
  protocol at `validation/wedge_behavior/PROTOCOL_v1.md` exists with
  the runner at `validation/wedge_behavior/run_pilot.py`. The first
  execution with N ≥ 30 documents per condition, the results
  publication under the same directory, and the CHANGELOG narrative
  linking those results, all land in v1.0.x rather than blocking
  the v1.0.0 cut. The contract item is honestly carried forward
  rather than silently treated as met.

### CI-driven publish from this repository

`v1.0.0` is the first release cut entirely from CI on this repository
alone. The `.github/workflows/publish.yml` pipeline (world-state
preflight + build + sigstore attestation + Trusted Publishing OIDC +
GitHub release) runs end-to-end on this tag push.

Five publish-workflow defects are fixed and held — four from the
0.9.x line, and one more surfaced during this cut itself:

1. The tag-vs-pyproject gate skips under `workflow_dispatch` (no
   longer hard-fails on branch refs).
2. The build job has the `attestations: write` permission sigstore
   needs.
3. The TestPyPI routing condition no longer substring-matches `'a'`
   in `master` under `workflow_dispatch`.
4. Every publish/release job is tag-prefix-anchored.
5. Routing uses `github.ref_name` (the bare tag name, e.g. `v1.0.0`)
   instead of `github.ref` (`refs/tags/v1.0.0`) for the `contains()`
   pre-release check. The prior fix at #3 added the
   `startsWith(refs/tags/v)` prefix to gate against branch refs but
   missed that `'a'` is in the literal `'tags/'` segment of every
   tag ref. Surfaced when v1.0.0 routed to TestPyPI instead of
   PyPI on the first cut attempt; fixed and re-tagged at the same
   commit before the release shipped.

### Source-quality cleanups landed in this cut

- All nine open CodeQL alerts cleared. Four false positives were
  dismissed with documented rationale (the lazy `import mcp_resources`
  inside `__getattr__`, the markdown content-substring check in a
  test, the `_SEC_TICKERS_FAIL_AT` writes that CodeQL did not trace
  through the `global` declaration). Four dead-code branches in
  `source_network.py:_match_in_text` (and the wheel-staged copy) were
  deleted; the function-entry guard already covers the case the inner
  branch tested for. One stale alert auto-cleared on re-scan after
  the underlying line had already been fixed.
- `llm_cost.compute_cost_usd` and `llm_client.xai_openai_client`
  upstream of the strict surface get type annotations so the strict
  pass on `comparison.py` does not surface their cascades.

### Note on prior versions

- `0.9.x` ships working capability and stays installable; `0.9.4` is
  the last 0.9.x release before this v1.0 cut. Existing pinned
  installs to `0.9.x` continue to resolve.
- v1.0 commits to no-breaking-change on the wire surface: the MCP
  URI scheme (`frame-check://library`, etc.), `serverInfo.name`,
  tool names (`frame_check`, `frame_compare`), and every JSON
  response field name carry forward unchanged from 0.9.x. Adopter
  code branching on these stays working.

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
