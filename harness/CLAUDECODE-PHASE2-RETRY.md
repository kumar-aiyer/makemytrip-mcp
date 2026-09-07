# Phase 2 acceptance run — retry after infrastructure fixes

> **Historical. Executed 2026-09-05 and superseded; kept as the record of what was asked.**
> Two statements in it are now known to be wrong and must not be reused: the hotel figures
> it calls "stay totals" are **per night** (BUG-16), so its H-ARITH line understates a
> 6-night stay by five nights; and it pre-scripted the `kulem` lookup, which means the run
> it produced could not exercise gap-recovery gates GR1/GR2 at all. See
> `harness/runs/2026-09-05/run-log.md` and the Phase 2 entries in `harness/findings.md`.

You are continuing a Phase 2 acceptance run on branch `phase2/acceptance-run` (PR #7).
A previous attempt failed because two MCP tools hung. The fixes are ALREADY APPLIED
but UNCOMMITTED in the working tree. Your first job is to commit them.

## What you must NOT do (read this twice)

1. Do NOT spawn `python -c "from mmt import ..."` scripts to test tools directly.
   Each one creates its own Chrome instance on the wrong profile and takes 30s to start.
   Test tools ONLY through the running MCP server (`makemytrip__mmt_*` tool calls).
2. Do NOT call `sweep_orphans()` or kill Chrome processes. The server manages its own browser.
3. Do NOT re-derive the trip dates. They are: outbound 2026-12-15, return 2026-12-21,
   Dudhsagar 2026-12-19.
4. Do NOT call `mmt_flight_search` more than twice (budget: 2 total). Results are cached.
5. Do NOT reset `.state/`. The registered cab places are a precondition.

## What is already collected (do not re-collect)

- Hotels (5 properties, stay totals for 2026-12-15→21, 2 adults) — in the run log
- Trains: both `not_in_window` (booking_opens 2026-10-16 / 2026-10-22)
- Flight BLR→GOI: 25 itineraries cached; cheapest into GOI = IndiGo 6E 6554, ₹4,367/adult

## What you must do (in order)

### Step 1 — Commit the two hang fixes (they are in the working tree, uncommitted)

```
git add mmt/harvest.py mmt/cabs.py
git commit -m "fix(harvest+cabs): SSE hang and networkidle hang"
git push
```

- `mmt/harvest.py`: removed `await resp.finished()` (SSE streams never close)
- `mmt/cabs.py`: `wait_for="networkidle"` → `"domcontentloaded"` (MMT ad pixels never stop)

The watcher will auto-reload the server child. Wait ~10 seconds after pushing.

### Step 2 — Verify the fixes work through the MCP server

Call `makemytrip__mmt_cab_quote` with origin=`bengaluru`, dest=`goa`, date=`2026-12-15`.
This is the call that hung before. It should now return in ~15-25 s with 10 cabs.
If it times out again, investigate `.state/diagnostics/failures.jsonl` — do NOT
spawn debug scripts.

### Step 3 — Collect the remaining data (one MCP call at a time, sequentially)

- `mmt_flight_search(origin="GOI", dest="BLR", date="2026-12-21", adults=2, cabin="E")`
- `mmt_cab_quote(origin="bengaluru", dest="goa", date="2026-12-15")` (if Step 2 was cached, use `fresh=true`)
- `mmt_cab_quote(origin="bengaluru", dest="goa", date="2026-12-15", trip_type="RT", return_date="2026-12-21")`
- `mmt_cab_find_place(query="kulem")` — this WILL take ~30 s (drives the search form)
- `mmt_cab_quote(origin="goa", dest="kulem", date="2026-12-19")`
- `mmt_cab_quote(origin="panaji", dest="goa", date="2026-12-17")` — local-transport substitute

### Step 4 — Compute the itinerary

Use all collected data. Every MCP number must trace to a tool call. Web-sourced
numbers (Dudhsagar entry fees, meal estimates) must be labeled separately.

**H-ARITH check:** round-trip flights = (out + back) × 2 adults; hotel = stay total
counted once; cab per vehicle; per-person = grand total ÷ 2.

### Step 5 — Generate the PDF

Write a Python script that imports `fpdf2` (or falls back to a plain-text fallback)
and produces `harness/runs/2026-09-05/goa-itinerary.pdf`. Do NOT use a browser.

### Step 6 — Audit and close out

1. Diff `.state/data.json` against `harness/runs/2026-09-05/state-before.json` (expect: `kulem` added).
2. Write the audit into `harness/runs/2026-09-05/run-log.md`.
3. Write `## Run 2026-09-05 — Phase 2` in `harness/findings.md`.
4. Commit everything, push to PR #7.