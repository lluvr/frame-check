# Security Policy

Frame Check has two distribution surfaces:

1. **Web service** at `frame.clarethium.com`: a free public research
   instrument (currently in operator-controlled deploy hold).
2. **MCP package** `frame-check-mcp` (Python wheel; pip-installable
   for use with Claude Desktop / Cursor / any MCP client). The wheel
   ships the deterministic measurement layer; LLM-augmented surfaces
   are caller-side.

The code is open source (Apache-2.0); corpus data and methodology
are open (CC-BY-4.0). Security-sensitive behavior exists in a small
number of surfaces enumerated below. Both surfaces are in scope for
reports.

## Reporting a vulnerability

**For non-public reports**: email `hello@clarethium.com` with
`[security]` in the subject line. Include:

- A description of the vulnerability (what, where, how to
  reproduce).
- The impact you believe the vulnerability has (data exposure,
  cost amplification, authentication bypass, etc.).
- Whether you have exploited it, and against what (if at all).
- Your preference for disclosure timeline and public acknowledgment.

**Acknowledgment timeline**: the curator (Lovro Lucic) commits to
acknowledging a security report within 72 hours of receipt. A
full diagnosis and remediation plan follows within 14 days of
acknowledgment. For severe issues (credential exposure, data
exfiltration, cost exhaustion), expect faster turnaround.

**Public disclosure**: the default is coordinated disclosure. The
reporter and the curator agree on a disclosure date after the fix
ships. Frame Check does not currently run a bug-bounty program; a
security report is a contribution, not a transaction.

## Supported versions

Frame Check has two release postures:

- **Web service** (`frame.clarethium.com`): a live deploy, not a
  released product with version ranges. The master branch at
  github.com/lluvr/frame-check-mcp is the authoritative source. The
  Fly.io image tracks master with operator-controlled deploy
  cadence.
- **MCP package** (`frame-check-mcp` on PyPI, planned 0.8.0
  initial release): semver-versioned. Security fixes for the
  current minor (0.8.x) ship as patch releases. There is no
  long-term-support track yet; expect every minor to require an
  upgrade for security fixes once 0.9.0 lands. This policy may
  tighten as adoption grows.

Security fixes land on master first. For the wheel, a fix triggers
a patch release within the timelines named under "Acknowledgment
timeline" above.

## How to verify the audit yourself

The 2026-04-27 publish-readiness audit is reproducible against any
released wheel. Steps an external reviewer (or future maintainer)
can run independently:

1. **Install the wheel under inspection** into a clean target.

       pip install --target /tmp/fc-target frame-check-mcp==<version>

2. **Run the lift dry-run** against a fresh build of the same
   version's source tree (clones the repo, builds the wheel, runs
   eight gates: clean state, build, `twine check --strict`,
   install, smoke import, CLI `--version`, conformance driver,
   inventory leak-check). The leak-check enforces the maintainer-side doc
   patterns enumerated in `scripts/lift_dry_run.py` and refuses
   any wheel that ships `data/falsifications/F-NNNN-NNN`,
   `EXP-NNN-data/`, or any of the named operator-private docs.

       python3 scripts/lift_dry_run.py

3. **Run the MCP client conformance driver** against the installed
   wheel (drives 32 round-trips through line-delimited JSON-RPC
   over stdio, the same wire shape Claude Desktop and Cursor use).

       python3 scripts/mcp_conformance_driver.py

4. **Run the adversarial harness** locally (63 tests across seven
   attack classes A-G, including the dispatcher input-shape
   discipline pinned by the 0.8.0 D2 fixes).

       python3 -m pytest test_mcp_adversarial.py -v

5. **Read the four audit deliverables** in the repository root for
   the original audit's findings, remediation log, conformance
   report, and verdict: `LEAKAGE_AUDIT_v1.md`,
   `REMEDIATION_LOG_v1.md`, `MCP_CLIENT_CONFORMANCE_v1.md`,
   `PUBLISH_READINESS_VERDICT_v1.md`.

If any of the four scripts above fail on a released wheel, that is
a security-relevant regression. File a report per "Reporting a
vulnerability" above.

## Audit history

| Date | Surface | Audit | Outcome |
|---|---|---|---|
| 2026-04-27 | `frame-check-mcp` 0.8.0 wheel | Pre-publish leakage audit + adversarial harness + client conformance | 16 leakage findings catalogued, 14 closed, 2 partial; 3 dispatcher defects surfaced + closed; 32/32 client round-trips pass. See `LEAKAGE_AUDIT_v1.md`, `REMEDIATION_LOG_v1.md`, `MCP_CLIENT_CONFORMANCE_v1.md`, `PUBLISH_READINESS_VERDICT_v1.md`. |
| 2026-04-18 | Web service | Phase 5 cost / origin / abuse hardening | $5 -> $3 daily cap, attacker-hardened error messages, /admin/gates operator endpoint, env-overrides on 7 caps. See commit range `bee2265..f3dce50`. |

## Security-sensitive surfaces

The following areas are worth attention. A report against any of
these is in scope.

- **Cost gates and rate limiting** (`security.py`,
  `app.py::charge_cost_gates`, per-feature daily limits). The
  gates protect against LLM-cost amplification. A bypass here
  has financial impact on the deploy.
- **User-text handling** (`app.py`, `comparison.py`, `framing_ai.py`,
  MCP server). The privacy page commits to a specific contract
  (`/privacy` and `DATA_MOAT.md` §3-§6); a leak of that contract
  is in scope. AI-interpretation flows send excerpts to
  third-party LLMs; user-facing documentation names this
  explicitly.
- **MCP server** (`mcp_server.py`, distributed as the
  `frame-check-mcp` wheel). Untrusted input reaches the detection
  engine through the MCP `frame_check` / `frame_compare` tools and
  through the `resources/read` URI surface. Panic /
  denial-of-service through crafted input is in scope. Path
  traversal, prompt injection that influences the static
  `agent_guidance` payload, leak of the `user_context` parameter
  (privacy posture: never round-trips), and JSON-RPC envelope
  shape violations are in scope. The dispatcher's input-shape
  discipline (params and arguments must be JSON Objects) is
  pinned by `test_mcp_adversarial.py` (61 tests across 7 attack
  classes); regressions surface there. The 0.8.0 audit closed
  three dispatcher defects (D2.1, D2.2, D2.3) where malformed
  input returned `-32603` instead of the documented `-32602`;
  see `REMEDIATION_LOG_v1.md` §K. Conformance against a real MCP
  client wire is verified by
  `scripts/mcp_conformance_driver.py` and recorded in
  `MCP_CLIENT_CONFORMANCE_v1.md`.
- **Observatory ingestion** (`observatory.py`, `telemetry.py`).
  The Observatory cycles through a curated topic list; no user
  submission reaches the Observatory corpus. A path that
  persists user content into the Observatory is a privacy
  violation in scope.
- **Saved-analyses URLs** (`/saved/{hash}` and
  `/compare/saved/{hash}` routes). URLs are hash-unguessable but
  not authenticated; shared URLs expose the analysis. A
  cross-hash leak (one save reading another) is in scope.
- **Corpus exports and R2 credentials** (`export_corpus.py`,
  `entrypoint.sh`, `litestream.yml`). Private-bucket credentials
  must not reach the public bucket and vice versa; see
  `RUNBOOK.md §1.1-1.2`.
- **Cloudflare Turnstile + origin protection** (`origin_protection.py`,
  Turnstile config). A bypass here raises cost-amplification risk
  because it removes a bot filter.

## Out of scope

- Denial of service via legitimate traffic volume. The per-IP rate
  limits and cost gates are the defenses; exhausting them at a
  given IP is expected behavior.
- Typos, low-severity UX issues, and ideas for additional
  security hardening that are not vulnerabilities. Use the issue
  templates (`.github/ISSUE_TEMPLATE/`) for those.
- Content moderation of user submissions. Frame Check processes
  text deterministically and does not retain submissions; there
  is no moderation surface.

## Dual-use guidance

Frame Check is a structural-analysis instrument, not a
truthfulness verdict. Agent integrators who use Frame Check's
output as a quality score, truthfulness flag, or editing rule
that suppresses minority framings are using the tool outside its
design scope. See `ANTICIPATED_CRITIQUES.md §7 C7.1` and the
MCP contract's `agent_guidance.dual_use_note` for the
construct-honesty framing.

## Cryptographic identity

The curator's commit signature and keybase/PGP details are not
currently published. Reports relying on identity verification
should use direct email to `hello@clarethium.com` and request
acknowledgment via a specific channel the reporter trusts.

A PGP key for security-report encryption is planned for the 0.9.0
release window. Until then, reporters who require non-email
encrypted channels should request a Signal handle in the initial
contact email and the curator will respond with a verification
phrase out of band.

---

*v3. 2026-04-27. Adds "How to verify the audit yourself" with the
four reproducibility scripts; names the 0.9.0 PGP key plan; v2's
MCP-distribution-surface and Audit-history additions retained.*
