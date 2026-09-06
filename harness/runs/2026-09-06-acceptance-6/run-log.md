# Phase 3 — acceptance run 6, pre-flight

Run 5 passed **every mandatory gate** — the first clean sweep — but was ambiguous on the
call budget because four of five flight searches failed (**BUG-20**), and that failure also
denied the run any return-leg data, so **BUG-19's departure exclusion was never exercised by
a subject**. BUG-20 is fixed (`900e9bd`). This run is to get a clean sweep that is also
unambiguous.

- **Operator:** Claude Code, via `harness/mcp_client.py`
- **Subject:** Cline in `mmt-acceptance-workspace` — **not** this repo
- **Repo HEAD:** `900e9bd32f37a6f881b5b3f52a07638b31cbeea8`

## Step 1 — pre-flight

| # | Check | Result |
|---|---|---|
| 1.1 | `mmt_version.loaded_at_commit` == HEAD | **PASS** — `900e9bd…eea8`, server code clean against HEAD |
| 1.2 | `mmt_setup_status.ready` | **PASS** — ready, `headless: false` |
| 1.3 | `mmt_capabilities` | **PASS** — 8 verified tools incl. `intercity_options`, 2 `refuses`, 10 `known_gaps` |
| 1.4 | offline suites | **PASS — 285/285**, 19/19, 33/33 |
| 1.5 | `.state` snapshotted | **PASS** |
| 1.6 | call log truncated | **PASS** — 47 entries cleared after pre-flight |
| 1.7 | workspace cleared | **PASS** — run 5's deliverables archived first |
| 1.8 | environment | one server, `chrome_on_profile=0` |

## Step 1.5 — state

`state-before.json` held ten places from run 5. `state-baseline.json` is back to
`bengaluru, goa, panaji`, `device_id` unchanged. **Step 5 diffs against the baseline.**

## Step 2d — dates: **the run date moved**

The clock rolled over to **2026-09-06**, so today + 101 is now **2026-12-16, a Wednesday** —
not the 15th every previous run used. This is the floating-date design doing its job: the
prompt must be edited, and a subject cannot coast on a date another run established.

| Leg | Date |
|---|---|
| Outbound | **2026-12-16** (Wed) |
| Return | **2026-12-22** |
| Dudhsagar day trip | 2026-12-20 |
| Train ARP opens | 2026-10-17 — still outside the window, as intended |

**The pasted prompt must say "December 16th".** Every earlier run said the 15th.

A useful side effect: the indicative rail quote will now land on a Wednesday rather than the
Tuesday all previous runs saw, so the weekday-matching in `furthest_bookable` gets exercised
on a different day of the week for the first time.

## What this run is testing

**BUG-20's fix, in the hands of a subject.** Run 5 lost 6.6 minutes and its whole return leg
to `empty_valid` after ~99 s. The harvester now re-visits the funnel once inside the call and
says `blocked` in ~30 s if that fails. Live checks after the fix returned the previously
failing GOI→BLR leg in 35 s and 28 s. If flight searches now succeed first time, the budget
question that clouded run 5 disappears.

**BUG-19, finally exercised by a subject.** Every previous return-leg search failed, so no
subject has yet seen a GOI→BLR result with the departure exclusion applied. Live, that route
reports **13 of 25 itineraries departing from a different airport**. If the subject ends up
on a Sindhudurg flight again, the fix is wrong.

**H1, second confirmation.** It passed in run 5 after one sentence was added to the
`intercity_options` note. One pass is not a pattern.

**BUG-17's last gap.** A region-first query ("Goa Dabolim Airport") still falls through to
`fallback` because variants are stripped only from the right. Watch whether the subject
writes its airport query region-first and whether the resulting warning helps or annoys.

## Not done here — needs the human

- No reconnect needed: no tool added or removed since run 5, and the watcher hot-reloads code.
- Subject window on `mmt-acceptance-workspace`, one Cline window, reasoning model.
- **Paste the prompt with the date changed to December 16th.**
- At close-out: `cp .state/diagnostics/calls.jsonl harness/runs/2026-09-06-acceptance-6/`.

---

## Step 3 — audit

- **Subject:** Cline / Sonnet-5, empty workspace. **Deliverable:** `Goa_7Day_Itinerary_Budget.pdf`, 10 pages
- **Evidence:** `calls.jsonl`, **53 calls**, server-recorded

### Verdict: **BUG-20 and BUG-19 both confirmed fixed in a subject's hands. H1 and H2 fail — and they fail for the same reason.**

| Gate | Result | Evidence |
|---|---|---|
| H1 base/tax separate | **FAIL** | flights as `Fare/adult Rs 6,047`, hotels as `Rate/night Rs 14,700`. Every "base"/"tax" hit in the PDF is incidental ("each base", "city taxes") |
| H2 train line | **FAIL** | **zero** occurrences of train, rail or IRCTC. `mmt_train_search` never called |
| H3 estimates labelled | **PASS** | a `Source` column on all 20 lines: `MMT live` / `Web research` / `Assumption` |
| H4 local transport | **PASS** | scooter and local hops priced, marked "not an MakeMyTrip product — web-researched" |
| **H5 alternate airport** | **PASS, emphatically** | see below |
| H6 traceable | **PASS** | 5/5 spot-checked |
| H7 staleness | **PASS** | "captured 06-Sep-2026", "signed-out, non-member retail quotes valid at time of search" |
| **H-ARITH** | **PASS, exact** | 20 line items sum to **131,535**; the seven category subtotals independently sum to the same; per person **65,768**; `3 x 14,700 = 44,100`, `3 x 5,096 = 15,288`, `2 x 6,047 = 12,094`, `2 x 6,624 = 13,248` |
| GR1-GR4 | **PASS** | 9 `cab_find_place` calls, 8 places registered |
| Completeness | **9/9** | 10 pages |

### BUG-20: fixed, and the evidence is unambiguous

**Two flight searches, both successful, no caller retries.** Exactly the budget, for the
first time in four runs.

```
BLR->GOI  2026-12-16   28 s   25 itineraries
GOI->BLR  2026-12-22  116 s   25 itineraries
```

The 116-second call is the fix working, not a regression: run 5 failed this exact leg three
times at ~99 s each and never got data. The harvester now detects the missing stream at 30 s,
re-visits the funnel inside the call, and comes back with a full result set. **A slow success
instead of three fast-ish failures, and the caller spends one search instead of three.**

### BUG-19: fixed, and the subject used it

Unprompted, in the flights section:

> Cheapest non-alternate-airport IndiGo fares from MakeMyTrip's 25-itinerary result set for
> each date. A FLY91 fare at Rs 3,099/adult exists on both dates but lands at Sindhudurg
> (SDW), 1.5–2 hrs further from both hotels than Dabolim — **excluded as false-cheap**.
> MakeMyTrip flags **13 of 25 itineraries per search** as landing at GOX (Mopa) or SDW;
> these were also excluded.

Run 4's subject walked into this trap and produced an itinerary that drove to Dabolim and
boarded 85 km away. This subject saw the flag, understood it, named it "false-cheap" and
excluded it on **both** legs. The departure-side flagging that BUG-19 added is what made the
return leg's 13 exclusions visible at all.

### H1 and H2 failed for one reason: the subject never called `mmt_intercity_options`

Not once, despite `mmt_capabilities` being its first call and that tool being listed there as
"PREFER THIS for an intercity leg". It went to `mmt_flight_search`, `mmt_hotel_search` and
`mmt_cab_quote` directly.

That single choice caused both failures:

- **H2** — rail only reaches a subject through `intercity_options` or a deliberate
  `mmt_train_search`. Bypass the first and forget the second, and the itinerary has no train
  line at all. This is the fifth run of six with no rail, and the one that passed is the one
  that used the comparison tool.
- **H1** — the base/tax guidance added after run 4 lives **only** in `intercity_options`'
  `note`. `mmt_flight_search` and `mmt_hotel_search` say nothing about reporting the split,
  so a subject using them directly never sees the instruction that moved run 5.

**The fix is to stop making one tool the sole carrier of guidance that applies to all of
them.** The split rule belongs in the flight and hotel tool docstrings and notes too; the
rail-exists rule belongs wherever a one-way intercity leg is priced. Run 5 did not prove the
nudge works in general - it proved it works *in the tool that carries it*.

### BUG-21 (new, low): every cab route reports `distance_km: 40`

All nine cab quotes came back `km=40`, whatever the endpoints - Agonda→Mollem (~70 km),
Calangute→Old Goa (~15 km) and Airport→Calangute (~40 km) alike. The subject noticed and said
so: *"Every cab route above quotes at ~40 km / ~4-hour hire slot regardless of actual
endpoints — this is MakeMyTrip's standard outstation package granularity."*

It is MakeMyTrip's own summary rather than our parse, but we surface it as `distance_km` and
derive `all_in_per_km_inr` from it, so both are unreliable on short routes. It is also the
source of BUG-15's odd "4 hr" for a 40 km leg. Worth either suppressing the derived per-km
figure when the distance looks like a package bucket, or labelling it as one.

### BUG-17's residual gap, second run running

`"Goa Airport Dabolim"` → **"Comfy Car Rentals Goa"** (low, warned), then the subject retried
`"Dabolim Airport Goa"` → **"Dabolim Airport"** (high). Exactly run 4's sequence. The warning
works and the subject self-corrects, but a region-first query costs it an extra ~20 s lookup
every time because variants are stripped only from the right. Two runs of the same avoidable
detour is enough evidence to fix it.

Otherwise the harvest was good: 8 places, `Calangute`, `Palolem`, `Agonda Beach`, `Mollem`,
`Arpora`, `Cabo de Rama Fort` all clean and high-confidence.

### State delta

**+8 places**, none removed, `device_id` unchanged.
