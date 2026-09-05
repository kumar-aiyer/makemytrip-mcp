"""Offline tests for tools/watch_server.py, the MCP development supervisor.

The supervisor is driven as a subprocess with a stub child - a tiny JSON-RPC
echo server written inline - so nothing touches the network or a browser. The
tests prove the three things the wrapper exists for:

  - transparent relay (client request reaches the child, response comes back),
  - autonomous restart when the child exits or its source changes,
  - graceful give-up when the child cannot stay up (a broken build must not
    respawn forever).

The stub child is read from a per-test env var by a `python -c` program.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "tools" / "watch_server.py"

STUB = (
    "import json, os, sys\n"
    "n = 0\n"
    "for line in sys.stdin:\n"
    "    n += 1\n"
    "    try:\n"
    "        rid = json.loads(line).get('id')\n"
    "    except Exception:\n"
    "        rid = None\n"
    "    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': rid, "
    "'result': {'n': n}}) + '\\n')\n"
    "    sys.stdout.flush()\n"
    "    if n >= int(os.environ.get('STUB_EXIT_AFTER', '999')):\n"
    "        break\n"
)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))


def _stub(exit_after: int = 999) -> tuple[list[str], dict[str, str]]:
    env = dict(os.environ)
    env["STUB_EXIT_AFTER"] = str(exit_after)
    return [sys.executable, "-u", "-c", STUB, "stubchild"], env


def _spawn_watcher(extra_args: list[str], env: dict[str, str],
                   watch_extra: list[str] | None = None):
    cmd = [sys.executable, str(WATCH), "--poll", "0.1"]
    if watch_extra:
        cmd += ["--watch", *watch_extra]
    cmd += extra_args
    p = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env)
    return p


def _child_args(child: list[str]) -> list[str]:
    """--child takes one JSON-encoded argv array, so embedded -u/-c survive."""
    return ["--child", json.dumps(child)]


def _drain_stderr(p) -> list[str]:
    lines: list[str] = []
    def go() -> None:
        for line in p.stderr:
            lines.append(line.decode("utf-8", "replace").rstrip())
    t = threading.Thread(target=go, daemon=True)
    t.start()
    return lines


def _read_line(p, timeout: float = 10.0) -> bytes | None:
    """Read one newline-terminated line from p.stdout with a timeout."""
    buf: list[bytes] = []
    def go() -> None:
        buf.append(p.stdout.readline())
    t = threading.Thread(target=go, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None
    return buf[0] if buf else None


def _wait_child_up(err: list[str], timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any("child up" in l for l in err):
            return True
        time.sleep(0.05)
    return False


def _kill(p) -> None:
    try:
        p.stdin.close()
    except OSError:
        pass
    try:
        p.kill()
    except OSError:
        pass
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def test_transparent_relay() -> None:
    child, env = _stub()
    p = _spawn_watcher(_child_args(child), env)
    err = _drain_stderr(p)
    try:
        ok = _wait_child_up(err)
        check("relay: child came up", ok, "\n".join(err))
        req = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        p.stdin.write(json.dumps(req).encode() + b"\n")
        p.stdin.flush()
        line = _read_line(p)
        check("relay: got a response line", line is not None)
        if line:
            resp = json.loads(line.decode())
            check("relay: id echoed", resp.get("id") == 1)
            check("relay: result carries child counter 1",
                  resp.get("result") == {"n": 1})
    finally:
        _kill(p)


def test_child_respawns_after_crash() -> None:
    # The stub exits after one request, so the second response proves a fresh
    # child answered it (its counter resets to 1).
    child, env = _stub(exit_after=1)
    p = _spawn_watcher(_child_args(child), env)
    err = _drain_stderr(p)
    try:
        ok = _wait_child_up(err)
        check("respawn: first child up", ok, "\n".join(err))
        p.stdin.write(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n')
        p.stdin.flush()
        line1 = _read_line(p)
        check("respawn: first response before crash", line1 is not None)
        # Let it crash and the supervisor restart it.
        time.sleep(2.5)
        check("respawn: stderr shows a restart",
              any("restarting" in l or "child up" in l for l in err))
        p.stdin.write(b'{"jsonrpc":"2.0","id":2,"method":"ping"}\n')
        p.stdin.flush()
        line2 = _read_line(p)
        check("respawn: second response after restart", line2 is not None)
        if line2:
            resp2 = json.loads(line2.decode())
            check("respawn: fresh child counter restarts at 1",
                  resp2.get("result") == {"n": 1})
    finally:
        _kill(p)


def test_reload_on_source_change() -> None:
    child, env = _stub()
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "marker.py"
        src.write_text("x = 1\n", encoding="utf-8")
        p = _spawn_watcher(_child_args(child), env, watch_extra=[td])
        err = _drain_stderr(p)
        try:
            ok = _wait_child_up(err)
            check("source: child up", ok, "\n".join(err))
            p.stdin.write(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n')
            p.stdin.flush()
            check("source: response before edit", _read_line(p) is not None)
            src.write_text("x = 2\n", encoding="utf-8")   # trigger the reload
            time.sleep(2.0)
            check("source: stderr shows a reload",
                  any("source changed" in l for l in err))
            p.stdin.write(b'{"jsonrpc":"2.0","id":2,"method":"ping"}\n')
            p.stdin.flush()
            line = _read_line(p)
            check("source: response after reload", line is not None)
            if line:
                # A fresh child restarts its counter at 1.
                check("source: fresh child counter restarts at 1",
                      json.loads(line.decode()).get("result") == {"n": 1})
        finally:
            _kill(p)


def test_gives_up_on_unstartable_child() -> None:
    # A child that exits 1 immediately must not loop forever: the supervisor
    # gives up with exit code 2.
    bad = [sys.executable, "-u", "-c", "import sys; sys.exit(1)", "bad"]
    env = dict(os.environ)
    p = _spawn_watcher(_child_args(bad), env)
    err = _drain_stderr(p)
    try:
        try:
            rc = p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            rc = None
            p.kill()
            p.wait(timeout=5)
        check("giveup: exits non-zero", rc == 2, f"rc={rc}")
        check("giveup: stderr explains the give-up",
              any("giving up" in l for l in err))
    finally:
        _kill(p)


def test_stdout_is_protocol_only() -> None:
    child, env = _stub()
    p = _spawn_watcher(_child_args(child), env)
    _drain_stderr(p)
    try:
        time.sleep(1.0)                  # let the child start
        for i in range(3):
            p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i,
                                      "method": "ping"}).encode() + b"\n")
            p.stdin.flush()
        lines = []
        for _ in range(3):
            line = _read_line(p)
            check("stdout-clean: got line", line is not None)
            if line is not None:
                lines.append(line)
        for raw in lines:
            try:
                json.loads(raw.decode())
                parsed = True
            except ValueError:
                parsed = False
            check("stdout-clean: every line is JSON", parsed, repr(raw))
    finally:
        _kill(p)


def test_real_server_handshake_through_watcher() -> None:
    """The stub tests mechanics; this proves the watcher relays the real
    server.py over a full MCP handshake - all offline (tools/list and
    mmt_version never touch the browser or the network)."""
    env = dict(os.environ)
    p = _spawn_watcher([], env)
    _drain_stderr(p)
    try:
        time.sleep(2.5)             # child cold start (imports, no browser)
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1,
                                  "method": "initialize",
                                  "params": {"protocolVersion": "2025-06-18",
                                             "capabilities": {},
                                             "clientInfo": {"name": "test",
                                                            "version": "1"}}}
                                 ).encode() + b"\n")
        p.stdin.flush()
        line = _read_line(p)
        check("real: initialize answered", line is not None)
        if line:
            init = json.loads(line.decode())
            check("real: protocol negotiated",
                  init.get("result", {}).get("protocolVersion")
                  in ("2024-11-05", "2025-06-18", "2025-03-26"))
        p.stdin.write(b'{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n')
        p.stdin.flush()
        line = _read_line(p)
        check("real: tools/list answered", line is not None)
        if line:
            names = [t["name"] for t in
                     json.loads(line.decode())["result"]["tools"]]
            check("real: mmt_version present", "mmt_version" in names)
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 3,
                                  "method": "tools/call",
                                  "params": {"name": "mmt_version",
                                             "arguments": {}}}).encode()
                      + b"\n")
        p.stdin.flush()
        line = _read_line(p)
        check("real: mmt_version call answered", line is not None)
        if line:
            call = json.loads(line.decode())
            text = call["result"]["content"][0]["text"]
            check("real: mmt_version reports a commit",
                  "loaded_at_commit" in text)
    finally:
        _kill(p)


def test_immediate_initialize_is_not_dropped() -> None:
    """The bug that caused Cline's 60s timeout: the host sends `initialize`
    the instant it connects, racing the watcher's initial child spawn. A frame
    arriving before the child exists must be buffered and replayed - never
    silently dropped - or the host times out the whole connection."""
    child, env = _stub()
    p = _spawn_watcher(_child_args(child), env)
    _drain_stderr(p)
    try:
        # No sleep: write the very first frame immediately, before the watcher
        # has had a chance to spawn the child.
        req = {"jsonrpc": "2.0", "id": 99, "method": "ping"}
        p.stdin.write(json.dumps(req).encode() + b"\n")
        p.stdin.flush()
        line = _read_line(p, timeout=10)
        check("race: initialize answered despite racing the spawn",
              line is not None)
        if line:
            resp = json.loads(line.decode())
            check("race: id preserved", resp.get("id") == 99)
    finally:
        _kill(p)


def main() -> None:
    test_transparent_relay()
    test_child_respawns_after_crash()
    test_reload_on_source_change()
    test_gives_up_on_unstartable_child()
    test_stdout_is_protocol_only()
    test_real_server_handshake_through_watcher()
    test_immediate_initialize_is_not_dropped()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n{passed}/{total} offline assertions passed (watch_server).")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAIL {name}  {detail}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()