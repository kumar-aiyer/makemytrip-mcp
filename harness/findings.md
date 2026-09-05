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
