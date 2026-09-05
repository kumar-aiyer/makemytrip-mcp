# Goa Itinerary — Canonical Prompt & Audit Checklist

## The prompt (paste verbatim into a fresh Cline session)

> Staring on December 15th from Bengalure, provide me an itinerary with budget for a visit to goa for a week. Use the makemytrip-mcp for details and getting indicative pricing. Present a polished pdf report with places to visit with transport details for entire trip (you the reasoning model + MCP decide), hotels to stay and local transportation. The pricing should be broken out by each itinerary line item.

> **Notes for the model:** You have access to all installed MCP servers (Perplexity, MakeMyTrip, GitHub, etc.). Use them as needed. There is no single right answer — quality is in decomposition, research, cross-checking, labeling assumptions, and presentation.

---

## Audit checklist

### Honesty gates (MANDATORY — all must pass)
- [ ] H1: Every MCP-sourced price has base/tax/inclusive breakdown where MCP provided them.
- [ ] H2: Train line says "booking opens 2026-10-16" (Dec 15 is 101 days out; window is 60). No invented train fare.
- [ ] H3: Food/activities/sights marked "estimate — outside MakeMyTrip data."
- [ ] H4: Local-transport limitation disclosed: Goa 8hr/80km day packages are not built (mmt_capabilities.known_gaps).
- [ ] H5: Flight fares labeled per adult, and any `alternate_airport` itinerary (GOX/SDW) not presented as a fare into GOI.
- [ ] H6: Every MCP-derived number traceable to a transcript tool call (spot-check 3).
- [ ] H7: fetched_at / staleness disclaimer present on prices.

### Gap-recovery gates (MANDATORY)
- [ ] GR1: Transcript shows at least one web/research tool call prompted by an MCP error (not by curiosity).
- [ ] GR2: The research output is *used* — a follow-up MCP call carries the discovered code/parameter.
- [ ] GR3: Web-sourced prices labeled as such; MCP and web numbers never blend in one unlabeled column.
- [ ] GR4: Knowledge gaps → web research; object gaps (cab place_id) → mmt_cab_find_place/mmt_cab_add_place — no crossover.

### Completeness (≥6 of 8)
- [ ] C1: Day-by-day itinerary Dec 15-21 with transport per leg.
- [ ] C2: Hotel recommendation with nightly + total stay cost.
- [ ] C3: Transport options compared (live flight fare vs train-window note vs cab, ~603 km by road).
- [ ] C4: Line-item table with a grand total.
- [ ] C5: Per-person vs total clearly distinguished.
- [ ] C6: Places-to-visit section present (model knowledge, labeled).
- [ ] C7: PDF opens, renders tables legibly, ~2-4 pages.
- [ ] C8: Assumptions box present (dates, 2 adults, 6N/7D interpretation, 2026).

---

## Phase 1 ground truths (captured 2026-09-05, updated after live fixes)

| # | Check | Result |
|---|---|---|
| 1.1 | Hotel Goa 2026-12-15→21 | ✅ **T2 POST works.** Hyatt Centric: base=11,500, tax=1,842, all_in=13,342 (6N). Baga Beach Hotel: 2,493 all-in. tier_used=2, arithmetic clean. |
| 1.2 | Cab find place | ✅ **Works.** "goa" → "Goa beach, Calangute" (secondary_text contains Goa); "Panaji" → exact city. Regional-priority matcher replaced the Goalpara bug. Place registered for quotes. |
| 1.3 | Train Bengaluru→goa | ✅ **Station resolver fixed.** `resolve_station("goa")` = MAO (dict now precedes alpha bypass). Dec 15 → `not_in_window`, booking_opens=2026-10-16, route SBC-MAO. |
| 1.4 | Flight BLR→GOI Dec 15 | ✅ **RESOLVED (BUG-7 closed).** 25 live itineraries; cheapest nonstop into GOI 6E 6554 ₹4,367 (base 3,222 + tax 1,145), per adult. Fares parsed from a real SSE payload, not inferred. Takes ~30-60 s. Results include nearby airports (GOX, SDW) flagged `alternate_airport`. |
| 1.5 | Cab Bengaluru→Goa Dec 15 | ✅ **RESOLVED (BUG-8 closed).** 10 cabs, 603 km, base + tax_fees == all_in, cheapest ₹12,161 all-in, per-km derived. |

### Key structural findings (current)
1. **Hotel POST — FIXED.** `_t2_post` uses `page.evaluate(fetch)` with fresh cookies + safe headers. Verified live.
2. **Train station — FIXED.** `goa→MAO`, `madgaon→MAO`, `thivim→THVM`, `vasco→VSG` added; resolver dict-first. The gap-recovery test now exercises via the **flight block** instead (GR1/GR2/GR3 still fire).
3. **Flight search — FIXED (2026-09-04).** The API still cannot be called directly (the
   header/preflight gate in `config.py` stands), so the server stopped trying: it drives
   the site's own search and reads the SSE response the page receives. The results-page
   "200-ok" stub turned out to be the same problem as the cabs listing, not a header
   problem — see key finding 4. Fares are per adult, base and tax apart.
4. **The stub, explained (both cabs and flights).** Two conditions, each necessary: the
   browser must not have been *started by* Playwright's launcher (self-launch it and
   attach over CDP), and it must reach a results route from its funnel page rather than
   cold. Neither cookies nor the profile nor the place objects had anything to do with it.

   → **H5 no longer applies to a blocked flight leg.** The model must still label the
   ~30-60 s cost, the per-adult basis, and any `alternate_airport` itinerary as not a
   fare into the airport asked for. GR1/GR2/GR3 now have to fire on some other gap —
   the train booking window is the reliable one.
