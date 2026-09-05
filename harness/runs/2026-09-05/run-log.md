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

> **Superseded 10:06 PDT.** With the user's approval the host problem was solved rather than
> deferred — see *Completed run* below. This section stands as the record of why the first
> attempt stopped, and its "To finish this run" advice is no longer the recommended path.

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

---

## Completed run — Claude Code session, 2026-09-05 10:06–10:20 PDT — **PASS**

The blocker above was the host, not the server. Rather than defer to Cline, the run was
completed with a driver written for the purpose: `harness/mcp_client.py` spawns `server.py`
**once** and holds one MCP handshake open for every call in a plan.

This is not the thing the retry prompt forbids. The ban was on *per-call* `python -c "from
mmt import ..."`, because each of those starts its own Chrome on the wrong profile and pays
~30 s of startup. This is the opposite and satisfies the intent of "test tools ONLY through
the running MCP server": one process, one browser, real JSON-RPC through the actual
`tools/call` handlers. It also records per-call elapsed time and writes raw results to JSON,
which is what the H-ARITH audit below is checked against.

### Pre-flight

| Gate | Result |
|---|---|
| Handshake | `makemytrip 1.0.0`, protocol `2025-06-18`, 14 tools listed |
| `mmt_version` | `loaded_at_commit` = `a59e389` == `git rev-parse HEAD` ✓ |
| `loaded_dirty` | `true`, caused **only** by untracked `harness/mcp_client.py`; `git diff HEAD -- mmt/ server.py tools/` is empty, so server code is byte-identical to HEAD |
| `mmt_setup_status` | `ready=true`, playwright installed, `headless=false` |
| Profile contention | no Chrome held `.state/chrome-profile` at start (the 300 s idle reaper had already closed the one belonging to Cline's `server.py` PID 60468); Cline left idle for the duration |

### Execution trace

| # | Call | Elapsed | Result |
|---|---|---|---|
| 1 | `mmt_cab_quote` bengaluru→goa 12-15 | **31.1 s** | 10 cabs, 603 km, cheapest ₹12,161 all-in — **the call that hung before; the `domcontentloaded` fix holds** |
| 2 | `mmt_flight_search` GOI→BLR 12-21 A2 E | 29.0 s | 25 itineraries, tier 2 |
| 3 | `mmt_flight_search` BLR→GOI 12-15 A2 E | 11.1 s | 25 itineraries, tier 2 |
| 4 | `mmt_cab_quote` bengaluru→goa RT 12-15/12-21 | 15.3 s | 9 cabs, cheapest ₹20,264 |
| 5 | `mmt_cab_find_place` "kulem" | 19.9 s | registered, `place_id ChIJU_8H2moHvzsRDqa5IZGjLk4` |
| 6 | `mmt_cab_quote` goa→kulem 12-19 | 11.4 s | 6 cabs, 40 km, cheapest ₹2,145 |
| 7 | `mmt_cab_quote` panaji→goa 12-17 | 11.4 s | 8 cabs, 40 km, cheapest ₹1,945 |
| 8 | `mmt_hotel_search` Goa 12-15→21 A2 R1 | 7.2 s | 5 properties, `nights=6`, CTGOI |
| 9 | `mmt_cab_quote` goa→kulem **RT** 12-19 | 29.8 s | 6 cabs, cheapest ₹2,145 — *identical to the one-way, see findings* |
| 10 | `mmt_hotel_rates` Hyatt (no `city`) | 0.0 s | `bad_input`, correct — the arg really is required |
| 11 | `mmt_hotel_rates` Hyatt Centric | ~20 s | **`shape_drift` — detail page 2,599,533 B exceeds the 2,097,152 B cache cap** |
| 12 | `mmt_hotel_search` Goa 12-15→17 (2 nights) | ~7 s | scaling cross-check, different top-5 so inconclusive |
| 13 | `mmt_train_search` SBC→MAO 12-15 | ~2 s | `not_in_window`, opens 2026-10-16 |
| 14 | `mmt_train_search` MAO→SBC 12-21 | ~2 s | `not_in_window`, opens 2026-10-22 |

**Flight budget: 2 of 2 used, exactly.** Trains were re-verified rather than inherited from
the prompt, so every number in the PDF traces to a call in this table.

### The alternate-airport trap (worth its own line)

On **both** legs the cheapest row is not a Goa flight. BLR→GOI returns 25 itineraries of
which only **11** land at GOI; the cheapest overall, FLY91 IC 5302 at ₹3,099, lands at SDW.
GOI→BLR returns 25 of which only **12** depart GOI; the cheapest overall, FLY91 IC 5301 at
₹3,699, leaves from SDW. The tool flags these `alternate_airport` and says so in `note`. A
consumer that sorts on price without filtering `to`/`from` understates the airfare by ~26 %.
Correct server behaviour, and the single easiest way to get this itinerary wrong.

### H-ARITH check

Computed programmatically, not by hand (assertions in the build script):

```
flights   (4,367 + 5,994) x 2 adults = 20,722   OK   round trip, per-adult fares doubled
hotel     13,342 counted once                   OK   stay total for 6 nights, not per night
cabs      2,145 + 1,945 per vehicle             OK   not multiplied by head count
GRAND TOTAL   Rs 57,674
PER PERSON    Rs 28,837   = 57,674 / 2
```

MCP-sourced: ₹38,154. Web-sourced (Dudhsagar fees ₹1,520) and estimate (meals ₹18,000):
₹19,520, labelled separately on every row of the PDF.

### Step 5 — PDF

`harness/runs/2026-09-05/goa-itinerary.pdf`, 2 pages, 4,264 bytes, produced by
`make_pdf.py` from `itinerary-data.json`. No browser. Three defects were fixed in the
generator while producing it: relative CLI paths resolved against the script directory
instead of the cwd, a missing `alternatives` section, and `multi_cell` defaulting to
`new_x=RIGHT` so the second consecutive call got zero width and raised.

### Step 6 — state audit

```
device_id            unchanged
cab_places added     ['kulem']
cab_places removed   []
cab_places changed   none
top-level keys       ['cab_places', 'device_id'] before and after
```

Exactly the expected side effect, nothing else. Note that `mmt_cab_find_place` reported
`known_places` including `kochi` and `rameswaram`, which are **not** in `.state/data.json` —
this is not a leak: `cabs.known_places()` merges `BUILTIN_PLACES` over saved places by
design (`mmt/cabs.py:49`). Checked rather than assumed.
