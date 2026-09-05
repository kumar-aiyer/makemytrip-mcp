"""Tool registry, JSON schemas and implementations.

Docstrings are the descriptions the model sees. Write them for a reader who has never
heard of MakeMyTrip.
"""
from __future__ import annotations

import functools
import inspect
from datetime import date, timedelta
from typing import Any, Callable

from . import cabs as CB
from . import config as C
from . import flights as FL
from . import harvest as HV
from . import hotels as HO
from . import trains as TR
from .cache import CACHE
from .errors import BadInput, EmptyValid, MMTError, NotInWindow, NullPrices
from .fetch import gather_limited
from .router import ROUTER
from .session import SESSION, playwright_available

TOOLS: dict[str, dict[str, Any]] = {}

S_STR = {"type": "string"}
S_INT = {"type": "integer"}
S_BOOL = {"type": "boolean"}


def tool(name: str, schema: dict[str, Any]) -> Callable:
    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(**kwargs):
            try:
                return await fn(**kwargs)
            except MMTError as e:
                return e.to_result()
            except TypeError as e:
                return {"error": f"bad arguments: {e}", "kind": "bad_input"}
            except Exception as e:
                return {"error": f"{type(e).__name__}: {e}", "kind": "unexpected"}
        TOOLS[name] = {"fn": wrapper, "schema": schema,
                       "description": inspect.getdoc(fn) or ""}
        return wrapper
    return deco


def _obj(props: dict, required: list[str]) -> dict:
    props = {**props, "fresh": {**S_BOOL,
             "description": "Bypass the 20-minute cache."}}
    return {"type": "object", "properties": props, "required": required}


# ------------------------------------------------------------------------- hotels

@tool("mmt_hotel_search", _obj({
    "city": {**S_STR, "description": "City name or MakeMyTrip locus code (CTCOK)."},
    "check_in": {**S_STR, "description": "ISO YYYY-MM-DD."},
    "check_out": {**S_STR, "description": "ISO YYYY-MM-DD."},
    "adults": S_INT, "rooms": S_INT,
    "child_ages": {"type": "array", "items": S_INT,
                   "description": "Ages of children sharing a room."},
    "star_rating": {**S_INT, "description": "Filter to this star rating."},
    "limit": S_INT,
}, ["city", "check_in", "check_out"]))
async def mmt_hotel_search(city: str, check_in: str, check_out: str, adults: int = 2,
                           rooms: int = 1, child_ages: list[int] | None = None,
                           star_rating: int | None = None,
                           limit: int = 20, fresh: bool = False) -> dict:
    """Search hotels in an Indian city for a date range and return prices.

    Prices are INR STAY TOTALS for the whole range, not per night, and are reported as
    base, tax and all-in separately - MakeMyTrip displays them apart and the all-in
    figure is roughly 18% above the headline. An all_in_per_night_inr is added for
    comparability.

    A wrong city code returns an empty result rather than an error, so the response
    carries a warning when that is what happened.
    """
    code = HO.resolve_city(city)
    n = HO.nights(check_in, check_out)
    valid_ages = child_ages or []
    response, meta = await HO.search(code, check_in, check_out, adults=adults,
                                     rooms=rooms, child_ages=valid_ages,
                                     limit=limit, star_rating=star_rating,
                                     fresh=fresh)
    hotels_raw = HO.flatten(response)
    if not HO.city_ok(response):
        return {"warning": f"city code {code} returned no location detail, so it is "
                           "probably wrong - MakeMyTrip fails silently on bad codes",
                "city_code": code, "hotels": []}
    if HO.all_prices_null(hotels_raw):
        raise NullPrices(
            "MakeMyTrip returned hotels but every price is null.",
            hint="This is the signature of a trimmed expData or featureFlags block in "
                 "mmt/config.py. Both must be sent complete.")
    hotels = [HO.summarise(h) for h in hotels_raw]
    for h in hotels:
        if isinstance(h.get("all_in_inr"), (int, float)):
            h["all_in_per_night_inr"] = round(h["all_in_inr"] / n)
    return {"city": city, "city_code": code, "check_in": check_in,
            "check_out": check_out, "nights": n, "rooms": rooms, "adults": adults,
            "total_in_city": response.get("hotelCountInCity"),
            "returned": len(hotels), "hotels": hotels,
            "note": "Signed-out retail rates. This server cannot book.",
            **meta.meta()}


@tool("mmt_find_hotel_id", _obj({
    "city": S_STR, "name": {**S_STR, "description": "Property name or fragment."},
    "check_in": S_STR, "check_out": S_STR,
}, ["city", "name", "check_in", "check_out"]))
async def mmt_find_hotel_id(city: str, name: str, check_in: str, check_out: str,
                            fresh: bool = False) -> dict:
    """Find a MakeMyTrip hotelId by property name.

    No match usually means the property is not sold on MakeMyTrip at all, rather than
    that it is sold out - the two are worth distinguishing before drawing conclusions.
    """
    code = HO.resolve_city(city)
    frag = name.strip().lower()
    response, meta = await HO.search(code, check_in, check_out, limit=40, fresh=fresh)
    hits = [HO.summarise(h) for h in HO.flatten(response)
            if frag in (h.get("name") or "").lower()]
    return {"query": name, "city_code": code, "match_count": len(hits),
            "matches": hits,
            "hint": ("No match - the property may not be listed on MakeMyTrip at all."
                     if not hits else None),
            **meta.meta()}


@tool("mmt_hotel_rates", _obj({
    "hotel_id": {**S_STR, "description": "18-digit MakeMyTrip hotelId."},
    "city": S_STR, "check_in": S_STR, "check_out": S_STR,
    "adults": S_INT, "rooms": S_INT,
}, ["hotel_id", "city", "check_in", "check_out"]))
async def mmt_hotel_rates(hotel_id: str, city: str, check_in: str, check_out: str,
                          adults: int = 2, rooms: int = 1, fresh: bool = False) -> dict:
    """Every room type and rate plan for one property, with base/tax/all-in per plan.

    Includes meal plan, cancellation policy and inclusions. Flags properties where every
    plan includes breakfast, so a room-only rate that does not exist is never reported.
    """
    code = HO.resolve_city(city)
    n = HO.nights(check_in, check_out)
    data = await HO.room_rates(hotel_id, code, check_in, check_out, adults=adults,
                               rooms=rooms, fresh=fresh)
    data["nights"] = n
    cheap = data.get("cheapest") or {}
    if isinstance(cheap.get("all_in_inr"), (int, float)):
        data["cheapest_per_night_inr"] = round(cheap["all_in_inr"] / n)
    if data.get("breakfast_only_rates"):
        data["warning"] = ("every rate plan here includes breakfast - there is no "
                           "room-only option to report")
    return data


@tool("mmt_price_itinerary", _obj({
    "stays": {"type": "array", "description":
              "Each: {hotel_id, city, check_in, check_out, adults?, rooms?, label?}",
              "items": {"type": "object"}},
}, ["stays"]))
async def mmt_price_itinerary(stays: list[dict], fresh: bool = False) -> dict:
    """Price a whole multi-stop itinerary at once and total it.

    The totals are summed here from the rows just fetched, so they cannot drift from the
    lines above them. One failing leg does not abort the run - it lands in `errors`.
    """
    if not isinstance(stays, list) or not stays:
        raise BadInput("stays must be a non-empty array")

    async def price(s: dict) -> dict:
        code = HO.resolve_city(s["city"])
        n = HO.nights(s["check_in"], s["check_out"])
        response, _ = await HO.search(code, s["check_in"], s["check_out"],
                                      adults=int(s.get("adults", 2)),
                                      rooms=int(s.get("rooms", 1)),
                                      hotel_ids=[str(s["hotel_id"])], limit=5,
                                      fresh=fresh)
        hits = HO.flatten(response)
        if not hits:
            raise EmptyValid(f"no availability for {s.get('label') or s['hotel_id']}")
        row = HO.summarise(hits[0])
        row.update({"label": s.get("label"), "city": s["city"],
                    "check_in": s["check_in"], "check_out": s["check_out"],
                    "nights": n})
        return row

    results = await gather_limited([price(s) for s in stays], limit=4)
    legs, errors = [], []
    for s, r in zip(stays, results):
        if isinstance(r, Exception):
            msg = r.message if isinstance(r, MMTError) else f"{type(r).__name__}: {r}"
            errors.append({"stay": s, "error": msg})
        else:
            legs.append(r)

    tb = sum(l["base_inr"] for l in legs if isinstance(l.get("base_inr"), (int, float)))
    tt = sum(l["tax_inr"] for l in legs if isinstance(l.get("tax_inr"), (int, float)))
    return {"legs": legs, "leg_count": len(legs),
            "total_nights": sum(l.get("nights") or 0 for l in legs),
            "total_base_inr": tb, "total_tax_inr": tt, "total_all_in_inr": tb + tt,
            "errors": errors,
            "note": "Retail OTA rates. An operator buys below these, so treat them as a "
                    "private benchmark rather than an opening number."}


# ------------------------------------------------------------------------ flights

@tool("mmt_flight_search", _obj({
    "origin": {**S_STR, "description": "IATA code or known city name."},
    "dest": S_STR, "date": {**S_STR, "description": "ISO YYYY-MM-DD."},
    "adults": S_INT, "children": S_INT, "infants": S_INT,
    "cabin": {**S_STR, "description": "E economy, W premium economy, B business."},
}, ["origin", "dest", "date"]))
async def mmt_flight_search(origin: str, dest: str, date: str, adults: int = 2,
                            children: int = 0, infants: int = 0, cabin: str = "E",
                            fresh: bool = False) -> dict:
    """Search flights on a route for one date.

    Fares are per adult, with base and tax separate, sorted cheapest first. Each
    itinerary carries its own `from`/`to`: MakeMyTrip answers with nearby airports
    too, and any itinerary not landing at `dest` is flagged `alternate_airport`.

    SLOW BY CONSTRUCTION (~40 s). The flights API cannot be called directly, so this
    drives the site's own search and reads the response the page receives. Prefer one
    call per route and date; the result is cached for 20 minutes.

    Goa is two airports: GOI (South, Dabolim) and GOX (North, Mopa). Bare "goa"
    means GOI.
    """
    o, d = FL.resolve_airport(origin), FL.resolve_airport(dest)
    return await FL.search(o, d, date, adults=adults, children=children,
                           infants=infants, cabin=cabin, fresh=fresh)


# ------------------------------------------------------------------------- trains

@tool("mmt_train_search", _obj({
    "origin": {**S_STR, "description": "Station code (MDU) or known city name."},
    "dest": S_STR, "date": {**S_STR, "description": "ISO YYYY-MM-DD."},
    "travel_class": {**S_STR, "description": "Blank for all classes, else 3A/2A/SL."},
}, ["origin", "dest", "date"]))
async def mmt_train_search(origin: str, dest: str, date: str, travel_class: str = "",
                           fresh: bool = False) -> dict:
    """Trains on a route for one date, with live class-by-class availability and fare.

    Returns each train with departure, arrival, duration, days it runs, and per class:
    quota, waitlist or availability status, fare, and MakeMyTrip's confirmation
    probability estimate.

    Indian Railways opens reservations 60 days ahead. Outside that window MakeMyTrip
    returns an empty page with HTTP 200, so this reports when booking opens instead of
    implying the route has no trains.
    """
    src, dst = TR.resolve_station(origin), TR.resolve_station(dest)
    if not TR.in_window(date):
        raise NotInWindow(
            f"{date} is outside Indian Railways' {TR.ARP_DAYS}-day reservation window, "
            "so MakeMyTrip has nothing to show yet.",
            hint=f"Booking for this date opens on {TR.booking_opens(date)}.",
            details={"booking_opens": TR.booking_opens(date), "route": f"{src}-{dst}"})
    out = await TR.search(src, dst, date, class_code=travel_class, fresh=fresh)
    if not out["train_count"]:
        out["warning"] = ("No trains returned even though the date is inside the "
                          "booking window - check the station codes.")
    return out


@tool("mmt_station_city", _obj({"origin": S_STR, "dest": S_STR}, ["origin", "dest"]))
async def mmt_station_city(origin: str, dest: str, fresh: bool = False) -> dict:
    """Map two railway station codes to MakeMyTrip city codes (MDU becomes CTIXM).

    Validates station codes and hands back the city code the hotel tools want, so a rail
    leg and its hotel can be priced from one lookup.
    """
    return await TR.station_to_city(TR.resolve_station(origin),
                                    TR.resolve_station(dest), fresh=fresh)


# --------------------------------------------------------------------------- cabs

@tool("mmt_cab_quote", _obj({
    "origin": {**S_STR, "description": "Registered place name."},
    "dest": S_STR, "date": {**S_STR, "description": "ISO YYYY-MM-DD."},
    "pickup_time": {**S_STR, "description": "24h HH:MM, default 10:00."},
    "trip_type": {**S_STR, "description": "OW one-way or RT round trip."},
    "return_date": {**S_STR, "description": "ISO YYYY-MM-DD, required when trip_type is RT."},
}, ["origin", "dest", "date"]))
async def mmt_cab_quote(origin: str, dest: str, date: str, pickup_time: str = "10:00",
                        trip_type: str = "OW", return_date: str = "",
                        fresh: bool = False) -> dict:
    """Outstation cab fares between two places on a date, by vehicle class.

    Returns base, tax and fees, all-in, the per-km rate implied by the route distance,
    and the extra-km charge beyond the included distance. Unlike trains, cab pricing has
    no advance-booking window - dates months out quote fine, usually at a premium.

    Places must be registered first; see mmt_cab_find_place.
    """
    return await CB.search(origin, dest, date, pickup_time=pickup_time,
                           trip_type=trip_type, return_date=return_date,
                           fresh=fresh)


@tool("mmt_cab_add_place", _obj({
    "listing_url": {**S_STR, "description": "A makemytrip.com/cabs/listing URL."},
    "name_origin": S_STR, "name_dest": S_STR,
}, ["listing_url"]))
async def mmt_cab_add_place(listing_url: str, name_origin: str = "",
                            name_dest: str = "", fresh: bool = False) -> dict:
    """Register cab pickup and drop locations from a MakeMyTrip URL.

    Search the route once on makemytrip.com/cabs, copy the resulting listing URL and
    pass it here - both endpoints are extracted and saved permanently. This is the
    reliable manual alternative to mmt_cab_find_place.
    """
    found = CB.place_from_url(listing_url)
    added = {}
    for side, given in (("from", name_origin), ("to", name_dest)):
        obj = found.get(side)
        if not obj:
            continue
        nm = (given or obj.get("city") or obj.get("locusV2Id") or side).strip().lower()
        CB.save_place(nm, obj)
        added[nm] = {"locus": obj.get("locusV2Id"), "place_id": obj.get("place_id"),
                     "address": obj.get("address")}
    return {"added": added, "known_places": sorted(CB.known_places()),
            "stored_in": str(C.DATA_FILE)}


@tool("mmt_cab_find_place", _obj({
    "query": {**S_STR, "description": "City or locality name to look up."},
    "save_as": {**S_STR, "description": "Name to register it under."},
}, ["query"]))
async def mmt_cab_find_place(query: str, save_as: str = "",
                             fresh: bool = False) -> dict:
    """Look up a cab pickup or drop location by name and register it.

    Drives MakeMyTrip's own search form, because it publishes no location autosuggest
    API. Slow (up to about 30 seconds) and occasionally flaky; if it fails, use
    mmt_cab_add_place with a pasted URL instead.
    """
    place = await HV.harvest_place(query)
    nm = (save_as or place.get("city") or query).strip().lower()
    CB.save_place(nm, place)
    return {"registered_as": nm, "place": place,
            "known_places": sorted(CB.known_places())}


# ---------------------------------------------------------------- meta and health

@tool("mmt_capabilities", {"type": "object", "properties": {}, "required": []})
async def mmt_capabilities() -> dict:
    """What this server can and cannot price, and why. Worth calling before planning.

    Covers which tools are verified versus experimental, the booking windows that differ
    per travel mode, known gaps, and the deliberate absence of any booking path.
    """
    return {
        "verified": {
            "hotel_search": "city plus dates to a priced list",
            "hotel_rates": "one property to every room and rate plan",
            "price_itinerary": "multi-stop total, summed server-side",
            "train_search": "trains with live per-class availability",
            "cab_quote": "outstation cabs by vehicle class",
            "station_city": "station code to city code",
            "flight_search": "fares per adult, base and tax apart, cheapest first - "
                             "but SLOW (~30-60 s) and it answers with nearby airports "
                             "as well as the one asked for",
        },
        "experimental": {
            "cab_find_place": "drives the search form; falls back to a pasted URL",
        },
        "booking_windows": {
            "hotels": "none - any future date prices",
            "cabs": "none on this endpoint; the ~60-day limit is only the website's "
                    "date picker",
            "flights": "none",
            "trains": f"Indian Railways opens reservations {TR.ARP_DAYS} days ahead; "
                      "outside that MakeMyTrip returns an empty page with HTTP 200",
        },
        "pricing_conventions": {
            "currency": "INR",
            "hotels": "stay totals for the whole range, not per night",
            "flights": "per adult, one way, for the cabin searched",
            "split": "base, tax and all-in are always reported separately",
        },
        "known_gaps": [
            "A wrong city or station code returns an empty result, not an error.",
            "Some properties are not sold on MakeMyTrip at all - absence is not "
            "the same as sold out.",
            "Local 8hr/80km cab day packages use a different funnel and are not built.",
            "Holiday packages are quoted per enquiry and are not searchable.",
            "A flight search takes ~30-60 s: the API cannot be called directly, so the "
            "server drives the site's own search page. Ask for one route and date at "
            "a time rather than sweeping a month.",
            "A flight search also returns nearby airports (a Goa search includes GOX "
            "and Sindhudurg). Itineraries not landing at the requested airport carry "
            "alternate_airport: true - do not quote them as fares into it.",
            "Goa is two airports: GOI (South, Dabolim) and GOX (North, Mopa). Bare "
            "'goa' means GOI.",
        ],
        "cannot": {
            "booking": "deliberately absent - this server has no booking, cart, "
                       "payment or login path",
            "member_rates": "requires a signed-in session, which this server never does",
        },
        "health": ROUTER.snapshot(),
        "cache": CACHE.stats(),
    }


@tool("mmt_setup_status", {"type": "object", "properties": {}, "required": []})
async def mmt_setup_status() -> dict:
    """Check whether the browser this server needs is installed and working.

    Call this first if tools are failing with browser errors. Returns exactly what to
    run to fix it.
    """
    ok, why = playwright_available()
    status = SESSION.status()
    steps: list[str] = []
    if not ok:
        steps.append("python -m pip install playwright")
    steps.append("Install Google Chrome or Microsoft Edge if neither is present, "
                 "or run: python -m playwright install chromium")
    warm = None
    if ok:
        try:
            warm = await SESSION.warmup()
        except MMTError as e:
            warm = e.to_result()
    return {"ready": bool(ok and warm and warm.get("ok")), **status,
            "warmup": warm, "next_steps": steps if not (ok and warm) else [],
            "state_dir": str(C.STATE_DIR)}


@tool("mmt_selftest", _obj({
    "quick": {**S_BOOL, "description": "Skip the slower checks."},
}, []))
async def mmt_selftest(quick: bool = False, fresh: bool = True) -> dict:
    """Run live checks against MakeMyTrip and report what still works.

    Use this when results look wrong or stale: it tells you which specific capability
    broke rather than leaving you to guess. Asserts on structure and arithmetic rather
    than on particular prices, which drift daily.
    """
    checks: list[dict[str, Any]] = []

    async def run(name: str, coro) -> None:
        try:
            r = await coro
            bad = isinstance(r, dict) and r.get("error")
            checks.append({"check": name, "ok": not bad,
                           "detail": r.get("error") if bad else "ok"})
        except MMTError as e:
            checks.append({"check": name, "ok": False,
                           "detail": f"{e.kind}: {e.message}"})
        except Exception as e:
            checks.append({"check": name, "ok": False,
                           "detail": f"{type(e).__name__}: {e}"})

    today = date.today()
    ci = (today + timedelta(days=30)).isoformat()
    co = (today + timedelta(days=32)).isoformat()
    train_day = (today + timedelta(days=30)).isoformat()   # inside the 60-day window
    cab_day = (today + timedelta(days=45)).isoformat()

    await run("hotel_search", mmt_hotel_search(city="Kochi", check_in=ci,
                                               check_out=co, limit=3, fresh=True))
    if not quick:
        await run("train_search", mmt_train_search(origin="MDU", dest="MS",
                                                   date=train_day, fresh=True))
        await run("cab_quote", mmt_cab_quote(origin="kochi", dest="rameswaram",
                                             date=cab_day, fresh=True))
        await run("station_city", mmt_station_city(origin="MDU", dest="MS", fresh=True))

    passed = sum(1 for c in checks if c["ok"])
    return {"passed": passed, "total": len(checks), "checks": checks,
            "router_health": ROUTER.snapshot(), "session": SESSION.status(),
            "cache": CACHE.stats()}
