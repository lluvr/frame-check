"""Regression scaffold for the Bitcoin/gold stress-test campaign.

This test locks the observed output of `build_epistemic_payload` and
`build_compare_payload` on a real-world advocacy document and a
deliberately-asymmetric counter-document, so that subsequent detector
or renderer changes produce a visible diff. It is a regression
scaffold, not a correctness test: several assertions pin construct-
honesty boundaries already documented in data/adversarial_fixtures/.

Findings tracked:

  F1 (genre): instruction wins decisively over advocacy on numbered
              argument sections. Sharpened against the FOMC regulatory
              doc, which has no numbered sections and correctly
              abstains (classification=None, confidence=low). So the
              defect is specifically the numbered-section promotion
              of instruction in advocacy contexts, not a blanket
              high-confidence-always behavior. The existing
              sales_pitch_as_analysis fixture covers a different
              recommendation-vs-narrative case; numbered-argument
              advocacy with non-procedural section content is a
              candidate new fixture. Asserted value locks current
              behavior; the FOMC tests below prove abstention works
              when the numbered-section trigger is absent.
  F2 (voice): analytical fires as cascade residual with confidence
              high. This is DELIBERATE design (locked separately by
              test_construct_honesty_voice::test_residual_analytical_
              confidence_is_always_high; documented in fixture
              voice_residual_analytical). The cascade hands caveat-
              rendering to the agent via the construct text.
  F3 (source network): pipx-installed wheel has no API keys; checked
              is 0 even though numeric_sentences is 17. Architectural
              decision pending; assertion locks current observed state.
  F4 (coverage): risks not flagged on bitcoin-thesis despite Section
              8 risk content (quantitative vocabulary: drawdown,
              standard deviation). RELATED to the existing fixture
              coverage_via_noncanonical_vocabulary which documents
              the evidence discipline: substrate intentionally
              operates on canonical regex vocabulary; under-detection
              on domain-specific language is acknowledged and the
              correct response is caveat propagation, NOT regex
              expansion (regex expansion would over-fire on existing
              fixtures). Cross-tool confirmed: frame_compare against
              gold-counter shows risks omitted only on bitcoin-thesis.
              Any future improvement is authoring scope: the
              under-detection on domain vocabulary is the documented
              design boundary, not a bug to fix.
  F6 (truth-in-labelling): evidence.signal_text read "No numerical
              claims to verify against sources" when checked == 0
              even with 17 numeric sentences (CLOSED 2026-04-30 by
              decision_readiness:_evidence_dimension; this regression
              now asserts the corrected text).
"""

import os
import sys

import mcp_server  # type: ignore  # pylint: disable=import-error

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOMC_PATH = os.path.join(
    REPO_ROOT, "data", "worked_examples", "fomc-statement-march-2026.md"
)


def _load_fomc():
    with open(FOMC_PATH, "r", encoding="utf-8") as f:
        return f.read()

DOC = """Core conclusion

Bitcoin is better than gold if the goal is the hardest, most portable, most verifiable, highest-upside store-of-value asset.

Gold is still better if the goal is lower volatility, crisis familiarity, and thousands of years of institutional trust.

So the strong claim is not "Bitcoin is safer than gold."
The strong claim is:

Bitcoin has better monetary properties than gold, but gold has better historical stability.

1. Bitcoin is scarcer than gold

Bitcoin has a fixed maximum supply of 21 million BTC, and by early 2026 over 95% had already been mined. Its issuance schedule is programmed through halvings roughly every four years.

After the 2024 halving, the block reward became 3.125 BTC per block. With roughly 144 blocks per day, that is about:

3.125 x 144 x 365 = 164,250 new BTC per year

With roughly 20 million BTC already mined, Bitcoin's current new supply rate is about:

164,250 / 19,960,000 = 0.82% per year

Gold is not fixed. The World Gold Council estimates total above-ground gold stock at 219,891 tonnes at end-2025, while 2025 mine production was about 3,672 tonnes.

That means gold's new mine supply rate is about:

3,672 / 219,891 = 1.67% per year

Data point: Bitcoin's new supply rate is currently roughly half of gold's, and after the next halving it should drop again.

That is the cleanest scarcity argument.

2. Bitcoin has a stronger stock-to-flow profile

Stock-to-flow means existing stock divided by annual new production.

Bitcoin today:
Existing stock around 19.96M BTC
Annual new supply around 164,250 BTC
Stock-to-flow around 121

Gold:
Existing stock 219,891 tonnes
Annual mine production 3,672 tonnes
Stock-to-flow around 60

So Bitcoin's current stock-to-flow is roughly 2x gold's.

This does not guarantee price appreciation, but it does prove one thing clearly:

Bitcoin is structurally harder to inflate than gold.

3. Bitcoin has crushed gold in purchasing power over 10 years

Measured directly against gold, Bitcoin has returned about 4,617% in gold terms from April 30, 2016 to April 30, 2026. In plain English, one Bitcoin buys dramatically more gold today than it did 10 years ago.

That is one of the strongest arguments because it removes the dollar from the equation.

It answers this question:

Has Bitcoin preserved and increased purchasing power against gold itself?

Over the last 10 years, yes. Massively.

4. Bitcoin still has much more upside by market size

As of April 30, 2026, Bitcoin was around $76,103. Spot gold was around $4,615.50 per ounce.

Using World Gold Council's above-ground stock estimate, gold's total market value is roughly:

219,891 tonnes x 32,150.7 oz per tonne x $4,615.50 = about $32.6 trillion

Bitcoin's market cap at roughly 19.96M BTC and $76,103 is about:

$1.52 trillion

So gold is still about 21.5x larger than Bitcoin.

That creates the asymmetric upside case:

If Bitcoin reached only 10% of gold's market cap, implied BTC price would be around $163,000.

If Bitcoin reached 25% of gold's market cap, implied BTC price would be around $409,000.

If Bitcoin reached 50% of gold's market cap, implied BTC price would be around $817,000.

This is not a prediction. It is market cap math.

The argument is simple:

Gold already became the global store-of-value asset. Bitcoin is still repricing into that role.

5. Bitcoin is more portable

Gold is heavy, physical, and expensive to move securely.

At $4,615.50 per ounce, $1 billion of gold equals roughly:

216,660 ounces, or about 6.7 metric tonnes

Moving that across borders requires vaults, insurance, logistics, guards, customs, and settlement infrastructure.

Bitcoin can move the same economic value globally through a digital network. That is not a small advantage. It is a different category of asset.

Gold is physical wealth.
Bitcoin is networked wealth.

6. Bitcoin is easier to verify

Gold must be assayed, stored, audited, insured, and protected. Even institutional gold ownership often depends on custody chains and reserve reporting.

Bitcoin can be verified by the network itself. Supply, ownership history, and settlement can be independently checked by anyone running a node or using blockchain data.

That matters because the modern financial system is moving toward assets that are:

Auditable, programmable, instantly transferable, and digitally native.

Gold is trusted because of history.
Bitcoin is trusted because of rules and verification.

7. Institutional adoption is no longer theoretical

BlackRock's iShares Bitcoin Trust ETF had about $61.16 billion in net assets as of April 29, 2026, with a 30-day average volume of about 41.1 million shares.

The Federal Register also cited IBIT market capitalization of about $52.66 billion and average daily volume of about 61.8 million shares as of February 11, 2026, while noting Bitcoin's total market cap was above $1.374 trillion at that time.

That matters because Bitcoin is no longer just a retail speculation vehicle.

It has entered the institutional wrapper layer: ETFs, custody, options, liquidity, portfolio allocation models.

That makes it much easier for capital to flow into Bitcoin than it was in previous cycles.

8. The honest risk data is still brutal

Bitcoin's upside comes with serious volatility.

From January 2011 to March 2026, Bitcoin had a compound annual return of about 126.44%, but with 180.05% standard deviation and a maximum drawdown of 81.56%.

Gold is much calmer. For GLD, the 30-year data through March 2026 showed about 8.25% annualized return, 16.18% standard deviation, and a maximum drawdown of 42.91%.

So the tradeoff is clear:

Bitcoin wins on upside, scarcity, portability, and verifiability.

Gold wins on stability, lower volatility, and psychological trust.

Final framing

The strongest case for Bitcoin over gold is this:

Bitcoin is a better monetary technology. It has fixed supply, lower issuance, higher stock-to-flow, superior portability, better divisibility, easier verification, and stronger asymmetric upside.

But the strongest counterpoint is also real:

Gold is still the more mature crisis asset. Bitcoin is better money in design, but gold is still better proven in panic.

My honest strategist take:

Bitcoin is better than gold for the next era of wealth storage. Gold is better for surviving the old era's fear cycles.
"""


GOLD_COUNTER = """Why gold is still the safer store of value than Bitcoin

Gold has been a reliable store of monetary value for thousands of years. Bitcoin has existed since 2009. The track record difference alone is reason for caution.

1. Volatility risk

Bitcoin has fallen more than 80% from peak in multiple cycles. Holders who bought near a top and needed to sell during a drawdown realized large losses. Gold's worst drawdown over 30 years was 42.91%, roughly half of Bitcoin's 81.56% maximum drawdown.

For retirees, foundations, or any holder with non-discretionary withdrawal needs, that volatility translates directly into sequence-of-returns risk that gold does not impose.

2. Custodial uncertainty

Bitcoin self-custody requires technical literacy. Lost keys mean lost coins, with no recovery process. Estimates suggest 3 to 4 million BTC are permanently lost.

Gold custody is a solved problem. Vaulting, insurance, and chain-of-custody all have centuries of standard practice and legal infrastructure. The downside risk is bounded.

3. Regulatory exposure

Bitcoin remains subject to evolving regulatory regimes worldwide. China banned domestic mining in 2021 with no advance warning.

Gold ownership is regulated but with a much narrower distribution of regulatory outcomes.

4. Network dependency

Bitcoin relies on continuous electrical power and internet connectivity to settle transactions. Gold can be physically transferred without any infrastructure dependency.

5. The store-of-value test is survival, not upside

Gold has passed regime-change tests repeatedly: through two world wars, multiple currency collapses, and several severe banking crises.

Bitcoin has not been tested in any of those conditions.

Conclusion

For asymmetric upside, Bitcoin remains a defensible speculative position. For asset preservation across regime change, gold's track record is unmatched.
"""


def check(condition, message):
    if not condition:
        print(f"FAIL: {message}")
        sys.exit(1)
    print(f"  ok: {message}")


def test_top_level_contract():
    """Top-level keys match FRAME_DIVERGENCE_CONTRACT_v1 §4.1."""
    p = mcp_server.build_epistemic_payload(DOC)
    expected = {"analysis", "agent_guidance", "provenance", "divergence"}
    actual = set(p.keys())
    check(expected.issubset(actual),
          f"top-level keys cover the four-key contract; got {sorted(actual)}")


def test_genre_classifies_numbered_argument_essay_as_instruction():
    """F1: numbered argument sections push the cascade toward
    'instruction' (current observed: confidence high, decisive
    margin). The sales_pitch_as_analysis fixture covers a related
    case at the recommendation layer but does NOT cover this exact
    class. Locks current behavior; will need updating if a new
    fixture lands or the cascade picks up a numbered-argument
    disambiguation rule.
    """
    p = mcp_server.build_epistemic_payload(DOC)
    g = p["analysis"]["genre"]
    check(g["classification"] == "instruction",
          f"genre currently classifies numbered-argument essay as "
          f"'instruction'; got {g['classification']}")
    check(g["confidence"] == "high",
          f"genre confidence is currently 'high' on this case; "
          f"got {g['confidence']}")


def test_voice_residual_high_confidence():
    """F2: analytical fires as cascade residual with confidence high."""
    p = mcp_server.build_epistemic_payload(DOC)
    v = p["analysis"]["voice"]
    check(v["classification"] == "analytical",
          f"voice classifies as 'analytical' residual; got {v['classification']}")
    check(v["confidence"] == "high",
          f"voice confidence currently 'high' on residual (F2 internal "
          f"contradiction); got {v['confidence']}")


def test_coverage_under_detects_quantitative_risk_vocabulary():
    """F4: risks regex operates on canonical vocabulary by design
    (per coverage_via_noncanonical_vocabulary fixture's audit). The
    bitcoin doc uses quantitative risk language (drawdown, standard
    deviation, volatility) which is not in the canonical set.
    Under-detection is the documented evidence discipline;
    the correct response is caveat propagation in the headline,
    not regex expansion. Locks current behavior.
    """
    p = mcp_server.build_epistemic_payload(DOC)
    cov = p["analysis"]["coverage"]
    check("risks" in cov["missing"],
          f"risks currently in 'missing' under quantitative-vocabulary "
          f"under-detection; got missing={cov['missing']}")
    check("trends" in cov["missing"],
          f"trends also in 'missing' (only 'causes' and 'uncertainty' "
          f"detected); got missing={cov['missing']}")


def test_evidence_signal_text_truth_in_labelling():
    """F6: when checked == 0 and numeric_sentences > 0, signal_text
    is currently misleading. Update this assertion when
    decision_readiness._evidence_dimension distinguishes 'no claims'
    from 'no attempt'.
    """
    p = mcp_server.build_epistemic_payload(DOC)
    e = p["analysis"]["decision_readiness"]["dimensions"]["evidence"]
    check(e["checked"] == 0,
          f"evidence.checked is 0 (no API keys in test env); got {e['checked']}")
    numeric = p["analysis"]["epistemic"]["numeric_sentences"]
    check(numeric > 0,
          f"epistemic.numeric_sentences > 0 (claims exist); got {numeric}")
    expected_substring = (
        f"0 of {numeric} numerical claim"
    )
    check(expected_substring in e["signal_text"],
          f"evidence.signal_text names the attempted=0 / numeric>0 case; "
          f"got: {e['signal_text']!r}")


def test_claim_extraction_matches_document_density():
    """Sanity check on claim extraction; this doc has ~30 numerical
    claims, so extraction should pull at least 30 to be meaningful."""
    p = mcp_server.build_epistemic_payload(DOC)
    total = p["analysis"]["claims_extracted"]["total"]
    check(total >= 30,
          f"claims_extracted.total >= 30 (doc has dense numerical "
          f"claims); got {total}")


def test_divergence_block_present_with_absences():
    """Divergence block fires by default per FRAME_DIVERGENCE_CONTRACT_v1
    c1.0 and surfaces absent frames. Only active-detection frames appear
    as absences: a retired or meta-side (n/a) frame cannot fire, so it is
    not reported as a phantom absence."""
    p = mcp_server.build_epistemic_payload(DOC)
    d = p.get("divergence")
    check(d is not None, "divergence block present by default")
    absent = d.get("absent_frames", [])
    check(len(absent) >= 5,
          f"divergence.absent_frames surfaces absences; got {len(absent)}")
    # No retired or meta-side frames leak in as phantom absences.
    from frame_library_index import parse_detection_states
    states = parse_detection_states()
    leaked = [f["frame_id"] for f in absent
              if states.get(f["frame_id"]) in ("retired", "n/a")]
    check(not leaked,
          f"absent_frames must exclude retired/meta-side frames; leaked {leaked}")


def test_provenance_carries_iso_timestamp():
    """provenance.analysis_timestamp_utc is the ISO-8601 timestamp the
    README promises (note: README says 'ISO-8601 timestamp' generically;
    the canonical field name is analysis_timestamp_utc, not 'timestamp')."""
    p = mcp_server.build_epistemic_payload(DOC)
    prov = p["provenance"]
    ts = prov.get("analysis_timestamp_utc")
    check(ts is not None and ts.endswith("Z"),
          f"analysis_timestamp_utc populated and Z-suffixed; got {ts!r}")


def test_compare_payload_contract_shape():
    """frame_compare returns analysis / agent_guidance / provenance
    (no divergence; that block is single-document only). The analysis
    block carries 'comparison' and 'documents' keys."""
    p = mcp_server.build_compare_payload(
        DOC, GOLD_COUNTER, "bitcoin-thesis", "gold-counter")
    expected_top = {"analysis", "agent_guidance", "provenance"}
    check(expected_top.issubset(set(p.keys())),
          f"compare top-level covers analysis/agent_guidance/provenance; "
          f"got {sorted(p.keys())}")
    a = p["analysis"]
    check("comparison" in a and "documents" in a,
          f"analysis carries comparison + documents; got {sorted(a.keys())}")


def test_compare_a_omits_risks_b_does_not():
    """Cross-tool confirmation of the F4 under-detection class:
    bitcoin-thesis (quantitative risk vocabulary: drawdown, standard
    deviation) is read as omitting risks; gold-counter (plain risk
    vocabulary: 'Volatility risk', 'exposure') is read as covering
    risks. When the headline-caveat propagation lands in framing.py,
    the under-detection caveat will surface clearly and this
    assertion's framing will need updating."""
    p = mcp_server.build_compare_payload(
        DOC, GOLD_COUNTER, "bitcoin-thesis", "gold-counter")
    cov = p["analysis"]["comparison"]["coverage"]
    check("risks" in cov.get("only_a_misses", []),
          f"bitcoin-thesis (a) currently misses 'risks' while gold-counter "
          f"(b) does not (F4 cross-tool confirmation); got "
          f"only_a_misses={cov.get('only_a_misses')}")


def test_fomc_genre_correctly_abstains():
    """Cross-document control: the FOMC regulatory statement has no
    numbered sections, no recommendation markers, no instruction
    markers. The classifier abstains (classification=None,
    confidence=low) instead of guessing. This is the construct-
    honest evidence-gate behavior. Pinned here so a future genre
    fix targeted at F1 (numbered-argument promotion) does not
    accidentally remove abstention or push FOMC into a confident
    mis-classification."""
    p = mcp_server.build_epistemic_payload(_load_fomc())
    g = p["analysis"]["genre"]
    check(g["classification"] is None,
          f"FOMC genre.classification is None (abstention); "
          f"got {g['classification']!r}")
    check(g["confidence"] == "low",
          f"FOMC genre.confidence is 'low' (abstention semantics); "
          f"got {g['confidence']!r}")


def test_fomc_coverage_detects_all_five_perspectives():
    """The FOMC statement covers all 5 analytical perspectives
    in canonical vocabulary. This is the upper-end of the coverage
    detector's range and is locked here to catch regressions that
    would silently drop a category."""
    p = mcp_server.build_epistemic_payload(_load_fomc())
    cov = p["analysis"]["coverage"]
    check(cov["missing"] == [],
          f"FOMC coverage.missing is empty; got {cov['missing']}")
    expected = {"causes", "risks", "stakeholders", "trends", "uncertainty"}
    check(set(cov["addressed"]) == expected,
          f"FOMC coverage.addressed covers all five; "
          f"got {sorted(cov['addressed'])}")


def test_fomc_evidence_signal_text_zero_numeric_branch():
    """The FOMC statement has zero numerical sentences (qualitative
    monetary-policy language). This exercises the original
    'No numerical claims to verify against sources.' branch in
    decision_readiness:_evidence_dimension, proving the same-day
    truth-in-labelling fix did NOT regress the legitimate
    no-numbers case."""
    p = mcp_server.build_epistemic_payload(_load_fomc())
    e = p["analysis"]["decision_readiness"]["dimensions"]["evidence"]
    numeric = p["analysis"]["epistemic"]["numeric_sentences"]
    check(numeric == 0,
          f"FOMC has zero numeric sentences; got {numeric}")
    check("No numerical claims to verify against sources." in e["signal_text"],
          f"FOMC evidence.signal_text uses the zero-numeric branch; "
          f"got {e['signal_text']!r}")


def test_compare_voice_match_both_residual():
    """Both documents fall to the analytical residual classification
    with high confidence. The compare surface flags this as match=true
    but the construct_note instructs the agent to surface confidence
    on either-borderline cases. Locks the residual-on-both behavior."""
    p = mcp_server.build_compare_payload(
        DOC, GOLD_COUNTER, "bitcoin-thesis", "gold-counter")
    voice = p["analysis"]["comparison"]["voice"]
    check(voice["match"] is True,
          f"voice.match=True (both classified analytical); got {voice['match']}")
    check(voice["a_classification"] == "analytical"
          and voice["b_classification"] == "analytical",
          "both classified as analytical (residual on both)")
    check("construct_note" in voice,
          "voice carries construct_note hint to agent")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    tests = [
        test_top_level_contract,
        test_genre_classifies_numbered_argument_essay_as_instruction,
        test_voice_residual_high_confidence,
        test_coverage_under_detects_quantitative_risk_vocabulary,
        test_evidence_signal_text_truth_in_labelling,
        test_claim_extraction_matches_document_density,
        test_divergence_block_present_with_absences,
        test_provenance_carries_iso_timestamp,
        test_compare_payload_contract_shape,
        test_compare_a_omits_risks_b_does_not,
        test_fomc_genre_correctly_abstains,
        test_fomc_coverage_detects_all_five_perspectives,
        test_fomc_evidence_signal_text_zero_numeric_branch,
        test_compare_voice_match_both_residual,
    ]
    for t in tests:
        print(f"\n=== {t.__name__} ===")
        t()
    print("\nALL OK")


if __name__ == "__main__":
    main()
