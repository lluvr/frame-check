"""Check a figure's full identity against the company's own SEC filings.

The claim reader says who and what a figure is about; it never said for which period,
on what basis or at what scope, and every false contradiction on a real results
release came from one of those (a segment, an adjusted figure, a quarter read as a
year, a component read as the line item). Here a model describes each figure's whole
identity (reader v3: measure, kind, period type, fiscal year, where the period came
from, basis, scope, line item, operations, comparison, scale, currency), and code
does the rest: resolves the company to a CIK (ticker list, then Wikidata P5531),
reads its fiscal calendar from its own annual filings, finds the filed fact for that
measure and period, and compares within the figure's own rounding.

A figure is refuted only when every identity field is set from its own words and the
path's row in ROLLOUT allows it; otherwise it may confirm, never refute. Measured
offline before wiring (scripts/phase3, the maintainers' evaluation record): 0 contradictions on
4,113 figures in 74 official results releases, 0 on 750 labeled true figures.

Off unless IDENTITY_PATH=on, because it sends the text to the model provider.
"""
import datetime as dt
import json
import logging
import re
import threading
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

# Which comparison may do what. Every new path starts confirm-only and earns the
# right to refute on evidence reported per path (the maintainers' evaluation record, Phase 1).
ROLLOUT = {
    "sec_level": {"confirm": True, "refute": True},        # headline line items
    "sec_level_other": {"confirm": True, "refute": False},  # other line items
    "sec_change": {"confirm": True, "refute": False},       # computed growth rates
    "sec_margin": {"confirm": True, "refute": False},       # computed margins
}

GAAP, IFRS = "us-gaap", "ifrs-full"
CONCEPTS = {
    "revenue": [(GAAP, "Revenues"), (GAAP, "RevenueFromContractWithCustomerExcludingAssessedTax"),
                (GAAP, "RevenueFromContractWithCustomerIncludingAssessedTax"), (GAAP, "SalesRevenueNet"),
                (GAAP, "RevenuesNetOfInterestExpense"), (IFRS, "Revenue"),
                (IFRS, "RevenueFromContractsWithCustomers")],
    "cost_of_revenue": [(GAAP, "CostOfRevenue"), (GAAP, "CostOfGoodsAndServicesSold"),
                        (GAAP, "CostOfGoodsSold"), (IFRS, "CostOfSales")],
    "gross_profit": [(GAAP, "GrossProfit"), (IFRS, "GrossProfit")],
    "operating_income": [(GAAP, "OperatingIncomeLoss"), (IFRS, "ProfitLossFromOperatingActivities")],
    "net_income": [(GAAP, "NetIncomeLoss"), (GAAP, "ProfitLoss"),
                   (GAAP, "NetIncomeLossAvailableToCommonStockholdersBasic"),
                   (IFRS, "ProfitLoss"), (IFRS, "ProfitLossAttributableToOwnersOfParent")],
    "pretax_income": [(GAAP, "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"),
                      (GAAP, "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
                      (IFRS, "ProfitLossBeforeTax")],
    "income_tax": [(GAAP, "IncomeTaxExpenseBenefit"), (IFRS, "IncomeTaxExpenseContinuingOperations")],
    "eps_diluted": [(GAAP, "EarningsPerShareDiluted"), (IFRS, "DilutedEarningsLossPerShare")],
    "eps_basic": [(GAAP, "EarningsPerShareBasic"), (IFRS, "BasicEarningsLossPerShare")],
    "operating_cash_flow": [(GAAP, "NetCashProvidedByUsedInOperatingActivities"),
                            (GAAP, "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
                            (IFRS, "CashFlowsFromUsedInOperatingActivities")],
    "capex": [(GAAP, "PaymentsToAcquirePropertyPlantAndEquipment"),
              (GAAP, "PaymentsToAcquireProductiveAssets"),
              (IFRS, "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities")],
    "cash": [(GAAP, "CashAndCashEquivalentsAtCarryingValue"),
             (GAAP, "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
             (IFRS, "CashAndCashEquivalents")],
    "total_assets": [(GAAP, "Assets"), (IFRS, "Assets")],
    "total_liabilities": [(GAAP, "Liabilities"), (IFRS, "Liabilities")],
    "equity": [(GAAP, "StockholdersEquity"),
               (GAAP, "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
               (IFRS, "EquityAttributableToOwnersOfParent"), (IFRS, "Equity")],
    "long_term_debt": [(GAAP, "LongTermDebtNoncurrent"), (GAAP, "LongTermDebt")],
    "dividends_per_share": [(GAAP, "CommonStockDividendsPerShareDeclared"),
                            (GAAP, "CommonStockDividendsPerShareCashPaid")],
    "rd_expense": [(GAAP, "ResearchAndDevelopmentExpense"), (IFRS, "ResearchAndDevelopmentExpense")],
    "sga_expense": [(GAAP, "SellingGeneralAndAdministrativeExpense")],
    "operating_expenses": [(GAAP, "OperatingExpenses"), (GAAP, "CostsAndExpenses")],
    "interest_expense": [(GAAP, "InterestExpense"), (GAAP, "InterestExpenseNonoperating")],
    "depreciation": [(GAAP, "DepreciationDepletionAndAmortization"), (GAAP, "DepreciationAndAmortization")],
    "share_repurchases": [(GAAP, "PaymentsForRepurchaseOfCommonStock")],
    "dividends_paid": [(GAAP, "PaymentsOfDividends"), (GAAP, "PaymentsOfDividendsCommonStock")],
    "inventory": [(GAAP, "InventoryNet")],
}
# Rollout: only headline line items may refute. A component filed under one of these
# ("$84 million LIFO favorability" read as gross profit) is not that line item.
REFUTABLE = {"revenue", "net_income", "operating_income", "gross_profit", "eps_diluted",
             "eps_basic", "total_assets", "operating_cash_flow"}
INSTANT = {"cash", "total_assets", "total_liabilities", "equity", "long_term_debt", "inventory"}
DURATION = {"FY": (350, 380), "TTM": (350, 380), "Q1": (80, 100), "Q2": (80, 100), "Q3": (80, 100),
            "Q4": (80, 100), "H1": (170, 195), "9M": (260, 285)}
SCALE = {"one": 1, "thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}
SCALE_WORDS = [(r"tri(?:llion)?\b|\bT\b|tn\b", 1e12), (r"bil(?:lion)?\b|bn\b|\bB\b", 1e9),
               (r"mil(?:lion)?\b|mn\b|\bM\b|\bm\b", 1e6), (r"thousand\b|\bk\b|\bK\b", 1e3)]
SYMBOLS = [("NT$", "TWD"), ("US$", "USD"), ("C$", "CAD"), ("A$", "AUD"), ("$", "USD"), ("€", "EUR"),
           ("£", "GBP"), ("¥", "JPY"), ("DKK", "DKK"), ("EUR", "EUR"), ("USD", "USD"), ("SEK", "SEK"),
           ("CHF", "CHF"), ("GBP", "GBP"), ("TWD", "TWD")]
# The reader's own words for what a figure measures. A component or effect of a line
# item ("settlement expense per diluted share", "favorable currency impact") is not the
# line item. Interim: the identity schema should carry this as a field.
COMPONENT = re.compile(r"\b(charges?|expenses?|benefits?|impacts?|effects?|contribut\w*|includ\w*|"
                       r"impairments?|settlements?|refunds?|favorab\w*|unfavorab\w*|variance|"
                       r"tax effect|one-time|special|restructuring)\b", re.I)
LEVEL_CHANGE = re.compile(r"\b(increase|decrease|change|growth|up|down|improvement|decline)\b", re.I)
# A change of something other than the measure year on year: comparable-store sales,
# a margin's change in points, quarter over quarter, a multi-year stack.
OTHER_CHANGE = re.compile(r"comparable|same[- ]store|\bcomps?\b|margin|basis points|\bbps\b|"
                          r"quarter[- ]over[- ]quarter|sequential|q/q|stack|two-year|organic|"
                          r"constant currency|absolute", re.I)
# A measure the document qualifies is another measure: same-store revenue is not revenue.
QUALIFIED = re.compile(r"same[- ]store|comparable|\borganic\b|\bfee\b|like[- ]for[- ]like|"
                       r"run[- ]rate|backlog|bookings|\borders\b|recurring|annualized", re.I)
CONTINUING = re.compile(r"continuing operations", re.I)
RANGE_BEFORE = re.compile(r"\d\s*%?\s*(?:to|-|\u2013)\s*$")
DISCONTINUED = [(GAAP, "IncomeLossFromDiscontinuedOperationsNetOfTax"),
                (GAAP, "IncomeLossFromDiscontinuedOperationsNetOfTaxAttributableToReportingEntity"),
                (GAAP, "DiscontinuedOperationIncomeLossFromDiscontinuedOperationNetOfTax"),
                (GAAP, "IncomeLossFromDiscontinuedOperationsNetOfTaxPerDilutedShare")]
HEDGE = re.compile(r"~|≈|\babout\b|\bapprox|\baround\b|\bnearly\b|\balmost\b|\bover\b|\bmore than\b|"
                   r"\bless than\b|\bunder\b|\broughly\b|\bsome\b|\bup to\b", re.I)


# ---------------------------------------------------------------- fetching

_MEMO = {}
_MEMO_LOCK = threading.Lock()
_MEMO_LIMIT = 512
_MEMO_SECONDS = 6 * 3600  # filings arrive daily; a lookup older than this is fetched again


def _get(url, name):
    """JSON from a public source, memoized per process; a failure reads as empty."""
    import time
    with _MEMO_LOCK:
        hit = _MEMO.get(name)
        if hit and time.monotonic() - hit[0] < _MEMO_SECONDS:
            return hit[1]
    from source_network import _SEC_HEADERS, _urlopen_with_deadline
    try:
        req = urllib.request.Request(url, headers=_SEC_HEADERS)
        data = json.loads(_urlopen_with_deadline(req, per_op_timeout=8))
    except Exception:
        data = {"_error": True}
    with _MEMO_LOCK:
        if len(_MEMO) >= _MEMO_LIMIT:
            _MEMO.clear()
        _MEMO[name] = (time.monotonic(), data)
    return data


def resolve_cik(entity):
    """The ticker list first, then Wikidata's SEC CIK property (P5531)."""
    from source_network import _find_cik
    for name in (entity, re.sub(r"^the\s+", "", entity, flags=re.I)):
        cik, _ = _find_cik(name)
        if cik:
            return cik.zfill(10), "tickers"
    q = urllib.parse.quote(entity)
    found = _get("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en"
                 f"&type=item&limit=3&search={q}", f"wd_search_{re.sub(r'[^A-Za-z0-9]', '_', entity)}.json")
    for hit in found.get("search", []):
        ent = _get(f"https://www.wikidata.org/wiki/Special:EntityData/{hit['id']}.json", f"wd_{hit['id']}.json")
        claims = ent.get("entities", {}).get(hit["id"], {}).get("claims", {})
        for c in claims.get("P5531", []):
            v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
            if v:
                return str(v).zfill(10), "wikidata"
    return None, None


class _Concepts:
    """One taxonomy of one company, fetched a concept at a time (10-50 KB each)
    instead of the whole catalogue (3.7 MB on average)."""

    def __init__(self, cik, taxonomy):
        self.cik, self.taxonomy = cik, taxonomy

    def get(self, concept, default=None):
        url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{self.cik}/{self.taxonomy}/{concept}.json"
        import source_network as sn
        if sn._sec_cache_users:
            # Inside a check: share the request's SEC cache with verify_sec_edgar, under
            # its own keys ("Revenues", "ifrs-full/Revenue"), so neither fetches twice.
            key = concept if self.taxonomy == "us-gaap" else f"{self.taxonomy}/{concept}"
            try:
                data = sn._sec_concept_data(self.cik, key, urllib.request.Request(url, headers=sn._SEC_HEADERS))
            except Exception:
                data = {}
        else:
            data = _get(url, f"cc_{self.cik}_{self.taxonomy}_{concept}")
        return default if not data or "_error" in data or "units" not in data else data


class _Facts(dict):
    """Looks like companyfacts to the code below: cf.get("facts").get(tax).get(concept)."""

    def __init__(self, cik):
        super().__init__(facts={tax: _Concepts(cik, tax) for tax in ("us-gaap", "ifrs-full")})
        self.cik = cik


def company_facts(cik):
    return _Facts(cik)


# ---------------------------------------------------------------- the figure

def parse_value(figure, reader_scale):
    m = re.search(r"\(?-?\d[\d,]*(?:\.\d+)?", figure)
    if not m:
        return None
    raw = m.group()
    negative = raw.startswith("(") or raw.startswith("-")
    digits = raw.strip("(").lstrip("-").replace(",", "")
    decimals = len(digits.split(".")[1]) if "." in digits else 0
    tail = figure[m.end():m.end() + 12]
    scale, scale_from_text = SCALE.get(reader_scale or "one", 1), False
    for pat, mult in SCALE_WORDS:
        if re.match(r"\s*(?:" + pat + ")", tail):
            scale, scale_from_text = mult, True
            break
    value = float(digits) * scale * (-1 if negative else 1)
    # Half a unit of the last digit written, in base units: the claim's own rounding.
    room = 0.5 * (10 ** -decimals) * scale
    return {"value": value, "room": room, "scale_from_text": scale_from_text}


def currency_of(figure, reader_currency):
    for sym, code in SYMBOLS:
        if sym in figure:
            return code
    return (reader_currency or "").upper()


# ---------------------------------------------------------------- facts

def _days(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def facts_for(cf, taxonomy, concept, unit_pred):
    node = cf.get("facts", {}).get(taxonomy, {}).get(concept)
    if not node:
        return []
    out = []
    for unit, rows in node.get("units", {}).items():
        if unit_pred(unit):
            for r in rows:
                out.append({**r, "unit": unit})
    return out


_ENDS = {}


def filer_taxonomy(cf):
    """"us-gaap" or "ifrs-full" when the company plainly files under one, else ""."""
    facts = cf.get("facts", {})
    for tax, concept in ((GAAP, "Assets"), (IFRS, "Assets")):
        if facts.get(tax, {}).get(concept):
            return tax
    return ""


def fiscal_ends(cf):
    key = getattr(cf, "cik", None) or id(cf)
    if key not in _ENDS:
        _ENDS[key] = _fiscal_ends(cf)
    return _ENDS[key]


def _fiscal_ends(cf):
    """The company's own fiscal-year labels -> the end date of that year, from its annual filings.

    A filing's own year tag is not trusted alone: Wolverine tagged its fiscal 2025 10-K
    as fiscal 2024, which put a 2026 year end under the 2024 label. Each annual filing's
    primary year end (its latest) gives the offset between its label and the calendar
    year of that end, pulled back ten days so a 52/53-week year ending January 3 counts
    in the year before. The offset most filings agree on labels every year end.
    """
    primary = {}
    # Net income and assets are filed by nearly every company; revenue concepts vary.
    for tax, concept in [(GAAP, "NetIncomeLoss"), (GAAP, "ProfitLoss"), (GAAP, "Assets"),
                         (IFRS, "ProfitLoss"), (IFRS, "Assets")]:
        for r in facts_for(cf, tax, concept, lambda u: True):
            if r.get("form") in ("10-K", "20-F", "40-F", "10-K/A", "20-F/A") and r.get("fp") == "FY" and r.get("fy"):
                if r.get("start") and not 350 <= _days(r["start"], r["end"]) <= 380:
                    continue
                accn = r.get("accn")
                if r["end"] > primary.get(accn, ("", 0))[0]:
                    primary[accn] = (r["end"], int(r["fy"]))

    def cal_year(end):
        return (dt.date.fromisoformat(end) - dt.timedelta(days=10)).year

    offsets = [fy - cal_year(end) for end, fy in primary.values()]
    if not offsets:
        return {}
    offset = max(set(offsets), key=offsets.count)
    ends = {}
    for end, _ in primary.values():
        label = str(cal_year(end) + offset)
        if end > ends.get(label, ""):
            ends[label] = end
    return ends


def target_window(fig, cf, instant):
    """(end_date, min_days, max_days) for the figure's period, or None, plus how it was found."""
    ptype = fig.get("period_type") or "unknown"
    if instant:
        ptype_ok = True
    else:
        ptype_ok = ptype in DURATION
    if not ptype_ok:
        return None, "period type unknown"
    lo, hi = (0, 0) if instant else DURATION[ptype]
    if fig.get("period_end") and re.match(r"\d{4}-\d{2}-\d{2}$", fig["period_end"]):
        return (fig["period_end"], lo, hi, 7), "stated end"
    fy = re.sub(r"\D", "", fig.get("fiscal_year") or "")
    if len(fy) == 2:
        fy = "20" + fy
    if not fy:
        return None, "no year"
    ends = fiscal_ends(cf)
    if fy not in ends:
        return None, "fiscal year not filed"
    fy_end = ends[fy]
    if ptype in ("FY", "TTM") or (instant and ptype in ("FY", "instant", "unknown", "Q4")):
        return (fy_end, lo, hi, 7), "fiscal calendar"
    # A quarter or part year: count back from the fiscal year's end.
    months_back = {"Q1": 9, "Q2": 6, "Q3": 3, "Q4": 0, "H1": 6, "9M": 3}.get(ptype)
    if months_back is None:
        return None, "period type unknown"
    end = dt.date.fromisoformat(fy_end)
    approx = end - dt.timedelta(days=round(months_back * 30.44))
    return (approx.isoformat(), lo, hi, 20), "fiscal calendar (approx end)"


def matching_facts(rows, window, instant):
    end, lo, hi, tol = window
    out = []
    for r in rows:
        if abs(_days(end, r["end"])) > tol:
            continue
        if instant:
            if r.get("start"):
                continue
        else:
            if not r.get("start") or not lo <= _days(r["start"], r["end"]) <= hi:
                continue
        out.append(r)
    return out


def derived_q4(rows, window):
    """FY minus 9M with the same fiscal-year end: no 10-K files Q4 alone."""
    end, _, _, tol = window
    fy = [r for r in rows if r.get("start") and abs(_days(end, r["end"])) <= tol
          and 350 <= _days(r["start"], r["end"]) <= 380]
    nine = [r for r in rows if r.get("start") and 260 <= _days(r["start"], r["end"]) <= 285]
    out = []
    for f in fy:
        for n in nine:
            if n["start"] == f["start"]:
                out.append({**f, "val": f["val"] - n["val"], "derived": True})
    return out


def prior_window(window):
    end, lo, hi, tol = window
    d = dt.date.fromisoformat(end)
    try:
        prior = d.replace(year=d.year - 1)
    except ValueError:
        prior = d - dt.timedelta(days=365)
    return (prior.isoformat(), lo, hi, tol)


# ---------------------------------------------------------------- verdicts

# Basis unknown blocked 58% of planted errors on 29 releases: documents rarely write
# "GAAP" beside a figure. Two cases where unknown can stand for reported: a measure
# companies almost never adjust (its adjusted forms, organic or constant currency,
# are coded as their own basis), and a document that never speaks of adjusted
# figures at all.
BASIS_STABLE = {"revenue", "total_assets", "cash", "operating_cash_flow"}
NON_GAAP_WORDS = re.compile(r"non-?GAAP|adjusted|\bexcluding\b|\bcore\b|underlying|"
                            r"\bpro forma\b|\bongoing\b|\bcomparable\b|\borganic\b", re.I)


# A refutation needs the reader's own words for the measure to name that line item and
# nothing else. Grok called Oracle's "cloud services and license support" ($44.0
# billion) revenue, whole company, whole line item; the words say otherwise, and the
# model's scope and line-item fields cannot be taken on trust alone.
MEASURE_WORDS = {
    "revenue": r"revenues?|sales|turnover",
    "net_income": r"net\s+(?:income|earnings|profit|loss)|profit|earnings|net\s+result",
    "operating_income": r"operating\s+(?:income|profit|loss|earnings)|income\s+from\s+operations|ebit",
    "gross_profit": r"gross\s+(?:profit|margin)",
    "eps_diluted": r"(?:diluted\s+)?(?:eps|earnings\s+per\s+(?:diluted\s+)?share|per\s+share)",
    "eps_basic": r"(?:basic\s+)?(?:eps|earnings\s+per\s+share|per\s+share)",
    "total_assets": r"(?:total\s+)?assets",
    "operating_cash_flow": r"(?:net\s+)?cash\s+(?:provided\s+by|from|generated\s+by)?\s*operat\w*(?:\s+activities)?|operating\s+cash\s+flows?",
}
_FILLER = re.compile(
    r"\b(?:total|net|gaap|reported|consolidated|group|company|annual|full[- ]year|fiscal|year|"
    r"quarter(?:ly)?|q[1-4]|fy\d*|h1|first|second|third|fourth|half|nine|months?|twelve|"
    r"diluted|basic|attributable|to|of|the|for|in|its|and|a|per|share|record|"
    r"\d{2,4}|prior|previous|last|this|current)\b", re.I)


def _names_only(words, pattern, entity, filler):
    """The words name the line item (pattern) and say nothing more."""
    rest = re.sub(pattern, " ", words, count=1, flags=re.I)
    if rest == words:
        return False  # the line item is not named at all
    rest = filler.sub(" ", rest)
    # The company's own name ("attributable to Coherent Corp.") says nothing more.
    for token in re.findall(r"[A-Za-z]{2,}", entity or ""):
        rest = re.sub(r"\b" + re.escape(token) + r"\b", " ", rest, flags=re.I)
    rest = re.sub(r"\b(?:inc|corp|corporation|co|ltd|plc|nv|sa|ag|holdings?|group)\b", " ", rest, flags=re.I)
    return not re.sub(r"[^A-Za-z]+", "", rest)


def measure_named(fig, measure):
    """The reader's own words name this line item and say nothing more."""
    pattern = MEASURE_WORDS.get(measure)
    words = (fig.get("measure") or "").strip()
    if not pattern or not words:
        return False
    return _names_only(words, pattern, fig.get("entity"), _FILLER)


# The document's side of the same test. The reader's words are a paraphrase: a reader
# that writes "revenue" for a segment's row passes measure_named, and on 74 official
# releases that alone produced 97 false contradictions (scripts/phase3/stress_labels.py).
# What the document itself says beside the figure decides instead. These rules can only
# withhold a refutation, never make one.
DOC_MEASURE_WORDS = {
    **MEASURE_WORDS,
    "revenue": MEASURE_WORDS["revenue"] + r"|rev\b",
    "net_income": MEASURE_WORDS["net_income"] + r"|\bni\b|net\s+inc\b",
    "operating_income": MEASURE_WORDS["operating_income"] + r"|op\.?\s*(?:inc(?:ome)?|profit)\b",
    "operating_cash_flow": (MEASURE_WORDS["operating_cash_flow"]
                            + r"|cash\s+flows?\s+(?:from|provided\s+by)\s+operat\w*(?:\s+activities)?"),
    # Measures only the SEC rules compare (source_network.verify_sec_edgar), so that
    # their refutations pass the same document-words test.
    "research_development": r"r\s*&\s*d|research\s+and\s+development",
    "operating_expenses": r"operating\s+expenses|opex",
    "cost_of_revenue": r"cost\s+of\s+(?:revenues?|sales|goods\s+sold)|cogs",
    "cash": r"cash(?:\s+and\s+(?:cash\s+)?equivalents)?",
    "stockholders_equity": r"(?:stock|share)holders['\u2019]?\s+equity|equity",
    "long_term_debt": r"long[- ]term\s+debt",
    "dividends_paid": r"dividends?(?:\s+paid)?",
    "inventory": r"inventor(?:y|ies)",
    "capex": r"capital\s+expenditures?|capex",
}
_PER_SHARE = r"(?:a|per)\s+(?:diluted\s+|basic\s+)?share|dil\.?\s+eps"
_EPS_ALSO = r"net\s+(?:income|earnings|profit|loss)|earnings|profit|loss"
_DOC_FILLER = re.compile(
    _FILLER.pattern[:-3] + r"|was|were|is|are|been|be|of|at|on|by|with|from|as|an|or|it|then|"
    r"reached|totaled|totalled|amounted|stood|came|landed|hit|finished|closed|rose|grew|"
    r"increased|decreased|fell|falling|rising|declined|dropped|climbed|jumped|reported|"
    r"posted|generated|delivered|recorded|had|achieved|saw|said|announced|earned|booked|"
    r"reporting|posting|generating|delivering|recording|earning|booking|"
    r"that|up|down|approximately|about|roughly|nearly|almost|over|around|some|increase|"
    r"decrease|growth|compared|record|basis|its|their|our|we|us|usd|dollars?|eur|euros?|"
    r"gbp|million|billion|thousand|trillion|bn|mn|mm|m|b|k|totals?|consolidated|overall|"
    r"whole|entire|company[- ]wide|months?|ended|ending|period|three|six|full|dil|bottom|"
    r"line|top|company|firm|airline|carrier|retailer|bank|lender|insurer|chipmaker|"
    r"automaker|manufacturer|giant|versus|vs|against|py|ly|amount|value|figure|metric|only|just|"
    r"strong|solid|robust|healthy|weak|modest|steady|flat|impressive|still|"
    r"spending|spent|spend|spends|expenses?|ran|put|loss|losses|totaling|totalling|also|"
    r"during|within|through|throughout)\b", re.I)
_SEGMENT_WORDS = re.compile(
    r"\b(?:segments?|reportable|divisions?|business\s+(?:units?|lines?|groups?)|"
    r"operating\s+groups?|regions?|regional|geographic\w*)\b", re.I)
_WHOLE = re.compile(r"\b(?:total|consolidated|company[- ]wide|overall)\b", re.I)
_WHOLE_TABLE = re.compile(r"\b(?:consolidated|company[- ]wide)\b", re.I)
_NUMBER = re.compile(r"\d[\d,.]*\s*(?:%|percent|million|billion|bn|mn|[mMbBkK]\b)?")
_CUT_WORDS = re.compile(r"\b(?:compared|versus|vs\.?|while|whereas)\b", re.I)
_JOIN_ONLY = re.compile(
    r"(?:[\s,;:()*]|\b(?:and|or|vs\.?|versus|compared|with|to|against|from|in|the|prior|"
    r"previous|last|year|py|ly|(?:19|20)\d\d)\b)*", re.I)
_TAIL = re.compile(r"[\s*_]*(?:in\s+|of\s+)?((?:[A-Za-z][A-Za-z'&-]*\s*){1,5})")
_NUMERIC_CELL = re.compile(r"[\s$€£¥()%+\-\u2013.,\d*]*(?:million|billion|bn|m|b|pts|bps)?[\s*]*", re.I)
_SENTENCE_MARKS = (". ", ".** ", ".* ", ".__ ", "\n", "•", "▪", "◦", "? ", "! ", "; ")
_CLAUSE_MARKS = (", ",)


def _is_year(text):
    return bool(re.fullmatch(r"(?:19|20)\d\d", text.strip()))


def _table_label(doc_text, line_start, line, at_in_line):
    """A markdown table row: the cells before the figure's cell, and that column's header."""
    cells, pos = [], 0
    for raw in line.split("|"):
        cells.append((pos, raw))
        pos += len(raw) + 1
    idx = max(i for i, (p, _) in enumerate(cells) if p <= at_in_line)
    # A third figure after two in its row, followed by a percentage, is the change
    # column ("| Net sales | $5,587 | $3,647 | $1,940 | 53.2% |"), not a level.
    money_before = sum(bool(c.strip()) and bool(re.search(r"\d", c)) and "%" not in c
                       and bool(_NUMERIC_CELL.fullmatch(c.strip())) for _, c in cells[:idx])
    if money_before >= 2 and any("%" in c for _, c in cells[idx + 1:]):
        return "change"
    label = " ".join(c.strip() for _, c in cells[:idx]
                     if c.strip() and not _NUMERIC_CELL.fullmatch(c.strip()))
    start = _table_start(doc_text, line_start)
    end = doc_text.find("\n", start)
    header = doc_text[start:end if end >= 0 else len(doc_text)]
    if header.strip() != line.strip():
        hcells = header.split("|")
        if idx < len(hcells) and not re.fullmatch(r"[\s:\-]*", hcells[idx]):
            label += " " + hcells[idx].strip()
    return label


def _table_start(doc_text, line_start):
    start = line_start
    while start > 0:
        prev_start = doc_text.rfind("\n", 0, start - 1) + 1
        if doc_text[prev_start:start - 1].count("|") < 2:
            break
        start = prev_start
    return start


def own_words(doc_text, at, figure, depth=0):
    """What the document itself says a figure is, at one place it appears: its table
    row label and column header, or its clause back to the previous figure. A figure
    joined to the one before it ("$465 million in 2024 and $641 million in 2025",
    "$10.45, versus $11.63") shares that figure's words."""
    line_start = doc_text.rfind("\n", 0, at) + 1
    line_end = doc_text.find("\n", at)
    line = doc_text[line_start:line_end if line_end >= 0 else len(doc_text)]
    if line.count("|") >= 2:
        return _table_label(doc_text, line_start, line, at - line_start)
    found = [doc_text.rfind(c, line_start, at) for c in _SENTENCE_MARKS]
    sentence_start = max([i + 1 for i in found if i >= 0] + [line_start])
    sentence = doc_text[sentence_start:at]
    numbers = [m for m in _NUMBER.finditer(sentence) if not _is_year(m.group())]
    cut = max([m.end() for m in numbers] + [m.end() for m in _CUT_WORDS.finditer(sentence)]
              + [sentence.rfind(c) + len(c) for c in _CLAUSE_MARKS if c in sentence] + [0])
    clause = sentence[cut:]
    if depth < 2 and _JOIN_ONLY.fullmatch(clause):
        # The previous figure of the same kind: "$1.82 from $1.67", "44.7% from 33.0%".
        pct = "%" in figure or "percent" in doc_text[at + len(figure):at + len(figure) + 9]
        same = [m for m in numbers if ("%" in m.group() or "percent" in m.group()) == pct]
        if same:
            prev = same[-1]
            # Everything between the two figures belongs to the pair: in "a $5.7 billion
            # income tax benefit, or $5.32 per share" the second is the benefit per share.
            return (own_words(doc_text, sentence_start + prev.start(), prev.group(), depth + 1)
                    + " " + sentence[prev.end():])
    return clause


def _trailing(doc_text, at, figure):
    """Words right after a figure ("$0.45 per diluted share", "$391 billion in revenue")."""
    tail = _TAIL.match(doc_text[at + len(figure):at + len(figure) + 60])
    return tail.group(1) if tail else ""


def _near_segment(doc_text, at):
    """Segment words in the figure's own paragraph or table, or the heading above it."""
    line_start = doc_text.rfind("\n", 0, at) + 1
    block = doc_text.rfind("\n\n", 0, _table_start(doc_text, line_start))
    block = 0 if block < 0 else block
    heading = doc_text.rfind("\n", 0, max(0, block - 1))
    heading = 0 if heading < 0 else heading
    end = doc_text.find("\n", at)
    return bool(_SEGMENT_WORDS.search(doc_text[heading:end if end >= 0 else len(doc_text)]))


def document_names(fig, measure, doc_text):
    """Every place the figure appears, the document's own words name this line item
    and nothing more; near segment text, they also say it is the whole company."""
    pattern = DOC_MEASURE_WORDS.get(measure)
    figure = fig.get("figure") or ""
    if not pattern or not figure:
        return False
    # Whole words only: "sales" is not the "Sales" in "Salesforce".
    pattern = rf"(?<![A-Za-z])(?:{pattern})(?![A-Za-z])"
    if measure.startswith("eps"):
        pattern = f"(?:{pattern}|{_PER_SHARE})"
        pattern = f"{pattern}(?:.*?(?:{_EPS_ALSO}))?|(?:{_EPS_ALSO}).*?{pattern}"
    entity = fig.get("entity") or ""
    names = [t for t in re.findall(r"[A-Za-z]{3,}", entity)
             if t.lower() not in ("inc", "corp", "corporation", "the", "company", "holdings", "group")]
    places = [m.start() for m in re.finditer(re.escape(figure), doc_text)]
    if not places and re.search(r"\d[BMKbmk]$", figure):
        # The decomposition can add the scale the text left to its caption: "$15.01B"
        # for the "$15.01" written.
        figure = figure[:-1]
        places = [m.start() for m in re.finditer(re.escape(figure), doc_text)]
    if not places:
        return False
    for at in places:
        words = re.sub(r"['’]s\b", "", own_words(doc_text, at, figure))
        # The words after the figure count only where its clause names no line item.
        if not re.search(pattern, words, re.I):
            words += " " + _trailing(doc_text, at, figure)
        if not _names_only(words, pattern, entity, _DOC_FILLER):
            return False
        # Near segment text a table's "Total" row is usually that segment's total; there
        # only "consolidated" or the company's name says the whole company.
        line_start = doc_text.rfind("\n", 0, at) + 1
        in_table = doc_text[line_start:doc_text.find("\n", at) if "\n" in doc_text[at:] else None].count("|") >= 2
        whole = _WHOLE_TABLE if in_table else _WHOLE
        if _near_segment(doc_text, at) and not whole.search(words) and not any(
                re.search(r"\b" + re.escape(t) + r"\b", words, re.I) for t in names):
            return False
    return True


def identity_gaps(fig, cur_ok, cik_how, measure=None, doc_text=""):
    """What stops this figure from being refuted. Empty means it may contradict."""
    gaps = []
    if measure is not None and measure not in REFUTABLE:
        gaps.append(f"path {measure} confirm-only")
    elif measure is not None and fig.get("kind") in ("level", "per_share") and not measure_named(fig, measure):
        gaps.append("measure words")
    elif (measure is not None and fig.get("kind") in ("level", "per_share") and doc_text
          and not document_names(fig, measure, doc_text)):
        gaps.append("document words")
    basis = fig.get("basis") or "unknown"
    if basis == "unknown" and (measure in BASIS_STABLE
                               or (doc_text and not NON_GAAP_WORDS.search(doc_text))):
        basis = "reported"
    if basis != "reported":
        gaps.append(f"basis {fig.get('basis')}")
    if (fig.get("scope") or "unknown") != "total":
        gaps.append(f"scope {fig.get('scope')}")
    if fig.get("period_from") not in ("sentence", "table_header"):
        gaps.append(f"period from {fig.get('period_from')}")
    if not cur_ok:
        gaps.append("currency")
    if cik_how != "tickers" and cik_how != "wikidata":
        gaps.append("entity")
    return gaps


def judge(diff, room, value_scale):
    """exact within the figure's own rounding; near up to 2% or three rounding units;
    beyond that a different figure."""
    if diff <= room * 1.0001 + 1e-9:
        return "exact"
    if diff <= max(3 * room, 0.02 * value_scale):
        return "near"
    return "differs"


def check_figure(fig, doc_text):
    """One reader figure -> a result dict, or None if this path has nothing to say."""
    if fig.get("status") != "stated" or not fig.get("figure") or fig["figure"] not in doc_text:
        return None
    kind = fig.get("kind")
    measure = fig.get("change_of") if kind == "change_pct" else (
        fig.get("margin_of") if kind == "margin_pct" else fig.get("measure_std"))
    if measure not in CONCEPTS or not fig.get("entity"):
        return None
    cik, how = resolve_cik(fig["entity"])
    if not cik:
        return {"verdict": "none", "why": "no CIK"}
    cf = company_facts(cik)
    if "_error" in cf:
        return {"verdict": "none", "why": "no companyfacts"}
    instant = measure in INSTANT
    window, why = target_window(fig, cf, instant and kind == "level")
    if not window:
        return {"verdict": "none", "why": why}
    parsed = parse_value(fig["figure"], fig.get("scale"))
    if not parsed:
        return None
    pos = doc_text.find(fig["figure"])
    words = fig.get("measure") or ""
    extra_gaps = []
    if COMPONENT.search(words):
        extra_gaps.append("component")
    if kind != "change_pct" and LEVEL_CHANGE.search(words):
        extra_gaps.append("a change, not a level")
    if CONTINUING.search(words):
        extra_gaps.append("continuing operations")
    if QUALIFIED.search(words):
        extra_gaps.append("qualified measure")
    if RANGE_BEFORE.search(doc_text[max(0, pos - 8):pos]):
        extra_gaps.append("range")
    # Reader v3 states these as fields. Absent (v2 readings), the word checks above
    # stand alone; present, a field that is not the safe value blocks a refutation.
    if fig.get("line_item") == "part":
        extra_gaps.append("component")
    if fig.get("line_item") == "unknown":
        extra_gaps.append("line item unknown")
    if fig.get("operations") == "continuing":
        extra_gaps.append("continuing operations")
    if kind == "change_abs":
        return None
    if kind == "change_pct" and (fig.get("comparison") or "") not in ("", "yoy"):
        return None
    if kind == "margin_pct" and measure == "revenue":
        return None
    if kind == "change_pct" and (OTHER_CHANGE.search(words) or "bps" in fig["figure"]):
        return None
    hedged = bool(HEDGE.search(doc_text[max(0, doc_text.find(fig["figure"]) - 12):
                                        doc_text.find(fig["figure"]) + len(fig["figure"])]))
    is_q4 = fig.get("period_type") == "Q4"
    # Shares outstanding differ by quarter: FY EPS minus nine-month EPS is not Q4 EPS.
    per_share_measure = kind == "per_share" or measure.startswith("eps") or measure == "dividends_per_share"

    def discontinued_in(win):
        for tax, concept in DISCONTINUED:
            for unit_rows in [facts_for(cf, tax, concept, lambda u: True)]:
                if any(r.get("val") for r in matching_facts(unit_rows, win, False)):
                    return True
        return False

    filer = filer_taxonomy(cf)

    def candidates(per_share=False, unit_code=None):
        for tax, concept in CONCEPTS[measure]:
            if filer and tax != filer:
                continue  # a US GAAP filer files nothing under IFRS, and the reverse
            if per_share or measure.startswith("eps") or measure == "dividends_per_share":
                def pred(u):
                    return u.endswith("/shares")
            elif unit_code:
                def pred(u, c=unit_code):
                    return u == c
            else:
                def pred(u):
                    return "/" not in u
            rows = facts_for(cf, tax, concept, pred)
            if rows:
                yield concept, rows

    def facts_in(rows, win):
        found = matching_facts(rows, win, instant and kind == "level")
        derived = False
        if not found and is_q4 and not instant and not per_share_measure:
            found, derived = derived_q4(rows, win), True
        return found, derived

    if kind in ("level", "per_share", "count"):
        # "4.25 billion shares" is a count; a monetary concept says nothing about it.
        after = doc_text[pos + len(fig["figure"]):pos + len(fig["figure"]) + 14]
        if re.match(r"\s*(shares|employees|people|units|stores|customers|vehicles|homes)\b", after, re.I) \
                or re.search(r"\bshares\b|headcount|employees", words, re.I) and kind != "per_share":
            return {"verdict": "none", "why": "a count, not an amount"}
        cur = currency_of(fig["figure"], fig.get("currency"))
        per_share = kind == "per_share" or measure.startswith("eps")
        results = []
        for concept, rows in candidates(per_share=per_share):
            found, derived = facts_in(rows, window)
            for r in found:
                unit_cur = r["unit"].split("/")[0]
                results.append((concept, r, derived, unit_cur))
            # A filed figure that matches ends the search; each further concept is a
            # request, and most do not exist for a given company.
            if any(judge(abs(abs(parsed["value"]) - abs(r["val"])), parsed["room"], abs(r["val"])) == "exact"
                   for r in found):
                break
        if not results:
            return {"verdict": "none", "why": "no fact for period", "window": window}
        best = None
        for concept, r, derived, unit_cur in results:
            if cur and unit_cur != cur:
                continue
            d = abs(abs(parsed["value"]) - abs(r["val"]))
            v = judge(d, parsed["room"], abs(r["val"]))
            rank = {"exact": 0, "near": 1, "differs": 2}[v]
            if best is None or rank < best[0]:
                best = (rank, v, concept, r, derived)
        if best is None:
            return {"verdict": "none", "why": f"currency {cur} vs {results[0][3]}"}
        _, v, concept, r, derived = best
        gaps = identity_gaps(fig, True, how, measure, doc_text) + extra_gaps
        if measure in ("net_income", "eps_diluted", "eps_basic") and discontinued_in(window):
            gaps.append("discontinued operations in period")
        if derived:
            gaps.append("derived Q4")
        if hedged:
            gaps.append("hedged")
        ratio = abs(parsed["value"]) / abs(r["val"]) if r["val"] else 0
        if not 0.2 <= ratio <= 5:
            # Another measure, not this one misstated.
            gaps.append("magnitude")
        # An adjusted or segment figure can match the filed one exactly; near or
        # different says nothing, since the two are not meant to be equal.
        # "Near" tells a reader the filed figure differs: a soft contradiction, so it
        # passes the same identity gate. On 29 untouched releases, 16 true figures
        # came out near before this, almost all continuing operations vs total.
        unlike = bool(gaps)
        verdict = {"exact": "verified", "near": "none" if unlike else "near",
                   "differs": "contradicted" if not gaps else "none"}[v]
        path = "sec_level" if measure in REFUTABLE else "sec_level_other"
        if verdict == "contradicted" and not ROLLOUT[path]["refute"]:
            verdict = "none"
        return {"verdict": verdict, "why": f"{concept} {r['end']} {r['val']} vs {parsed['value']}",
                "gaps": gaps, "path": path, "source_value": r["val"], "concept": concept,
                "end": r["end"], "cik": cik}

    if kind in ("change_pct", "margin_pct"):
        pct = parse_value(fig["figure"], "one")
        if not pct:
            return None
        claim = pct["value"]
        for concept, rows in candidates():
            cur_f, d1 = facts_in(rows, window)
            if not cur_f:
                continue
            if kind == "change_pct":
                pri_f, d2 = facts_in(rows, prior_window(window))
                if not pri_f:
                    continue
                pairs = [(c["val"] / p["val"] - 1) * 100 for c in cur_f for p in pri_f if p["val"]]
                if any(p["val"] <= 0 for p in pri_f):
                    extra_gaps.append("negative base")
                if fig["figure"].lstrip().startswith("-") or re.search(r"\b(down|fell|declin|decreas)", doc_text[max(0, doc_text.find(fig["figure"]) - 40):doc_text.find(fig["figure"])], re.I):
                    claim_signed = -abs(claim)
                else:
                    claim_signed = claim
                values = pairs
                derived = d1 or d2
            else:
                rev = []
                for tax, c in CONCEPTS["revenue"]:
                    rr = facts_for(cf, tax, c, lambda u: "/" not in u)
                    f, _ = facts_in(rr, window)
                    rev += f
                values = [n["val"] / r["val"] * 100 for n in cur_f for r in rev if r["val"]]
                claim_signed = claim
                derived = d1
            if not values:
                continue
            best = min(values, key=lambda x: abs(x - claim_signed))
            diff = abs(best - claim_signed)
            gaps = identity_gaps(fig, True, how, measure, doc_text) + extra_gaps
            if kind == "change_pct" and any(c <= 0 for c in [x["val"] for x in cur_f]):
                gaps.append("negative base")
            if derived:
                gaps.append("derived Q4")
            if hedged:
                gaps.append("hedged")
            # Rollout: a computed change or margin is a new path. It may confirm,
            # never refute, until the alarm corpora and a sealed set say otherwise.
            gaps.append(f"path {kind} confirm-only")
            unlike = bool(gaps)
            if diff <= pct["room"] + 0.05:
                v = "verified"
            elif diff <= max(1.0, 3 * pct["room"]):
                v = "none" if unlike else "near"
            else:
                v = "contradicted" if not gaps else "none"
            path = "sec_change" if kind == "change_pct" else "sec_margin"
            if v == "contradicted" and not ROLLOUT[path]["refute"]:
                v = "none"
            return {"verdict": v, "why": f"{kind} {concept} computed {best:.2f} vs {claim_signed}",
                    "gaps": gaps, "path": path, "source_value": round(best, 2), "concept": concept,
                    "cik": cik}
        return {"verdict": "none", "why": "no facts for change/margin"}
    return None


# ---------------------------------------------------------------- the pipeline

def _figure_key(figure):
    found = re.search(r"\d[\d,]*(?:\.\d+)?", str(figure))
    return found.group().replace(",", "") if found else ""


def _lf(text):
    """A browser submits a textarea's line breaks as CRLF, and nothing upstream
    rewrites them. The document-side rules read blank lines and line starts, and
    every test and harness run feeds LF, so the path reads what they measured."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _new_row(figure, doc_text, unit=""):
    """A result row for a figure the extractor left without one, in its own sentence."""
    from source_network import ClaimDecomposition, SourceNetworkResult
    hit = re.search(r"(?<![\d.])" + re.escape(figure), doc_text)
    if not hit:
        return None
    start = max(doc_text.rfind(m, 0, hit.start()) for m in (". ", "\n")) + 1
    end = min([i for i in (doc_text.find(". ", hit.end()), doc_text.find("\n", hit.end())) if i >= 0]
              or [len(doc_text)])
    # As the other rows show it: no list marker, no bold markers.
    sentence = re.sub(r"\*\*|__", "", doc_text[start:end + 1]).strip().lstrip("-*\u2022 ").strip()
    return SourceNetworkResult(
        claim_numbers=[figure], claim_sentence=sentence,
        decomposition=ClaimDecomposition(raw_value=figure, sentence=sentence, unit=unit),
        source_results=[], verdict="unverifiable", confidence=0.0, detail="")


def _compared(result):
    """The figure a result's verdict is about: its decomposition's own value."""
    return getattr(result.decomposition, "raw_value", "") or result.claim_numbers[0]


def _sec_url(cik):
    return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K"


# The identity path's own verdicts carry these details, so a harness can count them.
DETAIL_MATCH = "Matches the company's filed figure for the same measure and period."
DETAIL_DIFFERS = "Differs from the company's filed figure for the same measure and period."

_READING_POOL = None
_POOL_LOCK = threading.Lock()


def start_reading(doc_text, status=None):
    """Begin the identity reading alongside the other sources, or None when off.
    The model call is the slow part; started first, it costs no wall-clock of its own."""
    import identity_reader
    if not identity_reader.enabled():
        return None
    doc_text = _lf(doc_text)
    global _READING_POOL
    with _POOL_LOCK:
        if _READING_POOL is None:
            from concurrent.futures import ThreadPoolExecutor
            _READING_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="identity")
    return _READING_POOL.submit(identity_reader.read_identities, doc_text, status)


def apply_identity(results, doc_text, reading=None, deadline=None, status=None):
    """Settle what the identity path can settle in a list of SourceNetworkResult.

    It confirms a figure no other source contradicted, and refutes one no source
    confirmed, where its ROLLOUT row allows. Anything else is left as it was. With
    IDENTITY_PATH off, no reading, or the deadline (time.monotonic()) passed, nothing
    more changes.
    """
    import time
    from source_network import SourceResult, decompose_confidence
    if reading is None:
        return results
    doc_text = _lf(doc_text)
    try:
        wait = None if deadline is None else max(0.0, deadline - time.monotonic())
        figures = reading.result(timeout=wait) if hasattr(reading, "result") else reading
    except Exception:
        log.warning("identity path: no reading in time")
        if status is not None:
            status["identity_reader"] = "failed"
        return results
    if not figures:
        return results
    by_key = {}
    for fig in figures:
        by_key.setdefault(_figure_key(fig["figure"]), []).append(fig)
    # Figures the extractor left without a row: the reading found them, so the path
    # may settle them; a settled one gets a row of its own (its refutation passes the
    # same document-words guards as any other).
    seen_keys = {_figure_key(_compared(r)) for r in results if r.claim_numbers}
    orphans = []
    for fig in figures:
        key = _figure_key(fig["figure"])
        if key and key not in seen_keys and len(by_key.get(key, [])) == 1:
            row = _new_row(fig["figure"], doc_text)
            if row is not None:
                seen_keys.add(key)
                orphans.append(row)
    orphan_ids = {id(r) for r in orphans}
    for r in list(results) + orphans:
        if deadline is not None and time.monotonic() > deadline:
            break
        if r.verdict == "projection" or not r.claim_numbers:
            continue
        # The figure this row compared: a claim can list several numbers, and the
        # first is not always the one its verdict is about.
        candidates = by_key.get(_figure_key(_compared(r))) or []
        in_sentence = [f for f in candidates if f["figure"] in (r.claim_sentence or "")]
        pick = in_sentence or (candidates if len(candidates) == 1 else [])
        if len(pick) != 1:
            continue  # two readings of the same digits in one sentence: not ours to choose
        try:
            res = check_figure(pick[0], doc_text)
        except Exception:
            log.warning("identity path: check failed", exc_info=True)
            continue
        verdict = (res or {}).get("verdict")
        if id(r) in orphan_ids and verdict in ("verified", "contradicted"):
            results.append(r)
        if verdict == "verified" and r.verdict not in ("contradicted", "disputed"):
            match = "exact"
        elif verdict == "contradicted" and r.verdict not in ("verified", "close"):
            match = "contradicted"
        else:
            continue
        r.source_results.insert(0, SourceResult(
            source_name="SEC Filing",
            source_url=_sec_url(res.get("cik", "")),
            source_value=float(res.get("source_value") or 0),
            source_text=f"{res.get('concept', '')} {res.get('end', '')}".strip(),
            match_type=match,
            confidence=0.95,
        ))
        r.verdict = "verified" if match == "exact" else "contradicted"
        r.confidence = 0.95
        r.best_source = "SEC Filing"
        r.detail = DETAIL_MATCH if match == "exact" else DETAIL_DIFFERS
        r.confidence_dimensions = decompose_confidence(r.source_results)
    return apply_arithmetic(results, figures, doc_text)


DETAIL_INCONSISTENT = "Does not add up with this document's own figures"


def apply_arithmetic(results, figures, doc_text):
    """A stated change or margin the document's own levels contradict: "these figures
    cannot all be right". It names every figure involved, never one culprit, and only
    settles a figure no source did (arithmetic_check)."""
    import arithmetic_check
    from source_network import SourceResult
    try:
        flags = arithmetic_check.check(figures, doc_text)
    except Exception:
        log.warning("arithmetic check failed", exc_info=True)
        return results
    for flag in flags:
        key = _figure_key(flag["figure"])
        rows = [r for r in results if r.claim_numbers and _figure_key(_compared(r)) == key
                and flag["figure"] in (r.claim_sentence or "")]
        if not rows:
            # The extractor folded the change into its level's claim ("$2.81 billion,
            # ... an increase of 6.4%"): give the flagged figure a row of its own.
            row = _new_row(flag["figure"], doc_text, "percent")
            if row is None:
                continue
            rows = [row]
            results.append(row)
        for r in rows:
            if r.verdict not in ("unverifiable", "not_compared"):
                continue
            a, b = flag["from"]
            what = "a change of" if flag["kind"] == "change_pct" else "a margin of"
            r.source_results.insert(0, SourceResult(
                source_name="This document",
                source_value=float(flag["recomputed"]),
                source_text=f"{a} and {b} give {what} {flag['recomputed']}%",
                match_type="contradicted",
                confidence=0.9,
            ))
            r.verdict = "inconsistent"
            r.confidence = 0.9
            r.best_source = "This document"
            r.detail = (f"{DETAIL_INCONSISTENT}: {a} and {b} give {what} {flag['recomputed']}%, "
                        f"not {flag['figure']}. One of these figures is wrong.")
            break
    return results
