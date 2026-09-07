#!/usr/bin/env python3
"""MakeMyTrip pricing MCP server - stdio JSON-RPC 2.0.

Read-only. There is deliberately no booking, cart, payment or login path anywhere in
this program, and none should ever be added: it exists to benchmark prices.

The MCP protocol is implemented directly rather than through an SDK so the only runtime
dependency is Playwright, and even that is optional - without it the server still starts,
lists its tools, and explains what to install.

Works unchanged as a Claude Cowork plugin, an OpenClaw stdio server, a Claude Code MCP
server, or anything else that speaks MCP over stdio.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mmt import __version__                     # noqa: E402
from mmt import tools as T                      # noqa: E402
from mmt.session import SESSION                 # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "makemytrip"

MIN_PY = (3, 10)

# Protocol revisions this server can speak. initialize() answers with the client's
# requested version when it is in this set, else with our latest - so a 2025 client is
# not forced down to the 2024 framing it asked to avoid.
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", PROTOCOL_VERSION)

# The payloads contain the rupee sign. On a Windows console defaulting to cp1252 the
# first one would otherwise raise UnicodeEncodeError inside a protocol write and kill
# the server mid-handshake.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(msg: str) -> None:
    """Diagnostics go to stderr. stdout carries the protocol and nothing else."""
    print(f"[{SERVER_NAME}] {msg}", file=sys.stderr, flush=True)


def _err(code: int, message: str, rid: Any = None) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _ok(rid: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def tool_list() -> dict:
    """Advertised tools. Hidden ones stay callable by name - probe.py and
    mmt_intercity_options reach them directly - they are just not offered to a model."""
    return {"tools": [
        {"name": name, "description": spec["description"],
         "inputSchema": spec["schema"]}
        for name, spec in sorted(T.TOOLS.items()) if not spec.get("hidden")
    ]}


async def call_tool(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    spec = T.TOOLS.get(name)
    if spec is None:
        return {"content": [{"type": "text", "text": f"unknown tool: {name}"}],
                "isError": True}
    result = await spec["fn"](**args)
    is_error = isinstance(result, dict) and "error" in result
    return {"content": [{"type": "text",
                         "text": json.dumps(result, indent=2, default=str,
                                            ensure_ascii=False)}],
            "isError": is_error}


async def handle(msg: dict) -> dict | None:
    rid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}

    if method == "initialize":
        client_v = (msg.get("params") or {}).get("protocolVersion")
        chosen = client_v if client_v in SUPPORTED_PROTOCOLS else PROTOCOL_VERSION
        return _ok(rid, {
            "protocolVersion": chosen,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": __version__},
        })
    if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return _ok(rid, {})
    if method == "tools/list":
        return _ok(rid, tool_list())
    if method == "tools/call":
        try:
            return _ok(rid, await call_tool(params))
        except Exception as e:                       # never let one call kill the loop
            log(f"tools/call crashed: {type(e).__name__}: {e}")
            return _ok(rid, {"content": [{"type": "text", "text": json.dumps(
                {"error": f"{type(e).__name__}: {e}", "kind": "unexpected"})}],
                "isError": True})
    if rid is None:
        return None
    return _err(-32601, f"method not found: {method}", rid)


async def main() -> int:
    if sys.version_info < MIN_PY:
        log(f"Python {MIN_PY[0]}.{MIN_PY[1]}+ required, found "
            f"{sys.version_info.major}.{sys.version_info.minor}")
        return 1

    # stdin is read on a worker thread rather than via loop.connect_read_pipe:
    # that API does not work on Windows' ProactorEventLoop, and fails on any stdin
    # that cannot be polled (a file, or /dev/null). This works everywhere.
    log(f"ready (v{__version__}, {len(T.TOOLS)} tools)")

    try:
        while True:
            line = await asyncio.to_thread(sys.stdin.buffer.readline)
            if not line:
                break
            raw = line.decode("utf-8", "replace").strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                sys.stdout.write(json.dumps(_err(-32700, "parse error")) + "\n")
                sys.stdout.flush()
                continue
            response = await handle(msg)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
    finally:
        await SESSION.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
