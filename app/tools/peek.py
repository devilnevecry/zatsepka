"""Inspect captured JSON/HTML without printing large payloads.

Usage:
  python -m app.tools.peek <file> [--path a.b.0.c] [--grep text] [--depth 4] [--lines 40]

JSON: key tree with types and array lengths (strings cut to 60 chars).
HTML: tag outline showing only aria-label, role and data-* attributes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from selectolax.parser import HTMLParser

STR_CUT = 60
DEFAULT_LINES = 40


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return f"list[{len(value)}]"
    if isinstance(value, dict):
        return f"dict[{len(value)}]"
    return type(value).__name__


def _cut(value: Any) -> str:
    text = str(value)
    return text if len(text) <= STR_CUT else text[:STR_CUT] + "…"


def json_tree(data: Any, depth: int = 4, indent: int = 0, lines: list[str] | None = None) -> list[str]:
    out = lines if lines is not None else []
    pad = "  " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)) and indent < depth:
                out.append(f"{pad}{key}: {_type_name(value)}")
                json_tree(value, depth, indent + 1, out)
            else:
                shown = _cut(value) if isinstance(value, str) else _type_name(value)
                out.append(f"{pad}{key}: {shown}")
    elif isinstance(data, list):
        for i, value in enumerate(data):
            if isinstance(value, (dict, list)) and indent < depth:
                out.append(f"{pad}[{i}]: {_type_name(value)}")
                json_tree(value, depth, indent + 1, out)
            else:
                shown = _cut(value) if isinstance(value, str) else _type_name(value)
                out.append(f"{pad}[{i}]: {shown}")
            if i >= 19:
                out.append(f"{pad}… {len(data) - 20} more items")
                break
    return out


def get_path(data: Any, path: str) -> Any:
    node = data
    for part in path.split("."):
        if part == "":
            continue
        if isinstance(node, list):
            node = node[int(part)]
        elif isinstance(node, dict):
            node = node[part]
        else:
            raise KeyError(f"cannot descend into {_type_name(node)} at {part!r}")
    return node


def grep_json(data: Any, text: str, limit: int = 10, path: str = "", hits: list | None = None) -> list[tuple[str, str]]:
    out = hits if hits is not None else []
    needle = text.casefold()
    if len(out) >= limit:
        return out
    if isinstance(data, dict):
        for key, value in data.items():
            child = f"{path}.{key}" if path else str(key)
            if needle in str(key).casefold():
                out.append((child, _cut(key)))
            grep_json(value, text, limit, child, out)
            if len(out) >= limit:
                break
    elif isinstance(data, list):
        for i, value in enumerate(data):
            grep_json(value, text, limit, f"{path}.{i}", out)
            if len(out) >= limit:
                break
    elif isinstance(data, str) and needle in data.casefold():
        out.append((path or "$", _cut(data)))
    return out


def html_outline(html: str, max_nodes: int = 400) -> list[str]:
    parser = HTMLParser(html)
    out: list[str] = []
    interesting = ("aria-label", "role", "aria-role")

    def walk(node, depth: int) -> None:  # noqa: ANN001
        child = node.child
        while child is not None and len(out) < max_nodes:
            tag = child.tag
            if tag and tag not in ("-text", "-comment"):
                attrs = child.attrs or {}
                shown = []
                for key, value in attrs.items():
                    if key in interesting or key.startswith("data-"):
                        shown.append(f'{key}="{_cut(value or "")}"')
                suffix = (" " + " ".join(shown)) if shown else ""
                out.append(f"{'  ' * depth}{tag}{suffix}")
                walk(child, depth + 1)
            child = child.next

    root = parser.body if parser.body is not None else parser.root
    if root is not None:
        walk(root, 0)
    return out


def load_any(path: Path) -> tuple[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix in (".html", ".htm"):
        return "html", raw
    try:
        return "json", json.loads(raw)
    except json.JSONDecodeError:
        stripped = raw.lstrip()
        if stripped.startswith(")]}'"):
            cleaned = stripped.split("\n", 1)[-1]
            try:
                return "json", json.loads(cleaned)
            except json.JSONDecodeError:
                pass
        if "<html" in raw[:2000].lower() or "<!doctype" in raw[:200].lower():
            return "html", raw
        raise


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Inspect captured JSON/HTML payloads")
    ap.add_argument("file")
    ap.add_argument("--path", default="", help="dotted node path, e.g. a.b.0.c")
    ap.add_argument("--grep", default="", help="print up to 10 matching nodes with paths")
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--lines", type=int, default=DEFAULT_LINES)
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"file not found: {path}")
        return 1
    kind, data = load_any(path)

    if kind == "html":
        lines = html_outline(data)
    elif args.path:
        node = get_path(data, args.path)
        lines = json_tree(node, args.depth) if isinstance(node, (dict, list)) else [_cut(node)]
    elif args.grep:
        hits = grep_json(data, args.grep)
        lines = [f"{p}: {snippet}" for p, snippet in hits] or ["no matches"]
    else:
        lines = json_tree(data, args.depth)

    for line in lines[: args.lines]:
        print(line)
    if len(lines) > args.lines:
        print(f"… {len(lines) - args.lines} more lines (use --path / --grep / --lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
