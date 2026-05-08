# Detector empirics: per-FVS firing rates

**Generated:** 2026-05-01
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

Read this table as: 'FVS-NNN fires as PRESENT in K of N corpus documents.' The complement (`N - K`) is the absence count for the same detector. The methodology paper's claim 'FVS-NNN absent in M of N documents' is `(N - K)` for this row, MINUS any rows where the same FVS-NNN fires as ABSENCE-pattern (next table) since those are not silently-absent but actively-detected-as-absent.

## Per-FVS absence-pattern firing rate

| FVS | Fires in | of N | % |
|---|---|---|---|
| FVS-007 | 1 | 13 | 8 |

V1-detector absence-pattern fires (`pattern_kind == "absence_detected"` in the structured emission). Today only FVS-007 Failure Framing has an absence-pattern detector in `frame_library.py:362-370` (fires when risks AND uncertainty are both missing AND unhedged-claim density exceeds 60%). A document where FVS-007 fires absence-pattern is actively-detected-as-absent on the failure-framing dimension, distinct from documents where FVS-007 is silently-absent (no fire, no evidence of absence-detection structural conditions).

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

`(abstain)` = classifier returned `null` (no feature-marker regex matched). Abstention is preferred over mislabeling. A high abstention rate on a corpus is not a defect; it is a measurement of how often the regex-based feature surface fires.

## Voice classification distribution

| Classification | Count | % |
|---|---|---|
| analytical | 11 | 85 |
| prescriptive | 1 | 8 |
| advisory | 1 | 8 |

## Frame deepening per-detector firing rate

| Detector | Fires in | of N | % |
|---|---|---|---|
| temporal_scope | 13 | 13 | 100 |
| stakeholder_map | 13 | 13 | 100 |
| falsification_conditions | 13 | 13 | 100 |

Three regex/feature detectors at `frame_deepening.py` (`detect_temporal_scope`, `detect_stakeholder_map`, `detect_falsification_conditions`). Each returns `Optional[dict]`: `None` when no signal is found, a dict of structural evidence otherwise. The MCP wire shape at `analysis.frame_deepening.<detector>` preserves this distinction (`null` vs object). 'Fires' here means the detector returned a non-`None` dict, regardless of how rich the dict's content is. Per NEXT_STEPS.md "Substrate-side composition: web exposure", web exposure of `frame_deepening` is gated on per-detector expert-grading; this aggregate is the empirical baseline the grading pass calibrates against. A 100% firing rate across the corpus is itself a finding: it tells the operator the corpus has CEILING saturation on this detector and grading needs documents specifically lacking the signal to measure the false-positive boundary.

## Absence-cluster dimension incidence

| Dimension | Fires in | of N | % |
|---|---|---|---|
| calibration | 5 | 13 | 38 |
| coverage | 4 | 13 | 31 |
| counterfactual | 1 | 13 | 8 |

## Per-document detail

| Document | Words | Genre | Voice | Present | Absent-pattern | Addressed | Deepening |
|---|---|---|---|---|---|---|---|
| `adversarial/balanced_macroeconomic_outlook` | 615 | narrative | analytical | FVS-010,FVS-011 | - | causes,risks,stakeholders,trends,uncertainty | TSF |
| `adversarial/coverage_via_noncanonical_vocabulary` | 561 | - | analytical | FVS-011 | - | risks,stakeholders,trends | TSF |
| `adversarial/cross_domain_stakeholder` | 337 | - | analytical | FVS-012 | - | trends,uncertainty | TSF |
| `adversarial/epistemic_via_paraphrased_sourcing` | 653 | - | analytical | FVS-012 | - | trends,uncertainty | TSF |
| `adversarial/instruction_without_troubleshooting` | 246 | instruction | prescriptive | - | FVS-007 | - | TSF |
| `adversarial/sales_pitch_as_analysis` | 323 | recommendation | analytical | FVS-011 | - | risks,stakeholders,trends | TSF |
| `adversarial/voice_residual_analytical` | 336 | - | analytical | FVS-012 | - | uncertainty | TSF |
| `worked/ai-on-life-decisions-startup-2026` | 1545 | narrative | advisory | FVS-010,FVS-011,FVS-012 | - | causes,risks,stakeholders,trends,uncertainty | TSF |
| `worked/divergence-on-claude-bitcoin-retirement-2026` | 2132 | advocacy | analytical | FVS-009,FVS-010,FVS-011,FVS-012 | - | causes,risks,stakeholders,trends,uncertainty | TSF |
| `worked/fomc-statement-march-2026` | 1282 | - | analytical | FVS-009,FVS-010,FVS-011,FVS-012 | - | causes,risks,stakeholders,trends,uncertainty | TSF |
| `worked/four-llms-on-bitcoin-retirement-2026` | 1636 | recommendation | analytical | FVS-009,FVS-011,FVS-012 | - | causes,risks,stakeholders,trends,uncertainty | TSF |
| `worked/grok-on-nvidia-earnings-2026` | 2172 | - | analytical | FVS-010 | - | causes,risks,stakeholders,trends,uncertainty | TSF |
| `worked/the-intelligence-age-altman-2024` | 1382 | - | analytical | FVS-009,FVS-010 | - | causes,risks,stakeholders,trends,uncertainty | TSF |

## Reproducibility

Re-run via `python3 scripts/detector_empirics.py`. Determinism: the substrate is regex-only (no LLM); identical input produces identical output. Drift between this report and a future run either means (a) the corpus changed (added/removed/edited fixtures) or (b) a detector regex changed. The aggregate.json and per_document.json files in this directory are the machine-readable artifacts; this report is the human-readable summary derived from them.
