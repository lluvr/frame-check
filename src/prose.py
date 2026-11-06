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
    r'(US\$|\$|USD)?\s*(?:in\s+)?(?:\(?)(thousands|millions|billions)\b',
    re.IGNORECASE,
)
_PER_SHARE_RE = re.compile(r'\b(?:EPS|per[- ]share|per\s+\w+\s+share)\b', re.IGNORECASE)
_PLAIN_NUMBER_RE = re.compile(r'^\(?-?\d[\d,]*(?:\.\d+)?\)?$')
_ESTIMATE_COLUMN_RE = re.compile(
    r'\b(?:(?:19|20)\d{2}E|est\.?|estimates?|forecast|projected|target|guidance)\b',
    re.IGNORECASE,
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


def _cells(line):
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def _table_sentences(rows, preamble):
    """One sentence per cell, because a figure means nothing without its row
    and column: "Net sales in 2025 was $4,233.0 million."
    """
    header = _cells(rows[0])
    scale = _TABLE_SCALE_RE.search(preamble)
    out = []
    for row in rows[2:]:
        cells = _cells(row)
        label = cells[0]
        for column, cell in zip(header[1:], cells[1:]):
            if not cell or not re.search(r'\d', cell):
                continue
            if _ESTIMATE_COLUMN_RE.search(column):
                continue
            if scale and _PLAIN_NUMBER_RE.match(cell):
                symbol = "$" if scale.group(1) else ""
                if _PER_SHARE_RE.search(label):
                    cell = f"{symbol}{cell}"
                else:
                    cell = f"{symbol}{cell} {scale.group(2).lower().rstrip('s')}"
            if _YEAR_RE.search(column):
                out.append(f"{label} in {column} was {cell}.")
            else:
                # Lower case, or the column reads as part of the row's name.
                name = column if column.isupper() else column[:1].lower() + column[1:]
                out.append(f"{label} {name} was {cell}.")
    return out


def plain_prose(text):
    """Return text with its formatting read out. Safe to apply twice."""
    if not text:
        return text
    lines = text.split('\n')
    # "ATLANTA:" or "MEMO:" opens a document. Later on the same shape is a
    # label such as "GDP:".
    for n, line in enumerate(lines):
        if line.strip():
            if not _ALL_CAPS_TITLE_RE.match(line.strip()):
                lines[n] = _DATELINE_RE.sub('', line)
            break
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if (line.lstrip().startswith('|') and i + 1 < len(lines)
                and _TABLE_RULE_RE.match(lines[i + 1])):
            end = i + 2
            while end < len(lines) and lines[end].lstrip().startswith('|'):
                end += 1
            preamble = "\n".join(out[-4:])
            out.extend(_table_sentences(lines[i:end], preamble))
            i = end
            continue
        out.append(_plain_line(line))
        i += 1
    return "\n".join(out)


def _plain_line(line):
    stripped = line.strip()
    if _ALL_CAPS_TITLE_RE.match(stripped):
        return "# " + stripped.title()
    # A line that is all bold is a title.
    whole_bold = re.fullmatch(r'\*\*([^*]+)\*\*:?|__([^_]+)__:?', stripped)
    if whole_bold:
        return "# " + (whole_bold.group(1) or whole_bold.group(2)).strip()
    # A list item is its own statement; without an ending, the sentence
    # splitter would run neighbouring items together.
    was_item = bool(_BULLET_RE.match(line))
    line = _RUN_IN_LABEL_RE.sub('', line)
    line = _BULLET_RE.sub('', line)
    line = _BOLD_RE.sub(lambda m: m.group(1) or m.group(2), line)
    line = _ITALIC_RE.sub(r'\1', line)
    line = _FISCAL_YEAR_RE.sub(r'FY20\1\2', line)
    line = re.sub(r'\bper cent\b', 'percent', line)
    line = re.sub(r'\b(?:US|U\.S\.|USD)\s?\$', '$', line)
    line = re.sub(r'\brev\b', 'revenue', line)
    line = re.sub(r'\bNI\b', 'net income', line)
    line = _MILLION_PEOPLE_RE.sub(r'\1 million', line)
    line = _MILLION_COUNT_RE.sub(r'\1\2 million', line)
    if was_item and line.rstrip()[-1:] not in ('.', '!', '?', ':', ''):
        line = line.rstrip() + '.'
    return line
