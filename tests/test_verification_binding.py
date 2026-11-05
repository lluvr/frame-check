"""A green verdict must mean the same claim, not the same digits.

Each case is a shape where the matcher could compare digits without
checking what they were digits of: a true number contradicted, or a
false one confirmed. Network calls are stubbed; the passages follow what
the live providers return.
"""

import json

import pytest

import source_network as sn
from claim_analysis import analyze_claims
from clarethium_measure import (
    _number_in_source,
    extract_numbers_for_matching,
    source_matching,
)
from framing import (
    detect_coverage,
    detect_epistemic_basis,
    detect_voice,
    framing_portrait_natural,
    temporal_orientation,
)
from source_network import (
    ClaimDecomposition,
    SourceResult,
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
        lambda req, *args, **kwargs: APPLE_REVENUE,
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


def test_sec_stated_year_still_contradicts_wrong_value(apple_sec):
    r = verify_sec_edgar(_decomp(
        "Apple's revenue in fiscal 2023 was $420 billion.", 420e9,
        metric="revenue", time_period="2023"))
    assert r.match_type == "contradicted"
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
        source_name="example-blog.test", match_type=match_type,
        source_text="reached $187.4 billion", is_web_search=True,
        confidence=0.75,
    )


@pytest.mark.parametrize("match_type", ["exact", "close", "contradicted"])
def test_web_result_alone_gives_no_verdict(match_type):
    verdict, _conf, detail = _consensus([_web(match_type)])
    assert verdict == "unverifiable"
    assert "example-blog.test" in detail


def test_web_result_does_not_dispute_a_filing():
    filing = SourceResult(
        source_name="SEC Filing", match_type="exact", confidence=0.95)
    verdict, _conf, _detail = _consensus([filing, _web("contradicted")])
    assert verdict == "verified"


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

def _token_in_source(token, source):
    return _number_in_source(extract_numbers_for_matching(token)[0], source)


@pytest.mark.parametrize("token,source,expected", [
    ("$12.5 million", "Revenue was $12.5 billion in 2023.", False),
    ("$12.5 billion", "Revenue was $12.5 million in 2023.", False),
    ("$12.5B", "Revenue was $12.5 million in 2023.", False),
    ("$12.5 million", "Revenue was $12.5 million in 2023.", True),
    ("$12.5 million", "Revenue was $12.5M in 2023.", True),
    ("$12.5 million", "Revenue was $12,500,000 in 2023.", True),
    ("$12.5 billion", "Revenue was $12.5bn in 2023.", True),
    ("$5,000", "The fee was $5,000 last year.", True),
    ("$12.5M", "Revenue was $12.5 billion in 2023.", False),
    ("$140k", "The salary was $140,000 last year.", True),
    ("$12.5 trillion", "Revenue was $12.5 thousand in 2023.", False),
    ("$12,500,000", "Revenue was $12,500,000 in 2023.", True),
    ("$12.5 million", "Revenue was $12,500,000,000 in 2023.", False),
    ("$3B2B", "The fee was $3 per seat.", True),
    ("$12.5 bn", "Revenue was $12.5 billion in 2023.", True),
])
def test_source_match_respects_scale(token, source, expected):
    assert _token_in_source(token, source) is expected


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


def test_world_bank_confirms_a_true_population(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany has a population of about 84 million.", 84e6))
    assert r.match_type == "exact"


def test_world_bank_contradicts_a_wildly_false_population(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany has a population of about 12 million.", 12e6))
    assert r.match_type == "contradicted"


def test_ten_percent_off_is_not_a_close_match(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany has a population of about 93 million.", 93e6))
    assert r.match_type == "contradicted"


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


def test_dated_gdp_mismatch_is_a_contradiction(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany's GDP in 2023 was $900 billion.", 900e9,
        metric="gdp", unit="currency", time_period="2023"))
    assert r.match_type == "contradicted"


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


# ── Metric words, company names, durations ──────────────────────────

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
    assert sn.verify_world_bank(d).match_type == "contradicted"


def test_british_spelling_is_an_area():
    d = decompose_claim({
        "sentence": "Argentina spans about 3.5 million square kilometres.",
        "numbers": ["3.5 million"],
    })
    assert d.metric == "area"
    assert "verify_world_bank" in [
        f.__name__ for f in sn._classify_and_route(d)
    ]


def test_yearless_area_mismatch_is_a_contradiction(world_bank):
    r = sn.verify_world_bank(_country(
        "Germany has an area of 500,000 square kilometres.", 500000,
        metric="area", unit="distance"))
    assert r.match_type == "contradicted"


def test_a_sentence_naming_two_years_cannot_contradict(apple_sec):
    """"Swung from a loss in fiscal 2023 to a profit in fiscal 2024" must
    not compare the second figure to the first year."""
    r = verify_sec_edgar(_decomp(
        "Apple grew after a weak fiscal 2022, with revenue of $420 billion "
        "in fiscal 2023.", 420e9, metric="revenue",
    ))
    assert r.match_type == "no_data"


def test_one_year_named_twice_still_contradicts(apple_sec):
    r = verify_sec_edgar(_decomp(
        "In fiscal 2023 Apple's revenue was $420 billion, its fiscal 2023 "
        "report said.", 420e9, metric="revenue",
    ))
    assert r.match_type == "contradicted"


# ── Voice ───────────────────────────────────────────────────────────

def test_the_us_is_not_first_person():
    text = (
        "The US unemployment rate was 3.7% in December 2023 according to "
        "the labor department. US output rose sharply over the same "
        "period and the US dollar strengthened against the euro as well."
    )
    assert detect_voice(text)["we_pct"] == 0


def test_lowercase_us_is_still_first_person():
    text = "The board told us to expect delays across the whole of the program."
    assert detect_voice(text)["we_pct"] > 0


def test_short_imperatives_count():
    text = (
        "You should buy this stock now and hold it for the long term. "
        "Do not wait. Buy today. Act now."
    )
    assert detect_voice(text)["imperative_count"] >= 3


def test_a_first_person_call_is_not_analytical():
    assert detect_voice(HERO)["voice"] != "analytical"


def test_advisory_portrait_omits_a_zero_reader_share():
    assert "0% addressed to the reader" not in _portrait(HERO)


# ── Attribution is not evidence ─────────────────────────────────────

def _portrait(text):
    return framing_portrait_natural(
        detect_coverage(text), temporal_orientation(text), detect_voice(text),
        detect_epistemic_basis(text), analyze_claims(text),
    )


def test_naming_a_company_is_not_called_evidence():
    text = (
        "Apple reported fiscal 2023 revenue of $265.6 billion. NVIDIA "
        "reported fiscal 2024 revenue of $26.97 billion."
    )
    assert "evidence-based" not in _portrait(text)


def test_attribution_sentence_counts_sentences_with_numbers():
    text = (
        "Apple reported fiscal 2023 revenue of $383.3 billion in its "
        "annual filing. Net income was $97 billion for the same period. "
        "The chief executive spoke at length about the road ahead today."
    )
    portrait = _portrait(text)
    assert "of 3 sentences" not in portrait
    assert "1 of 2 sentences with numbers" in portrait
