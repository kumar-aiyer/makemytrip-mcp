#!/usr/bin/env python3
"""Is this machine able to run the server? One command, plain answers.

    python tools/doctor.py

Written for someone installing this, not for someone developing it. Every failure
prints the exact command or action that fixes it, and the exit code is the number of
things still wrong, so a script can gate on it.

It deliberately does NOT price anything. `tools/probe.py` is the live gate that drives
real searches; this only answers "will it start, and does it have what it needs".
"""
from __future__ import annotations

import os
import pathlib
import platform
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

OK, WARN, BAD = "  ok  ", " warn ", " FAIL "
problems: list[str] = []


def say(state: str, label: str, detail: str = "") -> None:
    print(f"[{state}] {label}" + (f"\n         {detail}" if detail else ""))


def fail(label: str, fix: str) -> None:
    say(BAD, label, "fix: " + fix)
    problems.append(f"{label} -> {fix}")


def check_python() -> None:
    v = sys.version_info
    if v < (3, 10):
        fail(f"Python {v.major}.{v.minor} is too old (3.10+ required)",
             "install Python 3.10 or newer and re-run with it")
    else:
        say(OK, f"Python {v.major}.{v.minor}.{v.micro} on {platform.system()}")


def check_platform() -> None:
    system = platform.system()
    if system == "Linux":
        say(WARN, "Linux detected",
            "MakeMyTrip's CDN blocks headless browsers and this server needs a headed "
            "one. Windows and macOS desktops are the supported targets.")
    elif system not in ("Windows", "Darwin"):
        say(WARN, f"{system} is untested", "Windows and macOS are the tested platforms.")


def check_playwright() -> None:
    # Ask the server's own check, so the doctor can never disagree with the thing it is
    # diagnosing. playwright exposes no __version__ attribute; the version comes from
    # package metadata.
    from mmt.session import playwright_available
    ok, why = playwright_available()
    if not ok:
        fail(f"playwright is not usable ({why})", "python -m pip install playwright")
        return
    try:
        import importlib.metadata as md
        version = md.version("playwright")
    except Exception:
        version = "unknown version"
    say(OK, f"playwright {version} installed")


def check_browser() -> None:
    try:
        from mmt.session import find_chrome
        found = find_chrome()
    except Exception:
        found = None

    if not found:
        # fall back to a direct look, so a rename inside mmt.session cannot break this
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
        found = next((p for p in candidates if p and os.path.exists(p)), None)
        found = found or shutil.which("google-chrome") or shutil.which("chromium")

    if found:
        say(OK, "browser found", str(found))
    else:
        fail("no Chrome or Edge found",
             "install Google Chrome, or run: python -m playwright install chromium")


def check_state() -> None:
    from mmt import config as C
    try:
        C.STATE_DIR.mkdir(parents=True, exist_ok=True)
        probe = C.STATE_DIR / ".doctor-write-test"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
    except Exception as e:
        fail(f"cannot write to {C.STATE_DIR}",
             "set MMT_MCP_HOME to a writable absolute path")
        return
    origin = "MMT_MCP_HOME" if os.environ.get("MMT_MCP_HOME") else "default"
    say(OK, f"state directory writable ({origin})", str(C.STATE_DIR))
    print(f"         it will hold: a device id and saved cab places (data.json), a "
          f"Chrome\n         profile with makemytrip.com cookies (chrome-profile/), and "
          f"a log of\n         every tool call with its results (diagnostics/). All "
          f"local; nothing\n         is sent anywhere but MakeMyTrip. Delete the folder "
          f"to reset.")


def check_server() -> None:
    try:
        from mmt import tools as T
        import server
        listed = len(server.tool_list()["tools"])
        hidden = sum(1 for s in T.TOOLS.values() if s.get("hidden"))
        say(OK, f"server imports; {listed} tools offered, {hidden} internal")
    except Exception as e:
        fail(f"the server does not import: {type(e).__name__}: {e}",
             "run from the repo root, and check the Python version above")


def check_network() -> None:
    import urllib.error
    import urllib.request
    req = urllib.request.Request(
        "https://www.makemytrip.com/", method="HEAD",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            say(OK, f"makemytrip.com reachable (HTTP {r.status})")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            fail(f"makemytrip.com answered HTTP {e.code}",
                 "this is what a datacenter IP gets. Run from a home connection - "
                 "a VPN, VM or cloud host will not work.")
        else:
            say(WARN, f"makemytrip.com answered HTTP {e.code}",
                "not necessarily fatal; the server drives a real browser, not this "
                "plain request.")
    except Exception as e:
        fail(f"cannot reach makemytrip.com: {type(e).__name__}",
             "check the internet connection and any proxy settings")


def main() -> int:
    print("makemytrip-mcp doctor\n" + "-" * 60)
    for fn in (check_python, check_platform, check_playwright, check_browser,
               check_state, check_server, check_network):
        try:
            fn()
        except Exception as e:                       # a broken check is not a verdict
            say(WARN, f"{fn.__name__} could not run: {type(e).__name__}: {e}")
    print("-" * 60)
    if problems:
        print(f"{len(problems)} thing(s) to fix:\n")
        for p in problems:
            print("  - " + p)
        print("\nThen re-run: python tools/doctor.py")
        return len(problems)
    print("Ready. Register the server with your host - see docs/INSTALL.md - then ask\n"
          "it for mmt_setup_status to confirm the browser launches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
