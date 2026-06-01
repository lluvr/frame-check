# Identity Framing Asymmetry

**FVS entry:** FVS-006
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12

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

**Adjacent frames:** Default Geometry (FVS-004, the defaults the identity operates against; FVS-004 withdrawn per INDEX.md "v1 publication state"), Frame Amplification (FVS-001, identity aligned with default is one precondition for amplification: what happens when the identity is aligned with the default and amplification compounds; the inverse is not symmetric), Prompt Attribution Error (FVS-003, the identity effect is prompt-level, not model-level; FVS-003 withdrawn per INDEX.md "v1 publication state")

**When this frame is appropriate:** Any time someone assigns a role, persona, or identity to an AI system expecting it to change behavior. Prompt engineering advice that says "tell the AI to be an expert." Any evaluation of whether role-assignment techniques work.

**When this frame is misleading:** When discussing identity effects in domains where all decisions are locked (some regulated domains show 4-5 locked decisions per scenario, leaving no room for identity effects). Also misleading when the user's goal IS the default behavior (telling the model to do what it would do anyway is redundant but not harmful).

**Honest limits:** The asymmetry is well-supported across 57 trials and 3 model families. Cross-domain replication exists but shows domain-dependent effects. The lock mechanism (why some decisions resist all identity framing) is not fully explained. The sample is AI-generated text, not human-AI collaborative decisions. Whether the asymmetry transfers to real-world task outcomes (not just text properties) is unmeasured.

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
