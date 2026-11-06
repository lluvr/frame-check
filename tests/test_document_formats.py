"""Real documents are not plain paragraphs.

Every case comes from a blind set of chat answers, press releases, analyst
notes and tables (calibration/binding_eval/heldout_docs_v4.json), where 8 of
52 true numbers were confirmed against about half on plain paragraphs. Nothing
here touches the network.
"""

import pytest

import source_network as sn
from claim_analysis import analyze_claims
from prose import plain_prose
from source_network import decompose_claim


def parse(text):
    """What the verifier compares, keyed by the figure as parsed."""
    doc = plain_prose(text)
    claims = sn._prepare_claims(analyze_claims(text)["claims"], doc)
    primary = sn.extract_doc_primary_entity(doc)
    out = {}
    for claim in claims:
        d = decompose_claim(claim, doc_text=doc, doc_primary_entity=primary)
        out[d.raw_value.strip()] = d
    return out


CHAT = """## Tractor Supply: FY2025 snapshot

Happy to help! Here's a quick rundown of **Tractor Supply Company** for the fiscal year ended December 27, 2025.

### Headline results

- **Revenue:** $15.52 billion
- **Diluted EPS:** **$2.06**

### Balance sheet

- **Inventory:** about **$4.1 billion**, reflecting its push on seasonal categories
"""


def test_formatting_is_read_out_and_stays_read_out():
    once = plain_prose("- **Revenue:** $15.52 billion\n* *note* FY23 up 3 per cent")
    assert once == "Revenue: $15.52 billion.\nnote FY2023 up 3 percent."
    assert plain_prose(once) == once


def test_a_section_label_is_not_the_company():
    parsed = parse(CHAT)
    for figure in ("$15.52 billion", "$2.06", "$4.1 billion"):
        assert "Tractor Supply" in parsed[figure].subject


def test_the_year_carries_across_sections():
    assert parse(CHAT)["$15.52 billion"].time_period == "2025"


def test_a_table_cell_keeps_its_row_column_and_scale():
    parsed = parse(
        "**Lincoln Electric Holdings: two-year summary**\n\n"
        "Figures in US$ millions, except per-share data.\n\n"
        "| Metric | 2024 | 2025 |\n|---|---|---|\n"
        "| Net sales | 4,008.7 | 4,233.0 |\n"
        "| Diluted EPS | 8.15 | 9.32 |\n"
    )
    sales = parsed["$4,233.0 million"]
    assert sales.value == pytest.approx(4_233_000_000)
    assert sales.metric == "revenue"
    assert sales.time_period == "2025"
    assert "Lincoln" in sales.subject
    assert parsed["$9.32"].metric == "eps"
    assert parsed["$9.32"].value == pytest.approx(9.32)


@pytest.mark.parametrize("text,raw,value", [
    ("Uruguay has 3.39m residents.", "3.39 million", 3_390_000),
    ("Mongolia has 4.7m, spread across the steppe.", "4.7 million", 4_700_000),
    ("Latvia counted 1.87m people in 2024.", "1.87 million", 1_870_000),
    ("Its population of 2.13m enjoys a long life.", "2.13 million", 2_130_000),
])
def test_millions_of_people_keep_their_scale(text, raw, value):
    assert parse("Some context here. " + text)[raw].value == pytest.approx(value)


def test_a_length_in_metres_is_not_millions():
    assert "4.3 million" not in plain_prose("It spans 4.3m from tip to tip.")


@pytest.mark.parametrize("text,raw,value", [
    ("Neptune orbits at about 4,515 million km from the Sun.",
     "4,515 million", 4_515_000_000),
    ("Sales were $4,233.0 million for the year.",
     "$4,233.0 million", 4_233_000_000),
])
def test_a_number_with_a_thousands_comma_stays_whole(text, raw, value):
    assert parse(text)[raw].value == pytest.approx(value)


def test_each_name_in_a_section_owns_its_own_bullet():
    parsed = parse(
        "## Venus and Mercury\n\n"
        "- **Venus** has a mean surface temperature of **464 C** today.\n"
        "- **Mercury** has a mean temperature of about **167 C** today.\n"
    )
    assert parsed["464"].subject == "Venus"
    assert parsed["167"].subject == "Mercury"


def test_a_country_possessive_locates_the_named_thing():
    parsed = parse("France's Millau Viaduct reaches a height of 343 metres.")
    assert parsed["343"].subject == "Millau Viaduct"


def test_an_ampersand_is_part_of_the_name():
    parsed = parse("Church & Dwight earned $960m on sales last year.")
    assert parsed["$960m"].subject == "Church & Dwight"


def test_per_share_is_not_a_name():
    parsed = parse(
        "Hormel reported results in fiscal 2025. Per share that's $3.02 overall."
    )
    assert parsed["$3.02"].subject == "Hormel"


def test_a_dateline_is_not_the_company():
    parsed = parse(
        "ATLANTA: Rollins, Inc. reported results for the year ended "
        "December 31, 2025.\n\nFull-Year 2025 Highlights\n\n"
        "Operating income of $726.1 million.\n"
    )
    assert parsed["$726.1 million"].subject.startswith("Rollins")
    assert parsed["$726.1 million"].time_period == "2025"


@pytest.mark.parametrize("text,raw,metric", [
    ("Botswana's GDP was $19.3 billion in 2024 with a population of around "
     "3.4 million.", "$19.3 billion", "gdp"),
    ("Botswana's GDP was $19.3 billion in 2024 with a population of around "
     "3.4 million.", "3.4 million", "population"),
    ("Slovenia's population of 2.13 million enjoys a life expectancy of "
     "82.3 years.", "82.3 years", "lifespan"),
    ("Rollins had net income of $526.7 million, or $1.09 per diluted share.",
     "$526.7 million", "profit"),
    ("Rollins had net income of $526.7 million, or $1.09 per diluted share.",
     "$1.09", "eps"),
    ("Snap-on banked $1.02bn of net income for fiscal 2025 and generated "
     "about $1.4bn of operating cash flow.", "$1.02bn", "profit"),
])
def test_each_figure_binds_to_the_metric_beside_it(text, raw, metric):
    assert parse(text)[raw].metric == metric


@pytest.mark.parametrize("sentence", [
    "Acme generated operating cash flow of $600 million in 2024.",
    "Acme had cash provided by operating activities of $600 million in 2024.",
])
def test_cash_flow_is_not_a_cash_balance(sentence):
    assert parse(sentence)["$600 million"].metric != "cash"


def test_figures_set_against_each_other_are_both_compared():
    parsed = parse("Uruguay's GDP is $82.3bn against Mongolia's $23.8bn.")
    assert parsed["$82.3bn"].subject == "Uruguay"
    assert parsed["$23.8bn"].subject == "Mongolia"


def test_a_label_after_the_opening_line_is_not_a_dateline():
    prose = plain_prose("Intro line.\n* **GDP:** roughly $83.3 billion")
    assert "GDP: roughly $83.3 billion." in prose


def test_a_labeled_figure_keeps_its_own_metric_in_a_list():
    parsed = parse(
        "Here's a summary of where **Ghana** stood in 2024.\n\n"
        "* **Population:** about 34.4 million\n"
        "* **GDP:** roughly **$83.3 billion** in current US dollars\n"
    )
    assert parsed["$83.3 billion"].metric == "gdp"
    assert parsed["$83.3 billion"].subject == "Ghana"


def test_a_hyphenated_company_keeps_its_whole_name():
    parsed = parse("Snap-on banked $1.02bn of net income for fiscal 2025.")
    assert parsed["$1.02bn"].subject == "Snap-on"


def test_an_economy_worth_a_figure_is_gdp():
    parsed = parse("Using 2024 data, Uruguay's economy is worth $82.3bn today.")
    assert parsed["$82.3bn"].metric == "gdp"


def test_a_small_figure_with_a_filed_metric_reaches_the_filings():
    parsed = parse("Rollins reported $1.09 per diluted share for 2025.")
    assert sn.verify_sec_edgar in sn._classify_and_route(parsed["$1.09"])


def test_a_company_word_does_not_hide_the_filer(monkeypatch):
    monkeypatch.setattr(
        sn, "_get_sec_tickers",
        lambda: ({"TRACTOR SUPPLY CO /DE/": ("1", "TSCO")}, {}),
    )
    assert sn._find_cik("Tractor Supply Company") == ("1", "TSCO")


def _world_bank_result(monkeypatch, decomp, value):
    monkeypatch.setattr(sn, "_wb_country_code", lambda country: "BW")
    monkeypatch.setattr(
        sn, "_fetch_json",
        lambda *a, **k: [
            {"page": 1},
            [{"value": value, "date": "2024", "country": {"value": "X"}}],
        ],
    )
    return sn.verify_world_bank(decomp)


def test_population_refutes_across_an_inherited_year(monkeypatch):
    parsed = parse("We use 2024 data here.\n\nBotswana has a population of 3.4 million people.")
    result = _world_bank_result(monkeypatch, parsed["3.4 million"], 2_480_000)
    assert parsed["3.4 million"].year_inherited
    assert result.match_type == "contradicted"


def test_a_close_population_miss_does_not_refute_across_an_inherited_year(monkeypatch):
    parsed = parse("We use 2024 data here.\n\nBotswana has a population of 3.4 million people.")
    result = _world_bank_result(monkeypatch, parsed["3.4 million"], 3_150_000)
    assert result.match_type == "no_data"


def test_a_dollar_figure_is_never_compared_to_a_head_count(monkeypatch):
    decomp = sn.decompose_claim({
        "sentence": "Ghana's population had $83.3 billion in 2024.",
        "numbers": ["$83.3 billion"],
    })
    assert decomp.metric == "population"
    result = _world_bank_result(monkeypatch, decomp, 34_000_000)
    assert result.match_type == "no_data"


@pytest.mark.parametrize("sentence,raw", [
    ("Italy had a population of about 59 million in 2024 and remains large in Europe.", "59 million"),
    ("The compound sits on 40 million acres of land.", "40 million"),
])
def test_a_currency_code_must_be_a_whole_word(sentence, raw):
    decomp = sn.decompose_claim({"sentence": sentence, "numbers": [raw]})
    assert decomp.unit != "currency"


def test_a_currency_prefix_is_not_the_country():
    parsed = parse(
        "MAURITIUS: COUNTRY BRIEFING\n\n"
        "The island economy reached US$16.2bn in 2025, shared among a "
        "population of 1.24 million.\n"
    )
    assert parsed["$16.2bn"].subject == "Mauritius"
    assert parsed["1.24 million"].subject == "Mauritius"


def test_a_year_compared_against_is_not_the_figures_year():
    parsed = parse(
        "Takeaways from Donaldson Company's fiscal 2026.\n\n"
        "Research and development spending was $76.1 million, lower than in "
        "fiscal 2025.\n"
    )
    decomp = parsed["$76.1 million"]
    assert decomp.time_period == "fiscal 2026"
    assert decomp.year_inherited


@pytest.mark.parametrize("sentence,raw,metric", [
    ("Landstar's revenue for fiscal 2025 was $4.74 billion and net income fell "
     "to $115 million.", "$4.74 billion", "revenue"),
    ("Landstar's revenue for fiscal 2025 was $4.74 billion and net income fell "
     "to $115 million.", "$115 million", "profit"),
    ("Paraguay's 2025 population is at 7.01 million and its GDP at $38 billion.",
     "7.01 million", "population"),
])
def test_and_starts_a_new_figure(sentence, raw, metric):
    assert parse(sentence)[raw].metric == metric


@pytest.mark.parametrize("opening", [
    "Rev", "Pulled together", "How big", "Around", "Worth noting",
    "Need", "Shareholders received", "Joblessness stood at",
])
def test_an_opening_word_is_not_a_name_by_being_capitalized(opening):
    parsed = parse(f"Toro reported results for 2025. {opening} $4.51 billion.")
    assert parsed["$4.51 billion"].subject == "Toro"


@pytest.mark.parametrize("sentence,subject", [
    ("Apple reported revenue of $383 billion.", "Apple"),
    ("Hormel, hit by costs, managed just $478 million.", "Hormel"),
    ("Toro's sales were $4.51 billion.", "Toro"),
    ("Tesla spans $90 billion of revenue.", "Tesla"),
])
def test_a_name_opening_a_sentence_still_counts(sentence, subject):
    parsed = parse("Microsoft reported earnings. " + sentence)
    assert parsed[next(k for k in parsed if "billion" in k or "million" in k)].subject == subject


def test_a_bold_run_in_label_is_not_the_subject():
    assert plain_prose("**Worth the trip.** Lake Titicaca sits high.") == (
        "Lake Titicaca sits high."
    )


def test_a_table_of_companies_binds_name_and_metric_and_skips_estimates():
    parsed = parse(
        "Water names, fiscal 2025 ($ in millions)\n\n"
        "| Company | Revenue | Net income | 2027E revenue (my est.) |\n"
        "|---|---|---|---|\n"
        "| Watts Water Technologies | 2,438.5 | 340.8 | 2,700 |\n"
    )
    revenue = parsed["$2,438.5 million"]
    assert revenue.subject == "Watts Water Technologies"
    assert revenue.metric == "revenue"
    assert parsed["$340.8 million"].metric == "profit"
    assert not any("2,700" in key for key in parsed)


@pytest.mark.parametrize("sentence,metric,indicator", [
    ("Its population of 2.13 million enjoys a life expectancy of 82.3 years.",
     "lifespan", "SP.DYN.LE00.IN"),
    ("A population of 1.24 million puts GDP per head at about $17,000.",
     "population", "SP.POP.TOTL"),
    ("A population of 1.24 million puts GDP per head at about $17,000.",
     "gdp", "NY.GDP.PCAP.CD"),
])
def test_the_indicator_follows_the_figures_metric(sentence, metric, indicator):
    assert sn._detect_wb_indicator(sentence, metric)[0] == indicator


@pytest.mark.parametrize("name", ["Starbucks", "Mars", "Siemens"])
def test_a_name_ending_in_s_still_counts(name):
    parsed = parse(f"China is a big market. {name} reported revenue of $36.2 billion.")
    assert parsed["$36.2 billion"].subject == name
