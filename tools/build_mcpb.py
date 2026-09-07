#!/usr/bin/env python3
"""Package the server as a Claude Desktop extension (.mcpb).

    python tools/build_mcpb.py                 -> dist/makemytrip-mcp-<version>.mcpb
    python tools/build_mcpb.py --vendor        -> also bundles playwright (see below)

An .mcpb is a zip of the server plus a manifest.json that a desktop host reads to
install it in one click, instead of the user hand-editing claude_desktop_config.json
with absolute paths.

**Playwright is deliberately not bundled by default.** It is 107 MB, of which 102 MB is a
driver containing a platform-specific node binary - so vendoring it would produce a
Windows-only bundle roughly a hundred times the size of the code it carries. The manifest
runs the server with the system `python`, so a playwright installed with pip resolves
normally. That leaves one `pip install` for the user, which is not the binding constraint
here: this server already needs Chrome installed and a residential connection, and it is
built to start without playwright and say what to install. `--vendor` is there for anyone
who wants a self-contained bundle and accepts that it only works on the platform that
built it.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PAYLOAD = ("server.py", "mmt", "skills")
EXCLUDE = {"__pycache__", ".state", ".git"}


def manifest(version: str) -> dict:
    return {
        "manifest_version": "0.3",
        "name": "makemytrip-mcp",
        "display_name": "MakeMyTrip pricing",
        "version": version,
        "description": "Live Indian travel prices - flights, trains, cabs and hotels - "
                       "read from MakeMyTrip through a real browser.",
        "long_description": (
            "Prices one journey by flight, train and cab at once on a comparable "
            "footing, and searches hotels by city and date range. Read-only: there is "
            "no booking, cart, payment or login path anywhere in it.\n\n"
            "Requirements this cannot install for you: Python 3.10+, the playwright "
            "package (`python -m pip install playwright`), Google Chrome or Edge, and a "
            "residential internet connection - MakeMyTrip's CDN refuses datacenter IPs, "
            "so a VPN or cloud host will not work. Run `python tools/doctor.py` from the "
            "repo to check all four at once."),
        "author": {"name": "Kumar Aiyer"},
        "server": {
            "type": "python",
            "entry_point": "server/server.py",
            "mcp_config": {
                "command": "python",
                "args": ["${__dirname}/server/server.py"],
                "env": {
                    "PYTHONPATH": "${__dirname}/server;${__dirname}/server/lib",
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUNBUFFERED": "1",
                    "MMT_MCP_HOME": "${user_config.state_dir}",
                },
            },
        },
        "user_config": {
            "state_dir": {
                "type": "directory",
                "title": "Data folder",
                "description": "Where the device id, saved cab places, browser profile "
                               "and call log are kept. Local only; delete it to reset.",
                "default": "${HOME}/.makemytrip-mcp",
                "required": False,
            },
        },
        "compatibility": {"runtimes": {"python": ">=3.10"}},
        "keywords": ["travel", "india", "flights", "trains", "hotels", "pricing"],
        "license": "see repository",
    }


def copy_payload(dest: pathlib.Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for item in PAYLOAD:
        src = ROOT / item
        if not src.exists():
            print(f"  ! missing {item}, skipped")
            continue
        if src.is_dir():
            shutil.copytree(src, dest / item,
                            ignore=shutil.ignore_patterns(*EXCLUDE, "*.pyc"))
        else:
            shutil.copy2(src, dest / item)
        print(f"  + {item}")


def vendor(dest: pathlib.Path) -> None:
    lib = dest / "lib"
    print("  vendoring playwright into server/lib (platform-specific, ~107 MB)")
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright",
                    "--target", str(lib), "--quiet"], check=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor", action="store_true",
                    help="bundle playwright; makes the .mcpb platform-specific")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-npx", action="store_true",
                    help="skip the official packer even if npx is available")
    a = ap.parse_args(argv[1:])

    from mmt import __version__ as version

    build = ROOT / "build" / "mcpb"
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)

    print(f"building makemytrip-mcp {version}")
    (build / "manifest.json").write_text(
        json.dumps(manifest(version), indent=2) + "\n", encoding="utf-8")
    print("  + manifest.json")
    copy_payload(build / "server")
    if a.vendor:
        vendor(build / "server")

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    out = pathlib.Path(a.out) if a.out else dist / f"makemytrip-mcp-{version}.mcpb"

    # Prefer the official packer when it is reachable - it validates the manifest against
    # the real schema on the way past, which is worth more than trusting this file's
    # reading of it. Falls back to a plain zip, which is all an .mcpb is.
    packed = False
    if not a.no_npx:
        try:
            r = subprocess.run(["npx", "-y", "@anthropic-ai/mcpb", "pack",
                                str(build), str(out)],
                               capture_output=True, text=True, timeout=300, shell=True)
            packed = r.returncode == 0 and out.exists()
            print("  packed with @anthropic-ai/mcpb" if packed else
                  f"  npx pack unavailable ({r.returncode}); using a plain zip")
        except Exception as e:
            print(f"  npx pack unavailable ({type(e).__name__}); using a plain zip")
    if not packed:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(build.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(build).as_posix())

    size = out.stat().st_size
    print(f"\nwrote {out}  ({size / 1e6:.1f} MB)")
    if not a.vendor:
        print("playwright is NOT bundled - the host runs the system python, so\n"
              "`python -m pip install playwright` on the target machine is required.")
    print("Install: Claude Desktop > Settings > Extensions > install from file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
