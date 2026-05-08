# Narrative Coherence

**FVS entry:** FVS-019
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13

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
