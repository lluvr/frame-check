# Transmissions

Transmissions are short, evidence-first research pieces published
at [blog.clarethium.com](https://blog.clarethium.com/). Each one
reports a specific finding from the research program that feeds
Framecheck. They are the thinking behind the measurement
instruments, written in a disciplined register the author uses
for published research (stated claim, evidence, what survived
and what did not survive testing, honest limits).

This directory is a curation pass: the transmissions the author
has explicitly marked as published are copied here verbatim so
an agent in an MCP session can read the research directly,
alongside the Frame Vocabulary Standard, the methodology paper,
the worked examples, and the calibration evidence. The URI
scheme is `frame-check://transmissions/{slug}` where `{slug}`
matches the public blog URL
`https://blog.clarethium.com/{slug}`.

Why expose them as MCP resources and not just link out: a
Cloudflare edge layer in front of the blog makes the public
site unreachable to automated clients. Serving the content
directly as an MCP resource removes that friction without
copying in private drafts: only the transmissions in the
author's explicit `PUBLISHED_IDS` list are surfaced here.

## Published transmissions

Each entry is markdown with YAML frontmatter carrying the
transmission id, display title, type, one-line summary, publish
date, models tested, and source URL. The body is the original
vault content verbatim.

- `fabrication-architecture.md` (T-311): Most AI Numbers Are
  Fabricated. 77 to 100 percent of AI-generated numbers are
  temporally unstable; source material fixes it, prompts do not.
- `attribution-error.md` (T-350): The Model Is Rarely the
  Variable. The prompt determines whether behaviors exist at
  all; the model adjusts the volume.
- `source-conditioning.md` (T-351): How to Stop AI from Making
  Up Numbers. Source material drops AI fabrication from 85
  percent to single digits; three steps.
- `self-check-illusion.md` (T-352): Why AI Can't Check Its Own
  Work. The agent reported clean, the output was wrong; same
  process generating and evaluating.
- `constraint-paradox.md` (T-353): Same Technique, Opposite
  Results. The structured approach that produced precision on
  convergent problems actively harmed exploratory ones.
- `ceiling-switch.md` (T-392): Stop Polishing, Start Switching.
  The ceiling is per generation mode; switch modes to access
  territory iteration cannot reach.
- `catching-your-own-overclaim.md` (T-415): The Most-Cited
  Finding Was Wrong. The most-cited effect across 80+
  experiments was three effects stacked; honest magnitude is
  40 percent smaller.
- `trust-signals-are-inverted.md` (T-418): The Most Trustworthy
  AI Output Is the Least Reliable. The signals used to judge AI
  trustworthiness are the same signals fabrication produces.
- `system-layer.md` (T-422): Four Layers Produce Every AI
  Output. The company's system. Your system. Your prompt. The
  model. Only one has a name.
- `first-read.md` (M-002): Your Body Reads AI Output Before You
  Do. 180 trials. The same circuits fire on AI disagreement as
  on human; the first read happens in the body before conscious
  evaluation.

## Curation

`PUBLISHED_IDS` is maintained in clarethium-app's
`src/content/blog/_registry.ts`. This directory reflects that
list; a new transmission published upstream appears here after
a re-run of the extract-transmissions pass. Unpublished drafts
in the clarethium-app vault are intentionally not copied here.

## License

The transmissions are the author's research writing, reproduced
here for structural analysis and MCP accessibility. They carry
the same license as the rest of the Framecheck corpus material:
CC-BY-4.0. Citation: `blog.clarethium.com/{slug}` is the
canonical URL; cite that alongside any derivative use.
