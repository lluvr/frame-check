---
name: Feature request
about: Suggest a change to functionality, UX, MCP contract, or methodology
title: "[feature] "
labels: enhancement
---

**Problem**
What user, workflow, or analytical question is unserved today?

**Proposed change**
What the feature would do. Keep it scoped.

**Surface affected**
Tick all that apply:

- [ ] Live web surface (templates, routes, UI)
- [ ] Detection engine (`framing.py`, `claim_analysis.py`,
      `frame_library.py`)
- [ ] MCP server (`mcp_server.py` contract; MCP resources)
- [ ] Corpus / library (FVS entries)
- [ ] Methodology (empirical studies, calibration data)
- [ ] caller or verification pipeline
- [ ] Governance or documentation

**Alternatives considered**
What did you rule out and why? This section helps reviewers
distinguish a feature request from an under-specified problem.

**Blocking gates**
Which of the following (if any) would this feature require?

- [ ] `[RFC]` because it would overturn or come close to overturning
      a durable governance decision named in `GOVERNANCE.md`
- [ ] A new detection rule in `frame_library.py` (see
      `CONTRIBUTING.md §"Contribution types"`)
- [ ] A new FVS library entry (see the same section)
- [ ] A backward-incompatible change to the MCP contract
- [ ] An external dependency addition
- [ ] A cost change (new LLM call, new paid provider)

**Honest limits of the proposal**
What would this feature NOT solve? What are the risks (false
positives, UX regression, cost, construct-honesty violation)?
Frame Check's practice is to ship honest-limits alongside every
shipped capability; proposals that carry their own limits are
easier to converge on.
