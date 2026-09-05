# Live test protocol (run from Cline via the makemytrip MCP tools)

This doc is the repeatable live-acceptance run. Run the phases in order. Each step lists
the tool call; **verify** each result before moving on. Log any bug into `findings.md`.

Preconditions: the `makemytrip` server is registered in Cline's
`cline_mcp_settings.json` and the `mmt_*` tools are visible (reconnect/restart Cline's
MCP if they are not).

Politeness: one call at a time, no loops, no scheduled polling. This whole protocol is
~15-20 calls and is within the README's conversational-usage guidance.

---

## Phase 0 — Environment (answers: does the browser stack get past Akamai here?)

1. `mmt_setup_status` → **DONE 2026-09-05**: `ready: true`, `headless: false`. (BUG-1 fixed.)
2. `mmt_selftest quick` → sanity check of tier/health. Run again before Phase 2 to confirm
   nothing regressed.

## Phase 1 — Core hotel path

3. `mmt_capabilities` — **DONE**: booking windows + known_gaps confirmed.
4. `mmt_hotel_search(city="goa", check_in="2026-12-15", check_out="2026-12-21", adults=2, limit=5)`
   - **DONE**: 5 priced hotels. Hyatt Centric base=11,500 tax=1,842 all_in=13,342 (6N),
     tier_used=2. `base + tax == all_in` clean on every row.
5. `mmt_hotel_rates` for a picked property → still OBEY: room plans with base/tax/all-in.
6. `mmt_price_itinerary(stays=[...])` for two legs → still OBEY: server-side `total` == sum.

## Phase 2 — Trains & cabs

7. `mmt_train_search(origin="Bengaluru", dest="goa", date="2026-12-15")`
   - **DONE**: not_in_window, route SBC-MAO, booking_opens=2026-10-16. (BUG-4 fixed.)
8. `mmt_station_city(origin="SBC", dest="MAO")` → **TO DO**: confirm city codes flow.
9. `mmt_cab_find_place(query="goa")` and `("Panaji")`
   - **DONE**: places registered. (BUG-5/6 fixed.)
10. `mmt_cab_quote(origin="bengaluru", dest="goa", date="<today+60..200>")`
    - **TO DO (handed to Phase 1 closure)**: places are registered; the quote was never run.
    - Verify `cab_count > 0`, `distance_km` present, `base + tax_fees == all_in`, per-km.
    - Zero cabs for a real route inside the window = BUG (log as BUG-8).

## Phase 2b — Flights (the open item, BUG-7)

- `mmt_flight_search(origin="BLR", dest="GOI", date="2026-12-15")` → **DONE (blocked)**:
  returns an honest blocked/experimental result. Unblock paths in
  `harness/CLAUDECODE-PHASE1.md` (manual profile warm) or a captured fixture.

## Phase 3 — Error taxonomy

9. `mmt_hotel_search(city="not-a-city", ...)` → kind `bad_input`, lists known cities.
10. `mmt_train_search(origin="MDU", dest="MS", date="not-a-date")` → kind `bad_input`.
11. `mmt_cab_quote(origin="nosuchplace", ...)` → kind `unregistered_place`, names the remedy.
12. `mmt_cab_quote(origin="kochi", dest="rameswaram", date="<ok>", trip_type="RT")`
    without `return_date` → kind `bad_input`.
13. After each error, the server must still respond to a normal call (alive check).
    → Mostly covered across the live work; sweep again at Phase 2 close.

## Phase 4 — Claude-shaped composite (the acceptance test)

The full Phase 2 protocol is `harness/PHASE2-TASKS.md` — run the canonical prompt in a fresh
Cline session with a reasoning model and audit against the 19-point checklist in
`harness/prompts/goa-itinerary.md`.

---

## Report

After the run, note in `findings.md` any deviation. If everything passes, drop a `## Run
<date>` entry with phase results and tier/latency readings.