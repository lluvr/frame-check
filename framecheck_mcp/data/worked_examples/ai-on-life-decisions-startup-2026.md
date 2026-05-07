---
title: One LLM, one life decision: what framing your AI imposes when you ask it for advice
slug: ai-on-life-decisions-startup-2026
author: Lovro Lucic
published: 2026-04-18
source_document_url: https://github.com/Clarethium/frame-check-mcp/tree/master/data/worked_examples/ai-on-life-decisions-startup-2026
source_document_title: GPT-5 response to a startup career-change prompt (2026-04-18)
source_document_author: OpenAI GPT-5 (`gpt-5-2025-08-07`)
source_document_type: LLM response to a life-decision prompt
frames_detected: [FVS-001]
verification_summary: "No Source Network verification attempted. The response makes advisory claims about startup economics (regulatory complexity, runway requirements, burn rate assumptions) that are judgment claims, not empirical claims against external authorities."
hook: A user asks an LLM about a career change. The LLM produces a framework. The user did not ask for a framework; the LLM imposed one. Frame Check names what the LLM did.
---

## Context

The prompt, word for word:

> I'm 35 with a stable job in finance, thinking about leaving to
> start a fintech startup. What do you think?

This is a life question. Not a research request, not a fact query,
not a creative task: a person asking an AI for an opinion on a
major career move. The kind of conversation LLM assistants have
millions of times a day.

The response analysed is from OpenAI GPT-5 (`gpt-5-2025-08-07`),
captured on 2026-04-18. The full response text and the complete
Frame Check payload are in
`data/worked_examples/ai-on-life-decisions-startup-2026/data.json`
alongside this writeup, so a reader in 2028 can verify the exact
bytes the analysis ran against.

The companion worked example
[Four LLMs, one investment question](four-llms-on-bitcoin-retirement-2026.md)
ran four frontier models against a similar question and compared
their framing signatures. This entry does the opposite move: zoom
in on a single LLM's response to a single life question and show
what Frame Check surfaces about the conversation that just
happened.

## What Frame Check saw

GPT-5's response is 814 words, 57 sentences. The structural
signature from the deterministic detectors:

- **Voice: prescriptive.** Second-person percentage at 42. Three
  imperatives. Zero first-person-plural. The response addresses
  the user directly and tells them what to do. No "let me share
  some thoughts," no collaborative register. The user asked "what
  do you think"; GPT-5 produced a framework.

- **Analytical coverage: 2 of 5.** Risks and stakeholders are
  addressed; causes, trends, and uncertainty are absent. The
  density matters: stakeholders at 16.4 per 1,000 words (high),
  risks at 8.2 (substantive), uncertainty at 1.2 (one mention,
  below the coverage threshold). The response names who is
  affected and what could go wrong, but says nothing about *why*
  the user might be considering this (causes) or *how the
  landscape is shifting* (trends), and almost nothing about *what
  would make the advice wrong* (uncertainty).

- **Temporal orientation: present 98%.** The response lives in
  the present tense ("fintech carries extra complexity," "your
  edge matters," "you need to validate"). Almost no past grounding
  (what has worked for comparable founders) and almost no
  explicit future projection. Present-as-description: this is the
  register that reads as authoritative.

- **Sourcing: 0% attributed.** The response makes specific
  factual claims ("fintech carries extra complexity on top of
  usual startup risks," "most startups fail," "12-18 months of
  runway is typical") and cites nothing. Ten extracted claims,
  zero hedged. The model states projections as facts.

> **Note on detection state.** This worked example was published 2026-04-18 against v1 substrate detection. The v1 deterministic rules for FVS-001 Frame Amplification and FVS-008 Growth Frame were retired the same day per `data/frame_library/INDEX.md` (validation evidence showed they fired on cases they should not flag, per `fvs_eval/validation_study/RULE_AUDIT.md` §2.1). The frame concepts stand as library entries; current-generation detection (V4.2 LLM-judge) replaces the v1 rules. The bullets above (voice, coverage, temporal, sourcing) preserve the publish-time analysis: those measurements still hold byte-for-byte against the response under the current substrate. The detection-side and absence-side surfaces below have been restructured to reflect post-retirement state; the teaching points describe what the response *does* (frame concepts), not what a particular detector layer flags.

### Frame detections

Under the current substrate (frame_library version 0.2.0), the frame-library matcher fires zero present-frames on this response. The saved snapshot in `data/worked_examples/ai-on-life-decisions-startup-2026/data.json` captures the publish-time state when FVS-001 Frame Amplification fired before its v1 rule retirement.

The divergence block surfaces 19 absent frames. The high-signal absences (the structural reading the absence-side analysis surfaces):

- [FVS-017 False Balance](/corpus/library/FVS-017.html) (high signal, stable).
- [FVS-009 Risk Frame](/corpus/library/FVS-009.html) (high signal, stable).
- [FVS-001 Frame Amplification](/corpus/library/FVS-001.html) (high signal, stable). The frame concept stands; the v1 PRESENT-detector retired (see Note on detection state above). The absence-side surface still flags the frame because the substrate measures structural coverage of the frame's vocabulary; whether the response IS amplifying a frame is the reader judgment the v1 detector previously attempted and the V4.2 LLM-judge will attempt next.
- [FVS-014 Temporal Anchoring](/corpus/library/FVS-014.html) (high signal, stable).

The teaching point preserved from the publish-time analysis (the structural reading does not depend on the v1 detector firing; it describes what the response does):

GPT-5's response opens with "A quick framework to decide" and then populates the framework with specific questions (unique edge, runway, customer validation, moat, regulatory approach, cofounder, contract constraints). Every subsequent section amplifies the framework-as-the-right-way-to-decide. The user did not ask for a framework. The LLM produced one and then used it to shape the rest of the conversation. The library entry's teaching question is exactly right here: "Is the increasing detail evidence of quality, or evidence that the analysis is locked in one frame?"

A reader looking at the text will also recognise the response is growth-framed at the reading level (FVS-008 territory: "it can be a great move," "edge," "moat," "runway"). The v1 FVS-008 detector retired same-day as FVS-001; the frame concept stands but no v1 rule fires here today. The "What the method missed" section below carries the broader scope-limit reading.

## What is visible in the response that the measurements point at

The detector surfaces the structure; the reader reads the
structure against the text. Three specific patterns in GPT-5's
response that the measurements point at:

- **The decision has been reframed as a checklist.** The user
  asked what the model thinks. The model produced a "quick
  framework" with six named criteria. Whatever answer the user
  reaches will be an answer to the model's checklist, not
  necessarily to their own question. This is what the FVS-001
  frame describes structurally: the model's opening frame
  becomes the shape of the subsequent conversation.

- **Uncertainty is not part of the frame.** The single
  uncertainty mention (density 1.2) is a passing "if the market
  shifts" clause. The response does not ask "what would have to
  be true for this advice to be wrong," does not name its own
  limits, and does not flag that this is exactly the kind of
  decision where a stranger's opinion (the model) should carry
  less weight than the user's own context.

- **Stakeholders are addressed generically.** Density 16.4 per
  1,000 words is high, and the response names categories: your
  cofounder, your dependents, your employer (regarding employment
  agreements). But all the stakeholders are *the user's adjacent
  people*, not *the people the user's decision affects*: the
  customers the startup would serve, the competing startups, the
  incumbents. "Stakeholders" in Frame Check's taxonomy is meant
  broader than "people close to the decision-maker." The
  detector flagged stakeholders as covered; a reader reviewing
  the substance would say the coverage is partial.

## What the method missed

- **v1 detector retirement scope.** The 2026-04-18 retirement of the FVS-001 / FVS-008 / FVS-015 v1 rules (per `INDEX.md`) means the frame-library matcher fires zero present-frames here today. Pre-retirement (saved snapshot), FVS-001 fired. The frame concepts stand as library entries; the V4.2 LLM-judge replaces the v1 rules. The evidence discipline this exemplifies: detection layers evolve when validation evidence shows they fail design intent; frame concepts are stable; absence-side analysis remains a reliable surface independent of which detector layer is active.

- **Density threshold and the Growth Frame that did not trigger (historical reading; FVS-008 v1 also retired).**
  GPT-5's response is growth-framed at the reading level (edge,
  moat, runway, great move). At publish time the matcher's threshold for Growth Frame did not fire on this prescriptive career-advice response with mixed register; the FVS-008 v1 rule has since been retired alongside FVS-001. A reader should read this as "the detector's match (or non-match) is a conservative floor; other frames may apply, and current-generation detection will re-examine these via V4.2 LLM-judge."

- **Semantic vs structural.** The detector flagged stakeholders
  as covered because the response uses stakeholder vocabulary at
  high density. Semantically, the response addresses a narrow
  slice of stakeholders (the user's adjacents). The detector
  cannot make that distinction. The reader has to.

- **Verification layer not invoked.** The response makes specific
  claims (regulatory complexity, runway norms, partnership
  bottlenecks). These are advisory claims about startup-ecosystem
  economics that no Source Network provider can directly verify.
  The verification layer is designed for measurable facts from
  authoritative sources; judgment claims in advice text live
  outside its regime. This is a scope limit, not a gap.

## Why this example is worth publishing

Because the reader is the point.

A person asking an AI assistant about a major life decision is
the single most common AI conversation shape. Millions of these
happen per day. The answers are typically prescriptive,
unsourced, framework-imposing, and confident. Frame Check does
not say these answers are *wrong*; they are often useful. Frame
Check says what structural frame the answer is putting on the
question, so the reader can see the frame and decide whether to
inherit it.

This is the sovereignty case. Not "your AI is biased" (Frame
Check does not produce verdicts). Not "your AI is wrong"
(correctness is outside the method's remit). Structural: "your
AI gave you a framework you did not request; the framework covers
two of five analytical perspectives; the uncertainty about
whether this advice applies to you is not in the response; the
sourcing is zero; the frame pattern detected is
Frame Amplification (the structural reading the response exhibits; the v1 detector that automated this at publish time was retired same-day per the Note above, the frame concept and reading remain valid)." The reader, seeing those surface signals,
can decide what to do with them.

The usage pattern this worked example is meant to enable: a user
in an agent conversation, about to act on the agent's advice,
invokes the `frame_check_my_response` MCP prompt. The agent
calls `frame_check` on its own last response. The measurements
come back. The agent surfaces them. The user sees the frame
their AI just put on their life decision. Then they decide.

## Reproducing this analysis

The prompt, the model ID, the verbatim response, and the full
Frame Check payload are captured in
`data/worked_examples/ai-on-life-decisions-startup-2026/data.json`
alongside this writeup. A reader in 2028 can load the file, run
Frame Check's deterministic layer on the stored response text,
and reproduce the measurements exactly. The same prompt run
against GPT-5 in 2028 will produce different text; the model
drifts, the measurements against today's captured response do
not. This is the reproducibility contract the content-hash field
in resource metadata is designed to support.

## Citation

Lucic, L. (2026). *One LLM, one life decision: what framing your
AI imposes when you ask it for advice*. Frame Check Worked
Examples.
(production paused)

Licensed CC-BY-4.0. The LLM response analysed is the output of a
third-party system (OpenAI GPT-5). Its reproduction here is for
structural analysis and falls under fair-use / fair-dealing
provisions for research and criticism. Only the Frame Check
analysis is open-licensed.
