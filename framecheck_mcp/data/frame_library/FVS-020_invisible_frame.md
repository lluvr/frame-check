# The Invisible Frame

**FVS entry:** FVS-020
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** M-004 (Frame Inventory, the founding insight), HI-061 (Frame Amplification), the value test (does it reduce manipulability)
**Status:** v1, single-curator, reviewers wanted

## Identification


> **Detection status (2026-04-23, Step 4 ratification): `vocabulary_only`.**
> FVS-020 is retired from V4 detector emission. Path A library revision
> attempt in library_v2 produced cross-family AC1 REGRESSION (v1 -0.161,
> v2 -0.453). The frame's interpretive dimensions (load-bearing claims,
> unnamed frame, non-obvious within genre) each require judgment that
> does not converge across LLM families, and multi-condition tightenings
> multiplied variance rather than reducing it.
>
> FVS-020 remains in the FVS vocabulary and library as a reader-
> orientation concept. Readers and curators may invoke it when asking
> "what frame is this document operating from?". A useful interpretive
> prompt even though text-level automatic detection cannot achieve
> useful cross-family reliability at library v1/v2 definitions.
>
> V4.2 LLM-judge detector excludes FVS-020 from its emission panel.
> V4.1 rule-based detector does not include FVS-020 in its rule set
> (FVS-020 was never rule-addressable).
>
> This retirement is reversible if a future library revision produces
> a text-property definition that achieves cross-family Gwet AC1 >= 0.55
> under the pinned evaluation panel. Step 4 Path A attempt is archived
> in library_v2/; it did not pass that bar.

Every document operates from a frame. The frame determines what is emphasized, what is omitted, which conclusions are reachable, and which are hidden. The frame is invisible to the reader unless deliberately surfaced. This is not a specific frame but the meta-condition of all frames: the fact that you are inside one right now and do not know which one. The invisible frame is the reason Frame Check exists. Every other entry in this library names a specific frame. This entry names the condition of not knowing which frame you are in.

**What this frame makes visible:**
- That no text is unframed (every document operates from some perspective)
- That the reader's own frame interacts with the document's frame (you see what your frame and the document's frame both make visible; everything else is invisible to both)
- That asking "what frame is this?" is itself a frame-level move that most readers do not make
- That the most dangerous frames are the ones that feel like "just describing reality" because they are invisible

**What this frame makes invisible:**
- This is a self-referential entry: what the invisible frame makes invisible is precisely what you cannot see until you name the frame. The answer is different for every document and every reader.

**Positive examples:** Any document that presents itself as neutral, objective, or comprehensive without naming its perspective. "This is a balanced analysis of..." is a frame claim, not a frame transcendence.

**Negative examples:** A document that begins "This analysis takes the perspective of [X] and deliberately does not address [Y, Z]" has made its frame visible. The invisible frame does not apply because the frame has been named.

**Adjacent frames:** All other FVS entries. Every named frame in this library is one specific instance of the invisible frame being made visible. Frame Amplification (FVS-001) is what happens when the invisible frame goes uninterrupted. The Fluency-Quality Illusion (FVS-002) is the surface mechanism that keeps the frame invisible. The Oracle Frame (FVS-013) is the reader posture that accepts the invisible frame.

**When this frame is appropriate:** Always. This entry is the reason the library exists. Surfacing the invisible frame is the cognitive move the product teaches.

**When this frame is misleading:** When it produces frame-paralysis: the realization that everything is framed can lead to "nothing can be trusted" which is nihilism, not literacy. Frame awareness is a tool for better judgment, not a tool for abandoning judgment. The goal is to SEE the frame, choose whether to accept it, and act from the choice. Not to be paralyzed by the existence of frames.

**Honest limits:** This is a meta-entry. It does not describe a specific detectable pattern. It describes the condition that all other entries address. A library of frames can never be complete because new frames can always be named. The invisible frame is the permanent reminder that the library has blind spots. This entry is honest about that limit by naming it as the entry itself.

## Decision-readiness implication

**Meta-meta frame.**

Every document operates from a frame; the invisible frame is the fact that you are inside one. Not a specific dimension. The [decision-readiness profile](/corpus/decision-readiness/) is the structural counterpart: it measures dimensions of decision support without claiming to identify the frame itself. Together, the profile (this is what the document does to your decision-readiness) and the Invisible Frame (you are reading from a frame) are the two halves of decision-aware reading.

## Generation affordances

**Rewrite prompt structure:** "Before reading further, pause and ask: what frame is this document operating from? Write your answer in one sentence. Then continue reading. At the end, check: was your initial reading of the frame correct, or did the document shift your frame without you noticing?"

**Salient questions under this frame:**
- What perspective is this document built from?
- What would I not think to question if I accepted this frame?
- What frame am I operating from as I read this?
- If I named the frame and stepped outside it, what would I see?

## Worked example

This entry IS its own worked example. You are reading a library entry that claims to name a meta-condition of all framing. What frame is this entry operating from? It assumes that frame awareness is valuable, that named frames are more visible than unnamed frames, that the cognitive move of surfacing frames improves judgment. These assumptions are not proven universally. They are the frame from which this library was built. The library does not transcend framing. It participates in it, deliberately and named.

## Branch applicability

**Primary branch:** Both A and B
**Branch A:** This is what the framing portrait is FOR. Every Frame Check analysis is an attempt to make the invisible frame visible. The portrait names coverage gaps, voice, temporal orientation, epistemic basis. Each of these is a partial surfacing of the invisible frame.
**Branch B:** The pre-commit intervention is the most direct response to the invisible frame. By writing your answer first, you make YOUR invisible frame visible to yourself. The comparison with AI's frame reveals both.

## Vocabulary connections

- **The amplification thesis** (HI-062): the invisible frame is what gets amplified. Without naming it, AI reinforces whatever frame was already invisible.
- **The construction trace** (T-356): generating your own analysis is the primary method for making the invisible frame visible. You discover your frame by trying to work without one and seeing what you default to.
- **The first read** (M-002): the somatic response that keeps the frame invisible. The body reads the frame before the mind can examine it.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per [fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md). The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** FVS-020 is excluded from V4.2 engine emission per Step 4 ratification (`vocabulary_only` status; see [INDEX.md](https://github.com/lluvr/frame-check/blob/master/data/frame_library/INDEX.md)). The frame is part of the FVS vocabulary but the engine does not emit a `library_consensus_ac1` for it. See `meta.fvs_020_status` in V4.2 results.

**Intra-rater stability.** FVS-020 is excluded from V4.2 engine emission per Step 4 vocabulary_only status; no intra-rater value applies. Reference intra-rater values for the 19 emitting frames live at [fvs_eval/v4/grok_intra_rater_ac1.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/grok_intra_rater_ac1.json).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM judge agreement on this frame's detectability under library_v4 Identification text; it does NOT measure agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check/blob/master/METHODOLOGY.md) section 1.3, the V1 detector's external-validation study against human labelers (mixed-genre n=12) returned macro-F1 0.157 (chance-level); library_v4 LLM-judge cross-family agreement has not been re-validated against human labelers. Read AC1 as a useful proxy for inter-LLM consensus, not as validated agreement with a human-derived ground truth.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.088, kappa 0.122, union 15/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): +0.25.
- **library_v2 (earlier variant):** Gwet's AC1 0.179, kappa 0.140, union 12/15.

See [fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md) §3 for library-wide tier context and [fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md) §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: [fvs_eval/mixed_genre_v1](https://github.com/lluvr/frame-check/tree/master/fvs_eval/mixed_genre_v1) n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.339 |
| Cohen's kappa (pairwise mean) | -0.014 |
| Raw agreement (pairwise mean) | 0.600 |
| Union prevalence | 15/15 = 100% |
| Intersection (all 4 agree positive) | 4/15 |

Per-family positives (of 15 docs): Claude 15, Gemini 8, Grok 15, GPT 8.
