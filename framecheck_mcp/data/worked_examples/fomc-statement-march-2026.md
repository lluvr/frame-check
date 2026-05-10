---
title: FOMC Statement March 2026: framing analysis of an institutional monetary-policy release
slug: fomc-statement-march-2026
author: Lovro Lucic
published: 2026-04-17
source_document_url: https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318a.htm
source_document_title: Federal Reserve Issues FOMC Statement (March 18, 2026)
source_document_author: Federal Open Market Committee
source_document_type: institutional monetary-policy release
frames_detected: [FVS-009]
verification_summary: "Policy values present (federal funds target range 3-1/2 to 3-3/4 percent; 2 percent longer-run inflation objective; 1/4 percentage point dissent). The Source Network is designed for empirical measurements from external providers; a central-bank policy release is itself the authoritative source for its own targets, so verification routing is intentionally not meaningful here."
hook: Same structural detector that flagged Altman's nominal risk coverage flags the FOMC statement as an active Risk Frame. Same keyword category; different substance, different frame, different teaching.
---

## Context

The Federal Open Market Committee publishes a short statement at
the close of each scheduled meeting. The statement is the formal
public record of whatever the Committee decided to do with the
federal funds rate and is the most widely-read monetary-policy
release in the world. Its tone, vocabulary, and structure are
all deliberately uniform across decades; changes in wording are
parsed word-by-word by markets.

This worked example analyses the
[March 18, 2026 statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318a.htm),
roughly three hundred words. Published a day after this writeup
was drafted, so it is genuinely a fresh document. Chosen as a
counterpoint to
[the Altman "Intelligence Age" essay](/corpus/worked-examples/the-intelligence-age-altman-2024/):
same paragraph-scale length, very different framing posture.
Where Altman is promotional, future-oriented, and unsourced, the
FOMC statement is analytical, present-oriented, and institutional.

## What Framecheck saw

The structural measurements, from the detectors in `framing.py`
and `claim_analysis.py` (deterministic, no LLM):

- **Voice: analytical.** Zero first-person-plural. Zero
  second-person. Zero imperatives. Twenty sentences, all in the
  institutional register ("the Committee decided to...," "the
  Committee is attentive to..."). The reader is not addressed at
  all; the text positions itself as a neutral record.

- **Analytical coverage: 3 of 5 perspectives detected.** Risks,
  trends, and uncertainty register as present. Causes and
  stakeholders register as absent. Density is high where it is
  present: risks at 12.3 mentions per 1,000 words, trends at
  12.3, uncertainty at 6.2. Compare the Altman essay: risks at
  3.6, trends at 2.7, uncertainty at 0.

- **Temporal orientation: present 70 percent, future 20 percent,
  past 10 percent.** The statement is grounded in what the
  Committee is doing now and what it plans to monitor going
  forward; past tense appears only in describing recent data.

- **Sourcing: 0 percent by the structural detector.** This is a
  correct measurement but an incomplete reading. The Fed is
  itself the authoritative source for its own policy values. The
  epistemic detector is calibrated against documents that cite
  external evidence; a primary-source release from the body that
  sets the rates does not need to cite anything. Naming this is
  part of the tool's construct-honesty commitment: the detector
  reports a measurement, not a judgment about what it should
  have measured.

- **Claims: one specific numeric extracted** by the claim-analysis
  layer. Several explicit policy values appear in the text (target
  range 3-1/2 to 3-3/4 percent; 2 percent longer-run inflation
  objective; 1/4 percentage point dissent) but the extractor is
  tuned for continuous values in prose and did not isolate all
  of them as claims. This is a real limit worth naming; see
  "What the method missed" below.

### Frame detections

The frame-library matcher suggests one entry:

- [FVS-009 Risk Frame (active)](/corpus/library/FVS-009.html).
  Triggered by substantive risk density (12.3 mentions per 1,000
  words) paired with uncertainty acknowledged. The library entry
  distinguishes an active risk frame (what could go wrong, what
  is vulnerable, what depends on holding assumptions) from a
  nominal one (risk as a single sentence pivoted past). The
  FOMC statement is the active kind: it names the risks
  ("somewhat elevated inflation," "implications of developments
  in the Middle East," "the risks to both sides of its dual
  mandate"), names the balance the Committee is trying to strike
  ("maximum employment and inflation at the rate of 2 percent"),
  and closes by describing how the Committee will reassess
  (labor-market conditions, inflation pressures, inflation
  expectations, financial and international developments).

The contrast with the Altman worked example is the teaching
point of this pair. Altman's essay also registers "risks" as
covered by the same detector, and it triggers
[FVS-002 Fluency Quality Illusion](/corpus/library/FVS-002.html)
instead of FVS-009. Same keyword category, different frame
assignment, different substance. The detector output by itself
does not tell a reader which is which; the detector plus the
library entry plus the reader's eye on the text does.

## What the method missed

Honest naming of the specific limits Framecheck hit on this
document:

- **Multiple policy values in prose, one extracted as a claim.**
  The claim extractor scans for structured numeric patterns in
  sentences; it caught the "2 percent" longer-run inflation
  objective but did not isolate the "3-1/2 to 3-3/4 percent"
  target range or the "1/4 percentage point" dissent as
  individual claims. All three are material; a more aggressive
  claim-extraction pass would catch them. This is a known gap
  that shows up especially in institutional writing where values
  are embedded in formal constructions ("decided to maintain the
  target range... at X to Y percent") that do not match the
  patterns the extractor is tuned for.

- **Source-network coverage for policy values.** The Source
  Network is designed for empirical measurements where the
  provider is external authority (SEC EDGAR for company financials,
  FRED for macro data, Wolfram Alpha for reference facts). A Fed
  policy value IS the reference fact; the Fed's own data pages
  would be the target. FRED does publish "Federal Funds Target
  Range - Upper Limit" and "Federal Funds Target Range - Lower
  Limit" as series; routing the extracted claim there would
  return "verified" trivially because the Fed sets what it
  reports. That verification is not false, but it is not
  informative in the way a Source Network verdict usually is.
  The honest naming: verification is most useful against
  independent primary sources, which monetary policy values
  mostly are not.

- **Stakeholder analysis.** The detector reports stakeholders
  as absent from the statement. The statement talks about "the
  economy," "the Committee," and "the dual mandate" but does
  not name workers, borrowers, savers, holders of different
  assets, or any specific group that the rate decision affects
  differently. The absence is real and worth naming. It is also
  characteristic of the institutional register: the FOMC
  statement is written to be read as a single voice speaking
  to "the markets" as an abstraction, not a policy text that
  engages with distributional consequences. Reading the
  statement against that gap is work the tool will not do for
  the reader.

## Why this example is worth publishing

Because the structural detector fires "risks covered" on both
this document and the Altman essay, but the two documents are
doing radically different things with that coverage. The Altman
essay uses the risk keyword once, then pivots. The FOMC
statement organises itself around risks. Same flag, different
frame assignment (FVS-002 vs FVS-009), different reader takeaway.

This pair, read together, is the single sharpest case for
construct honesty that Framecheck can make: a structural
detector that returns the same category label does not mean two
documents are doing the same thing. The tool surfaces surface
patterns; the library entries name which shape of the pattern
was detected; the reader closes the loop. That is the whole
method. A worked-example archive that holds only documents
Framecheck treats favourably is a selection-biased archive;
this entry exists partly to anchor the archive against that
bias.

## Citation

Lucic, L. (2026). *FOMC Statement March 2026: framing analysis
of an institutional monetary-policy release*. Framecheck
Worked Examples.
frame.clarethium.com/corpus/worked-examples/fomc-statement-march-2026/

Licensed CC-BY-4.0. The FOMC statement is a U.S. federal
government work in the public domain; this analysis does not
alter that status.
