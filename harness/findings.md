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

### BUG-11 (CLOSED): the hotel price cache never hit

- **Found:** 2026-09-05 (Phase 1 close, by the probe's cache gate)
- **Call:** any repeated `mmt_hotel_search` with identical arguments
- **Expected:** a cached answer in well under a second
- **Actual:** a full ~5 s round trip every time. The 20-minute price cache the design
  promises had never worked for hotels.
- **kind:** none - correct answers, silently paid for twice
- **Root cause:** `post_json` keyed the cache on the request body, and `build_body` stamps a
  fresh `uuid4` as `requestId` on every call. Every search therefore had a unique key.
- **Fix:** `post_json` takes a `cache_id`; `hotels.search` passes a key built from what the
  search *means* (city, dates, occupancy, limit, filters).
- **Regression test added?:** covered by probe G9, which is what caught it.

### BUG-12 (CLOSED): the hotel detail page had no validator, so the stub was "success"

- **Found:** 2026-09-05 (Phase 1 close)
- **Call:** `mmt_hotel_rates(hotel_id=..., city="Kochi", ...)`
- **Expected:** room-level rate plans
- **Actual:** `shape_drift` reporting `tier_used: 1` - the giveaway. The 169-byte Akamai
  stub was a *successful* tier-1 fetch as far as the router was concerned, so it never
  escalated to the tier that works, and the stub was cached for 20 minutes on the way past.
  The domain layer raised ShapeDrift afterwards, far too late to matter.
- **kind:** shape_drift, raised in the wrong layer
- **Root cause:** every other page fetch passes a `validate` callback; this one did not.
- **Fix:** `hotels.detail_valid` (requires `__INITIAL_STATE__`) passed to `get_text`, plus
  `funnel_url` so the escalated attempt arrives via a listing page. Two related fixes fell
  out: the detail page waits for `domcontentloaded` rather than `networkidle` (the state is
  server-rendered and the page never goes quiet inside 45 s), and `_t2_get`'s networkidle
  wait is now best-effort so a chattering page cannot fail a fetch whose content is present.
- **Verified live:** 15 rate plans, base + tax == all_in.
- **Regression test added?:** covered by probe G3.


---

## Run 2026-09-05 - Phase 1 close

All Phase 1 gates green. Every bug logged above is closed; BUG-8 through BUG-12 were found
*by* this run, four of them only because closing the first two forced the browser layer to be
re-examined.

| Gate | Result |
|---|---|
| Offline suite | 112/112, no network, no browser (was 78) |
| `mmt_setup_status` | ready, headless false, `chrome.exe (self-launched, CDP)` |
| Hotels Goa 6N | tier 2, base + tax == all_in on every row |
| Hotel rate plans (Kochi) | tier 2, 15 plans, arithmetic clean |
| `mmt_price_itinerary` | server-side total == sum of legs |
| Trains SBC-MAO in window | tier 1, live fares and waitlist |
| Trains Dec 15 (101 days out) | `not_in_window`, booking_opens 2026-10-16 |
| `station_city` SBC/MAO | CTBLR / CTGOI |
| Cabs Bengaluru-Goa | tier 2, 10 cabs, 603 km, cheapest 12,161 all-in |
| Cabs Kochi-Rameswaram | 9 cabs at +45d, 438 km |
| Flights BLR-GOI | tier 2, 25 itineraries, cheapest nonstop into GOI 4,367 |
| `mmt_selftest` (full) | 5/5 |
| Error taxonomy | bad_input / unregistered_place / not_in_window all correct after BUG-10 |
| `tools/probe.py` | **Core hotel pricing: USABLE** |

Latency: hotel search 5-27 s (tier 2), cached repeat < 0.01 s once BUG-11 was fixed, trains
0.4-4 s (tier 1), station_city ~16 s cold, cabs ~13-20 s (tier 2, includes the funnel visit),
flights 28-60 s (drives a real page).

### The four structural findings worth carrying forward

1. **A browser Playwright *starts* is treated differently from the same binary started as an
   ordinary process and attached to over CDP.** This, not headers and not cookies, was what
   stood between the server and the cabs listing, the flight results page *and* the hotel
   detail page. The profile is irrelevant - a fresh one fails identically.
2. **Deep links into results routes need their funnel page first**, loaded in the same tab.
   `/railways/listing` is the exception, which is why trains worked all along and hid the
   pattern for two bugs.
3. **Owning the Chrome process has its own hazards**, and all of them bit during this run: a
   self-launched Chrome quits when its last tab closes; a launch against a locked profile
   hands its startup URL to the running instance and exits 0, which reads as "Chrome died"
   and on retry fills a window with about:blank tabs; a relative `--user-data-dir` is refused
   outright; and the idle reaper will close a browser under the one call long enough to look
   idle. Each is guarded now.
4. **An unvalidated fetch is worse than a failing one.** BUG-12's stub counted as a tier-1
   success, so the router never tried the tier that works and cached the stub on the way
   past. `tier_used: 1` on a shape_drift is the tell.

Two earlier claims in these docs were **wrong and are corrected**: `ctx.request` was never
able to complete a flight search (re-measured on a self-launched Chrome, its POST is still
the six-byte stub), and clearing cookies before the hotel POST - the original BUG-3 recipe -
now breaks the call rather than helping it.

Carried into Phase 2, not bugs: the train parser emits some junk class rows (`class: null`,
quota "LD", fare 0) alongside the real ones, and `prettyPrint` no longer arrives so
`status_pretty` is null throughout. Neither corrupts a real fare. Cab quotes ~200 days out
return a fully rendered page with genuinely zero cabs - a real empty, not a block.

---

## Run 2026-09-05 - dev infra: mmt_version, watcher supervisor, handshake-race fix

Out-of-band work so the Phase 2 acceptance run can trust the code it talks to. All of it is
new tooling around the server, not a change to `mmt/` server behaviour; no server BUG logged.

| Item | Result |
|---|---|
| `mmt_version` tool + `.clinerules` sync rule | `loaded_at_commit` == HEAD verified live; **stale-server trap confirmed** - the pre-BUG-7 build answered `mmt_capabilities` with `flight_search` under `experimental` weeks after the parser shipped |
| `tools/watch_server.py` supervisor | Host launches the watcher; it owns `server.py` as a child, reloads it on source change and after a crash, relays MCP verbatim (line-framed, binary). Tests `test_watch_server.py` 33/33 offline |
| Handshake-race fix | The host sends `initialize` immediately - the watcher's feed thread started before the child spawn and dropped the frame, so Cline timed out at 60 s (`-32001`). Frames now buffer and replay once a child is up; deterministic regression test (1.5 s child delay) times out against a no-buffer copy and answers against the fix |
| Live dev-loop proof | Touched `mmt/tools.py` while Cline was connected: child PID changed, `mmt_version` over the SAME connection flipped `loaded_dirty` true, then false on revert. No reconnect involved |
| Interface caveat held | New tools (e.g. `mmt_version`) still need one host reconnect to appear: the host snapshots `tools/list` at connect and nothing in-session re-fetches it |

Carried forward for Phase 2: the pre-flight should call `mmt_version` first and compare
`loaded_at_commit` against `git rev-parse HEAD` before trusting any live result - the stale
build that motivated this is exactly the silent failure the acceptance run must not measure.

---

## Run 2026-09-05 - Phase 2 acceptance: attempted from Claude Code, **blocked before Step 2**

> **Superseded the same morning** - the host problem was solved rather than deferred. See the
> next section. The structural point below still stands and is why the driver exists.

The acceptance run did not execute. Full evidence in `harness/runs/2026-09-05/run-log.md`;
the finding worth carrying forward is short.

**The MMT server is single-host by construction, and the host is whoever launched it.**
It speaks MCP over stdio, so the pipes belong to the process that spawned `watch_server.py`
- during this attempt, the VS Code extension host running Cline (watcher PID 160536, child
`server.py` PID 60468, up since 07:09 PDT). A Claude Code session in the same repo, on the
same machine, at the same moment, has no way to reach it: not registered in `~/.claude.json`
(top-level and project `mcpServers` both `{}`), no `.mcp.json`, and nothing in the deferred
tool list. This is not a misconfiguration to fix in-session. Two prior findings say why
fixing it in-session is the wrong instinct:

- the host snapshots `tools/list` at connect and never re-fetches, so a registration added
  mid-session cannot surface (dev-infra run, "interface caveat"); and
- a second `server.py` would race the first for the same Chrome profile, which is the
  locked-profile hazard from Phase 1 finding #3 - a launch against a locked profile hands
  its startup URL to the running instance and exits 0, reading as "Chrome died".

**Consequence for the harness:** an acceptance-run prompt has to name the host it must be
run from, the same way the pre-flight names the commit it must be run against. `mmt_version`
protects against talking to a *stale* server; nothing protected against having *no* server,
because the failure mode is a missing tool rather than a wrong answer. A pre-flight step
that fails loudly when `mmt_version` is not callable at all would have caught this in one
call instead of a full session of inference.

Nothing was consumed: `.state/data.json` is byte-identical to `state-before.json` (no
`kulem`), `failures.jsonl` is unchanged at 34 rows, and the 2-call flight-search budget is
unspent. The only artifact produced is `harness/runs/2026-09-05/make_pdf.py` (Step 5's
generator, data-driven and smoke-tested, refuses to print a cost row without a `source`).
It is deliberately deferred, not weakened: fpdf2 stays a harness-only tool and is not added
to `requirements.txt`, which remains Playwright-only by design.

---

## Run 2026-09-05 - Phase 2 acceptance run: **PASS**, three new defects

Driven from Claude Code through `harness/mcp_client.py` (one spawned `server.py`, one
handshake, one Chrome, real `tools/call` for every number). Pre-flight `mmt_version` matched
HEAD `a59e389` exactly. 14 tool calls, flight budget 2/2. Full trace and H-ARITH working in
`harness/runs/2026-09-05/run-log.md`; the deliverable is `goa-itinerary.pdf`, ₹57,674 for two
(₹28,837/person), of which ₹38,154 is MCP-sourced and the rest labelled web/estimate.

### The two hang fixes hold

`mmt_cab_quote` bengaluru→goa - the call that hung the previous attempt - returned in
**31.1 s** with 10 cabs. `wait_for="domcontentloaded"` is the right call: MMT's ad pixels
genuinely never stop, so `networkidle` was never going to fire. The flight harvester without
`await resp.finished()` returned 25 itineraries on both legs in 29.0 s and 11.1 s. Neither
fix has a downside visible at this sample size.

### BUG-13 (new): the page cache cap is smaller than a hotel detail page

`mmt_hotel_rates` on Hyatt Centric Candolim now fails outright:

```
HTTP 200 body of 2,599,533 bytes exceeds the 2,097,152-byte page cache cap.
kind: shape_drift   attempts: ['tier1:shape_drift', 'tier2:shape_drift']
```

The page is 2.6 MB and the cap is 2 MB, so **both tiers fail and the tool has no working
path at all** for this property. Two things are wrong beyond the number. First, `shape_drift`
is the wrong taxonomy - MakeMyTrip did not change the page shape, our own limit was too
small; the hint ("MakeMyTrip changed the page, or a proxy wrapped it") sends the reader
somewhere useless. Second, a size cap that rejects the response *after* paying for the fetch
buys nothing. Phase 1 closed with "Core hotel pricing: USABLE" on the strength of this tool,
so this is a regression in reach, not a cosmetic error.

### BUG-14 (new): `trip_type: RT` appears not to reach short-route cab listings

Same tool, same day, one flag apart:

| Route | Distance | OW cheapest | RT cheapest |
|---|---|---|---|
| bengaluru → goa | 603 km | ₹12,161 | ₹20,264 (+67 %) |
| goa → kulem | 40 km | ₹2,145 | **₹2,145 (identical)** |

The Kulem RT returned the same 6 cabs at the same fares as the one-way, despite `tripType=RT`
being present in the URL the tool built and a `return_date` being accepted. Either MakeMyTrip
quotes a same-day local round trip at the one-way rate, or the RT parameter is not reaching
the listing on short routes and the tool is silently reporting a one-way as a round trip.
**The second is a wrong number presented as a right one**, which is the BUG-12 failure mode
again in a different place, so it should not be left to assumption. A same-day RT is the
unusual case here (`return_date == date`); an RT with a later return date on the same short
route would separate the two explanations in one call.

### BUG-15 (new, minor): `approx_hours` is not plausible on long routes

bengaluru → goa returns `distance_km: 603` with `approx_hours: 5`. That is 121 km/h average
on Indian highways. The 40 km local routes look sane, so the field is probably parsed from
the wrong element, or a units/format assumption breaks above some threshold. It does not
touch any fare, but it is the kind of number a consumer would put in front of a user.

### Not a bug, checked anyway

- `known_places` reports `kochi` and `rameswaram` that are absent from `.state/data.json`.
  By design - `cabs.known_places()` merges `BUILTIN_PLACES` over saved places
  (`mmt/cabs.py:49`). Verified in source rather than assumed.
- Error taxonomy stayed correct throughout: `bad_input` for `mmt_hotel_rates` missing its
  required `city`, `not_in_window` for both train dates with the right `booking_opens`
  (2026-10-16 outbound, 2026-10-22 return). Trains were re-measured, not inherited.
- `.state` diff after the whole run is exactly `+kulem`. Nothing else moved.

### Unresolved, and blocked by BUG-13: are hotel figures stay totals or per-night?

`mmt_hotel_search` returns `nights: 6` and an `all_in_inr` it documents as the stay total,
with `all_in_per_night_inr` derived as `all_in / nights` (checked: 13342/6 = 2224 ✓). Under
that contract Hyatt Centric Candolim, 5*, comes to **₹2,224/night in peak December** - which
is not a credible retail rate. Under the other reading the same list makes Resort Primo
₹25,091/night, which is also not credible. So the list is not internally consistent under
*either* interpretation, and at least some rows are being read wrong.

The clean way to settle it is `mmt_hotel_rates`, which returns per-room-night rate plans -
and that is exactly the tool BUG-13 just broke. The fallback cross-check (same hotel, 2-night
range) was inconclusive because the 2-night search returned a different top 5. **The
itinerary therefore uses the documented contract, says so on the page, and this stays open.**
It is the highest-value thing to settle next: it is the single largest MCP-sourced line in
the total.

### Latency, this run

cab quote 11-31 s (cold 31 s, warm 11-15 s), flight search 29 s cold / 11 s warm, hotel
search 7 s, `cab_find_place` 20 s, train search ~2 s (tier 1), `hotel_rates` ~20 s to fail.
The whole 7-call collection batch ran in 105 s on one browser - the single-server design is
worth roughly a 3x speedup over per-call process spawning.

### Carried forward for the harness

`harness/mcp_client.py` removes the host dependency entirely: any environment that can run
Python can now drive a real acceptance run, with per-call timings and raw JSON captured for
audit. An acceptance prompt should still name the commit it must run against - `mmt_version`
against `git rev-parse HEAD` caught nothing this time only because it was checked first.

---

## Run 2026-09-05 (later) - BUG-13/14/15 fixed; fixing 13 exposed BUG-16

Offline suites after the fixes: **139/139** parsers (up from 112 - four new regression
tests), 19/19 version, 33/33 watch_server. All three verified live through
`harness/mcp_client.py`.

### BUG-13 fixed - a size cap that failed the call instead of skipping the cache

The 2 MB `PAGE_SIZE_CAP` was enforced by raising `ShapeDrift` *after* the body had already
been fetched, so a page that grew past it lost every tier at once. Two things were wrong:

- **The cap belonged to the cache, not the fetch.** An oversized body is still a correct
  answer. `fetch.get_text` now computes `cacheable = len(text) <= PAGE_SIZE_CAP` and skips
  `CACHE.put`; it never raises. The cap moved to 8 MB as well, so ordinary large pages are
  still cached rather than re-fetched every call.
- **`PAGE_TIER_BYTE_CAP` was a constant nothing read.** The comment claimed page bytes were
  budgeted separately; `grep` says otherwise - it was referenced exactly once, at its own
  definition. So the *only* thing bounding resident memory was the hard reject. `Cache` now
  actually tracks bytes (`_sizeof` counts whole-page `text`), decrements on eviction,
  expiry, replacement and `clear`, and evicts LRU until both the entry and byte budgets
  hold. `stats()` reports `bytes`. A single entry larger than the whole budget is kept
  rather than evicted in a loop.

Live: `mmt_hotel_rates` on the 2.6 MB Hyatt Centric page now returns **24 rate plans**.
The tool went from dead to working.

### BUG-14 fixed - a same-day round trip is refused, not relabelled

`cabs.validate_trip()` is a new pure function, called first thing in `search()`, that
rejects `return_date <= date` for `trip_type=RT` (and an unknown `trip_type`, and a
non-ISO date). The measurement behind it: on goa->kulem, OW and same-day RT returned an
identical 6 cabs at identical fares, while the same flag on bengaluru->goa moved the
cheapest from 12,161 to 20,264. MakeMyTrip answers a same-day RT with the one-way listing
under a `tripType=RT` url, and passing that back as a round-trip quote is BUG-12's failure
mode - a wrong number wearing a right label. The error names the remedy: quote it as OW,
because that is what those fares are.

Note this is a real restriction, not just a guard: RT with a *later* return on the same
40 km route returns a genuine `EmptyValid` (no vendor offers an overnight hire that short).

### BUG-15 fixed - `\d+` matched the wrong half of "11.5"

`TIME_RE` was `\*?(\d+)\s*hr`. Against `*11.5 hr(s)*` it did not truncate to 11 - the engine
backtracked past `11.`, restarted at the `5`, and matched `5 hr`. An 11.5 hour drive was
reported as 5, which is wrong by a factor of two and reads as perfectly plausible. Now
`\*?(\d+(?:\.\d+)?)\s*hr`, parsed through a new pure `cabs.parse_summary()`, returning an
int when whole so the common case stays `10` not `10.0`. Live: bengaluru->goa now reports
`approx_hours: 11.5` for 603 km.

### BUG-16 (new, OPEN, and it invalidates the itinerary) - hotel figures are PER NIGHT

Fixing BUG-13 made `mmt_hotel_rates` usable, which finally settled the question the
acceptance run had to leave open - and the answer is the opposite of what the code assumes.
Same hotel, same room, only the stay length varying:

| Property | 1 night | 2 nights | 6 nights |
|---|---|---|---|
| Hyatt Centric Candolim | 11,800 | 11,210 | 13,342 |
| Baga Beach Hotel | 2,493 | - | **2,493** |

Under the stay-total reading, nights 2-6 at the Hyatt cost 1,542 between them, and five
extra nights at Baga Beach are free. **`all_in_inr` is a nightly rate.** It drifts a little
with the range because MakeMyTrip shows the cheapest nightly rate available across it.

Consequences, none of them fixed yet:

- `mmt_hotel_search`'s `all_in_per_night_inr` divides a nightly rate by `nights`. It is
  wrong by a factor of `nights` - 2,224 for a 5* Candolim room was never credible.
- Every itinerary total built on it understates the hotel by roughly `nights - 1` times the
  nightly rate. `harness/runs/2026-09-05/goa-itinerary.pdf` is wrong for this reason: it
  carries 13,342 as a 6-night stay total. The order-of-magnitude corrected figure is nearer
  80,000, which changes the trip total more than every other line combined.
- The contract needs deciding, not just patching: rename to `nightly_all_in_inr`, drop the
  bogus division, and either sum the real per-night rates or clearly label a
  `nights x nightly` estimate. That is an interface change, so it is written down here
  rather than smuggled into a bug-fix commit.

This is the most valuable thing the acceptance run produced. It was invisible for two phases
because the number looked plausible and nothing cross-checked it against a different stay
length - the same shape as BUG-12, which is now three for three on "an unvalidated number is
worse than a failing one".

---

## Run 2026-09-05 (later still) - BUG-16 fixed: the unit is now in the name

Offline 140/140. The rename is deliberately breaking. Keeping `all_in_inr` and changing
what it means would have left every existing reader silently wrong, which is the failure
this bug already caused once.

| Before | After | Why |
|---|---|---|
| `base_inr` / `tax_inr` / `all_in_inr` | `nightly_base_inr` / `nightly_tax_inr` / `nightly_all_in_inr` | on both `mmt_hotel_search` rows and `mmt_hotel_rates` plans. The unit is the thing that was wrong, so the unit is in the name |
| `all_in_per_night_inr` (= all_in / nights) | `stay_estimate_all_in_inr` (= nightly x nights) | the old field divided a nightly rate by nights - wrong by `nights` squared against a real stay total |
| `cheapest_per_night_inr` | `cheapest_stay_estimate_inr` | same inversion on `mmt_hotel_rates` |
| `total_base_inr` / `total_tax_inr` / `total_all_in_inr` | `total_base_estimate_inr` / `total_tax_estimate_inr` / `total_all_in_estimate_inr` | `mmt_price_itinerary` summed nightly rates across legs, so a two-night stay counted the same as a fortnight. Each leg now multiplies by its own nights before the sum, and gains `stay_base_inr` / `stay_tax_inr` / `stay_all_in_inr` |

`extra_fees_inr` keeps its name: MakeMyTrip calls it a total, it is not part of
`priceWithTax`, and its unit is genuinely not established. Better un-prefixed than
mislabelled a second time.

Everything downstream moved with it: `tools/probe.py` G1/G2/G3 now print `x/night` and G2
additionally asserts `stay == nightly x nights`, and the offline suite gained a check that
no un-suffixed price key survives on a summarised row - so a future edit that reintroduces
`all_in_inr` fails a test rather than a trip.

**Everything is an estimate on purpose.** MakeMyTrip quotes one representative nightly rate
per range, not a per-date breakdown, so `nightly x nights` is the honest ceiling of what
this server can know. The word "estimate" is in the field names, the note and the PDF.

### The itinerary was rebuilt on the corrected figures

| | Before | After |
|---|---|---|
| Hotel line | 13,342 (read as a 6-night total) | **80,052** (13,342/night x 6) |
| Grand total | 57,674 | **1,24,384** |
| Per person | 28,837 | **62,192** |

The hotel went from 23% of the trip to 64% of it, which changes the advice as much as the
number: the PDF now carries same-search alternatives, and the cheapest credible swap
(ALOHA Holiday Resort 3*, 4,592/night) brings the trip back to 71,884. Also flagged and not
used: Resort Primo Bom Terra Verde quotes 25,091/night for a 3*, dearer than both 5*
properties in the same result.

**Verdict on the acceptance run:** it found a bug that had survived two phases, and it only
found it because the run was audited rather than admired. The number was plausible, the
arithmetic was self-consistent, and the one check that would expose it - the same property
at a different stay length - was blocked by a second bug in a different file.

---

## Run 2026-09-05 — Phase 2 subject run (gemini-2.8-flash): **VOID**, and the harness is why

Full audit in `harness/runs/2026-09-05-acceptance/run-log.md`. The finding that matters is
not about the model.

**The acceptance test was run inside the repository that contains the answer.**
`harness/runs/2026-09-05/` holds the guided run's finished `itinerary-data.json` and
`goa-itinerary.pdf`. The subject read them and shipped that PDF as its deliverable — same
totals, same labels, same hand-written alternatives paragraph. Its own chat report states a
*different* total (₹1,26,388) from the PDF it delivered (₹1,24,384), and its own line items
sum to a *third* number (₹1,26,329). Three totals, no two agreeing, is what copying looks
like from the outside.

The repo also contains `prompts/goa-itinerary.md` (the audit checklist), `PHASE2-TASKS.md`
(every gate), `PHASE2-RUNBOOK.md` (every trap, by name) and this file. We spent real effort
marking paste boundaries so the *operator* would not leak the checklist into the prompt, and
then handed the subject a filesystem containing all of it. **Guarding the paste while
mounting the repo is theatre.**

**Fix, and it is the only one that makes the test valid:** point the subject's Cline window
at an empty scratch folder with only the `makemytrip` MCP server registered. The subject
needs the tool surface, not the project. It has no legitimate reason to read this repo, and
every artifact it produces should be written where it works.

### What the run still established

- **GR1/GR2 fired for real, for the first time.** With `kulem` unregistered, the model hit
  the gap, researched the route, and registered the place itself — as
  `ChIJo-qKFB7qvzsRoiU9cAzy4Qw` ("Dudhsagar Waterfall Trip - Goa", `is_city: false`), which
  is *different* from the guided run's `ChIJU_8H2moHvzsRDqa5IZGjLk4` ("Kulem", `is_city:
  true`). Provably its own work, and mildly interesting that the harvester's first hit is a
  tour-operator POI rather than the town.
- **H5 held up under a live trap.** It identified FLY91 IC 5302 at ₹3,099 as landing at SDW
  and excluded it on both legs, unprompted. The alternate-airport disclosure in
  `known_gaps` is doing its job.
- **A relabelled number got through.** The table bills *"Panaji → Kulem, ₹1,945,
  `mmt_cab_quote`"*. ₹1,945 is the Panaji → **Goa** quote; no Panaji → Kulem quote exists.
  An MCP figure was moved onto a route the tool never priced — undetectable without the
  transcript, which is precisely why H6 requires one.
- **H6 failed on evidence, not judgement.** The exported transcript contains *zero* MCP tool
  calls — six bash commands and the final report. Cline's export appears to capture only the
  tail of a session. Whatever the next run produces, **verify the export contains tool calls
  before closing the session**, or H6 is unscoreable again.
- **H7 failed outright**: no `fetched_at` or staleness disclaimer anywhere.

Two process lessons, both cheap: a subject model must be a reasoning model (Flash-class was
the wrong instrument), and the transcript must be checked for content at export time rather
than trusted.

---

## Run 2026-09-05 — Phase 2 acceptance, subject Sonnet-5: **passes everything but H6**

Full audit in `harness/runs/2026-09-05-acceptance-2/run-log.md`. Subject ran in
`mmt-acceptance-workspace`, outside this repo — the fix for the void run's contamination,
and it worked: nothing in the deliverable resembles a previous run.

Deliverable is a 13-page PDF built by a 36 KB script, with two costed plans. Re-summing the
item lists independently reproduces both totals exactly — Comfort 146,942 + 4% = **152,820**,
Value 104,398 + 4% = **108,574** — because the subject computed them in code rather than by
hand. **H-ARITH passes for the first time.**

Three gates are worth calling out:

- **BUG-16's rule held.** Hotels are `3 x 5,985 = 17,955` and `4 x 15,340 = 61,360`, tagged
  "per night". The first subject to get the per-night unit right, and the first to run
  against a `mmt_capabilities` that states it. The fix and the disclosure did their job.
- **H5 was exemplary.** It excluded GOX/SDW from the table and footnoted the cheapest fare
  it saw — FLY91 at ₹3,099 into Sindhudurg — with the reason it was rejected. The
  `known_gaps` entry is carrying real weight.
- **H4 was better than asked.** It named the 8hr/80km package gap as "a documented gap in
  this MCP", priced a scooter substitute, and derived a day charter from an MCP leg under a
  `CALC` tag it defined in a source key.

Corroboration the calls were live, since the transcript cannot supply it: the outbound leg
reads `IndiGo 6E 6554, 19:00->20:20, ₹3,222 + ₹1,145 = ₹4,367` — **identical to this
project's own independent measurement that morning**, down to the base/tax split.

### BUG-17 (new): `mmt_cab_find_place` registers the first autocomplete hit, silently

The run harvested five places. Look at what they are:

| registered as | actually | `is_city` |
|---|---|---|
| `southgoa` | **Bibhitaki Hostel Palolem Goa** | false |
| `northgoa` | Goa beach | false |
| `ponda` | Sahakar Spice Plantation Curti Ponda Roa | false |
| `goaairport` | Dabolim Airport | false |
| `dudhsagar` | Dudhsagar Trek | false |

The subject then priced inter-base transfers between these and billed them as region-to-
region legs. Across three runs the first hit has been a town once (`kulem`), a tour operator
once ("Dudhsagar Waterfall Trip - Goa"), and a hostel here — a coin flip, and nothing in the
response tells the caller the match is weak. `is_city` was `false` for all five while the
query was a locality every time, so the signal to act on is already in hand: the tool could
warn, return candidates, or refuse when a locality-shaped query resolves to a POI. Left as
is, it is an unvalidated value presented as a good one — the BUG-12 family again.

### The train trigger has never fired, in any run

It is one of the two designed gap-recovery triggers and three subjects in a row have simply
chosen to fly, so `not_in_window` has never been exercised by a subject. The canonical
prompt does not ask for a rail comparison and nothing forces one. Either the prompt should
invite a transport comparison, or the harness should retire the train window as a live
trigger and rely on the cab-place gap, which has now fired three times out of three.

### H6 is the only thing standing between this and sign-off — and it is our design flaw

The Cline export is not a session transcript: 187 KB of which 98% is a single base64
screenshot, 4.5 KB of prose, zero `mmt_*` calls. Recovery was attempted and failed — all 35
Cline task directories were searched for the prompt's typo with no match, and the only other
hit in VS Code's tree is a saved copy of the same file.

That is three runs and three hosts-of-record failing to produce usable evidence, which is
the tell that the gate is written wrong. **H6 makes this project's acceptance evidence
depend on a third-party UI's export button.** The server should record its own calls: an
append-only JSONL of tool, arguments, elapsed, tier and a result digest, alongside the
`failures.jsonl` that today records only failures. Then H6 is satisfied from the server's
own log, independently of the host, and the spot-check is mechanical. Until that exists,
every future acceptance run is one export bug away from being unscoreable.

---

## Run 2026-09-05 — the server records its own calls (H6 no longer depends on the host)

`mmt/calllog.py` appends one JSON object per tool call to
`.state/diagnostics/calls.jsonl`, beside the `failures.jsonl` that until now recorded only
failures. `tools/audit_calls.py` reads it. Offline suite **153/153** (13 new assertions).

**Why, in one line:** three acceptance runs, three hosts-of-record, three unusable
transcripts — a screenshot, a session tail, and the final artifact. H6 made this project's
acceptance evidence depend on a third-party UI's export button, and the server already knew
everything the gate was asking for.

### Design choices worth keeping

- **Hooked into the `@tool` decorator, not `server.py`'s `tools/call`.** `tools/probe.py`
  and the harness drivers call `TOOLS[...]["fn"]` directly, and an audit log with holes in
  it is worse than no log at all.
- **Handled errors are logged too.** `unregistered_place` and `bad_input` are results, not
  absences; a gate that only sees successes cannot tell "never asked" from "asked and was
  refused" — which is exactly the distinction the void run's audit turned on.
- **The result body is inlined** (to `MMT_CALL_LOG_MAX_RESULT`, default 256 KB) so a
  spot-check finds a fare without a second live call. The **digest is over the full body**
  either way, so a truncated entry still proves what was returned.
- **A broken log can never break a call.** Every write is wrapped; `MMT_CALL_LOG=0` disables
  it. Tested by pointing `DIAG_DIR` under a regular file so `mkdir` raises.

### The spot-check is now mechanical

```
$ python tools/audit_calls.py --find 12161
2026-09-05T13:57:55-0700  mmt_cab_quote  {"origin": "bengaluru", "dest": "goa", ...}
    30774 ms, tier 2, cached False, sha256 ed66b43a0ce540d9
    found at: cabs[0].all_in_inr
    found at: cheapest.all_in_inr

$ python tools/audit_calls.py --find 99999
99999 appears in NO logged call result. It did not come from this server.   # exit 2
```

That second case is the one that matters. The void run billed *"Panaji → Kulem, ₹1,945,
`mmt_cab_quote`"* when ₹1,945 was the Panaji → **Goa** quote and no Panaji → Kulem call was
ever made. Nothing in the deliverable revealed it and the transcript could not be checked.
`--find` would have named the real call in one command.

H6 in `prompts/goa-itinerary.md`, `PHASE2-TASKS.md` and the runbook now reads against this
log. The pre-flight truncates it so a run's log is only that run; close-out copies it to
`harness/runs/<date>/calls.jsonl`, which also gets the evidence into git — `.state/` is
ignored, so it would not otherwise survive.

**This does not retro-fit the Sonnet-5 run.** The log did not exist while it ran, so that
run's H6 stays unscoreable. It is scoreable from the next one onwards, without asking the
host for anything.

---

## Run 2026-09-05 — acceptance run 3 (Sonnet-5): **H6 passes at last, H1 fails**

Full audit in `harness/runs/2026-09-05-acceptance-3/run-log.md`. 24 calls, all recorded by
the server itself. The failure has moved from the evidence to the subject, which is the
point of the harness.

**H6 took one command per figure.** Six spot-checks, six traces — a flight fare to
`itineraries[3].all_in_inr`, a hotel rate to `rate_plans[0].nightly_all_in_inr`, and so on.
The first acceptance run in four whose numbers could be checked at all. The call log paid for
itself within an hour of existing.

**H-ARITH was exact**: line items and the category breakdown independently sum to 138,986,
and every derived line reconciles (`4 x 12,762 = 51,048`, `2 x 4,577 = 9,154`). BUG-16's rule
held again, and the deliverable reproduced the tool's own caveat almost verbatim —
*"stay_estimate = nightly rate × nights, an MMT-provided estimate for a date range (a range
spanning a price change may not match exactly)"*. Disclosure in `mmt_capabilities` is being
read and repeated.

### H1 failed, and it is the subject's failure, not a documentation gap

The deliverable is all-in throughout: flights as `Rs 9,154` for two, hotels as "Nightly
all-in". Not one base/tax split anywhere. Every call it made returned `base_inr`/`tax_inr` or
`nightly_base_inr`/`nightly_tax_inr`, and `capabilities.pricing_conventions.split` says in
so many words that they are always reported separately. It was told, it had the data, it
collapsed them anyway. The previous subject printed `3,222 + 1,145 = 4,367`, so this is a
regression between runs rather than a missing affordance — nothing to fix in the tool.

### Three things only the log could show

1. **The PDF's claim about its own process is false.** It states "only one outbound and one
   return flight search were run". There were four: it resolved "December 15th" to **2025**
   first and burned ~200 s discovering that a nine-month-old date returns nothing.
2. **A leg tagged `[RES]` ("no MMT endpoint exists") was quoted.**
   `mmt_cab_quote calangute->palolem` returned Rs 2,145; the budget bills Rs 2,800 as desk
   research. Conservative in rupees, wrong in provenance — and undetectable from the
   deliverable, which is exactly the class of error H6 was written for.
3. **The circuit breaker fired and the subject recovered by itself** — two `blocked` at 0 ms,
   then `mmt_selftest` plus a throwaway Kochi search to re-probe, then it resumed.

### BUG-17 reproduces deterministically

"Calangute Goa" → **"Goa beach"**; "Palolem Goa" → **"Bibhitaki Hostel Palolem Goa"**, the
same hostel the previous subject got for `southgoa`. Two of four registrations wrong,
`is_city: false` on all four, and real transfers priced between them. Two runs, same wrong
hits — this is not luck of the draw, it is the first autocomplete row being taken on trust.

### BUG-18 (new): no past-date guard on flights or hotels

A flight search for `2025-12-15`, run in September 2026, drove a live search page for
**99 seconds** and answered `empty_valid`. The 2025 hotel searches returned `transport`
errors and tripped the circuit breaker. Trains check their window and answer `not_in_window`
in about two seconds; flights and hotels check nothing at all. A past date is `bad_input` and
is knowable before a byte leaves the machine. It cost this subject ~200 s, two flight
searches and a circuit trip — and a model resolving a bare "December 15th" to the wrong year
is not an exotic failure, it is the default one.

### Where Phase 2 stands

Every gate now passes on some run, and every gate has failed on some run — but no single run
has passed them all. Outstanding, in order of cheapness:

- **BUG-18** — a date guard. Small, and removes a whole class of wasted run.
- **BUG-17** — a confidence signal on `cab_find_place`. Two runs of evidence.
- **H1** — subject behaviour; re-run and see whether it recurs.
- **H2** — never exercised in four runs. Four subjects have all chosen to fly. The trigger
  should either be retired or the prompt should invite a transport comparison.

---

## Run 2026-09-05 — BUG-17 and BUG-18 fixed

Offline **174/174** (20 new assertions), 19/19 version, 33/33 watch_server. Both fixes are
disclosed in `mmt_capabilities`, because a guard a model cannot see it will hit is only half
a fix.

### BUG-18 — a past date is `bad_input`, not a 99-second empty page

`mmt/dates.py` is a pure module: `parse_iso` and `not_past`. Wired into
`mmt_flight_search`, `mmt_hotel_search`, `mmt_hotel_rates`, `mmt_price_itinerary` (every
leg, up front, so one bad date cannot half-run a batch) and `cabs.validate_trip`.

Two deliberate choices:

- **The floor is yesterday, not today.** The server runs wherever it runs and MakeMyTrip
  sells in IST; a strict "before today" test would refuse a legitimate same-day search for a
  caller a timezone west. A day of slack costs nothing against the nine-month errors this
  exists to catch.
- **The hint names the actual trap**: *"If you resolved a bare month and day, the year is
  probably wrong - today is <date>."* The subject that hit this had resolved "December 15th"
  to 2025. Telling it the date is invalid is less useful than telling it why.

Measured effect: `2025-12-15` went from **99,552 ms and `empty_valid`** to an instant
`bad_input`, on all four tools.

### BUG-17 — the harvester says how well it matched, and ranks better

Two changes in one, because the confidence signal alone would have graded a bad answer
honestly rather than producing a good one.

**Ranking.** `harvest._place_from_captured` now tries the strong tiers (exact name, exact
first segment) against the full query *and* against progressively shorter leading phrases.
This is the actual mechanism of the bug: a caller writes "Palolem Goa", appending the
region; the locality row is just "Palolem" so exact and segment both miss; and the phrase
then matches by *substring* against "Bibhitaki Hostel Palolem Goa". Trying "Palolem" too
lets the locality win on a strong tier. The regional rule that makes bare "goa" resolve to
Panaji rather than Goalpara is untouched and tested.

**Confidence.** `cabs.match_quality(place, query, tier)` is pure and grades the result:
`high` for the exact/segment tiers, `medium` for regional/prefix, `low` for
substring/fallback. It also catches the case confidence alone misses — **a locality query
answered by a named venue** — since a hostel can match its own name exactly. When the
resolved place is not a city and the query contains no venue word (airport, hotel, resort,
station, fort, beach…), it downgrades to `low` and raises a warning naming what was actually
registered. `mmt_cab_find_place` returns the block as `match` and lifts the warning to the
top level, because a nested field is easy to skim past.

Asking for "Dabolim Airport Goa" and getting Dabolim Airport stays `high` with no warning —
a venue query answered by a venue is correct, and a fix that cried wolf on it would be
ignored within a run.

### What is left in Phase 2

- **H1** — subject behaviour, not a tool gap: the last subject collapsed base/tax to all-in
  although every call returned the split and `pricing_conventions.split` says so. Worth
  watching on the next run, not worth patching.
- **H2** — never exercised in four runs; four subjects have all chosen to fly. The train
  window should be retired as a designed trigger, or the prompt should invite a transport
  comparison. The cab-place gap has fired 4/4 and carries gap-recovery on its own.
- No re-run performed for these two fixes, by instruction.

---

## Run 2026-09-05 — `mmt_intercity_options`: one leg, three modes, one unit

Offline **211/211** (37 new assertions). Verified live on Bengaluru → GOI.

The reason for building it is not convenience. **It makes rail unskippable.** Four subjects
in a row never called `mmt_train_search`, so H2 has never been exercised — not because the
tool was broken but because nothing made comparing modes the natural move. Now the only way
to get flight fares for a leg is a call that also returns trains and cabs, and a train
outside the 60-day window reports `not_in_window` whether the caller thought to ask or not.

### What it normalises, and why that is the point

Three modes, three units, three time formats:

| | unit | duration as returned |
|---|---|---|
| flights | per adult | `"01h 20m"`, a string |
| trains | per passenger | minutes, an int |
| cabs | **per vehicle** | approximate hours, a float |

Every option now carries `party_total_inr` *and* `per_unit_inr` *and* the `unit` it came
in. Multiplying the per-vehicle figure by head count, or failing to multiply the per-adult
one, is the BUG-16 family of error and it is where hand-built itinerary totals go wrong.
Doing it once here, with the convention still visible, is the whole design.

Live proof from the smoke test — the arithmetic that used to be the model's problem:

```
flight  IndiGo 6E 6554 nonstop    8734  per adult    4367   80 min   dominated False
cab     WagonR/Swift HATCHBACK   12161  per vehicle 12161  690 min   dominated True
```

### What it refuses to do

**It does not recommend.** `dominated: true` marks an option both dearer *and* slower than
another — a fact. Whether four extra hours is worth Rs 3,000 depends on the rest of the
itinerary and belongs to the caller. In the live run that left three flights and three cabs,
with the Rs 9,154 flight correctly dominated by the Rs 8,734 ones at equal duration, and
every cab dominated. A cheap slow train is explicitly *not* dominated — it is a real
trade-off, and there is a test asserting so.

**It does not estimate door-to-door time.** A flight is 80 minutes in the air and some
hours kerb to kerb, and the difference is real — but inventing it would be fabrication. Each
option states what it `excludes` ("airport transfers at both ends") so the caller can price
those legs properly.

### Three things the build turned up

- **Partial failure is the normal case, so it is designed for.** The first live call
  returned zero options and three clean reasons: flights `empty_valid`, trains
  `not_in_window`, cabs `unregistered_place`. Nothing aborted anything else. That is the
  `mmt_price_itinerary` pattern applied to modes.
- **Each mode names places in a different domain**, and a natural call exposes it
  immediately: "Bengaluru" → "GOI" is fine for flights, meaningless to the cab funnel.
  `cabs.place_candidates` now also tries the city names an IATA or station code maps to, and
  the response says which name it actually priced. Without this the tool half-fails on every
  realistic call.
- **Mode guards protect the flight budget.** No airport pair resolves for goa → kulem, so no
  flight search is spent on a 40 km day trip. There is a test that fails loudly if one ever is.

### Sub-calls go through the tool wrapper, deliberately

`_sub()` dispatches through `TOOLS[name]["fn"]` rather than calling `FL.search` directly, so
each leg lands in `calls.jsonl` as its own entry. Routing around the wrapper would have made
this one tool opaque to H6 and to flight-budget accounting — the exact thing the call log was
built to prevent. `calls_made` in the response makes the budget cost explicit too.

**This is a new tool, so hosts need one reconnect to see it** — `tools/list` is snapshotted
at connect.
