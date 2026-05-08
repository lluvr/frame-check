---
title: Frame divergence in action: what frames Claude's Bitcoin retirement recommendation did not use
slug: divergence-on-claude-bitcoin-retirement-2026
author: Lovro Lucic
published: 2026-04-24
source_document_url: https://github.com/Clarethium/frame-check/tree/master/data/worked_examples/divergence-on-claude-bitcoin-retirement-2026
source_document_title: Claude Haiku 4.5 response to a Bitcoin retirement prompt (2026-04-18 run)
source_document_author: AI-generated (Anthropic Claude Haiku 4.5, `claude-haiku-4-5-20251001`)
source_document_type: AI-generated financial-advice response
frames_detected: [FVS-008, FVS-007]
frames_divergent: [FVS-001, FVS-002, FVS-003, FVS-004, FVS-005, FVS-006, FVS-009, FVS-010, FVS-011, FVS-012, FVS-013, FVS-014, FVS-015, FVS-016, FVS-017, FVS-018, FVS-019]
verification_summary: "No Source Network verification attempted; this worked example demonstrates the MCP divergence surface, not source fidelity."
hook: The V1 detector named two present frames. The divergence block named seventeen absent. Caller-side V4.2 composition is where the reader-side judgment discipline actually lands.
---

## Context

This worked example demonstrates frame divergence: the companion
primitive to Frame Check's V1 detection, shipped on the MCP surface
through the `divergence` block on `frame_check` output. The canonical
references are FRAME_DIVERGENCE_v1.md Part 1 (category definition
and non-negotiables) and `FRAME_DIVERGENCE_CONTRACT_v1.md` Part 2
c1.0 (interface contract).

The source document is Claude Haiku 4.5's response to a Bitcoin
retirement prompt, originally captured as part of the
[four-llms-on-bitcoin-retirement-2026](four-llms-on-bitcoin-retirement-2026.md)
worked example. That companion piece demonstrates `frame_compare`
across four frontier models. This piece takes a single response from
that set and shows what the divergence primitive surfaces on one
document, in one domain (`finance`), using the MCP surface where
V4.2 judgment is delegated to the caller's agent model (zero Frame
Check LLM cost; vendor-independence automatic).

The exact invocation is in "Reproducing" at the end. The full
`frame_check` response with the divergence block is in
`divergence-on-claude-bitcoin-retirement-2026/divergence_output.json`;
the source document text is in `source_document.md` in the same
directory so a reader in 2028 can re-run the analysis against the
identical input and reproduce the measurements.

## What `frame_check` returned

The V1 detector (rule-based, no LLM) matched two frame library
entries on Claude's response:

- [FVS-008 Growth Frame](/corpus/library/FVS-008.html). Triggered
  by the density of growth-framed vocabulary ("retirement," "long-
  term," "returns"). Present in Claude's response because Claude
  reasons about Bitcoin through the lens of conventional retirement-
  savings products (index funds, 401(k)s, diversification), not
  because Claude advocates for Bitcoin.
- [FVS-007 Failure Framing](/corpus/library/FVS-007.html). Triggered
  when a document names what could go wrong (volatility risk,
  psychological pressure to panic-sell, concentration risk,
  regulatory uncertainty).

Voice classification: prescriptive. Coverage: causes present; risks,
stakeholders, trends, uncertainty absent by the detector's threshold.
The full V1 output is in the captured JSON; the rest of this writeup
focuses on what the V1 detector did not match, which is what the
divergence block exposes.

## The divergence block

When `frame_check` is called with `include_divergence=true`, the
response carries a top-level `divergence` block alongside
`analysis` / `agent_guidance` / `provenance`. The block has two
fields:

- `absent_frames`: an array of `AbsentFrameRecord` entries, one per
  FVS library_v3 catalog entry the V1 detector did not match. Each
  carries `frame_id`, `frame_title`, `citation_uri`,
  `absence_basis`, `domain_relevance_rationale`, `stability`, and
  `frame_version`. On Claude's response the array has 17 entries
  (library_v3 has 19 entries; the V1 detector matched two; FVS-020
  is excluded from divergence per library_v3's retirement-from-
  detection-scope decision).
- `envelope`: a `FaithfulnessEnvelope` with `spec_version`
  (`FRAME_DIVERGENCE_v1_c1.0`), `catalog_version` (`library_v3`),
  `surface` (`mcp`), `v4_2_execution` (`caller_side`,
  `caller_model`), `v4_2_engine_status` (`beta` per
  `V4_2_GAP_INVENTORY_v1.md §5`), `domain_inferred` (`finance` for
  this invocation), `provisional_count`, `faithfulness_note`, and
  `limitations`.

Two keys land on `agent_guidance`: `how_to_render_divergence` (the
caller-side composition instructions) and
`absence_is_not_prescription` (the guarantee that divergence output
never tells the user which frames they should have used).

## The faithfulness envelope, in plain terms

The envelope is where the MCP surface names its own limits. Three
of them matter for reading the composition below:

1. **The MCP surface does not run an LLM for divergence.** V4.2
   judgment is delegated to the caller's agent model per Rec I in
   ENGINE_TIER_RECOMMENDATIONS_v1.md. `absence_basis` on each
   record is scaffolding ("Caller's model must confirm no FVS-XXX
   identification cues fired in the supplied document"), not a
   finished verdict. The final absence verdict is the caller's
   model's call.
2. **Domain filter is not yet wired to FVS entry metadata.** Passing
   `domain_hint='finance'` echoes to `envelope.domain_inferred` but
   does not currently filter out FVS entries whose applicability
   metadata would exclude them for this domain; every non-matched
   catalog entry returns. A future contract minor version (c1.1)
   will add per-entry applicability metadata; until then, the caller
   filters by relevance at composition time.
3. **Divergence is not prescription.** The
   `absence_is_not_prescription` agent-guidance key says it plainly:
   the surfaced absences never imply the user should have used the
   absent frames. The reader judges relevance.

## The 17 absent frames

For completeness, the raw catalog the V1 detector did not match on
Claude's response (library_v3):

```
FVS-001 Frame Amplification          FVS-010 Completeness Illusion
FVS-002 Fluency-Quality Illusion     FVS-011 Stakeholder Frame
FVS-003 Prompt Attribution Error     FVS-012 Uncertainty Frame
FVS-004 Default Geometry             FVS-013 Oracle Frame
FVS-005 System Attribution Error     FVS-014 Temporal Anchoring
FVS-006 Identity Framing Asymmetry   FVS-015 Efficiency Frame
FVS-009 Risk Frame                   FVS-016 Authority by Citation
                                      FVS-017 False Balance
                                      FVS-018 Scope Narrowing
                                      FVS-019 Narrative Coherence
```

Each entry's full identification cues and counter-examples are
readable at `frame-check://library/FVS-XXX`.

## Caller-side V4.2 composition

This is the section the divergence contract exists to enable. The
MCP surface handed back raw absences; the caller's model does the
judging. Below is the composition I would run as the caller's
agent for this document, honoring
`agent_guidance.how_to_render_divergence` in `list` rendering mode.
The move on each entry: read the document, confirm whether the
identification cues for the frame are really absent, and render the
absence without prescription.

Five of the seventeen absences carry reader-relevant meaning for a
Bitcoin-retirement recommendation; the remaining twelve are
catalog-true absences that a reader of this document would not
typically care about. The reader-relevant five:

### [FVS-011 Stakeholder Frame](frame-check://library/FVS-011): absent, reader-relevant

Identification cues for the stakeholder frame: explicit surfacing
of who is affected differently by the decision (partner, dependents,
family, other parties to the choice). Confirmed absent on reading:
Claude's response addresses "you" as an abstract 35-year-old
allocator. Spouse, children, dependents, partner, and others the
decision touches are not named. A reader with a partner whose
risk tolerance differs, or dependents whose retirement relies on
this choice, reads a document that treats the decision as
individual. Whether that is a gap for this reader is their call;
the divergence surface names the absence, the reader decides
relevance.

### [FVS-012 Uncertainty Frame](frame-check://library/FVS-012): absent, reader-relevant

Identification cues for the uncertainty frame: explicit naming of
what the recommendation depends on being true, what would make the
recommendation wrong, which claims are forecasts versus established
facts. Confirmed mostly absent on reading: Claude uses the word
"uncertainty" once, in the compound "regulatory uncertainty," and
states specific allocation percentages ("2-5%," "modest
allocation") without naming what assumptions those numbers rest on.
The underlying empirical claims (historical volatility, long-term
correlation with stocks, survival of crypto asset class through
multi-decade retirement horizon) are delivered in a register that
reads as description, not speculation. A reader deciding whether
to act on the recommendation benefits from seeing that the uncertainty
frame is not load-bearing in this response; the specific percentages
are the answer the model produced, not the space of answers a
different set of assumptions would produce.

### [FVS-016 Authority by Citation](frame-check://library/FVS-016): absent, reader-relevant but ambiguous

Identification cues for Authority by Citation: the document cites
external institutional authorities (studies, regulators, named
experts) to ground claims. Confirmed absent on reading: Claude's
response cites nothing. No studies. No named institutions. No
regulatory positions. No external voices. Ambiguous for this reader:
the absence can read as "the response is not leaning on authority
instead of reasoning" (positive) OR "the response makes empirical
claims without grounding them in verifiable sources" (gap). Frame
Check does not adjudicate between those readings; the reader decides
which applies to their purpose.

### [FVS-017 False Balance](frame-check://library/FVS-017): absent, absence is appropriate

Identification cues for False Balance: the document forces a
symmetric presentation ("on one hand... on the other hand") even
when the evidence is asymmetric, treating a strong position and a
weak position as equal. Confirmed absent on reading: Claude
recommends against Bitcoin as a core retirement holding clearly and
does not pad the conclusion with a symmetric pro-Bitcoin case. The
absence here is not a gap; it is the correct shape for a document
that has a recommendation to make. Naming it explicitly is the
discipline of not mistaking absence for deficit.

### [FVS-018 Scope Narrowing](frame-check://library/FVS-018): absent, absence is appropriate

Identification cues for Scope Narrowing: the document narrows its
scope to a defensible claim while declining to address the harder
question the user is actually asking. Confirmed absent on reading:
Claude does not narrow. The response addresses the question as
posed ("is Bitcoin a good investment for retirement?") with a
direct recommendation and the reasoning that produced it. A reader
who wanted an evasive "it depends on your situation" answer did
not get one; that is a feature of this response, not a gap.

### The remaining twelve absences

The other twelve absent frames (FVS-001 Frame Amplification, FVS-002
Fluency-Quality Illusion, FVS-003 Prompt Attribution Error, FVS-004
Default Geometry, FVS-005 System Attribution Error, FVS-006 Identity
Framing Asymmetry, FVS-009 Risk Frame, FVS-010 Completeness
Illusion, FVS-013 Oracle Frame, FVS-014 Temporal Anchoring, FVS-015
Efficiency Frame, FVS-019 Narrative Coherence) are catalog-true
absences. The MCP surface returned them because they are in the
library_v3 catalog and did not match. A reader of this specific
document would not typically read them as meaningful gaps; the
scope-narrowing-by-relevance is the caller-side move. A different
document in a different domain would have a different relevant
subset.

## Reader sovereignty, operationally

Five of seventeen absences are reader-relevant. Three of those five
are gaps the reader might want to close (stakeholder, uncertainty,
authority-ambiguous); two are absences the reader should read as
appropriate (false balance, scope narrowing). No prescription in
either direction: the composition above names what the document
did not do and hands the reader the information to decide what to
do with it. That is the faithfulness contract for the absence
claim, and `agent_guidance.absence_is_not_prescription` is the
structural guarantee that keeps the composition honest.

## What the method missed

The MCP divergence surface has structural limits worth naming on
this specific document:

- **`domain_hint='finance'` did no filtering.** All 17 non-matched
  catalog entries returned. The faithfulness envelope's
  `limitations` field carries this self-disclosure; c1.1 will add
  per-entry applicability metadata so domain hints do real filtering.
- **V1 detection limits carry into divergence.** The V1 detector did
  not match FVS-009 Risk Frame on this response, even though Claude
  names four specific risks (volatility, cash flows, concentration,
  regulatory). The risk-frame identification cues require a higher
  density of risk vocabulary than this 1,249-character response
  contains by the current threshold. The caller's V4.2 judgment
  would typically flip this to present after reading the document;
  the divergence composition above chose not to, respecting the
  catalog-true absence as-surfaced rather than second-guessing the
  detector. Both approaches are contract-valid; the caller's model
  decides.
- **No V4.2 engine was invoked.** Per contract c1.0 §7.1, the MCP
  surface delegates V4.2 judgment to the caller's agent model. The
  composition above is my (the caller's) model doing that work.
  A reader of this worked example who runs the same invocation
  through a different agent will get a different composition; the
  underlying divergence block will be byte-identical.

## Why publish this worked example

Frame divergence is the AGI-era primitive Frame Check claims
(FRAME_DIVERGENCE_v1.md §3). Without a worked example, the claim
is abstract. This piece makes it concrete in one direction: what
the MCP surface emits, what the caller-side composition does with
it, and what the reader-sovereignty constraint looks like in
practice on a real AI-generated document in a real domain.

The pattern generalises. Any agent-integrated use of Frame Check
that passes `include_divergence=true` on `frame_check` receives
the same block shape; any caller-side model that honors the two
added `agent_guidance` keys produces a composition in the same
faithfulness register. This is the compounding shape: the contract
is stable, the block is deterministic, and the caller's model does
the judging. No vendor lock-in, no per-product tool proliferation,
no Frame Check LLM cost.

## Reproducing this analysis

```python
import json
from mcp_server import build_epistemic_payload

with open("source_document.md") as f:
    document_text = f.read()

payload = build_epistemic_payload(
    document_text,
    include_divergence=True,
    domain_hint="finance",
    divergence_rendering="list",
)
```

The exact payload is captured at
`divergence-on-claude-bitcoin-retirement-2026/divergence_output.json`
with `provenance.analysis_latency_ms` stripped so the file is
byte-stable across reruns. `provenance.analysis_cost_usd == 0.0`
holds under divergence because the MCP surface delegates V4.2
judgment to the caller; the envelope's `v4_2_engine_status` is
`beta` per `V4_2_GAP_INVENTORY_v1.md §5` at the moment this was
run (2026-04-24). The caller-side composition above is mine (one
caller's model); a different caller's model run against the same
block would produce a different composition in the same contract-
valid shape.

## Citation

Lucic, L. (2026). *Frame divergence in action: what frames Claude's
Bitcoin retirement recommendation did not use*. Frame Check Worked
Examples.
frame.clarethium.com/corpus/worked-examples/divergence-on-claude-bitcoin-retirement-2026/

Licensed CC-BY-4.0. The source document (Claude Haiku 4.5 response)
is the output of a third-party system (Anthropic); its reproduction
here is for structural analysis and falls under fair-use / fair-
dealing provisions for research and criticism. Only the Frame
Check analysis and the divergence composition are open-licensed.
