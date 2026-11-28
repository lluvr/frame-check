"""A green verdict must mean the same claim, not the same digits.

Every case here came from a live audit of frame.clarethium.com on
2026-11-05, where a true number was contradicted or a false one was
marked Checked because the matcher compared digits and never checked
what they were digits of. Network calls are stubbed; the passages are
the ones the live providers returned.
"""

import json

import pytest

import source_network as sn
from claim_analysis import analyze_claims
from clarethium_measure import (
    number_token_in_source,
    source_matching,
)
from source_network import (
    ClaimDecomposition,
    SourceResult,
    _best_display_source,
    _consensus,
    _match_in_text,
    decompose_claim,
    verify_alpha_vantage,
    verify_sec_edgar,
)


HERO = (
    "I would overweight NVDA here.\n"
    "NVIDIA reported FY2024 revenue of $60.9 billion, up 126% from "
    "$26.97 billion. Net income was $29.76 billion. Microsoft, Amazon, "
    "Google, and Meta together committed roughly $200 billion to AI "
    "data-center buildout.\n"
    "For FY2025 NVIDIA guided revenue to $130 billion."
)


def _xbrl(*rows):
    """Annual XBRL rows as (end_date, filing_fy, filed, value)."""
    return json.dumps({"units": {"USD": [
        {"form": "10-K", "fp": "FY", "end": end, "fy": fy,
         "filed": filed, "val": val}
        for end, fy, filed, val in rows
    ]}}).encode()


APPLE_REVENUE = _xbrl(
    ("2016-09-24", 2018, "2018-11-05", 215_639_000_000),
    ("2022-09-24", 2022, "2022-10-28", 394_328_000_000),
    ("2023-09-30", 2023, "2023-11-03", 383_285_000_000),
)


@pytest.fixture
def apple_sec(monkeypatch):
    monkeypatch.setattr(sn, "_find_cik", lambda subject: ("320193", "AAPL"))
    monkeypatch.setattr(
        sn, "_urlopen_with_deadline",
        lambda req, per_op_timeout=8: APPLE_REVENUE,
    )


def _decomp(sentence, value, metric="", unit="currency", subject="Apple",
            time_period=""):
    return ClaimDecomposition(
        subject=subject, metric=metric, value=value, unit=unit,
        sentence=sentence, time_period=time_period,
    )


# ── SEC: never search a company's history for the nearest number ────

def test_sec_abstains_when_claim_names_no_metric(apple_sec):
    r = verify_sec_edgar(_decomp("Apple paid a $394 billion fine.", 394e9))
    assert r.match_type == "no_data"


def test_sec_abstains_on_metric_it_has_no_concept_for(apple_sec):
    r = verify_sec_edgar(_decomp(
        "Apple is priced at $394 billion.", 394e9, metric="price"))
    assert r.match_type == "no_data"


def test_sec_yearless_claim_does_not_match_an_old_year(apple_sec):
    r = verify_sec_edgar(_decomp(
        "Apple's revenue is $215 billion.", 215e9, metric="revenue"))
    assert r.match_type == "no_data"


def test_sec_yearless_mismatch_is_not_a_contradiction(apple_sec):
    r = verify_sec_edgar(_decomp(
        "Apple's revenue is $330 billion.", 330e9, metric="revenue"))
    assert r.match_type == "no_data"


def test_sec_yearless_claim_can_match_the_latest_year(apple_sec):
    r = verify_sec_edgar(_decomp(
        "Apple's revenue is $383.3 billion.", 383.3e9, metric="revenue"))
    assert r.match_type == "exact"


def _held_filing(r):
    assert r.match_type == "no_data"
    assert r.withheld_refute
    assert r.disagrees
    assert r.source_value
    return r


def test_sec_stated_year_keeps_the_filed_figure(apple_sec):
    r = _held_filing(verify_sec_edgar(_decomp(
        "Apple's revenue in fiscal 2023 was $420 billion.", 420e9,
        metric="revenue", time_period="2023")))
    assert r.source_value == 383_285_000_000


def test_sec_citation_names_the_data_year_and_metric(apple_sec):
    r = verify_sec_edgar(_decomp(
        "Apple's revenue in fiscal 2016 was $215.6 billion.", 215.6e9,
        metric="revenue", time_period="2016"))
    assert r.match_type == "exact"
    assert "FY2016" in r.source_text
    assert "FY2018" not in r.source_text
    assert "revenue" in r.source_text


# ── Alpha Vantage: only the metric the claim names ──────────────────

@pytest.fixture
def apple_av(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test")
    monkeypatch.setattr(sn, "_resolve_ticker", lambda subject: "AAPL")
    monkeypatch.setattr(sn, "_fetch_json", lambda url: {
        "Symbol": "AAPL",
        "RevenueTTM": "400000000000",
        "MarketCapitalization": "3000000000000",
        "GrossProfitTTM": "180000000000",
    })


def test_alpha_vantage_abstains_without_metric(apple_av):
    r = verify_alpha_vantage(_decomp("Apple paid a $400 billion fine.", 400e9))
    assert r.match_type == "no_data"


def test_alpha_vantage_does_not_cross_metrics(apple_av):
    r = verify_alpha_vantage(_decomp(
        "Apple's market cap is $400 billion.", 400e9, metric="market_cap"))
    assert r.match_type == "no_data"


def test_alpha_vantage_net_income_is_not_gross_profit(apple_av):
    r = verify_alpha_vantage(_decomp(
        "Apple's net income is $180 billion.", 180e9, metric="profit"))
    assert r.match_type == "no_data"


def test_alpha_vantage_ttm_cannot_verify_a_dated_claim(apple_av):
    r = verify_alpha_vantage(_decomp(
        "Apple's revenue in 2019 was $400 billion.", 400e9,
        metric="revenue", time_period="2019"))
    assert r.match_type == "no_data"


def test_alpha_vantage_matches_the_named_metric(apple_av):
    r = verify_alpha_vantage(_decomp(
        "Apple's revenue is $400 billion.", 400e9, metric="revenue"))
    assert r.match_type == "exact"


# ── Reference text: the number must be about the same thing ─────────

@pytest.mark.parametrize("sentence,value,metric,unit,subject,passage", [
    (
        "Germany has a population of about 12 million.", 12e6,
        "population", "count", "Germany",
        ("During the later stages of and after World War II, around "
        "12 million ethnic Germans were expelled from the east."),
    ),
    (
        "Mount Everest is 12,000 metres tall.", 12000,
        "height", "distance", "Mount Everest",
        ("Yielding a height above base in the range of 3,650 to 4,650 m "
        "(12,000 to 15,260 ft) on the Tibetan Plateau."),
    ),
    (
        "The Eiffel Tower is 900 metres tall.", 900,
        "height", "distance", "Eiffel Tower",
        ("The top level's upper platform is 276 m (900 ft) above the "
        "ground, and its height makes it a landmark."),
    ),
    (
        "Apple paid a $394 billion fine.", 394e9,
        "", "currency", "Apple",
        ("Apple is the largest technology company by revenue, with "
        "$394 billion in fiscal 2022."),
    ),
])
def test_coincidental_number_does_not_match(
    sentence, value, metric, unit, subject, passage,
):
    d = _decomp(sentence, value, metric=metric, unit=unit, subject=subject)
    assert _match_in_text(passage, value, sentence, decomp=d)[0] is None


@pytest.mark.parametrize("sentence,value,metric,unit,subject,passage", [
    (
        "Germany has a population of about 84 million.", 84e6,
        "population", "count", "Germany",
        ("With a population of 84.7 million according to the census, "
        "Germany is the most populous member state."),
    ),
    (
        "The Eiffel Tower is 330 metres tall.", 330,
        "height", "distance", "Eiffel Tower",
        ("The tower is 330 metres (1,083 ft) tall, about the same height "
        "as an 81-storey building."),
    ),
    (
        "Tesla delivered about 1.81 million vehicles in 2023.", 1.81e6,
        "count", "count", "Tesla",
        "In 2023 the company delivered 1.81 million vehicles worldwide.",
    ),
])
def test_genuine_passage_still_matches(
    sentence, value, metric, unit, subject, passage,
):
    d = _decomp(sentence, value, metric=metric, unit=unit, subject=subject)
    assert _match_in_text(passage, value, sentence, decomp=d)[0] is not None


# ── Web search finds leads, it does not verify ──────────────────────

def _web(match_type):
    return SourceResult(
        source_name="best-of-gaming.be", match_type=match_type,
        source_text="reached $187.4 billion", is_web_search=True,
        confidence=0.75,
    )


@pytest.mark.parametrize("match_type", ["exact", "close", "contradicted"])
def test_web_result_alone_gives_no_verdict(match_type):
    verdict, _conf, detail = _consensus([_web(match_type)])
    assert verdict == "unverifiable"
    assert "best-of-gaming.be" in detail


def test_web_result_does_not_dispute_a_filing():
    filing = SourceResult(
        source_name="SEC Filing", match_type="exact", confidence=0.95)
    verdict, _conf, _detail = _consensus([filing, _web("contradicted")])
    assert verdict == "verified"


def test_wikipedia_alone_is_not_a_check():
    page = SourceResult(
        source_name="Wikipedia", match_type="exact", confidence=0.8,
        source_text="revenue of 60.9 billion",
    )
    verdict, _conf, detail = _consensus([page])
    assert verdict == "unverifiable"
    assert "Wikipedia" in detail
    denied = SourceResult(
        source_name="Wikipedia", match_type="contradicted", confidence=0.8,
        source_value=1.0,
    )
    assert _consensus([denied])[0] == "unverifiable"


def test_wikipedia_does_not_take_the_name_from_a_filing():
    filing = SourceResult(
        source_name="SEC Filing", match_type="exact", confidence=0.6,
        source_url="https://www.sec.gov/example",
    )
    page = SourceResult(
        source_name="Wikipedia", match_type="exact", confidence=0.95,
        source_url="https://en.wikipedia.org/wiki/Example",
    )
    best = _best_display_source([page, filing])
    assert best.source_name == "SEC Filing"
    assert _best_display_source([page]).source_name == "Wikipedia"


def test_wikipedia_does_not_silence_or_invent_a_filing():
    filing = SourceResult(
        source_name="SEC Filing", match_type="exact", confidence=0.95)
    page = SourceResult(
        source_name="Wikipedia", match_type="exact", confidence=0.7)
    assert _consensus([filing, page])[0] == "verified"
    refuted = SourceResult(
        source_name="SEC Filing", match_type="contradicted", confidence=0.9,
        source_text="SEC Filing: 3.6 billion",
    )
    # A page that agrees with the text must not turn a filing's
    # disagreement into an announcement, and must not confirm it either.
    assert _consensus([refuted, page])[0] == "unverifiable"
    assert _consensus([refuted])[0] == "contradicted"


# ── A claim is bound to its own sentence ────────────────────────────

def _hero_claim(token):
    for c in analyze_claims(HERO)["claims"]:
        if any(token in str(n) for n in c["numbers"]):
            return c
    raise AssertionError(f"{token} not extracted")


def test_short_sentence_claim_does_not_absorb_neighbours():
    claim = _hero_claim("29.76")
    assert "Microsoft" not in claim["sentence"]
    assert "26.97" not in claim["sentence"]


def test_short_sentence_claim_keeps_its_scale_word():
    assert "$29.76 billion" in _hero_claim("29.76")["numbers"]


def test_short_sentence_claim_inherits_the_documents_entity():
    claim = _hero_claim("29.76")
    d = decompose_claim(claim, doc_text=HERO, doc_primary_entity="NVIDIA")
    assert d.subject == "NVIDIA"
    assert d.metric == "profit"


# ── Source mode: a different scale is a different number ────────────

@pytest.mark.parametrize("token,source,expected", [
    ("$12.5 million", "Revenue was $12.5 billion in 2023.", False),
    ("$12.5 billion", "Revenue was $12.5 million in 2023.", False),
    ("$12.5B", "Revenue was $12.5 million in 2023.", False),
    ("$12.5 million", "Revenue was $12.5 million in 2023.", True),
    ("$12.5 million", "Revenue was $12.5M in 2023.", True),
    ("$12.5 million", "Revenue was $12,500,000 in 2023.", True),
    ("$12.5 billion", "Revenue was $12.5bn in 2023.", True),
    ("$5,000", "The fee was $5,000 last year.", True),
])
def test_source_match_respects_scale(token, source, expected):
    assert number_token_in_source(token, source) is expected


def test_source_matching_flags_the_scale_error():
    out = source_matching(
        "Revenue was $12.5 million in 2023.",
        "Revenue was $12.5 billion in 2023.",
    )
    assert out["not_in_source"] == 1
    assert out["unsourced_details"][0]["raw"] == "$12.5 million"


# ── Country statistics come from the World Bank alone ───────────────
#
# restcountries.com retired v1-v4, and v5 needs an account. Its failure
# took verify_world_bank down with it, because the ISO code came from
# there, so no false population claim could be contradicted.

@pytest.fixture
def world_bank(monkeypatch):
    calls = []
    series = {
        "SP.POP.TOTL": 83_491_249,
        "NY.GDP.MKTP.CD": 4_500_000_000_000,
        "AG.SRF.TOTL.K2": 357_580,
        "NY.GDP.MKTP.KD.ZG": -0.87,
    }

    def fake_fetch(url, *args, **kwargs):
        calls.append(url)
        assert "restcountries" not in url
        if "/indicator/" in url:
            code = url.split("/indicator/")[1].split("?")[0]
            assert "/country/DE/" in url
            return [{}, [{"value": series[code], "date": "2023"}]]
        return [{}, [
            {"iso2Code": "AW", "name": "Aruba"},
            {"iso2Code": "DE", "name": "Germany"},
        ]]

    monkeypatch.setattr(sn, "_fetch_json", fake_fetch)
    monkeypatch.setattr(sn, "_WB_COUNTRY_CODES", {})
    return calls


def _country(sentence, value, metric="population", unit="count",
             time_period=""):
    return _decomp(sentence, value, metric=metric, unit=unit,
                   subject="Germany", time_period=time_period)


def test_imports_do_not_take_the_gdp_named_earlier_in_the_sentence(world_bank):
    for sentence in (
        "Germany's economy is often discussed, and goods imports were $4.5 trillion in 2023.",
        "Germany's GDP was large in 2023 and goods imports were $4.5 trillion.",
        "Germany's GDP was large in 2023, and the import bill came to $4.5 trillion.",
        "Germany's economy was large in 2023, with goods imports of $4.5 trillion.",
        "Germany's GDP was large in 2023 and goods imports $4.5 trillion.",
        "Germany's GDP was large in 2023, at $4.5 trillion for goods imports.",
        "Germany's GDP was large in 2023, for goods imports, at $4.5 trillion.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 4.5e12, metric="gdp", unit="currency", time_period="2023"))
        assert r.match_type == "no_data", sentence
        assert not r.withheld_refute
        assert not r.source_value
    r = sn.verify_world_bank(_country(
        "Germany's GDP was $4.5 trillion in 2023.",
        4.5e12, metric="gdp", unit="currency", time_period="2023"))
    assert r.match_type == "exact"


def test_world_bank_confirms_a_true_population(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany has a population of about 84 million.", 84e6))
    assert r.match_type == "exact"
    assert r.source_text.startswith("Germany, ")
    assert "Population" in r.source_text


def test_a_city_count_equal_to_the_country_is_not_a_tick(world_bank):
    r = sn.verify_world_bank(_country(
        "In Germany, the city population is about 84 million.", 84e6))
    assert r.match_type == "no_data"
    assert not r.withheld_refute
    assert not r.source_value


def test_a_named_city_equal_to_the_country_is_not_a_tick(world_bank):
    d = _country("In Germany, Hamburg has a population of about 84 million.", 84e6)
    d.subject = "Hamburg"
    r = sn.verify_world_bank(d)
    assert r.match_type == "no_data"
    assert not r.withheld_refute
    assert not r.source_value


def test_world_bank_keeps_a_wildly_false_population(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany has a population of about 12 million.", 12e6))
    # The World Bank earned refute on v32 (2026-11-28).
    assert r.match_type == "contradicted"
    assert not r.withheld_refute
    assert r.source_value == 83_491_249


def test_ten_percent_off_is_not_a_close_match(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany has a population of about 93 million.", 93e6))
    # The World Bank earned refute on v32 (2026-11-28).
    assert r.match_type == "contradicted"
    assert not r.withheld_refute
    assert r.source_value == 83_491_249


@pytest.mark.parametrize("sentence", [
    "About 12 million people in Germany use the service.",
    "Germany has an urban population of 12 million.",
    "Germany has a migrant population of 12 million.",
])
def test_part_of_a_country_is_not_its_population(world_bank, sentence):
    assert sn.verify_world_bank(_country(sentence, 12e6)).match_type == "no_data"


def test_yearless_gdp_mismatch_is_not_a_contradiction(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany's GDP is $900 billion.", 900e9,
        metric="gdp", unit="currency"))
    assert r.match_type == "no_data"


def test_a_quarter_is_not_the_years_gdp(world_bank):
    # The annual series is not a quarter's GDP, even when the digits match.
    # A quarter the figure is set against is not its period.
    for sentence in (
        "Germany's GDP was $4.5 trillion in the fourth quarter of 2023.",
        "Germany's GDP was $4.5 trillion in Q4 2023.",
        "In the fourth quarter of 2023, Germany's GDP was $4.5 trillion.",
        "In Q4 2023, Germany's GDP was $4.5 trillion.",
        "Germany's GDP for the three months ended December 31, 2023 was $4.5 trillion.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 4.5e12, metric="gdp", unit="currency", time_period="Q4 2023"))
        assert r.match_type == "no_data", sentence
        assert not r.withheld_refute
        assert not r.source_value
    for sentence in (
        "Germany's GDP was $4.5 trillion in 2023, compared with the fourth quarter of 2022.",
        "Germany's GDP was $4.5 trillion in 2023 compared with the fourth quarter of 2022.",
        "Germany's GDP was $4.5 trillion in 2023 versus Q4 2022.",
        "Compared with the fourth quarter of 2022, Germany's GDP was $4.5 trillion in 2023.",
        "After the fourth quarter of 2022, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in 2023 after the fourth quarter of 2022.",
        "In the fourth quarter of 2023, Germany's full-year GDP was $4.5 trillion.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 4.5e12, metric="gdp", unit="currency", time_period="2023"))
        assert r.match_type == "exact", sentence


def test_a_part_of_the_year_is_not_the_years_gdp(world_bank):
    for sentence in (
        "Germany's GDP was $4.5 trillion in the first half of 2023.",
        "Germany's GDP was $4.5 trillion in the second half of 2023.",
        "Germany's GDP in the first nine months of 2023 was $4.5 trillion.",
        "Germany's GDP was $4.5 trillion year to date in 2023.",
        "Germany's GDP was $4.5 trillion in H1 2023.",
        "Germany's GDP was $4.5 trillion on a quarterly basis in 2023.",
        "Germany's quarterly GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion at an annualized rate in 2023.",
        "Germany's GDP was $4.5 trillion in June 2023.",
        "In June 2023, Germany's GDP was $4.5 trillion.",
        "In the first half of 2023, Germany's GDP was $4.5 trillion.",
        "On a quarterly basis, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in the first 9 months of 2023.",
        "Germany's GDP was $4.5 trillion in the first 6 months of 2023.",
        "Germany's first-half GDP was $4.5 trillion in 2023.",
        "Germany's half-year GDP was $4.5 trillion in 2023.",
        "Germany's nine-month GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in H1'23.",
        "Germany's GDP was $4.5 trillion quarter on quarter in 2023.",
        "Germany's GDP was $4.5 trillion q/q in 2023.",
        "Germany's GDP was $4.5 trillion at a run rate in 2023.",
        "Germany's GDP was $4.5 trillion at a seasonally adjusted annual rate in 2023.",
        "Over the three months to December, Germany's GDP was $4.5 trillion in 2023.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 4.5e12, metric="gdp", unit="currency", time_period="2023"))
        assert r.match_type == "no_data", sentence
        assert not r.withheld_refute
        assert not r.source_value
    for sentence in (
        "Germany's GDP was $4.5 trillion in 2023, compared with the first half of 2022.",
        "Germany's GDP was $4.5 trillion in 2023 compared with the first half of 2022.",
        "Germany's GDP was $4.5 trillion in 2023 from the first half of 2022.",
        "Germany's GDP was $4.5 trillion in 2023 from the first 6 months of 2022.",
        "In June, Germany's GDP was $4.5 trillion in 2023.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 4.5e12, metric="gdp", unit="currency", time_period="2023"))
        assert r.match_type == "exact", sentence
    # Population is the stock the series counts. A month does not make it another figure.
    r = sn.verify_world_bank(_country(
        "Germany has a population of about 84 million in June 2023.", 84e6))
    assert r.match_type == "exact"
    r = sn.verify_world_bank(_country(
        "Germany has a population of about 84 million in the first half of 2023.", 84e6))
    assert r.match_type == "no_data"
    assert not r.source_value


def test_real_gdp_in_dollars_is_not_the_current_price_series(world_bank):
    for sentence in (
        "Germany's real GDP was $4.5 trillion in 2023.",
        "Germany's GDP in real terms was $4.5 trillion in 2023.",
        "Germany's GDP in constant prices was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion, in real terms, in 2023.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 4.5e12, metric="gdp", unit="currency", time_period="2023"))
        assert r.match_type == "no_data", sentence
        assert not r.withheld_refute
        assert not r.source_value
    r = sn.verify_world_bank(_country(
        "Real wages rose in Germany, while GDP was $4.5 trillion in 2023.",
        4.5e12, metric="gdp", unit="currency", time_period="2023"))
    assert r.match_type == "exact"


def test_a_euro_or_purchasing_power_figure_is_not_the_dollar_series(world_bank):
    # The current-dollar series is dollars. A euro figure, and a
    # purchasing-power figure, are other series even when the digits match.
    # A dollar sign on this figure wins over a euro equivalent beside it.
    # "euro area" is a place. The next sentence is not this figure.
    for sentence in (
        "Germany's euro GDP was 4.5 trillion in 2023.",
        "In euro terms, Germany's GDP was 4.5 trillion in 2023.",
        "In euros, Germany's GDP was 4.5 trillion in 2023.",
        "Germany's GDP was EUR 4.5 trillion in 2023.",
        "Germany's GDP was 4.5 trillion, measured in euros, in 2023.",
        "Germany's GDP was 4.5 trillion euros in 2023.",
        "GDP at purchasing power parity was $4.5 trillion in 2023.",
        "PPP GDP was $4.5 trillion in 2023.",
        "In PPP terms, Germany's GDP was $4.5 trillion in 2023.",
        "GDP in international dollars was $4.5 trillion in 2023.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 4.5e12, metric="gdp", unit="currency", time_period="2023"))
        assert r.match_type == "no_data", sentence
        assert not r.withheld_refute
        assert not r.source_value
    for sentence in (
        "Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion (€4.1 trillion) in 2023.",
        "Germany's GDP was $4.5 trillion (about 4.1 trillion euros) in 2023.",
        "Germany's GDP was 4.5 trillion in the euro area in 2023.",
        "Germany's GDP was 4.5 trillion in the eurozone in 2023.",
        "GDP at current prices was $4.5 trillion in 2023.",
        "Germany's nominal GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion, not PPP, in 2023.",
        "Germany's GDP was 4.5 trillion in 2023. In euros, that is a different amount.",
        "Germany's GDP was $4.5 trillion in 2023. In PPP terms, another series was larger.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 4.5e12, metric="gdp", unit="currency", time_period="2023"))
        assert r.match_type == "exact", sentence


def test_per_capita_at_purchasing_power_is_not_current_dollars(monkeypatch):
    def fetch(url, *args, **kwargs):
        if "/indicator/" not in url:
            return [{}, [{"iso2Code": "DE", "name": "Germany"}]]
        assert "NY.GDP.PCAP.CD" in url
        return [{}, [{"value": 52745, "date": "2023"}]]
    monkeypatch.setattr(sn, "_fetch_json", fetch)
    monkeypatch.setattr(sn, "_WB_COUNTRY_CODES", {})
    r = sn.verify_world_bank(_country(
        "GDP per capita at PPP was $52,745 in 2023.", 52745,
        metric="gdp_per_capita", unit="currency", time_period="2023"))
    assert r.match_type == "no_data"
    assert not r.source_value
    r = sn.verify_world_bank(_country(
        "GDP per capita was $52,745 in 2023.", 52745,
        metric="gdp_per_capita", unit="currency", time_period="2023"))
    assert r.match_type == "exact"
    r = sn.verify_world_bank(_country(
        "GDP per capita in 2015 prices was $52,745 in 2023.", 52745,
        metric="gdp_per_capita", unit="currency", time_period="2023"))
    assert r.match_type == "no_data"
    assert not r.source_value
    for sentence in (
        "Disposable income per person was $52,745 in 2023.",
        "GNI per capita was $52,745 in 2023.",
        "Household income per capita was $52,745 in 2023.",
        "GDP per person employed was $52,745 in 2023.",
        "GDP per person in work was $52,745 in 2023.",
        "GDP per person at work was $52,745 in 2023.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 52745, metric="", unit="currency", time_period="2023"))
        assert r.match_type == "no_data", sentence
        assert not r.source_value
    r = sn.verify_world_bank(_country(
        "Income per capita was $52,745 in 2023.", 52745,
        metric="", unit="currency", time_period="2023"))
    assert r.match_type == "exact"
    r = sn.verify_world_bank(_country(
        "GDP per person was $52,745 in 2023.", 52745,
        metric="", unit="currency", time_period="2023"))
    assert r.match_type == "exact"
    r = sn.verify_world_bank(_country(
        "GDP per head was $52,745 in 2023.", 52745,
        metric="", unit="currency", time_period="2023"))
    assert r.match_type == "exact"
    r = sn.verify_world_bank(_country(
        "GDP per inhabitant was $52,745 in 2023.", 52745,
        metric="", unit="currency", time_period="2023"))
    assert r.match_type == "exact"
    r = sn.verify_world_bank(_country(
        "GDP on a per person basis was $52,745 in 2023.", 52745,
        metric="", unit="currency", time_period="2023"))
    assert r.match_type == "exact"
    # The words beside this figure are per capita. A national total in the
    # same sentence keeps its own reading.
    inhabitant = sn.decompose_claim({
        "sentence": "Germany's GDP was $4.5 trillion in 2023, and GDP per inhabitant was $52,745.",
        "numbers": ["$52,745"],
    })
    assert inhabitant.metric == "gdp_per_capita"
    total = sn.decompose_claim({
        "sentence": "Germany's GDP was $4.5 trillion in 2023, and GDP per inhabitant was $52,745.",
        "numbers": ["$4.5 trillion"],
    })
    assert total.metric == "gdp"
    wrong = sn.verify_world_bank(_country(
        "GDP per inhabitant was $4.5 trillion in 2023.", 4.5e12,
        metric="", unit="currency", time_period="2023"))
    assert wrong.match_type not in ("exact", "close")


def test_a_component_of_prices_is_not_headline_inflation(monkeypatch):
    def fetch(url, *args, **kwargs):
        if "/indicator/" not in url:
            return [{}, [{"iso2Code": "DE", "name": "Germany"}]]
        assert "FP.CPI.TOTL.ZG" in url
        return [{}, [{"value": 6.2, "date": "2023"}]]
    monkeypatch.setattr(sn, "_fetch_json", fetch)
    monkeypatch.setattr(sn, "_WB_COUNTRY_CODES", {})
    for sentence in (
        "Food inflation was 6.2% in 2023.",
        "Energy inflation was 6.2% in 2023.",
        "Services inflation was 6.2% in 2023.",
        "Shelter inflation was 6.2% in 2023.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 6.2, metric="", unit="percent", time_period="2023"))
        assert r.match_type == "no_data", sentence
        assert not r.source_value
    for sentence in (
        "Median inflation was 6.2% in 2023.",
        "Trimmed mean inflation was 6.2% in 2023.",
        "Sticky inflation was 6.2% in 2023.",
        "Supercore inflation was 6.2% in 2023.",
        "Harmonised inflation was 6.2% in 2023.",
        "Underlying inflation was 6.2% in 2023.",
        "In the food category, inflation was 6.2% in 2023.",
        "Germany's CPI-W was 6.2% in 2023.",
        "Germany's chained CPI was 6.2% in 2023.",
        "Germany's C-CPI was 6.2% in 2023.",
        "Breakeven inflation was 6.2% in 2023.",
        "CPI for food was 6.2% in 2023.",
        "Inflation in food was 6.2% in 2023.",
        "Inflation for energy was 6.2% in 2023.",
        "Inflation in the services sector was 6.2% in 2023.",
        "Inflation was 6.2% in the services sector in 2023.",
        "Inflation was 6.2% in services in 2023.",
        "Inflation ran at 6.2% for food in 2023.",
        "Consumer prices were 6.2% on energy in 2023.",
        "Inflation was 6.2% in medical care in 2023.",
        "Inflation was 6.2% on energy markets in 2023.",
        "CPI excluding shelter was 6.2% in 2023.",
        "The CPI, excluding shelter, was 6.2% in 2023.",
        "Inflation ex-energy was 6.2% in 2023.",
        "Inflation less shelter was 6.2% in 2023.",
        "CPI less food and energy was 6.2% in 2023.",
        "Core inflation was 6.2% in 2023.",
        "The core rate of inflation was 6.2% in 2023.",
        "Inflation was 6.2% in the past quarter of 2023.",
        "Inflation was 6.2% on the quarter in 2023.",
        "Inflation expectations were 6.2% in 2023.",
        "Expected inflation was 6.2% in 2023.",
        "The expected rate of inflation was 6.2% in 2023.",
        "Inflation was 6.2% month on month in 2023.",
        "Inflation was 6.2% month-on-month in 2023.",
        "Inflation was 6.2% m/m in 2023.",
        "Inflation was 6.2% from the prior month in 2023.",
        "Trailing twelve-month inflation was 6.2% in 2023.",
        "Inflation was 6.2% excluding food in 2023.",
        "CPI was 6.2% ex-shelter in 2023.",
        "Inflation was 6.2% less energy in 2023.",
        "Inflation was 6.2% outside of energy in 2023.",
        "Inflation was 6.2% in the services industry in 2023.",
        "Inflation was 6.2% in the housing market in 2023.",
        "Inflation was 6.2% so far this year in 2023.",
        "Inflation was 6.2% so far in 2023.",
        "Inflation was 6.2% over the past four quarters in 2023.",
        "Inflation was 6.2% on a monthly basis in 2023.",
        "Inflation was 6.2% at a monthly rate in 2023.",
        "Inflation rose 6.2 percentage points in 2023.",
        "Inflation was 6.2 basis points in 2023.",
        "Inflation rose 6.2 ppt in 2023.",
        "Inflation was 6.2% at a monthly pace in 2023.",
        "Inflation was 6.2% at a quarterly pace in 2023.",
        "Inflation was 6.2% on a 3-month basis in 2023.",
        "Inflation was 6.2% so far this calendar year in 2023.",
        "In 2023, inflation was 6.2% in the year so far.",
        "Inflation was 6.2% versus the prior quarter in 2023.",
        "Inflation was 6.2% from the prior quarter in 2023.",
        "Inflation for apparel was 6.2% in 2023.",
        "Inflation for transportation was 6.2% in 2023.",
        "Inflation for gasoline was 6.2% in 2023.",
        "Apparel inflation was 6.2% in 2023.",
        "In the apparel category, inflation was 6.2% in 2023.",
        "In the apparel category, US inflation was 6.2% in 2023.",
        "Working-day adjusted inflation was 6.2% in 2023.",
        "Inflation was 6.2% q-o-q in 2023.",
        "Inflation was 6.2% sequentially in 2023.",
        "Inflation for recreation was 6.2% in 2023.",
        "Recreation inflation was 6.2% in 2023.",
        "In the recreation category, US inflation was 6.2% in 2023.",
        "Inflation for lodging was 6.2% in 2023.",
        "Inflation for communication was 6.2% in 2023.",
        "Inflation for tobacco was 6.2% in 2023.",
        "Inflation for airline fares was 6.2% in 2023.",
        "Inflation for fuel was 6.2% in 2023.",
        "Fuel inflation was 6.2% in 2023.",
        "Inflation for electricity was 6.2% in 2023.",
        "Inflation for utility gas was 6.2% in 2023.",
        "Inflation for household furnishings was 6.2% in 2023.",
        "Inflation for personal care was 6.2% in 2023.",
        "Inflation for alcoholic beverages was 6.2% in 2023.",
        "Inflation was 6.2% in owners' equivalent rent in 2023.",
        "House price inflation was 6.2% in 2023.",
        "Inflation for hospital services was 6.2% in 2023.",
        "Inflation for prescription drugs was 6.2% in 2023.",
        "Inflation for child care was 6.2% in 2023.",
        "Inflation for motor fuel was 6.2% in 2023.",
        "Inflation for used cars was 6.2% in 2023.",
        "Inflation was 6.2% quarter-over-quarter in 2023.",
        "Inflation was 6.2% q-on-q in 2023.",
        "Inflation was 6.2% over the quarter in 2023.",
        "Inflation was 6.2% in this quarter in 2023.",
        "Four-quarter inflation was 6.2% in 2023.",
        "Trading-day adjusted inflation was 6.2% in 2023.",
        "Inflation was 6.2% m-o-m in 2023.",
        "Inflation was 6.2% m.o.m. in 2023.",
        "Inflation was 6.2% quarter to quarter in 2023.",
        "Inflation was 6.2% from quarter to quarter in 2023.",
        "Over the latest quarter, inflation was 6.2% in 2023.",
        "Last quarter, inflation was 6.2% in 2023.",
        "Inflation was 6.2% over the latest quarter in 2023.",
        "Inflation for daycare was 6.2% in 2023.",
        "Inflation for day care was 6.2% in 2023.",
        "Inflation for food away from home was 6.2% in 2023.",
        "Inflation for motor vehicle insurance was 6.2% in 2023.",
        "Inflation for car insurance was 6.2% in 2023.",
        "Inflation for household energy was 6.2% in 2023.",
        "Inflation for fuel oil was 6.2% in 2023.",
        "Fuel oil inflation was 6.2% in 2023.",
        "Inflation for health insurance was 6.2% in 2023.",
        "Inflation for dental services was 6.2% in 2023.",
        "Inflation for physicians' services was 6.2% in 2023.",
        "Inflation for nursing homes was 6.2% in 2023.",
        "Inflation for eyeglasses was 6.2% in 2023.",
        "Inflation for car rental was 6.2% in 2023.",
        "Inflation for motor vehicle maintenance was 6.2% in 2023.",
        "Inflation for sporting goods was 6.2% in 2023.",
        "Inflation for club membership was 6.2% in 2023.",
        "Inflation for window coverings was 6.2% in 2023.",
        "Inflation for floor coverings was 6.2% in 2023.",
        "Inflation for major appliances was 6.2% in 2023.",
        "Inflation for furniture was 6.2% in 2023.",
        "Inflation for internet services was 6.2% in 2023.",
        "Inflation for wireless telephone was 6.2% in 2023.",
        "Inflation for garbage collection was 6.2% in 2023.",
        "Inflation for tenants' rent was 6.2% in 2023.",
        "Inflation for new vehicles was 6.2% in 2023.",
        "Inflation for footwear was 6.2% in 2023.",
        "Inflation for school books was 6.2% in 2023.",
        "Inflation for elder care was 6.2% in 2023.",
        "Inflation for home health care was 6.2% in 2023.",
        "Inflation for funeral expenses was 6.2% in 2023.",
        "Inflation for legal services was 6.2% in 2023.",
        "Inflation for financial services was 6.2% in 2023.",
        "Inflation for haircuts was 6.2% in 2023.",
        "Inflation for housekeeping supplies was 6.2% in 2023.",
        "Inflation for admission to movies was 6.2% in 2023.",
        "Inflation for full service meals was 6.2% in 2023.",
        "Inflation for limited service meals was 6.2% in 2023.",
        "Inflation for nonprescription drugs was 6.2% in 2023.",
        "Inflation for public transportation was 6.2% in 2023.",
        "Inflation for delivery services was 6.2% in 2023.",
        "Inflation for dry cleaning was 6.2% in 2023.",
        "Inflation for parking was 6.2% in 2023.",
        "Inflation for computers was 6.2% in 2023.",
        "Inflation for smartphones was 6.2% in 2023.",
        "Inflation for propane was 6.2% in 2023.",
        "Inflation for postage was 6.2% in 2023.",
        "In the daycare category, inflation was 6.2% in 2023.",
        "SWDA inflation was 6.2% in 2023.",
        "In the financial services category, inflation was 6.2% in 2023.",
        "Hospital inflation was 6.2% in 2023.",
        "Seasonally adjusted inflation was 6.2% in 2023.",
        "Inflation was 6.2% in fiscal 2023.",
        "Inflation was 6.2% in 2023, excluding shelter.",
        "The seasonally adjusted path of inflation was 6.2% in 2023.",
        "The seasonally adjusted trajectory of inflation was 6.2% in 2023.",
        "In the hospital category, inflation was 6.2% in 2023.",
        "Inflation for the hospital was 6.2% in 2023.",
        "Inflation was 6.2% in 2023, excluding energy from the total.",
        "Inflation was 6.2% in 2023, net of energy.",
        "Inflation was 6.2% excluding energy from the total in 2023.",
        "Inflation was 6.2% net of energy in 2023.",
        "Inflation was 6.2%, excluding energy from the total in 2023.",
        "Inflation was 6.2% in the hospital category in 2023.",
        "Inflation was 6.2% in hospital category in 2023.",
        "The seasonally adjusted reading of inflation was 6.2% in 2023.",
        "The seasonally adjusted version of inflation was 6.2% in 2023.",
        "The seasonally adjusted print of inflation was 6.2% in 2023.",
        "Inflation was 6.2% in 2023, in the hospital category.",
        "Inflation was 6.2%, in the hospital category in 2023.",
        "Inflation was 6.2% in 2023, for the hospital.",
        "Inflation was 6.2% in 2023, on the seasonally adjusted reading.",
        "In the hospital category in 2023, inflation was 6.2%.",
        "For the hospital, inflation was 6.2% in 2023.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 6.2, metric="", unit="percent", time_period="2023"))
        assert r.match_type == "no_data", sentence
        assert not r.source_value
    for sentence in (
        "Inflation was 6.2% in 2023.",
        "Consumer prices rose 6.2% in 2023.",
        "Headline inflation was 6.2% in 2023.",
        "Inflation was 6.2% in 2023, driven by food and energy.",
        "Consumer prices, including food and energy, rose 6.2% in 2023.",
        "Inflation was sticky at 6.2% in 2023.",
        "The underlying story of inflation was 6.2% in 2023.",
        "After food shortages, inflation was 6.2% in 2023.",
        "Food prices rose, while inflation was 6.2% in 2023.",
        "Inflation was 6.2% at an annual rate in 2023.",
        "Inflation was 6.2% in 2023, as expected.",
        "The expected path of inflation was 6.2% in 2023.",
        "CPI for all items was 6.2% in 2023.",
        "Inflation was 6.2% in 2023, up from the prior month.",
        "Inflation was 6.2% in 2023, compared with the month before.",
        "Food inflation was 4.1% in 2023, while headline inflation was 6.2%.",
        "The core of the story is that inflation was 6.2% in 2023.",
        "Inflation was 6.2% in the services report in 2023.",
        "Inflation was 6.2% in a services-led expansion in 2023.",
        "Inflation was 6.2% in service of a soft landing in 2023.",
        "Inflation was 6.2% over the past year in 2023.",
        "Inflation was 6.2% over the year in 2023.",
        "Inflation was 6.2% in the monthly report in 2023.",
        "Inflation was 6.2% in the housing report in 2023.",
        "The story so far this year is that inflation was 6.2% in 2023.",
        "So far this year, the ministry said inflation was 6.2% in 2023.",
        "He spoke on a monthly basis, and inflation was 6.2% in 2023.",
        "Inflation was 6.2% excluding the effects of a strike in 2023.",
        "Inflation was 6.2% (up 0.2 percentage points) in 2023.",
        "The story so far this calendar year is that inflation was 6.2% in 2023.",
        "In the year so far, the ministry said inflation was 6.2% in 2023.",
        "Inflation was 6.2% in the quarterly report in 2023.",
        "Inflation was 6.2% in the q-o-q report in 2023.",
        "Inflation in fact was 6.2% in 2023.",
        "In the education ministry, inflation was 6.2% in 2023.",
        "Calendar-year inflation was 6.2% in 2023.",
        "Inflation was 6.2% in 2023 versus 8.0% in the prior quarter.",
        "The sequential story is that inflation was 6.2% in 2023.",
        "Inflation was 6.2% in the recreation of a trend in 2023.",
        "Inflation was 6.2% in the recreation report in 2023.",
        "Recreation rose, while inflation was 6.2% in 2023.",
        "Inflation was 6.2% after lodging a complaint in 2023.",
        "Inflation was 6.2% in communication with the Fed in 2023.",
        "In communication with the Fed, inflation was 6.2% in 2023.",
        "Inflation was 6.2% in the tobacco report in 2023.",
        "The airline said inflation was 6.2% in 2023.",
        "Inflation was the fuel for the move at 6.2% in 2023.",
        "In the electricity report, inflation was 6.2% in 2023.",
        "Inflation was 6.2% in the hospital in 2023.",
        "House prices rose, while inflation was 6.2% in 2023.",
        "Inflation was 6.2% in this quarter's report in 2023.",
        "In the four-quarter report, inflation was 6.2% in 2023.",
        "The four-quarter story is that inflation was 6.2% in 2023.",
        "Talks over the quarter left inflation at 6.2% in 2023.",
        "Mom said inflation was 6.2% in 2023.",
        "Not seasonally adjusted inflation was 6.2% in 2023.",
        "Inflation was 6.2% in 2023, not seasonally adjusted.",
        "The information was that inflation was 6.2% in 2023.",
        "Hotels said inflation was 6.2% in 2023.",
        "The gas works said inflation was 6.2% in 2023.",
        "Inflation was 6.2% in the furniture of the argument in 2023.",
        "Daycare rose, while inflation was 6.2% in 2023.",
        "Inflation was 6.2% in the daycare report in 2023.",
        "Furniture rose, while inflation was 6.2% in 2023.",
        "After parking a complaint, inflation was 6.2% in 2023.",
        "Financial services rose, while inflation was 6.2% in 2023.",
        "The SWDA conference said inflation was 6.2% in 2023.",
        "Inflation was 6.2% in 2023 compared with the fourth quarter of 2022.",
        "Last quarter, the ministry said inflation was 6.2% in 2023.",
        "Growth over the last quarter century left inflation at 6.2% in 2023.",
        "The seasonally adjusted story is that inflation was 6.2% in 2023.",
        "Seasonally adjusted figures aside, inflation was 6.2% in 2023.",
        "In the financial services report, inflation was 6.2% in 2023.",
        "After the fiscal crisis, inflation was 6.2% in 2023.",
        "The seasonally adjusted path of the story is that inflation was 6.2% in 2023.",
        "The seasonally adjusted trajectory of the story is that inflation was 6.2% in 2023.",
        "In the hospital, inflation was 6.2% in 2023.",
        "Inflation for the hospital report was 6.2% in 2023.",
        "Inflation for the hospital's board was 6.2% in 2023.",
        "In the information category of the census, inflation was 6.2% in 2023.",
        "The seasonally adjusted reading of the story is that inflation was 6.2% in 2023.",
        "The seasonally adjusted print of the story is that inflation was 6.2% in 2023.",
        "A seasonally adjusted reading showed that inflation was 6.2% in 2023.",
        "Inflation was 6.2% in the hospital category of the census in 2023.",
        "Inflation was 6.2% in the gas sector of the economy in 2023.",
        "Inflation was 6.2% net of energy in the report in 2023.",
        "Inflation was 6.2% in 2023 (net of energy in the report).",
        "Inflation was 6.2% in 2023, for the hospital report.",
        "Inflation was 6.2% in 2023, the seasonally adjusted story.",
        "Inflation was 6.2% in 2023, before the seasonally adjusted revision.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 6.2, metric="", unit="percent", time_period="2023"))
        assert r.match_type == "exact", sentence
    # A component figure does not silence the headline figure beside it.
    both = "Food inflation was 4.1% in 2023, while headline inflation was 6.2%."
    food = sn.verify_world_bank(_country(
        both, 4.1, metric="", unit="percent", time_period="2023"))
    headline = sn.verify_world_bank(_country(
        both, 6.2, metric="", unit="percent", time_period="2023"))
    assert food.match_type == "no_data"
    assert not food.source_value
    assert headline.match_type == "exact"


def test_a_foreign_unit_or_subset_is_not_headline_gdp(world_bank):
    # Pounds, a dollar-sign prefix, a constant-price year, basic prices,
    # and a subset are other series. US$, market prices, and the same
    # year's prices stay the current-dollar total.
    for sentence in (
        "Germany's GDP was 4.5 trillion pounds in 2023.",
        "Sterling GDP was 4.5 trillion in 2023.",
        "Germany's GDP in sterling was 4.5 trillion in 2023.",
        "Germany's GDP was 4.5 trillion Canadian dollars in 2023.",
        "Germany's GDP was 4.5 trillion Australian dollars in 2023.",
        "Germany's GDP was C$4.5 trillion in 2023.",
        "Germany's GDP was A$4.5 trillion in 2023.",
        "Germany's GDP was HK$4.5 trillion in 2023.",
        "Germany's GDP was Can$4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in local currency in 2023.",
        "In local currency, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's non-oil GDP was $4.5 trillion in 2023.",
        "Germany's private-sector GDP was $4.5 trillion in 2023.",
        "Germany's manufacturing GDP was $4.5 trillion in 2023.",
        "Germany's industrial GDP was $4.5 trillion in 2023.",
        "Germany's oil GDP was $4.5 trillion in 2023.",
        "Germany's private GDP was $4.5 trillion in 2023.",
        "Germany's services GDP was $4.5 trillion in 2023.",
        "Germany's construction GDP was $4.5 trillion in 2023.",
        "Germany's agriculture GDP was $4.5 trillion in 2023.",
        "Germany's mining GDP was $4.5 trillion in 2023.",
        "Potential GDP was $4.5 trillion in Germany in 2023.",
        "Germany's GDP at basic prices was $4.5 trillion in 2023.",
        "Germany's GDP at basic price was $4.5 trillion in 2023.",
        "Germany's GDP at factor cost was $4.5 trillion in 2023.",
        "Germany's GDP at producer prices was $4.5 trillion in 2023.",
        "Germany's GDP at producers' prices was $4.5 trillion in 2023.",
        "Germany's GDP in 2015 prices was $4.5 trillion in 2023.",
        "Germany's GDP in 2017 dollars was $4.5 trillion in 2023.",
        "Germany's GDP in constant 2015 prices was $4.5 trillion in 2023.",
        "Germany's GDP in constant 2015 dollars was $4.5 trillion in 2023.",
        "Germany's GDP in chained 2017 dollars was $4.5 trillion in 2023.",
        "Germany's GDP in 2017 US dollars was $4.5 trillion in 2023.",
        "In 2015 prices, Germany's GDP was $4.5 trillion in 2023.",
        "In constant 2015 prices, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in the month in 2023.",
        "Germany's GDP was $4.5 trillion for the week in 2023.",
        "Germany's GDP was $4.5 trillion at an annual rate in 2023.",
        "Germany's GDP was $4.5 trillion in the quarter in 2023.",
        "Germany's GDP for the quarter was $4.5 trillion in 2023.",
        "During the quarter, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion SAAR in 2023.",
        "Germany's GDP in manufacturing was $4.5 trillion in 2023.",
        "Germany's GDP from oil was $4.5 trillion in 2023.",
        "Germany's GDP of the manufacturing sector was $4.5 trillion in 2023.",
        "Germany's GDP for the services sector was $4.5 trillion in 2023.",
        "Manufacturing's contribution to GDP was $4.5 trillion in Germany in 2023.",
        "Germany's nonfarm business GDP was $4.5 trillion in 2023.",
        "Germany's market-sector GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in domestic currency in 2023.",
        "Germany's GDP was $4.5 trillion in local-currency terms in 2023.",
        "Germany's GDP was $4.5 trillion (2015 prices) in 2023.",
        "Germany's GDP at prices of 2015 was $4.5 trillion in 2023.",
        "Germany's GDP in 2017 USD was $4.5 trillion in 2023.",
        "Germany's GDP in real 2015 dollars was $4.5 trillion in 2023.",
        "Germany's GDP in chained (2017) dollars was $4.5 trillion in 2023.",
        "Germany's GDP in chained-2017 dollars was $4.5 trillion in 2023.",
        "On a 2015 basis, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in 2023, reference year 2015.",
        "Germany's GDP was $4.5 trillion at previous year's prices in 2023.",
        "Germany's GDP was $4.5 trillion at last year's prices in 2023.",
        "Germany's GDP was $4.5 trillion in chain-linked volumes in 2023.",
        "Trailing twelve-month GDP in Germany was $4.5 trillion in 2023.",
        "Germany's GDP excluding agriculture was $4.5 trillion in 2023.",
        "Excluding agriculture, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP excluding oil was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in the past quarter of 2023.",
        "Germany's GDP was $4.5 trillion on the quarter in 2023.",
        "In the past quarter, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion excluding agriculture in 2023.",
        "Germany's GDP was $4.5 trillion (excluding agriculture) in 2023.",
        "Germany's GDP was $4.5 trillion other than oil in 2023.",
        "Germany's GDP was $4.5 trillion with agriculture excluded in 2023.",
        "Agriculture excluded, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP ex agriculture was $4.5 trillion in 2023.",
        "Germany's GDP rose by $4.5 trillion in 2023.",
        "Germany's GDP increased by $4.5 trillion in 2023.",
        "Germany's GDP was up by $4.5 trillion in 2023.",
        "Germany saw an increase of $4.5 trillion in GDP in 2023.",
        "Working-day adjusted German GDP was $4.5 trillion in 2023.",
        "Calendar-adjusted GDP in Germany was $4.5 trillion in 2023.",
        "Germany's GDP per worker was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion over the past four quarters in 2023.",
        "Germany's GDP was $4.5 trillion so far this year in 2023.",
        "In the past four quarters, Germany's GDP was $4.5 trillion in 2023.",
        "So far this year, Germany's GDP was $4.5 trillion in 2023.",
        "On a monthly basis, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP rose $4.5 trillion in 2023.",
        "Germany's GDP climbed about $4.5 trillion in 2023.",
        "Germany's GDP was up $4.5 trillion in 2023.",
        "Germany's GDP was higher by $4.5 trillion in 2023.",
        "Germany saw a $4.5 trillion increase in GDP in 2023.",
        "Germany's GDP for each worker was $4.5 trillion in 2023.",
        "Germany's GDP per filled job was $4.5 trillion in 2023.",
        "Germany's GDP per FTE was $4.5 trillion in 2023.",
        "Germany's GDP adjusted for working days was $4.5 trillion in 2023.",
        "Calendar and seasonally adjusted German GDP was $4.5 trillion in 2023.",
        "Trailing four quarters, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP jumped $4.5 trillion in 2023.",
        "Germany's GDP jumped by $4.5 trillion in 2023.",
        "Germany's GDP recorded a jump of $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion higher in 2023.",
        "Germany's GDP was $4.5 trillion more in 2023.",
        "Germany saw a $4.5 trillion surge in GDP in 2023.",
        "Germany's per-worker GDP was $4.5 trillion in 2023.",
        "Germany's GDP for every worker was $4.5 trillion in 2023.",
        "Germany's GDP per full-time equivalent was $4.5 trillion in 2023.",
        "On a per-worker basis, Germany's GDP was $4.5 trillion in 2023.",
        "Trading-day adjusted German GDP was $4.5 trillion in 2023.",
        "Germany's GDP adjusted for trading days was $4.5 trillion in 2023.",
        "Trading day and seasonally adjusted German GDP was $4.5 trillion in 2023.",
        "Germany's gross domestic income was $4.5 trillion in 2023.",
        "Germany's household consumption GDP was $4.5 trillion in 2023.",
        "Germany's government GDP was $4.5 trillion in 2023.",
        "Germany's GDP for private consumption was $4.5 trillion in 2023.",
        "Germany's GDP eased by $4.5 trillion in 2023.",
        "Germany's GDP was cut by $4.5 trillion in 2023.",
        "Germany's GDP was revised up by $4.5 trillion in 2023.",
        "Germany's GDP swelled $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion saar in 2023.",
        "Not seasonally adjusted German GDP was $4.5 trillion in 2023.",
        "Germany's SWDA GDP was $4.5 trillion in 2023.",
        "WDA German GDP was $4.5 trillion in 2023.",
        "Germany's GDP for each person employed was $4.5 trillion in 2023.",
        "Germany's GDP in fiscal 2023 was $4.5 trillion.",
        "In FY2023, Germany's GDP was $4.5 trillion.",
        "Germany's GDP was $4.5 trillion in 2023, net of agriculture.",
        "Germany's GDP was $4.5 trillion in 2023, excluding agriculture from the total.",
        "Germany's GDP was $4.5 trillion in 2023, net of agriculture from the total.",
        "Germany's GDP was $4.5 trillion in 2023, ex agriculture from the headline.",
        "Net of oil, Germany's GDP was $4.5 trillion in 2023.",
        "Net of oil in 2023, Germany's GDP was $4.5 trillion.",
        "Germany's GDP was $4.5 trillion excluding food from the total in 2023.",
        "Germany's GDP was $4.5 trillion, net of oil in 2023.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 4.5e12, metric="gdp", unit="currency", time_period="2023"))
        assert r.match_type == "no_data", sentence
        assert not r.withheld_refute
        assert not r.source_value
    r = sn.verify_world_bank(_country(
        "Germany's GDP in 2017 dollars was $4.5 trillion.", 4.5e12,
        metric="gdp", unit="currency"))
    assert r.match_type == "no_data"
    assert not r.source_value
    for sentence in (
        "Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was US$4.5 trillion in 2023.",
        "Germany's GDP was 4.5 trillion, in pounds of wheat, in 2023.",
        "A sterling result, and Germany's GDP was 4.5 trillion in 2023.",
        "Germany's GDP at market prices was $4.5 trillion in 2023.",
        "Germany's GDP at purchaser's prices was $4.5 trillion in 2023.",
        "Germany's GDP at 2023 prices was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion, not at basic prices, in 2023.",
        "Germany's GDP was $4.5 trillion, not at producer prices, in 2023.",
        "Manufacturing rose, while Germany's GDP was $4.5 trillion in 2023.",
        "Non-oil revenue rose, while Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in 2023 compared with the month before.",
        "Germany posted a potential record, and GDP was $4.5 trillion in 2023.",
        "After the quarter, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in 2023 compared with the quarter before.",
        "Germany's GDP was $4.5 trillion in the quarter before.",
        "Germany's GDP in Saar was $4.5 trillion in 2023.",
        "In the domestic currency market, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in 2023 in the manufacturing report.",
        "Germany's GDP was $4.5 trillion in 2023 in oil-importing terms.",
        "Germany's GDP was $4.5 trillion in 2023 for private investors.",
        "Germany's GDP was $4.5 trillion in 2023 in service of a longer expansion.",
        "Germany's GDP was $4.5 trillion in 2023, compared with last year's prices.",
        "Germany's GDP was $4.5 trillion in 2015 on a 2015 basis.",
        "Germany's GDP was $4.5 trillion in the reference year 2023.",
        "Nonfarm payrolls rose, while Germany's GDP was $4.5 trillion in 2023.",
        "Germany's full-year GDP was $4.5 trillion in 2023.",
        "Germany's calendar-year GDP was $4.5 trillion in 2023.",
        "Not excluding agriculture, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP not excluding agriculture was $4.5 trillion in 2023.",
        "In the past quarter of 2023, Germany's full-year GDP was $4.5 trillion.",
        "Growth over the last quarter century left Germany's GDP at $4.5 trillion in 2023.",
        "Germany's GDP rose to $4.5 trillion in 2023.",
        "The ex-president said Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion excluding the effects of a strike in 2023.",
        "The story so far is that Germany's GDP was $4.5 trillion in 2023.",
        "The story so far this year is that Germany's GDP was $4.5 trillion in 2023.",
        "So far this year, the ministry said Germany's GDP was $4.5 trillion in 2023.",
        "After four quarters of expansion, Germany's GDP was $4.5 trillion in 2023.",
        "Talks over the past four quarters left Germany's GDP at $4.5 trillion in 2023.",
        "Outside of the energy ministry, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion, up by $200 billion, in 2023.",
        "In the past four quarters, Germany's full-year GDP was $4.5 trillion.",
        "So far this year, Germany's full-year GDP was $4.5 trillion.",
        "Per worker productivity aside, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP climbed to $4.5 trillion in 2023.",
        "Germany's GDP was up to $4.5 trillion in 2023.",
        "Germany's GDP increased to $4.5 trillion in 2023.",
        "The estimate was backed up by Germany's GDP of $4.5 trillion in 2023.",
        "Seasonally adjusted figures aside, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP jumped to $4.5 trillion in 2023.",
        "Germany's GDP surged to about $4.5 trillion in 2023.",
        "Germany's GDP edged up to $4.5 trillion in 2023.",
        "Germany's GDP contracted to $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion more or less in 2023.",
        "Germany's GDP was $4.5 trillion higher than France's in 2023.",
        "Germany's GDP was $4.5 trillion more than France's in 2023.",
        "The report shed light on Germany's GDP of $4.5 trillion in 2023.",
        "The trading day was long, and Germany's GDP was $4.5 trillion in 2023.",
        "Trading-day adjusted figures aside, Germany's GDP was $4.5 trillion in 2023.",
        "On the trading day, Germany's GDP was $4.5 trillion in 2023.",
        "For every worker who asked, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's gross domestic product was $4.5 trillion in 2023.",
        "The GDI conference said Germany's GDP was $4.5 trillion in 2023.",
        "The German government's GDP was $4.5 trillion in 2023.",
        "The government said Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP eased to $4.5 trillion in 2023.",
        "Germany's GDP was revised to $4.5 trillion in 2023.",
        "The figures were revised, and Germany's GDP was $4.5 trillion in 2023.",
        "The estimate was revised by Germany's GDP of $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in 2023, not seasonally adjusted.",
        "Not seasonally adjusted, the ministry said Germany's GDP was $4.5 trillion in 2023.",
        "The SWDA conference said Germany's GDP was $4.5 trillion in 2023.",
        "For each person who asked, Germany's GDP was $4.5 trillion in 2023.",
        "Under the FY2024 framework, Germany's GDP was $4.5 trillion in 2023.",
        "After the fiscal crisis, Germany's GDP was $4.5 trillion in 2023.",
        "FYI, Germany's GDP was $4.5 trillion in 2023.",
        "In the FY2023 report, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in 2023, outside of the energy ministry.",
        "Germany's GDP was $4.5 trillion in 2023, net of tax.",
        "Germany's GDP was $4.5 trillion in 2023, net of the energy ministry.",
        "Germany's GDP was $4.5 trillion in 2023, excluding agriculture from the total economy.",
        "Germany's GDP was $4.5 trillion in 2023, excluding agriculture from Germany.",
        "Not excluding agriculture from the total, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion in 2023, less than the total.",
        "Germany's GDP was $4.5 trillion in 2023, excluding food from the total economy.",
        "Net of tax, Germany's GDP was $4.5 trillion in 2023.",
        "Germany's GDP was $4.5 trillion, net of oil in the report.",
        "Germany's GDP was $4.5 trillion in the hospital category in 2023.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 4.5e12, metric="gdp", unit="currency", time_period="2023"))
        assert r.match_type == "exact", sentence
    # The United States is the country whose local currency is the dollar series.
    us = _decomp(
        "United States GDP was $4.5 trillion in local currency in 2023.",
        4.5e12, metric="gdp", unit="currency", subject="United States",
        time_period="2023")
    assert sn._wb_figure_is_not_dollars(us) is False
    grew_claim = _country(
        "Germany's GDP excluding oil grew 5.5% in 2023.", 5.5,
        metric="", unit="percent", time_period="2023")
    assert sn._wb_indicator_for(grew_claim)[0] == "NY.GDP.MKTP.KD.ZG"
    assert sn._exclusion_before_figure(grew_claim)
    grew = sn.verify_world_bank(grew_claim)
    assert grew.match_type == "no_data"
    assert not grew.source_value


def test_a_narrow_labor_rate_is_not_the_total(monkeypatch):
    def fetch(url, *args, **kwargs):
        if "/indicator/" not in url:
            return [{}, [{"iso2Code": "DE", "name": "Germany"}]]
        assert "SL.UEM.TOTL.ZS" in url
        return [{}, [{"value": 5.5, "date": "2023"}]]
    monkeypatch.setattr(sn, "_fetch_json", fetch)
    monkeypatch.setattr(sn, "_WB_COUNTRY_CODES", {})
    for sentence in (
        "Youth unemployment was 5.5% in 2023.",
        "Long-term unemployment was 5.5% in 2023.",
        "Female unemployment was 5.5% in 2023.",
        "U-6 unemployment was 5.5% in 2023.",
        "Unemployment among youth was 5.5% in 2023.",
        "Jobless claims were 5.5% in 2023.",
        "Prime-age unemployment was 5.5% in 2023.",
        "Black unemployment was 5.5% in 2023.",
        "Insured unemployment was 5.5% in 2023.",
        "Unemployment was 5.5% in the month in 2023.",
        "Unemployment was 5.5% for the week in 2023.",
        "Hispanic unemployment was 5.5% in 2023.",
        "Unemployment among Hispanics was 5.5% in 2023.",
        "Asian unemployment was 5.5% in 2023.",
        "White unemployment was 5.5% in 2023.",
        "African American unemployment was 5.5% in 2023.",
        "Unemployment among teenagers was 5.5% in 2023.",
        "Teenagers' unemployment was 5.5% in 2023.",
        "Foreign-born unemployment was 5.5% in 2023.",
        "Unemployment among college graduates was 5.5% in 2023.",
        "Unemployment aged 25 to 54 was 5.5% in 2023.",
        "The 25-54 unemployment rate was 5.5% in 2023.",
        "U-4 unemployment was 5.5% in 2023.",
        "U-1 unemployment was 5.5% in 2023.",
        "Registered unemployment was 5.5% in 2023.",
        "Harmonised unemployment was 5.5% in 2023.",
        "The unemployment rate for Hispanics was 5.5% in 2023.",
        "Unemployment rate among teenagers was 5.5% in 2023.",
        "The unemployment rate for college graduates was 5.5% in 2023.",
        "The jobless rate for Asians was 5.5% in 2023.",
        "Unemployment rate among the foreign-born was 5.5% in 2023.",
        "The unemployment rate aged 25 to 54 was 5.5% in 2023.",
        "Unemployment was 5.5% for Hispanics in 2023.",
        "Unemployment stood at 5.5% for Hispanics in 2023.",
        "Unemployment reached 5.5% for Hispanics in 2023.",
        "Unemployment was 5.5% among teenagers in 2023.",
        "Unemployment was 5.5% for people without a high school diploma in 2023.",
        "Unemployment was 5.5% for workers with a bachelor's degree in 2023.",
        "Unemployment was 5.5% for people with a high school diploma in 2023.",
        "Unemployment was 5.5% for people with some college in 2023.",
        "Unemployment was 5.5% for people with an associate's degree in 2023.",
        "Unemployment was 5.5% for people with a master's degree in 2023.",
        "Unemployment was 5.5% for people with an advanced degree in 2023.",
        "Unemployment was 5.5% aged 16 to 19 in 2023.",
        "Unemployment was 5.5% for part-time workers in 2023.",
        "Unemployment was 5.5% for veterans in 2023.",
        "Unemployment was 5.5% for people with a disability in 2023.",
        "Unemployment was 5.5% for job losers in 2023.",
        "Unemployment was 5.5% for job leavers in 2023.",
        "Unemployment was 5.5% for new entrants in 2023.",
        "Unemployment was 5.5% for reentrants in 2023.",
        "Unemployment was 5.5% for discouraged workers in 2023.",
        "Unemployment was 5.5% for the marginally attached in 2023.",
        "Unemployment was 5.5% for those aged 55 and over in 2023.",
        "Unemployment was 5.5% for people aged 20 and over in 2023.",
        "Unemployment was 5.5% for multiple jobholders in 2023.",
        "Unemployment was 5.5% for the self-employed in 2023.",
        "Unemployment was 5.5% part time for economic reasons in 2023.",
        "Unemployment was 5.5% on temporary layoff in 2023.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 5.5, metric="", unit="percent", time_period="2023"))
        assert r.match_type == "no_data", sentence
        assert not r.source_value
    for sentence in (
        "Unemployment was 5.5% in 2023.",
        "Unemployment was 5.5% in 2023, in the hospital category.",
        "The jobless rate was 5.5% in 2023.",
        "Youth unemployment fell, while unemployment was 5.5% in 2023.",
        "Jobless claims fell, while unemployment was 5.5% in 2023.",
        "The claim that unemployment was 5.5% in 2023.",
        "U-3 unemployment was 5.5% in 2023.",
        "Unemployment was 5.5% in 2023, and men left the labor force.",
        "Black unemployment fell, while unemployment was 5.5% in 2023.",
        "Unemployment was 5.5% in 2023 compared with the month before.",
        "The White House said unemployment was 5.5% in 2023.",
        "After the Asian crisis, unemployment was 5.5% in 2023.",
        "Unemployment for the year was 5.5% in 2023.",
        "The unemployment rate for the year was 5.5% in 2023.",
        "Unemployment stood at 5.5% for the year in 2023.",
        "Unemployment was 5.5% because of the foreign-born influx in 2023.",
        "Unemployment was 5.5%, for Hispanics the rate was higher.",
        "Civilian unemployment was 5.5% in 2023.",
        "Unemployment was 5.5%, and workers with a bachelor's degree saw another rate.",
        "Unemployment was 5.5% in some college towns in 2023.",
        "Unemployment was 5.5% on pages 16 to 19 of the report in 2023.",
        "Unemployment was 5.5% as veterans returned in 2023.",
        "Unemployment was 5.5% in the part-time report in 2023.",
        "Part-time workers aside, unemployment was 5.5% in 2023.",
        "The veterans hospital said unemployment was 5.5% in 2023.",
        "West High School said unemployment was 5.5% in 2023.",
        "Unemployment was 5.5% for people aged 16 and over in 2023.",
        "The 16 years and over unemployment rate was 5.5% in 2023.",
        "Job losers rose, while unemployment was 5.5% in 2023.",
        "Self-employed workers aside, unemployment was 5.5% in 2023.",
    ):
        r = sn.verify_world_bank(_country(
            sentence, 5.5, metric="", unit="percent", time_period="2023"))
        assert r.match_type == "exact", sentence


def test_a_matching_gdp_names_the_country(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany's GDP in 2023 was $4.5 trillion.", 4.5e12,
        metric="gdp", unit="currency", time_period="2023"))
    assert r.match_type == "exact"
    assert r.source_text.startswith("Germany, ")
    assert "GDP" in r.source_text


def test_economic_output_is_still_gdp(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany's economic output in 2023 was $4.5 trillion.", 4.5e12,
        metric="gdp", unit="currency", time_period="2023"))
    assert r.match_type == "exact"


def test_a_sectors_output_equal_to_gdp_is_not_a_tick(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany's manufacturing output in 2023 was $4.5 trillion.", 4.5e12,
        metric="gdp", unit="currency", time_period="2023"))
    assert r.match_type == "no_data"
    assert not r.withheld_refute
    assert not r.source_value


def test_dated_gdp_mismatch_keeps_the_world_bank_figure(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany's GDP in 2023 was $900 billion.", 900e9,
        metric="gdp", unit="currency", time_period="2023"))
    # The World Bank earned refute on v32 (2026-11-28).
    assert r.match_type == "contradicted"
    assert not r.withheld_refute
    assert r.source_value == 4_500_000_000_000


def test_world_bank_answers_area_claims(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany has an area of 357,580 square kilometres.", 357580,
        metric="area", unit="distance"))
    assert r.match_type == "exact"


def test_country_list_is_fetched_once(world_bank):
    for _ in range(2):
        sn.verify_world_bank(_country(
            "Germany has a population of about 84 million.", 84e6))
    assert sum("/indicator/" not in url for url in world_bank) == 1


def test_retired_provider_is_not_routed():
    d = _country("Germany has a population of about 84 million.", 84e6)
    names = [f.__name__ for f in sn._classify_and_route(d)]
    assert "verify_world_bank" in names
    assert "verify_rest_countries" not in names


@pytest.mark.parametrize("sentence,subject,passage", [
    (
        "The United States has a population of 12 million.",
        "United States",
        ("Of the foreign-born population, some 45% (20.7 million) were "
        "naturalized citizens, 27% (12.3 million) were lawful permanent "
        "residents, 6% (2.2 million) were temporary lawful residents."),
    ),
    (
        "Germany has a population of about 12 million.",
        "Germany",
        ("Germany has one of the largest populations in the region and is "
        "home to the second-highest number of international migrants "
        "worldwide, about 5% or 12 million of all 244 million migrants."),
    ),
])
def test_subgroup_figure_is_not_a_population(sentence, subject, passage):
    d = _decomp(sentence, 12e6, metric="population", unit="count",
                subject=subject)
    assert _match_in_text(passage, 12e6, sentence, decomp=d)[0] is None


# ── From the held-out set written blind to this code ────────────────

@pytest.mark.parametrize("sentence,metric", [
    ("Walmart reported total revenues of about $648 billion in 2024.", "revenue"),
    ("Pfizer's profits were about $2 billion in 2023.", "profit"),
    ("The mean diameter of Mars is about 6,779 kilometres.", "diameter"),
])
def test_metric_is_recognised(sentence, metric):
    d = decompose_claim({"sentence": sentence, "numbers": ["1"]})
    assert d.metric == metric


def test_hyphenated_company_name_stays_whole():
    s = "In fiscal 2023, Coca-Cola's net operating revenues came to $45.8 billion."
    assert sn.extract_subject("", s) == "Coca-Cola"


def test_company_lookup_prefers_the_company_named(monkeypatch):
    titles = {
        "COCA-COLA EUROPACIFIC PARTNERS PLC": ("0001650107", "CCEP"),
        "COCA COLA CO": ("0000021344", "KO"),
    }
    monkeypatch.setattr(sn, "_get_sec_tickers", lambda: (titles, {}))
    assert sn._find_cik("Coca-Cola")[1] == "KO"


def test_a_diameter_is_not_an_orbit_in_the_next_clause():
    sentence = "The mean diameter of Mars is about 9,400 kilometres."
    passage = (
        "Mars has two moons, Phobos (about 22 km in diameter) and Deimos "
        "(about 12 km (7.5 mi) in diameter), which orbit at 9,376 km "
        "(5,826 mi) and 23,460 km (14,580 mi) around the planet."
    )
    d = _decomp(sentence, 9400, metric="diameter", unit="distance",
                subject="Mars")
    assert _match_in_text(passage, 9400, sentence, decomp=d)[0] is None


def test_a_stated_diameter_still_matches():
    sentence = "The mean diameter of Mars is about 6,779 kilometres."
    passage = "Mars has a mean diameter of 6,779 km, about half of Earth's."
    d = _decomp(sentence, 6779, metric="diameter", unit="distance",
                subject="Mars")
    assert _match_in_text(passage, 6779, sentence, decomp=d)[0] is not None


@pytest.mark.parametrize("raw,expected", [
    ("83 years", 83.0),
    ("5 months", 5.0),
    ("1.5 days", 1.5),
])
def test_a_duration_keeps_its_value(raw, expected):
    assert sn.normalize_value(raw, "") == expected


def test_life_expectancy_claims_reach_the_world_bank(monkeypatch):
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: (
        [{}, [{"value": 66.1, "date": "2023"}]] if "/indicator/" in url
        else [{}, [{"iso2Code": "ZA", "name": "South Africa"}]]
    ))
    monkeypatch.setattr(sn, "_WB_COUNTRY_CODES", {})
    text = "Life expectancy at birth in South Africa was about 78 years in 2023."
    d = decompose_claim(analyze_claims(text)["claims"][0], doc_text=text)
    assert d.value == 78.0
    r = sn.verify_world_bank(d)
    # The World Bank earned refute on v32 (2026-11-28).
    assert r.match_type == "contradicted"
    assert not r.withheld_refute
    assert r.source_value == 66.1


def test_british_spelling_is_an_area():
    d = decompose_claim({
        "sentence": "Argentina spans about 3.5 million square kilometres.",
        "numbers": ["3.5 million"],
    })
    assert d.metric == "area"
    assert "verify_world_bank" in [
        f.__name__ for f in sn._classify_and_route(d)
    ]


def test_a_sentence_naming_two_years_cannot_contradict(apple_sec):
    """From the second blind set. "Swung from a loss in fiscal 2023 to a
    profit in fiscal 2024" compared the second figure to the first year."""
    r = verify_sec_edgar(_decomp(
        "Apple grew after a weak fiscal 2022, with revenue of $420 billion "
        "in fiscal 2023.", 420e9, metric="revenue",
    ))
    assert r.match_type == "no_data"


def test_one_year_named_twice_keeps_the_filed_figure(apple_sec):
    r = verify_sec_edgar(_decomp(
        "In fiscal 2023 Apple's revenue was $420 billion, its fiscal 2023 "
        "report said.", 420e9, metric="revenue",
    ))
    _held_filing(r)


# ── Second review: entity, period, scale ────────────────────────────

@pytest.mark.parametrize("token,source,expected", [
    ("$12,500,000", "Revenue was $12,500,000,000 in 2023.", False),
    ("$12.5 trillion", "Revenue was $12.5 thousand.", False),
    ("$12.5 million", "Revenue was $12.5 million.", True),
    ("$5,000", "The fee was $5,000, paid in full.", True),
])
def test_needles_stop_at_the_end_of_the_number(token, source, expected):
    assert number_token_in_source(token, source) is expected


def _titles(monkeypatch, *rows):
    monkeypatch.setattr(sn, "_get_sec_tickers", lambda: (
        {title: (str(i), ticker) for i, (title, ticker) in enumerate(rows)},
        {},
    ))


def test_lookup_keeps_sec_file_order_not_shortest_title(monkeypatch):
    """SEC lists by market value. Shortest-title sent Honeywell to a spinoff."""
    _titles(monkeypatch, ("HONEYWELL INTERNATIONAL INC", "HON"),
            ("HONEYWELL AERO", "HONA"))
    assert sn._find_cik("Honeywell")[1] == "HON"


def test_lookup_matches_whole_words_only(monkeypatch):
    _titles(monkeypatch, ("OXFORD INDUSTRIES INC", "OXM"),
            ("METALS CO", "MTL"), ("FORD MOTOR CO", "F"),
            ("META PLATFORMS INC", "META"))
    assert sn._find_cik("Ford")[1] == "F"
    assert sn._find_cik("Meta")[1] == "META"


@pytest.mark.parametrize("sentence,subject", [
    (("For fiscal 2024, which ended in September, Visa earned net income of "
     "$19.7 billion."), "Visa"),
    ("Chipotle Mexican Grill's fiscal 2024 revenue totaled $11.3 billion.",
     "Chipotle Mexican Grill"),
    ("The Statue of Liberty stands about 93 metres tall.", "Statue of Liberty"),
    ("According to its report, UnitedHealth Group's revenue was $400 billion.",
     "UnitedHealth Group"),
    ("Angel Falls in Venezuela has a total height of 979 meters.", "Angel Falls"),
    ("Life expectancy at birth in Italy was about 83 years.", "Italy"),
    ("The population of Japan is about 125 million.", "Japan"),
    ("Germany's GDP was about $4 trillion.", "Germany"),
])
def test_subject_is_who_the_sentence_is_about(sentence, subject):
    assert sn.extract_subject("", sentence) == subject


def _sec_rows(monkeypatch, rows):
    monkeypatch.setattr(sn, "_find_cik", lambda s: ("1", "TGT"))
    body = json.dumps({"units": {"USD": rows}}).encode()
    monkeypatch.setattr(
        sn, "_urlopen_with_deadline", lambda req, per_op_timeout=8: body,
    )


def _row(end, fy, val, start=None):
    row = {"form": "10-K", "fp": "FY", "end": end, "fy": fy,
           "filed": f"{end[:4]}-03-01", "val": val}
    if start:
        row["start"] = start
    return row


TARGET = [
    _row("2023-01-28", 2022, 109_100_000_000, "2022-01-30"),
    _row("2023-01-28", 2023, 109_100_000_000, "2022-01-30"),
    _row("2024-02-03", 2023, 107_400_000_000, "2023-01-29"),
]


def test_fiscal_year_follows_the_filing_not_the_end_date(monkeypatch):
    """Target's fiscal 2023 ended in February 2024. Matching by end year
    compared the claim with fiscal 2022 and contradicted a true figure."""
    _sec_rows(monkeypatch, TARGET)
    r = verify_sec_edgar(_decomp(
        "Target's revenue for fiscal 2023 was $107.4 billion.", 107.4e9,
        metric="revenue", subject="Target", time_period="2023"))
    assert r.match_type == "exact"
    assert "FY2023" in r.source_text


TARGET_DATED = [
    _row("2024-02-03", 2023, 107_400_000_000, "2023-01-29"),
    _row("2024-02-03", 2024, 107_400_000_000, "2023-01-29"),
    _row("2025-02-01", 2024, 106_600_000_000, "2024-02-04"),
]
TARGET_LINE = "Target, whose fiscal 2024 ended February 1, 2025, had net sales of {}."


def _dated(figure, value):
    d = decompose_claim({"sentence": TARGET_LINE.format(figure), "numbers": [figure]})
    d.subject, d.metric, d.value = "Target", "revenue", value
    return d


def test_a_fiscal_year_the_text_dates_is_that_year_only(monkeypatch):
    """v15 x16: "fiscal 2024 ended February 1, 2025" was also read as the year
    ending February 2024, so fiscal 2023's figure confirmed."""
    _sec_rows(monkeypatch, TARGET_DATED)
    d = _dated("$107.4 billion", 107.4e9)
    assert d.fiscal_end == "2024|2025-02-01"
    r = verify_sec_edgar(d)
    assert r.match_type != "exact" and r.source_value == 106_600_000_000


def test_the_dated_fiscal_year_still_matches(monkeypatch):
    _sec_rows(monkeypatch, TARGET_DATED)
    assert verify_sec_edgar(_dated("$106.6 billion", 106.6e9)).match_type == "exact"


def test_a_quarter_inside_a_10k_is_not_the_annual_figure(monkeypatch):
    _sec_rows(monkeypatch, [
        _row("2023-12-31", 2023, 25_000_000_000, "2023-10-01"),
        _row("2023-12-31", 2023, 96_800_000_000, "2023-01-01"),
    ])
    r = _held_filing(verify_sec_edgar(_decomp(
        "Tesla's revenue in 2023 was $25 billion.", 25e9,
        metric="revenue", subject="Tesla", time_period="2023")))
    assert r.source_value == 96_800_000_000


def test_a_net_loss_matches_a_negative_filing(monkeypatch):
    _sec_rows(monkeypatch, [_row("2024-12-28", 2024, -18_800_000_000,
                                 "2023-12-31")])
    d = decompose_claim(
        {"sentence": "Intel posted a net loss of $18.8 billion in fiscal 2024.",
         "numbers": ["$18.8 billion"]})
    assert d.metric == "profit"
    assert verify_sec_edgar(d).match_type == "exact"


def test_fred_is_only_asked_about_the_united_states(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "x")
    spain = _decomp("Spain's unemployment rate averaged 11.4% in 2024.", 11.4,
                    unit="percent", subject="Spain")
    us = _decomp("The US unemployment rate was 3.7% in 2023.", 3.7,
                 unit="percent", subject="United States")
    assert "verify_fred" not in [f.__name__ for f in sn._classify_and_route(spain)]
    assert "verify_fred" in [f.__name__ for f in sn._classify_and_route(us)]


@pytest.mark.parametrize("sentence", [
    "Germany was home to about 90 million people in 2024.",
    "About 90 million people lived in Germany in 2024.",
])
def test_a_country_total_needs_no_word_population(world_bank, sentence):
    r = sn.verify_world_bank(_country(sentence, 90e6))
    # The World Bank earned refute on v32 (2026-11-28).
    assert r.match_type == "contradicted"
    assert not r.withheld_refute
    assert r.source_value == 83_491_249


def test_tallest_is_evidence_of_height():
    sentence = "Mount Fuji rises to an elevation of 3,776 meters."
    passage = "It is the tallest mountain in Japan, standing 3,776.24 m."
    d = _decomp(sentence, 3776, metric="height", unit="distance",
                subject="Mount Fuji")
    assert _match_in_text(passage, 3776, sentence, decomp=d)[0] is not None


# ── From the independent review ─────────────────────────────────────

@pytest.mark.parametrize("sentence,value,metric,unit", [
    ("NVIDIA's revenue grew 126% in FY2024.", 126, "revenue", "percent"),
    ("Earnings per share rose to $5.20 in FY2023.", 5.2, "profit", "currency"),
    ("Apple's gross profit was $169 billion in fiscal 2023.", 169e9, "profit",
     "currency"),
    ("Apple's operating profit was $114 billion in fiscal 2023.", 114e9,
     "profit", "currency"),
    ("Apple's EBITDA was $125 billion in fiscal 2023.", 125e9, "profit",
     "currency"),
    ("Apple's cost of revenue was $214 billion in fiscal 2023.", 214e9,
     "operating_expenses", "currency"),
])
def test_sec_only_compares_the_figure_it_holds(apple_sec, sentence, value,
                                               metric, unit):
    r = verify_sec_edgar(_decomp(
        sentence, value, metric=metric, unit=unit, time_period="2023",
    ))
    assert r.match_type == "no_data"


def test_sec_will_not_use_a_neighbouring_year(apple_sec):
    r = verify_sec_edgar(_decomp(
        "Apple's revenue in fiscal 2021 was $394 billion.", 394e9,
        metric="revenue", time_period="2021",
    ))
    assert r.match_type == "no_data"


def test_quarter_ignores_year_to_date_rows(monkeypatch):
    rows = [
        {"form": "10-Q", "fp": "Q2", "fy": 2023, "end": "2023-06-30",
         "start": "2023-01-01", "filed": "2023-08-01", "val": 50_000_000_000},
        {"form": "10-Q", "fp": "Q2", "fy": 2023, "end": "2023-06-30",
         "start": "2023-04-01", "filed": "2023-08-01", "val": 25_000_000_000},
    ]
    _sec_rows(monkeypatch, rows)
    r = _held_filing(verify_sec_edgar(_decomp(
        "Tesla's Q2 2023 revenue was $50 billion.", 50e9, metric="revenue",
        subject="Tesla", time_period="Q2 2023",
    )))
    assert r.source_value == 25_000_000_000


def test_world_bank_does_not_compare_a_rate_with_a_total(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany's population grew 0.1% in 2023.", 0.1, metric="population",
        unit="percent", time_period="2023",
    ))
    assert r.match_type == "no_data"


def test_gdp_growth_is_compared_with_growth_not_with_gdp(world_bank):
    # Real growth has its own series; the size of the economy is never it.
    sn.verify_world_bank(_country(
        "Germany's GDP grew 0.3% in 2023.", 0.3, metric="gdp",
        unit="percent", time_period="2023",
    ))
    asked = [u.split("/indicator/")[1].split("?")[0] for u in world_bank if "/indicator/" in u]
    assert asked and set(asked) == {"NY.GDP.MKTP.KD.ZG"}


def _georgia_bank(monkeypatch, value=3_700_000):
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: (
        [{}, [{"value": value, "date": "2023"}]] if "/indicator/" in url
        else [{}, [{"iso2Code": "GE", "name": "Georgia"}]]
    ))
    monkeypatch.setattr(sn, "_WB_COUNTRY_CODES", {})


def test_an_ambiguous_place_name_cannot_contradict(monkeypatch):
    _georgia_bank(monkeypatch)
    r = sn.verify_world_bank(_decomp(
        "Georgia's population was 10.9 million in 2023.", 10.9e6,
        metric="population", unit="count", subject="Georgia",
        time_period="2023",
    ))
    assert r.match_type == "no_data"


def test_bare_georgia_matching_the_country_is_not_a_tick(monkeypatch):
    _georgia_bank(monkeypatch)
    r = sn.verify_world_bank(_decomp(
        "Georgia's population was 3.7 million in 2023.", 3.7e6,
        metric="population", unit="count", subject="Georgia",
        time_period="2023",
    ))
    assert r.match_type == "no_data"
    assert not r.withheld_refute
    assert not r.source_value


def test_the_country_of_georgia_still_matches(monkeypatch):
    _georgia_bank(monkeypatch)
    r = sn.verify_world_bank(_decomp(
        "The country of Georgia had a population of 3.7 million in 2023.", 3.7e6,
        metric="population", unit="count", subject="Georgia",
        time_period="2023",
    ))
    assert r.match_type == "exact"
    assert r.source_text.startswith("Georgia, ")


@pytest.mark.parametrize("subject", ["Now", "Key", "One", "All", "Delta", "United"])
def test_ordinary_words_do_not_resolve_to_companies(monkeypatch, subject):
    monkeypatch.setattr(sn, "_get_sec_tickers", lambda: (
        {"DELTA AIR LINES INC": ("1", "DAL"), "UNITED AIRLINES": ("2", "UAL")},
        {"NOW": ("3", "NOW"), "KEY": ("4", "KEY"), "ONE": ("5", "ONE"),
         "ALL": ("6", "ALL")},
    ))
    assert sn._find_cik(subject) == (None, None)


def test_an_uppercase_ticker_still_resolves(monkeypatch):
    monkeypatch.setattr(sn, "_get_sec_tickers", lambda: (
        {}, {"NVDA": ("1", "NVDA")},
    ))
    assert sn._find_cik("NVDA")[1] == "NVDA"


@pytest.mark.parametrize("token,source,expected", [
    ("5%", "Growth was 25% last year.", False),
    ("5%", "Growth was 0.5% last year.", False),
    ("5%", "Growth was 5% last year.", True),
    ("12.5%", "Growth was 12% last year.", False),
    ("500", "We hired 1,500 people.", False),
    ("$5 million", "It costs $5 more.", False),
    ("$5 trillion", "It costs $5 to $7 million.", False),
])
def test_source_match_boundaries(token, source, expected):
    assert number_token_in_source(token, source) is expected


def test_own_sentence_finds_the_whole_number():
    from claim_analysis import _own_sentence
    doc = "Margins rose 25% overall. Fees were 5% this year."
    assert _own_sentence(doc, "5%") == "Fees were 5% this year."


def test_own_sentence_splits_before_a_dollar_figure():
    from claim_analysis import _own_sentence
    doc = "Revenue was flat, nearly. $5 billion went to capex."
    assert _own_sentence(doc, "$5 billion") == "$5 billion went to capex."


def test_an_altitude_about_something_else_is_not_the_subjects_height():
    sentence = "Mount Everest is 12,000 metres tall."
    passage = (
        "The hot-air balloons were modified to function at up to 12,000 m "
        "(40,000 ft) altitude."
    )
    d = _decomp(sentence, 12000, metric="height", unit="distance",
                subject="Mount Everest")
    assert _match_in_text(passage, 12000, sentence, decomp=d)[0] is None


def test_fiscal_label_conventions_differ_so_either_year_can_confirm(monkeypatch):
    """Salesforce's fiscal 2025 ended January 2025, with filings tagged so the
    fy=2025 rows hold the next year. Trusting the tag contradicted a true
    figure, so a claim stands if it matches either reading of the year."""
    _sec_rows(monkeypatch, [
        _row("2025-01-31", 2024, 37_900_000_000, "2024-02-01"),
        _row("2026-01-31", 2025, 41_500_000_000, "2025-02-01"),
    ])
    r = verify_sec_edgar(_decomp(
        "Salesforce generated $37.9 billion in revenue during its fiscal 2025.",
        37.9e9, metric="revenue", subject="Salesforce", time_period="2025"))
    assert r.match_type == "exact"


def test_matching_neither_reading_of_the_year_keeps_the_filed_figure(monkeypatch):
    _sec_rows(monkeypatch, [
        _row("2025-01-31", 2024, 37_900_000_000, "2024-02-01"),
        _row("2026-01-31", 2025, 41_500_000_000, "2025-02-01"),
    ])
    r = verify_sec_edgar(_decomp(
        "Salesforce generated $60 billion in revenue during its fiscal 2025.",
        60e9, metric="revenue", subject="Salesforce", time_period="2025"))
    _held_filing(r)


@pytest.mark.parametrize("sentence,raw,is_bound", [
    ("US national debt exceeded $34 trillion in January 2024.", "$34 trillion", True),
    ("UnitedHealth's revenue climbed past $400 billion.", "$400 billion", True),
    ("Revenue was over $5 billion in 2023.", "$5 billion", True),
    ("Revenue was at least $5 billion in 2023.", "$5 billion", True),
    ("Revenue was nearly $5 billion in 2023.", "$5 billion", False),
    ("Revenue was $5 billion in 2023, over the target.", "$5 billion", False),
])
def test_a_stated_bound_is_recognised(sentence, raw, is_bound):
    assert sn._states_a_bound(sentence, raw) is is_bound


def test_a_bound_cannot_be_contradicted():
    filing = SourceResult(source_name="SEC Filing", match_type="contradicted",
                          source_text="x", confidence=0.85)
    verdict, _c, detail = sn._consensus_for(
        ClaimDecomposition(
            sentence="Revenue exceeded $5 billion.", raw_value="$5 billion",
        ), [filing])
    assert verdict == "unverifiable"


def test_a_physical_measurement_gets_no_five_percent_slack():
    """From the final blind set: 457 m matched a 447 m observation deck."""
    sentence = "The CN Tower in Toronto is 457 meters tall."
    passage = "The tall observation deck stands at 447 m above the ground."
    d = _decomp(sentence, 457, metric="height", unit="distance",
                subject="CN Tower")
    assert _match_in_text(passage, 457, sentence, decomp=d)[0] is None


def test_a_rounded_physical_measurement_still_matches():
    sentence = "The Moon is about 384,400 km from Earth."
    passage = "The Moon orbits Earth at a distance of 378,000 km, on average."
    d = _decomp(sentence, 384400, metric="", unit="distance", subject="Moon")
    assert _match_in_text(passage, 384400, sentence, decomp=d)[0] is not None


# ── Reference-text precision ────────────────────────────────────────

@pytest.mark.parametrize("sentence,subject", [
    ("The Panama Canal runs for about 126 kilometers from ocean to ocean.",
     "Panama Canal"),
    ("The Suez Canal is about 193 kilometers long.", "Suez Canal"),
    ("Japan has a population of 125 million.", "Japan"),
    ("The population of Peru Today is about 34 million.", "Peru"),
])
def test_a_place_inside_a_name_is_not_the_subject(sentence, subject):
    assert sn.extract_subject("", sentence) == subject


def test_runs_for_is_a_length():
    d = decompose_claim({
        "sentence": "The Panama Canal runs for about 126 kilometers.",
        "numbers": ["126 kilometers"],
    })
    assert d.metric == "length"


def test_reference_revenue_must_be_for_the_year_claimed():
    """A range over 2009 to 2022 "confirmed" fiscal 2023 revenue while SEC was
    rate limited."""
    sentence = "Boeing brought in revenue of about $96 billion in fiscal 2023."
    passage = (
        "Research estimated Boeing made between $50 billion to $96 billion "
        "in revenue from contracts from 2009 through 2022."
    )
    d = _decomp(sentence, 96e9, metric="revenue", subject="Boeing",
                time_period="2023")
    assert _match_in_text(passage, 96e9, sentence, decomp=d)[0] is None


def test_reference_revenue_for_the_right_year_matches():
    sentence = "Boeing brought in revenue of about $78 billion in fiscal 2023."
    passage = "In 2023, Boeing reported revenue of $77.8 billion for the year."
    d = _decomp(sentence, 78e9, metric="revenue", subject="Boeing",
                time_period="2023")
    assert _match_in_text(passage, 78e9, sentence, decomp=d)[0] is not None


# ── From the fourth blind set ───────────────────────────────────────

def test_area_data_can_confirm_but_never_contradict(world_bank):
    """The World Bank series reported Canada at 15.6M square km against a true
    9.98M, so a true claim was contradicted. It is not reliable enough."""
    r = sn.verify_world_bank(_country(
        "Germany has an area of 500,000 square kilometres.", 500000,
        metric="area", unit="distance"))
    assert r.match_type == "no_data"


def test_two_financial_figures_in_a_sentence_cannot_contradict(monkeypatch):
    _sec_rows(monkeypatch, [_row("2023-12-31", 2023, 176_000_000_000,
                                 "2023-01-01")])
    r = verify_sec_edgar(_decomp(
        "Ford earned about $4.3 billion in net income in 2023 on revenue of "
        "about $176 billion.", 4.3e9, metric="revenue", subject="Ford",
        time_period="2023"))
    assert r.match_type == "no_data"


def test_a_monthly_rate_is_not_compared_with_an_annual_average(monkeypatch):
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: (
        [{}, [{"value": 133.5, "date": "2023"}]] if "/indicator/" in url
        else [{}, [{"iso2Code": "AR", "name": "Argentina"}]]
    ))
    monkeypatch.setattr(sn, "_WB_COUNTRY_CODES", {})
    r = sn.verify_world_bank(_decomp(
        "Argentina's annual inflation hit 211.4% in December 2023.", 211.4,
        metric="", unit="percent", subject="Argentina", time_period="2023"))
    assert r.match_type == "no_data"
    # The same sentence, when December's rate equals the annual average.
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: (
        [{}, [{"value": 211.4, "date": "2023"}]] if "/indicator/" in url
        else [{}, [{"iso2Code": "AR", "name": "Argentina"}]]
    ))
    r = sn.verify_world_bank(_decomp(
        "Argentina's annual inflation hit 211.4% in December 2023.", 211.4,
        metric="", unit="percent", subject="Argentina", time_period="2023"))
    assert r.match_type == "no_data"
    assert not r.withheld_refute
    assert not r.source_value


@pytest.mark.parametrize("sentence,numbers,primary", [
    ("Taipei 101 stands about 620 meters tall.", ["101", "620 meters"], "620 meters"),
    ("The Boeing 747 has a wingspan of 68 meters.", ["747", "68 meters"], "68 meters"),
    ("Population reached 500 people.", ["500 people"], "500 people"),
    ("Only 101 people attended.", ["101"], "101"),
])
def test_a_number_inside_a_name_is_not_the_claim(sentence, numbers, primary):
    d = decompose_claim({"sentence": sentence, "numbers": numbers})
    assert d.raw_value == primary


# ── From the 1.2.1 port review ──────────────────────────────────────

@pytest.mark.parametrize("sentence,subject", [
    (("While Kraft Heinz's net sales slipped to $25.8 billion in fiscal 2024, "
     "it stayed profitable."), "Kraft Heinz"),
    ("Although Apple's revenue fell, margins held.", "Apple"),
    ("The Walt Disney Company's revenue rose.", "Walt Disney Company"),
])
def test_a_leading_word_is_not_part_of_a_possessive_name(sentence, subject):
    assert sn.extract_subject("", sentence) == subject


@pytest.mark.parametrize("sentence", [
    "The Nile River is about 6,650 kilometers long.",
    "The Rhine runs for 1,230 kilometres.",
    "The route is 50 kilometer long.",
])
def test_kilometres_are_a_distance(sentence):
    d = decompose_claim({"sentence": sentence, "numbers": ["1"]})
    assert d.unit == "distance"


def test_feet_cannot_confirm_a_claim_in_kilometres():
    sentence = "The Nile River is about 6,600 kilometers long."
    passage = "The river is long, reaching 2 kilometers (6,600 ft) deep here."
    d = _decomp(sentence, 6600, metric="length", unit="distance",
                subject="Nile River")
    assert _match_in_text(passage, 6600, sentence, decomp=d)[0] is None


# End to end this time: extraction splits numbers into separate claims, so a
# guard inside decompose_claim never sees the two together.
@pytest.mark.parametrize("text,kept,dropped", [
    ("Taipei 101 stands about 620 meters tall.", "620", "101"),
    ("The Boeing 747 has a wingspan of 68 meters.", "68", "747"),
    ("Windows 11 reached 500 million users last year.", "500", "11"),
])
def test_extraction_drops_a_number_inside_a_name(text, kept, dropped):
    numbers = [
        str(n) for c in analyze_claims(text)["claims"] for n in c["numbers"]
    ]
    assert any(kept in n for n in numbers), numbers
    assert not any(n.strip() == dropped for n in numbers), numbers


@pytest.mark.parametrize("text,kept", [
    ("Only 101 people attended the event in the city hall.", "101"),
    ("Apple reported 2023 revenue of $383.3 billion.", "383.3"),
    ("Taipei 101 is a tower in Taiwan.", "101"),
])
def test_extraction_keeps_real_numbers(text, kept):
    numbers = [
        str(n) for c in analyze_claims(text)["claims"] for n in c["numbers"]
    ]
    assert any(kept in n for n in numbers), numbers


def test_extraction_keeps_a_number_after_an_opening_word():
    text = "About 500 people attended in 2023, and 120 stayed on afterwards."
    numbers = [
        str(n) for c in analyze_claims(text)["claims"] for n in c["numbers"]
    ]
    assert any("500" in n for n in numbers), numbers


# ── Whole documents: context has to carry across sentences ──────────

NIKE_DOC = (
    "Nike's fiscal 2024 ended on May 31, 2024, and it was a slow year. The "
    "company reported revenue of $51.4 billion, barely above the prior year. "
    "Net income for the year came in at $5.7 billion. Gross profit reached "
    "$27.6 billion, while total assets were $38.1 billion."
)
POLAND_DOC = (
    "Poland is one of the largest economies in Central Europe. The country "
    "had a population of about 44.2 million people in 2023. Its GDP that year "
    "was roughly $812 billion in current US dollars. Inflation ran at 11.5 "
    "percent. Life expectancy at birth was 78.3 years."
)
MIXED_DOC = (
    "Walmart reported revenue of $648.1 billion in fiscal 2024. Net income was "
    "$15.5 billion. Sweden makes a useful comparison. The country's GDP in "
    "2023 was about $579 billion."
)
APPLE_GERMANY_DOC = (
    "Apple's fiscal 2024 revenue was $383 billion and Germany's GDP was "
    "$4.5 trillion in 2023."
)
APPLE_GERMANY_CURLY = (
    "Apple\u2019s fiscal 2024 revenue was $383 billion and Germany\u2019s "
    "GDP was $4.5 trillion in 2023."
)


def _doc_decomps(text):
    entity = sn.extract_doc_primary_entity(text)
    claims = sn._split_multi_figure_claims(analyze_claims(text)["claims"])
    out = {}
    for c in sn._apply_discourse_context(claims, text):
        d = decompose_claim(c, doc_text=text, doc_primary_entity=entity)
        out[d.raw_value.strip()] = d
    return out


@pytest.mark.parametrize("text,number,subject", [
    (NIKE_DOC, "$51.4 billion", "Nike"),
    (NIKE_DOC, "$5.7 billion", "Nike"),
    (POLAND_DOC, "$812 billion", "Poland"),
    (POLAND_DOC, "78.3 years", "Poland"),
    (MIXED_DOC, "$15.5 billion", "Walmart"),
    (MIXED_DOC, "$579 billion", "Sweden"),
    (APPLE_GERMANY_DOC, "$383 billion", "Apple"),
    (APPLE_GERMANY_DOC, "$4.5", "Germany"),
    (APPLE_GERMANY_CURLY, "$383 billion", "Apple"),
    (APPLE_GERMANY_CURLY, "$4.5", "Germany"),
])
def test_a_later_sentence_keeps_the_nearest_subject(text, number, subject):
    assert _doc_decomps(text)[number].subject == subject


def test_the_year_carries_across_sentences():
    d = _doc_decomps(NIKE_DOC)["$5.7 billion"]
    assert "2024" in d.time_period


def test_a_multi_figure_sentence_checks_each_figure():
    decomps = _doc_decomps(NIKE_DOC)
    assert "$27.6 billion" in decomps and "$38.1 billion" in decomps
    assert "assets" not in decomps["$27.6 billion"].sentence
    assert decomps["$38.1 billion"].subject == "Nike"


def test_a_growth_rate_stays_with_its_figure(world_bank):
    text = "NVIDIA reported FY2024 revenue of $60.9 billion, up 126% from $26.97 billion."
    claims = sn._split_multi_figure_claims(analyze_claims(text)["claims"])
    assert len(claims) == 1
    for sentence in (
            ("Apple's revenue was $383 billion and Germany's GDP was not "
            "$4.5 trillion in 2023."),
            ("Apple's revenue was $383 billion and Germany's GDP wasn't "
            "$4.5 trillion in 2023."),
            ("US GDP was $27 trillion in 2023 and Germany's GDP ministry spent "
            "$4.5 trillion in 2023."),
            ("Apple's revenue was $383 billion and Germany's GDP grew "
            "5.5% in 2023."),
            ("Apple's revenue was $383 billion and Germany's oil GDP was "
            "$4.5 trillion in 2023."),
            ("Apple's revenue was $383 billion and Germany's Real GDP was "
            "$4.5 trillion in 2023."),
            ("Apple's revenue was $383 billion and Germany's 2024 GDP was "
            "$4.5 trillion in 2022."),
            ("Apple's revenue was $383 billion and Walmart's real revenue was "
            "$648 billion in 2024."),
    ):
        stayed = sn._split_multi_figure_claims(analyze_claims(sentence)["claims"])
        assert len(stayed) == 1, sentence
    for sentence in (
            ("Apple's fiscal 2024 revenue was $383 billion and Germany's real "
            "GDP was $4.5 trillion in 2023."),
            ("Apple's revenue was $383 billion and Germany's GDP in real terms "
            "was $4.5 trillion in 2023."),
            ("Apple's revenue was $383 billion and Germany's GDP in constant "
            "prices was $4.5 trillion in 2023."),
    ):
        germany = _doc_decomps(sentence)["$4.5"]
        assert germany.subject == "Germany", sentence
        quiet = sn.verify_world_bank(germany)
        assert quiet.match_type == "no_data", sentence
        assert not quiet.source_value
    for sentence in (
            ("Apple's revenue was $383 billion and Germany's nominal GDP was "
            "$4.5 trillion in 2023."),
            ("Apple's revenue was $383 billion and Germany's GDP in nominal "
            "terms was $4.5 trillion in 2023."),
    ):
        germany = _doc_decomps(sentence)["$4.5"]
        assert germany.subject == "Germany", sentence
        assert sn.verify_world_bank(germany).match_type == "exact", sentence


def test_an_inherited_year_alone_cannot_contradict(apple_sec):
    d = _decomp("Revenue is $420 billion.", 420e9, metric="revenue",
                time_period="2023")
    d.year_inherited = True
    assert verify_sec_edgar(d).match_type == "no_data"


def test_an_explicit_reference_to_the_year_keeps_the_filed_figure(apple_sec):
    d = _decomp("Revenue for the year was $420 billion.", 420e9,
                metric="revenue", time_period="2023")
    d.year_inherited = True
    _held_filing(verify_sec_edgar(d))


@pytest.mark.parametrize("sentence", [
    "Life expectancy at birth was 78.3 years.",
    "Inflation ran at 11.5 percent.",
    "Merchandise sales were $16.7 billion.",
    "It was worth $5 billion in current US dollars.",
])
def test_ordinary_openings_are_not_subjects(sentence):
    subject = sn.extract_subject("", sentence)
    assert subject in ("",), subject


REGION_DOC = (
    "Indonesia is the largest economy in Southeast Asia. Its population was "
    "281.2 million in 2023. Inflation averaged 3.7 percent, one of the lower "
    "rates in the European Union. It had 2.3 million square kilometers."
)
CHAIN_DOC = (
    "Sweden makes a useful comparison. The country's GDP in 2023 was about "
    "$579 billion, less than Walmart's annual sales. It had a population of "
    "about 12.4 million."
)


@pytest.mark.parametrize("text,number,subject", [
    (REGION_DOC, "281.2 million", "Indonesia"),
    (REGION_DOC, "3.7 percent", "Indonesia"),
    (REGION_DOC, "2.3 million", "Indonesia"),
    (CHAIN_DOC, "12.4 million", "Sweden"),
])
def test_regions_and_passing_mentions_do_not_take_the_subject(text, number,
                                                              subject):
    decomps = _doc_decomps(text)
    key = next(k for k in decomps if number.split()[0] in k)
    assert decomps[key].subject == subject


# ── Coverage: figures filings hold, subjects before the figure ──────

def _concept_rows(monkeypatch, by_concept, unit="USD"):
    monkeypatch.setattr(sn, "_find_cik", lambda s: ("1", "XYZ"))

    def fetch(req, per_op_timeout=8):
        concept = req.full_url.rsplit("/", 1)[1].replace(".json", "")
        rows = by_concept.get(concept)
        if rows is None:
            raise OSError("no such concept")
        return json.dumps({"units": {unit: rows}}).encode()

    monkeypatch.setattr(sn, "_urlopen_with_deadline", fetch)


@pytest.mark.parametrize("sentence,metric,value,concept,unit", [
    ("Starbucks' operating income in fiscal 2024 was $5.4 billion.",
     "operating_income", 5.4e9, "OperatingIncomeLoss", "USD"),
    ("Oracle's gross profit in fiscal 2024 was $37 billion.",
     "gross_profit", 37e9, "GrossProfit", "USD"),
    ("Deere spent $2.29 billion on research and development in fiscal 2024.",
     "research_development", 2.29e9, "ResearchAndDevelopmentExpense", "USD"),
    ("Starbucks' diluted earnings per share in fiscal 2024 were $3.31.",
     "eps", 3.31, "EarningsPerShareDiluted", "USD/shares"),
])
def test_filings_answer_the_other_figures_they_hold(monkeypatch, sentence,
                                                    metric, value, concept,
                                                    unit):
    d = decompose_claim({"sentence": sentence, "numbers": ["1"]})
    assert d.metric == metric
    d.value = value
    d.unit = "currency"
    d.time_period = "2024"
    _concept_rows(monkeypatch, {concept: [
        _row("2024-09-29", 2024, value, "2023-10-02"),
    ]}, unit=unit)
    assert verify_sec_edgar(d).match_type == "exact"


def test_a_different_eps_keeps_the_filed_eps(monkeypatch):
    d = decompose_claim({
        "sentence": "Starbucks' diluted earnings per share in fiscal 2024 were $9.",
        "numbers": ["$9"],
    })
    d.value, d.unit, d.time_period = 9.0, "currency", "2024"
    _concept_rows(monkeypatch, {"EarningsPerShareDiluted": [
        _row("2024-09-29", 2024, 3.31, "2023-10-02"),
    ]}, unit="USD/shares")
    r = _held_filing(verify_sec_edgar(d))
    assert r.source_value == 3.31


@pytest.mark.parametrize("text,number,subject", [
    (("Deere had a strong year. Net income was $7.1 billion as farmers in North "
     "America and South America pulled back."), "$7.1 billion", "Deere"),
    (("In fiscal 2024, Home Depot posted net sales of $159.5 billion, a total "
     "that included SRS Distribution."), "$159.5 billion", "Home Depot"),
    ("Apple's supplier in Germany reported revenue of $10 billion in 2023.",
     "$10 billion", "Apple"),
])
def test_a_name_after_the_figure_does_not_take_the_subject(text, number, subject):
    assert _doc_decomps(text)[number].subject == subject


def test_a_name_only_after_the_figure_is_still_used_alone():
    d = decompose_claim({"sentence": "Revenue was $5 billion at Apple in 2023.",
                         "numbers": ["$5 billion"]})
    assert d.subject == "Apple"


def test_a_possessive_company_name_keeps_its_s(monkeypatch):
    monkeypatch.setattr(sn, "_get_sec_tickers", lambda: (
        {"LOWES COMPANIES INC": ("1", "LOW")}, {},
    ))
    assert sn._find_cik("Lowe")[1] == "LOW"


def test_two_years_cannot_contradict_at_the_world_bank(monkeypatch):
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: (
        [{}, [{"value": 3.2, "date": "2024"}]] if "/indicator/" in url
        else [{}, [{"iso2Code": "PH", "name": "Philippines"}]]
    ))
    monkeypatch.setattr(sn, "_WB_COUNTRY_CODES", {})
    r = sn.verify_world_bank(_decomp(
        "Inflation eased to 4.4 percent in 2024 after averaging 6.0 percent "
        "in 2023.", 6.0, unit="percent", subject="Philippines",
        time_period="2024"))
    assert r.match_type == "no_data"


@pytest.mark.parametrize("sentence,value,metric,passage", [
    ("The surface pressure on Mars averages about 8.9 millibars.", 8.9, "count",
     "The surface pressure on Mars is close to 8.7 at some sites averages."),
    ("Life expectancy in Indonesia was 60.2 years.", 60.2, "lifespan",
     "Life expectancy in Indonesia reached 62.0 years old by then."),
])
def test_reference_text_gets_no_five_percent_slack_on_vague_figures(
        sentence, value, metric, passage):
    d = _decomp(sentence, value, metric=metric, unit="count", subject="Mars")
    assert _match_in_text(passage, value, sentence, decomp=d)[0] is None


def test_revenue_before_a_number_is_not_a_name():
    numbers = [
        str(n) for c in analyze_claims("Revenue 500 rose 3% last year.")["claims"]
        for n in c["numbers"]
    ]
    assert any("500" in n for n in numbers), numbers


def test_filing_concepts_are_fetched_once_per_request(monkeypatch):
    calls = []

    def fetch(req, per_op_timeout=8):
        calls.append(req.full_url)
        return json.dumps({"units": {"USD": [
            _row("2023-09-30", 2023, 383_285_000_000, "2022-10-01"),
        ]}}).encode()

    monkeypatch.setattr(sn, "_find_cik", lambda s: ("320193", "AAPL"))
    monkeypatch.setattr(sn, "_urlopen_with_deadline", fetch)
    monkeypatch.setattr(sn, "_query_wikipedia", lambda s: ("", "", 0))
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    text = (
        "Apple's revenue in fiscal 2023 was $383.3 billion. Apple's sales in "
        "fiscal 2023 were about $383 billion."
    )
    sn.verify_claims_source_network(analyze_claims(text)["claims"], doc_text=text)
    assert len(calls) == len(set(calls))


# ── Comparison documents ────────────────────────────────────────────

COMPARE_DOC = (
    "Chile and Peru share a long border. In 2023 Chile had about 19.7 million "
    "people, while Peru had about 33.8 million. Annual-average inflation was "
    "7.6 percent in Chile, as the central bank worked down an overshoot. "
    "Unemployment was 8.9 percent that year."
)
SOURCE_DOC = (
    "Kenya is a large economy. World Bank data put GDP at $107.5 billion in "
    "2023. The modeled unemployment rate was 5.4 percent."
)


@pytest.mark.parametrize("text,number,subject", [
    (COMPARE_DOC, "19.7 million", "Chile"),
    (COMPARE_DOC, "33.8 million", "Peru"),
    (COMPARE_DOC, "7.6 percent", "Chile"),
    (SOURCE_DOC, "$107.5 billion", "Kenya"),
    (SOURCE_DOC, "5.4 percent", "Kenya"),
])
def test_the_nearest_name_owns_the_figure(text, number, subject):
    decomps = _doc_decomps(text)
    key = next(k for k in decomps if number.split()[0] in k)
    assert decomps[key].subject == subject


def test_a_silently_inherited_subject_in_a_comparison_cannot_contradict(world_bank):
    decomps = _doc_decomps(
        "Germany and Spain are often compared. Germany has a population of "
        "about 84 million in 2023. Its neighbour Spain is smaller. The "
        "population was about 90 million in 2023."
    )
    d = decomps["90 million"]
    assert d.subject_ambiguous
    assert sn.verify_world_bank(d).match_type == "no_data"


def test_a_named_subject_in_a_comparison_keeps_the_world_bank_figure(world_bank):
    d = _country("Germany has a population of about 12 million in 2023.", 12e6,
                 time_period="2023")
    r = sn.verify_world_bank(d)
    # The World Bank earned refute on v32 (2026-11-28).
    assert r.match_type == "contradicted"
    assert not r.withheld_refute
    assert r.source_value == 83_491_249


def test_a_quarterly_eps_citation_keeps_its_cents(monkeypatch):
    _concept_rows(monkeypatch, {"EarningsPerShareDiluted": [{
        "form": "10-Q", "fp": "Q2", "fy": 2024, "end": "2024-03-31",
        "start": "2024-01-01", "filed": "2024-05-01", "val": 3.31,
    }]}, unit="USD/shares")
    r = verify_sec_edgar(_decomp(
        "Starbucks' diluted earnings per share in Q2 2024 were $3.31.", 3.31,
        metric="eps", subject="Starbucks", time_period="Q2 2024"))
    assert "$3.31" in r.source_text


def test_the_public_entry_point_names_its_arguments():
    import inspect
    params = inspect.signature(sn.verify_claims_source_network).parameters
    assert list(params)[:2] == ["claims", "topic"]


def test_a_fiscal_end_date_belongs_to_its_own_year_only():
    # v13 u02: "fiscal 2024 vs fiscal 2023\n(fiscal 2024 ended January 28, 2024"
    # gave fiscal 2023 that end date, and four true FY2023 figures were
    # compared with fiscal 2024.
    doc = ("NVIDIA, fiscal 2024 vs fiscal 2023\n"
           "(fiscal 2024 ended January 28, 2024; in millions, except per-share data)")
    assert sn._fiscal_end("", doc, "FY2023") == ""
    assert sn._fiscal_end("", doc, "FY2024") == "2024|2024-01-28"


def test_a_year_before_does_not_take_the_headings_end_date():
    # v12 t11: under "fiscal 2023 (year ended February 3, 2024)", "$10.21
    # billion the year before" was pinned to the year ending February 2024.
    heading = "Ulta Beauty, fiscal 2023 (year ended February 3, 2024)"
    line = "Net sales: $11.21 billion, up about 9.8% from $10.21 billion the year before"
    parts = sn._split_prior_figures({"sentence": line, "heading": heading,
                                     "numbers": ["$11.21 billion", "$10.21 billion"]})
    prior = next(p for p in parts if p.get("prior_figure"))
    d = decompose_claim(prior, doc_text=heading + "\n" + line)
    assert d.fiscal_end == ""


# The open real-world dev set (2026-11-08): results releases lead with the
# fourth quarter, and no filing states it. A 10-K holds the year and the
# Q3 10-Q the nine months that started the same day; the difference is Q4.
CLOROX_YEAR = [
    {"form": "10-K", "fp": "FY", "fy": 2024, "start": "2023-07-01", "end": "2024-06-30",
     "filed": "2024-08-13", "val": 7_093_000_000},
    {"form": "10-Q", "fp": "Q3", "fy": 2024, "start": "2023-07-01", "end": "2024-03-31",
     "filed": "2024-05-01", "val": 5_190_000_000},
    {"form": "10-Q", "fp": "Q3", "fy": 2024, "start": "2024-01-01", "end": "2024-03-31",
     "filed": "2024-05-01", "val": 1_809_000_000},
]


def _q4(figure, value, metric="revenue"):
    return _decomp(f"Clorox's fourth-quarter fiscal 2024 net sales were {figure}.", value,
                   metric=metric, subject="Clorox", time_period="Q4 2024")


def test_a_fourth_quarter_is_the_year_less_nine_months(monkeypatch):
    _sec_rows(monkeypatch, CLOROX_YEAR)
    r = verify_sec_edgar(_q4("$1,903 million", 1_903_000_000))
    assert r.match_type == "exact"
    assert "Q4" in r.source_text


def test_a_wrong_fourth_quarter_is_not_confirmed(monkeypatch):
    # A derived fourth quarter may confirm, never refute, until a fresh sealed
    # set validates it (see tests/test_release_alarms.py).
    _sec_rows(monkeypatch, CLOROX_YEAR)
    assert verify_sec_edgar(_q4("$2,400 million", 2_400_000_000)).match_type == "no_data"


def test_per_share_figures_do_not_add_up_to_a_fourth_quarter(monkeypatch):
    rows = [dict(r, val=r["val"] / 1e9) for r in CLOROX_YEAR]
    _sec_rows(monkeypatch, rows)
    assert verify_sec_edgar(_q4("$1.90", 1.90, metric="eps")).match_type == "no_data"


# Open dev set: ASML and Ferrari file 20-F reports under IFRS, in euros. A
# euro figure was refused outright and the us-gaap concepts held nothing.
ASML_ROWS = [{"form": "20-F", "fp": "FY", "fy": 2024, "start": "2024-01-01",
              "end": "2024-12-31", "filed": "2025-02-12", "val": 28_262_900_000}]


def _ifrs(monkeypatch, rows, unit="EUR"):
    import io
    import urllib.error
    monkeypatch.setattr(sn, "_find_cik", lambda s: ("937966", "ASML"))
    seen = []

    def fake(req, per_op_timeout=8):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        seen.append(url)
        if "/ifrs-full/" in url:
            return json.dumps({"units": {unit: rows}}).encode()
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))
    monkeypatch.setattr(sn, "_urlopen_with_deadline", fake)
    return seen


def test_a_euro_figure_is_checked_against_ifrs_in_euros(monkeypatch):
    _ifrs(monkeypatch, ASML_ROWS)
    r = verify_sec_edgar(_decomp("ASML's revenue was €28.3 billion in 2024.", 28.3e9,
                                 metric="revenue", subject="ASML", time_period="2024"))
    assert r.match_type == "exact"
    assert "€" in r.source_text or "EUR" in r.source_text


def test_a_wrong_euro_figure_is_not_confirmed(monkeypatch):
    # IFRS facts may confirm, never refute, until a fresh sealed set validates them.
    _ifrs(monkeypatch, ASML_ROWS)
    r = verify_sec_edgar(_decomp("ASML's revenue was €31.0 billion in 2024.", 31.0e9,
                                 metric="revenue", subject="ASML", time_period="2024"))
    assert r.match_type == "no_data"


def test_euros_never_match_dollar_facts(monkeypatch):
    _ifrs(monkeypatch, ASML_ROWS, unit="USD")
    r = verify_sec_edgar(_decomp("ASML's revenue was €28.3 billion in 2024.", 28.3e9,
                                 metric="revenue", subject="ASML", time_period="2024"))
    assert r.match_type == "no_data"


def test_a_us_gaap_filer_is_not_asked_for_ifrs(monkeypatch):
    seen = []
    monkeypatch.setattr(sn, "_find_cik", lambda s: ("1", "TGT"))

    def fake(req, per_op_timeout=8):
        seen.append(req.full_url)
        return json.dumps({"units": {"USD": TARGET_DATED}}).encode()
    monkeypatch.setattr(sn, "_urlopen_with_deadline", fake)
    verify_sec_edgar(_decomp("Target's revenue was $99.0 billion in fiscal 2024.", 99e9,
                             metric="revenue", subject="Target", time_period="2024"))
    assert seen and not any("/ifrs-full/" in u for u in seen)


@pytest.mark.parametrize("sentence,raw,code", [
    ("Revenue was EUR 28.3 billion in 2024.", "28.3 billion", "EUR"),
    ("Revenue was 28.3 billion euros in 2024.", "28.3 billion", "EUR"),
    ("Profit was 1.2 billion pounds sterling.", "1.2 billion", "GBP"),
    ("Revenue was $28.3 billion in 2024.", "$28.3 billion", "USD"),
])
def test_the_currency_is_read_from_words_as_well_as_symbols(sentence, raw, code):
    d = _decomp(sentence, 1.0, metric="revenue")
    d.raw_value = raw
    assert sn._claim_currency(d)[0] == code


def test_another_figures_currency_is_not_this_ones():
    d = _decomp("ASML's revenue was $30.6 billion, or €28.3 billion, in 2024.", 1.0,
                metric="revenue")
    d.raw_value = "$30.6 billion"
    assert sn._claim_currency(d)[0] == "USD"
    d.raw_value = "€28.3 billion"
    assert sn._claim_currency(d)[0] == "EUR"


# ------------------------------------------------ a number inside a hyphenated name

import pytest as _pytest_hyphen  # noqa: E402

from claim_analysis import analyze_claims as _analyze  # noqa: E402


def _figures(text):
    return [n for c in _analyze(text)["claims"] for n in c["numbers"]]


@_pytest_hyphen.mark.parametrize("text, not_a_figure", [
    # v19 (a World Bank country page, 2026-11-26): "19" in "Covid-19" was
    # refuted against the 2019 poverty rate, 10.90, when World Bank was
    # allowed to refute. A name is not a figure.
    ("Poverty fell to below 10 percent just before the Covid-19 pandemic.", "19"),
    ("The G-20 met as the COVID-19 crisis hit and orders rose 12%.", "20"),
    ("The F-35 programme cost rose 9% to $1.7 trillion.", "35"),
])
def test_a_number_hyphenated_to_a_name_is_not_a_figure(text, not_a_figure):
    assert not_a_figure not in _figures(text)


@_pytest_hyphen.mark.parametrize("text, figure", [
    # A figure after a lowercase hyphen word, a range, or a percent stays one.
    ("The rate fell from 30.8% in 2018 to 19.8% in 2024.", "19.8%"),
    ("Growth was 4.4-4.8% in the year.", "4.4-4.8%"),
    ("It ranks in the top-10 for exports with 12% of the market.", "12%"),
    ("About 19 million people live below the poverty line, 8.5 percent.", "19 million"),
    ("During Covid-19, 19 hospitals closed and 4,200 beds were cut.", "19"),
])
def test_other_figures_near_a_hyphen_stay(text, figure):
    assert figure in _figures(text)


# ------------------------------------------------ a country measure belongs to the document's country

import source_network as _sn_dom  # noqa: E402
from prose import plain_prose as _plain  # noqa: E402

_POLAND = (
    "Poland is one of the stronger performers in Central Europe.\n\n"
    "Real GDP growth was 4.6% in 2019, after the shock of the war in neighboring Ukraine.\n\n"
    "Inflation was low: consumer prices rose 2.1% in 2017 and 2.2% in 2019.\n\n"
    "Unemployment (ILO modeled) averaged 3.8% in 2018 and 3.2% in 2020.\n\n"
    "Wages are still below Western European levels, but Poland keeps closing the gap.\n\n"
    "The population was 36.6 million in 2024, and life expectancy was 78.3 years in 2023."
)


def _subjects(text):
    t = _plain(text)
    primary = _sn_dom.extract_doc_primary_entity(t)
    claims = _sn_dom._prepare_claims(_analyze(t)["claims"], t)
    return {n: _sn_dom.decompose_claim(c, doc_text=t, doc_primary_entity=primary).subject
            for c in claims for n in c["numbers"]}


def test_a_country_measure_takes_the_documents_country():
    """v20, 2026-11-26: with the reader down (production that day), Poland's
    inflation took "Ukraine" from a passing mention, its unemployment took
    "ILO" from "(ILO modeled)", and its population took "Wages", so none of
    them could be checked."""
    got = _subjects(_POLAND)
    for figure in ("2.1%", "2.2%", "3.8%", "3.2%", "36.6 million", "78.3 years"):
        assert got[figure] == "Poland", (figure, got[figure])


def test_a_named_city_or_country_keeps_its_own_figure():
    got = _subjects(
        "Nigeria is Africa's most populous country, with 223.8 million people in 2023.\n\n"
        "Lagos has a population of 15.4 million.\n\n"
        "In Ghana, inflation was 31.7% in 2022."
    )
    assert got["15.4 million"] == "Lagos"
    assert got["31.7%"] == "Ghana"


def test_a_comparison_document_is_left_as_it_was():
    text = ("Chile and Peru took different paths.\n\nChile grew fast.\n\nPeru did not, "
            "and Chile kept its lead.\n\nInflation was 7.8% in 2022.")
    before = _subjects(text)["7.8%"]
    assert before in ("Chile", "Peru", "")


def test_a_country_named_in_passing_does_not_take_the_documents_figures():
    """v9 r11: a report on Mongolia names China twice in passing ("between
    China and Russia", "exports to China"). Its GDP per capita is Mongolia's."""
    got = _subjects(
        "Mongolia, a landlocked country between China and Russia, had a population "
        "of roughly 3.39 million in 2024. The economy depends on copper exports to "
        "China. Consumer price inflation averaged 4.4% over the year. GDP per capita "
        "stood at about $6,751."
    )
    assert got["$6,751"] == "Mongolia"
    assert got["4.4%"] == "Mongolia"


@_pytest_hyphen.mark.parametrize("text, threshold", [
    # v19 (BEA county GDP release): "Large counties (population > 500,000)" was
    # refuted against the US population when World Bank was allowed to refute.
    ("Large counties (population > 500,000)\n\nReal GDP rose 2.8% in 2024.", "500,000"),
    ("Small counties (population < 50,000)\n\nIncome grew 4.1% in 2024.", "50,000"),
])
def test_a_threshold_after_a_comparison_sign_is_not_a_figure(text, threshold):
    assert threshold not in _figures(text)


def test_more_than_in_prose_is_still_a_figure():
    assert "500,000" in _figures("More than 500,000 people moved in 2023.")


import re as _re_reason  # noqa: E402


@_pytest_hyphen.mark.parametrize("sentence, states_another", [
    # v21 Sweden: the reason after the figure is not the figure's measure.
    ("The jobless rate was 6.8% in 2019 and rose to 8.8% in 2021 as pandemic restrictions bit.", False),
    ("Prices rose 3.1% in 2022 because energy costs surged.", False),
    ("Unemployment fell to 4.2% in 2023 amid strong hiring in services.", False),
    # A measure stated after the figure still counts.
    ("Exports rose to 31.0% as a share of GDP in 2022.", True),
    ("at 4.1% for union membership in 2023.", True),
])
def test_a_reason_after_the_figure_is_not_its_measure(sentence, states_another):
    figure = _re_reason.findall(r"\d[\d.]*%", sentence)[-1]
    pattern = _sn_dom._WB_INDICATOR_WORDS["SL.UEM.TOTL.ZS"] if "jobless" in sentence or "Unemploy" in sentence \
        else _sn_dom._WB_INDICATOR_WORDS["FP.CPI.TOTL.ZG"]
    at = sentence.rfind(figure)
    assert _sn_dom._clause_states_another(sentence, figure, at, pattern) is states_another


@_pytest_hyphen.mark.parametrize("text, figure, metric, subject", [
    # v21 (open since its one scoring): measures phrased the way people write.
    ("Malaysia grew fast.\n\nPeople could expect to live 75.4 years on average in 2016.",
     "75.4 years", "lifespan", "Malaysia"),
    ("Sweden is rich.\n\nThe average lifespan was 83.1 years in 2019.", "83.1 years", "lifespan", "Sweden"),
    ("Malaysia grew fast.\n\nHouseholds felt it.\n\nIncome per person was $10,902 in 2018.",
     "$10,902", "gdp_per_capita", "Malaysia"),
])
def test_natural_phrasings_of_country_measures(text, figure, metric, subject):
    t = _plain(text)
    primary = _sn_dom.extract_doc_primary_entity(t)
    for c in _sn_dom._prepare_claims(_analyze(t)["claims"], t):
        if figure in c["numbers"]:
            d = _sn_dom.decompose_claim(c, doc_text=t, doc_primary_entity=primary)
            assert (d.metric, d.subject) == (metric, subject)
            return
    raise AssertionError(f"{figure} not extracted")


def test_people_who_lived_there_are_the_population():
    import source_network as sn
    assert sn._COUNTRY_TOTAL_RE.search("About 32.4 million people lived there in 2017.")
    assert sn._COUNTRY_TOTAL_RE.search("Roughly 5.6 million people live in the country.")
    assert not sn._COUNTRY_TOTAL_RE.search("12 million people use the service there.")


def test_group_labels_in_a_release_are_not_figures():
    """v19 of03 (BEA county GDP): the main claim path still carried
    "Large counties (population > 500,000)" after the uncovered-number fix,
    and the next label bounds a group with a range."""
    text = ("In 2024, real GDP ranged from $813.7 billion in New York County, NY, to "
            "$15.7 million in Issaquena County, MS.\n\n"
            "Large counties (population > 500,000)\n\n"
            "Medium counties (population 100,000 to 500,000)\n\n"
            "Real GDP increased in 2,309 counties.")
    figures = _figures(text)
    assert "500,000" not in figures and "100,000" not in figures
    assert "$813.7 billion" in figures


@_pytest_hyphen.mark.parametrize("sentence, figure, sign", [
    # v22 Israel and Syria: "a contraction" belongs to the clause before the semicolon.
    (("Turning to the data, real growth came in at 3.6% in 2019; growth was -1.8% in 2020, "
     "a contraction; and output expanded 1.0% in 2024."), "1.0%", 1),
    (("growth was -6.4% in 2016, a contraction; output expanded 1.8% in 2021; and the "
     "economy contracted, with growth of -0.2% in 2022."), "1.8%", 1),
    # The figure's own clause still decides when it says the economy shrank.
    ("growth was 3.6% in 2019; the economy contracted 2.0% in 2020.", "2.0%", -1),
    ("Output grew 2.5% in 2018 and shrank 1.2% in 2020.", "1.2%", -1),
])
def test_a_figures_sign_comes_from_its_own_clause(sentence, figure, sign):
    assert _sn_dom._growth_sign(sentence, figure) == sign


@_pytest_hyphen.mark.parametrize("text, figure, subject", [
    # v22 (open): a sentence with no subject, and label words taken as one.
    ("Nepal is a landlocked Himalayan country.\n\nInflation hit 16.8% in 2021.", "16.8%", "Nepal"),
    ("Nepal is a landlocked Himalayan country.\n\nJobless rate: Unemployment stood at 12.7% in 2016.",
     "12.7%", "Nepal"),
    ("Nepal is a landlocked Himalayan country.\n\nEconomic growth: Output growth was -1.2% in 2016.",
     "1.2%", "Nepal"),
    ("Nepal is a landlocked Himalayan country.\n\nSize of the economy: $40.8 billion in 2022.",
     "$40.8 billion", "Nepal"),
])
def test_a_label_or_no_subject_takes_the_lead_country(text, figure, subject):
    got = _subjects(text)
    assert got.get(figure) == subject, got


@_pytest_hyphen.mark.parametrize("sentence, indicator", [
    ("Total output came to $1.9 billion in 2021.", "NY.GDP.MKTP.CD"),
    ("Size of the economy: $40.8 billion in 2022.", "NY.GDP.MKTP.CD"),
    ("Output per resident averaged $975 in 2016.", "NY.GDP.PCAP.CD"),
])
def test_ordinary_names_for_gdp_select_it(sentence, indicator):
    assert _sn_dom._detect_wb_indicator(sentence, "")[0] == indicator


@_pytest_hyphen.mark.parametrize("sentence, figure", [
    ("Economic growth was 10.1% in 2017.", "10.1%"),
    ("Output growth was -1.2% in 2016.", "1.2%"),
])
def test_plain_growth_in_a_country_answer_is_real_growth(sentence, figure):
    assert _sn_dom._is_real_growth(sentence, figure, sentence)


def test_sector_growth_is_still_not_the_economy():
    s = "Tourism growth was 12.0% in 2022."
    assert not _sn_dom._is_real_growth(s, "12.0%", s)


# ------------------------------------------------ fresh-eyes review, 2026-11-27

@_pytest_hyphen.mark.parametrize("sentence, figure, sign", [
    ("Real GDP growth - 2.0% (2024)", "2.0%", 1),          # a label dash is not a minus
    ("GDP grew between 2.1% - 3.4% in 2023", "3.4%", 1),    # nor is a range dash
    ("GDP grew 12% in 2019, then shrank 2% in 2020", "2%", -1),  # 2% is not inside 12%
    ("GDP grew 10.3% in 2021 and fell 0.3% in 2022", "0.3%", -1),
    ("Real GDP growth was -2.0% in 2020.", "2.0%", -1),     # a touching minus still is
])
def test_review_growth_signs(sentence, figure, sign):
    assert _sn_dom._growth_sign(sentence, figure) == sign


@_pytest_hyphen.mark.parametrize("line", [
    "Government debt, % of GDP: 98% in 2023.",
    "Health spending (% of GDP: 9.9%) in 2022.",
])
def test_a_share_of_gdp_is_not_gdp_growth(line):
    t = _plain("Poland is in Europe.\n\n" + line)
    figure = _re_reason.findall(r"\d[\d.]*%", line)[-1]
    for c in _sn_dom._prepare_claims(_analyze(t)["claims"], t):
        if figure in c["numbers"]:
            d = _sn_dom.decompose_claim(c, doc_text=t, doc_primary_entity="Poland")
            assert _sn_dom._wb_indicator_for(d)[0] != "NY.GDP.MKTP.KD.ZG"


def test_a_long_table_with_two_measures_keeps_their_names():
    out = _plain("| Country | Year | GDP growth | Inflation |\n|---|---|---|---|\n"
                 "| Poland | 2020 | -2.2% | 3.4% |\n")
    assert "Poland GDP growth was -2.2% in 2020." in out
    assert "Poland inflation was 3.4% in 2020." in out


def test_a_companys_revenue_growth_keeps_the_company():
    """Was a strict xfail (72186bc): "sells cars in China" made China the next
    sentence's subject."""
    got = _subjects("Tesla Q3 results.\n\nTesla sells cars in China and the US. "
                    "Revenue growth was 12% in 2023.")
    assert got["12%"] == "Tesla"


@_pytest_hyphen.mark.parametrize("text, figure, year", [
    # v24 (Haiku, from memory): the second figure's own "in 2022" lost to the
    # sentence's first year, and $812 billion was confirmed as 2023's GDP.
    (("Poland is in Europe.\n\nThe population was about 37.6 million in 2023, and GDP "
     "reached about $812 billion in 2022."), "$812 billion", "2022"),
    (("Poland is in Europe.\n\nThe population was about 37.6 million in 2023, and GDP "
     "reached about $812 billion in 2022."), "37.6 million", "2023"),
    # A price base is not the figure's year.
    ("Poland is in Europe.\n\nIn 2023 GDP was $640 billion in 2015 dollars.", "$640 billion", "2023"),
])
def test_a_figures_own_year_follows_it(text, figure, year):
    t = _plain(text)
    for c in _sn_dom._prepare_claims(_analyze(t)["claims"], t):
        if figure in c["numbers"]:
            d = _sn_dom.decompose_claim(c, doc_text=t, doc_primary_entity="Poland")
            assert year in d.time_period, (figure, d.time_period)
            return
    raise AssertionError(f"{figure} not extracted")


# ------------------------------------------------ comparison answers (v25 class)

@_pytest_hyphen.mark.parametrize("text, figure, subject", [
    # The second country's figure stays the second country's, however often the
    # first is named: the lead-country rule is for single-country answers.
    (("Egypt and the UAE differ sharply. Egypt has a young, fast-growing population and Egypt "
     "depends on tourism; Egypt also faces high inflation.\n\nThe United Arab Emirates is "
     "richer. Life expectancy stood at 79.1 years in 2021, which is high for the region."),
     "79.1 years", "United Arab Emirates"),
    (("Kenya and Tanzania are neighbours.\n\nKenya grew quickly.\n\nTanzania is poorer, and "
     "the economy expanded 4.7% in 2022."), "4.7%", "Tanzania"),
    # A country after "than in" is the comparison, not the subject.
    (("Serbia is the larger of the two.\n\nInflation has run hotter than in Switzerland, "
     "reaching 12.4% in 2023."), "12.4%", "Serbia"),
])
def test_a_comparison_keeps_each_countrys_figures(text, figure, subject):
    assert _subjects(text).get(figure) == subject


def test_a_single_country_answer_still_takes_its_country():
    got = _subjects(_POLAND)
    assert got["3.8%"] == "Poland" and got["2.1%"] == "Poland"


# ------------------------------------------------ v26 classes, tested on new wording

def test_whereas_gives_the_second_figure_its_own_country():
    got = _subjects("Ghana and Togo are neighbours.\n\nGhana's inflation was 31.7% in 2022, "
                    "whereas Togo's was 7.6% in 2022.")
    assert got["7.6%"] == "Togo" and got["31.7%"] == "Ghana"


def test_a_colon_ends_the_clause_that_set_a_sign():
    assert _sn_dom._growth_sign("Output fell by 8.0% in 2020, after a slow patch: growth was 1.5% "
                                "in 2019.", "1.5%") == 1


def test_a_passing_country_gives_way_to_the_paragraphs_country():
    text = ("Both are small economies with big neighbours.\n\n"
            "Norway is rich and its oil fund is huge.\n\n"
            "Georgia sits on a trade corridor. Remittances from Russia matter a great deal. "
            "Inflation was 11.9% in 2022 and unemployment was 17.3% in 2022.")
    got = _subjects(text)
    assert got["11.9%"] != "Norway" and got["17.3%"] != "Norway"


# ------------------------------------------------ v27 classes, tested on new wording

def test_a_country_named_with_for_after_its_figure_owns_it():
    got = _subjects("Chile and Peru are neighbours.\n\nChile's inflation was 7.6% in 2022, "
                    "against 8.1% in 2022 for Peru.")
    assert got["8.1%"] == "Peru" and got["7.6%"] == "Chile"


def test_bosnia_and_herzegovina_is_one_country():
    got = _subjects("Austria and Bosnia and Herzegovina differ.\n\nBosnia and Herzegovina's economy "
                    "grew, and its unemployment was 12.7% in 2021.")
    assert got["12.7%"] == "Bosnia and Herzegovina"


def test_a_paragraph_that_opens_on_the_second_country_keeps_its_figures():
    text = ("Spain is a large, rich economy, and Spain draws many tourists. Spain is popular.\n\n"
            "Over to Moldova now. Inflation was 28.6% in 2022 and unemployment was 3.1% in 2022.")
    got = _subjects(text)
    assert got["28.6%"] == "Moldova" and got["3.1%"] == "Moldova"


def test_a_data_label_in_the_second_countrys_paragraph_stays_there():
    text = ("Peru is a mining economy. Peru is popular with tourists.\n\n"
            "Turning to Jamaica. The unemployment rate (ILO modeled) was 8.4% in 2021.")
    assert _subjects(text)["8.4%"] == "Jamaica"


def test_browser_line_endings_keep_paragraphs():
    # A textarea posts CRLF; the paragraph rule must still see the paragraph.
    text = ("Peru is a mining economy. Peru is popular with tourists.\r\n\r\n"
            "Turning to Jamaica. The unemployment rate (ILO modeled) was 8.4% in 2021.")
    assert _subjects(text)["8.4%"] == "Jamaica"


def test_a_head_count_beside_a_dollar_clause_is_not_dollars():
    import source_network as sn
    from claim_analysis import analyze_claims
    from prose import plain_prose
    text = plain_prose("Fiji is a small island state. The population was 0.9 million in 2020, "
                       "and GDP in current US dollars was $4.5 billion in 2020.")
    for c in sn._prepare_claims(analyze_claims(text)["claims"], text):
        if "0.9 million" in c["numbers"]:
            dec = sn.decompose_claim(c, doc_text=text,
                                     doc_primary_entity=sn.extract_doc_primary_entity(text))
            assert dec.unit == "count"
            return
    raise AssertionError("figure not found")


def test_a_chain_of_change_verbs_stays_real_growth():
    import source_network as sn
    s = "Real GDP expanded 6.1% in 2018, eased to 3.0% in 2019 as trade cooled, and recovered to 5.2% in 2021."
    assert sn._is_real_growth(s, "3.0%", sn._clause_holding(s, "3.0%"))
    # A reason clause between the rates ("as trade cooled") can name another
    # measure ("as investment cooled"), so the chain stops there: unchecked,
    # never misread.
    assert not sn._is_real_growth(s, "5.2%", sn._clause_holding(s, "5.2%"))


def test_a_change_verb_on_another_measure_is_not_growth():
    import source_network as sn
    s = "Real GDP grew 4.0% in 2019, while inflation slowed to 2.1% in 2019."
    assert not sn._is_real_growth(s, "2.1%", sn._clause_holding(s, "2.1%"))


def test_a_lead_in_before_a_colon_is_not_the_subject():
    got = _subjects("Ghana is a gold and cocoa exporter.\n\n"
                    "Living standards improved: GDP per capita reached $2,260 in 2022.")
    assert got["$2,260"] == "Ghana"


def test_a_plural_forecaster_marks_a_forecast():
    from claim_analysis import analyze_claims
    claims = analyze_claims("Economists expect inflation of 4.1% next year in Brazil.")["claims"]
    assert any(c.get("is_prediction") for c in claims if "4.1%" in " ".join(c["numbers"]))


def test_a_wall_of_rates_does_not_recurse_without_bound():
    import time
    import source_network as sn
    s = "Real GDP grew 1.0% in 2001, " + ", ".join(f"slowed to {i % 9}.{i % 7}%" for i in range(3000)) + "."
    t = time.time()
    sn._is_real_growth(s, "8.6%", sn._clause_holding(s, "8.6%"))
    assert time.time() - t < 2.0


def test_a_named_clause_beats_an_opening_pronoun():
    got = _subjects("Chile has done well.\n\nIts economy grew 2.4% in 2018, while Peru grew 4.0% in 2018.")
    assert got["4.0%"] == "Peru" and got["2.4%"] == "Chile"


def test_a_bare_possessive_country_carries_the_measure():
    import source_network as sn
    s = "Chile's inflation was 7.6% in 2023, whereas Peru's reached 6.3% in 2023."
    assert not sn._clause_states_another(s, "6.3%", s.find("6.3%"), sn._WB_INDICATOR_WORDS["FP.CPI.TOTL.ZG"])


def test_a_quarter_as_a_fraction_is_not_a_period():
    import source_network as sn
    assert sn._FRACTION_QUARTER_RE.search("so it keeps more than a quarter of every dollar it sells")
    assert not sn._FRACTION_QUARTER_RE.sub("", "net income for the quarter was $5 billion") \
        == "net income for  was $5 billion"
    assert "quarter" in sn._FRACTION_QUARTER_RE.sub("", "a quarter of the year's sales came in Q4, the quarter")


def test_a_past_by_year_is_not_a_forecast():
    import datetime
    from claim_analysis import analyze_claims
    past = analyze_claims("Exports were $4.1 billion in 2016 and had risen to $5.0 billion by 2022.")["claims"]
    assert not any(c.get("is_prediction") for c in past)
    ahead = datetime.date.today().year + 3
    future = analyze_claims(f"Exports should reach $9.0 billion by {ahead}.")["claims"]
    assert any(c.get("is_prediction") for c in future)


def test_income_per_person_is_sent_to_the_world_bank():
    import source_network as sn
    from claim_analysis import analyze_claims
    text = "Italy is a large economy.\n\nIncome per person fell from $33,813 in 2019 to $32,091 in 2020."
    for c in sn._prepare_claims(analyze_claims(text)["claims"], text):
        if "$32,091" in c["numbers"]:
            dec = sn.decompose_claim(c, doc_text=text, doc_primary_entity=sn.extract_doc_primary_entity(text))
            assert sn._wb_indicator_for(dec)[0] == "NY.GDP.PCAP.CD"
            return
    raise AssertionError("figure not found")


def test_bare_growth_in_an_economy_answer_confirms_but_never_refutes():
    import source_network as sn
    from claim_analysis import analyze_claims
    text = "Peru's economy is mining-led.\n\nGrowth has been modest: 2.2% in 2019."
    for c in sn._prepare_claims(analyze_claims(text)["claims"], text):
        if "2.2%" in c["numbers"]:
            dec = sn.decompose_claim(c, doc_text=text, doc_primary_entity=sn.extract_doc_primary_entity(text))
            assert sn._wb_indicator_for(dec)[0] == "NY.GDP.MKTP.KD.ZG" and dec.confirm_only
            return
    raise AssertionError("figure not found")


def test_a_heading_word_is_not_a_subject():
    got = _subjects("Peru is a mining economy.\n\n**Jobs**\n- Unemployment was 3.9% in 2019.")
    assert got["3.9%"] == "Peru"


def test_another_measure_with_a_change_verb_is_not_gdp_growth():
    import source_network as sn
    for s, r in [("Spain's real GDP grew 2.1% in 2023, and investment rose 8% in 2023.", "8%"),
                 ("Real GDP grew 3.0% in 2022, while consumer spending climbed 4.4% in 2022.", "4.4%")]:
        assert not sn._is_real_growth(s, r, sn._clause_holding(s, r)), s
    s = "Real GDP grew 7.4% in 2019, slowed to 2.9% in 2020."
    assert sn._is_real_growth(s, "2.9%", sn._clause_holding(s, "2.9%"))


def test_the_growth_of_a_thing_is_not_bare_growth():
    import source_network as sn
    from claim_analysis import analyze_claims
    text = "Spain's economy is large.\n\nThe growth in tourism was 2.1% in 2023."
    for c in sn._prepare_claims(analyze_claims(text)["claims"], text):
        d = sn.decompose_claim(c, doc_text=text, doc_primary_entity=sn.extract_doc_primary_entity(text))
        assert sn._wb_indicator_for(d)[0] != "NY.GDP.MKTP.KD.ZG"


def test_confirm_only_holds_for_every_source():
    import source_network as sn
    d = sn.ClaimDecomposition(subject="Peru", metric="growth", value=2.0, raw_value="2.0%",
                              unit="percent", time_period="2019", sentence="Growth was 2.0% in 2019.")
    d.confirm_only = True
    out = sn._timed_verify(lambda _d: sn.SourceResult(source_name="Wikipedia", match_type="contradicted",
                                                      source_value=5.0, confidence=0.9), d)
    assert out.match_type == "no_data"


def test_a_short_lead_in_is_not_the_subject():
    import source_network as sn
    assert sn.extract_subject("", "Put simply: Peru has grown fast.") == "Peru"
    assert sn.extract_subject("", "Kenya: inflation was high.") == "Kenya"


def test_a_rate_after_filler_continues_its_series():
    import source_network as sn
    for s, r in [("Real GDP shrank by -0.4% in 2015, then grew 3.9% in 2019 and 4.1% in 2024.", "4.1%"),
                 ("Real GDP grew 4.5% in 2019 and 3.2% in 2023, but only 0.8% in 2024.", "0.8%")]:
        assert sn._is_real_growth(s, r, sn._clause_holding(s, r)), s
    s = "Real GDP grew 3.0% in 2022, and inflation 8.1% in 2022."
    assert not sn._is_real_growth(s, "8.1%", sn._clause_holding(s, "8.1%"))


def test_a_figures_size_decides_total_or_per_person():
    got = _wb_ids("Chile is rich.\n\nThe economy grew from $250.1 billion in 2016 to $301.0 billion in 2022, "
                  "and income per person reached $15,356 in 2022.")
    assert got["$301.0 billion"] == "NY.GDP.MKTP.CD" and got["$15,356"] == "NY.GDP.PCAP.CD"


def test_a_head_count_in_a_population_sentence_is_the_population():
    got = _wb_ids("Chile is rich.\n\nThe population went from 18.1 million in 2016 to 19.6 million in 2022, "
                  "and income per person rose.")
    assert got["19.6 million"] == "SP.POP.TOTL"


def test_a_country_right_next_to_its_figure_owns_it():
    got = _each("Two neighbours.\n\nUnemployment: Chile 7.9% in 2022, Peru 4.4% in 2022.", "subject")
    assert got["4.4%"] == "Peru" and got["7.9%"] == "Chile"
    got = _each("Two neighbours.\n\nUnemployment was 7.9% in 2022 in Chile and 4.4% in 2022 in Peru.", "subject")
    assert got["4.4%"] == "Peru"


def _each(text, field):
    """Each figure decomposed on its own, as the pipeline does."""
    import source_network as sn
    from claim_analysis import analyze_claims
    out = {}
    for c in sn._prepare_claims(analyze_claims(text)["claims"], text):
        for n in c["numbers"]:
            d = sn.decompose_claim({**c, "numbers": [n]}, doc_text=text,
                                   doc_primary_entity=sn.extract_doc_primary_entity(text))
            out[n] = getattr(d, field)
    return out


def _wb_ids(text):
    import source_network as sn
    from claim_analysis import analyze_claims
    out = {}
    for c in sn._prepare_claims(analyze_claims(text)["claims"], text):
        for n in c["numbers"]:
            d = sn.decompose_claim({**c, "numbers": [n]}, doc_text=text,
                                   doc_primary_entity=sn.extract_doc_primary_entity(text))
            out[n] = sn._wb_indicator_for(d)[0]
    return out


# ------------------------------------------------ v28 classes, tested on new wording

def test_a_bold_country_label_heads_its_section():
    text = ("Monaco is tiny next to France.\n\n**France.** The economy grew 2.5% in 2022, and "
            "unemployment was 7.3% in 2022.\n\n**Monaco.** Prices rose 5.0% in 2022.")
    got = _each(_plain(text), "subject")
    assert got["7.3%"] == "France" and got["5.0%"] == "Monaco"


def test_a_heading_country_runs_until_the_next_heading():
    text = ("Ghana and Togo compared.\n\n## Ghana\n- Inflation: 31.7% in 2022\n\n## Togo\n"
            "- Inflation: 7.6% in 2022\n- Unemployment: 1.7% in 2022")
    got = _each(_plain(text), "subject")
    assert got["31.7%"] == "Ghana" and got["1.7%"] == "Togo"


def test_its_after_a_comparison_is_the_sentence_subject():
    text = ("Fiji grew faster.\n\nFiji's economy was $5.0 billion in 2022, the same level as "
            "Samoa in 2015, but larger in people. Its population was 0.9 million in 2022.")
    assert _each(_plain(text), "subject")["0.9 million"] == "Fiji"


def test_saint_martin_with_a_hyphen_is_the_territory():
    text = ("Saint-Martin, the French part of the island, lives on tourism, with close ties to France.\n\n"
            "People could expect to live 80.1 years in 2019.")
    assert _each(_plain(text), "subject")["80.1 years"] != "France"


def test_a_country_that_grew_is_its_economy():
    import source_network as sn
    for s, r in [("Grenada grew 6.4% in 2015.", "6.4%"), ("Eswatini grew only 0.1% in 2018.", "0.1%"),
                 ("Costa Rica's economy expanded by 5.5% in 2022.", "5.5%")]:
        assert sn._is_real_growth(s, r, sn._clause_holding(s, r)), s
    for s, r in [("Kenya grew its exports 8.0% in 2022.", "8.0%"), ("Kenya grew tea output 4.0% in 2021.", "4.0%")]:
        assert not sn._is_real_growth(s, r, sn._clause_holding(s, r)), s


def test_a_word_that_never_acts_is_not_the_subject():
    got = _each(_plain("Uruguay is a small, stable economy.\n\nGrowth: Real GDP rose 0.4% in 2015."), "subject")
    assert got["0.4%"] == "Uruguay"
    got = _each(_plain("Kenya is growing fast.\n\nNairobi has a population of 4.4 million in 2019."), "subject")
    assert got["4.4 million"] == "Nairobi"


# ------------------------------------------------ v29 classes, tested on new wording

def test_the_gambia_heading_with_its_article_heads_its_section():
    text = ("Senegal and its neighbour.\n\n## Senegal\n- Inflation was 9.7% in 2022.\n\n"
            "## The Gambia\n- Inflation was 11.5% in 2022.")
    assert _each(_plain(text), "subject")["11.5%"] == "Gambia"


def test_us_dollars_never_name_the_subject():
    text = "Mostly, yes.\n\nHow wealthy is it? GDP in current US dollars was $6.1 billion in 2021."
    assert _each(_plain(text), "subject")["$6.1 billion"] != "United States"


def test_a_demonym_names_its_country():
    text = "Two neighbours.\n\nSerbia grew 2.5% in 2023. Croatian inflation reached 8.4% in 2023."
    assert _each(_plain(text), "subject")["8.4%"] == "Croatia"


def test_the_paragraphs_country_before_the_documents():
    text = ("Spain is Europe's tourism giant, and Portugal is smaller.\n\n"
            "Start with Portugal. Its population was 10.4 million in 2022. Inflation was 7.8% in 2022.")
    assert _each(_plain(text), "subject")["7.8%"] == "Portugal"


def test_a_country_its_paragraph_names_keeps_its_clause_figures():
    text = ("Honduras and Belize compared.\n\nHonduras had income per person of $2,735 in 2018. "
            "Belize had only 0.4 million people in 2024, and income per person of $6,012 in 2018.")
    assert _each(_plain(text), "subject")["$6,012"] == "Belize"


def test_the_faroes_are_the_faroe_islands():
    text = ("Italy and the Faroe Islands.\n\nItaly's GDP was $2.38 trillion in 2024.\n\n"
            "Per person, GDP per capita was $74,175 in 2024 for the Faroes.")
    assert _each(_plain(text), "subject")["$74,175"] == "Faroe Islands"


def _placed(sentence, paragraph, label=""):
    import source_network as sn
    d = sn.ClaimDecomposition(subject="x", metric="inflation", value=7.4, raw_value="7.4%",
                              unit="percent", time_period="2021", sentence=sentence)
    d.place_paragraph, d.place_label = paragraph, label
    return d


def test_a_refutation_needs_its_place_where_the_figure_is_written():
    import source_network as sn
    # The sentence names the country, and only it.
    assert sn._place_written(_placed("Kenya's inflation was 7.4% in 2021.", "p"), "Kenya")
    # The sentence names two: which one the figure belongs to is a reading.
    assert not sn._place_written(_placed(
        "Zambia's rate was 6.0% in 2020, whereas Eswatini's was 22.7% in 2016.", "p"), "Zambia")
    # A demonym names its country ("Croatian inflation" went to North Macedonia).
    assert not sn._place_written(_placed("Croatian inflation was 10.8% in 2022.", "p"),
                                 "North Macedonia")
    # The sentence names none: the section label or a one-country paragraph settles it.
    bare = "Inflation was 7.4% in 2021."
    assert sn._place_written(_placed(bare, "Inflation was 7.4% in 2021.", "Gambia"), "Gambia")
    lead = _placed(bare, "Peru grew. " + bare)
    lead.place_doc_lead = "Peru"
    lead.doc_country_counts = {"Peru": 2, "Chile": 1}
    assert sn._place_written(lead, "Peru")
    # The v29 Gambia section bound to South Africa: neither settles it.
    assert not sn._place_written(_placed(bare, bare, ""), "South Africa")
    assert not sn._place_written(_placed(bare, "Unlike Chile, Peru grew. " + bare), "Peru")
    # "GDP in current US dollars": currency is not a country.
    assert not sn._place_written(_placed("GDP in current US dollars was $5.7 billion in 2019.", "p"),
                                 "United States")
    # An answer about one country: "**People:** 7.4 million in 2017" under an
    # intro naming Belgium once. A document naming two settles nothing.
    one = _placed(bare, bare)
    one.place_doc_countries = frozenset({"Belgium"})
    assert sn._place_written(one, "Belgium")
    two = _placed(bare, bare)
    two.place_doc_countries = frozenset({"Gambia", "South Africa"})
    assert not sn._place_written(two, "South Africa")
    # v30: the sentence names one country, the figure's own clause none.
    for sentence, raw, wrong in [
            ("Prices rose 5.6% in 2020, which tracked Indian prices, and eased to 4.2% in 2023.",
             "4.2%", "India"),
            ("It is smaller than Moldova's, yet its GDP per capita was $170,663 in 2017.",
             "$170,663", "Moldova"),
            ("GDP per capita was $48,538 in 2018, whereas Timor-Leste's was $1,266 in 2017.",
             "$48,538", "Timor-Leste")]:
        d = _placed(sentence, "p")
        d.raw_value = raw
        assert not sn._place_written(d, wrong), sentence
    after = _placed("Growth was 5.1% in 2019 in Peru, while Chile lagged.", "p")
    after.raw_value = "5.1%"
    assert sn._place_written(after, "Peru")
    # v30: a paragraph of Namibia's answer that names only Germany, in passing.
    aside = _placed(bare, "Ties to Germany run deep. " + bare)
    aside.place_doc_countries = frozenset({"Namibia", "Germany"})
    aside.place_doc_lead = "Namibia"
    aside.doc_country_counts = {"Namibia": 3, "Germany": 1}
    assert not sn._place_written(aside, "Germany")
    aside.place_paragraph = "Namibia's jobs market is weak. " + bare
    assert sn._place_written(aside, "Namibia")
    # Built without a document: no evidence either way.
    d = _placed(bare, None)
    assert sn._place_written(d, "South Africa")


def test_the_place_is_read_from_the_document():
    import source_network as sn
    text = "## The Gambia\n\nInflation was 7.4% in 2021 and 11.5% in 2022.\n"
    d = sn.decompose_claim({"sentence": "Inflation was 7.4% in 2021 and 11.5% in 2022.",
                            "numbers": ["7.4%"]}, doc_text=text)
    assert d.place_label == "Gambia"
    assert "7.4%" in d.place_paragraph
    assert d.place_doc_countries == frozenset({"Gambia"})
    d = sn.decompose_claim({"sentence": "GDP in current US dollars was $5.7 billion in 2019.",
                            "numbers": ["$5.7 billion"]},
                           doc_text="GDP in current US dollars was $5.7 billion in 2019.")
    assert d.place_doc_countries == frozenset()


def test_an_aside_or_a_comparison_is_not_the_figures_place():
    import source_network as sn
    for clause, raw in [
            ("Real GDP growth was 6.2% in 2018 (stronger than in Germany, its largest partner).", "6.2%"),
            ("The modeled unemployment rate, well above Mexico's, was 10.5% in 2022", "10.5%"),
            (("The Pacific nation, whose compact with the United States supplies much of its "
             "funding, saw real GDP growth of 5.5% in 2018"), "5.5%"),
            ("GDP: $8.6 billion in 2016, similar to Mali's despite the smaller economy.", "$8.6 billion")]:
        assert sn._place_in_clause(clause, raw) == set(), clause
    assert sn._place_in_clause("Kenya's inflation was 7.4% in 2021.", "7.4%") == {"Kenya"}
    assert sn._place_in_clause("Inflation in Peru, at 3.2% in 2019, was low.", "3.2%") == {"Peru"}


def test_a_section_labelled_for_another_country_rules_out_a_refutation():
    import source_network as sn
    # v31: "## Djibouti" then "population was 1.0 million in 2016", the
    # paragraph naming Bahrain only as "well below Bahrain's".
    d = _placed("Population was 1.0 million in 2016.",
                "Population was 1.0 million in 2016. Life expectancy was well below Bahrain's.",
                "Djibouti")
    d.raw_value = "1.0 million"
    d.place_doc_lead = "Bahrain"
    assert not sn._place_written(d, "Bahrain")
    assert sn._place_written(d, "Djibouti")


def test_a_country_outside_the_figures_clause_does_not_settle_it():
    import source_network as sn
    d = _placed("Real GDP growth was 3.0% in 2024, steady, and tied closely to demand in Germany.",
                "Real GDP growth was 3.0% in 2024, steady, and tied closely to demand in Germany.")
    d.raw_value = "3.0%"
    d.place_doc_lead = "Germany"
    d.doc_country_counts = {"Germany": 1}
    assert not sn._place_written(d, "Germany")
    # The opening country leads only when it is also the one named most.
    bare = "Inflation was 7.4% in 2021."
    p = _placed(bare, "Exports go to Germany. " + bare)
    p.place_doc_lead = "Germany"
    p.doc_country_counts = {"Germany": 1, "North Macedonia": 3}
    assert not sn._place_written(p, "Germany")
    p.doc_country_counts = {"Germany": 3, "Austria": 1}
    assert sn._place_written(p, "Germany")


def test_a_place_the_checker_cannot_read_is_unsettled():
    import source_network as sn
    for clause in ["Unemployment was 26.4% in 2021 in the Palestinian territories",
                   "Maldivian GDP per capita was $10,176 in 2021",
                   "Growth in Gaza was 5.0% in 2019",
                   "The population of Nairobi was 4.4 million in 2019"]:
        assert sn._unread_place(clause), clause
    for clause in ["Kenya's inflation was 7.4% in 2021.", "Real GDP growth was 3.9% in 2015",
                   "Consumer price inflation was 4.1% in January 2020",
                   "GDP per capita in current US dollars was $5,000 in 2019"]:
        assert not sn._unread_place(clause), clause
    d = _placed("Unemployment was 26.4% in 2021 in the Palestinian territories.",
                "Unemployment was 26.4% in 2021 in the Palestinian territories.")
    d.raw_value = "26.4%"
    d.place_doc_countries = frozenset({"Pakistan"})
    assert not sn._place_written(d, "Pakistan")


def test_one_country_under_two_spellings_is_one_place():
    import source_network as sn
    assert sn._same_place("Türkiye", "Turkey")
    assert sn._same_place("Turkiye", "Türkiye")
    assert not sn._same_place("Bahrain", "Djibouti")
    assert sn._place_key("Côte D'Ivoire") == "cote d'ivoire"
    assert sn._place_key("The Bahamas") == "bahamas"


def test_review_shapes_do_not_settle_a_place():
    import source_network as sn
    # Review 2026-11-28: a figure after a comparison may be the compared
    # country's, and a bare place the checker cannot read is unsettled.
    for sentence, raw, country in [
            ("Peru's inflation was lower than Germany's 5.0% in 2020.", "5.0%", "Peru"),
            ("Compared with Germany's 5.0%, Peru's inflation was 3.0% in 2020.", "5.0%", "Peru"),
            ("Peru's inflation was 3.0% in 2020, versus Germany's 5.0%.", "5.0%", "Peru"),
            ("Scotland recorded inflation of 5.0% in 2020.", "5.0%", "United Kingdom"),
            ("Northern Ireland saw inflation of 5.0% in 2020.", "5.0%", "Ireland"),
            ("New Mexico saw GDP growth of 5.0% in 2020.", "5.0%", "Mexico")]:
        d = _placed(sentence, sentence)
        d.raw_value = raw
        d.place_doc_countries = frozenset({country})
        assert not sn._place_written(d, country), sentence
    for sentence, raw in [("Peru's inflation was 3.0% in 2020, versus Germany's 5.0%.", "3.0%"),
                          ("Real GDP growth was 3.9% in 2015.", "3.9%"),
                          ("Life expectancy at birth was 67.8 years in 2023.", "67.8 years")]:
        d = _placed(sentence, sentence)
        d.raw_value = raw
        d.place_doc_countries = frozenset({"Peru"})
        assert sn._place_written(d, "Peru"), sentence
