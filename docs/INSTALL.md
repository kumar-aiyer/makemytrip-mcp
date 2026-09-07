# Installing

The server is plain **MCP over stdio**, so every host below runs the same `server.py`.

## 0. Prerequisites

- **Python 3.10+** on `PATH` (`python --version`). On Windows, `py -3` also works — see the
  per-host notes.
- **A residential internet connection.** MakeMyTrip's CDN answers datacenter IPs with HTTP
  403. A cloud VM or container will not work regardless of configuration.
- **Chrome or Edge installed**, or be willing to run `python -m playwright install chromium`.

```bash
git clone <your-repo> makemytrip-mcp
cd makemytrip-mcp
python -m pip install playwright
python tools/doctor.py
```

**`doctor.py` is the check to run first.** It answers "will this start on this machine"
in a few seconds - Python version, playwright, a usable Chrome, a writable data folder,
the server importing, and whether MakeMyTrip answers at all from this connection. Every
failure prints the exact command that fixes it, and the exit code is the number of
things still wrong.

`tools/probe.py` is the heavier gate: it drives real searches and prints a PASS/FAIL
table. Run it when you want to confirm live pricing works, not just that the server
starts. If it says *Core hotel pricing: USABLE* you are done. If not,
[docs/RUNBOOK.md](RUNBOOK.md) has the fixes.

---

## 1. Claude Cowork (plugin)

Cowork installs plugins from a `.plugin` file you accept in chat.

```bash
# from the repo root
mkdir -p build/makemytrip-pricing
cp -r server.py mmt skills build/makemytrip-pricing/
cp -r plugin/.claude-plugin plugin/.mcp.json build/makemytrip-pricing/
cd build/makemytrip-pricing
zip -r ../makemytrip-pricing.plugin . -x "*__pycache__*" -x "*.pyc" -x ".state/*"
```

The archive's contents must sit at its **root** (`.claude-plugin/plugin.json`, not
`makemytrip-pricing/.claude-plugin/plugin.json`). Check with `unzip -l`.

Open the `.plugin` file in a Cowork chat and accept it.

`plugin/.mcp.json` declares:

```json
{
  "mcpServers": {
    "makemytrip": {
      "command": "python",
      "args": ["${CLAUDE_PLUGIN_ROOT}/server.py"],
      "env": {
        "MMT_MCP_HOME": "${CLAUDE_PLUGIN_ROOT}/.state",
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

Forward slashes even on Windows. `PYTHONIOENCODING=utf-8` is not optional — the payloads
contain `₹`, and a cp1252 console would kill the server mid-handshake. (`server.py` also
reconfigures its own streams, so this is belt and braces.)

> **Check where plugins actually execute.** If your Cowork plugins run inside a sandboxed
> environment rather than natively on your machine, they will inherit a datacenter IP and be
> refused by MakeMyTrip with 403. Verify before assuming: install, then run
> `mmt_setup_status` and `mmt_selftest`. If they report `blocked`, use the OpenClaw or Claude
> Code route on your laptop instead.

---

## 2. OpenClaw

CLI:

```bash
openclaw mcp add makemytrip \
  --command python \
  --arg /absolute/path/to/makemytrip-mcp/server.py \
  --cwd /absolute/path/to/makemytrip-mcp \
  --env PYTHONIOENCODING=utf-8 \
  --env PYTHONUNBUFFERED=1

openclaw mcp doctor makemytrip --probe
openclaw mcp list
```

Or edit `~/.openclaw/openclaw.json` directly, under `mcp.servers`:

```json5
{
  mcp: {
    servers: {
      makemytrip: {
        command: "python",
        args: ["/absolute/path/to/makemytrip-mcp/server.py"],
        cwd: "/absolute/path/to/makemytrip-mcp",
        transport: "stdio",
        enabled: true,
        connectionTimeoutMs: 20000,
        requestTimeoutMs: 120000,
        env: { PYTHONIOENCODING: "utf-8", PYTHONUNBUFFERED: "1" },
      },
    },
  },
}
```

Raise `requestTimeoutMs` well above the default: a cold start launches a browser and warms a
session, which can take ~20 seconds, and `mmt_cab_find_place` drives a form for up to 30.
A 20-second default will time out on the first call and look like a broken server.

OpenClaw runs stdio servers in its **Gateway process environment** — confirm that process has
the residential network path and can see your browser.

---

## 3. Claude Code

```bash
claude mcp add makemytrip --scope user -- python /absolute/path/to/makemytrip-mcp/server.py
claude mcp list
```

On Windows, if `python` resolves to the Microsoft Store shim, point at the interpreter
explicitly:

```powershell
claude mcp add makemytrip --scope user -- C:/Python312/python.exe C:/path/to/makemytrip-mcp/server.py
```

---

## 4. Claude desktop app

### 4a. As an extension (.mcpb) - the one-click path

```bash
python tools/build_mcpb.py
# -> dist/makemytrip-mcp-<version>.mcpb
```

Then **Claude Desktop → Settings → Extensions → install from file**, and pick that file.
The extension declares a *Data folder* setting, so the device id, saved cab places,
browser profile and call log land wherever you choose (default `~/.makemytrip-mcp`).

The build uses the official `@anthropic-ai/mcpb` packer when `npx` is available, which
validates the manifest against the real schema on the way past, and falls back to a plain
zip otherwise - an `.mcpb` is only a zip with a `manifest.json`.

**Playwright is not bundled.** It is 107 MB, and 102 MB of that is a driver containing a
platform-specific node binary, so bundling it would make a Windows-only file a hundred
times the size of the code it carries. The extension runs the system `python`, so
`python -m pip install playwright` on the target machine is enough. `--vendor` bundles it
anyway for anyone who wants a self-contained, platform-locked build.

That leaves the three things no installer can do for you, all of which `doctor.py`
checks: Python 3.10+, Chrome or Edge installed, and a **residential** connection.

### 4b. By hand

`%APPDATA%\Claude\claude_desktop_config.json` (Windows) or
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "makemytrip": {
      "command": "python",
      "args": ["C:/path/to/makemytrip-mcp/server.py"],
      "env": { "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

Restart the app.

---

## 5. Verify from any host

Ask for `mmt_setup_status`, then `mmt_selftest`. Between them they report whether the browser
launched, whether the session warmed, which tier each endpoint class is using, and which
capabilities currently work.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `MMT_MCP_HOME` | `~/.makemytrip-mcp` | State: device id, saved cab places, browser profile, diagnostics |
| `MMT_HEADLESS` | `0` (Windows) | `1` forces headless (e.g. Linux servers). **Not supported against MakeMyTrip** — Akamai resets HTTP/2 streams from headless browsers. Default is headed on Windows (proven to work). |
| `MMT_BROWSER_CHANNEL` | auto | Force `chrome`, `msedge`, or leave unset for bundled Chromium |
| `MMT_IDLE_TIMEOUT` | `300` | Seconds before an idle browser is closed |
