"""Unit tests for security.detect_pii_signals + pii_user_message.

The PII detector is the privacy-preserving core of the gap #8 intake
awareness feature. Wrong-positive false alarms erode trust as much
as missed leaks, so each category gets:

  1. A positive case the regex must match.
  2. A negative case structurally similar to the positive but not
     a real signal (catches over-matching).
  3. The substring-non-leak invariant: detect_pii_signals must
     return only ints, never any portion of the input.

Luhn validation on the credit-card path is the single piece of
non-trivial logic; it gets a positive (valid Luhn) and a negative
(invalid Luhn) case so a future regex-only refactor cannot silently
strip the integrity check.

The user-facing message is rendered by pii_user_message; tests pin
its format-correctness, ordering by severity (api_credential first),
and the empty-signals contract.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from security import detect_pii_signals, pii_user_message


# ── detect_pii_signals: empty / clean ─────────────────────────────

def test_empty_text_returns_empty_dict():
    assert detect_pii_signals("") == {}
    assert detect_pii_signals(None) == {}


def test_clean_analytical_text_returns_empty_dict():
    doc = (
        "The company reported revenue of 60.9 billion dollars in "
        "fiscal 2024, up 126% year-over-year. Data center revenue "
        "reached 47.5 billion. Growth is expected to continue."
    )
    assert detect_pii_signals(doc) == {}


# ── email category ────────────────────────────────────────────────

def test_email_simple():
    out = detect_pii_signals("Contact us at hello@example.com for details.")
    assert out == {"email": 1}


def test_email_with_subdomain_and_plus_addressing():
    out = detect_pii_signals(
        "Reach me at user.name+tag@mail.subdomain.example.co.uk."
    )
    assert "email" in out
    assert out["email"] == 1


def test_email_negative_at_sign_alone():
    """A bare @ in prose must not register as an email."""
    out = detect_pii_signals("Meet @ noon and review @ 3pm.")
    assert "email" not in out


# ── ssn category ──────────────────────────────────────────────────

def test_ssn_dashed_format():
    out = detect_pii_signals("Filing under SSN 123-45-6789.")
    assert "ssn" in out and out["ssn"] >= 1


def test_ssn_negative_plain_9_digit_run_without_context():
    """A bare 9-digit number with no `ssn` or `social security`
    context must not match. This is the false-positive guard:
    invoice numbers, IDs, and other 9-digit strings are common in
    analytical text and would generate a flood of warnings if the
    contextual gate were dropped."""
    out = detect_pii_signals("Tracking number 123456789 in transit.")
    assert "ssn" not in out


def test_ssn_negative_dashed_format_is_strict_3_2_4():
    """SSN dashed format is XXX-XX-XXXX (3-2-4). A 3-3-4 dash run
    (the US phone format) must not match the SSN pattern."""
    out = detect_pii_signals("Call 415-555-0100 for support.")
    assert "ssn" not in out


# ── credit card with Luhn ─────────────────────────────────────────

def test_credit_card_valid_luhn():
    """4242 4242 4242 4242 is the Stripe test card; Luhn passes."""
    out = detect_pii_signals("Card on file: 4242 4242 4242 4242.")
    assert out.get("credit_card") == 1


def test_credit_card_invalid_luhn_filtered():
    """4242 4242 4242 4241 has the same shape but fails Luhn; the
    regex would match but Luhn must reject it. Without this guard
    every 16-digit string in a doc would false-positive."""
    out = detect_pii_signals("Tracking number: 4242 4242 4242 4241.")
    assert "credit_card" not in out


def test_credit_card_random_16_digit_not_a_card():
    """Random 16-digit strings (order numbers, tracking IDs) will
    almost always fail Luhn; pin the negative explicitly."""
    out = detect_pii_signals("Order ID: 1234567890123456.")
    # 1234567890123456 fails Luhn (sum = 84, not divisible by 10)
    assert "credit_card" not in out


# ── phone category ────────────────────────────────────────────────

def test_phone_e164():
    out = detect_pii_signals("My number is +1-415-555-0100.")
    assert "phone" in out and out["phone"] >= 1


# ── api_credential category ───────────────────────────────────────

def test_api_credential_openai_style():
    out = detect_pii_signals(
        "API key: sk-proj-1234567890abcdefghij1234567890abcdefghij."
    )
    assert "api_credential" in out and out["api_credential"] >= 1


def test_api_credential_github_token():
    out = detect_pii_signals(
        "Token: ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789."
    )
    assert "api_credential" in out


def test_api_credential_aws_access_key():
    out = detect_pii_signals("Provisioned: AKIAIOSFODNN7EXAMPLE.")
    assert "api_credential" in out


def test_api_credential_negative_short_prefix_alone():
    """Just the prefix `sk-` without a long token must not trigger."""
    out = detect_pii_signals("Use sk- as the prefix when minting keys.")
    assert "api_credential" not in out


# ── multi-category ────────────────────────────────────────────────

def test_multi_category_all_categories_named():
    """A document with several categories names every one in the
    output dict so consumers can branch per-category."""
    doc = (
        "Email me at investor@example.com, phone +1-415-555-0100, "
        "card 4242424242424242, key sk-proj-1234567890abcdefghij1234567890."
    )
    out = detect_pii_signals(doc)
    assert "email" in out
    assert "phone" in out
    assert "credit_card" in out
    assert "api_credential" in out


# ── substring non-leak ────────────────────────────────────────────

def test_detect_returns_ints_only_no_substring_leak():
    """The privacy-preserving design depends on detect_pii_signals
    returning only category counts. If a future refactor accidentally
    threads matched substrings through the dict, this test fires.
    """
    doc = (
        "Email investor.relations@example.com about card 4242424242424242 "
        "and key sk-proj-1234567890abcdefghij1234567890."
    )
    out = detect_pii_signals(doc)
    # All values must be ints.
    for k, v in out.items():
        assert isinstance(v, int), (
            f"Category {k!r} has non-int value {v!r}; substring leak risk"
        )
    # Reconstruct the dict as JSON and confirm none of the original
    # input substrings appear. Defense in depth against the same
    # invariant.
    import json
    rendered = json.dumps(out)
    for needle in (
        "investor.relations", "example.com",
        "4242", "sk-proj", "1234567890",
    ):
        assert needle not in rendered, (
            f"Substring {needle!r} leaked into JSON-serialized dict {rendered!r}"
        )


# ── pii_user_message rendering ────────────────────────────────────

def test_message_empty_signals_returns_empty_string():
    assert pii_user_message({}) == ""
    assert pii_user_message(None) == ""


def test_message_single_category_singular_phrasing():
    msg = pii_user_message({"email": 1})
    assert "an email address" in msg
    assert "Frame Check does not store" in msg


def test_message_two_categories_uses_and():
    msg = pii_user_message({"email": 1, "phone": 1})
    # Format: "...like X and Y."
    assert " and " in msg
    assert "an email address" in msg
    assert "a phone number" in msg


def test_message_three_or_more_categories_oxford_comma():
    msg = pii_user_message({
        "email": 1, "phone": 1, "api_credential": 1,
    })
    # Format: "X, Y, and Z" — Oxford comma
    assert ", and " in msg


def test_message_orders_credential_first():
    """API credential is the most actionable category (rotate now);
    listing it first respects the user's likely priority."""
    msg = pii_user_message({"email": 1, "api_credential": 1})
    cred_pos = msg.find("API key or credential")
    email_pos = msg.find("email")
    assert cred_pos != -1 and email_pos != -1
    assert cred_pos < email_pos, (
        "API credential should appear before email in user message"
    )


def test_message_links_to_privacy_posture_via_template():
    """The full intake-notice path on results.html appends a
    'Privacy posture' link separately. The bare message does NOT
    embed an HTML link (separation of concerns; the security module
    must not depend on template HTML). The message DOES name
    Frame Check and the storage-posture commitment so the user
    sees the same statement whether or not the link renders."""
    msg = pii_user_message({"email": 1})
    assert "Frame Check" in msg
    assert "does not store" in msg
    assert "<a " not in msg  # no embedded HTML
    assert "href" not in msg


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
