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

### BUG-7 (OPEN): flights-cb search-stream unreachable from automated context

- **Found:** 2026-09-05 (Phase 1 ground truth 1.4)
- **Call:** `mmt_flight_search(origin="BLR", dest="GOI", date="2026-12-15")`
- **Expected:** streamed itineraries
- **Actual:** every automated path fails; documented exhaustively in mmt/config.py (header contract) and harness/prompts/goa-itinerary.md
- **kind:** blocked
- **Root cause:** the search-stream API requires a session-generated authorization token plus a header set (app-ver, mcid, device-id, os, src) that the browser will only send after a CORS preflight the server only grants to a real-user session. ctx.request is Akamai-denied at the network layer; in-page fetch with custom headers fails preflight; the Search-click results page renders the Akamai "200-ok" stub so the flight JS never runs there.
- **Fix:** NOT FIXED - two documented unblock paths: (A) open MMT manually in the server Chrome profile (.state/chrome-profile) to seed the preflight cache + sensor state, then retry automation; (B) capture a real search-stream response from the user's browser (DevTools), save as tests/fixtures/flight_stream.json, and rewrite parse_stream from verified field names.
- **Regression test added?:** n/a until a fixture exists.