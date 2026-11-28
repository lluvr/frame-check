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


def test_fred_names_another_years_rate_and_does_not_call_it_wrong(fred):
    data, _ = fred
    data["UNRATE"] = {2022: 3.6, 2023: 3.6, 2024: 4.0}
    r = sn.verify_fred(claim("US unemployment averaged 4.0% in 2023.", "4.0%"))
    assert r.match_type == "no_data"
    assert r.withheld_refute
    assert r.disagrees
    assert "2024 figure" in r.source_text


def test_fred_rate_tolerance_is_in_points_not_percent(fred):
    data, _ = fred
    data["UNRATE"] = {2023: 3.6}
    off = sn.verify_fred(claim("US unemployment averaged 3.9% in 2023.", "3.9%"))
    assert off.match_type == "no_data"
    assert off.withheld_refute
    assert off.source_value is not None
    assert sn.verify_fred(claim("US unemployment averaged about 4% in 2023.", "4%")).match_type == "close"


def test_fred_inflation_is_the_yearly_change_in_prices(fred):
    data, urls = fred
    data["CPIAUCNS"] = {2023: 4.12}
    r = sn.verify_fred(claim("US inflation was 4.1% in 2023.", "4.1%"))
    assert r.match_type in ("exact", "close")
    assert "units=pc1" in urls[0]


def test_a_quarter_is_not_the_years_inflation(fred):
    data, _ = fred
    data["CPIAUCNS"] = {2023: 4.1, 2022: 8.0}
    data["UNRATE"] = {2023: 3.6}
    for sentence in (
        "US inflation was 4.1% in the fourth quarter of 2023.",
        "US inflation was 4.1% in Q4 2023.",
        "US inflation was 4.1% for the three months ended December 31, 2023.",
    ):
        r = sn.verify_fred(claim(sentence, "4.1%"))
        assert r.match_type == "no_data", sentence
        assert not r.withheld_refute
        assert not r.source_value
    # The year, a comparison quarter, a named month, and an average still match.
    assert sn.verify_fred(claim(
        "US inflation was 4.1% in 2023.", "4.1%")).match_type in ("exact", "close")
    assert sn.verify_fred(claim(
        "US inflation was 4.1% in 2023, compared with the fourth quarter of 2022.",
        "4.1%")).match_type in ("exact", "close")
    assert sn.verify_fred(claim(
        "US inflation was 4.1% in 2023 compared with the fourth quarter of 2022.",
        "4.1%")).match_type in ("exact", "close")
    assert sn.verify_fred(claim(
        "In the fourth quarter of 2023, US inflation was 4.1%.",
        "4.1%")).match_type == "no_data"
    for sentence in (
        "US inflation was 4.1% in the first half of 2023.",
        "US inflation was 4.1% year to date in 2023.",
        "US inflation was 4.1% in H1 2023.",
        "US inflation was 4.1% on a quarterly basis in 2023.",
        "In the first half of 2023, US inflation was 4.1%.",
        "US inflation was 4.1% in the first 6 months of 2023.",
        "US inflation was 4.1% q/q in 2023.",
        "US inflation was 4.1% at a run rate in 2023.",
    ):
        r = sn.verify_fred(claim(sentence, "4.1%"))
        assert r.match_type == "no_data", sentence
        assert not r.source_value
    assert sn.verify_fred(claim(
        "US inflation was 4.1% in 2023, compared with the first half of 2022.",
        "4.1%")).match_type in ("exact", "close")
    assert sn.verify_fred(claim(
        "After the fourth quarter of 2022, US inflation was 4.1% in 2023.",
        "4.1%")).match_type in ("exact", "close")
    assert sn.verify_fred(claim(
        "US inflation was 4.1% in 2023 after the fourth quarter of 2022.",
        "4.1%")).match_type in ("exact", "close")
    assert sn.verify_fred(claim(
        "US unemployment averaged 3.6% for the year in 2023.", "3.6%")).match_type == "exact"


def test_another_index_or_a_run_rate_is_not_the_years_series(fred):
    data, _ = fred
    data["CPIAUCNS"] = {2023: 4.1}
    data["CPILFENS"] = {2023: 4.1}
    data["UNRATE"] = {2023: 4.1}
    data["GDP"] = {2023: 4500}
    data["GDPC1"] = {2023: 4500}
    data["PCEPI"] = {2023: 2.2}
    data["PCEPILFE"] = {2023: 2.4}
    for sentence, raw in (
        ("US median CPI was 4.1% in 2023.", "4.1%"),
        ("US trimmed mean inflation was 4.1% in 2023.", "4.1%"),
        ("US sticky inflation was 4.1% in 2023.", "4.1%"),
        ("US supercore inflation was 4.1% in 2023.", "4.1%"),
        ("US harmonised inflation was 4.1% in 2023.", "4.1%"),
        ("US underlying inflation was 4.1% in 2023.", "4.1%"),
        ("US jobless claims were 4.1% in 2023.", "4.1%"),
        ("US GDP was $4.5 trillion at an annual rate in 2023.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion in the quarter in 2023.", "$4.5 trillion"),
        ("During the quarter, US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion SAAR in 2023.", "$4.5 trillion"),
        ("US manufacturing GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US oil GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP at basic prices was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP at producer prices was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US CPI-W was 4.1% in 2023.", "4.1%"),
        ("US C-CPI was 4.1% in 2023.", "4.1%"),
        ("US breakeven inflation was 4.1% in 2023.", "4.1%"),
        ("US prime-age unemployment was 4.1% in 2023.", "4.1%"),
        ("US black unemployment was 4.1% in 2023.", "4.1%"),
        ("US insured unemployment was 4.1% in 2023.", "4.1%"),
        ("US unemployment was 4.1% in the month in 2023.", "4.1%"),
        ("US unemployment was 4.1% for the week in 2023.", "4.1%"),
        ("US GDP in manufacturing was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP from oil was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US nonfarm business GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US market-sector GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("Manufacturing's contribution to US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US CPI for food was 4.1% in 2023.", "4.1%"),
        ("US inflation in food was 4.1% in 2023.", "4.1%"),
        ("US inflation for energy was 4.1% in 2023.", "4.1%"),
        ("US inflation expectations were 4.1% in 2023.", "4.1%"),
        ("US expected inflation was 4.1% in 2023.", "4.1%"),
        ("US Hispanic unemployment was 4.1% in 2023.", "4.1%"),
        ("US unemployment among Hispanics was 4.1% in 2023.", "4.1%"),
        ("US Asian unemployment was 4.1% in 2023.", "4.1%"),
        ("US white unemployment was 4.1% in 2023.", "4.1%"),
        ("US unemployment aged 25 to 54 was 4.1% in 2023.", "4.1%"),
        ("The US 25-54 unemployment rate was 4.1% in 2023.", "4.1%"),
        ("US U-4 unemployment was 4.1% in 2023.", "4.1%"),
        ("US registered unemployment was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% month on month in 2023.", "4.1%"),
        ("US inflation was 4.1% m/m in 2023.", "4.1%"),
        ("US inflation was 4.1% from the prior month in 2023.", "4.1%"),
        ("Trailing twelve-month US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US inflation was 4.1% in the services sector in 2023.", "4.1%"),
        ("US inflation was 4.1% in services in 2023.", "4.1%"),
        ("US inflation ran at 4.1% for food in 2023.", "4.1%"),
        ("Consumer prices in the US were 4.1% on energy in 2023.", "4.1%"),
        ("US inflation was 4.1% in medical care in 2023.", "4.1%"),
        ("US inflation was 4.1% on energy markets in 2023.", "4.1%"),
        ("US CPI excluding shelter was 4.1% in 2023.", "4.1%"),
        ("The US CPI, excluding shelter, was 4.1% in 2023.", "4.1%"),
        ("US inflation ex-energy was 4.1% in 2023.", "4.1%"),
        ("US inflation less shelter was 4.1% in 2023.", "4.1%"),
        ("US core inflation was 4.1% in 2023.", "4.1%"),
        ("The core rate of US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in the past quarter of 2023.", "4.1%"),
        ("US inflation was 4.1% on the quarter in 2023.", "4.1%"),
        ("US GDP was $4.5 trillion on the quarter in 2023.", "$4.5 trillion"),
        ("In the past quarter, US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US GDP excluding agriculture was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("Excluding agriculture, US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("The US unemployment rate for Hispanics was 4.1% in 2023.", "4.1%"),
        ("US unemployment was 4.1% for Hispanics in 2023.", "4.1%"),
        ("US unemployment stood at 4.1% for Hispanics in 2023.", "4.1%"),
        ("The US unemployment rate aged 25 to 54 was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in the services industry in 2023.", "4.1%"),
        ("US inflation was 4.1% in the housing market in 2023.", "4.1%"),
        ("US inflation was 4.1% excluding food in 2023.", "4.1%"),
        ("US CPI was 4.1% ex-shelter in 2023.", "4.1%"),
        ("US inflation was 4.1% so far this year in 2023.", "4.1%"),
        ("US inflation was 4.1% over the past four quarters in 2023.", "4.1%"),
        ("US inflation was 4.1% on a monthly basis in 2023.", "4.1%"),
        ("US inflation was 4.1% at a monthly rate in 2023.", "4.1%"),
        ("US inflation rose 4.1 percentage points in 2023.", "4.1"),
        ("US GDP rose by $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP per worker was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("Working-day adjusted US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("Calendar-adjusted US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion ex agriculture in 2023.", "$4.5 trillion"),
        ("US GDP rose $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was up $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US saw a $4.5 trillion increase in GDP in 2023.", "$4.5 trillion"),
        ("US GDP for each worker was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("Calendar and seasonally adjusted US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US GDP adjusted for working days was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US inflation was 4.1% at a monthly pace in 2023.", "4.1%"),
        ("US inflation was 4.1% at a quarterly pace in 2023.", "4.1%"),
        ("US inflation was 4.1% on a 3-month basis in 2023.", "4.1%"),
        ("US inflation was 4.1% so far this calendar year in 2023.", "4.1%"),
        ("In 2023, US inflation was 4.1% in the year so far.", "4.1%"),
        ("US inflation was 4.1% versus the prior quarter in 2023.", "4.1%"),
        ("US inflation for apparel was 4.1% in 2023.", "4.1%"),
        ("Apparel inflation in the US was 4.1% in 2023.", "4.1%"),
        ("In the apparel category, US inflation was 4.1% in 2023.", "4.1%"),
        ("Working-day adjusted US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation rose 4.1 ppt in 2023.", "4.1"),
        ("US inflation was 4.1% q-o-q in 2023.", "4.1%"),
        ("US inflation was 4.1% sequentially in 2023.", "4.1%"),
        ("Trailing four quarters, US inflation was 4.1% in 2023.", "4.1%"),
        ("US unemployment was 4.1% for people without a high school diploma in 2023.",
         "4.1%"),
        ("US inflation was 4.1% for recreation in 2023.", "4.1%"),
        ("Recreation inflation in the US was 4.1% in 2023.", "4.1%"),
        ("In the recreation category, US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% for fuel in 2023.", "4.1%"),
        ("US inflation was 4.1% for airline fares in 2023.", "4.1%"),
        ("US inflation for house prices was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% quarter-over-quarter in 2023.", "4.1%"),
        ("US inflation was 4.1% q-on-q in 2023.", "4.1%"),
        ("US inflation was 4.1% over the quarter in 2023.", "4.1%"),
        ("US inflation was 4.1% in this quarter in 2023.", "4.1%"),
        ("Four-quarter US inflation was 4.1% in 2023.", "4.1%"),
        ("Trading-day adjusted US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP adjusted for trading days was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("Trading day and seasonally adjusted US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("Trading-day adjusted US inflation was 4.1% in 2023.", "4.1%"),
        ("US GDP jumped $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion higher in 2023.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion more in 2023.", "$4.5 trillion"),
        ("US GDP per-worker was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("On a per-worker basis, US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US unemployment was 4.1% for people with a high school diploma in 2023.",
         "4.1%"),
        ("US unemployment was 4.1% for veterans in 2023.", "4.1%"),
        ("US unemployment was 4.1% aged 16 to 19 in 2023.", "4.1%"),
        ("US unemployment was 4.1% for part-time workers in 2023.", "4.1%"),
        ("US inflation was 4.1% m-o-m in 2023.", "4.1%"),
        ("US inflation was 4.1% m.o.m. in 2023.", "4.1%"),
        ("US inflation was 4.1% quarter to quarter in 2023.", "4.1%"),
        ("US inflation was 4.1% from quarter to quarter in 2023.", "4.1%"),
        ("Over the latest quarter, US inflation was 4.1% in 2023.", "4.1%"),
        ("Last quarter, US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% over the latest quarter in 2023.", "4.1%"),
        ("US inflation for daycare was 4.1% in 2023.", "4.1%"),
        ("US inflation for day care was 4.1% in 2023.", "4.1%"),
        ("US inflation for food away from home was 4.1% in 2023.", "4.1%"),
        ("US inflation for motor vehicle insurance was 4.1% in 2023.", "4.1%"),
        ("US inflation for car insurance was 4.1% in 2023.", "4.1%"),
        ("US inflation for household energy was 4.1% in 2023.", "4.1%"),
        ("US inflation for fuel oil was 4.1% in 2023.", "4.1%"),
        ("US fuel oil inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation for health insurance was 4.1% in 2023.", "4.1%"),
        ("US inflation for public transportation was 4.1% in 2023.", "4.1%"),
        ("US inflation for financial services was 4.1% in 2023.", "4.1%"),
        ("US inflation for furniture was 4.1% in 2023.", "4.1%"),
        ("US inflation for parking was 4.1% in 2023.", "4.1%"),
        ("US inflation for computers was 4.1% in 2023.", "4.1%"),
        ("In the daycare category, US inflation was 4.1% in 2023.", "4.1%"),
        ("US GDP eased by $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was cut by $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was revised up by $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP swelled $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion saar in 2023.", "$4.5 trillion"),
        ("Not seasonally adjusted US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US SWDA GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("WDA US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP for each person employed was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US household consumption GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US government GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US unemployment was 4.1% for job losers in 2023.", "4.1%"),
        ("US unemployment was 4.1% for those aged 55 and over in 2023.", "4.1%"),
        ("US unemployment was 4.1% for people aged 20 and over in 2023.", "4.1%"),
        ("US unemployment was 4.1% for the self-employed in 2023.", "4.1%"),
        ("US unemployment was 4.1% part time for economic reasons in 2023.", "4.1%"),
        ("US unemployment was 4.1% on temporary layoff in 2023.", "4.1%"),
        ("US CPI was 4.1% in 2023, excluding shelter.", "4.1%"),
        ("US GDP was $4.5 trillion in 2023, excluding agriculture.",
         "$4.5 trillion"),
        ("US GDP in FY2023 was $4.5 trillion.", "$4.5 trillion"),
        ("In FY2023, US GDP was $4.5 trillion.", "$4.5 trillion"),
        ("US inflation in fiscal 2023 was 4.1%.", "4.1%"),
        ("Seasonally adjusted US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in 2023, seasonally adjusted.", "4.1%"),
        ("Seasonally adjusted US core CPI was 4.1% in 2023.", "4.1%"),
        ("In the financial services category, US inflation was 4.1% in 2023.",
         "4.1%"),
        ("US hospital inflation was 4.1% in 2023.", "4.1%"),
        ("US information inflation was 4.1% in 2023.", "4.1%"),
        ("US gas inflation was 4.1% in 2023.", "4.1%"),
        ("US hotel inflation was 4.1% in 2023.", "4.1%"),
        ("Under the FY2023 framework, US GDP was $4.5 trillion.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion in 2023, excluding agriculture from the total.",
         "$4.5 trillion"),
        ("US GDP was $4.5 trillion in 2023, net of oil.", "$4.5 trillion"),
        ("In the hospital category, US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation for the hospital was 4.1% in 2023.", "4.1%"),
        ("The seasonally adjusted path of US inflation was 4.1% in 2023.", "4.1%"),
        ("The seasonally adjusted trajectory of US inflation was 4.1% in 2023.",
         "4.1%"),
        ("In the hospital category, US core CPI was 4.1% in 2023.", "4.1%"),
        ("US GDP was $4.5 trillion excluding food from the total in 2023.",
         "$4.5 trillion"),
        ("Net of oil, US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion, net of oil in 2023.", "$4.5 trillion"),
        ("US inflation was 4.1% excluding energy from the total in 2023.", "4.1%"),
        ("US inflation was 4.1% in the hospital category in 2023.", "4.1%"),
        ("The seasonally adjusted reading of US inflation was 4.1% in 2023.",
         "4.1%"),
        ("The seasonally adjusted print of US inflation was 4.1% in 2023.",
         "4.1%"),
        ("US core CPI was 4.1% in the hospital category in 2023.", "4.1%"),
        ("The seasonally adjusted reading of US core CPI was 4.1% in 2023.",
         "4.1%"),
        ("US inflation was 4.1% in 2023, in the hospital category.", "4.1%"),
        ("US inflation was 4.1%, in the hospital category in 2023.", "4.1%"),
        ("US inflation was 4.1% in 2023, for the hospital.", "4.1%"),
        ("US inflation was 4.1% in 2023, on the seasonally adjusted reading.",
         "4.1%"),
        ("US core CPI was 4.1% in 2023, in the hospital category.", "4.1%"),
        ("US core CPI was 4.1% excluding shelter in 2023.", "4.1%"),
        ("US core CPI was 4.1% in 2023, excluding shelter.", "4.1%"),
        ("US core CPI was 4.1% excluding energy from the total in 2023.", "4.1%"),
        ("US core CPI was 4.1%, net of shelter in 2023.", "4.1%"),
        ("US core CPI was 4.1% in 2023, on the seasonally adjusted reading.",
         "4.1%"),
        ("US PCE inflation was 2.2% in the hospital category in 2023.", "2.2%"),
        ("US PCE inflation was 2.2% in 2023, in the hospital category.", "2.2%"),
        ("US PCE inflation was 2.2% excluding energy from the total in 2023.",
         "2.2%"),
        ("US core PCE inflation was 2.4% in the hospital category in 2023.",
         "2.4%"),
        ("Excluding shelter, US core CPI was 4.1% in 2023.", "4.1%"),
    ):
        r = sn.verify_fred(claim(sentence, raw))
        assert r.match_type == "no_data", sentence
        assert not r.withheld_refute
        assert not r.source_value
    for sentence, raw in (
        ("US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was sticky at 4.1% in 2023.", "4.1%"),
        ("The underlying story of US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% at an annual rate in 2023.", "4.1%"),
        ("US core CPI was 4.1% in 2023.", "4.1%"),
        ("The US jobless rate was 4.1% in 2023.", "4.1%"),
        ("Jobless claims fell, while US unemployment was 4.1% in 2023.", "4.1%"),
        ("The claim that US unemployment was 4.1% in 2023.", "4.1%"),
        ("US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("After the quarter, US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP in Saar was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion in 2023 compared with the quarter before.",
         "$4.5 trillion"),
        ("Real wages rose, while US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("Manufacturing rose, while US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US GDP at purchaser's prices was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US GDP at 2023 prices was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US U-3 unemployment was 4.1% in 2023.", "4.1%"),
        ("Black unemployment fell, while US unemployment was 4.1% in 2023.",
         "4.1%"),
        ("US unemployment was 4.1% in 2023 compared with the month before.",
         "4.1%"),
        ("The White House said US unemployment was 4.1% in 2023.", "4.1%"),
        ("After the Asian crisis, US unemployment was 4.1% in 2023.", "4.1%"),
        ("US unemployment for the year was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in 2023, as expected.", "4.1%"),
        ("The expected path of US inflation was 4.1% in 2023.", "4.1%"),
        ("US CPI for all urban consumers was 4.1% in 2023.", "4.1%"),
        ("The core of the story is that US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in the services report in 2023.", "4.1%"),
        ("US inflation was 4.1% in a services-led expansion in 2023.", "4.1%"),
        ("US inflation was 4.1% in service of a soft landing in 2023.", "4.1%"),
        ("Not excluding agriculture, US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("The US unemployment rate for the year was 4.1% in 2023.", "4.1%"),
        ("US unemployment stood at 4.1% for the year in 2023.", "4.1%"),
        ("US unemployment was 4.1% because of the foreign-born influx in 2023.",
         "4.1%"),
        ("US inflation was 4.1% over the past year in 2023.", "4.1%"),
        ("In the past quarter of 2023, US full-year GDP was $4.5 trillion.",
         "$4.5 trillion"),
        ("US inflation was 4.1% in 2023, up from the prior month.", "4.1%"),
        ("CPI for food was 3.1% in 2023, while US inflation was 4.1%.", "4.1%"),
        ("US GDP was $4.5 trillion in 2023 in the manufacturing report.",
         "$4.5 trillion"),
        ("Nonfarm payrolls rose, while US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US full-year GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP rose to $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US inflation was 4.1% in the monthly report in 2023.", "4.1%"),
        ("US inflation was 4.1% in the housing report in 2023.", "4.1%"),
        ("The story so far this year is that US inflation was 4.1% in 2023.", "4.1%"),
        ("So far this year, the ministry said US inflation was 4.1% in 2023.", "4.1%"),
        ("US unemployment was 4.1% (up 0.2 percentage points) in 2023.", "4.1%"),
        ("The ex-president said US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("In the past four quarters, US full-year GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US GDP climbed to $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was up to $4.5 trillion in 2023.", "$4.5 trillion"),
        ("Seasonally adjusted US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("The story so far this calendar year is that US inflation was 4.1% in 2023.",
         "4.1%"),
        ("In the year so far, the ministry said US inflation was 4.1% in 2023.",
         "4.1%"),
        ("US inflation was 4.1% in the quarterly report in 2023.", "4.1%"),
        ("US inflation was 4.1% in the q-o-q report in 2023.", "4.1%"),
        ("US inflation in fact was 4.1% in 2023.", "4.1%"),
        ("In the education ministry, US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in 2023 versus 8.0% in the prior quarter.", "4.1%"),
        ("The sequential story is that US inflation was 4.1% in 2023.", "4.1%"),
        ("US CPI for all items was 4.1% in 2023.", "4.1%"),
        ("Calendar-year US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in the recreation of a trend in 2023.", "4.1%"),
        ("US inflation was the fuel for the move at 4.1% in 2023.", "4.1%"),
        ("The airline said US inflation was 4.1% in 2023.", "4.1%"),
        ("House prices rose, while US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in the hospital in 2023.", "4.1%"),
        ("US inflation was 4.1% in this quarter's report in 2023.", "4.1%"),
        ("The four-quarter story is that US inflation was 4.1% in 2023.", "4.1%"),
        ("US GDP jumped to $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP surged to about $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion more or less in 2023.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion higher than France's in 2023.",
         "$4.5 trillion"),
        ("The trading day was long, and US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US unemployment was 4.1% on pages 16 to 19 of the report in 2023.",
         "4.1%"),
        ("US unemployment was 4.1% in some college towns in 2023.", "4.1%"),
        ("US unemployment was 4.1% as veterans returned in 2023.", "4.1%"),
        ("West High School said US unemployment was 4.1% in 2023.", "4.1%"),
        ("Mom said US inflation was 4.1% in 2023.", "4.1%"),
        ("Not seasonally adjusted US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in 2023, not seasonally adjusted.", "4.1%"),
        ("The information was that US inflation was 4.1% in 2023.", "4.1%"),
        ("Hotels said US inflation was 4.1% in 2023.", "4.1%"),
        ("The gas works said US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in the furniture of the argument in 2023.", "4.1%"),
        ("Daycare rose, while US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in the daycare report in 2023.", "4.1%"),
        ("Furniture rose, while US inflation was 4.1% in 2023.", "4.1%"),
        ("After parking a complaint, US inflation was 4.1% in 2023.", "4.1%"),
        ("Financial services rose, while US inflation was 4.1% in 2023.", "4.1%"),
        ("The SWDA conference said US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation was 4.1% in 2023 compared with the fourth quarter of 2022.",
         "4.1%"),
        ("Last quarter, the ministry said US inflation was 4.1% in 2023.", "4.1%"),
        ("US GDP eased to $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was revised to $4.5 trillion in 2023.", "$4.5 trillion"),
        ("The figures were revised, and US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("The estimate was revised by US GDP of $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US GDP was $4.5 trillion in 2023, not seasonally adjusted.",
         "$4.5 trillion"),
        ("Not seasonally adjusted, the ministry said US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("The SWDA conference said US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("The US government's GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US unemployment was 4.1% for people aged 16 and over in 2023.", "4.1%"),
        ("The 16 years and over US unemployment rate was 4.1% in 2023.", "4.1%"),
        ("Job losers rose, while US unemployment was 4.1% in 2023.", "4.1%"),
        ("Self-employed workers aside, US unemployment was 4.1% in 2023.", "4.1%"),
        ("Under the FY2024 framework, US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("After the fiscal crisis, US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("FYI, US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("In the FY2023 report, US GDP was $4.5 trillion in 2023.",
         "$4.5 trillion"),
        ("US GDP was $4.5 trillion in 2023, compared with fiscal 2022.",
         "$4.5 trillion"),
        ("Seasonally adjusted US unemployment was 4.1% in 2023.", "4.1%"),
        ("The seasonally adjusted story is that US inflation was 4.1% in 2023.",
         "4.1%"),
        ("Seasonally adjusted figures aside, US inflation was 4.1% in 2023.",
         "4.1%"),
        ("In the financial services report, US inflation was 4.1% in 2023.",
         "4.1%"),
        ("US GDP was $4.5 trillion in 2023 under the FY2024 framework.",
         "$4.5 trillion"),
        ("US GDP was $4.5 trillion in 2023, net of tax.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion in 2023, excluding agriculture from the total economy.",
         "$4.5 trillion"),
        ("The seasonally adjusted path of the story is that US inflation was 4.1% in 2023.",
         "4.1%"),
        ("The seasonally adjusted trajectory of the story is that US inflation was 4.1% in 2023.",
         "4.1%"),
        ("Seasonally adjusted path aside, US inflation was 4.1% in 2023.", "4.1%"),
        ("US inflation for the hospital report was 4.1% in 2023.", "4.1%"),
        ("US inflation for the hospital's board was 4.1% in 2023.", "4.1%"),
        ("In the hospital, US inflation was 4.1% in 2023.", "4.1%"),
        ("In the information category of the census, US inflation was 4.1% in 2023.",
         "4.1%"),
        ("US GDP was $4.5 trillion in 2023, excluding food from the total economy.",
         "$4.5 trillion"),
        ("Net of tax, US GDP was $4.5 trillion in 2023.", "$4.5 trillion"),
        ("US GDP was $4.5 trillion in 2023, net of oil in the report.",
         "$4.5 trillion"),
        ("US GDP was $4.5 trillion in the hospital category in 2023.",
         "$4.5 trillion"),
        ("The seasonally adjusted reading of the story is that US inflation was 4.1% in 2023.",
         "4.1%"),
        ("The seasonally adjusted print showed US inflation was 4.1% in 2023.",
         "4.1%"),
        ("US inflation was 4.1% in the gas sector of the economy in 2023.", "4.1%"),
        ("US core CPI was 4.1% in the hospital in 2023.", "4.1%"),
        ("US inflation was 4.1% net of energy in the report in 2023.", "4.1%"),
        ("US inflation was 4.1% in 2023 (net of energy in the report).", "4.1%"),
        ("US inflation was 4.1% in 2023, for the hospital report.", "4.1%"),
        ("US inflation was 4.1% in 2023, the seasonally adjusted story.", "4.1%"),
        ("US inflation was 4.1% in 2023, before the seasonally adjusted revision.",
         "4.1%"),
        ("US core CPI was 4.1% excluding the effects of a strike in 2023.", "4.1%"),
        ("Not excluding shelter, US core CPI was 4.1% in 2023.", "4.1%"),
        ("US core CPI was 4.1% in 2023, not net of shelter.", "4.1%"),
        ("US core CPI was 4.1% in 2023, for the hospital's board.", "4.1%"),
        ("US PCE inflation was 2.2% in 2023.", "2.2%"),
        ("US PCE inflation was 2.2% in the hospital in 2023.", "2.2%"),
        ("The seasonally adjusted reading of US PCE inflation was 2.2% in 2023.",
         "2.2%"),
        ("US PCE inflation was 2.2% in 2023, on the seasonally adjusted reading.",
         "2.2%"),
        ("US core PCE was 2.4% in 2023.", "2.4%"),
        ("US unemployment was 4.1% in 2023, in the hospital category.", "4.1%"),
        ("A seasonally adjusted reading showed that US inflation was 4.1% in 2023.",
         "4.1%"),
    ):
        r = sn.verify_fred(claim(sentence, raw))
        assert r.match_type in ("exact", "close"), sentence
    # Real GDP is the chained series. The nominal series must not answer it,
    # and a real-terms level must not answer for nominal GDP.
    data["GDP"] = {2023: 2000}
    data["GDPC1"] = {2023: 4500}
    real = sn.verify_fred(claim(
        "US real GDP was $4.5 trillion in 2023.", "$4.5 trillion"))
    assert real.match_type in ("exact", "close")
    assert "GDPC1" in real.source_text
    gross = sn.verify_fred(claim(
        "US real gross domestic product was $4.5 trillion in 2023.",
        "$4.5 trillion"))
    assert gross.match_type in ("exact", "close")
    assert "GDPC1" in gross.source_text
    terms = sn.verify_fred(claim(
        "US GDP in real terms was $4.5 trillion in 2023.", "$4.5 trillion"))
    assert terms.match_type == "no_data"
    assert not terms.source_value
    data["GDP"] = {2023: 4500}
    data["GDPC1"] = {2023: 2000}
    nominal = sn.verify_fred(claim(
        "US GDP was $4.5 trillion in 2023.", "$4.5 trillion"))
    assert nominal.match_type in ("exact", "close")
    assert "GDP" in nominal.source_text and "GDPC1" not in nominal.source_text
    # The price year is in the stub too, so a missed gate would match it.
    data["GDP"] = {2015: 4500, 2017: 4500, 2023: 4500}
    for sentence in (
        "US GDP in 2015 prices was $4.5 trillion in 2023.",
        "US GDP in constant 2015 prices was $4.5 trillion in 2023.",
        "US GDP in chained 2017 dollars was $4.5 trillion in 2023.",
        "US GDP in 2017 US dollars was $4.5 trillion in 2023.",
        "In constant 2015 prices, US GDP was $4.5 trillion in 2023.",
    ):
        r = sn.verify_fred(claim(sentence, "$4.5 trillion"))
        assert r.match_type == "no_data", sentence
        assert not r.source_value
    for sentence in (
        "US GDP was $4.5 trillion in chained (2017) dollars in 2023.",
        "US GDP was $4.5 trillion (2015 prices) in 2023.",
        "US GDP at prices of 2015 was $4.5 trillion in 2023.",
        "US GDP in 2017 USD was $4.5 trillion in 2023.",
        "US GDP in real 2015 dollars was $4.5 trillion in 2023.",
        "US GDP in chained-2017 dollars was $4.5 trillion in 2023.",
        "On a 2015 basis, US GDP was $4.5 trillion in 2023.",
        "US GDP was $4.5 trillion at previous year's prices in 2023.",
        "US GDP was $4.5 trillion in chain-linked volumes in 2023.",
    ):
        r = sn.verify_fred(claim(sentence, "$4.5 trillion"))
        assert r.match_type == "no_data", sentence
        assert not r.source_value
    # The chain year on real GDP is the chained series, not a reason to
    # drop it. Nominal GDP above stays quiet on the same words.
    data["GDPC1"] = {2017: 22000, 2023: 22000}
    real_chain = sn.verify_fred(claim(
        "US real GDP was $22 trillion in chained (2017) dollars in 2023.",
        "$22 trillion"))
    assert real_chain.match_type in ("exact", "close")
    assert "GDPC1" in real_chain.source_text
    real_volume = sn.verify_fred(claim(
        "US real GDP was $22 trillion in chain-linked volumes in 2023.",
        "$22 trillion"))
    assert real_volume.match_type in ("exact", "close")
    assert "GDPC1" in real_volume.source_text
    kept_basis = sn.verify_fred(claim(
        "US GDP was $4.5 trillion in 2023, compared with last year's prices.",
        "$4.5 trillion"))
    assert kept_basis.match_type in ("exact", "close")
    data["UNRATE"] = {(2023, 12): 4.1}
    month = sn.verify_fred(claim(
        "US unemployment was 4.1% in the month of December 2023.", "4.1%"))
    assert month.match_type in ("exact", "close")


def test_a_figure_does_not_take_a_series_named_elsewhere_in_the_sentence(fred):
    data, _ = fred
    data["CPIAUCNS"] = {2023: 4.1}
    data["UNRATE"] = {2023: 3.6}
    data["GDP"] = {2023: 27720.709}
    union = claim(
        "US inflation was the whole story in 2023, while the share of private "
        "workers in unions was 4.1%.",
        "4.1%",
    )
    r = sn.verify_fred(union)
    assert r.match_type == "no_data"
    assert not r.withheld_refute
    assert not r.source_value
    imports = claim(
        "US GDP was large in 2023, and goods imports were $27.7 trillion.",
        "$27.7 trillion",
    )
    r = sn.verify_fred(imports)
    assert r.match_type == "no_data"
    assert not r.withheld_refute
    assert not r.source_value
    # The same digits still match when the clause names the series, and a
    # later rate in the same series still matches.
    assert sn.verify_fred(claim(
        "US inflation was 4.1% in 2023.", "4.1%")).match_type in ("exact", "close")
    data["UNRATE"] = {2022: 3.6, 2024: 4.0}
    sent = "US unemployment averaged 3.6% in 2022 and 4.0% in 2024."
    parts = sn._split_series({"sentence": sent, "numbers": ["3.6%", "4.0%"]})
    later = sn.decompose_claim(next(p for p in parts if p["numbers"] == ["4.0%"]))
    assert "2024" in later.time_period
    assert sn.verify_fred(later).match_type == "exact"
    # A new measure with no copula is still not the series named beside it.
    for sentence, raw in (
        ("US GDP was large in 2023, and the import bill came to $27.7 trillion.",
         "$27.7 trillion"),
        ("US GDP was large in 2023 and goods imports totaled $27.7 trillion.",
         "$27.7 trillion"),
        ("US GDP was large in 2023, with an import bill of $27.7 trillion.",
         "$27.7 trillion"),
        ("US inflation was the story in 2023, while union membership stood at 4.1%.",
         "4.1%"),
        ("US GDP was large in 2023 and goods imports $27.7 trillion.",
         "$27.7 trillion"),
        ("US GDP was large in 2023, goods imports $27.7 trillion.",
         "$27.7 trillion"),
        ("US inflation was the story in 2023, union membership 4.1%.",
         "4.1%"),
        ("US GDP was large in 2023 and goods imports reaching $27.7 trillion.",
         "$27.7 trillion"),
    ):
        r = sn.verify_fred(claim(sentence, raw))
        assert r.match_type == "no_data", sentence
        assert not r.withheld_refute
        assert not r.source_value
    # The same digits in a second clause that states another measure are not
    # a match: this claim cannot tell the two 4.1% figures apart.
    twin = claim(
        "US inflation was 4.1% in 2023, while the union share was 4.1%.",
        "4.1%",
    )
    r = sn.verify_fred(twin)
    assert r.match_type == "no_data"
    assert not r.source_value
    # A label before ", at" is the measure. The series named in the previous
    # clause is not, unless that label is the series. A preposition is not a label.
    data["UNRATE"] = {2023: 3.6}
    for sentence in (
        "US unemployment, at 3.6% in 2023, was the lowest in decades.",
        "After a long expansion, at 3.6% in 2023, US unemployment was low.",
        "For comparison, at 3.6% in 2023, US unemployment was low.",
        "US inflation was high in 2023, at 4.1%.",
    ):
        raw = "4.1%" if "4.1%" in sentence else "3.6%"
        r = sn.verify_fred(claim(sentence, raw))
        assert r.match_type in ("exact", "close"), sentence
    for sentence in (
        "US inflation was the story in 2023, union membership, at 4.1%.",
        "US inflation was the story in 2023, for union membership, at 4.1%.",
        "US inflation was high in 2023, at 4.1% for union membership.",
    ):
        r = sn.verify_fred(claim(sentence, "4.1%"))
        assert r.match_type == "no_data", sentence
        assert not r.source_value


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
    assert r.match_type == "no_data"
    assert r.withheld_refute
    assert "square kilometres" in r.source_text


def test_wikidata_keeps_a_wrong_length(wikidata):
    wikidata["Q5513"] = {"label": "Lake Baikal", "claims": {"P2043": [_quantity(636, "Q828224")]}}
    r = sn.verify_wikidata(claim("Lake Baikal is 890 km long.", "890"))
    assert r.match_type == "no_data"
    assert r.withheld_refute
    assert r.source_value is not None


def test_wikidata_feet_for_metres(wikidata):
    wikidata["Q1"] = {"label": "Gateway Arch", "claims": {"P2048": [_quantity(192, "Q11573")]}}
    r = sn.verify_wikidata(claim("The Gateway Arch is 630 metres tall.", "630"))
    assert r.match_type == "no_data"
    assert r.withheld_refute
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
    off = sn.verify_wikidata(claim("Acme Corporation had 120,000 employees in 2024.", "120,000"))
    assert off.match_type == "no_data"
    assert off.withheld_refute
    assert off.source_value is not None


def test_wikidata_a_population_without_a_year_only_confirms(wikidata):
    wikidata["Q1"] = {"label": "Lyon", "claims": {"P1082": [_quantity(522250, "Q199", 2021)]}}
    assert sn.verify_wikidata(claim("Lyon has a population of 522,250 people.", "522,250")).match_type == "exact"
    assert sn.verify_wikidata(claim("Lyon has a population of 900,000 people.", "900,000")).match_type == "no_data"


def test_wikidata_routing():
    assert sn.verify_wikidata in sn._classify_and_route(claim("Lake Baikal is 636 km long.", "636"))
    assert sn.verify_wikidata not in sn._classify_and_route(claim("Germany's population was 84 million in 2023.", "84 million"))


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


def test_a_matching_radius_of_another_body_is_not_a_tick(wikidata):
    wikidata["Q1"] = {"label": "Pluto", "claims": {"P2120": [_quantity(1188.3, "Q828224")]}}
    d = claim("Ganymede: radius of 1,188 km.", "1,188")
    d.subject = "Pluto"
    r = sn.verify_wikidata(d)
    assert r.match_type == "no_data"
    assert not r.withheld_refute
    assert not r.source_value


def test_a_length_that_matches_an_elevation_is_not_a_tick(wikidata):
    wikidata["Q1"] = {"label": "Matterhorn", "claims": {"P2044": [_quantity(4478, "Q11573")]}}
    d = claim("The Matterhorn tunnel is 4,478 m long.", "4,478")
    d.metric = "height"
    r = sn.verify_wikidata(d)
    assert r.match_type == "no_data"
    assert not r.withheld_refute
    assert not r.source_value


def test_a_count_does_not_take_a_height_named_earlier_in_the_sentence(wikidata):
    wikidata["Q1"] = {"label": "Matterhorn", "claims": {"P2044": [_quantity(4478, "Q11573")]}}
    for sentence in (
        "The Matterhorn is 4,478 m tall, and the herd was counted at 4478.",
        "The Matterhorn is 4,478 m tall and the herd was counted at 4478.",
    ):
        d = claim(sentence, "4478")
        d.metric = "height"
        r = sn.verify_wikidata(d)
        assert r.match_type == "no_data", sentence
        assert not r.withheld_refute
        assert not r.source_value
    for sentence in (
        "The Matterhorn is 4,478 m tall, and the herd numbered 4478.",
        "The Matterhorn is 4,478 m tall, and the herd reached 4478.",
        "The Matterhorn is 4,478 m tall, and the herd reaching 4478.",
        "The Matterhorn is 4,478 m tall and the herd 4478.",
    ):
        numbered = claim(sentence, "4478")
        numbered.metric = "height"
        r = sn.verify_wikidata(numbered)
        assert r.match_type == "no_data", sentence
        assert not r.source_value
    still = claim("The Matterhorn is 4,478 m tall.", "4,478")
    still.metric = "height"
    assert sn.verify_wikidata(still).match_type == "exact"


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
    r = sn.verify_wikidata(d)
    assert r.match_type == "no_data"
    assert r.withheld_refute
    assert r.source_value is not None


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
    r = sn.verify_world_bank(d)
    # The World Bank earned refute on v32 (2026-11-28).
    assert r.match_type == "contradicted"
    assert not r.withheld_refute
    assert r.source_value == 84.04
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
    r = sn.verify_wikidata(d)
    assert r.match_type == "no_data"
    assert r.withheld_refute
    assert "feet" in r.source_text


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


# ------------------------------------------------ a currency is not the country

import pytest as _pt_us  # noqa: E402

import source_network as _sn_us  # noqa: E402

_TURKIYE = (
    "Turkiye's recent economic story is one of fast but volatile growth.\n\n"
    "| Measure | Year | Value |\n|---|---|---|\n"
    "| Consumer price inflation | 2016 | 7.8% |\n"
    "| GDP, current US dollars | 2018 | $788.4 billion |\n"
)


def test_a_country_written_the_world_banks_way_is_not_the_us():
    """v20, 2026-11-26: a Turkiye answer quoting GDP in current US dollars
    read as a US document, and FRED refuted its inflation and unemployment
    with US series (and could confirm a Turkish figure that equalled a US one)."""
    assert not _sn_us._doc_is_us(_TURKIYE)
    assert not _sn_us._doc_no_country(_TURKIYE)


@_pt_us.mark.parametrize("name", [
    "Turkiye", "Türkiye", "Viet Nam", "Slovak Republic", "Kyrgyz Republic", "Lao PDR",
    "Cabo Verde", "Syrian Arab Republic", "Sao Tome and Principe", "West Bank and Gaza",
    "St. Lucia", "Cayman Islands", "Curacao",
])
def test_world_bank_country_names_are_countries(name):
    assert _sn_us._COUNTRY_NAMES_RE.search(f"Growth in {name} was 3.1% in 2022.")


@_pt_us.mark.parametrize("text, is_us", [
    ("GDP was $1.95 trillion in current US dollars in 2022.", False),
    ("Exports reached US$12.4 billion in 2023.", False),
    ("The US unemployment rate averaged 3.6% in 2023.", True),
    ("Inflation in the U.S. was 4.1% in 2023.", True),
])
def test_a_dollar_amount_does_not_name_the_us(text, is_us):
    assert _sn_us._doc_is_us(text) is is_us


@_pt_us.mark.parametrize("text, lead", [
    # v22: Macao's figures were bound to China and Sint Maarten's to the
    # Netherlands, its parent named later in the answer.
    (("Macao is a special administrative region of China. About 0.7 million people "
     "lived there in 2019."), "Macao"),
    (("Sint Maarten, the Dutch half of the island, depends on tourism. Its economy was "
     "worth $1.4 billion in 2017, and ties to the Netherlands remain close."), "Sint Maarten"),
])
def test_a_territory_leads_its_own_answer(text, lead):
    got, _ = _sn_us._lead_country(text)
    assert got == lead


@_pt_us.mark.parametrize("name, code", [
    ("macao", "MO"), ("macau", "MO"), ("sint maarten", "SX"), ("hong kong", "HK"),
])
def test_territories_have_world_bank_codes(name, code):
    assert _sn_us._wb_country_code(name) == code


def test_a_country_named_once_in_passing_cannot_refute(monkeypatch):
    """v23 Mexico: the answer never names Mexico; "a structural story tied to
    the US" made the US its subject, and World Bank refuted Mexico's figures
    with US data. A refutation needs its country settled: named in the
    figure's own sentence, or at least twice in the document."""
    monkeypatch.setattr(_sn_us, "_REFUTE_TRIAL", frozenset({"World Bank"}))
    doc = ("**Short version:** a sharp hit in 2020 and a structural story tied to the US.\n\n"
           "**The hit.** Growth printed -8.4% in 2020.")
    d = _sn_us.ClaimDecomposition(subject="United States", metric="growth", value=-8.4,
                                  raw_value="-8.4%", unit="percent", time_period="2020",
                                  sentence="Growth printed -8.4% in 2020.",
                                  doc_country_counts={"United States": 1})
    assert not _sn_us._country_settled(d, "United States")
    d2 = _sn_us.ClaimDecomposition(subject="United States", metric="growth", value=-8.4,
                                   raw_value="-8.4%", unit="percent", time_period="2020",
                                   sentence="US growth printed -8.4% in 2020.",
                                   doc_country_counts={"United States": 1})
    assert _sn_us._country_settled(d2, "United States")
    d3 = _sn_us.ClaimDecomposition(subject="Mexico", metric="growth", value=-8.4,
                                   raw_value="-8.4%", unit="percent", time_period="2020",
                                   sentence="Growth printed -8.4% in 2020.",
                                   doc_country_counts={"Mexico": 3})
    assert _sn_us._country_settled(d3, "Mexico")
    assert doc  # the document the case came from


@_pt_us.mark.parametrize("name, code", [
    ("Republic of the Congo", "CG"), ("Democratic Republic of the Congo", "CD"), ("DRC", "CD"),
])
def test_the_two_congos_are_two_countries(name, code):
    """v22: the Republic of the Congo's growth was refuted with the DRC's."""
    found = _sn_us._COUNTRY_NAMES_RE.search(f"Growth in {name} was 1.9% in 2023.").group(1)
    canonical = _sn_us._COUNTRY_CANONICAL.get(found, found)
    assert _sn_us._wb_country_code(canonical) == code
