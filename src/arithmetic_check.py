"""Check a document's figures against each other.

A stated change ("revenue rose 12% to $4.1 billion from $3.66 billion") and a stated
margin ("operating margin of 18.2%") can be recomputed from levels the same document
states. No source is needed, so it works where no filing exists yet: a results release
is the first record of its own figures, and AI answers slip in exactly this arithmetic.

Pairs come from the identity reader (identity_reader.expand): same measure, basis,
scope, period type and currency, consecutive fiscal years. Every figure's own rounding
is carried, so the recomputed value is an interval; a figure is flagged only when it
lies outside that interval by more than its own rounding.

A flag names every figure involved, never one culprit: on a labeled set a true
33.0% margin failed to recompute because the document's revenue was the wrong
figure. "These figures cannot all be right" was true; "the margin is wrong" was not.
"""
import re

NUM = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?")
SCALE = {"one": 1, "thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}
SCALE_WORDS = [(r"tri(?:llion)?\b|\bT\b|tn\b", 1e12), (r"bil(?:lion)?\b|bn\b|\bB\b", 1e9),
               (r"mil(?:lion)?\b|mn\b|\bM\b", 1e6), (r"thousand\b|\bk\b|\bK\b", 1e3)]
DOWN = re.compile(r"\b(down|fell|fall|declin\w*|decreas\w*|lower|drop\w*|shr[ai]nk\w*)\b", re.I)


def _value(fig):
    """(value, half a unit of its last digit) in base units, or None."""
    m = NUM.search(fig["figure"])
    if not m:
        return None
    raw = m.group()
    digits = raw.strip("(").lstrip("-").replace(",", "")
    decimals = len(digits.split(".")[1]) if "." in digits else 0
    scale = SCALE.get(fig.get("scale") or "one", 1)
    tail = fig["figure"][m.end():m.end() + 12]
    for pat, mult in SCALE_WORDS:
        if re.match(r"\s*(?:" + pat + ")", tail):
            scale = mult
            break
    sign = -1 if raw.startswith(("(", "-")) else 1
    return sign * float(digits) * scale, 0.5 * 10 ** -decimals * scale


def _same_identity(a, b):
    return all(a.get(k) == b.get(k) for k in ("entity", "basis", "scope", "period_type",
                                              "currency", "operations"))


def _eligible(fig):
    return (fig.get("line_item") in ("whole", None) and fig.get("scope") == "total"
            and fig.get("measure_std") not in ("other", "", None))


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n")
MARGIN_WORDS = {
    "gross_profit": r"gross\s+(?:profit\s+)?margin",
    "operating_income": r"(?:operating|ebit)\s+(?:profit\s+|income\s+)?margin",
    "net_income": r"(?:net\s+(?:profit\s+|income\s+)?|profit\s+)margin",
}


def _token(figure):
    """The figure as a whole token: "9%" is not the 9 in "1,950" or "2019"."""
    return re.compile(r"(?<![\d.,])" + re.escape(figure) + r"(?![\d])")


def _together(doc_text, figures):
    """A sentence or table row of the document that states every one of these figures:
    (its start, where the first figure sits in it). The document pairs them itself:
    "rose 9% to $1.82 from $1.67". None if no single sentence holds them all."""
    start = 0
    for piece in _SENTENCE_END.split(doc_text):
        at = doc_text.find(piece, start)
        start = at + len(piece)
        if all(_token(f).search(piece) for f in figures):
            return at, at + _token(figures[0]).search(piece).start()
    return None


def _margin_named(fig, measure, doc_text):
    """The margin's own words in the document name that margin."""
    from identity_path import own_words
    pattern = MARGIN_WORDS.get(measure)
    hit = _token(fig["figure"]).search(doc_text)
    if not pattern or not hit:
        return False
    words = own_words(doc_text, hit.start(), fig["figure"])
    after = doc_text[hit.end():hit.end() + 40]
    return bool(re.search(pattern, words, re.I) or re.match(r"[\s*]*(?:" + pattern + ")", after, re.I))


def check(figures, doc_text):
    """Flags for stated changes and margins the document's own levels contradict."""
    levels = [f for f in figures if f.get("kind") in ("level", "per_share") and _eligible(f)]
    flags = []
    for f in figures:
        if not _eligible(f) or f.get("kind") not in ("change_pct", "margin_pct"):
            continue
        stated = _value({**f, "scale": "one"})
        if not stated:
            continue
        pct, pct_room = stated
        try:
            year = int(re.sub(r"\D", "", f.get("fiscal_year") or "")[:4])
        except ValueError:
            continue
        if f["kind"] == "change_pct":
            if (f.get("comparison") or "yoy") != "yoy":
                continue
            cur = [x for x in levels if x["measure_std"] == f["change_of"] and _same_identity(x, f)
                   and x.get("fiscal_year") == str(year)]
            pri = [x for x in levels if x["measure_std"] == f["change_of"] and _same_identity(x, f)
                   and x.get("fiscal_year") == str(year - 1)]
            pairs = [(c, p) for c in cur for p in pri]
        else:
            cur = [x for x in levels if x["measure_std"] == f["margin_of"] and _same_identity(x, f)
                   and x.get("fiscal_year") == str(year)]
            rev = [x for x in levels if x["measure_std"] == "revenue" and _same_identity(x, f)
                   and x.get("fiscal_year") == str(year)]
            pairs = [(c, r) for c in cur for r in rev]
        if not pairs or len({(c["figure"], p["figure"]) for c, p in pairs}) > 1:
            continue  # nothing to recompute from, or more than one candidate pair
        c, p = pairs[0]
        # The reader's labels pair the figures; the document must agree. On 29
        # official releases, labels rewritten as a careless reader would write them
        # (scripts/phase3/stress_labels.py) paired a segment's growth with other
        # levels three times.
        if f["kind"] == "change_pct":
            found = _together(doc_text, [f["figure"], c["figure"], p["figure"]])
            if found is None:
                continue
            start, pos = found
            # "fell 3%" within the change's own sentence, not the one before it.
            if DOWN.search(doc_text[max(start, pos - 50):pos]) and pct > 0:
                pct = -pct
        else:
            from identity_path import document_names
            if not (_margin_named(f, f["margin_of"], doc_text)
                    and document_names(c, c["measure_std"], doc_text)
                    and document_names(p, "revenue", doc_text)):
                continue
        cv, pv = _value(c), _value(p)
        if not cv or not pv or pv[0] <= 0 or cv[0] < 0:
            continue  # signs make a change on a loss ambiguous
        (a, ar), (b, br) = cv, pv
        if f["kind"] == "change_pct":
            lo = ((a - ar) / (b + br) - 1) * 100
            hi = ((a + ar) / (b - br) - 1) * 100
        else:
            lo = (a - ar) / (b + br) * 100
            hi = (a + ar) / (b - br) * 100
        if pct < lo - pct_room - 0.05 or pct > hi + pct_room + 0.05:
            flags.append({
                "figure": f["figure"], "kind": f["kind"],
                "involved": [f["figure"], c["figure"], p["figure"]],
                "recomputed": round((a / b - 1) * 100 if f["kind"] == "change_pct" else a / b * 100, 2),
                "from": (c["figure"], p["figure"]),
            })
    return flags
