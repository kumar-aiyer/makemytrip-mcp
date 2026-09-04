"""React Server Component unwrapping - shared by trains and cabs.

Both listing pages are Next.js App Router pages: no separate search API, the data
arrives inside the RSC stream embedded in the HTML.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator

PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')
LINE_RE = re.compile(r"^([0-9a-fA-F]+):(.*)$")
REF_RE = re.compile(r"^\$([0-9a-fA-F]+)$")
MAX_DEPTH = 12


def blob(html: str) -> str:
    """Concatenate and JSON-unescape every __next_f push payload.

    Chunks split mid-line, so concatenation must happen before any line splitting.
    """
    parts: list[str] = []
    for m in PUSH_RE.finditer(html):
        try:
            parts.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            continue
    return "".join(parts)


def chunks(text: str) -> dict[str, Any]:
    """Parse `<hexid>:<json>` lines into a reference table.

    Non-JSON lines (`1:HL[...]` preload hints) are skipped, not errors.
    """
    out: dict[str, Any] = {}
    for line in text.split("\n"):
        m = LINE_RE.match(line)
        if not m:
            continue
        try:
            out[m.group(1).lower()] = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
    return out


def resolve(node: Any, table: dict[str, Any], depth: int = 0) -> Any:
    """Replace "$<hexid>" references with the chunk they point at. Depth-capped."""
    if depth > MAX_DEPTH:
        return node
    if isinstance(node, str):
        m = REF_RE.match(node)
        if m:
            k = m.group(1).lower()
            if k in table:
                return resolve(table[k], table, depth + 1)
        return node
    if isinstance(node, list):
        return [resolve(v, table, depth + 1) for v in node]
    if isinstance(node, dict):
        return {k: resolve(v, table, depth + 1) for k, v in node.items()}
    return node


def balanced(s: str, start: int) -> str | None:
    """Return the balanced {...} substring beginning at `start`.

    String-aware: a brace inside a quoted value must not close the object.
    """
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return None


def iter_objects(text: str, marker: re.Pattern[str]) -> Iterator[dict]:
    """Yield each balanced object whose start matches `marker`."""
    for m in marker.finditer(text):
        raw = balanced(text, m.start())
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue
