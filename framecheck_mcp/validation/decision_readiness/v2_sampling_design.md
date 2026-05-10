# v2 randomly-sampled corpus: design specification

The v1 seeded corpus is convenience-sampled from documents
already captured for other Framecheck worked examples. This is
documented honestly on the
[methodology page](https://frame.clarethium.com/corpus/decision-readiness/)
under "Sampling honesty," but acknowledgment alone does not
defend the methodology against selection-bias critique.

The v2 corpus addresses this with a randomly-sampled component.
This document specifies the sampling design BEFORE implementation
so the method is reviewable. Implementation is deliberately
deferred; the design reduces the implementation surface to
mechanical work once the methodology is approved.

## Status

- v1 seeded corpus: shipped (10 entries across 2 genres)
- v2 randomly-sampled component: design specified (this file)
- v2 implementation: pending

## Design goals

1. **Defensibility against selection bias.** A reviewer should
   be able to inspect the sampling procedure and conclude that
   the v2 entries were not chosen to make Framecheck look good
   (or bad).
2. **Reproducibility.** Anyone with the source pool, sampling
   seed, and procedure should be able to derive the same v2
   corpus.
3. **Per-genre coverage.** Each missing genre gets at least
   three v2 entries so per-genre Spearman has a non-degenerate
   sample.
4. **Diff visibility against v1.** The harness should compute
   per-dimension correlations separately for v1 and v2 entries
   so the difference itself becomes evidence of selection bias
   (or its absence).

## Sampling design per genre

### `policy` (3 v2 entries)

**Source pool:** all FOMC statements published in
[federalreserve.gov/monetarypolicy/fomccalendars.htm](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
between 2020-01-01 and the v2 cutoff date. Approximately 8 per
year, so roughly 32-50 candidate statements depending on the
cutoff.

**Sampling procedure:**

1. Enumerate the source pool deterministically by date ascending.
2. Hash the corpus version string (e.g., `"v2-2026-Q3"`) with
   SHA-256 and take the first 4 bytes as a seed integer.
3. Use Python `random.Random(seed)` to draw 3 indices without
   replacement from the enumerated pool.
4. Fetch the corresponding statement texts, capture metadata
   (publication date, FOMC meeting reference, retrieved-at
   timestamp), record the SHA-256 of each fetched text in
   metadata.yaml for content provenance.

**Why this works:** the seed is derived from a public string,
the source pool is finite and enumerable, and the procedure is
deterministic. A reviewer with the same Python version and the
same source-pool enumeration can reproduce the exact 3 entries.
There is no opportunity for the curator to swap one entry for
another without leaving a visible diff.

### `journalism` (3 v2 entries)

**Source pool:** Associated Press wire stories on a single
specified topic class (e.g., "natural disasters reported in
2025") drawn from the AP archive. Topic class chosen to give
the documents shared subject matter without selecting for any
particular argument shape.

**Alternative source pool:** ProPublica's article archive,
which is CC-BY-NC-ND licensed (research use OK) and indexed
chronologically.

**Sampling procedure:** identical pattern to `policy` — hash
the corpus version, derive seed, draw 3 indices.

**Excerpt rule:** if a story is longer than 5,000 characters,
include only the first 5,000 characters and mark the
truncation in metadata.yaml. Truncating from the start (not
mid-document) preserves the lede + first body section, which
is what most readers actually consume.

### `other` (3 v2 entries)

**Source pool:** essays from
[The Conversation](https://theconversation.com/) tagged
"economics" or "policy" published in a defined window. The
Conversation is CC-BY-ND, which permits research use with
attribution.

**Alternative source pool:** academic essays from
[arXiv](https://arxiv.org/) under permissive license, drawn
from a single subject classification (e.g., q-fin.GN).

**Sampling procedure:** identical pattern.

## Implementation surface

The implementation work, once the design is approved:

1. Write `validation/decision_readiness/sample_v2.py` that:
   a. Takes a corpus version string (CLI arg)
   b. Enumerates each genre's source pool (genre-specific
      adapters)
   c. Derives the per-genre seed from
      `SHA256(version_string + genre)`
   d. Draws indices, fetches text, writes corpus entries
   e. Runs `compute_decision_readiness` to populate
      `profile.json` for each new entry
2. Update `metadata.yaml` schema to include:
   - `corpus_version: "v2-..."`
   - `sampling_method: "random"`
   - `sampling_seed_source: "{version}+{genre}"`
   - `source_pool_description`
   - `position_in_enumerated_pool`
3. Update `run_validation.py` to compute per-corpus-version
   correlations (v1-only, v2-only, combined) so the v1-vs-v2
   diff becomes a visible signal.

## Why deferred

Three blockers:

1. **Source-pool fetching infrastructure.** Each genre needs
   an adapter that knows how to enumerate its source pool. AP /
   The Conversation / arXiv each have different APIs (or no
   API). The code to fetch them is genre-specific work that
   the v1 corpus doesn't need.
2. **License compliance.** Each source pool has a license; the
   adapter must respect it (attribution, no commercial use, no
   derivatives in some cases). Per-source license review is the
   load-bearing pre-implementation work.
3. **Storage and content provenance.** v2 entries with fetched
   text need SHA-256 hashing, attribution metadata, and a
   commit log that captures the corpus version. The metadata
   schema above is the design; implementation is mechanical.

None of these blockers is hard. They're just real work that
should not be wedged into a session focused on something else.

## When to do it

The v2 randomly-sampled component is the load-bearing defense
against the selection-bias critique. The right time to ship it
is:

- After Phase 2 v1 ratings produce initial correlations on the
  convenience-sampled corpus
- BEFORE publishing those correlations as validation evidence

Publishing v1 correlations without v2 cross-validation invites
exactly the selection-bias critique the methodology page
acknowledges. The publication SHOULD include both v1 and v2
results side by side, with the difference itself reported as
evidence of (or absence of) selection effect.

If v1 and v2 correlations agree closely, the convenience-
sampling did not bias the result and v1 correlations stand on
their own. If they diverge, the divergence itself is the most
informative output of the validation.

## Reviewer checklist

If you are reviewing this design before implementation:

- [ ] Are the named source pools appropriate for their genre?
- [ ] Is the seed derivation reproducible enough to satisfy
      reproducibility goal #2?
- [ ] Does the per-genre N (3) suffice for v1-vs-v2 comparison,
      or should it be larger?
- [ ] Are the suggested alternative source pools licensed for
      research use?
- [ ] Is the truncation rule for long journalism documents
      defensible, or should it be uniform across genres?

Open issues / decisions to make at implementation time:

- Whether to include a small v2 component WITHIN ai_response too,
  to test the convenience-sampling-vs-random diff in the
  best-covered genre. Current design says yes (3 entries via
  random sampling from a defined AI-response pool, separate
  from the existing four-llms file).
- Whether to publish the seed string in advance (deters cherry-
  picking) or only at sampling time (prevents reviewers from
  precomputing the result).
