"""Frame Check MCP package.

This file marks `framecheck_mcp/` as a Python package so setuptools
includes the bundled data files (frame library, worked examples,
transmissions, methodology, calibration runs, validation corpus,
divergence spec) as `framecheck_mcp/...` paths in the wheel.

The 0.8.0 release ships with FLAT-LAYOUT code at the wheel's top
level (mcp_server, framing, clarethium_measure, ...) and bundled
data under this package. `mcp_server.py`'s `_DATA_ROOT` resolution
detects this layout at runtime: if a `framecheck_mcp/` directory
sits next to `mcp_server.py`, that's the data root; otherwise
the script directory is used (dev / repo layout).

This package will hold the full module tree at 1.0.0 when the
src-layout refactor lands. For now it is intentionally a thin
data carrier.
"""

# No public API; this package exists for setuptools to recognize
# data-bundling. Consumers import the analyzer modules from the
# top-level py-modules namespace (mcp_server, framing, ...).
