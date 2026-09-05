# ClaudeCode prompt — finish Phase 1 (flights) and verify

This file is the handoff to a ClaudeCode session for the `makemytrip-mcp` repository. Paste
the block below into ClaudeCode with this repo as the working directory. It is self-contained.

---

## The prompt

Phase 1 of this project's live acceptance testing is complete except one item: **flights**.
Your job is (1) verify the four green ground truths still hold, (2) close the flights open
item through one of the two documented paths, and (3) run the cab-quote end-to-end that was
never exercised. Commit after each passing gate, naming the gate in the message.

### Read first, in this order

- `README.md`, `docs/DESIGN.md`, `docs/API-REFERENCE.md`, `docs/RUNBOOK.md`
- `harness/findings.md` — the complete bug log (BUG-1..BUG-7)
- `harness/prompts/goa-itinerary.md` — the acceptance test the whole effort serves
- `mmt/config.py` — the flights header contract is documented right at the endpoints section

### Ground truths to verify (should all still pass)

1. `python tests/test_parsers.py` → 78/78, no network, no browser.
2. `mmt_setup_status` → `ready: true`, `headless: false`.
3. `mmt_hotel_search("goa", "<today+100ish>", "+6 nights", 2)` → priced hotels, base+tax=all-in,
   `tier_used: 2`. (T2 in-page POST works.)
4. `mmt_train_search("Bengaluru", "goa", "<date>")` → `resolve_station("goa") == "MAO"`;
   a far-future date returns `not_in_window` with `booking_opens`.
5. `mmt_cab_find_place("Panaji")` → exact city place object. (Regional matcher.)

### The open item: flights (BUG-7)

`mmt_flight_search` cannot retrieve live itineraries from automated context on this machine.
The full evidence chain is in `mmt/config.py` and `findings.md`. Do NOT re-run the failed
experiments. Instead, attempt the two documented unblock paths IN ORDER:

**Path A — same-profile real-user warm (cheapest, may fully fix):**
1. The server's Chrome profile is `<state>/chrome-profile`. Launch a *headed* Chrome using
   THAT profile directory (channel=chrome, not bundled): `chrome.exe --user-data-dir=<abs path
   to .state/chrome-profile> https://www.makemytrip.com/flights/`.
2. In that window, behave like a user: search BLR→GOI for a near-future date, let results
   fully render, then close the window. This seeds the Akamai sensor state AND the CORS
   preflight cache (Access-Control-Max-Age) into the profile.
3. Re-run the server's `mmt_flight_search` and check whether the in-page-fetch now succeeds.
4. If the preflight is now granted, wire it back into `mmt/flights.py` (the header set from
   the config.py contract) and add a `harvest_search` that fills the form then fetches.
5. Restart the MCP server, verify live, commit.

**Path B — verified fixture from the user's real browser (always works, fixes the parser):**
1. Ask the user to open `https://www.makemytrip.com/flights/` in their own browser, search
   BLR→GOI (or BLR→GOX for North Goa) for 2026-12-15, open DevTools → Network, filter
   Fetch/XHR, find `search-stream`, right-click → Copy → Copy response.
2. Paste it into `tests/fixtures/flight_stream.json` (trim to ~200 KB if huge).
3. Rewrite `mmt/flights.py::parse_stream` from the VERIFIED field names in that payload.
   Delete the inferred-shape heuristics. Add one offline test per itinerary field you now
   trust (fare, airline, flight_no, depart, arrive, duration, stops).
4. Wire `mmt_flight_search` to report real rolled-up itineraries. Commit.

**Add GOX:** MMT splits Goa into Goa (North) = GOX (Mopa) and Goa (South) = GOI (Dabolim).
The `AIRPORTS` dict only has `goa <- GOI`. Add `goa north`, `mopa` -> `GOX` (and keep
`goa` -> `GOI` as the current default since it is the existing contract).

### Then: cab quote end-to-end (never exercised)

- `mmt_cab_find_place("Bengaluru")` then `mmt_cab_quote("Bengaluru", "goa", "2026-12-15")`.
- Verify: cab_count > 0, distance_km present, each cab base+tax_fees==all_in, per-km derived.
- If quote returns zero cabs for a real route inside the window, THAT is a BUG (not a valid
  empty) - a place object source is broken or the page moved. Log it as BUG-8.

### Finally

- `mmt_selftest` full, record tier/latency readings in `harness/findings.md` under a
  `## Run <date>` entry.
- Update `harness/prompts/goa-itinerary.md` ground-truth 1.4 to whichever of Path A/B (or
  neither) resolved, and reflect it in `docs/RUNBOOK.md` and `mmt_capabilities`.
- Commit each gate. Keep the repo clean, no scratch files.

### Rules

- Read-only server: never touch checkout/cart/login. No credentials. No new tests that hit
  the network.
- Prefer a clear error to a fabricated number. If flights cannot be unblocked, leave
  BUG-7 open and make ABSOLUTELY sure `mmt_flight_search` and `mmt_capabilities` state the
  limitation to the model that calls them. That is an acceptable outcome (it is already
  documented); a silent wrong or fabricated fare is not.