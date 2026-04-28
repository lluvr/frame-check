"""Extract published transmissions from clarethium-app's blog vault
into frame-check/data/transmissions/ as normalized markdown files
with YAML frontmatter.

Reads:
  {SOURCE_VAULT}/_registry.ts
  {SOURCE_VAULT}/{ID}_*.md

Writes:
  {TARGET_DIR}/{slug}.md

Defaults resolve relative to this repo's working copy, assuming
clarethium-app is a sibling checkout at ../clarethium-app. Override
with CLI arguments if the upstream lives elsewhere.

Re-run this script after the author publishes a new transmission
(by adding a new transmission id to PUBLISHED_IDS in the upstream
_registry.ts). Transmissions marked draft in the registry are
intentionally NOT copied here: only the author's
explicit-publish list reaches the Frame Check MCP resource
surface.

The frontmatter captures the registry fields the blog carries
(transmission_id, display_title, type, summary, published,
models, source_url), plus updated and updateNote fields when
the author has edited a post after publication. The body is
the original vault content verbatim.
"""
import argparse
import os
import re
import sys


DEFAULT_VAULT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "clarethium-app",
        "src", "content", "blog",
    )
)
DEFAULT_OUT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "data", "transmissions",
    )
)
BLOG_BASE_URL = "https://blog.clarethium.com/blog"


def parse_array_literal(text: str, name: str) -> list:
    """Extract a TypeScript readonly string[] declared by name.

    Uses a non-greedy match to handle arrays with `as const` trailing.
    """
    pattern = (
        rf"{re.escape(name)}[^=]*=\s*\[([\s\S]*?)\]\s*(?:as\s+const\s*)?;"
    )
    m = re.search(pattern, text)
    if not m:
        raise RuntimeError(f"array literal {name!r} not found")
    body = m.group(1)
    return re.findall(r"'([^']+)'", body)


def parse_simple_record(text: str, name: str) -> dict:
    """Extract a TypeScript Record<string, string> literal. Keys and
    values are single- or double-quoted strings. Does not handle
    multi-line values or escapes (none present in the registry today)."""
    pattern = (
        rf"{re.escape(name)}[^=]*=\s*{{([\s\S]*?)}}\s*;"
    )
    m = re.search(pattern, text)
    if not m:
        raise RuntimeError(f"record literal {name!r} not found")
    body = m.group(1)
    out = {}
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        m2 = re.match(
            r"'([^']+)'\s*:\s*(['\"])(.*?)\2\s*,?\s*(?://.*)?$",
            stripped,
        )
        if m2:
            out[m2.group(1)] = m2.group(3)
    return out


def parse_meta(text: str) -> dict:
    """Extract TRANSMISSION_META. Each entry is an object literal keyed
    by transmission id; fields include type, models, published, summary,
    updated, updateNote, receipts. Multi-entry objects with nested braces
    are not expected here, so a simple non-nested brace match is sufficient.
    """
    pattern = r"'(T-\d+|M-\d+)'\s*:\s*{([^{}]*)}"
    out = {}
    for m in re.finditer(pattern, text):
        tid = m.group(1)
        body = m.group(2)
        entry = {}
        for field in [
            "type", "models", "published", "summary",
            "updated", "updateNote", "receipts",
        ]:
            fm = re.search(
                rf"{field}\s*:\s*(['\"])(.*?)\1\s*,?\s*$",
                body,
                re.M,
            )
            if fm:
                entry[field] = fm.group(2)
        out[tid] = entry
    return out


def find_markdown_file(vault_dir: str, transmission_id: str) -> str:
    """Find the markdown file for a transmission id. Files are named
    '{ID}_{title}.md' where title may contain underscores or hyphens."""
    prefix = transmission_id + "_"
    for name in sorted(os.listdir(vault_dir)):
        if name.startswith(prefix) and name.endswith(".md"):
            return os.path.join(vault_dir, name)
    raise FileNotFoundError(
        f"no markdown file for {transmission_id} in {vault_dir}"
    )


def yaml_escape(value: str) -> str:
    """Quote a string for YAML frontmatter. Double-quote and escape
    backslashes and double-quotes; leave single quotes alone so
    apostrophes render naturally in titles and summaries."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_frontmatter(
    transmission_id: str,
    slug: str,
    display_title: str,
    meta: dict,
) -> str:
    lines = ["---"]
    lines.append(f"transmission_id: {transmission_id}")
    lines.append(f"display_title: {yaml_escape(display_title)}")
    if meta.get("type"):
        lines.append(f"type: {meta['type']}")
    if meta.get("summary"):
        lines.append(f"summary: {yaml_escape(meta['summary'])}")
    if meta.get("published"):
        lines.append(f"published: {meta['published']}")
    if meta.get("updated"):
        lines.append(f"updated: {meta['updated']}")
    if meta.get("updateNote"):
        lines.append(f"update_note: {yaml_escape(meta['updateNote'])}")
    if meta.get("models"):
        lines.append(f"models: {yaml_escape(meta['models'])}")
    lines.append(f"source_url: {BLOG_BASE_URL}/{slug}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extract published transmissions from "
            "clarethium-app's blog vault into this repo's "
            "data/transmissions directory."
        ),
    )
    parser.add_argument(
        "--vault",
        default=DEFAULT_VAULT,
        help=(
            "Absolute path to clarethium-app/src/content/blog. "
            f"Default: {DEFAULT_VAULT}"
        ),
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help=(
            "Absolute path to the target transmissions directory. "
            f"Default: {DEFAULT_OUT}"
        ),
    )
    args = parser.parse_args()

    registry_path = os.path.join(args.vault, "_registry.ts")
    if not os.path.isfile(registry_path):
        print(
            f"ERROR: {registry_path} does not exist. "
            "Pass --vault explicitly if the blog vault lives "
            "elsewhere.",
            file=sys.stderr,
        )
        return 1

    with open(registry_path, encoding="utf-8") as f:
        registry_text = f.read()

    published = parse_array_literal(registry_text, "PUBLISHED_IDS")
    slugs = parse_simple_record(
        registry_text, "TRANSMISSION_URL_SLUGS"
    )
    titles = parse_simple_record(registry_text, "DISPLAY_TITLES")
    meta = parse_meta(registry_text)

    print(
        f"Published transmissions: {len(published)}",
        file=sys.stderr,
    )

    os.makedirs(args.out, exist_ok=True)

    written = 0
    skipped = 0
    for tid in published:
        slug = slugs.get(tid)
        if not slug:
            print(
                f"WARN: no slug for {tid}, skipping",
                file=sys.stderr,
            )
            skipped += 1
            continue
        display_title = titles.get(tid) or tid
        entry_meta = meta.get(tid, {})
        try:
            md_path = find_markdown_file(args.vault, tid)
        except FileNotFoundError as e:
            print(f"WARN: {e}", file=sys.stderr)
            skipped += 1
            continue
        with open(md_path, encoding="utf-8") as f:
            body = f.read()

        fm = build_frontmatter(tid, slug, display_title, entry_meta)
        out_path = os.path.join(args.out, f"{slug}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(fm + body)
        print(f"  {tid} -> {out_path}", file=sys.stderr)
        written += 1

    print(
        f"\nWrote {written} transmissions, skipped {skipped}, "
        f"to {args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
