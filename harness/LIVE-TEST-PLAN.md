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

1. `mmt_setup_status`
   - Expect: `ready: true`, a real browser (chrome/msedge), warmup result present.
   - If `ready: false`: read the `next_steps` and do them (e.g. `python -m playwright
     install chromium`).
2. `mmt_selftest quick`
   - Expect: `hotel_search` check `ok: true`; `router_health.hotel_api.tier_used` sane.
   - If the browser stack 403s from this machine at every tier, stop: that is an
     environment/network finding, not a code bug.

## Phase 1 — Core hotel path

3. `mmt_capabilities` — expect booking windows listed.
4. `mmt_hotel_search(city="Kochi", check_in="<today+30>", check_out="<today+32>", limit=3)`
   - Verify: every priced hotel has `base_inr`/`tax_inr`/`all_in_inr` with
     `base + tax == all_in`; a per-night figure is present.
5. Pick the cheapest hotel's `id`, then `mmt_hotel_rates(hotel_id=..., city="Kochi",
   check_in=..., check_out=...)`
   - This exercises the T2 page-render path (`_t2_get`). Verify room plans parsed with
     base/tax/all-in arithmetic.
6. `mmt_price_itinerary(stays=[{...}])` for two legs with the SAME dates.
   - Verify the server-side `total` == sum of the legs.

## Phase 2 — Trains & cabs

7. `mmt_train_search(origin="MDU", dest="MS", date="<today+30>")`
   - Verify trains parse with per-class `availablityStatus`, `confirm_probability_pct`.
8. `mmt_train_search(origin="MDU", dest="MS", date="<today+90>")`
   - Verify kind == `not_in_window` and a `booking_opens` field is present.
9. `mmt_station_city(origin="MDU", dest="MS")` — verify both city codes returned.
10. `mmt_cab_quote(origin="kochi", dest="rameswaram", date="<today+200>")`
    - Verify `cab_count > 0`, `distance_km` present, each cab has
      `base_inr + tax_fees_inr == all_in_inr` and a per-km figure.

## Phase 3 — Error taxonomy

11. `mmt_hotel_search(city="not-a-city", ...)` → kind `bad_input`, lists known cities.
12. `mmt_train_search(origin="MDU", dest="MS", date="not-a-date")` → kind `bad_input`.
13. `mmt_cab_quote(origin="nosuchplace", ...)` → kind `unregistered_place`, names the
    remedy (`mmt_cab_add_place`).
14. `mmt_cab_quote(origin="kochi", dest="rameswaram", date="<ok>", trip_type="RT")`
    without `return_date` → kind `bad_input` (RT requires return_date).
15. After each error, the server must still respond to a normal call (alive check).

## Phase 4 — Claude-shaped composite

16. Answer as a user: *"What would four nights in Kochi in December cost, and how does
    the cab from Kochi to Rameswaram compare?"*
    - Do this the way a real model would (call `mmt_capabilities` first, then search,
      then the cab).
    - Audit the answer: base AND tax quoted separately; stay-total vs per-night not
      confused; limitations stated plainly; no empty result reported as "nothing found".

---

## Report

After the run, note in `findings.md` any deviation. If everything passes, drop a `## Run
<date>` entry with phase results and tier/latency readings.