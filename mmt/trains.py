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
    # Known names always win over the alpha-code guess - "goa" must resolve
    # to MAO via the dict, not bypass to the invalid code "GOA".
    code = C.STATIONS.get(n.lower())
    if code:
        return code
    if 2 <= len(n) <= 5 and n.isalpha():
        return n.upper()
    raise BadInput(f"unknown station {name!r}",
                   hint="Known: " + ", ".join(sorted(set(C.STATIONS))) +
                        ". Or pass a station code directly, e.g. MDU.")


def booking_opens(iso_date: str) -> str:
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        raise BadInput("date must be ISO YYYY-MM-DD") from None
    return (d - timedelta(days=ARP_DAYS)).isoformat()


def furthest_bookable(iso_date: str, today: date | None = None) -> str | None:
    """The latest date Indian Railways will quote right now, for the same weekday.

    A date past the 60-day reservation window has no fare, and until now the honest
    answer stopped there - so subjects substituted a web estimate for the rail leg or
    dropped it. There IS a real number available: the same route on the furthest date
    that is currently open. It is not the fare for the requested date and must never be
    presented as one, but it is MakeMyTrip data rather than a guess.

    Stepped back to match the requested date's weekday, because train schedules vary by
    day - a Tuesday service may not run on the boundary Friday, and comparing a fare
    against a train that does not run on your day would be worse than no fare at all.

    Returns None when the requested date is already bookable.
    """
    t = today or date.today()
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        raise BadInput("date must be ISO YYYY-MM-DD") from None
    boundary = t + timedelta(days=ARP_DAYS)
    if d <= boundary:
        return None
    step_back = (boundary.weekday() - d.weekday()) % 7
    candidate = boundary - timedelta(days=step_back)
    return (candidate if candidate >= t else boundary).isoformat()


def in_window(iso_date: str, today: date | None = None) -> bool:
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        # in_window runs before any fetch, so an unparseable date reached the caller
        # as a raw ValueError - kind "unexpected" - rather than as bad_input.
        raise BadInput("date must be ISO YYYY-MM-DD",
                       hint=f"Got {iso_date!r}. Example: 2026-12-15.") from None
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

    res = await get_text(url, ec=TRAIN_PAGE, wait_for="networkidle", fresh=fresh,
                         validate=body_valid)
    out = parse(res.text, url=url, iso_date=iso_date, src=src, dest=dest)
    out.update(res.meta())
    return out


def body_valid(html: str) -> bool:
    """A trains page is usable when it carries an RSC stream. A stream with zero trains
    (outside the window, or none on that route) is still a valid answer surfaced as
    NotInWindow/empty; only a page with no RSC data at all is an interstitial, not a
    result."""
    return bool(rsc.blob(html))


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
