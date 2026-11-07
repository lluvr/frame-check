"""FRED and Wikidata, checked the way the other sources are: the same entity,
metric, unit and period, and a stated reason when a figure is wrong. No
network here.
"""

import urllib.parse

import pytest

import source_network as sn


def claim(sentence, raw, **fields):
    return sn.decompose_claim({"sentence": sentence, "numbers": [raw], **fields})


# ---------------------------------------------------------------- FRED

@pytest.fixture
def fred(monkeypatch):
    """Annual (or monthly) values per series, keyed by year or (year, month)."""
    monkeypatch.setenv("FRED_API_KEY", "test")
    data = {}
    urls = []

    def fake(url, *a, **k):
        urls.append(url)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        series = data.get(q["series_id"], {})
        start, end = q["observation_start"][:10], q["observation_end"][:10]
        rows = []
        for key, value in sorted(series.items()):
            date = (f"{key[0]}-{key[1]:02d}-01" if isinstance(key, tuple) else f"{key}-01-01")
            if start <= date <= end:
                rows.append({"date": date, "value": str(value)})
        return {"observations": rows}

    monkeypatch.setattr(sn, "_fetch_json", fake)
    return data, urls


def test_fred_confirms_the_named_years_average(fred):
    data, urls = fred
    data["UNRATE"] = {2022: 3.6, 2023: 3.6, 2024: 4.0}
    r = sn.verify_fred(claim("US unemployment averaged 3.6% in 2023.", "3.6%"))
    assert r.match_type == "exact"
    assert "frequency=a" in urls[0]


def test_fred_refutes_a_wrong_rate_and_names_its_year(fred):
    data, _ = fred
    data["UNRATE"] = {2022: 3.6, 2023: 3.6, 2024: 4.0}
    r = sn.verify_fred(claim("US unemployment averaged 4.0% in 2023.", "4.0%"))
    assert r.match_type == "contradicted"
    assert "2024 figure" in r.source_text


def test_fred_rate_tolerance_is_in_points_not_percent(fred):
    data, _ = fred
    data["UNRATE"] = {2023: 3.6}
    assert sn.verify_fred(claim("US unemployment averaged 3.9% in 2023.", "3.9%")).match_type == "contradicted"
    assert sn.verify_fred(claim("US unemployment averaged about 4% in 2023.", "4%")).match_type == "close"


def test_fred_inflation_is_the_yearly_change_in_prices(fred):
    data, urls = fred
    data["CPIAUCNS"] = {2023: 4.12}
    r = sn.verify_fred(claim("US inflation was 4.1% in 2023.", "4.1%"))
    assert r.match_type in ("exact", "close")
    assert "units=pc1" in urls[0]


def test_fred_gdp_in_dollars(fred):
    data, _ = fred
    data["GDP"] = {2023: 27720.709}
    r = sn.verify_fred(claim("US GDP was $27.7 trillion in 2023.", "$27.7 trillion"))
    assert r.match_type in ("exact", "close")


def test_fred_without_a_year_can_confirm_but_not_refute(fred):
    data, _ = fred
    data["UNRATE"] = {2024: 4.0, 2025: 4.2}
    assert sn.verify_fred(claim("US unemployment is 4.2%.", "4.2%")).match_type == "exact"
    assert sn.verify_fred(claim("US unemployment is 6.5%.", "6.5%")).match_type == "no_data"


def test_fred_reads_a_named_month(fred):
    data, urls = fred
    data["UNRATE"] = {(2023, 3): 3.5}
    r = sn.verify_fred(claim("US unemployment was 3.5% in March 2023.", "3.5%"))
    assert r.match_type == "exact"
    assert "frequency=m" in urls[0]


def test_fred_ignores_a_sentence_it_has_no_series_for(fred):
    assert sn.verify_fred(claim("US wheat output was 1.8 billion bushels in 2023.", "1.8 billion")).match_type == "no_data"


# ---------------------------------------------------------------- Wikidata

def _quantity(amount, unit_q, year=None):
    statement = {
        "rank": "normal",
        "mainsnak": {"datavalue": {"value": {
            "amount": f"+{amount}", "unit": f"http://www.wikidata.org/entity/{unit_q}",
        }}},
    }
    if year:
        statement["qualifiers"] = {"P585": [{"datavalue": {"value": {
            "time": f"+{year}-01-01T00:00:00Z"}}}]}
    return statement


@pytest.fixture
def wikidata(monkeypatch):
    monkeypatch.setattr(sn, "_WIKIDATA_CACHE", {})
    entities = {}

    def fake(url, *a, **k):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        if q["action"] == "wbsearchentities":
            term = q["search"].lower()
            hits = [
                {"id": qid, "label": e["label"]} for qid, e in entities.items()
                if term in e["label"].lower() or term in [a.lower() for a in e.get("aliases", [])]
            ]
            return {"search": hits}
        ids = q["ids"].split("|")
        return {"entities": {
            qid: {
                "labels": {"en": {"value": entities[qid]["label"]}},
                "aliases": {"en": [{"value": a} for a in entities[qid].get("aliases", [])]},
                "claims": entities[qid]["claims"],
            } for qid in ids if qid in entities
        }}

    monkeypatch.setattr(sn, "_fetch_json", fake)
    return entities


def test_wikidata_confirms_an_area_in_the_same_unit(wikidata):
    wikidata["Q5513"] = {"label": "Lake Baikal", "claims": {"P2046": [_quantity(31722, "Q712226")]}}
    r = sn.verify_wikidata(claim("Lake Baikal covers 31,722 km2.", "31,722"))
    assert r.match_type == "exact"
    assert r.source_name == "Wikidata"


def test_wikidata_converts_units(wikidata):
    wikidata["Q5513"] = {"label": "Lake Baikal", "claims": {"P2046": [_quantity(31722, "Q712226")]}}
    r = sn.verify_wikidata(claim("Lake Baikal covers about 12,248 square miles.", "12,248"))
    assert r.match_type in ("exact", "close")


def test_wikidata_names_a_unit_slip(wikidata):
    wikidata["Q5513"] = {"label": "Lake Baikal", "claims": {"P2046": [_quantity(31722, "Q712226")]}}
    r = sn.verify_wikidata(claim("Lake Baikal covers 31,722 square miles.", "31,722"))
    assert r.match_type == "contradicted"
    assert "square kilometres" in r.source_text


def test_wikidata_refutes_a_wrong_length(wikidata):
    wikidata["Q5513"] = {"label": "Lake Baikal", "claims": {"P2043": [_quantity(636, "Q828224")]}}
    assert sn.verify_wikidata(claim("Lake Baikal is 890 km long.", "890")).match_type == "contradicted"


def test_wikidata_feet_for_metres(wikidata):
    wikidata["Q1"] = {"label": "Gateway Arch", "claims": {"P2048": [_quantity(192, "Q11573")]}}
    r = sn.verify_wikidata(claim("The Gateway Arch is 630 metres tall.", "630"))
    assert r.match_type == "contradicted"
    assert "feet" in r.source_text


def test_wikidata_height_counts_elevation_too(wikidata):
    wikidata["Q7296"] = {"label": "Mount Kilimanjaro", "aliases": ["Kilimanjaro"],
                         "claims": {"P2044": [_quantity(5895, "Q11573")]}}
    assert sn.verify_wikidata(claim("Kilimanjaro rises 19,341 feet tall.", "19,341")).match_type in ("exact", "close")


def test_wikidata_skips_a_namesake_without_the_property(wikidata):
    wikidata["Q925"] = {"label": "Mercury", "claims": {}}
    wikidata["Q308"] = {"label": "Mercury", "claims": {"P2120": [_quantity(2439.7, "Q828224")]}}
    assert sn.verify_wikidata(claim("Mercury has a radius of 2,440 km.", "2,440")).match_type in ("exact", "close")


def test_wikidata_radius_is_not_diameter(wikidata):
    wikidata["Q308"] = {"label": "Mercury", "claims": {"P2386": [_quantity(4879.4, "Q828224")]}}
    assert sn.verify_wikidata(claim("Mercury has a radius of 4,879 km.", "4,879")).match_type == "no_data"


def test_wikidata_needs_a_unit_for_a_measurement(wikidata):
    wikidata["Q5513"] = {"label": "Lake Baikal", "claims": {"P2043": [_quantity(636, "Q828224")]}}
    assert sn.verify_wikidata(claim("Lake Baikal is about 636 long.", "636")).match_type == "no_data"


def test_wikidata_a_contested_measurement_is_not_refuted(wikidata):
    wikidata["Q1"] = {"label": "Mekong", "claims": {"P2043": [_quantity(4909, "Q828224")]}}
    assert sn.verify_wikidata(claim("The Mekong is 4,350 km long.", "4,350")).match_type == "no_data"


def test_wikidata_employees_by_year(wikidata):
    wikidata["Q1"] = {"label": "Acme Corporation", "claims": {"P1128": [
        _quantity(85000, "Q199", 2023), _quantity(90400, "Q199", 2024)]}}
    assert sn.verify_wikidata(claim("Acme Corporation had 90,400 employees in 2024.", "90,400")).match_type == "exact"
    assert sn.verify_wikidata(claim("Acme Corporation had 120,000 employees in 2024.", "120,000")).match_type == "contradicted"


def test_wikidata_a_population_without_a_year_only_confirms(wikidata):
    wikidata["Q1"] = {"label": "Lyon", "claims": {"P1082": [_quantity(522250, "Q199", 2021)]}}
    assert sn.verify_wikidata(claim("Lyon has a population of 522,250 people.", "522,250")).match_type == "exact"
    assert sn.verify_wikidata(claim("Lyon has a population of 900,000 people.", "900,000")).match_type == "no_data"


def test_wikidata_routing():
    assert sn.verify_wikidata in sn._classify_and_route(claim("Lake Baikal is 636 km long.", "636"))
    assert sn.verify_wikidata not in sn._classify_and_route(claim("Germany's population was 84 million in 2023.", "84 million"))


def test_wikidata_is_a_known_source_name():
    telemetry = pytest.importorskip("telemetry")  # web-app only
    assert telemetry.SOURCE_NAME_CANONICAL["Wikidata"] in telemetry.SOURCE_NAMES


def test_fred_only_answers_figures_that_name_the_us(fred):
    assert not sn._fred_applies(claim("GDP was $16.4 billion in 2025.", "$16.4 billion"))
    assert not sn._fred_applies(claim("Rwanda's GDP was $16.4 billion in 2025.", "$16.4 billion"))
    assert sn._fred_applies(claim("US GDP was $27.7 trillion in 2023.", "$27.7 trillion"))
    assert sn._fred_applies(claim("The U.S. unemployment rate averaged 3.6% in 2023.", "3.6%"))


def test_fred_a_gap_of_orders_of_magnitude_is_another_economy(fred):
    data, _ = fred
    data["GDP"] = {2025: 30861.29}
    assert sn.verify_fred(claim("US GDP was $16.4 billion in 2025.", "$16.4 billion")).match_type == "no_data"


def test_wikidata_refutes_only_a_subject_named_in_the_sentence(wikidata):
    wikidata["Q1"] = {"label": "Pluto", "claims": {"P2120": [_quantity(1188.3, "Q828224")]}}
    d = claim("Ganymede: radius of 2,631 km.", "2,631")
    d.subject = "Pluto"
    assert sn.verify_wikidata(d).match_type == "no_data"


def test_wikidata_a_gap_beyond_a_unit_slip_is_another_thing(wikidata):
    wikidata["Q419"] = {"label": "Peru", "claims": {"P2046": [_quantity(1285216, "Q712226")]}}
    d = claim("Lake Titicaca (Peru/Bolivia): surface area of 8,372 square kilometres.", "8,372")
    d.subject = "Peru"
    assert sn.verify_wikidata(d).match_type == "no_data"


def test_wikidata_a_depth_is_not_a_length():
    d = claim("Lake Superior reaches a maximum depth of 1,332 feet.", "1,332")
    assert not sn._wikidata_applies(d)


def test_fred_reads_a_document_about_the_us_economy():
    doc = ("2023 was a year of cooling inflation.\n\nThe unemployment rate averaged 3.6% for "
           "the year. The Fed kept tightening. Mortgages got expensive, according to Freddie Mac.\n")
    claims = sn._prepare_claims(
        [{"sentence": "The unemployment rate averaged 3.6% for the year.", "numbers": ["3.6%"]}], doc,
    )
    d = sn.decompose_claim(claims[0], doc_text=doc)
    assert sn._fred_applies(d)


def test_fred_stays_out_of_a_document_about_another_country():
    doc = ("Brazil had a hard year, and the central bank kept tightening like the Fed.\n\n"
           "The unemployment rate averaged 7.8% for the year.\n")
    claims = sn._prepare_claims(
        [{"sentence": "The unemployment rate averaged 7.8% for the year.", "numbers": ["7.8%"]}], doc,
    )
    assert not sn._fred_applies(sn.decompose_claim(claims[0], doc_text=doc))


def test_a_structured_disagreement_vetoes_a_loose_text_match(wikidata):
    wikidata["Q43512"] = {"label": "K2", "claims": {"P2044": [_quantity(8611, "Q11573")]}}
    d = claim("K2 (Pakistan/China): 7,611 m, the second highest on Earth.", "7,611")
    d.subject, d.metric = "K2", "height"  # as the claim reader gives them
    structured = sn.verify_wikidata(d)
    assert structured.match_type == "no_data" and structured.disagrees
    text = sn.SourceResult(source_name="Wikipedia", match_type="exact", confidence=0.7)
    assert sn._consensus_for(d, [text, structured])[0] == "unverifiable"


def test_a_parenthetical_does_not_hide_the_subject(wikidata):
    wikidata["Q29294"] = {"label": "Willis Tower", "claims": {"P2048": [_quantity(442.1, "Q11573")]}}
    d = claim("Willis Tower (Chicago) is 527 m tall.", "527")
    d.subject = "Willis Tower (Chicago)"
    assert sn.verify_wikidata(d).match_type == "contradicted"


def test_a_precise_same_year_count_is_not_close_at_one_percent(wikidata):
    wikidata["Q35765"] = {"label": "Osaka", "claims": {"P1082": [_quantity(2751862, "Q199", 2021)]}}
    r = sn.verify_wikidata(claim("Osaka had about 2.79 million people in 2021.", "2.79 million"))
    assert r.match_type not in ("exact", "close")
    assert r.disagrees


def test_a_precise_measurement_is_not_matched_loosely_in_text():
    d = claim("K2 rises 7,611 m above the sea.", "7,611")
    page = "Climbers established camp IV at 7,650 metres (25,100 ft) above sea level on K2."
    assert sn._match_in_text(page, 7611.0, d.sentence, decomp=d)[0] is None


def test_world_bank_life_expectancy_is_compared_in_years(monkeypatch):
    monkeypatch.setattr(sn, "_wb_country_code", lambda c: "JP")
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: [{"page": 1}, [{"value": 84.04, "date": "2024"}]])
    d = claim("Japan's life expectancy in 2024 was 83.2 years.", "83.2 years")
    assert sn.verify_world_bank(d).match_type == "contradicted"
    ok = claim("Japan's life expectancy in 2024 was 84.0 years.", "84.0 years")
    assert sn.verify_world_bank(ok).match_type in ("exact", "close")


def test_a_country_in_parentheses_only_locates_the_name():
    d = claim("Willis Tower (Chicago, United States) is 442 m tall.", "442")
    assert d.subject == "Willis Tower"
    d = claim("Lake Titicaca (Peru/Bolivia) covers 8,372 square kilometres.", "8,372")
    assert d.subject == "Lake Titicaca"


def test_wikidata_total_area_says_nothing_about_land_area():
    assert not sn._wikidata_applies(claim("Canada's land area is 9.98 million square kilometres.", "9.98 million"))
    assert sn._wikidata_applies(claim("Canada covers 9.98 million square kilometres.", "9.98 million"))


def test_wikidata_lookups_are_cached(wikidata, monkeypatch):
    wikidata["Q5513"] = {"label": "Lake Baikal", "claims": {"P2046": [_quantity(31722, "Q712226")],
                                                           "P2043": [_quantity(636, "Q828224")]}}
    inner = sn._fetch_json
    seen = []
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: seen.append(url) or inner(url, *a, **k))
    sn.verify_wikidata(claim("Lake Baikal covers 31,722 km2.", "31,722"))
    sn.verify_wikidata(claim("Lake Baikal is 636 km long.", "636"))
    assert len(seen) == 2


def test_a_failed_wikidata_lookup_is_not_cached(wikidata, monkeypatch):
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: None)
    sn.verify_wikidata(claim("Lake Baikal is 636 km long.", "636"))
    assert not sn._WIKIDATA_CACHE


def test_fred_reads_the_effective_funds_rate(fred):
    data, _ = fred
    data["FEDFUNDS"] = {2023: 5.02}
    r = sn.verify_fred(claim("The Fed's effective funds rate averaged 5.02% in 2023.", "5.02%"))
    assert r.match_type == "exact"


def test_a_subject_named_in_its_own_sentence_can_be_refuted_in_a_busy_document(wikidata):
    wikidata["Q1"] = {"label": "Gateway Arch", "claims": {"P2048": [_quantity(192, "Q11573")]}}
    d = claim("The Gateway Arch in St. Louis is 630 metres tall.", "630")
    d.subject_ambiguous = True  # the document names several things
    assert sn.verify_wikidata(d).match_type == "contradicted"


def test_a_measurement_stated_to_the_metre_is_not_confirmed_nine_metres_off(wikidata):
    """heldout_docs_v12: "Matterhorn: 4,487 m" (transposed digits) came back
    verified against 4,478 m, because a measurement within 0.5% was exact."""
    wikidata["Q1374"] = {"label": "Matterhorn", "claims": {"P2044": [_quantity(4478, "Q11573")]}}
    off = sn.verify_wikidata(claim("The Matterhorn has an elevation of 4,487 m.", "4,487"))
    assert off.match_type not in ("exact", "close")
    assert sn.verify_wikidata(claim("The Matterhorn has an elevation of 4,478 m.", "4,478")).match_type == "exact"
    assert sn.verify_wikidata(claim("The Matterhorn has an elevation of about 4,500 m.", "4,500")).match_type in ("exact", "close")


def test_a_survey_difference_of_a_few_metres_still_confirms(wikidata):
    wikidata["Q583"] = {"label": "Mont Blanc", "claims": {"P2044": [_quantity(4805.59, "Q11573")]}}
    assert sn.verify_wikidata(claim("Mont Blanc has an elevation of 4,808 m.", "4,808")).match_type in ("exact", "close")
