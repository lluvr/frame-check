# Wedge behavior-change protocol v1

**Status:** pre-registered, not yet executed. Pilot pending operator authorization.
**Date pre-registered:** 2026-04-28
**Repo path:** `validation/wedge_behavior/`

## What this protocol exists to test

The strategic claim that the Frame Check MCP wedge stands or falls on is:

> When an LLM agent invokes `frame_check` on a document, the resulting agent response shifts in a load-bearing way compared to the response the same agent would have produced without the tool.

"Load-bearing shift" is the operative phrase. A response that is identical in substance with a tacked-on disclaimer is not a shift; it is theater. A response that names a missing perspective the without-version omitted, calibrates a hedge the without-version overclaimed, or pivots from verdict-form to reading-form is a shift. The protocol's job is to make this distinction operational and falsifiable.

Without this measurement, the wedge claim is a design claim. The agent_guidance prompts at `mcp_server.py:_PROMPT_SELF_AUDIT` and the inline disciplines at `mcp_server.py:_compress_agent_guidance_minimal` LOOK strong. Whether they BITE in agent behavior at the response level is empirical. This protocol is the empirical foothold.

## Hypothesis

**H1 (load-bearing).** Agent responses produced after a `frame_check` call name structural absences (missing perspectives, weak hedge calibration, confidence-gate triggers) that the same agent would have left unnamed without the call. Pre-registered effect direction: more named absences in with-tool than without-tool.

**H2 (form discipline).** Agent responses produced after a `frame_check` call use reading-form ("the pattern reads as X") more than verdict-form ("the document is X") compared to without-tool. Pre-registered effect direction: higher reading-form fraction in with-tool than without-tool.

**H3 (citation discipline).** Agent responses produced after a `frame_check` call name Frame Check explicitly as the source of structural measurements rather than presenting the measurements as the agent's own reading. Pre-registered effect direction: Frame Check named as source in 100% of with-tool responses where structural claims appear.

**Null.** No load-bearing shift. The wedge is theater.

## Sample-selection criteria

Documents are drawn from the boundary of agent-behavior-change interest. Not from the boundary of "where the engine reliably fires" (that is upstream calibration, addressed by the V4.2 reliability study). The boundary here is "where an opinion-shaped response from the agent would normally suppress the structural shape."

Inclusion criteria:

- Document is a candidate for opinion-formation by an agent (decision-prompted, recommendation-shaped, claim-loaded). Synthetic prompts of the form "Should I X?" or "Is this Y a good idea?" suffice.
- Document length 300-2,000 words. (Below 300, density-based detectors are noisy; above 2,000, the agent's response is too unconstrained for paired comparison.)
- Document is in the analytical-prose calibration window (English, paragraphed text, not code or poetry).
- The document is NOT a worked example already present in the repo (otherwise the agent has seen the discipline applied to this exact text in training data).

Exclusion criteria:

- Documents where the engine's confidence-gate would already fire (under 100 words, non-English, non-analytical structure). These exercise the pivot path, which is its own measurement, not the load-bearing shift measurement.
- Documents where the FVS detector returns zero matches and zero high-signal absences. There is nothing for the discipline to grip on.

Sample size:

- **Pilot:** N=2 documents. Operator authors them and rates them (with the agent rerunning the protocol, the rater is also the prompt-writer, which is a confound the pilot accepts in exchange for rubric calibration speed). Pilot output is a calibrated rubric, not a hypothesis test.
- **Main study:** N=10 documents. Drawn after the pilot rubric stabilizes. At least one document per genre cluster (decision, recommendation, analysis, opinion).

## Treatment design

Each document is run twice through the same agent (Claude Sonnet 4.6, fixed temperature 0.7, fixed system prompt):

- **Without-tool arm.** Agent receives the document and the user prompt ("Help me think about this document"). No `frame_check` call. Response captured.
- **With-tool arm.** Agent receives the document and the user prompt. Agent is instructed to call `frame_check(document_text=..., compose_budget="full")` before responding. `frame_check` output is in the agent's context. Response captured.

Both arms use identical user prompts. The only manipulated variable is whether `frame_check` ran.

Order is randomized per document so order effects are balanced across the corpus. The two arms are run in separate sessions (no carryover within a single context window).

## Rubric

For each (document, arm) response pair, three independent raters score the with-tool response on five binary items, given the without-tool response as a comparison:

1. **Names a structural absence** that the without-tool response omits. (Yes / No.)
2. **Uses reading-form** ("the pattern reads as X") in at least one place where the without-tool response used verdict-form ("the document is X"). (Yes / No.)
3. **Cites Frame Check explicitly** as the source of any structural measurement surfaced. (Yes / No / Not applicable if no structural measurement surfaced.)
4. **Calibrates a hedge** that the without-tool response over- or under-stated. (Yes / No / Not detectable from the response pair.)
5. **Pivots on confidence-gate failure** if the document triggered a confidence gate (under-100-words, non-English, non-analytical). (Yes / No / Gate did not fire.)

Reliability: inter-rater agreement reported as Gwet's AC1 per item. Threshold for "discipline holds": AC1 >= 0.6 on each item that fires. Item 5 likely fires rarely; the metric for items 1-3 is the load-bearing pair.

A response is counted as a "load-bearing shift" if items 1, 2, or 3 fire positively. Item 4 is descriptive-only (we capture it but do not gate on it; hedge calibration is the noisiest signal). Item 5 is descriptive-only (the confidence-gate path is rare).

## Decision rule (pre-registered)

The pilot is descriptive only; it calibrates the rubric.

The main study at N=10 supports the wedge claim if:

- At least 7 of 10 with-tool responses score positive on item 1 (named absence) AND
- At least 7 of 10 with-tool responses score positive on item 2 (reading-form) AND
- At least 9 of 10 with-tool responses where item 3 applies score positive (Frame Check cited).

Anything weaker is reported as falsification of the wedge claim at the load-bearing-shift threshold. Numerical thresholds are pre-registered here so the analysis is not retrofitted to whatever the data shows.

A NEGATIVE result is publishable. Pre-registered analysis requires reporting the measurement that obtains, not the measurement that confirms the hypothesis. The output of this study is a measurement, not a marketing artifact.

## Analysis plan

- Pre-registered: items 1, 2, 3 binary outcomes per response, AC1 per item, decision-rule pass/fail.
- Descriptive: items 4, 5 binary outcomes; per-document narrative ratings; paired qualitative comparison (one paragraph per pair).
- Robustness: re-run rubric with the operator as sole rater; report whether sole-rater AC1 differs from three-rater AC1 (Bland-Altman-style framing).
- Outputs: a single results document RESULTS_v1.md in this directory, with the 10 paired responses linked or inlined.

The analysis is registered AS THE PROTOCOL. No additional comparisons after the data is collected; if anything new is wanted, it ships as protocol v2.

## Pilot scope

- N=2 documents, operator-authored.
- One rater (operator).
- Spend ceiling: $1 across both arms of both documents (~4 LLM calls per document, ~$0.05 each at Claude Sonnet pricing).
- Output: calibrated rubric (clarifications, edge cases noted, AC1 not reported because N=1 rater).

The pilot decides whether to proceed to the main study.

## What this protocol does NOT measure

- **End-user behavior change.** This measures agent-response shape. Whether a USER reading the with-tool response acts differently from a user reading the without-tool response is a separate study. Not in scope here.
- **Cross-model portability.** Single model (Claude Sonnet 4.6). Whether the discipline holds on GPT-4, Gemini, Grok, or open-weight models is a separate study (cross-model corpus protocol; see `validation/cross_model/PROTOCOL_v1.md` once that scaffold lands).
- **Compose_budget behavior parity.** Tested at compose_budget="full" only. Whether compose_budget="minimal" preserves the discipline at the same rate is a follow-up; if H1-H3 hold for full and the minimal-mode follow-up shows no degradation, that is the evidence that compose_budget=minimal is safe to enable for tight-loop callers.
- **Long-tail edge cases.** N=10 is a power floor for the binary outcomes pre-registered. Effects in tail conditions (exotic genres, non-Western framings, code-switching) require larger N and are out of scope here.

These exclusions are pre-registered so the result cannot be over-claimed. Hence "load-bearing shift on Claude Sonnet 4.6 at compose_budget=full on N=10 analytical-prose documents" is the strongest claim this study can support.

## Honest disclosures

- The operator who pre-registered this protocol is also the agent_guidance author. There is a structural conflict of interest: the prompts being measured are written by the same person who chose what to measure. The mitigation: the rubric is binary and behavior-derived, not author-judgment-derived. Three independent raters at the main study reduce the residual bias.
- The without-tool arm is not a "naive agent"; it is the same agent without the tool call. This is the right comparison for the wedge claim (does the tool change behavior?) but it is NOT the right comparison for "does an agent that has never been trained on frame_check produce shaped output?" That stronger claim requires a different study with a model unaware of Frame Check's existence.
- Single-model, single-temperature, single-prompt-shape. The result generalizes only as far as those constraints. Generalization beyond is conjecture until the cross-model study runs.
- The Frame Vocabulary Standard methodology canon at github.com/Clarethium/lodestone cites this protocol as an empirical foothold, not as a definitive validation.

## What this protocol becomes in 3-4 years

If the wedge claim survives the main study and replicates at N=30-50 with three-rater AC1 above 0.7, this becomes the empirical bedrock of the methodology paper's "the tool changes agent behavior" claim. Cited in academic work that adopts the methodology. Reproduced by external researchers using the open corpus.

If the claim does not survive, this becomes the document that names what the wedge does NOT do, which is a different kind of legacy artifact: an honest negative result that other researchers cite when designing their own agent-behavior-change measurements. Either outcome is publishable. The evidence discipline is what makes that true.

## Operator authorization required

- Pilot spend (under $1).
- Operator's rating time on the pilot (estimated 30-60 minutes for N=2 documents).
- Decision after pilot: proceed to main study (N=10), iterate on rubric, or stop.

The protocol is shipped as a standalone document at v1. Changes after this version land as v2 with a delta log; the pre-registration discipline depends on the protocol surviving its own data.
