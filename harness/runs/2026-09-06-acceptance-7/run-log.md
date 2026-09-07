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

---

## Step 3 — audit

- **Subject:** Cline / Sonnet-5, empty workspace. **Deliverable:** `Goa_Itinerary_Dec2026.pdf`, 9 pages
- **Evidence:** `calls.jsonl`, **36 calls** (down from run 6's 53), server-recorded

### Verdict: **clean sweep. Every mandatory gate passes, inside the call budget, with nothing unscoreable.**

| Gate | Result | Evidence |
|---|---|---|
| **H1 base/tax separate** | **PASS** | declared on the cover — *"Flight and cab figures show base + tax separately"* — with `Base`/`Tax` columns in the mode table, and hotels as `Nightly base 6,163 / Nightly tax 557 / Nightly all-in 6,720` |
| **H2 train line** | **PASS** | train rows on **both** legs of a full mode-comparison table |
| H3 estimates labelled | **PASS** | `[MMT]` / `[EST]` on every figure with a legend explaining why EST exists |
| H4 local transport | **PASS** | names the 8hr/80km gap explicitly and prices EST day-hire against MMT point-to-point |
| H5 alternate airport | **PASS** | zero mentions of SDW or GOX; all three flight rows per leg are GOI |
| H6 traceable | **PASS** | 4/4 spot-checked, including `6,163` → `rate_plans[0].nightly_base_inr` |
| H7 staleness | **PASS** | "live indicative quote … on 6 Sep 2026, signed-out retail rate, subject to change and **NOT a booking**" |
| **H-ARITH** | **PASS, exact** | categories sum to **1,37,762**, per person **68,881**; `9,644+2,450 = 12,094`, `8,054+3,304 = 11,358`, `6,163+557 = 6,720 x4 = 26,880`, `12,094+11,358 = 23,452` |
| GR1-GR4 | **PASS** | 8 `cab_find_place` calls, 8 registered, EST never blended with MMT |
| Completeness | **9/9** | 9 pages |
| **Call budget** | **respected** | **2 flight searches**, both inner to `mmt_intercity_options`, both successful |

### The hide worked, and the shape of the run changed

`mmt_intercity_options` was called **10 times** and is now the only route to a priced leg:

```
Bengaluru -> Goa        2026-12-16   27s  9 options  ran=[cab,flight,train]
Goa -> Bengaluru        2026-12-23   29s  9 options  ran=[cab,flight,train]
Goa Airport -> Vagator  2026-12-16   12s  3 options  ran=[cab]
Vagator -> Old Goa      2026-12-18   10s  3 options  ran=[cab]
Vagator -> Benaulim     2026-12-20   11s  3 options  ran=[cab]
Benaulim -> Colva       2026-12-21   12s  3 options  ran=[cab]
Benaulim -> Goa Airport 2026-12-23   11s  3 options  ran=[cab]
Old Goa -> Benaulim     2026-12-20   12s  3 options  ran=[cab]
```

Six local transfers cost **one cab quote each**, 10-12 s — the mode guards and the tightened
station guard doing exactly what they were built for, in a subject's hands for the first
time. **Total calls fell from 53 to 36.** Narrowing the interface made the run cheaper, not
more expensive.

### H2 passed the way it was designed to

The report carries a per-leg table of flight, train and cab with `Base`, `Tax`,
`Total (2 pax)` and a **Dominated?** column — the comparator's own output, rendered. And the
caveat, unprompted:

> *Train fares are indicative — this route falls outside IRCTC's 60-day booking window until
> 17 Oct 2026, so MakeMyTrip quoted the nearest priced date (4 Nov 2026, same weekday
> pattern) as a stand-in for comparison, not the 16 Dec fare itself.*

4 Nov 2026 is a Wednesday, matching 16 Dec. The weekday matching in `furthest_bookable` has
now been exercised on a second day of the week and reported correctly.

### H1: the answer to the question this run existed to ask

Run 6 failed the split on flight **and hotel** rows. The intercity note fixed the first; the
second only moved once the same instruction went into `mmt_hotel_search` and
`mmt_hotel_rates`. It is now on the cover, in the mode table, and in the hotel table.

**"Put the guidance where the caller is looking" generalises.** Three runs of evidence: silent
schema → collapsed (runs 3, 4); instruction in the comparison tool → split, but only for
tools that route through it (run 5, then run 6 bypassed it); instruction in every priced
tool → split everywhere (run 7).

### BUG-18 fired in a subject's hands, for the first time

```
ERR Bengaluru->Goa    2025-12-16 | date 2025-12-16 is in the past.
ERR Goa->Bengaluru    2025-12-23 | date 2025-12-23 is in the past.
```

The subject resolved "December 16th" to **2025**, was refused in **0 ms twice**, and
corrected. Run 3 made the identical mistake and paid ~200 seconds and two flight searches for
it. The guard is worth what it cost.

### BUG-17: 7 of 8 clean

`Dabolim Airport`, `Calangute Beach`, `Colva Beach`, `Anjuna Beach`, `Panaji`,
`Vagator Beach`, `Benaulim Beach` all `high` on the first attempt — no repeat of run 4 and
run 6's three-attempt airport hunt, because the query happened to be written name-first.

One residual false warning: `"Old Goa Basilica of Bom Jesus"` → `Basilica of Bom Jesus`,
graded `low` because `basilica` is not in the venue-word list (which has `church`, `temple`,
`fort`). The answer was right. Also worth noting **only 1 of 8 registered places has
`is_city: true`** — the correct answers here are beaches and an airport — which is why
downgrading a strong tier on `is_city` alone was wrong, and confirms that fix.

### State delta

**+8 places**, none removed, `device_id` unchanged.

### Phase 3

**Closed.** Every mandatory gate passes on one run, within budget, from a subject that saw
only the narrowed interface, with the evidence produced by the server itself.
