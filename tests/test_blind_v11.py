"""Faults from the natural-plus-planted blind set (heldout_docs_v11). No network."""

import urllib.parse

import pytest

import source_network as sn
from prose import plain_prose


def claim(sentence, raw, **fields):
    return sn.decompose_claim({"sentence": sentence, "numbers": [raw], **fields})


@pytest.fixture
def fred(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test")
    data, urls = {}, []

    def fake(url, *a, **k):
        urls.append(url)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        rows = []
        for key, value in sorted(data.get(q["series_id"], {}).items()):
            date = f"{key[0]}-{key[1]:02d}-01" if isinstance(key, tuple) else f"{key}-01-01"
            if q["observation_start"][:10] <= date <= q["observation_end"][:10]:
                rows.append({"date": date, "value": str(value)})
        return {"observations": rows}

    monkeypatch.setattr(sn, "_fetch_json", fake)
    return data, urls


def test_headline_inflation_is_the_unadjusted_series(fred):
    data, urls = fred
    data["CPIAUCNS"] = {(2022, 6): 9.06}
    r = sn.verify_fred(claim("US inflation peaked at 9.1% in June 2022.", "9.1%"))
    assert r.match_type in ("exact", "close")
    assert "CPIAUCNS" in urls[0]


def test_the_month_nearest_the_figure_is_used(fred):
    data, _ = fred
    data["FEDFUNDS"] = {(2024, 8): 5.33, (2024, 12): 4.48}
    d = claim("The effective funds rate sat at 5.33% through August 2024, then fell to "
              "4.48% by December 2024.", "4.48%")
    assert sn.verify_fred(d).match_type == "exact"


def test_a_target_range_is_confirmed_by_a_rate_inside_it_and_never_refuted(fred):
    data, _ = fred
    data["FEDFUNDS"] = {(2023, 7): 5.12}
    inside = claim("The Fed raised the funds rate to a range of 5.25%-5.50% by July 2023.", "5.25%-5.50%")
    data["FEDFUNDS"][(2023, 7)] = 5.33
    assert sn.verify_fred(inside).match_type in ("exact", "close")
    data["FEDFUNDS"][(2023, 7)] = 5.12
    assert sn.verify_fred(inside).match_type == "no_data"


@pytest.mark.parametrize("sentence,raw", [
    ("The Fed cut the funds rate by 100 basis points in late 2024.", "100 basis points"),
    ("The 10-year Treasury yield averaged 480 basis points in October 2023.", "480 basis points"),
])
def test_basis_points_are_not_compared_as_a_rate(fred, sentence, raw):
    data, _ = fred
    data["FEDFUNDS"] = {2024: 5.1}
    data["DGS10"] = {(2023, 10): 4.80}
    assert sn.verify_fred(claim(sentence, raw)).match_type == "no_data"


@pytest.mark.parametrize("sentence,raw", [
    ("30-year mortgage rates peaked at 7.79% in late October 2023.", "7.79%"),
    ("Inflation peaked in early 2023 at around 18% year-on-year in Poland.", "18%"),
])
def test_a_peak_is_never_refuted_by_an_average(sentence, raw):
    d = claim(sentence, raw)
    contradicted = sn.SourceResult(source_name="FRED", match_type="contradicted", confidence=0.85)
    assert sn._consensus_for(d, [contradicted])[0] == "unverifiable"


def test_loss_per_share_written_as_a_label_is_negative():
    assert sn._is_loss_per_share("Loss per share: around $10.73.", "$10.73")


def test_a_unit_after_the_figure_counts_even_when_hedged():
    d = claim("Crater: The summit crater is about 780 ft across.", "780")
    page = "Fuji's main crater is 780 m (2,560 ft) in diameter and 240 m (790 ft) deep."
    assert sn._match_in_text(page, 780.0, d.sentence, decomp=d)[0] is None


def test_cost_of_revenue_is_its_own_filed_metric():
    d = claim("Lyft's cost of revenue in 2023 was $2,435.7 million.", "$2,435.7 million")
    assert d.metric == "cost_of_revenue"
    assert "CostOfRevenue" in sn._METRIC_CONCEPTS["cost_of_revenue"]


def test_a_table_in_millions_of_dollars_marks_its_cells_as_dollars():
    doc = ("Lyft, Inc. selected financials (in millions of US dollars, except per-share data)\n\n"
           "| Item | 2023 |\n|---|---|\n| Cost of revenue | 2,435.7 |\n")
    assert "$2,435.7 million" in plain_prose(doc)
