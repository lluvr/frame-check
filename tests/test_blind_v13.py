"""Faults from blind set v13 (heldout_docs_v13), scored before these fixes:
14 of 187 true numbers contradicted, 11 of them US macro figures read for the
wrong period. No network here.
"""

import pytest

import source_network as sn
from tests import test_blind_v12, test_fred_wikidata

# Shared stubs: pytest finds a fixture by the module attribute that holds it.
fred = test_blind_v12.fred
wikidata = test_fred_wikidata.wikidata
_quantity = test_fred_wikidata._quantity


def claim(sentence, raw, **fields):
    return sn.decompose_claim({"sentence": sentence, "numbers": [raw], **fields})


def verdict(sentence, raw, **fields):
    return sn.verify_fred(claim(sentence, raw, **fields)).match_type


# ------------------------------------------------ a month named without its year

@pytest.mark.parametrize("sentence, raw", [
    ("US CPI was up 7.0% year over year in December 2021.", "7.0%"),
    ("US CPI was up 7.0% year over year in December, the fastest pace since 1982.", "7.0%"),
    ("US CPI rose 7.0% in the twelve months through December.", "7.0%"),
])
def test_a_month_without_its_year_takes_the_year_of_the_figure(fred, sentence, raw):
    data, urls = fred
    data["CPIAUCNS"] = {2021: 4.70, (2021, 12): 7.04}
    assert verdict(sentence, raw, inherited_year="2021") in ("exact", "close")
    assert "frequency=m" in urls[-1]


def test_a_second_figure_in_a_december_sentence_is_read_in_december(fred):
    data, _ = fred
    data["CPIAUCNS"] = {2021: 4.70, (2021, 12): 7.04}
    data["CPILFENS"] = {2021: 3.57, (2021, 12): 5.48}
    sentence = ("US CPI was up 7.0% year over year in December, the fastest pace since 1982, "
                "and core CPI was up 5.5%.")
    assert verdict(sentence, "5.5%", inherited_year="2021") in ("exact", "close")


# ------------------------------------------------ the nearest cue decides

def test_an_annual_average_beside_a_december_figure_is_the_average(fred):
    data, _ = fred
    data["UNRATE"] = {2019: 3.68, (2019, 12): 3.6}
    sentence = "The US unemployment rate was 3.6% in December 2019 and averaged 3.7% for the year."
    assert verdict(sentence, "3.7%") in ("exact", "close")
    assert verdict(sentence, "3.6%") in ("exact", "close")


def test_a_year_end_figure_after_a_peak_month_is_read_in_december(fred):
    data, _ = fred
    data["DGS10"] = {2018: 2.91, (2018, 11): 3.12, (2018, 12): 2.83}
    sentence = ("The 10-year Treasury yield peaked at 3.24% in early November before falling "
                "back to end the year at 2.69%.")
    assert verdict(sentence, "2.69%", inherited_year="2018") != "contradicted"
    assert verdict(sentence, "3.24%", inherited_year="2018") != "contradicted"


def test_a_peak_is_not_refuted_by_the_months_average(fred):
    data, _ = fred
    data["MORTGAGE30US"] = {2018: 4.54, (2018, 11): 4.87}
    sentence = "Mortgage rates followed, with the 30-year fixed rate topping out at 4.94% in November."
    assert verdict(sentence, "4.94%", inherited_year="2018") != "contradicted"


def test_a_figure_a_year_earlier_is_read_a_year_earlier(fred):
    data, _ = fred
    data["UNRATE"] = {(2021, 12): 3.9, (2020, 12): 6.7, 2020: 8.1, 2021: 5.4}
    sentence = "US unemployment fell to 3.9% in December 2021 from 6.7% a year earlier."
    assert verdict(sentence, "6.7%") in ("exact", "close")


# ------------------------------------------------ no cue: December or the average

def test_a_rate_without_a_cue_is_confirmed_by_december_or_the_average(fred):
    data, _ = fred
    data["PCEPI"] = {2021: 4.04, (2021, 12): 5.8}
    assert verdict("The US PCE price index rose 5.8%.", "5.8%", inherited_year="2021") in ("exact", "close")
    assert verdict("The US PCE price index rose 4.0%.", "4.0%", inherited_year="2021") in ("exact", "close")


def test_a_rate_without_a_cue_far_from_both_is_still_refuted(fred):
    data, _ = fred
    data["PCEPI"] = {2021: 4.04, (2021, 12): 5.8}
    assert verdict("In 2021 the US PCE price index rose 9.5%.", "9.5%") == "contradicted"


# ------------------------------------------------ World Bank: a rate is not a count

def test_a_count_is_not_the_world_banks_unemployment_rate(monkeypatch):
    monkeypatch.setattr(sn, "_wb_country_code", lambda c: "US")
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: [
        {}, [{"value": 8.05, "date": "2020"}]])
    d = claim("US unemployment fell to 3.9%, and nonfarm payrolls grew by about 6.7 million "
              "in 2020.", "6.7 million")
    assert sn.verify_world_bank(d).match_type != "contradicted"


# ------------------------------------------------ a part, a multiple, another currency

def test_a_component_listed_after_including_is_a_part_of_the_total():
    sentence = ("Total revenue was $254.5 billion, including net sales of $249.6 billion and "
                "membership fees of $4.83 billion.")
    assert claim(sentence, "$4.83 billion").is_segment
    assert not claim(sentence, "$254.5 billion").is_segment


def test_a_multiple_is_not_an_amount():
    sentence = "Japan's economy is still about 2.2 times the size of Korea's."
    assert sn._is_a_ratio(sentence, "2.2")
    assert sn._is_a_ratio("Revenue grew threefold, or 3x, since 2019.", "3x")
    assert not sn._is_a_ratio("Revenue was $2.2 billion, three times last year's.", "$2.2 billion")


def test_yen_is_not_compared_with_the_world_banks_dollars(monkeypatch):
    monkeypatch.setattr(sn, "_wb_country_code", lambda c: "JP")
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: [
        {}, [{"value": 33797.1, "date": "2024"}]])
    d = claim("GDP per capita was roughly ¥33,800 in Japan in 2024.", "¥33,800")
    assert sn.verify_world_bank(d).match_type not in ("exact", "close")


# ------------------------------------------------ a qualified height needs the same qualifier

def test_a_height_to_the_tip_is_not_confirmed_by_an_unqualified_height(wikidata):
    wikidata["Q1"] = {"label": "Willis Tower", "claims": {"P2048": [_quantity(442.1, "Q11573")]}}
    d = claim("Willis Tower height to tip was 1,451 ft.", "1,451")
    d.subject, d.metric = "Willis Tower", "height"
    assert sn.verify_wikidata(d).match_type == "no_data"


def test_a_height_to_the_tip_needs_a_page_that_says_tip():
    sentence = "Willis Tower height to tip was 1,451 ft."
    page = "The 1,450-foot-tall (440 m) building would contain 109 stories."
    value, context, _ = sn._match_in_text(page, 1451, sentence, decomp=claim(sentence, "1,451"))
    assert value is None, context
    page = "Its antenna brings the height to tip to 1,729 ft, the roof is at 1,451 ft."
    sentence = "Willis Tower's roof is at 1,451 ft."
    value, _, _ = sn._match_in_text(page, 1451, sentence, decomp=claim(sentence, "1,451"))
    assert value == 1451


# ------------------------------------------------ the subject is not always the country

def test_a_citys_population_is_not_refuted_by_its_countrys(monkeypatch):
    monkeypatch.setattr(sn, "_wb_country_code", lambda c: "US")
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: [
        {}, [{"value": 331578104, "date": "2020"}]])
    d = claim("Population: 1,608,139 at the 2020 census, making it the fifth-largest city "
              "in the US.", "1,608,139", heading="Phoenix at a glance")
    d.subject = "Phoenix at a glance"
    assert sn.verify_world_bank(d).match_type != "contradicted"


# ------------------------------------------------ a document that says its figures are averages

def test_a_document_of_annual_averages_is_read_as_averages(fred):
    data, _ = fred
    data["MORTGAGE30US"] = {2022: 5.34, (2022, 12): 6.36}
    doc = ("Here are the annual averages you asked for, pulled from FRED last night.\n\n"
           "| Series | 2022 |\n|---|---|\n| 30-year fixed mortgage | 6.34% |")
    d = sn.decompose_claim({"sentence": "30-year fixed mortgage in 2022 was 6.34%.",
                            "numbers": ["6.34%"]}, doc_text=doc)
    assert sn.verify_fred(d).match_type == "contradicted"


def test_one_annual_average_does_not_make_every_figure_an_average(fred):
    data, _ = fred
    data["PCEPI"] = {2025: 2.59, (2025, 12): 2.8}
    doc = "Unemployment: the 2025 annual average was 4.3%.\nPCE inflation was 2.8%."
    d = sn.decompose_claim({"sentence": "US PCE inflation was 2.8%.", "numbers": ["2.8%"],
                            "inherited_year": "2025"}, doc_text=doc)
    assert sn.verify_fred(d).match_type in ("exact", "close")


def test_an_exact_count_is_not_close_to_another_census():
    sentence = "Population: 2,731,571 at the 2021 census, making it Canada's largest city."
    page = ("behind Mexico City, New York City, and Los Angeles, with a census population of "
            "2,794,356 as of 2021.")
    value, context, _ = sn._match_in_text(page, 2731571, sentence, decomp=claim(sentence, "2,731,571"))
    assert value is None, context
    sentence = "Population: about 2.8 million at the 2021 census."
    value, _, _ = sn._match_in_text(page, 2.8e6, sentence, decomp=claim(sentence, "2.8 million"))
    assert value == 2794356


def test_a_count_for_one_census_is_not_confirmed_by_another_census():
    sentence = "Population: 2,731,571 at the 2021 census, making it Canada's largest city."
    page = ("total private dwellings, a change of 2.3 per cent from its 2016 population of "
            "2,731,571. With a land area of 631.1 km2")
    value, context, _ = sn._match_in_text(page, 2731571, sentence, decomp=claim(sentence, "2,731,571"))
    assert value is None, context
    page = "In the 2021 census, Toronto had a population of 2,794,356."
    sentence = "Population: 2,794,356 at the 2021 census."
    value, _, _ = sn._match_in_text(page, 2794356, sentence, decomp=claim(sentence, "2,794,356"))
    assert value == 2794356
