"""Unit tests for calibration/run_calibration.py.

The harness has two classes of logic:
  1. Pure bookkeeping: verdict matching, stale-date detection,
     confusion matrix computation. Unit-testable without network.
  2. Source Network invocation: requires network + API keys.
     Exercised via a separate live integration run, not covered here.

These tests lock in the bookkeeping contract so a future refactor
cannot silently change how precision/recall are computed without
a deliberate test update.
"""

import sys
import pathlib

import pytest

# Import the harness module from the calibration/ subdir.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "calibration"))
import run_calibration as rc


# ================================================================
# _verdict_matches: loose matching semantics
# ================================================================

class TestVerdictMatches:
    def test_exact_match_is_match(self):
        assert rc._verdict_matches("verified", "verified") is True
        assert rc._verdict_matches("contradicted", "contradicted") is True
        assert rc._verdict_matches("unverifiable", "unverifiable") is True

    def test_verified_close_are_mutual(self):
        # Tighter vs looser same-bucket verdicts count as matches.
        assert rc._verdict_matches("verified", "close") is True
        assert rc._verdict_matches("close", "verified") is True

    def test_contradicted_does_not_match_verified(self):
        assert rc._verdict_matches("verified", "contradicted") is False
        assert rc._verdict_matches("contradicted", "verified") is False

    def test_unverifiable_does_not_match_verified(self):
        assert rc._verdict_matches("verified", "unverifiable") is False

    def test_error_does_not_match(self):
        assert rc._verdict_matches("verified", "error") is False


# ================================================================
# _as_of_stale: ground-truth freshness gate
# ================================================================

class TestAsOfStale:
    def test_recent_date_not_stale(self):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        claim = {"as_of_date": today}
        assert rc._as_of_stale(claim, max_days=90) is False

    def test_old_date_is_stale(self):
        claim = {"as_of_date": "2020-01-01"}
        assert rc._as_of_stale(claim, max_days=90) is True

    def test_missing_date_is_stale(self):
        # A claim with no as_of_date cannot be grounded, so treat as stale.
        assert rc._as_of_stale({}) is True

    def test_malformed_date_is_stale(self):
        assert rc._as_of_stale({"as_of_date": "not-a-date"}) is True


# ================================================================
# _compute_confusion: TP/FP/FN/TN + precision/recall/F1
# ================================================================

def _row(provider, expected, observed):
    return {
        "id": "x", "provider_key": provider,
        "expected": expected, "observed": observed,
    }


class TestComputeConfusion:
    def test_all_true_positive(self):
        rows = [
            _row("sec_edgar", "verified", "verified"),
            _row("sec_edgar", "verified", "close"),
            _row("sec_edgar", "close", "verified"),
        ]
        c = rc._compute_confusion(rows)["sec_edgar"]
        assert c["TP"] == 3
        assert c["FP"] == 0
        assert c["FN"] == 0
        assert c["TN"] == 0
        assert c["precision"] == 1.0
        assert c["recall"] == 1.0
        assert c["f1"] == 1.0

    def test_false_positive(self):
        # Expected negative (contradicted), observed positive (verified).
        rows = [_row("fred", "contradicted", "verified")]
        c = rc._compute_confusion(rows)["fred"]
        assert c["FP"] == 1
        assert c["TP"] == 0
        # Precision is 0/1=0
        assert c["precision"] == 0.0
        # Recall undefined (no positives expected): TP=0, FN=0 → None
        assert c["recall"] is None

    def test_false_negative(self):
        # Expected positive (verified), observed negative (unverifiable).
        rows = [_row("fred", "verified", "unverifiable")]
        c = rc._compute_confusion(rows)["fred"]
        assert c["FN"] == 1
        assert c["TP"] == 0
        # Recall is 0/1=0; precision undefined (no positives observed)
        assert c["recall"] == 0.0
        assert c["precision"] is None

    def test_true_negative(self):
        # Expected unverifiable, observed unverifiable: correct negative.
        rows = [_row("rest_countries", "unverifiable", "unverifiable")]
        c = rc._compute_confusion(rows)["rest_countries"]
        assert c["TN"] == 1
        assert c["TP"] == 0
        assert c["FP"] == 0
        assert c["FN"] == 0

    def test_mixed_provider_f1(self):
        rows = [
            _row("sec_edgar", "verified", "verified"),       # TP
            _row("sec_edgar", "verified", "verified"),       # TP
            _row("sec_edgar", "contradicted", "contradicted"),  # TN
            _row("sec_edgar", "verified", "unverifiable"),  # FN
            _row("sec_edgar", "unverifiable", "verified"),  # FP
        ]
        c = rc._compute_confusion(rows)["sec_edgar"]
        assert c["TP"] == 2
        assert c["FP"] == 1
        assert c["FN"] == 1
        assert c["TN"] == 1
        # precision = 2/(2+1) = 0.667
        assert c["precision"] == pytest.approx(2 / 3)
        # recall = 2/(2+1) = 0.667
        assert c["recall"] == pytest.approx(2 / 3)
        # f1 = 2 * 0.667 * 0.667 / (0.667 + 0.667) = 0.667
        assert c["f1"] == pytest.approx(2 / 3)

    def test_per_provider_isolation(self):
        rows = [
            _row("sec_edgar", "verified", "verified"),
            _row("fred", "verified", "contradicted"),  # FN for fred
        ]
        c = rc._compute_confusion(rows)
        assert c["sec_edgar"]["TP"] == 1
        assert c["fred"]["FN"] == 1
        assert c["sec_edgar"]["FN"] == 0
        assert c["fred"]["TP"] == 0


# ================================================================
# _load_corpus: schema integrity
# ================================================================

class TestLoadCorpus:
    def test_seed_corpus_loads(self):
        repo_root = pathlib.Path(__file__).resolve().parent
        path = repo_root / "calibration" / "source_network_corpus.yaml"
        meta, claims = rc._load_corpus(str(path))
        assert meta.get("version") == "0.1"
        assert len(claims) >= 20, "seed corpus is sparse"

    def test_every_claim_has_required_fields(self):
        repo_root = pathlib.Path(__file__).resolve().parent
        path = repo_root / "calibration" / "source_network_corpus.yaml"
        _meta, claims = rc._load_corpus(str(path))
        required = {
            "id", "claim", "primary_source", "primary_source_url",
            "as_of_date", "primary_verifier", "category",
            "expected_verdict", "rationale",
        }
        for c in claims:
            missing = required - set(c.keys())
            assert not missing, f"Claim {c.get('id', '?')} missing: {missing}"

    def test_expected_verdicts_are_known(self):
        repo_root = pathlib.Path(__file__).resolve().parent
        path = repo_root / "calibration" / "source_network_corpus.yaml"
        _meta, claims = rc._load_corpus(str(path))
        allowed = {"verified", "close", "contradicted", "disputed", "unverifiable"}
        for c in claims:
            assert c["expected_verdict"] in allowed, (
                f"Claim {c['id']} has unknown expected_verdict "
                f"{c['expected_verdict']!r}"
            )

    def test_categories_are_known(self):
        repo_root = pathlib.Path(__file__).resolve().parent
        path = repo_root / "calibration" / "source_network_corpus.yaml"
        _meta, claims = rc._load_corpus(str(path))
        allowed = {
            "KNOWN_TRUE", "KNOWN_FALSE", "OUT_OF_COVERAGE",
            "SCALE_EDGE", "TEMPORAL_EDGE", "ROUTING_TEST",
        }
        for c in claims:
            assert c["category"] in allowed, (
                f"Claim {c['id']} has unknown category {c['category']!r}"
            )

    def test_provider_keys_are_consistent(self):
        repo_root = pathlib.Path(__file__).resolve().parent
        path = repo_root / "calibration" / "source_network_corpus.yaml"
        _meta, claims = rc._load_corpus(str(path))
        for c in claims:
            assert c["_provider_key"] == c["primary_verifier"], (
                f"Claim {c['id']}: provider block {c['_provider_key']!r} "
                f"!= primary_verifier {c['primary_verifier']!r}"
            )
