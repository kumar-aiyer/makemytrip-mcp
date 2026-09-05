# Agent prompt — finish, verify and ship the `makemytrip` MCP server

Paste this whole file into Cline (or any coding agent) with this repository open as the
workspace. It is self-contained; everything it references is in the repo.

---

## 0. Read this first

This is **not a greenfield build.** A working reference implementation is already here, with
112 offline tests passing and the MCP protocol verified end to end. Your job is to finish the
parts that could not be completed without live network access from a residential connection,
verify the whole thing against the real site, and package it for the user's host.

**Do not rewrite what already works.** If you find yourself regenerating `mmt/rsc.py` or
`mmt/hotels.py::parse_rate_plans` from scratch, stop — those are validated against captured
payloads. Change them only when a live capture proves them wrong, and change the fixture and
test in the same commit.

Read in this order: `README.md`, `docs/DESIGN.md`, `docs/API-REFERENCE.md`,
`docs/RUNBOOK.md`. The API reference is authoritative on the wire format.

---

## 1. Mission

A local MCP server that prices Indian travel from MakeMyTrip — hotels, flights, trains and
outstation cabs — installable into **Claude Cowork** as a plugin and into **OpenClaw** as a
stdio server, running on the user's own laptop.

Success is not "the code runs". Success is: the user asks *"what would four nights in Kochi
in December cost, and how does the cab from Kochi to Rameswaram compare?"* and gets correct
numbers, with base and tax separated, in under ten seconds, with any limitation stated
plainly rather than silently swallowed.

---

## 2. Invariants — never violate these

1. **No booking path. Ever.** No tool may add to cart, hold inventory, select a fare, proceed
   to checkout, or submit a payment form. If a task seems to require posting to `/review`,
   `/checkout`, `/hold` or `/book`, it is out of scope by design, not by oversight.
2. **No authentication.** No login, session cookies, `mmt-auth` token, member rates, or
   credential storage. Every figure is a signed-out guest rate and that is correct. There are
   currently no credentials anywhere in this repo — keep that true.
3. **Never accept or store card, passport or identity data.** No tool takes such a parameter.
4. **Politeness.** One stable device id (never a rotating pool), concurrency capped at 4,
   150–400 ms jitter between batched calls, one retry maximum, no scheduled polling, no price
   history harvesting.
5. **Base and tax stay separate.** Every price surfaces as `base_inr`, `tax_inr`,
   `all_in_inr`. Never emit a single blended figure. This is a correctness rule, not a style
   preference — see §5.
6. **Prefer a clear error to an empty result.** Almost every failure on this site is a silent
   HTTP 200. Converting those into sentences a person can act on is the whole point of the
   server.
7. **Undocumented endpoints.** MakeMyTrip's terms do not invite automated access. Do not
   publish this to any registry or package index. Keep the note in the README.

---

## 3. What already exists and is verified

| Component | State |
|---|---|
| `server.py` — MCP stdio protocol, 13 tools | **Verified**: initialize, tools/list, tools/call, unknown method, unknown tool, clean shutdown. `tools/list` in <0.2 s with no browser |
| `mmt/rsc.py` — RSC unwrapping | **Verified** against fixtures, including chunks split mid-line and `$ref` resolution |
| `mmt/state.py` — `__INITIAL_STATE__` extraction | **Verified**, including a `}` inside a quoted string |
| `mmt/hotels.py` — body builder, flatten, summarise, rate-plan parser, URL builder | **Verified offline AND live (T2)**: hotel search Goa returns real priced hotels (`all_in == base + tax`) |
| `mmt/trains.py` — parser, 60-day window, station lookup | **Verified offline AND live**: `resolve_station("goa") == "MAO"`; SBC→MAO 2026-12-15 → `not_in_window`, `booking_opens=2026-10-16` |
| `mmt/cabs.py` — parser, place registry, URL builder | **Verified offline AND live**: places harvested for goa, panaji, kochi, rameswaram; regional-priority matcher |
| `mmt/router.py` — tiering and circuit breaker | **Verified** offline: degrade, open, recover. Ceilings updated: HOTEL_API→PAGE (T2-POST), FLIGHT_API→PAGE |
| `mmt/errors.py`, `mmt/cache.py`, `mmt/fetch.py`, `mmt/session.py` | **Verified live**: warmup NoneType crash fixed (PR #1); `_t2_post` in-page fetch added (BUG-3); cache validate-gate |
| `mmt/fetch.py::_t2_post` | **New (BUG-3 fix)**: clear_cookies → goto HOME → in-page `fetch` POST with browser-managed headers stripped. The only hotel-POST path from this network |
| `mmt/harvest.py` — cab place harvesting | **Verified live (BUG-5/6 fixes)**: dismisses login modal, clicks the from-city label, types into the react-autosuggest overlay, captures `autocomplete/v3` responses, prefers regional matches |
| `mmt/flights.py` — `parse_stream` | **Field names inferred. UNPROVEN — and currently UNREACHABLE from automation.** See BUG-7. |
| `tests/test_parsers.py` | **112 assertions, all passing**, no network or browser needed |
| `tools/probe.py` | Live gate harness — superseded by `harness/LIVE-TEST-PLAN.md` + the Cline registered server |

Run `python tests/test_parsers.py` before touching anything. If it is not 112/112, fix that
first: something in the environment is wrong.

**All of Phase 1's original checklist is now done except flights.** The bug log,
evidence chain and unblock paths are in `harness/findings.md` (BUG-1..BUG-7).

---

## 4. What you must do

### Phase 1 — establish a live baseline

**DONE 2026-09-04/05.** Hotels, trains and cabs verified live; 78 offline tests pass.
The remaining open item — flights — is thrown to a ClaudeCode session via
`harness/CLAUDECODE-PHASE1.md` (same-profile manual warm, or captured-fixture parser rewrite).
Probe from the user's laptop on a residential connection only.

### Phase 2 — finish flights (the main open work)

`mmt/flights.py::parse_stream` still guesses at itinerary field names, and — more
fundamentally — the search-stream endpoint refuses every automated path we tried from this
network (BUG-7). Do **not** re-run the failed experiments (they are catalogued in
`mmt/config.py` and `harness/findings.md`). Follow `harness/CLAUDECODE-PHASE1.md` and use one
of the two documented unblock paths:

1. **Same-profile manual warm**: launch headed Chrome with `--user-data-dir=<state>/chrome-profile`,
   search MMT flights as a human, close. The preflight cache + Akamai sensor state may then make
   `mmt_flight_search` work. If it does, wire the header set from `config.py` into the search.
2. **Captured fixture**: have the user copy a real `search-stream` response from their browser's
   DevTools into `tests/fixtures/flight_stream.json`; write the fixture test first, then rewrite
   `parse_stream` from the verified field names; delete the heuristic key-guessing.
3. Add `goa north`/`mopa` → `GOX` to `AIRPORTS` (MMT splits Goa into GOX North + GOI South).
4. Drop the "experimental" caveat in `mmt_flight_search` only once a live call returns verified
   itineraries.

### Phase 3 — finish cab place harvesting

**DONE 2026-09-05 (BUG-5/6).** `harvest_place` now: dismisses the login modal
(`commonModal__close`) and banner, clicks `label[for='fromCity']` to open the react-autosuggest
overlay, types into it, captures the `cabs.makemytrip.com/autocomplete/v3` response, and selects
by regional priority rather than blind ArrowDown+Enter. Places for goa/panaji/kochi/rameswaram
are registered. `mmt_cab_add_place` (paste a URL) remains the documented fallback.

### Phase 4 — resilience gates

Add to `tools/probe.py` and confirm:

- **Browser crash**: kill Chromium mid-call; the server must recover, retry once, and return
  real data.
- **No network**: airplane mode gives a `transport` error in under 5 s, not a 45 s hang.
- **Cache**: 20 rapid identical calls make at most 2 network calls.
- **Tier escalation**: set `ROUTER.force_min_tier = Tier.PAGE` and confirm `mmt_hotel_rates`
  still works via a full render.
- **Circuit breaker**: force repeated failures, confirm the circuit opens and fails fast
  rather than burning 12 s per call.

### Phase 5 — package and install

Follow `docs/INSTALL.md`. Build the Cowork `.plugin`, register with OpenClaw, and verify from
inside the host by asking for `mmt_setup_status` then `mmt_selftest`.

**Verify where Cowork plugins actually execute.** If they run in a sandboxed environment
rather than natively, they inherit a datacenter IP and will be refused with 403. Test this
early — it determines whether the Cowork route is viable at all, and the OpenClaw/laptop route
is the fallback.

---

## 5. Domain rules that are easy to get wrong

**Hotel prices are stay totals**, for the whole date range and room count — not per night.
Divide before comparing properties with different stay lengths.

**`TOTAL_AMOUNT` in the detail page payload is base only.** All-in is `BASE_FARE + TAXES`.
A field named "total" that is not the total; reading it as final under-reports by ~18%.

**The silent-null trap.** With a trimmed `expData` string or `featureFlags` block, the hotel
API returns HTTP 200 and the correct hotels with every `priceDetail` null. Send both complete.
A test asserting only "200 and some hotels" passes while the server returns nothing useful —
hence the dedicated `null_prices` error kind. Never "tidy up" those two constants.

**`availablityStatus` and `availablityDate`** are misspelled in MakeMyTrip's train payload
(no second `i`). Correcting the typo yields `None` and reports every train as unavailable.

**Four date formats.** ISO in the hotel API, `MMDDYYYY` in the hotel page URL, `YYYYMMDD` for
flights and trains, `DD-MM-YYYY` for cabs. Every public tool parameter takes ISO; convert once
per module at the boundary and unit-test each conversion.

**Cab place objects must be complete.** A trimmed one, or one missing `place_id`, returns zero
cabs with HTTP 200. Percent-encode spaces — a `+` inside the JSON blob is not reliably decoded.

**Trains have a 60-day booking wall; cabs have none.** Indian Railways opens reservations 60
days ahead and MakeMyTrip returns an empty page with HTTP 200 outside it. The cab date picker
looks like it has a similar limit, but the endpoint does not — dates months out quote fine.

**Bad city, station and airport codes fail silently** with valid-looking empty responses.

**A property returning nothing may simply not be sold on MakeMyTrip** — different from being
sold out, and worth distinguishing before anyone draws a conclusion.

---

## 6. Module contracts

Full signatures are in the source with docstrings. The contracts that matter across modules:

- `mmt/rsc.py` and `mmt/state.py` are **pure**. They import nothing from `fetch`, `router` or
  `session`. Keep it that way — it is why the offline suite needs no network.
- Domain modules expose `parse(html, **ctx) -> dict` as a pure function, and an
  `async search(...)` that fetches then parses. **Never merge them**; the pure half is the
  testable half.
- `mmt/fetch.py` is the only module that performs I/O. It owns tier selection, retries,
  caching and error classification.
- Any new tool goes in `mmt/tools.py` via the `@tool(name, schema)` decorator, which wraps it
  so exceptions become structured results rather than protocol errors. The **docstring is the
  description the model sees** — write it for someone who has never heard of MakeMyTrip, and
  state the units and any window.
- `server.py` does protocol and dispatch only: no HTTP, no parsing. Nothing but JSON-RPC
  frames on stdout; diagnostics to stderr.

---

## 7. Adding a capability

Worked example — local 8hr/80km cab day packages, deliberately not implemented:

1. Do the discovery **in a browser first**, with DevTools open. Find the URL and the payload.
2. Save a real trimmed payload into `tests/fixtures/`.
3. Write the pure parser plus its offline test. Get the test passing.
4. Add the `async search(...)` wrapper using `fetch.get_text` with an appropriate endpoint
   class, adding one to `mmt/router.py` if it needs different tiering.
5. Add the tool in `mmt/tools.py` with a schema and a real docstring.
6. Add a gate to `tools/probe.py`.
7. Update `docs/API-REFERENCE.md` and the capability list in `mmt_capabilities`.

Never skip step 2. A parser written from a description rather than a payload is a parser that
fails silently — which is precisely the failure mode this whole design exists to prevent.

---

## 8. Definition of done

1. `python tests/test_parsers.py` → all pass, no network, no browser.
2. `python tools/probe.py` → `Core hotel pricing: USABLE`, and every gate either passes or is
   documented in `docs/RUNBOOK.md` **with the affected tool degrading honestly**: a clear
   error naming the cause and the fallback, never an empty result that reads as "nothing
   found".
3. Installed and answering in at least one host (Cowork plugin or OpenClaw), verified by
   asking for `mmt_setup_status` and `mmt_selftest` from inside it.
4. Flights either work, or `mmt_flight_search` states its own limitation in its output.
5. Grep clean: no `book`, `checkout`, `payment`, `password`, `login` code path.
6. Every price path returns base, tax and all-in separately.
7. `mmt_price_itinerary` sums the legs it just fetched and returns the total in the same
   object.
8. `.gitignore` still excludes `.state/`, `chrome-profile/`, `diagnostics/` and `data.json`.
   `diagnostics/failures.jsonl` is metadata only (endpoint, kind, message, tiers).
9. README's "where it must run" note is still accurate for the chosen host.
10. Phase 2 acceptance passed: the reasoning-model run in `harness/PHASE2-TASKS.md` satisfied
    every mandatory honesty + gap-recovery gate, or each failure is logged in
    `harness/findings.md` with a tool-side fix.

---

## 9. Out of scope

- Booking, cart, hold, checkout, payment. **The hard line.**
- Login, member rates, loyalty numbers, `mmt-auth`.
- Holiday packages (quoted per enquiry, not searchable), buses, homestays.
- A Google Places integration to synthesise cab `place_id`s. The harvest-or-paste workflow is
  deliberate: it avoids a second API key and keeps the dependency list at one.
- Scraping at volume, scheduled polling, price-history collection.
- Any attempt to defeat a block that persists from a residential connection. If MakeMyTrip
  refuses consistently, stop.

---

## 10. Open questions — surface these, do not silently decide

1. Does the same-profile manual warm (opening MMT flights once in `<state>/chrome-profile`)
   actually unblock `mmt_flight_search`? Documented as Path A; unproven. Tested via
   `harness/CLAUDECODE-PHASE1.md`.
2. What is the real flight stream shape? Until Path A or B succeeds, `parse_stream` is
   unproven and the tool stays experimental.
3. Is `harvest_place` reliability acceptable as the primary path, or does the paste-a-URL
   fallback become the documented default? Currently the primary path works for goa/panaji.
4. Does state under `${CLAUDE_PLUGIN_ROOT}/.state` survive a plugin update? If not, saved cab
   places are lost on upgrade and `mmt_cab_add_place` should say where they live.

---

## 11. Working style

- Build order: offline tests → live baseline → flights → harvest → resilience → packaging.
- Commit after each passing gate, with the gate named in the message.
- When something is uncertain, write it into `docs/RUNBOOK.md` rather than guessing. A
  documented gap is a working feature; a silent wrong number is not.
- Prefer deleting a guess over keeping it beside the real implementation.
