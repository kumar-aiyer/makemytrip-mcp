#!/usr/bin/env python3
"""Read the server's own call log. This is what the H6 gate should be scored against.

    python tools/audit_calls.py --summary
    python tools/audit_calls.py --find 4367          # which call produced this figure?
    python tools/audit_calls.py --tool mmt_cab_quote --tail 5
    python tools/audit_calls.py --since 2026-09-05T12:00 --summary

`--find` is the spot-check: give it a number off a deliverable and it names the call that
returned it, with the path inside the result where it appears. A number that appears in no
call was not sourced from this server, which is exactly what H6 is trying to establish.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mmt import calllog as CALLLOG    # noqa: E402


def walk(node, path=""):
    """Every scalar in a nested result, with a dotted path to it."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, node


def matches(value, target: float) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return abs(float(value) - target) < 0.01
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("Rs", "").replace("₹", "").strip()
        try:
            return abs(float(cleaned) - target) < 0.01
        except ValueError:
            return False
    return False


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--find", type=float, metavar="N",
                    help="trace a figure back to the call that returned it")
    ap.add_argument("--tool", help="filter to one tool name")
    ap.add_argument("--since", help="ISO prefix, e.g. 2026-09-05T12")
    ap.add_argument("--tail", type=int, help="only the last N entries")
    ap.add_argument("--path", action="store_true", help="print the log path and exit")
    a = ap.parse_args(argv[1:])

    if a.path:
        print(CALLLOG.path())
        return 0

    entries = CALLLOG.read()
    if not entries:
        print(f"no calls logged at {CALLLOG.path()}")
        return 1
    if a.tool:
        entries = [e for e in entries if e.get("tool") == a.tool]
    if a.since:
        entries = [e for e in entries if str(e.get("at", "")) >= a.since]
    if a.tail:
        entries = entries[-a.tail:]

    if a.find is not None:
        hits = 0
        for e in entries:
            if "result" not in e:
                continue
            where = [p for p, v in walk(e["result"]) if matches(v, a.find)]
            if where:
                hits += 1
                print(f"{e['at']}  {e['tool']}  {json.dumps(e['args'], ensure_ascii=False)}")
                print(f"    {e['elapsed_ms']} ms, tier {e.get('tier_used', '-')}, "
                      f"cached {e.get('cached', '-')}, sha256 {e['result_sha256'][:16]}")
                for p in where[:6]:
                    print(f"    found at: {p}")
                if len(where) > 6:
                    print(f"    ... and {len(where) - 6} more positions")
        if not hits:
            print(f"{a.find:g} appears in NO logged call result. "
                  "It did not come from this server.")
            return 2
        print(f"\n{hits} call(s) returned {a.find:g}")
        return 0

    if a.summary:
        by: dict[str, dict] = {}
        for e in entries:
            s = by.setdefault(e.get("tool", "?"), {"n": 0, "ok": 0, "ms": 0, "kinds": {}})
            s["n"] += 1
            s["ok"] += 1 if e.get("ok") else 0
            s["ms"] += e.get("elapsed_ms", 0)
            if not e.get("ok"):
                k = e.get("kind") or "?"
                s["kinds"][k] = s["kinds"].get(k, 0) + 1
        print(f"{len(entries)} calls  {entries[0]['at']} .. {entries[-1]['at']}")
        print(f"{'tool':<24}{'n':>4}{'ok':>5}{'avg ms':>9}  errors")
        for name, s in sorted(by.items(), key=lambda x: -x[1]["n"]):
            kinds = ", ".join(f"{k}x{v}" for k, v in s["kinds"].items()) or "-"
            print(f"{name:<24}{s['n']:>4}{s['ok']:>5}{s['ms'] // s['n']:>9}  {kinds}")
        return 0

    for e in entries:
        flag = "ok " if e.get("ok") else f"ERR({e.get('kind')})"
        print(f"{e['at']}  {flag:<18}{e['tool']:<22}{e['elapsed_ms']:>7} ms  "
              f"{json.dumps(e['args'], ensure_ascii=False)[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
