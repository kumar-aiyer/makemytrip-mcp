# MCP server sync — test the code you are looking at

The `makemytrip` MCP server captures its code path and git commit **once, at process
start**. A server keeps running — and keeps answering tool calls "successfully" — long
after the repo moves forward, serving pre-fix behaviour. Nothing in the MCP protocol
tells you which build you are talking to. `mmt_version` exists to make that checkable.

## Mandatory before any `mmt_*` call in a session

1. Check the server has `mmt_version` in its tool list. **Absent → the server
   predates it and is stale by definition** — restart / re-register it.
2. Run `mmt_version` and compare `loaded_at_commit` with the workspace head:
   `git rev-parse HEAD`.
   - **Match** → proceed.
   - **Mismatch** → the running process was built from older code. Restart the MCP
     server (the session process only reloads when it is actually restarted), then
     re-run `mmt_version` and confirm the match.
3. Check `code_path`. If it is **not** this workspace's repo root, the server was
   registered from another clone — re-register it with absolute paths and an
   **absolute** `MMT_MCP_HOME` pointing at this repo's `.state`.
4. After **any** commit that touches `mmt/`, `server.py`, `tools/` or
   `requirements.txt`, restart the MCP server before doing further live testing.

## If the check fails

Do **not** run Phase 1/2 gates, `tools/probe.py`, or any priced tool call against a
server whose `loaded_at_commit` does not match the checkout. Restart, re-register, re-check.

## Where the version lives

`mmt_version` is the dedicated tool, and the same `version` record is embedded in
`mmt_capabilities` and `mmt_setup_status`, so no single call is the only place to read it.

## When the server runs under the watcher (tools/watch_server.py)

The supervisor keeps the *host* connection alive across child restarts, so the two cases
collapse differently:

- **Code-only changes** (fixing logic behind an existing tool, editing internals): the
  watcher reloads the child automatically. No user action needed — verify with
  `mmt_version`, whose `loaded_at_commit` updates to the new code.
- **Interface changes** (new/renamed tools, schema edits, config/args/env changes): still
  need **one** reconnect — the host snapshots `tools/list` at connect and nothing in the
  session forces a re-fetch. Do not claim a new tool is available until a reconnect has
  happened and `mmt_version` at that new process matches the checkout.

Rule of thumb: **a changed behavior you can smoke-test via an existing tool needs no
reconnect; a changed tool surface always does.**