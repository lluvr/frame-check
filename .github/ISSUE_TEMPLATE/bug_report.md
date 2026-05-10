---
name: Bug report
about: Report unexpected behavior, incorrect measurements, or broken deploy
title: "[bug] "
labels: bug
---

**Summary**
One sentence describing what went wrong.

**Surface**
Where did the bug appear? Tick one:

- [ ] Live site at frame.clarethium.com
- [ ] Local run (`uvicorn app:app`)
- [ ] MCP server (via Claude Desktop / Cursor / other client)
- [ ] Test suite (`run_tests.py` or direct pytest)
- [ ] Corpus artifacts / export pipeline
- [ ] Documentation or corpus site

**Reproduction**
Precise steps. For detection or comparison bugs, include the exact
text that produced the unexpected output (or a minimal excerpt) so
the behavior reproduces deterministically.

1. ...
2. ...
3. ...

**Expected**
What you expected to happen.

**Actual**
What happened instead. If applicable, paste the raw Framecheck output
or tool response.

**Environment**

- Framecheck commit or deploy date:
- Python version (for local runs):
- Browser (for UI bugs):
- OS:

**Construct-honesty check**
If the bug is about a measurement you believe is wrong, please
distinguish:

- [ ] The measurement's primary output is incorrect (a detection is
      firing where it should not, or vice versa).
- [ ] The measurement's framing / language to the reader is incorrect
      (the detection is right but the portrait prose misleads).
- [ ] The measurement's candidate-miss surfacing is noisy (a
      candidate sentence surfaces that is clearly irrelevant).

See the methodology canon at github.com/Clarethium/lodestone for the
distinction between a detection error and a framing error in the
reader-facing prose.
