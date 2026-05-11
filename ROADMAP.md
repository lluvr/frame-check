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

One v1.0 contract item remains deferred to a future patch.

### Validation pre-registration first execution

`validation/wedge_behavior/PROTOCOL_v1.md` is the pre-registered
behavior-change study; `validation/wedge_behavior/run_pilot.py`
is the runner. The first execution with N ≥ 30 documents per
condition, the results publication under the same directory,
and a CHANGELOG narrative linking those results, all land in a
`1.0.x` patch.

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
