"""The exact code this server process is running.

Not the same question as what is on disk: the MCP server imports every domain
module once at startup, so a stale process keeps serving old tool behaviour long
after `git commit` moved the repo forward - and nothing in the MCP protocol
surfaces that. The git commit is therefore captured **once at import time**,
because that is the code the process was built from. `mmt_version` returns the
record, and the project rule (`.clinerules/mcp-server-sync.md`) makes comparing
it against the workspace checkout mandatory before trusting any other tool call.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import __version__ as VERSION

_CODE_DIR = Path(__file__).resolve().parent   # .../mmt
_CODE_PATH = _CODE_DIR.parent                 # the checkout root


def _in_git(root: Path) -> bool:
    # A directory for a normal clone, a file for a worktree checkout.
    return (root / ".git").exists()


def _git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=str(root),
                             capture_output=True, text=True, timeout=3.0)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _capture() -> dict[str, Any]:
    """Best-effort facts about the checkout this module was imported from."""
    root = _CODE_PATH
    if not _in_git(root):
        return {"loaded_at_commit": "not-a-git-checkout",
                "loaded_dirty": None,
                "code_path": str(root)}
    commit = _git(root, "rev-parse", "HEAD")
    dirty = _git(root, "status", "--porcelain")
    return {
        "loaded_at_commit": commit or "unknown",
        "loaded_dirty": None if dirty is None else bool(dirty),
        "code_path": str(root),
    }


_STARTED = time.time()
_STATE = _capture()


def get_version() -> dict[str, Any]:
    """Public version record for this running process."""
    return {
        "tool": "mmt_version",
        "version": VERSION,
        "loaded_at_commit": _STATE["loaded_at_commit"],
        "loaded_dirty": _STATE["loaded_dirty"],
        "code_path": _STATE["code_path"],
        "mmt_module_dir": str(_CODE_DIR),
        "python": sys.version.split()[0],
        "server_os": os.name,
        "started_unix": round(_STARTED),
        "uptime_s": round(time.time() - _STARTED),
    }