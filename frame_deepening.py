"""Per-frame deepening of three load-bearing FVS areas.

Each detection is a deterministic surgical addition to a specific
FVS area: temporal anchoring (FVS-014), stakeholder mapping
(FVS-011), and falsification conditions (FVS-007 / FVS-009). The
goal is to give the agent specific document-content evidence
beyond the FVS firing/absence signal.

The substrate stays deterministic. Each detection is regex-based
or structural; no LLM is invoked. Each emits a construct-honest
shape with explicit fields and (where meaningful) candidate
samples that the agent can cite inline.

Each detector returns None when the document is too short or
malformed for its analysis to be meaningful (typically <100
words). The MCP response then omits the corresponding sub-field
rather than carrying empty placeholders.
"""

from __future__ import annotations

import re
from typing import Optional


# Minimum word count before any deepening detector emits results.
# Below this, density and conditional patterns are too noisy to
# anchor an honest reading.
_MIN_WORDS = 100


def _word_count(text: str) -> int:
    return len(text.split())


# ── Item 8: Temporal scope detection (deepens FVS-014) ──

# Year references: 4-digit years 1900-2099. Word boundaries to
# avoid false positives ("1234" inside other numbers).
_YEAR_RE = re.compile(r"\b(19[0-9]{2}|20[0-9]{2})\b")

# Decade phrasing ("the 2020s", "early 2010s"). Anchors temporal
# scope at the decade level.
_DECADE_RE = re.compile(
    r"\b(early|mid|late)?\s*(19|20)[0-9]0s\b",
    re.IGNORECASE,
)

# Relative temporal anchors that indicate forward projection or
# retrospective lookback without naming a specific year.
_PROJECTION_RE = re.compile(
    r"\b(?:next\s+(?:year|decade|quarter|five\s+years|ten\s+years)|"
    r"by\s+(?:end\s+of\s+)?(?:the\s+decade|2[0-9]{3})|"
    r"in\s+(?:five|ten|twenty)\s+years|"
    r"by\s+(?:19|20)[0-9]{2})\b",
    re.IGNORECASE,
)

_RETROSPECTIVE_RE = re.compile(
    r"\b(?:last\s+(?:year|decade|quarter)|"
    r"in\s+(?:19|20)[0-9]{2}|"
    r"a\s+(?:few\s+)?(?:years|decades|quarters)\s+ago|"
    r"since\s+(?:19|20)[0-9]{2})\b",
    re.IGNORECASE,
)


def detect_temporal_scope(text: str, current_year: int = 2026) -> Optional[dict]:
    """Detect temporal scope: which years the document references,
    how those years cluster (near-now, historical, projection), and
    a one-line scope reading naming the time-horizon shape.

    Returns None when the text is too short for the analysis to be
    meaningful.

    Output:
      {
        "years_referenced": sorted list of unique 4-digit years,
        "year_count": int,
        "near_now_years": years within +/- 2 of current_year,
        "historical_years": years more than 5 years before current,
        "projection_years": years more than 2 years after current,
        "decade_references": list of decade strings ("the 2020s"),
        "projection_phrase_count": int,
        "retrospective_phrase_count": int,
        "scope_reading": one-line prose anchoring the temporal
                         shape ("Document reasons across 2024-2026
                         figures..."),
      }
    """
    if _word_count(text) < _MIN_WORDS:
        return None

    # Extract years.
    year_matches = _YEAR_RE.findall(text)
    years = sorted({int(y) for y in year_matches})
    near_now = [y for y in years if abs(y - current_year) <= 2]
    historical = [y for y in years if (current_year - y) > 5]
    projection = [y for y in years if (y - current_year) > 2]

    # Decade and phrase counts.
    decades = sorted(set(m.group(0) for m in _DECADE_RE.finditer(text)))
    projection_count = len(_PROJECTION_RE.findall(text))
    retrospective_count = len(_RETROSPECTIVE_RE.findall(text))

    # Compose the scope reading. Construct-honest: name what the
    # document anchors itself to, not a verdict.
    if not years and not decades and projection_count == 0 and retrospective_count == 0:
        scope_reading = (
            "No explicit temporal anchors detected. The document "
            "does not name specific years, decades, or projection "
            "windows; the time horizon of its claims is structurally "
            "unspecified."
        )
    else:
        anchor_parts: list[str] = []
        if near_now:
            anchor_parts.append(
                f"near-now years ({', '.join(str(y) for y in near_now)})"
            )
        if historical:
            anchor_parts.append(
                f"historical years ({', '.join(str(y) for y in historical[:3])}"
                f"{', ...' if len(historical) > 3 else ''})"
            )
        if projection:
            anchor_parts.append(
                f"forward-projection years ("
                f"{', '.join(str(y) for y in projection[:3])}"
                f"{', ...' if len(projection) > 3 else ''})"
            )
        if not anchor_parts:
            anchor_parts.append("decade-level or relative temporal phrases")
        scope_reading = (
            "Document anchors temporal scope across "
            + " plus ".join(anchor_parts)
            + ". The same conclusion at different time horizons may "
            "shift; the reader can ask what changes if the figures "
            "or events were shifted forward or backward by the "
            "anchoring window."
        )

    return {
        "years_referenced": years,
        "year_count": len(years),
        "near_now_years": near_now,
        "historical_years": historical,
        "projection_years": projection,
        "decade_references": decades,
        "projection_phrase_count": projection_count,
        "retrospective_phrase_count": retrospective_count,
        "scope_reading": scope_reading,
    }


# ── Item 9: Stakeholder map detection (deepens FVS-011) ──

# Stakeholder role categories. Conservative regex; matches noun
# phrases that appear in analytical/business prose. Each role is a
# tuple of (canonical_label, regex_pattern). Order matters: more
# specific roles first so the regex doesn't over-match generic
# terms.
_STAKEHOLDER_ROLES = [
    ("regulators", re.compile(
        r"\b(?:regulators?|regulatory\s+(?:bodies|agencies|"
        r"authorities)|"
        r"the\s+(?:SEC|FDA|EPA|FCC|FTC|CFTC|NIST|FAA)|"
        r"government(?:al)?\s+(?:agencies|authorities|bodies))\b",
        re.IGNORECASE,
    )),
    ("policymakers", re.compile(
        r"\b(?:policymakers?|policy\s+makers?|legislators?|"
        r"lawmakers?|congress|parliament|senators?|"
        r"representatives|the\s+(?:administration|"
        r"government))\b",
        re.IGNORECASE,
    )),
    ("public", re.compile(
        r"\b(?:the\s+public|citizens?|voters?|the\s+electorate|"
        r"residents?|taxpayers?|the\s+populace)\b",
        re.IGNORECASE,
    )),
    ("investors", re.compile(
        r"\b(?:investors?|shareholders?|venture\s+capitalists?|"
        r"institutional\s+investors?|"
        r"limited\s+partners|VCs?|private\s+equity|funds?)\b",
        re.IGNORECASE,
    )),
    ("customers", re.compile(
        r"\b(?:customers?|clients?|end[- ]users?|consumers?|"
        r"buyers?|subscribers?|patrons?|users?)\b",
        re.IGNORECASE,
    )),
    ("employees", re.compile(
        r"\b(?:employees?|workers?|staff(?:ers)?|engineers?|"
        r"developers?|the\s+team|labor|the\s+workforce)\b",
        re.IGNORECASE,
    )),
    ("competitors", re.compile(
        r"\b(?:competitors?|rivals?|incumbents?|challengers?|"
        r"market\s+(?:leaders|entrants)|critics)\b",
        re.IGNORECASE,
    )),
    ("communities", re.compile(
        r"\b(?:communities|neighbors?|local\s+"
        r"(?:populations?|groups))\b",
        re.IGNORECASE,
    )),
    ("suppliers", re.compile(
        r"\b(?:suppliers?|vendors?|partners?|distributors?|"
        r"contractors?)\b",
        re.IGNORECASE,
    )),
    ("management", re.compile(
        r"\b(?:management|executives?|the\s+CEO|the\s+CFO|"
        r"the\s+(?:board|leadership)|founders?)\b",
        re.IGNORECASE,
    )),
    ("industry_actors", re.compile(
        r"\b(?:the\s+(?:fossil\s+fuel|tech|finance|healthcare|"
        r"pharmaceutical|automotive|energy)\s+industry|"
        r"the\s+sector|industry\s+(?:players|leaders|incumbents))\b",
        re.IGNORECASE,
    )),
    ("affected_populations", re.compile(
        r"\b(?:patients?|students?|workers\s+in|"
        r"affected\s+(?:populations?|groups|individuals)|"
        r"vulnerable\s+(?:populations?|groups))\b",
        re.IGNORECASE,
    )),
]


def detect_stakeholder_map(text: str) -> Optional[dict]:
    """Detect which stakeholder roles the document mentions.
    Returns None when text is too short.

    Output:
      {
        "roles_mentioned": sorted list of role labels detected,
        "role_count": int,
        "per_role_mention_count": {role: int},
        "total_stakeholder_mentions": int,
        "scope_reading": one-line prose naming which stakeholder
                         roles the document carries and which it
                         leaves out (relative to a per-genre
                         canonical set).
      }

    Substrate stays construct-honest: the regex matches surface
    forms; whether a stakeholder role is substantively analyzed
    versus mentioned is a reading the agent makes.
    """
    if _word_count(text) < _MIN_WORDS:
        return None

    per_role: dict[str, int] = {}
    for role_label, pattern in _STAKEHOLDER_ROLES:
        matches = pattern.findall(text)
        if matches:
            per_role[role_label] = len(matches)

    roles = sorted(per_role.keys())
    total = sum(per_role.values())

    if not roles:
        scope_reading = (
            "No stakeholder roles detected via the deterministic "
            "regex set (regulators, investors, customers, employees, "
            "competitors, communities, suppliers, management). The "
            "document may name specific entities the regex did not "
            "match; the reader can verify by inspection."
        )
    else:
        scope_reading = (
            f"Document carries {len(roles)} stakeholder role"
            f"{'s' if len(roles) != 1 else ''} ("
            f"{', '.join(roles)}) with "
            f"{total} mention{'s' if total != 1 else ''} total. "
            f"Stakeholder roles NOT mentioned: "
            f"{', '.join(r for r, _ in _STAKEHOLDER_ROLES if r not in per_role)}. "
            f"The reader can ask which absent stakeholders' "
            f"perspectives would change the framing."
        )

    return {
        "roles_mentioned": roles,
        "role_count": len(roles),
        "per_role_mention_count": dict(sorted(per_role.items())),
        "total_stakeholder_mentions": total,
        "scope_reading": scope_reading,
    }


# ── Item 10: Falsification condition detection (deepens FVS-007/009) ──

# Falsification patterns: explicit statements of conditions under
# which the document's claims would be wrong. Conservative regex;
# matches conditional structures that introduce disconfirming
# scenarios. Word boundaries to avoid false positives.
_FALSIFICATION_RE = re.compile(
    r"(?i)\b(?:"
    r"would\s+be\s+wrong\s+if|"
    r"would\s+fail\s+if|"
    r"fails?\s+(?:if|when)|"
    r"the\s+conclusion\s+depends\s+on|"
    r"this\s+(?:analysis|claim|prediction)\s+(?:assumes|requires|relies\s+on)|"
    r"unless\s+(?:we|you|one)\s+(?:assume|posit|grant)|"
    r"(?:if|when)\s+(?:that|this)\s+(?:assumption|premise)\s+"
    r"(?:fails|breaks|doesn't\s+hold)|"
    r"the\s+main\s+risk\s+is|"
    r"a\s+key\s+vulnerability|"
    r"break(?:s|ing)?\s+(?:case|scenario)|"
    r"if\s+(?:the\s+)?(?:earlier|later|alternative|opposite|"
    r"competing)\s+(?:timeline|scenario|estimate|view|"
    r"hypothesis|assumption)\s+(?:holds|proves|turns\s+out)|"
    r"if\s+(?:that|this)\s+(?:turns\s+out|proves)\s+to\s+be\s+"
    r"(?:wrong|false|incorrect|inaccurate)|"
    r"(?:becomes|proves)\s+(?:wrong|false|invalid)\s+if|"
    r"(?:fails|breaks)\s+to\s+account\s+for|"
    r"could\s+be\s+(?:wrong|invalidated|overturned)\s+(?:by|if)|"
    r"the\s+argument\s+(?:rests|hinges|turns)\s+on"
    r")\b"
)

# Conditional + uncertainty markers that often accompany
# falsification statements. Used as secondary-signal candidates
# when the primary regex did not fire but the document carries
# conditional language.
_CONDITIONAL_MARKER_RE = re.compile(
    r"(?i)\b(?:"
    r"if\s+\w+\s+\w+\s+(?:were|was|is\s+not|isn't),|"
    r"in\s+the\s+(?:event|case)\s+(?:that|of)|"
    r"under\s+(?:the\s+)?(?:assumption|conditions?)\s+that|"
    r"contingent\s+on|"
    r"depends?\s+on\s+whether"
    r")\b"
)

# Sentence splitter: simple period-bounded segmentation good
# enough to extract the surrounding context for a matched
# falsification phrase. We do not use spaCy or NLTK to keep
# dependencies bounded.
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def detect_falsification_conditions(text: str) -> Optional[dict]:
    """Detect explicit falsification statements (conditions under
    which the document's claims would be wrong) and conditional
    markers that may carry falsification framing.

    Returns None when text is too short.

    Output:
      {
        "primary_match_count": int (count of strong falsification
                                    pattern matches),
        "candidate_match_count": int (conditional-marker matches
                                      that may indicate
                                      falsification framing),
        "extracted_conditions": list of up to 5 sentence previews
                                 containing primary matches,
        "candidate_conditions": list of up to 3 sentence previews
                                 containing candidate-marker
                                 matches (clearly labeled),
        "scope_reading": one-line prose naming whether the document
                         carries explicit falsification structure
                         and what the reader can interrogate.
      }
    """
    if _word_count(text) < _MIN_WORDS:
        return None

    sentences = _SENTENCE_BOUNDARY_RE.split(text)

    primary_extractions: list[str] = []
    candidate_extractions: list[str] = []

    for sent in sentences:
        sent_stripped = sent.strip()
        if not sent_stripped:
            continue
        primary = _FALSIFICATION_RE.search(sent_stripped)
        candidate = _CONDITIONAL_MARKER_RE.search(sent_stripped)
        preview = sent_stripped[:200] + (
            "..." if len(sent_stripped) > 200 else ""
        )
        if primary:
            primary_extractions.append(preview)
        elif candidate:
            candidate_extractions.append(preview)

    primary_count = len(primary_extractions)
    candidate_count = len(candidate_extractions)

    if primary_count > 0:
        scope_reading = (
            f"Document carries {primary_count} explicit "
            f"falsification statement"
            f"{'s' if primary_count != 1 else ''} (e.g., 'would be "
            f"wrong if', 'fails when', 'the conclusion depends on'). "
            f"The reader can interrogate the named conditions: are "
            f"they precise enough to be tested? Do they cover the "
            f"load-bearing assumptions of the document's claims?"
        )
    elif candidate_count > 0:
        scope_reading = (
            f"No explicit falsification statements detected by "
            f"primary regex ('would be wrong if', 'fails when', "
            f"'depends on'); {candidate_count} candidate conditional "
            f"phrase{'s' if candidate_count != 1 else ''} detected "
            f"that may carry falsification framing (e.g., 'if X "
            f"were Y', 'under the assumption that'). The reader can "
            f"verify whether the conditional markers introduce true "
            f"falsification conditions or just hedge language."
        )
    else:
        scope_reading = (
            "No falsification statements or conditional markers "
            "detected. The document does not name conditions under "
            "which its claims would be wrong, nor introduce "
            "conditional structure that might carry falsification "
            "framing. The reader can compose the falsification "
            "questions themselves: what would have to change about "
            "the document's premises for its conclusion to fail?"
        )

    return {
        "primary_match_count": primary_count,
        "candidate_match_count": candidate_count,
        "extracted_conditions": primary_extractions[:5],
        "candidate_conditions": candidate_extractions[:3],
        "scope_reading": scope_reading,
    }
