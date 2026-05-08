"""
Framing analysis validation corpus.

The framing detectors in framing.py (detect_coverage, detect_voice,
temporal_orientation, detect_epistemic_basis) are 100% deterministic
regex/text computation with zero LLM calls. Until this corpus, none
of them had empirical validation: each function had been hand-tuned
against ad-hoc examples but never tested against documents with
KNOWN framing characteristics.

This corpus changes that. Each test case is a carefully crafted
short document where one or two framing dimensions are extreme
(purely promotional, no risks coverage, all-future tense, etc.).
The assertions verify that the detectors classify those extremes
correctly, locking in the current behavior so future tuning does
not silently regress.

These tests run without any API calls. The whole file should
finish in under a second.

Notes on writing test documents:
  - split_sentences() filters sentences shorter than 30 characters,
    so test sentences must be at least that long. Short complete
    sentences ("Demand exceeds supply.") will be silently dropped
    from the analysis, distorting the test.
  - split_sentences() joins consecutive non-heading, non-list-item
    lines into paragraphs before splitting by sentence boundary.
    Multi-line paragraphs are handled correctly. One sentence per
    line still works and is easier to read in tests.
  - Markdown headings (## Heading) are recognized by split_sentences
    and excluded from the sentence count, so use them freely for
    structure.
"""

from framing import (
    detect_coverage,
    temporal_orientation,
    detect_voice,
    detect_epistemic_basis,
)


# ================================================================
# GROUP 1: VOICE DETECTION
# ================================================================

class TestVoiceDetection:
    """The voice detector classifies documents into one of:
    prescriptive, promotional, descriptive, advisory, analytical.
    Each class has specific markers that must be present in
    sufficient density."""

    def test_prescriptive_voice_detected(self):
        """Prescriptive: high you-pct + imperatives. The doc tells
        the reader what to do."""
        doc = (
            "## How to Allocate Your Portfolio\n\n"
            "You should diversify your holdings across asset classes.\n"
            "Your bond allocation must match your risk tolerance.\n"
            "You need to rebalance your portfolio at least quarterly.\n"
            "Make sure you reinvest your dividends into the same fund.\n"
            "Avoid the temptation to time the market with your savings.\n"
            "You can use dollar-cost averaging for steady contributions.\n"
        )
        result = detect_voice(doc)
        assert result["voice"] == "prescriptive", (
            f"Expected prescriptive, got {result['voice']!r}. "
            f"you_pct={result['you_pct']}, imperatives={result['imperative_count']}"
        )
        assert result["you_pct"] >= 50, (
            f"Expected high you_pct (>=50), got {result['you_pct']}"
        )

    def test_promotional_voice_via_we_our(self):
        """Promotional: high we/our pct. The company speaks about
        its own products and achievements."""
        doc = (
            "## Why We Lead the Industry\n\n"
            "Our innovative platform serves millions of customers globally.\n"
            "We have invested heavily in our research and development.\n"
            "Our products consistently outperform our competitors in tests.\n"
            "We are proud of our exceptional customer satisfaction scores.\n"
            "Our roadmap includes several breakthrough features for next year.\n"
            "We continue to expand our presence in international markets.\n"
        )
        result = detect_voice(doc)
        assert result["voice"] == "promotional", (
            f"Expected promotional via we/our, got {result['voice']!r}. "
            f"we_pct={result['we_pct']}"
        )
        assert result["we_pct"] >= 50, (
            f"Expected high we_pct, got {result['we_pct']}"
        )

    def test_promotional_voice_via_third_person_superlatives(self):
        """Promotional: third-person but saturated with positive
        superlatives. No we/our, no you, but every sentence is
        a hype marker. The threshold is 20% of sentences containing
        promotional markers."""
        doc = (
            "## Industry Snapshot\n\n"
            "The company is delivering unprecedented growth this quarter.\n"
            "Their tremendous opportunities continue to drive remarkable results.\n"
            "The transformative platform is creating substantial opportunities now.\n"
            "Record-breaking quarterly performance has analysts increasingly bullish.\n"
            "The cutting-edge technology dominates the entire industry segment.\n"
            "Their best-in-class execution remains the gold standard for peers.\n"
        )
        result = detect_voice(doc)
        assert result["voice"] == "promotional", (
            f"Expected promotional via superlatives, got {result['voice']!r}. "
            f"we_pct={result['we_pct']}, you_pct={result['you_pct']}"
        )

    def test_analytical_voice_for_neutral_third_person(self):
        """Analytical: third-person, no you/we, no superlatives.
        This is the residual / default voice."""
        doc = (
            "## Quarterly Earnings Review\n\n"
            "The company reported revenue of fifty billion dollars last quarter.\n"
            "This represents a notable change from the prior year period reported.\n"
            "Operating margins compressed slightly due to higher input costs reported.\n"
            "Several analysts have updated their estimates for the coming year.\n"
            "The capital expenditure outlook remains in line with prior guidance issued.\n"
            "Management discussed segment performance during the conference call.\n"
        )
        result = detect_voice(doc)
        assert result["voice"] == "analytical", (
            f"Expected analytical, got {result['voice']!r}. "
            f"you_pct={result['you_pct']}, we_pct={result['we_pct']}"
        )

    def test_advisory_voice_for_low_you_directed(self):
        """Advisory: some you-directed guidance but not enough to
        be prescriptive (you_pct between 5 and 15)."""
        doc = (
            "## Considerations for Long-Term Investors\n\n"
            "Long-term investors typically benefit from broad diversification strategies.\n"
            "Index funds offer a simple way to achieve such broad market exposure.\n"
            "You may want to review your asset allocation periodically over the years.\n"
            "Tax-advantaged accounts often improve after-tax returns considerably overall.\n"
            "The right approach depends on individual goals and circumstances entirely.\n"
            "Costs and fees compound significantly over multi-decade time horizons.\n"
        )
        result = detect_voice(doc)
        # One "you may want to review" out of 6 sentences -> ~17% you_pct
        # That's right at the prescriptive threshold. The test allows
        # either advisory or prescriptive depending on exact rounding.
        assert result["voice"] in ("advisory", "prescriptive"), (
            f"Expected advisory or prescriptive, got {result['voice']!r}. "
            f"you_pct={result['you_pct']}"
        )


class TestVoiceClassificationConfidence:
    """Phase B voice construct: classification confidence, runner-up,
    borderline flag. The under-detection construct from Fix A does not
    apply to classification signals (no not_detected state); this is
    the analogous evidence posture for voice.

    Shape:
      voice: the classifier's pick
      margin_to_threshold: the BEST margin across firing rules for the
        winning class. Large positive = winner's rule(s) decisively
        crossed thresholds; near zero = winner barely activated.
      runner_up: next class in cascade (skipping multiple winner-class rules)
      runner_up_margin: best margin across that class's rules; negative
        values mean that class missed by that much; positive values mean
        the class's rule would fire but was preempted by cascade order.
      confidence: "high" | "borderline" | "insufficient"
    """

    def test_clear_classification_has_high_confidence(self):
        """Strongly prescriptive document should have high confidence:
        winner margin large, runner-up margin negative (missed by a lot).
        """
        doc = (
            "## How to Allocate Your Portfolio\n\n"
            "You should diversify your holdings across asset classes.\n"
            "Your bond allocation must match your risk tolerance.\n"
            "You need to rebalance your portfolio at least quarterly.\n"
            "Make sure you reinvest your dividends into the same fund.\n"
            "Avoid the temptation to time the market with your savings.\n"
            "You can use dollar-cost averaging for steady contributions.\n"
        )
        result = detect_voice(doc)
        assert result["voice"] == "prescriptive"
        assert result["confidence"] == "high", (
            f"Strongly prescriptive doc should have high confidence; "
            f"got {result['confidence']!r}. runner_up={result['runner_up']}, "
            f"margin={result['runner_up_margin']}, "
            f"winner_margin={result['margin_to_threshold']}"
        )
        assert result["margin_to_threshold"] >= 2.0, (
            f"Expected winner margin >= 2 for clear classification; "
            f"got {result['margin_to_threshold']}"
        )

    def test_classification_shape(self):
        """Every classification has margin_to_threshold (numeric),
        runner_up (class name or None), runner_up_margin (numeric or None),
        and confidence in {high, borderline, insufficient}."""
        doc = (
            "The company reported revenue of forty-two million dollars in 2024.\n"
            "Operating margins expanded versus the prior year.\n"
            "Competitive positioning remains intact across segments.\n"
            "Product adoption has accelerated in enterprise customers.\n"
            "The outlook balances growth and risk considerations.\n"
            "Analysts continue to monitor the company closely over time.\n"
        )
        result = detect_voice(doc)
        assert "margin_to_threshold" in result
        assert isinstance(result["margin_to_threshold"], (int, float))
        assert "runner_up" in result
        assert result["runner_up"] is None or isinstance(result["runner_up"], str)
        assert "runner_up_margin" in result
        assert "confidence" in result
        assert result["confidence"] in ("high", "borderline", "insufficient")

    def test_insufficient_input_schema_parity(self):
        """Empty-text input must return the same schema as happy-path.
        Downstream consumers (templates, MCP payloads) read fields by
        name without branching on voice=='insufficient'; a schema leak
        (missing margin_to_threshold or runner_up_margin on insufficient
        path) would KeyError at the template layer.

        Regression pin for the post-refactor insufficient-return shape.
        """
        result = detect_voice("")
        expected_keys = {
            "voice", "you_pct", "we_pct", "imperative_count", "spec_pct",
            "total_sentences", "margin_to_threshold", "runner_up",
            "runner_up_margin", "confidence",
        }
        actual_keys = set(result.keys())
        missing = expected_keys - actual_keys
        assert not missing, (
            f"insufficient-path return missing keys {missing}; shape "
            f"must match happy-path. Template access without "
            f"voice=='insufficient' branch will KeyError otherwise."
        )
        assert result["voice"] == "insufficient"
        assert result["confidence"] == "insufficient"
        assert result["runner_up"] is None
        assert result["runner_up_margin"] is None

    def test_borderline_classification_flagged(self):
        """Document with you_pct just crossing advisory threshold (5%)
        should flag borderline; the winner's threshold crossing is tight.
        """
        sentences = [
            "The dataset contains records spanning multiple fiscal periods for review.",
            "Each record carries metadata describing acquisition conditions and provenance.",
            "Methodology notes accompany the dataset as separate documentation files.",
            "Researchers have used this dataset in several published analyses previously.",
            "Summary statistics appear in the accompanying tables at the document top.",
            "Detailed breakdowns by segment follow in the appendix after main tables.",
            "Reviewers have noted several limitations that should temper interpretation.",
            "Future versions of the dataset may incorporate revised collection protocols.",
            "The data stewardship team reviews quality reports on a quarterly cadence.",
            "Users seeking access through the restricted portal must complete training.",
            "You might also consult the methodology appendix before drawing conclusions.",
            "Annual reviews include external auditors for accuracy verification purposes.",
            "Comparable datasets from adjacent domains support cross-validation checks.",
            "Researchers should document any preprocessing steps in their publications.",
            "Annual updates typically release in late March following quality review.",
            "Data quality has improved consistently since the initial release version.",
            "Comparisons to baseline should account for methodological revisions over time.",
        ]
        doc = "## Dataset Overview\n\n" + "\n".join(sentences)
        result = detect_voice(doc)
        # Near the advisory threshold; classifier picks either class.
        assert result["voice"] in ("advisory", "analytical"), (
            f"expected advisory or analytical near-boundary, got "
            f"{result['voice']!r}"
        )
        # Borderline should be flagged (winner margin tight OR runner-up close)
        assert result["confidence"] == "borderline", (
            f"Near-threshold classification should flag borderline; got "
            f"confidence={result['confidence']}, "
            f"margin={result['margin_to_threshold']}, "
            f"runner_up={result['runner_up']}, "
            f"runner_up_margin={result['runner_up_margin']}, "
            f"you_pct={result['you_pct']}"
        )


# ================================================================
# GROUP 2: COVERAGE DETECTION
# ================================================================

class TestCoverageDetection:
    """detect_coverage identifies which of 5 analytical categories
    a document covers: causes, risks, stakeholders, trends, uncertainty.
    A category is "covered" if its marker count is >= 2."""

    def test_full_coverage_doc_covers_all_five(self):
        """A document that explicitly addresses all 5 categories
        should mark all of them as covered."""
        doc = (
            "## Comprehensive Analysis\n\n"
            "Revenue grew because of new product launches and stronger demand.\n"
            "Customer adoption increased as a result of the marketing investment.\n"
            "However, several risks could threaten this growth trajectory now.\n"
            "Supply chain vulnerabilities remain a significant concern for management.\n"
            "Customers and employees both stand to benefit from the expansion plans.\n"
            "Stakeholders affected include consumers, workers, and local communities directly.\n"
            "The company grew sales twenty-five percent this past quarter year-over-year.\n"
            "Profits increased substantially compared to the prior year same period.\n"
            "Many uncertainties remain about future growth rates and market conditions.\n"
            "Some analysts may underestimate the complexity of the regulatory environment.\n"
        )
        result = detect_coverage(doc)
        assert result["coverage_count"] >= 4, (
            f"Expected coverage_count >= 4 for full doc, got {result['coverage_count']}. "
            f"covered={result['covered']}, missing={result['missing']}"
        )

    def test_doc_missing_risks_marks_risks_missing(self):
        """A doc that only contains positive analysis (causes, growth,
        stakeholders) but no risk language should mark risks as missing."""
        doc = (
            "## Growth Story\n\n"
            "Revenue expanded thirty percent driven by strong customer demand last year.\n"
            "Adoption accelerated because of significant product improvements over time.\n"
            "Customers benefited substantially from the new features and services delivered.\n"
            "Sales teams reached record performance levels across every territory measured.\n"
            "Margins improved as scale efficiencies began to compound over the period.\n"
            "Investors and analysts both viewed the quarterly results very favorably.\n"
            "Growth continued throughout the second half of the fiscal year reporting.\n"
        )
        result = detect_coverage(doc)
        assert "risks" in result["missing"], (
            f"Expected 'risks' to be missing in growth-only doc. "
            f"covered={result['covered']}, missing={result['missing']}"
        )

    def test_doc_missing_uncertainty_marks_uncertainty_missing(self):
        """A doc that asserts everything as fact without hedging or
        uncertainty markers should mark uncertainty as missing."""
        doc = (
            "## Definitive Outlook\n\n"
            "Revenue grew thirty percent because of stronger consumer demand last year.\n"
            "Operating margins expanded due to improved supply chain management efficiency.\n"
            "The market share increased as competitors lost ground in core categories.\n"
            "Investors saw substantial returns thanks to the disciplined capital allocation.\n"
            "Customers benefited from the lower pricing and improved product quality offered.\n"
            "Profits doubled compared with the prior year on the strength of expansion.\n"
        )
        result = detect_coverage(doc)
        assert "uncertainty" in result["missing"], (
            f"Expected 'uncertainty' missing in definitive doc. "
            f"covered={result['covered']}, missing={result['missing']}"
        )

    def test_reversed_uncertainty_language_detected(self):
        """'Data remains limited' uses reversed word order from
        'limited data' but expresses the same epistemic uncertainty.
        The uncertainty detector should catch both forms."""
        doc = (
            "## Clinical Trial Review\n\n"
            "The treatment showed a 20 percent reduction in adverse cardiovascular events.\n"
            "The trial enrolled 17,604 participants across 41 countries over several years.\n"
            "Gastrointestinal side effects occurred in approximately 50 percent of patients.\n"
            "Treatment discontinuation rates were higher in the active treatment group overall.\n"
            "Long-term safety data beyond 5 years remains limited for this class of drugs.\n"
            "The evidence for use in patients without obesity remains insufficient.\n"
        )
        result = detect_coverage(doc)
        assert "uncertainty" in result["covered"], (
            f"Reversed uncertainty language (data remains limited, "
            f"evidence remains insufficient) should count as uncertainty coverage. "
            f"covered={result['covered']}, missing={result['missing']}, "
            f"uncertainty_count={result['categories']['uncertainty']['count']}"
        )

    def test_dismissive_risk_before_keyword_not_counted(self):
        """'Minimal risks' uses risk vocabulary but dismisses it.
        Diminisher before risk keyword should suppress the match."""
        doc = (
            "## Stable Outlook\n\n"
            "The company operates in a mature market with minimal risks to revenue growth.\n"
            "Market conditions remain favorable with negligible threats to profitability now.\n"
            "The management team has effectively addressed all known concerns already.\n"
            "Investors can be confident in the steady performance trajectory going forward.\n"
            "Demand remains strong across every product category measured this quarter.\n"
        )
        result = detect_coverage(doc)
        assert "risks" in result["missing"], (
            f"Dismissive risk language (minimal risks, negligible threats) "
            f"should NOT count as risk coverage. "
            f"covered={result['covered']}, missing={result['missing']}, "
            f"risk_count={result['categories']['risks']['count']}"
        )

    def test_dismissive_risk_after_keyword_not_counted(self):
        """'Risks are minimal' also uses risk vocabulary to dismiss.
        Diminisher after risk keyword should suppress the match."""
        doc = (
            "## Business Review\n\n"
            "The identified risks are minimal and well within acceptable tolerance levels.\n"
            "Operational challenges remain manageable given the current resource allocation.\n"
            "The company maintains strong cash reserves and disciplined spending overall.\n"
            "Revenue growth has been consistent across every quarter reported this year.\n"
            "Any concerns raised by analysts are largely overstated by market observers.\n"
        )
        result = detect_coverage(doc)
        assert "risks" in result["missing"], (
            f"Post-keyword dismissive language (risks are minimal, "
            f"challenges remain manageable) should NOT count as risk coverage. "
            f"covered={result['covered']}, missing={result['missing']}, "
            f"risk_count={result['categories']['risks']['count']}"
        )

    def test_genuine_risk_coverage_not_suppressed(self):
        """Substantive risk analysis should still count as covered.
        The diminisher check must not suppress genuine risk language."""
        doc = (
            "## Risk Assessment\n\n"
            "Supply chain disruptions pose significant risks to manufacturing output.\n"
            "Cybersecurity threats have increased substantially across the industry.\n"
            "Regulatory challenges could materially affect the company's expansion plans.\n"
            "Currency volatility and trade barriers represent ongoing concerns for operations.\n"
            "The competitive landscape presents additional headwinds for market share retention.\n"
            "Management has identified several key vulnerabilities requiring immediate attention.\n"
        )
        result = detect_coverage(doc)
        assert "risks" in result["covered"], (
            f"Genuine risk discussion should count as covered. "
            f"covered={result['covered']}, missing={result['missing']}, "
            f"risk_count={result['categories']['risks']['count']}"
        )

    def test_negated_risks_not_covered(self):
        """A document that explicitly denies risks should NOT count
        as having risk coverage. Negation words (no, zero, without)
        directly before a risk keyword indicate dismissal, not analysis.

        Regression test for negation bypass fix."""
        doc = (
            "## Product Safety Assessment\n\n"
            "There are no meaningful risks associated with this product at all.\n"
            "Our testing found zero safety threats or material concerns anywhere.\n"
            "The product poses no challenges to existing regulations or standards.\n"
            "Revenue expanded by twenty-eight percent compared to the prior year.\n"
            "The company grew sales across all segments and geographic regions.\n"
            "Market trends indicate continued strong growth throughout next year.\n"
        )
        result = detect_coverage(doc)
        assert "risks" not in result["covered"], (
            f"Negated risks ('no risks', 'zero threats') should not count. "
            f"covered={result['covered']}, risk_count={result['categories']['risks']['count']}"
        )

    def test_negated_uncertainty_not_covered(self):
        """A document that denies uncertainty should not get uncertainty
        coverage credit."""
        doc = (
            "## Certainty Statement\n\n"
            "There is zero uncertainty about the product timeline or delivery.\n"
            "Without any unresolved questions, the strategy is entirely clear.\n"
            "The path forward has no unclear elements or debated assumptions.\n"
            "Revenue grew substantially in every quarter of the fiscal year.\n"
            "Growth accelerated through the second half of the reporting period.\n"
            "Market trends indicate strong continued demand going forward.\n"
        )
        result = detect_coverage(doc)
        assert "uncertainty" not in result["covered"], (
            f"Negated uncertainty should not count. "
            f"covered={result['covered']}, unc_count={result['categories']['uncertainty']['count']}"
        )

    def test_dismissed_count_tracked(self):
        """When risk keywords are negated, the dismissed count should
        reflect how many were filtered. A document with 3 negated risk
        keywords and 0 surviving should have dismissed=3."""
        doc = (
            "## Safety Report\n\n"
            "There are no meaningful risks associated with this product at all.\n"
            "Our testing found zero safety threats or material concerns anywhere.\n"
            "The product poses no challenges to existing regulations or standards.\n"
            "Revenue expanded by twenty-eight percent compared to the prior year.\n"
            "The company grew sales across all segments and geographic regions.\n"
            "Market trends indicate continued strong growth throughout next year.\n"
        )
        result = detect_coverage(doc)
        risks = result["categories"]["risks"]
        assert risks["dismissed"] >= 2, (
            f"Expected at least 2 dismissed risk keywords, got {risks['dismissed']}"
        )
        assert "risks" not in result["covered"], (
            "Dismissed risks should not count as covered"
        )

    def test_dismissed_surfaces_in_portrait(self):
        """When risk language is explicitly dismissed (negated >= 2),
        the portrait should say 'explicitly dismissed' not just
        'no downside scenarios'."""
        doc = (
            "## Safety Report\n\n"
            "There are no meaningful risks associated with this product at all.\n"
            "Our testing found zero safety threats or material concerns anywhere.\n"
            "The product poses no challenges to existing regulations or standards.\n"
            "Revenue expanded by twenty-eight percent compared to the prior year.\n"
            "The company grew sales across all segments and geographic regions.\n"
            "Market trends indicate continued strong growth throughout next year.\n"
        )
        from framing import framing_portrait
        from claim_analysis import analyze_claims
        cov = detect_coverage(doc)
        voice = detect_voice(doc)
        temp = temporal_orientation(doc)
        epist = detect_epistemic_basis(doc)
        ca = analyze_claims(doc)
        portrait = framing_portrait(cov, temp, voice, epist, ca)
        assert "dismissed" in portrait.lower(), (
            f"Portrait should mention dismissal. Got: {portrait}"
        )

    def test_diminisher_does_not_bleed_across_sentences(self):
        """A diminisher in one sentence must not filter risk keywords
        in the next sentence. 'Risks are minimal. However, threats
        and vulnerabilities remain.' should cover risks from the second
        sentence.

        Regression test for cross-sentence diminisher bleed fix."""
        doc = (
            "## Market Analysis\n\n"
            "Risks are minimal in the current operating environment.\n"
            "However, supply chain threats and regulatory barriers could\n"
            "significantly impact the business going forward this year.\n"
            "Revenue grew by thirty percent compared to the prior year.\n"
            "The company expanded sales across all geographic segments.\n"
            "Market trends indicate continued strong demand and growth.\n"
        )
        result = detect_coverage(doc)
        assert "risks" in result["covered"], (
            f"Diminisher in previous sentence should not filter keywords "
            f"in current sentence. count={result['categories']['risks']['count']}, "
            f"dismissed={result['categories']['risks'].get('dismissed', 0)}"
        )

    def test_negation_does_not_suppress_legitimate_discussion(self):
        """Sentences where 'no' modifies a different noun (not the
        risk keyword) should still count as risk discussion."""
        doc = (
            "## Market Risk Analysis\n\n"
            "No company can afford to ignore the growing cybersecurity risks today.\n"
            "There is no doubt that supply chain threats remain very serious.\n"
            "Risks are real and substantial across every segment of the business.\n"
            "Challenges in regulatory compliance continue to mount significantly.\n"
            "Revenue grew substantially in every quarter of the fiscal year.\n"
            "Growth accelerated through the second half of the reporting period.\n"
        )
        result = detect_coverage(doc)
        assert "risks" in result["covered"], (
            f"Legitimate risk discussion (negation on other noun) should count. "
            f"covered={result['covered']}, risk_count={result['categories']['risks']['count']}"
        )


# ================================================================
# GROUP 3: TEMPORAL ORIENTATION
# ================================================================

class TestTemporalOrientation:
    """temporal_orientation computes past/present/future percentages
    based on tense markers in each sentence. Present is the residual
    bucket for sentences with no past/future markers."""

    def test_future_dominant_doc(self):
        """A doc that talks entirely about future plans should
        be classified as future-dominant."""
        doc = (
            "## Five Year Plan\n\n"
            "We will launch the new platform across all markets in 2027.\n"
            "Revenue will reach one billion dollars within the next three years.\n"
            "The company will expand into Asia in the second half of next year.\n"
            "Costs will decline as the manufacturing facility comes online soon.\n"
            "Customers will benefit from the new features being developed currently.\n"
            "Innovation will continue to drive long-term growth into the next decade.\n"
        )
        result = temporal_orientation(doc)
        assert result["dominant"] == "future", (
            f"Expected future-dominant, got {result['dominant']}. "
            f"past={result['past_pct']}, present={result['present_pct']}, "
            f"future={result['future_pct']}"
        )
        assert result["future_pct"] >= 50, (
            f"Expected future_pct >= 50, got {result['future_pct']}"
        )

    def test_past_dominant_doc(self):
        """A doc that recounts historical events should be
        classified as past-dominant."""
        doc = (
            "## Company History\n\n"
            "The founders started the company in nineteen ninety-eight from a garage.\n"
            "Revenue grew rapidly during the early years of the dot-com boom period.\n"
            "The company went public in two thousand four after filing its prospectus.\n"
            "Several acquisitions followed over the next decade and a half period.\n"
            "Profits reached record highs in two thousand twenty during the pandemic.\n"
            "The CEO retired last year after a long and distinguished career there.\n"
        )
        result = temporal_orientation(doc)
        assert result["dominant"] == "past", (
            f"Expected past-dominant, got {result['dominant']}. "
            f"past={result['past_pct']}, present={result['present_pct']}, "
            f"future={result['future_pct']}"
        )

    def test_distribution_sums_to_100_across_corpora(self):
        """Largest Remainder method invariant: past_pct + present_pct +
        future_pct must sum to exactly 100 for any non-empty document.
        Pre-2026-04-28 used independent round() per bucket which
        produced sums of 99 or 101 on real corpus documents; this test
        guards against any regression to that pattern (or any other
        rounding scheme that doesn't preserve the sum invariant).

        Sentences must clear split_sentences's >30-char filter to count;
        the cases below are long-form synthetic prose with varied tense
        mixes that exercise the residue-distribution path. Each case
        produces a non-degenerate (sentence_count >= 2) sentence list
        so the residue is non-trivially in {0, 1, 2}.
        """
        # Each case: a markdown doc with at least 7 long sentences in
        # varied tense mixes. The sentence-count + tense-distribution
        # combinations are chosen to land on different fractional-part
        # patterns, exercising residue=0, 1, and 2 paths.
        cases = [
            # Past-dominant historical narrative.
            "## History\n\n"
            "The founders started the company in nineteen ninety-eight from a garage.\n"
            "Revenue grew rapidly during the early years of the dot-com boom.\n"
            "The company went public in two thousand four after filing.\n"
            "Several acquisitions followed over the next decade in the industry.\n"
            "Profits reached record highs in two thousand twenty during the pandemic.\n"
            "The CEO retired last year after a long and distinguished career.\n"
            "Many employees stayed through the long arc of the company's life.\n",
            # Future-dominant strategy doc.
            "## Five Year Plan\n\n"
            "We will launch the new platform across all markets in 2027.\n"
            "Revenue will reach one billion dollars within the next three years.\n"
            "The company will expand into Asia in the second half of next year.\n"
            "Costs will decline as the manufacturing facility comes online soon.\n"
            "Customers will benefit from the new features being developed currently.\n"
            "Innovation will continue to drive long-term growth into the next decade.\n"
            "Markets will reward the disciplined approach we plan to maintain.\n",
            # Mixed past + present + future, biased toward present.
            "## Mixed Document\n\n"
            "The company achieved record revenue last quarter according to filings.\n"
            "Operations continue to run smoothly across all major regions today.\n"
            "Customer acquisition costs are declining steadily over time periods.\n"
            "The product team will ship a major release in the third quarter.\n"
            "Market share remains strong despite increased competitive pressure.\n"
            "Engineering velocity is accelerating as the team grows in size.\n"
            "Forward guidance suggests continued momentum into the next year.\n",
            # Heavy mix to exercise residue distribution.
            "## Variety\n\n"
            "We grew the topline by twenty percent last year through new launches.\n"
            "The team will continue to expand into adjacent verticals next season.\n"
            "Customers report high satisfaction across all major surveys conducted.\n"
            "Margins improved as cost discipline took hold in the second half.\n"
            "Future product lines will leverage the same go-to-market motion.\n"
            "Operations are stable and predictable across our global footprint.\n"
            "Several risks remain on the horizon but we plan to address them.\n",
        ]
        for doc in cases:
            result = temporal_orientation(doc)
            total = (
                result["past_pct"] + result["present_pct"]
                + result["future_pct"]
            )
            assert total == 100, (
                f"distribution must sum to exactly 100; got {total} "
                f"for doc starting {doc[:60]!r}: past="
                f"{result['past_pct']}, present={result['present_pct']}, "
                f"future={result['future_pct']}"
            )

    def test_empty_document_returns_zero_pcts(self):
        """Zero-sentence edge case: empty (or whitespace-only) input
        must return all-zero pcts rather than spuriously assigning the
        residue to a bucket. Pinning this explicitly because the LR
        algorithm's residue-distribution loop would otherwise read from
        a zero-floor / zero-fractional triad and assign the residue to
        whichever bucket sorted first. Documents that fail
        split_sentences's >30-char filter (very short prose, fragments)
        also land here; the early-return guards them too.
        """
        for doc in ("", "   ", "\n\n\n", "Short. Tiny. Brief."):
            result = temporal_orientation(doc)
            assert result["past_pct"] == 0
            assert result["present_pct"] == 0
            assert result["future_pct"] == 0


# ================================================================
# GROUP 4: EPISTEMIC BASIS
# ================================================================

class TestEpistemicBasis:
    """detect_epistemic_basis identifies how many sentences in a
    document have source attribution. Two signals: explicit source
    markers ('according to', 'study') and entity attribution
    ('Apple reported', 'NIH announced')."""

    def test_well_sourced_doc(self):
        """A doc with explicit source attribution on most sentences
        should report a high sourced_pct."""
        doc = (
            "## Industry Trends\n\n"
            "According to a recent McKinsey study, the market is growing at fifteen percent.\n"
            "Research from MIT shows that adoption is accelerating across all industries surveyed.\n"
            "A Bloomberg analysis found that prices have stabilized in the past two quarters.\n"
            "Pew Research polled consumers and discovered widespread interest in the technology.\n"
            "Industry data from Gartner indicates that spending will reach new records next year.\n"
            "Apple reported strong results in its most recent quarterly earnings filing released.\n"
        )
        result = detect_epistemic_basis(doc)
        assert result["sourced_pct"] >= 60, (
            f"Expected sourced_pct >= 60, got {result['sourced_pct']}. "
            f"sourced={result['sourced']}, total={result['total_sentences']}"
        )

    def test_unsourced_doc(self):
        """A doc that asserts everything without attribution should
        report a low sourced_pct."""
        doc = (
            "## Market Outlook\n\n"
            "The market is growing rapidly across multiple geographic regions worldwide.\n"
            "Adoption is accelerating in every major customer segment surveyed extensively.\n"
            "Competition is intensifying as more entrants pursue the same opportunity space.\n"
            "Margins are improving for early movers with established brand recognition already.\n"
            "Demand exceeds available supply in most premium product categories observed.\n"
            "Growth seems sustainable based on current macroeconomic and demographic trends.\n"
        )
        result = detect_epistemic_basis(doc)
        assert result["sourced_pct"] <= 20, (
            f"Expected sourced_pct <= 20 for unsourced doc, got {result['sourced_pct']}. "
            f"sourced={result['sourced']}, total={result['total_sentences']}"
        )

    def test_entity_attribution_counts_as_sourced(self):
        """Sentences with real entity attribution ('Apple reported',
        'NIH announced') should count as sourced even without
        explicit source markers."""
        doc = (
            "## Healthcare Quarterly\n\n"
            "Pfizer announced quarterly results above analyst estimates this morning early.\n"
            "Moderna disclosed new vaccine trial data in a regulatory filing last week.\n"
            "Johnson and Johnson reported steady revenue growth in its consumer division.\n"
            "Eli Lilly published clinical trial outcomes for its new diabetes medication.\n"
            "Novo Nordisk filed updated safety information with European regulators recently.\n"
            "Merck stated that the fourth quarter would see continued momentum overall.\n"
        )
        result = detect_epistemic_basis(doc)
        assert result["sourced_pct"] >= 50, (
            f"Expected entity attributions to register as sourced. "
            f"Got sourced_pct={result['sourced_pct']}, "
            f"sourced={result['sourced']}, total={result['total_sentences']}"
        )

    def test_self_reference_does_not_count_as_sourced(self):
        """'The company reported', 'we disclosed' must NOT count as
        source attribution. Self-reference is not a source."""
        doc = (
            "## Internal Update\n\n"
            "The company reported strong quarterly performance to its board of directors.\n"
            "The firm disclosed several strategic initiatives during the management meeting.\n"
            "Our team reported notable progress on the platform migration this past month.\n"
            "We announced new product features at the recent industry conference attended.\n"
            "The organization stated its commitment to long-term sustainable growth always.\n"
            "Management confirmed the prior guidance for the upcoming fiscal year ahead.\n"
        )
        result = detect_epistemic_basis(doc)
        # All sentences are self-reference. Sourced count should be very low.
        assert result["sourced_pct"] <= 20, (
            f"Self-reference should not count as sourced. "
            f"Got sourced_pct={result['sourced_pct']}"
        )


# ================================================================
# GROUP: split_sentences paragraph-joining behavior
# ================================================================
# These tests validate the fix to split_sentences that joins
# consecutive non-heading, non-list-item lines into paragraphs
# before splitting by sentence boundary. Without the fix,
# sentences that wrap across lines were split at line breaks,
# and short fragments were silently dropped.

from clarethium_measure import split_sentences


class TestSplitSentencesParagraphJoining:

    def test_wrapped_paragraph_joins_lines(self):
        """Sentences that wrap across lines should be joined."""
        text = (
            "## Analysis\n"
            "The company reported revenue of $47.5 billion,\n"
            "driven by strong data center demand across all regions.\n"
        )
        results = split_sentences(text)
        sentences = [s for _, s, _ in results]
        assert len(sentences) == 1, (
            f"Wrapped paragraph should produce 1 sentence, got {len(sentences)}: {sentences}"
        )
        assert "47.5 billion" in sentences[0]
        assert "data center demand" in sentences[0]

    def test_wrapped_paragraph_short_fragments_not_dropped(self):
        """Short line fragments should not be dropped when they are
        part of a longer sentence that wraps across lines."""
        text = (
            "## Growth\n"
            "Revenue grew to\n"
            "$47.5 billion in fiscal year 2025.\n"
        )
        results = split_sentences(text)
        sentences = [s for _, s, _ in results]
        assert len(sentences) == 1, (
            f"Wrapped short lines should join into 1 sentence, got {len(sentences)}: {sentences}"
        )
        assert "Revenue grew" in sentences[0]
        assert "$47.5 billion" in sentences[0]

    def test_two_sentences_on_consecutive_lines(self):
        """Two complete sentences on consecutive lines (no blank line
        between them) should be joined into one paragraph then split
        back by the sentence boundary regex."""
        text = (
            "## Overview\n"
            "The semiconductor market reached $574 billion in global revenue last year.\n"
            "Analysts project continued growth driven by artificial intelligence demand.\n"
        )
        results = split_sentences(text)
        sentences = [s for _, s, _ in results]
        assert len(sentences) == 2, (
            f"Two sentences on consecutive lines should produce 2, got {len(sentences)}: {sentences}"
        )

    def test_list_items_processed_independently(self):
        """List items should not be joined with surrounding text."""
        text = (
            "## Key Findings\n"
            "- Revenue increased by 26 percent year over year to reach new highs.\n"
            "- Operating margin expanded to 38 percent from the prior year level.\n"
            "- The company returned $25 billion to shareholders through buybacks.\n"
        )
        results = split_sentences(text)
        sentences = [s for _, s, _ in results]
        assert len(sentences) == 3, (
            f"Three list items should produce 3 sentences, got {len(sentences)}: {sentences}"
        )

    def test_paragraph_break_at_empty_line(self):
        """Empty lines should break paragraphs."""
        text = (
            "## Section A\n"
            "First paragraph discusses the revenue growth trajectory in detail.\n"
            "\n"
            "Second paragraph addresses the risk factors and market uncertainties.\n"
        )
        results = split_sentences(text)
        sentences = [s for _, s, _ in results]
        assert len(sentences) == 2
        para_indices = [idx for _, _, idx in results]
        assert para_indices[0] != para_indices[1], (
            "Different paragraphs should have different para_idx values"
        )

    def test_heading_breaks_paragraph(self):
        """Headings should break paragraphs even without blank lines."""
        text = (
            "## Revenue\n"
            "The company reported strong revenue growth across all product lines.\n"
            "## Risks\n"
            "Several risk factors could impact the forward-looking projections.\n"
        )
        results = split_sentences(text)
        headings = [h for h, _, _ in results]
        assert headings[0] == "Revenue"
        assert headings[1] == "Risks"

    def test_mixed_list_and_paragraph(self):
        """List items between paragraph text should not merge with it."""
        text = (
            "## Analysis\n"
            "The following factors contributed to the strong quarterly performance:\n"
            "- Data center revenue surged 154 percent driven by AI training demand.\n"
            "- Gaming revenue recovered with new product launches in the quarter.\n"
            "Overall the company exceeded analyst expectations by a wide margin.\n"
        )
        results = split_sentences(text)
        sentences = [s for _, s, _ in results]
        assert len(sentences) >= 4, (
            f"Para + 2 list items + para should produce at least 4, got {len(sentences)}: {sentences}"
        )
        assert any("Data center" in s for s in sentences)
        assert any("Gaming" in s for s in sentences)
        assert any("exceeded" in s for s in sentences)


class TestComputeSentenceSpansPerformance:
    """Performance pins for _compute_sentence_spans (framing.py:477).

    The function locates each sentence from split_sentences inside
    the original text using a whitespace-tolerant regex. Pre-2026-04-30
    the implementation had two pathologies that combined to produce
    O(n_sentences * text_length) wall-clock on long documents and
    catastrophic backtracking on documents containing markdown tables.
    Both are fixed; the tests below pin the fix so the slow shape
    cannot return without surfacing.
    """

    def test_markdown_table_does_not_trigger_catastrophic_backtracking(self):
        """A markdown table joined into a single sentence by
        split_sentences must not trigger catastrophic regex
        backtracking. The probe (first 60 chars of the table) has
        long runs of consecutive spaces (column padding); the
        whitespace-tolerant pattern construction must collapse
        those runs into a single \\s+ rather than emitting one
        \\s+ per escaped-space, which created N independent
        quantifiers and exponential backtracking.

        Empirical regression: at the 30K-cap doc-size sweep the
        sole table-bearing sentence in the worked-examples corpus
        took 678ms to locate, dominating the 700ms total; this
        test pins the fix at <50ms per call (200x headroom over
        the regression).
        """
        from framing import _compute_sentence_spans
        import time

        # Markdown table that mirrors the worked-examples corpus
        # shape: column-padded cells joined by | separators. The
        # padding produces 20+ consecutive spaces in the joined
        # sentence which is the catastrophic-backtracking trigger.
        text = (
            "## Per-model signature\n"
            "\n"
            "| Model   | Voice         | Covers                              |"
            " Missing                                    | Sourced |\n"
            "| ------- | ------------- | ----------------------------------- |"
            " ------------------------------------------ | ------- |\n"
            "| Claude  | prescriptive  | causes                              |"
            " risks, stakeholders, trends, uncertainty   | 0%      |\n"
            "| GPT-5   | prescriptive  | risks, trends                       |"
            " causes, stakeholders, uncertainty          | 0%      |\n"
        )

        # Warm so first-call regex compile cost does not skew.
        _compute_sentence_spans(text)

        t0 = time.perf_counter()
        for _ in range(5):
            _compute_sentence_spans(text)
        per_call_ms = (time.perf_counter() - t0) * 200  # avg of 5 in ms

        assert per_call_ms < 50, (
            f"_compute_sentence_spans on a markdown-table document "
            f"took {per_call_ms:.1f}ms per call (regression budget: "
            f"50ms). Pre-fix the same case took 678ms; the "
            f"run-collapse fix in the whitespace-tolerant pattern "
            f"construction must hold for this not to recur."
        )

    def test_long_document_scales_under_substrate_budget(self):
        """The function must complete in well under the 100ms
        budget the substrate analyzers as a whole share. The test
        measures at 30_000 chars (above the current production cap
        of MAX_DOC_CHARS=20_000) so it surfaces regressions that
        appear above the cap before they appear at the cap. Two
        rationales for measuring above the cap rather than at it:

        1. Headroom check. The cap can move (it has moved twice in
           a week: 10K -> 30K -> 20K). A test that measures only
           at the current cap silently loses headroom every time
           the cap drops.

        2. F-1 unblocked the substrate to handle ~500K chars
           cleanly. Pinning at 30K confirms the F-1 fix holds
           well above the operating point. Pre-F-1, this case
           took 692ms; post-fix, ~2ms.

        Regression budget: 50ms (25x headroom). Above that,
        _compute_sentence_spans is eating too much of the 15-second
        analyzer-timeout envelope and F-1 has regressed.
        """
        from framing import _compute_sentence_spans
        import pathlib
        import time

        worked = sorted(pathlib.Path(__file__).parent.parent.glob(
            "data/worked_examples/*.md"
        ))
        parts = [
            p.read_text() for p in worked
            if not p.name.startswith("_") and p.name != "README.md"
        ]
        if not parts:
            # Nothing to test in this environment; skip silently.
            return
        natural = "\n\n---\n\n".join(parts)
        text = natural[:30_000]

        # Warm
        _compute_sentence_spans(text)

        t0 = time.perf_counter()
        for _ in range(3):
            _compute_sentence_spans(text)
        per_call_ms = (time.perf_counter() - t0) * 1000 / 3

        assert per_call_ms < 50, (
            f"_compute_sentence_spans at 30K natural prose took "
            f"{per_call_ms:.1f}ms per call (regression budget: 50ms)."
        )
