# Narrative Coherence

**FVS entry:** FVS-019
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** HI-012 (Fluency-Quality Illusion, narrative coherence is one form of fluency), EXP-094 (the confound where correct analysis within a wrong frame produces a coherent but wrong narrative)
**Status:** v1, single-curator, reviewers wanted

## Identification

A document tells a coherent story. The data points connect. The logic flows. The conclusions follow from the premises. This coherence feels like evidence of correctness because humans are wired to trust narratives. But narrative coherence is independent of factual accuracy: a completely fabricated story can be perfectly coherent, and a collection of accurate facts can be incoherent. AI systems produce highly coherent narratives by default because transformer models are trained to produce text where each token is conditioned on all preceding tokens, creating maximum local coherence. The coherence is an architectural property, not an epistemic one.

**What this frame makes visible:**
- How story structure makes claims feel true regardless of their factual basis
- Why a document that "makes sense" is not necessarily a document that is correct
- The distinction between logical coherence (the argument follows from its premises) and empirical coherence (the premises are true)

**What this frame makes invisible:**
- Data points that do not fit the narrative (they were omitted to maintain coherence)
- Alternative narratives that explain the same data differently
- The difference between "this story is well-told" and "this story is true"

**Positive examples:** An AI-generated analysis of a company's decline that constructs a compelling narrative: "rising costs led to margin pressure, which caused reduced investment, which led to competitive weakness, which accelerated the decline." Each step follows logically. The narrative is coherent. But: did rising costs actually cause margin pressure, or did management decisions cause both? The narrative picks ONE causal chain and tells it coherently, hiding the alternatives.

**Negative examples:** A document that explicitly presents competing narratives for the same data ("Narrative A: the decline was cost-driven. Narrative B: the decline was management-driven. The data is consistent with both.") is not operating from the narrative coherence frame because it makes the multiplicity of narratives visible.

**Adjacent frames:** Frame Amplification (FVS-001, narrative coherence deepens with each iteration as the story gets more detailed and more convincing), Fluency-Quality Illusion (FVS-002, narrative coherence is the macro version of fluency), Growth Frame (FVS-008, growth narratives are among the most coherent because growth is a simple story)

**When this frame is appropriate:** Evaluating any analytical document that tells a story: market analyses, case studies, strategic recommendations, historical accounts, investigative reports. Any context where the reader should ask "is this coherent because it is true, or because it is well-constructed?"

**When this frame is misleading:** Purely factual content that does not tell a story (data tables, specifications, reference material). Also misleading when applied to genuinely coherent truthful narratives: not every coherent story is fabricated.

**Honest limits:** Narrative coherence is not automatically detectable. The current detectors can identify: voice (analytical vs promotional), coverage breadth, temporal orientation, and epistemic basis. None of these directly measures narrative coherence vs factual accuracy. This entry names the pattern for reader awareness. Automated detection would require comparing the document's causal claims against verified causal relationships, which is an unsolved problem.

## Generation affordances

**Rewrite prompt structure:** "This document tells a coherent story. Identify the causal chain: A caused B caused C caused D. Then produce two alternative causal chains that explain the same data points differently. Name which data points are consistent with all three narratives and which are consistent with only one."

**Salient questions under this frame:**
- Is this coherent because it is true, or because it is well-constructed?
- What data points were omitted to make the story work?
- What alternative narratives could explain the same data?
- If one fact in the narrative turned out to be wrong, would the whole story collapse?

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Not directly detectable as a single signal. The combination of analytical voice + high coverage in one dimension + low uncertainty language + high fluency produces conditions where narrative coherence is most likely to be operating unchallenged.
**Branch B:** The pre-commit intervention disrupts narrative coherence by forcing the user to articulate their OWN narrative before reading AI's. The comparison reveals whether the user adopted AI's narrative or maintains their own.

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.000 |
| Gwet's AC1 (pairwise mean) | 0.964 |
| Raw agreement (pairwise mean) | 0.967 |
| Union prevalence (all families) | 98% |

Per-family positives (of 15 docs): Claude 14, Gemini 15, Grok 15, GPT-5 15.

**V4 detection mode:** meta (not detected by rule-based; consensus evaluation only)

**Interpretation:** Kappa paradox pattern (low Cohen's kappa due to prevalence extreme 98%, but Gwet's AC1 shows substantial cross-family agreement). Reliable under prevalence-robust metrics.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-13; grounded-authorship retrofit 2026-04-25 per FRAME_DIVERGENCE_v2.md §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04; prevalence 98 percent - the highest-prevalence frame in the catalog)
- HI-012 Fluency-Quality Illusion (narrative coherence is the macro-level instance of fluency)
- EXP-094 confound (correct analysis within wrong frame produces coherent but wrong narrative)
- Company-decline worked example (v1 Identification)
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Kappa paradox at extreme high prevalence. F-2026-027 showed kappa 0.000 (zero) but AC1 0.964 (substantial). Union prevalence 98 percent (Claude 14, Gemini 15, Grok 15, GPT-5 15 of 15) - virtually every document tells a coherent story; near-universal document presence makes Cohen's kappa non-informative. Kappa paradox-distorted; AC1 carries actual agreement signal under prevalence robustness.
2. Not directly detectable as a single rule-based signal. The combination of analytical voice plus high coverage in one dimension plus low uncertainty language plus high fluency produces conditions where narrative coherence is most likely operating unchallenged. No single rule-based test isolates narrative coherence specifically; detection mode is consensus evaluation only.
3. Automated coherence-vs-accuracy detection is unsolved. Comparing a document's causal claims against verified causal relationships requires real-world causal-graph knowledge that Frame Check does not have. The frame names the pattern for reader awareness; detection is reader-side discipline. Automating this requires advances in causal inference that are open research.

**Success record.** Two operationalized cases:
1. Company-decline worked example (v1 Identification). Document constructed compelling causal narrative ("rising costs led to margin pressure, which caused reduced investment, which led to competitive weakness, which accelerated the decline"). Counter-frame surfaced: did rising costs actually cause margin pressure, or did management decisions cause both? The narrative picks one causal chain and tells it coherently, hiding alternatives. Diagnostic: produce two alternative causal chains explaining the same data; identify which data points are consistent with all three vs only one.
2. EXP-094 confound integration. The confound where "correct analysis within wrong frame produces a coherent but wrong narrative" is the operational case study for narrative coherence as separate from factual accuracy. A perfectly coherent story can be false; a collection of accurate facts can be incoherent. The construction trace (T-356) is the antidote: generating your own causal model before reading AI's narrative creates the comparison point that reveals whether you adopted AI's narrative or maintained your own.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where the operator accepted a coherent AI narrative as true and later found that an alternative causal chain explained the data better, or that data points were omitted to maintain the narrative's coherence; (2) the alternative-narrative diagnostic applied (could other causal chains explain the same data); (3) outcome differential observed (narrative challenged, alternative pursued, decision re-anchored on more accurate causal model); (4) concrete first-person recall. Held open per FRAME_DIVERGENCE_v2.md P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application: ~2-5 minutes (identify causal chain; produce 1-2 alternative chains; check data points against each)
- V4.2 LLM judge invocation: limited applicability (consensus mode only; not rule-based-detectable)
- Alternative-narrative generation: ~5-10 minutes for substantive counter-narrative production
- Use depth: any analytical document that tells a causal story; especially valuable on AI-generated case studies, market analyses, historical accounts

**Applicability metadata.**
- Domains: market analysis (high stake-relevance), case studies (high), strategic recommendations (high), historical accounts (medium-high), investigative reports (high), AI-generated causal-chain content (very high; near-universal frame presence)
- Decision types: any decision based on causal-narrative analysis
- Stake levels: medium to high; coherent-but-wrong narratives at high stakes are costly
- Inappropriate contexts: purely factual content that does not tell a story (data tables, specifications, reference material); genuinely coherent truthful narratives where alternative-narrative production would be artificial

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa 0.000 (paradox-distorted), AC1 0.964 (substantial), raw 0.967, union prevalence 98 percent (Claude 14, Gemini 15, Grok 15, GPT-5 15 of 15) - the highest-prevalence frame in the catalog; near-universal document presence
- HI-012 Fluency-Quality Illusion as macro-level companion
- EXP-094 confound: correct-within-wrong-frame produces coherent-but-wrong narrative
- T-356 construction trace antidote
- V4 detection mode: meta (not detected by rule-based; consensus evaluation only)
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
