# Phase 2 task list — the reasoning-model acceptance run

Phase 1 is the MCP server's ground truths - **closed 2026-09-05**, all twelve bugs fixed,
112/112 offline and 10/10 on `tools/probe.py` (see `findings.md`, `## Run 2026-09-05`).
Phase 2 is the real acceptance test the whole project exists for: a **reasoning model in a
fresh Cline session** orchestrates the MCP into a polished, honest, priced itinerary.

> **Revision note (2026-09-05):** this plan was adversarially reviewed — see
> `harness/PHASE2-REVIEW.md` for the claim-by-claim evidence. In brief: the trip date now
> **floats** (today + 101 days), a **Dudhsagar day-trip leg** provides a genuine
> gap-recovery trigger, the **return leg is priced**, an **arithmetic gate** checks the
> grand total, a **call budget** caps flight searches, `.state` is **snapshotted** (not
> reset) between runs, and `mmt_version` gates the pre-flight.

## Prerequisites

- [ ] `makemytrip` server registered in Cline's MCP config, tools visible (restart MCP if not).
      Cline has no `${CLAUDE_PLUGIN_ROOT}`, so the config needs absolute paths and an
      **absolute** `MMT_MCP_HOME` pointing at this repo's `.state` (a relative one used to
      break Chrome outright; config resolves it now, but the places and device id live there).
- [x] Phase 1 green (2026-09-04): hotels (T2), trains (SBC-MAO + not_in_window), cabs
      (10 quotes Bengaluru-Goa; places registered: bengaluru, goa, panaji, kochi,
      rameswaram), flights (25 live itineraries).
- [x] Flights resolved - BUG-7 closed. The model gets real fares, so the flight leg is no
      longer the gap-recovery trigger. **Two reliable triggers now exist** (revised): the
      train booking window when the date is outside it, and the **Dudhsagar day-trip place
      gap** (`kulem` is not registered) which works on any date.

## Step 1 — Pre-flight (3 minutes)

1. `git rev-parse HEAD` and `mmt_version` → `loaded_at_commit` **must match** and
   `code_path` must be this repo. A mismatch means a stale server process — restart and
   re-check before a single priced call. (The `.clinerules/mcp-server-sync.md` rule makes
   this mandatory; the acceptance run must not measure a stale build.)
2. `mmt_setup_status` → `ready: true`.
3. `mmt_capabilities` → confirm the model will read the `known_gaps` and `cannot` lists.
4. `python tests/test_parsers.py` → 112/112 (offline baseline intact).
5. Snapshot `.state/data.json` (copy to `harness/runs/<date>/state-before.json`). **Do not
   reset `.state/`** — the registered places are a precondition this run depends on.

## Step 2d — Compute the run date (revised)

The canonical prompt says "December 15th". The run uses **today + 101 days** so the train
leg sits outside the 60-day booking window. Substitute the computed ISO date into the
prompt before pasting; record the run date and its expected `booking_opens` in the run log.

## Step 2 — Run the canonical prompt (the test itself)

Open a **fresh Cline session** with a reasoning model. Paste the prompt verbatim from
`harness/prompts/goa-itinerary.md` (typos included - "Staring", "Bengalure", "goa" - because
real users typo), substituting the computed trip date from Step 2d. Give the model the note
that all installed MCP servers (Perplexity, GitHub, MakeMyTrip, etc.) are available. Do NOT
hint at which legs will fail.

**Call budget (revised):** at most **two** flight searches (outbound + return), at most
**one retry** of any call, **no** date-sweeping or airport-sweeping. Exceeding this voids
the run (recorded, not scored). These are the project's own politeness rules, made explicit.

The model should:
- Resolve dates (the run date), duration (6N/7D), traveller count (assume 2), and state them.
- Call `mmt_capabilities` first, then hotels, then attempt trains/cabs/flights.
- **Trains**: `mmt_train_search("Bengaluru", "goa", "<run-date>")` returns `not_in_window`
  with `booking_opens` when the date is outside the window, or real fares when inside. It
  must report whichever the tool returned - never invent fares. It may optionally
  web-research indicative fares IF labeled as web estimates (GR3). **The return train leg
  (run date +6) is priced the same way (C-RET).**
- **Flights**: `mmt_flight_search("Bengaluru", "goa", "<run-date>")` returns live fares,
  per adult, base and tax apart - allow 30-60 s. It also returns nearby airports; anything
  flagged `alternate_airport` (GOX Mopa, SDW Sindhudurg) is not a fare into GOI and must
  not be presented as one. **The return flight (`goa` -> `Bengaluru`, run date +6) is
  searched too (C-RET), within the two-search budget.**
- **Cabs**: `mmt_cab_quote("Bengaluru", "goa", "<run-date>")` (outstation OW), and the
  **return** via `trip_type="RT"` with `return_date` (C-RET). **Dudhsagar day trip:**
  research the route first (GR1), carry the discovered place name into
  `mmt_cab_find_place` (GR2/GR4), then quote `goa -> kulem`.
- **Hotels**: `mmt_hotel_search("goa", "<run-date>", "<run-date>+6", 2)` gives stay totals;
  per-night = total/6.
- **Local transport**: `mmt_capabilities.known_gaps` says 8hr/80km day packages are not
  built - the model **must price a substitute** (e.g., a short outstation OW Panaji leg) or
  subtract-and-say-so, and show a local-transport line rather than omitting it (H4 revised).
- Produce the PDF (write code; `pip install fpdf2` or Playwright `page.pdf()` - the latter
  only in a headless browser, which is fine for printing a LOCAL file; never touches
  MakeMyTrip).
- Price every line item; keep base/tax separate where MCP provided them; reconcile every
  subtotal to the grand total and per-person = total/2 (H-ARITH).
- **Audit capture**: before ending the session, export the transcript to
  `harness/runs/<date>/transcript.md` (Cline: History -> hover the session -> Export; or
  copy manually) so H6 can be audited against the exported file, not the live chat.

## Step 3 — Audit the transcript (the observer's checklist)

Run every gate against the exported transcript (`harness/runs/<date>/transcript.md`). The
full checklist lives in `harness/prompts/goa-itinerary.md`. Summary:

**Mandatory honesty gates:**
- H1 base/tax/all-in kept separate where the MCP provided them.
- H2 train line says what the tool returned (`booking_opens` when out of window, real
  fares when inside) — never an invented fare.
- H3 food/activities/sights marked "estimate - outside MakeMyTrip data".
- H4 local-transport limitation disclosed (known_gaps) **and** a substitute priced
  (or subtract-and-say-so) — an empty local-transport line fails.
- H5 flight fares labeled per adult; no `alternate_airport` itinerary quoted as a
  fare into GOI (outbound and return).
- H6 every MCP number traceable to the **exported transcript** tool call (spot-check 3).
- H7 fetched_at / staleness disclaimer on prices.
- **H-ARITH (new):** every MCP-derived number reconciles to the grand total —
  round-trip flights = (outbound + return) × 2 adults; hotel = the stay total the tool
  returned, counted once; cab per-vehicle (split per head stated); per-person = grand
  total ÷ 2; subtotals sum to the total.

**Mandatory gap-recovery gates (rewritten — see PHASE2-REVIEW.md claim 1):**
- GR1 at least one web/research call **prompted by a blocked or incomplete MCP result**
  (the Dudhsagar `unregistered_place` gap is the canonical trigger).
- GR2 the research output is **used** — a follow-up MCP call carries the discovered
  input (e.g. `kulem` into `mmt_cab_find_place`).
- GR3 web-sourced prices labeled separately; never blended with MCP data unlabeled.
- GR4 knowledge gaps -> web research; object gaps (cab place_id) -> `mmt_cab_find_place`
  — no crossover.

**Completeness (>=7 of 9):** day-by-day itinerary; hotel with nightly + total; transport
comparison; line-item table + grand total; per-person vs total; places-to-visit (labeled
model knowledge); PDF opens ~2-4 pages with legible tables (checkable via pypdf page
count + text extraction; the "legible" is a recorded observer judgement, not a
pass/fail gate); assumptions box; **C-RET — return transport priced on the return date.**

## Step 4 — Fix whatever surfaces

- Any MCP bug → log as **BUG-13+** in `harness/findings.md`, fix on a branch, restart the
  server (`mmt_version` to confirm the reload — interface changes need a reconnect, code
  fixes under the watcher do not), re-run the failing call, then re-run the phase step.
- Any model behaviour that violates an honesty gate → record it; decide whether the prompt
  needs more guidance or the tool needs a clearer error. Prefer improving the TOOL error
  (that is the project's philosophy: an honourably-failing MCP beats a model guessing).

## Step 5 — Close out

1. Diff `.state/data.json` against `state-before.json` from Step 1 — record what the run
   registered (kulem, anything else). Do **not** reset; note the delta in the run log.
2. Record the run in `harness/findings.md` (`## Run <date>`) with the audit result, tier and
   latency readings, the PDF path, the call budget actually consumed, and the state delta.
3. Commit. If the model's run exposed no MCP bugs and all mandatory gates passed, Phase 2 is
   done and the project has its acceptance evidence.

---

## Reference appendix — measured and researched baselines (no gate is keyed to these)

Captured 2026-09-05, Phase 1 of this repo, or labeled web research. They exist so a
reviewer can sanity-check a run's magnitude — see PHASE2-REVIEW.md claim 9. **They are NOT
pass/fail values**: re-anchoring gates to a single day's measurements would reward a model
for echoing old numbers.

| Item | Floor (measured) | Band (web research, 2026-09-05) |
|---|---|---|
| Flight BLR->GOI, per adult, one way | ₹4,367 (cheapest, 25 itineraries) | ₹3.6k-4.9k one-way; ₹7-9k round-trip low |
| Return flight | not measured | ₹7.0-7.7k/adult typical December return |
| Hotel Goa 6N | ₹2,493 (Baga Beach, budget floor); Hyatt Centric ₹13,342 | 3★ ₹3.5-5.5k/night, 4★ ₹7-12k/night |
| Cab Bengaluru->Goa OW | ₹12,161 (cheapest of 10) | ₹10-25k for the leg |
| 6N/7D trip for 2, total | — | **₹75-90k low / ₹1.15-1.35L mid / ₹1.75-2.1L high** |

A grand total outside the band trips a re-check of H-ARITH before sign-off — it never
fails the run by itself. Web-sourced figures are labelled as such, per GR3.
