# Phase 3 — acceptance run 5, pre-flight

Run 4 passed nine gates and failed two, both of them ours. This run re-tests exactly those
two after the fixes in `5984678`; everything else it re-tests for free.

- **Operator:** Claude Code, via `harness/mcp_client.py`
- **Subject:** Cline in `mmt-acceptance-workspace` — **not** this repo
- **Repo HEAD:** `59846782e5174ee6f271720752930edd4690c54d`

## Step 1 — pre-flight

| # | Check | Result |
|---|---|---|
| 1.1 | `mmt_version.loaded_at_commit` == HEAD | **PASS** — `5984678…0c54d` |
| | server code vs HEAD | clean — `git diff HEAD -- mmt/ server.py tools/` is empty |
| 1.2 | `mmt_setup_status.ready` | **PASS** — ready, `headless: false` |
| 1.3 | `mmt_capabilities` | **PASS** — 8 verified tools incl. `intercity_options`, 2 `refuses`, 10 `known_gaps` |
| 1.4 | offline suites | **PASS — 271/271**, 19/19, 33/33 |
| 1.5 | `.state` snapshotted | **PASS** |
| 1.6 | call log truncated | **PASS** — 40 entries cleared after pre-flight |
| 1.7 | workspace cleared | **PASS** — run 4's deliverables archived first, workspace empty |
| 1.8 | environment | one server, `chrome_on_profile=0` |

## Step 1.5 — state

`state-before.json` held eleven places, including run 4's three airport attempts
(`goi_airport`, `goi_airport2`, `goi_airport3`). `state-baseline.json` is back to
`bengaluru, goa, panaji`; `device_id` unchanged. **Step 5 diffs against the baseline.**

## Dates

Outbound **2026-12-15**, return 2026-12-21, Dudhsagar 2026-12-19. Unchanged, so the prompt
needs no substitution.

## What this run is testing

**H5 — the gate run 4 failed because of us.** `alternate_airport` now covers departures as
well as arrivals. On the GOI→BLR leg that misled run 4, **13 of 25 itineraries depart from
another airport** and are now excluded and counted. If a subject still ends up on a
Sindhudurg flight, the fix is wrong; if it lands on IndiGo 6E 6163 at ~Rs 11,988 for two,
the fix holds.

**H1 — failed twice running.** `mmt_intercity_options` now says in its `note` that flight and
cab rows carry `base_inr` and `tax_inr` and that they should be reported separately. This is
the cheapest possible nudge. **If this subject also collapses the split, stop blaming the
subject** — three of four would mean H1 asks for something the tool surface does not
encourage, and the gate or the schema needs the rethink, not the model.

**BUG-17's refinement.** `"Palolem Goa"` → `Palolem` should now come back `high` with no
warning, while a genuine mis-resolve still warns. Run 4's subject visibly acted on these
warnings, so the risk of a false one is that it teaches the next subject to ignore them.

## Not done here — needs the human

- **No reconnect needed this time.** No tool was added or removed since run 4; only
  behaviour inside existing tools changed, and the watcher hot-reloads code. Reconnecting
  anyway does no harm.
- Subject window on `mmt-acceptance-workspace`, one Cline window, reasoning model.
- Paste only the two blockquotes between the PASTE markers of `prompts/goa-itinerary.md`.
- At close-out: `cp .state/diagnostics/calls.jsonl harness/runs/2026-09-05-acceptance-5/`.

---

## Step 3 — audit

- **Subject:** Cline / Sonnet-5, empty workspace. **Deliverable:** `Goa_Trip_Itinerary_and_Budget.pdf`, 11 pages, from `build_goa_report.py`
- **Evidence:** `calls.jsonl`, **42 calls**, server-recorded

### Verdict: **every mandatory gate passes — the first clean sweep. The flight-search budget was exceeded, because the server failed four times.**

| Gate | Result | Evidence |
|---|---|---|
| **H1 base/tax separate** | **PASS — first time in three runs** | flights `₹3,222+₹1,145 tax`; hotels carry a `Nightly (base+tax)` column, `₹8,099 + ₹1,458 tax` and `₹11,259 + ₹1,621 tax` |
| H2 train line | **PASS** | both legs, with the indicative caveat in full |
| H3 estimates labelled | **PASS** | a `Source` column on every row: `MMT live` / `Research estimate` / `ESTIMATE (MMT search failed)` |
| H4 local transport | **PASS** | explains there is no 8hr/80km product, uses one-way legs as a flagged RT proxy |
| H5 alternate airport | **PASS** | no alternate-airport fare quoted; zero mentions of FLY91 or SDW |
| H6 traceable | **PASS** | 5/5 spot-checked to `calls.jsonl` |
| H7 staleness | **PASS** | "pulled on the research date", "a planning benchmark, not a booking" |
| **H-ARITH** | **PASS, exact** | core **142,137**, per person **71,068**, with-optional **144,137**; and every split reconciles: `8,099+1,458=9,557 x4 = 38,228`, `11,259+1,621=12,880 x2 = 25,760`, `3,222+1,145=4,367 x2 = 8,734` |
| GR1-GR4 | **PASS** | 8 `cab_find_place` calls, 7 places registered, research labelled and never blended |
| Completeness | **9/9** | 11 pages |

### H1 passed, and the note is why

Two subjects running had collapsed base/tax. The only change was one sentence added to
`mmt_intercity_options`' `note` telling the caller the rows carry `base_inr`/`tax_inr` and
to report them apart. This subject split them on **both** flights and hotels, including a
dedicated "Nightly (base+tax)" column. One sentence in a tool response moved a gate that two
runs of a correct-but-silent schema had not.

### How it handled a failure is better than what any gate asks for

The GOI→BLR flight search failed every time it was tried. Rather than dropping the leg or
quietly inventing a fare, the report says:

> **FLIGHT (chosen, ESTIMATED)** — MMT flight search failed twice for GOI→BLR on this date
> (empty response / blocked) — **DATA GAP**. Estimate below uses the outbound non-stop
> IndiGo fare as a same-class proxy.

with a paragraph naming it "a known site-blocking issue, not a real 'sold out' signal",
giving a ₹4,300–4,600 planning range, and flagging it as one of the two widest-uncertainty
lines in the budget. No gate requires that. It is exactly the behaviour the whole project is
arguing for.

One inaccuracy: it says the search failed **twice**; the log shows the return was attempted
**three** times. It under-reports its own effort rather than overstating success, which is
the harmless direction, but it is the same class of self-report slip as run 3's.

### The budget was exceeded, and the server is why

**Five flight searches** against a budget of two plus one retry each:

```
22:59:51  BLR->Goa  2026-12-15   98.9s  empty_valid
23:01:45  Goa->BLR  2026-12-21   99.6s  empty_valid
23:03:22  BLR->Goa  2026-12-15   11.2s  OK
23:05:06  Goa->BLR  2026-12-21   99.2s  empty_valid
23:06:49  Goa->BLR  2026-12-21   98.8s  empty_valid
```

The outbound stayed inside the rule (one failure, one retry). The **return was attempted
three times and never succeeded**, which is two retries and one over.

`PHASE2-TASKS.md` says exceeding the budget voids a run. Applied literally, this run is void.
Applied to what the rule is *for* - politeness, not hammering the site - a subject retrying a
call that returns nothing twice is behaving reasonably, and the four failures cost **6.6
minutes of wall clock** on a server that answered in 11 seconds when it worked at all.
**This is a judgement for the project owner, and it should be made after BUG-20 below, not
instead of it.**

### BUG-20 (new): `mmt_flight_search` fails `empty_valid` intermittently and expensively

Four of five flight searches returned "No flight itineraries parsed" after ~99 seconds each.
The pattern is not new - runs 3, 4 and 5 all hit it, and the ~99 s is the harvest timeout
rather than a fast negative. Consequences, in order of importance:

1. It denied this run its return-leg data entirely, so **BUG-19's departure-exclusion path
   was never exercised by a subject.** That fix remains verified only by unit tests and the
   operator's own live check.
2. It is what pushed the run over the call budget, so it will keep voiding runs on a strict
   reading until it is fixed.
3. A ~99 s failure is worse than a fast one: the caller cannot tell a blocked render from a
   genuinely empty route, and pays a minute and a half to find out.

Worth investigating whether the funnel page is loading at all on the failing attempts, and
whether a shorter timeout with a clearer `blocked` verdict is more useful than a long
`empty_valid`.

### BUG-17: seven of eight resolved cleanly on the first try

| query | resolved to | confidence |
|---|---|---|
| Candolim Goa / Colva Goa / Benaulim Goa | Candolim / Colva / Benaulim | **high** |
| Palolem Beach Goa | Palolem Beach | **high** — no false warning, the fix working |
| Old Goa, Dudhsagar Falls, Bengaluru | exact | **high** |
| Goa Dabolim Airport | Dabolim Airport | **low**, warned |

Compare run 4, where the same airport query landed on "Comfy Car Rentals Goa". The remaining
gap: variants are only stripped from the **right**, so a query written region-first ("Goa
Dabolim Airport") falls through to `fallback` - it got the correct airport by the luck of
result ordering, not by ranking, and warned about a right answer. A token-subset match rather
than leading-phrase prefixes would close it.

### State delta

**+7 places**, none removed, `device_id` unchanged: `benaulim`, `candolim`, `colva`,
`dudhsagar`, `goaairport`, `oldgoa`, `palolem`. Five of seven are `is_city: true` - the
cleanest harvest of any run.
