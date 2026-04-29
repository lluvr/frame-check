# Changelog

All notable changes to the Frame Check MCP server are documented here, in reverse chronological order. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [semantic versioning](https://semver.org/).

Release arc per `STRATEGY.md §14`: `0.8.0` (2026-04-27) was the first public PyPI release; `0.8.1` (2026-04-28) republished from the public split repo `lluvr/frame-check-mcp` to fix the dead Project-URL surface that shipped in 0.8.0 (see [0.8.1] notes below). `1.0.0` is the API-freeze line adopting the v2 construct-carrying shape per `MCP_CONTRACT_V2_PROPOSAL.md`. Versions prior to `0.8.0` were internal (not on PyPI); `SERVER_VERSION` in `mcp_server.py` matches the released wheel and is reported to clients on the MCP `initialize` handshake.

The earlier plan for a `0.7.1` V1-only name-reservation release on PyPI was retired 2026-04-23 in favor of V4.2-first launch discipline; see `MCP_SERVER.md` "Release arc" for the canonical commitment.

## [Unreleased]

### Public-repo completeness

- `.github/` directory now ships to the public repository at `lluvr/frame-check-mcp`. Three GitHub Actions workflows that already existed in the upstream tree (`tests.yml` for pytest on PR + push, `publish.yml` for build + smoke-test on tag with PyPI publish steps commented out for safety, `dco-check.yml` for Developer Certificate of Origin verification on every PR) now visibly demonstrate the project's engineering rigor on every PR. Issue templates (`bug_report`, `feature_request`, `frame_proposal`) and the PR template ship alongside, closing the dead `.github/ISSUE_TEMPLATE/` reference in `SECURITY.md`. Fixed in `extract_public_repo.py` `INCLUDE_DIRS`.

- Audit deliverables now ship to the public repository: `LEAKAGE_AUDIT_v1.md` (16 pre-publish leakage findings, 14 closed + 2 partial), `REMEDIATION_LOG_v1.md` (the per-finding remediation record), and `PUBLISH_READINESS_VERDICT_v1.md` (the campaign synthesis verdict). `SECURITY.md` references these as "verify the audit yourself" reproducibility artifacts; previously they existed in the upstream private tree only, so the references were dead. The deliverables ship to the public repo root and are NOT bundled in the wheel (the wheel `gate-8 audit-doc check` enforces that). Aligns with the existing self-disclosure pattern (`V4_2_GAP_INVENTORY_v1.md` and `MCP_CLIENT_CONFORMANCE_v1.md` already shipped publicly under the same evidence discipline).

### Tool interface

- Tool descriptions for `frame_check` and `frame_compare` rewritten to lead with WHEN to use the tool, not just WHAT it returns. The new descriptions name the use case ("Use this when the user pastes a document and asks for a structural read"), surface the zero-arg invocation shape (`frame_check(document_text=<text>)` works for any English analytical document), and reserve the "what it returns" detail for a second paragraph. The previous descriptions opened with "Returns analysis (measurements) + agent_guidance + provenance," which told the agent the output shape but not the use case.

- Per-parameter descriptions rewritten to lead with the trigger condition. `include_divergence` now opens with "Default true. You do not need to pass this," so an agent reading the schema does not defensively pass `include_divergence=true` (the most common cause of the parameter being specified despite the default already being correct since 0.8.0). `source_text`, `user_context`, and `user_goal` now lead with "Pass when ..." so the agent knows the trigger condition (the user provided source material; the user stated a decision context; the user named a goal), not just the field shape.

- Three maintainer-internal parameters removed from the agent-facing schema: `prefer_contract_version` (coverage v1/v2 migration window), `catalog_version_pin` (stability pin for advanced integrators), and `domain_hint` (echo-only with no field-level filtering). These are not decisions an agent should be making per call; they pollute the agent's decision space without adding value. Backward compatible: the dispatch layer still accepts all three when passed explicitly, so an integrator who pinned the older surface is not broken.

- New `instructions` field on the MCP InitializeResult (top-level, per the MCP protocol). Carries server-orientation prose to the agent: when to use Frame Check, the default invocation shape, the four-prompt workflow surface (`frame_check_my_response`, `frame_check_this_ai_response`, `challenge_document`, `explain_framing`). The previous handshake returned only `protocolVersion`, `capabilities`, and `serverInfo`; the missing orientation field meant the agent had to read every per-tool description to learn the workflow shape. Three new regression tests pin the field's presence and content.

### Output usability

- FVS frame references in `frame_check` and `frame_compare` responses now carry a `library_url` field pointing at the entry's markdown source on the public GitHub repository (`github.com/lluvr/frame-check-mcp/blob/master/data/frame_library/...`). End-users in MCP clients (Claude Desktop, Cursor) cannot click `frame-check://library/...` resource URIs because those are MCP-internal; the new field gives them an HTTP link they can follow. Applies to `analysis.frame_library_matches[]`, `divergence.absent_frames[]`, and the `typical_co_fires` / `typical_co_absences` entries inside each absent frame's `corpus_context`. The previous-form `library_url` (which pointed at `frame.clarethium.com/corpus/library/FVS-XXX.html`) was the paused production URL; the new GitHub URL is always resolvable regardless of hosting state. The same change updates `decision_readiness.library_entry_ref` so canon-graph references in the decision-readiness profile and aggregate findings carry the same GitHub URL form.

- `agent_guidance.how_to_cite_frame_matches` now mandates rendering FVS references as markdown links: `[FVS-XXX Frame Title](library_url)`. Previously the guidance instructed agents to render plain-text "FVS-XXX" references that the user could not follow. The four MCP prompts (`frame_check_my_response`, `frame_check_this_ai_response`, `challenge_document`, `explain_framing`) carry the same updated citation form so the discipline is uniform across surfaces.

- New `agent_guidance.suggested_next_actions` block carries 2-4 specific next-action entries derived from the call's structural findings. Each entry is structural-finding-anchored (the highest-signal absent frame's library entry, a hedge-by-claim reprompt when the unhedged-claim rate exceeds 50 percent, an attribution reprompt when sourced sentences fall below 10 percent, and an always-included pointer to the `challenge_document` MCP prompt for the deeper multi-turn loop). The block exists so a Frame Check finding has a discoverable path forward instead of a static reading; previously the tool surfaced findings without telling the user what to do about them, and the four MCP prompts were invisible to anyone not reading `prompts/list`. Capped at 4 entries; survives `compose_budget` compression so compact callers still get the discovery loop.

- `agent_guidance.how_to_render_suggested_next_actions` carries the rendering instruction so the agent knows to surface the actions as a small explicit list at the end of the response, with action_text rendered verbatim (the embedded markdown link in resource-kind entries preserved, the quoted reprompt question rendered as-is, the prompt name surfaced for prompt_followup discoverability).

### Security

- Prompt-injection protection now covers all four LLM-backed endpoints. The optional AI-narrative path (Grok), the reframe endpoint, the cross-model topic generator, and the consensus verifier previously interpolated user-supplied document text into model prompts with no isolation, so a document containing the substring `</user_document>` could terminate the prompt's data block early and have its trailing content read as instructions. The new `prompt_safety` module centralizes a sentinel-wrap-and-reject pattern that every LLM-backed endpoint now applies before any model client is constructed, so hostile input never reaches the network. Pinned by 14 new tests covering the primitives, per-endpoint pre-LLM rejection via a patched client, and consensus claim-skip behavior.

### Provenance

- Every `frame_check` and `frame_compare` response now carries `production_status` and `production_status_note` in the `provenance` block. The hosted site `frame.clarethium.com` was paused 2026-04-23 with resume as the default trajectory; the URLs in `provenance` (tool URL, methodology, frame library, calibration corpus) point at the canonical addresses but may not currently resolve. The new fields let MCP clients distinguish "URL canonicalized but currently paused" from "URL malformed or wrong." The active artifacts during the pause are the GitHub repository (`lluvr/frame-check-mcp`) and the PyPI package (`frame-check-mcp`), both named in the note.

### Documentation

- `MCP_SERVER.md` Citation block now points at the GitHub repository instead of the paused production site. The published wheel previously rendered the citation as "Lucic, L. (YEAR). Frame Check ... verification in documents. (production paused)" because the extract pipeline rewrote the bare production URL inside the citation code block. The new form (`https://github.com/lluvr/frame-check-mcp`) matches `CITATION.cff` and survives the extract pipeline cleanly.

- `FRAME_DIVERGENCE_CONTRACT_v1.md` corrects two contract specification contradictions: §2.2 and §7.1 listed `include_divergence` default as `false`, but §3.1 and the shipped server behavior since 0.8.0 are `true`. All three sections now agree. §8.5 release-state language updated to reflect the 0.8.0 / 0.8.1 / 0.8.2 PyPI publish history.

- `STRATEGY.md` PL1 row replaces previously-pinned test counts (which had decayed past accuracy) with a construct-honest description: approximately 906 test functions across 59 files; precise pass count requires running `python3 run_tests.py`.

- `README.md` clarifies repository scope: the PyPI MCP install is the primary path; the Flask web app in this repository is repository-only and is not bundled in the wheel.

### Notes for contributors

- `prompt_safety` deliberately re-exports the V4.2 markers rather than importing from the V4.2 engine, because the V4.2 engine is dev-tree-only and cannot be imported from the wheel. A test pins byte-equivalence between the two copies in environments where both are importable. The module is added to `pyproject.toml` `py-modules` and to `scripts/extract_public_repo.py` `INCLUDE_FILES` so it ships in the wheel.

- Internal vault references previously embedded in `FRAME_DIVERGENCE_v1.md` and `FRAME_DIVERGENCE_CONTRACT_v1.md` status headers are removed; `lift_dry_run.py` step 8 now reports zero vault references against a fresh wheel build.

- `scripts/lift_dry_run.py` gate 10 (wheel-content scan) regex aligned with the `extract_public_repo.py` rewriter's exclusion policy. Both now share the same `(?<![@\w`/])` lookbehind that excludes email addresses, word-character concatenations, backtick-protected code-span text mentions, and path-internal slashes. Without this alignment, the gate would flag references the rewriter intentionally preserves (a doc section that explains "the previous form was `frame.clarethium.com/corpus/library/...`" is intentional documentation surrounded by backticks; the rewriter leaves it alone, and the gate now does too). Pinned by a regression test in `test_mcp_server.py` that verifies the gate's regex behavior matches the rewriter's exclusion contexts.

- Verified locally pre-commit: lift_dry_run gates 1-8 + 10-11 pass with versions temporarily aligned at 0.8.3 (gate 9 Project-URL HEAD checks pass against the extract-rewritten public-tree pyproject and are expected to fail on the dev tree by design); 247 targeted tests across `test_mcp_server` and `test_prompt_safety` pass; em-dash and smart-quote scan clean on all session-touched files.

### MCP wire-payload weight reduction (2026-04-28)

- **`compose_budget="standard"` now compresses `agent_guidance` to load-bearing prescriptions** (essence-preserving: every load-bearing rule preserved verbatim). Prior to this change, the `standard` tier was effectively `full` for `agent_guidance`: it only trimmed divergence-side output volume (top-5 absent_frames) but left the 31 KB guidance block untouched. Standard now applies the same compression that `minimal` uses, while keeping standard's divergence-side semantics (all clusters, all patterns; top-5 absent_frames). Measured on a 6-sentence document: agent_guidance 31,487 -> 11,917 bytes (62 percent reduction), total wire payload 83,127 -> 50,401 bytes (39 percent reduction). The compression drops the inline `claim_level_treatments` table, worked examples in `composition_discipline`, and `how_to_map_user_intent` from the wire; load-bearing rules (Frame Check naming, reading-form-not-verdict-form, dual-use anti-misuse, self-audit rule, citation discipline) are preserved verbatim. The compressed shape carries a `claim_level_treatments_note` and an updated `compose_budget_applied_note` pointing callers to `compose_budget="full"` for the inline table; the table is identical across calls so an agent can fetch once at full and cache for subsequent compressed-tier calls.

- **Default `compose_budget="full"` is unchanged**: existing integrators omitting the parameter continue to receive the verbose guidance with all worked examples and the full L5 claim-level table inline. Standard becomes the recommended tier for production agent loops; minimal stays the recommendation for tight per-turn loops where divergence-side cluster/pattern surfaces are also acceptable cuts. The default-flip decision (standard vs full) is queued for operator review as a public-contract change requiring a SERVER_VERSION minor bump.

- **Tool-schema description updated** so MCP clients surface the corrected per-tier semantics (`mcp_server.py` `frame_check` tool definition).

- **Polish: trust-posture cleanup.** The compressed-tier notes had inherited a pre-existing reference to `frame-check://docs/claim_levels` and `frame-check://docs/composition_discipline` (commit `2e9ede3b`), but neither URI is served via `_list_resources()`; the wire payload was promising agents a 404-able resource. Both notes now describe the architectural pattern in plain language without the broken URI claim. The `claim_level_treatments_uri` field is renamed to `claim_level_treatments_note` to match its now-accurate value shape (no URI). The internal compression helper is renamed `_compress_agent_guidance_minimal` -> `_compress_agent_guidance_to_load_bearing` to reflect that both `standard` and `minimal` route through it.

- **Regression tests pinned**: `test_compose_budget_standard_compresses_agent_guidance` asserts (a) standard agent_guidance is at least 1.5x smaller than full, (b) standard and minimal share agent_guidance key shape (same compression rules), (c) `compose_budget_applied_note` reports `standard` AND does not promise a `frame-check://` URI, (d) load-bearing rules survive (Frame Check named, reading-form preserved, dual-use note kept, self-audit rule kept), (e) standard divergence-side preserves all clusters and all frame_patterns (only minimal cuts those). `test_compose_budget_minimal_compresses_agent_guidance` updated for the renamed `claim_level_treatments_note` field and gains an explicit "no `frame-check://` URI promised" assertion plus a "points at `compose_budget='full'`" assertion. Full test suite: 49/49 suites pass; quality driver: 38/39 (unchanged from baseline; the single FAIL is the parked D3 teaching_questions gap covered by `KNOWN_HARNESS_GAPS`).

### Methodology + audit increments (2026-04-28)

- **SUBSTRATE_PARALLEL_AUDIT_v1.md (new)**: closes recommended next move #1 from the v1.1 LLM-judge audit. Runs the deterministic regex/structural substrate detection (construct #7: `framing.py` analyzers + `frame_library.py::suggest_frames` rules; the actually-shipping detection layer in the 0.8.1 PyPI wheel) against the same mg_v1 + mg_v2 corpora and same 4-family panel as the V4.2 LLM-judge audit. **Headline (apples-to-apples 8-frame, FVS-001 excluded on both sides since substrate retires it):** substrate macro-F1 = 0.222 (mg_v1) / 0.211 (mg_v2) against the same panel that V4.2 LLM-judge scored 0.511 / 0.761 against (8-frame, run-pair avg). The 0.29 / 0.55 gap quantifies the V4.2 architectural transition's value-add on a denominator-matched comparison; the canonical 9-frame V4.2 macro-F1 from F-2026-034 / F-2026-035 (0.510 / 0.732) is reported with FVS-001 contributing f1=0.500, while the substrate 9-frame macro under FVS-001=0 is 0.198 / 0.188, so the 9-frame gap (~0.31 / ~0.54) is also constructively unfair (mixed denominators). The 8-frame number is the construct-honest gap; the F-V4-2 threshold (0.40) is set for the V4.2 LLM-judge architecture and not directly comparable to a structural-signal layer. **Per-frame substrate classification:** 5 of 9 frames have ZERO TPs across both corpora (FVS-001 RETIRED in substrate; FVS-002 + FVS-007 STRUCTURAL_BLIND because constructs are semantic; FVS-014 STRUCTURAL_THRESHOLD_TOO_STRICT + STRUCTURAL_RULE_GAP because the rule has no present-anchor path despite present being the dominant tense in 3 of 4 spot-checked panel-positive docs; FVS-015 STRUCTURAL_THRESHOLD_TOO_STRICT). FVS-011 is the strongest substrate frame (mg_v2 f1 = 0.61); FVS-008 (mg_v2 f1 = 0.55, perfect precision) and FVS-009 / FVS-012 (high precision, low recall) are partial detectors. Substrate's 0.8.1-shipping value is the framing portrait + teaching questions + library cross-references, NOT panel-aligned per-frame binary verdicts; the architectural staging in `METHODOLOGY.md` and `METHODOLOGY_PAPER_v2_6a_TRACK_A_REVISITED_v1.md` §6a.6 has always declared this. **Recommended next moves**: (a) substrate calibration v1 (FVS-014 dominant-anchor rule + threshold drop, FVS-009 conjunction relaxation, FVS-015 conjunction simplification, FVS-012 threshold relaxation; each with adversarial fixture coverage) -- highest leverage; (b) F-2026-035 outcome-body clarification distinguishing evaluation construct from shipping construct -- low cost; (c) operator decision on whether to ship a parallel substrate-honest-limits surface on the wheel README or MCP tool description. Files: `SUBSTRATE_PARALLEL_AUDIT_v1.md` (synthesis doc), `scripts/audit_substrate_parallel.py` (deterministic per-doc per-frame fire matrix script, zero API calls, runs `framing.py` analyzers + `frame_library.py::suggest_frames` against corpus + panel labels), `fvs_eval/v4/substrate_parallel_audit.md` (auto-generated per-frame fire-pattern dump for hand-classification), `fvs_eval/v4/substrate_parallel_audit.json` (machine-readable summary).

- **TP_RATIONALE_PATTERN_AUDIT_v1.md (v1.1)**: stress-test pass on the v1 audit shipped 2026-04-27 surfaced two real defects + one understatement, all closed in v1.1.
  - **Numbers fix in §1**: FVS-007 row used run-pair averages (FP=7.5, 9.5; precision 0.118, 0.174) while every other frame in the same table used union-across-runs counts (matching `audit_tp_rationale_patterns.py` script output and §2 cross-frame summary). Replaced with union counts (FP=9, 11; precision 0.100, 0.154) for uniform metric. Ship-readiness doc §1 retains run-pair averages by methodological declaration; the two views are reconcilable but should not be mixed in one table.
  - **Retraction of §5 caveat #5**: v1 asserted panel labels store binary `exhibits` fields without rationales. **This was factually wrong.** Panel labels in `*_new_library_v{3,4}.json` actually store `{'exhibits': bool, 'reasoning': str}` cells. v1.1 retracts the caveat and ships a panel-rationale parallel audit.
  - **Counterfactual macro-F1 added to §3.1**: removing FVS-007 + FVS-001 from the macro RAISES the macro on every cell on both corpora (mg_v1 0.58 -> 0.64; mg_v2 0.73 -> 0.83). The two confused frames DRAG macro down, not inflate it. v1's "macro is intact at macro level" framing was understated; v1.1 sharpens to "library_v5 fixes likely shift macro UP toward upper edge of 0.65-0.75 band, not collapse out of it".

- **panel_rationale_pattern_audit.md + scripts/audit_panel_rationale_patterns.py (new)**: deterministic per-frame panel rationale dump for all 9 default-mode frames across mg_v1 + mg_v2. Zero API spend; reads `*_new_library_v{3,4}.json` reasoning fields. Closes the v1 audit's central not-verified caveat. **Headline panel-level findings:**
  - **FVS-007 panel co-confusion confirmed**: 3 of 4 panel families (Gemini, Grok-panel, GPT) consistently apply the substrate-confused failure-of-subject reading; only Claude consistently applies the library-construct failure-of-self reading. The 2 mg_v2 panel TPs (mg2_33_nadelson, mg2_43_cirincione) achieve 3-of-4 consensus via co-confusion of the 3 permissive families, not via panel-correct convergence. Strengthens the prediction that library_v5 disambiguation will shift both detector AND panel emissions on those docs.
  - **FVS-001 panel-direction misapplication**: ALL 4 panel families misapply the construct, in two opposite directions. Engine + Grok-panel apply strict session-wise reading and reject all single-turn docs. Claude / Gemini / GPT extend "iterative refinement" to within-document elaboration (multi-example single-thesis structure). Neither matches the library Identification text precisely; both miss Branch A's static-document coverage-imbalance criterion. Library_v5 fold-in of Branch A is the structural resolution.
  - **Other 7 frames CONSTRUCT_CORRECT verdicts confirmed at panel level**: panel families converge on intended construct (FVS-009 vulnerability-coverage; FVS-002 polish-vs-substance; FVS-014 dominant-vs-balanced temporal anchoring with Claude-strict-vs-rest-permissive threshold latitude); disagreements reflect threshold latitude, not substrate-level criterion misapplication.

- **FVS_007_001_SHIP_READINESS_v1.md disclosure draft voice fix (§2.4 + §3.4)**: existing engine `HONEST_LIMIT_DISCLOSURES` entries (FVS-002 / FVS-004 / FVS-010 / FVS-016 at `fvs_eval/v4/v4_2_engine.py:204-262`) follow a uniform second-clause structure ("Step 4 cross-family AC1 = X.XXX"). The 2026-04-27 v1 drafts substituted cross-corpus emission-rate language, creating apparent voice divergence. Updated drafts now lead with intra-rater AC1 -> Step 4 cross-family AC1 (FVS-007 = 0.42 moderate, FVS-001 = 0.62 moderate, per `library_v4_reliability.json`) -> panel-rationale construct decomposition -> cross-corpus emission rate as supplemental evidence -> operator guidance. Voice now parallels the existing template.

- **FVS_007_001_SHIP_READINESS_v1.md §5 caveat #3 update**: "CLOSED 2026-04-27 by TP_RATIONALE_PATTERN_AUDIT_v1.md" extended to "EXTENDED 2026-04-28 by panel-rationale parallel audit (audit doc v1.1)" with three nuance points: (a) FVS-007 substrate confusion is NOT detector-only; (b) FVS-001 panel application is itself misapplied, in different direction from engine; (c) other 7 frames CONSTRUCT_CORRECT verdicts confirmed at panel level. Recommendation unchanged (disclosure now + library-fix at v5).

## [0.8.2] - 2026-04-28

### Distribution: in-content link rewriter + lift_dry_run step 10 (2026-04-28)

- **0.8.2 closes the second class of dead-link defect surfaced by fresh-eyes stress test on the 0.8.1 wheel.** The 0.8.1 wheel METADATA Project-URLs were correct (Path A.1 fix in 0.8.1), but the wheel-bundled markdown content carried roughly 400 hyperlinks to `lluvr/frame-check` (private repo, 404 to non-collaborator visitors) and 460 to `frame.clarethium.com` (production paused 2026-04-23). Every FVS frame library entry, every worked example, MCP_SERVER, METHODOLOGY, and FRAME_DIVERGENCE v1/v2 doc each had 6 to 18 dead hyperlinks. `lift_dry_run.py` step 9 missed the defect because step 9 only checks Project-URLs in METADATA, not embedded link surface. No functional code changes from 0.8.1; the deployment-affecting deltas are bundled markdown content + bumped `SERVER_VERSION = "0.8.2"`.

- **`scripts/extract_public_repo.py` grows `rewrite_content_links()`** (commit `5a5df3e`). Walks every `.md` / `.txt` in the destination tree and applies four rewrites between pyproject rewrite and README write:
  - Markdown link `[label](url)` where `url` points at the private repo: rewrite to the new public repo URL if the linked path exists in dest, else drop the link wrapper and keep `label` as plain text.
  - Markdown link where `url` points at `frame.clarethium.com`: drop the link wrapper, keep `label`.
  - Bare `https://github.com/lluvr/frame-check-mcp/...` URLs: same path-existence rule; non-existent paths replaced with `(see upstream development tree)`.
  - Bare `(production paused)...` URLs: replaced with `(production paused)`.

  Schemeless forms (`github.com/...`, `frame.clarethium.com/...`) handled with a negative lookbehind that excludes email `@`, word chars, code-span backtick, and path-internal slash so textual mentions inside code blocks and email addresses (`curator@frame.clarethium.com`) are left intact. Trailing sentence punctuation stripped from the URL match before substitution and reattached after. Tested on full upstream tree to v2 extract: 1269 private refs + 1455 production refs reduced to 0 + 0; 1764 refs rewritten, 1539 stripped. Default `--new-version` bumped to `0.8.2`.

- **`scripts/lift_dry_run.py` grows step 10 of 10: wheel content scan** (commit `5a5df3e`). Iterates every `.md` / `.txt` member of the built wheel and scans for `github.com/lluvr/frame-check` (without `-mcp` suffix) or `frame.clarethium.com`. Returns the violating files + hit counts and FAILS the dry-run, naming `extract_public_repo.py` as the source of the rewrite that closes the leak. Bypassed with `--skip-content` for staged-release scenarios. The defect that shipped in 0.8.0 + 0.8.1 cannot recur silently.

- **Lift sequence executed 2026-04-28** (this upstream is source-of-truth; public lift on `lluvr/frame-check-mcp`):
  - Fresh extract of upstream HEAD to public split tree under `/tmp/frame-check-mcp-public/`.
  - `lift_dry_run.py` 10/10 GREEN (208 → 210 files due to symlink resolution after content edits, 0 leaks, 0 vault refs, 0 audit-doc accidents bundled, `twine check --strict` PASSES, 32/32 conformance, URL surface 6/6, content scan 106 markdown/text files clean).
  - Public commit `ac596da` ("Cut v0.8.2 release") + annotated tag `v0.8.2` pushed to `lluvr/frame-check-mcp`; package live at `https://pypi.org/project/frame-check-mcp/0.8.2/`.
  - `mcp_server.py` `SERVER_VERSION = "0.8.2"`; `pyproject.toml` bumped from `0.8.2.dev0` to `0.8.3.dev0` for next dev cycle.
  - This upstream commit (`67ea167`) mirrors the cut so the audit trail stays aligned across both repos.

- **Two-repo discipline reinforced.** Step 10 enforces that wheel-bundled content cannot leak private-repo or paused-domain hyperlinks at lift time; the gate is bypassable only with explicit `--skip-content`. Future releases will re-run extract + lift_dry_run from upstream HEAD.

## [0.8.1] - 2026-04-28

### Distribution: Path A.1 split-repo migration (2026-04-28)

- **0.8.1 republishes 0.8.0's wheel functionality from a public source repo.** The 0.8.0 lift on 2026-04-27 shipped from a upstream development tree (`lluvr/frame-check`); the resulting PyPI sidebar carried seven dead Project-URLs (five `lluvr/frame-check` 404s for non-collaborator visitors, two paused `frame.clarethium.com` endpoints) plus roughly ten more dead blob-path links in the rendered README. `REPO_STRATEGY_DECISION_v1.md` v1.1 records the operator's 2026-04-28 choice of Path A.1 (split repo, conservative): create a public `lluvr/frame-check-mcp` containing only the wheel-bundled subset, ship 0.8.1 from there, leave the upstream private. The new repo is live; all six 0.8.1 Project-URLs (Repository, Issues, Changelog, Security, Methodology, Frame Library) return HTTP 200; the Homepage URL is intentionally omitted from 0.8.1's pyproject because `frame.clarethium.com` is paused (production resume / retire decision is downstream of Path A.1). No functional code changes from 0.8.0; the only deployment-affecting deltas are pyproject Project-URLs + README link surface + bumped `SERVER_VERSION = "0.8.1"`.

- **`scripts/extract_public_repo.py`** (commit `57c8afe`): click-to-execute extractor for the wheel-bundled subset. Enumerates 95 `INCLUDE_FILES` + 5 `INCLUDE_DIRS`, mirrors `setup.py`'s `_should_skip` exclusion logic at the repo level, rewrites `pyproject.toml` Project-URLs and version, syncs `mcp_server.SERVER_VERSION` and `scripts/mcp_conformance_driver.py`'s hardcoded version assertion, generates a clean public README without the dead-link surface, runs `lift_dry_run.py` against the new tree to verify GREEN. Reproducible: any future release of the public split is a single `python3 scripts/extract_public_repo.py` from upstream.

- **`scripts/lift_dry_run.py` step 9 of 9** (commit `09c7f30`): URL surface check via HEAD with GET fallback, catches dead Project-URLs in wheel METADATA before `twine upload`. The defect that shipped in 0.8.0 cannot recur silently. Skip with `--skip-urls` for staging cases where the public repo isn't pushed yet. Verified: identifies all 7 of 7 broken URLs in the 0.8.0 metadata; passes 6 of 6 against the new 0.8.1 metadata.

- **Lift sequence executed 2026-04-28** (this upstream is source-of-truth):
  - Public repo created at `https://github.com/lluvr/frame-check-mcp` (maintainer-side).
  - `extract_public_repo.py` produced 105-INCLUDE + recursive contents = 503 git-tracked files at `/tmp/frame-check-mcp-public/`.
  - Initial commit `55c712f` (DCO sign-off, author `Lovro Lucic <lovro.lucic@gmail.com>`) pushed to `lluvr/frame-check-mcp:master`.
  - `lift_dry_run.py` 9/9 GREEN (208-file wheel, 0 leaks, 0 vault refs, 0 audit-doc accidents, twine check --strict PASSES, 32/32 conformance, URL surface check 6/6 GREEN, the first time step 9 has executed against a real public source).
  - `twine upload --repository testpypi` returned 403 (token PyPI-prod-scoped, same as 0.8.0 lift); fell through to direct PyPI per the 0.8.0 path.
  - `twine upload dist/frame_check_mcp-0.8.1-py3-none-any.whl` succeeded; package live at `https://pypi.org/project/frame-check-mcp/0.8.1/`.
  - End-to-end verify: clean install via `pip install --target ... --no-cache-dir frame-check-mcp==0.8.1`; `SERVER_VERSION == "0.8.1"`; all 6 Project-URLs in installed METADATA point at `lluvr/frame-check-mcp`.
  - `cut_release.py` ran in public tree; produced commit `97496a0` ("Cut v0.8.1 release") + annotated tag `v0.8.1`; pushed both to `lluvr/frame-check-mcp`.
  - This upstream commit mirrors the cut (CHANGELOG cut + pyproject bump + tag) so the audit trail stays aligned across both repos.

- **Two-repo discipline now in force.** Wheel-relevant source changes land in upstream private repo first, then re-extract via `scripts/extract_public_repo.py` and push to public. The public repo is a frozen projection, never the editing surface. Strategic vault, web app, Tier-A research, audit chain, full FVS library v1+v2+v3+v4, methodology paper, claim A protocol + sealed Phase 1 outputs all stay private.

- **Outreach unblocks.** `MCP_INTEGRATOR_OUTREACH_v1.md` Templates 1-3 are no longer blocked by the dead-URL surface: the deployed PyPI artifact at https://pypi.org/project/frame-check-mcp/ is now 0.8.1 with all six Project-URLs resolving. The remaining gates for Cline outreach are maintainer-side (GitHub Release page authored, channel chosen, contact field populated).

### Methodology + audit increments (2026-04-27)

- **F-2026-035**: V4.2-stage F-V4-2 measurement on `mixed_genre_v2` (n=26). Run-pair-averaged macro-F1 = **0.732** (include-self 3-of-4 fast-tier panel consensus, primary metric); +0.332 above the 0.40 F-V4-2 threshold; bootstrap CI lower bound 0.581-0.607 across all four cells, sitting 0.18-0.21 above threshold. Discharges F-V4-2 under V4.2 LLM-judge architecture; supersedes F-2026-030 (V4.1 rule-based, macro-F1 = 0.215, FAILED) per the V4.1 -> V4.2 architectural staging that F-2026-030's outcome body named "(future) LLM-judge augmentation" alongside honest_limit #4 path (c) library taxonomy revision. The 3.4x improvement is bundled (V4.1->V4.2 detector + SOTA->fast-tier panel + library_v3->library_v4), NOT a clean detector ablation. Cross-corpus picture under V4.2: mg_v1 (F-2026-034) = 0.510, mg_v2 (F-2026-035) = 0.732; the expected generalization penalty does NOT manifest. Most parsimonious reading: V4.2 macro-F1 sits in 0.65-0.75 band on both corpora; mg_v1 n=15 was variance-dominated. Per-frame profile replicates cross-corpus: FVS-007 over-fire (precision 0.125 -> 0.167) and FVS-001 low-recall (0.333 both corpora) confirmed as engine-level behaviors; FVS-015's mg_v1 zero was n=1 noise (resolves to clean 0.714 on mg_v2). Files: `data/falsifications/F-2026-035.md`, `data/falsifications/F-2026-030.md` (revised + superseded_by F-035 + V4.1 historical record preserved), `fvs_eval/v4/measure_v4_2_macro_f1_mg_v2.py`, `fvs_eval/v4/v4_2_macro_f1_mg_v2_results.json`, `fvs_eval/mixed_genre_v2/labels/claude_haiku_4_5_new_library_v4.json` (Haiku 4.5 panel completion at library_v4, ~$0.50 API spend). Run-pair intra-rater variance collapses at n=26 (0.001 swing on include-self vs 0.134 on mg_v1 n=15); F-2026-034 honest_limit #2 and #7 (run-pair averaging discipline) remain correct as principle but empirically less load-bearing once corpus absorbs single-cell flips.

- **METHODOLOGY_PAPER_v2_6a_TRACK_A_REVISITED_v1.md (v2)**: §6a draft extended same-day to fold in F-2026-035 mg_v2 V4.2-stage discharge (§6a.5 generalization gate, §6a.6 architectural transition framing, §6a.7 expanded "what this discharges" subsection). Both anchors (F-034 mg_v1 PASS at 0.510, F-035 mg_v2 PASS at 0.732) now in scope; the paper's V4.2 claim can scope to "clears the F-V4-1 macro gate on the design corpus AND the F-V4-2 macro gate on the fresh corpus under construct-honest measurement amendment discipline." Curator-gated for METHODOLOGY_PAPER_OUTLINE_v2.md §6a integration.

- **CONSTRUCT_VALIDITY_AUDIT_v1.md (v1.1)**: adds construct #13 (V4.2 LLM-judge FVS detection, engine surface at `fvs_eval/v4/v4_2_engine.py`); surfaces an L5 framework gap that the new construct exposes (V4.2 emissions are LLM-judged binary classifications without confidence scores or runner-up alternatives, fitting none of the four existing claim levels cleanly); proposes two resolution paths (Proposal A: fifth claim level `llm_classifier_output`; Proposal B: broaden `classifier_output` with a per-pattern split). v1.1 names the gap and defers the resolution to operator decision per the audit's "version increments when claim_level changes" discipline; v1.2 will be the version that resolves. Construct count for paper §4 spine: 12 -> 13. The 0.8.0 MCP wheel (just published 2026-04-27, commit 1d0c542) ships the deterministic substrate's regex-based FVS detection (construct #7), NOT V4.2 LLM-judge; V4.2 is evaluation-only as of 2026-04-27. Cross-references: F-2026-034 + F-2026-035 (construct #13 reliability evidence on both corpora), `fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md` (per-FVS-frame sibling document covering the orthogonal "do judges describe the same thing when they agree on the label?" question), `METHODOLOGY_PAPER_v2_6a_TRACK_A_REVISITED_v1.md` (paper §6a draft anticipates the construct addition).

- **METHODOLOGY_PAPER_v2_FIGURES_v1.md (new)**: drafts the four v2 NEW or revised paper figures (F1 L5 framework table; F6 per-level cascade trace using instruction_without_troubleshooting fixture pre/post-tightening; F7 13-by-5 construct-validity matrix; F8 adversarial fixture diagnosis schema). All four figures rendered as paper-ready markdown tables / structured text suitable for review and future PNG/SVG conversion. F2-F5 unchanged-from-v1 figures not drafted here. F1 footer surfaces the L5 framework gap (construct #13) as load-bearing. F7 documents 6 of 65 cells with ⚠ marks (4 open with named resolution paths, 2 mixed ✓+⚠); 59 cells fully ✓ or (✓). F8 includes the 3-rule discipline + fixture-suite state table (paper-submission-readiness MET at 5 fixtures + 1 dual-purpose; paper-revision-readiness 7/10 closed as of 2026-04-27). METHODOLOGY_PAPER_OUTLINE_v2.md §3 ("Key figures") cross-references each. Curator-gated for paper inclusion.

- **TP_RATIONALE_PATTERN_AUDIT_v1.md (new)**: cross-frame audit closing the FVS_007_001_SHIP_READINESS_v1.md §3 not-verified-gap #3 (does the substrate-confusion failure mode generalize beyond FVS-007 + FVS-001?). Hand-classification across all 9 default-mode frames using engine rationales for every TP, FP, and FN doc on mg_v1 (n=15) + mg_v2 (n=26) include-self 3-of-4 cells. **Headline finding: substrate-confusion failure mode is ISOLATED to FVS-007 (LEXICAL_CAPTURE) and FVS-001 (PROCESS_NARRATIVE_MISAPPLY).** The other 7 default-mode frames (FVS-002, 008, 009, 011, 012, 014, 015) classify as CONSTRUCT_CORRECT: TP rationales cite distinguishing criteria aligned with the library Identification's intended construct; detector-panel disagreements reflect judgment latitude on borderline cases (precision range 0.54-0.875), not substrate-level criterion misapplication. **Implication for F-2026-035 PASS reading**: macro-F1 = 0.732 is NOT a panel-detector co-confusion artifact at the macro level; 7 of 9 frames apply construct-correct criteria. The methodology paper §6a "V4.2 macro-F1 sits in 0.65-0.75 band on both corpora" claim remains supported. A library_v5 fix on FVS-007 + FVS-001 will shift those two frames' f1 (FVS-007 likely down because current TPs are mostly failure-of-subject docs that panel happened to call yes on lexical match; FVS-001 likely up as Branch A criterion lifts recall) but the 7 unaffected frames' contribution is intact. **Implication for ship-readiness scope**: stops at FVS-007 + FVS-001; no additional frames need parallel substrate-confusion treatment. One residual question surfaced: FVS-014 high-prevalence (31 TPs / 41 docs = 76% positive rate) might mask LEXICAL_CAPTURE on temporal markers vs reflect ubiquity of temporal anchoring as organizing principle. Target-scope check recommended at low cost. 7 explicit "what I have NOT verified" entries scope inference vs measurement (single-classifier reliability, FVS-014 ambiguity, run-pair flips not classified as separate axis, inter-corpus stability, no panel-rationale audit, internal-coherence vs construct-validity distinction, V4.2-only scope NOT extended to deterministic substrate). 3 next-move recommendations: FVS-014 disambiguation (default YES), stub disclosures for FVS-011 + FVS-012 (default borderline), substrate parallel audit (default YES if symmetry wanted). Files: `TP_RATIONALE_PATTERN_AUDIT_v1.md` (synthesis doc), `scripts/audit_tp_rationale_patterns.py` (deterministic audit script, zero API calls, generalizes the per-frame mis-fire enumeration to all 9 default-mode frames), `fvs_eval/v4/tp_rationale_pattern_audit.md` (auto-generated per-frame TP/FP/FN rationale dump for hand-classification).

- **FVS_007_001_SHIP_READINESS_v1.md (new)**: per-frame ship-readiness review for the two cross-corpus replicated V4.2 engine gaps surfaced by F-2026-034 and F-2026-035 (FVS-007 over-fire, FVS-001 low-recall). Substrate-level diagnosis grounded in extracted engine rationales across all 20 unique FP docs (FVS-007) and 9 unique FN docs (FVS-001) on mg_v1 + mg_v2, both runs, both consensus modes, plus all 5 stable TP docs across both frames. **FVS-007 over-fire root cause**: lexical-capture confusion between failure-of-self (the library construct: "what would make THIS analysis wrong") and failure-of-subject (descriptive content: "co-founder conflicts cause startup failure", "Big Tech privacy violations", "policy failure modes", etc.). The detector reads "failure" as a topic word and matches documents that catalog failure modes of their subject matter. **TP rationales reveal the same pattern**: all 3 cross-corpus FVS-007 TPs (mg_32_higgins_vaccine_skepticism on mg_v1; mg2_33_nadelson_cigna_downcoding + mg2_43_cirincione_nuclear_consensus on mg_v2) cite "failure conditions / failure modes" of their subject matter, exactly the substrate confusion that produces the FPs. TP-vs-FP is determined by panel co-alignment with the same lexical confusion, not by detector correctness; the precision number (0.118 mg_v1 to 0.174 mg_v2, run-pair averaged) reflects panel-detector co-alignment. **FVS-001 low-recall root cause**: structural extraction gap. The detection criterion (Branch A: static coverage imbalance across analytical dimensions) lives outside the Identification section the V4.2 engine extracts per the library_v3-to-v4 byte-equivalence contract; the engine instead imports the Identification's process narrative ("iterative refinement", "extended sessions") as the detection criterion and rejects all single-turn documents (essentially every published essay). **Both FVS-001 TPs (mg_13_thompson_bubbles, mg2_13_currier_consumer_back) reveal an accidental-precision pattern**: detector cites "iteratively refines" applied to within-document elaboration (multiple historical examples, citations across paragraphs), which happens to overlap with Branch A's coverage-imbalance criterion in narrow cases (multi-example single-thesis documents). Precision 1.000 cross-corpus is accidental; recall 0.333 is the engine criterion miss. The library_v4 entry already documents the conservative-pole behavior at lines 113-114 with the explicit note "Canon-status and production disclosures should name this explicitly", but the disclosure has NOT been wired into engine HONEST_LIMIT_DISCLOSURES. **Verdict per frame**: SHIP WITH DISCLOSURE (engine HONEST_LIMIT_DISCLOSURES wire-up now, voice-aligned draft text per frame in §2.4 and §3.4 leading with intra-rater AC1 0.707/1.000 like existing FVS-002/004/010/016 disclosures) + library-fix at next library_v5 ratification (Identification revision per frame in §2.4 and §3.4). 4 independent operator decisions enumerated (2 disclosure wire-ups + 2 library proposals) with default recommendation YES on all four. 7 explicit "what I have NOT verified" entries scope the inference vs measurement boundary. Pre-registered next measurements drafted for both decisions if they ship. Construct-revision measurement-paradox caveat surfaced explicitly: post-fix metrics may shift in unexpected directions (e.g., FVS-007 macro-F1 may DROP under library_v5 because current TPs are mostly failure-of-subject docs that happen to have panel agreement; that drop would be construct-alignment improvement, not regression). Files: `FVS_007_001_SHIP_READINESS_v1.md` (review doc), `scripts/diagnose_fvs_007_001_mis_fires.py` (deterministic mis-fire enumeration script, zero API calls), `scripts/extract_fvs_007_001_rationales.py` (deterministic rationale extraction script), `fvs_eval/v4/per_frame_007_001_diagnostic.json` (machine-readable diagnostic), `fvs_eval/v4/per_frame_007_001_rationales.md` (human-readable rationale table). Cross-references added to F-2026-035 cross-corpus-replication callout and CONSTRUCT_VALIDITY_AUDIT_v1.md §13 "Where it breaks" subsection.

## [0.8.0] - 2026-04-27

Target: `0.8.0` (first public PyPI release). Depends on the operator lifting the publish hold per `STRATEGY.md §11` and the V4.2 engine reaching Tier 2 completion per `V4_2_GAP_INVENTORY_v1.md §5`.

### Security + governance (publish-readiness audit campaign, 2026-04-27)

Pre-publish hardening campaign on the `frame-check-mcp` 0.8.0 wheel.
Six commits (`9095f4b`, `4918f67`, `faa8c6a`, `1351cbf`, `9c3a04e`,
`fb50d00`) ship the audit, the dispatcher fixes the audit surfaced,
the conformance evidence, the verdict, and the governance docs.
Verdict: unconditional GREEN for TestPyPI lift; PyPI lift gated only
on the operator's call between three Finding 17 strategies.

- **Leakage audit (D1)**: `LEAKAGE_AUDIT_v1.md` catalogues 16
  findings on the wheel (operator-path leaks, maintainer-side doc proxy-leaks,
  unreachable Python modules, license-posture gaps, unbundled-doc
  references, AI-authored audits, dev CLI scripts, historic
  cross_check artifacts). 14 fully closed; 2 partial closes named
  explicitly (Finding 5 URL-form-cited at brief-named scope, wider
  ~150-ref FVS-to-research-artifact surface deferred as Finding 17;
  Finding 14 cross_check files dropped from wheel, aggregate.json/md
  history retained). Wheel reduction 264 -> 208 files. Closure
  evidence per finding in `REMEDIATION_LOG_v1.md` sections A-J and
  the §L closure summary added by operator commit `9c3a04e`.

- **Adversarial harness (D2)**: `test_mcp_adversarial.py` adds 63
  tests across 7 attack classes (A prompt injection, B path traversal
  with 39 parametrized cases, C oversized input boundary, D
  encoding/unicode, E malformed JSON-RPC, F resource content +
  operator-stderr safety, G byte-determinism). Three real
  dispatcher defects surfaced + closed in the same commit: D2.1
  `dispatch()` returned ERR_INTERNAL on non-Object `params` (now
  ERR_INVALID_PARAMS); D2.2 crashed on non-string `method` (now
  ERR_METHOD_NOT_FOUND); D2.3 `handle_tools_call()` accepted
  non-Object `arguments` (now ValueError -> ERR_INVALID_PARAMS).
  Each defect leaked the exception class name to the wire and
  violated the dispatcher's own docstring discipline that -32602 vs
  -32603 distinguishes "malformed request" from "server crash."

- **Client conformance (D3)**: `MCP_CLIENT_CONFORMANCE_v1.md` records
  32/32 round-trips against the installed wheel via subprocess +
  line-delimited JSON-RPC over stdio (the I/O shape Claude Desktop
  and Cursor use). Driver: `scripts/mcp_conformance_driver.py`,
  reusable for future releases via the three-step build/install/run
  sequence in the doc.

- **Verdict (D4)**: `PUBLISH_READINESS_VERDICT_v1.md` synthesizes
  the audit into a per-surface GREEN/YELLOW table, names the two
  operator-owned conditions (version lift, Finding 17 strategy),
  enumerates the audit deliverables, and recommends a ten-step lift
  sequence that preserves the publish-hold hard gate.

- **Stress-test closure (`fb50d00`)**: the one residual flagged
  across D2/D3/D4 (maintainer-side stderr control-character leak in
  `mcp_server.log()`) is closed via a new `_sanitize_log_message()`
  helper that escapes ASCII C0 controls (except CR/LF/TAB) to
  `\xNN` form. Pinned by 2 new tests (F6 unit, F7 end-to-end via
  `capsys`). Verified live in wheel via subprocess capture against
  a hostile resource URI carrying ANSI escapes.

### Added (governance, 2026-04-27)

- **DCO sign-off requirement (`1351cbf`)**: `CONTRIBUTING.md` adds
  Developer Certificate of Origin v1.1 with the full DCO text quoted
  inline. Every commit going forward must carry a `Signed-off-by:`
  trailer (`git commit -s`). PR-process step gated on sign-off; no
  CLA, no central paperwork. Linux kernel pattern; preserves the
  same legal substrate (clean per-commit copyright provenance) at
  lower friction. Solo-author commits prior to this commit are not
  retroactively signed; DCO is a forward-looking policy from this
  commit forward.

- **`SECURITY.md` audit history (`1351cbf`, v2)**: restructured to
  recognize two distribution surfaces (web service +
  `frame-check-mcp` wheel). Expanded MCP server bullet names the
  specific in-scope concerns (path traversal, prompt-injection-
  influencing-static-payload, `user_context` privacy posture,
  JSON-RPC envelope shape) and references the audit deliverables.
  New "Audit history" table records the 2026-04-27 audit and the
  prior 2026-04-18 Phase 5 cost/origin/abuse hardening.

- **`pyproject.toml` `[project.urls]` Issues + Security**:
  PyPI sidebar surfaces both. Other URL entries
  (Homepage, Repository, Changelog, Methodology, Frame Library)
  unchanged.

- **Wheel verified PyPI-clean**: `twine check --strict` PASSES.
  PEP 639 license layout: `dist-info/licenses/{LICENSE,NOTICE}` both
  bundled. Description-Content-Type: text/markdown; classifiers
  list Python 3.10/3.11/3.12 and the relevant topic + audience
  trove entries.

### Audit gap-closure pass (2026-04-27, post-publish-fresh-eyes review)

A second-pass review of the post-audit branch state surfaced eight
remaining gaps. All are closed in this batch; the wheel rebuild
passes the (now-extended) eight-gate `lift_dry_run.py` end-to-end.

- **Finding 17 closed (URL-form-cite + vault-leak strip)**: new
  `scripts/normalize_library_refs.py` performs a two-class
  transformation across the 43 shipped catalog files in
  `data/frame_library/` and `data/frame_library_v3/`. Class A:
  ~360 backtick references to tracked-on-master artifacts
  (`fvs_eval/v4/RELIABILITY_STUDY.md`, `FRAME_DIVERGENCE_v2.md`,
  `METHODOLOGY.md`, sibling FVS files, etc.) become URL-form-cited
  links to GitHub master so the wheel-only consumer can resolve
  the breadcrumb. Class B: 88 backtick references to operator-private
  artifact paths (`data/falsifications/F-2026-NNN.md`,
  `EXP-096-data/scorecards_pass1.md`) collapse to bare artifact
  IDs (`F-2026-027`) so the catalog still tells the reader which
  internal pre-registration the rule's empirical claim came from
  without proxy-leaking the gitignored vault tree's existence and
  naming convention. Idempotent: simple string replacement; second
  run is a no-op. 424 total replacements across 43 files.

- **Leak check extended to catch the Class B pattern**:
  `scripts/lift_dry_run.py` `VAULT_DOC_PATTERNS` gains
  `r"data/falsifications/F-\d{4}-\d{3}"` and `r"\bEXP-\d{3}-data/"`.
  The original pattern set covered named vault docs (`STRATEGY.md`,
  `THE_BETS.md`, etc.) but not the maintainer-internal artifact
  directories that Finding 17 surfaced. Future drift (a new catalog
  edit reintroducing a vault path reference) now fails the leak
  gate at lift time. Caught two prior leaks in `clarethium_measure.py`
  comments (`EXP-095-data/GFP_CODEBOOK.md` references in the GFP
  classifier docstring + module comment); both rewritten to name
  EXP-095 as an internal artifact without the path form.

- **`lift_dry_run.py` reads version dynamically**:
  `EXPECTED_SERVER_VERSION` is now read from `pyproject.toml`
  `[project] version` at runtime via `_read_pyproject_version()`
  rather than hardcoded. The script no longer drifts whenever the
  operator lifts the project version; reusable across 0.8.x, 0.9.0,
  1.0.0 without editing.

- **NOTICE CC-BY-4.0 enumeration extended**: the four 2026-04-27
  audit deliverables (`LEAKAGE_AUDIT_v1.md`, `REMEDIATION_LOG_v1.md`,
  `MCP_CLIENT_CONFORMANCE_v1.md`, `PUBLISH_READINESS_VERDICT_v1.md`)
  are added to the CC-BY-4.0 list as research output that travels
  with the repository's standing audit posture for each shipped
  wheel. Aligned with the existing posture for METHODOLOGY.md,
  FRAME_DIVERGENCE_v1.md, V4_2_GAP_INVENTORY_v1.md, etc.

- **DCO sign-off enforcement workflow**:
  `.github/workflows/dco-check.yml` checks every PR commit (excluding
  merge commits) for a `Signed-off-by:` trailer and fails the check
  on missing sign-off, with explicit remediation guidance in the
  failure output (`git rebase --signoff`, `git commit --amend
  --signoff`). Mechanical enforcement of the DCO 1.1 contract
  added in `1351cbf`.

- **Pull request template**: `.github/PULL_REQUEST_TEMPLATE.md`
  prompts contributors for change summary, scope category (with
  catalog and MCP server checkboxes that name the catalog and
  dispatcher surfaces explicitly), test plan, documentation
  touched, and DCO sign-off self-check. Pairs with the DCO workflow.

- **README MCP quickstart block**: added a "Quickstart (MCP server)"
  section near the top of README.md so the PyPI consumer arriving
  at the GitHub readme sees `pip install frame-check-mcp` plus the
  Claude Desktop config snippet immediately, rather than having to
  scroll past the web-app "Running locally" instructions to reach
  the MCP install at line ~330. The detailed install + Cursor
  pattern + `--test` mode coverage in the existing MCP section
  remains the authoritative reference; the quickstart points to it.

- **`SECURITY.md` reproducibility section + PGP plan**: new "How to
  verify the audit yourself" section names the four scripts that
  reproduce the 2026-04-27 audit's evidence (`lift_dry_run.py`,
  `mcp_conformance_driver.py`, `test_mcp_adversarial.py`, plus
  reading the four audit deliverables) and pins regression on any
  released wheel as security-relevant. The "Cryptographic identity"
  section gains an explicit 0.9.0-window PGP key plan with a
  Signal-handle interim path so reporters who require non-email
  encrypted channels are not blocked by the absent key. Bumped to
  v3.

Verification: full `lift_dry_run.py` passes 8/8 gates against the
rebuilt wheel (208 files, 0 leaks under the extended pattern set,
0 vault refs, 0 audit-doc accidents, 32/32 conformance round-trips,
twine check --strict PASSES). Full project test suite: 49/49 pass
(163s). Adversarial harness: 63/63 pass (0.27s).

### Added (Move D-FVS-008: Growth Frame content discriminator)

One bounded substrate change shipped 2026-04-27 closing the FVS-008 over-fire pattern that two cross-domain adversarial fixtures (`epistemic_via_paraphrased_sourcing/`, `cross_domain_stakeholder/`) had reproduced. Empirically grounded in cross-domain fixture evidence + validation-corpus impact analysis.

- **Move D-FVS-008 (FVS-008 Growth Frame content discriminator)**: extends `frame_library.py::suggest_frames` FVS-008 rule with a business-growth content requirement (`_FVS_008_GROWTH_CONTENT_RE`). The pre-Move-D rule fired on the structural signal alone (trends/causes covered + risks missing + voice not descriptive); this over-fired on documents using directional-change vocabulary (trends regex matches "evolution", "shift", "emerging", "transformation", "expand" generically) without business-growth context. The new rule additionally requires text-level vocabulary indicating business growth (revenue, sales, earnings, market share/expansion/opportunity, customer/user/subscriber growth/adoption/acquisition/base, TAM, top-line, commercialization, OR a quantified-growth pattern like "X grew by $Y" or "N percent growth/annualized").

- **Empirical scope of the over-fire pattern (pre-Move-D)**: 2 adversarial fixtures + 9 of 28 validation-corpus documents fired FVS-008 incorrectly (a04 PG cities/ambition, a05 PG how-you-know, a09 arxiv foundation models, b05 remote work productivity, c03 quantum supremacy, c04 UBI, c05 nuclear fusion, c07 climate mitigation, c10 microplastic). None of these are substantively about business-growth framing per the frame's CONSTRUCT (`_DEFINITIONS["FVS-008"]`: "Organizes information around growth metrics, market expansion, and upward trajectory while omitting risks, stakeholders, and uncertainty").

- **Post-Move-D verification**: all 11 over-fire cases (2 fixtures + 9 corpus) correctly suppress FVS-008 firing. The 2 fixtures' `expected.json` re-captured: `frame_library_matches` loses FVS-008; `frame_patterns` no longer carries `growth-without-risk` (which was a cascade-from-upstream-error case); `absence_clusters` correctly add FVS-008 to absent member_frames. The 9 corpus docs now show OTHER genuine `frame_patterns` (recommendation-without-falsification, advocacy-without-counter-perspective, narrative-without-stakeholders, analysis-without-grounding, forward-projection-without-anchoring) that previously could not fire because FVS-008 over-fire crowded the frame-pattern landscape; these patterns are not new substrate behavior, they fire because the upstream FVS-008 detection is now correct.

- **Caller updates**: `frame_library.py::suggest_frames` documents the FVS-008 rule as text-dependent (consistent with FVS-006 Identity Framing's existing pattern). Three legacy callers updated to pass `text` (`reframe.py`, `l2_concept_validation.py`, `l2_extended_validation.py`); two test files updated (`test_frame_library.py::_detect_frames`, `test_decision_readiness.py::test_decision_readiness_caps_with_real_detector`). MCP path (`mcp_server.py`) already passed `text`; user-facing surfaces are unaffected by the caller-update churn.

- **Regression tests**: `test_frame_library.py::TestGrowthFrame` updated to pass minimal growth-vocab text on the existing 4 tests (so they still test the structural rule firing), plus 2 new pinning tests (`test_not_suggested_without_growth_vocabulary` exercising the discriminator's negative case via cross-domain-shaped synthetic prose; `test_not_suggested_when_text_is_none` pinning the text-required discipline). 310 tests pass on `test_frame_library.py + test_decision_readiness.py + test_mcp_server.py + test_adversarial_fixtures.py` cumulative; full project suite 47/47 pass.

- **Audit updates**: both fixture audits gain a "Post-tightening (2026-04-27): Move D-FVS-008 shipped" section documenting the per-fixture substrate-behavior delta. CONSTRUCT_VALIDITY_AUDIT_v1.md §7 (frame library matches) updated in-place naming Move D-FVS-008 + the 2-fixture + 9-corpus impact.

Discipline notes:
- Move D-FVS-008 is the FIRST substrate-tightening commit that responds to fixture findings BEYOND a regex extension (Move E was a regex addition; Move A and Move B were regex tightenings on the genre classifier). Move D-FVS-008 modifies a compositional rule and adds a content discriminator, demonstrating the fixture-to-substrate-tightening loop on a different class of substrate change.
- Cross-fixture corroboration was the gating evidence: a single fixture surfacing FVS-008 over-fire would be ambiguous (could be fixture-specific composition); two fixtures in distinct registers (literature review + treaty governance) plus 9 validation-corpus docs across 4 domain classes (PG essay, arxiv abstract, business policy brief, Wikipedia) makes the pattern empirically structural rather than fixture-specific.
- The frame's CONSTRUCT (business-growth framing) was the principled basis for the discriminator design. The substrate's prior rule was checking a structural shape (trends-covered + risks-missing) that the construct does not fully entail; Move D-FVS-008 tightens to match the construct.
- The "text is None" path: when callers don't pass text, the FVS-008 rule no longer fires (consistent with the function's standing "text-dependent rules don't fire when text is None" discipline that already governed FVS-006). This is a behavior change for callers that don't pass text but is the cleaner discipline; legacy callers were updated rather than preserved.

### Added (seventh adversarial fixture: cross-domain stakeholder)

- **Cross-domain stakeholder fixture** (`data/adversarial_fixtures/cross_domain_stakeholder/`) with `document.md` (a 334-word public-international-law analytical text on Antarctic Treaty System governance, naming roughly ten stakeholder entities specific to the treaty regime: Consultative Parties, Non-Consultative Parties, Secretariat, Committee for Environmental Protection, Scientific Committee on Antarctic Research, Council of Managers of National Antarctic Programs, Claimant states, Inspecting parties, depositary government, Antarctic and Southern Ocean Coalition), `expected.json`, `audit.md`. Closes paper-revision readiness #9 per `data/adversarial_fixtures/README.md` strategic gap-closure plan.

- **Headline finding**: `stakeholder_map.role_count = 0` despite the document substantively describing stakeholder relationships throughout. The canonical 12-role regex (`frame_deepening.py::_STAKEHOLDER_ROLES`) covers regulators, policymakers, public, investors, customers, employees, competitors, communities, suppliers, management, industry_actors, affected_populations; none match treaty-defined or institutional-governance role vocabulary. The substrate's `scope_reading` honestly reports the gap rather than fabricating a stakeholder reading; evidence discipline holds.

- **Cross-domain confirmation of FVS-008 over-fire pattern**: this is the SECOND fixture surfacing FVS-008 (Growth Frame) firing on non-growth content. The first was `epistemic_via_paraphrased_sourcing/` (academic literature review on language-model interpretability); now reproduced in international-treaty governance domain. Two registers, same FVS-008 over-fire signature. The cross-domain pattern elevates Move D's priority on FVS-008 specifically (per-FVS detector audit; named in `balanced_macroeconomic_outlook/audit.md`).

- **FVS-011 (Stakeholder Frame) under-fire on stakeholder-centric content** is a new gap surfaced. The frame-library detection layer carries the same domain-coverage gap as the deepening-layer regex: stakeholder framing in non-canonical vocabulary is structurally invisible to both layers. Documented as open trace investigation in this fixture's audit.

- **Tightening targets documented**: Move L (cross-domain stakeholder regex extension covering treaty_parties / international_bodies / legal_actors / governance_actors role classes; medium-risk; multi-session scope; conservative path defers until a second cross-domain stakeholder fixture in legal/judicial domain corroborates) plus the two open trace investigations (FVS-008 over-fire audit, FVS-011 under-fire audit). All tightening evaluated separately per the standing fixture discipline; the fixture's expected.json pins the current substrate reading as the regression baseline.

- **Discipline reinforcement**: the genre abstention discipline holds on a fourth document register (legal-institutional analysis); the voice residual-analytical (5.0, high, None) signature reproduces (this fixture serves as cross-register pin alongside `voice_residual_analytical/`); the cascade-from-upstream-error pattern in `frame_patterns` (`growth-without-risk` fires because FVS-008 over-fires) is reproduced for the second time across fixtures.

- **README updates**: fixture summary table gains a row for the new fixture; paper-revision readiness #9 marked CLOSED; counter advances from 6/10 to 7/10 toward paper-revision target.

Tests: 10 adversarial fixture tests pass (was 9; +1 for the new fixture, auto-discovered); cumulative 239 mcp_server.py + adversarial_fixtures.py tests pass; em-dash gate clean across all 3 new/modified files.

Discipline notes:
- Composed once (a structural description of the Antarctic Treaty System), captured, audited honestly. Substrate is NOT iterated against the fixture; the discipline holds.
- The fixture is gap-surfacing (stakeholder regex domain coverage; FVS-008 over-fire; FVS-011 under-fire) as opposed to discipline-pinning (which `voice_residual_analytical/` is). The README's fixture summary now distinguishes the two classes; this fixture is the third-most-substantive gap-surfacing fixture (after `instruction_without_troubleshooting/` and `coverage_via_noncanonical_vocabulary/`).
- Move L is bounded but multi-session scope; the conservative path (defer until a second cross-domain stakeholder fixture in a different non-canonical domain corroborates the gap) follows the discipline applied for Move D (per-FVS detector audit) of requiring multi-fixture corroboration before regex expansion.

### Added (sixth adversarial fixture: voice residual-analytical discipline pin)

- **Voice residual-analytical fixture** (`data/adversarial_fixtures/voice_residual_analytical/`) with `document.md` (literary-essayistic reflection on waiting; ~330 words; third-person register; zero second-person pronouns, zero first-person plural pronouns, zero imperative-start sentences, zero specification labels, zero promotional sentiment markers), `expected.json` (substrate's reading pinned as regression baseline), `audit.md` (per-level catch-vs-miss diagnosis). The fixture pins the canonical (margin_to_threshold=5.0, confidence=high, runner_up=None) residual-analytical signature at fixture level. The L3a serialization discipline (CONSTRUCT_HONESTY_AUDIT_v1.md, shipped 2026-04-21) was previously pinned only at the surface-rendering layer by 3 unit tests (portrait, framing_ai, comparison surfaces); this fixture extends the pin to the substrate-output layer, so future drift on the residual-analytical signature OR the caveat prose in `voice.construct.how_to_serialize` produces a regression diff.

- **First "discipline-pinning" fixture** (rather than gap-surfacing): the prior five fixtures each surface a specific operationalization gap and propose tightening moves. This fixture has no tightening moves identified; its purpose is to capture an existing discipline's behavior on a realistic document so the discipline cannot silently regress. The README's fixture summary now distinguishes the two classes; future fixture composition should label its class explicitly.

- **Paper-revision readiness #6 closed** per `data/adversarial_fixtures/README.md` strategic gap-closure plan. Fixture count advances from 5 (paper-submission readiness met) to 6/10 toward paper-revision readiness target.

- **CONSTRUCT_VALIDITY_AUDIT_v1.md updates**: the voice signal's "Fixture coverage" entry (§4) now names this fixture as direct (vs. the prior indirect coverage via sales_pitch_as_analysis and instruction_without_troubleshooting); the "Hidden-residual sweep" entry #3 (voice analytical residual) names the fixture-level pin shipped 2026-04-27. In-place edits per the audit's own discipline (gap was OPEN-at-prose-level, now CLOSED at fixture-level; no version increment).

Tests: 9 adversarial fixture tests pass (was 8 before; +1 for the new fixture, auto-discovered by `_list_fixtures`); 237 mcp_server.py + adversarial_fixtures.py tests pass cumulative; em-dash gate clean across all 4 new/modified files.

Discipline notes:
- The fixture is composed once (a realistic literary essay on waiting), captured, audited honestly. Substrate is NOT iterated against the fixture; the discipline holds.
- The fixture composition was checked against the voice cascade's threshold conditions (Rule 1-7 in `framing.py::_voice_cascade_eval`) before commit: every above-rule misses by enough margin to produce the canonical (5.0, high, None) signature. The composition target is structural (the residual-analytical case), not adversarial in the deception sense.
- The audit explicitly names the fixture's residual: the L3a discipline is prose-only; an agent that ignores `voice.construct.how_to_serialize` and reads only `voice.classification` + `voice.confidence` will still treat the document as decisively analytical. L3b (a new confidence state distinct from "high" that names the residual case structurally) remains curator-gated per `fvs_eval/CONSTRUCT_HONESTY_AUDIT_v1.md`. This fixture does NOT close that residual; it pins the prose-level discipline.

### Added (Move E + Phase 2 audit correction)

One bounded substrate change shipped 2026-04-27 plus a corrective audit pass on a prior-session construct-validity drift. Both items emerged from a stress-test of the proposed Tier 1 path; the proposed path was pushed back on and replaced with this bounded scope.

- **Move E (epistemic candidate-attribution: agency-style parenthetical citations)**: extends `framing.py::EPISTEMIC_CANDIDATE_ATTRIBUTION` with three sub-patterns (E.1 acronym-delimiter-content, E.2 acronym-near-year, E.3 capitalized-two-word-name-with-year). Each sub-pattern uses a `(?-i:...)` inline scope so the outer `re.IGNORECASE` does not break the case discriminators. Surfaces forms like `(BEA, June 2026)`, `(BLS, June 2026 release)`, `(FDIC, OCC)`, `(BLS multifactor productivity, services sector, ...)`, `(Bloomberg survey, July 2026)` as candidate attribution. Conservative scope: candidate path only; primary `_SOURCE_RE` and `sourced_pct` unchanged. CONSTRUCT_VALIDITY_AUDIT_v1.md §2 named this gap; `balanced_macroeconomic_outlook` adversarial fixture provided the worked example. On the macro fixture: `candidate_attribution_count` rises from 1 to 6 (5 new genuine catches + 1 prior false positive `(June 2026)` from the existing case-insensitive Author-YYYY pattern). On the validation corpus (N=28): zero new candidate matches surfaced, because the corpus does not represent the parenthetical-agency-citation register Move E targets. Pinned by `test_mcp_server.py::test_epistemic_candidate_attribution_surfaces_agency_parentheticals` which verifies each sub-pattern catches its representative form AND verifies bare abbreviation-definition parens like `(LLM)` and `(FDA)` do NOT surface as candidates.

- **Macro fixture audit post-tightening section**: `data/adversarial_fixtures/balanced_macroeconomic_outlook/audit.md` gains a "Post-tightening (2026-04-27): Move E shipped" section documenting the substrate-behavior delta (sourced_pct unchanged, candidate_attribution_count rises). The captured-reading subset in `expected.json` does not pin `candidate_attribution_count`, so the regression test stays green without re-capture; the substrate's reading on this fixture is meaningfully better at the candidate layer with no expected.json churn.

- **User-experience grounding analysis** (`data/adversarial_fixtures/balanced_macroeconomic_outlook/user_experience_grounding.md`): walks Move E through the four operator-discipline questions (what document classes do users paste; real or theoretical case; agent-rendered before-vs-after delta; remaining residuals). Names two surviving residuals honestly: `(Census Bureau)` and similar undated capitalized-name parens still missed; the genre cascade still mis-classifies the macro fixture as narrative BORDERLINE (Move C territory; deferred). Required deliverable per the operator's discipline; future fixture-tightening commits in this directory should follow the same grounding pattern.

- **Phase 2 audit correction (epistemic_via_paraphrased_sourcing fixture)**: the prior-session audit framed "claim extractor returns ZERO claims on a 653-word literature review" as a HIGH-PRIORITY substrate gap with cascade impact. Stress-test re-read: the substrate's claim extractor (`claim_analysis.py::analyze_claims` -> `clarethium_measure.py::extract_numerical_claims`) is by construct a NUMERICAL extractor; the literature-review document has zero digit-formatted numbers; claim_count=0 is the correct substrate reading; CONSTRUCT_VALIDITY_AUDIT_v1.md §3 already documents the abstention path as construct-honest. The original framing conflated user-meaningful "claim" with the substrate's narrow operationalization (numerical claim). The audit's "Open trace investigation (HIGH PRIORITY)" entry is closed; replaced with a "Closed (2026-04-27): claim extractor returning zero is the construct working as designed, not a gap" section walking the construct boundary. README.md fixture summary row updated. Move J (epistemic paraphrased-aggregation regex) deferred: the register Move J targets (academic literature review with paraphrased aggregation) is not represented in the validation corpus, worked examples, or any user-realistic finance-domain content; re-evaluate when a finance/policy fixture or user-surfaced document carries that register.

Discipline notes:
- Move E ships separately from any fixture commit per the standing tightening-vs-fixture discipline. The macro fixture's `expected.json` is unchanged because the captured subset does not pin `candidate_attribution_count`; the audit.md still gains a post-tightening section documenting the substrate-behavior change for future readers.
- The Phase 2 audit correction is a construct-validity drift fix, not a substrate change. The fixture's expected.json is unchanged. The audit.md is corrected in-place because the original framing was wrong; this is the audit's "correction" path (analogous to the construct-validity audit's in-place edit discipline for OPEN-to-CLOSED gap closures, but for FRAMED-AS-GAP-to-NOT-A-GAP corrections). Future fixture audits should walk the construct boundary explicitly before naming a behavior as a gap.
- The proposed Tier 1 path (claim extractor trace investigation as Phase 2 + Move J as Phase 3) was stress-tested before execution per the operator's discipline; both phases were pushed back on with reasoning and an alternative recommendation (Move E + Phase 2 correction) was proposed and approved before execution. Premature convergence avoided.

Tests: 237 mcp_server.py + adversarial_fixtures.py tests pass (was 236; +1 for the new Move E sub-pattern regression); full project suite 47/47 pass; em-dash gate clean across all touched files.

### Added (adversarial fixture infrastructure expansion + construct-validity audit + paper outline v2)

Four work items shipped 2026-04-27 building on the L5 per-level claim treatment framework. Each item closes a gap surfaced by stress-testing the substrate from external-evaluator perspectives. None requires substrate semantics changes beyond the genre-classifier tightening (Move A and Move B); the rest is regression infrastructure, audit artifact, and outline.

- **Second adversarial fixture**: `data/adversarial_fixtures/instruction_without_troubleshooting/` with `document.md` (5-step setup guide composed without failure-mode coverage), `expected.json` (substrate's reading pinned as regression baseline), `audit.md` (per-level catch-vs-miss diagnosis). Fixture exposed two compounding genre-classifier gaps simultaneously: descriptive `you should see` triggered HIGH-confidence recommendation misclassification (Move A), and markdown-header step formatting `## Step N:` was not matched by the instruction regex (Move B). The L5 framework's per-level visibility was load-bearing in scoping the fix to the classifier layer rather than tweaking pattern thresholds at composed_pattern level.

- **Move A (recommendation regex perception-verb negative lookahead)**: `you\s+should` now carries `(?!\s+(?:see|notice|observe|hear)\b)` to exclude unambiguous descriptive forms. Ambiguous-perception verbs (expect, find, feel, get) deliberately remain matched to avoid false negatives on legitimate recommendations. Pinned by `test_genre_recommendation_regex_excludes_perception_verbs` (covers descriptive exclusion + prescriptive inclusion + ambiguous-residual deliberate inclusion).

- **Move B (instruction regex markdown-header alternative)**: additive alternative `(?:^|\n)#{1,6}\s+step\s+\d+[:.]\s` matches setup-guide and runbook formatting (`## Step N:` through `###### Step N:`). Pinned by `test_genre_instruction_regex_matches_markdown_headers` (covers markdown-header forms + bare-line forms preserved).

- **Construct-validity audit v1** (`CONSTRUCT_VALIDITY_AUDIT_v1.md`): living artifact for external evaluators. Walks 12 substrate constructs through 5 evaluator questions (validity, honesty, calibration, failure modes, reproducibility) at 4 claim levels. Construct-honesty mechanism integrity audit (signal_type + statement + how_to_serialize alignment). Five-surface alignment matrix (template / portrait / MCP / comparison / LLM context). Hidden-residual sweep (5 known residuals; 1 open: frame_patterns co-fire). Update discipline: version increments on construct/claim_level/serialization changes; in-place edits for OPEN-to-CLOSED gap closures (the audit's claim trajectory remains monotonic).

- **Methodology paper outline v2** (`METHODOLOGY_PAPER_OUTLINE_v2.md`): supersedes outline v1 (2026-04-20). Five named changes: methodological centerpiece shifts to L5 per-level claim discipline (subsuming v1's 5-signal posture); adversarial fixtures become Track C (third evidence stream alongside Track A classifier validation and Track B reader-aid pre-registration); §4 spine is CONSTRUCT_VALIDITY_AUDIT_v1.md; honest-limits expanded with cascade-error inheritance + fixture-suite-not-representative + LLM-augmented-construct nondeterminism; three new figure candidates (L5 framework table, per-level cascade trace using instruction_without_troubleshooting, construct-validity audit five-question matrix). Outline v1 retained for diff inspection. Curator gating preserved: full draft estimated 15-25 hours, requires venue + L5-framing decision before drafting begins.

- **Adversarial fixture re-capture helper** (`data/adversarial_fixtures/recapture.py`): CLI helper that re-captures `expected.json` for one fixture (`python3 data/adversarial_fixtures/recapture.py <fixture_name>`) or all fixtures (`--all`). Writes with `sort_keys=True` and `indent=2` for stable diffs. Reduces fixture-recapture friction so future tightening commits across multiple fixtures are mechanical rather than copy-paste from inline Python. README.md updated to reference the helper.

Tests: 229 mcp_server.py + adversarial_fixtures.py tests pass; full project suite 47/47 pass; em-dash gate clean across all six new/modified docs.

Discipline notes:
- Move A and Move B are tightening commits SEPARATE from the fixture commit, per the adversarial-fixture-suite rule "tightening moves are evaluated separately, not bolted onto the fixture commit." The fixture's `expected.json` was re-captured against the post-tightening substrate and `audit.md` gained a "post-tightening update (2026-04-27)" section documenting the cascade trace (genre wrong upstream -> wrong frame_pattern fires; both corrected by upstream tightening).
- The construct-validity audit's `§6 Genre` was updated in-place to mark Move A and Move B CLOSED with cross-references to the regression tests; per the audit's own "minor in-place edits" discipline (added in this commit), no version increment was needed.
- Outline v2 explicitly is NOT a paper draft. Drafting remains curator-gated per outline v1's discipline. v2 prepares the curator decision against the current substrate state by incorporating the L5 framework + fixtures + audit infrastructure shipped between 2026-04-20 and 2026-04-27.

### Added
- **Frame divergence block on `frame_check` output** (opt-in via `include_divergence=true`) per `FRAME_DIVERGENCE_CONTRACT_v1.md` Part 2 c1.0. The block carries `absent_frames` (FVS catalog entries the V1 detector did not match, each with `frame_id`, `frame_title`, `citation_uri`, `absence_basis`, `domain_relevance_rationale`, `stability`, `frame_version`) and a `FaithfulnessEnvelope` with `spec_version`, `catalog_version`, `surface`, `v4_2_execution`, `v4_2_engine_status`, `v4_2_engine_status_reference`, `domain_inferred`, `provisional_count`, `faithfulness_note`, `limitations`. Two new keys on `agent_guidance`: `how_to_render_divergence` (caller-side composition instructions) and `absence_is_not_prescription` (the guarantee divergence output never tells the user which frames they should have used).
- **New optional parameters on `frame_check`**: `prefer_contract_version` (coverage shape opt-in), `include_divergence`, `domain_hint`, `divergence_rendering`, `catalog_version_pin`.
- **Frame Divergence v1 spec resources** on the `frame-check://` scheme: `frame-check://spec/frame-divergence/v1` (generated index), `frame-check://spec/frame-divergence/v1/part-1` (category definition), `frame-check://spec/frame-divergence/v1/part-2` (interface contract c1.0). Traversal-safe dispatch: non-integer part suffixes rejected at the dispatcher, missing part numbers return `FileNotFoundError`.
- **`_cli_test()` exercises the divergence path** (`include_divergence=true, domain_hint='finance'`). Operators running the install confidence check see divergence working end-to-end.
- **Divergence worked example** at `data/worked_examples/divergence-on-claude-bitcoin-retirement-2026.md` with asset directory containing source document and byte-stable divergence output JSON. Demonstrates caller-side V4.2 composition on five reader-relevant absences while honoring the `absence_is_not_prescription` discipline.
- **Four new prompt regression tests** in `test_mcp_server.py` pinning the divergence-aware shape of the four sovereignty prompts.

### Changed
- **All four sovereignty prompts are now divergence-aware.** `frame_check_my_response`, `frame_check_this_ai_response`, and `challenge_document` pass `include_divergence=true` on the tool call; all four step through `absent_frames` filtered for reader-relevance, honor `absence_is_not_prescription`, and cite by `frame_id` and `citation_uri`. The three tool-invoking prompts gained a new divergence step (renumbered cascading step references). `explain_framing` walks the divergence block when present and skips the step otherwise.
- **README.md** MCP section surfaces frame divergence as the headline capability with the AGI-era primitive framing, the block shape, the MCP-caller-side V4.2 model, and the forward 0.8.0 commitment.
- **METHODOLOGY.md §8** adds a frame-divergence positioning paragraph composing FVS library + V4.2 judge + evidence discipline, with canonical references.
- **MCP_SERVER.md**: `frame_check` tool-surface table expanded from 2 to 7 parameters; new "Release arc" and "Divergence block" sections; coverage migration language updated from Phase 1 to Phase 2 active deprecation (effective 2026-04-21).
- **Coverage v1 deprecation notice** activates in the v1 `caveat` field (Phase 2 per `MCP_CONTRACT_V2_PROPOSAL.md §4.1`). New integrations MUST read `coverage_v2`.

### Fixed
- **Divergence envelope citation path**: `mcp_server.py::_build_divergence_block` was emitting `"fvs_eval/v4/V4_2_GAP_INVENTORY_v1.md §5"` in `v4_2_engine_status_reference`; the file is at repo root as `V4_2_GAP_INVENTORY_v1.md`. Every divergence-enabled MCP response now carries the correct citation path.

### Changed (input limits)
- **`MAX_DOCUMENT_CHARS` raised from 10,000 to 1,000,000.** The old 10k cap was inherited from the web surface's shorter-text posture and was too restrictive for MCP agent-facing use (full papers, briefings, multi-page analyses; book-length is ~400k chars). New ceiling is defensive against pathological multi-GB inputs that would hang the stdio loop; practical analytical documents are unbounded.
- **`MAX_SOURCE_CHARS` raised from 20,000 to 2,000,000.** Same rationale; source material can be longer than the document under analysis.
- Tool-schema `maxLength` and adversarial-input tests updated to the new limits. Tool-surface tables in MCP_SERVER.md reflect the new caps.

### Changed (divergence shape: 0.8.0 default-flip + tier signal + summary prose + catalog-pin clarity)

Four polish moves shipped to make the divergence block load-bearing for AGI-era multi-perspective composition rather than reading as set-arithmetic. The discipline is: divergence is the substrate the caller's model composes against, not a verdict.

- **`include_divergence` defaults to `true` at 0.8.0** (was `false` at 0.7.x). The divergence block is the headline capability; shipping it by default removes the opt-in friction. Callers who want the v0.7.x-shape response with no divergence block set `include_divergence=false` explicitly. Backward-compatible for callers who pass the flag explicitly; forward-incompatible only for callers who depended on the `false` default. Sovereignty prompts already pass `include_divergence=true` so prompt behavior is unchanged.
- **`signal_strength` tier on each absent_frame record** (`high` / `medium` / `low`). Heuristic uses the canon-graph (`DIMENSION_LIBRARY_ENTRIES` in `decision_readiness.py`) plus the document's coverage-weakness signal. Records are sorted high-first so callers can take the top-N entries without further filtering. `affects_dimensions` is exposed alongside the tier so the caller sees which canon dimensions drove the score. `domain_relevance_rationale` is now per-tier specific (not boilerplate).
- **`divergence_summary` prose field in the envelope.** A 1-2 sentence preface naming the semantic intent of the block (catalog-driven perspective absence as substrate, not verdict) plus per-tier counts. Reduces the "set-arithmetic" feel by carrying the intent in-band.
- **`tier_counts` envelope field** (`{"high": N, "medium": N, "low": N}`). Quick triage for callers who want to know "is there any high-tier signal here?" without iterating.
- **`agent_guidance.how_to_render_divergence` carries catalog-pin clarity.** Added the explicit explanation that `library_v3` (catalog_version) is contract-pinned per c1.0 stability while `library_v4` is engine-current and byte-equivalent on `## Identification` sections that drive divergence detection. The pin is intentional, not stale.
- **`agent_guidance.absence_is_not_prescription` clarified.** Added the descriptive-vs-prescriptive distinction: a user explicitly asking "what's missing?" can be answered descriptively (naming absences); the discipline forbids prescription, not description.

Tests: `test_divergence_present_by_default`, `test_divergence_legacy_opt_out`, `test_absent_frames_carry_signal_strength_tier`, `test_envelope_carries_divergence_summary_and_tier_counts`, `test_how_to_render_divergence_carries_catalog_pin_clarity`. 188 MCP tests pass (was 184).

### Changed (UX shift: compact-default sovereignty prompts + inline citations + action question + confidence gate + user_context)

Six polish moves shipped to make the MCP's user-facing surface workflow-valuable rather than information-dump. Each move addresses a specific gap surfaced by stress-testing the response shape from structurally different perspectives (first-time user, power user, urgent decision state, off-methodology document, integrating adopter, three-year-out reviewer).

- **Sovereignty prompts compressed to compact-default + on-demand expand.** All four prompts (`frame_check_my_response`, `frame_check_this_ai_response`, `challenge_document`, `explain_framing`) restructured to lead with: 1-sentence portrait + 2-3 highest signal_strength absent frames + 1 action question + the prompt's signature closing line + an invitation to expand. Prompt bodies now ~270-320 words (was 600+). Default agent response is 100-200 words; full deep readout (coverage with density, voice with confidence + runner-up, temporal with balanced flag, epistemic, all FVS matches with teaching_question and affects_dimensions, decision-readiness across five dimensions with status 'experimental' verbatim, scope notes, agent_guidance.what_this_tool_does_not_tell_you) is one ask away.
- **Inline citations replace the bottom Sources block.** Citations rendered as `[FVS-XXX Title](frame-check://library/FVS-XXX)` adjacent to the claim they cite. Bottom bibliography forbidden by every prompt's discipline. Reader sees claim and source travel together; cognitive disconnect collapses.
- **Action question per prompt.** Each compact response ends with one question that translates the structural finding into a thinkable next step. Question form, never statement; honors `agent_guidance.absence_is_not_prescription` (the question helps the user think; never tells them what they should have done).
- **Confidence gate.** Each prompt detects document-scope mismatches before the analysis: under 100 words → "below statistical floor; low confidence"; non-English → "methodology validated on English; low confidence"; non-analytical structure (code, poetry, fragments) → "calibrated for analytical prose; low confidence". Triggered gates name the warning in one sentence before the analysis. Closes the evidence discipline at the user-facing layer; the methodology is validated on English analytical prose, and the prompts now reflect that.
- **`user_context` parameter on `frame_check`.** Optional string (max 2000 chars). When provided, `agent_guidance.how_to_render_divergence` is extended with contextual filtering instruction plus the prescription-prevention guardrail. MCP does NOT echo the value into the response (privacy posture per DATA_MOAT.md §3); the caller's agent has it from its own call args. Discipline: context personalizes RELEVANCE FILTERING, never PRESCRIPTION; the absence_is_not_prescription guarantee extends to contextual surfacing.
- **`divergence_summary` envelope field surfaced as the compact lead.** Prompts use the field shipped earlier in this release as a starting point for the 1-sentence portrait. The semantic intent of the divergence block now flows into the agent's compact response without the agent paraphrasing.

Tests added (4 new prompt-discipline regressions + 2 user_context regressions + 1 silent-hole-pattern fix; 192 MCP tests total):
- `test_all_prompts_have_compact_default_discipline`: pins compact lead, signal_strength filtering, inline citation pattern, expand invitation, no-bibliography rule.
- `test_all_prompts_have_confidence_gate`: pins all three gate triggers (length floor, language, structure).
- `test_all_prompts_have_action_question`: pins question-form discipline.
- `test_user_context_extends_agent_guidance`: pins the addendum + guardrail + non-echo behavior.
- `test_user_context_validation`: pins type/empty/over-limit rejection.
- Four existing prompt tests (`test_all_prompts_are_divergence_aware`, `test_all_prompts_honor_absence_is_not_prescription`, `test_self_audit_and_ai_response_audit_pass_include_divergence_true`, `test_all_prompts_mention_affects_dimensions_for_matched_frames`) updated to use `_assert_no_new_failures` helper, eliminating the silent-hole pattern where `check()` failures accumulated without raising.
- `test_all_prompts_cite_library_v3_catalog_pin` removed; coverage migrated to `test_how_to_render_divergence_carries_catalog_pin_clarity` which asserts the pin clarity in `agent_guidance.how_to_render_divergence` (single source of truth, not duplicated across four prompt bodies).

### Changed (UX shift: insight-led composition replaces measurement-walking)

Operator testing of the 0.8.0 prerelease in Claude Desktop surfaced a UX failure that the compact-default discipline alone did not solve. An agent walking the measurements one-by-one (even compactly) delivered a statistical readout the user could not act on: "There is a lot of statistics there which user actually has nothing to act on... no frame divergence, no frame identification, no frame opportunity. The intelligence stuff that happens there is mechanical stuff." The insight-led shift moves the discipline from "lead with the measurements compactly" to "compose ONE insight grounded in cited measurements, a reading the user could not see by re-reading their own document".

- **`agent_guidance.composition_discipline` field on every `frame_check` response.** Pushes the insight-led discipline into the tool surface so it travels with every invocation, not only with sovereignty-prompt invocations. Carries the five composition rules: (1) INSIGHT-GROUNDED (every clause cites a specific measurement), (2) READING-FORM, NEVER VERDICT-FORM ("the pattern reads as X" not "the document is X"), (3) CONFIDENCE-GATE PIVOTS THE FRAME (off-methodology triggers pivot the insight from "reading of the document" to "what this run reveals about Frame Check's scope"), (4) CROSS-CONTEXT COMPOUNDING ONLY WHEN IT ADDS, (5) ABSENCE IS NOT PRESCRIPTION (extension to insight composition).
- **`frame_check` tool description rewritten** to lead with the agent's role: compose ONE insight grounded in cited measurements, a reading the user could not see by re-reading their own document. Cites measurements as Frame Check's; frames the reading as a reading, never a verdict.
- **All four sovereignty prompts rewritten to insight-led shape.** Compact default response is now: ONE insight (~2-4 sentences, grounded in 2-3 specific cited measurements, reading-form not verdict-form) + ONE question + signature closing + expand invitation. `challenge_document` is the variant: 2-3 questions, each a compressed reading-as-question grounded in cited measurements. The deep measurement walk moved to the expand path; canon-graph traversal (per-dimension `library_entries[].library_resource_uri`, `fired_library_entries`, `/corpus/decision-readiness/` methodology link) is preserved in expand sections.
- **Confidence-gate semantics tightened.** When an off-methodology trigger fires, the agent now PIVOTS the frame instead of just naming a warning before the analysis. The insight becomes a reading of what the run reveals about the tool's scope on this kind of text, not a confident reading of the document. The user still gets a reading; it is now construct-honest about what is being read.

Tests added (3 new prompt-discipline regressions; 142 mcp_server tests pass via pytest, full script-mode also passes after fixing a stale `test_divergence_absent_by_default` reference in `main()` left over from the divergence default-flip):
- `test_all_prompts_have_insight_led_discipline`: pins ONE-insight (or 2-3 grounded questions) shape, reading-form vs verdict-form rule, do-not-walk-measurements forbidding language, `composition_discipline` reference.
- `test_all_prompts_pivot_frame_on_off_methodology`: pins the pivot discipline (PIVOT keyword + scope target).
- `test_agent_guidance_carries_composition_discipline`: pins the field's presence and the five composition rules at the tool-level surface so natural-language invocations (not just sovereignty prompts) carry the discipline.

### Added (substrate-side composition: absence_clusters by canonical dimension)

First move into the L4 territory of substrate-side composition. Where the divergence block previously delivered a sorted list of absent frames and required the agent to discover dimension-level themes across that list, the substrate now surfaces those themes directly through a new `absence_clusters` field. The substrate stays deterministic (canon-graph set membership and per-frame signal_strength aggregation only; no LLM, no document-content semantics).

Operator stress-test of the 0.8.0 prerelease in Claude Desktop showed Claude composing dimension-level themes on the fly from the absent_frames list ("these four absences cluster around one vulnerability"). That composition was the agent's, not the substrate's. The substrate provided named components; the agent assembled them. This release moves the cluster reading into the substrate so it travels with every divergence response, surfaces in the JSON before the agent gets it, and is reproducible across runs.

- **`divergence.absence_clusters` field on every divergence response.** Groups absent frames by shared canonical decision-readiness dimensions (`coverage`, `calibration`, `evidence`, `robustness`, `counterfactual` per `DIMENSION_LIBRARY_ENTRIES`). Each cluster carries `dimension`, `member_frames` (sorted), `member_count`, `canon_size`, `canon_coverage_fraction`, `signal_strength` (aggregated from highest member tier), and a dimension-specific evidence-anchored `reading`. Clusters fire when at least 2 absent frames share a dimension AND at least 50 percent of that dimension's canon is absent (the two-condition threshold is calibration-honest across dimensions of varying canon size; an absolute threshold would silently drop strong small-canon signals like "both calibration canon frames absent"). Sorted by signal_strength (high first), then canon_coverage_fraction descending, then dimension alphabetical for stable tiebreaking.
- **Curated per-dimension readings.** Five reading-form prose strings, one per canonical dimension, describing what the dimension's absence means structurally. Reading-form not verdict-form ("the framing leaves out perspectives that..."), tied to each dimension's canon-graph definition. Each reading is anchored in cluster evidence: the rendered text appends "N of M dimension-canon frames are absent in this document" so the prose is no longer dimension-generic.
- **Single-canon dimensions cannot cluster.** `evidence` and `robustness` have one canon member each (FVS-016) in the current `DIMENSION_LIBRARY_ENTRIES`; they cannot reach 2 absent and the substrate stays honest by not surfacing them as clusters. The cluster format treats this as a structural feature of the canon graph, not a missing case.
- **`envelope.divergence_summary` updated to name clusters.** When clusters surface, the summary names them as the recommended composition starting point. When no cluster reaches threshold, the summary names the empty case construct-honestly.
- **`agent_guidance.how_to_render_divergence` re-numbered to teach cluster-first composition.** Step 1 instructs the agent to start with `absence_clusters` when present, use the cluster reading as the lead synthesis, then walk the supporting per-frame entries. The absence-is-not-prescription discipline extends to clusters explicitly.
- **`agent_guidance.composition_discipline` extended to name absence_clusters.** Natural-language invocations (without a sovereignty prompt) now carry the cluster-first instruction at tool level. The cluster reading is named as Frame Check's substrate-side composition over multiple absent frames; the agent cites it as such.
- **All four sovereignty prompts updated to lead with the strongest cluster's reading when present.** `frame_check_my_response`, `frame_check_this_ai_response`, `challenge_document`, and `explain_framing` all carry cluster-first composition instructions in their compact-default sections. `challenge_document` explicitly translates the cluster theme into the lead question. When `absence_clusters` is empty, all four prompts fall back to per-frame composition.

Tests added (9 substrate-composition regressions; 151 mcp_server tests pass via pytest):
- `test_divergence_block_carries_absence_clusters`: pins shape (seven canonical fields), threshold (>=2 absent AND >=50 percent canon coverage), evidence anchoring in reading, sort order (signal_strength then canon_coverage_fraction descending).
- `test_absence_clusters_empty_when_no_dimension_reaches_threshold`: pins the threshold discipline.
- `test_absence_clusters_threshold_relative_to_canon_size`: pins calibration cluster fires at 100 percent canon (both members absent) and single-canon dimensions never cluster.
- `test_absence_cluster_signal_strength_aggregates_member_tiers`: pins signal_strength aggregation (cluster as strong as strongest member).
- `test_absence_cluster_readings_are_dimension_specific`: pins five canonical dimension readings, all distinct, reading-form not verdict-form.
- `test_divergence_summary_names_clusters_when_present`: pins construct-honest summary reporting.
- `test_how_to_render_divergence_teaches_cluster_first_composition`: pins agent_guidance teaches lead-with-clusters.
- `test_all_prompts_teach_absence_clusters_lead_when_present`: pins all four sovereignty prompts teach cluster-first composition.
- `test_composition_discipline_names_absence_clusters`: pins the tool-level discipline names absence_clusters so natural-language invocations carry it.

This is item 1 of 12 in the substrate-side composition roadmap (the L4 territory). Smallest engineering move with the largest perceived shift in substrate intelligence: the JSON now contains thinking-shaped output (named dimension clusters with composed readings) instead of only listing-shaped output (sorted absences). The agent's "asymmetry between confidence and grounding" reading becomes substrate-suggested, not invented. Verified on the agriculture document from the operator's stress test: 17 absences resolve to 3 clusters (calibration 2 of 2, coverage 7 of 8, counterfactual 4 of 5; all high-signal).

### Added (substrate-side composition Items 5/6/7: corpus_context exposure)

Items 5, 6, and 7 of the substrate-side composition roadmap, shipped together because they share the corpus aggregator infrastructure. Frame Check ships with a small validation corpus (10 documents today) plus aggregate findings; this empirical signal previously did not surface through the MCP response. Now every matched frame, absent frame, and absence cluster carries a `corpus_context` block, and the divergence envelope carries a `corpus_summary` with the small-N caveat.

The substrate stays deterministic. The aggregator runs once at first query (lazy-cached for the server's lifetime), reads existing `profile.json` files and the most recent `aggregate.json`, computes per-frame and per-dimension stats, and exposes query functions consumed by the MCP payload builder. No LLM is invoked.

- **`corpus_intelligence` module added.** New file at repo root (`corpus_intelligence.py`) bundles into the wheel via the existing flat py-modules layout. Exposes three query functions: `get_frame_corpus_context(fvs_id, ...)`, `get_dimension_corpus_context(dimension, ...)`, `get_corpus_summary(...)`. Each returns `None` when the corpus is unavailable, so the MCP response simply omits the corpus_context fields rather than carrying empty placeholders.
- **Per-frame `corpus_context` on `frame_library_matches` and `divergence.absent_frames`.** Each frame entry now carries `prevalence` ("fires in N of M corpus documents"), `fires_in_count`, `fires_in_total`, `typical_co_fires` (top-3 frames that fire alongside; each with `citation_uri`), `typical_co_absences` (top-3 frames typically absent alongside), and `corpus_entries_fired_uris` (cite-back URIs to corpus entries). Item 5 (prevalence + co-patterns) and item 7 (cite-back URIs) ship together.
- **Per-dimension `corpus_context` on `divergence.absence_clusters`.** Each cluster entry carries `peer_pair_difference_rate` ("differs across N of M peer pairs in the validation corpus"), `peer_pair_difference_count`, `peer_pair_total`, `cross_question_outlier` (when present, names the model and dimension where validation found a cross-question outlier), and `canon_size`. Item 6: outcome-shaped signals from validation runs, named honestly as peer-pair-difference rates rather than expert-rated outcomes.
- **`divergence.envelope.corpus_summary`.** Whole-corpus context: `n_documents`, `state_hash`, `aggregate_computed_at_utc`, and `small_n_caveat`. The caveat explicitly names the small-N discipline and that outcome data based on expert ratings is not yet available; the outcome-shaped signals surfaced are peer-pair-difference rates and cross-question outlier findings.
- **`agent_guidance.composition_discipline` extended.** Names `corpus_context` as a valid grounding measurement, references the `small_n_caveat`, and applies cross-context compounding rule (4): cite corpus context only when it sharpens the reading, never as scenery.
- **`agent_guidance.how_to_render_divergence` extended with step (7).** Teaches the corpus_context layer: prevalence interpretation, co-pattern interpretation, peer-pair-difference rate as cluster-level corpus signal, cross-question outlier as model-by-dimension finding, cite-back URI usage. Honors the small-N discipline.

Tests added (6 new corpus-context regressions; 157 mcp_server tests pass via pytest):
- `test_frame_library_matches_carry_corpus_context`: pins per-frame corpus_context shape and citation_uri scheme on matched frames.
- `test_absent_frames_carry_corpus_context`: pins corpus_context attachment on absent_frames.
- `test_absence_clusters_carry_corpus_context`: pins per-dimension corpus_context shape on clusters; peer_pair_difference_rate text shape; cross_question_outlier shape when present.
- `test_envelope_carries_corpus_summary`: pins envelope corpus_summary with required fields and small_n_caveat text discipline.
- `test_composition_discipline_names_corpus_context`: pins tool-level discipline names corpus_context so natural-language invocations carry the empirical-anchoring layer.
- `test_how_to_render_divergence_teaches_corpus_context_layer`: pins step (7) of the divergence guidance teaches corpus_context, corpus_summary, and peer-pair-difference rate.

This is the second move into the L4 territory of substrate-side composition. The corpus has been load-bearing infrastructure but had no MCP surface as patterns; now the agent reading divergence sees not only "FVS-008 fired" but "FVS-008 fires in 3 of 10 corpus documents, alongside FVS-007 and FVS-001 (3 of 3 times)". The reading lands with empirical anchoring, not catalog assertion. On the agriculture document from the operator's stress test: the counterfactual cluster carries "differs across 10 of 12 peer pairs; Claude is the cross-question outlier on this dimension"; the calibration cluster carries "differs across 12 of 12 peer pairs". These are substrate-composed empirical statements the agent did not have to invent.

### Added (substrate-side composition Item 2: structural genre classifier)

Item 2 of the substrate-side composition roadmap. Foundational primitive that Item 3 (per-genre absence ranking) and Item 4 (pattern composition with prevalence) will build on. The classifier emits a bounded-set genre label with construct-honest confidence reporting in the same shape as voice's classification.

The substrate stays deterministic. The classifier composes existing analyzer outputs (voice, claim hedge ratio) with text-feature regexes (recommendation markers, instruction markers, alternative-surveying markers, advocacy markers, narrative markers) into per-genre scores. No LLM is invoked.

- **`genre_classifier` module added.** New file at repo root (`genre_classifier.py`); bundles into the wheel via the existing flat py-modules layout. Exposes `classify_genre(text, voice=, claims=)` returning the construct-honest classification dict.
- **Bounded genre set.** Six structural genres: `recommendation` (gives a pick or suggests action), `analysis` (investigates without committing), `narrative` (tells a story or sequence), `advocacy` (argues for a position with persuasive force), `exploration` (surveys options without committing), `instruction` (explains procedurally with numbered steps). Adding a new genre is a four-step change: enum addition, scoring function, construct text, per-genre absence map (Item 3).
- **`analysis.genre` field on every frame_check response.** Carries `classification`, `confidence` (high / borderline / low), `runner_up`, `runner_up_margin`, `score_distribution` over all six genres, `available_classes`, and `construct` (per-genre description of how the classification was composed). Mirrors voice's classification-confidence shape exactly.
- **Construct-honest abstention.** When no feature fires (empty text, very short, off-methodology structure that does not match any genre regex), the classifier abstains: `classification` is `null` and `confidence` is `low`. The substrate does not guess.
- **`agent_guidance.composition_discipline` extended to name `analysis.genre`.** The discipline now lists genre classification as a valid grounding measurement so agents know to surface it as part of their reading.

Tests added (5 genre regressions; 162 mcp_server tests pass via pytest):
- `test_analysis_carries_structural_genre_classification`: pins field shape, bounded available_classes, classification-confidence treatment.
- `test_genre_classifies_recommendation_correctly`: pins classifier on the operator's agriculture-recommendation fixture.
- `test_genre_classifies_instruction_correctly`: pins classifier on a procedural how-to fixture (non-recommendation, non-analysis baseline).
- `test_genre_abstains_on_empty_or_featureless_text`: pins the abstention discipline.
- `test_composition_discipline_names_genre`: pins tool-level discipline names analysis.genre as a grounding measurement.

This is the third move into the L4 territory of substrate-side composition. With genre classification in place, the substrate now has the primitive that Items 3 and 4 need: per-genre canon-graph maps will assert "for recommendation genre, FVS-007 Failure Framing is load-bearing because recommendations without falsification conditions cannot be stress-tested"; pattern composition will assert "Growth fired plus Risk absent plus Failure-Framing absent in recommendation genre is the recommendation-without-falsification pattern". Both deterministic, both consequential, both gated on genre classification existing as a substrate field.

### Added (substrate-side composition Item 3: genre-relative absence ranking)

Item 3 of the substrate-side composition roadmap, built on Item 2's genre classifier. When a document classifies into a structural genre, absences that are load-bearing for that genre's reasoning are promoted within their `signal_strength` tier. The substrate carries a curated per-genre map; agents reading divergence see not only the catalog/coverage tier but also which absences are load-bearing for THIS document's genre, with the structural reason named.

The substrate stays deterministic. The per-genre maps are curated text; the relevance lookup is exact-match against canon FVS IDs; no LLM is invoked.

- **Per-genre load-bearing absence maps in `genre_classifier`.** Six maps (one per structural genre). Recommendation has four entries (FVS-007 Failure Framing, FVS-009 Risk Frame, FVS-014 Temporal Anchoring, FVS-012 Uncertainty Frame). Analysis has four (FVS-016 Authority by Citation, FVS-012, FVS-017 False Balance, FVS-011 Stakeholder Frame). Narrative, advocacy, exploration, and instruction each have their curated load-bearing absences. Each entry pairs an FVS ID with a one-sentence reading-form reason.
- **`genre_relevance` field on `absent_frames` records.** When the document has a classified genre and the absent frame is in that genre's load-bearing map, the record carries `{relevant_for_genre, priority, reason}`. `null` when the document has no classified genre or the frame is not in that genre's map.
- **Sort order updated.** `absent_frames` now sorts by `signal_strength` tier first (catalog/coverage logic), then `genre_relevance.priority` ascending within tier (1 = most load-bearing for the document's genre; non-relevant entries sort with priority 999), then `frame_id` alphabetical for stability. Catalog/coverage tier and genre relevance compose without overriding each other.
- **`agent_guidance.how_to_render_divergence` step (6.5) added.** Teaches the genre_relevance layer: classified genre, priority, reason citation. Names the structural-basis discipline ("for recommendation genre, FVS-007 absent is load-bearing because recommendations without falsification conditions cannot be stress-tested").
- **`envelope.divergence_summary` updated.** Names the document's classified genre and the count of absent frames carrying genre_relevance, when applicable.

Tests added (5 genre_relevance regressions + 1 sort-order test updated; 167 mcp_server tests pass via pytest):
- `test_absent_frames_carry_genre_relevance_for_classified_genre`: pins field shape and per-genre map coverage on the recommendation fixture.
- `test_genre_relevance_promotes_absences_within_tier`: pins the promotion invariant (no non-relevant absence appears before a relevant one in the same tier).
- `test_genre_relevance_absent_when_no_classified_genre`: pins the construct-honest abstention path.
- `test_per_genre_load_bearing_maps_cover_all_genres`: pins that every classifier genre has a curated map of at least three entries with substantive reasons.
- `test_how_to_render_divergence_teaches_genre_relevance`: pins agent_guidance step (6.5).
- `test_absent_frames_carry_signal_strength_tier`: updated sort assertion to include genre_relevance.priority as the within-tier tiebreaker.

This is the fourth move into the L4 territory of substrate-side composition. The substrate now reads "this is a recommendation; for recommendations the load-bearing absence is FVS-007 Failure Framing because recommendations without falsification conditions cannot be stress-tested" before the agent composes a single sentence. Catalog assertion + coverage weakness + genre relevance compose into a document-aware ranking that catalog set arithmetic alone cannot produce.

### Added (substrate-side composition Item 4: named structural patterns with corpus prevalence)

Item 4 of the substrate-side composition roadmap, built on Items 2 (genre classifier), 3 (per-genre absence ranking), and 5/6/7 (corpus context). Where clusters surface dimension-level themes over absences alone, named patterns surface RECOGNIZED structural shapes that combine present and absent frames into a single named composition with curated reading and corpus prevalence as empirical anchoring.

The substrate stays deterministic. Pattern matching is set membership; corpus prevalence is a count over per-document frame fire sets cached by the corpus aggregator; no LLM is invoked.

- **`frame_patterns` module added.** New file at repo root (`frame_patterns.py`); bundles into the wheel via the existing flat py-modules layout. Carries the curated pattern catalog (`_PATTERNS`) and exposes `match_patterns(matched_ids, absent_ids, genre)` returning the list of triggered patterns.
- **Initial pattern catalog (4 patterns).** `recommendation-without-falsification`, `growth-without-risk`, `analysis-without-grounding`, `advocacy-without-counter-perspective`. Each pattern carries `id`, `name`, `trigger` (frames_present_all / frames_absent_all / frames_present_any / frames_absent_any plus optional `genre`), `reading` (curated reading-form prose), and `load_bearing_dimensions`. Adding a new pattern requires curation review and an entry in `_PATTERNS`.
- **`divergence.frame_patterns` field on every divergence response.** List of triggered patterns; empty list when no pattern matches. Each entry carries the pattern's id, name, reading, supporting_evidence (which specific frames triggered the match), trigger_genre, and load_bearing_dimensions.
- **Corpus prevalence per pattern.** Each triggered pattern carries `corpus_context` with `matches_count`, `total_corpus`, `match_rate`, `prevalence` (text), and `small_n_caveat`. The aggregator counts corpus entries matching the same frame-shape trigger; the genre constraint applies to the current document only (the corpus does not yet carry per-document genre classifications), named honestly in the caveat.
- **`corpus_intelligence.count_corpus_pattern_matches` added.** Walks the cached per-document fired sets, applies the pattern's frame-shape trigger conditions, returns counts. Reuses existing aggregator infrastructure.
- **`agent_guidance.how_to_render_divergence` step (6.7) added.** Teaches the frame_patterns layer: pattern reading as Frame Check's named composition, supporting_evidence as inline citation surface, corpus prevalence as empirical anchoring. Names the discipline that patterns are stronger evidence than per-frame walks (lead with the pattern reading when present).
- **`envelope.divergence_summary` updated.** Names the count of triggered patterns and their human-readable names when present.

Tests added (4 pattern regressions; 171 mcp_server tests pass via pytest):
- `test_divergence_carries_frame_patterns`: pins shape (id, name, reading, supporting_evidence, load_bearing_dimensions, corpus_context); pins agriculture-recommendation fixture triggers `recommendation-without-falsification`.
- `test_frame_patterns_no_match_yields_empty_list`: pins the always-present-as-list discipline.
- `test_pattern_corpus_prevalence_uses_corpus_aggregator`: pins corpus_context shape (matches_count, total_corpus, match_rate, prevalence text, small_n_caveat).
- `test_how_to_render_divergence_teaches_frame_patterns`: pins agent_guidance step (6.7) teaches recognized-shape composition + supporting_evidence citation.

This is the fifth move into the L4 territory of substrate-side composition. The substrate now reads "this document matches the 'recommendation-without-falsification' pattern (recommendation genre, failure-framing absence detected, risk frame and temporal anchoring not actively detected); observed in 4 of 10 corpus documents". That is a fully composed substrate reading: a recognized structural shape, named, anchored in evidence, before the agent composes a single sentence. Verified on the operator's agriculture-recommendation fixture: pattern triggers with 0.4 corpus match rate.

### Added (substrate-side composition Items 8/9/10: per-frame deepening)

Items 8, 9, and 10 of the substrate-side composition roadmap, shipped together as parallel surgical additions to three load-bearing FVS areas. Each gives the agent specific document-content evidence beyond the FVS firing/absence signal: temporal scope deepens FVS-014, stakeholder map deepens FVS-011, falsification conditions deepens FVS-007 and FVS-009.

The substrate stays deterministic. Each detection is regex-based or structural; no LLM is invoked. Each detector returns `null` when the document is below the 100-word floor (construct-honest abstention; the MCP response omits the corresponding sub-field rather than carrying empty placeholders).

- **`frame_deepening` module added.** New file at repo root (`frame_deepening.py`); bundles into the wheel via the existing flat py-modules layout. Exposes three detector functions: `detect_temporal_scope(text, current_year)`, `detect_stakeholder_map(text)`, `detect_falsification_conditions(text)`.

- **`analysis.frame_deepening` block on every frame_check response.** Three sub-fields:
  - `temporal_scope` (Item 8): years_referenced (sorted unique 4-digit years), classified by relation to current_year (near_now / historical / projection), plus decade_references, projection_phrase_count, retrospective_phrase_count, and scope_reading.
  - `stakeholder_map` (Item 9): roles_mentioned (subset of regulators, investors, customers, employees, competitors, communities, suppliers, management), per_role_mention_count, total_stakeholder_mentions, and scope_reading naming present and absent roles.
  - `falsification_conditions` (Item 10): primary_match_count and extracted_conditions (sentence previews containing "would be wrong if", "fails when", "the conclusion depends on", risk markers); candidate_match_count and candidate_conditions (conditional markers that may carry falsification framing); scope_reading naming the three cases (primary present / only candidates / neither).

- **`agent_guidance.composition_discipline` extended.** Names `analysis.frame_deepening` sub-fields as grounding measurements alongside the existing categories.
- **`agent_guidance.what_this_tool_tells_you` extended.** Lists the deepening sub-fields explicitly so the agent can find them.

Tests added (6 frame_deepening regressions; 177 mcp_server tests pass via pytest):
- `test_analysis_carries_frame_deepening_block`: pins block presence + three required sub-keys.
- `test_temporal_scope_extracts_years_and_projection_windows`: pins year extraction, classification (near-now / historical / projection), and scope_reading.
- `test_stakeholder_map_detects_role_categories`: pins eight role categories and absence-listing in scope_reading.
- `test_falsification_conditions_extracts_explicit_statements`: pins primary-match extraction and scope_reading discipline.
- `test_frame_deepening_returns_none_below_word_floor`: pins the construct-honest abstention path.
- `test_composition_discipline_names_frame_deepening`: pins agent_guidance teaches the deepening layer.

This is the sixth move into the L4 territory of substrate-side composition. Where the FVS detectors previously emitted only firing/absence signals at the frame level, the substrate now surfaces document-specific evidence per load-bearing frame: which years the document anchors itself in (temporal_scope), which stakeholder roles it carries and which it leaves out (stakeholder_map), and whether it explicitly names conditions under which its claims would be wrong (falsification_conditions). The agent composing a reading can cite specific extracted text rather than abstract presence/absence: "Document reasons across 2024-2030; what changes at 2035 figures?"; "Stakeholder roles absent: competitors, customers, employees; whose perspective would shift the framing?"; "Falsification statements present: 'would be wrong if carbon credit prices crashed'; is that condition precise enough to test?".

Verified on the operator's agriculture-recommendation fixture (extended with risk language): temporal_scope detects 2026 (near-now) and 2030 (projection); stakeholder_map detects investors and regulators (with customers/employees/competitors/etc. flagged absent); falsification_conditions extracts "the conclusion would be wrong if carbon credit prices crashed" and "the main risk is policy reversal under different administrations".

### Polish: construct-honest abstention across substrate composition

Stress-testing the substrate-side composition layers with fresh eyes surfaced two construct-honesty violations.

First, empty / very-short / non-English / code / poetry documents triggered absence clusters mechanically. With zero (or near-zero) FVS matches, `absent_frames` becomes the catalog itself; clusters then surface canon-graph structure rather than document signal. On Lorem ipsum at 160 words, the substrate composed three "load-bearing absence" clusters as if substantive analysis was meaningful.

Second, the genre classifier classified non-English Lorem ipsum and code as `analysis` with high confidence. The voice classifier produces a label on any text, and the genre scorer's voice contribution gave that signal enough weight to win when no English-feature regexes had matched and no claims had been detected. The substrate named a genre on text it could not analyze.

Both violations cascade: a misclassified genre then gates `frame_patterns` triggers (e.g., `analysis-without-grounding` fires on Lorem ipsum because misclassified genre + missing FVS-016 + missing FVS-012 all hold). One bad signal upstream produces several bad signals downstream.

Polish moves shipped:

- **`_build_absence_clusters` abstains on three off-methodology signals.** New gates: `document_word_count` below 100 (the same floor frame_deepening uses); `matched_frame_count == 0` (catalog set arithmetic without document signal); `document_claim_count == 0` (the claim extractor found no analytical content, even when an FVS detector fired vacuously). Each gate returns `[]` rather than fabricating clusters. Construct-honest: when there is no analytical signal, the substrate surfaces no composition.
- **`classify_genre` requires feature evidence.** New gate: when no feature regex matches AND no claims are detected, the classifier abstains with `genre=None`, `confidence='low'`, and a construct sentence explaining that voice classification alone is insufficient evidence for structural genre. Voice signal can no longer carry off-methodology text into a confident classification.
- **Cascade fixed.** With genre abstaining on off-methodology text, downstream layers (`frame_patterns`, genre-relative absence ranking) also abstain naturally. No mechanical false positives across the substrate.

Tests added (5 polish regressions; 182 mcp_server tests pass via pytest, 46 of 46 project suites pass via run_tests.py):
- `test_clusters_abstain_on_short_documents`
- `test_clusters_abstain_when_zero_frames_match`
- `test_clusters_abstain_when_zero_claims_detected`
- `test_genre_abstains_without_feature_evidence`
- `test_full_payload_abstains_construct_honestly_on_off_methodology`

Verified across the original stress matrix: empty / single-word / very-short / non-English / code / poetry inputs all yield `genre=None`, `absence_clusters=[]`, `frame_patterns=[]`. The agriculture-recommendation document at 152 words still composes its 3 clusters and 1 pattern correctly.

This is not a new substrate layer; it is the discipline that the existing layers were missing. The substrate composes when it has signal; it abstains when it does not. Same construct-honesty rule the per-frame deepening detectors already followed (Items 8/9/10 abstain below 100 words); now extended to clusters, patterns, and genre.

### Added (substrate-side composition Item 11: goal-aware divergence ranking)

Item 11 of the substrate-side composition roadmap, the last deterministic-only item before the Item 12 strategic reservation. The user (or agent on behalf of the user) signals a goal: `decide`, `brainstorm`, `persuade`, `learn`, `audit`. The divergence ranking shifts accordingly so the absences load-bearing for the user's stated intent rise within their tier.

The substrate stays deterministic. Per-goal maps are curated text; the relevance lookup is exact-match against canon FVS IDs; no LLM is invoked.

- **`user_goals` module added** (`user_goals.py` at repo root, bundled by the existing flat py-modules layout). Exposes `get_user_goals()`, `get_goal_load_bearing_frames(goal)`, `get_goal_relevance(fvs_id, goal)`. Curated load-bearing frame maps for five goals; `audit` is the default-equivalent posture with an empty map.
- **`user_goal` parameter on `frame_check`.** Optional enum (`decide` / `brainstorm` / `persuade` / `learn` / `audit`); validated by the dispatcher with a structured error response on invalid values. When omitted, behavior matches `audit`.
- **`goal_relevance` field on `absent_frames` records.** Carries `{relevant_for_goal, priority, reason}` when the user has signalled a goal and the absent frame is in that goal's load-bearing map. None otherwise.
- **`absent_frames` sort updated.** Now four-tier: `signal_strength` (catalog + coverage), `goal_relevance.priority` (user intent), `genre_relevance.priority` (document state), `frame_id` (stability). Goal precedes genre because user intent is a more direct signal than inferred document classification; signal precedes goal because empirical signal cannot be overridden by user preference.
- **`envelope.divergence_summary` updated to name the chosen goal and re-ranking note.** When `user_goal=audit`, summary explicitly names the sovereignty posture.

Tests added (5 goal regressions; 187 mcp_server tests pass via pytest):
- `test_user_goal_attaches_goal_relevance_to_absent_frames`
- `test_user_goal_promotes_goal_relevant_absences`
- `test_user_goal_audit_applies_no_override`
- `test_user_goal_invalid_value_rejected_by_dispatcher`
- `test_per_goal_load_bearing_maps_cover_all_goals`

Verified on the agriculture-recommendation document:
- `decide`: FVS-009 Risk Frame and FVS-014 Temporal Anchoring rise to the top of the high tier (priorities 2 and 3 in the decide map).
- `brainstorm`: FVS-001 Frame Amplification and FVS-009 Risk Frame rise (priorities 2 and 3 in the brainstorm map).
- `persuade`: FVS-017 False Balance jumps to the top with priority 1.
- `learn`: FVS-001 Frame Amplification and FVS-014 Temporal Anchoring rise (priorities 1 and 2 in the learn map).
- `audit` and no goal: identical orderings (audit is the default-equivalent posture).

This is the seventh and final move into the deterministic L4 territory of substrate-side composition. The substrate now reads "for the goal of deciding, the load-bearing absent frame is FVS-007 Failure Framing because recommendations without falsification conditions cannot be stress-tested at decision time" before the agent composes a single sentence. Item 12 (LLM-augmented frame-opportunity composition) remains as the strategic reservation that breaks the zero-LLM-cost moat; an explicit operator decision is required to ship it.

### Added (substrate-side composition Item 12: opt-in LLM-augmented frame opportunities)

The strategic reservation, ratified by explicit operator decision. Item 12 of the substrate-side composition roadmap is the only item that breaks the zero-LLM-cost moat the deterministic substrate has held until now. It is opt-in only via `include_frame_opportunities=true`; the default behavior is preserved deterministic substrate composition (Items 1-11).

The strategic discipline. The deterministic substrate (clusters, patterns, absences with goal/genre relevance, frame deepening, corpus context) is the irreducible identity of Frame Check. Item 12 is layered on top as a hybrid: the substrate identifies the load-bearing absent frames, then an LLM composes a document-specific question from the absent frame's teaching question + document content + user goal. The substrate is what is reproducible; the opportunities are what the substrate identifies as load-bearing made specific to this document.

The cost story. Each opportunity is one Gemini Flash call (~0.0001-0.0005 USD). Maximum 3 opportunities per request. Total bounded at ~0.001 USD per invocation when enabled. Cost is surfaced per-opportunity in `model_provenance.cost_usd` and at envelope level in `frame_opportunities.total_cost_usd`.

What lands:

- **`frame_opportunities` module added** (`frame_opportunities.py` at repo root, bundled by the existing flat py-modules layout). Exposes `generate_frame_opportunities(absent_records, document_text, document_genre, user_goal, max_opportunities, model)` returning the opportunities dict. Graceful degradation: returns empty list with `available=false` when GEMINI_API_KEY is missing or `google.genai` library is unavailable.
- **`frame_library.TEACHING_QUESTIONS` lookup added.** Canonical teaching questions for the 11 catalog FVS entries that ship one. Mirrors the questions the firing rules in `suggest_frames()` emit; available via `get_teaching_question(fvs_id)` for absent frames that never fire (and therefore never get a question via `_add()`). The lookup is the source of truth for `frame_opportunities` composition, so absent frames are paired with their canonical teaching question before LLM composition.
- **`include_frame_opportunities` parameter on `frame_check`.** Optional boolean (default `false`); validated by the dispatcher with structured error response on non-boolean values. When `false` or omitted, no LLM is invoked; the deterministic substrate composes alone.
- **`divergence.frame_opportunities` field on every divergence response.** Always present; carries `opportunities` (list of opportunity dicts), `total_cost_usd`, `available` (null when not invoked, true when invoked successfully, false when invoked but LLM unavailable), and a `note` field naming the opt-in discipline.
- **Each opportunity carries `model_provenance`** with provider (`gemini`), model (`gemini-2.5-flash`), `cost_usd`, `input_tokens`, `output_tokens`, and `is_deterministic=false`. The flag is the explicit construct-honesty signal that distinguishes LLM-generated content from deterministic substrate measurements.
- **`agent_guidance.frame_opportunities_discipline` field added.** Carries the five-rule discipline for surfacing opportunities: cite the is_deterministic flag, surface the cost, keep general teaching question alongside generated question, never present LLM content as Frame Check's measurement, handle graceful degradation as a feature rather than an error.
- **`agent_guidance.what_this_tool_tells_you` extended.** Names the optional opt-in opportunity layer with explicit cost + non-determinism flagging.

Tests added (4 frame_opportunities regressions; 192 mcp_server tests pass via pytest):
- `test_frame_opportunities_default_omitted` (pins moat-preserving default)
- `test_frame_opportunities_optin_populates_block` (end-to-end with graceful-degradation fallback)
- `test_frame_opportunities_carries_provenance_discipline`
- `test_frame_opportunities_invalid_value_rejected`

Verified on the operator's agriculture-recommendation document with `user_goal=decide` and `include_frame_opportunities=true`:
- Cost: 0.000282 USD for 3 opportunities (FVS-009, FVS-014, FVS-001).
- Each opportunity cites specific document phrases ("My Pick: Regenerative Ag", "turns the farm into a carbon vacuum", "data is the new topsoil") and applies the absent frame's perspective.
- Each carries `is_deterministic=false` and the model name in provenance.

This is the seventh and final move of the substrate-side composition roadmap, and the only one that breaks the zero-LLM-cost moat. The strategic posture is clear: the deterministic substrate (Items 1-11) is what Frame Check is. Item 12 is a hybrid layer that generates the user-facing forward-direction questions when the user explicitly requests them; absence of the flag preserves the original substrate behavior with no change in cost or determinism. Frame Check is the AI-era thinking substrate that does deterministic structural analysis by default and offers LLM-composed document-specific application when the cost is explicitly worth it.

### Polish: full-roadmap fresh-eyes review

End-to-end stress-testing the full roadmap across the six structural genres surfaced four real gaps. Each was a content-level discrimination problem rather than an architectural one.

- **Pattern triggers were too lenient.** `analysis-without-grounding` and `advocacy-without-counter-perspective` fired 10/10 in the corpus; the patterns surfaced as labels rather than discriminating compositions. Triggers depended on FVS detectors that rarely fire (FVS-016 needs sourced_pct >= 50%; FVS-017 is in the DEFERRED rule set and never fires positively). Polish: pattern triggers now accept frame_deepening + epistemic discriminators (`falsification_max_count`, `sourced_pct_max`, `stakeholder_role_count_max`) so they fire only when document content evidence confirms the structural shape. Updated patterns:
  - `recommendation-without-falsification` requires `falsification_max_count=0` (document must lack explicit "would be wrong if" statements).
  - `analysis-without-grounding` requires `sourced_pct_max=20` (analysis must have very low source attribution, not merely below the 50% citation-density firing threshold).
  - `advocacy-without-counter-perspective` requires `stakeholder_role_count_max=1` (advocacy must mention at most one stakeholder category, indicating structural one-sidedness).
- **Stakeholder regex missed politically-relevant categories.** The original eight categories (regulators, investors, customers, employees, competitors, communities, suppliers, management) did not catch policymakers, public/citizens/voters, fossil fuel industry / auto industry / sector actors, or affected populations like patients/students/workers in. Real coverage gap on advocacy and policy documents. Polish: added `policymakers`, `public`, `industry_actors`, `affected_populations` categories; total now 12.
- **Falsification regex missed conditional reasoning.** The "if X timeline holds / the argument rests on / if that turns out wrong" structures of analysis documents were not detected. Polish: added 7 new patterns covering `if (earlier|later|alternative) X holds`, `if that turns out wrong`, `the argument (rests|hinges|turns) on`, `could be wrong if`, `fails to account for`, `becomes wrong if`.
- **`divergence_summary` had grammar bug.** Singular/plural mismatch: "3 absent frames carries" should be "3 absent frames carry". Polish: genre_phrase and goal_phrase now use grammatical agreement.

Tests added (4 polish regressions; 196 mcp_server tests pass via pytest, 46 of 46 project suites pass via run_tests.py):
- `test_pattern_triggers_use_doc_signals_for_discrimination` (pins the discrimination logic on all three tightened patterns)
- `test_stakeholder_regex_covers_policymakers_public_industry`
- `test_falsification_regex_covers_conditional_reasoning`
- `test_divergence_summary_grammar_correct`

End-to-end verification on the six-genre fixture set:
- Patterns now fire only when truly discriminating: recommendation-with-explicit-falsification correctly suppresses the pattern; analysis-with-50%-sourced correctly suppresses; advocacy-with-6-stakeholder-roles correctly suppresses.
- Stakeholder regex catches all six advocacy stakeholders (policymakers, public, competitors, industry_actors, employees, affected_populations) on the longer fixture.
- Falsification regex catches at least 3 of the conditional reasoning patterns in the analysis fixture.

This is the final fresh-eyes pass on the deterministic substrate. The patterns are now discriminating compositions rather than genre labels; the regex coverage is proportionate to the documents the substrate analyzes; the prose is grammatically correct.

### Polish (Item E): genre-segmented corpus prevalence + classifier bug fix

The highest-leverage real opportunity from the post-roadmap fresh-eyes review: corpus statistics previously mixed all genres into a single denominator ("fires in 3 of 10 corpus documents"), making expert-defensible interpretation impossible. With genre segmentation, the same data reads "fires in 1 of 5 recommendation-genre corpus documents (20%)"; like-vs-like comparison, small-N honestly named.

This commit ships E plus a related classifier bug fix that surfaced during implementation.

- **Classifier bug fix.** `genre_classifier.classify_genre` previously had an evidence gate that abstained when no feature regex matched AND no claims were detected. The hole: when claims existed but no feature regex matched, advocacy received a 1.5 baseline score from `(1.0 - hedge_ratio) * 1.5`, classifying every unhedged claim-bearing document as advocacy with high confidence. On the operator's bitcoin-claude corpus document (zero advocacy markers, zero recommendation markers, all claims unhedged), the classifier returned advocacy with 100% confidence; clearly wrong. Polish: the gate now requires `feature_total > 0` regardless of claims; voice + hedge ratio alone are not sufficient evidence.
- **Recommendation regex expanded** to catch contractions and common LLM-output patterns: `i'd recommend`, `i'd lean toward`, `you'd want to`, `my (direct) recommendation is`, `(should|could) be considered`, `as a core (holding|investment|position)`. Caught the bitcoin-claude doc's "I'd lean toward no as a core retirement holding" structure that the original regex missed.
- **Corpus aggregator classifies each entry by genre at lazy-load time.** New `_classify_corpus_entry_genre(slug_dir)` runs `classify_genre` with `analyze_claims` and `detect_voice` on the corpus document.md. Stores genre per slug in `state.per_document_genre`; aggregates into `state.per_genre_counts` with `_unclassified` bucket for abstentions.
- **`corpus_summary.per_genre_counts` field added.** Surfaces the per-genre denominator distribution at envelope level. Includes `_unclassified` bucket so the agent can see how much of the corpus is in unsegmentable territory. The small_n_caveat names the segmentation discipline.
- **Per-frame `corpus_context.fires_in_by_genre` field added.** Each entry carries `fires_in_count`, `genre_total`, `rate`. Agents can now report "FVS-008 fires in 1 of 5 recommendation-genre corpus documents (20%)" instead of mixing genres into a 3-of-10 number.
- **Per-pattern `corpus_context.genre_segmented_prevalence` field added.** When a pattern has a genre constraint, the corpus context surfaces both the full-corpus match rate (for reference) and the segmented match rate (the like-vs-like comparison). Shape: `{matches_in_genre_count, genre_total, genre_match_rate, trigger_genre, genre_segmented_prevalence (text), small_n_caveat (segmentation discipline)}`. Patterns without a genre constraint surface only the full-corpus rate with a small_n_caveat noting segmentation is not applicable.
- **`count_corpus_pattern_matches` extended.** Returns both `matches/total/match_rate` (full corpus) and `matches_in_genre/genre_total/genre_match_rate` (genre-segmented). Backward-compatible: existing callers still get the full-corpus fields.

Tests added (4 segmentation regressions; 200 mcp_server tests pass via pytest, 46 of 46 project suites pass via run_tests.py):
- `test_corpus_carries_per_genre_segmentation` (pins per_genre_counts shape, sums to n_documents, names segmentation discipline)
- `test_per_frame_corpus_context_carries_fires_in_by_genre`
- `test_pattern_corpus_context_carries_genre_segmented_prevalence`
- `test_genre_classifier_requires_feature_evidence` (pins the classifier bug fix; factual numeric reports without feature markers must abstain)

Verified on the validation corpus (10 documents):
- Distribution: 5 recommendation, 2 narrative, 1 advocacy, 2 unclassified.
- FVS-008 Growth Frame: fires in 1 of 5 recommendation docs (20%), 1 of 2 narrative docs (50%), 0 of 1 advocacy doc, 1 of 2 unclassified docs.
- Pattern `recommendation-without-falsification`: matches frame-shape in 4 of 10 corpus docs (40%) but only 1 of 5 recommendation-genre docs (20%); segmented rate shows the pattern is less common when restricted to its target genre, which is signal the mixed denominator hid.

This is the foundational polish move: every future statistical claim Frame Check makes about its corpus is now genre-aware automatically. As the corpus scales (10 docs → 100 → 1000), segmented Ns become statistically meaningful while keeping the per-genre comparison honest. The infrastructure is in place before scale.

### Polish (E1): low-N warnings + segmentation discipline in agent_guidance

Stress-testing E surfaced three real gaps. Per-genre rates were emitted without flagging when the denominator was statistically meaningless (advocacy: N=1 means 0% or 100% rates). The `_unclassified` bucket appeared alongside genre buckets without explicit guidance that it is documents whose structural shape couldn't be inferred (not a genre). agent_guidance taught corpus_context broadly but did not teach the segmentation discipline concretely.

- **`low_n_warning` field per-genre stat in `fires_in_by_genre`.** True when `genre_total < 3`. The substrate flags small-N denominators rather than letting the agent cite a 100% rate over N=1 as if statistically calibrated.
- **`is_unclassified_bucket` field per-genre stat.** True for the `_unclassified` key, False for actual genres. The agent reading the JSON sees the explicit distinction.
- **`genre_segmented_low_n_warning` field on pattern corpus_context.** Same logic for pattern-segmented prevalence: when the trigger genre has fewer than 3 corpus documents, flag the rate as not statistically meaningful.
- **Pattern `small_n_caveat` adapts to low-N case.** Two distinct caveat texts: one when N is meaningful (segmented is the like-vs-like comparison), one when N < 3 (do not cite as population estimate).
- **`agent_guidance.how_to_render_divergence` step (7.1) added.** Teaches the genre-segmented prevalence discipline concretely: prefer segmented denominator over full-corpus rate; honor low_n_warning; NEVER cite the _unclassified bucket as a genre; for patterns, segmented prevalence is the primary citation with full-corpus as reference.

Tests added (3 polish regressions; 203 mcp_server tests pass via pytest):
- `test_per_genre_stats_carry_low_n_warning` (pins low_n_warning + is_unclassified_bucket flags + invariants)
- `test_pattern_segmented_prevalence_carries_low_n_warning` (advocacy N=1 → True; recommendation N=5 → False)
- `test_segmentation_discipline_in_agent_guidance` (pins concrete discipline language)

This polish closes the loop on E. The substrate now surfaces segmented prevalence with explicit construct-honesty flags so agents can reason about denominator quality without needing to compute N thresholds themselves.

### Added (D): pattern catalog 4 to 8 with new signal discriminators

The next compounding move after E. Pattern catalog expanded from four patterns to eight, each curated to identify a discriminating structural shape rather than a genre label. New patterns inherit the genre-segmented corpus prevalence from E automatically, so reports like "matches in 1 of 5 recommendation-genre corpus documents" are like-vs-like from the moment a pattern is added.

The substrate stays deterministic. New pattern triggers are extended with three new doc_signal keys plumbed through `_build_document_signals`: `projection_phrase_count` (from `frame_deepening.temporal_scope`), `voice_label` (from `voice.classification`), and `hedge_ratio` (computed from `claims_extracted`). The pattern matcher gains four new constraint kinds: `_min` (signal must be present and >= threshold; abstains on signal absence), `voice_match` (signal must equal expected string), `hedge_ratio_max` (lenient `_max` semantic), and a paired `_min`/`_max` idiom for strict-equality constraints.

Bug fix surfaced during implementation: `doc_signals` plumbing in `_build_divergence_block` was forwarding only three keys (`falsification_count`, `stakeholder_role_count`, `sourced_pct`) from the function parameter to `match_patterns`, silently dropping the new signal keys. Fixed by replacing the inline rebuild with `dict(document_signals or {})`. Without this fix, new patterns dependent on `voice_label` or `projection_phrase_count` would silently fail to fire even when their conditions were met.

Four new patterns:

- **`narrative-without-stakeholders`**: `genre=narrative` AND `stakeholder_role_count` exactly 0 (signal must be present and zero; pattern abstains on short documents where frame_deepening returns None). Story without people; events without perspective. Load-bearing dimension: coverage.
- **`instruction-without-failure-modes`**: `genre=instruction` AND FVS-009 Risk Frame absent AND `falsification_count = 0`. Procedural document presents steps as if they cannot fail; troubleshooting scaffold is missing. Load-bearing dimension: counterfactual.
- **`forward-projection-without-anchoring`**: genre-agnostic. `projection_phrase_count >= 2` AND `falsification_count = 0`. Document makes substantial forward-looking claims (phrases like "by 2030", "next decade", "in five years") without naming validity windows or conditions under which projections would be revised. Load-bearing dimensions: counterfactual, calibration.
- **`cited-but-promotional`**: FVS-016 Authority by Citation fires AND `voice_label = promotional`. Citations carried in promotional register; structural shape that can mask cherry-picking. Distinct from `analysis-without-grounding` which fires when citations are absent. Load-bearing dimension: evidence.

Tests added (5 D regressions; 208 mcp_server tests pass via pytest, 46 of 46 project suites pass via run_tests.py):
- `test_pattern_catalog_has_eight_patterns` (pins catalog size and IDs; substantive readings >= 100 chars)
- `test_narrative_without_stakeholders_pattern` (fires on stakeholder_role_count==0; abstains on signal None; no-fire on stakeholders present)
- `test_instruction_without_failure_modes_pattern` (fires on full triggers; no-fire when falsifications present)
- `test_forward_projection_without_anchoring_pattern` (fires on >=2 projections + zero falsifications; no-fire on single projection phrase)
- `test_cited_but_promotional_pattern` (fires on FVS-016 + voice=promotional; no-fire on analytical voice; abstains on signal None)

Verified on dedicated genre fixtures:
- Narrative fixture (events without people, 116 words above floor): narrative-without-stakeholders fires; forward-projection-without-anchoring also fires (the narrative has multiple "By 2014, By 2017, By 2020" projections without anchoring conditions).
- Instruction fixture (5-step setup guide without troubleshooting): instruction-without-failure-modes fires.
- Forward-projection fixture (heavy future-oriented, 12 projection phrases): forward-projection-without-anchoring fires.
- Cited-promotional fixture (heavy citations + promotional voice): cited-but-promotional fires; sourced_pct=62%.

Each new pattern is a discriminating composition, not a label. Combined with E's genre-segmented prevalence, the substrate now reports patterns with both structural identification and like-vs-like corpus anchoring. The substrate composes more recognizable shapes per document, with stronger empirical grounding per shape.

### Polish (C): frame_opportunities prompt enriched with substrate composition

The final move in the post-roadmap polish sequence. Item C of the real-opportunities review: the frame_opportunities LLM prompt previously fed the LLM the absent frame in isolation (frame name, teaching question, genre, goal, document excerpt). With E and D shipped, the substrate has richer composition (cluster readings, pattern readings, segmented corpus prevalence) that the LLM should consume.

Now the prompt carries:

- **Cluster readings** from `divergence.absence_clusters[*].reading`: the dimension-level themes the substrate identified.
- **Pattern readings** from `divergence.frame_patterns[*].reading`: named structural shapes the substrate matched.
- **Per-frame corpus context** from the absent frame's `corpus_context`: segmented prevalence (genre-by-genre rates, with `_unclassified` filtered out and `low_n_warning` flagged inline) plus full-corpus reference.

Two new helper functions in `frame_opportunities.py`:
- `_build_substrate_context_block(cluster_readings, pattern_readings)` formats the substrate composition section. Empty when both lists are empty.
- `_build_corpus_context_block(absent_frame)` formats the per-frame corpus prevalence section. Skips the `_unclassified` bucket (does not emit confused-signal to the LLM); flags low-N genres inline.

Wired through `mcp_server.py`: the divergence builder extracts cluster_readings and pattern_readings from the just-built absence_clusters and triggered_patterns lists, passes them to `generate_frame_opportunities`. Per-frame corpus_context is already attached to absent_records.

Tests added (1 prompt-structure regression; 209 mcp_server tests pass via pytest):
- `test_frame_opportunities_prompt_carries_substrate_context` (pins the prompt template placeholders + helper function semantics including _unclassified filtering)

Verified end-to-end on the agriculture-recommendation document with `user_goal=decide`:

Before C, the LLM-generated question for FVS-001 Frame Amplification was generic ("what specific data collection requirements would Regenerative Agriculture entail beyond merely 'turning the farm into a carbon vacuum'?"). 

After C, the same call produces: "if this analysis were explicitly named as being framed by 'optimizing agri-tech for investor financial return on carbon assets,' what alternative perspectives, such as impacts on water availability or biodiversity beyond carbon, might be prompted for consideration, especially given the document's broad absence of coverage for other viewpoints?" The question now explicitly cites the substrate's coverage cluster reading and the Frame Amplification's perspective in concert. Cost increased from 0.000282 to 0.000545 USD per invocation due to the larger prompt; still well under the 0.001 USD bound per request.

This closes the post-roadmap real-opportunities loop. The four real opportunities (E, E1, D, C) are all shipped. The substrate composes:
- Catalog assertion (FVS firings)
- Coverage measurement
- Genre classification
- Per-frame deepening (temporal, stakeholder, falsification)
- Goal-aware ranking
- Genre-relative ranking
- Dimension clusters
- Named patterns (catalog of 8)
- Corpus prevalence (genre-segmented)
- LLM-augmented opportunities (opt-in, consuming all the above)

The agent reading a frame_check response with full divergence + opt-in opportunities now has: structural identification, dimension-level themes, named patterns, empirical anchoring (segmented), and document-specific generated questions (substrate-grounded). All composed before the agent writes a single sentence.

### Polish (post-Claude-Desktop): cite-by-name discipline for cluster dimension + pattern id

The operator tested the post-D-and-E substrate in Claude Desktop. The agent's reading composed an excellent insight-led response with cited measurements, construct-honest cascade observations, and reading-form throughout. But the substrate's distinct named compositions (cluster.dimension, pattern.id) were paraphrased rather than cited by name. The agent said "Four high-signal absent frames cluster on the same blind spot" instead of "Frame Check identified a counterfactual cluster"; never cited the recommendation-without-falsification pattern by id even though it matched.

The result: the substrate's distinctness was invisible to the user. The user reading the response sees "the agent's reading" rather than "the agent citing Frame Check's substrate-side composition".

Polish: `agent_guidance.composition_discipline` now explicitly instructs CITE THE PATTERN BY ITS id and CITE THE CLUSTER BY ITS dimension name. The discipline names why: the dimension name is canon-graph anchored and lets the user trace the cluster to decision-readiness methodology; the pattern id makes the substrate's named identification visible to the user; paraphrasing as "blind spot" or generic "theme" hides what the substrate composed.

Tests added (1 polish regression; 210 mcp_server tests pass via pytest):
- `test_composition_discipline_nudges_cite_by_name` (pins both CITE-THE-PATTERN-BY-ITS-id and CITE-THE-CLUSTER-BY-ITS-dimension instructions in agent_guidance)

This is the visibility polish: the substrate now produces named compositions (E + D), and the agent now has explicit instruction to surface those names. The user reading the next Claude Desktop test should see "Frame Check identified the counterfactual cluster" or "this matches Frame Check's recommendation-without-falsification pattern" rather than agent-paraphrased prose.

### Added (substrate-side composition L5 interface UX Step 3: how_to_map_user_intent agent guidance)

Step 2 shipped the user-intent vocabulary at the prompt-arguments layer (depth/goal/questions). But the agent invoking those prompts on behalf of the user (when the user types natural language rather than structured arguments) still has no explicit guidance for translating "I'm trying to figure out whether to ship this" into `goal=decide`. Without guidance, the agent guesses; the user-intent layer (Step 2) is invisible to the agent.

This commit adds `agent_guidance.how_to_map_user_intent` to every `frame_check` response. The new key teaches the calling agent to translate natural-language user requests into the option space the four sovereignty prompts expose. Each axis (depth, goal, questions) gets concrete user-phrase → argument mappings:

- `quick check` / `TL;DR` / `fast read` → `depth=quick`
- `careful audit` / `deep dive` / no qualifier → `depth=thorough`
- `I'm trying to decide whether to` / `should I` → `goal=decide`
- `what am I missing` / `gaps in this` → `goal=audit`
- `challenge this` / `play devil's advocate` → `goal=challenge`
- `help me explore options` → `goal=explore`
- `teach me about the framing` / `walk me through` → `goal=learn`
- `questions to think about` / `help me question this` → `questions=yes`

The guidance also names the discipline:
- Surface chosen options briefly to the user before invoking ("I'll do a thorough decision-focused audit") so the user can adjust.
- Default to safe values on ambiguity (depth=thorough; goal=audit; questions=no; opportunities are opt-in for cost reasons).
- Honor explicit prompt arguments verbatim; do not override with inference.

Pure guidance addition; no substrate behavior change. Backwards-compatible: agents that ignore the new key continue to work; agents that read it stop guessing.

Test added (1 new; 228 mcp_server tests pass via pytest, 47 of 47 project suites pass via run_tests.py):
- `test_agent_guidance_carries_how_to_map_user_intent`: pins the key's presence, the three argument axes named, concrete mappings per axis, the surface-chosen-options discipline, the default-on-ambiguity discipline, and the honor-explicit-arguments discipline.

This completes the three-layer interface UX (Step 2 + Step 3): prompt arguments (user-vocabulary surface), MCP-parameter translation (prompt body internals), and agent guidance for natural-language mapping (when the user does not type arguments directly). Three years out, a user typing "I want to challenge this analysis" gets a thorough adversarial reading without typing any parameters; the agent receives explicit translation guidance from the substrate; the substrate composes per the user's stated goal.

### Added (substrate-side composition L5 interface UX: compose_budget + sovereignty prompt user-intent arguments)

The L5 framework distinguishes per-level claims structurally but the user-facing surface still uses developer-facing parameter names (`include_divergence`, `user_goal`, `include_frame_opportunities`) that the end user does not share. The agent invoking the substrate has no guidance for mapping natural-language user intent (decide / explore / audit / challenge / quick / thorough) to MCP parameter values. This commit ships the user-intent vocabulary at the prompt arguments layer plus the bounding mechanism the substrate needed (compose_budget) so an agent in a tight working-memory budget can request a compact reading without losing structural shape.

**`compose_budget` MCP parameter on `frame_check`**.

Optional enum (`minimal` / `standard` / `full`; default `full` for backwards compat). Bounds the substrate's output volume:

- `minimal`: top-3 absent_frames, top-1 absence_cluster, top-1 frame_pattern. For agents in tight working-memory budgets (quick responses).
- `standard`: top-5 absent_frames, all clusters, all patterns. Middle ground; preserves cluster + pattern surfaces.
- `full` (default): unfiltered. Backwards-compatible; existing callers see no change.

Implementation: slicing happens in `_build_divergence_block` AFTER the envelope is built so `envelope.tier_counts` reflects PRE-slice counts (the agent sees the truncation honestly rather than thinking the substrate found fewer absences). New `divergence.compose_budget_applied` field surfaces the slice level + per-layer returned/total counts so the agent can render "Frame Check identified N absences; showing top M".

**Sovereignty prompt user-intent arguments** (the operator's central UX call-out).

Each of the four sovereignty prompts (`frame_check_my_response`, `frame_check_this_ai_response`, `challenge_document`, `explain_framing`) gains three optional arguments that surface user-intent vocabulary:

- `depth`: `"quick"` | `"thorough"` (default `thorough`). Maps to `compose_budget=minimal|full`.
- `goal`: `"decide"` | `"explore"` | `"audit"` | `"challenge"` | `"learn"` (default `audit`). Maps to `user_goal` (decide → decide; explore → brainstorm; challenge → audit + adversarial composition note; learn → learn; audit → audit).
- `questions`: `"yes"` | `"no"` (default `no`). Maps to `include_frame_opportunities=true|false`.

The user types in their own vocabulary (depth / goal / questions); the prompt body that goes to the agent contains the translated MCP-layer values (compose_budget / user_goal / include_frame_opportunities). The user's mental model ("quick fast read" vs "thorough deep audit") translates to the substrate's parameter shape; the user does not need to know what `compose_budget` is.

`goal=challenge` injects an adversarial composition note into the prompt body that directs the agent to compose the insight as questions surfacing structural weaknesses (per `agent_guidance.composition_discipline` rule 5, the questions are reading-form not prescriptive).

Implementation: new helpers `_translate_prompt_arguments` (user-intent → MCP-parameter values + the challenge note) and `_populate_prompt_body` (replaces `<<PLACEHOLDER>>` tokens in the prompt body with the values). `<<KEY>>` placeholder format chosen to avoid colliding with the literal `{slug}` placeholder in `_PROMPT_EXPLAIN_FRAMING`. Invalid argument values fall back to defaults (do not raise; prompts are user-invoked surfaces and rejecting an invalid value would be poor UX).

Backwards-compatible: omitting all three arguments produces the same prompt body the prior version produced (default values match prior behavior). Existing MCP integrations are unaffected.

Tests added (5 new + smoke test infra; 227 mcp_server tests pass via pytest, 47 of 47 project suites pass via run_tests.py):
- `test_compose_budget_full_preserves_current_behavior`: pins backwards compat (omitted = full).
- `test_compose_budget_minimal_filters_top_n`: pins top-3/top-1/top-1 slicing + envelope.tier_counts honesty (PRE-slice counts).
- `test_compose_budget_invalid_value_rejected`: pins dispatcher rejection with structured error naming the valid enum.
- `test_sovereignty_prompts_advertise_user_intent_arguments`: pins all four prompts advertise depth/goal/questions in `prompts/list`.
- `test_prompt_arguments_translate_to_mcp_parameters`: pins user-intent → MCP-parameter translation (depth=quick → compose_budget=minimal; goal=explore → user_goal=brainstorm; goal=challenge → user_goal=audit + ADVERSARIAL CHALLENGE note; invalid values fall back to defaults).

This is the load-bearing UX move: the user now invokes `/frame_check_my_response` with `depth=thorough` and `goal=decide` in their own vocabulary, and the agent receives a prompt that directs it to call `frame_check(...,compose_budget=full, user_goal=decide, include_frame_opportunities=false)`. Three years out, the four sovereignty prompts plus the structured arguments are the user-facing interface; users navigate by intent, not by parameter.

### Polish: genre classifier recommendation-marker categorical bonus + frame_opportunities test resilience

The first adversarial fixture (`sales_pitch_as_analysis`) identified two per-level tightening moves: a citation-form date discriminator (audit's first recommendation, which turned out to be **wrong** on diagnosis) and a recommendation-marker floor (audit's second recommendation, which is correct). This commit ships the second; the first is documented as a corrected diagnosis (premature convergence on a speculated cause was caught by tracing what actually fired).

**Genre classifier (classifier_output level): recommendation-marker categorical bonus.**

When explicit pick markers fire above zero (`rec_count > 0`), recommendation gets a +5.0 categorical bonus on top of the density scoring. Pick markers ("I would lean toward", "I recommend", "the best option", "core position", "my pick") are high-precision evidence that the document positions itself to name a pick; the categorical bonus prevents competing genres' density signals (narrative density from sentence-internal `in YYYY` references; alternative-surveying density from one-hand/other-hand framing) from overriding when the document explicitly states a pick. The density component still rewards documents with multiple pick markers more highly; the categorical component says presence-at-all is meaningful.

Calibrated against the adversarial fixture: 2 narrative-anchor matches (`in 2026` from the title, `in 2022` from the body) had pushed narrative score to ~9.3 and overrode the explicit "I would lean toward" pick scoring ~6.2; the +5.0 floor brings recommendation to ~11.2, restoring correct classification (recommendation, borderline, runner-up narrative) without lowering the narrative weight.

Calibration verified against the validation corpus (10 documents): all preserve their prior genre classifications (5 recommendation, 2 narrative, 1 advocacy, 2 unclassified). No regressions.

**Corrected diagnosis on the citation-form discriminator.** The original fixture audit speculated that "the narrative regex matches dated citation patterns" and recommended a citation-form discriminator. **Tracing what actually fired revealed this was wrong.** Citation forms like `(CCAF, 2025)` do NOT match the narrative regex `\b(in (19|20)\d{2}|...)\b` (no `in` prefix). The actual narrative matches in the fixture were two `in YYYY` patterns (`in 2026` from the title, `in 2022` from the body). The corrected diagnosis is documented in `data/adversarial_fixtures/sales_pitch_as_analysis/audit.md` so the discipline (trace before recommending tightening; don't speculate about causes) is on the record.

**Substance check on falsification: deferred.** The fixture's "would be wrong if regulatory posture shifted abruptly" satisfies `recommendation-without-falsification`'s `falsification_max_count=0` and prevents the pattern from firing despite genre now being correctly recommendation. A reliable substance check would distinguish substantive falsifications (named numerical thresholds, specific scenarios, time-bounded conditions) from token disclaimers (vague macro categories), but is hard to operationalize as deterministic regex without overfitting; would require either operator decision to allow LLM-augmented pattern detection or a separate "recommendation-with-token-disclaimer" pattern. Out of scope; documented in audit.md.

**Test resilience: third graceful-degradation path on `test_frame_opportunities_optin_populates_block`.** The test previously had two paths: `available=False` (key/library missing → opportunities=[]) and `available=True` (LLM responsive → opportunities populated). A third path was missing: `available=True` (key/library present so `_is_gemini_available()` returned True) but the API call(s) returned None (transient API failure, rate limit, network blip), yielding `opportunities=[]`. The substrate's contract is "graceful degradation as a feature, not an error" (frame_opportunities_discipline rule 5); the test now honors that by accepting the empty-opportunities case rather than treating it as a regression.

Tests: 222 mcp_server tests pass via pytest (was 219 before the L5 series; +3 from L5 framework + adversarial fixture infra; this commit fixed 1 flaky test by adding the third graceful-degradation path; same 222 pass count). 47 of 47 project suites pass via run_tests.py. The adversarial fixture's `expected.json` updated to reflect the post-fix reading; `audit.md` extensively rewritten with the corrected diagnosis, the shipped fix, and the deferred substance-check work.

This is the audit-then-tighten discipline working in practice: the adversarial fixture identified gaps; one was correctly diagnosed (recommendation-marker floor) and shipped; one was incorrectly diagnosed (citation-form discriminator) and the diagnosis was corrected via tracing; one was correctly diagnosed but is a harder design problem (substance check) and is deferred with rationale. The fixture is the regression bar that future tightening will continue to test against.

### Added (adversarial fixture suite: operational test of L5 per-level construct treatment)

The L5 framework needs operational validation. Adversarial fixtures are the operational test: each fixture is a deceptive document composed by a hypothetical motivated writer who wants their pitch / advocacy / analysis to evade Frame Check's structural pattern detection. The fixture exposes which per-level claim discipline catches the deception and which fails to.

- **`data/adversarial_fixtures/` directory added** with `README.md` naming the discipline (compose ONCE, capture, audit honestly; read per-level not as overall pass/fail; tightening moves are evaluated separately, not bolted onto the fixture). Each fixture subdirectory carries `document.md` (the deceptive document), `expected.json` (substrate's reading captured at fixture composition time, the regression baseline), `audit.md` (per-level catch-vs-miss analysis with per-level tightening proposals).
- **First fixture: `sales_pitch_as_analysis/`**. An investment-recommendation document (Bitcoin core position) composed to look like balanced analysis: cited multi-source evidence (CCAF, BIS, Fidelity, Glassnode), explicit pick markers ("I would lean toward", "core 5-10% position"), generic risk disclaimer ("would be wrong if regulatory posture shifted"), 5 stakeholder roles named, analytical voice register. Targets the recommendation-without-falsification, advocacy-without-counter-perspective, and cited-but-promotional patterns simultaneously.
- **Headline finding from fixture #1**: the genre classifier's narrative regex matches dated citation patterns ("CCAF, 2025", "BIS WP 1198, 2025", "Glassnode December 2025") at high enough density to overwhelm recommendation markers. **Genre flips to `narrative` with HIGH confidence**, gating ALL recommendation-genre patterns. Zero patterns trigger despite the document being explicitly a recommendation. The substrate's clusters and decision_readiness readings DO catch the structural weaknesses (3 high-signal clusters: calibration, counterfactual, coverage) but the named-pattern layer is silent. A motivated writer can defeat the recommendation-genre patterns by adding cited-source dates.
- **Per-level tightening moves the fixture identifies** (documented in audit.md, NOT shipped as part of this commit): (a) genre classifier should distinguish citation-form dates from narrative-event dates (parenthetical-date forms are bibliography, not narrative anchors); (b) recommendation marker floor (when explicit pick markers fire above zero, recommendation gets a guaranteed minimum score that prevents narrative density override); (c) substance check on falsification statements (token disclaimers should not satisfy recommendation-without-falsification's threshold; either substance-check via LLM in Item 12 territory or threshold lift to require multiple substantive falsifications).

- **`test_adversarial_fixtures.py` regression module added**. Loads each fixture's document.md, runs build_epistemic_payload, compares specific captured fields (genre, voice, temporal, frame_library_matches, frame_deepening, epistemic_sourced_pct, decision_readiness signal_text, absence_clusters with frame_id list and signal_strength, frame_patterns with id) against expected.json. Field-by-field comparison so failure messages name which field diverged. Pinned: each fixture has all three required files; suite has at least one fixture; per-fixture reading matches baseline. Three test entries pass.
- **Wired into `run_tests.py`**. Project suite count moves from 46 to 47.

Tests added (3 fixture regressions; mcp_server.py untouched; 219 mcp_server tests still pass via pytest, 47 of 47 project suites pass via run_tests.py with adversarial_fixtures included).

This is the substrate's first operational defense infrastructure. The fixture itself is the load-bearing artifact; the per-level audit document is the strategic product (it tells the operator where to invest tightening effort). Three years out, the suite has 30+ fixtures across genre boundaries and deception shapes; each substrate tightening is regression-tested against the prior fixtures. Today: one fixture, one audit, one regression module. The shape is the commitment.

### Added (substrate-side composition L5 coverage: decision_readiness dimensions)

The L5 framework's last visible coverage gap closed. `analysis.decision_readiness.dimensions` carries five per-dimension dicts (coverage / calibration / evidence / robustness / counterfactual) each with curator-authored `signal_text`. They are structurally `composed_pattern` (deterministic trigger over multi-feature scoring + curator-authored reading) but were not tagged.

- **Each per-dimension dict carries `claim_level=composed_pattern`** so the agent honors the per-level discipline (cite the trigger as deterministic AND the signal_text as Frame Check's curator reading) rather than treating the prose as a measurement. Decoration happens at the mcp_server.py wrapping point (where `compute_decision_readiness` output is wired into `analysis`); `decision_readiness.py` itself is unchanged so other consumers (web app surface) are not affected.

Test added (1 new; 219 mcp_server tests pass via pytest, 46 of 46 project suites pass via run_tests.py):
- `test_decision_readiness_dimensions_carry_claim_level`: pins `claim_level=composed_pattern` on each of the five canonical dimensions in `analysis.decision_readiness.dimensions`. Uses the recommendation fixture (operator's agriculture pattern, paraphrased) which carries enough framing + claims data to populate the profile.

The L5 framework now covers every composed entity in the `frame_check` analysis surface: detector measurements (frame_library_matches entries, absent_frames records, frame_deepening parent block), classifier outputs (voice, genre, temporal), composed patterns (absence_clusters, frame_patterns, decision_readiness dimensions), and agent_generated content (Item 12 frame_opportunities). Same coverage on `frame_compare` (per-document voice, temporal, frame_library_matches; agent_guidance carries the shared treatments dict).

### Added (substrate-side composition L5 completion: agent_generated claim level)

The L5 framework's coverage gap closed. Item 12 frame_opportunities are opt-in LLM-composed content; until now they carried `is_deterministic=false` per-opportunity in `model_provenance` but no per-level discipline at the structural level. This release adds the fourth claim level `agent_generated` so the L5 framework covers all kinds of substrate output.

- **New constant `_CLAIM_LEVEL_AGENT_GENERATED = "agent_generated"`** plus the corresponding entry in `_CLAIM_LEVEL_TREATMENTS`. The treatment is the only level with `validation_status.deterministic = False` (the other three are deterministic by design); IRR is `not_applicable` because different models or runs producing different content is the design, not a validity gap; `validity_data` names that the per-output `model_provenance` is the audit trail and that the substrate-deterministic identity is preserved (when the opt-in flag is omitted, the substrate composes without LLM).
- **Each opportunity dict carries `claim_level=agent_generated`**. The existing `is_deterministic=false` flag in `model_provenance` is preserved (per-opportunity construct-honesty signal); `claim_level` is the structural signal at the per-level discipline.
- **`composition_discipline` rule (6) updated to four levels.** Names `agent_generated` alongside detector_measurement / classifier_output / composed_pattern; the closing sentence updates from "three epistemic claim levels" to "four". The agent's per-level treatment instruction now includes "agent_generated content surfaces the model provenance and cost AND is never presented as Frame Check's measurement".
- **Forward-compat shipping.** The previous `test_claim_level_treatments_carries_required_levels` test (renamed from `_carries_three_levels` for accuracy) was already designed with subset assertion not exact equality, so adding the fourth level required no test change at the foundational layer.

Tests added (1 new + 1 updated; 218 mcp_server tests pass via pytest, 46 of 46 project suites pass via run_tests.py):
- `test_agent_generated_claim_level_for_opportunities`: pins the agent_generated treatment in `claim_level_treatments` (deterministic=False, IRR not_applicable, validity_data names model_provenance, how_to_cite directs to model_provenance), pins the fourth level named in composition_discipline, and pins claim_level on each opportunity when LLM is available. Graceful-degradation path covered (treatments-shape only when LLM unavailable).
- `test_frame_opportunities_optin_populates_block` extended to assert `claim_level=agent_generated` on each populated opportunity.

Verified end-to-end on the operator's agriculture-recommendation fixture with `include_frame_opportunities=true` and `user_goal=decide`: 3 opportunities populate, each carrying `claim_level=agent_generated` plus the existing `model_provenance.is_deterministic=false`. The L5 framework now covers all four kinds of substrate output (deterministic detectors, deterministic classifiers, deterministic composed patterns, opt-in non-deterministic agent-generated content) under one per-level discipline.

### Added (substrate-side composition L5: per-level construct treatment)

The next L4 of substrate-side composition is not more composition; it is per-level epistemic discipline. The substrate produces three qualitatively different kinds of claim, each with its own construct discipline. Until now those kinds were conflated under one uniform `composition_discipline`. This release ships per-level `claim_level` metadata on every composed entity plus a per-level treatment dict in `agent_guidance.claim_level_treatments` that is keyed by claim_level value and carries structured validation_status (deterministic / methodology_documented / inter_rater_reliability / validity_data) plus per-level caveats and how-to-cite phrasing templates.

Why this is the L5 territory. External evaluation needs a clear epistemic claim chain to evaluate: today the substrate's claims are uniform under one composition_discipline; per-level treatment makes the claim chain visible. The methodology paper (METHODOLOGY_PAPER_OUTLINE_v1.md → published artifact) needs per-level construct treatment as its central argument. A teaching surface that adapts to user state needs per-level metadata to decide which claims to surface with which discipline. All three compounding loops (external evaluators, academic citation, user sovereignty as graduation rather than dependency) need the substrate to know what kind of claim it makes at each layer. This is the substrate-internal foundation for the user-facing and academic compounding chains.

The three claim levels:

- **`detector_measurement`**: deterministic regex/feature detector firing or non-firing. Examples: every `frame_library_matches` entry (V1 detector firing); every `divergence.absent_frames` record (V1 detector non-firing). Validation: reproducibility is the validity claim (algorithmic detectors do not need IRR); per-signal `construct` blocks carry the detector-specific caveats.
- **`classifier_output`**: deterministic cascade or scoring classifier with margin-aware confidence and runner-up reporting. Examples: `analysis.voice` (7-rule cascade), `analysis.genre` (six-class scoring with feature-evidence gate), `analysis.temporal` (distribution with dominant + balanced flag). Validation: documented thresholds and abstention discipline; no precision/recall against labeled gold-standard yet, no IRR pilot. Honesty gap named explicitly in `validation_status.validity_data`.
- **`composed_pattern`**: substrate-side composition over detector and classifier outputs. Trigger conditions deterministic (canon-graph set membership for `absence_clusters`; multi-frame plus doc-signal discriminators for `frame_patterns`); reading text inside is single-curator authored. Examples: each entry in `divergence.absence_clusters`; each entry in `divergence.frame_patterns`. Validation: trigger reproducible; reading is curator's normative claim about what the trigger means; no IRR pilot has measured whether other readers compose the same patterns from the same triggers.

What lands:

- **Module-level constants** `_CLAIM_LEVEL_DETECTOR`, `_CLAIM_LEVEL_CLASSIFIER`, `_CLAIM_LEVEL_COMPOSED` plus helper `_build_claim_level_treatments()` returning the per-level treatments dict. New code organized adjacent to the existing per-signal construct builders (`_build_voice_construct`, `_build_temporal_construct`, `_build_coverage_v2`).
- **`claim_level` field on every composed entity**: each `frame_library_matches` entry, each `divergence.absent_frames` record, each `divergence.absence_clusters` entry, each `divergence.frame_patterns` entry, plus `analysis.voice`, `analysis.genre`, and `analysis.temporal`. Existing per-signal `construct` blocks are preserved; `claim_level` adds the structural discipline.
- **`agent_guidance.claim_level_treatments` dict** keyed by claim_level value. Each treatment carries: `claim_type` (one-line description of the claim shape), `validation_status` (structured: deterministic, methodology_documented, inter_rater_reliability, validity_data), `caveats` (list of things the agent must surface when citing), `how_to_cite` (phrasing template). The validation_status fields are construct-honest: classifier_output and composed_pattern report `inter_rater_reliability: "not_yet_measured"` since no IRR pilot has shipped; detector_measurement reports `"not_applicable"` since reproducibility is the validity claim for algorithmic detectors. `validity_data` strings name the IRR gap explicitly so external evaluators see what is not yet validated. Built once at module import as `_CLAIM_LEVEL_TREATMENTS` (no per-call variation; the prior helper-function shape was an unnecessary call per request).
- **`analysis.frame_deepening` parent block carries `claim_level=detector_measurement`** so the agent honors the lower-bound vocabulary discipline when citing extracted evidence (years_referenced, roles_mentioned, extracted_conditions). The sub-fields (temporal_scope, stakeholder_map, falsification_conditions) inherit the discipline structurally.
- **`composition_discipline` extended with rule (6) PER-LEVEL CLAIM TREATMENT**. The five existing rules are preserved (insight-grounded, reading-form, confidence-gate, cross-context, absence-not-prescription). The new rule names the three claim levels, directs the agent to `claim_level_treatments` for the per-level discipline, and carries worked-example contrasts per level (the same lesson the cite-by-name discipline shipped: abstract instructions do not change agent behavior, concrete contrasts do). Detector example contrasts "the document covers risks" (verdict, ignores under-detection construct) with "Frame Check's detector found markers for risks (vocabulary-and-pattern based)". Classifier example contrasts "the document is promotional" with "classified as promotional (high confidence; runner-up advisory)" and the borderline variant. Composed-pattern example contrasts "this is a recommendation without falsification" with the cite-by-trigger-and-reading discipline.
- **`frame_compare` parity**. `_summarize_per_document` now emits `claim_level` on each per-document `voice`, `temporal`, and `frame_library_matches` entry; `build_compare_payload`'s `agent_guidance` carries the same `claim_level_treatments` dict. A client handles both surfaces (frame_check and frame_compare) under one per-level discipline rather than diverging by tool.

Tests added (5 L5 regressions; 217 mcp_server tests pass via pytest, 46 of 46 project suites pass via run_tests.py):
- `test_each_composed_entity_carries_claim_level`: pins claim_level on frame_library_matches, absent_frames, absence_clusters, frame_patterns, voice, genre, temporal, plus the frame_deepening parent block. Uses an inline recommendation-genre fixture (operator's agriculture pattern, paraphrased) that triggers FVS detectors and the recommendation-without-falsification pattern, exercising the full per-level metadata surface (matches + clusters + patterns simultaneously). Replaces the prior get-out-of-jail (`or not analysis.get(...)`) with an explicit non-empty assertion.
- `test_claim_level_treatments_carries_three_levels`: pins the three current keys, structured validation_status block, caveats list, how_to_cite template. Forward-compat: uses `expected_keys.issubset(actual_keys)` rather than exact equality so future levels (e.g. `agent_generated` for opt-in LLM opportunities under Item 12) can be added without breaking the test.
- `test_claim_level_treatments_validation_status_honest`: pins inter_rater_reliability values per level (`not_applicable` for detector_measurement; `not_yet_measured` for classifier_output and composed_pattern), and pins that `validity_data` names the IRR gap explicitly so external evaluators see what is not yet validated.
- `test_frame_compare_parity_carries_claim_level`: pins parity. `frame_compare` agent_guidance carries `claim_level_treatments`; per-document voice/temporal carry `claim_level=classifier_output`; per-document frame_library_matches carry `claim_level=detector_measurement`.
- `test_composition_discipline_teaches_per_level_treatment`: pins rule (6) in composition_discipline, the three claim_level values, the directive to `claim_level_treatments`, and the per-level worked-example contrasts (verbatim "high confidence; runner-up advisory" for classifier_output; verbatim pattern id "recommendation-without-falsification pattern" for composed_pattern).

Verified end-to-end on the operator's agriculture-recommendation fixture: every composed entity carries `claim_level` matching its kind; treatments dict has structured per-level validation status with honest IRR gaps; composition_discipline names rule (6) and the three levels. The substrate now distinguishes detection from classification from composition at the structural level, rather than only via the uniform composition_discipline prose.

This is the substrate-internal foundation that the user-facing teaching surface, the methodology paper, and external-evaluator engagement all depend on. It is also the move I would defend three years out: the substrate visibly distinguishes what kind of claim it makes at each layer, with construct-honest validation_status per layer, so the substrate can be evaluated and improved at the layer where the gap exists rather than under one uniform discipline.

### Polish: worked-example cite-by-name + uncertainty-vs-hedge detector boundary

Three Claude Desktop tests surfaced two related polish opportunities. The first cite-by-name polish (`fdedf97`) added abstract instructions ("CITE THE PATTERN BY ITS id") but the agent continued to paraphrase substrate compositions. The third test (AI opportunities document) surfaced a substrate boundary (uncertainty coverage = 0 while hedge ratio = 21%) that the agent flagged implicitly without explicit method-limit framing.

Polish:

- **Cite-by-name now carries worked examples.** The composition_discipline contrasts paraphrase with cite-by-name verbatim: "instead of 'the pick gets a one-sided defense pattern' (paraphrase, substrate invisible), write 'this matches Frame Check's recommendation-without-falsification pattern' (substrate identified, user can chain to definition)." Same treatment for cluster.dimension. Concrete examples replace abstract instructions; the agent has a model to follow rather than a rule to interpret.
- **Uncertainty-vs-hedge detector boundary disclosed in `what_this_tool_does_not_tell_you`.** The substrate's coverage detection for uncertainty uses vocabulary markers (uncertain, unknown, contested, range, depends, varies), not hedge markers in claim positions (might, could, expected to, projected to). A document can carry a 21% hedge ratio while uncertainty coverage shows zero markers; that's a detector boundary, not a contradiction. The discipline names this so future agents surface the disconnect as a methodological observation rather than a finding about the document.

Tests added (2 polish regressions; 212 mcp_server tests pass via pytest):
- `test_cite_by_name_carries_worked_examples` (pins the paraphrase-vs-cite contrast and verbatim pattern id in worked example)
- `test_uncertainty_vs_hedge_disclosure` (pins the detector boundary in agent_guidance method limits)

These close the loop on the post-roadmap polish series. The substrate now produces named compositions (E + D), the agent has explicit instruction with concrete worked examples to surface those names (cite-by-name with worked example), and the substrate's detector boundaries are named in agent_guidance so the agent can flag construct-honest disconnects without inventing them.

### Frame-explorer extension pattern reservation (FRAME_DIVERGENCE_CONTRACT_v1.md §12)

Doc-only architectural commitment. Documents the additive-sibling-field extension pattern under the `divergence` block for future categories beyond frame divergence: scenario divergence, persona divergence, constraint divergence, timeframe divergence, cultural-lens divergence, regulatory-regime divergence, stakeholder-position divergence (candidate categories the parallel agent's research surfaces). Three invariants govern any future category addition: additive-not-breaking, same faithfulness contract, catalog-traceable. Tool surface stays at `frame_check` and `frame_compare` per Rec II discipline; new categories ship as output-shape extensions with opt-in flags mirroring `include_divergence`. The reservation is the load-bearing architectural commitment that makes the MCP a substrate for AGI-era multi-perspective primitives, not a single-category endpoint.

### Added (packaging scaffolding for 0.8.0 PyPI release)
- **`pyproject.toml` at repo root.** Setuptools-based PEP 621 metadata. Package name `frame-check-mcp`, build version `0.8.0.dev0` (PEP 440 pre-release marker; bumps to `0.8.0` at publish). Entry point: `frame-check-mcp = "mcp_server:main"`. Single runtime dependency: `PyYAML>=6.0,<7.0` (model_registry only). Optional `[test]` extra: pytest + pytest-timeout. Build matrix targets Python 3.10/3.11/3.12.
- **`framecheck_mcp/` package shell at repo root.** Empty `__init__.py` plus symlinks to data carriers (`data/`, `METHODOLOGY.md`, `calibration/`, `validation/`, `pipeline_version.txt`, `FRAME_DIVERGENCE_v1.md`, `FRAME_DIVERGENCE_CONTRACT_v1.md`, `V4_2_GAP_INVENTORY_v1.md`). At wheel-build time, setuptools follows the symlinks and bundles the real files inside the wheel under `framecheck_mcp/`. In dev mode, the symlinks resolve to the repo-root data tree (no duplication).
- **`_DATA_ROOT` indirection in `mcp_server.py` and `frame_library_index.py`.** Both modules probe for a `framecheck_mcp/` subdirectory next to themselves; if found, that's the data root (installed-wheel layout); otherwise the script directory is the data root (dev / repo layout). All path constants (`_LIBRARY_DIR`, `_LIBRARY_V3_DIR`, `_WORKED_EXAMPLES_DIR`, `_TRANSMISSIONS_DIR`, `_METHODOLOGY_PATH`, `_CALIBRATION_RESULTS_DIR`, `_AGGREGATE_RESULTS_DIR`, `_CORPUS_ENTRIES_DIR`, `_SPEC_FD_V1_PART1_PATH`, `_SPEC_FD_V1_PART2_PATH`, frame-library `VERSION` lookup) route through `_DATA_ROOT`. End-to-end verified: extracted wheel produces correct `frame_library_version=0.2.0`, `corpus_slugs=10`, `corpus_hash=7a6e2f294c9e`, `provenance.analysis_cost_usd=0.0` from a fresh layout.

### Architectural choice (will be revisited at 1.0.0)
- **Flat py-modules layout, not src-layout.** Per MCP_PACKAGE_DESIGN_v1.md §4 we evaluated both Option A (flat py-modules with namespace pollution risk) and Option B (src-layout under `src/framecheck_mcp/`). For 0.8.0 we ship Option A: the 18 MCP modules (`mcp_server`, `framing`, `clarethium_measure`, `claim_analysis`, `frame_library`, `frame_library_index`, `decision_readiness`, `comparison`, `pipeline`, `source_network`, `claim_selector`, `llm_cost`, `tier_a_event`, `model_registry`, `telemetry`, `version`, `entity_classifier`, `time_context`) install at top-level. Risk: a few names (`pipeline`, `telemetry`, `framing`) could collide in shared environments; mitigated by recommending `uvx frame-check-mcp` or dedicated venvs in install docs. The src-layout refactor is bundled with `1.0.0` (which STRATEGY §14 already names as the API-freeze line adopting the v2 contract shape per MCP_CONTRACT_V2_PROPOSAL.md). Both layout and API are breaking; bundled for one major-version transition.

## [0.7.1]

Internal release. Additive frame-divergence spec resources on the canonical `frame-check://` scheme landed at this version (additive to v1 contract; no `SERVER_VERSION` bump because `0.8.0` is reserved for the divergence-capable `frame_check` enhancement per Rec II in `ENGINE_TIER_RECOMMENDATIONS_v1.md`).

### Added
- `frame-check://spec/frame-divergence/v1` (generated index), `frame-check://spec/frame-divergence/v1/part-1` (FRAME_DIVERGENCE_v1.md, category definition and non-negotiables), `frame-check://spec/frame-divergence/v1/part-2` (FRAME_DIVERGENCE_CONTRACT_v1.md, contract c1.0). Parts 3-4 slot in by the same pattern when authored.
- `PROMPT_AI_RESPONSE_AUDIT` and `PROMPT_EXPLAIN_FRAMING` gained optional context paragraphs pointing agents at `frame-check://aggregate/latest` for cross-question outlier findings and `frame-check://corpus/{slug}` for specific documents.

## [0.7.0]

Internal release. Canon-graph distribution surface at the corpus-pair level.

### Added
- Per-pair comparison artifacts exposed as MCP resources: `frame-check://corpus/{slug}/peer/{partner_slug}` (side-by-side numerical comparison) and `frame-check://corpus/{slug}/diff/{partner_slug}` (annotated framing-level interpretation).
- Aggregate `cross_question_findings` gained `corpus_entries` field carrying `corpus_entry_ref` objects (slug + title + `corpus_resource_uri` + `public_url`) so MCP agents chain from findings directly to corpus entries without applying the slug-matching heuristic client-side.

## [0.6.0]

Internal release. Canon-graph distribution surface at the corpus-entry level.

### Added
- Validation corpus entries exposed as MCP resources: `frame-check://corpus/{slug}` (document.md, text/markdown) and `frame-check://corpus/{slug}/profile` (profile.json, application/json). Traversal-safe slug resolution via strict regex + asset whitelist. Omitted from `resources/list` on deploys without the validation tree.

## [0.5.0]

Internal release. FVS-016 activation and canon-graph title-inlining.

### Added
- FVS-016 Authority by Citation detector activated. Synthesized in `decision_readiness` from `sourced_pct` + source_network signals (the detector layer does not have source_network access). When the document carries substantial citation markers (≥30% of sentences) but only a minority of checked numerical claims verify (≤50% with at least 3 checked), FVS-016 fires in both `evidence` and `robustness` `fired_library_entries` (canon membership in both dimensions).
- Library entry titles inlined in canon-graph reference shape (`library_entry_ref` now carries `title` from `INDEX.md`); `adjacent_frames` also gained `title` for uniform shape.
- `frame_library_matches` now carry `affects_dimensions`: the list of decision-readiness dimensions for which the matched frame is canon.
- New MCP resource: `frame-check://aggregate/latest`. JSON payload of the most recent decision-readiness corpus aggregate (cross_question_findings, library_entries_per_dimension, per-dimension divergence rates).

### Changed
- Aggregate `cross_question_findings` field `canon_library_entries` renamed to `library_entries` for naming consistency with the per-document profile field.
- All four sovereignty prompts updated to mention `affects_dimensions` for matched frames.

## [0.4.0]

Internal release. Detector-identified subset of canon-graph dimensions.

### Added
- Each decision-readiness dimension now carries `fired_library_entries`: the canon-aligned subset of `library_entries` whose detector specifically detected the named pattern in this document (vs `library_entries`, the dimension's full canon space). Same ref shape; agents iterating receive the focused detector-identified set.

### Changed
- All four sovereignty prompts updated to prefer `fired_library_entries` when non-empty; fall back to `library_entries` for broader-vocabulary discussion.

## [0.3.0]

Internal release. Canon-graph references self-resolvable from MCP responses.

### Changed
- Per-dimension `library_entries` on the decision_readiness profile changed shape from list-of-FVS-IDs to list-of-objects matching `adjacent_frames`: `{fvs_id, library_resource_uri, public_url}`. All four sovereignty prompts updated to point agents at `library_resource_uri` for chaining to the named patterns behind weak dimensions. Schema break is bounded by the `experimental` status field on the profile.

## [0.2.0]

Internal release. Decision-readiness surfacing.

### Added
- `analysis.decision_readiness` added to `frame_check` responses. All four sovereignty prompts updated to surface the new field. Aligns with the Phase 1.5 ship documented at `/corpus/decision-readiness/`.

## [0.1.0]

Internal release. Initial MCP server.

### Added
- `frame_check` and `frame_compare` tools.
- Four sovereignty prompts: `frame_check_my_response`, `frame_check_this_ai_response`, `challenge_document`, `explain_framing`.
- Three-section epistemic payload: `analysis` + `agent_guidance` + `provenance`.
- Resource surface for frame library, methodology, worked examples, transmissions, calibration runs.

---

*Maintained by Lovro Lucic. License: Apache-2.0 (code); CC-BY-4.0 (corpus and analysis). Citation per `CITATION.cff`.*
