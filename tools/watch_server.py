#!/usr/bin/env python3
"""MCP server supervisor for live development.

A stdio MCP host (Cline, Claude Code, the desktop app) launches one process per MCP
server and, once that process exits, does not reliably respawn it - so a crash or a
stale build silently kills the capability until a human reconnects. This wrapper is
what the host launches instead of the raw server. It keeps the MCP stdio boundary
alive and owns a real server.py as its child, restarting that child whenever it
exits or the server's source changes. The agent can therefore develop the server
from inside a session: edit code, the child reloads, and the existing tools answer
again - no user reload - because the host is still talking to this same process.

Transparency: stdin and stdout pass straight through, unexamined and unreformatted,
in binary (MCP frames are newline-delimited JSON; text mode would mangle line
endings on Windows). Diagnostics go to stderr only - stdout carries the protocol
and nothing else, which is the contract every stdio MCP server must honour.

Interface changes (new/renamed tools, schema edits) still need ONE host reconnect,
because the host snapshots tools/list at connect. The child re-captures its git
commit at import, so `mmt_version` reports the freshly loaded code after every
restart.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHILD = [sys.executable, "-u", str(REPO_ROOT / "server.py")]

# A child that dies this many times, each within RAPID_WINDOW of its start, means
# the build is broken - respawning forever would only mask it. Give up instead.
RAPID_FAILURES = 3
RAPID_WINDOW = 3.0        # seconds
BASE_BACKOFF = 0.2        # seconds, doubled per consecutive rapid failure
MAX_BACKOFF = 5.0


def _log(msg: str) -> None:
    print(f"[watcher] {msg}", file=sys.stderr, flush=True)


def _iter_watch_files(paths: list[Path]):
    """A file, or every *.py under a directory - de-duplicated, sorted."""
    seen: set[Path] = set()
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.rglob("*.py")):
                if f not in seen:
                    seen.add(f)
                    yield f
        elif p not in seen:
            seen.add(p)
            yield p


def _snapshot(paths: list[Path]) -> dict[str, tuple[int, int]]:
    """mtime+size per watched file -> detect source edits without a dependency."""
    snap: dict[str, tuple[int, int]] = {}
    for p in _iter_watch_files(paths):
        try:
            st = p.stat()
        except OSError:
            continue
        snap[str(p)] = (st.st_mtime_ns, st.st_size)
    return snap


class _Pump(threading.Thread):
    """Copy src -> dst until EOF, line-streamed in binary.

    MCP frames are newline-delimited JSON, so a line per read is the faithful
    unit (and, unlike `read(n)`, never blocks waiting to fill a buffer).
    """

    def __init__(self, src, dst, name: str, lock: threading.Lock):
        super().__init__(daemon=True, name=name)
        self.src = src
        self.dst = dst
        self.wlock = lock

    def run(self) -> None:
        try:
            for line in self.src:
                with self.wlock:
                    self.dst.write(line)
                    self.dst.flush()
        except (BrokenPipeError, OSError):
            pass


class _Watcher:
    def __init__(self, child_cmd: list[str], watch_paths: list[Path],
                 poll: float):
        self.child_cmd = list(child_cmd)
        self.watch_paths = list(watch_paths)
        self.poll = max(0.05, poll)
        self.child = None
        self.out_lock = threading.Lock()
        self._pending: list[bytes] = []
        self._pending_lock = threading.Lock()
        self._failures = 0
        self._last_start = 0.0
        self._gone = False

    # -- child lifecycle ----------------------------------------------------

    def start_child(self, delay: float = 0.0, reason: str = "start") -> None:
        if delay:
            time.sleep(delay)
        if self._gone:
            return
        self._last_start = time.monotonic()
        child = subprocess.Popen(
            self.child_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,          # child diagnostics land on our stderr, not stdout
            bufsize=0,
        )
        _Pump(child.stdout, sys.stdout.buffer, "child->client",
              self.out_lock).start()
        # Publish the child and flush any client frames that arrived while no
        # child was running (the initial handshake races this spawn; a
        # crash-reload gap can too). All of this happens under the same lock
        # write_client uses, so an old buffered frame can never be overtaken by
        # a newer direct write to the just-published child.
        with self._pending_lock:
            pending = self._pending
            self._pending = []
            self.child = child
        for frame in pending:
            self.write_client(frame)
        _log(f"child up pid={child.pid} ({reason})")

    def stop_child(self) -> None:
        old = self.child
        self.child = None
        if old is None or old.poll() is not None:
            return
        try:
            old.stdin.close()
        except OSError:
            pass
        try:
            old.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            try:
                old.terminate()
                old.wait(timeout=2.0)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    old.kill()
                except OSError:
                    pass
        try:
            old.stdout.close()
        except OSError:
            pass
        _log(f"child stopped exit={old.returncode}")

    def write_client(self, data: bytes) -> None:
        """Client stdin -> current child stdin.

        If no child is up yet (the initial spawn races the very first frames,
        and a crash-reload gap can too), the frame is buffered and flushed once
        the next child starts rather than being dropped - a dropped initialize
        would make the host time out the connection.
        """
        with self._pending_lock:
            c = self.child
            if c is None or c.poll() is not None:
                self._pending.append(data)
                return
        try:
            c.stdin.write(data)
            c.stdin.flush()
        except (BrokenPipeError, OSError):
            with self._pending_lock:
                self._pending.append(data)

    # -- supervision --------------------------------------------------------

    def check(self) -> bool:
        """True = keep running, False = give up (child is terminally broken)."""
        c = self.child
        if c is None:
            return True
        rc = c.poll()
        if rc is None:                      # alive
            if time.monotonic() - self._last_start > RAPID_WINDOW:
                self._failures = 0
            return True
        # Exited. A short-lived start counts as a rapid failure; a death after a
        # healthy life resets the counter to one.
        if time.monotonic() - self._last_start <= RAPID_WINDOW:
            self._failures += 1
        else:
            self._failures = 1
        if self._failures >= RAPID_FAILURES:
            _log(f"child exited {self._failures}x within {RAPID_WINDOW:.0f}s "
                 "of starting - giving up; fix the build then reconnect")
            self._gone = True
            return False
        backoff = min(BASE_BACKOFF * (2 ** (self._failures - 1)), MAX_BACKOFF)
        _log(f"child exited rc={rc}; restarting in {backoff:.1f}s "
             f"(rapid-failure {self._failures}/{RAPID_FAILURES})")
        self.start_child(delay=backoff, reason="crash-restart")
        return True

    def reload_if_source_changed(self, snap: dict) -> dict:
        fresh = _snapshot(self.watch_paths)
        if fresh == snap:
            return snap
        _log("source changed; reloading child")
        self.stop_child()
        self.start_child(delay=0.2, reason="source-change")
        return fresh


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run server.py as a supervised, self-reloading child.")
    ap.add_argument("--child", type=json.loads, default=DEFAULT_CHILD,
                    help="JSON array of argv for the supervised command "
                         "(default: [sys.executable, '-u', repo/server.py])")
    ap.add_argument("--watch", nargs="*", default=None,
                    help="extra files/dirs to watch (repo server.py and mmt/ "
                         "are always watched)")
    ap.add_argument("--poll", type=float, default=1.0,
                    help="seconds between source-watch polls (default: 1.0)")
    args = ap.parse_args(argv)

    watch = [REPO_ROOT / "server.py", REPO_ROOT / "mmt"]
    if args.watch:
        watch += [Path(p) for p in args.watch]

    watcher = _Watcher(args.child, watch, args.poll)
    snap = _snapshot(watch)

    def feed() -> None:
        src = sys.stdin.buffer
        try:
            for line in src:
                if not line:
                    break
                watcher.write_client(line)
        finally:
            stdin_eof.set()

    stdin_eof = threading.Event()
    threading.Thread(target=feed, daemon=True, name="client->child").start()
    _log(f"watch_server up; child={' '.join(args.child)}; "
         f"watching {len(snap)} files; poll={args.poll}s")
    watcher.start_child(reason="initial")

    def shutdown() -> None:
        # Do NOT close stdin here: the feeder thread is blocked reading it and
        # closing it from another thread aborts the process on Windows. The
        # feeder is a daemon - os._exit below abandons it wholesale.
        watcher._gone = True
        try:
            watcher.stop_child()
        except OSError:
            pass

    exit_code = 0
    try:
        while not watcher._gone and not stdin_eof.is_set():
            if not watcher.check():
                exit_code = 2
                break
            snap = watcher.reload_if_source_changed(snap)
            time.sleep(watcher.poll)
    except KeyboardInterrupt:
        _log("shutting down")
    finally:
        shutdown()

    _log(f"watch_server exiting ({exit_code})")
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except OSError:
        pass
    # Skip interpreter finalization. The stdin feeder and stdout pumps are daemon
    # threads blocked on OS pipes; Python's shutdown crashes or mangles the exit
    # code trying to acquire their locks on Windows. Every protocol frame was
    # already flushed, so the OS exit code is the only thing left to preserve.
    os._exit(exit_code)


if __name__ == "__main__":
    sys.exit(main())