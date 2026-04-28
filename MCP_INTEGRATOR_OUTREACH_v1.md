# MCP Integrator Outreach

**Status:** pre-curator-draft v0.1, 2026-04-27. Not sent. Companion to `MCP_PACKAGE_DESIGN_v1.md` and `MCP_CLIENT_CONFORMANCE_v1.md`. Drafts the maintainer-side cold outreach to MCP host integrators (Cline, Cursor, Continue.dev, Anthropic Solutions, etc.) once `frame-check-mcp` is live on PyPI.

**Companion doctrine.** `STRATEGY.md §9` names public portfolio + MCP-first distribution as compounding effects 2 + 4. `ANTICIPATED_CRITIQUES.md` C3.2 names "MCP contract is aspirational; zero adopters" as a load-bearing open question. This document closes the gap from "ship the contract" to "ask one specific integrator if it belongs in their default catalog."

**Pre-conditions** (both must hold before sending any of these):

1. `frame-check-mcp` is published on PyPI. **Met as of 2026-04-28** (https://pypi.org/project/frame-check-mcp/0.8.1/; 0.8.0 superseded by the URL-fix republish).
2. The package's Project-URLs (Repository, Issues, Changelog, Security, Methodology, Frame Library) resolve to public endpoints. **MET as of 2026-04-28**: Path A.1 fully executed. All six Project-URLs in the deployed 0.8.1 METADATA return HTTP 200 against `lluvr/frame-check-mcp`. GitHub Release page at https://github.com/lluvr/frame-check-mcp/releases/tag/v0.8.1 is published. **Outreach is now unblocked.**

The Path A.1 lift is documented in `REPO_STRATEGY_DECISION_v1.md` v1.2 (fully executed + URL verification matrix).

**Sequencing.** Send to ONE integrator first. Wait two weeks for a response. Adjust the template based on the engagement (or non-engagement). Then send to a second. Burst-sending five identical cold emails on day one is a low-information move; sequential single-target outreach lets each response inform the next.

**Principle.** Construct-honesty preserved in outreach. The detector F1 = 0.36 published negative is named upfront. The MCP server's vendor-independence architecture (caller's agent runs the LLM judge, Frame Check bears no per-query cost) is the actual selling point and is named first. No inflated adoption claims; the project's adoption count is zero and the email says so.

---

## Template 1: Cline (recommended first target)

**Why first.** Open source, MCP-native by design, public Discord and GitHub, smaller team that can actually engage on a code-level review. Lower friction than Cursor (corporate gate) or Anthropic Solutions (warm-intro required). The Cline catalog has a precedent of community-contributed MCP servers; a quality submission is on-doctrine for them.

**Channel.** GitHub issue on cline/cline (preferred for visibility) OR Discord #mcp-servers channel. Email-form below adapts to either; `[CHANNEL]` token marks where the format diverges.

**Subject line (email) / Issue title:** `frame-check-mcp on PyPI: structural framing analysis as an MCP tool`

**Body:**

Hi Cline team,

I shipped a Model Context Protocol server, `frame-check-mcp`, to PyPI and want to ask whether it belongs in the default Cline catalog or as a featured community submission.

What it does: deterministic structural framing analysis on any text the agent passes in. The agent gets a `frame_check` tool that returns a coverage profile (which of five analytical perspectives the document takes), voice posture, temporal orientation, epistemic basis, and named Frame Vocabulary Standard candidate matches with worked examples. Output is regex-based and reproducible; the same input always returns the same structure.

Why this might fit Cline specifically:

1. **Vendor-independent by design.** The server returns structural detection plus a `divergence` block whose evaluation runs *in the caller's agent* using the caller's LLM. Frame Check bears zero per-query LLM cost; Cline users keep their existing model preference. Architecture documented at `FRAME_DIVERGENCE_CONTRACT_v1.md` in the source repo.

2. **Deterministic and offline.** Structural detection is regex-based, requires no API keys, runs locally. Cline users get a tool they can rely on without network surprises.

3. **Construct-honest output.** Each match ships with a teaching question, not a verdict. Output explicitly names what the detector measures (vocabulary-based markers) and what it does not (semantic intent). No false-confidence patterns.

Honest state, not buried:

- This is the first public release. Zero MCP host integrations to date.
- Detector F1 against expert labelers landed at 0.36 in pre-registered validation, below the useful threshold of 0.4. The pivot to construct-honesty (surfacing under-detection markers rather than asserting labels with false confidence) is the load-bearing claim at v0; published in full at `fvs_eval/validation_study/REPORT_V3_TRACK_A.md`.
- 32/32 conformance round-trips against the installed wheel (line-delimited JSON-RPC, identical I/O shape to Claude Desktop and Cursor). Conformance harness in `scripts/mcp_conformance_driver.py`.

The asks:

- Five-minute install verification: `pip install frame-check-mcp`, point your MCP client at the entry point, run any document through `frame_check`. If it lands cleanly, what's the path to default-catalog or featured-community status?
- If something breaks during install or first-use, GitHub issues on `lluvr/frame-check` are the right place to surface it; same-day response on cold-start setup defects.

The package is Apache-2.0 licensed. Source: `https://github.com/lluvr/frame-check-mcp`. PyPI: `https://pypi.org/project/frame-check-mcp/`. Methodology paper: `https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md`.

Happy to talk on Discord, GitHub, or async whatever fits.

Lovro Lucic
[CONTACT]

---

## Template 2: Generic MCP host integrator

**Target audience:** any MCP-host integrator that maintains a public catalog or featured-server list (Cursor, Continue.dev, Zed, etc.). Adapt §1 selling-point order to the integrator's stated values.

**Subject line:** `frame-check-mcp: structural framing analysis as an MCP tool, catalog candidate?`

**Body:**

Hi [TEAM],

I shipped a Model Context Protocol server, `frame-check-mcp`, to PyPI and want to ask whether it fits in the [TEAM]'s server catalog or featured-community list.

What it does: deterministic structural framing analysis on any text the agent passes in. The agent gets a `frame_check` tool that returns a coverage profile (which of five analytical perspectives the document takes), voice posture, temporal orientation, epistemic basis, and named Frame Vocabulary Standard candidate matches with worked examples. Output is regex-based and reproducible.

Three things that may matter to [TEAM] specifically:

1. **Zero per-query LLM cost on the server side.** The MCP server returns structural detection plus a `divergence` block whose evaluation is delegated to the caller's agent and the caller's model. The caller pays for their own judgment; Frame Check is a free pure-detection tool from the integrator's user's perspective.

2. **Deterministic, offline, no API keys required.** Regex-based detection runs locally without network. Predictable behavior in agent loops.

3. **Construct-honest output.** Each match ships with a teaching question, not a verdict. The detector explicitly names what it measures (vocabulary-based markers) and what it does not (semantic intent).

Honest state:

- First public release; zero MCP host integrations to date.
- Detector F1 = 0.36 against expert labelers in pre-registered validation, below the useful threshold of 0.4. The construct-honesty posture (surfacing under-detection markers rather than asserting confident labels) is the load-bearing claim; published in full.
- 32/32 conformance round-trips against the installed wheel. Identical I/O shape to Claude Desktop and Cursor.

The ask: a five-minute install + spot-check. `pip install frame-check-mcp`, point an MCP client at the entry point, run a document through `frame_check`. If clean, what's the path to catalog inclusion? If broken, GitHub issues on `lluvr/frame-check` are the channel.

Apache-2.0 licensed. Source: `https://github.com/lluvr/frame-check-mcp`. PyPI: `https://pypi.org/project/frame-check-mcp/`.

Lovro Lucic
[CONTACT]

---

## Template 3: Anthropic Solutions / Claude Desktop integrator (warm-intro variant)

**Target audience:** internal Anthropic team or partner-network contact. Different posture: warm channel, less pitch, more peer-level surface of work.

**Subject line:** `Quick note: frame-check-mcp is on PyPI`

**Body:**

Hi [NAME],

Following up on [PRIOR CONTEXT]. The `frame-check-mcp` server is now public on PyPI (Apache-2.0). It returns deterministic structural framing analysis as an MCP tool with caller-agent-runs-the-judge architecture per `FRAME_DIVERGENCE_CONTRACT_v1.md`.

Specifically Claude-Desktop-relevant: 32/32 conformance round-trips against the installed wheel; the I/O shape is identical to what Claude Desktop already speaks. Install is `pip install frame-check-mcp` plus a one-line `claude_desktop_config.json` entry.

Construct-honest disclosure: detector F1 = 0.36 in pre-registered validation, below the useful threshold of 0.4; the pivot to construct-honesty surfacing rather than confident labels is the load-bearing claim. Methodology paper covers the pivot in §1.

If there's a Claude Desktop default-catalog process, I'd appreciate a pointer to whoever manages that. If the right move is to wait until the construct-honesty posture is externally validated (Track B reader-aid study, separately pre-registered), that's also a useful answer.

Lovro

---

## Tracking

The operator records each outreach in `SESSION_STATE.md §1` on send (timestamp, target, channel, template used). Replies (or non-replies after 14 days) feed the response analysis in a future `MCP_ADOPTION_LOG_v1.md`.

**Failure-mode discipline.** If three sequential outreaches return zero engagement over 60 days, that is a load-bearing signal that the MCP-first distribution thesis needs a different angle (different selling point, different target class, or different channel). Failure mode is named at `STRESS_TEST_ASSESSMENT_v1.md §3` as load-bearing empirical question #3; this document is one half of testing it. The other half is publishing the package and waiting.

**Out of scope for v0.1.** This document does not draft the post-engagement response (what to say after an integrator opens an issue or replies); that requires the actual response in hand. Composing those replies is maintainer-side, on-the-fly.

---

*v0.1, 2026-04-27. Templates one through three. Cline is the recommended first target. Templates two and three adapt for subsequent integrators. None sent. Send sequentially, not in burst.*
