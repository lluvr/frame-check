# Source Network Calibration Report

- **Corpus version:** 0.1
- **Corpus seeded:** 2026-04-16
- **Run started:** 2026-04-17T18:20:10.081105+00:00
- **Total claims:** 33
- **Stale ground-truth claims:** 0

## Per-provider results (all claims)

| Provider | N | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| alpha_vantage | 4 | 1 | 0 | 1 | 2 | 1.00 | 0.50 | 0.67 |
| fred | 5 | 1 | 0 | 2 | 2 | 1.00 | 0.33 | 0.50 |
| rest_countries | 5 | 3 | 1 | 0 | 1 | 0.75 | 1.00 | 0.86 |
| sec_edgar | 5 | 3 | 0 | 0 | 2 | 1.00 | 1.00 | 1.00 |
| wikipedia | 6 | 4 | 1 | 0 | 1 | 0.80 | 1.00 | 0.89 |
| wolfram_alpha | 4 | 1 | 1 | 1 | 1 | 0.50 | 0.50 | 0.50 |
| world_bank | 4 | 2 | 0 | 0 | 2 | 1.00 | 1.00 | 1.00 |

## Per-provider results (stale claims excluded)

Claims with `as_of_date` older than 90 days are excluded from the numbers below. Comparing these F1 values against the table above separates 'ground truth has drifted since the corpus was seeded' from 'the verifier genuinely misses'.

| Provider | N | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| alpha_vantage | 4 | 1 | 0 | 1 | 2 | 1.00 | 0.50 | 0.67 |
| fred | 5 | 1 | 0 | 2 | 2 | 1.00 | 0.33 | 0.50 |
| rest_countries | 5 | 3 | 1 | 0 | 1 | 0.75 | 1.00 | 0.86 |
| sec_edgar | 5 | 3 | 0 | 0 | 2 | 1.00 | 1.00 | 1.00 |
| wikipedia | 6 | 4 | 1 | 0 | 1 | 0.80 | 1.00 | 0.89 |
| wolfram_alpha | 4 | 1 | 1 | 1 | 1 | 0.50 | 0.50 | 0.50 |
| world_bank | 4 | 2 | 0 | 0 | 2 | 1.00 | 1.00 | 1.00 |

## Claim-level detail

| ID | Provider | Expected | Observed | Match | Best source |
|---|---|---|---|---|---|
| sec-001 | sec_edgar | verified | verified | yes | SEC Filing |
| sec-002 | sec_edgar | verified | verified | yes | SEC Filing |
| sec-003 | sec_edgar | contradicted | contradicted | yes |  |
| sec-004 | sec_edgar | unverifiable | unverifiable | yes |  |
| sec-005 | sec_edgar | verified | verified | yes | insideevs.com |
| fred-001 | fred | verified | disputed | no | World Bank |
| fred-002 | fred | verified | close | yes | Wikipedia |
| fred-003 | fred | contradicted | unverifiable | no |  |
| fred-004 | fred | unverifiable | disputed | no | World Bank |
| fred-005 | fred | verified | unverifiable | no |  |
| rc-001 | rest_countries | verified | verified | yes | Wikipedia |
| rc-002 | rest_countries | verified | verified | yes | Wolfram Alpha |
| rc-003 | rest_countries | contradicted | contradicted | yes |  |
| rc-004 | rest_countries | verified | verified | yes | World Bank |
| rc-005 | rest_countries | unverifiable | verified | no | www.reddit.com |
| wb-001 | world_bank | verified | verified | yes | World Bank |
| wb-002 | world_bank | close | close | yes | World Bank |
| wb-003 | world_bank | contradicted | contradicted | yes |  |
| wb-004 | world_bank | unverifiable | unverifiable | yes |  |
| av-001 | alpha_vantage | verified | unverifiable | no |  |
| av-002 | alpha_vantage | contradicted | unverifiable | no |  |
| av-003 | alpha_vantage | unverifiable | unverifiable | yes |  |
| av-004 | alpha_vantage | close | verified | yes | SEC Filing |
| wa-001 | wolfram_alpha | verified | verified | yes | Wolfram Alpha |
| wa-002 | wolfram_alpha | verified | unverifiable | no |  |
| wa-003 | wolfram_alpha | contradicted | unverifiable | no |  |
| wa-004 | wolfram_alpha | unverifiable | verified | no | www.reddit.com |
| wiki-001 | wikipedia | verified | verified | yes | Wolfram Alpha |
| wiki-002 | wikipedia | verified | verified | yes | Wikipedia |
| wiki-003 | wikipedia | verified | verified | yes | Wolfram Alpha |
| wiki-004 | wikipedia | contradicted | verified | no | Wikipedia |
| wiki-005 | wikipedia | contradicted | unverifiable | no |  |
| wiki-006 | wikipedia | verified | close | yes | Wikipedia |
