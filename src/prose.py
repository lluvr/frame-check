"""Turn formatted text into the plain prose the claim readers expect.

Chat answers, press releases and analyst notes state their numbers in markdown
lists, tables and shorthand. Read as written, a table row loses its column, a
bullet's bold label reads as a name, and "3.39m" loses its scale.
"""

import re

_TABLE_RULE_RE = re.compile(r'^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$')
_BULLET_RE = re.compile(r'^\s*(?:[-*•]|\d{1,2}[.)])\s+')
_BOLD_RE = re.compile(r'\*\*(.+?)\*\*|__(.+?)__')
_ITALIC_RE = re.compile(r'(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])')
_DATELINE_RE = re.compile(r'^[A-Z][A-Z .,]{2,30}:\s+(?=\S)')
_FISCAL_YEAR_RE = re.compile(r'\bFY\s?(\d{2})(E?)\b')
_YEAR_RE = re.compile(r'\b(?:FY|fiscal\s+)?(?:19|20)\d{2}\b', re.IGNORECASE)
_TABLE_SCALE_RE = re.compile(
    r'(US\$|\$|USD)?\s*(?:in\s+)?(?:\(?)(thousands|millions|billions|000s|000\'s|000,000s)(?!\w)',
    re.IGNORECASE,
)
_PER_SHARE_RE = re.compile(r'\b(?:EPS|per[- ]share|per\s+(?:\w+\s+){1,3}share)\b', re.IGNORECASE)
_PLAIN_NUMBER_RE = re.compile(r'^\(?-?\d[\d,]*(?:\.\d+)?\)?$')
_ESTIMATE_COLUMN_RE = re.compile(
    r'\b(?:(?:19|20)\d{2}E|est\.?|estimates?|forecast|projected|target|guidance)\b',
    re.IGNORECASE,
)
_DASH_DATELINE_RE = re.compile(
    r'^[A-Z][A-Z .]{2,30}(?:,\s*[A-Z][a-z]+\.?)?\s*(?:--|-|\u2014|\u2013)\s+(?=[A-Z])'
)
_ATTENDEES_RE = re.compile(r'^\s*Attendees:\s*(.+)$', re.MULTILINE)
_FAQ_MARKER_RE = re.compile(r'^\s*[QA]:\s+')
_DROPPED_LINE_RE = re.compile(
    r'^\s*(?:TO|FROM|CC|Attendees|Date|Hi\s+\w+,?|Hello\s+\w+,?|Dear\s+\w+,?)(?::.*)?\s*$',
)
_MEMO_LABEL_RE = re.compile(r'^\s*(?:RE|Re|Subject):\s+')
_PERIOD_DATELINE_RE = re.compile(r'^[A-Z][A-Z ]{2,30}\.\s+(?=[A-Z])')
_FISCAL_YEAR_END_RE = re.compile(r'\bFYE\s+[A-Z][a-z]{2}-(\d{2})\b')
_SHORTHAND = (
    (re.compile(r'\b[Rr]ev\b'), 'revenue'),
    (re.compile(r'\bNI\b'), 'net income'),
    (re.compile(r'\bOp inc\b'), 'operating income'),
    (re.compile(r'\bop inc\b'), 'operating income'),
    (re.compile(r'\bDil EPS\b'), 'diluted EPS'),
    (re.compile(r'\bYE cash\b'), 'year-end cash'),
    (re.compile(r'\bGP\b'), 'gross profit'),
    (re.compile(r'\bInv\b'), 'inventory'),
    (re.compile(r'\bLTD\b'), 'long-term debt'),
    (re.compile(r'\bGDP/capita\b'), 'GDP per capita'),
    (re.compile(r'\bPop\.(?=\s)'), 'population'),
)
_RUN_IN_LABEL_RE = re.compile(r'^\s*\*\*[^*\n]{1,40}\.\*\*\s+(?=\S)')
_ALL_CAPS_TITLE_RE = re.compile(r"^[A-Z][A-Z0-9 ,:&'-]{4,}$")

# "3.39m residents": millions of people, not metres. Only where the sentence
# says so, because "It spans 4.3m" is a length.
_MILLION_PEOPLE_RE = re.compile(
    r'\b(\d+(?:\.\d+)?)m\b(?=\s+(?:people|residents|inhabitants|citizens|'
    r'users|customers|subscribers|employees|workers|voters|visitors)\b)',
)
_MILLION_COUNT_RE = re.compile(
    r'(\b(?:population|headcount)\s+(?:of\s+|was\s+|is\s+|at\s+)'
    r'(?:about\s+|around\s+|roughly\s+|nearly\s+)?'
    r'|\b(?:has|have|had|counted)\s+(?:about\s+|around\s+|roughly\s+|nearly\s+)?)'
    r'(\d+(?:\.\d+)?)m\b(?!\s*(?:tall|high|long|wide|deep|across|of))',
)


def _words(text):
    return frozenset(text.split())


_ENGLISH_WORDS = _words(
    "the and of to is was were are for that with as on by at from it its this "
    "an be or which has had have not but")
_OTHER_WORDS = _words(
    # German, French, Spanish, Italian, Portuguese, Dutch function words that
    # are not English words. Counted only in lower case: in English they turn
    # up capitalized inside names ("Los Angeles", "Des Moines", "El Paso").
    "der das und ist mit von eine ein nicht auf sich dem zu wurde im bei hatte "
    "rund betrug auch nach wie aus sind wird einer eines zur zum als oder "
    "für über "
    "le la les et est une du que pour dans sur aux avec mais sont été "
    "el los las y es por para una del se lo fue más pero como está de en un al "
    "il di che della sono gli "
    "os da em uma "
    "het een van zijn niet voor")


def is_english(text):
    """False for a text written in another language. Figures there are
    written another way ("84,5 Millionen" is 84.5 million, "2.962 Meter" is
    2,962 metres), so reading them as English misreads them."""
    words = re.findall(r"[A-Za-zÀ-ÿ]+", text or "")
    english = sum(w.lower() in _ENGLISH_WORDS for w in words)
    # Case kept: "Los Angeles" and "Des Moines" are English.
    other = sum(w in _OTHER_WORDS for w in words)
    return not (other >= 4 and other > 2 * english and other >= 0.05 * len(words))


def _cells(line):
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def _table_sentences(rows, preamble, group=None):
    """One sentence per cell, because a figure means nothing without its row
    and column: "Net sales in 2025 was $4,233.0 million."

    A group row above the header ("Three Months Ended September 30," over
    "2026 | 2025") is part of each column's name, and the header's first cell
    ("(In thousands, except per share amounts)") is a caption.
    """
    header = _cells(rows[0])
    # The header continued on the first row: "2026 | 2025 | $ Change" under
    # "August 31, | August 31,", often one cell short of a row label.
    if len(rows) > 2:
        below = _cells(rows[2])
        caption_first = bool(below) and not re.search(r'\d', below[0]) and len(below[0]) > 12
        rest = below[1:] if caption_first else below
        if below and all(re.fullmatch(r'(?:FY\s?)?(?:19|20)\d\d|[$%]?\s*change(?:\(\d\))?|'
                                      r'%\s*chg\.?|', c, re.IGNORECASE) for c in rest) and \
                any(_YEAR_RE.fullmatch(c) for c in rest):
            if caption_first:
                # "In millions, except per share amounts | 2026 | 2025": a caption.
                preamble = f"{preamble}\n{below[0]}"
                below = [""] + rest
            if below[0] and _YEAR_RE.fullmatch(below[0]):
                below = [""] + below
            width = max(len(header), len(below))
            header += [""] * (width - len(header))
            below += [""] * (width - len(below))
            header = [header[0]] + [f"{h} {b}".strip() for h, b in zip(header[1:], below[1:])]
            rows = rows[:2] + rows[3:]
    # Columns named by figures ("Revenue | $9,115 | $7,302"): the real header
    # was lost, and no cell can be named.
    if any(re.search(r'\$\s?\d|\d,\d{3}', c) for c in header[1:]):
        return []
    if group:
        above, carried = _cells(group), ""
        for k in range(1, len(header)):
            if k < len(above) and above[k]:
                carried = above[k]
            if carried:
                header[k] = f"{carried} {header[k]}".strip()
    # "Three Months Ended October 31," in the first cell is every year
    # column's period.
    if header and _PERIOD_CELL_RE.match(header[0]):
        for k in range(1, len(header)):
            if _YEAR_RE.fullmatch(header[k].strip()) and not _PERIOD_CELL_RE.search(header[k]):
                header[k] = f"{header[0]} {header[k]}"
    preamble = f"{preamble}\n{header[0]}" if header and header[0] else preamble
    scale = _TABLE_SCALE_RE.search(preamble)
    columns = _caption_column_units(preamble, header)
    measure = _CAPTION_MEASURE_RE.search(preamble or "")
    if columns:
        # The caption gave each column its unit: it is no scale for them all.
        scale = None
    out = []
    # A long table: one column holds each row's year ("| Measure | Year |
    # Figure |", v22), or the rows are years ("| Year | Growth | Inflation |").
    year_col = next((k for k, h in enumerate(header)
                     if re.fullmatch(r'(?:year|period|date)', h.strip(), re.IGNORECASE)), None)
    for row in rows[2:]:
        cells = _cells(row)
        if year_col is not None and year_col < len(cells) and _YEAR_RE.fullmatch(cells[year_col]):
            year = cells[year_col]
            label = cells[0] if year_col else ""
            if year_col and not label:
                continue
            figures = [(column, cell) for k, (column, cell) in enumerate(zip(header, cells))
                       if k != year_col and (k or not year_col) and cell and re.search(r'\d', cell)]
            for column, cell in figures:
                if not year_col:
                    name = column
                elif len(figures) == 1:
                    name = label  # "| Income per person | 2017 | $712 |"
                else:
                    # "| Poland | 2020 | -2.2% | 3.4% |": each column is a measure.
                    name = f"{label} {column[:1].lower() + column[1:] if not column[1:2].isupper() else column}"
                # Prose order, "Real GDP growth was 11.8% in 2021.": with the year
                # before the verb the growth reader lost its head (v20 Turkiye).
                out.append(f"{name} was {cell} in {year}.")
            continue
        label = cells[0]
        # "Population (millions)", "GDP (US$ bn)", "Real GDP growth (%)": the
        # row's own unit, written onto each of its cells.
        unit = _ROW_UNIT_RE.search(label)
        if unit:
            label = label[:unit.start()].rstrip()
        # A converted statement can leave a figure in the row's name
        # ("Net income $9,115"): no cell of that row can be read.
        if re.search(r'\$\s?\d|\d,\d{3}', label):
            continue
        # More cells than the header has columns: which column a cell
        # belongs to cannot be told.
        if len([c for c in cells if c]) > len(header):
            continue
        for column, cell in zip(header[1:], cells[1:]):
            if not cell or not re.search(r'\d', cell):
                continue
            if _ESTIMATE_COLUMN_RE.search(column):
                continue
            # "(main span)" after a row's name is no unit: the caption decides.
            if unit and _PLAIN_NUMBER_RE.match(cell) and \
                    _with_row_unit(cell, unit.group(1)) != cell:
                cell = _with_row_unit(cell, unit.group(1))
            elif columns.get(column) and _PLAIN_NUMBER_RE.match(cell):
                cell = _with_row_unit(cell, columns[column])
            elif (measure and _PLAIN_NUMBER_RE.match(cell)
                  and not _YEAR_COLUMN_RE.search(column)
                  and not re.fullmatch(r'(?:1[5-9]|20)\d\d', cell)):
                # "All figures in metres": every measure, not the years.
                cell = f"{cell} {_MEASURE_SHORT.get(measure.group(1).lower(), measure.group(1))}"
            elif (scale and _DOLLAR_CELL_RE.match(cell) and not _PER_SHARE_RE.search(label)
                    and _CAPTION_SCALE_RE.search(preamble)):
                # "$7,140,027" under "(in thousands)" is $7.1 billion.
                cell = f"{cell} {_scale_word(scale.group(2))}"
            elif scale and _PLAIN_NUMBER_RE.match(cell):
                # "(in millions of US dollars)" says dollars after the scale.
                symbol = "$" if (scale.group(1) or re.search(
                    r'\b(?:of\s+)?(?:US\s+)?dollars\b|\bUSD\b', preamble, re.IGNORECASE,
                )) else ""
                if _PER_SHARE_RE.search(label):
                    cell = f"{symbol}{cell}"
                else:
                    cell = f"{symbol}{cell} {_scale_word(scale.group(2))}"
            if _YEAR_RE.search(column):
                out.append(f"{label} in {column} was {cell}.")
            elif _LINE_ITEM_HEADER_RE.fullmatch(header[0].strip()):
                # "| Line item | PepsiCo | McDonald's |": the column is whose.
                out.append(f"{column} {label[:1].lower() + label[1:]} was {cell}.")
            else:
                # Lower case, or the column reads as part of the row's name.
                # "GDP per capita" keeps its acronym.
                name = column if column.isupper() or column[1:2].isupper() \
                    else column[:1].lower() + column[1:]
                out.append(f"{label} {name} was {cell}.")
    return out


# "(in thousands, except per-share amounts)" or "$ in millions" is a caption;
# "we serve millions of customers" is not.
_CAPTION_SCALE_RE = re.compile(
    r'(?:\(\s*(?:US\$|\$|USD)?\s*(?:in\s+)?|\bin\s+(?:US\$|\$|USD\s+)?)'
    r'(?:thousands|millions|billions|000s|000\'s)(?!\w)',
    re.IGNORECASE,
)
_PERIOD_CELL_RE = re.compile(
    r'\s*(?:three|six|nine|twelve|3|6|9|12)\s+months\s+ended\b|\s*(?:quarter|year)\s+ended\b',
    re.IGNORECASE)
def _scale_word(found):
    """"thousands" or "000s" as the word written after a figure."""
    found = found.lower()
    return {"000s": "thousand", "000's": "thousand", "000,000s": "million"}.get(
        found, found.rstrip("s"))


_ROW_UNIT_RE = re.compile(r'\s*\(([^()]{1,20})\)\s*$')
# A first header cell saying the rows are line items: the columns are names.
_LINE_ITEM_HEADER_RE = re.compile(
    r'(?:line\s+items?|items?|metrics?|measures?|financials?|key\s+figures)', re.IGNORECASE)
# "All figures in metres": one measure for every cell of the table.
_CAPTION_MEASURE_RE = re.compile(
    r'\b(?:all\s+)?(?:figures|values|numbers|heights|lengths|distances|measurements)\s+'
    r'(?:are\s+)?in\s+(metres|meters|feet|kilometres|kilometers|km|miles)\b',
    re.IGNORECASE,
)
_MEASURE_SHORT = {"metres": "m", "meters": "m", "feet": "ft", "kilometres": "km",
                  "kilometers": "km"}
_YEAR_COLUMN_RE = re.compile(
    r'\b(?:year|completed|opened|built|founded|since|established)\b', re.IGNORECASE)
# "GDP in billions of current US dollars; population in millions; growth,
# inflation and unemployment in percent": each column named with its unit.
_CAPTION_UNIT_RE = re.compile(
    r'^\s*(?P<names>[A-Za-z][A-Za-z ,]*?)\s+(?:(?:is|are)\s+)?in\s+'
    r'(?P<unit>(?:(?:billions|millions|thousands|trillions)\b[^;.]*|percent|per\s+cent|%|'
    r'(?:US\s+)?dollars|years))\s*$',
    re.IGNORECASE,
)


def _caption_column_units(preamble, header):
    """Each column's unit from a caption that names columns with units,
    matched by the column's last word: "Real GDP growth" is growth."""
    units = {}
    for part in re.split(r'[;.]\s*|\n', preamble or ""):
        found = _CAPTION_UNIT_RE.match(part)
        if not found:
            continue
        for name in re.split(r',\s*|\s+and\s+', found.group("names")):
            name = name.strip().lower()
            if name:
                units[name] = found.group("unit")
    if len(units) < 2:
        return {}
    out = {}
    for column in header[1:]:
        words = re.findall(r'[a-z]+', column.lower())
        unit = next((u for name, u in units.items()
                     if words and name.split()[-1] == words[-1]
                     and all(w in words for w in name.split())), None)
        if unit:
            out[column] = unit
    return out
_DOLLAR_CELL_RE = re.compile(r'^[$€£]\(?-?\d[\d,]*(?:\.\d+)?\)?$')
_ROW_SCALES = (
    (r'\b(?:bn|billions?)\b', "billion"), (r'\b(?:mn|m|millions?)\b', "million"),
    (r'\b(?:k|thousands?)\b', "thousand"), (r'\b(?:tn|trillions?)\b', "trillion"),
)


def _with_row_unit(cell, unit):
    """A cell with the unit its row label gave: "71.7" under "(millions)" is
    "71.7 million", "529.4" under "(US$ bn)" is "$529.4 billion". A label it
    cannot read leaves the cell as it was."""
    text = unit.strip()
    if re.fullmatch(r'%|percent|per\s+cent', text, re.IGNORECASE):
        return f"{cell}%"
    # A unit alone is a measurement: "Height (m)" is metres, not millions.
    if re.fullmatch(r'years?|days?|km|m|ft|feet|miles?|kg|tonnes?|hours?|km2|km\u00b2',
                    text, re.IGNORECASE):
        return f"{cell} {text}"
    symbol = "$" if re.search(r'US\$|\$|\bUSD\b|dollars', text, re.IGNORECASE) else ""
    scale = next((word for pattern, word in _ROW_SCALES
                  if re.search(pattern, text, re.IGNORECASE)), "")
    if symbol or scale:
        return f"{symbol}{cell}{' ' + scale if scale else ''}"
    return cell


_ALIGNED_ROW_RE = re.compile(
    r'^(\s*[A-Za-z][A-Za-z ,&()\'-]*?)(\s{2,})(\(?-?\d[\d,]*(?:\.\d+)?\)?)((?:\s{2,}\(?-?\d[\d,]*(?:\.\d+)?\)?)*)\s*$'
)


def _scale_aligned_tables(text):
    """A plain-text table under "(in thousands)" states its figures without a
    scale; write the scale onto each figure, except per-share amounts."""
    scale = _TABLE_SCALE_RE.search(text)
    if not scale or "|" in text:
        return text
    word = _scale_word(scale.group(2))
    out = []
    for line in text.split('\n'):
        row = _ALIGNED_ROW_RE.match(line)
        if row and not _PER_SHARE_RE.search(row.group(1)):
            line = re.sub(
                r'(?<![\d.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{2,})(?![\d.,])',
                lambda m: f"{m.group(1)} {word}", line,
            )
        out.append(line)
    return '\n'.join(out)


# A line broken inside a sentence ends without closing punctuation, and the
# next carries on in lower case, with a figure, or in a bracket.
def _join_wrapped_lines(text):
    """"(adjusted net earnings of\n$179 million" is one sentence. A table row
    is never joined, and no line is joined onto a bullet or a table row."""
    lines = text.split("\n")
    out = []
    for line in lines:
        if (out and out[-1].strip() and line.strip()
                and not out[-1].lstrip().startswith("|")
                and not re.match(r'\s*(?:[|\u2022*-]|\d{1,2}[.)]\s)', line)
                and re.search(r'[A-Za-z,]\s*$', out[-1])
                and re.match(r'\s*(?:[a-z]|[$\u20ac\u00a3(]\s*\d|\d)', line)):
            out[-1] = out[-1].rstrip() + " " + line.strip()
        else:
            out.append(line)
    return "\n".join(out)


def plain_prose(text):
    """Return text with its formatting read out. Safe to apply twice."""
    if not text:
        return text
    # CRLF from a browser form or a Windows file: blank lines mark paragraphs.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _join_wrapped_lines(text)
    if not re.search(r'\d (?:thousand|million|billion)\b', text):
        text = _scale_aligned_tables(text)
    # Someone listed as attending is not what the notes are about.
    for found in _ATTENDEES_RE.finditer(text):
        for name in re.findall(r'\b[A-Z][a-z]+\b', found.group(1)):
            text = re.sub(
                r'(?m)^((?!\s*Attendees:).*?)\b' + name + r'\b', r'\1they', text,
            )
    lines = text.split('\n')
    # "ATLANTA:" or "MEMO:" opens a document. Later on the same shape is a
    # label such as "GDP:".
    for n, line in enumerate(lines):
        if line.strip():
            if not _ALL_CAPS_TITLE_RE.match(line.strip()):
                lines[n] = _PERIOD_DATELINE_RE.sub('', _DATELINE_RE.sub('', line))
            break
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        group = None
        if (line.lstrip().startswith('|') and i + 2 < len(lines)
                and lines[i + 1].lstrip().startswith('|')
                and not _TABLE_RULE_RE.match(lines[i + 1])
                and _TABLE_RULE_RE.match(lines[i + 2])):
            # A two-row header: this row groups the columns of the next.
            group, i = line, i + 1
            line = lines[i]
        if (line.lstrip().startswith('|') and i + 1 < len(lines)
                and _TABLE_RULE_RE.match(lines[i + 1])):
            end = i + 2
            while end < len(lines) and lines[end].lstrip().startswith('|'):
                end += 1
            preamble = "\n".join(out[-4:])
            out.extend(_plain_line(t) for t in _table_sentences(lines[i:end], preamble, group))
            i = end
            continue
        if _DROPPED_LINE_RE.match(line):
            i += 1
            continue
        # A short line with no ending, right above a list, titles that list.
        if (line.strip() and len(line.split()) <= 5 and line.rstrip()[-1] not in '.:!?'
                and not line.lstrip().startswith('#')
                and not _BULLET_RE.match(line)
                and i + 1 < len(lines) and _BULLET_RE.match(lines[i + 1])):
            out.append("# " + _plain_line(line).strip())
            i += 1
            continue
        out.append(_plain_line(line))
        # A list item stands alone. The sentence splitter only breaks before a
        # capital, and an item can open with "$3bn" or "2025 sales".
        if _BULLET_RE.match(line):
            out.append("")
        i += 1
    return "\n".join(out)


def _spelled_out(spelled, match):
    """Keep a sentence's capital, which is where the sentence splitter breaks."""
    before = match.string[:match.start()].rstrip()
    if not before or before[-1] in '.!?;':
        return spelled[:1].upper() + spelled[1:]
    return spelled


def _loss(currency, digits, scale):
    """'$340.3 million (a loss)': a word scale is spaced, a suffix is not."""
    return f"{currency}{digits}{' ' if len(scale) > 2 else ''}{scale} (a loss)"


def _names_a_country(text):
    from source_network import _COUNTRY_NAMES_RE
    return bool(_COUNTRY_NAMES_RE.fullmatch(text or ""))


def _plain_line(line):
    stripped = line.strip()
    if _ALL_CAPS_TITLE_RE.match(stripped):
        return "# " + stripped.title()
    # A line that is all bold is a title.
    whole_bold = re.fullmatch(r'\*\*([^*]+)\*\*:?|__([^_]+)__:?', stripped)
    if whole_bold:
        return "# " + (whole_bold.group(1) or whole_bold.group(2)).strip()
    # A list item is its own statement, so it gets an ending.
    was_item = bool(_BULLET_RE.match(line))
    # "**Worth the trip.**" goes; "**2024: back to profit.**" names the year.
    label = _RUN_IN_LABEL_RE.match(line)
    named = label.group().strip().strip('*').rstrip('.').strip() if label else ""
    if label and re.search(r'\b(?:19|20)\d{2}\b', label.group()):
        line = named + '. ' + line[label.end():]
    elif label and _names_a_country(named):
        # "**China.** The economy was ...": the country heads its section (v28:
        # dropping it gave China's figures to Macao).
        return "# " + named + "\n" + _plain_line(line[label.end():])
    else:
        line = _RUN_IN_LABEL_RE.sub('', line)
    line = _BULLET_RE.sub('', line)
    line = _BOLD_RE.sub(lambda m: m.group(1) or m.group(2), line)
    line = _ITALIC_RE.sub(r'\1', line)
    if len(line.split()) > 9:
        line = _DASH_DATELINE_RE.sub('', line)
    line = _FAQ_MARKER_RE.sub('', line)
    line = _MEMO_LABEL_RE.sub('', line)
    line = _FISCAL_YEAR_RE.sub(r'FY20\1\2', line)
    line = re.sub(r'\bper cent\b', 'percent', line)
    # "$(52.5)M" is how a statement writes a loss.
    line = re.sub(
        r'([$\u20ac\u00a3])\((\d[\d,]*(?:\.\d+)?)\)'
        r'(\s?(?:bn|mn|[MBK])\b|\s+(?:thousand|million|billion|trillion)\b)?',
        # The scale stays with the figure: "$340.3 (a loss) million" was read
        # as $340.30.
        lambda m: _loss(m.group(1), m.group(2), (m.group(3) or '').strip()), line,
    )
    line = re.sub(r'\b(?:US|U\.S\.|USD)\s?\$', '$', line)
    line = _FISCAL_YEAR_END_RE.sub(r'FY20\1', line)
    for pattern, spelled in _SHORTHAND:
        line = pattern.sub(lambda m: _spelled_out(spelled, m), line)
    line = _MILLION_PEOPLE_RE.sub(r'\1 million', line)
    line = _MILLION_COUNT_RE.sub(r'\1\2 million', line)
    if was_item and line.rstrip()[-1:] not in ('.', '!', '?', ':', ''):
        line = line.rstrip() + '.'
    return line
