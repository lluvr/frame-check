"""Gaps left after the v12 fixes: the true numbers the rules path (reader down)
still contradicted, found by the outage drills. No network here.
"""

import source_network as sn
from tests import test_fred_wikidata

# Shared stub: pytest finds a fixture by the module attribute that holds it.
wikidata = test_fred_wikidata.wikidata
_quantity = test_fred_wikidata._quantity


def claim(sentence, raw, **fields):
    return sn.decompose_claim({"sentence": sentence, "numbers": [raw], **fields})


# ------------------------------------------------ the year of an event is not the figure's

def test_the_year_of_a_later_split_is_not_the_figures_year():
    d = claim(
        "Diluted EPS: $44.34 (before the 50-for-1 stock split in 2024).", "$44.34",
        heading="Chipotle Mexican Grill, fiscal 2023 at a glance",
    )
    assert "2023" in d.time_period


def test_an_event_year_in_parentheses_leaves_the_period_empty_without_a_heading():
    d = claim("Diluted EPS was $44.34 (before the stock split in 2024).", "$44.34")
    assert "2024" not in d.time_period


def test_a_plain_year_in_parentheses_is_still_the_period():
    d = claim("Diluted EPS was $6.13 (fiscal 2024).", "$6.13")
    assert "2024" in d.time_period


# ------------------------------------------------ a bullet naming a business line is a segment

def test_a_bullet_labelled_with_a_business_line_is_a_segment():
    d = claim(
        "Wizards of the Coast & Digital Gaming: the bright spot, with revenue up "
        "about 10% to around $1.46 billion, helped by licensing.", "$1.46 billion",
        heading="Hasbro (HAS) - 2023 financial snapshot",
    )
    assert d.is_segment


def test_a_bullet_labelled_with_a_metric_is_not_a_segment():
    for sentence in (
        "Net revenue: $5.00 billion, down about 15% from 2022.",
        "Total revenue: $5.00 billion.",
        "Full year 2023: revenue of $5.00 billion.",
        "Net loss attributable to Hasbro: about $1.49 billion.",
        "Free cash flow: $725 million.",
    ):
        d = claim(sentence, "$5.00 billion" if "5.00" in sentence else sentence.split()[-2])
        assert not d.is_segment, sentence


# ------------------------------------------------ Wikidata: the measure named

def test_a_bridge_span_is_not_its_total_length():
    d = claim("The Golden Gate Bridge has a main span of 4,200 ft (1,280 m) and opened in 1937.", "4,200")
    assert d.metric == "length"
    assert sn._wd_properties(d) == ("P2787",)


def test_a_roof_height_is_never_confirmed_by_the_height_to_the_tip(wikidata):
    wikidata["Q12495"] = {"label": "Burj Khalifa", "claims": {"P2048": [_quantity(828, "Q11573")]}}
    for sentence, raw in (("The Burj Khalifa's roof sits at about 2,717 feet.", "2,717"),
                          ("The Burj Khalifa's roof is 739 m high.", "739"),
                          ("The Burj Khalifa reaches 828 m to its roof.", "828")):
        d = claim(sentence, raw)
        d.subject, d.metric = "Burj Khalifa", "height"
        r = sn.verify_wikidata(d)
        assert r.match_type == "no_data", sentence
        # Silent, not a disagreement: Wikipedia's "roof height of 828 m" stands.
        assert not r.disagrees, sentence


def test_a_roof_height_far_below_the_tip_is_still_refuted(wikidata):
    # 828 feet is 252 m: a unit slip for 828 m, not a roof.
    wikidata["Q12495"] = {"label": "Burj Khalifa", "claims": {"P2048": [_quantity(828, "Q11573")]}}
    d = claim("Dubai's Burj Khalifa reaches 828 feet to its roof.", "828")
    d.subject, d.metric = "Burj Khalifa", "height"
    r = sn.verify_wikidata(d)
    assert r.match_type == "contradicted"
    assert "metres" in r.source_text


def test_a_total_length_beside_a_span_is_the_length():
    d = claim("The Akashi Kaikyo Bridge has a central span of 1,991 ft and a total length "
              "of 3,911 m; it opened in 1998.", "3,911")
    d.metric = "length"
    assert sn._wd_properties(d) == ("P2043",)


def test_a_plain_height_still_uses_height():
    d = claim("The Burj Khalifa is 828 m tall.", "828")
    d.metric = "height"
    assert sn._wd_properties(d) == ("P2048", "P2044")


# ------------------------------------------------ a year is confirmed by its event

PAGE = ("Calgary was incorporated as a town in 1884. In 1884, the HBC established a sales shop "
        "in Calgary. It was incorporated as a city in 1894. Fort Calgary was established in 1875.")


def test_a_year_is_not_confirmed_by_another_event_in_that_year():
    # The real Wikipedia passage. "established" belongs to the other clause.
    sentence = "Fort Calgary was established in 1875, and Calgary was incorporated as a city in 1884."
    page = ("later developed into the modern cities of Winnipeg, Calgary, and Edmonton. In 1884, "
            "the HBC established a sales shop in Calgary. HBC also built the first of the")
    value, context, _ = sn._match_in_text(page, 1884, sentence, decomp=claim(sentence, "1884"))
    assert value is None, context


def test_a_year_is_confirmed_by_its_own_event():
    sentence = "Fort Calgary was established in 1875."
    d = claim(sentence, "1875")
    value, _, _ = sn._match_in_text(PAGE, 1875, sentence, decomp=d)
    assert value == 1875


def test_a_year_as_a_city_is_not_the_year_as_a_town():
    sentence = "Fort Calgary was established in 1875, and Calgary was incorporated as a city in 1884."
    page = ("District No. 19 was formed by the Legislature on March 2, 1885.\nOn November 27, 1884, "
            "Lieutenant Governor Dewdney proclaimed the incorporation of The Town of Calgary.")
    value, context, _ = sn._match_in_text(page, 1884, sentence, decomp=claim(sentence, "1884"))
    assert value is None, context
    page = "On January 1, 1894, Calgary was incorporated as a city."
    sentence = "Calgary was incorporated as a city in 1894."
    value, _, _ = sn._match_in_text(page, 1894, sentence, decomp=claim(sentence, "1894"))
    assert value == 1894
