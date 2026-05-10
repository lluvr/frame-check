"""Classify a claim subject into one of the entity types the
verification pipeline knows how to handle.

Before this module existed, source_network.py routed claims by
running regexes over the subject string and sentence text, then
inferring 'probably a company' from capitalization plus a financial
keyword. The 2026-04-16 first calibration run surfaced the failure
mode this produces: the claim "US national debt exceeded $34 trillion"
was routed to SEC EDGAR because the subject "United States" matched
the `\\b[A-Z][A-Za-z]+\\b` capitalization gate and the sentence
contained a financial keyword. SEC returned a tiny $243M from an
unrelated filing, the consensus went to `disputed`, and the user
saw what looked like a real contradiction. See
`calibration/results/2026-04-16-first-run/FINDINGS.md` category B.3.

The structural answer is a first-class subject classifier. This
module is it. Every place in the router that previously consulted
a heuristic over the subject string now asks this module once,
and the returned `EntityType` drives the routing decision. New
verifiers added to Framecheck will register against a type, not
against a regex.

## Design commitments

* **Specific before generic.** Rule priority runs from tightest
  (known crypto name) to broadest (fallback UNKNOWN). A subject
  that matches multiple rules takes the first; ties do not exist
  by construction.

* **Explainable.** Every `Classification` carries the rule that
  fired. A researcher querying the corpus can filter on
  `classification_reason` to audit decisions.

* **Honest about UNKNOWN.** A subject that does not match any
  known entity type gets UNKNOWN. The router then falls back to
  Wikipedia plus the Brave fallback, the same broad-coverage
  path that unknown subjects took historically. UNKNOWN is a
  first-class value, not "probably a company."

* **Fast.** All rules are pure local lookups against the existing
  data tables in `source_network.py`. No network. No regex
  backtracking. Safe to call inside a hot path.
"""

from enum import Enum
from typing import NamedTuple, Optional

from entity_data import (
    _CRYPTO_NAMES,
    _COUNTRY_CANONICAL,
    _COUNTRY_NAMES_RE,
    _COUNTRY_ABBREV_RE,
)


class EntityType(str, Enum):
    """What kind of subject a claim is about.

    The enum values are stable; external consumers (corpus
    queries, UI badges) rely on these strings. Do not rename
    without a schema bump.
    """

    COMPANY = "company"
    COUNTRY = "country"
    CRYPTO_ASSET = "crypto_asset"
    UNKNOWN = "unknown"


class Classification(NamedTuple):
    """The result of classifying a subject.

    entity_type: which bucket the subject landed in.
    canonical: the normalised form of the subject; the name the
        downstream verifier should use. For COMPANY this is the
        ticker when resolvable, for COUNTRY the canonical English
        country name, for CRYPTO_ASSET the lowercase coin id as
        used by CoinGecko, for UNKNOWN it is the original subject
        string unchanged.
    reason: the rule that matched. Values are stable short slugs
        suitable for telemetry tagging:
        'crypto_name_match', 'country_alias_match',
        'sec_cik_resolved', 'empty_subject', 'no_rule_matched'.
    """

    entity_type: EntityType
    canonical: str
    reason: str


# ================================================================
# Classification
# ================================================================

def classify_subject(subject: Optional[str]) -> Classification:
    """Classify a claim subject into an EntityType.

    Priority order, most specific first:

      1. Known cryptocurrency name or ticker -> CRYPTO_ASSET.
         Tight set (`_CRYPTO_NAMES` in source_network); a hit
         here is unambiguous.
      2. Known country name, alias, or ISO code -> COUNTRY.
         Tight set (`_COUNTRY_CANONICAL` in source_network);
         matches include both the raw input and its title-cased
         form so "united states" and "United States" both land.
      3. SEC-resolvable company identifier -> COMPANY. The
         resolver (`_find_cik`) tries exact ticker, then exact
         title, then suffix-stripped title, then substring match.
         Only a positive resolution counts; an unresolvable
         string is NOT classified as a company.
      4. Everything else -> UNKNOWN.

    The COMPANY check is last by design. Running it before the
    country and crypto checks risks false positives: the SEC
    ticker table contains entries like "US PHYSICAL THERAPY INC"
    and the substring gate in `_find_cik` would match "US" as a
    plausible company when the subject is actually a country.
    Ordering eliminates the collision class entirely.
    """
    if subject is None or not subject.strip():
        return Classification(EntityType.UNKNOWN, "", "empty_subject")

    raw = subject.strip()

    crypto_canonical = _match_crypto(raw)
    if crypto_canonical is not None:
        return Classification(
            EntityType.CRYPTO_ASSET, crypto_canonical, "crypto_name_match"
        )

    country_canonical = _match_country(raw)
    if country_canonical is not None:
        return Classification(
            EntityType.COUNTRY, country_canonical, "country_alias_match"
        )

    company_canonical = _match_company(raw)
    if company_canonical is not None:
        return Classification(
            EntityType.COMPANY, company_canonical, "sec_cik_resolved"
        )

    return Classification(EntityType.UNKNOWN, raw, "no_rule_matched")


# ================================================================
# Rule implementations
# ================================================================
#
# Each rule is isolated so the priority order in classify_subject
# is the ONLY place ordering is expressed. The rules themselves
# make no claim about relative priority; they simply report
# whether this specific subject matches their type and return the
# canonical form if it does.
#
# All rules import from source_network at call time rather than at
# module load time. This avoids a circular dependency: source_network
# imports from this module at call-time (in _classify_and_route) and
# this module imports from source_network at call time (here).

def _match_crypto(raw: str) -> Optional[str]:
    """Return the canonical CoinGecko id for a crypto subject, or None.

    The `_CRYPTO_NAMES` table maps both full names ("bitcoin") and
    tickers ("btc") to the canonical CoinGecko id. Keys in that
    table are already lowercase, so we lowercase the input.
    Trailing punctuation from sloppy sentence extraction ("BTC,")
    is stripped before lookup.
    """
    key = raw.lower().rstrip(".,;:!?\"')")
    return _CRYPTO_NAMES.get(key)


def _match_country(raw: str) -> Optional[str]:
    """Return the canonical country name, or None.

    Uses the same two tables source_network uses for country
    detection in free text: `_COUNTRY_ABBREV_RE` for the
    case-sensitive ISO-style abbreviations ("US", "U.S.", "UK",
    "EU") and `_COUNTRY_NAMES_RE` for the full-name and demonym
    alternation ("United States", "France", "American",
    "German", etc.) under case-insensitive matching. Both
    regexes are compiled once at module load in source_network.

    We use `fullmatch` rather than `search` because a subject
    classifier is about what the WHOLE subject is, not whether a
    country name appears somewhere inside it. "United States
    Steel" must not classify as COUNTRY just because "United
    States" is a substring; the company-name resolver gets a
    chance at that subject in the next priority rule.

    The canonical form returned is the dict value for known
    aliases (demonyms and abbreviations), otherwise the
    title-cased form of the matched text so lowercase inputs
    like "france" normalize to "France".
    """
    key = raw.rstrip(".,;:!?\"')")
    if not key:
        return None

    # Abbreviations are case-sensitive by design so "us" as a
    # pronoun does not trigger classification as the United
    # States. Only actual ISO-style forms (US, U.S., UK, EU) hit.
    abbrev = _COUNTRY_ABBREV_RE.fullmatch(key)
    if abbrev:
        matched = abbrev.group()
        return _COUNTRY_CANONICAL.get(matched, matched)

    # Full names and demonyms (case-insensitive). When the match
    # lands on a demonym ("French") the canonical map translates
    # to the country name ("France"); when it lands on an
    # already-canonical name ("France") the map lookup misses
    # and we fall through to the title-cased form.
    name = _COUNTRY_NAMES_RE.fullmatch(key)
    if name:
        matched = name.group()
        return _COUNTRY_CANONICAL.get(
            matched,
            _COUNTRY_CANONICAL.get(matched.title(), matched.title()),
        )

    return None


def _match_company(raw: str) -> Optional[str]:
    """Return the SEC ticker for a resolvable company, or None.

    Uses `_find_cik` from source_network which performs exact
    ticker match, then exact title match, then suffix-stripped
    title match, then substring match. A None return means the
    subject is NOT resolvable as a company; we do NOT fall back
    to any other signal. Callers that want the classification
    to be something other than COMPANY when _find_cik misses
    rely on that contract.

    The ticker is returned rather than the title so the canonical
    form is short and stable across corpus queries.
    """
    from source_network import _find_cik

    try:
        cik, ticker = _find_cik(raw)
    except Exception:
        # _find_cik may fetch the SEC ticker cache on cold start
        # and that can fail in offline test runs. Treat any
        # failure as "cannot resolve" rather than blowing up the
        # entire routing pass.
        return None
    if cik:
        return ticker or raw
    return None
