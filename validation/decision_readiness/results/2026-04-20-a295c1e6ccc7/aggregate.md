# Decision-readiness corpus aggregate findings

**Descriptive of corpus state, not inference about populations.**
Every claim below names its sample size inline. With small N,
individual outliers may be sampling noise rather than signal.
Aggregate findings become inference-grade only when N grows
substantially across genres and questions.

- **Computed at:** 2026-04-20T07:51:28.785400+00:00
- **Corpus state hash:** `a295c1e6ccc7` (SHA-256 prefix; identifies the exact corpus revision)
- **Corpus entries:** 10 (10 with profile.json, 2 with paired_with metadata, 8 with peer_group metadata)

## Peer-comparison findings

Aggregated across **N = 12 pairwise peer comparisons** in **2 peer groups**. Each comparison is non-directional; counts below represent the number of pairs in which the two peers measurably differed on a given dimension.

### Per-dimension divergence rate

Of 12 pairs, three outcomes per dimension: peers measurably differ, peers agree (signals comparable and match), or non-comparable (data missing on one or both sides; e.g., evidence and robustness when corpus profiles were computed without Source Network).

| Dimension | Differ | Agree | Non-comparable | Rate (of comparable) |
|-----------|-------:|------:|---------------:|---------------------:|
| coverage | 10 | 2 | 0 | 83% of 12 |
| calibration | 12 | 0 | 0 | 100% of 12 |
| evidence | 3 | 9 | 0 | 25% of 12 |
| robustness | 0 | 0 | 12 | n/a |
| counterfactual | 6 | 6 | 0 | 50% of 12 |

### Named library entries per dimension

When a dimension diverges in this aggregate, the named patterns in the Frame Vocabulary Standard describe the structural failure modes that produce the divergence. Click through to read the canonical entry for each frame.

- **Coverage**: FVS-001, FVS-008, FVS-009, FVS-010, FVS-011, FVS-014, FVS-015, FVS-017
- **Calibration**: FVS-012, FVS-017
- **Evidence**: FVS-016
- **Robustness**: FVS-016
- **Counterfactual**: FVS-001, FVS-007, FVS-009, FVS-012, FVS-014

### Per-peer-group breakdown

Counts within each peer group. A group with N members yields C(N, 2) pairs.

**bitcoin_retirement_question** (6 pairs):

  - coverage: 5 of 6 pairs differ
  - calibration: 6 of 6 pairs differ
  - evidence: 3 of 6 pairs differ
  - robustness: 0 of 6 pairs differ
  - counterfactual: 3 of 6 pairs differ

**startup_offer_question** (6 pairs):

  - coverage: 5 of 6 pairs differ
  - calibration: 6 of 6 pairs differ
  - evidence: 0 of 6 pairs differ
  - robustness: 0 of 6 pairs differ
  - counterfactual: 3 of 6 pairs differ

### Per-LLM participation in differing pairs

When two peers differ on a dimension, BOTH peers participated. These counts are descriptive of HOW OFTEN each LLM is in a pair where some divergence was measured. Cross-LLM behavioral claims require larger N.

Outlier identification: per peer group, the member whose signal value is most different from the group median on a given dimension is identified as the outlier on that dimension. Counts below report how many groups each LLM was the outlier in (out of the groups it appeared in).

| LLM | Groups | Cov | Cal | Evi | Rob | CF |
|-----|------:|----:|----:|----:|----:|----:|
| claude | 2 | 1 of 2 | 0 of 2 | n/a | n/a | 2 of 2 |
| gemini | 2 | 1 of 2 | 1 of 2 | n/a | n/a | 0 of 2 |
| grok | 2 | 0 of 2 | 1 of 2 | n/a | n/a | 0 of 2 |
| openai | 2 | 0 of 2 | 0 of 2 | n/a | n/a | 0 of 2 |

Legend: Cov = Coverage, Cal = Calibration, Evi = Evidence, Rob = Robustness, CF = Counterfactual. Cell shows outlier-count of comparable-group-count (n/a when the dimension was non-comparable in every group containing this LLM).

## Cross-question outlier consistency

When the same LLM is identified as the outlier on the same dimension across multiple distinct peer groups (different questions), that consistency is a stronger structural signal than any single-group outlier identification. The findings below report every (LLM, dimension) cell where the LLM is the outlier in EVERY comparable group it appears in.

- **claude** is the counterfactual outlier in **all 2 of 2** comparable peer groups it appears in. Named library entries for counterfactual: FVS-001, FVS-007, FVS-009, FVS-012, FVS-014.

These findings still inherit the corpus-level N caveat (current peer groups: 2). Cross-question consistency is more compelling at 2 groups than at 1, more compelling at 5 than at 2. The threshold for 'corpus-level finding' rises with the question-diversity of the peer groups.

## Transformation-diff findings

Aggregated across **N = 1 transformation pair**. Each pair is a directional source -> derived comparison.

**Small sample warning.** N = 1 is below the threshold (3) at which per-dimension rates become interpretive. Rates below should be read as raw counts, not as corpus-level findings. The aggregate becomes informative as more transformation pairs are added (see `CORPUS_GENRE_GAPS.md`).

### Per-dimension movement rate

Of 1 pairs, the count of pairs where the transformation measurably moved a dimension:

| Dimension | Pairs moved | Rate |
|-----------|------------:|-----:|
| coverage | 0 of 1 | 0/1 (small N) |
| calibration | 1 of 1 | 1/1 (small N) |
| evidence | 1 of 1 | 1/1 (small N) |
| robustness | 0 of 1 | 0/1 (small N) |
| counterfactual | 0 of 1 | 0/1 (small N) |

### Per-transformation-kind breakdown

- **llm_summary**: 1 pair

## Honest limits

- **Sample size**: peer N = 12, transformation N = 1. Conclusions about specific LLMs or specific transformation effects need substantially larger N.
- **Convenience sampling**: the v1 corpus is convenience-sampled from existing worked examples (see methodology page). Selection bias is acknowledged; v2 randomly-sampled component is the planned correction.
- **Genre coverage**: the corpus is heavily ai_response. Cross-genre claims require corpus expansion (see CORPUS_GENRE_GAPS.md).
- **Profile validation**: per-dimension absolute signals remain experimental until Phase 2 expert validation lands. Comparison signals (peer differs / transformation moved) are LESS dependent on absolute signal validity but still inherit the underlying methodology.

## Citation

Lucic, L. (2026). Frame Check decision-readiness aggregate findings, corpus revision `a295c1e6ccc7`, computed 2026-04-20. (production paused)

