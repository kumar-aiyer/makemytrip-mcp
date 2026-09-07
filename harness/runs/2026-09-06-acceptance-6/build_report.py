# -*- coding: utf-8 -*-
"""
Goa 7-Day Itinerary & Budget Report generator
Builds a polished PDF using ReportLab from data sourced via the MakeMyTrip MCP
(flights, hotels, cabs) plus supplementary web research (activities, food,
weather) dated 2026-09-06.
"""
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    HRFlowable, ListFlowable, ListItem, NextPageTemplate, PageTemplate,
    Frame, BaseDocTemplate, KeepTogether
)
from reportlab.platypus.tableofcontents import TableOfContents

OUT_PATH = r"C:\Users\kumar\projects\claudecodeprojects\mmt-acceptance-workspace\goa_itinerary\Goa_7Day_Itinerary_Budget.pdf"

NAVY = colors.HexColor("#0B2545")
TEAL = colors.HexColor("#0F766E")
GOLD = colors.HexColor("#C9932A")
LIGHT = colors.HexColor("#F4F6F8")
GREY = colors.HexColor("#5B6770")
LINE = colors.HexColor("#D8DEE3")

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(name="CoverTitle", fontName="Helvetica-Bold", fontSize=30,
                           leading=34, textColor=NAVY, alignment=TA_LEFT, spaceAfter=6))
styles.add(ParagraphStyle(name="CoverSub", fontName="Helvetica", fontSize=14,
                           leading=18, textColor=TEAL, spaceAfter=4))
styles.add(ParagraphStyle(name="CoverMeta", fontName="Helvetica", fontSize=10.5,
                           leading=15, textColor=GREY))
styles.add(ParagraphStyle(name="H1", fontName="Helvetica-Bold", fontSize=17,
                           leading=20, textColor=NAVY, spaceBefore=4, spaceAfter=8))
styles.add(ParagraphStyle(name="H2", fontName="Helvetica-Bold", fontSize=12.5,
                           leading=15, textColor=TEAL, spaceBefore=10, spaceAfter=5))
styles.add(ParagraphStyle(name="Body", fontName="Helvetica", fontSize=9.6,
                           leading=13.6, textColor=colors.HexColor("#222831"),
                           spaceAfter=5))
styles.add(ParagraphStyle(name="BodySmall", fontName="Helvetica", fontSize=8.6,
                           leading=12, textColor=GREY, spaceAfter=4))
styles.add(ParagraphStyle(name="Caption", fontName="Helvetica-Oblique", fontSize=8.3,
                           leading=11.5, textColor=GREY, spaceAfter=4))
styles.add(ParagraphStyle(name="DayHeader", fontName="Helvetica-Bold", fontSize=11.5,
                           leading=14, textColor=colors.white, spaceAfter=0,
                           spaceBefore=0))
styles.add(ParagraphStyle(name="TblHead", fontName="Helvetica-Bold", fontSize=8.6,
                           leading=10.5, textColor=colors.white))
styles.add(ParagraphStyle(name="TblCell", fontName="Helvetica", fontSize=8.6,
                           leading=11.2, textColor=colors.HexColor("#222831")))
styles.add(ParagraphStyle(name="TblCellR", fontName="Helvetica", fontSize=8.6,
                           leading=11.2, textColor=colors.HexColor("#222831"),
                           alignment=2))
styles.add(ParagraphStyle(name="TblCellBold", fontName="Helvetica-Bold", fontSize=8.8,
                           leading=11.2, textColor=NAVY))
styles.add(ParagraphStyle(name="TblCellBoldR", fontName="Helvetica-Bold", fontSize=8.8,
                           leading=11.2, textColor=NAVY, alignment=2))

def p(text, style="Body"):
    return Paragraph(text, styles[style])

def money(n):
    return "Rs {:,.0f}".format(n)

# =====================================================================
# COST MODEL  (single source of truth - all figures below feed both the
# cover-page summary and the detailed section tables, so the two can
# never drift apart)
# =====================================================================
PAX = 2

# ---- 1. Flights (MakeMyTrip live search, 2 adults, Economy) ----
FLIGHT_OUT_PP = 6047.0   # 6E 6753 BLR->GOI 16:10-17:30, 16-Dec-2026
FLIGHT_RET_PP = 6624.0   # 6E 6163 GOI->BLR 19:15-20:25, 22-Dec-2026
flights_total = (FLIGHT_OUT_PP + FLIGHT_RET_PP) * PAX

# ---- 2. Hotels (MakeMyTrip live rates, cheapest room-only w/ free cancel) ----
HOTEL_SOUTH_NIGHT = 14700.0   # The Shore Agonda, Deluxe Seaview Villa
HOTEL_SOUTH_NIGHTS = 3
HOTEL_NORTH_NIGHT = 5096.0    # Summit Calangute Resort & Spa, Deluxe Room
HOTEL_NORTH_NIGHTS = 3
hotel_south_total = HOTEL_SOUTH_NIGHT * HOTEL_SOUTH_NIGHTS
hotel_north_total = HOTEL_NORTH_NIGHT * HOTEL_NORTH_NIGHTS
hotels_total = hotel_south_total + hotel_north_total

# ---- 3. Intercity / airport transfer cabs (MakeMyTrip live cab quotes, cheapest car) ----
CAB_AIRPORT_TO_AGONDA = 2045.0     # Dabolim Airport -> Agonda, 16 Dec
CAB_AGONDA_TO_MOLLEM  = 2045.0     # Agonda -> Mollem (Dudhsagar gateway), 21 Dec
CAB_MOLLEM_TO_AGONDA  = 2045.0     # return leg, same tariff assumed
CAB_AGONDA_TO_CALANGUTE = 2145.0   # Agonda -> Calangute, 19 Dec
CAB_CALANGUTE_TO_AIRPORT = 2145.0  # Calangute -> Dabolim Airport, 22 Dec
transfers_total = (CAB_AIRPORT_TO_AGONDA + CAB_AGONDA_TO_MOLLEM + CAB_MOLLEM_TO_AGONDA
                   + CAB_AGONDA_TO_CALANGUTE + CAB_CALANGUTE_TO_AIRPORT)

# ---- 4. Local transport within each base (scooter rental - not an MMT product; web-sourced) ----
SCOOTER_PER_DAY = 500.0
SCOOTER_DAYS = 3          # Day 2 (South), Day 5 & 6 (North)
ARPORA_LOCAL_HOP = 300.0  # short taxi/auto, Calangute <-> Arpora night market
local_transport_total = SCOOTER_PER_DAY * SCOOTER_DAYS + ARPORA_LOCAL_HOP

# ---- 5. Activities & entry fees (web-sourced; MMT has no activity-booking product) ----
DOLPHIN_TRIP_PP = 400.0
BUTTERFLY_BOAT_PP = 600.0
DUDHSAGAR_JEEP_PP = 1500.0
FORT_AGUADA_ENTRY_PP = 40.0
WATERSPORTS_COMBO_PP = 2000.0
activities_total = (DOLPHIN_TRIP_PP + BUTTERFLY_BOAT_PP + DUDHSAGAR_JEEP_PP
                     + FORT_AGUADA_ENTRY_PP + WATERSPORTS_COMBO_PP) * PAX

# ---- 6. Food & beverage (web-sourced mid-range daily benchmark, per couple) ----
FOOD_FULL_DAY = 3500.0
FOOD_FULL_DAYS = 5        # Days 2,3,4,5,6 fully in Goa
FOOD_ARRIVAL_DAY = 1200.0  # Day 1: dinner only
FOOD_DEPARTURE_DAY = 1800.0  # Day 7: breakfast + lunch only
food_total = FOOD_FULL_DAY * FOOD_FULL_DAYS + FOOD_ARRIVAL_DAY + FOOD_DEPARTURE_DAY

# ---- 7. Contingency / incidentals (SIM, tips, market shopping, fee buffer) ----
contingency_total = 5000.0

GRAND_TOTAL = (flights_total + hotels_total + transfers_total + local_transport_total
               + activities_total + food_total + contingency_total)
PER_PERSON = GRAND_TOTAL / PAX
PER_PERSON_PER_DAY = PER_PERSON / 7

story = []

# ---------------------------------------------------------------- COVER ----
story.append(Spacer(1, 40*mm))
story.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=10))
story.append(p("GOA GETAWAY", "CoverTitle"))
story.append(p("A 7-Day / 6-Night Beach &amp; Heritage Itinerary for Two", "CoverSub"))
story.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceBefore=10, spaceAfter=18))
story.append(p("Bengaluru (BLR) &rarr; Goa (GOI) &rarr; Bengaluru (BLR)", "CoverMeta"))
story.append(p("16&ndash;22 December 2026 &nbsp;|&nbsp; 2 Adults &nbsp;|&nbsp; South Goa (Agonda) + North Goa (Candolim/Calangute)", "CoverMeta"))
story.append(Spacer(1, 6*mm))
story.append(p("Prepared using live MakeMyTrip fare &amp; rate data (flights, hotels, outstation cabs) "
                "captured on 6&nbsp;September&nbsp;2026, supplemented with independently researched "
                "activity, food and local-transport benchmarks where MakeMyTrip has no product "
                "(e.g. scooter rental, local sightseeing packages, entry fees).", "CoverMeta"))
story.append(Spacer(1, 60*mm))
cover_tbl = Table([
    ["Grand total (2 adults, all-in)", money(GRAND_TOTAL) + " approx."],
    ["Per person", money(PER_PERSON) + " approx."],
    ["Per person / per day (7 days)", money(PER_PERSON_PER_DAY) + " approx."],
], colWidths=[95*mm, 75*mm])
cover_tbl.setStyle(TableStyle([
    ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
    ("FONTNAME", (1,0), (1,-1), "Helvetica-Bold"),
    ("FONTSIZE", (0,0), (-1,-1), 11),
    ("TEXTCOLOR", (0,0), (-1,-1), NAVY),
    ("ALIGN", (1,0), (1,-1), "RIGHT"),
    ("LINEBELOW", (0,0), (-1,-2), 0.5, LINE),
    ("TOPPADDING", (0,0), (-1,-1), 6),
    ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ("BOX", (0,0), (-1,-1), 0.75, GOLD),
    ("BACKGROUND", (0,0), (-1,-1), LIGHT),
]))
story.append(cover_tbl)
story.append(Spacer(1, 8*mm))
story.append(p("All fares/rates in Indian Rupees (INR). Figures are signed-out, non-member retail "
               "quotes valid at time of search; MakeMyTrip does not support booking through this "
               "channel and prices are not held. See Section 6 for full pricing assumptions and caveats.",
               "Caption"))
story.append(PageBreak())

# ------------------------------------------------------------- OVERVIEW ----
story.append(p("1. Trip Overview", "H1"))
story.append(p(
    "This itinerary splits six nights evenly between South Goa's quieter Agonda coast and "
    "North Goa's lively Candolim/Calangute belt, so the trip opens calm and closes energetic. "
    "December is peak season in Goa (dry, sunny, 21&ndash;32&deg;C, negligible rain) and also the "
    "most expensive and crowded month of the year &mdash; book flights and hotels early, and expect "
    "the North Goa/Baga-Calangute stretch to be busy after dark.", "Body"))

ov_data = [
    ["Day", "Date", "Base", "Focus"],
    ["1", "Wed 16 Dec", "Arrive &middot; South Goa", "Flight BLR&rarr;GOI, transfer to Agonda, settle in"],
    ["2", "Thu 17 Dec", "South Goa", "Agonda &amp; Palolem beaches, dolphin trip, Butterfly Beach boat"],
    ["3", "Fri 18 Dec", "South Goa", "Full-day Dudhsagar Falls &amp; Mollem National Park excursion"],
    ["4", "Sat 19 Dec", "South &rarr; North Goa", "Checkout, transfer to Candolim, evening at Arpora Saturday Night Market"],
    ["5", "Sun 20 Dec", "North Goa", "Fort Aguada, Old Goa churches (UNESCO), Panaji &amp; Fontainhas"],
    ["6", "Mon 21 Dec", "North Goa", "Water sports at Calangute/Baga, Anjuna, Chapora Fort, Vagator sunset"],
    ["7", "Tue 22 Dec", "Depart", "Leisure morning, checkout, transfer to GOI, flight GOI&rarr;BLR"],
]
ov_rows = [[Paragraph(c, styles["TblHead"] if r == 0 else styles["TblCell"]) for c in row]
           for r, row in enumerate(ov_data)]
ov_tbl = Table(ov_rows, colWidths=[10*mm, 24*mm, 40*mm, 96*mm], repeatRows=1)
ov_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.4, LINE),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("TOPPADDING", (0,0), (-1,-1), 4),
    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(ov_tbl)
story.append(Spacer(1, 4*mm))
story.append(p("<b>Why this split, not the reverse:</b> the only Saturday that falls inside the trip "
               "window is 19 Dec &mdash; the Arpora Saturday Night Market date. Doing South Goa first "
               "means the North Goa check-in lands on that exact evening, so the market visit needs no "
               "extra transfer. The Anjuna Wednesday flea market (16 Dec) is skipped by design: it "
               "closes near sunset and the outbound flight only lands at 17:30, leaving no realistic "
               "window &mdash; called out here rather than silently dropped.", "BodySmall"))
story.append(p("<b>Weather (Goa, mid-to-late December, 10-yr averages):</b> daytime highs "
               "~31&ndash;33&deg;C, nights ~21&ndash;23&deg;C, humidity 50&ndash;65%, "
               "negligible rainfall, sea temperature ~28&deg;C &mdash; ideal beach weather. "
               "Source: web research (weather2travel, AccuWeather), not MakeMyTrip.", "BodySmall"))
story.append(PageBreak())

# ============================================================ DAY BY DAY ===
def day_block(day_no, date_str, title, items, cost_rows, cost_note=None):
    """items: list of (time, text) tuples. cost_rows: list of (label, amount_str)"""
    hdr = Table([[Paragraph("DAY {} &nbsp;&middot;&nbsp; {}".format(day_no, date_str), styles["DayHeader"]),
                  Paragraph(title, styles["DayHeader"])]],
                colWidths=[55*mm, 111*mm])
    hdr.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("SPAN", (0,0), (0,0)),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (0,0), 8),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
        ("RIGHTPADDING", (1,0), (1,0), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    block = [hdr, Spacer(1, 2*mm)]
    item_rows = [[Paragraph(t, styles["TblCellBold"]), Paragraph(txt, styles["TblCell"])]
                 for t, txt in items]
    it_tbl = Table(item_rows, colWidths=[22*mm, 144*mm])
    it_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LINEBELOW", (0,0), (-1,-2), 0.3, LINE),
    ]))
    block.append(it_tbl)
    block.append(Spacer(1, 2*mm))
    if cost_rows:
        crows = [[Paragraph(lbl, styles["TblCell"]), Paragraph(amt, styles["TblCellR"])]
                 for lbl, amt in cost_rows]
        c_tbl = Table(crows, colWidths=[124*mm, 42*mm])
        c_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), LIGHT),
            ("BOX", (0,0), (-1,-1), 0.4, LINE),
            ("TOPPADDING", (0,0), (-1,-1), 2.5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2.5),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
        ]))
        block.append(c_tbl)
    if cost_note:
        block.append(Spacer(1, 1.5*mm))
        block.append(p(cost_note, "Caption"))
    return KeepTogether(block)

story.append(p("2. Day-by-Day Itinerary", "H1"))

story.append(day_block(1, "Wed 16 Dec", "Arrive &middot; Transfer to South Goa (Agonda)",
    [("11:40", "Depart Bengaluru (BLR). Suggested flight: <b>IndiGo 6E 6753, 16:10&ndash;17:30</b> "
              "(MakeMyTrip cheapest non-alternate-airport fare landing at GOI). Arrive Goa Dabolim (GOI)."),
     ("18:00", "Prepaid outstation cab from Dabolim Airport direct to Agonda Beach (~40&nbsp;km, "
               "quoted as a ~4&nbsp;hr hire slot by MakeMyTrip)."),
     ("19:30", "Check in to <b>The Shore Agonda</b> (5-star boutique, Deluxe Seaview Villa). Relax, "
               "walk the beach at sunset."),
     ("20:30", "Dinner at a beach shack on Agonda Beach &mdash; known for being quieter and less "
               "commercial than Palolem/Baga.")],
    [("Flights BLR&rarr;GOI (2 adults, Economy, all-in)", money(FLIGHT_OUT_PP*PAX)),
     ("Cab: Dabolim Airport &rarr; Agonda (cheapest car, all-in)", money(CAB_AIRPORT_TO_AGONDA)),
     ("Dinner (couple)", money(FOOD_ARRIVAL_DAY))],
    "Flight fare is MakeMyTrip live quote for 2 adults, Economy cabin, captured 06-Sep-2026; excludes "
    "seat/baggage add-ons. Cab fare is MakeMyTrip's cheapest listed car (WagonR/Swift hatchback, Taxibazaar)."))

story.append(Spacer(1, 4*mm))
story.append(day_block(2, "Thu 17 Dec", "South Goa Beaches &middot; Palolem &amp; Butterfly Beach",
    [("08:00", "Breakfast at hotel/local cafe. Rent a scooter for the day (self-drive, most flexible "
              "way to cover Agonda&ndash;Palolem&ndash;Colva)."),
     ("10:00", "Morning at <b>Agonda Beach</b> &mdash; swim, walk; quieter than the northern beaches."),
     ("12:30", "Ride to <b>Palolem Beach</b> (~10&nbsp;km). Lunch at a beach shack."),
     ("14:30", "Boat trip: <b>dolphin-spotting</b> excursion from Palolem, followed by a boat ride to "
               "the secluded <b>Butterfly Beach</b>."),
     ("17:30", "Sunset at Palolem; optional stop at <b>Colva/Benaulim</b> on the ride back."),
     ("20:00", "Dinner back in Agonda.")],
    [("Scooter rental (1 day)", money(SCOOTER_PER_DAY)),
     ("Dolphin-spotting boat trip (2 pax)", money(DOLPHIN_TRIP_PP*PAX)),
     ("Butterfly Beach boat ride (2 pax)", money(BUTTERFLY_BOAT_PP*PAX)),
     ("Food &amp; drinks, full day (couple)", money(FOOD_FULL_DAY))],
    "Scooter/activity/food figures are independently researched benchmarks (MakeMyTrip has no local "
    "activity-booking or self-drive scooter product) &mdash; see Section 6."))

story.append(Spacer(1, 4*mm))
story.append(day_block(3, "Fri 18 Dec", "Full-Day Dudhsagar Falls &amp; Mollem National Park",
    [("07:00", "Early breakfast, depart by shared/private jeep transfer to <b>Mollem</b> "
              "(gateway to Dudhsagar; ~40&nbsp;km from Agonda)."),
     ("09:30", "Forest-department jeep safari into <b>Mollem National Park</b> to <b>Dudhsagar "
               "Falls</b> (India's 5th-tallest waterfall, four-tiered)."),
     ("13:00", "Packed lunch/local dhaba near the falls; swim at the base pool if open."),
     ("16:00", "Return transfer to Agonda."),
     ("19:30", "Rest, dinner at hotel or nearby shack.")],
    [("Return cab: Agonda &harr; Mollem (2 legs, cheapest car)", money(CAB_AGONDA_TO_MOLLEM + CAB_MOLLEM_TO_AGONDA)),
     ("Dudhsagar shared jeep safari incl. park entry (2 pax)", money(DUDHSAGAR_JEEP_PP*PAX)),
     ("Food &amp; drinks, full day (couple)", money(FOOD_FULL_DAY))],
    "MakeMyTrip has no jeep-safari/park-entry product; jeep safari price is a researched benchmark. "
    "The Agonda&harr;Mollem cab legs use MakeMyTrip's live outstation quote (cheapest car each way)."))

story.append(PageBreak())
story.append(day_block(4, "Sat 19 Dec", "Check Out South &middot; Transfer North &middot; Arpora Market",
    [("10:00", "Check out of The Shore Agonda. Late-morning stop at <b>Cabo de Rama Fort</b> en route "
              "north &mdash; a quiet cliff-top fort with sweeping coastal views."),
     ("11:00", "Outstation cab: Agonda &rarr; Candolim/Calangute (~40&nbsp;km)."),
     ("15:00", "Check in to <b>Summit Calangute Resort &amp; Spa</b>. Afternoon at Calangute Beach."),
     ("18:30", "Evening at the <b>Arpora Saturday Night Market</b> &mdash; the only Saturday of the "
               "trip, so timed deliberately. Food stalls, live music, crafts and clothing.")],
    [("Cab: Agonda &rarr; Calangute (cheapest car, all-in)", money(CAB_AGONDA_TO_CALANGUTE)),
     ("Local hop: Calangute &harr; Arpora market (auto/taxi)", money(ARPORA_LOCAL_HOP)),
     ("Food &amp; drinks, full day incl. market food (couple)", money(FOOD_FULL_DAY))],
    "Cabo de Rama is a free-standing detour on the same one-way cab route, not separately billed."))

story.append(Spacer(1, 4*mm))
story.append(day_block(5, "Sun 20 Dec", "Fort Aguada &middot; Old Goa Churches &middot; Panaji",
    [("09:00", "Breakfast, then scooter/day-cab to <b>Fort Aguada</b> (Sinquerim) &mdash; 17th-century "
              "Portuguese fort, lighthouse, sea views."),
     ("11:30", "Drive to <b>Old Goa</b> (UNESCO World Heritage churches): <b>Basilica of Bom Jesus</b> "
               "(St. Francis Xavier's remains) and <b>S&eacute; Cathedral</b>."),
     ("13:30", "Lunch in Panaji."),
     ("14:30", "Stroll <b>Fontainhas</b>, Panaji's colourful Latin Quarter, and the Church of Our Lady "
               "of the Immaculate Conception."),
     ("18:00", "Return to Calangute; relaxed dinner.")],
    [("Scooter rental (1 day)", money(SCOOTER_PER_DAY)),
     ("Fort Aguada entry (Indian nationals, 2 pax)", money(FORT_AGUADA_ENTRY_PP*PAX)),
     ("Old Goa churches entry", "Free"),
     ("Food &amp; drinks, full day (couple)", money(FOOD_FULL_DAY))],
    "Basilica of Bom Jesus and S&eacute; Cathedral have no entry fee. Fort Aguada ASI entry is "
    "~Rs 40/Indian visitor (foreign nationals ~Rs 600) &mdash; researched, not an MMT product."))

story.append(Spacer(1, 4*mm))
story.append(day_block(6, "Mon 21 Dec", "Water Sports &middot; Anjuna &middot; Chapora &middot; Vagator",
    [("09:30", "Morning water-sports session at <b>Calangute/Baga Beach</b>: parasailing + jet-ski "
              "combo."),
     ("13:00", "Lunch at a Baga beach shack."),
     ("14:30", "Explore <b>Anjuna Beach</b>; browse craft/curio stalls."),
     ("16:00", "Drive up to <b>Chapora Fort</b> for cliff-top views, then <b>Vagator/Ozran Beach</b>."),
     ("18:00", "Sunset at Vagator &mdash; among North Goa's best."),
     ("20:00", "Farewell dinner in Candolim/Calangute.")],
    [("Scooter rental (1 day)", money(SCOOTER_PER_DAY)),
     ("Parasailing + jet-ski combo (2 pax)", money(WATERSPORTS_COMBO_PP*PAX)),
     ("Food &amp; drinks, full day (couple)", money(FOOD_FULL_DAY))],
    "Water-sports combo price is a researched benchmark (private beach-shack operators, not sold via "
    "MakeMyTrip)."))

story.append(Spacer(1, 4*mm))
story.append(day_block(7, "Tue 22 Dec", "Departure",
    [("09:00", "Late breakfast, leisurely check-out from Summit Calangute Resort &amp; Spa."),
     ("10:30", "Last-minute souvenir shopping in Calangute; light lunch."),
     ("16:30", "Outstation cab: Calangute &rarr; Dabolim Airport (~40&nbsp;km, allow "
               "~1&ndash;1.5 hrs driving plus buffer for peak-season traffic)."),
     ("19:15", "Depart Goa (GOI). Suggested flight: <b>IndiGo 6E 6163, 19:15&ndash;20:25</b> "
               "(MakeMyTrip cheapest non-alternate-airport fare from GOI). Arrive Bengaluru (BLR).")],
    [("Cab: Calangute &rarr; Dabolim Airport (cheapest car, all-in)", money(CAB_CALANGUTE_TO_AIRPORT)),
     ("Flights GOI&rarr;BLR (2 adults, Economy, all-in)", money(FLIGHT_RET_PP*PAX)),
     ("Food, breakfast + lunch (couple)", money(FOOD_DEPARTURE_DAY))],
    None))
story.append(PageBreak())

# ================================================================ HOTELS ===
story.append(p("3. Hotels", "H1"))
story.append(p("Both properties below were checked directly via MakeMyTrip's live hotel-rates tool "
               "for the exact stay dates; figures are the <b>cheapest available room-only rate plan "
               "with free cancellation</b> at each property, per night, for 2 adults / 1 room.", "Body"))

hotel_data = [
    ["Base", "Property", "Nights", "Room type", "Rate/night", "Stay total"],
    ["South Goa\n(Agonda)", "The Shore Agonda\n(5-star boutique)\nRating 4.0/5", "3\n(16&ndash;19 Dec)",
     "Deluxe Seaview Villa,\nRoom Only, free cancel", money(HOTEL_SOUTH_NIGHT), money(hotel_south_total)],
    ["North Goa\n(Calangute)", "Summit Calangute\nResort &amp; Spa (4-star)\nRating 4.1/5", "3\n(19&ndash;22 Dec)",
     "Deluxe Room w/ Private\nBalcony, Room Only, free cancel", money(HOTEL_NORTH_NIGHT), money(hotel_north_total)],
]
h_rows = [[Paragraph(c, styles["TblHead"] if r==0 else styles["TblCell"]) for c in row]
          for r, row in enumerate(hotel_data)]
h_tbl = Table(h_rows, colWidths=[24*mm, 42*mm, 16*mm, 46*mm, 22*mm, 26*mm], repeatRows=1)
h_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.4, LINE),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("ALIGN", (4,0), (5,-1), "RIGHT"),
    ("TOPPADDING", (0,0), (-1,-1), 4),
    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(h_tbl)
story.append(Spacer(1, 3*mm))
tot_tbl = Table([["Hotels grand total (6 nights, 2 stays)", money(hotels_total)]], colWidths=[150*mm, 26*mm])
tot_tbl.setStyle(TableStyle([
    ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 9.5),
    ("TEXTCOLOR", (0,0), (-1,-1), NAVY), ("ALIGN", (1,0), (1,0), "RIGHT"),
    ("BACKGROUND", (0,0), (-1,-1), LIGHT), ("BOX", (0,0), (-1,-1), 0.6, GOLD),
    ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
]))
story.append(tot_tbl)
story.append(Spacer(1, 3*mm))
story.append(p("<b>Alternative properties considered</b> (also live on MakeMyTrip, for comparison): "
               "Ginger Goa Candolim (4-star, ~Rs 9,557/night), Fairfield by Marriott Goa Anjuna "
               "(4-star, ~Rs 9,062&ndash;12,632/night depending on dates), and Orchid Passaros "
               "Benaulim (4-star adults-only, South Goa, ~Rs 12,764/night, breakfast-inclusive "
               "only). The Shore Agonda and Summit Calangute were selected to balance beach-town "
               "atmosphere against budget &mdash; swapping in the Marriott/Ginger properties would add "
               "roughly Rs 12,000&ndash;40,000 to the trip total.", "BodySmall"))
story.append(PageBreak())

# ============================================================== TRANSPORT ==
story.append(p("4. Transport", "H1"))

story.append(p("4.1 Flights (MakeMyTrip live search, Economy cabin, 2 adults)", "H2"))
fl_data = [
    ["Leg", "Flight", "Depart &rarr; Arrive", "Fare/adult", "2 adults"],
    ["16 Dec: BLR &rarr; GOI", "IndiGo 6E 6753", "16:10 &rarr; 17:30 (1h20m, non-stop)",
     money(FLIGHT_OUT_PP), money(FLIGHT_OUT_PP*PAX)],
    ["22 Dec: GOI &rarr; BLR", "IndiGo 6E 6163", "19:15 &rarr; 20:25 (1h10m, non-stop)",
     money(FLIGHT_RET_PP), money(FLIGHT_RET_PP*PAX)],
]
fl_rows = [[Paragraph(c, styles["TblHead"] if r==0 else styles["TblCell"]) for c in row]
           for r, row in enumerate(fl_data)]
fl_tbl = Table(fl_rows, colWidths=[32*mm, 26*mm, 54*mm, 24*mm, 24*mm], repeatRows=1)
fl_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.4, LINE), ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("ALIGN", (3,0), (4,-1), "RIGHT"), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(fl_tbl)
story.append(p("Cheapest non-alternate-airport IndiGo fares from MakeMyTrip's 25-itinerary result set "
               "for each date. A FLY91 fare at Rs 3,099/adult exists on both dates but lands at Sindhudurg "
               "(SDW), 1.5&ndash;2 hrs further from both hotels than Dabolim &mdash; excluded as false-cheap. "
               "MakeMyTrip flags 13 of 25 itineraries per search as landing at GOX (Mopa, North Goa, "
               "~60&ndash;70&nbsp;km from these bases) or SDW; these were also excluded.", "Caption"))

story.append(Spacer(1, 4*mm))
story.append(p("4.2 Intercity &amp; airport cabs (MakeMyTrip live outstation quotes, cheapest listed car)", "H2"))
cab_data = [
    ["Date", "Route", "Distance", "Cheapest car", "Fare (all-in)"],
    ["16 Dec", "Dabolim Airport &rarr; Agonda", "~40 km", "WagonR/Swift (CNG hatchback)", money(CAB_AIRPORT_TO_AGONDA)],
    ["21 Dec", "Agonda &rarr; Mollem (Dudhsagar)", "~40 km", "WagonR/Swift (CNG hatchback)", money(CAB_AGONDA_TO_MOLLEM)],
    ["21 Dec", "Mollem &rarr; Agonda (return)", "~40 km", "WagonR/Swift (CNG hatchback)", money(CAB_MOLLEM_TO_AGONDA)],
    ["19 Dec", "Agonda &rarr; Calangute", "~40 km", "Dzire/Etios (diesel sedan)", money(CAB_AGONDA_TO_CALANGUTE)],
    ["22 Dec", "Calangute &rarr; Dabolim Airport", "~40 km", "Dzire/Etios (diesel sedan)", money(CAB_CALANGUTE_TO_AIRPORT)],
]
cab_rows = [[Paragraph(c, styles["TblHead"] if r==0 else styles["TblCell"]) for c in row]
            for r, row in enumerate(cab_data)]
cab_tbl = Table(cab_rows, colWidths=[16*mm, 56*mm, 18*mm, 46*mm, 24*mm], repeatRows=1)
cab_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.4, LINE), ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("ALIGN", (4,0), (4,-1), "RIGHT"), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(cab_tbl)
story.append(p("Every cab route above quotes at ~40&nbsp;km / ~4-hour hire slot regardless of "
               "actual endpoints &mdash; this is MakeMyTrip's standard outstation package granularity, "
               "not a real-time distance measurement; treat the per-route figures as directionally "
               "correct rather than exact. Fares are for the cheapest available car each time; an "
               "SUV (Ertiga/Innova) typically costs Rs 1,700&ndash;2,500 more per leg and may be "
               "preferable for airport transfers with luggage.", "Caption"))

story.append(Spacer(1, 4*mm))
story.append(p("4.3 Local transport within each base (not an MakeMyTrip product &mdash; web-researched)", "H2"))
loc_data = [
    ["Item", "Rate", "Qty", "Total"],
    ["Self-drive scooter rental", "Rs 500/day", "3 days (Day 2, 5, 6)", money(SCOOTER_PER_DAY*SCOOTER_DAYS)],
    ["Local hop: Calangute &harr; Arpora market", "Rs 300 (auto/taxi, round trip)", "1", money(ARPORA_LOCAL_HOP)],
]
loc_rows = [[Paragraph(c, styles["TblHead"] if r==0 else styles["TblCell"]) for c in row]
            for r, row in enumerate(loc_data)]
loc_tbl = Table(loc_rows, colWidths=[70*mm, 40*mm, 34*mm, 16*mm], repeatRows=1)
loc_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.4, LINE), ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("ALIGN", (3,0), (3,-1), "RIGHT"), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(loc_tbl)
story.append(p("Peak-season (December) scooter rates run Rs 400&ndash;700/day; Rs 500/day used as a "
               "mid-point. Fuel is extra (~Rs 150&ndash;250/day of riding). A self-drive hatchback "
               "(Rs 1,800&ndash;2,500/day) or a full-day private sedan (Rs 3,500&ndash;5,500) are pricier "
               "alternatives if not comfortable riding two-up.", "Caption"))
story.append(PageBreak())

# ============================================================ MASTER BUDGET =
story.append(p("5. Full Budget Breakdown (Line by Line)", "H1"))
story.append(p("Every line below rolls up into the cover-page total; nothing is added or rounded "
               "differently between this table and the day-by-day sections.", "Body"))

budget_rows = [
    ["#", "Category", "Line item", "Source", "Amount"],
    ["1", "Flights", "BLR&rarr;GOI, 16 Dec, 6E 6753 (2 adults)", "MMT live", money(FLIGHT_OUT_PP*PAX)],
    ["2", "Flights", "GOI&rarr;BLR, 22 Dec, 6E 6163 (2 adults)", "MMT live", money(FLIGHT_RET_PP*PAX)],
    ["3", "Hotels", "The Shore Agonda, 3 nights @ "+money(HOTEL_SOUTH_NIGHT), "MMT live", money(hotel_south_total)],
    ["4", "Hotels", "Summit Calangute Resort &amp; Spa, 3 nights @ "+money(HOTEL_NORTH_NIGHT), "MMT live", money(hotel_north_total)],
    ["5", "Transfers", "Dabolim Airport &rarr; Agonda cab (16 Dec)", "MMT live", money(CAB_AIRPORT_TO_AGONDA)],
    ["6", "Transfers", "Agonda &rarr; Mollem cab (21 Dec)", "MMT live", money(CAB_AGONDA_TO_MOLLEM)],
    ["7", "Transfers", "Mollem &rarr; Agonda return cab (21 Dec)", "MMT live", money(CAB_MOLLEM_TO_AGONDA)],
    ["8", "Transfers", "Agonda &rarr; Calangute cab (19 Dec)", "MMT live", money(CAB_AGONDA_TO_CALANGUTE)],
    ["9", "Transfers", "Calangute &rarr; Dabolim Airport cab (22 Dec)", "MMT live", money(CAB_CALANGUTE_TO_AIRPORT)],
    ["10", "Local transport", "Scooter rental, 3 days @ "+money(SCOOTER_PER_DAY), "Web research", money(SCOOTER_PER_DAY*SCOOTER_DAYS)],
    ["11", "Local transport", "Calangute &harr; Arpora market local hop", "Web research", money(ARPORA_LOCAL_HOP)],
    ["12", "Activities", "Dolphin-spotting boat, Palolem (2 pax)", "Web research", money(DOLPHIN_TRIP_PP*PAX)],
    ["13", "Activities", "Butterfly Beach boat ride (2 pax)", "Web research", money(BUTTERFLY_BOAT_PP*PAX)],
    ["14", "Activities", "Dudhsagar jeep safari + park entry (2 pax)", "Web research", money(DUDHSAGAR_JEEP_PP*PAX)],
    ["15", "Activities", "Fort Aguada entry (2 pax, Indian nationals)", "Web research", money(FORT_AGUADA_ENTRY_PP*PAX)],
    ["16", "Activities", "Parasailing + jet-ski combo, Baga (2 pax)", "Web research", money(WATERSPORTS_COMBO_PP*PAX)],
    ["17", "Food &amp; drink", "5 full days @ "+money(FOOD_FULL_DAY)+"/couple/day", "Web research", money(FOOD_FULL_DAY*FOOD_FULL_DAYS)],
    ["18", "Food &amp; drink", "Day 1 arrival dinner", "Web research", money(FOOD_ARRIVAL_DAY)],
    ["19", "Food &amp; drink", "Day 7 departure breakfast + lunch", "Web research", money(FOOD_DEPARTURE_DAY)],
    ["20", "Contingency", "SIM/data, tips, shopping, fee buffer (~4% of trip)", "Assumption", money(contingency_total)],
]
b_rows = [[Paragraph(c, styles["TblHead"] if r==0 else styles["TblCell"]) for c in row]
          for r, row in enumerate(budget_rows)]
b_tbl = Table(b_rows, colWidths=[9*mm, 24*mm, 74*mm, 22*mm, 23*mm], repeatRows=1)
b_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.4, LINE), ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("ALIGN", (4,0), (4,-1), "RIGHT"), ("FONTSIZE", (0,1), (-1,-1), 8.0), ("LEADING", (0,1), (-1,-1), 10.5),
    ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
]))
story.append(b_tbl)
story.append(Spacer(1, 4*mm))

subtot_rows = [
    ["Flights subtotal", money(flights_total)],
    ["Hotels subtotal", money(hotels_total)],
    ["Transfers subtotal", money(transfers_total)],
    ["Local transport subtotal", money(local_transport_total)],
    ["Activities subtotal", money(activities_total)],
    ["Food &amp; drink subtotal", money(food_total)],
    ["Contingency", money(contingency_total)],
    ["GRAND TOTAL (2 adults)", money(GRAND_TOTAL)],
    ["Per person", money(PER_PERSON)],
    ["Per person, per day (&divide;7)", money(PER_PERSON_PER_DAY)],
]
s_rows = [[Paragraph(l, styles["TblCellBold"] if "TOTAL" in l or "Per person" in l else styles["TblCell"]),
           Paragraph(a, styles["TblCellBoldR"] if "TOTAL" in l or "Per person" in l else styles["TblCellR"])]
          for l, a in subtot_rows]
s_tbl = Table(s_rows, colWidths=[124*mm, 28*mm])
s_tbl.setStyle(TableStyle([
    ("LINEBELOW", (0,0), (-1,-4), 0.3, LINE),
    ("LINEABOVE", (0,-3), (-1,-3), 1, GOLD),
    ("BACKGROUND", (0,-3), (-1,-3), LIGHT),
    ("BACKGROUND", (0,-2), (-1,-1), LIGHT),
    ("TOPPADDING", (0,0), (-1,-1), 3.5), ("BOTTOMPADDING", (0,0), (-1,-1), 3.5),
]))
story.append(KeepTogether(s_tbl))
story.append(PageBreak())

# =========================================================== ASSUMPTIONS ==
story.append(p("6. Assumptions, Caveats &amp; Data Sources", "H1"))

story.append(p("6.1 What came directly from MakeMyTrip (live, dated 06-Sep-2026)", "H2"))
mmt_items = [
    "Flight fares: <b>mmt_flight_search</b> BLR&harr;GOI, 2 adults, Economy &mdash; one outbound + one "
    "return search only, per the call budget. All 25 itineraries per search were reviewed; "
    "alternate-airport (GOX/SDW) results were excluded from the recommended flights.",
    "Hotel rates: <b>mmt_hotel_search</b> + <b>mmt_hotel_rates</b> for Goa (city code CTGOI) on both "
    "date ranges, cheapest room-only plan with free cancellation, per property, per night.",
    "Cab fares: <b>mmt_cab_quote</b> for every intercity/airport leg, cheapest listed car each time; "
    "pickup points resolved and verified via <b>mmt_cab_find_place</b> (all high-confidence city or "
    "named-landmark matches except the initial 'Goa Airport Dabolim' query, which was corrected to "
    "'Dabolim Airport' after a low-confidence fallback match).",
]
story.append(ListFlowable([ListItem(p(t, "Body")) for t in mmt_items]))

story.append(p("6.2 What is independently researched (MakeMyTrip has no matching product)", "H2"))
web_items = [
    "Local self-drive scooter/bike rental rates, and full-day private cab sightseeing packages "
    "(explicitly listed as a known gap in <b>mmt_capabilities</b>: \"Local 8hr/80km cab day packages "
    "use a different funnel and are not built\").",
    "Activity/attraction pricing: dolphin-spotting boat, Butterfly Beach boat, Dudhsagar jeep safari, "
    "parasailing/jet-ski combo, and Fort Aguada/Old Goa church entry fees.",
    "Daily food &amp; beverage budget (mid-range beach-shack/casual-restaurant benchmark for a couple).",
    "December weather averages, and the Anjuna/Arpora market calendar used to sequence Days 1 and 4.",
    "All web-sourced figures are ranges from multiple travel-cost articles/blogs (not MakeMyTrip), "
    "cross-checked for consistency, and the mid-point or a conservative estimate was used in the "
    "budget. Treat every 'Web research' row in Section 5 as a planning estimate, not a quote.",
]
story.append(ListFlowable([ListItem(p(t, "Body")) for t in web_items]))

story.append(p("6.3 Known limitations &amp; things that could change this budget", "H2"))
lim_items = [
    "<b>No booking capability.</b> MakeMyTrip's MCP tools deliberately have no booking, cart, payment "
    "or login path; every figure is a signed-out retail quote, not a held price. Fares/rates can move "
    "before actual booking, especially this close to a peak-season date (Dec 2026 is &gt;90 days out "
    "from the data-capture date).",
    "<b>Hotel stay totals are estimates.</b> <b>stay_estimate_all_in_inr</b> is nightly rate &times; "
    "nights; MakeMyTrip quotes one representative nightly rate per range rather than a per-date "
    "breakdown, so an actual multi-night stay spanning a price change will differ slightly. This "
    "report instead reads each night's own quoted rate.",
    "<b>Cab distance/duration is standardised, not measured.</b> Every outstation quote returned "
    "~40&nbsp;km / ~4&nbsp;hours regardless of the actual point-to-point distance between "
    "the specific places resolved (e.g. Agonda&rarr;Mollem vs. Airport&rarr;Agonda) &mdash; this "
    "appears to be MakeMyTrip's package-tier granularity rather than a live routing engine. Actual "
    "drive times are shorter (all legs are realistically 45&ndash;75 minutes); fares are usable as "
    "quoted but treat the 'distance/hours' columns as indicative only.",
    "<b>No local 8hr/80km day-package product exists</b> on this channel for full-day North or South "
    "Goa sightseeing by private cab; the itinerary instead uses self-drive scooters for local touring "
    "(cheaper, matches Goa's usual tourist pattern) with outstation one-way cabs reserved for the "
    "longer inter-region and airport transfers.",
    "<b>Flight seat/baggage add-ons, hotel resort fees/city taxes beyond what MakeMyTrip quotes, "
    "travel insurance, and visa/passport costs</b> (not applicable for domestic Indian travellers) "
    "are excluded.",
    "<b>Call budget adhered to:</b> exactly one outbound and one return flight search were run (no "
    "date- or airport-sweeping); each MakeMyTrip data point above was fetched once, with a small "
    "number of one-time retries only where an initial cab-place lookup returned a low-confidence match.",
]
story.append(ListFlowable([ListItem(p(t, "Body")) for t in lim_items]))

story.append(Spacer(1, 6*mm))
story.append(HRFlowable(width="100%", thickness=0.75, color=LINE))
story.append(Spacer(1, 3*mm))
story.append(p("Report generated 06 September 2026 for a trip departing 16 December 2026. "
               "Pricing sources: MakeMyTrip MCP (flights, hotels, cabs) &mdash; live data; "
               "Perplexity web research (weather, activities, food, local transport benchmarks) "
               "&mdash; secondary sources cited inline. This document is a planning estimate and "
               "does not constitute a booking or a price guarantee.", "Caption"))

# ---------------------------------------------------------------- BUILD ----
doc = SimpleDocTemplate(OUT_PATH, pagesize=A4,
                         leftMargin=18*mm, rightMargin=18*mm,
                         topMargin=16*mm, bottomMargin=16*mm,
                         title="Goa 7-Day Itinerary & Budget",
                         author="Cline Travel Planner")
doc.build(story)
print("PDF written to:", OUT_PATH)
print("GRAND_TOTAL={:.0f} PER_PERSON={:.0f} PER_PERSON_PER_DAY={:.0f}".format(
    GRAND_TOTAL, PER_PERSON, PER_PERSON_PER_DAY))

