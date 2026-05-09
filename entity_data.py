"""Shared lookup tables for entity classification.

This module holds the small set of constants that both the source-
network verification layer and the entity classifier read at every
call. Hosting them here (rather than in either consumer) breaks what
would otherwise be a bidirectional import cycle between
``source_network.py`` (which uses these tables for country and
crypto detection in claim sentences) and ``entity_classifier.py``
(which uses them to canonicalize subject strings).

The four exports are:

- ``_COUNTRY_NAMES_RE``: alternation regex matching country full
  names and demonyms in English. Case-insensitive. The alternation
  order is curated so multi-word and disambiguating forms (``North
  Korea``, ``Dominican Republic``) match before the bare prefix
  forms (``Korea``, ``Dominican``).
- ``_COUNTRY_ABBREV_RE``: case-sensitive regex for ISO-style
  abbreviations. Case-sensitivity prevents ``us`` (pronoun) and
  ``eu`` (substring of ``neurological``) from spuriously matching.
- ``_COUNTRY_CANONICAL``: maps abbreviations and demonyms to the
  canonical country name that REST Countries and World Bank APIs
  expect.
- ``_CRYPTO_NAMES``: maps full names and tickers to the canonical
  CoinGecko id used by the verification layer.
"""

import re


# ── Country detection ─────────────────────────────────────────────

_COUNTRY_NAMES_RE = re.compile(
    r'\b(Afghanistan|Albania|Algeria|Andorra|Angola|Antigua and Barbuda|'
    r'Argentina|Armenia|Australia|Austria|Azerbaijan|'
    r'Bahamas|Bahrain|Bangladesh|Barbados|Belarus|Belgium|Belize|Benin|'
    r'Bhutan|Bolivia|Bosnia|Botswana|Brazil|Brunei|Bulgaria|'
    r'Burkina Faso|Burundi|'
    r'Cambodia|Cameroon|Canada|Cape Verde|Central African Republic|'
    r'Chad|Chile|China|Colombia|Comoros|Congo|Costa Rica|Croatia|Cuba|'
    r'Cyprus|Czechia|Czech Republic|Czech|'
    r'Denmark|Djibouti|Dominica|Dominican Republic|Dominican|'
    r'Ecuador|Egypt|El Salvador|Equatorial Guinea|Eritrea|Estonia|'
    r'Eswatini|Swaziland|Ethiopia|'
    r'Fiji|Finland|France|'
    r'Gabon|Gambia|Georgia|Germany|Ghana|Greece|Greenland|Grenada|'
    r'Guatemala|Guinea-Bissau|Guinea|Guyana|'
    r'Haiti|Honduras|Hong Kong|Hungary|'
    r'Iceland|India|Indonesia|Iran|Iraq|Ireland|Israel|'
    # Cote d'Ivoire: accepted in plain ASCII form matching the canonical
    # key stored in _COUNTRY_CANONICAL; the accented Côte d'Ivoire is
    # out of scope for this pass (would need Unicode normalisation).
    r"Italy|Ivory Coast|Cote d'Ivoire|"
    r'Jamaica|Japan|Jordan|'
    # Korea variants: North and South must come BEFORE bare "Korea" in
    # the alternation so search-based callers prefer the more specific
    # form when both appear. fullmatch callers (entity classifier) get
    # the right answer either way.
    r'Kazakhstan|Kenya|Kiribati|North Korea|South Korea|Korea|Kosovo|Kuwait|Kyrgyzstan|'
    r'Laos|Latvia|Lebanon|Lesotho|Liberia|Libya|Liechtenstein|'
    r'Lithuania|Luxembourg|'
    r'Macau|Madagascar|Malawi|Malaysia|Maldives|Mali|Malta|'
    r'Marshall Islands|Mauritania|Mauritius|Mexico|Micronesia|Moldova|'
    r'Monaco|Mongolia|Montenegro|Morocco|Mozambique|Myanmar|'
    r'Namibia|Nauru|Nepal|Netherlands|New Zealand|Nicaragua|Niger|'
    r'Nigeria|North Macedonia|Norway|'
    r'Oman|'
    r'Pakistan|Palau|Palestine|Panama|Papua New Guinea|Paraguay|Peru|'
    r'Philippines|Poland|Portugal|Puerto Rico|'
    r'Qatar|'
    r'Romania|Russia|Rwanda|'
    r'Saint Kitts and Nevis|Saint Lucia|Saint Vincent|Samoa|'
    r'San Marino|Saudi Arabia|Senegal|Serbia|Seychelles|Sierra Leone|'
    r'Singapore|Slovakia|Slovenia|Solomon Islands|Somalia|South Africa|'
    r'South Sudan|Spain|Sri Lanka|Sudan|Suriname|Sweden|Switzerland|'
    r'Syria|'
    r'Taiwan|Tajikistan|Tanzania|Thailand|Timor-Leste|East Timor|Togo|'
    r'Tonga|Trinidad and Tobago|Tunisia|Turkey|Turkmenistan|Tuvalu|'
    r'Uganda|Ukraine|United Arab Emirates|United Kingdom|United States|'
    r'Uruguay|Uzbekistan|'
    r'Vanuatu|Vatican City|Venezuela|Vietnam|'
    r'Western Sahara|Yemen|Zambia|Zimbabwe'
    # Demonyms that map unambiguously to a country
    r'|American|British|Chinese|French|German|Indian|Japanese|'
    r'Brazilian|Russian|Mexican|Canadian|Australian|Italian|Spanish|'
    r'Korean|Turkish|Indonesian|Saudi|Egyptian|Nigerian|South African|'
    r'Pakistani|Bangladeshi|Thai|Vietnamese|Colombian|Argentine|'
    r'Chilean|Peruvian|Venezuelan|Malaysian|Philippine|Singaporean|'
    r'Swedish|Norwegian|Danish|Finnish|Dutch|Swiss|Belgian|Austrian|'
    r'Polish|Czech|Hungarian|Romanian|Greek|Portuguese|Irish)\b',
    re.IGNORECASE
)

# Abbreviations checked separately (case-sensitive to avoid matching
# "us" as a pronoun, "eu" in "neurological", etc.)
_COUNTRY_ABBREV_RE = re.compile(r'\b(U\.?S\.?A?\.?|U\.?K\.?|EU)\b')


# Map abbreviations and demonyms to the canonical name that
# REST Countries and World Bank APIs expect.
_COUNTRY_CANONICAL = {
    "US": "United States", "U.S.": "United States", "U.S.A.": "United States",
    "USA": "United States", "U.S.A": "United States",
    "UK": "United Kingdom", "U.K.": "United Kingdom",
    "EU": "European Union",
    "American": "United States", "British": "United Kingdom",
    "Chinese": "China", "French": "France", "German": "Germany",
    "Indian": "India", "Japanese": "Japan", "Brazilian": "Brazil",
    "Russian": "Russia", "Mexican": "Mexico", "Canadian": "Canada",
    "Australian": "Australia", "Italian": "Italy", "Spanish": "Spain",
    "Korean": "Korea", "Turkish": "Turkey", "Indonesian": "Indonesia",
    "Saudi": "Saudi Arabia", "Egyptian": "Egypt", "Nigerian": "Nigeria",
    "South African": "South Africa", "Pakistani": "Pakistan",
    "Bangladeshi": "Bangladesh", "Thai": "Thailand",
    "Vietnamese": "Vietnam", "Colombian": "Colombia",
    "Argentine": "Argentina", "Chilean": "Chile", "Peruvian": "Peru",
    "Venezuelan": "Venezuela", "Malaysian": "Malaysia",
    "Philippine": "Philippines", "Singaporean": "Singapore",
    "Swedish": "Sweden", "Norwegian": "Norway", "Danish": "Denmark",
    "Finnish": "Finland", "Dutch": "Netherlands", "Swiss": "Switzerland",
    "Belgian": "Belgium", "Austrian": "Austria", "Polish": "Poland",
    "Czech": "Czechia", "Hungarian": "Hungary", "Romanian": "Romania",
    "Greek": "Greece", "Portuguese": "Portugal", "Irish": "Ireland",
    # Alternative country names to canonical REST Countries / World Bank names
    "Czech Republic": "Czechia", "Swaziland": "Eswatini",
    "East Timor": "Timor-Leste", "Ivory Coast": "Cote d'Ivoire",
    "Cape Verde": "Cabo Verde",
    "Guinea-Bissau": "Guinea-Bissau",  # prevent "Guinea" substring match
    # Korea disambiguation. REST Countries and World Bank index these
    # separately; an unqualified "Korea" alone is ambiguous and should
    # stay as "Korea" so the verifier layer can decide how to resolve
    # it, but the explicit "North Korea" / "South Korea" forms must
    # pass through without collapsing.
    "North Korea": "North Korea",
    "South Korea": "South Korea",
    # Dominican Republic: the bare "Dominican" demonym already maps
    # to "Dominican Republic" (above in the demonym section; see
    # the entry below); the explicit country name must be present
    # here so fullmatch-based callers resolve it.
    "Dominican Republic": "Dominican Republic",
    # Cote d'Ivoire in its canonical form is self-mapping so callers
    # that pass the plain-ASCII country name straight through get
    # the same result as going via "Ivory Coast".
    "Cote d'Ivoire": "Cote d'Ivoire",
}


# ── Crypto detection ──────────────────────────────────────────────

_CRYPTO_NAMES = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana",
    "cardano": "cardano", "ada": "cardano",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "ripple": "ripple", "xrp": "ripple",
    "polkadot": "polkadot", "dot": "polkadot",
    "avalanche": "avalanche-2", "avax": "avalanche-2",
    "litecoin": "litecoin", "ltc": "litecoin",
    "chainlink": "chainlink", "link": "chainlink",
}


__all__ = [
    "_COUNTRY_NAMES_RE",
    "_COUNTRY_ABBREV_RE",
    "_COUNTRY_CANONICAL",
    "_CRYPTO_NAMES",
]
