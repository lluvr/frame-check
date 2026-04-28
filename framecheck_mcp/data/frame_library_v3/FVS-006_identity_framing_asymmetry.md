# Identity Framing Asymmetry

**FVS entry:** FVS-006
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** HI-021 (Identity Framing Asymmetry), EXP-005 (57 trials, 3 models), EXP-025 (negation specificity), EXP-010 (architecture separation)
**Status:** v1, single-curator, reviewers wanted

## Identification

Identity framing in AI interaction is asymmetric: assigning a role or identity shifts behavior only when the identity opposes the model's default on the specific question. An identity that matches the default (telling a model that already defaults to caution to "be cautious") produces results indistinguishable from no identity at all. Counter-default identities diverge consistently. Certain decisions are locked by training-data priors regardless of identity framing.

**What this frame makes visible:**
- That "assign a role to get better results" only works in one direction (counter-default), and the popular advice to "tell the AI it is an expert" is only effective when the model's default for that question is non-expert behavior
- Which decisions are trainable (movable by framing) vs locked (immovable regardless of framing), and that stronger models lock more decisions
- How failure frames that repeat the identity's message weaken the effect (redundancy), while consequence frames compound when architecturally separated (system prompt + user message)

**What this frame makes invisible:**
- What the model's default actually IS for any given question (requires baseline testing, not intuition)
- Why some domains (regulated, institutional) lock more decisions than others (strategy domains show zero locks in some experiments)
- The difference between "the identity changed the model's behavior" and "the identity changed which part of the model's behavior distribution I sampled"

**Positive examples:** Telling Claude to adopt a "risk-focused analyst" identity when analyzing a market opportunity produces measurably different output (more risk identification, more caveats) than the same analysis without the identity. This works because Claude's default on market analysis is growth-oriented; the risk identity is counter-default.

**Negative examples:** Telling Claude to be "a thoughtful, careful analyst" produces no measurable change because Claude's default already includes thoughtfulness and care. The identity is redundant, not counter-default.

**Adjacent frames:** Default Geometry (FVS-004, the defaults the identity operates against), Frame Amplification (FVS-001, what happens when the identity is aligned with the default and amplification compounds), Prompt Attribution Error (FVS-003, the identity effect is prompt-level, not model-level)

**When this frame is appropriate:** Any time someone assigns a role, persona, or identity to an AI system expecting it to change behavior. Prompt engineering advice that says "tell the AI to be an expert." Any evaluation of whether role-assignment techniques work.

**When this frame is misleading:** When discussing identity effects in domains where all decisions are locked (some regulated domains show 4-5 locked decisions per scenario, leaving no room for identity effects). Also misleading when the user's goal IS the default behavior (telling the model to do what it would do anyway is redundant but not harmful).

**Honest limits:** The asymmetry is well-supported across 57 trials and 3 model families (EXP-005). Cross-domain replication exists (EXP-027/028) but shows domain-dependent effects. The lock mechanism (why some decisions resist all identity framing) is not fully explained. The sample is AI-generated text, not human-AI collaborative decisions. Whether the asymmetry transfers to real-world task outcomes (not just text properties) is unmeasured.

## Decision-readiness implication

**Meta-side frame.**

About how assigned roles shift LLM behavior asymmetrically. The [decision-readiness profile](/corpus/decision-readiness/) measures the resulting document; this entry names the mechanism by which prompting choices upstream shaped what dimensions the document addresses.

## Generation affordances

**Rewrite prompt structure:** "Identify the identity or role this document assumes for its audience ('the reader is an investor,' 'the reader is a risk manager'). What is the default identity for this kind of document? Is the assigned identity counter-default or aligned? If aligned, the framing adds nothing. Rewrite with a counter-default identity and note what changes."

**Counter-document prompt:** "This analysis was produced for a specific audience identity. Identify that identity and the model's default for this type of analysis. Then produce the same analysis addressed to the counter-default audience. The counter-default version should surface what the default version hides."

**Salient questions under this frame:**
- Does the assigned role actually differ from what the model would do by default?
- What would happen if no role were assigned?
- Are any of the conclusions locked regardless of role assignment?
- Am I using identity framing as a real intervention or as a ritual that feels productive?

## Worked example

**Document excerpt:** "As your financial advisor, I recommend a balanced portfolio approach that considers both growth opportunities and risk mitigation. Diversification across asset classes will help manage volatility while capturing upside potential."

**Frame present:** Advisory identity. The document is framed as expert financial advice, using "as your financial advisor" to establish authority.

**Frame absent:** Whether the advisory identity is actually counter-default or aligned. If the model's default for financial questions is already balanced, moderate advice, then "as your financial advisor" added nothing. The document would read identically without the identity framing.

**How to read past it:** Compare with and without the identity. Ask: "what would this model say about the same portfolio question with NO role assigned?" If the answer is the same balanced advice, the identity framing was cosmetic.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected when a document uses identity markers ("as an expert in," "from the perspective of," role language) combined with output that matches expected model defaults. The gap between the claimed identity and the actual behavioral shift is the signal.
**Branch B:** In the pre-commit intervention, the user's own identity framing can be surfaced: "what role am I assuming when I approach this question?" is a productive pre-commit that reveals the user's own default geometry.

## Vocabulary connections

- **The amplification thesis** (HI-062): identity framing that aligns with the default amplifies the default rather than challenging it.
- **The construction trace** (T-356): generating your own analysis (with its own implicit identity) before consulting AI creates the comparison point that reveals whether the AI's identity framing actually shifted anything.

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | undefined |
| Gwet's AC1 (pairwise mean) | 1.000 |
| Raw agreement (pairwise mean) | 1.000 |
| Union prevalence (all families) | 0% |

Per-family positives (of 15 docs): Claude 0, Gemini 0, Grok 0, GPT-5 0.

**V4 detection mode:** meta (not present in mixed_genre_v1)

**Interpretation:** Frame absent from this corpus; reliability undefined by lack of variability.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-12; grounded-authorship retrofit 2026-04-25 per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04; frame absent from corpus, prevalence 0 percent)
- HI-021 Identity Framing Asymmetry case study (origin)
- EXP-005 controlled experiment (57 trials, 3 model families)
- EXP-025 negation specificity
- EXP-010 architecture separation
- EXP-027/028 cross-domain replication
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Frame absent from F-2026-027 mixed_genre_v1. Cross-family AC1 1.000, prevalence 0 percent - same corpus mismatch as FVS-003/004/005. Identity-framing detection requires AI-interaction-prompt content not present in mixed_genre_v1. Reliability undefined by lack of variability.
2. Lock mechanism not fully explained. Some decisions are immovable regardless of identity framing; some regulated domains show 4-5 locked decisions per scenario, while strategy domains show zero locks. The mechanism (why some decisions resist all identity framing) is empirically observed in EXP-027/028 but not theoretically anchored.
3. Sample is AI-generated text, not human-AI collaborative decisions. EXP-005's 57 trials measure text properties under identity framing. Whether the asymmetry transfers to real-world decisions and outcomes (not just text features) is unmeasured. Generalization claim is open.

**Success record.** Two operationalized cases:
1. EXP-005 well-supported across 3 model families. The asymmetry is reproducible: counter-default identity framing produces measurable behavioral shifts; aligned identity framing produces no measurable change. 57 trials across 3 model families is a solid empirical foundation.
2. Cross-domain replication (EXP-027/028). Domain-dependent effects observed; some domains (strategy) show zero locks while others (regulated) show many. This dependency itself is an empirical finding that anchors the claim that identity framing is not universally effective. Operational diagnostic: ask "what is the model's default for this question; is the assigned identity counter-default or aligned" before assuming identity framing will shift behavior.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where the operator caught themselves applying redundant identity framing (telling AI to do what it would have done anyway) versus genuinely counter-default framing; (2) the asymmetry diagnostic applied (did the framing actually shift output); (3) outcome differential observed (prompt-engineering practice revised, identity framing dropped where redundant or replaced with counter-default); (4) concrete first-person recall. Held open per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check-mcp/blob/master/FRAME_DIVERGENCE_v2.md) P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application: ~30-60 seconds per identity-framing decision (ask "is this counter-default or aligned")
- V4.2 LLM judge invocation: limited applicability (corpus mismatch; detection requires AI-interaction-prompt content)
- Baseline-vs-identity controlled comparison: requires running same prompt with and without identity assignment; ~5 minutes of API time per check
- Use depth: any prompt-engineering decision that includes role or persona assignment

**Applicability metadata.**
- Domains: prompt engineering (high stake-relevance), AI-interaction design (high), AI workflow optimization (medium-high), prompt-engineering tutorials and advice (high)
- Decision types: prompt design, role assignment, persona engineering
- Stake levels: medium (impact compounds across many invocations of same prompt)
- Inappropriate contexts: domains where all decisions are locked (no room for identity effects); cases where the user's goal IS the default behavior (telling model to do what it would do anyway is redundant but not harmful)

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa undefined, AC1 1.000, raw 1.000, prevalence 0 percent (frame absent from corpus)
- EXP-005 origin: 57 trials, 3 models; well-supported asymmetry
- EXP-025 negation specificity
- EXP-010 architecture separation
- EXP-027/028 cross-domain replication: domain-dependent lock effects
- HI-021 origin study
- V4 detection mode: meta (not present in mixed_genre_v1)
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
