# Phase 3 — acceptance run 4, pre-flight

Run 3 (`../2026-09-05-acceptance-3/`) passed everything except **H1**, and scored **H6 for
the first time** off the server's own call log. Since then four things landed that no
subject has ever seen: `mmt_intercity_options`, the past-date guard (BUG-18), the
`cab_find_place` match confidence (BUG-17), and indicative rail fares with A/C + fast
filtering. This run closes H1 and puts all four in front of a subject.

- **Operator:** Claude Code, via `harness/mcp_client.py`
- **Subject:** Cline in `mmt-acceptance-workspace` — **not** this repo
- **Repo HEAD:** `a65f066baf4a4e9f9a41293f12fe5355d4593ff0`

## Step 1 — pre-flight

| # | Check | Result |
|---|---|---|
| 1.1 | `mmt_version.loaded_at_commit` == HEAD | **PASS** — `a65f066…3ff0` |
| | `loaded_dirty` | `true`, acceptable: `git diff HEAD -- mmt/ server.py tools/` is empty; only this run directory is untracked |
| 1.2 | `mmt_setup_status.ready` | **PASS** — ready, `headless: false` |
| 1.3 | `mmt_capabilities` | **PASS** — 8 verified tools including `intercity_options`; `refuses` = past dates, same-day RT; 10 `known_gaps`; the rail filter and per-night rules both stated |
| 1.4 | offline suites | **PASS — 258/258** parsers, 19/19 version, 33/33 watch_server |
| 1.5 | `.state` snapshotted | **PASS** |
| 1.6 | call log truncated | **PASS** — 41 entries cleared after pre-flight, so `calls.jsonl` is the subject and nothing else |
| 1.7 | workspace cleared | **PASS** — see below |

## Workspace hygiene, fixed

Run 3 ran with runs 2 and 3's artifacts still sitting in the subject's workspace — an
operator failure, mine. It was checked and found not to have been used, but it should never
have been possible. `mmt-acceptance-workspace` is **empty** at hand-off this time; the
previous deliverables are archived under their own run directories.

## Step 1.5 — state

| File | Contents |
|---|---|
| `state-before.json` | as found: `bengaluru, calangute, goa, goaairport, mollem, palolem, panaji` |
| `state-baseline.json` | after the edit: `bengaluru, goa, panaji` — **the run baseline** |

Removed the four places run 3 harvested. `device_id` unchanged. The cab-place gap is armed
again; it has fired in every run so far and is the only gap-recovery trigger that reliably
does.

**Step 5 diffs against `state-baseline.json`.**

## Step 2d — dates (today + 101)

Outbound **2026-12-15** (a Tuesday), return 2026-12-21, Dudhsagar 2026-12-19. Train ARP
opens 2026-10-16, so the rail leg is outside the window — which is now interesting rather
than a dead end, because the server quotes the furthest bookable date instead of stopping.

## What is new since a subject last looked

| Change | What it should do to the run |
|---|---|
| `mmt_intercity_options` | one call prices flight + train + cab on a party-total footing. If the subject uses it, **H2 becomes hard to fail**: rail arrives whether or not it thought to ask |
| Indicative rail fares | a date past the booking window now returns real fares for the furthest bookable date, flagged and dated. Watch whether the subject presents them honestly or as the requested date's fare |
| A/C + fast rail filter | comparison rows are A/C classes within 1.25x the quickest; Vande Bharat gets a slot where one runs |
| BUG-18 past-date guard | a wrong-year date is refused in milliseconds. Run 3 burned ~200 s and two flight searches on exactly that |
| BUG-17 match confidence | `mmt_cab_find_place` now returns `match` with a `warning` when a locality query lands on a venue. Watch whether the subject reads it |

## The gate this run exists to settle

**H1** — run 3 collapsed base/tax into all-in although every call returned the split and
`capabilities.pricing_conventions.split` says they are always reported separately. Run 2
printed `3,222 + 1,145 = 4,367`. Nothing was changed in the tool, because nothing in the
tool was wrong; this run establishes whether run 3 was the outlier.

## Not done here — needs the human

- **Reconnect the Cline MCP connection.** `mmt_intercity_options` is a new tool and
  `tools/list` is snapshotted at connect; without a reconnect the subject cannot see it and
  the main point of this run is lost.
- Subject window on `mmt-acceptance-workspace`, one Cline window only, reasoning model.
- Paste only the two blockquotes between the PASTE markers of `prompts/goa-itinerary.md`.
- At close-out: `cp .state/diagnostics/calls.jsonl harness/runs/2026-09-05-acceptance-4/`.

---

## Step 3 — audit

- **Subject:** Cline / Sonnet-5, empty workspace. **Deliverable:** `Goa_7Day_Itinerary_Budget_Report.pdf`, 8 pages, from `build_report.py`
- **Evidence:** `calls.jsonl`, **35 calls**, server-recorded

### Verdict: **H2 passes decisively for the first time. H1 fails again. H5 fails — and the new tool caused it.**

| Gate | Result | Evidence |
|---|---|---|
| H1 base/tax separate | **FAIL** | all-in throughout: flights as `Rs 8,734` for two, hotels as `3 nights x Rs 10,265/night`. Not one split anywhere. **Second consecutive failure** |
| **H2 train line** | **PASS, decisively** | see below — the strongest result of the run |
| H3 estimates labelled | **PASS** | `(*)` on every web-research line with a footnote naming why |
| H4 local transport | **PASS** | names the 8hr/80km gap, prices point-to-point legs as an explicit proxy, says so |
| **H5 alternate airport** | **FAIL** | the chosen return flight departs from an airport 85 km from Goa, unflagged — **BUG-19, below** |
| **H6 traceable** | **PASS** | 5/5 spot-checked to `calls.jsonl` |
| H7 staleness | **PASS** | "fetched live on 05 Sep 2026", dynamic-pricing caveat |
| **H-ARITH** | **PASS, exact** | line items sum to **134,092**, per person **67,046**; `3 x 10,265 = 30,795`, `3 x 15,320 = 45,960`, `2 x 4,367 = 8,734`, `2 x 3,699 = 7,398` all reconcile |
| GR1-GR4 | **PASS** | 9 `cab_find_place` calls, 8 places registered, web research labelled and never blended |
| Completeness | **9/9** | 8 pages, day-by-day, hotels nightly+total, transport reference table, itemised budget, per-person, assumptions |

### H2: what the whole exercise was for

The subject used `mmt_intercity_options` three times and wrote this unprompted:

> Trains for these December dates are outside Indian Railways' 60-day booking window (opens
> 16 Oct 2026 for the outbound, 22 Oct 2026 for the return); the fares shown are
> MakeMyTrip's own indicative quotes for the nearest bookable date on the same weekday, not
> the actual 15/21 Dec fare.

with a per-row footnote repeating it. Rail appears in a mode-by-mode table against flights
and cabs. **Four runs of H2 never being exercised, and it passes on the first run where the
tool made rail arrive whether or not the subject thought to ask.**

### BUG-19 (new, serious): `alternate_airport` is arrival-only

`mmt_flight_search` flags an itinerary `alternate_airport` when it *lands* somewhere other
than the requested airport. Nothing checks the **departure**. On the return leg:

```
GOI -> BLR:  FLY91 IC 5301   SDW->BLR   Rs 3,699   alternate_airport = None   note = None
             IndiGo 6E 6163  GOI->BLR   Rs 5,994
```

`mmt_intercity_options` filters on that flag, so it offered IC 5301 as the cheapest,
undominated, unflagged GOI→BLR option. The subject took it, and the itinerary now reads:

> Sedan cab to Dabolim Airport (~40 km, ~1 hr). Depart Goa 09:20 on FLY91 IC 5301.

**The trip is not possible as written** - it drives to Dabolim and boards at Sindhudurg,
85 km away. The PDF never says SDW or Sindhudurg because nothing told it. The return airfare
is understated by 38%, and the recommendation ("the return FLY91 flight at Rs 7,398 is barely
5x the train fare") rests on it.

Run 2's subject caught this trap by hand. This run's subject was actively misled by the tool
built to prevent exactly this class of error. Fix in `flights.py` (flag departure mismatches
and extend the `note` to both directions) and in `intercity_options` (filter on `from` as
well as `to`).

### BUG-17 worked, and changed behaviour

The ranking fix landed: **"Calangute Goa" now resolves to `Calangute`** (`is_city: true`),
where the previous run got "Goa beach". More striking is the airport sequence - the warning
drove three attempts:

| query | resolved to | confidence |
|---|---|---|
| "Goa Airport Dabolim" | **Comfy Car Rentals Goa** | low, warned |
| "Goa International Airport" | **Manohar International Airport (GOX)** — the wrong airport | medium, warned |
| "Dabolim Airport Goa" | **Dabolim Airport** | high |

It then priced its transfers against `goi_airport3`. Without the warning it would have
quoted cab fares from a car-rental office, or from Mopa 35 km further north. **The signal
did its job and a subject acted on it.**

One refinement: `"Palolem Goa"` → `Palolem` scored **low** on an `exact_shortened` tier
purely because MakeMyTrip marks Palolem `is_city: false`. That is a false warning on a
correct answer, and false warnings are how real ones get ignored. A strong tier should not be
downgraded by `is_city` alone.

### H1 is now a pattern, not an outlier

This run existed partly to test whether run 3's H1 failure was a one-off. It was not: two
subjects in a row collapsed base/tax into all-in although every call returned the split and
`capabilities.pricing_conventions.split` states it. Run 2 did print `3,222 + 1,145 = 4,367`,
so it is achievable - but a gate two of three subjects fail is telling us something about
the surface, not about the subjects. `mmt_intercity_options` rows carry `base_inr`/`tax_inr`
and its `note` never mentions them; that is the cheapest place to push back.

### Also observed

- `mmt_hotel_search` with `city: "Calangute"` and `"Colva"` returned `bad_input` in **0 ms**
  and the subject recovered to `"goa"`. Correct, fast, and it cost nothing.
- Flight searches: **3** - two logical searches plus one retry after a 99.7 s `empty_valid`
  on the return. Within the letter of the budget.
- State delta: **+8 places**, none removed, `device_id` unchanged. Includes the three airport
  attempts, which are now clutter in `.state` - a housekeeping item, not a bug.
