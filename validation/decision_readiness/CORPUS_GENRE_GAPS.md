# Corpus genre gaps: what's still needed and how to add it

The seeded corpus (`corpus/`) covers two genres: `ai_response`
(9 entries) and `financial` (1 entry). Three genres named in the
methodology page are still missing or under-represented.

This file is a curator's checklist. Anyone with permission to
fetch text from the listed sources can close one or more gaps in
under fifteen minutes per entry.

## Why this matters

The methodology page commits to per-genre Spearman thresholds
(>= 0.4 per individual genre, >= 0.6 averaged). The harness
computes per-genre breakdowns automatically from each entry's
`metadata.yaml` genre field. With only two genres in the corpus
today, three genre buckets stay empty regardless of how many
ratings arrive.

A single corpus entry per missing genre is enough to compute a
per-genre correlation; two or three is enough to make the
correlation useful. The marginal value of the second cross-genre
entry is large; the marginal value of the tenth ai_response
entry is small at this point.

## Missing genres and recommended sources

### `policy` (zero entries)

**Recommended source:** the most-recent FOMC statement at
[federalreserve.gov/monetarypolicy](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm).
US Federal Reserve press releases are public domain works of the
US government and are well-suited to decision-readiness
validation: they are short (~300 words), structurally
conservative, and explicitly designed to communicate decision
rationale.

**Alternative:** any central-bank policy release in English,
World Bank or IMF policy statement, or a published government
agency decision memo.

### `journalism` (zero entries)

**Recommended source:** an Associated Press wire story
(AP allows quotation of full short articles under fair use for
academic / research purposes; note attribution explicitly in
metadata.yaml.notes). News reporting that contains numerical
claims and named sources is the right shape.

**Alternative:** Reuters, BBC News, ProPublica, or any news
outlet whose content licensing permits research use.
Single-author opinion columns belong under `other`, not
`journalism`; reserve `journalism` for reported stories with
explicit sourcing.

### `other` (zero entries; reserved for essays, manifestos, opinion)

**Recommended source:** a published essay where the author makes
a clear argument with cited evidence. Examples: published
academic essays under CC license, op-eds with explicit
permission, or essays from CC-licensed publications like
[The Conversation](https://theconversation.com/).

The Altman "Intelligence Age" essay referenced in the existing
worked example would fit here; capturing the verbatim text
requires fetching from the published source.

## How to add a corpus entry from a fetched document

The easy path: save the captured text to a UTF-8 file, then run
`add_external_corpus_entry.py` with the metadata as flags. The
script does the directory creation, profile computation, and
metadata file writing in one command.

Example for a fetched FOMC statement:

```
python3 validation/decision_readiness/add_external_corpus_entry.py \\
    --slug fomc-statement-2026-03 \\
    --text-file /tmp/fomc-statement.txt \\
    --genre policy \\
    --title "FOMC Statement (March 18, 2026)" \\
    --source "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318a.htm" \\
    --license-note "US government work, public domain"
```

For a transformation-pair entry (e.g., an LLM summary of an
already-curated source), add `--paired-with {source_slug}` and
`--transformation-kind llm_summary` (or other vocabulary).

For a peer-group entry, add `--peer-group {group_name}`.

The validation harness picks up new corpus entries on its next
run; no registration step is needed. The bundled corpus ships the
comparison files (`diff_with_*.json`, `peer_with_*.json`) for its
existing entries.

If you prefer manual control over the directory structure, the
fallback path is to create `corpus/{slug}/document.md` +
`metadata.yaml` + `profile.json` directly. The
`add_external_corpus_entry.py` script's source code documents
the metadata schema if you need to mirror it by hand.

## What NOT to add

- **Synthetic / fabricated documents.** A document Frame Check
  is supposed to validate against expert judgment must be a real
  document expert raters can engage with. Fictional documents
  contaminate the corpus.
- **Texts with restrictive licenses.** Corpus entries are
  CC-BY-4.0 along with the rest of the Frame Check corpus;
  texts with incompatible licenses cannot be redistributed.
  Quote excerpts under fair use only when the license permits
  research-purpose quotation, and document the attribution in
  metadata.yaml.notes.
- **Long-form documents past 10,000 characters.** Excerpt to a
  representative section if the full document is longer; raters
  cannot calibrate consistently across very long documents.
  Mark the excerpt range in metadata.yaml.

## Tracking

When you close one of the genre gaps above, delete the gap from
the "Missing genres" section and add the new corpus entry to
the seeded corpus table in `README.md`. The genre count in this
file and the README should always agree with the actual
contents of `corpus/`.
