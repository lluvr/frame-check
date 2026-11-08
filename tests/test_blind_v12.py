"""Faults from the natural-plus-planted blind set (heldout_docs_v12) and the
US macro probes behind it. Most are a true number contradicted, the worst
error the verifier can make. No network here.
"""

import types
import urllib.parse

import pytest

import claim_reader
import source_network as sn


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
        for key, value in sorted(data.get(q["series_id"], {}).items(), key=lambda kv: str(kv[0])):
            # Like FRED: an annual query returns years, a monthly one months.
            if q.get("frequency") and isinstance(key, tuple) != (q["frequency"] == "m"):
                continue
            date = f"{key[0]}-{key[1]:02d}-01" if isinstance(key, tuple) else f"{key}-01-01"
            if q["observation_start"][:10] <= date <= q["observation_end"][:10]:
                rows.append({"date": date, "value": str(value)})
        return {"observations": rows}

    monkeypatch.setattr(sn, "_fetch_json", fake)
    return data, urls


# ------------------------------------------------ FRED: the series named

def test_core_cpi_is_its_own_series(fred):
    data, urls = fred
    data["CPIAUCNS"] = {(2023, 12): 3.35}
    data["CPILFENS"] = {(2023, 12): 3.93}
    r = sn.verify_fred(claim("US core CPI inflation was 3.9% in December 2023.", "3.9%"))
    assert r.match_type in ("exact", "close")
    assert "CPILFENS" in urls[0]


def test_pce_inflation_is_not_cpi(fred):
    data, urls = fred
    data["CPIAUCNS"] = {2023: 4.12}
    data["PCEPI"] = {2023: 3.7}
    data["PCEPILFE"] = {2023: 4.1}
    r = sn.verify_fred(claim("In the United States, PCE inflation averaged 3.7% in 2023.", "3.7%"))
    assert r.match_type in ("exact", "close") and "PCEPI" in urls[-1]
    r = sn.verify_fred(claim("US core PCE inflation averaged 4.1% in 2023.", "4.1%"))
    assert r.match_type in ("exact", "close") and "PCEPILFE" in urls[-1]


def test_core_inflation_without_a_named_index_is_not_refuted(fred):
    data, _ = fred
    data["CPIAUCNS"] = {2023: 4.12}
    d = claim("US core inflation, which excludes food and energy, averaged 4.8% in 2023.", "4.8%")
    assert sn.verify_fred(d).match_type != "contradicted"


def test_a_two_year_treasury_is_not_the_ten_year(fred):
    data, urls = fred
    data["DGS10"] = {2023: 3.96}
    data["DGS2"] = {2023: 4.58}
    r = sn.verify_fred(claim("The US 2-year Treasury yield averaged 4.58% in 2023.", "4.58%"))
    assert r.match_type in ("exact", "close") and "DGS2" in urls[-1]
    # A maturity with no series here says nothing.
    r = sn.verify_fred(claim("The US 7-year Treasury yield averaged 4.2% in 2023.", "4.2%"))
    assert r.match_type == "no_data"


@pytest.mark.parametrize("sentence", [
    "The average US credit card interest rate was 21.5% in 2023.",
    "The average US auto loan interest rate was 7.5% in 2023.",
    "US savings account interest rates averaged 0.5% in 2023.",
])
def test_a_consumer_interest_rate_is_not_the_funds_rate(fred, sentence):
    data, _ = fred
    data["FEDFUNDS"] = {2023: 5.02}
    raw = sentence.split(" was ")[-1].split(" averaged ")[-1].split(" in ")[0]
    assert sn.verify_fred(claim(sentence, raw)).match_type == "no_data"


def test_a_mortgage_interest_rate_is_the_mortgage_series(fred):
    data, urls = fred
    data["FEDFUNDS"] = {2023: 5.02}
    data["MORTGAGE30US"] = {2023: 6.81}
    d = claim("The average 30-year fixed mortgage interest rate in the US was 6.8% in 2023.", "6.8%")
    assert sn.verify_fred(d).match_type in ("exact", "close")
    assert "MORTGAGE30US" in urls[-1]


def test_a_count_is_not_a_rate(fred):
    data, _ = fred
    data["FEDFUNDS"] = {(2023, 7): 5.12}
    d = claim("The Fed raised rates 11 times, taking the federal funds target range to "
              "5.25% to 5.50% in July 2023.", "11")
    assert sn.verify_fred(d).match_type == "no_data"


def test_one_end_of_a_target_range_is_never_refuted(fred):
    data, _ = fred
    data["FEDFUNDS"] = {(2023, 7): 5.12, 2023: 5.02}
    sentence = ("The Fed raised rates 11 times, taking the federal funds target range to "
                "5.25% to 5.50% in July 2023.")
    for raw in ("5.25%", "5.50%"):
        assert sn.verify_fred(claim(sentence, raw)).match_type != "contradicted"


def test_a_figure_for_part_of_the_year_is_not_refuted_by_its_average(fred):
    data, _ = fred
    data["MORTGAGE30US"] = {2023: 6.81}
    d = claim("The average 30-year fixed mortgage rate reached 7.79% that same month "
              "according to Freddie Mac.", "7.79%", inherited_year="2023")
    assert sn.verify_fred(d).match_type != "contradicted"


def test_a_year_end_figure_is_read_in_december(fred):
    data, urls = fred
    data["CPILFENS"] = {2023: 4.8, (2023, 12): 3.93}
    d = claim("US core CPI ended 2023 at 3.9%.", "3.9%")
    assert sn.verify_fred(d).match_type in ("exact", "close")
    assert "frequency=m" in urls[-1]


# ------------------------------------------------ World Bank

def test_a_count_of_jobs_is_not_gdp(monkeypatch):
    monkeypatch.setattr(sn, "_wb_country_code", lambda c: "US")
    monkeypatch.setattr(sn, "_fetch_json", lambda url, *a, **k: [
        {}, [{"value": 27.8e12, "date": "2023"}]])
    d = claim("US real GDP grew 2.5% in 2023, and the economy added about 3 million jobs.",
              "3 million")
    assert sn.verify_world_bank(d).match_type != "contradicted"


def test_core_inflation_is_not_the_world_banks_inflation():
    assert sn._detect_wb_indicator(
        "US core inflation averaged 4.8% in 2023.", "")[0] is None


# ------------------------------------------------ SEC

def row(year, val):
    return {"start": f"{year}-01-01", "end": f"{year}-12-31", "val": val,
            "fy": year, "fp": "FY", "form": "10-K", "filed": f"{year + 1}-02-20"}


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


def test_a_figure_in_parentheses_is_negative(filings):
    filings["EarningsPerShareDiluted"] = [row(2024, -1.51)]
    d = claim("Acme's diluted EPS in FY2024 was (1.51).", "(1.51)", metric="eps")
    assert sn.verify_sec_edgar(d).match_type in ("exact", "close")


def test_a_figure_in_another_currency_is_not_compared_with_dollars(filings):
    filings["ResearchAndDevelopmentExpense"] = [row(2023, 904.696e6)]
    d = claim("Acme's FY2023 R&D was €904.7M.", "€904.7M")
    assert d.subject
    assert sn.verify_sec_edgar(d).match_type == "no_data"


# ------------------------------------------------ figures that are not values

def test_a_split_ratio_is_not_a_figure():
    assert sn._is_a_ratio("Diluted EPS: $44.34 (before the 50-for-1 stock split in 2024).", "50")
    assert sn._is_a_ratio("a 3:1 split", "3")
    assert not sn._is_a_ratio("EPS was $50 for fiscal 2024.", "$50")


# ------------------------------------------------ derivations

def _result(sentence, value, metric, verdict, claim_type="direct"):
    return types.SimpleNamespace(
        verdict=verdict, confidence=0.9, detail="", best_source="SEC Filing",
        decomposition=types.SimpleNamespace(
            heading="Chipotle 2023", sentence=sentence, value=value, metric=metric,
            claim_type=claim_type,
        ),
    )


def test_a_growth_rate_is_not_refuted_by_unrelated_figures():
    growth = _result("Comparable restaurant sales: up 7.9%.", 7.9, "", "verified", "derived")
    results = [
        _result("Revenue: about $9.9 billion", 9.9e9, "revenue", "verified"),
        _result("Net income: $1.23 billion", 1.23e9, "profit", "verified"),
        _result("Diluted EPS: $44.34", 44.34, "eps", "verified"),
        growth,
    ]
    sn.check_derivations(results)
    assert growth.verdict == "verified"


def test_a_growth_rate_is_refuted_by_its_own_two_years():
    growth = _result("Revenue grew 25% in 2023.", 25, "revenue", "unverifiable", "derived")
    results = [
        _result("Revenue was $4,403.6 million in 2023", 4403.6e6, "revenue", "verified"),
        _result("Revenue was $4,095.1 million in 2022", 4095.1e6, "revenue", "verified"),
        growth,
    ]
    sn.check_derivations(results)
    assert growth.verdict == "contradicted"


def test_a_growth_rate_matching_one_pair_of_its_metric_stands():
    growth = _result("Revenue grew 7.5% in 2023.", 7.5, "revenue", "unverifiable", "derived")
    results = [
        _result("Net income was $340 million", 340e6, "profit", "verified"),
        _result("Revenue was $4,403.6 million in 2023", 4403.6e6, "revenue", "verified"),
        _result("Revenue was $4,095.1 million in 2022", 4095.1e6, "revenue", "verified"),
        growth,
    ]
    sn.check_derivations(results)
    assert growth.verdict != "contradicted"


# ------------------------------------------------ the reader's time

def test_the_reader_does_not_retry_past_its_timeout(monkeypatch):
    """The SDK retries twice by default, so a 12 second timeout became 37
    seconds in the blind runs and used up the whole verification budget."""
    seen = {}

    class Client:
        def with_options(self, **kw):
            seen.update(kw)
            return self

        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    return types.SimpleNamespace(choices=[])

    monkeypatch.setattr("llm_client.xai_openai_client", lambda: Client())
    claim_reader._call_model("text")
    assert seen.get("max_retries") == 0


# ------------------------------------------------ found by the fast regression

def test_a_table_row_names_its_own_series(fred):
    """A flattened table puts the next row's series name nearer the figure."""
    data, urls = fred
    data["DGS10"] = {2022: 2.95}
    data["MORTGAGE30US"] = {2022: 5.34}
    d = claim("Effective fed funds rate in 2022 was 2.41%. 10-year Treasury yield in 2022 "
              "was 2.95%. 30-year fixed mortgage in 2022 was 6.34%.", "2.95%")
    assert sn.verify_fred(d).match_type in ("exact", "close")
    assert "DGS10" in urls[-1]


def test_an_appended_label_does_not_replace_the_series_named(fred):
    data, urls = fred
    data["CPILFENS"] = {2024: 3.4, (2024, 12): 3.24}
    data["CPIAUCNS"] = {2024: 2.95}
    d = claim("core CPI was 3.2%. (inflation)", "3.2%",
              full_sentence="Headline CPI inflation ended the year at 2.9% year over year "
                            "in December, while core CPI was 3.2%.",
              inherited_year="2024")
    assert sn.verify_fred(d).match_type != "contradicted"
    assert "CPILFENS" in urls[-1]


def test_a_growth_rate_a_source_confirmed_is_not_overturned():
    growth = _result("Comparable restaurant sales: up 7.9%.", 7.9, "revenue", "verified", "derived")
    results = [
        _result("Revenue was $9.9 billion in 2023", 9.9e9, "revenue", "verified"),
        _result("Revenue was $8.6 billion in 2022", 8.6e9, "revenue", "verified"),
        growth,
    ]
    sn.check_derivations(results)
    assert growth.verdict == "verified"


def test_a_growth_rate_whose_sentence_names_another_measure_is_not_derived():
    growth = _result("Comparable restaurant sales: up 7.9%.", 7.9, "revenue", "unverifiable", "derived")
    results = [
        _result("Revenue was $9.9 billion in 2023", 9.9e9, "revenue", "verified"),
        _result("Revenue was $8.6 billion in 2022", 8.6e9, "revenue", "verified"),
        growth,
    ]
    sn.check_derivations(results)
    assert growth.verdict != "contradicted"


def test_a_loss_in_parentheses_keeps_its_spelled_out_scale():
    from prose import plain_prose
    text = plain_prose("Net loss in 2023 was $(340.3) million.")
    assert "$340.3 million (a loss)" in text


def test_a_hung_reader_gives_up_at_its_deadline(monkeypatch):
    """The SDK timeout bounds each socket read, not the call: a reply that
    trickles in can hold the whole check. The reading has its own deadline."""
    import time
    monkeypatch.setenv("CLAIM_READER", "on")
    monkeypatch.setattr(claim_reader, "enabled", lambda: True)
    monkeypatch.setattr(claim_reader, "READER_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(claim_reader, "_call_model", lambda doc: time.sleep(3) or "")
    start = time.monotonic()
    assert claim_reader.read_figures("Acme made $5 billion in 2024 (hung).") == []
    assert time.monotonic() - start < 1.5
