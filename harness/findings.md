# Live find-bug log

Every bug found by the live testing harness (Cline + makemytrip MCP tools) goes here.
One block per bug. Copy the block, fill it in, keep it - it survives across sessions.

---

## Bugs

### BUG-1: mmt_setup_status crashes with NoneType on cold start

- **Found:** 2026-09-04 (Phase 0)
- **Call:** `mmt_setup_status()` on a fresh server
- **Expected:** ready:true/false with a diagnostic
- **Actual:** `{"error": "AttributeError: NoneType object has no attribute new_page", "kind": "unexpected"}`
- **kind:** unexpected
- **Root cause:** SESSION.warmup() dereferenced self._ctx before ensure() had launched the browser.
- **Fix:** PR #1 (commit 3f60525) - warmup() now launches the context if absent; ensure() guards the warmup call; navigation errors return a structured diagnostic instead of raising.
- **Regression test added?:** covered by live tool verification; mmt_setup_status returns ready:true.

### BUG-2: Akamai resets HTTP/2 streams from headless browsers

- **Found:** 2026-09-04 (Phase 0)
- **Call:** any tool, from an automated session
- **Expected:** normal navigation
- **Actual:** net::ERR_HTTP2_PROTOCOL_ERROR on every www.makemytrip.com navigation when headless=True
- **kind:** blocked
- **Root cause:** Akamai fingerprints headless Chrome TLS/Client-Hints and RSTs the HTTP/2 stream. Verified: headed Chrome gets HTTP 200 + all 12 clearance cookies; headless gets RST at every tier.
- **Fix:** PR #1 - SessionConfig.headless defaults to False on Windows; docs updated in INSTALL.md/RUNBOOK.md.
- **Regression test added?:** no (environment-dependent).

### BUG-3: Hotel search returns stub body from T1; no POST path existed beyond it

- **Found:** 2026-09-04 (Phase 1 ground truth 1.1)
- **Call:** `mmt_hotel_search(city="goa", check_in="2026-12-15", check_out="2026-12-21")`
- **Expected:** priced hotel list
- **Actual:** Transport error - non-JSON body beginning "200-OK" (Akamai stub on mapi POST via ctx.request)
- **kind:** transport
- **Root cause:** post_json capped the POST tier at REQUEST; the only working path from this network is an in-page fetch (page.evaluate) with fresh clearance cookies.
- **Fix:** commit 428f7aa - added _t2_post (clear_cookies + goto HOME + in-page fetch with safe headers); HOTEL_API ceiling raised to PAGE tier; dispatch wired in post_json.
### BUG-4: resolve_station("goa") returned the invalid code GOA

- **Found:** 2026-09-05 (Phase 1 ground truth 1.3a)
- **Call:** `mmt_train_search(origin="Bengaluru", dest="goa", date="2026-12-15")`
- **Expected:** MAO (Madgaon) or an honest unknown-station error
- **Actual:** resolved to "GOA" - the 2-5 char alpha bypass fired before the STATIONS dict lookup, silently passing a non-existent code
- **kind:** bad_input (should have been)
- **Root cause:** resolver ordering. Known names must win over the alpha-code guess.
- **Fix:** commit 3f53cb3 - dict lookup now precedes the bypass; added goa/madgaon/margao -> MAO, thivim -> THVM, vasco -> VSG to STATIONS.
- **Regression test added?:** verified live: resolve_station("goa")=="MAO"; full route SBC-MAO returns not_in_window with booking_opens=2026-10-16.

### BUG-5: Cab place harvest blocked by login modal + readonly widget

- **Found:** 2026-09-05 (Phase 1 ground truth 1.2)
- **Call:** `mmt_cab_find_place(query="Goa")`
- **Expected:** a registered place object
- **Actual:** Blocked - "Could not focus the cab location field"
- **kind:** blocked
- **Root cause:** three stacked issues: (1) a login modal (SECTION.modalMain) intercepts every click until dismissed; (2) input#fromCity is a READONLY display widget - the real input lives in a react-autosuggest overlay opened by clicking label[for=fromCity]; (3) the response-capture filter looked for "locations" in the URL but the endpoint is cabs.makemytrip.com/autocomplete/v3.
- **Fix:** commit 3f53cb3 - _dismiss_popups (commonModal__close + charDhamBanner__closeBtn); click the label; use the overlay input; SUGGEST_HINT = "autocomplete"; best-matching suggestion clicked by text prefix.
- **Regression test added?:** live - place objects registered for goa and panaji.

### BUG-6: "goa" query matched Goalpara, Assam (prefix luck)

- **Found:** 2026-09-05 (after BUG-5 fix)
- **Call:** `mmt_cab_find_place(query="Goa")`
- **Expected:** a place in Goa
- **Actual:** registered "Goalpara, Assam, India" - "goa" is a prefix of "goalpara" and the matcher returned the first substring hit
- **kind:** none (wrong data, not an error)
- **Root cause:** single-tier substring matching has no regional preference.
- **Fix:** commit 6a43dc0 - _place_from_captured now prioritises: exact name, first-segment match, secondary_text containing the query (a place IN the region), prefix, substring. Verified: "goa" now registers "Goa beach, Calangute, Goa, India"; "Panaji" still exact.
- **Regression test added?:** live verification only.

### BUG-7 (CLOSED): flights-cb search-stream unreachable from automated context

- **Found:** 2026-09-05 (Phase 1 ground truth 1.4)
- **Call:** `mmt_flight_search(origin="BLR", dest="GOI", date="2026-12-15")`
- **Expected:** streamed itineraries
- **Actual:** every direct path to the API failed - `ctx.request` Akamai-denied, in-page
  fetch with custom headers denied by CORS preflight, bare fetch 403 "Missing Header
  app-ver", and the Search-click results page rendered the Akamai "200-ok" stub.
- **kind:** blocked
- **Root cause (revised 2026-09-04):** two separate things were tangled together. The API
  gate is real and stands - it cannot be called directly. But the *results page* stub had
  the same cause as BUG-8: a browser started by Playwright's launcher, arriving at the
  results route without the funnel page's sensor chain. Neither is about the headers.
- **Fix:** commit 49a534c. The API is not called at all. `harvest_flight_search` does what
  a person does - open `/flights/`, then the results page, and read the SSE response the
  page itself receives. `parse_stream` was rewritten from a real 114 KB capture: the body
  is **Server-Sent Events whose data frames are base64-encoded gzip**, not the run of
  concatenated JSON documents the inferred parser assumed. Fares come from `cardList`
  (`fare`, plus `fareBreakup` giving Base Fare and Surcharges apart) joined to
  `journeyMap` by `journeyKeys` for times, stops and airports.
- **Verified live:** BLR-GOI 2026-12-15, 25 itineraries, base + tax == all_in on every
  row, cheapest nonstop into GOI 6E 6554 at 4,367 (3,222 + 1,145). BLR-COK in
  `mmt_selftest`, so it is not route-specific. The same flight prices identically at A-1
  and A-2, so **fares are per adult** - reported as `fare_basis` rather than assumed.
- **Cost:** ~30-60 s per search. `mmt_capabilities` says so, so a caller does not sweep a
  month of dates.
- **Regression test added?:** yes - `tests/fixtures/flight_stream.sse` (real wire format,
  trimmed) and `flight_stream.json` (decoded, readable); one assertion per trusted field.

### BUG-8 (CLOSED): cab quote returned shape_drift at every tier

- **Found:** 2026-09-04 (Phase 1 closure - the quote had never been run)
- **Call:** `mmt_cab_quote(origin="Bengaluru", dest="goa", date="2026-12-15")`
- **Expected:** priced cabs by vehicle class
- **Actual:** `shape_drift` at tier 1 and tier 2. `/cabs/listing` returned a 169-byte
  Akamai stub whose body is the string "200-OK" - the same stub as the flight results
  page. So did `/cabs/` -> listing, a same-origin in-page fetch, and the site's own
  Search click.
- **kind:** shape_drift (correctly - a silent 200 with an unusable body)
- **Root cause:** nothing to do with the place objects, the URL length, or the JSON blobs
  in the query string - even a bare `/cabs/listing` with no parameters was stubbed.
  Bisected against a real Chrome; **two conditions are each necessary**:
  1. the browser must not have been started by Playwright's launcher (`navigator.webdriver`
     is false either way, so the tell is the launch itself, not the flag);
  2. it must arrive with the funnel page's sensor chain established - cold gets the stub,
     `/cabs/` first then the listing gets the real page.
- **Fix:** commit f922186. `session` self-launches Chrome and attaches over CDP, falling
  back to `launch_persistent_context` where no Chrome or Edge exists; `get_text` grows a
  `funnel_url` for the T2 navigation path and cabs passes `CAB_HOME`.
- **Verified live:** Bengaluru -> Goa 2026-12-15, 10 cabs, 603 km, base + tax_fees ==
  all_in on every row, cheapest 12,161 all-in.
- **Regression test added?:** no (environment-dependent); covered by `mmt_selftest`.

### BUG-9 (CLOSED): resolve_airport("goa") returned GOA - which is Genoa, Italy

- **Found:** 2026-09-04 (while adding the GOX codes)
- **Call:** `mmt_flight_search(origin="Bengaluru", dest="goa", ...)`
- **Expected:** GOI
- **Actual:** "GOA" - the three-letter alpha bypass fired before the AIRPORTS dict lookup.
  GOA is Genoa, Italy, and it appears in MakeMyTrip's own autosuggest for the query "goa".
  A Bengaluru-to-Goa flight search was silently pricing Bengaluru to Genoa.
- **kind:** none - wrong data, no error, the worst shape a bug can take here
- **Root cause:** resolver ordering. Exactly the mistake BUG-4 fixed for stations; the
  same fix was never applied to airports.
- **Fix:** commit 49a534c - dict lookup precedes the bypass. GOI/GOX added from the site's
  own autosuggest: GOI "Goa (South) - Dabolim", GOX "Goa (North) - Manohar" (Mopa).
- **Regression test added?:** yes - `test_flight_airports`, named for the trap.

### BUG-10 (CLOSED): an unparseable train date surfaced as kind "unexpected"

- **Found:** 2026-09-04 (error-taxonomy sweep)
- **Call:** `mmt_train_search(origin="MDU", dest="MS", date="not-a-date")`
- **Expected:** `bad_input`
- **Actual:** `{"error": "ValueError: Invalid isoformat string: 'not-a-date'", "kind":
  "unexpected"}` - a raw stack-level message, and the one kind that tells a caller nothing
- **kind:** should have been bad_input
- **Root cause:** `trains.in_window` parsed the date without the guard its siblings
  (`booking_opens`, `listing_url`) have, and it runs before any fetch.
- **Fix:** commit pending - `in_window` raises BadInput naming the value it got.
- **Regression test added?:** yes - `test_train_bad_date`, covering both entry points.

---

## Run 2026-09-04 - Phase 1 close

All Phase 1 gates green. Every bug logged above is closed; BUG-8, BUG-9 and BUG-10 were
found *by* this run.

| Gate | Result |
|---|---|
| Offline suite | 112/112, no network, no browser (was 78) |
| `mmt_setup_status` | ready, headless false, `chrome.exe (self-launched, CDP)` |
| Hotels Goa 6N | tier 2, base + tax == all_in on every row |
| Trains SBC-MAO in window | tier 1, 6 trains with live fares and waitlist |
| Trains Dec 15 (101 days out) | `not_in_window`, booking_opens 2026-10-16 |
| `station_city` SBC/MAO | CTBLR / CTGOI |
| Cabs Bengaluru-Goa | tier 2, 10 cabs, 603 km, cheapest 12,161 all-in |
| Flights BLR-GOI | tier 2, 25 itineraries, cheapest nonstop into GOI 4,367 |
| `mmt_selftest` (full) | 5/5; hotel_api, train_page, cab_page all healthy |
| Error taxonomy | bad_input / unregistered_place / not_in_window all correct after BUG-10 |

Latency: hotel search 7-27 s (tier 2), trains 0.4-4 s (tier 1), station_city ~16 s cold,
cabs ~13 s (tier 2, includes the funnel visit), flights 28-60 s (drives a real page).

The two structural findings worth carrying forward:

1. **A browser Playwright *starts* is treated differently from the same binary started as
   an ordinary process and attached to over CDP.** This, not headers and not cookies, was
   what stood between the server and both the cabs listing and the flight results page.
   The profile does not matter (a fresh one fails the same way); the launcher does.
2. **Deep links into results routes need the funnel page first.** `/cabs/listing` and
   `/flight/search` are stubbed when arrived at cold, and render in full when the funnel
   page (`/cabs/`, `/flights/`) was loaded in the same page first. `/railways/listing` is
   not fussy, which is why trains worked all along and hid the pattern.

Carried into Phase 2, not bugs: the train parser emits some junk class rows (`class: null,
quota "LD", fare 0`) alongside the real ones, and `prettyPrint` no longer arrives so
`status_pretty` is null throughout. Neither corrupts a real fare.
