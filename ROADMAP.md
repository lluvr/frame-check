# Roadmap

A roadmap is a contract about direction, not a schedule. Calendar
estimates accrete pretend precision; this document instead names
the discrete pieces of work that have to land for the next stable
line, the order they unblock each other in, and the falsifiable
evidence each one ships against.

The current PyPI line is `0.9.x`. The next stable target is `1.0.0`.

## What 0.9.x is

The 0.9 line is the stabilization arc that closes the cleanup work
the 0.8 line started: public-canon discipline (no internal vocabulary
in shipped artifacts), CI-driven publishing (FM-PCD-12 preflight,
Trusted Publishing, sigstore attestation, GitHub release on tag
push), and the audit + lint + type-check infrastructure that future
contributions run against.

0.9.x ships working capability. It is not yet at the v1.0 quality
bar described below.

## What v1.0 is (the contract)

A `1.0.0` release commits to:

- **Strict typing on the public wheel surface.** ``mypy --strict``
  passes against `mcp_server`, `mcp_compose`, `mcp_resources`,
  `mcp_schema`, `framing`, `comparison`, `clarethium_measure`. The
  current incremental ``[tool.mypy]`` config in `pyproject.toml`
  raises to strict at the v1.0 cut.
- **Zero ruff lints.** The current PR-time `quality` job runs ruff
  with select families (E, F, B, ISC) and is informational. At v1.0
  it becomes blocking with no remaining lints across the codebase
  (the tail of E402, B007, B028 closes).
- **Coverage floor.** Per-module line coverage on the public wheel
  surface holds above a target the v1.0 cut declares (currently the
  `pytest-cov` report runs at PR time, no enforced floor). The
  pre-v1.0 milestone names the floor and the modules it applies to.
- **Doctest-runnable adopter examples.** The README quickstart and
  `data/worked_examples/*.md` snippets execute under `python -m
  pytest --doctest-modules` (or equivalent) and are part of the CI
  gate.
- **Conformance driver gate.** `scripts/mcp_conformance_driver.py`
  runs against the freshly-built wheel in CI on every tag push (it
  already runs in the publish workflow's smoke test; the gate
  becomes blocking at v1.0).
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
The catalog is intentionally conservative — entries land only when
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

### Decoupling completion

The 2026-05-09 incident (FM-PCD-6 in
`PUBLIC_CANON_DISCIPLINE.md`) revealed that the operator dev tree
that bundled the web surface and the MCP source was a structural
risk for the publish path. The current pipeline replaces that with
CI-driven tag-push publishing from this repository alone. v1.0
confirms: the legacy operator-tree orchestrator is retired, the
release has cut from this repo at least once, and the
`RELEASING.md` flow has executed end-to-end including PyPI
Trusted Publishing.

## Past v1.0 (open questions)

- **Multi-language MCP wrappers** (TypeScript, Go) — contingent on
  adopter demand surfaced through GitHub discussions.
- **Framing-check on PR diffs** — agentic CI integration where the
  detector runs on the document content of pull requests.
- **Streaming MCP transport** — the current stdio JSON-RPC line-
  delimited protocol is enough for desktop clients; remote / web
  MCP transports are an open question.
- **Independent rater rounds** — beyond the existing `docs/RATERS.md`
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
