# makemytrip-mcp

An MCP server that prices Indian travel — **hotels, flights, trains and outstation cabs** —
from MakeMyTrip, so costing a trip is a question you ask rather than a browser session you
drive.

Runs anywhere that speaks MCP over stdio: **Claude Cowork** (as a plugin), **OpenClaw**,
**Claude Code**, or the Claude desktop app.

> **Read-only by design.** There is no booking, cart, payment or login path in this program,
> and none should be added. Every figure is a signed-out guest rate — a benchmark, not a
> reservation.

## What it gives you

| Tool | What it answers |
|---|---|
| `mmt_capabilities` | What can be priced, what the booking windows are, current health |
| `mmt_hotel_search` | City + dates → priced list, base/tax/all-in **per night**, plus a `nights x nightly` stay estimate |
| `mmt_find_hotel_id` | Property name → MakeMyTrip hotelId |
| `mmt_hotel_rates` | One property → every room type and rate plan, with meal plan and cancellation |
| `mmt_price_itinerary` | A multi-stop trip → per-leg table **and a total summed server-side** |
| `mmt_flight_search` | *Internal.* Route + date → fares per adult, base/tax apart *(slow — see note below)*. **Not listed to callers** — reached through `mmt_intercity_options` |
| `mmt_train_search` | *Internal.* Trains with live per-class status and fare; outside the 60-day window it also quotes the furthest bookable date as an **indicative** fare. **Not listed to callers** |
| `mmt_station_city` | Station codes → city codes, tying a rail leg to its hotel |
| `mmt_cab_quote` | *Internal.* Two places + date → every vehicle class, base/tax/all-in. **Not listed to callers** |
| `mmt_intercity_options` | **The interface for pricing a journey.** One leg by **flight, train and cab at once**, normalised to a party total with the source unit kept visible; marks options that are dearer *and* slower as `dominated` and leaves the choice to you |
| `mmt_cab_find_place` | Register a cab location by name (drives the site's own form) |
| `mmt_cab_add_place` | Register one from a pasted URL — the reliable manual path |
| `mmt_selftest` | Live check of what still works, and which tier the router is using |
| `mmt_setup_status` | Is the browser installed and working, and what to run if not |
| `mmt_version` | **The exact code this server is running** — git commit, path, uptime. Call first to confirm you are not talking to a stale process (see `.clinerules/mcp-server-sync.md`) |

## Install

```bash
git clone <your-repo> makemytrip-mcp
cd makemytrip-mcp
python -m pip install playwright
python tools/probe.py          # live acceptance harness - run this first
```

Then register it: **[docs/INSTALL.md](docs/INSTALL.md)** covers Claude Cowork, OpenClaw,
Claude Code and the desktop app.

Playwright's *Python package* is the only dependency, and even that is optional — without it
the server still starts, lists its tools and tells you what to install. It drives **Chrome or
Edge already on the machine**, so there is usually no 150 MB browser download.

## Where it must run

**On a machine with an ordinary residential connection.** MakeMyTrip's CDN returns HTTP 403
to datacenter IP ranges — verified directly, along with the same treatment for other Indian
travel sites. A cloud VM, CI runner or sandboxed container will be refused before any of this
code matters. Laptop or desktop: fine.

## How it works, briefly

Three execution tiers, chosen per endpoint by a circuit-breaking router, plus an
in-page-fetch POST path for the hotel JSON API:

| Tier | Mechanism | Used for |
|---|---|---|
| 0 | Plain `urllib` | The one JSON API with no bot sensor in front of it |
| 1 | Playwright's `context.request` — the browser's network stack, no page rendering | **Default.** Real TLS fingerprint and cookies at HTTP speed |
| 2 | Full page render | Bot-check interstitials, and driving forms |
| 2-POST | Full render + in-page `fetch()` | The hotel search JSON API from this network (T1's POST is Akamai-stubbed) |

The browser is **started as an ordinary process and attached to over the DevTools
protocol**, not launched by Playwright. On this network that is the difference between a
cab listing and a 169-byte stub; where no Chrome or Edge exists the server falls back to
Playwright's own launcher.

Tier 1 is the design's centre of gravity: it issues requests through a real Chromium without
paying for rendering, which is what makes an approach that would otherwise be blocked both
reliable *and* fast. Architecture and rationale: **[docs/DESIGN.md](docs/DESIGN.md)**.

## Things that will bite you

Documented at length in [docs/RUNBOOK.md](docs/RUNBOOK.md); the short version:

- **Four date formats.** Every tool takes ISO `YYYY-MM-DD`; the wire wants `MMDDYYYY`,
  `YYYYMMDD` or `DD-MM-YYYY` depending on which corner of the site you are in.
- **Silent 200s everywhere.** A wrong city code, a date outside the train booking window, or
  a trimmed config block all return HTTP 200 with nothing useful. Each has its own error kind
  so it never reads as "no availability".
- **`TOTAL_AMOUNT` is base only.** All-in is `BASE_FARE + TAXES`. A field named "total" that
  is not the total.
- **Trains have a 60-day wall; cabs do not.** Indian Railways opens reservations 60 days
  ahead. Cab pricing has no such limit — dates months out quote fine.
- **`availablityStatus`** is misspelled in MakeMyTrip's payload. Correcting it yields `None`
  for every train.
- **A flight search takes 30–60 seconds.** The flights API cannot be called directly — it
  gates on a session-generated token — so the server does what a person does: it drives the
  site's own search and reads the response the page receives. Ask for one route and date at
  a time. Everything else here answers in seconds.
- **Results routes need their funnel page first.** `/cabs/listing` and `/flight/search`
  answer a cold visit with a 169-byte stub whose body is the string `200-OK`. Loading
  `/cabs/` or `/flights/` first in the same page gets the real thing. This cost two bugs
  (BUG-7, BUG-8) before it was understood.
- **Flight results include nearby airports.** A Goa search returns itineraries into GOX
  (Mopa) and Sindhudurg as well as GOI. Each carries its own `from`/`to`, and anything
  landing elsewhere is flagged `alternate_airport` — not a fare into the airport you asked
  for.
- **Goa is two airports on MMT.** Goa (North) = GOX (Mopa), Goa (South) = GOI (Dabolim).
  Bare `goa` maps to `GOI`; say `goa north` or `mopa` for GOX.

## Tests

```bash
python tests/test_parsers.py   # 112 assertions, no network and no browser needed
python tests/test_version.py   # mmt_version record + sync against checkout HEAD, also offline
python tests/test_watch_server.py  # the dev supervisor (relay, restart, give-up), also offline
python tools/probe.py          # live gates
```

For live development, register the server to run `tools/watch_server.py` instead of
`server.py`: it supervises the child, reloads it on source changes, and restarts it after a
crash, so code edits behind a stable tool surface need no MCP reconnect. See
`docs/RUNBOOK.md` → *Developing the server live*.

The offline suite asserts on **structure and arithmetic** (`base + tax == all_in`), never on
particular prices — those drift daily.

## Legal

Unofficial. These are undocumented internal endpoints and MakeMyTrip's terms do not invite
automated access. Personal, low-volume, read-only use: request volume stays at roughly what a
person browsing would generate, with one stable device id and no scheduled polling. Don't
redistribute it, and stop if MakeMyTrip signals otherwise.
