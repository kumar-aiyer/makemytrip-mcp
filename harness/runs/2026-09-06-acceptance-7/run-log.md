# Phase 3 — acceptance run 7, pre-flight

Run 6 confirmed BUG-19 and BUG-20 fixed in a subject's hands, but failed H1 and H2 — both
because the subject never called `mmt_intercity_options` and so never met either the rail
comparison or the base/tax instruction that lived in its note.

The response was to remove the choice: **the single-mode searches are no longer advertised.**
This run tests whether that works, and whether hotels — untouched by the hide — still lose
the base/tax split.

- **Operator:** Claude Code, via `harness/mcp_client.py`
- **Subject:** Cline in `mmt-acceptance-workspace` — **not** this repo
- **Repo HEAD:** `b57e743c7ad886c7c57a08220ebe8e79ed6d2c15`

## Step 1 — pre-flight

| # | Check | Result |
|---|---|---|
| 1.1 | `mmt_version.loaded_at_commit` == HEAD | **PASS** — `b57e743…2c15`, server code clean |
| 1.2 | `mmt_setup_status.ready` | **PASS** — ready, `headless: false` |
| 1.3 | `mmt_capabilities` | **PASS** — `verified` is now hotel_search, hotel_rates, price_itinerary, **intercity_options**, station_city; 2 `refuses`; 10 `known_gaps` |
| 1.4 | offline suites | **PASS — 308/308**, 19/19, 33/33 |
| 1.5 | `.state` snapshotted | **PASS** — 11 places → `bengaluru, goa, panaji` |
| 1.6 | call log truncated | **PASS** — 60 entries cleared after pre-flight |
| 1.7 | workspace cleared | **PASS** — run 6 archived first |
| 1.8 | **tools/list over real MCP** | **12 advertised**, and `mmt_flight_search` / `mmt_train_search` / `mmt_cab_quote` confirmed **absent** |
| 1.9 | environment | one watcher (12692) → one server (151048), `chrome_on_profile=0` |

## Dates

Outbound **2026-12-16** (Wed), return 2026-12-22, ARP opens 2026-10-17 — the rail leg is
still outside the booking window, so the indicative quote path stays in play. Same dates as
run 6, so run 6's numbers are a direct comparator.

## ⚠ A reconnect is mandatory this time

Runs 5 and 6 did not need one. This one does: **the hide is a `tools/list` change**, and a
host snapshots that list at connect. Without a reconnect Cline will still believe
`mmt_flight_search`, `mmt_train_search` and `mmt_cab_quote` exist, will call them — they are
still callable by name — and the run will measure nothing.

Confirm after reconnecting that the Cline MCP panel shows **12** tools and that the three are
gone.

## What this run is testing

**Does removing the choice fix H2?** Five of six runs had no rail line. The one that passed
used the comparison tool. If a subject with no alternative still produces an itinerary
without a train row, the problem was never tool discovery.

**Does it fix H1 for flights, and do hotels still fail?** The base/tax instruction is now in
the intercity note *and* in `mmt_hotel_search` / `mmt_hotel_rates`. Run 6 failed the split on
both flight and hotel rows. Hotels were 32 of its 53 calls and 45% of its budget, and hiding
intercity tools does nothing for them — so hotels are the real test of whether
"put the guidance where the caller is looking" generalises.

**Does one door cost more?** Measured on the operator side already: `goa → panaji` through
`mmt_intercity_options` costs one cab quote in 31 s, with the flight and train skips
explained. Watch whether the subject's total call count rises against run 6's 53.

**Two things the hide required, now in front of a subject for the first time:** the tightened
station guard (a five-letter place like `colva` no longer triggers a train search) and
`pickup_time` on the comparison tool (run 6 used 14:00 for an airport transfer; without it
every transfer would be pinned to 10:00).

## Not done here — needs the human

- **Reconnect the Cline MCP connection, and verify 12 tools.** Non-optional this run.
- Subject window on `mmt-acceptance-workspace`, one Cline window, reasoning model.
- Paste the prompt with the date as **December 16th**.
- At close-out: `cp .state/diagnostics/calls.jsonl harness/runs/2026-09-06-acceptance-7/`.
