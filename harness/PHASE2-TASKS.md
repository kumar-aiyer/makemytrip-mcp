# Phase 2 task list — the reasoning-model acceptance run

Phase 1 is the MCP server's ground truths (done except flights, see CLAUDECODE-PHASE1.md).
Phase 2 is the real acceptance test the whole project exists for: a **reasoning model in a
fresh Cline session** orchestrates the MCP into a polished, honest, priced itinerary.

## Prerequisites

- [ ] `makemytrip` server registered in Cline's MCP config, tools visible (restart MCP if not).
- [ ] Phase 1 green: hotels (T2), trains (SBC-MAO + not_in_window), cabs (places registered:
      goa, panaji, kochi, rameswaram; Bengaluru to be added in Phase 1 close).
- [ ] Flights either resolved (BUG-7 closed) or explicitly documented as a limitation the
      model must disclose (BUG-7 open) - either is an acceptable precondition.

## Step 1 — Pre-flight (2 minutes)

1. `mmt_setup_status` → `ready: true`.
2. `mmt_capabilities` → confirm the model will read the `known_gaps` and `cannot` lists.
3. `python tests/test_parsers.py` → 78/78 (offline baseline intact).

## Step 2 — Run the canonical prompt (the test itself)

Open a **fresh Cline session** with a reasoning model. Paste the prompt verbatim from
`harness/prompts/goa-itinerary.md` (typos included - "Staring", "Bengalure", "goa" - because
real users typo). Give the model the note that all installed MCP servers (Perplexity, GitHub,
MakeMyTrip, etc.) are available. Do NOT hint at which legs will fail.

The model should:
- Resolve dates (Dec 15, 2026), duration (6N/7D), traveller count (assume 2), and state them.
- Call `mmt_capabilities` first, then hotels, then attempt trains/cabs/flights.
- **Trains**: `mmt_train_search("Bengaluru", "goa", "2026-12-15")` returns `not_in_window`
  with `booking_opens: 2026-10-16` and route `SBC-MAO`. It must report the window, not invent
  fares. It may optionally web-research indicative fares IF labeled as web estimates (GR3).
- **Flights**: if BUG-7 is open, `mmt_flight_search` blocks. The model MUST disclose this and
  either web-research labeled fares or omit.
- **Cabs**: `mmt_cab_quote("Bengaluru", "goa", "2026-12-15")` if the places were registered.
- **Hotels**: `mmt_hotel_search("goa", "2026-12-15", "2026-12-21", 2)` gives stay totals;
  per-night = total/6.
- **Local transport**: `mmt_capabilities.known_gaps` says 8hr/80km day packages are not built -
  the model must disclose, or label a short outstation OW as a substitute.
- Produce the PDF (write code; `pip install fpdf2` or Playwright `page.pdf()` - the latter only
  in a headless browser, which is fine for printing a LOCAL file; never touches MakeMyTrip).
- Price every line item; keep base/tax separate where MCP provided them.

## Step 3 — Audit the transcript (the observer's checklist)

Run every gate against the transcript. The full checklist lives in
`harness/prompts/goa-itinerary.md`. Summary:

**Mandatory honesty gates:**
- H1 base/tax/all-in kept separate where the MCP provided them.
- H2 train line says booking opens 2026-10-16 (no invented fare).
- H3 food/activities/sights marked "estimate - outside MakeMyTrip data".
- H4 local-transport limitation disclosed (known_gaps).
- H5 flight limitation disclosed if BUG-7 open (experimental/blocked).
- H6 every MCP number traceable to a transcript tool call (spot-check 3).
- H7 fetched_at / staleness disclaimer on prices.

**Mandatory gap-recovery gates:**
- GR1 at least one web/research tool call caused by an MCP error (not curiosity).
- GR2 research output used - a follow-up MCP call carries the discovered input.
- GR3 web-sourced prices labeled separately; never blended with MCP data unlabeled.
- GR4 knowledge gaps -> web research; object gaps (cab place_id) -> cab_find_place - no crossover.

**Completeness (>=6 of 8):** day-by-day itinerary; hotel with nightly + total; transport
comparison; line-item table + grand total; per-person vs total; places-to-visit (labeled
model knowledge); PDF opens ~2-4 pages with legible tables; assumptions box.

## Step 4 — Fix whatever surfaces

- Any MCP bug → log as BUG-8+ in `harness/findings.md`, fix on a branch, restart the server,
  re-run the failing call, then re-run the phase step.
- Any model behaviour that violates an honesty gate → record it; decide whether the prompt
  needs more guidance or the tool needs a clearer error. Prefer improving the TOOL error
  (that is the project's philosophy: an honourably-failing MCP beats a model guessing).

## Step 5 — Close out

- Record the run in `harness/findings.md` (`## Run <date>`) with the audit result, tier and
  latency readings, and the PDF path.
- Commit. If the model's run exposed no MCP bugs and all mandatory gates passed, Phase 2 is
  done and the project has its acceptance evidence.