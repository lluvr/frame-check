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

**Adjacent frames:** Fluency-Quality Illusion (FVS-002, citation form is part of the fluency that creates the illusion), Oracle Frame (FVS-013, citations reinforce oracle mode by making the output look researched), Uncertainty Frame (FVS-012, genuine citations include uncertainty; authority-by-citation citations present certainty)

**When this frame is appropriate:** Evaluating any document that uses citation-like language. Research summaries, policy recommendations, market analyses that reference studies or data. Any context where the authority of the claims rests on external sources.

**When this frame is misleading:** Documents that genuinely cite and have been verified. Not every citation is fabricated. The frame is a prompt to CHECK, not to dismiss.

**Honest limits:** The epistemic basis detector in framing.py measures sourced vs unsupported numerical claims but does not verify whether the cited sources are real or accurate. Authority by citation is detectable only as a pattern (citation language present with low verifiability), not as a fact (the citation is wrong). Full citation verification requires external lookup.

**Revision note (2026-04-23, Phase 1C):** Revised from v1 with explicit 3-case fire conditions and 3-case exclusion conditions, resolving narrow-vs-broad reader split identified in F-2026-027 and F-2026-030. v1's opening sentence ("A document establishes credibility by citing sources") licensed a broad reading (ANY citation use = authority-by-citation); v2 makes the specific gap between citation-form and citation-substance the firing condition. Predicted cross-family Gwet's AC1 lift: 0.245 → approximately 0.60-0.70.

## Decision-readiness implication

**Direct readiness implication.**

When this frame fires, the document carries citation-like language but the citations are fabricated, misattributed, or unverified. Affects:

- **Evidence** ([methodology](/corpus/decision-readiness/)): false signal of source backing. The sentence-attribution proxy fires positively but the underlying sources do not validate the claims.
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

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on fvs_eval/mixed_genre_v1 n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.246 |
| Gwet's AC1 (pairwise mean) | 0.245 |
| Raw agreement (pairwise mean) | 0.600 |
| Union prevalence (all families) | 43% |

Per-family positives (of 15 docs): Claude 2, Gemini 6, Grok 11, GPT-5 7.

**V4 detection mode:** honest-limit

**Interpretation:** Persistent cross-family divergence across all three metrics. Detection is interpretation-dependent; see fvs_eval/v4/RELIABILITY_STUDY.md for split-vote reasoning analysis.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See fvs_eval/v4/RELIABILITY_STUDY.md for methodology, fvs_eval/v4/DESIGN.md for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-13; revised Phase 1C 2026-04-23 (3-case fire + 3-case exclusion conditions per Revision note above); grounded-authorship retrofit 2026-04-25 per FRAME_DIVERGENCE_v2.md §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- fvs_eval/mixed_genre_v1 (n=15, four-family panel; F-2026-027 baseline 2026-04 measured pre-Phase 1C; post-revision re-measurement pending)
- `detect_epistemic_basis` in `framing.py` (rule-based detector)
- EXP-094 confound audit (tolerance collisions hiding real fabrications)
- HI-059 Claim-Binding Fabrication case study
- F-2026-027 plus F-2026-030 narrow-vs-broad reader split that prompted Phase 1C
- MCP integration as canonical absent-frame in `_PROMPT_CHALLENGE_DOCUMENT`
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Phase 1C-pre split-vote at moderate prevalence. F-2026-027 v1 baseline showed AC1 0.245 - very low for a frame intended as a primary detection target. The narrow-vs-broad reader split was the cause: v1's opening sentence licensed broad reading (any citation use = authority-by-citation); some families fired on every cited document, others only on uncited fabrications. Phase 1C revision (2026-04-23) added 3-case fire conditions + 3-case exclusion conditions to resolve. Predicted AC1 lift to 0.60-0.70.
2. Detection cannot verify citations. The epistemic basis detector measures sourced_pct (sentences with attribution) but does not check whether cited sources are real or accurate. Authority-by-citation fires on PATTERN (citation language present with low verifiability), not on FACT (the citation is fabricated). Full citation verification requires external lookup; Source Network is the operationalization for real attribution checking.
3. Fabricated citations are common in AI output but proving fabrication is hard at scale. Three case types fire: fabricated (source does not exist), misattributed (source exists but does not say what claim says), authority-veneer ("according to research" without specifics). All three are rule-based-detectable as "low-specificity citation form" but proving fabrication requires external per-claim verification.

**Success record.** Two operationalized cases:
1. AI enterprise-AI market analysis worked example (v1 Identification). Document presented "according to a 2024 McKinsey study," "Research from MIT's Media Lab," "industry analysts project" - three authority-veneer signals. Authority-by-citation detection surfaced: no specific report titles, no DOI, no author names, no methodology. Reader can apply three diagnostic questions per citation; arguments anchored only on institution authority collapse without specific sourcing.
2. MCP integration as canonical absent-frame. FVS-016 cited in MCP `_PROMPT_CHALLENGE_DOCUMENT` as canonical absent-frame for divergence: "FVS-016 (Authority by Citation) absent leads to question 'Which claims here lean on the author's register rather than on citable sources?'" Operationally embedded as agent-facing divergence target.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where applying the three diagnostic questions (can-I-look-it-up; does-it-support-this-claim; would-it-stand-without-citation) to a citation-laden document revealed fabricated, misattributed, or authority-veneer citations; (2) the contrast between the cited-as-authoritative reading and the verification-tested reading is concrete; (3) outcome differential observed; (4) concrete first-person recall. Held open per FRAME_DIVERGENCE_v2.md P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application: ~1-3 minutes per document, scaling with citation density
- V4.2 LLM judge invocation: ~$0.0008/document (detection-only; verification requires external lookup)
- Source Network per-citation verification: cost depends on which lookup APIs are used (most are free)
- One-pass detection: appropriate for any citation-laden analytical document
- Deep-dive verification: appropriate when citations are load-bearing for high-stake decisions

**Applicability metadata.**
- Domains: research summaries (high stake-relevance), policy recommendations (high), market analyses with cited data (high), AI-generated analytical content (high), academic-genre documents (medium-high)
- Decision types: any with evidence-based readiness requirement; any where citations are load-bearing
- Stake levels: medium to high. Low-stake casual reading does not require this analysis.
- Inappropriate contexts: documents with verified citations (frame is a prompt to CHECK, not to dismiss); rhetorical or illustrative references (e.g., "as Orwell warned"); standard genre conventions (legal, scholarly, journalistic citing practice)

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027 v1 baseline): kappa 0.246, AC1 0.245 (low; persistent split-vote), raw 0.600, union prevalence 43% (Claude 2, Gemini 6, Grok 11, GPT-5 7 of 15)
- Phase 1C revision (2026-04-23): predicted AC1 lift from 0.245 to 0.60-0.70; post-revision re-measurement pending
- EXP-094 confound audit: ongoing; tolerance collisions hide real fabrications
- HI-059 Claim-Binding Fabrication origin study
- MCP integration: operationally embedded as canonical absent-frame in challenge prompts
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
