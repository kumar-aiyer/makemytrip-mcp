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
- [ ] H5: Flight result labeled experimental if parse degraded.
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
- [ ] C3: Transport options compared (flight vs train-window note vs cab with ~560 km drive cost).
- [ ] C4: Line-item table with a grand total.
- [ ] C5: Per-person vs total clearly distinguished.
- [ ] C6: Places-to-visit section present (model knowledge, labeled).
- [ ] C7: PDF opens, renders tables legibly, ~2-4 pages.
- [ ] C8: Assumptions box present (dates, 2 adults, 6N/7D interpretation, 2026).

---

## Phase 1 ground truths (captured 2026-09-05)

| Check | Result |
|---|---|
| 1.3a: resolve_station("Goa") | Returns "GOA" — WRONG! 2-5 char code bypass. Real Goa station codes: MAO (Madgaon) or THVM (Thivim). Requires web research. |
| 1.3b: resolve_station("MAO") | Returns "MAO" — direct code acceptance works. |
| 1.3c: in_window("2026-12-15") | False (101 days out). booking_opens = 2026-10-16. |
| 1.1: Hotel search GOI Dec 15-21 | FAILS: T1 ctx.request.post returns stub "200-OK". No T2 POST path exists in current code. |
| 1.2: Cab find place Goa | Not run (needs Cline MCP restart). |
| 1.4: Flight search BLR-GOI Dec 15 | Not run (needs Cline MCP restart or direct Python). |

### Key structural findings
1. **Hotel POST gap (blocking):** T1 `ctx.request.post` returns stub "200-OK" from this network. T2 in-page `page.evaluate(fetch)` works but is not wired into `post_json` — it caps at REQUEST tier. This is the #1 infrastructure gap for this test.
2. **Train station gap (intentional):** Goa absent from STATIONS dict. MAO/THVM accepted by resolver. Model must web-research → discover → re-query MCP. This is the exact gap-recovery pattern the test measures.
3. **Flight search:** Experimental with inferred field names — parser may degrade. Result carries raw_head for fixture capture.
# Goa Itinerary - Canonical Prompt

## The prompt

Placeholder - will be written via Python


## Live results 2026-09-04
- Hotels T2: WORKING (Hyatt: 13,342 all-in)
- Flights T2: BLOCKED (403)
