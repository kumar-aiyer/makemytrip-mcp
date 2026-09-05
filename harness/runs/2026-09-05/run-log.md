# Phase 2 Acceptance Run Log — 2026-09-05

- **Runner:** Cline (self-run per user instruction; see self-run caveat in findings.md)
- **Base commit:** `e5dd08c` (squashed PR #6)
- **Loaded server commit:** `e3abe96` (diff against base is harness-only: PHASE2-REVIEW, PHASE2-TASKS, goa-itinerary.md; server code in `mmt/`, `server.py`, `tools/` is 100% byte-identical)
- **Dates computed (today + 101 days):**
  - Outbound: **2026-12-15** (101 days out; Indian Railways 60-day ARP opens 2026-10-16)
  - Return: **2026-12-21** (107 days out; opens 2026-10-22)
  - Dudhsagar day trip: **2026-12-19**
- **Initial state snapshot:** `harness/runs/2026-09-05/state-before.json` (hash: `2A28863A54D92A8D7AF4B6979B8B559FE72CF85D527BE35E35400466EDD75E81`)
- **Call budget limit:** ≤ 2 flight searches, ≤ 1 retry per call, no sweeping.

## Pre-flight Checklist
- [x] `mmt_version` called: `e3abe96`, clean, server code identical to HEAD
- [x] `mmt_setup_status` called: ready=true
- [x] Offline suites: 112/112 parsers, 19/19 version, 33/33 watch_server
- [x] `.state/data.json` snapshotted

## Execution Trace (in progress)
*(Calls will be recorded here with tool name, arguments, elapsed time, and key returned fields)*

---

## Retry attempt — Claude Code session, 2026-09-05 09:30 PDT — **BLOCKED, run not executed**

Ran against `harness/CLAUDECODE-PHASE2-RETRY.md`. Steps 2–6 could not be attempted:
**the `makemytrip` MCP server is not reachable from a Claude Code session.**

### Step 1 — already satisfied (no action needed)

The two hang fixes were not uncommitted; they had already been committed and pushed as
`eff6b04`, and the branch is level with `origin/phase2/acceptance-run` (0 ahead / 0 behind).
Verified content of that commit:

| File | Change |
|---|---|
| `mmt/harvest.py` | `await resp.finished()` removed from the flight response harvester (SSE streams never close) |
| `mmt/cabs.py` | `wait_for="networkidle"` → `"domcontentloaded"` on the cab listing fetch (MMT ad pixels never stop) |

### Steps 2–6 — blocked

The prompt requires every tool exercise to go through `makemytrip__mmt_*` tool calls, and
explicitly forbids the only local alternative (ad-hoc `python -c` scripts, which each start
their own Chrome on the wrong profile). Neither path was available:

| Check | Result |
|---|---|
| `makemytrip__mmt_*` in the session tool list | absent |
| Deferred-tool search for `mmt_*` / `makemytrip` | no match |
| `.mcp.json` in repo | does not exist |
| `~/.claude.json` top-level `mcpServers` | `{}` |
| `~/.claude.json` → project `c:/Users/kumar/projects/claudecodeprojects/makemytrip-mcp` → `mcpServers` | `{}` |
| Cline (`saoudrizwan.claude-dev` 4.1.17) | installed; its global `cline_mcp_settings.json` reads `{}`, so 4.x keeps the registration elsewhere — the live watcher is the proof it holds one |
| Watcher process | **running**, PID 160536 (`tools/watch_server.py`), child `server.py` PID 60468 |
| Watcher parent | PID 136328 = VS Code extension-host utility process (started 07:09 PDT) |

So the server is alive and healthy — but it is a **stdio** server whose pipes are held by
the VS Code extension host that launched it. A Claude Code session has no channel to those
pipes, and no registration of its own. This is the runtime constraint already recorded from
Phase 1 ("no MCP registration in Claude Code"), now confirmed against a live server.

Registering it mid-session would not have helped either:
- the host snapshots `tools/list` at connect and nothing re-fetches it in-session
  (the interface caveat logged in the dev-infra run), so new tools need a reconnect; and
- a second `server.py` would contend with PID 60468 for the same Chrome profile — the
  locked-profile hazard from finding #3 of Phase 1.

### Evidence the run did not touch anything

- `.state/data.json` `cab_places` is still exactly `{goa, panaji, bengaluru}` — **no `kulem`**,
  which is the Step 3 side effect. State is byte-identical to `state-before.json`.
- `.state/diagnostics/failures.jsonl` is unchanged at 34 rows; the newest is still the
  pre-fix cab hang from the previous attempt:
  `2026-09-05T08:47:50-0700 cab_page transport TargetClosedError ['tier1:shape_drift', 'tier2:TargetClosedError']`.
- No flight searches were spent. The ≤ 2 budget is fully intact.

### What was produced instead

`harness/runs/2026-09-05/make_pdf.py` — Step 5's generator, written and smoke-tested. It is
data-driven by design: it reads `itinerary-data.json` and renders `goa-itinerary.pdf` via
fpdf2 (installed, 2.8.8), falling back to a `.txt` sibling if fpdf2 is missing. No browser.
Every cost row must carry `label` / `amount` / `source`; the loader hard-fails on a row that
omits `source`, so the generator cannot emit an unattributed number, and it exits 1 with
"Step 3 must run first" when the data file is absent. It has never been run against real
data — **no `goa-itinerary.pdf` exists**, deliberately.

### To finish this run

Re-run the retry prompt from **Cline**, which is the host that owns the live watcher
(and the runner of record for this run log). Steps 2–6 are
untouched and the preconditions (registered cab places, cached flight results, unspent
search budget) all still hold. Alternatively, register the server for Claude Code
(`claude mcp add makemytrip -- python <abs>/tools/watch_server.py`), close the Cline
connection so the two do not fight for the Chrome profile, and start a fresh session.
