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


def test_an_inherited_year_refutes_when_no_nearby_year_fits(filings):
    filings[REVENUE] = [row(2023, 3.9e9), row(2024, 4.1e9), row(2025, 4.3e9)]
    d = claim("Acme's revenue was $5.6 billion.", "$5.6 billion", "2025")
    assert d.year_inherited
    assert sn.verify_sec_edgar(d).match_type == "contradicted"


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
    assert sn.verify_sec_edgar(precise).match_type == "contradicted"


def test_names_a_figure_from_the_wrong_year(filings):
    filings[REVENUE] = [row(2024, 3.5e9), row(2025, 4.3e9)]
    r = sn.verify_sec_edgar(claim("Acme's revenue was $3.5 billion in 2025.", "$3.5 billion"))
    assert r.match_type == "contradicted"
    assert "FY2024 figure" in r.source_text


def test_names_a_scale_slip(filings):
    filings["NetIncomeLoss"] = [row(2025, 4.2e9)]
    r = sn.verify_sec_edgar(claim("Acme's net income was $4.2 million in 2025.", "$4.2 million"))
    assert r.match_type == "contradicted"
    assert "scale" in r.source_text


def test_names_a_figure_under_the_wrong_metric(filings):
    filings["NetIncomeLoss"] = [row(2025, 500e6)]
    filings["GrossProfit"] = [row(2025, 900e6)]
    r = sn.verify_sec_edgar(claim("Acme's net income was $900 million in 2025.", "$900 million"))
    assert r.match_type == "contradicted"
    assert "gross profit" in r.source_text


def test_a_lone_year_makes_a_stale_figure_wrong(filings):
    filings[REVENUE] = [row(2024, 3.5e9), row(2025, 4.3e9)]
    d = claim("Acme's revenue was $3.5 billion.", "$3.5 billion", "2025", year_sole=True)
    r = sn.verify_sec_edgar(d)
    assert r.match_type == "contradicted"
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
    assert sn.verify_world_bank(d).match_type == "contradicted"


def test_world_bank_holds_back_when_a_nearby_year_fits(series):
    series.update({2023: 47.5e9, 2024: 55e9, 2025: 61.6e9})
    d = claim("Norway's GDP was $48 billion.", "$48 billion", "2025")
    assert sn.verify_world_bank(d).match_type == "no_data"


def test_world_bank_names_the_wrong_year(series):
    series.update({2024: 55e9, 2025: 61.6e9})
    r = sn.verify_world_bank(claim("Norway's GDP was $55 billion in 2025.", "$55 billion"))
    assert r.match_type == "contradicted"
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
    assert sn.verify_world_bank(d).match_type not in ("exact", "close")


def test_a_mistagged_fiscal_year_does_not_stand_in_for_another(filings):
    # Wolverine's 10-K tags the year ending 2026-01-03 as fy 2024.
    filings["NetIncomeLoss"] = [
        {**row(2024, 45.2e6), "end": "2024-12-28"},
        {"start": "2024-12-29", "end": "2026-01-03", "val": 95.8e6, "fy": 2024,
         "fp": "FY", "form": "10-K", "filed": "2026-02-27"},
    ]
    d = claim("Wolverine's net income in 2024 was $97.5 million.", "$97.5 million")
    assert sn.verify_sec_edgar(d).match_type == "contradicted"
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
