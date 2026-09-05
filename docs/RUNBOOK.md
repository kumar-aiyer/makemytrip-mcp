# Runbook

## Triage order

1. `mmt_setup_status` — is there a working browser?
2. `mmt_selftest` — which capability broke, and which tier is each endpoint on?
3. `<state>/diagnostics/failures.jsonl` — the last failures: endpoint, error kind,
   message and which tiers were attempted. Metadata only — response bodies and
   screenshots are not stored.
4. **Headed is the default on Windows.** On a Linux server, set `MMT_HEADFUL=1` to see the browser. Headless is **known-blocked** by Akamai (`ERR_HTTP2_PROTOCOL_ERROR`).
5. **Which browser did it get?** `mmt_setup_status.browser` distinguishes the two launch
   paths. `chrome.exe (self-launched, CDP)` is the good one; a bare `chrome` or `bundled
   chromium` means it fell back to Playwright's launcher, and the cabs listing and flight
   results page will return the `200-OK` stub. Set `MMT_CHROME_PATH` if Chrome lives
   somewhere unusual.

## Symptoms

| Symptom | Cause | Fix |
|---|---|---|
| HTTP 200, hotels listed, every price `null` | `expData` / `featureFlags` trimmed | Restore both complete in `mmt/config.py`. Surfaces as `null_prices` |
| 403 from everything, all tiers | Datacenter IP, or the client IP is flagged | Run from a residential connection. Verified: cloud VMs get `403 AkamaiGHost` |
| `blocked` at T1, works at T2 | Akamai wants a rendered challenge | Nothing to do — the router escalates. Persistent T2 means slow but working |
| Hotel search: T1 POST → body starts `200-OK` | `ctx.request.post` is Akamai-stubbed on `mapi` | Expected from this network. The router escalates to T2-POST (in-page fetch), which works |
| 403 `Missing Header <x>` on flights | Something called the flight API directly | Nothing should. The API is unreachable from here by design of the gate; flights go through `harvest_flight_search`, which reads what the page receives |
| 169-byte body reading `200-OK` on `/cabs/listing` or `/flight/search` | Reached a results route cold, or the browser was launched by Playwright | Load the funnel page (`/cabs/`, `/flights/`) first in the same page, and make sure the session took the self-launched-Chrome path — `mmt_setup_status.browser` should say `(self-launched, CDP)`. Cookies, profile and query string are all red herrings here |
| Flight search takes 30-60 s | Expected | It drives a real search page; there is no URL to fetch. Results cache for 20 minutes |
| Flight fares look too cheap for the airport asked for | An itinerary into a nearby airport | Check `to` and `alternate_airport` per itinerary. A Goa search returns GOX (Mopa) and SDW (Sindhudurg) as well as GOI |
| `TargetClosedError` on every call after one failure | The self-launched Chrome exited and the context went stale | Handled: a disconnected browser is detected and relaunched. If it recurs constantly, check whether the profile is open in another Chrome window |
| Cab field won't focus / "Could not focus" | A login modal (`commonModal__close`) intercepts clicks | Already handled by `_dismiss_popups` in `harvest.py`. If it recurs, re-run the DOM diagnostic |
| Cab place registered is the wrong city (e.g. Goalpara for "goa") | Prefix/substring matcher beat a regional hit | Matcher now prefers places whose `secondary_text` contains the query. Re-harvest to overwrite |
| `unknown station GOA` | "goa" once bypassed the STATIONS dict as a 3-char alpha | Fixed — dict lookup precedes the bypass. If it recurs, check the resolver ordering |
| A flight search prices the wrong city entirely | A three-letter name bypassing the AIRPORTS dict — GOA is Genoa, Italy | Fixed (BUG-9), same ordering rule as stations. Any new resolver must look the name up **before** guessing it is a code |
| Empty result for a real city | Wrong locus code | The tool warns; check `cityLocationDetail` |
| Hotels missing from the response | Shape moved off `personalizedSections[].hotels` | `mmt/hotels.py::flatten` |
| `Missing Header <x>` (403) on flights | The flights gate wants another header | Add `<x>` to `config.flight_headers()` — the error names it |
| Detail page has no `__INITIAL_STATE__` | Interstitial, or the page changed | Router escalates to T2; if T2 also fails, `mmt_hotel_search` still gives property-level pricing |
| Zero trains for a real route | Date outside the 60-day window | Expected. The result carries `booking_opens` |
| Every train shows unavailable | Someone "fixed" the `availablity` misspelling | Spell it MakeMyTrip's way |
| Zero cabs, HTTP 200 | Place object trimmed or missing `place_id` | Re-harvest with `mmt_cab_find_place` |
| Empty result for a real city | Wrong locus code | The tool warns; check `cityLocationDetail` |
| 200 with a non-JSON body | Captive proxy or TLS interceptor | The error says so explicitly — it is not a request problem |
| Server starts, no tools appear | stdout polluted | Only protocol frames on stdout; everything else to stderr |
| Server appears to hang | Buffered stdout | `PYTHONUNBUFFERED=1` |
| `UnicodeEncodeError` on `₹` | Windows cp1252 console | `PYTHONIOENCODING=utf-8` |
| First call times out in OpenClaw | Cold start launches a browser | Raise `requestTimeoutMs` well above 20 s |
| Plugin absent after install | Zip root wrong, or a bad plugin name | `unzip -l`; kebab-case name |

## When MakeMyTrip changes something

1. `mmt_selftest` to identify which capability broke.
2. Re-capture per [API-REFERENCE.md](API-REFERENCE.md) §7.
3. Save a trimmed real payload into `tests/fixtures/`.
4. Extend `tests/test_parsers.py` **first**, then fix the parser.
5. `python tools/probe.py` to confirm live.

Assert on structure and arithmetic (`base + tax == all_in`), never on particular prices.

## Performance budget

| Operation | Target |
|---|---|
| `tools/list` | < 2 s, no browser |
| Cold start incl. warmup | < 20 s, once per session |
| Hotel search (warm) | < 3 s |
| Rate plans / trains / cabs (warm) | < 5 s |
| 14-leg itinerary | < 25 s |
| Cab place harvest | < 30 s |
| Cab quote (includes the funnel visit) | < 20 s |
| Flight search (drives a real page) | 30-60 s |
| Cached repeat | < 50 ms |

A warm call consistently over ~8 s means the router is sitting at T2. `mmt_selftest` shows
which endpoint class and why.

## Politeness

One stable device id, concurrency capped at 4, 150–400 ms jitter between batched calls, one
retry maximum, no scheduled polling. Keep usage conversational. If MakeMyTrip starts
returning 403 at every tier from a residential connection, stop rather than working around it.
