# Detector empirics: per-FVS firing rates

**Generated:** 2026-04-29
**Corpus size:** 13 documents
**Source:** `data/adversarial_fixtures/*/document.md` + `data/worked_examples/*.md` (top-level only)

## What this measures

Firing rate per FVS detector and per coverage perspective. Genre + voice classification distribution. Absence-cluster dimension incidence. Computed by running `frame_check` over stdio MCP against each document and aggregating the structural fields. **Recall and precision are not reported**; those require gold-standard labels per document, which is operator-authoring work outside this harness.

## Per-FVS firing rate (presence detection)

| FVS | Fires in | of N | % |
|---|---|---|---|
| FVS-011 | 7 | 13 | 54 |
| FVS-012 | 7 | 13 | 54 |
| FVS-010 | 6 | 13 | 46 |
| FVS-009 | 4 | 13 | 31 |

Read this table as: 'FVS-NNN fires as PRESENT in K of N corpus documents.' The complement (`N - K`) is the absence count for the same detector. The methodology paper's claim 'FVS-NNN absent in M of N documents' is `(N - K)` for this row.

## Coverage perspective addressed rate

| Perspective | Addressed in | of N | % |
|---|---|---|---|
| causes | 7 | 13 | 54 |
| risks | 9 | 13 | 69 |
| stakeholders | 9 | 13 | 69 |
| trends | 11 | 13 | 85 |
| uncertainty | 10 | 13 | 77 |

## Genre classification distribution

| Classification | Count | % |
|---|---|---|
| (abstain) | 7 | 54 |
| narrative | 2 | 15 |
| recommendation | 2 | 15 |
| instruction | 1 | 8 |
| advocacy | 1 | 8 |

`(abstain)` = classifier returned `null` (no feature-marker regex matched). Per the evidence discipline, abstention is preferred over mislabeling. A high abstention rate on a corpus is not a defect; it is a measurement of how often the regex-based feature surface fires.

## Voice classification distribution

| Classification | Count | % |
|---|---|---|
| analytical | 11 | 85 |
| prescriptive | 1 | 8 |
| advisory | 1 | 8 |

## Absence-cluster dimension incidence

| Dimension | Fires in | of N | % |
|---|---|---|---|
| calibration | 5 | 13 | 38 |
| coverage | 4 | 13 | 31 |
| counterfactual | 1 | 13 | 8 |

## Per-document detail

| Document | Words | Genre | Voice | FVS fires | Addressed |
|---|---|---|---|---|---|
| `adversarial/balanced_macroeconomic_outlook` | 615 | narrative | analytical | FVS-010,FVS-011 | causes,risks,stakeholders,trends,uncertainty |
| `adversarial/coverage_via_noncanonical_vocabulary` | 561 | - | analytical | FVS-011 | risks,stakeholders,trends |
| `adversarial/cross_domain_stakeholder` | 337 | - | analytical | FVS-012 | trends,uncertainty |
| `adversarial/epistemic_via_paraphrased_sourcing` | 653 | - | analytical | FVS-012 | trends,uncertainty |
| `adversarial/instruction_without_troubleshooting` | 246 | instruction | prescriptive | - | - |
| `adversarial/sales_pitch_as_analysis` | 323 | recommendation | analytical | FVS-011 | risks,stakeholders,trends |
| `adversarial/voice_residual_analytical` | 336 | - | analytical | FVS-012 | uncertainty |
| `worked/ai-on-life-decisions-startup-2026` | 1545 | narrative | advisory | FVS-010,FVS-011,FVS-012 | causes,risks,stakeholders,trends,uncertainty |
| `worked/divergence-on-claude-bitcoin-retirement-2026` | 2132 | advocacy | analytical | FVS-009,FVS-010,FVS-011,FVS-012 | causes,risks,stakeholders,trends,uncertainty |
| `worked/fomc-statement-march-2026` | 1282 | - | analytical | FVS-009,FVS-010,FVS-011,FVS-012 | causes,risks,stakeholders,trends,uncertainty |
| `worked/four-llms-on-bitcoin-retirement-2026` | 1543 | recommendation | analytical | FVS-009,FVS-011,FVS-012 | causes,risks,stakeholders,trends,uncertainty |
| `worked/grok-on-nvidia-earnings-2026` | 2074 | - | analytical | FVS-010 | causes,risks,stakeholders,trends,uncertainty |
| `worked/the-intelligence-age-altman-2024` | 1382 | - | analytical | FVS-009,FVS-010 | causes,risks,stakeholders,trends,uncertainty |

## Reproducibility

Re-run via `python3 scripts/detector_empirics.py`. Determinism: the substrate is regex-only (no LLM); identical input produces identical output. Drift between this report and a future run either means (a) the corpus changed (added/removed/edited fixtures) or (b) a detector regex changed. The aggregate.json and per_document.json files in this directory are the machine-readable artifacts; this report is the human-readable summary derived from them.
