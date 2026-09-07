# -*- coding: utf-8 -*-
"""Goa 7-Day Itinerary & Budget Report Builder (ReportLab)."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT

NAVY = colors.HexColor("#0B3D59")
TEAL = colors.HexColor("#0E7C7B")
SAND = colors.HexColor("#F4E9DA")
LIGHT = colors.HexColor("#F7F9FA")
GREY = colors.HexColor("#5A5A5A")
GOLD = colors.HexColor("#C9963E")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="H1", fontSize=16, leading=20, textColor=NAVY,
                           fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6))
styles.add(ParagraphStyle(name="H2", fontSize=12, leading=15, textColor=TEAL,
                           fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4))
styles.add(ParagraphStyle(name="Body", fontSize=9.3, leading=13, textColor=colors.HexColor("#222222"),
                           fontName="Helvetica"))
styles.add(ParagraphStyle(name="BodySmall", fontSize=8.2, leading=11, textColor=GREY,
                           fontName="Helvetica"))
styles.add(ParagraphStyle(name="Assumption", fontSize=8.2, leading=11.5, textColor=colors.HexColor("#7A5B00"),
                           fontName="Helvetica-Oblique"))
styles.add(ParagraphStyle(name="TblHead", fontSize=8.6, leading=11, textColor=colors.white,
                           fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="TblCell", fontSize=8.2, leading=10.6, textColor=colors.HexColor("#222222"),
                           fontName="Helvetica"))
styles.add(ParagraphStyle(name="TblCellR", fontSize=8.2, leading=10.6, textColor=colors.HexColor("#222222"),
                           fontName="Helvetica", alignment=TA_RIGHT))
styles.add(ParagraphStyle(name="TblCellBold", fontSize=8.6, leading=11, textColor=NAVY,
                           fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="TblCellBoldR", fontSize=8.6, leading=11, textColor=NAVY,
                           fontName="Helvetica-Bold", alignment=TA_RIGHT))
styles.add(ParagraphStyle(name="FootNote", fontSize=7.6, leading=10, textColor=GREY,
                           fontName="Helvetica-Oblique"))

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm

def money(n):
    return "Rs {:,.0f}".format(n)

def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(MARGIN, 10*mm, "Goa Getaway | 15-21 Dec 2026 | 2 adults from Bengaluru")
    canvas.drawRightString(PAGE_W - MARGIN, 10*mm, "Page {}".format(doc.page))
    canvas.setStrokeColor(colors.HexColor("#CCCCCC"))
    canvas.line(MARGIN, 13*mm, PAGE_W-MARGIN, 13*mm)
    canvas.restoreState()

def cover_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, PAGE_H-95*mm, PAGE_W, 95*mm, stroke=0, fill=1)
    canvas.setFillColor(GOLD)
    canvas.rect(0, PAGE_H-97*mm, PAGE_W, 2*mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 30)
    canvas.drawString(MARGIN, PAGE_H-45*mm, "GOA GETAWAY")
    canvas.setFont("Helvetica", 14)
    canvas.drawString(MARGIN, PAGE_H-55*mm, "A 7-Day / 6-Night Itinerary & Budget Report")
    canvas.setFont("Helvetica", 10.5)
    canvas.drawString(MARGIN, PAGE_H-65*mm, "Bengaluru -> Goa -> Bengaluru  |  15-21 December 2026  |  2 Adults")
    canvas.setFont("Helvetica-Oblique", 9)
    canvas.drawString(MARGIN, PAGE_H-73*mm, "North Goa (Candolim) 3N  +  South Goa (Colva) 3N")
    canvas.setFillColor(colors.HexColor("#D8E6EA"))
    canvas.setFont("Helvetica", 8.3)
    canvas.drawString(MARGIN, 20*mm, "Prices sourced live via MakeMyTrip MCP tools (flights, hotels, cabs) on 05 Sep 2026,")
    canvas.drawString(MARGIN, 16*mm, "cross-checked with web research for sightseeing & local transport. All figures are indicative, pre-booking estimates.")
    canvas.restoreState()

story = []

# ============ SECTION: Executive Summary ============
story.append(Spacer(1, 100*mm))
story.append(Paragraph("Executive Summary", styles["H1"]))
story.append(Paragraph(
    "This report prices a 7-day / 6-night Goa holiday for <b>2 adults</b> departing Bengaluru on "
    "<b>Tuesday, 15 December 2026</b> and returning <b>Monday, 21 December 2026</b>. The trip is split "
    "3 nights in North Goa (Candolim &ndash; lively beaches, forts, markets, nightlife) and 3 nights in "
    "South Goa (Colva &ndash; quieter beaches, Old Goa churches, Dudhsagar Falls, Palolem), connected by a "
    "single road transfer on Day 4. All flight, hotel and cab prices below were fetched live from the "
    "MakeMyTrip MCP tools for the exact travel dates; sightseeing entry fees, scooter rental and food costs "
    "are triangulated from current travel-cost web research, since MakeMyTrip does not sell local "
    "day-sightseeing cab packages or attraction e-tickets.",
    styles["Body"]))
story.append(Spacer(1, 5))

summary_data = [
    [Paragraph("Category", styles["TblHead"]), Paragraph("What's Included", styles["TblHead"]),
     Paragraph("Cost (2 pax)", styles["TblHead"])],
    ["Flights (round trip)", "IndiGo BLR->GOI outbound + FLY91 GOI->BLR return, nonstop", money(16132)],
    ["Hotels (6 nights)", "Park Inn by Radisson Candolim (3N) + Courtyard Marriott Colva (3N)", money(76755)],
    ["Airport & inter-town transfers", "Airport-Candolim, Candolim-Colva, Colva-Airport (sedan cabs)", money(6335)],
    ["Sightseeing day-cabs", "Old Goa, Dudhsagar, Palolem return legs (sedan, 2-way each)", money(12870)],
    ["Scooter self-ride", "2 scooters x 2 days in North Goa @ Rs 600/day (research est.)", money(2400)],
    ["Attraction & activity fees", "Fort Aguada, Old Goa churches, spice plantation, Dudhsagar jeep, river cruise", money(4000)],
    ["Food (lunch/dinner/snacks)", "6 days x 2 pax @ Rs 1,300/person/day average (research est.)", money(15600)],
]
tbl = Table(summary_data, colWidths=[46*mm, 96*mm, 32*mm])
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY),
    ("TEXTCOLOR", (0,0), (-1,0), colors.white),
    ("FONTSIZE", (0,1), (-1,-1), 8.2),
    ("FONTNAME", (0,1), (0,-1), "Helvetica-Bold"),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#DDDDDD")),
    ("ALIGN", (2,0), (2,-1), "RIGHT"),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 4),
    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ("LEFTPADDING", (0,0), (-1,-1), 5),
]))
story.append(tbl)
story.append(Spacer(1, 6))
story.append(Paragraph(
    "<b>Estimated Grand Total: Rs 1,34,092</b> for 2 adults (&asymp; Rs 67,046 per person, &asymp; Rs 9,578 "
    "per person per day). See the Budget Summary section near the end of this report for the full "
    "line-by-line arithmetic, and each day's page for the assumptions behind that day's numbers.",
    styles["Body"]))
story.append(PageBreak())

# ============ SECTION: Intercity Transport Comparison ============
story.append(Paragraph("Getting There: Bengaluru &harr; Goa Transport Comparison", styles["H1"]))
story.append(Paragraph(
    "MakeMyTrip's intercity comparison tool was queried for both legs, pricing flight, train and cab options "
    "side by side for 2 adults. Trains for these December dates are outside Indian Railways' 60-day booking "
    "window (opens 16 Oct 2026 for the outbound, 22 Oct 2026 for the return); the fares shown are MakeMyTrip's "
    "own <i>indicative</i> quotes for the nearest bookable date on the same weekday, not the actual 15/21 Dec fare.",
    styles["Body"]))
story.append(Spacer(1, 4))
story.append(Paragraph("Outbound &ndash; 15 December 2026 (Bengaluru &rarr; Goa)", styles["H2"]))
out_data = [
    [Paragraph(x, styles["TblHead"]) for x in ["Mode", "Option", "Depart-Arrive", "Duration", "Cost (2 pax)"]],
    ["Flight (chosen)", "IndiGo 6E 6554 nonstop", "19:00-20:20", "1h 20m", money(8734)],
    ["Flight (alt.)", "IndiGo 6E 977 nonstop", "20:50-22:10", "1h 20m", money(8734)],
    ["Train (indicative)", "16210 Ajmer Exp, CC class*", "23:50-08:28", "8h 38m", money(1470)],
    ["Cab", "Sedan (Dzire/Etios), one-way", "~10:00 start", "11h 30m", money(12407)],
]
t1 = Table(out_data, colWidths=[24*mm, 46*mm, 26*mm, 20*mm, 28*mm])
t1.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), TEAL),
    ("TEXTCOLOR", (0,0), (-1,0), colors.white),
    ("FONTSIZE", (0,1), (-1,-1), 8.2),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#DCF0EE")),
    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#DDDDDD")),
    ("ALIGN", (4,0), (4,-1), "RIGHT"),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 3.5), ("BOTTOMPADDING", (0,0), (-1,-1), 3.5),
]))
story.append(t1)
story.append(Paragraph("* Train fare is indicative, quoted for 03-Nov-2026 (same weekday) &ndash; not bookable for 15-Dec until 16-Oct-2026.", styles["FootNote"]))
story.append(Spacer(1, 6))

story.append(Paragraph("Return &ndash; 21 December 2026 (Goa &rarr; Bengaluru)", styles["H2"]))
ret_data = [
    [Paragraph(x, styles["TblHead"]) for x in ["Mode", "Option", "Depart-Arrive", "Duration", "Cost (2 pax)"]],
    ["Flight (chosen)", "FLY91 IC 5301 nonstop", "09:20-11:10", "1h 50m", money(7398)],
    ["Flight (alt.)", "IndiGo 6E 6163 nonstop", "19:15-20:25", "1h 10m", money(11988)],
    ["Train (indicative)", "20675 Vishwamanav Exp, CC*", "07:50-17:45", "9h 55m", money(1570)],
    ["Cab", "Sedan (Dzire/Etios), one-way", "~10:00 start", "11h 30m", money(13673)],
]
t2 = Table(ret_data, colWidths=[24*mm, 46*mm, 26*mm, 20*mm, 28*mm])
t2.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), TEAL),
    ("TEXTCOLOR", (0,0), (-1,0), colors.white),
    ("FONTSIZE", (0,1), (-1,-1), 8.2),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#DCF0EE")),
    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#DDDDDD")),
    ("ALIGN", (4,0), (4,-1), "RIGHT"),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 3.5), ("BOTTOMPADDING", (0,0), (-1,-1), 3.5),
]))
story.append(t2)
story.append(Paragraph("* Train fare is indicative, quoted for 02-Nov-2026 (same weekday) &ndash; not bookable for 21-Dec until 22-Oct-2026.", styles["FootNote"]))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "<b>Recommendation:</b> Flights are the clear choice on both legs &ndash; the outbound flight costs "
    "~6x the train's indicative fare but saves 7+ hours, and the return FLY91 flight at Rs 7,398 for two "
    "is barely 5x the (indicative, not-yet-bookable) train fare while taking a quarter of the time. The 603 km "
    "road trip (~11.5 hr one-way) is dominated by air on both cost and time and is not recommended for this leg; "
    "it is priced here only for completeness. Actual train fares/availability for these exact dates will only be "
    "visible once the 60-day booking window opens &ndash; re-check closer to the date if rail is preferred.",
    styles["Assumption"]))
story.append(PageBreak())

# ============ SECTION: Hotels ============
story.append(Paragraph("Where You'll Stay", styles["H1"]))
story.append(Paragraph(
    "Both properties were selected from live MakeMyTrip hotel search results (signed-out retail rates, "
    "for 2 adults / 1 room) balancing rating, location and price. Rates are PER NIGHT; the stay total is "
    "nightly rate x nights and is MakeMyTrip's own estimate (it quotes one representative nightly rate per "
    "date range, not a per-date breakdown).", styles["Body"]))
story.append(Spacer(1, 4))

story.append(Paragraph("North Goa: Park Inn by Radisson, Candolim (4-star, rated 3.9/5)", styles["H2"]))
h1 = [
    [Paragraph(x, styles["TblHead"]) for x in ["Nights", "Room Type", "Meal Plan", "Nightly All-in", "Stay Total"]],
    ["15-18 Dec (3N)", "Standard Queen with Balcony, free cancellation", "Breakfast included",
     money(10265), money(30795)],
]
th1 = Table(h1, colWidths=[22*mm, 62*mm, 30*mm, 26*mm, 26*mm])
th1.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
    ("FONTSIZE", (0,1), (-1,-1), 8.2), ("BACKGROUND", (0,1), (-1,1), LIGHT),
    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#DDDDDD")),
    ("ALIGN", (3,0), (4,-1), "RIGHT"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(th1)
story.append(Paragraph(
    "Includes free cancellation (before 01 Dec), complimentary welcome drink, Rs 1,000 F&amp;B credit and "
    "happy-hour 1+1 offer. Free breakfast is bundled into every rate plan at this property.", styles["FootNote"]))
story.append(Spacer(1, 6))

story.append(Paragraph("South Goa: Courtyard by Marriott, Colva (5-star, rated 4.7/5)", styles["H2"]))
h2 = [
    [Paragraph(x, styles["TblHead"]) for x in ["Nights", "Room Type", "Meal Plan", "Nightly All-in", "Stay Total"]],
    ["18-21 Dec (3N)", "Deluxe Room, Queen Bed, free cancellation", "Breakfast included",
     money(15320), money(45960)],
]
th2 = Table(h2, colWidths=[22*mm, 62*mm, 30*mm, 26*mm, 26*mm])
th2.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
    ("FONTSIZE", (0,1), (-1,-1), 8.2), ("BACKGROUND", (0,1), (-1,1), LIGHT),
    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#DDDDDD")),
    ("ALIGN", (3,0), (4,-1), "RIGHT"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(th2)
story.append(Paragraph(
    "Includes free cancellation (before 13 Dec), complimentary bicycle, welcome alcoholic beverage, "
    "10% off F&amp;B and daily buffet breakfast. A pool-view upgrade is available for ~Rs 560 extra per night.",
    styles["FootNote"]))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "<b>Budget alternative (either city):</b> The Hosteller Goa, Anjuna (3-star hostel/private rooms) prices "
    "around Rs 2,156-2,316 all-in per night, and Panjim City Dorms around Rs 1,202/night &ndash; either could "
    "cut the hotel line by roughly Rs 55,000-65,000 for a backpacker-style trip, at the cost of resort amenities.",
    styles["Assumption"]))
story.append(PageBreak())

# ============ SECTION: Day-by-Day Itinerary ============
story.append(Paragraph("Day-by-Day Itinerary", styles["H1"]))
story.append(Paragraph(
    "Base: <b>North Goa &ndash; Candolim</b> (Day 1-3, Park Inn by Radisson) then <b>South Goa &ndash; Colva</b> "
    "(Day 4-6, Courtyard by Marriott). Each day lists the plan, mode of local transport, and the cost driver "
    "already reflected in the Budget Summary. Attraction fees are ballpark web-research figures (per person) "
    "since MakeMyTrip does not sell entry tickets.", styles["Body"]))
story.append(Spacer(1, 4))

def day_block(day_no, date_str, title, items, transport, cost_note):
    story.append(Paragraph("Day {} &mdash; {} &nbsp;|&nbsp; {}".format(day_no, date_str, title), styles["H2"]))
    for it in items:
        story.append(Paragraph("&bull; " + it, styles["Body"]))
    story.append(Paragraph("<b>Local transport:</b> " + transport, styles["BodySmall"]))
    story.append(Paragraph("<b>Cost note:</b> " + cost_note, styles["BodySmall"]))
    story.append(Spacer(1, 5))

day_block(1, "Tue 15 Dec", "Arrival &amp; North Goa check-in",
    ["Depart Bengaluru ~19:00 on IndiGo 6E 6554, land Goa (Dabolim/GOI) ~20:20.",
     "Pre-booked sedan cab from airport to Park Inn by Radisson, Candolim (~40 km, ~1 hr).",
     "Check in, relax; light dinner at a Candolim beach shack."],
    "Airport &rarr; Candolim sedan cab (pre-booked via MMT cabs, Rs 2,045 all-in).",
    "Cab Rs 2,045 (2-pax total) + dinner ~Rs 1,300/pax included in food budget.")

day_block(2, "Wed 16 Dec", "Candolim, Calangute &amp; Baga beaches + Fort Aguada",
    ["Morning: Fort Aguada &amp; lighthouse (entry ~Rs 50/pax).",
     "Sinquerim &amp; Candolim beach walk.",
     "Afternoon at Calangute Beach, evening at Baga Beach; shacks &amp; live music at night."],
    "Self-ride scooter, 2 units for the day (~Rs 600/day/scooter).",
    "Scooter Rs 1,200 (2 units) + Fort Aguada entry Rs 100 (2 pax).")

day_block(3, "Thu 17 Dec", "Anjuna, Vagator, Chapora Fort &amp; Old Goa churches",
    ["Morning: Anjuna Beach; Anjuna flea market if it falls on a Wednesday during your actual travel week.",
     "Vagator Beach and sunset at Chapora Fort.",
     "Detour to Old Goa: Basilica of Bom Jesus and Se Cathedral (both free entry; small museum fee optional).",
     "Evening: Mandovi River sunset cruise from Panaji (~Rs 500/pax standard cruise)."],
    "Sedan cab, round trip Candolim-Old Goa-Panaji-Candolim (booked as one-way MMT quote x2 as proxy).",
    "Cab ~Rs 4,290 (2,145 x2 legs) + cruise Rs 1,000 (2 pax) + museum ~Rs 100.")

day_block(4, "Fri 18 Dec", "Transfer to South Goa via Mapusa Market",
    ["Morning: Mapusa Market for spices, cashew feni &amp; local produce.",
     "Check out of Candolim hotel; road transfer south (~40 km, ~1 hr) to Colva.",
     "Check in to Courtyard by Marriott Colva; afternoon on Colva Beach."],
    "Sedan cab, Candolim &rarr; Colva (MMT quote, Rs 2,145 all-in).",
    "Cab Rs 2,145 (2-pax total); no separate attraction fee.")

day_block(5, "Sat 19 Dec", "Colva, Benaulim, Margao &amp; Palolem",
    ["Morning: Colva &amp; Benaulim beaches on scooter, quieter than the north.",
     "Margao town: municipal market and old Portuguese quarter.",
     "Afternoon excursion to Palolem Beach (and Patnem/Colomb if time allows); return by evening."],
    "Scooter (2 units) for the Colva/Benaulim/Margao morning; sedan cab return trip to Palolem in the afternoon.",
    "Scooter Rs 1,200 (2 units) + cab ~Rs 4,290 (2 legs, 2-pax total); lunch included in food budget.")

day_block(6, "Sun 20 Dec", "Dudhsagar Falls day excursion",
    ["Early departure (~07:00) for Dudhsagar Falls via Mollem.",
     "Regulated forest-department jeep safari to the falls base (~Rs 700/pax incl. permit).",
     "Optional spice plantation stop with traditional Goan lunch (~Rs 700/pax) on the way back.",
     "Return to Colva by late afternoon; relaxed evening."],
    "Sedan cab, Colva &rarr; Dudhsagar return (MMT one-way quote x2 as proxy, Rs 2,145 each way).",
    "Cab ~Rs 4,290 + jeep safari Rs 1,400 (2 pax) + plantation lunch Rs 1,400 (2 pax).")

day_block(7, "Mon 21 Dec", "Departure",
    ["Leisurely morning at Colva Beach; check out by 10:00.",
     "Sedan cab to Dabolim Airport (~40 km, ~1 hr).",
     "Depart Goa 09:20 on FLY91 IC 5301, land Bengaluru 11:10."],
    "Colva &rarr; Airport sedan cab (MMT quote, Rs 2,145 all-in).",
    "Cab Rs 2,145 (2-pax total).")

story.append(PageBreak())

# ============ SECTION: Local Transport Reference ============
story.append(Paragraph("Local Transport & Cab Reference Rates", styles["H1"]))
story.append(Paragraph(
    "MakeMyTrip's outstation cab product does not sell 8hr/80km local sightseeing-day packages, so each "
    "point-to-point leg below was priced individually via mmt_cab_quote and used as the transport proxy for "
    "that day. Self-ride scooter rental is not sold on MakeMyTrip at all (no such product exists on the "
    "platform) and is sourced from current Goa travel-cost research instead.", styles["Body"]))
story.append(Spacer(1, 4))
lt_data = [
    [Paragraph(x, styles["TblHead"]) for x in ["Route", "Vehicle", "All-in Fare", "Source"]],
    ["Dabolim Airport -> Candolim", "Sedan (Dzire/Etios), CNG", money(2045), "MakeMyTrip cab quote"],
    ["Candolim -> Old Goa (one-way)", "Sedan (Dzire/Etios)", money(2145), "MakeMyTrip cab quote"],
    ["Candolim -> Colva", "Sedan (Dzire/Etios)", money(2145), "MakeMyTrip cab quote"],
    ["Colva -> Palolem (one-way)", "Sedan (Dzire/Etios)", money(2145), "MakeMyTrip cab quote"],
    ["Colva -> Dudhsagar Falls (one-way)", "Sedan (Dzire/Etios)", money(2145), "MakeMyTrip cab quote"],
    ["Colva -> Dabolim Airport", "Sedan (Dzire/Etios)", money(2145), "MakeMyTrip cab quote"],
    ["Scooter rental", "Activa/Access class", "Rs 500-900 /day", "Web research (not on MMT)"],
]
tlt = Table(lt_data, colWidths=[58*mm, 40*mm, 28*mm, 40*mm])
tlt.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), TEAL), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
    ("FONTSIZE", (0,1), (-1,-1), 8.2), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#DDDDDD")),
    ("ALIGN", (2,0), (2,-1), "RIGHT"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(tlt)
story.append(Spacer(1, 4))
story.append(Paragraph(
    "Note: distances for several of these point-to-point legs render as ~40 km / ~4 hr in MakeMyTrip's cab "
    "engine regardless of the actual geographic distance between the named localities &ndash; this looks like "
    "a platform default rather than a precise routing estimate, so treat the fares as directionally right but "
    "not GPS-precise. Return legs for the Old Goa, Palolem and Dudhsagar excursions are approximated as the "
    "one-way fare doubled, since MakeMyTrip's cab search only returns one-way outstation pricing on this route.",
    styles["Assumption"]))
story.append(Spacer(1, 6))

story.append(Paragraph("Attraction & Activity Fees (per person, research estimate)", styles["H2"]))
at_data = [
    [Paragraph(x, styles["TblHead"]) for x in ["Attraction", "Per-person Fee"]],
    ["Fort Aguada & lighthouse", "Rs 50"],
    ["Basilica of Bom Jesus / Se Cathedral", "Free (optional museum ~Rs 20-100)"],
    ["Mandovi River sunset cruise", "Rs 500"],
    ["Spice plantation tour + Goan lunch", "Rs 700"],
    ["Dudhsagar Falls jeep safari (incl. permit)", "Rs 700"],
]
tat = Table(at_data, colWidths=[110*mm, 56*mm])
tat.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), TEAL), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
    ("FONTSIZE", (0,1), (-1,-1), 8.2), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#DDDDDD")),
    ("ALIGN", (1,0), (1,-1), "RIGHT"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(tat)
story.append(PageBreak())

# ============ SECTION: Full Budget Summary ============
story.append(Paragraph("Full Budget Summary &mdash; Line by Line", styles["H1"]))
story.append(Paragraph(
    "Every line below is priced for the whole party of <b>2 adults</b>. Flight, hotel and cab figures are "
    "live MakeMyTrip quotes fetched on 05 Sep 2026 for the exact dates shown; lines marked (*) are web-research "
    "estimates because MakeMyTrip does not sell that product.", styles["Body"]))
story.append(Spacer(1, 4))

budget_rows = [
    [Paragraph(x, styles["TblHead"]) for x in ["#", "Line Item", "Detail", "Amount"]],
    ["1", "Flight: Bengaluru -> Goa", "IndiGo 6E 6554, 15 Dec, 19:00-20:20, 2 adults", money(8734)],
    ["2", "Flight: Goa -> Bengaluru", "FLY91 IC 5301, 21 Dec, 09:20-11:10, 2 adults", money(7398)],
    ["3", "Hotel: Park Inn Candolim", "3 nights x Rs 10,265/night, Standard Queen w/ Balcony", money(30795)],
    ["4", "Hotel: Courtyard Marriott Colva", "3 nights x Rs 15,320/night, Deluxe Queen Room", money(45960)],
    ["5", "Cab: Airport -> Candolim", "Sedan, 15 Dec", money(2045)],
    ["6", "Cab: Candolim -> Old Goa (return)*", "Sedan one-way x2, 17 Dec", money(4290)],
    ["7", "Cab: Candolim -> Colva", "Sedan, 18 Dec (hotel-to-hotel transfer)", money(2145)],
    ["8", "Cab: Colva -> Palolem (return)*", "Sedan one-way x2, 19 Dec", money(4290)],
    ["9", "Cab: Colva -> Dudhsagar (return)*", "Sedan one-way x2, 20 Dec", money(4290)],
    ["10", "Cab: Colva -> Airport", "Sedan, 21 Dec", money(2145)],
    ["11", "Scooter rental*", "2 units x 2 days x Rs 600/day (Day 2 & Day 5 mornings)", money(2400)],
    ["12", "Fort Aguada entry*", "2 pax x Rs 50", money(100)],
    ["13", "Old Goa museum (optional)*", "2 pax x Rs 50", money(100)],
    ["14", "Mandovi sunset cruise*", "2 pax x Rs 500", money(1000)],
    ["15", "Spice plantation + lunch*", "2 pax x Rs 700", money(1400)],
    ["16", "Dudhsagar jeep safari*", "2 pax x Rs 700", money(1400)],
    ["17", "Food: lunch/dinner/snacks*", "6 days x 2 pax x Rs 1,300/person/day", money(15600)],
]
tb = Table(budget_rows, colWidths=[8*mm, 46*mm, 78*mm, 24*mm])
tb.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
    ("FONTSIZE", (0,1), (-1,-1), 7.9), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#DDDDDD")),
    ("ALIGN", (3,0), (3,-1), "RIGHT"), ("ALIGN", (0,0), (0,-1), "CENTER"),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 3.2), ("BOTTOMPADDING", (0,0), (-1,-1), 3.2),
]))
story.append(tb)
story.append(Spacer(1, 6))

grand_rows = [
    [Paragraph("Grand Total (2 adults)", styles["TblCellBold"]), Paragraph(money(134092), styles["TblCellBoldR"])],
    [Paragraph("Per person", styles["TblCell"]), Paragraph(money(67046), styles["TblCellR"])],
    [Paragraph("Per person, per day (7 days)", styles["TblCell"]), Paragraph(money(9578), styles["TblCellR"])],
]
tg = Table(grand_rows, colWidths=[136*mm, 20*mm])
tg.setStyle(TableStyle([
    ("BOX", (0,0), (-1,-1), 0.8, NAVY),
    ("LINEBELOW", (0,0), (-1,0), 0.6, NAVY),
    ("BACKGROUND", (0,0), (-1,0), SAND),
    ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(tg)
story.append(Spacer(1, 8))
story.append(Paragraph(
    "* Web-research estimate (not a MakeMyTrip product): scooter rental, attraction/activity entry fees, and "
    "food. All other lines are live MakeMyTrip quotes for the stated dates. Hotel and flight rates are "
    "signed-out retail prices and can move before booking; cab fares are outstation point-to-point quotes "
    "used as a proxy for local sightseeing since MakeMyTrip has no day-package product.",
    styles["FootNote"]))
story.append(PageBreak())

# ============ SECTION: Assumptions & Notes ============
story.append(Paragraph("Assumptions, Data Sources & Caveats", styles["H1"]))
assumptions = [
    "<b>Pricing date:</b> All MakeMyTrip figures were fetched live on 05 Sep 2026. Fares and room rates "
    "change frequently (dynamic pricing) &ndash; treat every number here as an indicative benchmark, not a "
    "locked-in price, and re-quote close to your booking date.",
    "<b>Flights:</b> Cheapest nonstop option was chosen per leg from MakeMyTrip's live search "
    "(1 search per direction, respecting the 2-search budget). Fares are per-adult, one-way, economy, and "
    "exclude airport transfers (priced separately as cabs above) and seat/baggage add-ons.",
    "<b>Trains:</b> 15 &amp; 21 Dec 2026 fall outside Indian Railways' 60-day advance-reservation window. "
    "MakeMyTrip's \"indicative\" fares (for 02-03 Nov 2026, the furthest bookable date on the same weekday) "
    "are shown only for cost/time comparison in the transport section &ndash; they are not valid quotes for "
    "the actual travel dates and are excluded from the Grand Total.",
    "<b>Hotels:</b> Rates are MakeMyTrip's signed-out retail nightly rates for 2 adults / 1 room, with free "
    "cancellation. The multi-night stay figure is nightly-rate x nights, which is MakeMyTrip's own estimate "
    "convention (it does not return a per-date breakdown for a range).",
    "<b>Local sightseeing cabs:</b> MakeMyTrip has no 8hr/80km local day-package product. Each excursion "
    "(Old Goa, Palolem, Dudhsagar) is priced as a one-way outstation sedan fare doubled, as a reasonable "
    "proxy for a there-and-back private cab. Actual day-rental packages booked locally in Goa are often "
    "cheaper (~Rs 2,500-4,000 all day) than two one-way fares &ndash; this is flagged as a potential saving.",
    "<b>Scooter, attractions, food:</b> Not sold on MakeMyTrip; sourced from current (2025-2026) Goa "
    "travel-cost web research and presented as ballpark per-day / per-person ranges, with the midpoint used "
    "in the budget total.",
    "<b>Party size &amp; rooms:</b> Priced throughout for 2 adults sharing 1 hotel room. Costs scale "
    "roughly linearly for flights, cabs (per vehicle, so 2 adults = same cab cost as up to 4) and food, but "
    "hotel and cab costs do NOT double for a larger party in the same room/vehicle &ndash; re-quote for your "
    "actual group size.",
    "<b>Excluded from this budget:</b> Travel insurance, visa/ID fees (not applicable for domestic Indian "
    "travel), alcohol beyond what's bundled into hotel welcome offers, shopping/souvenirs, spa/water-sports "
    "add-ons, and any tips or gratuities.",
    "<b>Tool call budget compliance:</b> This report used exactly 2 flight searches (1 outbound, 1 return, "
    "both via mmt_intercity_options which internally spends one mmt_flight_search call each) and no date- "
    "or airport-sweeping; Goa is treated as GOI (Dabolim) per default MMT convention.",
]
for a in assumptions:
    story.append(Paragraph("&bull; " + a, styles["Body"]))
    story.append(Spacer(1, 3))

story.append(Spacer(1, 8))
story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#CCCCCC")))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "This report was generated by an AI travel-planning assistant using the MakeMyTrip MCP tool suite "
    "(flight search, hotel search/rates, cab quotes, intercity comparison) plus supplementary web research "
    "for on-ground activity costs. It does not constitute a booking, quote, or offer &ndash; verify all "
    "prices directly on MakeMyTrip or with the respective vendor before purchase.",
    styles["FootNote"]))

# ============ BUILD DOCUMENT ============
doc = SimpleDocTemplate(
    "Goa_7Day_Itinerary_Budget_Report.pdf", pagesize=A4,
    leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
    title="Goa 7-Day Itinerary & Budget Report", author="AI Travel Planner (MakeMyTrip MCP)"
)

def first_page(canvas, doc_):
    cover_page(canvas, doc_)
    header_footer(canvas, doc_)

def later_pages(canvas, doc_):
    header_footer(canvas, doc_)

doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)
print("PDF generated: Goa_7Day_Itinerary_Budget_Report.pdf")

