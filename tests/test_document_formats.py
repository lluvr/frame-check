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
    assert once == "Revenue: $15.52 billion.\n\nnote FY2023 up 3 percent.\n"
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
    (("Botswana's GDP was $19.3 billion in 2024 with a population of around "
      "3.4 million."), "$19.3 billion", "gdp"),
    (("Botswana's GDP was $19.3 billion in 2024 with a population of around "
      "3.4 million."), "3.4 million", "population"),
    (("Slovenia's population of 2.13 million enjoys a life expectancy of "
      "82.3 years."), "82.3 years", "lifespan"),
    ("Rollins had net income of $526.7 million, or $1.09 per diluted share.",
     "$526.7 million", "profit"),
    ("Rollins had net income of $526.7 million, or $1.09 per diluted share.",
     "$1.09", "eps"),
    (("Snap-on banked $1.02bn of net income for fiscal 2025 and generated "
      "about $1.4bn of operating cash flow."), "$1.02bn", "profit"),
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


def test_a_population_a_nearby_year_fits_does_not_refute_across_an_inherited_year(monkeypatch):
    parsed = parse("We use 2023 and 2024 data here.\n\nBotswana has a population of 3.4 million people.")
    monkeypatch.setattr(sn, "_wb_country_code", lambda country: "BW")
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: [
        {"page": 1},
        [{"value": 3_150_000, "date": "2024"}, {"value": 3_380_000, "date": "2022"}],
    ])
    assert sn.verify_world_bank(parsed["3.4 million"]).match_type == "no_data"


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
    (("Landstar's revenue for fiscal 2025 was $4.74 billion and net income fell "
      "to $115 million."), "$4.74 billion", "revenue"),
    (("Landstar's revenue for fiscal 2025 was $4.74 billion and net income fell "
      "to $115 million."), "$115 million", "profit"),
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
     "gdp_per_capita", "NY.GDP.PCAP.CD"),
])
def test_the_indicator_follows_the_figures_metric(sentence, metric, indicator):
    assert sn._detect_wb_indicator(sentence, metric)[0] == indicator


@pytest.mark.parametrize("name", ["Starbucks", "Mars", "Siemens"])
def test_a_name_ending_in_s_still_counts(name):
    parsed = parse(f"China is a big market. {name} reported revenue of $36.2 billion.")
    assert parsed["$36.2 billion"].subject == name


def test_a_fraction_on_the_page_is_not_a_number():
    text = "Its surface gravity is 1⁄6 of the Moon's, and 3/8 of Mars."
    decomp = sn.decompose_claim({
        "sentence": "One orbit takes about 6.1 Earth years.", "numbers": ["6.1"],
    })
    assert sn._match_in_text(text, 6.1, decomp.sentence, decomp=decomp)[0] is None
    assert sn._match_in_text(text, 8.0, "It is 8 of those.")[0] is None


def test_a_figure_compared_against_gets_the_earlier_year():
    parsed = parse(
        "Federal Signal reported results for the year ended December 31, 2025.\n\n"
        "Net sales were $2.18 billion, compared with $1.86 billion in 2024, an "
        "increase. Operating income for the year came to $340.9 million.\n"
    )
    assert parsed["$2.18 billion"].time_period == "2025"
    assert parsed["$1.86 billion"].time_period == "2024"
    assert parsed["$1.86 billion"].metric == "revenue"
    assert parsed["$1.86 billion"].year_inherited
    assert parsed["$340.9 million"].time_period == "2025"


@pytest.mark.parametrize("sentence,current,prior", [
    ("Net sales of Acme were $688.0 million in 2026, up from $620.0 million a year earlier.",
     "$688.0 million", "$620.0 million"),
    ("Acme's gross profit declined to $243.9 million in 2026, from $401.8 million in the prior year.",
     "$243.9 million", "$401.8 million"),
])
def test_a_prior_figure_is_checked_against_the_prior_year(sentence, current, prior):
    parsed = parse(sentence)
    assert parsed[current].time_period == "2026"
    assert parsed[prior].time_period == "2025"
    assert parsed[prior].metric == parsed[current].metric


def test_growth_from_an_earlier_figure_stays_one_claim():
    parsed = parse("Acme's revenue reached $60.9 billion in 2024, up 126% from $26.97 billion.")
    assert "$26.97 billion" not in parsed


@pytest.mark.parametrize("opening", [
    "Emigration remains", "Builders embedded", "Slowly,", "Mostly", "Quick pass",
    "Size:", "Radius:", "Tom:", "Directors noted",
])
def test_ordinary_openers_are_not_names(opening):
    parsed = parse(f"Toro reported results for 2025. {opening} $4.51 billion.")
    assert parsed["$4.51 billion"].subject == "Toro"


def test_a_name_with_digits_is_a_name():
    parsed = parse(
        "## WD-40 Company: fiscal 2026 snapshot\n\nHere's an overview.\n\n"
        "### Top line\n- **Net sales:** $688.0 million\n\n"
        "### Profitability\n- **Operating income:** $139.6 million\n"
    )
    assert parsed["$688.0 million"].subject == "WD-40 Company"
    assert parsed["$139.6 million"].subject == "WD-40 Company"
    assert sn._find_cik.__name__


def test_faq_markers_are_not_names():
    parsed = parse(
        "Frequently asked questions about the Moon\n\n"
        "Q: How big is it?\nA: The Moon's mean radius is 1,737 km.\n\n"
        "Q: Would I weigh less there?\nA: Yes. Surface gravity is 1.62 m/s2 here.\n"
    )
    assert parsed["1.62"].subject == "Moon"


def test_a_short_line_above_a_list_titles_it():
    parsed = parse(
        "Attendees: Priya, Tom, Reza\n\n"
        "Dorman\n- Tom: 2025 sales came in at $2.13B, gross profit $897.7M\n\n"
        "Hexcel\n- Reza: 2025 sales about $1.89B, basically flat\n"
    )
    assert parsed["$2.13B"].subject == "Dorman"
    assert parsed["$897.7M"].subject == "Dorman"
    assert parsed["$897.7M"].metric == "gross_profit"
    assert parsed["$1.89B"].subject == "Hexcel"


def test_analyst_shorthand_is_read():
    parsed = parse(
        "Snack names, FY25 recap\n\nJJSF (FYE Sep-25)\n- Rev $1.58bn, flat y/y\n"
        "- Op inc $84.3m\n- Dil EPS $3.36\n"
    )
    assert parsed["$1.58bn"].subject == "JJSF"
    assert parsed["$1.58bn"].metric == "revenue"
    assert parsed["$1.58bn"].time_period == "FY2025"
    assert parsed["$84.3m"].metric == "operating_income"
    assert parsed["$3.36"].metric == "eps"


def test_a_memo_is_about_its_subject_line():
    parsed = parse(
        "MEMORANDUM\n\nTO: Board of Directors\nRE: Albany International Corp., "
        "review of fiscal 2025 results\n\nThe Company recorded net sales of "
        "$1.18 billion. The Committee notes that long-term debt stood at "
        "$612.0 million at year end.\n"
    )
    assert parsed["$1.18 billion"].subject.startswith("Albany International")
    assert parsed["$612.0 million"].subject.startswith("Albany International")
    assert parsed["$612.0 million"].metric == "long_term_debt"


def test_figures_listed_with_only_a_comma_are_separate():
    parsed = parse("Hexcel's R&D spend was $56.4M in 2025, cash at year end $92.3M.")
    assert parsed["$56.4M"].metric == "research_development"
    assert parsed["$92.3M"].metric == "cash"


@pytest.mark.parametrize("sentence,indicator", [
    ("Exports of goods and services were equal to 47.5 percent of GDP in 2024.", "NE.EXP.GNFS.ZS"),
    ("Roughly 58 percent of residents now live in cities and towns.", "SP.URB.TOTL.IN.ZS"),
    ("Urbanisation is high, with 95.6% of people in towns.", "SP.URB.TOTL.IN.ZS"),
    ("Some 82.9% of people had access to electricity in 2024.", "EG.ELC.ACCS.ZS"),
    ("Internet use covered 58 percent of residents in 2024.", "IT.NET.USER.ZS"),
    ("Under-five mortality has fallen to 6.4 deaths per 1,000 live births.", "SH.DYN.MORT"),
    ("Consumer prices rose 28.7 percent in 2022.", "FP.CPI.TOTL.ZG"),
    ("Joblessness stood at 7.9 percent.", "SL.UEM.TOTL.ZS"),
    ("Income per person was $5,940 in 2024.", "NY.GDP.PCAP.CD"),
])
def test_more_of_the_world_bank_is_read(sentence, indicator):
    metric = sn.decompose_claim({"sentence": sentence, "numbers": ["1"]}).metric
    assert sn._detect_wb_indicator(sentence, metric)[0] == indicator


def test_a_dividend_per_share_is_not_dividends_paid():
    parsed = parse("Acme paid dividends of $41.2 million in 2025.")
    assert parsed["$41.2 million"].metric == "dividends_paid"
    per_share = parse("Acme paid dividends of $1.60 per share in 2025.")["$1.60"]
    assert sn.verify_sec_edgar(per_share).match_type == "no_data"


def test_a_date_or_citation_on_the_page_is_not_a_measurement():
    page = "Capture came on 6 March 2015. See Proceedings doi:10.1061/41173(414)200."
    assert sn._match_in_text(page, 6.1, "One orbit takes 6.1 Earth years.")[0] is None
    distance = sn.decompose_claim({
        "sentence": "Builders embedded 410 miles of pipe at Hoover Dam.", "numbers": ["410"],
    })
    assert sn._match_in_text(page, 410.0, distance.sentence, decomp=distance)[0] is None


def test_a_stated_decimal_needs_more_than_a_round_number():
    assert sn._match_in_text("It takes 6 years to orbit.", 6.1, "It takes 6.1 years to orbit.")[0] is None
    assert sn._match_in_text("It takes 6.1 years to orbit.", 6.1, "It takes 6.1 years to orbit.")[0] == 6.1


def test_a_measurement_in_another_unit_does_not_confirm():
    decomp = sn.decompose_claim({
        "sentence": "Builders embedded 410 miles of pipe at Hoover Dam.", "numbers": ["410"],
    })
    page = "The pipe at Hoover Dam ran for 412 feet."
    assert sn._match_in_text(page, 410.0, decomp.sentence, decomp=decomp)[0] is None


@pytest.mark.parametrize("name", ["Micron swung", "Deere beat", "Airbus hit", "Tesla cut"])
def test_a_name_with_an_irregular_verb_still_counts(name):
    parsed = parse(f"China is a big market. {name} revenue to $5.0 billion.")
    assert parsed["$5.0 billion"].subject == name.split()[0]


def test_a_rival_in_passing_does_not_take_over_the_subject():
    parsed = parse(
        "Micron swung back to profit in 2024. Rivals such as Arista kept pressing, "
        "and it kept pace with Samsung and SK Hynix.\n\n"
        "The company reported net income of $778 million.\n"
    )
    assert parsed["$778 million"].subject == "Micron"


def test_a_figure_after_vs_cannot_refute():
    parsed = parse("Acme results for fiscal 2025.\n\n- Diluted EPS $3.36 vs $4.45\n")
    assert parsed["$4.45"].year_inherited


def test_a_head_count_of_city_dwellers_is_not_the_urban_share():
    assert sn._detect_wb_indicator("Germany has an urban population of 12 million.", "population")[0] == "SP.POP.TOTL"
    assert sn._detect_wb_indicator("The urban population was 71% of people.", "population")[0] == "SP.URB.TOTL.IN.ZS"


def test_a_measurement_in_fathoms_does_not_confirm_kilometres():
    decomp = sn.decompose_claim({
        "sentence": "It runs for some 890 km at Lake Baikal.", "numbers": ["890"],
    })
    page = "Lake Baikal is the deepest lake at 1,642 metres (5,387 feet; 898 fathoms)."
    assert sn._match_in_text(page, 890.0, decomp.sentence, decomp=decomp)[0] is None


@pytest.mark.parametrize("opening", [
    "MILWAUKEE, Wis. -- Brady Corporation reported results for the year 2026 at last.",
    "LILONGWE - On a dry morning Brady Corporation reported results for the year 2026.",
])
def test_a_dateline_with_a_dash_is_dropped(opening):
    parsed = parse(f"{opening}\n\nNet earnings of $205.4 million.\n")
    assert parsed["$205.4 million"].subject == "Brady Corporation"


def test_a_ticker_title_with_a_dash_stays():
    parsed = parse("POOL - FY25 wrap\nRev $5.29B, basically flat vs FY24 $5.31B. NI $406M.\n")
    assert parsed["$5.29B"].subject == "POOL"
    assert parsed["$5.29B"].time_period == "FY2025"
    assert parsed["$5.31B"].time_period == "2024"
    assert parsed["$406M"].subject == "POOL"


def test_a_question_word_is_not_part_of_the_name():
    parsed = parse("Q: Is Baikal long?\nA: Very. It runs for some 636 km from end to end.\n")
    assert parsed["636"].subject == "Baikal"


@pytest.mark.parametrize("line,raw,metric", [
    ("Stockholders' equity reached roughly $1.96 billion in 2025.", "$1.96 billion", "stockholders_equity"),
    ("Long-term debt stood at about $1.02 billion in 2025.", "$1.02 billion", "long_term_debt"),
    ("Financial position. Total assets fell to $2.12 billion in 2025.", "$2.12 billion", "total_assets"),
])
def test_labels_are_not_names(line, raw, metric):
    parsed = parse(f"Kinsale reported results for 2025.\n\n{line}\n")
    assert parsed[raw].subject == "Kinsale"
    assert parsed[raw].metric == metric


def test_shorthand_labels_are_spelled_out():
    parsed = parse("POOL - FY25 wrap\nEBIT $780M. GP $1.57B.\nInv $1.03B, watch it. LTD $1.19B.\n")
    assert parsed["$1.57B"].metric == "gross_profit"
    assert parsed["$1.03B"].metric == "inventory"
    assert parsed["$1.19B"].metric == "long_term_debt"
    assert parsed["$1.19B"].subject == "POOL"


def test_slide_shorthand_keeps_country_scale_and_metric():
    parsed = parse(
        "Slide 2 - Georgia at a glance\n- GDP $38.1B (2025)\n- Pop. 3.9M\n"
        "- GDP/capita $9.7K\n"
    )
    assert parsed["3.9M"].value == pytest.approx(3_900_000)
    assert parsed["3.9M"].metric == "population"
    assert parsed["3.9M"].subject == "Georgia"
    assert sn._detect_wb_indicator(parsed["$9.7K"].sentence, parsed["$9.7K"].metric)[0] == "NY.GDP.PCAP.CD"


def test_people_listed_as_attendees_are_not_subjects():
    parsed = parse(
        "Kennametal coverage sync\nAttendees: JL, Priya, Sam (Omar out)\n\n"
        "- Net income $342.4M. Sam thinks this overstates run rate.\n"
        "- Inventory $780M at year end\n"
    )
    assert parsed["$780M"].subject == "Kennametal"


@pytest.mark.parametrize("sentence,current,prior", [
    ("Acme's net sales declined to $1.79 billion in 2026 from $1.91 billion the year before.",
     "$1.79 billion", "$1.91 billion"),
    ("Acme's sales were $2.36B in 2026 vs $1.97B prior year.", "$2.36B", "$1.97B"),
    ("Acme's net sales of $1.66 billion in 2026, up 9.8% from $1.51 billion in the prior year.",
     "$1.66 billion", "$1.51 billion"),
])
def test_more_ways_of_stating_the_prior_figure(sentence, current, prior):
    parsed = parse(sentence)
    assert parsed[current].time_period == "2026"
    assert parsed[prior].time_period == "2025"


def test_equity_figures_set_side_by_side_are_separate():
    parsed = parse("Acme's total assets fell to $2.12 billion in 2025 and shareholders' equity to $1.10 billion.")
    assert parsed["$1.10 billion"].metric == "stockholders_equity"


def test_a_statement_style_loss_keeps_its_scale_and_sign():
    assert "$52.5M (a loss)" in plain_prose("Net loss was $(52.5)M last year.")
    parsed = parse(
        "Freight scorecard, calendar 2025 ($ in millions)\n\n"
        "| Carrier | Net income (loss) |\n|---|---|\n| Heartland Express | $(52.5)M |\n"
    )
    d = next(v for k, v in parsed.items() if "52.5" in k)
    assert d.value == pytest.approx(52_500_000)


def test_per_capita_is_its_own_metric():
    parsed = parse("Albania's GDP reached $30.5bn in 2025, and GDP per head about $13,000.")
    assert parsed["$30.5bn"].metric == "gdp"
    head = next(v for k, v in parsed.items() if "13,000" in k)
    assert head.metric == "gdp_per_capita"


def test_a_plain_text_table_in_thousands_keeps_its_scale():
    doc = (
        "Cal-Maine Foods, Inc.\nSelected financial data (in thousands, except per share amounts)\n\n"
        "                    Fiscal 2026      Fiscal 2025\n"
        "Net sales           2,911,632        4,261,885\n"
        "Diluted EPS         6.63             24.95\n"
    )
    parsed = parse(doc)
    sales = next(v for k, v in parsed.items() if "2,911,632" in k)
    assert sales.value == pytest.approx(2_911_632_000)
    eps = next(v for k, v in parsed.items() if "6.63" in k)
    assert eps.value == pytest.approx(6.63)


def test_a_run_in_label_with_a_year_keeps_the_year():
    doc = ("Wolverine World Wide timeline.\n\n**2023: shrinking.** Revenue fell.\n\n"
           "**2024: back to profit.** Net income was $97.5 million.\n")
    assert parse(doc)["$97.5 million"].time_period == "2024"


@pytest.mark.parametrize("claim_text,raw,page", [
    ("The Gateway Arch is 630 metres tall.", "630",
     "The Gateway Arch is a 630-foot-tall (192 m) monument."),
    ("Lake Baikal covers 31,722 square miles and is 636 km long.", "31,722",
     "Lake Baikal has a surface area of 31,722 km2 (12,248 sq mi)."),
])
def test_the_same_digits_in_another_unit_do_not_confirm(claim_text, raw, page):
    d = sn.decompose_claim({"sentence": claim_text, "numbers": [raw]})
    value = float(raw.replace(",", ""))
    assert sn._match_in_text(page, value, claim_text, decomp=d)[0] is None


def test_the_same_unit_still_confirms():
    text = "Lake Baikal covers 31,722 km2 of Siberia."
    d = sn.decompose_claim({"sentence": text, "numbers": ["31,722"]})
    page = "Lake Baikal has a surface area of 31,722 km2 (12,248 sq mi)."
    assert sn._match_in_text(page, 31722.0, text, decomp=d)[0] == 31722.0


def test_a_count_of_steps_does_not_match_feet():
    text = "It's roughly 900 steps from the ground to the second floor of the Eiffel Tower."
    d = sn.decompose_claim({"sentence": text, "numbers": ["900"]})
    page = "The upper platform of the Eiffel Tower is 276 m (906 ft) above the ground."
    assert sn._match_in_text(page, 900.0, text, decomp=d)[0] is None


def test_land_area_is_not_total_area():
    text = "Canada's land area is 9.98 million square kilometres."
    d = sn.decompose_claim({"sentence": text, "numbers": ["9.98 million"]})
    page = "Canada has a total area of 9.98 million square kilometres, the second largest."
    assert sn._match_in_text(page, 9.98e6, text, decomp=d)[0] is None


def test_the_metric_before_a_figure_wins_a_tie():
    parsed = parse("Wolverine posted a net loss of $188.3 million as inventory piled up in 2022.")
    assert parsed["$188.3 million"].metric == "profit"


def test_land_area_needs_the_page_to_say_land():
    text = "Land area: 9.98 million square kilometres in Canada."
    d = sn.decompose_claim({"sentence": text, "numbers": ["9.98 million"]})
    page = "Canada covers 9.98 million square kilometres (3.85 million square miles)."
    assert sn._match_in_text(page, 9.98e6, text, decomp=d)[0] is None


@pytest.mark.parametrize("text,raw,subject", [
    ("Intro line here. The Gateway Arch in St. Louis is 630 metres tall.", "630", "Gateway Arch"),
    ("Intro line here. Mt. Everest rises 8,849 metres above the sea.", "8,849", "Everest"),
    ("Intro line here. Acme Inc. reported revenue of $4.2 billion in 2025.", "$4.2 billion", "Acme"),
])
def test_an_abbreviation_does_not_end_the_sentence(text, raw, subject):
    from claim_analysis import _own_sentence
    assert subject.split()[0] in _own_sentence(text, raw)
    assert subject in parse(text)[raw].subject
