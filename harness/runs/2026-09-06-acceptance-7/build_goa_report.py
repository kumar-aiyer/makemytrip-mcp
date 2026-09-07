# -*- coding: utf-8 -*-
"""
Builds a polished PDF itinerary + budget report for a 7-night Goa trip
(Bengaluru -> Goa -> Bengaluru), 16-23 Dec 2026, for 2 adults.
Pricing sourced from MakeMyTrip MCP (flights/trains/cabs/hotels) where marked [MMT],
and from Perplexity web research where marked [EST] (MMT has no local-day-package
or F&B/activity pricing funnel).
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                 HRFlowable, PageBreak, ListFlowable, ListItem, KeepTogether)
from reportlab.pdfgen import canvas

OUT = r"C:\Users\kumar\projects\claudecodeprojects\mmt-acceptance-workspace\Goa_Itinerary_Dec2026.pdf"

NAVY = colors.HexColor("#0b3d5c")
TEAL = colors.HexColor("#0d7377")
SAND = colors.HexColor("#f6efe3")
GOLD = colors.HexColor("#c9922b")
GREY = colors.HexColor("#666666")
LIGHT = colors.HexColor("#eef3f5")
RED = colors.HexColor("#a33b3b")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("TitleBig", fontName="Helvetica-Bold", fontSize=26, textColor=colors.white,
                           leading=30, alignment=TA_LEFT))
styles.add(ParagraphStyle("SubBig", fontName="Helvetica", fontSize=13, textColor=colors.white,
                           leading=17, alignment=TA_LEFT))
styles.add(ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=16, textColor=NAVY,
                           leading=20, spaceBefore=14, spaceAfter=6))
styles.add(ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=12.5, textColor=TEAL,
                           leading=16, spaceBefore=10, spaceAfter=4))
styles.add(ParagraphStyle("Body", fontName="Helvetica", fontSize=9.6, textColor=colors.black,
                           leading=13.5, spaceAfter=4))
styles.add(ParagraphStyle("BodySmall", fontName="Helvetica", fontSize=8.6, textColor=GREY,
                           leading=12, spaceAfter=3))
styles.add(ParagraphStyle("Tag", fontName="Helvetica-Bold", fontSize=7.6, textColor=colors.white,
                           leading=10, alignment=TA_CENTER))
styles.add(ParagraphStyle("CellHead", fontName="Helvetica-Bold", fontSize=8.6, textColor=colors.white,
                           leading=11))
styles.add(ParagraphStyle("Cell", fontName="Helvetica", fontSize=8.6, textColor=colors.black, leading=11.5))
styles.add(ParagraphStyle("CellBold", fontName="Helvetica-Bold", fontSize=8.8, textColor=NAVY, leading=11.5))
styles.add(ParagraphStyle("Note", fontName="Helvetica-Oblique", fontSize=8.4, textColor=GREY, leading=11.5,
                           spaceBefore=4, spaceAfter=4))
styles.add(ParagraphStyle("DayTitle", fontName="Helvetica-Bold", fontSize=12.5, textColor=colors.white,
                           leading=15))
styles.add(ParagraphStyle("DaySub", fontName="Helvetica", fontSize=9, textColor=colors.white, leading=12))


def fmt(n):
    return "Rs {:,.0f}".format(n)


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)

    def showPage(self):
        self.setFont("Helvetica", 8)
        self.setFillColor(GREY)
        self.drawString(20 * mm, 10 * mm,
                         "Goa Itinerary & Budget | Bengaluru <-> Goa | 16-23 Dec 2026")
        self.drawRightString(190 * mm, 10 * mm, "Page %d" % self._pageNumber)
        self.setStrokeColor(LIGHT)
        self.line(20 * mm, 13 * mm, 190 * mm, 13 * mm)
        canvas.Canvas.showPage(self)


def cover_page(story):
    header = Table([[Paragraph("GOA GETAWAY", styles["TitleBig"]),
                      Paragraph("Prepared: 6 Sep 2026", ParagraphStyle("d", parent=styles["SubBig"], alignment=2))],
                     [Paragraph("A 7-Night / 8-Day Itinerary &amp; Budget &mdash; Bengaluru to Goa to Bengaluru",
                                styles["SubBig"]), ""]],
                    colWidths=[130 * mm, 40 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("SPAN", (0, 1), (1, 1)),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(header)
    story.append(Spacer(1, 10))

    info = [
        ["Travelers", "2 adults"],
        ["Dates", "Wed 16 Dec 2026 to Wed 23 Dec 2026 (7 nights)"],
        ["Route", "Bengaluru (BLR) to Goa Dabolim (GOI) to Bengaluru (BLR)"],
        ["Base plan", "4 nights North Goa (Vagator) + 3 nights South Goa (Benaulim)"],
        ["Pricing sources", "MakeMyTrip MCP live quotes [MMT] for flights, hotels, intercity/point-to-point "
                            "cabs; web-researched benchmark rates [EST] for local day-hire transport, entry "
                            "fees, activities and meals, which MakeMyTrip does not expose via this tool"],
        ["Currency", "All figures in INR. Hotel figures are per-night rates x nights (an estimate, not a "
                     "locked total). Flight and cab figures show base + tax separately."],
    ]
    t = Table([[Paragraph("<b>{}</b>".format(k), styles["Body"]), Paragraph(v, styles["Body"])] for k, v in info],
               colWidths=[35 * mm, 135 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SAND),
        ("BOX", (0, 0), (-1, -1), 0.6, GOLD),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Trip at a glance", styles["H1"]))
    glance = [
        ["Grand total (2 adults, all-in)", "Rs 1,37,762"],
        ["Per person", "Rs 68,881"],
        ["Per day (party of 2, 8 days)", "approx Rs 17,220"],
        ["Flights (round-trip, 2 pax)", "Rs 23,452  [MMT]"],
        ["Hotels (7 nights, 1 room)", "Rs 71,130  [MMT]"],
        ["Transport - transfers & local hire", "Rs 15,880  [MMT + EST]"],
        ["Activities & sightseeing entries", "Rs 8,800  [EST]"],
        ["Dudhsagar Falls day-trip package", "Rs 5,500  [EST]"],
        ["Meals across 8 days (indicative)", "Rs 13,000  [EST]"],
    ]
    t2 = Table([[Paragraph(a, styles["Body"]), Paragraph("<b>{}</b>".format(b), styles["Body"])] for a, b in glance],
                colWidths=[110 * mm, 60 * mm])
    t2.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, LIGHT),
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t2)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "[MMT] = live indicative quote from the MakeMyTrip MCP tool on 6 Sep 2026, signed-out retail rate, "
        "subject to change and NOT a booking. [EST] = web-researched market benchmark used because MakeMyTrip's "
        "public search does not price that item (local full-day cab packages, entry tickets, activities, food). "
        "See \"Assumptions &amp; Data Sources\" at the end of this report for full detail.", styles["Note"]))
    story.append(PageBreak())


def day_bar(title, sub):
    t = Table([[Paragraph(title, styles["DayTitle"]), Paragraph(sub, styles["DaySub"])]],
               colWidths=[85 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    return t


def cost_table(rows, col_widths=(95 * mm, 30 * mm, 20 * mm)):
    """rows: list of (item, cost_str, tag) ; tag in {MMT, EST, INC}"""
    tag_color = {"MMT": TEAL, "EST": GOLD, "INC": GREY}
    data = [[Paragraph("Item", styles["CellHead"]), Paragraph("Cost (2 pax)", styles["CellHead"]),
             Paragraph("Source", styles["CellHead"])]]
    for item, cost, tag in rows:
        data.append([Paragraph(item, styles["Cell"]), Paragraph(cost, styles["Cell"]),
                     Paragraph(tag, styles["Tag"])])
    t = Table(data, colWidths=list(col_widths))
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, LIGHT),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ]
    for i, row in enumerate(rows, start=1):
        style.append(("BACKGROUND", (2, i), (2, i), tag_color.get(row[2], GREY)))
    t.setStyle(TableStyle(style))
    return t


def build_itinerary(story):
    story.append(Paragraph("Day-by-Day Itinerary", styles["H1"]))
    story.append(Paragraph(
        "Base: 2 adults. 4 nights North Goa (Vagator/Anjuna belt) + 3 nights South Goa (Benaulim/Colva belt), "
        "the split research consistently recommends for a 7-night December visit \u2013 North for forts, markets "
        "and nightlife, South for quieter beaches and a relaxed finish. One hotel change only, to avoid burning "
        "a travel day.", styles["Body"]))
    story.append(Spacer(1, 6))

    # DAY 1
    story.append(day_bar("Day 1 &middot; Wed 16 Dec", "Bengaluru &rarr; Goa &middot; check-in North Goa"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Fly IndiGo 6E&nbsp;6753, BLR 16:10 &rarr; GOI 17:30 (1h20m nonstop). Private cab from Dabolim Airport to "
        "Vagator (~40 km, ~70-90 min in evening traffic). Check in to <b>ibis Styles Goa Vagator</b>. Evening: "
        "stroll Vagator/Anjuna beachfront, dinner at a beach shack.", styles["Body"]))
    story.append(cost_table([
        ("Flight BLR&rarr;GOI, IndiGo 6E 6753, 2 adults (Economy)", fmt(12094), "MMT"),
        ("Airport transfer: Goa Airport &rarr; Vagator (sedan, ~40km/240min incl. buffer)", fmt(2045), "MMT"),
        ("Dinner, Day 1 (2 pax, casual beach shack)", fmt(1500), "EST"),
    ]))
    story.append(Spacer(1, 8))

    # DAY 2
    story.append(day_bar("Day 2 &middot; Thu 17 Dec", "North Goa beaches &middot; Forts"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Full-day local cab hire (8hr/80km) covering: Fort Aguada &amp; lighthouse, Candolim beach, Calangute "
        "and Baga beach, water sports session (parasailing + jet-ski + banana boat), sunset at Vagator's Chapora "
        "Fort (Dil Chahta Hai viewpoint). Dinner in Anjuna.", styles["Body"]))
    story.append(cost_table([
        ("Full-day local cab, 8hr/80km, North Goa sightseeing loop", fmt(3000), "EST"),
        ("Fort Aguada entry (2 pax)", fmt(100), "EST"),
        ("Water sports package: parasailing + jet-ski + banana boat (2 pax)", fmt(3600), "EST"),
        ("Meals, Day 2 (2 pax, breakfast/lunch/dinner)", fmt(2200), "EST"),
    ]))
    story.append(Spacer(1, 8))

    # DAY 3
    story.append(day_bar("Day 3 &middot; Fri 18 Dec", "Old Goa heritage &middot; Panaji"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Round-trip cab Vagator &rarr; Old Goa to see the UNESCO churches (Basilica of Bom Jesus, Se Cathedral), "
        "then on to Panaji: Fontainhas Latin quarter, Mandovi riverfront. Evening: Mandovi river sunset cruise "
        "with dinner and live music.", styles["Body"]))
    story.append(cost_table([
        ("Cab Vagator &rarr; Old Goa &rarr; Panaji &rarr; Vagator (sedan, half-day)", fmt(2145), "MMT"),
        ("Basilica of Bom Jesus / Old Goa churches entry (2 pax, largely free/donation)", fmt(100), "EST"),
        ("Mandovi river sunset cruise with dinner (2 pax)", fmt(5000), "EST"),
    ]))
    story.append(Spacer(1, 8))

    # DAY 4
    story.append(day_bar("Day 4 &middot; Sat 19 Dec", "Dudhsagar Falls day trip"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Early start for a shared-jeep safari to Dudhsagar Falls (Bhagwan Mahaveer Sanctuary), Goa's iconic "
        "four-tier waterfall \u2014 approx. 3hr each way including the jeep safari inside the reserve; return by "
        "evening. This is a day-package MakeMyTrip does not price directly, so the fee below is a market rate "
        "for a shared 4x4 safari + entry, inclusive of pickup/drop from North Goa.", styles["Body"]))
    story.append(cost_table([
        ("Dudhsagar Falls jeep safari day-trip, shared 4x4, pickup/drop incl. (2 pax)", fmt(5500), "EST"),
        ("Meals en route, Day 4 (2 pax, packed lunch + dinner)", fmt(1200), "EST"),
    ]))
    story.append(Spacer(1, 8))

    # DAY 5
    story.append(day_bar("Day 5 &middot; Sun 20 Dec", "Relocate North &rarr; South Goa"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Check out of Vagator late morning. En-route stop at Arpora / Mapusa for souvenirs if the Saturday "
        "Night Market timing doesn't align (it runs Sat evenings, so this trip's dates don't hit it \u2014 noted "
        "as a schedule constraint, not swapped for a substitute cost). Direct transfer south to Benaulim "
        "(~65-70 km, ~2 hours), check in to <b>Fairfield by Marriott Goa Benaulim</b>. Evening at leisure on "
        "Benaulim beach.", styles["Body"]))
    story.append(cost_table([
        ("Transfer Vagator &rarr; Benaulim (sedan, cross-Goa relocation)", fmt(2145), "MMT"),
        ("Meals, Day 5 (2 pax)", fmt(1800), "EST"),
    ]))
    story.append(Spacer(1, 8))

    # DAY 6
    story.append(day_bar("Day 6 &middot; Mon 21 Dec", "South Goa beaches &middot; Colva"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Full-day local cab hire covering South Goa's quieter belt: Colva beach, Betalbatim, Majorda, and a "
        "look at Cabo de Rama Fort viewpoint. Relaxed pace \u2014 fewer crowds than the North. Seafood dinner "
        "at a Colva shack.", styles["Body"]))
    story.append(cost_table([
        ("Full-day local cab, 8hr/80km, South Goa loop incl. Colva &amp; Cabo de Rama", fmt(3000), "EST"),
        ("Meals, Day 6 (2 pax, incl. seafood dinner)", fmt(2200), "EST"),
    ]))
    story.append(Spacer(1, 8))

    # DAY 7
    story.append(day_bar("Day 7 &middot; Tue 22 Dec", "Leisure day &middot; Benaulim/Varca"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Free day to relax by the resort pool/beach, optional spa session, or a short scooter ride to Varca "
        "and Fatrade beach. Kept deliberately light as a buffer day before the flight home \u2014 also absorbs any "
        "slippage from Day 4's Dudhsagar trip. Farewell dinner.", styles["Body"]))
    story.append(cost_table([
        ("Scooter rental, optional, full day (2 scooters)", fmt(1400), "EST"),
        ("Farewell dinner, Day 7 (2 pax, sit-down restaurant)", fmt(2800), "EST"),
    ]))
    story.append(Spacer(1, 8))

    # DAY 8
    story.append(day_bar("Day 8 &middot; Wed 23 Dec", "Goa &rarr; Bengaluru"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Check out of Fairfield Benaulim by late morning. Cab to Dabolim Airport (~30 km, ~45-60 min). Fly "
        "IndiGo 6E&nbsp;901, GOI 22:45 &rarr; BLR 23:55 (1h10m nonstop) \u2014 a late-evening return keeps the whole "
        "day free in Goa; earlier options exist (6E 6584 13:15, 6E 6163 19:15) at a similar fare if an earlier "
        "arrival into Bengaluru is preferred.", styles["Body"]))
    story.append(cost_table([
        ("Flight GOI&rarr;BLR, IndiGo 6E 901, 2 adults (Economy)", fmt(11358), "MMT"),
        ("Airport transfer: Benaulim &rarr; Goa Airport (sedan)", fmt(2145), "MMT"),
        ("Meals, Day 8 (2 pax, breakfast + airport snacks)", fmt(1300), "EST"),
    ]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Note on train &amp; road alternatives: MakeMyTrip's rail search for these dates falls outside the "
        "60-day IRCTC booking window (opens 17 &amp; 24 Oct 2026 respectively); indicative AC-class fares for a "
        "comparable date are Rs&nbsp;1,470&ndash;1,670 per couple one-way (8.5&ndash;9.5 hr) \u2014 cheaper than "
        "flying but 6-8x slower in transit time. A self-drive/outstation cab one-way runs "
        "Rs&nbsp;12,100&ndash;12,450 for the 603 km route \u2014 costlier AND slower than flying for this route, so "
        "flights are the clear choice both ways.", styles["Note"]))
    story.append(PageBreak())


def build_transport_section(story):
    story.append(Paragraph("Intercity Transport &ndash; Mode Comparison", styles["H1"]))
    story.append(Paragraph(
        "Priced via the MakeMyTrip MCP's combined intercity comparator for both legs (2 adults). Flight fares "
        "are per-adult and doubled for the party; cab fares are per-vehicle already. All rows below list base "
        "and tax separately as MakeMyTrip does. <b>Dominated</b> = both dearer and slower than another option "
        "on the same leg.", styles["Body"]))

    story.append(Paragraph("Leg 1: Bengaluru &rarr; Goa, 16 Dec 2026", styles["H2"]))
    rows1 = [
        ["Mode", "Option", "Depart-Arrive", "Duration", "Base", "Tax", "Total (2 pax)", "Dominated?"],
        ["Flight", "IndiGo 6E 6753 (chosen)", "16:10-17:30", "1h20m", "9,644", "2,450", "12,094", "No"],
        ["Flight", "IndiGo 6E 977", "20:50-22:10", "1h20m", "9,644", "2,450", "12,094", "No"],
        ["Flight", "IndiGo 6E 6583", "11:20-12:40", "1h20m", "10,244", "2,480", "12,724", "Yes"],
        ["Train", "16210 Ajmer Exp (CC)*", "00:03-08:28", "8h25m", "-", "-", "1,470", "No"],
        ["Train", "16589 Rani Chennamma (3E)*", "23:00-07:58", "8h58m", "-", "-", "1,670", "No"],
        ["Cab", "Sedan (Dzire/Etios)", "on request", "11h30m", "11,450", "957", "12,407", "Yes"],
        ["Cab", "Hatchback (WagonR/Swift)", "on request", "11h30m", "11,216", "945", "12,161", "Yes"],
    ]
    story.append(mode_table(rows1))
    story.append(Paragraph(
        "*Train fares are indicative \u2014 this route falls outside IRCTC's 60-day booking window until "
        "17 Oct 2026, so MakeMyTrip quoted the nearest priced date (4 Nov 2026, same weekday pattern) as a "
        "stand-in for comparison, not the 16 Dec fare itself. <b>Chosen: flight</b> \u2014 cab is both costlier "
        "and far slower (dominated); train is cheaper but ~7x the flight's in-vehicle time, losing most of "
        "Day 1.", styles["BodySmall"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Leg 2: Goa &rarr; Bengaluru, 23 Dec 2026", styles["H2"]))
    rows2 = [
        ["Mode", "Option", "Depart-Arrive", "Duration", "Base", "Tax", "Total (2 pax)", "Dominated?"],
        ["Flight", "IndiGo 6E 901 (chosen)", "22:45-23:55", "1h10m", "8,054", "3,304", "11,358", "No"],
        ["Flight", "IndiGo 6E 6584", "13:15-14:25", "1h10m", "8,654", "3,334", "11,988", "Yes"],
        ["Flight", "IndiGo 6E 6163", "19:15-20:25", "1h10m", "8,654", "3,334", "11,988", "Yes"],
        ["Train", "20675 Vishwamanav Exp (CC)*", "07:50-17:45", "9h55m", "-", "-", "1,570", "No"],
        ["Train", "16590 Rani Chennamma (3E)*", "19:20-06:20", "11h00m", "-", "-", "1,670", "No"],
        ["Cab", "Sedan (Dzire/Etios)", "on request", "11h30m", "11,400", "1,038", "12,438", "Yes"],
        ["Cab", "Hatchback (WagonR/Swift)", "on request", "11h30m", "11,165", "1,026", "12,191", "Yes"],
    ]
    story.append(mode_table(rows2))
    story.append(Paragraph(
        "*Same indicative-date caveat as Leg 1 (train booking opens 24 Oct 2026). <b>Chosen: flight</b> for the "
        "same reason \u2014 the late 22:45 departure is the cheapest of the three nonstops and still returns "
        "same-day, keeping Day 8 free for a relaxed checkout.", styles["BodySmall"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Local &amp; Point-to-Point Transport (within Goa)", styles["H2"]))
    rows3 = [
        ("Airport (GOI) &rarr; Vagator, Day 1", "Rs 2,045", "MMT"),
        ("Vagator &rarr; Old Goa/Panaji &rarr; Vagator, Day 3 (half-day)", "Rs 2,145", "MMT"),
        ("Vagator &rarr; Benaulim relocation, Day 5", "Rs 2,145", "MMT"),
        ("Benaulim &rarr; Goa Airport (GOI), Day 8", "Rs 2,145", "MMT"),
        ("Full-day local cab (8hr/80km), North Goa loop, Day 2", "Rs 3,000", "EST"),
        ("Full-day local cab (8hr/80km), South Goa loop, Day 6", "Rs 3,000", "EST"),
        ("Optional scooter rental x2, full day, Day 7", "Rs 1,400", "EST"),
    ]
    story.append(cost_table(rows3, col_widths=(105 * mm, 30 * mm, 20 * mm)))
    story.append(Paragraph(
        "MMT rows are live point-to-point cab quotes from the MakeMyTrip MCP (Savaari/Taxibazaar/Eroovo "
        "operators, sedan class chosen as the best price/comfort balance). EST rows are full-day 8hr/80km "
        "local hire packages, which MakeMyTrip's cab funnel does not price (it only prices point-to-point "
        "trips) \u2014 market rate of Rs 2,500-4,000/day is used per web research, and scooter rental at "
        "Rs 500-800/day/scooter.", styles["Note"]))
    story.append(PageBreak())


def mode_table(rows):
    header = rows[0]
    data = [[Paragraph(h, styles["CellHead"]) for h in header]]
    for r in rows[1:]:
        cells = [Paragraph(r[0], styles["Cell"]), Paragraph(r[1], styles["Cell"]), Paragraph(r[2], styles["Cell"]),
                  Paragraph(r[3], styles["Cell"]), Paragraph(r[4], styles["Cell"]), Paragraph(r[5], styles["Cell"]),
                  Paragraph("<b>{}</b>".format(r[6]), styles["Cell"]), Paragraph(r[7], styles["Cell"])]
        data.append(cells)
    t = Table(data, colWidths=[15*mm, 33*mm, 22*mm, 15*mm, 15*mm, 13*mm, 20*mm, 17*mm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, LIGHT),
        ("ALIGN", (4, 0), (6, -1), "RIGHT"),
        ("ALIGN", (7, 0), (7, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("FONTSIZE", (0, 0), (-1, -1), 7.6),
    ]
    for i, r in enumerate(rows[1:], start=1):
        if r[7] == "Yes":
            style.append(("TEXTCOLOR", (7, i), (7, i), RED))
            style.append(("FONTNAME", (7, i), (7, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(style))
    return t


def build_hotels_section(story):
    story.append(Paragraph("Hotels", styles["H1"]))
    story.append(Paragraph(
        "Both properties are 4-star, live-priced via the MakeMyTrip MCP hotel search &amp; rates tools for the "
        "exact travel dates, 1 room / 2 adults. Rates shown are the cheapest available rate plan at each "
        "property (room-only, non-refundable) plus the retail all-in nightly rate MakeMyTrip displays.",
        styles["Body"]))

    story.append(Paragraph("North Goa (16&ndash;20 Dec, 4 nights): ibis Styles Goa Vagator \u2013 An Accor Brand",
                            styles["H2"]))
    h1 = [
        ("Star rating / Guest review", "4-star / 4.4", "MMT"),
        ("Room type (cheapest)", "Standard Twin/Queen Room, Room Only", "MMT"),
        ("Nightly base", "Rs 6,163", "MMT"),
        ("Nightly tax", "Rs 557", "MMT"),
        ("Nightly all-in", "Rs 6,720", "MMT"),
        ("4-night stay estimate (all-in)", "Rs 26,880", "MMT"),
        ("Cancellation", "Non-refundable on cheapest plan; free-cancellation plan available at +Rs 395/night",
         "MMT"),
    ]
    story.append(cost_table(h1, col_widths=(95 * mm, 55 * mm, 15 * mm)))
    story.append(Paragraph(
        "Why Vagator: central to the Anjuna-Vagator-Baga-Calangute nightlife/beach belt, walkable to Chapora "
        "Fort, ~25 min from Old Goa/Panaji, ~40 min from the airport.", styles["BodySmall"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("South Goa (20&ndash;23 Dec, 3 nights): Fairfield by Marriott Goa Benaulim",
                            styles["H2"]))
    h2 = [
        ("Star rating / Guest review", "4-star / 4.5", "MMT"),
        ("Room type (cheapest)", "Fairfield Deluxe Queen, Free Cancellation, Room Only", "MMT"),
        ("Nightly base", "Rs 12,500", "MMT"),
        ("Nightly tax", "Rs 2,250", "MMT"),
        ("Nightly all-in", "Rs 14,750", "MMT"),
        ("3-night stay estimate (all-in)", "Rs 44,250", "MMT"),
        ("Cancellation", "Free cancellation before 15 Dec 2:59 PM on this plan", "MMT"),
    ]
    story.append(cost_table(h2, col_widths=(95 * mm, 55 * mm, 15 * mm)))
    story.append(Paragraph(
        "Why Benaulim: quiet upscale South Goa beach belt next to Colva &amp; Varca, ~30 min from the airport "
        "for an easy departure-day transfer. Higher-rated (4.5) than the North property and includes free "
        "cancellation on the booked plan, useful given the Dec-peak pricing volatility.", styles["BodySmall"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Combined stay total via MakeMyTrip's multi-stop pricer: <b>Rs 62,152 base + Rs 8,978 tax = "
        "Rs 71,130 all-in</b> for 7 nights, 1 room, 2 adults. This is an OTA retail benchmark, not a locked "
        "price \u2014 MakeMyTrip quotes one representative nightly rate per date range rather than a per-date "
        "breakdown, so actual booking totals may vary slightly, especially this close to Christmas week.",
        styles["Body"]))
    story.append(PageBreak())


def build_budget_summary(story):
    story.append(Paragraph("Consolidated Budget &ndash; Line by Line", styles["H1"]))
    story.append(Paragraph(
        "Every line item across the 8-day trip, in order incurred, for 2 adults. [MMT] rows are live "
        "MakeMyTrip MCP quotes fetched 6 Sep 2026; [EST] rows are web-researched market benchmarks for "
        "items MakeMyTrip's public tools do not price (local day-hire cabs, scooters, entry tickets, "
        "activities, meals).", styles["Body"]))
    rows = [
        ("Flight: BLR &rarr; GOI, IndiGo 6E 6753 (Day 1)", "Rs 12,094", "MMT"),
        ("Airport transfer: GOI &rarr; Vagator (Day 1)", "Rs 2,045", "MMT"),
        ("Dinner, Day 1", "Rs 1,500", "EST"),
        ("Full-day local cab, North Goa loop (Day 2)", "Rs 3,000", "EST"),
        ("Fort Aguada entry (Day 2)", "Rs 100", "EST"),
        ("Water sports package (Day 2)", "Rs 3,600", "EST"),
        ("Meals, Day 2", "Rs 2,200", "EST"),
        ("Cab: Vagator-Old Goa-Panaji-Vagator (Day 3)", "Rs 2,145", "MMT"),
        ("Old Goa churches entry (Day 3)", "Rs 100", "EST"),
        ("Mandovi sunset cruise with dinner (Day 3)", "Rs 5,000", "EST"),
        ("Dudhsagar Falls jeep safari day-trip (Day 4)", "Rs 5,500", "EST"),
        ("Meals en route, Day 4", "Rs 1,200", "EST"),
        ("Transfer: Vagator &rarr; Benaulim (Day 5)", "Rs 2,145", "MMT"),
        ("Meals, Day 5", "Rs 1,800", "EST"),
        ("Full-day local cab, South Goa loop (Day 6)", "Rs 3,000", "EST"),
        ("Meals, Day 6", "Rs 2,200", "EST"),
        ("Optional scooter rental x2 (Day 7)", "Rs 1,400", "EST"),
        ("Farewell dinner, Day 7", "Rs 2,800", "EST"),
        ("Flight: GOI &rarr; BLR, IndiGo 6E 901 (Day 8)", "Rs 11,358", "MMT"),
        ("Airport transfer: Benaulim &rarr; GOI (Day 8)", "Rs 2,145", "MMT"),
        ("Meals, Day 8", "Rs 1,300", "EST"),
        ("Hotel: ibis Styles Goa Vagator, 4 nights", "Rs 26,880", "MMT"),
        ("Hotel: Fairfield by Marriott Goa Benaulim, 3 nights", "Rs 44,250", "MMT"),
    ]
    story.append(cost_table(rows, col_widths=(115 * mm, 30 * mm, 20 * mm)))
    story.append(Spacer(1, 8))

    totals = [
        ["Flights (2 legs, 2 pax)", "Rs 23,452"],
        ["Hotels (7 nights)", "Rs 71,130"],
        ["Intercity/local transport (4 MMT transfers + 2 local-hire days + scooters)", "Rs 15,880"],
        ["Activities &amp; entries", "Rs 8,800"],
        ["Meals (8 days, indicative)", "Rs 13,000"],
        ["Dudhsagar Falls day-trip package", "Rs 5,500"],
        ["<b>GRAND TOTAL (2 adults)</b>", "<b>Rs 1,37,762</b>"],
        ["<b>Per person</b>", "<b>Rs 68,881</b>"],
        ["<b>Per day, party of 2 (8 days)</b>", "<b>Rs 17,220</b>"],
    ]
    t = Table([[Paragraph(a, styles["Body"]), Paragraph(b, ParagraphStyle("r", parent=styles["Body"],
               alignment=2))] for a, b in totals], colWidths=[130 * mm, 40 * mm])
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND", (0, -3), (-1, -1), SAND),
        ("LINEABOVE", (0, -3), (-1, -3), 1, GOLD),
    ]
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Budget flex: the figures above use mid-range choices throughout (4-star hotels, sedan cabs, "
        "moderate-priced activities). A leaner version \u2014 3-star hotels, shared local transport, skipping "
        "the Mandovi cruise and water sports \u2014 could bring the per-person figure down toward "
        "Rs 45,000-50,000. A more premium version (5-star resort stays, private car throughout, spa "
        "treatments) could push it past Rs 1,00,000 per person.", styles["Body"]))
    story.append(PageBreak())


def build_assumptions(story):
    story.append(Paragraph("Assumptions &amp; Data Sources", styles["H1"]))

    story.append(Paragraph("What came from MakeMyTrip (live, [MMT])", styles["H2"]))
    bullets_mmt = [
        "Flight fares: mmt_intercity_options, Bengaluru&harr;Goa, 2 adults, Economy, fetched 6 Sep 2026 for "
        "travel on 16 &amp; 23 Dec 2026. One flight search per direction, per the two-search call budget.",
        "Hotel rates: mmt_hotel_search + mmt_hotel_rates + mmt_price_itinerary for ibis Styles Goa Vagator and "
        "Fairfield by Marriott Goa Benaulim, 1 room / 2 adults, exact check-in/out dates.",
        "Point-to-point cab fares: mmt_intercity_options / mmt_cab_quote for Airport&harr;Vagator, "
        "Vagator&harr;Old Goa/Panaji, Vagator&harr;Benaulim, and Benaulim&harr;Airport, sedan class chosen "
        "(best price/comfort trade-off; hatchback is marginally cheaper, SUV is dominated on every leg).",
        "Train fares: same comparator, flagged indicative because 16 &amp; 23 Dec 2026 fall outside IRCTC's "
        "60-day reservation window (opens 17 &amp; 24 Oct 2026) &mdash; MakeMyTrip substituted the furthest "
        "currently-priced date on the same weekday pattern.",
    ]
    story.append(ListFlowable([ListItem(Paragraph(b, styles["Body"]), bulletColor=TEAL) for b in bullets_mmt],
                                bulletType="bullet", start="circle"))

    story.append(Paragraph("What was web-researched ([EST]) and why", styles["H2"]))
    bullets_est = [
        "Full-day (8hr/80km) local sightseeing cab hire: MakeMyTrip's cab tool prices point-to-point trips "
        "only, not day packages, per the tool's own documented gap. Substituted with a Perplexity-sourced "
        "market range of Rs 2,500-4,000/day; Rs 3,000 used.",
        "Scooter rental: not sold on MakeMyTrip; Rs 500-800/day/scooter market range used, Rs 700 x 2 assumed.",
        "Entry tickets (Fort Aguada, Old Goa churches), water sports, Mandovi cruise, Dudhsagar Falls jeep "
        "safari: none of these are inventoried on MakeMyTrip's searchable funnels (holiday packages there "
        "are quote-on-enquiry, not searchable). Perplexity web research supplied December-2026 market "
        "ranges; the midpoint or a slightly conservative figure was used in each case.",
        "Meals: no OTA prices day-to-day food. Estimated at Rs 600-1,400/meal-set per day per couple "
        "depending on whether a paid activity/dinner (cruise, farewell dinner) already includes food.",
    ]
    story.append(ListFlowable([ListItem(Paragraph(b, styles["Body"]), bulletColor=GOLD) for b in bullets_est],
                                bulletType="bullet", start="circle"))

    story.append(Paragraph("Key caveats", styles["H2"]))
    bullets_caveat = [
        "All MMT figures are signed-out retail rates captured on 6 Sep 2026 and are NOT a booking or a price "
        "lock. Hotel figures in particular are a representative nightly rate x nights, not a per-date "
        "breakdown, so a booking spanning a rate change will differ slightly from the estimate shown.",
        "December 16-23 is Goa's peak/Christmas-run-up season; all EST figures may run higher during the "
        "actual Christmas/New Year week (24 Dec onward), which this trip's dates avoid by ending on 23 Dec.",
        "Arpora's famous Saturday Night Market runs Saturday evenings; this itinerary's one Saturday (19 Dec) "
        "is dedicated to the Dudhsagar Falls day trip, so the market was consciously left out rather than "
        "priced as a substitute.",
        "This report contains no booking, cart or payment step of any kind &mdash; the MakeMyTrip MCP tool "
        "used deliberately has no such capability. All fares should be re-verified on MakeMyTrip or the "
        "airline/hotel/operator's own channel before purchase.",
        "Call budget used: 2 flight searches total (1 outbound BLR&rarr;GOI, 1 return GOI&rarr;BLR), no date "
        "or airport sweeping, each MCP call used at most once (no retries needed).",
    ]
    story.append(ListFlowable([ListItem(Paragraph(b, styles["Body"]), bulletColor=RED) for b in bullets_caveat],
                                bulletType="bullet", start="circle"))
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.6, color=LIGHT))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Report generated by an AI travel-planning assistant using the MakeMyTrip MCP server (live pricing) "
        "and Perplexity MCP (web research) on 6 September 2026, for a hypothetical booking window opening "
        "16 December 2026.", styles["BodySmall"]))


def main():
    doc = SimpleDocTemplate(OUT, pagesize=A4,
                             leftMargin=20 * mm, rightMargin=20 * mm,
                             topMargin=16 * mm, bottomMargin=18 * mm,
                             title="Goa Itinerary & Budget, Dec 2026", author="AI Travel Planner")
    story = []
    cover_page(story)
    build_itinerary(story)
    build_transport_section(story)
    build_hotels_section(story)
    build_budget_summary(story)
    build_assumptions(story)
    doc.build(story, canvasmaker=NumberedCanvas)
    print("PDF written to", OUT)


if __name__ == "__main__":
    main()
