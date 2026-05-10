# Roadmap

A roadmap is a contract about direction, not a schedule. Calendar
estimates accrete pretend precision; this document instead names
the discrete pieces of work that have to land for the next stable
line, the order they unblock each other in, and the falsifiable
evidence each one ships against.

The current PyPI line is `0.9.x`. The next stable target is `1.0.0`.

## What 0.9.x is

The 0.9 line is the stabilization arc that closes the cleanup work
the 0.8 line started. CI-driven publishing landed in `0.9.4` with a
destination-state preflight (refuses to proceed if the GitHub
repository is archived, disabled, or has a different default
branch), Trusted Publishing for OIDC-authenticated PyPI uploads,
sigstore build-provenance attestation, and a GitHub release created
from the annotated tag on every successful publish. The audit, lint,
and type-check infrastructure that future contributions run against
ships in the same line.

0.9.x ships working capability. It is not yet at the v1.0 quality
bar described below.

## What v1.0 is (the contract)

A `1.0.0` release commits to:

- **Strict typing on the public wheel surface.** ``mypy --strict``
  passes against `mcp_server`, `mcp_compose`, `mcp_resources`,
  `mcp_schema`, `framing`, `comparison`, `clarethium_measure`. The
  lenient ``[tool.mypy]`` config already passes clean on this surface
  and is strict-blocking at PR time; the strict pass shows ~348
  remaining errors (mostly ``[type-arg]`` and ``[no-untyped-def]``)
  that close at v1.0.
- **Zero ruff lints.** Done as of `0.9.x`. The PR-time `quality`
  job runs ruff with select families (E, F, B, ISC) and the gate is
  strict-blocking. New violations fail PR.
- **Coverage floor.** The 0.9.x line declares a 65% production-code
  floor enforced via ``pytest --cov-fail-under=65`` on the Python
  3.12 matrix run. ``[tool.coverage.run] omit`` in pyproject.toml
  excludes ``tests/``, ``setup.py``, ``run_tests.py``, and the
  ``framecheck_mcp/`` build-staging copy so the headline is honest
  production-code coverage rather than the inflated number that
  results from counting tests-testing-themselves. Current
  production coverage: 69%. The biggest single drag is
  ``source_network.py`` at 10% (1435 statements, network-bound code
  paths that need provider-mocked tests to exercise). v1.0 raises
  the floor to 80% on the public wheel surface modules
  (``mcp_server``, ``mcp_compose``, ``mcp_resources``, ``mcp_schema``,
  ``framing``, ``comparison``, ``clarethium_measure``) with
  per-module declarations; the matrix runs the per-module threshold
  instead of the global one.
- **Adopter-contract test coverage.** The cookbook claims and
  README "Approach" positioning claims (zero per-query cost,
  determinism, response-shape contract) are verified against the
  running API in `tests/test_cookbook_recipes.py` and run as part
  of the regular pytest suite at PR time. Done as of `0.9.x`. v1.0
  expectation: keep the test in step with cookbook edits; a new
  recipe lands with a matching test or it does not land at all.
- **Conformance driver gate.** `scripts/mcp_conformance_driver.py`
  runs against the freshly-built wheel on every tag push and is
  PR-blocking as of `0.9.x`. The driver speaks JSON-RPC over stdio
  to the wheel as an external MCP client would and validates every
  primitive (initialize, tools/list, tools/call for `frame_check`
  and `frame_compare`, resources/list, resources/read, prompts/list,
  prompts/get, ping, error handling). v1.0 expectation: keep this
  gate green across all primitives at every cut.
- **Validation pre-registration completed.** The behavior-change
  study pre-registered at `validation/wedge_behavior/PROTOCOL_v1.md`
  has its first execution complete with N≥30 documents per
  condition, results published in the same directory, and
  CHANGELOG narrative for the cut links to those results.
- **Methodology citation paths verified.** `CITATION.cff` resolves
  to a real Zenodo deposit at the cut commit; the methodology canon
  reference at `Clarethium/lodestone` points at content that exists;
  the README detector-F1 number cites a study artifact that anyone
  can reproduce from corpus + harness.

The v1.0 cut is not on a calendar. It happens when the contract
above is met.

## In flight (pre-v1.0 milestones, no order)

These are pieces of work whose completion unblocks the v1.0 cut.
Each one is independently shippable in a `0.9.x` release.

### Engine: V4.2 capability

The current Frame Divergence emission carries `engine_status =
"beta"`. The named-pattern detector reports F1 = 0.36 against expert
labelers (pre-registered, below the useful threshold of 0.4).
v1.0 ships either:

- A V4.2 engine that crosses the useful threshold (F1 ≥ 0.4 against
  the same labelers + scope), and CHANGELOG narrative documents the
  promotion criteria the new engine met.
- Or, if the threshold is not crossed, an explicit decision in
  CHANGELOG narrative to ship v1.0 with the under-detection-marker
  pivot as load-bearing (per the README "Approach" section), making
  the v1.0 contract honest about what the detector does and does not
  do.

### Validation: Track B reader-aid study

A second pre-registered study (alongside the wedge-behavior
protocol) tests whether Frame Check's surfacing actually helps a
reader see structural framing they would otherwise miss. The
protocol drafts at `validation/wedge_behavior/PROTOCOL_v1.md` give
the H1/H2/H3 hypothesis structure; Track B follows the same shape
on a reader-task corpus.

### Catalog: Frame Vocabulary Standard expansion

The current FVS catalog ships 20 entries (`data/frame_library/`).
The catalog is intentionally conservative: entries land only when
the rule reaches a useful detection rate against the labelers and
the entry survives a public adoption pass. Pre-v1.0 candidate
entries live in the methodology canon at `Clarethium/lodestone` and
get promoted into the public catalog when ratified.

### Adopter surface: cookbook + comparison

- A cookbook (`docs/COOKBOOK.md` or similar) showing 5+ adopter
  recipes: framing-check before AI agent commit, divergence at
  decision points, claim verification on financial documents, etc.
- A comparison section in README that names what Frame Check gives
  an adopter that a plain LLM call does not.

### Cut a release end-to-end via the new pipeline

`0.9.4` shipped via the prior orchestrator path. The CI-driven
pipeline in `.github/workflows/publish.yml` is in place but has
not yet executed end-to-end (the PyPI Trusted Publishing
registration is the one-time manual gate before the first
CI-driven publish). v1.0 confirms: at least one release cut and
published from this repository alone via tag push, with the
sigstore attestation, GitHub release, and Trusted Publishing
upload all green.

## Past v1.0 (open questions)

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

A new line under "In flight" or "Past v1.0" enters the roadmap
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
