"""Reader v3: a model describes each figure's whole identity; code checks the rest.

The claim reader (claim_reader.py) says who and what a figure is about. This reader
also says for which period, where that period came from, on what basis, at what scope,
whether the figure is a line item or a part of one, total or continuing operations,
and what a change is measured against: the attributes whose absence caused every false
contradiction on real results releases (the maintainers' evaluation record).

The reply is compact (short keys, the main entity and currency stated once, no
non-facts) because a full reading of a results release ran to 7,000 output tokens.
A document over SECTION_CHARS is read in sections in parallel, each given the
document's title as context. A figure not found verbatim in its section is dropped.

Off unless IDENTITY_PATH=on, because it sends the text to the model provider.
"""
import hashlib
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

# The reading starts with the request and the check's budget is 25 s, so it may use
# 22 s: a results release's sections take 15-22 s on Grok 4.20 (owner's choice,
# 2026-11-09: check long documents at about 20 s rather than skip them).
READER_TIMEOUT_SECONDS = float(os.environ.get("IDENTITY_READER_TIMEOUT", "22"))
# Grok 4.20 writes about 80-100 tokens a second, and a reading runs to about half a
# token per character read: a 5,000-character section took 33 s (measured 2026-11-09).
# 2,000-character sections, read in parallel, each fit the 12 s reader timeout.
SECTION_CHARS = 2000
_MAX_SECTIONS = 8
_MAX_DOC_CHARS = 14000
_CACHE_LIMIT = 64
_cache = {}
_cache_lock = threading.Lock()

PROMPT = """Describe every figure in the document so code can look it up in the company's filed
accounts. Never judge truth, never use outside knowledge. Reply with compact JSON only:

{"e": "main company as named", "c": "main currency ISO code", "f": [
 {"v": "figure exactly as written", "e": "company, only if not the main one",
  "m": "what is measured, at most four words", "s": "standard measure",
  "k": "kind", "p": "period type", "y": "fiscal year label", "d": "period end YYYY-MM-DD or omit",
  "w": "where the period came from", "b": "basis", "o": "scope", "l": "line item",
  "op": "operations", "cm": "comparison", "c": "currency, only if not the main one",
  "x": "scale, omit if none"}]}

Codes:
s: revenue cost_of_revenue gross_profit operating_income net_income pretax_income income_tax
   eps_diluted eps_basic operating_cash_flow capex free_cash_flow cash total_assets
   total_liabilities equity long_term_debt dividends_per_share rd_expense sga_expense
   operating_expenses interest_expense depreciation share_repurchases dividends_paid inventory
   ebitda comparable_sales other
k: lv (amount or count) | ps (per share) | ch (percentage change) | ca (absolute change,
   "up $0.85") | mg (percentage of revenue) | rt (other ratio or rate)
p: FY Q1 Q2 Q3 Q4 H1 9M TTM in (a balance at a date) un (unknown)
w: s (the figure's own sentence) | t (its table column or row header) | h (document title)
   | e (earlier text) | n (nowhere)
b: r (reported, GAAP or IFRS) | a (adjusted, non-GAAP, "excluding", "core") | cc (constant
   currency) | og (organic) | pf (pro forma) | u (document does not say)
o: t (whole company) | sg (segment) | rg (region) | pr (product or brand)
l: w (the line item itself) | p (a part, effect or component of it: a charge, a benefit, a
   currency impact, "includes $X of", a per-share effect of an item)
op: t (total) | co (continuing operations only)
cm: for k=ch or ca only: yy (vs the same period a year earlier) | sq (vs the previous
    quarter) | my (multi-year stack) | pt (a change in percentage points or bps)
x: k m b t (thousand, million, billion, trillion), including a table header "(in millions)"

Rules: every factual number gets one entry, including each table cell, with period, basis
and scale taken from its column and table headers. Skip dates, page numbers, ranks, phone
numbers, and numbers inside names. Skip forecasts, guidance and outlook. Reported results of
any year are facts, even if the year seems future to you. "y" is the company's own label
("fiscal 2025", "FY25" -> "2025").

Document:
"""

KINDS = {"lv": "level", "ps": "per_share", "ch": "change_pct", "ca": "change_abs",
         "mg": "margin_pct", "rt": "ratio"}
WHERE = {"s": "sentence", "t": "table_header", "h": "title", "e": "earlier_text", "n": "none"}
BASIS = {"r": "reported", "a": "adjusted", "cc": "constant_currency", "og": "organic",
         "pf": "pro_forma", "u": "unknown"}
SCOPE = {"t": "total", "sg": "segment", "rg": "region", "pr": "product"}
SCALE = {"k": "thousand", "m": "million", "b": "billion", "t": "trillion"}
PERIOD = {"in": "instant", "un": "unknown"}


def enabled():
    if os.environ.get("IDENTITY_PATH", "off").lower() != "on":
        return False
    from llm_client import xai_configured
    return xai_configured()


def expand(reply):
    """Compact reply -> one dict per figure with every identity field spelled out."""
    data = json.loads(reply) if isinstance(reply, str) else reply
    if not isinstance(data, dict):
        return []
    main_e, main_c = data.get("e", ""), data.get("c", "")
    out = []
    for f in data.get("f", []) if isinstance(data.get("f"), list) else []:
        if not isinstance(f, dict):
            continue
        kind = KINDS.get(f.get("k", "lv"), "other")
        s = f.get("s", "other")
        out.append({
            "figure": str(f.get("v", "")),
            "entity": f.get("e") or main_e,
            "measure": str(f.get("m", "")),
            "measure_std": s,
            "kind": kind,
            "change_of": s if kind in ("change_pct", "change_abs") else "",
            "margin_of": s if kind == "margin_pct" else "",
            "period_type": PERIOD.get(f.get("p"), f.get("p") or "unknown"),
            "fiscal_year": str(f.get("y") or ""),
            "period_end": f.get("d") or "",
            "period_from": WHERE.get(f.get("w"), "none"),
            "basis": BASIS.get(f.get("b"), "unknown"),
            "scope": SCOPE.get(f.get("o"), "unknown"),
            "scope_name": "",
            "currency": f.get("c") or main_c,
            "scale": SCALE.get(f.get("x"), "one"),
            "status": "stated",
            "line_item": {"w": "whole", "p": "part"}.get(f.get("l"), "unknown"),
            "operations": {"t": "total", "co": "continuing"}.get(f.get("op"), "unknown"),
            "comparison": {"yy": "yoy", "sq": "sequential", "my": "multi_year",
                           "pt": "points"}.get(f.get("cm"), ""),
        })
    return out


def sections(document):
    """The document whole if short, else sections of at most SECTION_CHARS cut at line
    breaks. Each later section carries the title, and when it starts inside a table,
    that table's header rows, as context: a cell's period and scale live there."""
    if len(document) <= SECTION_CHARS:
        return [document]
    # The first line with some substance: an EDGAR exhibit opens "EX-99.1".
    title = next((ln.strip() for ln in document.split("\n") if len(ln.strip()) >= 25),
                 document.strip().split("\n", 1)[0])[:200]
    out, current, header, prev_table_line = [], [], [], False
    for line in document.split("\n"):
        is_table = line.lstrip().startswith("|")
        if is_table and not prev_table_line:
            header = [line]  # a new table: its first row is the header
        elif is_table and len(header) == 1 and set(line.replace("|", "").strip()) <= set("-: "):
            header.append(line)  # the separator row
        prev_table_line = is_table
        size = sum(len(x) + 1 for x in current)
        if current and size + len(line) + 1 > SECTION_CHARS:
            out.append(("\n".join(current), header[:] if is_table else []))
            current = []
        current.append(line)
    if any(x.strip() for x in current):
        out.append(("\n".join(current), []))
    out = out[:_MAX_SECTIONS]
    parts = [out[0][0]]
    for body, head in out[1:]:
        ctx = f"Document title: {title}"
        if head:
            ctx += "\nTable header: " + " ".join(head)
        parts.append(f"[Context only, list none of its figures. {ctx}]\n\n{body}")
    return parts


def _call_model(text):
    from llm_client import GROK_MODEL, check_served, xai_openai_client
    client = xai_openai_client()
    if client is None:
        return ""
    client = client.with_options(max_retries=0)
    response = client.chat.completions.create(
        model=GROK_MODEL,
        messages=[{"role": "user", "content": PROMPT + text}],
        temperature=0,
        max_completion_tokens=4000,
        timeout=READER_TIMEOUT_SECONDS,
    )
    check_served(response, "identity_reader")
    return (response.choices[0].message.content or "") if response.choices else ""


def _validated(raw, body):
    """Figures found verbatim in the section's own text; the title context does not count."""
    try:
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip())
        figures = expand(text)
    except (ValueError, AttributeError, TypeError):
        return []
    return [f for f in figures if f["figure"] and f["figure"] in body and re.search(r"\d", f["figure"])]


def _record_failure(kind):
    try:
        from source_network import provider_health
        provider_health.record_error("identity_reader", kind)
    except Exception:
        pass


def _read_section(section):
    body = section.split("]\n\n", 1)[1] if section.startswith("[Context only") else section
    try:
        return _validated(_call_model(section), body)
    except Exception as exc:
        log.warning("identity reader failed: %s", type(exc).__name__)
        _record_failure(type(exc).__name__)
        return None


def read_identities(document, status=None):
    """Every figure's identity, or [] when the reading cannot be had.

    ``status``, when given, gets ``status["identity_reader"] = "failed"`` when
    any section of the reading did not come back."""
    if not document or not enabled():
        return []
    document = document[:_MAX_DOC_CHARS]
    key = hashlib.sha256(document.encode("utf8", "replace")).hexdigest()
    with _cache_lock:
        if key in _cache:
            return _cache[key]
    parts = sections(document)
    pool = ThreadPoolExecutor(max_workers=len(parts))
    futures = [pool.submit(_read_section, p) for p in parts]
    deadline = time.monotonic() + READER_TIMEOUT_SECONDS + 1
    figures, failed = [], False
    for future in futures:
        try:
            got = future.result(timeout=max(0.0, deadline - time.monotonic()))
        except Exception:
            _record_failure("deadline")
            got = None
        if got is None:
            failed = True
        else:
            figures.extend(got)
    pool.shutdown(wait=False)
    if failed and status is not None:
        status["identity_reader"] = "failed"
    if not failed:  # a partial reading is used but not remembered
        with _cache_lock:
            if len(_cache) >= _CACHE_LIMIT:
                _cache.clear()
            _cache[key] = figures
    return figures
