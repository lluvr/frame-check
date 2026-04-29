# Wedge pilot document sourcing guide v1

**Status:** advisory; operator picks N=2 documents from this guide for the pilot.
**Date:** 2026-04-28
**Use:** companion to PROTOCOL_v1.md inclusion criteria. The guide reduces blank-page friction without overriding operator judgment on what to test.

## What this guide does

The wedge pilot needs N=2 documents (per PROTOCOL_v1.md). The protocol's inclusion criteria require: opinion-formation candidate (decision-prompted, recommendation-shaped, claim-loaded), 300-2000 words, English analytical prose, NOT a worked example already in the repo. The exclusion criteria rule out: under-100-word documents, non-analytical structures, documents where neither FVS detector matches nor high-signal absences fire.

This guide names ten candidate categories with one concrete example per category. The operator picks two. The guide does not pre-author documents (that would override the operator's judgment on what to stress-test); it reduces the search-and-screen cost from "blank page" to "pick from a primed list."

## Selection guidance

Two documents from different categories produces a more informative pilot than two from the same category. The pilot's job is to calibrate the rubric on real variance; same-category samples constrain the variance the rubric encounters and weaken the calibration. Recommended: one decision-prompted document plus one recommendation-shaped or claim-loaded document.

## Ten candidate categories

### A. Federal Reserve speeches and policy communications

Public, deliberately analytical, well-paragraphed, decision-shaped (the Fed is making a policy choice and the speech defends it). Often hits 800-1500 words. Frame Check's calibration window fits well.

**Example:** A recent FOMC chair speech on rate-decision rationale. Search "FOMC chair speech [recent month]" on federalreserve.gov; pick one that defends a rate move (decision-prompted) rather than a market-update (descriptive).

**Why it works for the pilot:** the decision-shape is explicit; the document foregrounds the chosen path and downplays counterfactuals; the agent's response will reveal whether frame_check surfaces the absent-counterfactual structure or the without-tool baseline glosses past it.

### B. Investment bank or sell-side analyst recommendations

Recommendation-shaped, claim-loaded, often promotional in voice. Public via SEC filings or sell-side research aggregators.

**Example:** A recent analyst upgrade or downgrade memo on a public company. Look for "ANALYST UPGRADES [TICKER]" on a financial-news aggregator; pick a memo that names a target price and a rationale (the rationale paragraph is the analytical-prose payload).

**Why it works:** classic recommendation-without-falsification territory. The agent's response will reveal whether frame_check's FVS-007 (recommendation-without-falsification) detector contributes to a load-bearing reading the without-tool baseline misses.

### C. Corporate strategy memos (public letters)

CEO letters to shareholders, strategic-direction announcements, public memos. Often opinion-loaded with corporate-positioning vocabulary.

**Example:** Annual shareholder letter from a public company. Available on every public company's IR page. Pick one with a clear strategic-shift narrative (entering a new market, restructuring, leadership change).

**Why it works:** voice classification often lands `promotional` or `analytical-with-promotional-runner-up`; coverage often misses risk and counterfactual perspectives; agent responses can be compared on whether they surface the structural shape of the corporate framing.

### D. Op-eds in major newspapers

Opinion-loaded by definition, written for analytical-prose readers, paragraphed. Public via newspaper websites.

**Example:** A recent op-ed in the New York Times, Wall Street Journal, Financial Times, or similar national newspaper on a contested topic. Pick one that takes a clear position (decision-shaped: the reader should believe X).

**Why it works:** voice cascades reliably here; FVS detectors fire across the framing landscape; the without-tool baseline often summarizes the argument while the with-tool response can reveal structural asymmetries.

### E. Academic abstracts on contested empirical claims

Analytical-prose by convention, well-bounded, decision-relevant when the topic is policy-adjacent. Public via SSRN, NBER, RePEc, arXiv.

**Example:** An NBER working paper abstract on a policy-relevant economic claim (minimum wage, immigration, education). Pick an abstract that summarizes findings (the abstract is the document; the paper itself is too long).

**Why it works:** the abstract foregrounds a finding and often understates uncertainty; the agent's response can be compared on whether frame_check surfaces the hedge-calibration gap.

### F. Tech-industry post-mortems and incident reports

Analytical-prose, decision-shaped (we did X, here's why we changed). Public on company engineering blogs.

**Example:** A recent post-mortem from a major tech company's engineering blog (Cloudflare, AWS, GitHub, etc.). Pick one that describes the incident response and the rationale for the chosen mitigation.

**Why it works:** the document is analytically structured but defends a chosen path; the agent's response can be compared on whether frame_check surfaces the absent-alternative perspective.

### G. Medical recommendations or guideline summaries

Analytical-prose, recommendation-shaped, claim-loaded with explicit hedges. Public via professional society publications.

**Example:** A recent USPSTF (US Preventive Services Task Force) recommendation summary, or a professional-society guideline summary on a contested clinical question.

**Why it works:** medical recommendations are well-hedged at the surface level; the agent's response can be compared on whether frame_check's hedge-calibration measurement surfaces the document's hedge density distinct from the agent's first-read impression.

### H. Long-form journalism on contested topics

Analytical-prose, often opinion-loaded under reporting voice, well-paragraphed. Public via magazine or longform publication.

**Example:** A recent feature in The Atlantic, The New Yorker, ProPublica, or similar on a policy or social topic. Pick one with a clear thesis stated in the first three paragraphs.

**Why it works:** the document mixes reporting and argument; the agent's response can be compared on whether frame_check surfaces voice classification distinct from the agent's first-read impression.

### I. Public-company SEC filings (specifically MD&A sections)

Analytical-prose, decision-relevant, claim-loaded with regulatory-defined hedges. Public via SEC EDGAR.

**Example:** The MD&A section of a recent 10-K from a public company. The full 10-K is too long; the MD&A is bounded analytical prose.

**Why it works:** corporate framing under regulatory constraint; the agent's response can be compared on whether frame_check's FVS detectors surface promotional-with-required-caveat structure.

### J. AI-generated analytical responses on contested topics

The self-audit case: a fresh response from another LLM on a contested topic, which the user pastes into the agent for analysis.

**Example:** Generate (or have on hand) a Claude or GPT-4 or Gemini response to a prompt like "Should I take this job offer?" or "Is investing in [asset] a good idea?" Use the response itself as the document. Anonymize the source LLM if relevant.

**Why it works:** this is the canonical sovereignty use case (frame_check_my_response prompt). The agent's response can be compared on whether frame_check surfaces the structural shape of the other LLM's framing in a way the without-tool baseline misses.

## Operator workflow

1. Pick two categories from A-J. Recommended: one decision-shaped (A, F, I) plus one recommendation-shaped or opinion-loaded (B, C, D, J).
2. Locate one concrete document per category that fits the size band (300-2000 words). If the source document exceeds 2000 words, extract the analytical-prose payload (a section, an executive summary, the MD&A). Cite the source.
3. Save each as a markdown file in `validation/wedge_behavior/pilot_inputs_v1/<doc-slug>.md` with a header naming the source URL and the date retrieved.
4. Run `python3 validation/wedge_behavior/run_pilot.py validation/wedge_behavior/pilot_inputs_v1/<doc-slug>.md --user-prompt "Help me think about this document" --doc-slug <doc-slug>`.
5. Follow the runner's printed instructions for the next steps (paste prompts into Claude, capture responses, score against the rubric).

## What to record beyond the rubric

The protocol's rubric is the load-bearing scoring instrument. In addition, the operator should record per-document:

- Source URL and retrieval date.
- One sentence on why this document was picked from its category (e.g., "FOMC May 2026 speech defending the 25bps cut despite mixed inflation prints; chose for the explicit decision-shape").
- One sentence on what the operator EXPECTED the wedge to surface, before running the pilot (e.g., "I expect the absent-counterfactual perspective to be named with-tool but glossed without-tool"). This is pre-registered intuition; comparing it to the actual outcome is part of the pilot's calibration value.

## What this guide does NOT do

- Pre-author the documents. The operator's editorial judgment on what to stress-test is part of the calibration; pre-authored documents would weaken that calibration.
- Fix the rubric. The rubric is in `rubric_template.md`; this guide is upstream of scoring.
- Authorize spend. The pilot's spend ceiling (under $1) is named in PROTOCOL_v1.md; this guide assumes the operator has already authorized that ceiling for their own Claude session.

## Operator authorization checklist

Before running the pilot:

- [ ] Two documents selected from different categories (A-J).
- [ ] Each document fits 300-2000 words and is analytical-prose English.
- [ ] Neither document is in `data/worked_examples/` or other repo locations the agent may have seen in training.
- [ ] Source URLs and retrieval dates recorded.
- [ ] Pre-registered expectation recorded per document.
- [ ] Operator's Claude session ready for paired-prompt runs.
- [ ] Rubric form (`rubric_template.md`) printed or open for scoring.
