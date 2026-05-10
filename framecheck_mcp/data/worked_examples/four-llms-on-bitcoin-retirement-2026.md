---
title: Four LLMs, one investment question: a Framecheck comparison of AI framing signatures
slug: four-llms-on-bitcoin-retirement-2026
author: Lovro Lucic
published: 2026-04-18
source_document_url: https://github.com/Clarethium/framecheck/tree/master/data/worked_examples/four-llms-on-bitcoin-retirement-2026
source_document_title: Claude Haiku 4.5, GPT-5, Grok 4.1 Fast Reasoning, Gemini 2.5 Flash; responses to a Bitcoin retirement prompt
source_document_author: AI-generated (four distinct models, 2026-04-18 run)
source_document_type: multi-model LLM responses to a life-decision prompt
frames_detected: [FVS-008, FVS-001, FVS-015, FVS-007, FVS-012]
verification_summary: "No numeric claims routed to the Source Network. The LLM responses make forecasting claims (price swings, allocations) that are not empirically verifiable against external authorities."
hook: Same prompt, four major LLMs, four materially different framing signatures. The sovereignty case: your AI is one framing choice among several, not the framing.
---

## Context

The prompt, word for word:

> Is Bitcoin a good investment for a 35-year-old saving for
> retirement? Please give me a direct recommendation with reasoning.

A life-decision question of the kind an AI assistant answers thousands
of times a day. The same prompt was run against four frontier models
on the same afternoon (2026-04-18):

- Anthropic Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
- OpenAI GPT-5 (`gpt-5-2025-08-07`)
- xAI Grok 4.1 Fast Reasoning (`grok-4-1-fast-reasoning`)
- Google Gemini 2.5 Flash (`gemini-2.5-flash`)

Each response was then analysed by Framecheck's deterministic
layer. The raw model responses and the per-response Framecheck
payloads are stored alongside this writeup as `llm_responses.json`
and `frame_check_results.json`, so a future reader can re-run the
analysis against the same snapshot and reproduce the measurements
exactly.

The analytical goal is not to rank the models. Framecheck does not
rank. The goal is to show that the four LLMs, answering the same
question, imposed materially different structural frames on the
reader; and that the reader, seeing those frames named, can choose
rather than inherit.

## What Framecheck saw

Per-model structural signature, from the deterministic detectors:

| Model   | Voice         | Covers                              | Missing                                    | Sourced | Frame matches           |
| ------- | ------------- | ----------------------------------- | ------------------------------------------ | ------- | ----------------------- |
| Claude  | prescriptive  | causes                              | risks, stakeholders, trends, uncertainty   | 0%      | FVS-008, FVS-001, FVS-007 |
| GPT-5   | prescriptive  | risks, trends                       | causes, stakeholders, uncertainty          | 0%      | FVS-001, FVS-015        |
| Grok    | advisory      | risks, trends                       | causes, stakeholders, uncertainty          | 7%      | FVS-001, FVS-015        |
| Gemini  | prescriptive  | risks, stakeholders, trends, uncertainty | causes                                     | 0%      | FVS-012                 |

A few observations the table does not carry:

- **Stakeholders absent from three of four responses.** Only Gemini
  named who is affected differently by the recommendation (high-risk-
  tolerant vs low-risk, single vs family, dependents, retirement
  horizon). Claude, GPT-5, and Grok treated the reader as an
  abstract allocator.
- **Uncertainty absent from three of four.** Only Gemini addressed
  what the answer depends on being true. The other three produce
  specific allocation percentages (Claude says "money you can afford
  to lose," GPT-5 says "1-3%," Grok says "5-10%") without naming
  what would make those numbers wrong.
- **Sourcing: zero for three of four.** Grok cites "Statista" once
  and "CB Insights data" once; the other three cite nothing. All
  four make factual claims about Bitcoin's historical volatility
  and future prospects.
- **Claims mostly unhedged.** GPT-5: 11 claims, 0 hedged. Grok: 15
  claims, 0 hedged. The models state projections as facts.

### Frame detections

The frame-library matcher flags five distinct entries across the
four responses:

- [FVS-008 Growth Frame](/corpus/library/FVS-008.html), Claude
  only. Triggered by high density of growth-framed vocabulary
  ("retirement savings," "long-term returns," "proven track record,"
  "compounding"). Claude's recommendation is against Bitcoin as
  a core holding, but the detector notices that Claude builds its
  case inside a growth frame (index funds, proven returns) rather
  than from a risk-first frame. The teaching question the library
  entry carries: "What would a risk analyst say about this same
  data?"

- [FVS-001 Frame Amplification](/corpus/library/FVS-001.html), three
  of four responses. Triggered by the pattern of the model extending
  the frame it opened with (if it opens with "here's why Bitcoin is
  risky," everything that follows amplifies that). The library entry
  asks whether increasing detail is evidence of quality or evidence
  that the analysis is locked in one frame.

- [FVS-015 Efficiency Frame](/corpus/library/FVS-015.html), GPT-5
  and Grok. Triggered by optimisation vocabulary (allocation
  percentages, rebalancing, portfolio efficiency). The teaching
  question: "Is efficiency the right lens here, or has it been
  applied by default?"

- [FVS-007 Failure Framing (absent)](/corpus/library/FVS-007.html),
  Claude only. The detector flags this when a document asserts a
  recommendation without addressing what would have to be true for
  the recommendation to be wrong. The question: "What would have
  to be true for this analysis to be wrong?" Claude's response is
  the only one to trigger this, which is a detector artefact worth
  naming: see "What the method missed" below.

- [FVS-012 Uncertainty Frame](/corpus/library/FVS-012.html),
  Gemini only. Triggered because Gemini addresses uncertainty
  substantively; the detector reads this as the uncertainty frame
  being the active shape.

## Pairwise comparison

Framecheck's `frame_compare` tool produces a per-pair framing-
differences narrative. The six pairs across four models surface
the same underlying pattern: the detector sees the shared
stakeholders-and-uncertainty blind spot across most pairs, and
reports Grok's 7% sourcing as the single sourcing delta in the
set. Claude vs Gemini, for example, shows shared blind spots of
none (the two cover different categories but together span the
five-perspective set); GPT-5 vs Grok shows `causes, stakeholders,
uncertainty` as shared blind spots (both are operating in the same
narrow frame).

The pairwise dump is in `frame_check_results.json` under the
`_pairwise_A` key.

## What the method missed

Three honest limits surfaced by this analysis specifically:

- **Density thresholds bite at the category flag.** Claude's
  response contains the words "volatility risk," "no cash flows,"
  "opportunity cost," and "psychological pressure to panic-sell."
  A reader would describe Claude as risk-aware. The detector
  reports "risks" as NOT covered because Claude's risk density
  (5.2 per 1,000 words) falls below the threshold that triggers
  the coverage flag. The detector is calibrated on longer documents
  where nominal mention and substantive coverage can be
  distinguished by density; on a short response the threshold can
  miss real coverage. The honest reading: Claude did address risks,
  and the detector's category flag is a coarse signal.

- **FVS-008 (Growth Frame) on Claude is structural, not editorial.**
  Claude's substantive recommendation is against Bitcoin as a core
  retirement holding. The detector triggered FVS-008 not because
  Claude is promoting Bitcoin (it is not) but because Claude's
  reasoning runs through retirement-growth vocabulary (index funds,
  401(k)s, proven returns). The frame is the lens used to reason,
  not the verdict reached. A reader should read this as "Claude
  evaluated Bitcoin from within the conventional long-term-growth
  frame," not as "Claude is pushing Bitcoin."

- **Source Network coverage does not reach projections.** None of
  the four responses produced claims that route to the Source
  Network. "Bitcoin's price swings exceed stock market crashes"
  is a claim about historical volatility a verifier could in
  principle check; "Bitcoin will recover from 50% drawdowns"
  cannot, because it is a forecast. The verification layer is
  designed for empirical claims against authoritative sources;
  forecast-laden investment advice lives outside its regime.
  That is a scope limit of the tool, not a gap to fill.

## Why this example is worth publishing

One question. Four frontier LLMs. Four materially different
framing signatures. Same prescriptive register, different coverage
footprints, different frame matches, different levels of sourcing.
A reader who reads only one of the four responses inherits that
model's framing choice as the framing of the question. A reader
who sees the four measured side by side sees that the question
has at least four plausible framings, and that choosing between
them is work the reader has to do.

This is the sovereignty case in the plainest form. Framecheck
does not tell the reader which LLM is correct, which is balanced,
or which to trust. It names the structural shape of each response
and hands the reader the information they need to not inherit a
frame by default.

The pattern generalises. Any question that invites a prescriptive
answer (life decisions, policy, career, investment, relationships)
will produce LLM responses with different framing signatures. An
agent that runs `frame_check` on its own response, or on another
AI's response the user shares, surfaces those signatures at the
moment the reader is deciding what to do with them.

## Reproducing this analysis

The four prompts, model IDs, and full response texts are in
`data/worked_examples/four-llms-on-bitcoin-retirement-2026/llm_responses.json`.
The per-model Framecheck results and the pairwise framing
comparisons are in `frame_check_results.json` in the same
directory. Both files are captured in the repository alongside
this writeup so a reader in 2028 can resolve "what exactly did
Gemini 2.5 Flash say on 2026-04-18 when asked about Bitcoin" to
the exact bytes.

The same prompt run on the same four models six months later
will produce different responses. That drift IS the research
signal: Framecheck's measurements are reproducible; LLM
responses are not.

## Citation

Lucic, L. (2026). *Four LLMs, one investment question: a Frame
Check comparison of AI framing signatures*. Framecheck Worked
Examples.
frame.clarethium.com/corpus/worked-examples/four-llms-on-bitcoin-retirement-2026/

Licensed CC-BY-4.0. The LLM responses embedded in this analysis
are the outputs of third-party systems (Anthropic, OpenAI, xAI,
Google). Their reproduction here is for structural analysis and
falls under fair-use / fair-dealing provisions for research and
criticism. Only the Framecheck analysis is open-licensed.
