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


# Air-conditioned classes, seated and sleeper. Observed live on this corridor: 1A, 2A,
# 3A, 3E, CC alongside the non-AC SL and 2S. EC/EA/EV/EM are the Vande Bharat and Tejas
# chair cars. FC (First Class) is deliberately absent - it is not air-conditioned.
AC_SLEEPER_CLASSES = frozenset({"1A", "2A", "3A", "3E"})
AC_SEATED_CLASSES = frozenset({"CC", "EC", "EA", "EV", "EM"})
AC_CLASSES = AC_SLEEPER_CLASSES | AC_SEATED_CLASSES

VANDE_BHARAT_RE = re.compile(r"vande\s*bharat", re.I)

# How much slower than the quickest train on the route still counts as "fast". Relative
# on purpose: an absolute km/h threshold that suits a 550 km corridor is wrong for a
# 2,000 km one, and the useful question is always "slow compared to what is on offer".
FAST_FACTOR = 1.25


def is_ac_class(code: Any) -> bool:
    return str(code or "").strip().upper() in AC_CLASSES


def ac_classes(train: dict[str, Any]) -> list[dict[str, Any]]:
    """Priced A/C classes only. Drops the null-class junk rows the listing carries."""
    return [c for c in (train.get("classes") or [])
            if is_ac_class(c.get("class"))
            and isinstance(c.get("fare_inr"), (int, float)) and c["fare_inr"] > 0]


def is_vande_bharat(train: dict[str, Any]) -> bool:
    return bool(VANDE_BHARAT_RE.search(str(train.get("train_name") or "")))


def avg_kmph(train: dict[str, Any]) -> float | None:
    """Average speed, which is the only defensible way to call a train fast: it comes
    from the timetable rather than from the name."""
    km, mins = train.get("distance_km"), train.get("duration_min")
    try:
        km, mins = float(km), float(mins)
    except (TypeError, ValueError):
        return None
    return round(km / (mins / 60), 1) if mins > 0 and km > 0 else None


def filter_trains(trains: list[dict[str, Any]], *, ac_only: bool = True,
                  fast_only: bool = True,
                  fast_factor: float = FAST_FACTOR) -> tuple[list[dict[str, Any]], dict]:
    """Keep the trains a traveller would actually consider, and say what was dropped.

    `ac_only` keeps trains offering a priced air-conditioned class, seated or sleeper -
    an unreserved 2S seat for nine hours is not a comparable to a flight. `fast_only`
    keeps those within `fast_factor` of the quickest survivor on the route.

    Vande Bharat services are marked rather than privileged here; ordering is the
    caller's business, and a filter that silently promoted one would be making a
    judgement instead of reporting a fact.

    Returns (kept, summary) - the summary is what makes the filter honest, because a
    caller can see how many options were removed and why.
    """
    total = len(trains)
    kept = list(trains)
    dropped_non_ac = 0
    if ac_only:
        with_ac = [t for t in kept if ac_classes(t)]
        dropped_non_ac = len(kept) - len(with_ac)
        kept = with_ac

    dropped_slow = 0
    fastest = None
    durations = [t.get("duration_min") for t in kept
                 if isinstance(t.get("duration_min"), (int, float))
                 and t["duration_min"] > 0]
    if fast_only and durations:
        fastest = min(durations)
        limit = fastest * fast_factor
        quick = [t for t in kept
                 if not isinstance(t.get("duration_min"), (int, float))
                 or t["duration_min"] <= limit]
        dropped_slow = len(kept) - len(quick)
        kept = quick

    for train in kept:
        train["vande_bharat"] = is_vande_bharat(train)
        train["avg_kmph"] = avg_kmph(train)

    return kept, {
        "considered": total, "kept": len(kept),
        "dropped_no_ac_class": dropped_non_ac,
        "dropped_slower_than_limit": dropped_slow,
        "fastest_min": fastest,
        "fast_factor": fast_factor if fast_only else None,
        "ac_classes": sorted(AC_CLASSES),
        "note": "Filtered to trains offering a priced A/C class (seated or sleeper) and "
                "within {}x the quickest on the route. Unfiltered results are available "
                "with ac_only/fast_only false.".format(fast_factor),
    }


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
