"""Append-only record of every tool call this server answers.

Why this exists: the acceptance harness's H6 gate asks that every priced number in a
deliverable be traceable to the tool call that produced it. Three runs in a row it was
unscoreable, because the gate read from the *host's* transcript export - and Cline's
export produced a screenshot, a tail, and the final artifact respectively. The server
already knows what it was asked and what it answered, so it should say so itself.

One JSON object per line in `.state/diagnostics/calls.jsonl`, alongside the failures log
next to it (which records only failures). Nothing here is on the hot path: every write is
wrapped, and a broken log must never break a call.

Off with `MMT_CALL_LOG=0`. Result bodies are inlined up to `MMT_CALL_LOG_MAX_RESULT`
bytes (default 256 KB) so a spot-check can find a fare without a second call; above that
only the digest and size are kept. The digest is over the full body either way, so a
truncated entry still proves what was returned.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from . import config as C

MAX_RESULT = int(os.environ.get("MMT_CALL_LOG_MAX_RESULT", 256 * 1024))
# Roughly 4.8 KB per call in practice, so 16 MB is about 3,300 calls. One previous
# generation is kept, capping the whole thing at ~32 MB. An append-only diagnostics log
# that grows without limit is a bug in anything anyone else installs.
MAX_BYTES = int(os.environ.get("MMT_CALL_LOG_MAX_BYTES", 16 * 1024 * 1024))
FILENAME = "calls.jsonl"


def enabled() -> bool:
    return os.environ.get("MMT_CALL_LOG", "1") not in ("0", "false", "False", "")


def path():
    return C.DIAG_DIR / FILENAME


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def _canon(value: Any) -> str:
    """Stable text for digesting and for inlining. `default=str` because results carry
    dates and the odd non-JSON scalar; sort_keys so the digest does not depend on dict
    ordering."""
    return json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)


def record(tool: str, args: dict[str, Any], result: Any, elapsed_ms: int) -> None:
    """Append one entry. Never raises."""
    if not enabled():
        return
    try:
        body = _canon(result)
        entry: dict[str, Any] = {
            "at": _now_iso(),
            "tool": tool,
            "args": args,
            "elapsed_ms": elapsed_ms,
            "result_bytes": len(body.encode("utf-8")),
            "result_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }
        if isinstance(result, dict):
            err = result.get("error")
            entry["ok"] = err is None
            if err is not None:
                entry["kind"] = result.get("kind")
                entry["error"] = str(err)[:500]
            # the routing facts an auditor asks about first
            for k in ("tier_used", "cached", "fetched_at"):
                if k in result:
                    entry[k] = result[k]
        else:
            entry["ok"] = True

        if entry["result_bytes"] <= MAX_RESULT:
            entry["result"] = result
        else:
            entry["result_truncated"] = True

        C.DIAG_DIR.mkdir(parents=True, exist_ok=True)
        _rotate_if_large()
        with path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _rotate_if_large() -> None:
    """Roll the log over once it passes MAX_BYTES, keeping one previous generation.

    Rotation rather than trimming: rewriting a large file in place to drop old lines
    costs more than it saves, and an audit wants whole entries rather than a file that
    was truncated mid-JSON.
    """
    p = path()
    try:
        if MAX_BYTES <= 0 or not p.exists() or p.stat().st_size < MAX_BYTES:
            return
        previous = p.with_suffix(p.suffix + ".1")
        previous.unlink(missing_ok=True)
        p.rename(previous)
    except Exception:
        pass


def read(limit: int | None = None) -> list[dict[str, Any]]:
    """Entries oldest-first, from the current generation only.

    A half-written final line (killed mid-append) is skipped rather than raising - this
    is diagnostics, not a ledger. The rotated `.1` file is deliberately not merged in: an
    acceptance run truncates the log at pre-flight, so the current file is the run.
    """
    p = path()
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out[-limit:] if limit else out
