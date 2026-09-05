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

## Phase 1 ground truths (captured 2026-09-05, updated after live fixes)

| # | Check | Result |
|---|---|---|
| 1.1 | Hotel Goa 2026-12-15→21 | ✅ **T2 POST works.** Hyatt Centric: base=11,500, tax=1,842, all_in=13,342 (6N). Baga Beach Hotel: 2,493 all-in. tier_used=2, arithmetic clean. |
| 1.2 | Cab find place | ✅ **Works.** "goa" → "Goa beach, Calangute" (secondary_text contains Goa); "Panaji" → exact city. Regional-priority matcher replaced the Goalpara bug. Place registered for quotes. |
| 1.3 | Train Bengaluru→goa | ✅ **Station resolver fixed.** `resolve_station("goa")` = MAO (dict now precedes alpha bypass). Dec 15 → `not_in_window`, booking_opens=2026-10-16, route SBC-MAO. |
| 1.4 | Flight BLR→GOI Dec 15 | ❌ **EXPERIMENTAL / BLOCKED.** Every automated path to flights-cb fails (see Key finding 3). No live itinerary available from MCP. Perplexity web benchmark (must be labeled): IndiGo ₹4,000–7,000, Air India ₹5,000–9,000 one-way/pp, peak Dec. |

### Key structural findings (current)
1. **Hotel POST — FIXED.** `_t2_post` uses `page.evaluate(fetch)` with fresh cookies + safe headers. Verified live.
2. **Train station — FIXED.** `goa→MAO`, `madgaon→MAO`, `thivim→THVM`, `vasco→VSG` added; resolver dict-first. The gap-recovery test now exercises via the **flight block** instead (GR1/GR2/GR3 still fire).
3. **Flight search — blocked from automation (definitive, 2026-09-05):** header contract captured (app-ver, mcid, device-id, os, src, authorization...) but:
   - `ctx.request` → Akamai "Access Denied" (non-page network context)
   - `page.evaluate(fetch)` with custom headers → CORS preflight to flights-cb rejected (automated browser has no user-session preflight cache)
   - bare fetch → API 403 "Missing Header app-ver"
   - Search-click navigation → results page renders Akamai "200-ok" stub
   - **Proven-working path is the user's real browser only.** Possibly fixable by manually opening MMT once in the server's Chrome profile (caches preflight + sensor state).
   
   → **Model must disclose this limitation and use web-researched fares labeled as such (H5 + GR3).**
