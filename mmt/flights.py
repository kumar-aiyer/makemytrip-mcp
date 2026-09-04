"""Flights.

A GET with query parameters, streamed. Gated on three headers (mcid, device-id,
app-ver) that are NOT signed - a synthetic UUID satisfies them. In a browser page the
app-ver header trips CORS preflight; tier 1 is not a page origin, so it does not.

The response is a stream of concatenated JSON documents, not one object. The itinerary
field names below are INFERRED and unproven against a live payload - capture_mode=True
saves the raw stream to a fixture so the parser can be rewritten from reality.
"""
from __future__ import annotations

import time
import uuid
from datetime import date
from typing import Any, Iterator
from urllib.parse import urlencode

from . import config as C
from . import rsc
from .errors import BadInput
from .fetch import get_text
from .router import FLIGHT_API


def resolve_airport(name: str) -> str:
    n = (name or "").strip()
    if len(n) == 3 and n.isalpha():
        return n.upper()
    code = C.AIRPORTS.get(n.lower())
    if not code:
        raise BadInput(f"unknown airport {name!r}",
                       hint="Pass an IATA code (BLR, IXE, COK) or one of: " +
                            ", ".join(sorted(set(C.AIRPORTS))))
    return code


def search_url(origin: str, dest: str, iso_date: str, *, adults: int = 2,
               children: int = 0, infants: int = 0, cabin: str = "E") -> str:
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        raise BadInput("date must be ISO YYYY-MM-DD") from None
    params = {
        "it": f"{origin.upper()}-{dest.upper()}-{d.strftime('%Y%m%d')}",
        "pax": f"A-{adults}_C-{children}_I-{infants}",
        "cc": cabin, "cur": "INR", "currency": "INR",
        "region": "in", "language": "eng", "pfm": "DESKTOP", "sortBy": "rhino",
        "forwardFlowRequired": "true", "shd": "true", "dfs": "0", "safs": "st_0:0",
        "crId": str(uuid.uuid4()), "apiCallTimestamp": str(int(time.time() * 1000)),
        "cmpId": "", "creditShellInfo": "", "src": "",
    }
    return C.FLIGHT_SEARCH + "?" + urlencode(params)


async def search(origin: str, dest: str, iso_date: str, *, adults: int = 2,
                 children: int = 0, infants: int = 0, cabin: str = "E",
                 max_results: int = 25, fresh: bool = False) -> dict[str, Any]:
    url = search_url(origin, dest, iso_date, adults=adults, children=children,
                     infants=infants, cabin=cabin)
    res = await get_text(url, ec=FLIGHT_API, headers=C.flight_headers(), fresh=fresh,
                         timeout=60.0)
    itineraries = parse_stream(res.text, max_results)
    out: dict[str, Any] = {
        "route": f"{origin.upper()}-{dest.upper()}",
        "date": iso_date,
        "pax": f"A-{adults}_C-{children}_I-{infants}",
        "cabin": cabin,
        "parsed_count": len(itineraries),
        "itineraries": itineraries,
        "raw_len": len(res.text),
    }
    if not itineraries:
        # Not an error: return enough to fix the parser rather than claiming no flights.
        out["raw_head"] = res.text[:2000]
        out["warning"] = (
            "The stream returned data but no itineraries were recognised. The parser's "
            "field names are inferred, not verified. Save raw_head to "
            "tests/fixtures/flight_stream.json and rewrite parse_stream from it.")
    out.update(res.meta())
    return out


def iter_json_objects(text: str) -> Iterator[dict]:
    """Yield every balanced top-level {...} in the concatenated stream."""
    i = 0
    n = len(text)
    while i < n:
        j = text.find("{", i)
        if j < 0:
            return
        raw = rsc.balanced(text, j)
        if not raw:
            return
        i = j + len(raw)
        try:
            import json
            yield json.loads(raw)
        except Exception:
            continue


def _walk(obj: Any) -> Iterator[dict]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def parse_stream(text: str, max_results: int = 25) -> list[dict[str, Any]]:
    """INFERRED shapes. Replace wholesale once a real payload exists."""
    found: list[dict[str, Any]] = []
    for doc in iter_json_objects(text):
        for node in _walk(doc):
            if not ({"legs", "segments", "flights"} & set(node.keys())):
                continue
            fare = _num(node, ("totalFare", "fare", "amount", "price", "displayFare",
                               "tf"))
            if fare is None:
                continue
            found.append({
                "fare_inr": fare,
                "airline": _str(node, ("airlineName", "airline", "carrier",
                                       "airlineCode")),
                "flight_no": _str(node, ("flightNumber", "fltNo", "number")),
                "depart": _str(node, ("departureTime", "depTime", "dt")),
                "arrive": _str(node, ("arrivalTime", "arrTime", "at")),
                "duration": _str(node, ("duration", "totalDuration", "dur")),
                "stops": node.get("stops") if isinstance(node.get("stops"), int) else None,
            })

    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for it in sorted(found, key=lambda x: x["fare_inr"]):
        k = (it["airline"], it["flight_no"], it["depart"], it["fare_inr"])
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
        if len(out) >= max_results:
            break
    return out


def _num(node: dict, keys) -> float | None:
    for k in keys:
        v = node.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, dict):
            for kk in ("amount", "total", "value", "displayAmount"):
                if isinstance(v.get(kk), (int, float)):
                    return float(v[kk])
    return None


def _str(node: dict, keys) -> str | None:
    for k in keys:
        v = node.get(k)
        if isinstance(v, str) and v:
            return v
    return None
