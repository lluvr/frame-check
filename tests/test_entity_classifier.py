"""Tests for entity_classifier.classify_subject.

These tests lock in the priority order that makes Bug 2
(calibration FINDINGS.md B.3) impossible by construction: a
subject like "United States" classifies as COUNTRY even though
`_find_cik` would substring-match it against the SEC ticker table.

Priority tests are first-class. If a future refactor reorders
the rules, these tests fail loudly rather than silently
regressing the calibration-surfaced bug.
"""

import pytest

from entity_classifier import (
    EntityType, Classification, classify_subject,
)


# ================================================================
# Country classification
# ================================================================

class TestCountryClassification:

    def test_canonical_country_name(self):
        r = classify_subject("United States")
        assert r.entity_type == EntityType.COUNTRY
        assert r.canonical == "United States"
        assert r.reason == "country_alias_match"

    def test_lowercase_country(self):
        r = classify_subject("france")
        assert r.entity_type == EntityType.COUNTRY
        assert r.canonical == "France"

    def test_iso_code_uppercase(self):
        r = classify_subject("US")
        assert r.entity_type == EntityType.COUNTRY

    def test_iso_code_lowercase_is_unknown(self):
        # Lowercase "us" is the English pronoun, not the country
        # abbreviation. _COUNTRY_ABBREV_RE is case-sensitive
        # deliberately (source_network.py comment at the regex
        # definition). This test locks in the disambiguation so a
        # future refactor cannot silently flip "us" into COUNTRY.
        r = classify_subject("us")
        assert r.entity_type == EntityType.UNKNOWN

    def test_trailing_punctuation_stripped(self):
        r = classify_subject("Germany.")
        assert r.entity_type == EntityType.COUNTRY
        assert r.canonical == "Germany"


class TestAmbiguousCountrySubjects:
    """Multi-word, hyphenated, and apostrophe-bearing country names
    that the fullmatch regex needs to handle. These cases are a
    post-classifier-landing audit: the initial implementation used
    _COUNTRY_NAMES_RE.fullmatch which rejected prefix-qualified
    country names (North/South Korea), compound Latin names
    (Cote d'Ivoire), and "Republic"-suffixed forms (Dominican
    Republic). The fix extended both the regex and the canonical
    map; these tests lock in the result so future refactors cannot
    silently demote these claims back to UNKNOWN."""

    def test_north_korea(self):
        r = classify_subject("North Korea")
        assert r.entity_type == EntityType.COUNTRY
        assert r.canonical == "North Korea"

    def test_south_korea(self):
        r = classify_subject("South Korea")
        assert r.entity_type == EntityType.COUNTRY
        assert r.canonical == "South Korea"

    def test_bare_korea_still_classifies(self):
        # Bare "Korea" is ambiguous; the classifier keeps it as
        # COUNTRY with canonical "Korea" so the verifier layer can
        # make the DPRK-vs-ROK decision rather than the classifier.
        r = classify_subject("Korea")
        assert r.entity_type == EntityType.COUNTRY

    def test_cote_divoire_ascii_form(self):
        r = classify_subject("Cote d'Ivoire")
        assert r.entity_type == EntityType.COUNTRY
        assert r.canonical == "Cote d'Ivoire"

    def test_ivory_coast_maps_to_canonical(self):
        r = classify_subject("Ivory Coast")
        assert r.entity_type == EntityType.COUNTRY
        assert r.canonical == "Cote d'Ivoire"

    def test_dominican_republic(self):
        r = classify_subject("Dominican Republic")
        assert r.entity_type == EntityType.COUNTRY
        assert r.canonical == "Dominican Republic"

    def test_guinea_bissau_hyphenated(self):
        r = classify_subject("Guinea-Bissau")
        assert r.entity_type == EntityType.COUNTRY

    def test_united_arab_emirates(self):
        # Three-word country name: sanity check that multi-word
        # fullmatch works in general, not just for Korea variants.
        r = classify_subject("United Arab Emirates")
        assert r.entity_type == EntityType.COUNTRY


# ================================================================
# Crypto classification
# ================================================================

class TestCryptoClassification:

    def test_full_name(self):
        r = classify_subject("bitcoin")
        assert r.entity_type == EntityType.CRYPTO_ASSET
        assert r.reason == "crypto_name_match"

    def test_uppercase_ticker(self):
        r = classify_subject("BTC")
        assert r.entity_type == EntityType.CRYPTO_ASSET

    def test_mixed_case_name(self):
        r = classify_subject("Ethereum")
        assert r.entity_type == EntityType.CRYPTO_ASSET


# ================================================================
# Company classification (depends on SEC ticker cache; may be
# cold-started in isolated test runs; the rule falls through
# gracefully in that case so we test only the known-ticker path
# here and trust the integration tests to exercise the warm path)
# ================================================================

class TestCompanyClassification:
    """The SEC ticker lookup may fail in offline test environments
    where the ticker cache has never been populated. These tests
    verify the RULE ORDER; that a COMPANY-like subject does not
    match the earlier country/crypto rules; and that the fallback
    to UNKNOWN is clean when the resolver is unavailable."""

    def test_unambiguous_non_country_non_crypto_not_classified_as_other(self):
        r = classify_subject("NVIDIA Corporation")
        # Either COMPANY (resolver warm and matched) or UNKNOWN
        # (resolver cold/offline). Must NOT be COUNTRY or CRYPTO.
        assert r.entity_type in (EntityType.COMPANY, EntityType.UNKNOWN)

    def test_ticker_like_string_not_a_country(self):
        r = classify_subject("NVDA")
        # NVDA is not in any country alias table.
        assert r.entity_type != EntityType.COUNTRY

    def test_resolver_failure_falls_through_cleanly(self, monkeypatch):
        # Force _find_cik to raise; classifier must not propagate.
        import entity_classifier

        def _boom(subject):
            raise RuntimeError("network down")

        import source_network
        monkeypatch.setattr(source_network, "_find_cik", _boom)
        r = classify_subject("SomeRandomCompanyName Inc")
        assert r.entity_type == EntityType.UNKNOWN
        assert r.reason == "no_rule_matched"


# ================================================================
# Priority order; THE regression guard
# ================================================================
# The bug this classifier fixes is: "United States" was classified
# as a company because the SEC ticker substring match caught it.
# The priority order (crypto, country, company, else) prevents
# that permanently. These tests are the load-bearing check.

class TestPriorityOrder:

    def test_country_beats_company_substring_match(self):
        """"United States" must classify as COUNTRY, not COMPANY,
        even though the SEC ticker table contains entries whose
        names contain 'US' and _find_cik would substring-match."""
        r = classify_subject("United States")
        assert r.entity_type == EntityType.COUNTRY
        assert r.reason == "country_alias_match"

    def test_us_abbreviation_is_country(self):
        r = classify_subject("US")
        assert r.entity_type == EntityType.COUNTRY

    def test_bitcoin_is_crypto_not_unknown(self):
        r = classify_subject("bitcoin")
        assert r.entity_type == EntityType.CRYPTO_ASSET

    def test_empty_subject_is_unknown(self):
        r = classify_subject("")
        assert r.entity_type == EntityType.UNKNOWN
        assert r.reason == "empty_subject"

    def test_none_subject_is_unknown(self):
        r = classify_subject(None)
        assert r.entity_type == EntityType.UNKNOWN
        assert r.reason == "empty_subject"

    def test_whitespace_only_is_unknown(self):
        r = classify_subject("   ")
        assert r.entity_type == EntityType.UNKNOWN
        assert r.reason == "empty_subject"

    def test_garbage_is_unknown(self):
        r = classify_subject("asdjkhasd13987")
        assert r.entity_type == EntityType.UNKNOWN
        assert r.reason == "no_rule_matched"


# ================================================================
# Contract stability; corpus consumers depend on this
# ================================================================

class TestContractStability:
    """The enum values and reason strings are shipped in corpus
    events and UI displays. A rename would invalidate historical
    data. These tests keep the contract visible in the codebase."""

    def test_entity_type_values_are_stable(self):
        assert EntityType.COMPANY.value == "company"
        assert EntityType.COUNTRY.value == "country"
        assert EntityType.CRYPTO_ASSET.value == "crypto_asset"
        assert EntityType.UNKNOWN.value == "unknown"

    def test_reason_slugs_are_stable(self):
        # The reason slugs are promised in the module docstring.
        # Exhaustive check: every classify_subject call returns
        # exactly one of this set.
        allowed = {
            "crypto_name_match",
            "country_alias_match",
            "sec_cik_resolved",
            "empty_subject",
            "no_rule_matched",
        }
        for subject in [
            "", None, "   ", "bitcoin", "BTC", "Germany", "US",
            "asdjkhasd", "NVIDIA",
        ]:
            r = classify_subject(subject)
            assert r.reason in allowed, (
                f"classify_subject({subject!r}) produced unknown "
                f"reason {r.reason!r}; contract broken"
            )

    def test_classification_is_a_namedtuple(self):
        r = classify_subject("France")
        # NamedTuple behaviour: unpackable, indexable, named access.
        etype, canon, reason = r
        assert etype == r[0] == r.entity_type
        assert canon == r[1] == r.canonical
        assert reason == r[2] == r.reason
