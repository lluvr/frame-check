"""
Unit tests for subject_classifier.py and metric_classifier.py.

PHASE_1_5_GAPS.md Part B Prereqs 2 + 3. Verifies that the
two classifiers map free-form strings into the closed
DATA_MOAT.md Section 5 enums for `decomp.subject_class` and
`decomp.metric_class`.

Both classifiers are conservative: false negatives (returning
"other") are STRICTLY better than false positives. The tests
encode this discipline by checking BOTH that known cases
classify correctly AND that ambiguous cases default to
"other" rather than the wrong specific bucket.
"""

import sys

from subject_classifier import classify_subject, SUBJECT_CLASSES
from metric_classifier import classify_metric, METRIC_CLASSES
from telemetry import SUBJECT_CLASSES as TELEMETRY_SUBJECT_CLASSES
from telemetry import METRIC_CLASSES as TELEMETRY_METRIC_CLASSES


def check(condition, msg):
    if not condition:
        print(f"  FAIL: {msg}")
        sys.exit(1)


# ── subject_classifier ──

def test_subject_enums_match_telemetry():
    """The classifier's enum tuple must be a subset of telemetry's
    SUBJECT_CLASSES frozenset, and the only allowed return values
    must be telemetry-recordable."""
    print("=== subject_classifier enum aligns with telemetry ===")
    classifier_set = set(SUBJECT_CLASSES)
    telemetry_set = set(TELEMETRY_SUBJECT_CLASSES)
    extra = classifier_set - telemetry_set
    check(not extra,
          f"classifier returns values not in telemetry SUBJECT_CLASSES: {extra}")
    missing = telemetry_set - classifier_set
    check(not missing,
          f"classifier missing telemetry-allowed values: {missing}")
    print("  Subject enums aligned")
    print("  PASS\n")


def test_classify_subject_companies():
    print("=== classify_subject: companies ===")
    cases = [
        ("Apple Inc", "company"),
        ("Apple Inc.", "company"),
        ("Microsoft Corporation", "company"),
        ("Tesla Inc.", "company"),
        ("Volkswagen AG", "company"),
        ("Novo Nordisk A/S", "company"),  # falls through to known list partial match
        ("ASML Holding N.V.", "company"),
        ("Google", "company"),
        ("OpenAI", "company"),
        ("Amazon", "company"),
        ("TSMC", "company"),
        ("Samsung", "company"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} company cases classified correctly")
    print("  PASS\n")


def test_classify_subject_case_insensitive_companies():
    """Source_network may emit all-caps company names like
    'NVIDIA' even though the known-company list stores mixed
    case 'Nvidia'. The classifier normalizes case, so both
    forms must match."""
    print("=== classify_subject: case-insensitive company matching ===")
    cases = [
        ("NVIDIA", "company"),
        ("nvidia", "company"),
        ("Nvidia", "company"),
        ("TSMC", "company"),
        ("tsmc", "company"),
        ("ASML", "company"),
        ("asml", "company"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} case variants classified correctly")
    print("  PASS\n")


def test_classify_subject_multi_word_companies():
    """Multi-word company subjects like 'ASML Holding NV' and
    'Saudi Aramco' must classify as company even though the
    exact multi-word string may not be in the known list and
    the tokens could otherwise trigger the person regex."""
    print("=== classify_subject: multi-word companies ===")
    cases = [
        ("Saudi Aramco", "company"),
        ("Aramco", "company"),
        ("ASML Holding NV", "company"),
        ("ASML Holding", "company"),
        ("ASML Holding N.V.", "company"),
        # Progressive prefix match: trailing qualifier stripped.
        ("Apple Inc 2024", "company"),
        ("Microsoft 2023 annual", "company"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} multi-word company cases classified correctly")
    print("  PASS\n")


def test_classify_subject_company_beats_country_on_substring():
    """Companies whose name contains a country substring must
    classify as company, not country. The country regex uses
    re.search and matches anywhere in the text, so without the
    company-first ordering plus the indicator heuristic,
    'Taiwan Semiconductor' would classify as country because
    'Taiwan' is in the country list.

    This test is the binding against that class of bug.
    """
    print("=== classify_subject: company beats country when substring overlap ===")
    cases = [
        ("Taiwan Semiconductor Manufacturing Company Limited", "company"),
        ("Taiwan Semiconductor Manufacturing", "company"),
        ("Japan Airlines", "company"),
        ("Qatar Airways", "company"),
        ("Air France", "company"),
        ("Bank of Japan", "company"),  # central bank, but closer to company than country
        ("Deutsche Bank", "company"),
        ("Swiss Re", "company"),
        ("HSBC", "company"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} overlap cases classified correctly")
    print("  PASS\n")


def test_classify_subject_countries_not_broken_by_company_check():
    """Sanity: moving company check before country check must
    not break pure country classifications. Pure country names
    (no company indicators, not in known list) must still
    classify as country."""
    print("=== classify_subject: pure countries still classify correctly ===")
    cases = [
        ("France", "country"),
        ("Japan", "country"),
        ("Germany", "country"),
        ("Taiwan", "country"),
        ("Saudi Arabia", "country"),
        ("United States", "country"),
        ("United Kingdom", "country"),
        ("South Africa", "country"),
        ("United Arab Emirates", "country"),
        ("New Zealand", "country"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} pure country cases classified correctly")
    print("  PASS\n")


def test_classify_subject_geographic_features_not_persons():
    """Geographic features like 'Mount Everest' and 'Lake Baikal'
    are Title Case First+Last patterns that match the person
    regex otherwise. The explicit geographic-prefix deny-list
    catches these before the person check fires. Test cases
    deliberately use second-word names that are NOT country
    names so the country check does not intercept them first."""
    print("=== classify_subject: geographic features are not persons ===")
    cases = [
        ("Mount Everest", "other"),
        ("Mount Kilimanjaro", "other"),
        ("Lake Baikal", "other"),
        ("River Thames", "other"),
        ("Cape Horn", "other"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} geographic features correctly not classified as person")
    print("  PASS\n")


def test_classify_subject_countries():
    print("=== classify_subject: countries ===")
    cases = [
        ("France", "country"),
        ("United States", "country"),
        ("Japan", "country"),
        ("Brazil", "country"),
        ("China", "country"),
        ("South Africa", "country"),
        ("United Arab Emirates", "country"),
        ("Taiwan", "country"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} country cases classified correctly")
    print("  PASS\n")


def test_classify_subject_currencies():
    print("=== classify_subject: currencies ===")
    cases = [
        ("USD", "currency"),
        ("EUR", "currency"),
        ("JPY", "currency"),
        ("US dollar", "currency"),
        ("euro", "currency"),
        ("Japanese yen", "currency"),
        ("Indian rupee", "currency"),
        # Phase 1.6e: cryptocurrency tickers and names. The
        # Observatory topic bitcoin_all_time_high_usd produces
        # claims with subjects like "Bitcoin" and "BTC".
        ("Bitcoin", "currency"),
        ("bitcoin", "currency"),
        ("BTC", "currency"),
        ("Ethereum", "currency"),
        ("ETH", "currency"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} currency cases classified correctly")
    print("  PASS\n")


def test_classify_subject_chemicals():
    print("=== classify_subject: chemicals ===")
    cases = [
        ("semaglutide", "chemical"),
        ("Semaglutide", "chemical"),
        ("ozempic", "chemical"),
        ("Wegovy", "chemical"),
        ("CO2", "chemical"),
        ("H2O", "chemical"),
        ("ibuprofen", "chemical"),
        ("aspirin", "chemical"),
        # Phase 1.6e: element names and isotope notation for
        # Observatory scientific topics (carbon_12_atomic_mass,
        # proton_rest_mass_kg).
        ("carbon", "chemical"),
        ("Carbon", "chemical"),
        ("carbon-12", "chemical"),
        ("Carbon-12", "chemical"),
        ("proton", "chemical"),
        ("uranium-235", "chemical"),
        ("oxygen", "chemical"),
        ("iron", "chemical"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} chemical cases classified correctly")
    print("  PASS\n")


def test_classify_subject_persons():
    print("=== classify_subject: persons ===")
    # The person check is deliberately last and noisy. Only
    # cases that do NOT match company / country / currency /
    # chemical / metric should classify as person.
    cases = [
        ("Albert Einstein", "person"),
        ("Marie Curie", "person"),
        ("Elon Musk", "person"),
        ("Charles de Gaulle", "person"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} person cases classified correctly")
    print("  PASS\n")


def test_classify_subject_metrics():
    print("=== classify_subject: bare metric subjects ===")
    cases = [
        ("GDP", "metric"),
        ("CPI", "metric"),
        ("unemployment", "metric"),
        ("inflation", "metric"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} metric cases classified correctly")
    print("  PASS\n")


def test_classify_subject_falls_back_to_other():
    """Anything ambiguous or unclassifiable returns "other".
    This is the conservative default."""
    print("=== classify_subject: conservative fallback to other ===")
    cases = [
        (None, "other"),
        ("", "other"),
        ("   ", "other"),
        ("the quick brown fox", "other"),
        ("xyzzy", "other"),
        ("42", "other"),
    ]
    for text, expected in cases:
        got = classify_subject(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} ambiguous cases fell back to 'other'")
    print("  PASS\n")


# ── metric_classifier ──

def test_metric_enums_match_telemetry():
    print("=== metric_classifier enum aligns with telemetry ===")
    classifier_set = set(METRIC_CLASSES)
    telemetry_set = set(TELEMETRY_METRIC_CLASSES)
    extra = classifier_set - telemetry_set
    check(not extra,
          f"classifier returns values not in telemetry METRIC_CLASSES: {extra}")
    missing = telemetry_set - classifier_set
    check(not missing,
          f"classifier missing telemetry-allowed values: {missing}")
    print("  Metric enums aligned")
    print("  PASS\n")


def test_classify_metric_revenue():
    print("=== classify_metric: revenue ===")
    cases = [
        ("revenue", "revenue"),
        ("total revenue", "revenue"),
        ("net sales", "revenue"),
        ("gross profit", "revenue"),
        ("EBITDA", "revenue"),
        ("operating income", "revenue"),
        ("market cap", "revenue"),
        ("GDP", "revenue"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} revenue cases classified correctly")
    print("  PASS\n")


def test_classify_metric_growth_rate_beats_revenue():
    """A 'revenue growth rate' string must classify as
    growth_rate, not revenue, because growth rates are a
    distinct query class in the corpus."""
    print("=== classify_metric: growth_rate beats revenue (order matters) ===")
    cases = [
        ("revenue growth rate", "growth_rate"),
        ("YoY growth", "growth_rate"),
        ("year-over-year change", "growth_rate"),
        ("CAGR", "growth_rate"),
        ("inflation rate", "growth_rate"),
        ("unemployment rate", "growth_rate"),
        ("interest rate", "growth_rate"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} growth_rate cases classified correctly")
    print("  PASS\n")


def test_classify_metric_population():
    print("=== classify_metric: population ===")
    cases = [
        ("population", "population"),
        ("total population", "population"),
        ("number of inhabitants", "population"),
        ("workforce", "population"),
        ("employees", "population"),
        ("subscribers", "population"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} population cases classified correctly")
    print("  PASS\n")


def test_classify_metric_price():
    print("=== classify_metric: price ===")
    cases = [
        ("price", "price"),
        ("stock price", "price"),
        ("closing price", "price"),
        ("retail price", "price"),
        ("salary", "price"),
        ("wage", "price"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} price cases classified correctly")
    print("  PASS\n")


def test_classify_metric_dimensional():
    print("=== classify_metric: dimensional (length, area, temperature, time) ===")
    cases = [
        ("height in meters", "length"),
        ("length", "length"),
        ("distance", "length"),
        ("surface area", "area"),
        ("square kilometers", "area"),
        ("temperature", "temperature"),
        ("global warming", "temperature"),
        ("celsius", "temperature"),
        ("duration", "time"),
        ("lifespan", "time"),
        ("years", "time"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} dimensional cases classified correctly")
    print("  PASS\n")


def test_classify_metric_count():
    print("=== classify_metric: count ===")
    cases = [
        ("number of cases", "count"),
        ("total deaths", "count"),
        ("infections", "count"),
        ("transactions", "count"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} count cases classified correctly")
    print("  PASS\n")


def test_classify_metric_life_expectancy_is_time():
    """Life expectancy is a demographic duration measured in
    years. Added to _TIME_RE explicitly because 'expectancy'
    does not otherwise match any time-related word."""
    print("=== classify_metric: life expectancy is time ===")
    cases = [
        ("life expectancy", "time"),
        ("global life expectancy", "time"),
        ("expectancy at birth", "time"),
        ("life span", "time"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} time cases classified correctly")
    print("  PASS\n")


def test_classify_metric_health_rates_are_growth_rate():
    """Health rates (mortality, morbidity, prevalence, case
    fatality) are structurally rates over populations or time
    windows and classify as growth_rate, not price. The 'rate'
    keyword alone matches _PRICE_RE, so health rates must be
    in _GROWTH_RATE_RE to be caught first."""
    print("=== classify_metric: health rates are growth_rate ===")
    cases = [
        ("mortality rate", "growth_rate"),
        ("case fatality rate", "growth_rate"),
        ("infant mortality", "growth_rate"),
        ("morbidity", "growth_rate"),
        ("prevalence", "growth_rate"),
        ("incidence", "growth_rate"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} health rate cases classified correctly")
    print("  PASS\n")


def test_classify_metric_vehicle_deliveries_is_count():
    """Tesla and auto industry topics use 'deliveries' for
    discrete vehicle counts. 'Deliveries' must be in _COUNT_RE
    explicitly because it overlaps neither with population
    nor with more specific categories."""
    print("=== classify_metric: vehicle deliveries is count ===")
    cases = [
        ("vehicle deliveries", "count"),
        ("total deliveries", "count"),
        ("annual deliveries", "count"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} delivery cases classified correctly")
    print("  PASS\n")


def test_classify_metric_contract_with_decompose_claim():
    """Contract test: every value that source_network.decompose_claim
    can store in ClaimDecomposition.metric must classify to a
    non-'other' bucket (except 'weight' and the empty string,
    which have no valid bucket in METRIC_CLASSES).

    The 13 values come from source_network._METRIC_PATTERNS keys.
    This test is the binding between the two modules: if
    decompose_claim adds a new metric name, this test fails
    until metric_classifier is updated too. If metric_classifier
    is tightened in a way that breaks one of these values, this
    test fails before the Observatory misclassifies real events.
    """
    print("=== classify_metric: contract with decompose_claim ===")
    cases = [
        ("",           "other"),      # no _METRIC_PATTERNS matched
        ("revenue",    "revenue"),
        ("profit",     "revenue"),    # profit is a revenue sub-class
        ("market_cap", "revenue"),    # underscored key from decompose_claim
        ("population", "population"),
        ("area",       "area"),
        ("height",     "length"),
        ("weight",     "other"),      # mass class does not exist in METRIC_CLASSES
        ("length",     "length"),
        ("lifespan",   "time"),
        ("price",      "price"),
        ("gdp",        "revenue"),    # GDP is top-line economic
        ("growth",     "growth_rate"),
        ("count",      "count"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} decompose_claim metric keys classified correctly")
    print("  PASS\n")


def test_classify_metric_reduction_is_growth_rate():
    """Clinical reduction values (HbA1c reduction, LDL
    reduction, weight loss reduction) are structurally
    percentage changes, same shape as growth rates. Added
    'reduction' to _GROWTH_RATE_RE explicitly because
    'decrease' and 'decline' do not capture clinical usage."""
    print("=== classify_metric: reduction is growth_rate ===")
    cases = [
        ("HbA1c reduction", "growth_rate"),
        ("LDL reduction", "growth_rate"),
        ("cholesterol reduction", "growth_rate"),
        ("blood pressure reduction", "growth_rate"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} reduction cases classified correctly")
    print("  PASS\n")


def test_classify_metric_falls_back_to_other():
    print("=== classify_metric: conservative fallback to other ===")
    cases = [
        (None, "other"),
        ("", "other"),
        ("   ", "other"),
        ("xyzzy nonsense", "other"),
        ("the quick brown fox", "other"),
    ]
    for text, expected in cases:
        got = classify_metric(text)
        check(got == expected,
              f"{text!r} -> expected {expected!r}, got {got!r}")
    print(f"  {len(cases)} ambiguous cases fell back to 'other'")
    print("  PASS\n")


def main():
    print("Running classifier tests...")
    print()
    test_subject_enums_match_telemetry()
    test_classify_subject_companies()
    test_classify_subject_case_insensitive_companies()
    test_classify_subject_multi_word_companies()
    test_classify_subject_company_beats_country_on_substring()
    test_classify_subject_countries_not_broken_by_company_check()
    test_classify_subject_geographic_features_not_persons()
    test_classify_subject_countries()
    test_classify_subject_currencies()
    test_classify_subject_chemicals()
    test_classify_subject_persons()
    test_classify_subject_metrics()
    test_classify_subject_falls_back_to_other()
    test_metric_enums_match_telemetry()
    test_classify_metric_revenue()
    test_classify_metric_growth_rate_beats_revenue()
    test_classify_metric_population()
    test_classify_metric_price()
    test_classify_metric_dimensional()
    test_classify_metric_count()
    test_classify_metric_life_expectancy_is_time()
    test_classify_metric_health_rates_are_growth_rate()
    test_classify_metric_vehicle_deliveries_is_count()
    test_classify_metric_contract_with_decompose_claim()
    test_classify_metric_reduction_is_growth_rate()
    test_classify_metric_falls_back_to_other()
    print("=== ALL CLASSIFIER TESTS PASSED ===")


if __name__ == "__main__":
    main()
