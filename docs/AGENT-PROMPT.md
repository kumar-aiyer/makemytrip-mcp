# Agent prompt — finish, verify and ship the `makemytrip` MCP server

Paste this whole file into Cline (or any coding agent) with this repository open as the
workspace. It is self-contained; everything it references is in the repo.

---

## 0. Read this first

This is **not a greenfield build.** A working reference implementation is already here, with
63 offline tests passing and the MCP protocol verified end to end. Your job is to finish the
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
| `mmt/hotels.py` — body builder, flatten, summarise, rate-plan parser, URL builder | **Verified** offline. `all_in == base + tax`; `TOTAL_AMOUNT` correctly ignored |
| `mmt/trains.py` — parser, 60-day window, station lookup | **Verified** offline, including the `availablity` misspelling |
| `mmt/cabs.py` — parser, place registry, URL builder | **Verified** offline, compact and pretty-printed payloads |
| `mmt/router.py` — tiering and circuit breaker | **Verified** offline: degrade, open, recover |
| `mmt/errors.py`, `cache.py`, `fetch.py`, `session.py` | Written, exercised indirectly; **not yet live-tested** |
| `mmt/flights.py` — `parse_stream` | **Field names inferred. Unproven.** See §6 |
| `mmt/harvest.py` — cab place harvesting | **Written from the site's structure, never executed.** See §7 |
| `tests/test_parsers.py` | 63 assertions, all passing, no network or browser needed |
| `tools/probe.py` | Live gate harness — never yet run against the real site |

Run `python tests/test_parsers.py` before touching anything. If it is not 63/63, fix that
first: something in the environment is wrong.

---

## 4. What you must do

### Phase 1 — establish a live baseline

```bash
python -m pip install playwright
python tools/probe.py
```

**Do this from the user's laptop, on a residential connection.** MakeMyTrip's CDN answers
datacenter IPs with `403 AkamaiGHost` — verified — so a cloud VM, CI runner or container will
fail before any of this code matters. If every gate 403s, check where you are running before
debugging anything else.

Record which gates pass. Gates G0–G3, G5, G7, G8 should pass on a healthy machine. G4
(flights) is expected to fail or return an empty parse — that is Phase 2.

### Phase 2 — finish flights (the main open work)

`mmt/flights.py::parse_stream` guesses at itinerary field names. Fix it properly:

1. Call `mmt_flight_search` and capture the raw stream. When nothing parses, the tool already
   returns `raw_head`; for the full body, temporarily write `res.text` to
   `tests/fixtures/flight_stream.json`.
2. If it 403s with `Missing Header <x>`, add `<x>` to `config.flight_headers()`. The error
   names it. Known-good so far: `mcid`, `device-id`, `app-ver`.
3. Read the fixture. Find where itineraries actually live and what the fare, airline, flight
   number, times, duration and stop count are really called.
4. **Write the fixture test first**, then rewrite `parse_stream` against it. Delete the
   heuristic key-guessing entirely — do not leave both paths in.
5. Extend `mmt_flight_search`'s docstring to drop the "experimental" caveat only once G4
   passes.

### Phase 3 — finish cab place harvesting

`mmt/harvest.py::harvest_place` drives MakeMyTrip's cab search form to capture a place object
with a Google `place_id`, because no autosuggest endpoint exists. It has never been run.

Run it with `MMT_HEADFUL=1` and watch. Expect to adjust: the selector for the location field,
the URL fragment that identifies the autosuggest response, and the timing. The field is
genuinely flaky — the overlay input sometimes does not take focus, so the click-wait-type
sequence is retried once, and **nothing must be interleaved between the click and the type**
or the overlay closes.

If harvesting proves unreliable, that is acceptable: `mmt_cab_add_place` (paste a URL) is the
documented fallback and always works. Say so in the tool's own output rather than failing
opaquely.

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
8. `.gitignore` still excludes `.state/`, `chrome-profile/`, `diagnostics/` and `data.json` —
   diagnostics dumps contain full response bodies.
9. README's "where it must run" note is still accurate for the chosen host.

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

1. Do Cowork plugins execute natively on the user's machine or in a sandbox? Determines
   whether the Cowork route works at all (§4 Phase 5).
2. What is the real flight stream shape? Until answered, the tool is experimental.
3. Is `harvest_place` reliable enough to be the primary path, or does the paste-a-URL fallback
   become the documented default?
4. Does state under `${CLAUDE_PLUGIN_ROOT}/.state` survive a plugin update? If not, saved cab
   places are lost on upgrade and `mmt_cab_add_place` should say where they live.

---

## 11. Working style

- Build order: offline tests → live baseline → flights → harvest → resilience → packaging.
- Commit after each passing gate, with the gate named in the message.
- When something is uncertain, write it into `docs/RUNBOOK.md` rather than guessing. A
  documented gap is a working feature; a silent wrong number is not.
- Prefer deleting a guess over keeping it beside the real implementation.
