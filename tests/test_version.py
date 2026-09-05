"""Offline tests for mmt/version.py and the mmt_version tool registration.

No network, no browser, no Playwright. Mirrors what the sync rule
(`.clinerules/mcp-server-sync.md`) does: compares the running record against the
checkout HEAD so a stale server process cannot pass the pre-flight.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mmt import tools            # noqa: E402
from mmt import version as VS    # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))


def test_version_record_shape() -> None:
    v = VS.get_version()
    for key in ("tool", "version", "loaded_at_commit", "loaded_dirty",
                "code_path", "mmt_module_dir", "python", "uptime_s"):
        check(f"version: {key} present", key in v)
    check("version: tool name", v.get("tool") == "mmt_version")
    check("version: code_path is this repo", v.get("code_path") == str(ROOT))
    check("version: version field is a string", isinstance(v.get("version"), str))


def test_loaded_commit_matches_repo_head() -> None:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                         capture_output=True, text=True, timeout=3)
    head = out.stdout.strip()
    v = VS.get_version()
    check("version: loaded_at_commit == repo HEAD",
          v.get("loaded_at_commit") == head,
          f"record={v.get('loaded_at_commit')} head={head}")


def test_tool_registered() -> None:
    check("tools: mmt_version registered", "mmt_version" in tools.TOOLS)
    schema = tools.TOOLS["mmt_version"]["schema"]
    check("tools: mmt_version takes no arguments",
          schema == {"type": "object", "properties": {}, "required": []})
    desc = tools.TOOLS["mmt_version"]["description"]
    check("tools: mmt_version description mentions commit", "commit" in desc)


def test_dirty_flag_is_bool_or_none() -> None:
    v = VS.get_version()
    check("version: loaded_dirty is bool or None",
          v.get("loaded_dirty") is None or isinstance(v.get("loaded_dirty"), bool))


def test_uptime_monotonic() -> None:
    a = VS.get_version()["uptime_s"]
    time.sleep(0.05)
    b = VS.get_version()["uptime_s"]
    check("version: uptime_s is non-decreasing", b >= a)


def test_no_git_checkout_falls_back_gracefully() -> None:
    # Temporarily point the module at a checkout-less directory and re-capture.
    old_dir, old_path = VS._CODE_DIR, VS._CODE_PATH
    try:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            VS._CODE_DIR = root / "mmt"
            VS._CODE_PATH = root
            st = VS._capture()
            check("version: no-git checkout reports not-a-git-checkout",
                  st["loaded_at_commit"] == "not-a-git-checkout")
            check("version: no-git dirty is None", st["loaded_dirty"] is None)
    finally:
        VS._CODE_DIR, VS._CODE_PATH = old_dir, old_path


def main() -> None:
    test_version_record_shape()
    test_loaded_commit_matches_repo_head()
    test_tool_registered()
    test_dirty_flag_is_bool_or_none()
    test_uptime_monotonic()
    test_no_git_checkout_falls_back_gracefully()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n{passed}/{total} offline assertions passed (mmt/version + mmt_version).")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAIL {name}  {detail}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()