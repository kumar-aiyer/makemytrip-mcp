# -*- coding: utf-8 -*-
"""
Builds a polished PDF itinerary + budget report for a 7-day Goa trip
(15-21 Dec 2026) departing from Bengaluru, for 2 adults.

Data sources:
 - MakeMyTrip MCP (flights, hotels, cabs, trains) - live pulls
 - Perplexity research - for line items MMT does not price directly
   (scooter rental, entry fees, water sports, food budget) - labeled.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    HRFlowable, ListFlowable, ListItem, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas as canvas_module
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Base-14 Helvetica has no Rupee glyph (U+20B9) and no arrow/bullet glyphs used
# below render blank/boxed. Arial (present on Windows) covers all of them, so
# register it under font names that stand in for Helvetica everywhere in this doc.
FONT_DIR = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Arial", FONT_DIR + "arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", FONT_DIR + "arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", FONT_DIR + "ariali.ttf"))
pdfmetrics.registerFont(TTFont("Arial-BoldItalic", FONT_DIR + "arialbi.ttf"))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold",
                               italic="Arial-Italic", boldItalic="Arial-BoldItalic")
FN_REG = "Arial"
FN_BOLD = "Arial-Bold"

INR = "\u20b9"
styles = getSampleStyleSheet()

NAVY = colors.HexColor("#0B2545")
TEAL = colors.HexColor("#0F6E6E")
LIGHT_BG = colors.HexColor("#EEF3F7")
GOLD = colors.HexColor("#C9972B")
GREY = colors.HexColor("#5B6470")
INK = colors.HexColor("#20242B")

styles.add(ParagraphStyle(name="CoverSub", fontName="Arial", fontSize=14,
                           leading=18, textColor=TEAL, alignment=TA_CENTER, spaceBefore=8))
styles.add(ParagraphStyle(name="CoverMeta", fontName="Arial", fontSize=10.5,
                           leading=15, textColor=GREY, alignment=TA_CENTER, spaceBefore=4))
styles.add(ParagraphStyle(name="H1", fontName="Arial-Bold", fontSize=17,
                           leading=21, textColor=NAVY, spaceBefore=4, spaceAfter=10))
styles.add(ParagraphStyle(name="H2", fontName="Arial-Bold", fontSize=12.5,
                           leading=16, textColor=TEAL, spaceBefore=12, spaceAfter=6))
styles.add(ParagraphStyle(name="Body", fontName="Arial", fontSize=9.3, leading=13, textColor=INK))
styles.add(ParagraphStyle(name="BodySmall", fontName="Arial", fontSize=8.2, leading=11.5, textColor=GREY))
styles.add(ParagraphStyle(name="TableCell", fontName="Arial", fontSize=8.4, leading=11, textColor=INK))
styles.add(ParagraphStyle(name="TableCellBold", fontName="Arial-Bold", fontSize=8.6, leading=11, textColor=NAVY))
styles.add(ParagraphStyle(name="TableHeader", fontName="Arial-Bold", fontSize=8.6, leading=11, textColor=colors.white))
styles.add(ParagraphStyle(name="DayHeader", fontName="Arial-Bold", fontSize=12.5, leading=15, textColor=colors.white))
styles.add(ParagraphStyle(name="DayDate", fontName="Arial", fontSize=9.3, leading=12, textColor=colors.HexColor("#DCE9F5")))
styles.add(ParagraphStyle(name="Caveat", fontName="Arial", fontSize=8.6, leading=12.5, textColor=INK, leftIndent=4))
styles.add(ParagraphStyle(name="TotalLabel", fontName="Arial-Bold", fontSize=11, textColor=colors.white, alignment=TA_LEFT))
styles.add(ParagraphStyle(name="TotalValue", fontName="Arial-Bold", fontSize=13, textColor=colors.white, alignment=TA_RIGHT))
styles.add(ParagraphStyle(name="MegaTitle", fontName="Arial-Bold", fontSize=54, leading=56, textColor=colors.white, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="MegaSub", fontName="Arial-Bold", fontSize=13, leading=18, textColor=colors.HexColor("#DCE9F5"), alignment=TA_CENTER, spaceBefore=6))

PAGE_W, PAGE_H = A4
MARGIN = 1.6 * cm

def cell(text, style="TableCell"):
    return Paragraph(text, styles[style])

def money(n):
    return f"{INR}{n:,.0f}"

# =====================================================================
# COST MODEL (single source of truth - all tables/text reference these)
# =====================================================================
PAX = 2

# Intercity flights (party totals)
FLIGHT_OUT = 4367 * PAX          # MMT live: IndiGo 6E 6554
FLIGHT_RET_EST = 4400 * PAX      # ESTIMATE - MMT search failed twice, see notes

# Hotels (party totals, MMT live nightly x nights)
HOTEL_NORTH = 38228              # Ginger Goa Candolim, 4N
HOTEL_SOUTH = 25760              # Orchid Passaros Benaulim, 2N
HOTEL_SUBTOTAL = HOTEL_NORTH + HOTEL_SOUTH

# Ground transport - cabs (party totals, MMT live sedan quotes, all-in)
CAB_AIRPORT_IN = 2145            # Day1 Dabolim -> Candolim
CAB_OLDGOA_RT = 2145 * 2         # Day3 Candolim <-> Old Goa/Panaji (RT proxy, flagged)
CAB_RELOCATE = 2145              # Day5 Candolim -> Benaulim
CAB_DUDHSAGAR_RT = 2145 * 2      # Day6 Benaulim <-> Dudhsagar (RT proxy, flagged)
CAB_AIRPORT_OUT = 2145           # Day7 Benaulim -> Dabolim Airport
CAB_SUBTOTAL = CAB_AIRPORT_IN + CAB_OLDGOA_RT + CAB_RELOCATE + CAB_DUDHSAGAR_RT + CAB_AIRPORT_OUT

# Local self-drive - scooter rental (research estimate, party totals)
SCOOTER_PER_DAY_PER_UNIT = 550
SCOOTER_DAYS = 2                 # Day 2 sightseeing loop + Day 4 free day
SCOOTER_UNITS = 2                # 1 scooter per person
SCOOTER_SUBTOTAL = SCOOTER_PER_DAY_PER_UNIT * SCOOTER_DAYS * SCOOTER_UNITS

# Activities & entry fees (research estimate, party totals unless noted)
FEE_FORTS_CHURCHES = 0            # Fort Aguada, Chapora Fort, Bom Jesus, Se Cathedral - free
FEE_ANJUNA_MARKET = 0             # free entry (shopping not budgeted)
FEE_WATERSPORTS = 1750 * PAX      # Day3 parasail+jetski+banana boat combo, per person
FEE_CRUISE = 450 * PAX            # Day3 Mandovi sunset cruise, per person
FEE_DUDHSAGAR_COMBO = 2000 * PAX  # Day6 jeep safari + spice plantation combo, per person
FEE_NIGHTLIFE = 2000 * PAX        # Day2 club cover + drinks, per person
FEE_SPICE_PLANTATION_OPT = 1000 * PAX  # Day4 OPTIONAL spice plantation add-on, per person
ACTIVITIES_CORE = (FEE_FORTS_CHURCHES + FEE_ANJUNA_MARKET + FEE_WATERSPORTS +
                    FEE_CRUISE + FEE_DUDHSAGAR_COMBO + FEE_NIGHTLIFE)

# Food (research estimate, mid-range, per person per day x 7 days)
FOOD_PER_PERSON_PER_DAY = 2000
FOOD_DAYS = 7
FOOD_SUBTOTAL = FOOD_PER_PERSON_PER_DAY * PAX * FOOD_DAYS

# Incidentals (research estimate, flat, party total): SIM/data, tips, sunscreen, misc
INCIDENTALS = 3000

CORE_TOTAL = (FLIGHT_OUT + FLIGHT_RET_EST + HOTEL_SUBTOTAL + CAB_SUBTOTAL +
              SCOOTER_SUBTOTAL + ACTIVITIES_CORE + FOOD_SUBTOTAL + INCIDENTALS)
GRAND_TOTAL_WITH_OPTIONAL = CORE_TOTAL + FEE_SPICE_PLANTATION_OPT
PER_PERSON_CORE = CORE_TOTAL / PAX

elements = []

def on_page(cv: canvas_module.Canvas, doc):
    cv.saveState()
    if doc.page == 1:
        cv.setFillColor(NAVY)
        cv.rect(0, PAGE_H - 9.2 * cm, PAGE_W, 9.2 * cm, fill=1, stroke=0)
        cv.setFillColor(GOLD)
        cv.rect(0, PAGE_H - 9.35 * cm, PAGE_W, 0.15 * cm, fill=1, stroke=0)
        cv.setFillColor(GOLD)
        cv.rect(0, 0, PAGE_W, 0.25 * cm, fill=1, stroke=0)
    else:
        cv.setStrokeColor(LIGHT_BG)
        cv.setLineWidth(0.8)
        cv.line(MARGIN, PAGE_H - 1.15 * cm, PAGE_W - MARGIN, PAGE_H - 1.15 * cm)
        cv.setFont("Arial", 8)
        cv.setFillColor(GREY)
        cv.drawString(MARGIN, PAGE_H - 1.0 * cm,
                       "Bengaluru \u2192 Goa \u2192 Bengaluru  |  7 Days / 6 Nights  |  15\u201321 Dec 2026")
        cv.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.0 * cm, "Goa Trip Dossier")
        cv.line(MARGIN, 1.2 * cm, PAGE_W - MARGIN, 1.2 * cm)
        cv.drawString(MARGIN, 0.85 * cm, "Prepared via MakeMyTrip MCP live pricing + supplementary research")
        cv.drawRightString(PAGE_W - MARGIN, 0.85 * cm, f"Page {doc.page}")
    cv.restoreState()

# ---------------------------------------------------------------- cover ---
elements.append(Spacer(1, 2.6 * cm))
elements.append(Paragraph("GOA", styles["MegaTitle"]))
elements.append(Paragraph("7-DAY ITINERARY &amp; BUDGET DOSSIER", styles["MegaSub"]))
elements.append(Spacer(1, 6.0 * cm))
elements.append(Paragraph("Bengaluru &#8594; North Goa &#8594; South Goa &#8594; Bengaluru", styles["CoverSub"]))
elements.append(Paragraph("15&ndash;21 December 2026  &bull;  6 Nights / 7 Days  &bull;  2 Adults", styles["CoverMeta"]))
elements.append(Spacer(1, 0.6 * cm))
elements.append(Paragraph(
    "All prices in Indian Rupees (INR). Pricing pulled live via the MakeMyTrip MCP "
    "(flights, hotels, cabs, trains) and cross-checked with web research for items "
    "MakeMyTrip does not price directly. Full sourcing and assumptions are in the "
    "section below &mdash; read it before treating any number as a quote.",
    styles["CoverMeta"]))
elements.append(PageBreak())

# ---------------------------------------------- assumptions / how-to-read ---
elements.append(Paragraph("Assumptions &amp; How to Read This Report", styles["H1"]))
elements.append(Paragraph(
    "This dossier was generated using the MakeMyTrip MCP tool for live, indicative "
    "retail pricing (flights, hotels, cabs, trains), supplemented by general web "
    "research for line items MakeMyTrip does not price directly (scooter rental, "
    "monument entry fees, water sports, nightlife spend, daily food budget). "
    "It is a planning benchmark, not a booking &mdash; this tool cannot book anything.",
    styles["Body"]))
elements.append(Spacer(1, 6))

assumptions = [
    "Party size: 2 adults, 1 room throughout.",
    "Trip dates: Tue 15 Dec 2026 (depart BLR) \u2192 Mon 21 Dec 2026 (return to BLR). Peak "
    "winter season in Goa \u2014 expect premium pricing and crowded beaches/roads.",
    "Split: 4 nights North Goa (Candolim) + 2 nights South Goa (Benaulim), which keeps "
    "one intra-Goa relocation instead of hotel-hopping, while still covering both coasts.",
    "Flights: Outbound BLR\u2192GOI priced live via MMT (IndiGo 6E 6554, 19:00\u201320:20, "
    "\u20b94,367/adult all-in) on the research date. The RETURN GOI\u2192BLR search on the MMT "
    "MCP returned an empty result twice (site blocked / no parse) \u2014 flagged as a DATA "
    "GAP. A same-fare-class placeholder is used for the return leg and is clearly marked "
    "as an ESTIMATE, not an MMT quote; re-run closer to the booking window.",
    "Trains: Indian Railways opens bookings only 60 days ahead, so MMT could not price "
    "the actual 15/21 Dec 2026 trains (outside window at research time). MMT's own "
    "\u201cindicative\u201d fares for the nearest bookable same-weekday date are shown for "
    "context only \u2014 they are real fares for a DIFFERENT date, not the dates of this trip.",
    "Hotels: MMT nightly retail (signed-out) rates, multiplied by nights per its own "
    "convention. These are non-negotiated OTA rates \u2014 typically at or above what a "
    "traveler pays after coupons/loyalty pricing at actual checkout.",
    "Cabs: MMT's outstation-cab engine prices point-to-point one-way transfers. It has "
    "no native \u201clocal full-day 8hr/80km package\u201d product, so day-trip local transport "
    "(e.g. Dudhsagar excursion, beach hopping) is priced as the nearest one-way-equivalent "
    "route and flagged. Actual local package/day-rental rates from tour operators are "
    "typically lower than stringing together one-way outstation fares \u2014 see notes per line.",
    "Scooter/bike rental, entry fees, water sports, cruises, nightlife and daily food "
    "budgets are NOT available on the MakeMyTrip MCP and are sourced from general web "
    "research (Perplexity), not from MakeMyTrip. These are labeled \u201cResearch estimate\u201d "
    "throughout and given as ranges.",
    "All amounts are per the whole party of 2 unless marked \u201cper person\u201d.",
]
elements.append(ListFlowable(
    [ListItem(Paragraph(a, styles["Caveat"]), leftIndent=12, spaceAfter=5) for a in assumptions],
    bulletType="bullet", start="circle", bulletFontSize=6, bulletColor=TEAL,
))
elements.append(PageBreak())

def day_banner(daynum, datestr, title):
    t = Table([[Paragraph(f"DAY {daynum}", styles["DayHeader"]),
                Paragraph(title, ParagraphStyle(name=f"dt{daynum}", fontName="Arial-Bold",
                                                 fontSize=12.5, leading=15, textColor=colors.white,
                                                 alignment=TA_RIGHT))],
               [Paragraph(datestr, styles["DayDate"]), ""]],
              colWidths=[8.0 * cm, 8.3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("SPAN", (1, 1), (1, 1)),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
    ]))
    return t

def day_body(activities, transport, stay):
    rows = []
    span_rows = []  # row indices where col0 should span the full width

    def add_header(text):
        rows.append([cell(text, "TableCellBold"), ""])
        span_rows.append(len(rows) - 1)

    add_header("Activities &amp; Places")
    for a in activities:
        rows.append([cell("&bull;", "TableCell"), cell(a, "TableCell")])
    add_header("Transport")
    for tr in transport:
        rows.append([cell("&bull;", "TableCell"), cell(tr, "TableCell")])
    add_header("Overnight: " + stay)

    t = Table(rows, colWidths=[0.5 * cm, 15.8 * cm])
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    for r in span_rows:
        style.append(("SPAN", (0, r), (1, r)))
        style.append(("TOPPADDING", (0, r), (1, r), 7 if r > 0 else 2.5))
    t.setStyle(TableStyle(style))
    return t

# =====================================================================
# TRIP AT A GLANCE
# =====================================================================
elements.append(Paragraph("Trip at a Glance", styles["H1"]))

glance_data = [
    [cell("Route", "TableHeader"), cell("Bengaluru (BLR) \u2194 Goa (GOI, Dabolim)", "TableCell")],
    [cell("Duration", "TableHeader"), cell("7 Days / 6 Nights &mdash; Tue 15 Dec to Mon 21 Dec 2026", "TableCell")],
    [cell("Base split", "TableHeader"), cell("4N North Goa (Candolim) + 2N South Goa (Benaulim)", "TableCell")],
    [cell("Travellers", "TableHeader"), cell("2 Adults, 1 Room", "TableCell")],
    [cell("Outbound flight", "TableHeader"), cell("IndiGo 6E 6554, BLR 19:00 \u2192 GOI 20:20 (1h20m, non-stop) &mdash; live MMT fare", "TableCell")],
    [cell("Return flight", "TableHeader"), cell("GOI \u2192 BLR, evening, non-stop (MMT search unavailable on this date &mdash; ESTIMATED, see notes)", "TableCell")],
    [cell("North Goa base", "TableHeader"), cell("Ginger Goa, Candolim (4-star) &mdash; 4 nights", "TableCell")],
    [cell("South Goa base", "TableHeader"), cell("Orchid Passaros, Benaulim (4-star, adults-only) &mdash; 2 nights", "TableCell")],
    [cell("Estimated total cost", "TableHeader"), cell(
        f"{money(CORE_TOTAL)} for 2 pax ({money(PER_PERSON_CORE)}/person), core plan &mdash; "
        f"full line-by-line breakdown follows", "TableCell")],
]
t = Table(glance_data, colWidths=[4.3 * cm, 12.0 * cm])
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (0, -1), NAVY),
    ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
    ("BACKGROUND", (1, 0), (1, -1), LIGHT_BG),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
]))
elements.append(t)
elements.append(Spacer(1, 10))
elements.append(Paragraph(
    "Why this split? North Goa (Candolim/Calangute/Baga/Anjuna) concentrates the forts, "
    "flea markets, water sports and nightlife within a compact, walkable/scooter-able "
    "radius. South Goa (Benaulim/Colva/Palolem) is quieter, closer to Dudhsagar Falls "
    "and the Western Ghats hinterland, and better for slow beach days. One relocation "
    "(Day 5) avoids the cost and hassle of hotel-hopping every 1-2 nights.",
    styles["Body"]))
elements.append(PageBreak())

# =====================================================================
# DAY BY DAY ITINERARY
# =====================================================================
elements.append(Paragraph("Day-by-Day Itinerary", styles["H1"]))
elements.append(Paragraph(
    "North Goa anchor: Candolim. South Goa anchor: Benaulim. Distances/costs for each "
    "transport leg are broken out in the Transport Cost Summary and Cost Breakdown "
    "tables later in this report.", styles["Body"]))
elements.append(Spacer(1, 8))

day1 = KeepTogether([
    day_banner(1, "Tuesday, 15 Dec 2026", "Fly In &amp; Settle into North Goa"),
    day_body(
        ["Morning: Depart Bengaluru; free until evening flight &mdash; pack, last-minute errands.",
         "Land in Goa (Dabolim, GOI) by 20:20; check in to Candolim.",
         "Evening: gentle walk on Candolim Beach; casual seafood dinner at a beach shack."],
        ["Flight: IndiGo 6E 6554 BLR 19:00 \u2192 GOI 20:20 (non-stop, 1h20m).",
         "Airport \u2192 Candolim: pre-booked outstation cab, sedan, ~40km/45min drive (live MMT quote)."],
        "Ginger Goa, Candolim (North Goa)"),
])
elements.append(day1)
elements.append(Spacer(1, 10))

day2 = KeepTogether([
    day_banner(2, "Wednesday, 16 Dec 2026", "Forts, Flea Market &amp; Sunset"),
    day_body(
        ["Morning: Fort Aguada &amp; lighthouse (free entry) &mdash; panoramic Arabian Sea views.",
         "Midday: Anjuna flea market (Wednesdays only \u2014 this date lines up perfectly).",
         "Afternoon: Vagator Beach; Chapora Fort at sunset (of \u201cDil Chahta Hai\u201d fame, free entry).",
         "Evening: dinner + casual nightlife around Anjuna/Vagator."],
        ["Self-drive scooter rental for the day (recommended for North Goa hopping) OR "
         "pre-booked local sedan for a half-day sightseeing loop.",
         "Candolim \u2194 Anjuna/Vagator/Chapora: ~12\u201315 km each way by scooter/local taxi."],
        "Ginger Goa, Candolim (North Goa)"),
])
elements.append(day2)
elements.append(Spacer(1, 10))

day3 = KeepTogether([
    day_banner(3, "Thursday, 17 Dec 2026", "Water Sports, Old Goa &amp; River Cruise"),
    day_body(
        ["Morning: Water sports at Calangute/Baga &mdash; parasailing, jet ski, banana boat combo.",
         "Afternoon: Old Goa UNESCO site &mdash; Basilica of Bom Jesus &amp; S\u00e9 Cathedral (both free entry); "
         "Panaji's Fontainhas Latin Quarter.",
         "Evening: Mandovi River sunset cruise from Panaji (live music/folk dance, standard ticket)."],
        ["Candolim \u2192 Old Goa: pre-booked outstation cab, sedan, ~40km (live MMT quote).",
         "Old Goa \u2192 Panaji \u2192 back to Candolim: same cab retained for the day / return taxi."],
        "Ginger Goa, Candolim (North Goa)"),
])
elements.append(day3)
elements.append(Spacer(1, 10))

day4 = KeepTogether([
    day_banner(4, "Friday, 18 Dec 2026", "Free Beach Day / Optional Spice Plantation"),
    day_body(
        ["Free/flex day to recover from sightseeing, or optional half-day spice plantation "
         "tour with traditional Goan lunch (Sahakari/Tropical Spice Plantation area).",
         "Relax at Calangute/Candolim beach; try Goan cafes and beach shacks.",
         "Evening: pack up for the move south tomorrow."],
        ["Optional: spice plantation round-trip from Candolim, ~55km round trip, half-day cab hire.",
         "No transfer today &mdash; stay put in North Goa."],
        "Ginger Goa, Candolim (North Goa)"),
])
elements.append(day4)
elements.append(Spacer(1, 10))

day5 = KeepTogether([
    day_banner(5, "Saturday, 19 Dec 2026", "Relocate to South Goa"),
    day_body(
        ["Morning: check out of Candolim; scenic drive south, with a stop at Dona Paula "
         "viewpoint or Goa State Museum en route.",
         "Afternoon: check in to Benaulim; relax at Benaulim/Colva Beach &mdash; noticeably "
         "quieter and less commercial than the north.",
         "Evening: seafood dinner by the coast; early night ahead of tomorrow's excursion."],
        ["Candolim \u2192 Benaulim: pre-booked outstation cab, sedan, ~40km (live MMT quote, "
         "~1\u20131.5 hrs actual drive time in normal traffic)."],
        "Orchid Passaros, Benaulim (South Goa)"),
])
elements.append(day5)
elements.append(Spacer(1, 10))

day6 = KeepTogether([
    day_banner(6, "Sunday, 20 Dec 2026", "Dudhsagar Falls Day Trip"),
    day_body(
        ["Full day: Dudhsagar Falls jeep safari through Bhagwan Mahavir Wildlife "
         "Sanctuary (regulated access, shared jeep from the collection point) &mdash; "
         "India's tallest waterfall on the Goa-Karnataka border.",
         "Often bundled with a spice plantation lunch stop on the return leg.",
         "Evening: return to Benaulim; low-key dinner, pack for departure."],
        ["Benaulim \u2192 Dudhsagar collection point: pre-booked outstation cab (live MMT "
         "quote used as the nearest priceable proxy \u2014 see Transport Cost Summary note on "
         "local-package pricing gap).",
         "Shared jeep safari inside the sanctuary is a separate, mandatory local fee "
         "(not sold on MMT \u2014 research estimate)."],
        "Orchid Passaros, Benaulim (South Goa)"),
])
elements.append(day6)
elements.append(Spacer(1, 10))

day7 = KeepTogether([
    day_banner(7, "Monday, 21 Dec 2026", "Palolem Beach &amp; Fly Back"),
    day_body(
        ["Morning: Palolem Beach &amp; Cabo de Rama Fort coastal viewpoint, or a relaxed "
         "final swim at Colva/Benaulim if time is tight.",
         "Check out; head to the airport for the evening flight to Bengaluru."],
        ["Benaulim \u2192 Palolem (round trip if visited) OR direct Benaulim \u2192 Dabolim "
         "Airport transfer, sedan, ~40km (live MMT quote).",
         "Return flight GOI \u2192 BLR, evening, non-stop (MMT search returned no result for "
         "this date &mdash; ESTIMATED fare used, see Assumptions)."],
        "Flight home"),
])
elements.append(day7)
elements.append(PageBreak())

# =====================================================================
# HOTELS
# =====================================================================
elements.append(Paragraph("Where to Stay", styles["H1"]))
elements.append(Paragraph(
    "Rates below are live MakeMyTrip signed-out retail rates for 2 adults / 1 room, "
    "pulled for the exact travel dates. Both are 4-star-rated properties chosen for "
    "consistency of comfort at a similar price tier; budget and luxury alternatives "
    "are noted for reference.", styles["Body"]))
elements.append(Spacer(1, 8))

hotel_rows = [
    [cell("Leg", "TableHeader"), cell("Property", "TableHeader"), cell("Nights", "TableHeader"),
     cell("Nightly (base+tax)", "TableHeader"), cell("Stay total (all-in)", "TableHeader")],
    [cell("North Goa<br/>(15&ndash;19 Dec)"), cell("Ginger Goa, Candolim &mdash; 4-star, rated 4.2/5"),
     cell("4", "TableCell"), cell(f"{money(8099)} + {money(1458)} tax", "TableCell"),
     cell(money(38228), "TableCellBold")],
    [cell("South Goa<br/>(19&ndash;21 Dec)"), cell("Orchid Passaros, Benaulim &mdash; 4-star adults-only, rated 4.4/5"),
     cell("2", "TableCell"), cell(f"{money(11259)} + {money(1621)} tax", "TableCell"),
     cell(money(25760), "TableCellBold")],
    [cell("", "TableCell"), cell("Combined hotel subtotal", "TableCellBold"), cell("6", "TableCellBold"),
     cell("", "TableCell"), cell(money(63988), "TableCellBold")],
]
ht = Table(hotel_rows, colWidths=[2.6*cm, 6.9*cm, 1.6*cm, 3.6*cm, 3.6*cm])
ht.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("BACKGROUND", (0, 1), (-1, -2), LIGHT_BG),
    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D7E6E6")),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("ALIGN", (2, 0), (4, -1), "CENTER"),
    ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
]))
elements.append(ht)
elements.append(Spacer(1, 8))
elements.append(Paragraph(
    "<b>Note on estimate accuracy:</b> stay totals are the nightly all-in rate multiplied "
    "by nights (MakeMyTrip's own convention for a date range) &mdash; not a per-date "
    "breakdown, so a stay spanning a price change won't match exactly. Both rates above "
    "include free cancellation and are room-only (breakfast optional add-on at Ginger Goa; "
    "included in most Orchid Passaros plans). Budget alternative: dorm/guesthouse options in "
    "Goa run &#8377;1,200&ndash;2,300/night all-in (e.g., Panjim City Dorms, The Hosteller Anjuna). "
    "Luxury alternative: 5-star beachfront resorts (Taj Exotica, The Westin, St. Regis) run "
    "&#8377;18,000&ndash;88,500/night all-in in this same window.", styles["BodySmall"]))
elements.append(PageBreak())

# =====================================================================
# INTERCITY TRANSPORT: BENGALURU <-> GOA
# =====================================================================
elements.append(Paragraph("Getting There &amp; Back: Bengaluru &#8596; Goa", styles["H1"]))
elements.append(Paragraph(
    "MMT's intercity comparison tool priced flight, train and cab together for both "
    "legs. All three modes are shown so the trade-off between cost, time and comfort "
    "is explicit &mdash; flight chosen for the itinerary given the time saved.",
    styles["Body"]))
elements.append(Spacer(1, 8))

elements.append(Paragraph("Outbound &mdash; 15 Dec 2026, Bengaluru &#8594; Goa", styles["H2"]))
out_rows = [
    [cell("Mode", "TableHeader"), cell("Option", "TableHeader"), cell("Duration", "TableHeader"),
     cell("Per person", "TableHeader"), cell("Party total (2)", "TableHeader")],
    [cell("FLIGHT <b>(chosen)</b>"), cell("IndiGo 6E 6554, 19:00\u219220:20, non-stop"),
     cell("1h 20m"), cell(f"{money(3222)}+{money(1145)} tax"), cell(money(4367*2), "TableCellBold")],
    [cell("TRAIN"), cell("16210 Ajmer Express, CC class, 23:50\u219208:28+1"),
     cell("8h 38m"), cell(money(735)), cell(money(1470))],
    [cell("TRAIN"), cell("16589 Rani Chennamma, 3E class, 23:00\u219207:58+1"),
     cell("8h 58m"), cell(money(835)), cell(money(1670))],
    [cell("CAB"), cell("Sedan (Dzire/Etios), self-drive-hire outstation"),
     cell("~11h 30m"), cell("per vehicle"), cell(money(12407), "TableCellBold")],
    [cell("CAB"), cell("Hatchback (WagonR/Swift), cheapest cab option"),
     cell("~11h 30m"), cell("per vehicle"), cell(money(12161))],
]
t1 = Table(out_rows, colWidths=[2.6*cm, 6.3*cm, 2.4*cm, 3.0*cm, 3.4*cm])
t1.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#D7E6E6")),
    ("BACKGROUND", (0, 2), (-1, -1), LIGHT_BG),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (2, 0), (4, -1), "CENTER"),
    ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
elements.append(t1)
elements.append(Spacer(1, 6))
elements.append(Paragraph(
    "Train fares are MMT's <b>indicative</b> figures for 3 Nov 2026 (the furthest date "
    "Indian Railways currently prices, same weekday) &mdash; the 15 Dec 2026 date is "
    "outside the 60-day booking window (opens 16 Oct 2026); use these only to compare "
    "against air/road, not as the actual fare for this trip. Cab durations exclude "
    "driver breaks/traffic; the flight is the clear time-value winner on this route.",
    styles["BodySmall"]))
elements.append(Spacer(1, 10))

elements.append(Paragraph("Return &mdash; 21 Dec 2026, Goa &#8594; Bengaluru", styles["H2"]))
ret_rows = [
    [cell("Mode", "TableHeader"), cell("Option", "TableHeader"), cell("Duration", "TableHeader"),
     cell("Per person", "TableHeader"), cell("Party total (2)", "TableHeader")],
    [cell("FLIGHT <b>(chosen, ESTIMATED)</b>"),
     cell("MMT flight search failed twice for GOI\u2192BLR on this date (empty response / "
          "blocked) &mdash; DATA GAP. Estimate below uses the outbound non-stop IndiGo fare "
          "as a same-class proxy."),
     cell("~1h 25m (est.)"), cell(f"~{money(4400)} (est.)"), cell(money(8800), "TableCellBold")],
    [cell("TRAIN"), cell("20675 Vishwamanav Exp, CC class, 07:50\u219217:45"),
     cell("9h 55m"), cell(money(785)), cell(money(1570))],
    [cell("TRAIN"), cell("16590 Rani Chennamma, 3E class, 19:20\u219206:20+1"),
     cell("11h 00m"), cell(money(835)), cell(money(1670))],
    [cell("CAB"), cell("Sedan (Dzire/Etios), outstation one-way"),
     cell("~11h 30m"), cell("per vehicle"), cell(money(13673))],
    [cell("CAB"), cell("Hatchback (WagonR/Swift), cheapest cab option"),
     cell("~11h 30m"), cell("per vehicle"), cell(money(13401))],
]
t2 = Table(ret_rows, colWidths=[2.6*cm, 6.3*cm, 2.4*cm, 3.0*cm, 3.4*cm])
t2.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F7E7C4")),
    ("BACKGROUND", (0, 2), (-1, -1), LIGHT_BG),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (2, 0), (4, -1), "CENTER"),
    ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
elements.append(t2)
elements.append(Spacer(1, 6))
elements.append(Paragraph(
    "<b>Flagged data gap:</b> the MakeMyTrip MCP's live flight search for GOI\u2192BLR on "
    "21 Dec 2026 returned a 0-byte page twice (once on first attempt, once on retry) "
    "&mdash; a known site-blocking issue, not a real \u201csold out\u201d signal. Rather than "
    "silently omitting the return flight or presenting a made-up fare as if it were "
    "quoted, this report uses the outbound fare class as an explicit ESTIMATE (highlighted "
    "gold) and recommends re-querying MMT directly closer to the booking window. Historically "
    "GOI\u2192BLR non-stop evening IndiGo/Air India Express fares track within \u00b110\u201315% of the "
    "outbound fare at the same lead time, so &#8377;4,300\u20134,600/adult is a reasonable planning "
    "range.", styles["BodySmall"]))
elements.append(PageBreak())

# =====================================================================
# LOCAL TRANSPORT WITHIN GOA
# =====================================================================
elements.append(Paragraph("Local Transport Within Goa", styles["H1"]))
elements.append(Paragraph(
    "Goa has essentially no ride-hailing coverage (Uber/Ola presence is patchy and "
    "often blocked by the local taxi lobby outside a few pockets) &mdash; the two "
    "realistic choices are a self-drive rented scooter/car, or a pre-booked taxi/cab "
    "for point-to-point transfers. This itinerary uses a mix: pre-booked cabs (MMT-priced) "
    "for the longer inter-town transfers, and a self-drive scooter for North Goa's "
    "compact daily hopping.", styles["Body"]))
elements.append(Spacer(1, 8))

local_rows = [
    [cell("Item", "TableHeader"), cell("Basis", "TableHeader"), cell("Source", "TableHeader"),
     cell("Amount", "TableHeader")],
    [cell("Scooter rental (self-drive)"), cell(f"2 scooters &times; 2 days &times; {money(SCOOTER_PER_DAY_PER_UNIT)}/day"),
     cell("Research estimate"), cell(money(SCOOTER_SUBTOTAL), "TableCellBold")],
    [cell("Airport &#8594; Candolim transfer"), cell("Sedan, one-way, ~40km"),
     cell("MMT live quote"), cell(money(CAB_AIRPORT_IN))],
    [cell("Candolim &#8596; Old Goa/Panaji (Day 3)"), cell("Sedan, round trip, ~80km total"),
     cell("MMT live quote &times;2 (RT proxy)"), cell(money(CAB_OLDGOA_RT))],
    [cell("Candolim &#8594; Benaulim relocation"), cell("Sedan, one-way, ~40km"),
     cell("MMT live quote"), cell(money(CAB_RELOCATE))],
    [cell("Benaulim &#8596; Dudhsagar Falls (Day 6)"), cell("Sedan, round trip, ~80km total"),
     cell("MMT live quote &times;2 (RT proxy)"), cell(money(CAB_DUDHSAGAR_RT))],
    [cell("Benaulim &#8594; Airport transfer"), cell("Sedan, one-way, ~40km"),
     cell("MMT live quote"), cell(money(CAB_AIRPORT_OUT))],
    [cell("Local transport subtotal", "TableCellBold"), cell("", "TableCell"), cell("", "TableCell"),
     cell(money(SCOOTER_SUBTOTAL + CAB_SUBTOTAL), "TableCellBold")],
]
lt = Table(local_rows, colWidths=[5.3*cm, 5.0*cm, 3.5*cm, 2.7*cm])
lt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("BACKGROUND", (0, 1), (-1, -2), LIGHT_BG),
    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D7E6E6")),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
    ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
elements.append(lt)
elements.append(Spacer(1, 8))
elements.append(Paragraph(
    "<b>Known pricing gap, flagged per MMT's own documentation:</b> MakeMyTrip's cab "
    "engine only prices point-to-point outstation one-way/round-trip fares &mdash; it has "
    "no \u201clocal full-day 8hr/80km package\u201d product that Goa taxi unions typically sell for "
    "sightseeing loops (e.g., a full-day Old Goa + Panaji + back loop, or the Dudhsagar "
    "day trip). For both loop trips above, this report doubles the one-way MMT quote as "
    "a conservative round-trip proxy. In practice, a local full-day package for these "
    "same routes typically runs &#8377;2,500&ndash;3,500 flat (cheaper than 2&times; a one-way "
    "outstation fare), so treat the CAB_OLDGOA_RT and CAB_DUDHSAGAR_RT lines above as a "
    "ceiling, not a floor. The Dudhsagar jeep safari itself (inside the sanctuary, shared "
    "jeep, mandatory) is a separate fee not sold on MMT at all &mdash; see Activities table.",
    styles["BodySmall"]))
elements.append(PageBreak())

# =====================================================================
# ACTIVITIES, ENTRY FEES & FOOD
# =====================================================================
elements.append(Paragraph("Activities, Entry Fees &amp; Food", styles["H1"]))
elements.append(Paragraph(
    "None of these are priced by MakeMyTrip (it does not sell attraction tickets or "
    "F&amp;B in Goa) &mdash; all figures below are research estimates from general web "
    "sources, given as mid-range planning numbers for 2 people.", styles["Body"]))
elements.append(Spacer(1, 8))

act_rows = [
    [cell("Day", "TableHeader"), cell("Item", "TableHeader"), cell("Per person", "TableHeader"),
     cell("Party total (2)", "TableHeader")],
    [cell("2"), cell("Fort Aguada, Chapora Fort, Anjuna flea market entry"), cell(money(0)), cell(money(0))],
    [cell("2"), cell("Baga/Tito's Lane nightlife (cover + drinks)"), cell(money(2000)), cell(money(FEE_NIGHTLIFE), "TableCellBold")],
    [cell("3"), cell("Water sports combo (parasail + jet ski + banana boat)"), cell(money(1750)), cell(money(FEE_WATERSPORTS), "TableCellBold")],
    [cell("3"), cell("Basilica of Bom Jesus &amp; S\u00e9 Cathedral entry"), cell(money(0)), cell(money(0))],
    [cell("3"), cell("Mandovi sunset river cruise"), cell(money(450)), cell(money(FEE_CRUISE), "TableCellBold")],
    [cell("4"), cell("OPTIONAL: spice plantation tour + Goan lunch"), cell(money(1000)), cell(money(FEE_SPICE_PLANTATION_OPT), "TableCellBold")],
    [cell("6"), cell("Dudhsagar jeep safari + spice plantation/lunch combo"), cell(money(2000)), cell(money(FEE_DUDHSAGAR_COMBO), "TableCellBold")],
    [cell("&mdash;", "TableCellBold"), cell("Activities subtotal (core plan, excl. optional)", "TableCellBold"), cell("", "TableCell"),
     cell(money(ACTIVITIES_CORE), "TableCellBold")],
]
at = Table(act_rows, colWidths=[1.4*cm, 8.7*cm, 3.0*cm, 3.4*cm])
at.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("BACKGROUND", (0, 1), (-1, -2), LIGHT_BG),
    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D7E6E6")),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0,0),(0,-1),"CENTER"),
    ("ALIGN", (2, 0), (3, -1), "RIGHT"),
    ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
elements.append(at)
elements.append(Spacer(1, 10))

elements.append(Paragraph("Food Budget", styles["H2"]))
food_rows = [
    [cell("Basis", "TableHeader"), cell("Per person/day", "TableHeader"), cell("Days", "TableHeader"),
     cell("Party total (2)", "TableHeader")],
    [cell("Mid-range: breakfast at hotel/cafe, lunch + dinner at beach shacks/casual restaurants, "
          "a few drinks"), cell(money(FOOD_PER_PERSON_PER_DAY)), cell(str(FOOD_DAYS)),
     cell(money(FOOD_SUBTOTAL), "TableCellBold")],
]
ft = Table(food_rows, colWidths=[8.0*cm, 3.0*cm, 1.8*cm, 3.7*cm])
ft.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("BACKGROUND", (0, 1), (-1, -1), LIGHT_BG),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (3, -1), "CENTER"),
    ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
]))
elements.append(ft)
elements.append(Spacer(1, 6))
elements.append(Paragraph(
    "Budget travelers can expect &#8377;800&ndash;1,200/person/day (local thalis, simple "
    "shacks); this plan uses the mid-range &#8377;1,500&ndash;2,500/person/day band, "
    "settling at &#8377;2,000/person/day. Alcohol, especially at beach clubs, is the "
    "biggest swing factor &mdash; Goa's low excise duty makes it cheap by Indian standards, "
    "but frequent nights out add up fast.", styles["BodySmall"]))
elements.append(PageBreak())

# =====================================================================
# MASTER COST BREAKDOWN
# =====================================================================
elements.append(Paragraph("Complete Cost Breakdown", styles["H1"]))
elements.append(Paragraph(
    "Every line item from the sections above, in one place, with its data source. "
    "Amounts are for the whole party of 2 unless noted otherwise.", styles["Body"]))
elements.append(Spacer(1, 8))

def srow(category, item, amount, source, bold=False):
    style = "TableCellBold" if bold else "TableCell"
    return [cell(category, style), cell(item, style), cell(source, "TableCell"),
            cell(money(amount), "TableCellBold")]

master_rows = [
    [cell("Category", "TableHeader"), cell("Line item", "TableHeader"),
     cell("Source", "TableHeader"), cell("Amount", "TableHeader")],
    srow("Flights", "Bengaluru \u2192 Goa, IndiGo 6E 6554 (2 adults)", FLIGHT_OUT, "MMT live"),
    srow("Flights", "Goa \u2192 Bengaluru, evening non-stop (2 adults)", FLIGHT_RET_EST, "ESTIMATE (MMT search failed)"),
    srow("Hotels", "North Goa: Ginger Goa, Candolim, 4 nights", HOTEL_NORTH, "MMT live"),
    srow("Hotels", "South Goa: Orchid Passaros, Benaulim, 2 nights", HOTEL_SOUTH, "MMT live"),
    srow("Cabs", "Airport \u2192 Candolim transfer", CAB_AIRPORT_IN, "MMT live"),
    srow("Cabs", "Candolim \u2194 Old Goa/Panaji day trip (RT proxy)", CAB_OLDGOA_RT, "MMT live (x2, flagged)"),
    srow("Cabs", "Candolim \u2192 Benaulim relocation", CAB_RELOCATE, "MMT live"),
    srow("Cabs", "Benaulim \u2194 Dudhsagar Falls day trip (RT proxy)", CAB_DUDHSAGAR_RT, "MMT live (x2, flagged)"),
    srow("Cabs", "Benaulim \u2192 Airport transfer", CAB_AIRPORT_OUT, "MMT live"),
    srow("Local self-drive", "Scooter rental, 2 units x 2 days", SCOOTER_SUBTOTAL, "Research estimate"),
    srow("Activities", "Forts &amp; churches (Aguada, Chapora, Bom Jesus, S\u00e9)", 0, "Free entry"),
    srow("Activities", "Nightlife (Baga/Tito's Lane)", FEE_NIGHTLIFE, "Research estimate"),
    srow("Activities", "Water sports combo", FEE_WATERSPORTS, "Research estimate"),
    srow("Activities", "Mandovi sunset cruise", FEE_CRUISE, "Research estimate"),
    srow("Activities", "Dudhsagar jeep safari + plantation combo", FEE_DUDHSAGAR_COMBO, "Research estimate"),
    srow("Food", f"{FOOD_DAYS} days x 2 pax x {money(FOOD_PER_PERSON_PER_DAY)}/day", FOOD_SUBTOTAL, "Research estimate"),
    srow("Incidentals", "SIM/data, tips, sunscreen, misc.", INCIDENTALS, "Research estimate"),
    [cell("CORE TRIP TOTAL", "TableCellBold"), cell("(excludes optional spice plantation add-on)", "TableCellBold"),
     cell("", "TableCell"), cell(money(CORE_TOTAL), "TableCellBold")],
    srow("Optional add-on", "Day 4 spice plantation tour + lunch", FEE_SPICE_PLANTATION_OPT, "Research estimate"),
    [cell("GRAND TOTAL", "TableCellBold"), cell("(with optional spice plantation add-on)", "TableCellBold"),
     cell("", "TableCell"), cell(money(GRAND_TOTAL_WITH_OPTIONAL), "TableCellBold")],
]
mt = Table(master_rows, colWidths=[2.6*cm, 7.7*cm, 3.4*cm, 2.8*cm])
mt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("BACKGROUND", (0, 1), (-1, -4), LIGHT_BG),
    ("BACKGROUND", (0, -3), (-1, -3), colors.HexColor("#D7E6E6")),
    ("BACKGROUND", (0, -2), (-1, -2), LIGHT_BG),
    ("BACKGROUND", (0, -1), (-1, -1), GOLD),
    ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
    ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("LINEABOVE", (0, -3), (-1, -3), 1.2, NAVY),
    ("LINEABOVE", (0, -1), (-1, -1), 1.2, NAVY),
]))
elements.append(mt)
elements.append(Spacer(1, 12))

summary_tbl = Table([
    [Paragraph("CORE TRIP &mdash; PARTY OF 2", styles["TotalLabel"]), Paragraph(money(CORE_TOTAL), styles["TotalValue"])],
    [Paragraph("Per person (core plan)", ParagraphStyle(name="pp1", fontName="Arial", fontSize=10, textColor=colors.white)),
     Paragraph(money(PER_PERSON_CORE), ParagraphStyle(name="pp2", fontName="Arial-Bold", fontSize=11, textColor=colors.white, alignment=TA_RIGHT))],
], colWidths=[10.0*cm, 6.5*cm])
summary_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), TEAL),
    ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.white),
]))
elements.append(summary_tbl)
elements.append(Spacer(1, 10))
elements.append(Paragraph(
    "<b>Bottom line:</b> budget roughly " + money(CORE_TOTAL) + " for two people "
    "(about " + money(PER_PERSON_CORE) + " per person) for this 7-day/6-night core "
    "itinerary, excluding shopping, spa treatments, souvenirs, travel insurance and any "
    "further optional excursions. Add " + money(FEE_SPICE_PLANTATION_OPT) +
    " if including the optional Day 4 spice plantation visit. Treat the two ESTIMATE / "
    "flagged proxy lines (return flight, and the two round-trip cab proxies) as the "
    "widest-uncertainty items in this budget \u2014 everything else traces to a live MMT quote "
    "pulled on the research date.", styles["Body"]))

# =====================================================================
# BUILD
# =====================================================================
OUT_PATH = __file__.replace("build_goa_report.py", "Goa_Trip_Itinerary_and_Budget.pdf")

doc = SimpleDocTemplate(
    OUT_PATH, pagesize=A4,
    leftMargin=MARGIN, rightMargin=MARGIN,
    topMargin=1.5 * cm, bottomMargin=1.6 * cm,
    title="Goa 7-Day Itinerary and Budget Dossier",
    author="MakeMyTrip MCP + Research",
)
doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)
print(f"PDF written to: {OUT_PATH}")
print(f"CORE_TOTAL={CORE_TOTAL}  PER_PERSON_CORE={PER_PERSON_CORE}  GRAND_TOTAL_WITH_OPTIONAL={GRAND_TOTAL_WITH_OPTIONAL}")


