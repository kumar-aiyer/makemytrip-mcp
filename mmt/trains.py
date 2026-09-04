"""Trains. The listing page IS the API - a Next.js App Router page whose RSC payload
carries every train, class and live availability.

The parameter names matter and are not guessable: date=YYYYMMDD, srcStn/destStn are
station codes, srcCity/destCity are cosmetic.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode

from . import config as C
from . import rsc
from .cache import STRUCTURAL_TTL
from .errors import BadInput, NotInWindow
from .fetch import get_text, post_json
from .router import TRAIN_PAGE

ARP_DAYS = 60   # Indian Railways advance reservation period

_DAYS = [("Mon", "runningMon"), ("Tue", "runningTue"), ("Wed", "runningWed"),
         ("Thu", "runningThu"), ("Fri", "runningFri"), ("Sat", "runningSat"),
         ("Sun", "runningSun")]


def resolve_station(name: str) -> str:
    n = (name or "").strip()
    if not n:
        raise BadInput("station is required")
    if 2 <= len(n) <= 5 and n.isalpha():
        return n.upper()
    code = C.STATIONS.get(n.lower())
    if not code:
        raise BadInput(f"unknown station {name!r}",
                       hint="Known: " + ", ".join(sorted(set(C.STATIONS))) +
                            ". Or pass a station code directly, e.g. MDU.")
    return code


def booking_opens(iso_date: str) -> str:
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        raise BadInput("date must be ISO YYYY-MM-DD") from None
    return (d - timedelta(days=ARP_DAYS)).isoformat()


def in_window(iso_date: str, today: date | None = None) -> bool:
    d = date.fromisoformat(iso_date)
    t = today or date.today()
    return 0 <= (d - t).days <= ARP_DAYS


def listing_url(src: str, dest: str, iso_date: str, *, class_code: str = "") -> str:
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        raise BadInput("date must be ISO YYYY-MM-DD") from None
    return C.TRAIN_LISTING + "?" + urlencode({
        "date": d.strftime("%Y%m%d"),
        "srcStn": src.upper(), "srcCity": "",
        "destStn": dest.upper(), "destCity": "",
        "classCode": class_code,
    })


async def search(src: str, dest: str, iso_date: str, *, class_code: str = "",
                 fresh: bool = False) -> dict[str, Any]:
    url = listing_url(src, dest, iso_date, class_code=class_code)

    def _valid(html: str) -> bool:
        table = rsc.chunks(rsc.blob(html))
        return any(isinstance(v, dict) and "trainNumber" in v for v in table.values())

    res = await get_text(url, ec=TRAIN_PAGE, wait_for="networkidle", fresh=fresh,
                         validate=_valid)
    out = parse(res.text, url=url, iso_date=iso_date, src=src, dest=dest)
    out.update(res.meta())
    return out


def parse(html: str, *, url: str = "", iso_date: str = "", src: str = "",
          dest: str = "") -> dict[str, Any]:
    """Pure. Unwrap the RSC stream and flatten trains plus per-class availability."""
    table = rsc.chunks(rsc.blob(html))
    trains: list[dict[str, Any]] = []
    seen: set[str] = set()

    for value in table.values():
        if not (isinstance(value, dict) and "trainNumber" in value):
            continue
        t = rsc.resolve(value, table)
        num = str(t.get("trainNumber"))
        if num in seen:
            continue
        seen.add(num)
        trains.append({
            "train_number": num,
            "train_name": t.get("trainName"),
            "from": t.get("frmStnCode"), "from_name": t.get("frmStnName"),
            "to": t.get("toStnCode"), "to_name": t.get("toStnName"),
            "departure": t.get("departureTime"), "arrival": t.get("arrivalTime"),
            "duration_min": t.get("duration"),
            "duration": _hhmm(t.get("duration")),
            "distance_km": t.get("distance"),
            "runs_on": _runs_on(t),
            "booking_allowed": t.get("bookingAllowed"),
            "classes": _classes(t),
        })

    trains.sort(key=lambda x: (x.get("departure") or "99:99"))
    return {
        "route": f"{src.upper()}-{dest.upper()}" if src else None,
        "date": iso_date, "url": url,
        "train_count": len(trains), "trains": trains,
    }


def _classes(t: dict) -> list[dict[str, Any]]:
    """Per-class availability.

    MakeMyTrip misspells these keys - availablityStatus / availablityDate, no second
    'i'. Spelling them correctly yields None for every train.
    """
    avail = t.get("tbsAvailability")
    if not isinstance(avail, list):
        return []
    out = []
    for a in avail:
        if not isinstance(a, dict):
            continue
        out.append({
            "class": a.get("classType"),
            "quota": a.get("quota"),
            "status": a.get("availablityStatus"),
            "status_pretty": a.get("prettyPrint"),
            "fare_inr": a.get("totalFare"),
            "confirm_probability_pct": _num(a.get("predictionPercentage")),
            "last_updated": a.get("lastUpdatedOn"),
        })
    out.sort(key=lambda c: (c["fare_inr"] is None, c["fare_inr"] or 0))
    return out


def _runs_on(t: dict) -> str:
    on = [label for label, k in _DAYS if t.get(k) == "Y"]
    return "daily" if len(on) == 7 else ",".join(on)


def _hhmm(minutes: Any) -> str | None:
    if not isinstance(minutes, (int, float)):
        return None
    m = int(minutes)
    return f"{m // 60}h {m % 60:02d}m"


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def station_to_city(src: str, dest: str, fresh: bool = False) -> dict[str, Any]:
    """Map station codes to MakeMyTrip city codes. Also validates the codes."""
    url = C.GET_LOCUS + "?" + urlencode({"from": src.upper(), "to": dest.upper()})
    res = await get_text(url, ec=TRAIN_PAGE, headers=None, fresh=fresh,
                         cache_ttl=STRUCTURAL_TTL)
    import json
    try:
        d = (json.loads(res.text) or {}).get("data") or {}
    except json.JSONDecodeError:
        from .errors import ShapeDrift
        raise ShapeDrift("getLocusId returned non-JSON.") from None
    return {
        "from_station": d.get("fromLobCode") or src.upper(),
        "from_city_code": d.get("fromLocusCode") or d.get("sourceCityLocusV2Id"),
        "to_station": d.get("toLobCode") or dest.upper(),
        "to_city_code": d.get("toLocusCode") or d.get("destinationCityLocusV2Id"),
        **res.meta(),
    }
