"""Outstation cabs. Same RSC mechanism as trains.

Two facts that cost time to discover: the ~60-day limit is the date-picker widget and
not the endpoint (December prices today), and the from/to place objects must be
complete - a trimmed one, or one without place_id, returns zero cabs with HTTP 200.
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlparse

from . import config as C
from . import rsc
from .errors import BadInput, EmptyValid, UnregisteredPlace
from .fetch import get_text
from .router import CAB_PAGE

BUILTIN_PLACES: dict[str, dict[str, Any]] = {
    "kochi": {
        "locusV2Id": "CTCOK", "locusV2Type": "CITY",
        "address": "Cochin, Kerala, India",
        "latitude": 9.9312328, "longitude": 76.26730409999999,
        "place_id": "ChIJv8a-SlENCDsRkkGEpcqC1Qs", "is_city": True,
        "is_airport": False, "city": "Kochi", "country": "India",
        "country_code": "IN", "state": "Kerala", "city_type": "Leisure",
    },
    "rameswaram": {
        "locusV2Id": "CTXAE", "locusV2Type": "city",
        "address": "Rameswaram, Tamil Nadu, India",
        "latitude": 9.287583699999999, "longitude": 79.3129488,
        "place_id": "ChIJs_Ic5sTjATsRoWO9i7n5Z9Y", "is_city": True,
        "is_airport": False, "city": "Rameshwaram", "city_code": "XAE",
        "country": "India", "country_code": "IN", "state": "Tamil Nadu",
        "city_type": "Pilgrim",
    },
}

ALIASES = {"cochin": "kochi", "rameshwaram": "rameswaram", "ernakulam": "kochi"}

CAB_RE = re.compile(r'\{\s*"type"\s*:\s*"CAB"\s*,\s*"data"\s*:\s*\{')
SUMMARY_RE = re.compile(r'"summaryText"\s*:\s*"([^"]+)"')
DIST_RE = re.compile(r"\*?(\d[\d,]*)\s*Kms?\*?", re.I)
TIME_RE = re.compile(r"\*?(\d+)\s*hr", re.I)


def known_places() -> dict[str, dict[str, Any]]:
    saved = (C.load_data().get("cab_places") or {})
    return {**BUILTIN_PLACES, **saved}


def save_place(name: str, place: dict[str, Any]) -> None:
    data = C.load_data()
    data.setdefault("cab_places", {})[name.strip().lower()] = place
    C.save_data(data)


def resolve_place(name: str) -> dict[str, Any]:
    key = ALIASES.get((name or "").strip().lower(), (name or "").strip().lower())
    places = known_places()
    if key in places:
        return places[key]
    raise UnregisteredPlace(
        f"no cab place object registered for {name!r}",
        hint="MakeMyTrip needs a full place object including a Google place_id and "
             "publishes no autosuggest for it. Either call mmt_cab_find_place to "
             "harvest one by driving the site, or search the route once on "
             "makemytrip.com/cabs and paste the resulting URL into mmt_cab_add_place.",
        details={"known_places": sorted(places)})


def place_from_url(url: str) -> dict[str, dict[str, Any]]:
    """Extract from/to place objects from a cabs listing URL copied out of a browser.

    fromCity / toCity are ignored - verified redundant.
    """
    qs = parse_qs(urlparse(url).query)
    out: dict[str, dict[str, Any]] = {}
    for side in ("from", "to"):
        raw = (qs.get(side) or [None])[0]
        if not raw or raw == "null":
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("place_id"):
            out[side] = obj
    if not out:
        raise BadInput("no usable from/to place objects found in that URL",
                       hint="Copy the full URL from the cabs listing page after a "
                            "search, including the from= and to= parameters.")
    return out


def place_label(place: dict[str, Any]) -> str:
    """A human name for a place object.

    Harvested objects carry main_text/address but no `city` - the site fills that
    in from its own fetchLocation call - so reading `city` alone renders a route as
    "None -> None".
    """
    for key in ("city", "main_text"):
        val = place.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    addr = place.get("address")
    if isinstance(addr, str) and addr.strip():
        return addr.split(",")[0].strip()
    return "unknown"


def listing_url(origin: dict, dest: dict, iso_date: str, *, pickup_time: str = "10:00",
                trip_type: str = "OW", return_date: str = "") -> str:
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        raise BadInput("date must be ISO YYYY-MM-DD") from None
    params = {
        "tripType": trip_type,
        "departDate": d.strftime("%d-%m-%Y"),
        "pickupTime": pickup_time,
        "intlFlow": "false",
        "from": json.dumps(origin, separators=(",", ":")),
        "to": json.dumps(dest, separators=(",", ":")),
    }
    if return_date:
        rd = date.fromisoformat(return_date)
        params["returnDate"] = rd.strftime("%d-%m-%Y")
    # percent-encode spaces rather than using '+': the place objects are JSON blobs and
    # a '+' inside "Cochin, Kerala, India" is not reliably decoded back to a space.
    return C.CAB_LISTING + "?" + urlencode(params, quote_via=quote)


async def search(origin: str | dict, dest: str | dict, iso_date: str, *,
                 pickup_time: str = "10:00", trip_type: str = "OW",
                 return_date: str = "", fresh: bool = False) -> dict[str, Any]:
    o = origin if isinstance(origin, dict) else resolve_place(origin)
    d = dest if isinstance(dest, dict) else resolve_place(dest)
    url = listing_url(o, d, iso_date, pickup_time=pickup_time, trip_type=trip_type,
                      return_date=return_date)
    if trip_type == "RT" and not return_date:
        raise BadInput("trip_type RT requires a return_date.")

    # funnel_url: /cabs/listing is Akamai-stubbed for a browser that arrives cold.
    res = await get_text(url, ec=CAB_PAGE, wait_for="networkidle", fresh=fresh,
                         funnel_url=C.CAB_HOME, validate=body_valid)
    out = parse(res.text, url=url, iso_date=iso_date,
                route=f"{place_label(o)} -> {place_label(d)}")
    if not out["cab_count"]:
        raise EmptyValid(
            f"No cabs offered for {out['route']} on {iso_date}.",
            hint="If this route normally has cabs, the place objects may be stale - "
                 "re-harvest with mmt_cab_find_place.",
            details=out)
    out.update(res.meta())
    return out


def body_valid(html: str) -> bool:
    """A cabs listing is usable when it carries the RSC stream. Zero cabs (a stale place
    object, no vendors bidding) is a valid answer surfaced as EmptyValid; only a page
    with no RSC data (an interstitial) is unusable."""
    return bool(rsc.blob(html))


def parse(html: str, *, url: str = "", iso_date: str = "",
          route: str = "") -> dict[str, Any]:
    """Pure. Typed cards in the RSC stream: SEARCH_SUMMARY plus one CAB per quote."""
    blob = rsc.blob(html)
    cabs: list[dict[str, Any]] = []
    for card in rsc.iter_objects(blob, CAB_RE):
        data = card.get("data") or {}
        info = data.get("cabInfo") or {}
        fb = (data.get("priceInfo") or {}).get("fareBreakup") or {}
        cabs.append({
            "car": info.get("title"),
            "category": info.get("type"),
            "fuel": info.get("fuelIdentifier"),
            "seats": next((f.get("title") for f in (info.get("features") or [])
                           if "seat" in str(f.get("title", "")).lower()), None),
            "vendor": (data.get("supplierInfo") or {}).get("vendorName"),
            "base_inr": fb.get("basePrice"),
            "tax_fees_inr": fb.get("miscCharges"),
            "all_in_inr": fb.get("totalAmount"),
            "extra_per_km_inr": fb.get("perKmExtraCharge"),
        })

    sm = SUMMARY_RE.search(blob)
    summary = sm.group(1) if sm else ""
    km = DIST_RE.search(summary)
    hrs = TIME_RE.search(summary)
    distance = int(km.group(1).replace(",", "")) if km else None

    for c in cabs:
        if distance and isinstance(c.get("all_in_inr"), (int, float)):
            c["all_in_per_km_inr"] = round(c["all_in_inr"] / distance, 2)
    cabs.sort(key=lambda c: (c["all_in_inr"] is None, c["all_in_inr"] or 0))

    return {
        "route": route, "date": iso_date, "url": url,
        "distance_km": distance,
        "approx_hours": int(hrs.group(1)) if hrs else None,
        "cab_count": len(cabs), "cabs": cabs,
        "cheapest": cabs[0] if cabs else None,
    }
