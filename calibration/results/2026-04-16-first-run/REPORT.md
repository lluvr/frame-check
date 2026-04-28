# Source Network Calibration Report

- **Corpus version:** 0.1
- **Corpus seeded:** 2026-04-16
- **Run started:** 2026-04-16T15:15:51.268350+00:00
- **Total claims:** 27
- **Stale ground-truth claims:** 11 (see list at end)

## Per-provider results

| Provider | N | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| alpha_vantage | 4 | 1 | 0 | 1 | 2 | 1.00 | 0.50 | 0.67 |
| fred | 5 | 0 | 0 | 3 | 2 | n/a | 0.00 | n/a |
| rest_countries | 5 | 2 | 1 | 0 | 2 | 0.67 | 1.00 | 0.80 |
| sec_edgar | 5 | 2 | 0 | 1 | 2 | 1.00 | 0.67 | 0.80 |
| wolfram_alpha | 4 | 1 | 0 | 1 | 2 | 1.00 | 0.50 | 0.67 |
| world_bank | 4 | 1 | 0 | 1 | 2 | 1.00 | 0.50 | 0.67 |

## Claim-level detail

| ID | Provider | Expected | Observed | Match | Best source |
|---|---|---|---|---|---|
| sec-001 | sec_edgar | verified | verified | yes | SEC Filing |
| sec-002 | sec_edgar | verified | verified | yes | SEC Filing |
| sec-003 | sec_edgar | contradicted | contradicted | yes |  |
| sec-004 | sec_edgar | unverifiable | unverifiable | yes |  |
| sec-005 | sec_edgar | verified | contradicted | no |  |
| fred-001 | fred | verified | unverifiable | no |  |
| fred-002 | fred | verified | disputed | no | Wikipedia |
| fred-003 | fred | contradicted | unverifiable | no |  |
| fred-004 | fred | unverifiable | unverifiable | yes |  |
| fred-005 | fred | verified | unverifiable | no |  |
| rc-001 | rest_countries | verified | verified | yes | Wikipedia |
| rc-002 | rest_countries | verified | verified | yes | REST Countries |
| rc-003 | rest_countries | contradicted | contradicted | yes |  |
| rc-004 | rest_countries | contradicted | verified | no | World Bank |
| rc-005 | rest_countries | unverifiable | no_claim_extracted | no |  |
| wb-001 | world_bank | verified | verified | yes | World Bank |
| wb-002 | world_bank | close | unverifiable | no |  |
| wb-003 | world_bank | contradicted | contradicted | yes |  |
| wb-004 | world_bank | unverifiable | unverifiable | yes |  |
| av-001 | alpha_vantage | verified | unverifiable | no |  |
| av-002 | alpha_vantage | contradicted | unverifiable | no |  |
| av-003 | alpha_vantage | unverifiable | unverifiable | yes |  |
| av-004 | alpha_vantage | close | verified | yes | SEC Filing |
| wa-001 | wolfram_alpha | verified | verified | yes | Wikipedia |
| wa-002 | wolfram_alpha | verified | unverifiable | no |  |
| wa-003 | wolfram_alpha | contradicted | unverifiable | no |  |
| wa-004 | wolfram_alpha | unverifiable | no_claim_extracted | no |  |

## Stale ground-truth claims

These claims have an as_of_date older than 90 days. Re-verify the primary source before treating their results as calibration signal.

- `sec-001`
- `sec-002`
- `sec-003`
- `sec-005`
- `fred-001`
- `fred-002`
- `fred-003`
- `fred-005`
- `wb-001`
- `wb-002`
- `wb-003`
