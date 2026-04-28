# MCP TypeScript port: decision log and implementation plan

**Status:** decisions locked 2026-04-18. Implementation cleared to
begin. This document started as a scoping proposal (five open
questions, five trade-offs analysed) and has been revised into the
decision record for the port. The analysis sections are preserved
so a future reader can see the reasoning behind the commitments.

## Locked decisions

1. **Approach: Option B.** TypeScript protocol layer calling the
   Python analyzer as a subprocess. Full TypeScript port of the
   analyzers (Option C) deferred to v2, reactivated when adoption
   evidence justifies the multi-week parity engineering or when
   AI-assisted porting makes it cheap (expected to collapse in
   cost by 2029 regardless).
2. **Package namespace: `@clarethium/frame-check-mcp`.** Org-scoped
   under the Clarethium brand; signals Frame Check is one of
   several tools from the research program.
3. **Subprocess RPC protocol: stdin/stdout JSON.** Same pattern as
   MCP itself. Cross-platform without Windows-fragile sockets.
4. **Repository layout: `/ts/` subdirectory in this repo.**
   Monorepo for v1; separate repo postponed until the TypeScript
   contract is stable enough that npm publishing pipeline
   overhead is earned.
5. **Parity test corpus: existing worked-examples corpus plus a
   short synthetic suite** covering empty document, single-sentence
   document, number-saturated document, all-coverage-categories
   document. The TypeScript output must match the Python output
   byte-for-byte on every input.

## Trigger for Option C reactivation

Watch two signals. If either fires, re-evaluate the Option C
decision:

- **Edge-compute MCP adoption.** Cloudflare Workers, browser-based
  MCP clients, or other serverless MCP runtimes gain non-trivial
  share. Python does not run on these surfaces; the subprocess
  bridge is blocked there. An HTTP transport is the first
  mitigation; full TypeScript port is the second.
- **Unsolicited pure-Node demand.** Two or more separate users
  report that the Python dependency is the reason they did not
  adopt Frame Check. Signal that the Python tax has become
  real, not theoretical.

Until then, Option B is the right investment and AI-assisted
porting will carry the analyzer port cheaply when demand
materializes.

## Why this document exists

Horizon 2 of the Frame Check roadmap includes a TypeScript
implementation so Frame Check can ship as an npm package inside
the JavaScript/Node MCP ecosystem. The earlier working note
rejected a "Node shim" approach in favour of a "full TypeScript
protocol layer." Before any TypeScript code lands, the scope of
"full TypeScript" has to be decided, because the options span
one day of work to several weeks, and the maintenance burden
differs by an order of magnitude between them.

## The source-of-truth problem

Frame Check's deterministic analyzers live in Python:

- `framing.py`: coverage, voice, temporal, epistemic detectors
- `claim_analysis.py`: numeric claim extraction and hedging
- `frame_library.py`: FVS matcher against coverage/voice/temporal
  signatures
- `clarethium_measure.py`: Layer 11 grounding decomposition, the
  portrait generator, the larger measurement stack

These are regex-heavy, calibrated against a corpus, and pinned by
a Python test suite. Any TypeScript implementation that claims to
be "Frame Check" has to produce the same output as the Python
implementation for the same input, or the measurement contract
breaks. A citation that reads "Frame Check says this document has
3 of 5 analytical perspectives covered" has to resolve to the
same number whether the user ran the Python server or the
TypeScript one.

The source-of-truth problem is the axis the approaches below
sit on.

## Approaches considered

### Option A: Node shim that wraps the Python server

**Shape:** an npm package that, when invoked, spawns
`python3 mcp_server.py` as a subprocess and forwards stdio.
The shim is a thin protocol bridge; Python remains the
execution engine.

- **Effort:** one day (stdio forwarding, package metadata,
  postinstall Python-version check, a handful of tests).
- **Source of truth:** Python. No parity risk.
- **User UX:** `npx @clarethium/frame-check-mcp` works iff the
  user has Python 3.10+ on PATH. The npm install itself is
  fast and has no native deps; the Python dependency is a
  runtime check, not a build-time requirement.
- **Maintenance:** negligible. The shim rarely changes.
- **What it does not unlock:** pure-Node use (user still
  needs Python), no web-platform port (Cloudflare Workers,
  browsers), no distribution as a native npm dependency.

**Rejected in the earlier scoping conversation** on the grounds
that "full TypeScript" was the goal. Listed here for
completeness and because it is the baseline against which the
other options' effort and payoff are compared.

### Option B: TypeScript protocol layer calling Python as subprocess

**Shape:** a proper TypeScript implementation of the JSON-RPC
surface (initialize, tools/list, tools/call, resources/list,
resources/read, prompts/list, prompts/get), with the
analyzer work delegated to a Python subprocess via a narrow
RPC. The TypeScript layer owns the client-facing contract; the
analyzer is still Python.

- **Effort:** three to five days (JSON-RPC plumbing, schemas,
  subprocess contract, agent_guidance/provenance payload
  construction on the Node side, a parity test harness).
- **Source of truth:** Python analyzers, TypeScript protocol
  surface. Two artifacts to keep consistent.
- **User UX:** same Python-required constraint as Option A.
- **Maintenance:** medium. Two protocol implementations
  (Python and TypeScript) to keep in sync on payload shape.
  Any new MCP primitive has to be added twice. Every
  agent_guidance block has to be authored in two languages.
- **What it does not unlock:** pure-Node use. The Python
  dependency is still real.

### Option C: Full TypeScript port of the analyzers

**Shape:** port every deterministic analyzer (framing.py,
claim_analysis.py, frame_library.py, clarethium_measure.py) to
TypeScript. The TypeScript package is self-contained; no
Python dependency at runtime.

- **Effort:** three to six weeks. This is the full-scope work.
  Each analyzer is regex-heavy, calibrated against a corpus,
  pinned by tests. Porting means reproducing every regex,
  every density-threshold constant, every frame-library
  matching rule, every calibration-derived value.
- **Source of truth:** two parallel implementations. The Python
  tests have to pass; the TypeScript tests have to pass; a
  parity harness has to confirm both produce byte-identical
  measurements on a corpus of test documents.
- **User UX:** `npx @clarethium/frame-check-mcp` runs with no
  Python, anywhere Node runs. Cloudflare Workers possible with
  additional bundling constraints.
- **Maintenance:** HIGH. Every change to a detector has to be
  made in two languages and verified against parity. Every
  calibration update has to propagate across both. Drift is
  inevitable without continuous parity testing.
- **What it does unlock:** true cross-ecosystem first-class
  shipping. The npm package stands on its own.

### Option D: Hybrid: shared schemas, Python analyzers, TypeScript MCP layer, pyodide for pure-Node users

**Shape:** shared JSON Schema for types (worked-examples,
transmissions, frame-library entries), TypeScript MCP layer,
Python analyzers, and a fallback that runs the Python analyzers
inside a pyodide WASM runtime for users without Python
installed locally.

- **Effort:** four to eight weeks. Pyodide integration is the
  unknown unknowns.
- **Source of truth:** Python. Parity is automatic (it is
  literally the same code).
- **User UX:** Python users get native Python; no-Python users
  get pyodide WASM. Startup time and memory footprint both
  worsen with pyodide.
- **Maintenance:** medium. Python is source of truth; WASM
  packaging is one additional concern.
- **Risk:** pyodide is ~15MB compressed; not all MCP clients
  are patient about startup latency.

### Option E: Thin TypeScript MCP that calls the hosted frame.clarethium.com API

**Shape:** a TypeScript MCP server that implements the
protocol surface but performs analysis by HTTPS call to the
hosted site (which would need a structured-JSON endpoint
added).

- **Effort:** two to four days (hosted-site endpoint + TS
  client + MCP surface). Depends on the hosted site having an
  endpoint that returns the JSON-RPC-ready payload.
- **Source of truth:** the hosted Python deploy. Single
  source, no parity risk.
- **User UX:** fast npm install, no Python required, but
  every call goes over the network.
- **Maintenance:** low on TypeScript side, new responsibility
  on the hosted site (it becomes a public structured API, not
  just an HTML app).
- **Risk:** introduces a service dependency (hosted site up
  and responsive) and a cost pass-through (hosted-site
  compute cost scales with npm-package usage). Also the daily
  cost cap (`DAILY_CAP_MESSAGE`) would refuse npm users when
  the cap is hit, which is a bad UX.
- **What it fits:** a short-term distribution answer while
  Option C is built. A useful bridge, not a destination.

## Recommendation

**Begin with Option B (TypeScript protocol layer + Python
subprocess analyzers) as v1 of the npm package.** Treat Option
C (full TypeScript port) as a v2 milestone, not a v1 blocker.

The reasoning:

1. **The sovereignty-instrument claim does not depend on
   language.** The load-bearing feature is the prompts primitive
   (frame_check_my_response) and the agent_guidance payload.
   Those live at the protocol layer. Option B delivers both
   without the analyzer port.

2. **Python is not a significant barrier for the MCP agent
   audience.** Claude Desktop users, Cursor users, agent
   framework users: most already have Python. The Python
   dependency is a shallow one (python3 on PATH), not a deep
   one (no native deps, no virtualenv required beyond the
   repo's own requirements.txt).

3. **The parity problem is real.** Option C, done honestly, is a
   three-to-six-week commitment that doubles the ongoing
   maintenance surface forever. It should be undertaken when
   there is demand evidence that the Python dependency is
   actually blocking adoption, not as a prophylactic.

4. **Option B unblocks npm-ecosystem distribution.** The package
   is published, the protocol surface is first-class
   TypeScript, agents can install it via the MCP registries
   that assume Node. That alone is the distribution win the
   roadmap was aiming for.

5. **Option E (hosted-call bridge) is a tempting shortcut that
   creates a cost-attack surface.** Every user's agent call
   hits the hosted site. The hosted-site cost cap refuses npm
   users when hit. This couples distribution to deploy health
   in a way the sovereignty instrument framing specifically
   argues against (self-host should be first-class).

Option C is still the destination. Option B is the bridge that
gets us there without spending a month up front on parity
engineering for a benefit that may or may not materialise.

## Scope for v1 (Option B)

In:

- Complete TypeScript JSON-RPC 2.0 implementation over stdio
- Complete protocol surface: initialize, tools/list, tools/call,
  resources/list, resources/read, prompts/list, prompts/get,
  ping
- Tools: frame_check and frame_compare, with arguments, schemas,
  and return shapes identical to the Python server's
- Resources: every URI the Python server advertises, same
  content hashes
- Prompts: every prompt the Python server serves, same text
- Subprocess bridge to Python analyzer (narrow stdin/stdout
  JSON protocol)
- TypeScript test suite with parity assertions: for each of a
  test corpus of documents, the TypeScript output must equal
  the Python output
- npm package metadata (`@clarethium/frame-check-mcp` or
  similar namespace), postinstall Python-version check with
  a helpful error message
- Documentation: install in Claude Desktop / Cursor via npm,
  mirror of the README MCP section

Out of v1:

- Re-implementation of the deterministic analyzers in
  TypeScript
- Pyodide or WASM fallback
- Web-platform targets (browsers, Cloudflare Workers)
- Hosted-call bridge
- Publishing to the npm registry (the package lives in-repo
  first, graduates to npm when we know the contract is stable)

## Open decisions for the author

All five locked 2026-04-18. See the "Locked decisions" section
at the top of the document. The analysis that produced the
commitments is preserved in the sections below for audit and
for future reconsideration under the named triggers.

## Effort estimate

Option B v1 as scoped: three to five working days. Distribution:

- Day 1: JSON-RPC dispatcher + stdio transport + schema types
- Day 2: frame_check tool + subprocess bridge + parity harness
  for frame_check
- Day 3: frame_compare tool + resources/list and resources/read
  + prompts/list and prompts/get
- Day 4: full parity test pass + npm packaging + install
  documentation
- Day 5: refinement, error paths, timeouts on subprocess calls,
  graceful degradation when Python is missing

Each day ends with a passing test suite including a parity
assertion against the Python reference.

## Risks

1. **Subprocess startup cost.** Python import time adds ~300ms
   per invocation. For a chatty agent making many tool calls,
   this compounds. Mitigation: keep the Python subprocess
   alive between calls within one MCP session; spawn once at
   initialize, terminate at shutdown.

2. **Windows path handling.** Spawning python3 on Windows
   requires finding the right interpreter (python, py -3,
   full path from PATH). Mitigation: configurable Python path
   via environment variable, with sensible discovery defaults.

3. **Parity drift.** Every change to the Python analyzers now
   requires a parity re-check on the TypeScript side.
   Mitigation: CI runs the parity harness on every commit;
   TypeScript output is a hashed artifact of the Python
   result, not a reimplementation, so drift is structurally
   impossible during v1.

4. **Error-path coverage.** The Python server has careful error
   handling for malformed JSON-RPC and missing URIs. The
   TypeScript server has to replicate that, or agents see
   different errors depending on which transport they are
   using. Mitigation: a shared error-code contract file that
   both implementations consume.

## Next step

Decisions locked. Implementation sequence:

1. Day 1. Scaffold `/ts/` subdirectory: package.json with the
   `@clarethium/frame-check-mcp` name and bin entry, tsconfig,
   stdio JSON-RPC dispatcher, schema types generated from the
   MCP protocol surface the Python server already advertises.
2. Day 2. `frame_check` tool end-to-end: subprocess bridge
   (spawn `python3 mcp_server.py` or a narrower analyzer entry
   point, forward request / receive response), shape the
   epistemic payload the Python server already produces, plus
   the first parity assertion against one of the existing
   worked examples.
3. Day 3. `frame_compare` tool, `resources/list` +
   `resources/read`, `prompts/list` + `prompts/get`. At this
   point every Python-side MCP primitive has a TypeScript
   counterpart.
4. Day 4. Full parity test pass: every document in the parity
   corpus runs through both implementations; byte-identical
   output is the assertion. npm package metadata (name,
   author, license, keywords, repository), postinstall Python
   version check with a helpful error.
5. Day 5. Error paths (malformed JSON-RPC, missing URIs, bad
   slugs), subprocess timeouts, graceful degradation when
   python3 is not found on PATH, Windows path handling. Each
   day ends with a passing test suite including the parity
   assertion.

npm publishing is deliberately out of v1 scope. The package
lives in-repo first; publishing happens after the contract is
stable and the live MCP validation in Claude Desktop has
produced no regressions against the Python implementation.
