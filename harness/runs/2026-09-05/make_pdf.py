#!/usr/bin/env python3
"""Render the Phase 2 acceptance-run itinerary to PDF.

Data-driven on purpose: every number in the output comes from the JSON file, so
the generator can never invent a fare. Each cost line carries a `source` that is
printed alongside it -- an MCP tool call (`mmt_*`) or a labelled web/estimate
source -- which is what the H-ARITH audit checks against.

    python harness/runs/2026-09-05/make_pdf.py itinerary-data.json goa-itinerary.pdf

Uses fpdf2 when importable and falls back to a plain-text .txt sibling otherwise.
No browser is involved.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None


def rupees(n: float) -> str:
    """Indian digit grouping, e.g. 1234567 -> 12,34,567."""
    neg, n = n < 0, abs(int(round(n)))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if neg else "") + "Rs " + s


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in ("trip", "legs", "costs") if k not in data]
    if missing:
        raise SystemExit(f"{path}: missing required key(s): {', '.join(missing)}")
    for i, c in enumerate(data["costs"]):
        for k in ("label", "amount", "source"):
            if k not in c:
                raise SystemExit(f"{path}: costs[{i}] missing '{k}' -- every "
                                 "amount must name where it came from")
    return data


def totals(data: dict) -> tuple[float, float]:
    grand = sum(float(c["amount"]) for c in data["costs"])
    adults = int(data["trip"].get("adults", 2))
    return grand, grand / adults


def render_text(data: dict) -> str:
    t = data["trip"]
    grand, per_person = totals(data)
    L: list[str] = []
    L.append(t.get("title", "Itinerary"))
    L.append("=" * len(L[0]))
    L.append(f"{t['start']} to {t['end']}  |  {t.get('adults', 2)} adults")
    if t.get("note"):
        L += ["", t["note"]]

    L += ["", "DAY BY DAY", "-" * 10]
    for leg in data["legs"]:
        L.append(f"{leg['date']}  {leg['title']}")
        for line in leg.get("detail", []):
            L.append(f"    {line}")

    L += ["", "COSTS", "-" * 5]
    width = max(len(c["label"]) for c in data["costs"])
    for c in data["costs"]:
        L.append(f"{c['label']:<{width}}  {rupees(c['amount']):>12}   [{c['source']}]")
    L.append("")
    L.append(f"{'GRAND TOTAL':<{width}}  {rupees(grand):>12}")
    L.append(f"{'PER PERSON (/' + str(t.get('adults', 2)) + ')':<{width}}  "
             f"{rupees(per_person):>12}")

    if data.get("unpriced"):
        L += ["", "NOT PRICED", "-" * 10] + [f"  - {u}" for u in data["unpriced"]]
    if data.get("sources"):
        L += ["", "SOURCES", "-" * 7] + [f"  {k}: {v}" for k, v in data["sources"].items()]
    return "\n".join(L) + "\n"


def render_pdf(data: dict, out: Path) -> Path:
    t = data["trip"]
    grand, per_person = totals(data)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, t.get("title", "Itinerary"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"{t['start']} to {t['end']}   |   {t.get('adults', 2)} adults",
             new_x="LMARGIN", new_y="NEXT")
    if t.get("note"):
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 5, t["note"])
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Day by day", new_x="LMARGIN", new_y="NEXT")
    for leg in data["legs"]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, f"{leg['date']}  -  {leg['title']}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for line in leg.get("detail", []):
            pdf.set_x(pdf.l_margin + 6)
            pdf.multi_cell(0, 5, line)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Costs", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(95, 6, "Item", border="B")
    pdf.cell(30, 6, "Amount", border="B", align="R")
    pdf.cell(0, 6, "Source", border="B", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for c in data["costs"]:
        pdf.cell(95, 6, c["label"])
        pdf.cell(30, 6, rupees(c["amount"]), align="R")
        pdf.cell(0, 6, c["source"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(95, 7, "Grand total", border="T")
    pdf.cell(30, 7, rupees(grand), border="T", align="R")
    pdf.cell(0, 7, "", border="T", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 6, f"Per person (/{t.get('adults', 2)})")
    pdf.cell(30, 6, rupees(per_person), align="R")
    pdf.cell(0, 6, "", new_x="LMARGIN", new_y="NEXT")

    if data.get("unpriced"):
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Not priced", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for u in data["unpriced"]:
            pdf.multi_cell(0, 5, f"- {u}")
    if data.get("sources"):
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Sources", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        for k, v in data["sources"].items():
            pdf.multi_cell(0, 4.5, f"{k}: {v}")

    pdf.output(str(out))
    return out


def main(argv: list[str]) -> int:
    src = Path(argv[1]) if len(argv) > 1 else HERE / "itinerary-data.json"
    out = Path(argv[2]) if len(argv) > 2 else HERE / "goa-itinerary.pdf"
    if not src.is_absolute():
        src = HERE / src
    if not out.is_absolute():
        out = HERE / out
    if not src.exists():
        raise SystemExit(f"no itinerary data at {src} -- Step 3 must run first")

    data = load(src)
    if FPDF is None:
        out = out.with_suffix(".txt")
        out.write_text(render_text(data), encoding="utf-8")
        print(f"fpdf2 not installed; wrote plain-text fallback {out}")
    else:
        render_pdf(data, out)
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
