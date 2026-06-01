# Roadmap

A roadmap is a contract about direction, not a schedule. Calendar
estimates accrete pretend precision; this document instead names
the discrete pieces of work that have to land for the next stable
line, the order they unblock each other in, and the falsifiable
evidence each one ships against.

The current PyPI line is `1.0.x`. The next stable target is `1.x`
(open; no hard version commitment until the contract below is met).

## What 1.0.0 shipped

- Strict typing on the seven-module wheel surface (`mcp_server`,
  `mcp_compose`, `mcp_resources`, `mcp_schema`, `framing`,
  `comparison`, `clarethium_measure`) under `mypy --strict`.
- Adopter-contract test coverage in
  `tests/test_cookbook_recipes.py`.
- Conformance driver gate (`scripts/mcp_conformance_driver.py`)
  PR-blocking and run against the freshly-built wheel on every
  tag push.
- Methodology citation paths verified against the published Zenodo
  concept-DOI and the methodology canon at `Clarethium/lodestone`.
- CI-driven publish from this repository alone (the
  `.github/workflows/publish.yml` pipeline ran end-to-end on
  the v1.0.0 tag push: world-state preflight + build + sigstore
  attestation + Trusted Publishing OIDC + GitHub release).
- Engine V4.2 capability decision: ships the under-detection-marker
  pivot (per the README "Approach" section) as the load-bearing
  claim; detector F1 = 0.36 against expert labelers stays the
  honest position rather than waiting for the engine to cross the
  0.4 threshold.

See `CHANGELOG.md` `[1.0.0]` for the cut narrative and the
five-defect publish-workflow audit that landed alongside.

## Closed in v1.0.x

### Per-module 80% coverage on the wheel surface (closed in 1.0.1)

The v1.0 contract committed each of the seven wheel-surface
modules to 80% production-code coverage; v1.0.0 deferred this
because four modules were below target. The deferral closed in
the v1.0.x line: provider-mock test infrastructure for
`comparison.py` and targeted tests for `framing`, `mcp_server`,
and `clarethium_measure` brought every module to or above the
floor. The CI gate at `scripts/check_per_module_coverage.py`
(invoked by `tests.yml`) is strict-blocking.

The 80% per-module floor scope is intentionally the wheel-
surface seven modules only. Other modules (`source_network`,
`frame_library`, `manifest`, `prompt_safety`,
`frame_opportunities`, `version`, etc.) are bundled in the
wheel as implementation dependencies of the surface and are
held to the global 65% floor only. Adopters interact with
those modules transitively through the seven; targeted tests
on them follow as the project finds load-bearing gaps, but
they are not part of the per-module 80% contract. A future
1.x cut can promote a module into the per-module floor by
adding it to the FLOORS dict in
`scripts/check_per_module_coverage.py` alongside the matching
ROADMAP entry; promotion follows the same DCO + rationale
process as a contract change.

| Module                  | Pre-1.0.x | Post-1.0.x |
|-------------------------|-----------|------------|
| `mcp_schema`            |   100.0%  |    100.0%  |
| `mcp_compose`           |    94.9%  |     94.9%  |
| `mcp_resources`         |    90.3%  |     90.3%  |
| `framing`               |    69.5%  |     82.6%  |
| `mcp_server`            |    69.4%  |     81.5%  |
| `clarethium_measure`    |    62.6%  |     84.4%  |
| `comparison`            |    20.9%  |     86.5%  |

## Deferred from v1.0 to v1.0.x

### Validation pre-registration first execution

`validation/wedge_behavior/PROTOCOL_v1.md` is the pre-registered
behavior-change study. The pre-registered protocol + harness
shipped end-to-end (`run_pilot.py` + `run_arms.py`); a 2026-05-12
pipeline smoke test verified the harness drives both arms via
Anthropic API, captures responses with full metadata, and
produces rubric-scored output. Smoke-test pilot data is kept in
the author's local workspace, not committed to this public
repo (the pilot used self-authored documents and agent-as-rater,
methodologically pipeline-verification not validation evidence
— see
[`validation/wedge_behavior/STATUS.md`](validation/wedge_behavior/STATUS.md)
for the honest scope).

The smoke test surfaced three rubric calibration findings:
catalog-naming as distinct evidence on item 1, reading-form
dominance vs. presence on item 2, and hedge-calibration two
kinds on item 4. These ship into PROTOCOL_v2 if accepted before
the main study locks.

The next gate is methodologically credible main-study evidence:
externally-sourced documents (public LLM-output corpora, random
op-ed samples, Wikipedia featured articles), three independent
raters with Gwet's AC1 reliability per item, and PROTOCOL_v2
locked before execution. Human-driven work; harness is ready to
drive once the three sourcing conditions are met.

`validation/baseline_comparison/PROTOCOL_v1.md` is the parallel
study testing information advantage over a frontier LLM prompted
for framing analysis. Same shape: protocol + harness ready;
methodologically credible execution awaits the same external
sourcing + independent-rater conditions.

## In flight (1.x milestones, no order)

These are pieces of work that were open at v1.0 and stay open
for the 1.x line. None of them is on a calendar.

### Validation: Track B reader-aid study

A second pre-registered study (alongside the wedge-behavior
protocol) tests whether the structural surfacing actually helps
a reader see framing they would otherwise miss. The
H1/H2/H3 hypothesis structure follows
`validation/wedge_behavior/PROTOCOL_v1.md`; Track B applies the
same shape on a reader-task corpus.

### Catalog: Frame Vocabulary Standard expansion

The FVS catalog ships 20 entries (`data/frame_library/`). The
catalog is intentionally conservative: entries land only when
the rule reaches a useful detection rate against the labelers
and the entry survives a public adoption pass. Pre-1.x candidate
entries live in the methodology canon at `Clarethium/lodestone`
and get promoted into the public catalog when ratified.

### Engine: V4.2 capability re-attempt

v1.0 shipped the under-detection-marker pivot; the V4.2-engine
path (named-pattern detector F1 ≥ 0.4 against expert labelers)
remains open. A V4.2 promotion in 1.x would carry CHANGELOG
narrative documenting the criteria the new engine met and
flip `engine_status` from `"beta"` to a stronger statement.

## v2.0 breaking changes (committed)

Items the builder and adopters can both rely on landing at
the next major-version boundary. Each is named here so the
v2.0 cut is a contract execution, not a discovery exercise.

### Remove `framecheck_version` from manifest payload

The MCP manifest block currently emits both
`manifest.frame_check_version` (canonical, matching
`version.py:FRAME_CHECK_VERSION`) and
`manifest.framecheck_version` (legacy, deprecated since
v1.0.1). Both carry the same value; the additive emission is
a deprecation grace period for adopters whose integrations
still read the v0.9.x typo'd field name. At v2.0, the legacy
key is dropped and only `frame_check_version` remains. Code
sites: `manifest.py:447,636` (emit), `CHANGELOG.md [1.0.1]`
section (rationale).

Note that the `provenance` block carries only
`provenance.frame_check_version` (canonical) and never
emitted the legacy key — the deprecation pair lives in the
`manifest` block alone.

### Remove `analysis.coverage` (v1) block

The MCP payload currently emits both `analysis.coverage`
(v1, keyword + pattern based; `addressed`/`missing` lists
plus density-per-1k-words) and `analysis.coverage_v2` (v2,
per-dimension construct block with detection-confidence
metadata). v1 carries an inline DEPRECATION NOTICE on its
`caveat` string flagged at Phase 2 (2026-04-21) pointing
adopters at v2 as the forward contract. At v2.0 the v1
block is removed; only `coverage_v2` remains. Code sites:
`mcp_compose.py:327` (`_build_coverage_v2`), inline caveat
at the same file's `_compose` block (~2415).

Adopters reading `analysis.coverage` today must migrate to
`analysis.coverage_v2` before the v2.0 cut. The `caveat`
string in every response carries the migration directive;
this ROADMAP entry is its committed counterpart.

## v2.0 design questions (uncommitted, revisit at scoping)

Items that are NOT pre-committed but warrant explicit scoping
before v2.0 ships. Each carries a real tradeoff that should be
weighed in light of v1.0.x adoption signal.

### Re-evaluate the v1.0.10/v1.0.11/v1.0.12 alias quartet

Every FVS-reference record in the wire payload now carries
`{citation_uri, library_resource_uri, library_url, public_url}`
where `citation_uri == library_resource_uri` and
`library_url == public_url`. The aliasing closed cross-block
naming inconsistencies and lets adopters write a single FVS
renderer for any block. Measured cost on the bundled
Grok-NVIDIA fixture: **+15.5% wire payload size** vs. emitting
only the canonical name per pair (16.7KB of pure alias
redundancy on a 108KB baseline).

The cost scales linearly with FVS-reference count per response.
On adopter integrations with token-limited LLM contexts and
many `frame_library_matches` + `absent_frames` + nested
`corpus_context.typical_co_*` records, the overhead is real
per-call cost.

Options to weigh at v2.0 scoping:

1. **Keep the quartet (status quo).** Schema coherence wins
   over payload size; adopters who don't care about size pay
   nothing they wouldn't have paid.
2. **Drop the alias names, keep only the canonical pair**
   (`citation_uri` + `library_url`). Reverses the v1.0.10–12
   sweep; adopters who hardcoded the alias names break and
   must migrate.
3. **Gate the aliases behind an opt-in flag** (e.g.,
   `prefer_compat_aliases=true`, default false). Smaller
   default payload; adopters who need the aliases opt in.

This ROADMAP entry pre-commits nothing. The decision needs
v1.0.x adoption signal: do adopters use the aliases, are
they hitting token limits because of them, what naming
convention does the integration ecosystem actually settle on?
The canonical-only-emit option (#2) is reversible-as-additive
later (re-add the aliases if adopters protest); the keep-quartet
option is forever-additive (aliases can't be cleanly removed
once shipped longer than v1.0.x).

## Past 1.x (open questions)

- **Multi-language MCP wrappers** (TypeScript, Go): contingent on
  adopter demand surfaced through GitHub discussions.
- **Framing-check on PR diffs**: agentic CI integration where the
  detector runs on the document content of pull requests.
- **Streaming MCP transport**: the current stdio JSON-RPC line-
  delimited protocol is enough for desktop clients; remote / web
  MCP transports are an open question.
- **Independent rater rounds**: beyond the existing `docs/RATERS.md`
  protocol, expand to a multi-rater consortium with public
  attribution.

These are entered here as named possibilities, not commitments.

## How decisions enter this document

A new line under "In flight" or "Past 1.x" enters the roadmap
through the same process as a substantive code decision:
sign-off-by-DCO commit + the short rationale captured either in
the commit body or as a `[RFC]` issue per `GOVERNANCE.md`. The
roadmap is not a strategy memo; it is the public face of decisions
that have already been argued through.

## What's deliberately not on this roadmap

- **Calendar dates.** Calendar precision is dishonest given the
  research nature of the program. The contract above is the gate;
  it ships when it ships.
- **Marketing direction.** Adopters reading this document want to
  know what the artifact will do, not how it will be sold.
- **Funding or staffing posture.** Public roadmap is about what
  ships, not how it gets there.
