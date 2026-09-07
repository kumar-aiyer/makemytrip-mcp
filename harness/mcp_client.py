#!/usr/bin/env python3
"""Drive the MMT server over real MCP stdio from one long-lived process.

This is the acceptance-run driver for a host that cannot register the server
(see harness/findings.md, 2026-09-05). It spawns `server.py` ONCE and keeps the
handshake open across every call in a plan, so all calls share a single browser
-- which is the whole point. The thing the run prompt forbids is a *per-call*
`python -c`, because each of those starts its own Chrome; this does the opposite.

    python harness/mcp_client.py --list
    python harness/mcp_client.py --plan plan.json --out results.json

A plan is a JSON list of {"tool": ..., "args": {...}} objects, executed in order,
stopping at the first error unless the entry sets "allow_error": true.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "2025-06-18"


class Server:
    def __init__(self, state_home: str = ".state", timeout: float = 180.0):
        env = dict(os.environ,
                   MMT_MCP_HOME=str((ROOT / state_home).resolve()),
                   PYTHONIOENCODING="utf-8")
        self.timeout = timeout
        self.proc = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "server.py")],
            cwd=str(ROOT), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1)
        self._id = 0
        self._out: queue.Queue = queue.Queue()
        self.stderr: list[str] = []
        threading.Thread(target=self._pump_stdout, daemon=True).start()
        threading.Thread(target=self._pump_stderr, daemon=True).start()

    def _pump_stdout(self) -> None:
        for line in self.proc.stdout:
            line = line.strip()
            if line:
                self._out.put(line)
        self._out.put(None)

    def _pump_stderr(self) -> None:
        for line in self.proc.stderr:
            self.stderr.append(line.rstrip())

    def rpc(self, method: str, params: dict | None = None, timeout: float | None = None):
        self._id += 1
        rid = self._id
        msg = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        deadline = time.monotonic() + (timeout or self.timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"{method} timed out after {timeout or self.timeout}s")
            try:
                line = self._out.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f"{method} timed out after {timeout or self.timeout}s")
            if line is None:
                tail = "\n".join(self.stderr[-15:])
                raise RuntimeError(f"server exited during {method}. stderr tail:\n{tail}")
            msg = json.loads(line)
            if msg.get("id") != rid:
                continue                       # notification or stale reply
            if "error" in msg:
                raise RuntimeError(f"{method}: {msg['error']}")
            return msg["result"]

    def notify(self, method: str, params: dict | None = None) -> None:
        self.proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "method": method, "params": params or {}}) + "\n")
        self.proc.stdin.flush()

    def initialize(self) -> dict:
        r = self.rpc("initialize", {
            "protocolVersion": PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": "harness/mcp_client.py", "version": "1"},
        }, timeout=30)
        self.notify("notifications/initialized")
        return r

    def list_tools(self) -> list[dict]:
        return self.rpc("tools/list", timeout=30).get("tools", [])

    def call(self, tool: str, args: dict, timeout: float | None = None):
        """Returns (parsed_payload, raw_result). The server wraps payloads as
        one text content block holding JSON."""
        raw = self.rpc("tools/call", {"name": tool, "arguments": args}, timeout=timeout)
        text = "".join(c.get("text", "") for c in raw.get("content", [])
                       if c.get("type") == "text")
        try:
            return json.loads(text), raw
        except json.JSONDecodeError:
            return text, raw

    def close(self) -> None:
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="handshake + tools/list, then exit")
    ap.add_argument("--plan", help="JSON file: [{tool, args, timeout?, allow_error?}, ...]")
    ap.add_argument("--out", help="write results JSON here")
    ap.add_argument("--timeout", type=float, default=180.0)
    a = ap.parse_args(argv[1:])

    s = Server(timeout=a.timeout)
    try:
        info = s.initialize()
        si = info.get("serverInfo", {})
        print(f"connected: {si.get('name')} {si.get('version')} "
              f"(protocol {info.get('protocolVersion')})", flush=True)

        if a.list:
            for t in s.list_tools():
                print(f"  {t['name']:<28} {t.get('description','').splitlines()[0][:70]}")
            return 0

        if not a.plan:
            ap.error("give --list or --plan")

        plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
        results = []
        for i, step in enumerate(plan, 1):
            tool, args = step["tool"], step.get("args", {})
            print(f"[{i}/{len(plan)}] {tool} {json.dumps(args, ensure_ascii=False)}",
                  flush=True)
            t0 = time.monotonic()
            rec = {"tool": tool, "args": args}
            try:
                payload, _ = s.call(tool, args, timeout=step.get("timeout", a.timeout))
                rec["elapsed_s"] = round(time.monotonic() - t0, 1)
                rec["result"] = payload
                err = payload.get("error") if isinstance(payload, dict) else None
                print(f"      -> {rec['elapsed_s']}s "
                      f"{'ERROR: ' + str(err) if err else 'ok'}", flush=True)
                if err and not step.get("allow_error"):
                    results.append(rec)
                    break
            except Exception as e:
                rec["elapsed_s"] = round(time.monotonic() - t0, 1)
                rec["exception"] = f"{type(e).__name__}: {e}"
                print(f"      -> {rec['elapsed_s']}s {rec['exception']}", flush=True)
                results.append(rec)
                break
            results.append(rec)

        if a.out:
            Path(a.out).write_text(json.dumps(results, indent=2, ensure_ascii=False,
                                              default=str), encoding="utf-8")
            print(f"wrote {a.out}")
        return 0
    finally:
        s.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
