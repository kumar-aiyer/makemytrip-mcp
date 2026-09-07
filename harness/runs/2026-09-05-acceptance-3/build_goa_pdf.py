# -*- coding: utf-8 -*-
"""
Builds a polished PDF itinerary + budget report for a 7-day / 6-night
Bengaluru -> Goa trip, Dec 15-21, 2026, for 2 adults.

Pricing sources:
  [MMT]  = live/indicative quote pulled from the makemytrip-mcp server on
           2026-09-05 (signed-out retail rates; this server cannot book).
  [RES]  = desk research (Perplexity) on typical Dec-season Goa prices;
           MMT has no endpoint for these (local day-hire packages, entry
           tickets, water sports, cruises, market shopping).
  [ASM]  = planning assumption (e.g. meals, contingency) made by the author.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, ListFlowable, ListItem, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

OUT = r"C:\Users\kumar\projects\claudecodeprojects\mmt-acceptance-workspace\Goa_Itinerary_Dec2026.pdf"

styles = getSampleStyleSheet()
NAVY = colors.HexColor("#0B3954")
TEAL = colors.HexColor("#087E8B")
SAND = colors.HexColor("#F4E9CD")
LIGHT = colors.HexColor("#F7F9FA")
GREY = colors.HexColor("#5A5A5A")
GOOD = colors.HexColor("#1B7A43")

styles.add(ParagraphStyle("TitleBig", parent=styles["Title"], fontSize=26, textColor=NAVY, spaceAfter=6, leading=30))
styles.add(ParagraphStyle("SubTitle", parent=styles["Normal"], fontSize=13, textColor=TEAL, spaceAfter=14, alignment=TA_CENTER))
styles.add(ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16, textColor=NAVY, spaceBefore=14, spaceAfter=8))
styles.add(ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12.5, textColor=TEAL, spaceBefore=10, spaceAfter=6))
styles.add(ParagraphStyle("Body", parent=styles["Normal"], fontSize=9.6, leading=13.5))
styles.add(ParagraphStyle("BodySmall", parent=styles["Normal"], fontSize=8.3, leading=11.5, textColor=GREY))
styles.add(ParagraphStyle("DayTitle", parent=styles["Heading2"], fontSize=12, textColor=colors.white, spaceBefore=0, spaceAfter=0))
styles.add(ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8.5, leading=11))
styles.add(ParagraphStyle("CellHead", parent=styles["Normal"], fontSize=8.7, leading=11, textColor=colors.white, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle("Note", parent=styles["Normal"], fontSize=8, leading=11, textColor=GREY, alignment=TA_LEFT))

def P(text, style="Body"):
    return Paragraph(text, styles[style])

story = []

# ------------------------------------------------------------------ COVER
story.append(Spacer(1, 40))
story.append(P("GOA GETAWAY", "TitleBig"))
story.append(P("7 Days / 6 Nights &nbsp;|&nbsp; Bengaluru &#8596; Goa &nbsp;|&nbsp; 15&ndash;21 December 2026 &nbsp;|&nbsp; 2 Adults", "SubTitle"))
story.append(HRFlowable(width="100%", thickness=1.4, color=TEAL, spaceAfter=14))

story.append(P(
    "This report presents a day-by-day itinerary for a one-week Goa holiday, split between "
    "North Goa (nightlife, water sports, forts, markets, Old Goa heritage) and South Goa "
    "(quiet beaches, Cabo de Rama, Agonda/Palolem), plus a fully itemised budget in Indian "
    "Rupees (INR). Flight, hotel and outstation-cab figures are live/indicative quotes pulled "
    "on <b>5 Sep 2026</b> via the makemytrip-mcp server (signed-out retail rates; MakeMyTrip "
    "cannot be booked through this tool). Entry fees, water-sports, cruise, jeep-safari and "
    "self-drive scooter costs are not exposed by any MakeMyTrip API/search funnel available "
    "to this tool, so they are sourced from December-2025/2026-season desk research and are "
    "clearly marked <b>[RES]</b> throughout, alongside <b>[MMT]</b> for live quotes and "
    "<b>[ASM]</b> for planning assumptions (meals, tips, contingency).", "Body"))
story.append(Spacer(1, 10))

cover_tbl_data = [
    [P("Route", "CellHead"), P("Bengaluru (BLR) &#8596; Goa Dabolim (GOI)", "Cell")],
    [P("Dates", "CellHead"), P("Depart Tue 15 Dec 2026 &nbsp;&#8226;&nbsp; Return Mon 21 Dec 2026 (6 nights)", "Cell")],
    [P("Base 1", "CellHead"), P("North Goa &#8211; Candolim/Baga belt, 4 nights (15&ndash;19 Dec)", "Cell")],
    [P("Base 2", "CellHead"), P("South Goa &#8211; Agonda/Palolem belt, 2 nights (19&ndash;21 Dec)", "Cell")],
    [P("Travellers", "CellHead"), P("2 adults, sharing 1 room throughout", "Cell")],
    [P("Total trip cost", "CellHead"), P("<b>&#8377; 1,38,986</b> all-in for 2 people (&#8377;69,493 per person) &#8211; see itemised budget for the full line-by-line breakdown", "Cell")],
]
t = Table(cover_tbl_data, colWidths=[110, 340])
t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (0,-1), NAVY),
    ("TEXTCOLOR", (0,0), (0,-1), colors.white),
    ("BACKGROUND", (1,0), (1,-1), LIGHT),
    ("GRID", (0,0), (-1,-1), 0.5, colors.white),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 6),
    ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ("LEFTPADDING", (0,0), (-1,-1), 8),
]))
story.append(t)
story.append(Spacer(1, 14))
story.append(P("<b>Legend:</b> [MMT] = live MakeMyTrip quote via mmt-mcp on 5-Sep-2026 &nbsp;|&nbsp; "
               "[RES] = Dec-season desk research (no MMT endpoint for this item) &nbsp;|&nbsp; "
               "[ASM] = planning assumption.", "Note"))
story.append(PageBreak())

# ------------------------------------------------------------ TRIP LOGIC
story.append(P("Trip Design &amp; Reasoning", "H1"))
story.append(P(
    "Goa's North (Bardez taluka: Candolim/Calangute/Baga/Anjuna/Vagator) and South "
    "(Canacona/Salcete taluka: Agonda/Palolem/Cabo de Rama) belts are 60&ndash;75&nbsp;km apart "
    "&#8211; a 2&ndash;2.5 hour drive. Shuttling between them daily would burn a full day of the trip "
    "in transit, so the itinerary is <b>split into two bases</b>: 4 nights in North Goa "
    "(where most heritage sites, markets, water sports and nightlife are clustered) and "
    "2 nights in South Goa (for a quieter, beach-relaxation finish). Days within each base are "
    "grouped by geography to minimise backtracking, and two flea-market visits are pinned to "
    "their actual open days in Dec 2026 (Anjuna &#8211; Wednesdays, Mapusa &#8211; Fridays); with only one "
    "week available, Mapusa was traded off against the Dudhsagar Falls/spice-plantation day, "
    "which needs a full day. Dabolim (GOI) is used throughout &#8211; not Mopa (GOX) &#8211; since it sits "
    "closer to both bases and every itinerary the flight search returned into GOX carried a "
    "materially higher fare or a layover.", "Body"))
story.append(Spacer(1, 8))

day_colors = [NAVY, TEAL]

def day_header(daynum, datestr, title, base):
    tbl = Table([[P(f"DAY {daynum} &#8211; {datestr}", "DayTitle"), P(title, "DayTitle")]],
                colWidths=[110, 340])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), day_colors[0] if base=="N" else day_colors[1]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    return tbl

def day_block(daynum, datestr, title, base, bullets, cost_note):
    items = [ListItem(P(b, "Body"), leftIndent=10, bulletColor=TEAL) for b in bullets]
    lf = ListFlowable(items, bulletType="bullet", start="\u2022", leftIndent=14)
    block = [day_header(daynum, datestr, title, base), Spacer(1,4), lf, Spacer(1,3),
             P(f"<i>{cost_note}</i>", "BodySmall"), Spacer(1, 10)]
    return KeepTogether(block)

story.append(day_block(1, "Tue 15 Dec", "Arrival &amp; North Goa check-in", "N", [
    "Depart BLR 17:25, land GOI 18:45 (IndiGo 6E 6168, non-stop, 1h20m) &#8211; [MMT]",
    "Pre-booked cab from Dabolim Airport to Candolim (~45&ndash;60 min) &#8211; [MMT]",
    "Check in to hotel in Candolim; evening walk on Calangute/Baga beach and casual dinner at a beach shack",
], "Transport: airport transfer &#8377;2,095 [MMT]. No entry fees today."))

story.append(day_block(2, "Wed 16 Dec", "Forts, Anjuna flea market &amp; sunset at Vagator", "N", [
    "Morning: Fort Aguada + Sinquerim Beach &amp; lighthouse (Portuguese-era fort, sweeping Arabian Sea views)",
    "Late morning&ndash;afternoon: Anjuna Wednesday Flea Market &#8211; Goa's iconic bazaar for clothes, jewellery &amp; souvenirs (only runs Wednesdays in season)",
    "Evening: Chapora Fort (the \"Dil Chahta Hai\" fort) and Vagator/Ozran Beach for sunset",
    "Self-drive scooter for the day (2 scooters) for flexibility between Candolim&#8211;Anjuna&#8211;Vagator",
], "Transport: 2 scooters &#8377;1,200 + fuel &#8377;200 [RES]. Entry: Fort Aguada/Sinquerim &#8377;100 for 2 [RES]. Flea market entry free; shopping budgeted separately."))

story.append(day_block(3, "Thu 17 Dec", "Water sports, Baga nightlife &amp; Mandovi sunset cruise", "N", [
    "Morning: water sports at Baga/Calangute &#8211; jet-ski, parasailing, banana/bumper boat combo",
    "Afternoon: leisure time at the pool/beach; optional spa",
    "Evening: Mandovi River sunset cruise from Panjim jetty (live music &amp; snacks on most operators)",
    "Night: Tito's Lane, Baga &#8211; Goa's best-known nightlife strip (cover charge + drinks)",
], "Transport: 2 scooters &#8377;1,200 + fuel &#8377;200 [RES]. Water sports &#8377;2,600 for 2 [RES]. Cruise &#8377;1,200 for 2 [RES]. Nightlife &#8377;4,000 for 2 [RES/ASM]."))

story.append(day_block(4, "Fri 18 Dec", "Dudhsagar Falls &amp; spice plantation (full-day excursion)", "N", [
    "Early transfer (~07:00) from Candolim to Kulem/Mollem, gateway to Bhagwan Mahaveer Sanctuary",
    "Shared 4x4 jeep safari through the sanctuary to Dudhsagar Falls (India's 5th-tallest waterfall, in season through Dec&ndash;May)",
    "Return via a Ponda-area spice plantation &#8211; guided walk + traditional Goan buffet lunch",
    "Evening: return to Candolim, rest day/free evening",
], "Transport: chauffeured car Candolim&#8596;Mollem return &#8377;4,290 [MMT] (MMT has no 8hr/80km local day-package funnel; two one-way outstation legs are summed as a substitute &#8211; see note below). Jeep safari + park entry &#8377;1,300 for 2 [RES]. Spice plantation tour + lunch &#8377;1,600 for 2 [RES]."))

story.append(day_block(5, "Sat 19 Dec", "Old Goa heritage, Panjim &amp; transfer south via Cabo de Rama", "N", [
    "Morning: Basilica of Bom Jesus (UNESCO World Heritage Site, relics of St. Francis Xavier) and S&eacute; Cathedral, Old Goa",
    "Late morning: Fontainhas &#8211; Panjim's Latin Quarter &#8211; for a heritage walk among Portuguese-tiled houses",
    "Check out of North Goa hotel; drive south (~2&ndash;2.5 hrs) with a stop at Cabo de Rama Fort (clifftop views, quieter than the northern forts)",
    "Check in to South Goa hotel in Agonda by early evening; relaxed sunset on Agonda beach",
], "Transport: full-day chauffeured sedan, Candolim&#8594;Old Goa&#8594;Panjim&#8594;Cabo de Rama&#8594;Agonda &#8377;2,800 [RES] (a multi-stop day-hire; MMT's point-to-point one-way quote of &#8377;2,145 would undercount the detours and wait time, so a typical Dec-season 8hr/80km sedan day-rate is used instead). Old Goa church entry is free; nominal museum/donation &#8377;100 for 2 [ASM]."))

story.append(day_block(6, "Sun 20 Dec", "South Goa beach day &#8211; Agonda &amp; Palolem", "S", [
    "Morning: relaxed swim and breakfast at Agonda beach (a fraction of North Goa's crowds)",
    "Midday: short scooter ride to Palolem &#8211; Goa's famous crescent-shaped beach",
    "Afternoon: optional dolphin-spotting/kayak boat trip from Palolem",
    "Evening: beachside bonfire dinner at a Palolem shack",
], "Transport: 2 scooters for the day &#8377;1,200 + fuel &#8377;200 [RES]. Optional boat/kayak trip &#8377;1,400 for 2 [ASM, optional]."))

story.append(day_block(7, "Mon 21 Dec", "Leisure morning &amp; departure", "S", [
    "Late checkout; final relaxed morning/swim at Palolem",
    "Transfer to Dabolim Airport (~1.5&ndash;2 hrs from Palolem)",
    "Depart GOI 19:15, land BLR 20:25 (IndiGo 6E 6163, non-stop, 1h10m) &#8211; [MMT]",
], "Transport: Palolem &#8594; Airport &#8377;2,045 [MMT]."))

story.append(PageBreak())

# ------------------------------------------------------------ FLIGHTS
story.append(P("Flights &#8211; Bengaluru &#8596; Goa (Dabolim)", "H1"))
story.append(P("Fetched live from MakeMyTrip via mmt-mcp on 5-Sep-2026 for 2 adults, economy cabin. "
               "Fares are per adult; totals below are for 2 passengers. GOX (Mopa) options are shown "
               "in the raw data but excluded here as GOI suits both bases better.", "BodySmall"))
story.append(Spacer(1, 6))

flight_data = [
    [P("Leg", "CellHead"), P("Flight", "CellHead"), P("Depart &#8594; Arrive", "CellHead"),
     P("Duration", "CellHead"), P("Fare/adult", "CellHead"), P("Total (2)", "CellHead")],
    [P("Outbound &#8211; 15 Dec", "Cell"), P("IndiGo 6E 6168", "Cell"), P("BLR 17:25 &#8594; GOI 18:45", "Cell"),
     P("1h 20m, non-stop", "Cell"), P("&#8377;4,577", "Cell"), P("<b>&#8377;9,154</b>", "Cell")],
    [P("Return &#8211; 21 Dec", "Cell"), P("IndiGo 6E 6163", "Cell"), P("GOI 19:15 &#8594; BLR 20:25", "Cell"),
     P("1h 10m, non-stop", "Cell"), P("&#8377;5,994", "Cell"), P("<b>&#8377;11,988</b>", "Cell")],
]
t = Table(flight_data, colWidths=[75, 75, 110, 75, 70, 65])
t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY),
    ("GRID", (0,0), (-1,-1), 0.5, colors.white),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [LIGHT, colors.white]),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
]))
story.append(t)
story.append(P("<b>Flight subtotal (2 pax, round trip): &#8377;21,142</b> [MMT]. "
               "Cheapest options seen were FLY91 (&#8377;3,099/&#8377;3,699 into SDW &ndash; Sindhudurg, an alternate "
               "airport ~1.5&ndash;2 hrs north of North Goa, not used here) and IndiGo's late-evening 6E 6554/6E 977 "
               "(&#8377;4,367) &#8211; the 17:25 departure was chosen for a same-day, comfortable arrival window.", "BodySmall"))
story.append(Spacer(1, 14))

# ------------------------------------------------------------ HOTELS
story.append(P("Hotels", "H1"))
story.append(P("Live MakeMyTrip nightly retail rates (signed-out), 1 room / 2 adults. "
               "<i>stay_estimate</i> = nightly rate &#215; nights, an MMT-provided estimate for a date range "
               "(a range spanning a price change may not match exactly).", "BodySmall"))
story.append(Spacer(1, 6))

hotel_data = [
    [P("Base", "CellHead"), P("Hotel", "CellHead"), P("Nights", "CellHead"),
     P("Nightly all-in", "CellHead"), P("Stay estimate", "CellHead")],
    [P("North Goa<br/>(Candolim)", "Cell"), P("Hyatt Centric Candolim Goa &#9733;5<br/>(4.3&#9733; reviews) &#8211; chosen mid-range pick", "Cell"),
     P("4<br/>(15&ndash;19 Dec)", "Cell"), P("&#8377;12,762", "Cell"), P("<b>&#8377;51,048</b>", "Cell")],
    [P("South Goa<br/>(Agonda)", "Cell"), P("The Shore Agonda &#9733;5<br/>(4.0&#9733; reviews) &#8211; Garden View room", "Cell"),
     P("2<br/>(19&ndash;21 Dec)", "Cell"), P("&#8377;8,308", "Cell"), P("<b>&#8377;16,616</b>", "Cell")],
]
t = Table(hotel_data, colWidths=[70, 190, 55, 75, 80])
t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY),
    ("GRID", (0,0), (-1,-1), 0.5, colors.white),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [LIGHT, colors.white]),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
]))
story.append(t)
story.append(Spacer(1,4))
story.append(P("<b>Hotel subtotal: &#8377;67,664</b> [MMT] (room-only rate; breakfast-inclusive plan for "
               "Hyatt Centric adds &#8377;638/night &#8211; not included in the base budget below). "
               "<b>Budget alternative</b> [MMT]: Ginger Goa, Candolim (&#9733;4, 4.2&#9733;) at &#8377;9,557/night "
               "(&#8377;38,228 for 4 nights) would cut &#8377;12,820 from the North Goa leg if a business/lifestyle "
               "hotel is preferred over a 5-star resort.", "BodySmall"))
story.append(PageBreak())

# ------------------------------------------------------------ GROUND TRANSPORT
story.append(P("Ground Transport &amp; Intercity Cabs", "H1"))
story.append(P("Outstation point-to-point cab fares below are live MMT quotes [MMT]. MakeMyTrip's "
               "cab funnel only prices point-to-point trips, not the 8hr/80km local day-hire packages "
               "that Goa taxis commonly sell for multi-stop sightseeing days (Day 4 &amp; Day 5) &#8211; this is "
               "a known gap in the MMT tool, so those two days instead sum/substitute one-way legs or use "
               "a researched day-rate, both flagged in the day-by-day notes above.", "BodySmall"))
story.append(Spacer(1, 6))

cab_data = [
    [P("Route", "CellHead"), P("Date", "CellHead"), P("Vehicle (cheapest)", "CellHead"), P("Fare (all-in)", "CellHead")],
    [P("Dabolim Airport &#8594; Calangute/Candolim", "Cell"), P("15 Dec", "Cell"), P("WagonR/Swift hatchback, CNG", "Cell"), P("&#8377;2,045", "Cell")],
    [P("Candolim &#8594; Mollem (Dudhsagar gateway)", "Cell"), P("18 Dec", "Cell"), P("Dzire/Etios sedan, diesel", "Cell"), P("&#8377;2,145", "Cell")],
    [P("Mollem &#8594; Candolim (return)", "Cell"), P("18 Dec", "Cell"), P("Dzire/Etios sedan, diesel", "Cell"), P("&#8377;2,145", "Cell")],
    [P("Candolim &#8594; Palolem/Agonda (via Cabo de Rama)", "Cell"), P("19 Dec", "Cell"), P("Sedan day-hire (multi-stop)", "Cell"), P("&#8377;2,800 [RES]", "Cell")],
    [P("Palolem &#8594; Dabolim Airport", "Cell"), P("21 Dec", "Cell"), P("WagonR/Swift hatchback, CNG", "Cell"), P("&#8377;2,045", "Cell")],
]
t = Table(cab_data, colWidths=[190, 45, 130, 80])
t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY),
    ("GRID", (0,0), (-1,-1), 0.5, colors.white),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [LIGHT, colors.white]),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
]))
story.append(t)
story.append(Spacer(1,4))
story.append(P("<b>Intercity/transfer cab subtotal: &#8377;11,180</b> ([MMT] &#8377;8,380 + [RES] &#8377;2,800). "
               "All MMT quotes above returned Eroovo/Taxibazaar-operated hatchback or sedan cabs "
               "(~40&nbsp;km, ~4&nbsp;hr trips per the tool's distance/duration estimate) as the cheapest option; "
               "6-seat SUV upgrades (Ertiga/Innova) run &#8377;600&ndash;2,500 more per leg if extra luggage space is needed.", "BodySmall"))
story.append(Spacer(1, 10))
story.append(P("Local (within-belt) transport &#8211; self-drive scooters on 3 sightseeing days "
               "(Day 2, Day 3, Day 6) &#215; 2 scooters @ &#8377;600/day + fuel &#8377;200/day/scooter-pair "
               "= <b>&#8377;4,200</b> [RES]. Petrol-run gearless scooters (Activa/Jupiter class) typically "
               "rent for &#8377;400&ndash;900/day in Dec peak season, rising toward &#8377;1,000&ndash;1,500/day right "
               "around Christmas week; this trip ends just before that spike (21 Dec).", "Body"))
story.append(PageBreak())

# ------------------------------------------------------------ FULL BUDGET
story.append(P("Full Itemised Budget (2 Adults, INR)", "H1"))
story.append(P("Every line below is priced for the whole party of 2, in the currency and per-item "
               "convention returned by its source. [MMT] = live tool quote; [RES] = desk research "
               "(no MMT endpoint exists for this category); [ASM] = planning assumption.", "BodySmall"))
story.append(Spacer(1, 6))

budget_rows = [
    ["Category", "Item", "Source", "Amount (INR)"],
    ("Flights", "Bengaluru &#8594; Goa, 15 Dec, IndiGo 6E 6168 (2 adults)", "MMT", "9,154"),
    ("Flights", "Goa &#8594; Bengaluru, 21 Dec, IndiGo 6E 6163 (2 adults)", "MMT", "11,988"),
    ("Hotel", "Hyatt Centric Candolim Goa, 4 nights (15&ndash;19 Dec)", "MMT", "51,048"),
    ("Hotel", "The Shore Agonda, 2 nights (19&ndash;21 Dec)", "MMT", "16,616"),
    ("Airport transfer", "Dabolim Airport &#8594; Candolim, 15 Dec", "MMT", "2,045"),
    ("Airport transfer", "Palolem &#8594; Dabolim Airport, 21 Dec", "MMT", "2,045"),
    ("Intercity cab", "Candolim &#8596; Mollem return (Dudhsagar day), 18 Dec", "MMT", "4,290"),
    ("Intercity cab", "Candolim &#8594; Agonda via Old Goa/Cabo de Rama, 19 Dec", "RES", "2,800"),
    ("Local transport", "Self-drive scooter x2, 3 days + fuel", "RES", "4,200"),
    ("Entry fees", "Fort Aguada/Sinquerim", "RES", "100"),
    ("Entry fees", "Old Goa church donation/museum", "ASM", "100"),
    ("Activity", "Water sports combo, Baga/Calangute (2 pax)", "RES", "2,600"),
    ("Activity", "Mandovi sunset river cruise (2 pax)", "RES", "1,200"),
    ("Activity", "Dudhsagar jeep safari + sanctuary entry (2 pax)", "RES", "1,300"),
    ("Activity", "Spice plantation tour + Goan lunch (2 pax)", "RES", "1,600"),
    ("Activity", "Palolem dolphin/kayak boat trip (2 pax, optional)", "ASM", "1,400"),
    ("Nightlife", "Tito's Lane cover + drinks (2 pax)", "ASM", "4,000"),
    ("Shopping", "Anjuna flea market &amp; souvenirs (budget, ASM)", "ASM", "3,000"),
    ("Food", "Meals not covered above &#8211; ~6 meals/day &#215; 6 days (2 pax)", "ASM", "14,000"),
    ("Contingency", "Tips, SIM/data, misc (~5% of trip)", "ASM", "5,500"),
]
tbl = [budget_rows[0]] + [[P(r[0],"Cell"), P(r[1],"Cell"), P(r[2],"Cell"), P(f"&#8377;{r[3]}","Cell")] for r in budget_rows[1:]]
tbl[0] = [P(h,"CellHead") for h in budget_rows[0]]
total_row = [P("<b>TOTAL</b>","CellHead"), P("<b>All items above, 2 adults</b>","CellHead"),
             P("&#8211;","CellHead"), P("<b>&#8377;1,38,986</b>","CellHead")]
tbl.append(total_row)
t = Table(tbl, colWidths=[68, 227, 45, 70])
t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY),
    ("BACKGROUND", (0,-1), (-1,-1), TEAL),
    ("GRID", (0,0), (-1,-1), 0.4, colors.white),
    ("ROWBACKGROUNDS", (0,1), (-1,-2), [LIGHT, colors.white]),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("ALIGN", (3,0), (3,-1), "RIGHT"),
    ("TOPPADDING", (0,0), (-1,-1), 4.5), ("BOTTOMPADDING", (0,0), (-1,-1), 4.5),
]))
story.append(t)
story.append(Spacer(1, 10))
story.append(P("<b>Per-person total: &#8377;69,493.</b> Breakdown by category: Flights &#8377;21,142 (15.2%) &#8226; "
               "Hotels &#8377;67,664 (48.7%) &#8226; Ground transport (airport + intercity + local) &#8377;15,380 (11.1%) "
               "&#8226; Activities &amp; entry fees &#8377;8,300 (6.0%) &#8226; Nightlife &#8377;4,000 (2.9%) &#8226; "
               "Shopping &#8377;3,000 (2.2%) &#8226; Food &#8377;14,000 (10.1%) &#8226; Contingency &#8377;5,500 (4.0%). "
               "Hotels dominate the budget because both properties chosen are 5-star; swapping to the Ginger Goa "
               "budget alternative on Day 1&ndash;5 (see Hotels section) brings the trip to roughly <b>&#8377;1,26,166</b> "
               "(&#8377;63,083/person) without changing any activity.", "Body"))
story.append(PageBreak())

# ------------------------------------------------------------ ASSUMPTIONS & NOTES
story.append(P("Assumptions, Data Caveats &amp; How to Re-Price", "H1"))
story.append(P("<b>What is a live MakeMyTrip quote vs. research:</b> Flights, hotel nightly rates and "
               "the four outstation cab legs were pulled directly from MakeMyTrip via the makemytrip-mcp "
               "server on 5 Sep 2026 and are the actual signed-out retail figures the site shows today for "
               "these dates. Entry tickets, water sports, cruises, the jeep safari, spice-plantation tours, "
               "nightlife cover charges, scooter rentals, shopping and food are <b>not exposed by any "
               "MakeMyTrip search/booking funnel</b> reachable from this tool (confirmed via the capabilities "
               "probe) and were sized from December-season desk research instead.", "Body"))
story.append(Spacer(1,6))
story.append(P("<b>Call-budget discipline:</b> Per the task brief, only one outbound and one return "
               "flight search were run (no date- or airport-sweeping); the fares quoted are for the "
               "17:25 BLR&#8594;GOI and 19:15 GOI&#8594;BLR non-stops specifically, not a sweep of the cheapest "
               "across the whole day. Two hotel searches (one per base's date range) and four one-way cab "
               "quotes were run, each once, with the two hotel searches retried once after an initial "
               "date-format/circuit-breaker failure (see below) &#8211; within the one-retry allowance.", "Body"))
story.append(Spacer(1,6))
story.append(P("<b>Date correction:</b> The MakeMyTrip tool's clock reports the current date as "
               "5 September 2026; \"15 December\" therefore resolves to 15 Dec 2026, not 2025 (confirmed "
               "when initial 2025-dated hotel searches were rejected as being in the past). All prices in "
               "this report are for December 2026 accordingly.", "Body"))
story.append(Spacer(1,6))
story.append(P("<b>Known gaps flagged by the MMT tool itself</b> and how this report handled them: "
               "(1) no 8hr/80km local day-package cab funnel &#8211; substituted with either two one-way legs "
               "(Day 4) or a researched day-hire rate (Day 5), both called out inline; (2) hotel "
               "stay_estimate_all_in_inr is nightly &#215; nights, not a true multi-night quote, so a rate "
               "change mid-stay would not be captured; (3) MakeMyTrip cannot be booked through this tool &#8211; "
               "all figures are indicative, pre-tax-surcharge-drift pricing for planning purposes, and should "
               "be re-confirmed on the site (or app) before actual payment.", "Body"))
story.append(Spacer(1,6))
story.append(P("<b>To refresh this report closer to the trip date</b>, re-run: mmt_flight_search "
               "(BLR&#8596;GOI, both dates), mmt_hotel_rates for the two chosen hotel_ids, and mmt_cab_quote "
               "for the four routes listed in the Ground Transport table &#8211; fares can move with demand, "
               "especially in the week immediately before Christmas.", "Body"))
story.append(Spacer(1, 16))
story.append(HRFlowable(width="100%", thickness=0.8, color=GREY))
story.append(Spacer(1, 6))
story.append(P("Report generated by Cline using the makemytrip-mcp server (live pricing) and Perplexity "
               "research (activity/local-transport context) on 5 Sep 2026. All prices in Indian Rupees (INR) "
               "and subject to change.", "Note"))

# ------------------------------------------------------------------ BUILD
def _footer(canvas, doc_):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(20*mm, 12*mm, "Goa Getaway \u2013 7D/6N Itinerary & Budget \u2013 Dec 2026")
    canvas.drawRightString(190*mm, 12*mm, f"Page {doc_.page}")
    canvas.restoreState()

doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    leftMargin=20*mm, rightMargin=20*mm, topMargin=16*mm, bottomMargin=18*mm,
    title="Goa Getaway - 7D/6N Itinerary & Budget - Dec 2026",
    author="Cline (makemytrip-mcp + Perplexity research)",
)
doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
print(f"PDF written to {OUT}")

