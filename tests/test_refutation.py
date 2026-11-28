"""A number that fits no nearby year is wrong whichever year was meant.

The rule that a year carried over from an earlier sentence cannot refute threw
away most of the evidence: across three blind sets, about 44 false numbers were
read against the right filing or series, disagreed, and came back unresolved.
Refuting across nearby years keeps the protection and recovers them. When a
number is wrong, saying why is what makes the finding usable. No network here.
"""

import pytest

import source_network as sn


def row(year, val, form="10-K"):
    return {
        "start": f"{year}-01-01", "end": f"{year}-12-31", "val": val,
        "fy": year, "fp": "FY", "form": form, "filed": f"{year + 1}-02-20",
    }


@pytest.fixture
def filings(monkeypatch):
    concepts = {}
    monkeypatch.setattr(sn, "_find_cik", lambda subject: ("0000000001", "ACME"))
    monkeypatch.setattr(
        sn, "_sec_concept_data",
        lambda cik, concept, request: {"units": {
            ("USD/shares" if concept == "EarningsPerShareDiluted" else "USD"):
                concepts.get(concept, []),
        }},
    )
    return concepts


def claim(sentence, raw, inherited=None, **fields):
    data = {"sentence": sentence, "numbers": [raw], **fields}
    if inherited:
        data["inherited_year"] = inherited
    return sn.decompose_claim(data)


REVENUE = "RevenueFromContractWithCustomerExcludingAssessedTax"


def held(r):
    """The lexical filing check kept the figure and did not call it wrong."""
    assert r.match_type == "no_data"
    assert r.withheld_refute
    assert r.disagrees
    assert r.confidence == 0.0
    assert r.source_value
    return r


def test_an_inherited_year_keeps_the_filing_when_no_nearby_year_fits(filings):
    filings[REVENUE] = [row(2023, 3.9e9), row(2024, 4.1e9), row(2025, 4.3e9)]
    d = claim("Acme's revenue was $5.6 billion.", "$5.6 billion", "2025")
    assert d.year_inherited
    r = held(sn.verify_sec_edgar(d))
    verdict, _, detail = sn._consensus_for(d, [r])
    assert verdict == "unverifiable"
    assert "wrong" not in detail.lower()
    assert detail.startswith("SEC Filing gives a different value:")


def test_an_inherited_year_still_cannot_refute_when_a_nearby_year_fits(filings):
    filings[REVENUE] = [row(2023, 3.9e9), row(2024, 5.5e9), row(2025, 4.3e9)]
    d = claim("Acme's revenue was $5.6 billion.", "$5.6 billion", "2025")
    assert sn.verify_sec_edgar(d).match_type == "no_data"


@pytest.mark.parametrize("sentence", [
    "Acme's adjusted net income was $900 million in 2025.",
    "Acme's non-GAAP net income was $900 million in 2025.",
    "Acme's pro forma net income was $900 million in 2025.",
    "Acme's net income excluding one-time items was $900 million in 2025.",
])
def test_an_adjusted_figure_is_not_refuted_by_the_reported_one(filings, sentence):
    filings["NetIncomeLoss"] = [row(2025, 500e6)]
    assert sn.verify_sec_edgar(claim(sentence, "$900 million")).match_type == "no_data"


def test_a_rounded_figure_is_not_refuted_by_its_precision(filings):
    filings[REVENUE] = [row(2025, 4.4e9)]
    d = claim("Acme's revenue was about $4 billion in 2025.", "$4 billion")
    assert sn.verify_sec_edgar(d).match_type == "close"
    precise = claim("Acme's revenue was $4.0 billion in 2025.", "$4.0 billion")
    held(sn.verify_sec_edgar(precise))


def test_names_a_figure_from_the_wrong_year(filings):
    filings[REVENUE] = [row(2024, 3.5e9), row(2025, 4.3e9)]
    r = held(sn.verify_sec_edgar(claim("Acme's revenue was $3.5 billion in 2025.", "$3.5 billion")))
    assert "FY2024 figure" in r.source_text


def test_names_a_scale_slip(filings):
    filings["NetIncomeLoss"] = [row(2025, 4.2e9)]
    r = held(sn.verify_sec_edgar(claim("Acme's net income was $4.2 million in 2025.", "$4.2 million")))
    assert "scale" in r.source_text


def test_names_a_figure_under_the_wrong_metric(filings):
    filings["NetIncomeLoss"] = [row(2025, 500e6)]
    filings["GrossProfit"] = [row(2025, 900e6)]
    r = held(sn.verify_sec_edgar(claim("Acme's net income was $900 million in 2025.", "$900 million")))
    assert "gross profit" in r.source_text


def test_a_lone_year_makes_a_stale_figure_wrong(filings):
    filings[REVENUE] = [row(2024, 3.5e9), row(2025, 4.3e9)]
    d = claim("Acme's revenue was $3.5 billion.", "$3.5 billion", "2025", year_sole=True)
    r = held(sn.verify_sec_edgar(d))
    assert "FY2024 figure" in r.source_text


def test_a_lone_year_does_not_override_a_pointer_to_another_period(filings):
    filings[REVENUE] = [row(2024, 3.5e9), row(2025, 4.3e9)]
    d = claim("A year ago Acme's revenue was $3.5 billion.", "$3.5 billion", "2025", year_sole=True)
    assert sn.verify_sec_edgar(d).match_type == "no_data"


@pytest.fixture
def series(monkeypatch):
    values = {}

    def fake(url, *a, **k):
        found = sn.re.search(r'date=(\d{4})(?::(\d{4}))?', url)
        low = int(found.group(1))
        high = int(found.group(2) or low)
        rows = [
            {"date": str(y), "value": v} for y, v in sorted(values.items(), reverse=True)
            if low <= y <= high
        ]
        return [{"page": 1}, rows]

    monkeypatch.setattr(sn, "_fetch_json", fake)
    monkeypatch.setattr(sn, "_wb_country_code", lambda name: "NO")
    return values


def test_world_bank_refutes_across_an_inherited_year(series):
    series.update({2023: 58e9, 2024: 60e9, 2025: 61.6e9})
    d = claim("Norway's GDP was $48 billion.", "$48 billion", "2025")
    assert d.year_inherited
    r = sn.verify_world_bank(d)
    # The World Bank earned refute on v32 (2026-11-28).
    assert r.match_type == "contradicted"
    assert not r.withheld_refute
    assert r.source_value is not None


def test_world_bank_holds_back_when_a_nearby_year_fits(series):
    series.update({2023: 47.5e9, 2024: 55e9, 2025: 61.6e9})
    d = claim("Norway's GDP was $48 billion.", "$48 billion", "2025")
    assert sn.verify_world_bank(d).match_type == "no_data"


def test_world_bank_names_the_wrong_year(series):
    series.update({2024: 55e9, 2025: 61.6e9})
    r = sn.verify_world_bank(claim("Norway's GDP was $55 billion in 2025.", "$55 billion"))
    # The World Bank earned refute on v32 (2026-11-28).
    assert r.match_type == "contradicted"
    assert not r.withheld_refute
    assert "2024 figure" in r.source_text


def test_world_bank_shows_a_rate_with_its_decimals(series):
    series.update({2025: 3.67})
    r = sn.verify_world_bank(claim("Norway's inflation was 3.7 percent in 2025.", "3.7"))
    assert "3.67" in r.source_text


def test_a_lone_year_is_recorded_on_the_claim():
    doc = "Acme results for fiscal 2025.\n\nRevenue was $4.3 billion.\n"
    claims = sn._apply_discourse_context(
        [{"sentence": "Revenue was $4.3 billion.", "numbers": ["$4.3 billion"]}], doc,
    )
    assert claims[0]["year_sole"] is True
    many = "Acme in 2024 and 2025.\n\nRevenue was $4.3 billion.\n"
    claims = sn._apply_discourse_context(
        [{"sentence": "Revenue was $4.3 billion.", "numbers": ["$4.3 billion"]}], many,
    )
    assert claims[0]["year_sole"] is False


def test_a_figure_after_vs_is_never_called_stale(filings):
    filings["EarningsPerShareDiluted"] = [row(2024, 4.45), row(2025, 3.36)]
    d = claim("Diluted EPS $3.36 vs $4.45.", "$4.45", "FY2025", year_sole=True)
    assert sn.verify_sec_edgar(d).match_type == "no_data"


def test_a_figure_in_parentheses_is_a_loss(filings):
    filings["NetIncomeLoss"] = [row(2025, -52.5e6)]
    d = claim("Heartland's net income in 2025 was $52.5M (a loss).", "$52.5M")
    assert sn.verify_sec_edgar(d).match_type in ("exact", "close")


def test_a_net_loss_about_another_figure_does_not_flip_this_one(filings):
    filings["NetIncomeLoss"] = [row(2026, 63.2e6), row(2025, -118.9e6)]
    d = claim("Acme reported net income of $63.2 million for 2026, compared with a "
              "net loss of $118.9 million a year earlier.", "$63.2 million")
    assert sn.verify_sec_edgar(d).match_type == "exact"


def test_a_bare_number_off_by_exactly_a_scale_is_not_refuted(filings):
    filings[REVENUE] = [row(2026, 2_911_632_000)]
    d = claim("Acme net sales in 2026 were 2,911,632.", "2,911,632")
    assert sn.verify_sec_edgar(d).match_type == "no_data"


def test_a_loss_per_share_is_negative(filings):
    filings["EarningsPerShareDiluted"] = [row(2025, -1.14)]
    d = claim("Teladoc posted a net loss of $200.3 million for 2025, or $1.14 per share.", "$1.14")
    assert sn.verify_sec_edgar(d).match_type == "exact"


def test_earnings_per_share_stay_positive(filings):
    filings["EarningsPerShareDiluted"] = [row(2025, 3.36)]
    d = claim("Acme earned net income of $84 million in 2025, or $3.36 per share, "
              "after a loss in 2024.", "$3.36")
    assert sn.verify_sec_edgar(d).match_type == "exact"


def test_a_near_miss_on_a_precise_figure_is_not_close(series):
    series.update({2024: 3_524_788})
    d = claim("Norway had a population of roughly 3.39 million in 2024.", "3.39 million")
    # 4% off a precise figure is never a match. It is near (close), which every
    # view shows as not equal, with the source's figure, and never refutes.
    r = sn.verify_world_bank(d)
    assert r.match_type == "close"
    result = sn.SourceNetworkResult(
        claim_numbers=["3.39 million"], claim_sentence=d.sentence, decomposition=d,
        source_results=[r], verdict="close", confidence=0.75, detail="")
    assert sn._settle_close([result])[0].verdict == "close"


def test_a_mistagged_fiscal_year_does_not_stand_in_for_another(filings):
    # Wolverine's 10-K tags the year ending 2026-01-03 as fy 2024.
    filings["NetIncomeLoss"] = [
        {**row(2024, 45.2e6), "end": "2024-12-28"},
        {"start": "2024-12-29", "end": "2026-01-03", "val": 95.8e6, "fy": 2024,
         "fp": "FY", "form": "10-K", "filed": "2026-02-27"},
    ]
    d = claim("Wolverine's net income in 2024 was $97.5 million.", "$97.5 million")
    held(sn.verify_sec_edgar(d))
    d = claim("Wolverine's net income in 2025 was $95.8 million.", "$95.8 million")
    assert sn.verify_sec_edgar(d).match_type == "exact"


def test_a_loss_per_share_after_a_split_keeps_its_sign(filings):
    filings["EarningsPerShareDiluted"] = [row(2025, -1.14)]
    doc = "Teladoc posted a net loss of $200.3 million for 2025, or $1.14 per share, compared with a loss of $1.2 billion in 2024."
    claims = sn._prepare_claims(
        [{"sentence": doc, "numbers": ["$200.3 million", "$1.14", "$1.2 billion"]}], doc,
    )
    per_share = next(c for c in claims if "$1.14" in c["numbers"])
    d = sn.decompose_claim(per_share, doc_text=doc)
    assert sn.verify_sec_edgar(d).match_type == "exact"


# v17 (2026-11-10): seven true figures were refuted against a measure the
# sentence mentions but the figure's own words do not name.
def test_a_figure_named_as_another_measure_is_not_refuted_as_revenue(filings):
    filings["Revenues"] = [row(2024, 4.5e9)]
    for sentence, raw in (
        ("In 2024 Acme's free cash flow was around $1.5 billion, a lot of its revenue.", "$1.5 billion"),
        ("In 2024 Acme's gross merchandise sales were around $13.2 billion.", "$13.2 billion"),
        ("In 2024 Acme's Comirnaty (vaccine) sales were around $11.2 billion.", "$11.2 billion"),
    ):
        assert sn.verify_sec_edgar(claim(sentence, raw)).match_type != "contradicted", sentence


def test_a_figure_its_words_name_as_revenue_keeps_the_filing(filings):
    filings["Revenues"] = [row(2024, 4.5e9)]
    d = claim("Acme's revenue in 2024 was $1.5 billion.", "$1.5 billion")
    held(sn.verify_sec_edgar(d))


def test_a_city_figure_is_not_refuted_by_the_country(series):
    series.update({2023: 18_124_838})
    d = claim("In 2023 the Oslo city metro population was roughly 3 million.", "3 million")
    assert sn.verify_world_bank(d).match_type != "contradicted"


def test_a_year_that_belongs_to_another_figure_does_not_refute(filings):
    """Zoom, v17: fiscal 2022 is the last figure's year, not the first's."""
    filings["Revenues"] = [row(2022, 4.10e9), row(2023, 4.39e9), row(2024, 4.53e9)]
    d = claim("Revenue came in at about $4.53 billion, up roughly 3% from $4.39 billion the "
              "year before, which itself was up only 7% from fiscal 2022's $4.10 billion.",
              "$4.53 billion")
    assert sn.verify_sec_edgar(d).match_type != "contradicted"


def test_a_leading_year_keeps_the_filing(filings):
    filings["Revenues"] = [row(2024, 4.5e9)]
    d = claim("In 2024, Acme's revenue was $1.5 billion.", "$1.5 billion")
    held(sn.verify_sec_edgar(d))


def test_a_city_named_after_the_figure_is_not_the_country(series):
    series.update({2020: 126_000_000})
    d = claim("Founded in 794, Japan's old capital had a population of about 1.46 million "
              "people in the city itself in 2020.", "1.46 million")
    assert sn.verify_world_bank(d).match_type != "contradicted"


def test_a_figure_named_as_another_indicator_is_not_refuted(monkeypatch):
    """Belarus, v17: the median age is not life expectancy."""
    monkeypatch.setattr(sn, "_wb_country_code", lambda name: "BY")
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: [{"page": 1}, [{"date": "2023", "value": 74.18}]])
    d = claim("In 2023 Belarus life expectancy is roughly 74 years, the median age is about 41.", "41")
    assert sn.verify_world_bank(d).match_type != "contradicted"


def test_a_median_age_equal_to_life_expectancy_is_not_a_tick(monkeypatch):
    monkeypatch.setattr(sn, "_wb_country_code", lambda name: "BY")
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: [{"page": 1}, [{"date": "2023", "value": 74.18}]])
    d = claim("In 2023 the median age in Belarus is about 74.2 years.", "74.2")
    d.metric = "lifespan"
    r = sn.verify_world_bank(d)
    assert r.match_type == "no_data"
    assert not r.withheld_refute
    assert not r.source_value


def test_an_urban_share_still_matches(monkeypatch):
    monkeypatch.setattr(sn, "_WB_COUNTRY_CODES", {})

    def fetch(url, *a, **k):
        if "/indicator/" in url:
            assert "SP.URB.TOTL.IN.ZS" in url
            return [{}, [{"value": 77.6, "date": "2023"}]]
        return [{}, [{"iso2Code": "DE", "name": "Germany"}]]

    monkeypatch.setattr(sn, "_fetch_json", fetch)
    r = sn.verify_world_bank(claim(
        "77.6 percent of people in Germany live in cities.", "77.6"))
    assert r.match_type in ("exact", "close")


# v18 (2026-11-10): FRED refuted three true US figures by asking the wrong period.
def test_a_year_earlier_shifts_only_the_base_figure():
    import re as _re
    sent = "CPI up 2.1% in December 2016 from a year earlier."
    assert not _re.search(r'\b(?:from|compared\s+(?:with|to)|versus|vs\.?)\s+(?:about\s+|around\s+|roughly\s+)?$',
                          sent[max(0, sent.find("2.1%") - 30):sent.find("2.1%")])
    base = "Inflation was 2.1% in December 2016, up from 0.7% a year earlier."
    at = base.find("0.7%")
    assert _re.search(r'\b(?:from|compared\s+(?:with|to)|versus|vs\.?)\s+(?:about\s+|around\s+|roughly\s+)?$',
                      base[max(0, at - 30):at])


def test_a_brief_move_is_not_the_months_average():
    assert sn._FRED_EXTREME_RE.search("the 10-year Treasury yield briefly dropped to roughly 1.4% in July 2016")


def test_us_only_measures_make_a_document_american():
    assert sn._doc_is_us("Employers added roughly 2.3 million nonfarm jobs in 2016.")
    assert sn._doc_is_us("Core PCE topped out near 5.6% in early 2022.")
    assert not sn._doc_is_us("Spain's unemployment rate was 12% while nonfarm jobs grew.")


def test_a_document_naming_no_country_lets_fred_confirm_but_not_refute():
    assert sn._doc_no_country("The unemployment rate averaged about 4.9% in 2016.")
    d = claim("The unemployment rate averaged about 9.9% in 2016.", "9.9%")
    d.doc_no_country = True
    assert sn._fred_applies(d) and not sn._fred_us_stated(d)


def test_words_after_a_figure_naming_another_year_take_it_from_the_claim():
    d = claim("The PCE rate peaked at roughly 7.0 percent in June 2022 and had come down to "
              "around 2.5 percent by late 2024.", "2.5 percent")
    d.time_period = "June 2022"
    assert sn._trailing_year_differs(d)


def test_a_year_stated_once_for_two_figures_covers_both():
    d = claim("The 10-year Treasury yield averaged 4.6% for 2024, and the 30-year mortgage "
              "rate averaged 4.21%, keeping buyers away.", "4.21%")
    d.time_period = "2024"
    assert not sn._trailing_year_differs(d)
