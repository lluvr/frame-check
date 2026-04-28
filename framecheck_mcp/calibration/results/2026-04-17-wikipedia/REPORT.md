# Source Network Calibration Report

- **Corpus version:** 0.1
- **Corpus seeded:** 2026-04-16
- **Run started:** 2026-04-17T18:18:17.401056+00:00
- **Total claims:** 6
- **Stale ground-truth claims:** 0

## Per-provider results (all claims)

| Provider | N | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| wikipedia | 6 | 4 | 1 | 0 | 1 | 0.80 | 1.00 | 0.89 |

## Per-provider results (stale claims excluded)

Claims with `as_of_date` older than 90 days are excluded from the numbers below. Comparing these F1 values against the table above separates 'ground truth has drifted since the corpus was seeded' from 'the verifier genuinely misses'.

| Provider | N | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| wikipedia | 6 | 4 | 1 | 0 | 1 | 0.80 | 1.00 | 0.89 |

## Claim-level detail

| ID | Provider | Expected | Observed | Match | Best source |
|---|---|---|---|---|---|
| wiki-001 | wikipedia | verified | verified | yes | Wolfram Alpha |
| wiki-002 | wikipedia | verified | verified | yes | Wikipedia |
| wiki-003 | wikipedia | verified | verified | yes | Wolfram Alpha |
| wiki-004 | wikipedia | contradicted | verified | no | Wikipedia |
| wiki-005 | wikipedia | contradicted | unverifiable | no |  |
| wiki-006 | wikipedia | verified | close | yes | Wikipedia |
