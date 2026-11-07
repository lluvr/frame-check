"""A language model reads the document; the data still decides.

Rules can only recognize the forms they were written for, and every new blind
set found another: "Full", "Tirana" and "How many people live in Rwanda?" all
passed as the subject of a number. Who and what a figure is about is a reading
problem. So a model reads that much, and nothing it says reaches a verdict
without being checked: a figure and an entity must appear in the text as
written, a metric must come from a closed list, and the comparison with the
source stays in code. Any failure leaves the rule-based reading in place.

Off unless CLAIM_READER=on, because it sends the text to the model provider.
"""

import hashlib
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

# Within the 25-second verification budget, leaving the sources most of it.
READER_TIMEOUT_SECONDS = float(os.environ.get("CLAIM_READER_TIMEOUT", "12"))
_MAX_DOC_CHARS = 14000
_CACHE_LIMIT = 64
_cache = {}
_cache_lock = threading.Lock()

METRICS = (
    "revenue", "profit", "operating_income", "gross_profit", "eps",
    "research_development", "operating_expenses", "operating_cash_flow",
    "cash", "total_assets", "stockholders_equity", "long_term_debt", "inventory",
    "capex", "dividends_paid", "market_cap", "gdp", "gdp_per_capita", "population",
    "inflation", "unemployment", "life_expectancy", "area", "height", "length",
    "diameter", "weight", "other",
)
_STATUSES = ("stated", "forecast", "opinion", "not_a_fact")
_PERIOD_RE = re.compile(r'^(?:FY\s?|Q[1-4]\s+)?20[0-3]\d$', re.IGNORECASE)

_SYSTEM = (
    "You read documents and list the numbers they state. You never judge whether "
    "a number is true and you never use outside knowledge. Reply with JSON only."
)
_INSTRUCTIONS = """List every figure in the document below as JSON:
{"figures": [{"figure": "...", "entity": "...", "metric": "...", "attribute": "...",
"period": "...", "period_in_sentence": true, "status": "..."}]}

figure: copied exactly as written, with currency and scale ("$4.2bn", "1,642 m", "3.7 per cent").
entity: the company, country or thing the figure is about, copied from the document in its
fullest form ("Federal Signal Corporation"). Resolve "the company" and "it" to the name. Not a
section title, an author, or a person in a meeting. Empty if the document does not say.
metric: one of {metrics}. "profit" is net income or net loss. Use "other" if none fits.
attribute: for "other", a few words on what is measured ("internet users share", "shoreline").
period: the year the figure is for: "2025", "FY2025" or "Q2 2025". Use the year the document
says this figure is for, including a year set by a title or earlier sentence. For "up from X a
year earlier", X has the earlier year. Empty if unknown.
period_in_sentence: true only if the figure's own sentence names that period.
status: "stated" for a claim of fact, including reported results for any year, even one
that seems recent or future to you. "forecast" for a projection, target or guidance. "opinion"
for the author's guess. "not_a_fact" for a date, page number, rank, or a number inside a name.

Document:
"""


def enabled():
    if os.environ.get("CLAIM_READER", "off").lower() != "on":
        return False
    from llm_client import xai_configured
    return xai_configured()


def _call_model(document):
    import llm_client
    from llm_client import xai_openai_client
    GROK_MODEL = getattr(llm_client, "GROK_MODEL", "grok-4.20-0309-non-reasoning")
    client = xai_openai_client()
    if client is None:
        return ""
    response = client.chat.completions.create(
        model=GROK_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": (
                _INSTRUCTIONS.replace("{metrics}", ", ".join(METRICS)) + document
            )},
        ],
        temperature=0,
        max_completion_tokens=4000,
        timeout=READER_TIMEOUT_SECONDS,
    )
    return (response.choices[0].message.content or "") if response.choices else ""


def _names_in(entity, document):
    """The entity as written, or "" if the text does not contain it."""
    entity = (entity or "").strip().strip(".,")
    if len(entity) < 2:
        return ""
    # A possessive or a corporate suffix can differ between mentions.
    core = re.sub(r"['’]s$", "", entity)
    if re.search(r'(?<!\w)' + re.escape(core) + r'(?!\w)', document, re.IGNORECASE):
        return core
    return ""


def _validated(raw, document):
    """Keep only what the document itself supports."""
    try:
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip())
        figures = json.loads(text).get("figures", [])
    except (ValueError, AttributeError):
        return []
    out = []
    for item in figures if isinstance(figures, list) else []:
        if not isinstance(item, dict):
            continue
        figure = str(item.get("figure") or "").strip()
        if not figure or figure not in document or not re.search(r'\d', figure):
            continue
        metric = str(item.get("metric") or "")
        period = str(item.get("period") or "").strip()
        status = str(item.get("status") or "")
        out.append({
            "figure": figure,
            "entity": _names_in(item.get("entity"), document),
            "metric": metric if metric in METRICS and metric != "other" else "",
            "attribute": str(item.get("attribute") or "")[:60],
            "period": period if _PERIOD_RE.match(period) else "",
            "period_in_sentence": bool(item.get("period_in_sentence")),
            "status": status if status in _STATUSES else "stated",
        })
    return out


def _agreed(first, second):
    """What two independent readings agree on. A field they differ on is left
    to the rules, and a figure only one of them found is dropped: one model
    call read "Drinkware did $1.09 billion" as revenue and the next did not.
    """
    other = {f["figure"]: f for f in second}
    out = []
    for figure in first:
        twin = other.get(figure["figure"])
        if twin is None:
            continue
        merged = {"figure": figure["figure"]}
        for field in ("entity", "metric", "attribute", "period"):
            merged[field] = figure[field] if figure[field] == twin[field] else ""
        merged["period_in_sentence"] = figure["period_in_sentence"] and twin["period_in_sentence"]
        merged["status"] = figure["status"] if figure["status"] == twin["status"] else "stated"
        out.append(merged)
    return out


def _one_reading(document):
    try:
        return _validated(_call_model(document), document)
    except Exception as exc:
        # The rule-based reading stands. Never let the reader break a check.
        log.warning("claim reader failed: %s", type(exc).__name__)
        _record_failure(type(exc).__name__)
        return None


def _record_failure(kind):
    try:
        from source_network import provider_health
        provider_health.record_error("claim_reader", kind)
    except Exception:
        pass


def read_figures(document):
    """The validated reading of a document, or [] when it cannot be had.

    Two readings run in parallel and only what both say is kept, so a verdict
    does not flip between runs on the same text. If one call fails, the other
    is used alone.
    """
    if not document or not enabled():
        return []
    document = document[:_MAX_DOC_CHARS]
    key = hashlib.sha256(document.encode("utf8", "replace")).hexdigest()
    with _cache_lock:
        if key in _cache:
            return _cache[key]
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(_one_reading, [document, document])
    if first is None and second is None:
        return []
    if first is None or second is None:
        figures = first if first is not None else second
    else:
        figures = _agreed(first, second)
    with _cache_lock:
        if len(_cache) >= _CACHE_LIMIT:
            _cache.clear()
        _cache[key] = figures
    return figures


def figure_key(figure):
    """The digits of a figure, so "$4.2bn" and "4.2" can be paired."""
    found = re.search(r'\d[\d,]*(?:\.\d+)?', str(figure))
    return found.group().replace(",", "") if found else ""
