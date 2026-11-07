"""The reader may only say what the document supports. No network here."""

import json
import re

import pytest

import claim_reader as cr
import source_network as sn
from claim_analysis import analyze_claims
from prose import plain_prose

DOC = (
    "FOR IMMEDIATE RELEASE\n\nFull year highlights from Federal Signal Corporation "
    "for the year ended December 31, 2025.\n\nNet sales were $2.18 billion, compared "
    "with $1.86 billion in 2024. We expect sales of $3 billion by 2028.\n"
)


def reading(*figures):
    return json.dumps({"figures": list(figures)})


def fig(figure, **fields):
    return {
        "figure": figure, "entity": "Federal Signal Corporation", "metric": "revenue",
        "attribute": "", "period": "2025", "period_in_sentence": False,
        "status": "stated", **fields,
    }


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setenv("CLAIM_READER", "on")
    monkeypatch.setattr(cr, "enabled", lambda: True)
    cr._cache.clear()
    answer = {"text": reading()}
    monkeypatch.setattr(cr, "_call_model", lambda document: answer["text"])
    return answer


def parse(document):
    doc = plain_prose(document)
    claims = sn._prepare_claims(analyze_claims(document)["claims"], doc)
    claims = sn._apply_reader(claims, doc)
    return {
        d.raw_value.strip(): d for d in (
            sn.decompose_claim(c, doc_text=doc) for c in claims
        )
    }


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("CLAIM_READER", raising=False)
    assert cr.enabled() is False
    assert cr.read_figures(DOC) == []


def test_a_figure_not_in_the_document_is_dropped(model):
    model["text"] = reading(fig("$2.18 billion"), fig("$9.99 billion"))
    assert [f["figure"] for f in cr.read_figures(DOC)] == ["$2.18 billion"]


def test_an_entity_not_in_the_document_is_dropped(model):
    model["text"] = reading(fig("$2.18 billion", entity="Oshkosh Corporation"))
    assert cr.read_figures(DOC)[0]["entity"] == ""


def test_a_metric_outside_the_list_is_dropped(model):
    model["text"] = reading(fig("$2.18 billion", metric="vibes"))
    assert cr.read_figures(DOC)[0]["metric"] == ""


def test_a_malformed_period_is_dropped(model):
    model["text"] = reading(fig("$2.18 billion", period="last year"))
    assert cr.read_figures(DOC)[0]["period"] == ""


@pytest.mark.parametrize("garbage", ["", "not json", "[1,2]", '{"figures": "x"}'])
def test_garbage_gives_no_reading(model, garbage):
    model["text"] = garbage
    assert cr.read_figures(DOC) == []


def test_a_failing_model_gives_no_reading(monkeypatch):
    monkeypatch.setattr(cr, "enabled", lambda: True)
    cr._cache.clear()

    def boom(document):
        raise TimeoutError("slow")

    monkeypatch.setattr(cr, "_call_model", boom)
    assert cr.read_figures(DOC) == []


def test_the_reading_sets_subject_metric_and_year(model):
    model["text"] = reading(fig("$2.18 billion"))
    d = parse(DOC)["$2.18 billion"]
    assert d.subject == "Federal Signal Corporation"
    assert d.metric == "revenue"
    assert d.time_period == "2025"
    assert d.year_inherited


def test_a_year_named_in_the_sentence_is_not_inherited(model):
    model["text"] = reading(fig("$1.86 billion", period="2024", period_in_sentence=True))
    d = parse(DOC)["$1.86 billion"]
    assert d.time_period == "2024"
    assert not d.year_inherited


def test_a_forecast_is_a_projection(model):
    model["text"] = reading(fig("$3 billion", status="forecast", period="2028"))
    assert parse(DOC)["$3 billion"].claim_type == "projection"


def test_a_figure_the_rules_missed_is_added(model):
    doc = "Acme Corporation had a good year.\n\nRevenue was 12.5 million dollars in 2025.\n"
    model["text"] = reading(fig("12.5 million dollars", entity="Acme Corporation", period="2025"))
    parsed = parse(doc)
    assert any(d.subject == "Acme Corporation" for d in parsed.values())


def test_rule_reading_stands_without_the_model(monkeypatch):
    monkeypatch.setattr(cr, "enabled", lambda: False)
    parsed = parse("Apple reported revenue of $383 billion in 2023.")
    assert parsed["$383 billion"].subject == "Apple"


def test_each_reader_figure_gets_its_own_claim(model):
    doc = "Acme's revenue was $5 billion and net income $1 billion in 2025.\n"
    model["text"] = reading(
        fig("$5 billion", entity="Acme", metric="revenue", period_in_sentence=True),
        fig("$1 billion", entity="Acme", metric="profit", period_in_sentence=True),
    )
    parsed = parse(doc)
    assert parsed["$5 billion"].metric == "revenue"
    assert parsed["$1 billion"].metric == "profit"


def test_reader_metrics_all_map_to_something_the_checkers_know():
    known = set(sn._METRIC_PATTERNS) | {"gdp_per_capita", "inflation", "unemployment", "life_expectancy"}
    assert set(cr.METRICS) - {"other"} <= known


def test_a_forecast_needs_forecast_wording(model):
    doc = "Kennametal FY26 review.\n\nSales were $2.36B in FY2026.\n"
    model["text"] = reading(fig("$2.36B", entity="Kennametal", period="FY2026", status="forecast"))
    assert parse(doc)["$2.36B"].claim_type != "projection"


def test_the_figures_metric_picks_the_series(model):
    doc = ("Mauritius: the economy reached $16.2bn in 2025, putting GDP per head "
           "at about $13,000.\n")
    model["text"] = reading(
        fig("$16.2bn", entity="Mauritius", metric="gdp", period_in_sentence=True),
        fig("$13,000", entity="Mauritius", metric="gdp_per_capita", period_in_sentence=True),
    )
    parsed = parse(doc)
    total = parsed["$16.2bn"]
    assert sn._detect_wb_indicator(total.sentence, total.metric)[0] == "NY.GDP.MKTP.CD"
    head = next(v for k, v in parsed.items() if "13,000" in k)
    assert sn._detect_wb_indicator(head.sentence, head.metric)[0] == "NY.GDP.PCAP.CD"


def test_a_specific_physical_metric_is_not_overridden(model):
    doc = "The Moon's mean radius is 2,240 km.\n"
    model["text"] = reading(fig("2,240 km", entity="Moon", metric="length", period=""))
    assert parse(doc)["2,240"].metric == "diameter"


def test_a_diameter_does_not_confirm_a_radius():
    d = sn.decompose_claim({"sentence": "The Moon's mean radius is 2,240 km.", "numbers": ["2,240"]})
    page = "The South Pole-Aitken basin, some 2,240 km (1,390 mi) in diameter, is the largest crater."
    assert sn._match_in_text(page, 2240.0, d.sentence, decomp=d)[0] is None
    ok = "The Moon has a mean radius of 1,737 km and a diameter of 3,475 km."
    assert sn._match_in_text(ok, 1737.0, "The Moon's radius is 1,737 km.", decomp=d)[0] == 1737.0


def test_the_reader_counts_against_the_verification_budget(monkeypatch):
    import time
    monkeypatch.setattr(sn, "SN_BUDGET_SECONDS", 0.2)
    monkeypatch.setattr(sn, "read_figures", lambda doc: time.sleep(0.4) or [])
    called = []
    monkeypatch.setattr(sn, "_classify_and_route", lambda d: called.append(d) or [])
    sn.verify_claims_source_network(
        [{"sentence": "Apple reported revenue of $383 billion in 2023.", "numbers": ["$383 billion"]}],
        doc_text="Apple reported revenue of $383 billion in 2023.",
    )
    assert not called


def test_the_reader_timeout_leaves_room_for_the_sources():
    assert cr.READER_TIMEOUT_SECONDS <= 12


def test_a_metric_only_the_reader_supplies_cannot_refute(model):
    doc = "YETI fiscal 2025 numbers.\n\nDrinkware did $1.09 billion in FY2025.\n"
    model["text"] = reading(fig("$1.09 billion", entity="YETI", metric="revenue",
                                period="FY2025", period_in_sentence=True))
    d = parse(doc)["$1.09 billion"]
    assert d.metric == "revenue" and d.metric_inferred
    contradicted = sn.SourceResult(source_name="SEC Filing", match_type="contradicted", confidence=0.85)
    assert sn._consensus_for(d, [contradicted])[0] == "unverifiable"
    confirmed = sn.SourceResult(source_name="SEC Filing", match_type="exact", confidence=0.95)
    assert sn._consensus_for(d, [confirmed])[0] == "verified"


def test_a_metric_the_sentence_names_can_refute(model):
    doc = "YETI fiscal 2025 numbers.\n\nNet sales were $1.87 billion in FY2025.\n"
    model["text"] = reading(fig("$1.87 billion", entity="YETI", metric="revenue",
                                period="FY2025", period_in_sentence=True))
    assert not parse(doc)["$1.87 billion"].metric_inferred


@pytest.mark.parametrize("sentence,metric", [
    ("CPI inflation averaged 6.1% in 2023.", "inflation"),
    ("The unemployment rate averaged 3.6% in 2023.", "unemployment"),
    ("Life expectancy in 2024 was 83.2 years.", "life_expectancy"),
    ("GDP per head was about $13,000 in 2025.", "gdp_per_capita"),
])
def test_a_metric_the_sentence_names_in_its_own_words_is_not_inferred(model, sentence, metric):
    raw = re.search(r'\$?[\d,.]+%?', sentence).group()
    model["text"] = reading(fig(raw, entity="", metric=metric, period_in_sentence=True))
    assert not parse(sentence)[raw].metric_inferred


def test_two_readings_keep_only_what_they_agree_on(monkeypatch):
    monkeypatch.setattr(cr, "enabled", lambda: True)
    monkeypatch.setattr(cr, "_cache", {})
    answers = iter([
        reading(fig("$2.18 billion", metric="revenue"), fig("$1.86 billion", period="2024")),
        reading(fig("$2.18 billion", metric="other", attribute="segment sales"),
                fig("$1.86 billion", period="2023")),
    ])
    monkeypatch.setattr(cr, "_call_model", lambda document: next(answers))
    figures = {f["figure"]: f for f in cr.read_figures(DOC)}
    assert figures["$2.18 billion"]["entity"] == "Federal Signal Corporation"
    assert figures["$2.18 billion"]["metric"] == ""
    assert figures["$1.86 billion"]["period"] == ""


def test_a_figure_only_one_reading_found_is_dropped(monkeypatch):
    monkeypatch.setattr(cr, "enabled", lambda: True)
    monkeypatch.setattr(cr, "_cache", {})
    answers = iter([reading(fig("$2.18 billion"), fig("$1.86 billion")), reading(fig("$2.18 billion"))])
    monkeypatch.setattr(cr, "_call_model", lambda document: next(answers))
    assert [f["figure"] for f in cr.read_figures(DOC)] == ["$2.18 billion"]


def test_one_failed_reading_falls_back_to_the_other(monkeypatch):
    monkeypatch.setattr(cr, "enabled", lambda: True)
    monkeypatch.setattr(cr, "_cache", {})
    calls = {"n": 0}

    def flaky(document):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("slow")
        return reading(fig("$2.18 billion"))

    monkeypatch.setattr(cr, "_call_model", flaky)
    assert [f["figure"] for f in cr.read_figures(DOC)] == ["$2.18 billion"]


def test_reader_failures_are_counted_for_health(monkeypatch):
    import source_network as sn_mod
    monkeypatch.setattr(cr, "enabled", lambda: True)
    monkeypatch.setattr(cr, "_cache", {})
    sn_mod.provider_health.reset()

    def boom(document):
        raise TimeoutError("slow")

    monkeypatch.setattr(cr, "_call_model", boom)
    assert cr.read_figures(DOC) == []
    assert sn_mod.provider_health.snapshot()["providers"]["claim_reader"]["total"] == 2
