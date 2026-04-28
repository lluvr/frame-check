# Authority by Citation

**FVS entry:** FVS-016
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** detect_epistemic_basis in framing.py, EXP-094 (tolerance collisions hiding real fabrications), HI-059 (Claim-Binding Fabrication)
**Status:** v1, single-curator, reviewers wanted

## Identification


**Authority by Citation fires when a document uses the form of citation (source references, named authorities, quoted experts) to create an impression of evidence, but the citation does not actually support the claim it is attached to.** The frame is in the gap between citation-form and citation-substance. AI systems generate citation-like language by default because citation patterns are heavily represented in training data.

**Three cases fire the frame:**
1. **Fabricated citation.** The source does not exist (AI-generated "according to a 2024 MIT study" that cannot be looked up).
2. **Misattributed citation.** The source exists but does not say what the document claims it says, or is real but not supporting the specific claim attached to it.
3. **Authority-veneer citation.** The source is named but vague ("industry analysts," "according to research," "a Harvard study"), blocking verification and using the institution's authority as evidence substitute.

**The frame does NOT fire when:**
- Citations are real, specific enough to verify, and support the attached claims. A historian citing a specific book, a journalist quoting a named expert by name and role, a policy analyst referencing an executive order by number or date: these are genuine use of evidence, not authority by citation.
- Arguments are made via named authorities whose positions are reported accurately. Citing Harold Varmus on NIH cuts is not the frame; inventing a "2024 NIH internal memo that said..." is.
- Historical, legal, or scholarly references are used in the expected genre convention. A research summary that names its sources with enough specificity to look them up is exhibiting citation practice, not authority-by-citation.
- Illustrative or rhetorical references (e.g., "as Orwell warned") that are clearly rhetorical and not evidentiary do not fire; they are understood as allusion.

**What this frame makes visible:**
- How the FORM of citation (mentioning a source, using quotation marks, naming a study) creates an impression of evidence regardless of whether the citation is accurate
- The gap between "this claim has a citation" and "this claim is verified by the cited source"
- Why AI-generated documents that cite "according to" or "research shows" may be borrowing the authority of citation form without the substance

**What this frame makes invisible:**
- Whether the cited source actually says what the document claims it says
- Whether the source exists at all (fabricated citations are common in AI output)
- Whether the source is authoritative for THIS specific claim (a real source making a different point)
- The selection bias: which sources were cited and which were omitted

**Positive examples:** An AI-generated research summary that cites "according to a 2024 study by MIT researchers" without naming the specific study, DOI, or publication venue. The citation has the form of authority but not the substance. Also: "industry analysts project" without a named analyst or methodology.

**Negative examples:** A document that cites specific studies with DOIs, quotes exact figures with page numbers, and the citations can be independently verified. This is genuine evidence, not authority by citation. A journalist naming an expert ("Dr. Jane Doe, professor of epidemiology at Johns Hopkins") whose quoted position reflects their actual stated views.

**Adjacent frames:** Fluency-Quality Illusion (FVS-002, citation form is part of the fluency that creates the illusion), Oracle Frame (FVS-013, citations reinforce oracle mode by making the output look researched), Uncertainty Frame (FVS-012, genuine citations include uncertainty; authority-by-citation citations present certainty), False Balance (FVS-017, false balance often uses authority by citation to ballast each pole; named figures on each side give an authority signal the reader translates into evidence weight)

**When this frame is appropriate:** Evaluating any document that uses citation-like language. Research summaries, policy recommendations, market analyses that reference studies or data. Any context where the authority of the claims rests on external sources.

**When this frame is misleading:** Documents that genuinely cite and have been verified. Not every citation is fabricated. The frame is a prompt to CHECK, not to dismiss.

**Honest limits:** The epistemic basis detector in framing.py measures sourced vs unsupported numerical claims but does not verify whether the cited sources are real or accurate. Authority by citation is detectable only as a pattern (citation language present with low verifiability), not as a fact (the citation is wrong). Full citation verification requires external lookup.

**Revision note (2026-04-23, Phase 1C):** Revised from v1 with explicit 3-case fire conditions and 3-case exclusion conditions, resolving narrow-vs-broad reader split identified in F-2026-027 and F-2026-030. v1's opening sentence ("A document establishes credibility by citing sources") licensed a broad reading (ANY citation use = authority-by-citation); v2 makes the specific gap between citation-form and citation-substance the firing condition. Predicted cross-family Gwet's AC1 lift: 0.245 → approximately 0.60-0.70.

## Decision-readiness implication

**Direct readiness implication.**

When this frame fires, the document carries citation-like language but the citations are fabricated, misattributed, or unverified. Affects:

- **Evidence** ([methodology](/corpus/decision-readiness/)): false signal of source backing; the sentence-attribution proxy fires positively but the underlying sources do not validate the claims.
- **Robustness**: when load-bearing claims rely on fabricated citations, they fail under scrutiny.

The Source Network calibration corpus is the direct corrective: per-source F1 measurement against ground truth distinguishes real attribution from citation-shaped language.

## Generation affordances

**Rewrite prompt structure:** "For each citation or source reference in this document, annotate: (a) is the source named specifically enough to look up? (b) does the claim match what the source likely says? (c) could this citation be fabricated? If any answer is uncertain, the citation is providing authority without verification."

**Salient questions under this frame:**
- Can I look up the specific source cited?
- Does the source actually support THIS specific claim?
- Would the argument collapse if the citations were removed?
- How many of the citations are "according to" without a specific reference?

## Worked example

**Document excerpt:** "According to a 2024 McKinsey study, 73% of enterprises are deploying generative AI across core operations. Research from MIT's Media Lab shows that organizations adopting AI report a 30% productivity lift within the first year. Industry analysts project the enterprise AI market to exceed $150 billion by 2028."

**Frame present:** Authority by citation. The paragraph carries three citation-like signals: "a 2024 McKinsey study," "Research from MIT's Media Lab," "industry analysts project." Each produces the surface properties of evidence. Reading creates the impression that the claims are researched, sourced, and institutionally backed.

**Frame absent:** Verifiability. No specific report title is named for the McKinsey study (McKinsey publishes many 2024 AI reports with different metrics; which one?). No authors are named for the MIT Media Lab work (the Media Lab has many groups and publications; which?). No analyst or methodology is named for the market projection ("industry analysts" is a collective that does not produce a traceable forecast).

**How to read past it:** For each citation-like phrase, ask three questions. (a) Is the source named specifically enough to look up (report title plus year, DOI, or URL, not just institution)? (b) Does the claim match what the specific source actually says, or what sounds plausible given the institution? (c) If the citation phrase were removed, would the assertion stand on its own?

For the 73% claim: answer (a) is no, so (b) is unresolvable and (c) becomes the test. "73% of enterprises are deploying generative AI" without attribution is a strong claim that needs a source to be taken seriously. The institution name is doing the work a specific citation should do.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected via epistemic basis: high sourced_pct (many claims use citation language) with low verification rate (Source Network cannot confirm the cited values). The gap between "claims that look sourced" and "claims that ARE verified" is the signal.

## Vocabulary connections

- **Source conditioning** (T-351, CLARETHIUM_VOCABULARY): providing real source material forces the output to ground in that material. The antidote to authority-by-citation is requiring the document to cite specifically enough that the reader can verify. Source-conditioned prompts convert citation form back into citation substance.
- **The fluency-quality illusion** (FVS-002): citation form is one surface feature that produces the fluency-quality response. Confident citation cadence makes the document feel researched; the reader accepts the claims because the delivery matches the genre of a sourced document.
- **The construction trace** (T-356, CLARETHIUM_VOCABULARY): the reader who generates their own understanding of the topic before reading the AI output notices when cited claims do not match their mental model. Without the construction trace, the citations set the terms of acceptance; with it, the citations become hypotheses to verify.
- **The first read** (M-002, CLARETHIUM_VOCABULARY): the somatic response to citation-laden prose is to grant authority before conscious evaluation. The first read accepts citations as evidence; conscious evaluation asks whether the citations check out.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md. The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.495** (tier: **moderate**), per fvs_eval/v4/library_v4_reliability.json. Per-corpus reproducible values (regen: fvs_eval/v4/compute_per_corpus_reliability.py; artifact: fvs_eval/v4/library_v4_per_corpus_reliability.json): MG_v3=0.633 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.541 (3-family partial; Anthropic queued). Historical: MG2_v1=0.41 (library_v1), MG2_v2=0.452 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md; rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **0.858** across n=41 docs at temp=0 (4 verdict flip(s); per fvs_eval/v4/grok_intra_rater_ac1.json). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check-mcp/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.633, kappa 0.145, union 7/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): -0.29.
- **library_v2 (earlier variant):** Gwet's AC1 0.538, kappa 0.119, union 8/15.

See fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md §3 for library-wide tier context and fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: fvs_eval/mixed_genre_v1 n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.340 |
| Cohen's kappa (pairwise mean) | 0.200 |
| Raw agreement (pairwise mean) | 0.633 |
| Union prevalence | 11/15 = 73% |
| Intersection (all 4 agree positive) | 1/15 |

Per-family positives (of 15 docs): Claude 5, Gemini 3, Grok 5, GPT 8.
