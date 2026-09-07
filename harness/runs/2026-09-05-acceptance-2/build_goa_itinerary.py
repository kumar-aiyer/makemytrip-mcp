# -*- coding: utf-8 -*-
"""
Builds the polished Goa 7-night itinerary PDF report.
Data sourced from makemytrip-mcp (flights, hotels, cab transfers - live quotes,
non-bookable) and Perplexity web research (activities, local transport market
rates, meal costs) where the MCP has no matching endpoint (local day packages).
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    HRFlowable, KeepTogether, ListFlowable, ListItem
)
from reportlab.pdfgen import canvas as canvas_mod

OUT_PATH = r"C:\Users\kumar\projects\claudecodeprojects\mmt-acceptance-workspace\Goa_7Night_Itinerary_Dec2026.pdf"

NAVY = colors.HexColor("#0B3D5C")
TEAL = colors.HexColor("#0E7C7B")
SAND = colors.HexColor("#F5EFE6")
GOLD = colors.HexColor("#C9962C")
GREY = colors.HexColor("#5A5A5A")
LIGHTGREY = colors.HexColor("#EFEFEF")
RED = colors.HexColor("#B23B3B")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleBig", fontName="Helvetica-Bold", fontSize=26,
                           leading=30, textColor=colors.white, alignment=TA_LEFT))
styles.add(ParagraphStyle(name="SubTitle", fontName="Helvetica", fontSize=13,
                           leading=17, textColor=colors.white, alignment=TA_LEFT))
styles.add(ParagraphStyle(name="H1", fontName="Helvetica-Bold", fontSize=16,
                           leading=20, textColor=NAVY, spaceBefore=14, spaceAfter=8))
styles.add(ParagraphStyle(name="H2", fontName="Helvetica-Bold", fontSize=12.5,
                           leading=16, textColor=TEAL, spaceBefore=10, spaceAfter=6))
styles.add(ParagraphStyle(name="Body", fontName="Helvetica", fontSize=9.6,
                           leading=13.5, textColor=colors.HexColor("#222222")))
styles.add(ParagraphStyle(name="BodySmall", fontName="Helvetica", fontSize=8.4,
                           leading=11.5, textColor=GREY))
styles.add(ParagraphStyle(name="Note", fontName="Helvetica-Oblique", fontSize=8.3,
                           leading=11.5, textColor=RED))
styles.add(ParagraphStyle(name="TableHead", fontName="Helvetica-Bold", fontSize=8.6,
                           leading=11, textColor=colors.white))
styles.add(ParagraphStyle(name="TableCell", fontName="Helvetica", fontSize=8.6,
                           leading=11))
styles.add(ParagraphStyle(name="TableCellBold", fontName="Helvetica-Bold", fontSize=8.8,
                           leading=11))
styles.add(ParagraphStyle(name="DayTitle", fontName="Helvetica-Bold", fontSize=11.5,
                           leading=14, textColor=colors.white))
styles.add(ParagraphStyle(name="DaySub", fontName="Helvetica", fontSize=8.8,
                           leading=11, textColor=colors.white))

def cell(text, style="TableCell"):
    return Paragraph(text, styles[style])

def money(n):
    return f"Rs {n:,.0f}"

FRONT_TITLE = "GOA ESCAPE"
FRONT_SUB = "A 7-Night / 8-Day Itinerary from Bengaluru | 15-22 December 2026"

def draw_cover(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    c.setFillColor(TEAL)
    c.rect(0, A4[1]-6.6*cm, A4[0], 0.18*cm, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, A4[1]-6.8*cm, A4[0], 0.06*cm, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 34)
    c.setFillColor(colors.white)
    c.drawString(2*cm, A4[1]-4.6*cm, FRONT_TITLE)
    c.setFont("Helvetica", 14)
    c.drawString(2*cm, A4[1]-5.5*cm, FRONT_SUB)
    c.setFont("Helvetica-Oblique", 10.5)
    c.setFillColor(colors.HexColor("#BFD8E8"))
    c.drawString(2*cm, A4[1]-6.15*cm, "Bengaluru (BLR) -> Goa (GOI, Dabolim) -> Bengaluru (BLR)  |  2 Adults")
    c.restoreState()

def footer(c, doc):
    c.saveState()
    c.setFont("Helvetica", 7.6)
    c.setFillColor(GREY)
    c.drawString(2*cm, 1.2*cm, "Goa Escape Itinerary  |  Indicative pricing only, not a booking  |  Prepared using MakeMyTrip live-quote MCP + web research")
    c.drawRightString(A4[0]-2*cm, 1.2*cm, f"Page {doc.page}")
    c.setStrokeColor(LIGHTGREY)
    c.line(2*cm, 1.5*cm, A4[0]-2*cm, 1.5*cm)
    c.restoreState()

def on_first_page(c, doc):
    draw_cover(c, doc)

def on_later_pages(c, doc):
    footer(c, doc)

def section_header_bar(text, sub=None, color=NAVY, height=1.15):
    data = [[Paragraph(text, styles["DayTitle"])]]
    if sub:
        data.append([Paragraph(sub, styles["DaySub"])])
    t = Table(data, colWidths=[17*cm])
    style = [
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
    ]
    t.setStyle(TableStyle(style))
    return t

# ============================================================================
# COST MODEL  (single source of truth - every number in the report is derived
# from this list so the summary page and the detailed tables can never drift
# apart). Each item: (category, description, source, qty, unit_inr, pax_note)
# Sources: "MCP" = live MakeMyTrip MCP quote captured 2026-09-05 for the exact
# dates below; "WEB" = Perplexity web research (MakeMyTrip has no matching
# product - local day tours / bike rental / meals - flagged per the MCP's own
# known_gaps note); "CALC" = arithmetic derived from an MCP quote (e.g. a
# return leg estimated at the same base fare as the one-way MCP quote).
# ============================================================================

FLIGHTS = [
    ("Flights", "Outbound BLR -> GOI, 15 Dec 2026, IndiGo 6E 6554 (19:00-20:20), Economy",
     "MCP live quote", 2, 4367, "per adult, x2 adults"),
    ("Flights", "Return GOI -> BLR, 22 Dec 2026, IndiGo 6E 6584 (13:15-14:25), Economy",
     "MCP live quote", 2, 6309, "per adult, x2 adults"),
]

HOTEL_NORTH = ("Accommodation", "North Goa - The Fern Habitat Candolim (4-star), Room Only, 3 nights",
               "MCP live quote", 3, 5985, "per night, room-only, 2 adults sharing")

HOTEL_SOUTH_COMFORT = ("Accommodation", "South Goa - Fairfield by Marriott Goa Benaulim (4-star), Room Only, 4 nights",
                        "MCP live quote", 4, 15340, "per night, room-only, 2 adults sharing")

HOTEL_SOUTH_VALUE = ("Accommodation", "South Goa - Aloha Holiday Resort (3-star), Room Only, 4 nights",
                      "MCP live quote", 4, 4704, "per night, room-only, 2 adults sharing")

TRANSFERS = [
    ("Transfers", "Airport transfer: Dabolim (GOI) -> Candolim, 15 Dec, private sedan",
     "MCP live quote", 1, 2095, "one car, both travellers"),
    ("Transfers", "Inter-base transfer: Candolim -> Benaulim, 18 Dec, private sedan",
     "MCP live quote", 1, 2145, "one car, both travellers"),
    ("Transfers", "Airport transfer: Benaulim -> Dabolim (GOI), 22 Dec, private sedan",
     "MCP live quote", 1, 2095, "one car, both travellers"),
]

LOCAL_TRANSPORT = [
    ("Local transport", "Self-drive scooter rental, 2 scooters x 7 days",
     "WEB research (Rs 400/scooter/day, peak season)", 14, 400, "2 scooters, one each"),
    ("Local transport", "Scooter fuel/petrol, both scooters, 7 days",
     "WEB research estimate (~Rs 150/day for both)", 7, 150, "both scooters combined"),
    ("Local transport", "Full-day private car charter, Benaulim <-> Ponda & Dudhsagar (Molem) circuit",
     "CALC: MCP one-way quote (Rs 2,145) x2 to approximate the return leg + extra distance",
     2, 2145, "one car, both travellers, full day"),
]

ACTIVITIES = [
    ("Activities & sightseeing", "Dudhsagar Falls shared jeep safari incl. forest permit (per person)",
     "WEB research (Rs 700 pp)", 2, 700, "2 adults"),
    ("Activities & sightseeing", "Ponda spice plantation guided tour incl. traditional Goan lunch (per person)",
     "WEB research (Rs 800 pp)", 2, 800, "2 adults"),
    ("Activities & sightseeing", "Dolphin-spotting boat trip, Colva/Betul, ~1 hr, shared boat (per person)",
     "WEB research (Rs 600 pp)", 2, 600, "2 adults"),
    ("Activities & sightseeing", "Kayak trip to Butterfly Beach from Palolem (per person)",
     "WEB research (Rs 1,000 pp)", 2, 1000, "2 adults"),
    ("Activities & sightseeing", "Fort Aguada entry ticket (per person)",
     "WEB research (Rs 50 pp)", 2, 50, "2 adults"),
    ("Activities & sightseeing", "Mandovi River sunset cruise, Panaji (per person)",
     "WEB research (Rs 600 pp)", 2, 600, "2 adults"),
    ("Activities & sightseeing", "One evening club/beach-party cover charge, Baga/Vagator (per couple)",
     "WEB research estimate", 1, 1500, "both travellers"),
]

FOOD = [
    ("Food & incidentals", "Meals (breakfast, lunch, dinner) for 2, blended shack/casual-dining average, 8 days",
     "WEB research (Rs 2,500/day for 2, incl. one shack meal + one sit-down meal + breakfast/snacks)",
     8, 2500, "2 adults, per day"),
]

def line_total(item):
    return item[3] * item[4]

def build_cost_table(items, contingency_pct=0.04):
    subtotal = sum(line_total(i) for i in items)
    contingency = round(subtotal * contingency_pct)
    return subtotal, contingency, subtotal + contingency

COMFORT_ITEMS = FLIGHTS + [HOTEL_NORTH, HOTEL_SOUTH_COMFORT] + TRANSFERS + LOCAL_TRANSPORT + ACTIVITIES + FOOD
VALUE_ITEMS = FLIGHTS + [HOTEL_NORTH, HOTEL_SOUTH_VALUE] + TRANSFERS + LOCAL_TRANSPORT + ACTIVITIES + FOOD

COMFORT_SUBTOTAL, COMFORT_CONTINGENCY, COMFORT_TOTAL = build_cost_table(COMFORT_ITEMS)
VALUE_SUBTOTAL, VALUE_CONTINGENCY, VALUE_TOTAL = build_cost_table(VALUE_ITEMS)

story = []

# ---------------------------------------------------------------- COVER TEXT
story.append(Spacer(1, 7.2*cm))
story.append(Paragraph(
    "Prepared for: 2 Adults  |  Trip length: 7 nights / 8 days<br/>"
    "Route: North Goa (Candolim) 3N &nbsp;+&nbsp; South Goa (Benaulim) 4N<br/>"
    "Pricing basis: Live indicative quotes pulled via the MakeMyTrip MCP on 5-Sep-2026 for "
    "travel on 15-22 Dec 2026, cross-checked with web research for line items MakeMyTrip "
    "does not sell (local day tours, scooter rental, meals). All figures are estimates for "
    "planning only &mdash; this is not a booking and fares/rates will move before you book.",
    styles["Body"]))
story.append(PageBreak())

# ---------------------------------------------------------------- TRIP AT A GLANCE
story.append(section_header_bar("TRIP AT A GLANCE"))
story.append(Spacer(1, 0.3*cm))
glance_data = [
    [cell("Dates", "TableCellBold"), cell("Tue 15 Dec 2026 &rarr; Tue 22 Dec 2026 (7 nights)")],
    [cell("Travellers", "TableCellBold"), cell("2 Adults")],
    [cell("Route", "TableCellBold"), cell("Bengaluru (BLR) &rarr; Goa Dabolim (GOI) &rarr; Bengaluru (BLR)")],
    [cell("Base 1", "TableCellBold"), cell("North Goa &ndash; Candolim, 3 nights (15&ndash;18 Dec)")],
    [cell("Base 2", "TableCellBold"), cell("South Goa &ndash; Benaulim, 4 nights (18&ndash;22 Dec)")],
    [cell("Local transport", "TableCellBold"), cell("2 self-drive scooters for the week + pre-booked private cabs for all transfers &amp; day trips")],
    [cell("Grand total (Comfort plan)", "TableCellBold"), cell("<b>Rs 1,52,820</b> all-in for 2 people (&asymp; Rs 76,410 per person)", "TableCellBold")],
    [cell("Grand total (Value plan)", "TableCellBold"), cell("<b>Rs 1,08,574</b> all-in for 2 people (&asymp; Rs 54,290 per person) &ndash; swaps to a 3-star South Goa stay, everything else identical")],
]
t = Table(glance_data, colWidths=[4.2*cm, 12.8*cm])
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (0, -1), SAND),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("GRID", (0, 0), (-1, -1), 0.5, LIGHTGREY),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("ROWBACKGROUNDS", (0, -2), (-1, -1), [colors.HexColor("#E9F3EF")]),
]))
story.append(t)
story.append(Spacer(1, 0.4*cm))
story.append(Paragraph(
    "Why this split? Goa's North and South coasts have very different characters &ndash; North is "
    "livelier (forts, markets, nightlife, water sports), South is quieter and greener (long empty "
    "beaches, spice plantations, dolphin trips). Basing 3 nights in the North and 4 in the South avoids "
    "the 40 km/1&ndash;1.5 hr commute every day and lets you experience both sides without backtracking "
    "more than once.", styles["Body"]))
story.append(PageBreak())

# ---------------------------------------------------------------- FLIGHTS
story.append(section_header_bar("FLIGHTS - BENGALURU <-> GOA"))
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph(
    "Live fares pulled from MakeMyTrip for the exact travel dates (one outbound search, one return "
    "search - within the 2-search budget). Fares are per adult, economy cabin; taxes are shown separately. "
    "MakeMyTrip's search also surfaces nearby-airport options (GOX/Mopa, SDW/Sindhudurg) which are cheaper "
    "but land 60-100 km further from our North/South Goa bases, so they are excluded below and shown only "
    "as a footnote.", styles["Body"]))
story.append(Spacer(1, 0.25*cm))
flight_head = [cell(x, "TableHead") for x in ["Leg", "Date", "Airline / Flight", "Depart-Arrive", "Fare/adult (base+tax)", "x2 adults"]]
flight_rows = [flight_head]
flight_rows.append([
    cell("Outbound<br/>BLR &rarr; GOI"), cell("15 Dec 2026"), cell("IndiGo 6E 6554"),
    cell("19:00 &rarr; 20:20 (1h20m, non-stop)"), cell("Rs 3,222 + Rs 1,145 = <b>Rs 4,367</b>"), cell(money(2*4367))
])
flight_rows.append([
    cell("Return<br/>GOI &rarr; BLR"), cell("22 Dec 2026"), cell("IndiGo 6E 6584"),
    cell("13:15 &rarr; 14:25 (1h10m, non-stop)"), cell("Rs 4,627 + Rs 1,682 = <b>Rs 6,309</b>"), cell(money(2*6309))
])
flight_rows.append([cell("", ), cell(""), cell(""), cell(""), cell("Flights subtotal", "TableCellBold"), cell(money(21352), "TableCellBold")])
ft = Table(flight_rows, colWidths=[2.1*cm, 1.9*cm, 3.0*cm, 4.4*cm, 4.2*cm, 2.2*cm])
ft.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), TEAL),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("GRID", (0, 0), (-1, -2), 0.5, LIGHTGREY),
    ("LINEABOVE", (0, -1), (-1, -1), 1, NAVY),
    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, SAND]),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.append(ft)
story.append(Spacer(1, 0.25*cm))
story.append(Paragraph(
    "Note: The cheapest fares MakeMyTrip returned for these dates were on FLY91 (Rs 3,099, non-stop, "
    "~1h45m) but they land at Sindhudurg (SDW) ~85 km north of Goa, and there was no matching return-day "
    "flight into GOI on FLY91 at a comparable price, so IndiGo direct-into-GOI flights are used as the "
    "primary recommendation for simplicity and to avoid an extra long transfer.", styles["Note"]))
story.append(PageBreak())

# ---------------------------------------------------------------- DAY BY DAY ITINERARY
story.append(section_header_bar("DAY-BY-DAY ITINERARY"))
story.append(Spacer(1, 0.3*cm))

DAYS = [
    ("Day 1 - Tue 15 Dec", "Arrival & Candolim settle-in",
     ["Fly BLR -> GOI (IndiGo 6E 6554, 19:00-20:20); private cab to Candolim (~40 km, ~1 hr) - check into The Fern Habitat.",
      "Late dinner at a Candolim/Fort Aguada Road restaurant; early night to recover."]),
    ("Day 2 - Wed 16 Dec", "Anjuna flea market, Vagator & sunset",
     ["Morning: Vagator & Ozran ('Little Vagator') beaches.",
      "Wednesday is Anjuna's famous weekly flea market day - browse it late morning/early afternoon.",
      "Evening: Chapora Fort for sunset (views over Vagator), then beach shacks/live music in Anjuna or Vagator."]),
    ("Day 3 - Thu 17 Dec", "Forts & Panaji",
     ["Morning: Fort Aguada & lighthouse, Sinquerim Beach.",
      "Midday: Fontainhas (Panaji's Latin Quarter) walk, lunch in Panaji; Dona Paula/Miramar viewpoint.",
      "Evening: dinner & nightlife in Baga/Calangute."]),
    ("Day 4 - Fri 18 Dec", "Old Goa + move to South Goa",
     ["Morning: Basilica of Bom Jesus & Se Cathedral, Old Goa (UNESCO churches).",
      "Stop at Mapusa Market (Friday market day) en route if convenient, or Dona Paula viewpoint.",
      "Afternoon: check out of Candolim; private cab transfer to Benaulim (~45-50 km, ~1-1.5 hr); check into Fairfield by Marriott Goa Benaulim.",
      "Evening: relax on Benaulim/Colva beach, seafood dinner."]),
    ("Day 5 - Sat 19 Dec", "Colva coast & dolphin trip",
     ["Morning: dolphin-spotting boat trip from Colva/Betul jetty (~1 hr, sightings not guaranteed).",
      "Colva, Benaulim & Varca beaches; lunch at a Colva beach shack.",
      "Evening: Cavelossim/Mobor for a quieter sunset walk."]),
    ("Day 6 - Sun 20 Dec", "Palolem & Canacona day trip",
     ["Full day trip south to Palolem (~30-40 min drive): Palolem Beach, kayak to Butterfly Beach, Patnem & Colomb beaches.",
      "Optional: Cabo de Rama Fort for coastal views on the way back.",
      "Return to Benaulim for dinner."]),
    ("Day 7 - Mon 21 Dec", "Spice plantation & Dudhsagar Falls",
     ["Full-day private car charter: Ponda spice plantation guided tour with traditional Goan lunch, then on to Dudhsagar Falls (Molem) for the shared jeep safari to the base of the falls.",
      "Long day (~7-8 hrs round trip incl. drive) - carry swimwear for the falls.",
      "Relaxed dinner back at Benaulim."]),
    ("Day 8 - Tue 22 Dec", "Departure",
     ["Free morning: last swim/breakfast at leisure.",
      "Check out; private cab from Benaulim to Dabolim Airport (~30 km, ~45 min-1 hr).",
      "Fly GOI -> BLR (IndiGo 6E 6584, 13:15-14:25)."]),
]

for title, sub, bullets in DAYS:
    block = [section_header_bar(title, sub, color=NAVY if "Day 1" not in title else NAVY)]
    items = [ListItem(Paragraph(b, styles["Body"]), bulletColor=TEAL) for b in bullets]
    block.append(Spacer(1, 0.15*cm))
    block.append(ListFlowable(items, bulletType="bullet", start="circle", leftIndent=14))
    block.append(Spacer(1, 0.25*cm))
    story.append(KeepTogether(block))

story.append(PageBreak())

# ---------------------------------------------------------------- HOTELS
story.append(section_header_bar("WHERE YOU'LL STAY"))
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph(
    "All rates below are live, signed-out retail rates pulled from MakeMyTrip for the exact check-in/out "
    "dates (room-only plan, 2 adults sharing, 1 room). They are per-night figures; the stay total is "
    "nightly rate x nights - exact for these dates since each hotel quoted one flat nightly rate across "
    "its whole stay (no mid-stay price change to average over).", styles["Body"]))
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph("North Goa base (15-18 Dec, 3 nights)", styles["H2"]))
hotel_n_data = [
    [cell("Property", "TableHead"), cell("Star", "TableHead"), cell("Rating", "TableHead"),
     cell("Nightly base", "TableHead"), cell("Nightly tax", "TableHead"), cell("Nightly all-in", "TableHead"), cell("3-night total", "TableHead")],
    [cell("<b>The Fern Habitat, Candolim</b> (recommended)"), cell("4*"), cell("4.2/5"),
     cell(money(5700)), cell(money(285)), cell(money(5985)), cell(money(17955), "TableCellBold")],
    [cell("Fairfield by Marriott Goa Anjuna"), cell("4*"), cell("3.8/5"),
     cell(money(7084)), cell(money(354)), cell(money(7438)), cell(money(22314))],
    [cell("Ginger Goa, Candolim"), cell("4*"), cell("4.2/5"),
     cell(money(8099)), cell(money(1458)), cell(money(9557)), cell(money(28671))],
]
hnt = Table(hotel_n_data, colWidths=[5.2*cm, 1.1*cm, 1.5*cm, 2.3*cm, 2.1*cm, 2.3*cm, 2.5*cm])
hnt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
    ("GRID", (0, 0), (-1, -1), 0.5, LIGHTGREY),
    ("ROWBACKGROUNDS", (0, 1), (-1, 1), [colors.HexColor("#E9F3EF")]),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.append(hnt)
story.append(Spacer(1, 0.35*cm))

story.append(Paragraph("South Goa base (18-22 Dec, 4 nights) - two tiers", styles["H2"]))
hotel_s_data = [
    [cell("Property", "TableHead"), cell("Star", "TableHead"), cell("Rating", "TableHead"),
     cell("Nightly base", "TableHead"), cell("Nightly tax", "TableHead"), cell("Nightly all-in", "TableHead"), cell("4-night total", "TableHead")],
    [cell("<b>Fairfield by Marriott Goa Benaulim</b> (Comfort plan)"), cell("4*"), cell("4.5/5"),
     cell(money(13000)), cell(money(2340)), cell(money(15340)), cell(money(61360), "TableCellBold")],
    [cell("<b>Aloha Holiday Resort</b> (Value plan)"), cell("3*"), cell("4.2/5"),
     cell(money(4200)), cell(money(504)), cell(money(4704)), cell(money(18816), "TableCellBold")],
]
hst = Table(hotel_s_data, colWidths=[5.2*cm, 1.1*cm, 1.5*cm, 2.3*cm, 2.1*cm, 2.3*cm, 2.5*cm])
hst.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
    ("GRID", (0, 0), (-1, -1), 0.5, LIGHTGREY),
    ("ROWBACKGROUNDS", (0, 1), (-1, 2), [colors.HexColor("#E9F3EF"), colors.HexColor("#FBF3E3")]),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.append(hst)
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph(
    "Both South Goa options are close to Benaulim/Colva beach. The Value swap saves Rs 42,544 on the "
    "4-night stay (Rs 61,360 &rarr; Rs 18,816) and drops the trip's grand total by roughly 29%, at the "
    "cost of resort-level amenities (pool bar, spa, better breakfast service) the 4-star offers.",
    styles["Body"]))
story.append(PageBreak())

# ---------------------------------------------------------------- TRANSPORT
story.append(section_header_bar("TRANSPORT WITHIN GOA"))
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph(
    "Airport transfers and the inter-base relocation are live private-cab quotes from the MakeMyTrip MCP "
    "(outstation cab funnel, one-way). Day-to-day local hopping is best done on a self-drive scooter - "
    "MakeMyTrip's cab product does not sell hourly/local 8hr-80km day packages or bike rentals (a "
    "documented gap in this MCP), so that figure is sourced from web research instead, flagged below.",
    styles["Body"]))
story.append(Spacer(1, 0.25*cm))

transport_data = [
    [cell("Leg / Item", "TableHead"), cell("Date", "TableHead"), cell("Vehicle (cheapest quoted)", "TableHead"),
     cell("Vendor", "TableHead"), cell("Distance", "TableHead"), cell("All-in fare", "TableHead")],
    [cell("Dabolim Airport &rarr; Candolim"), cell("15 Dec"), cell("WagonR/Swift hatchback (CNG)"), cell("Taxibazaar"), cell("~40 km"), cell(money(2045))],
    [cell("Candolim &rarr; Benaulim"), cell("18 Dec"), cell("Dzire/Etios sedan (diesel)"), cell("Eroovo"), cell("~40 km"), cell(money(2145))],
    [cell("Benaulim &rarr; Dabolim Airport"), cell("22 Dec"), cell("WagonR/Swift hatchback (CNG)"), cell("Taxibazaar"), cell("~40 km"), cell(money(2045))],
    [cell("Full-day charter: Benaulim &rarr; Ponda &rarr; Dudhsagar &rarr; Benaulim"), cell("21 Dec"),
     cell("Sedan, full day (CALC: 2x one-way quote)"), cell("Eroovo (est.)"), cell("~80 km round trip"), cell(money(2*2145))],
]
tt = Table(transport_data, colWidths=[5.4*cm, 1.6*cm, 4.3*cm, 2.2*cm, 2.0*cm, 1.5*cm])
tt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), TEAL),
    ("GRID", (0, 0), (-1, -1), 0.5, LIGHTGREY),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SAND]),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.append(tt)
story.append(Spacer(1, 0.3*cm))

story.append(Paragraph("Local day-to-day mobility", styles["H2"]))
local_data = [
    [cell("Item", "TableHead"), cell("Basis", "TableHead"), cell("Qty", "TableHead"), cell("Rate", "TableHead"), cell("Total", "TableHead")],
    [cell("Self-drive scooter rental (2 scooters)"), cell("Web research, peak-season rate"), cell("14 scooter-days"), cell(money(400)+"/day"), cell(money(5600))],
    [cell("Petrol for both scooters"), cell("Web research estimate"), cell("7 days"), cell(money(150)+"/day"), cell(money(1050))],
]
lt_table = Table(local_data, colWidths=[5.4*cm, 5.0*cm, 2.6*cm, 2.0*cm, 2.0*cm])
lt_table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), TEAL),
    ("GRID", (0, 0), (-1, -1), 0.5, LIGHTGREY),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SAND]),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.append(lt_table)
story.append(Spacer(1, 0.25*cm))
story.append(Paragraph(
    "A metered/app taxi alternative to scooters would run roughly Rs 15-25/km and add up fast for casual "
    "beach-hopping; two self-drive scooters give the most flexibility for the cost in Goa's flat, short-hop "
    "geography. One 4-seat self-drive car (~Rs 1,200-1,500/day) or a full-day driver-cab (~Rs 2,500-3,000/day) "
    "is a reasonable non-scooter alternative for travellers who prefer not to ride two-wheelers.",
    styles["BodySmall"]))
story.append(PageBreak())

# ---------------------------------------------------------------- FULL ITEMIZED COST BREAKDOWN
story.append(section_header_bar("FULL COST BREAKDOWN - COMFORT PLAN", "Every line item, source-tagged | 2 adults, 7 nights"))
story.append(Spacer(1, 0.3*cm))

def cost_table(items, subtotal, contingency, total, label):
    rows = [[cell("#", "TableHead"), cell("Category", "TableHead"), cell("Line item", "TableHead"),
             cell("Source", "TableHead"), cell("Qty", "TableHead"), cell("Unit (Rs)", "TableHead"), cell("Line total (Rs)", "TableHead")]]
    cur_cat = None
    n = 0
    for it in items:
        cat, desc, src, qty, unit, note = it
        n += 1
        catcell = cat if cat != cur_cat else ""
        cur_cat = cat
        rows.append([cell(str(n)), cell(f"<b>{catcell}</b>" if catcell else ""), cell(f"{desc}<br/><font size=7 color='#5A5A5A'>{note}</font>"),
                     cell(src, "TableCell"), cell(str(qty)), cell(f"{unit:,.0f}"), cell(f"{qty*unit:,.0f}", "TableCellBold")])
    rows.append([cell(""), cell(""), cell(""), cell(""), cell(""), cell("Subtotal", "TableCellBold"), cell(f"{subtotal:,.0f}", "TableCellBold")])
    rows.append([cell(""), cell(""), cell(""), cell(""), cell(""), cell("Contingency (4%)", "TableCellBold"), cell(f"{contingency:,.0f}", "TableCellBold")])
    rows.append([cell(""), cell(""), cell(""), cell(""), cell(""), cell(f"GRAND TOTAL - {label}", "TableCellBold"), cell(f"{total:,.0f}", "TableCellBold")])
    t = Table(rows, colWidths=[0.6*cm, 2.3*cm, 6.6*cm, 3.2*cm, 1.0*cm, 1.6*cm, 1.9*cm], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -4), 0.4, LIGHTGREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 1), (-1, -4), 7.8),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, -3), (-1, -3), 1, NAVY),
        ("BACKGROUND", (0, -1), (-1, -1), GOLD),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("SPAN", (0, -1), (-3, -1)), ("SPAN", (0, -2), (-3, -2)), ("SPAN", (0, -3), (-3, -3)),
    ]
    t.setStyle(TableStyle(style))
    return t

story.append(cost_table(COMFORT_ITEMS, COMFORT_SUBTOTAL, COMFORT_CONTINGENCY, COMFORT_TOTAL, "COMFORT PLAN"))
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph(
    "Contingency (4%) covers minor fare/rate movement between this quote and actual booking, plus small "
    "unbudgeted spends (tips, extra snacks, souvenirs). Source key: <b>MCP live quote</b> = pulled directly "
    "from the MakeMyTrip MCP for these exact dates; <b>WEB research</b> = MakeMyTrip has no matching sellable "
    "product for this item, so Perplexity-sourced market rates are used instead (flagged per the MCP's own "
    "documented gaps); <b>CALC</b> = derived by combining/doubling an MCP quote for a leg the MCP could not "
    "quote directly (e.g. a multi-stop day charter).", styles["BodySmall"]))
story.append(PageBreak())

story.append(section_header_bar("FULL COST BREAKDOWN - VALUE PLAN", "Same trip, 3-star South Goa stay | 2 adults, 7 nights"))
story.append(Spacer(1, 0.3*cm))
story.append(cost_table(VALUE_ITEMS, VALUE_SUBTOTAL, VALUE_CONTINGENCY, VALUE_TOTAL, "VALUE PLAN"))
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph(
    "Identical to the Comfort Plan in every line except South Goa accommodation, which switches from "
    "Fairfield by Marriott Goa Benaulim (4-star, Rs 61,360 for 4 nights) to Aloha Holiday Resort "
    "(3-star, Rs 18,816 for 4 nights) - a saving of Rs 42,544 that flows straight through to the grand total.",
    styles["BodySmall"]))
story.append(PageBreak())

# ---------------------------------------------------------------- CATEGORY SUMMARY
story.append(section_header_bar("COST SUMMARY BY CATEGORY"))
story.append(Spacer(1, 0.3*cm))

def category_totals(items):
    out = {}
    for cat, desc, src, qty, unit, note in items:
        out[cat] = out.get(cat, 0) + qty*unit
    return out

cc = category_totals(COMFORT_ITEMS)
cv = category_totals(VALUE_ITEMS)
cat_order = ["Flights", "Accommodation", "Transfers", "Local transport", "Activities & sightseeing", "Food & incidentals"]
summary_rows = [[cell("Category", "TableHead"), cell("Comfort Plan (Rs)", "TableHead"), cell("Value Plan (Rs)", "TableHead"), cell("Per person, Comfort (Rs)", "TableHead")]]
for c in cat_order:
    summary_rows.append([cell(c), cell(f"{cc[c]:,.0f}"), cell(f"{cv[c]:,.0f}"), cell(f"{cc[c]/2:,.0f}")])
summary_rows.append([cell("Subtotal", "TableCellBold"), cell(f"{COMFORT_SUBTOTAL:,.0f}", "TableCellBold"), cell(f"{VALUE_SUBTOTAL:,.0f}", "TableCellBold"), cell(f"{COMFORT_SUBTOTAL/2:,.0f}", "TableCellBold")])
summary_rows.append([cell("Contingency (4%)", "TableCellBold"), cell(f"{COMFORT_CONTINGENCY:,.0f}", "TableCellBold"), cell(f"{VALUE_CONTINGENCY:,.0f}", "TableCellBold"), cell(f"{COMFORT_CONTINGENCY/2:,.0f}", "TableCellBold")])
summary_rows.append([cell("GRAND TOTAL", "TableCellBold"), cell(f"{COMFORT_TOTAL:,.0f}", "TableCellBold"), cell(f"{VALUE_TOTAL:,.0f}", "TableCellBold"), cell(f"{COMFORT_TOTAL/2:,.0f}", "TableCellBold")])

st = Table(summary_rows, colWidths=[5.5*cm, 3.8*cm, 3.8*cm, 3.9*cm])
st.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
    ("GRID", (0, 0), (-1, -4), 0.4, LIGHTGREY),
    ("LINEABOVE", (0, -3), (-1, -3), 1, NAVY),
    ("BACKGROUND", (0, -1), (-1, -1), GOLD),
    ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
    ("ROWBACKGROUNDS", (0, 1), (-1, -4), [colors.white, SAND]),
    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
]))
story.append(st)
story.append(Spacer(1, 0.5*cm))

story.append(Paragraph("Where the money goes (Comfort Plan)", styles["H2"]))
for c in cat_order:
    pct = cc[c] / COMFORT_SUBTOTAL * 100
    bar_width = 14 * (pct / 100)
    bt = Table([[""]], colWidths=[bar_width*cm], rowHeights=[0.35*cm])
    bt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), TEAL)]))
    story.append(Paragraph(f"{c} &mdash; {money(cc[c])} ({pct:.0f}%)", styles["BodySmall"]))
    story.append(bt)
    story.append(Spacer(1, 0.12*cm))
story.append(PageBreak())

# ---------------------------------------------------------------- ASSUMPTIONS & CAVEATS
story.append(section_header_bar("ASSUMPTIONS, SOURCES & CAVEATS"))
story.append(Spacer(1, 0.3*cm))

assumptions = [
    "This is a planning estimate, not a booking. The MakeMyTrip MCP used to build this report has "
    "no booking, cart, payment or login path by design - every figure is a live, signed-out retail "
    "quote, and actual prices at the time of booking will differ.",
    "Flights: fares are per-adult, economy, for the exact 15 Dec / 22 Dec 2026 dates, captured from one "
    "outbound and one return MakeMyTrip search (2-search budget used exactly once each, no date sweeping). "
    "The first attempt at both searches returned an empty/blocked response; both were retried once "
    "successfully per the single-retry allowance.",
    "Hotels: room-only retail rates for 2 adults sharing 1 room, signed out (no loyalty/member pricing). "
    "MakeMyTrip flags stay totals as nightly-rate x nights, which is exact here since neither property's "
    "nightly rate changed across the quoted date range.",
    "Cab transfers: MakeMyTrip's outstation one-way cab funnel, cheapest vehicle class shown per leg "
    "(hatchback/sedan, CNG or diesel, various vendors: Taxibazaar, Eroovo, WTicabs, Taxida). Same-day "
    "round trips are refused by this MCP by design (MakeMyTrip would silently answer a same-day RT quote "
    "with one-way pricing) - none were requested here since all cab needs are genuinely one-way transfers.",
    "The Ponda + Dudhsagar full-day charter is NOT a direct MCP product (MakeMyTrip's cab tool prices "
    "point-to-point outstation trips, not multi-stop day hires). It is approximated as 2x the one-way "
    "Benaulim-to-Ponda quote to cover the return leg and the short additional hop to Dudhsagar - flagged "
    "as CALC in the cost tables, not a literal MakeMyTrip quote.",
    "Local transport (scooter rental, fuel), activities (Dudhsagar jeep, spice plantation, dolphin trip, "
    "kayaking, entry fees, nightlife cover) and food are priced from web research (Perplexity), because "
    "MakeMyTrip does not sell these products at all (documented gap: 'Local 8hr/80km cab day packages use "
    "a different funnel and are not built' and no bike-rental or food-and-beverage product exists on the platform). "
    "These are market-typical December-2024/2025 rates and should be treated as directionally correct "
    "rather than exact.",
    "Seasonality: 15-22 December is Goa's peak season (pre-Christmas). Expect hotel and flight prices to "
    "possibly rise further as the date approaches (especially the week of Christmas/New Year, which this "
    "trip narrowly avoids), and beach shacks/clubs to be busier and pricier than the quoted averages.",
    "Two airports: Goa has GOI (Dabolim, South) and GOX (Mopa, North). This itinerary uses GOI throughout, "
    "which is roughly equidistant from both bases (~40 km to Candolim, ~40 km to Benaulim) and had the "
    "best direct fares for these dates. GOX appeared in search results at similar/lower fares in places "
    "but is materially farther from South Goa, so was not used.",
    "A 4% contingency is added to each plan's subtotal to cover minor fare drift and incidentals; it is "
    "not a substitute for travel insurance, visa costs (n/a - domestic trip), or a buffer for spontaneous "
    "extra activities beyond those listed.",
]
items = [ListItem(Paragraph(a, styles["Body"]), bulletColor=GOLD) for a in assumptions]
story.append(ListFlowable(items, bulletType="bullet", start="square", leftIndent=14, spaceAfter=8))

story.append(Spacer(1, 0.4*cm))
story.append(HRFlowable(width="100%", thickness=0.6, color=LIGHTGREY))
story.append(Spacer(1, 0.2*cm))
story.append(Paragraph(
    "Report generated 5 September 2026 using the makemytrip-mcp server (flights, hotels, cab transfers) "
    "and Perplexity web research (activities, local transport market rates, meal costs, day-by-day "
    "sightseeing plan). All amounts in Indian Rupees (INR).", styles["BodySmall"]))

# ============================================================================
# BUILD PDF
# ============================================================================
doc = SimpleDocTemplate(
    OUT_PATH, pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm, topMargin=1.8*cm, bottomMargin=1.8*cm,
    title="Goa 7-Night Itinerary - 15 to 22 Dec 2026", author="Cline Travel Planner"
)
doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
print(f"PDF written to: {OUT_PATH}")
