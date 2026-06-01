# Annotated interpretation: Claude vs Grok on the bitcoin retirement question

This is an illustrative reading of
`corpus/four-llms-bitcoin-claude/peer_with_four-llms-bitcoin-grok.json`.
The comparison is computed automatically; this file teaches how
to READ it without overgeneralizing.

## The pair

- **Claude** (`four-llms-bitcoin-claude`): 1249 characters,
  responding to the prompt "should I retire on Bitcoin"
- **Grok** (`four-llms-bitcoin-grok`): 2097 characters,
  responding to the same prompt

Both are independent peer responses; neither is a transformation
of the other. The comparison is non-directional. Naming WHICH
model has more of something is a description of the two specific
responses, not a model verdict.

## Reading the comparison field by field

### Coverage: Claude 1/5 vs Grok 2/5

Claude addresses ONE analytical perspective (causes). Grok
addresses TWO (risks, trends). Their addressed sets overlap on
nothing.

**Substantive read for THIS pair:** the two models structured
their responses around different perspectives. Claude leaned
into WHY (causes — explaining what makes Bitcoin retirement
risky); Grok leaned into WHAT IF (risks) and WHAT'S CHANGING
(trends). Different framings of the same question.

**What this comparison cannot conclude:** "Claude has narrower
coverage than Grok in general." This is one prompt, one
generation, one comparison. Coverage might invert on the
startup-offer question, or on a different bitcoin prompt, or
with different sampling parameters. The aggregate findings page
shows that across 12 peer pairs, coverage differs in 10 of 12.
The pattern is corpus-level; individual-pair attribution is not.

### Calibration: Claude hedge ratio 0.00 (4 claims) vs Grok 0.20 (15 claims)

Claude makes 4 numerical claims, none hedged. Grok makes 15
numerical claims, 3 hedged (20%).

**Substantive read:** Grok wrote a longer response with more
numerical specifics AND more hedging. Claude wrote a shorter
response with fewer specifics and no hedging.

This is interestingly ambiguous. A reader might conclude:
- "Grok is better calibrated" (more hedges)
- "Claude is more parsimonious" (fewer specific claims to
  calibrate)
- Both — different rhetorical strategies for the same prompt

The peer comparison surfaces the structural difference. It does
not tell you which response is BETTER. That depends on what the
reader needs from the response.

### Evidence: sentence-attribution Claude 0% vs Grok 7%

Neither response cites external sources for numerical claims
(verification ratio is null on both — the corpus profiles were
computed without Source Network). The difference here is in
SENTENCE-LEVEL ATTRIBUTION: Grok's response carries some
attribution language ("according to," "studies show," etc.) at
7% of sentences; Claude's response has none.

**Substantive read:** Grok is more ATTRIBUTED than Claude in
this response. Whether the attributions Grok added are
faithful to real sources or invented is a different question
that Frame Check's structural analysis cannot answer. The
comparison is the start of an investigation, not the end.

**Important caveat:** because BOTH peers have null verification
ratios, the evidence dimension here is comparing the SECONDARY
signal (sentence-attribution percentage), not the PRIMARY
signal (numerical-claim verification ratio). This is honestly
disclosed in the comparison_text but a reader skimming the
narrative might miss it.

### Robustness: neither peer had claims checked against external sources

This dimension is non-comparable for THIS PAIR (and for ALL
pairs in the v1 corpus — see the aggregate findings: robustness
is non-comparable in 12 of 12 peer pairs). The corpus profiles
were computed offline without Source Network.

**Substantive read:** robustness is a corpus gap, not a finding.
A future Phase 2.5 corpus refresh with Source Network enabled
would fill this in. A researcher should NOT report "robustness
agrees" for any peer pair in v1; they should report "robustness
not measured."

### Counterfactual: only Grok engages with counterfactual thinking; Claude does not

Grok's response includes uncertainty markers and engages with
how the recommendation might be wrong (failure-framing
present). Claude's response does not (FVS-007 fires for Claude;
not for Grok).

**Substantive read for THIS pair:** Grok's response is more
counterfactually engaged than Claude's.

**Aggregate connection (the outlier signal).** The aggregate
findings page
(`results/{date}-{corpus_hash}/aggregate.md`) computes per-
group median-distance outlier identification: for each peer
group, the member whose signal value is most different from
the group median on a given dimension is the outlier on that
dimension in that group. The table reports Claude as the
counterfactual outlier in 2 of 2 peer groups it appears in.

This is the methodologically correct signal: Claude's
counterfactual signal_value (False) is the outlier from the
group median (most members engage; Claude does not) in BOTH
the bitcoin and startup peer groups. The per-LLM PARTICIPATION
count would have been the wrong signal — participation just
means "Claude was in N differing pairs," which doesn't
distinguish whose value is the outlier.

**This is a corpus-level signal, not a model-level claim.** It
holds in 2 of 2 Claude-containing peer groups (N=2). Whether
Claude is systematically less counterfactually engaged across
DIFFERENT questions and DIFFERENT corpora is a separate
question; the aggregate findings document the per-group
finding honestly with explicit N.

## Synthesizing the comparison

How Claude and Grok differ structurally on the bitcoin
retirement question:

1. **Coverage divergence**: Claude leans causes; Grok leans
   risks + trends. Neither is wrong; both are valid framings
   of the same question.

2. **Calibration divergence**: Grok has more numerical claims
   AND more hedges; Claude has fewer of both. Different
   rhetorical strategies; structural comparison cannot pick a
   winner.

3. **Evidence divergence**: Grok carries some sentence-level
   attribution; Claude has none. Grok's attributions warrant
   independent verification; Claude's complete absence is a
   gap.

4. **Counterfactual divergence**: Grok engages with
   counterfactual thinking; Claude does not. The aggregate
   findings identify Claude as the counterfactual OUTLIER (via
   median-distance from the group) in 2 of 2 peer groups it
   appears in.

5. **Robustness**: not measured.

## What this comparison does NOT tell us

- Which response is "better" — that depends on what the reader
  needs. Frame Check's structural analysis is silent on quality.
- Whether either response's claims are factually correct — the
  comparison is structural, not semantic.
- Whether Claude is "less hedged in general" — this is one
  prompt, one generation. Cross-question and cross-prompt
  generalization needs more pairs.
- What WOULD have happened if either model had been re-prompted
  with sampling temperature 0 — single-shot comparisons are not
  controlled experiments.

## What a writeup of this comparison would say

> On the bitcoin retirement question, Claude and Grok produce
> structurally different responses across four of five
> decision-readiness dimensions. Claude's response is shorter
> (4 numerical claims vs Grok's 15), structured around causes,
> and unhedged; Grok's response is longer, structured around
> risks and trends, with 20% of claims hedged. Grok engages
> with counterfactual thinking; Claude does not. The aggregate
> findings identify Claude as the counterfactual outlier
> (median-distance method) in 2 of 2 peer groups it appears in.
> Evidence dimension comparison reflects sentence-level
> attribution only (verification ratios are non-comparable
> across the v1 corpus); Grok's 7% sentence-attribution
> warrants independent verification.
>
> Neither response should be treated as more decision-ready
> than the other on the structural signals alone; the
> comparison surfaces structural differences that a reader
> can use as a starting point for their own judgment.
>
> Cited from the Frame Check decision-readiness corpus,
> revision `70e2a95a9d1f`.
