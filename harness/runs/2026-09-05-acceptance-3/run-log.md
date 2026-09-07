# Phase 2 acceptance run 3 — pre-flight

The Sonnet-5 run (`../2026-09-05-acceptance-2/`) passed every mandatory gate except **H6**,
which was unscoreable because no usable transcript existed. This run exists only to close
H6, now that the server records its own calls (`mmt/calllog.py`, commit `8cef7ce`). It is a
full run, not a partial one — the subject starts clean and everything is re-scored.

- **Operator:** Claude Code, via `harness/mcp_client.py`
- **Subject:** Cline in `mmt-acceptance-workspace` — **not** this repo
- **Repo HEAD:** `8cef7cea75bfc007c12d17d116b2d4f3ab12eba2`

## Step 1 — pre-flight

| # | Check | Result |
|---|---|---|
| 1.1 | `mmt_version.loaded_at_commit` == `git rev-parse HEAD` | **PASS** — `8cef7ce…eba2` |
| | `loaded_dirty` | `true`, **acceptable**: `git diff HEAD -- mmt/ server.py tools/` is empty; the only untracked path is this run directory |
| 1.2 | `mmt_setup_status.ready` | **PASS** — `ready: true`, playwright installed, `headless: false` |
| 1.3 | `mmt_capabilities` called | **PASS** — `refuses` present, 8 `known_gaps`, `pricing_conventions.hotels` states the per-night rule |
| 1.4 | `python tests/test_parsers.py` | **PASS — 153/153** (19/19 version suite too) |
| 1.5 | `.state/data.json` snapshotted | **PASS** — see below |
| 1.6 | call log truncated | **PASS** — 6 pre-flight entries cleared, so `calls.jsonl` will contain the subject's calls and nothing else |

Raw payloads: `preflight-results.json`.

## Step 1.5 — state

| File | Contents |
|---|---|
| `state-before.json` | as found: `bengaluru, dudhsagar, goa, goaairport, northgoa, panaji, ponda, southgoa` |
| `state-baseline.json` | after the edit: `bengaluru, goa, panaji` — **the run baseline** |

Removed the five places the previous subject harvested (`dudhsagar`, `goaairport`,
`northgoa`, `ponda`, `southgoa`). `device_id` unchanged (`00000000-…`). The cab-place
gap-recovery trigger is armed again — it has fired in all three runs so far and is the only
trigger that reliably does.

**Step 5 diffs against `state-baseline.json`.**

## Step 2d — run dates (today + 101)

| Leg | Date |
|---|---|
| Outbound | **2026-12-15** (train ARP opens 2026-10-16 — outside the 60-day window, as intended) |
| Return | 2026-12-21 |
| Dudhsagar day trip | 2026-12-19 |

No substitution needed in the prompt: today + 101 lands on the "December 15th" it already
says.

## Environment at hand-off

- One server only: watcher `158048` → `server.py` `149980`. No second client.
- No Chrome holding the profile (`chrome_on_profile=0`).
- Server code byte-identical to HEAD.

## What is different about this run

Only the evidence. `.state/diagnostics/calls.jsonl` will record every call the subject
makes — tool, arguments, elapsed, tier, cached, a digest and the result body. H6 is scored
with `tools/audit_calls.py --find <figure>` against that file, not against a host export.

## Not done here — needs the human

- Subject window on `C:/Users/kumar/projects/claudecodeprojects/mmt-acceptance-workspace`,
  **not** this repo, with only that one Cline window connected.
- Reasoning model (Sonnet-5 or equivalent).
- Paste only the two blockquotes between the PASTE markers of
  `harness/prompts/goa-itinerary.md`.
- At close-out: `cp .state/diagnostics/calls.jsonl harness/runs/2026-09-05-acceptance-3/`.
  A host transcript is welcome but no longer required.

---

## Step 3 — audit

- **Subject:** Cline / Sonnet-5, workspace `mmt-acceptance-workspace`
- **Deliverable:** `Goa_Itinerary_Dec2026.pdf`, 7 pages, from `build_goa_pdf.py`
- **Evidence:** `calls.jsonl` — **24 calls, written by the server itself**

### Verdict: **H6 passes for the first time. H1 fails.**

Not a clean sweep, but the failure has moved from the evidence to the subject, which is what
the harness is for. Nothing about this run is unscoreable.

| Gate | Result | Evidence |
|---|---|---|
| H1 base/tax separate | **FAIL** | the deliverable is all-in throughout. Zero occurrences of a base/tax split anywhere: flights show `Rs 9,154` for two, hotels show "Nightly all-in". The MCP returned `base_inr`/`tax_inr` and `nightly_base_inr`/`nightly_tax_inr` on every one of those calls, and `capabilities.pricing_conventions.split` says they are always reported separately. A regression against the previous run, which printed `3,222 + 1,145 = 4,367` |
| H2 train line | **NOT EXERCISED** | zero mentions of train or rail; `mmt_train_search` never called. Fourth run running |
| H3 estimates labelled | **PASS** | `[MMT]` / `[RES]` / `[ASM]` tags with a legend on the cover and repeated on the budget page |
| H4 local transport | **PASS** | names the 8hr/80km gap as "a known gap in the MMT tool" and substitutes one-way legs or a researched day rate, flagged per day |
| H5 alternate airport | **PASS** | "Dabolim (GOI) is used throughout - not Mopa (GOX) - since every itinerary the flight search returned into GOX carried a materially higher fare or a layover" |
| **H6 traceable** | **PASS** | six figures spot-checked against `calls.jsonl`, all traced — below |
| H7 staleness | **PASS** | "pulled on 5 Sep 2026", plus "indicative, pre-tax-surcharge-drift pricing ... should be re-confirmed on the site" |
| **H-ARITH** | **PASS, exactly** | line items sum to **138,986**; the category breakdown independently sums to **138,986**; per-person 69,493. Every derived line checks: `4 x 12,762 = 51,048`, `2 x 8,308 = 16,616`, `2 x 4,577 = 9,154`, `2 x 5,994 = 11,988` |
| GR1 / GR2 | **PASS** | four places harvested and registered mid-run (`goaairport`, `calangute`, `palolem`, `mollem`) |
| GR3 web prices labelled | **PASS with one error** | see the mislabelled leg below |
| GR4 no crossover | **PASS** | |
| Completeness | **9/9** | 7 pages: cover, trip design + day-by-day, flights, hotels, ground transport, itemised budget, assumptions/caveats/re-price |

### H6, done mechanically — `tools/audit_calls.py --find`

| Figure | Traced to |
|---|---|
| 4,577/adult | `mmt_flight_search BLR->GOI 2026-12-15` → `itineraries[3].all_in_inr` |
| 5,994/adult | `mmt_flight_search GOI->BLR 2026-12-21` → `itineraries[1].all_in_inr` |
| 2,045 | `mmt_cab_quote goaairport->calangute` → `cheapest.all_in_inr` |
| 2,095 | **same call**, `cabs[1].all_in_inr` — the second-cheapest vehicle |
| 12,762 | `mmt_hotel_search` → `hotels[16].nightly_all_in_inr`, confirmed by `mmt_hotel_rates` → `rate_plans[0]` |
| 8,308 | `mmt_hotel_rates` (The Shore Agonda) → `cheapest.nightly_all_in_inr` |

Six for six. The 2,045/2,095 pair is worth noting: the day-by-day quotes 2,095 for the
airport transfer and the budget table bills 2,045. Both are real and from the same call —
different vehicles — so it is an internal inconsistency in the deliverable, not a fabrication.
Without the log that distinction would have been unavailable, which is the entire argument
for having one.

### What the log caught that the deliverable would not have revealed

**1. The call-budget claim is false.** The PDF states: *"only one outbound and one return
flight search were run (no date- or airport-sweeping)"*. The log shows **four**:

```
14:23:04  Bengaluru->GOI 2025-12-15   99552 ms  ERR empty_valid
14:24:43  GOI->Bengaluru 2025-12-21   98838 ms  ERR empty_valid
14:25:44  Bengaluru->GOI 2026-12-15   10916 ms  OK
14:25:56  GOI->Bengaluru 2026-12-21   11342 ms  OK
```

It resolved "December 15th" to **2025** first — a date nine months in the past — and burned
~200 seconds discovering that. Whether the budget was breached is arguable (the rule allows
one retry per call, and these were the same two logical searches re-dated), but the
*statement about its own process* is not accurate, and only the log shows it.

**2. A leg tagged as desk research was actually quoted.** The budget bills *"Candolim →
Agonda via Old Goa/Cabo de Rama, 19 Dec — RES — Rs 2,800"* under a legend that says `[RES]`
means "no MMT endpoint exists for this category". The log has
`mmt_cab_quote calangute->palolem 2026-12-19` returning **Rs 2,145** across 6 cabs. The
quote exists; the deliverable substituted a higher researched figure and mislabelled its
provenance. Conservative in rupees, wrong in attribution.

**3. The circuit breaker fired and the subject recovered on its own.** Two `mmt_hotel_search`
calls returned `blocked` at 0 ms (circuit open after the 2025-dated transport failures). It
then ran `mmt_selftest` and a throwaway Kochi hotel search to re-probe, and resumed. Good
behaviour, invisible in the deliverable.

### State delta

`state-baseline.json` → `state-after.json`: **+4, none removed, `device_id` unchanged.**

| key | harvested as | is_city |
|---|---|---|
| `goaairport` | Dabolim Airport | false |
| `calangute` | **Goa beach** | false |
| `palolem` | **Bibhitaki Hostel Palolem Goa** | false |
| `mollem` | Biodiversity Park, Mollem Goa | false |

**BUG-17 reproduces, deterministically.** "Calangute Goa" resolved to "Goa beach" and
"Palolem Goa" to a hostel — the *same* hostel the previous run got for `southgoa`. Two of
four are wrong, `is_city` false on all four, and the subject priced real transfers between
them.

### Contamination check

The previous run's `Goa_7Night_Itinerary_Dec2026.pdf` and `build_goa_itinerary.py` were
still in the workspace (operator hygiene failure — mine). No evidence they were used: run 2's
total, its hotels (Fern, Fairfield) and its structure appear nowhere in run 3, and every run-3
figure traces to a run-3 call. **Clear the workspace between runs anyway.**

### BUG-18 (new): no past-date guard on flights or hotels

`mmt_flight_search` for `2025-12-15`, run in September 2026, spent **99 seconds** driving a
live search page and returned `empty_valid` — "No flight itineraries parsed". Hotel searches
on 2025 dates returned `transport` errors and tripped the circuit breaker. Trains check their
booking window and answer `not_in_window` in ~2 seconds; flights and hotels check nothing. A
date in the past is a `bad_input`, knowable before a single byte leaves the machine. It cost
this subject ~200 s, two flight searches and a circuit trip, and it will cost every subject
that resolves a bare month-and-day to the wrong year — which is a thing models do.
