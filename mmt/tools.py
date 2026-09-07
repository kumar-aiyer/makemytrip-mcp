"""Tool registry, JSON schemas and implementations.

Docstrings are the descriptions the model sees. Write them for a reader who has never
heard of MakeMyTrip.
"""
from __future__ import annotations

import functools
import inspect
import time
from datetime import date, timedelta
from typing import Any, Callable

from . import cabs as CB
from . import calllog as CALLLOG
from . import compare as CMP
from . import config as C
from . import dates as D
from . import flights as FL
from . import harvest as HV
from . import hotels as HO
from . import trains as TR
from . import version as VS
from .cache import CACHE
from .errors import BadInput, EmptyValid, MMTError, NotInWindow, NullPrices
from .fetch import gather_limited
from .router import ROUTER
from .session import SESSION, playwright_available

TOOLS: dict[str, dict[str, Any]] = {}

S_STR = {"type": "string"}
S_INT = {"type": "integer"}
S_BOOL = {"type": "boolean"}


def tool(name: str, schema: dict[str, Any], *, hidden: bool = False) -> Callable:
    """Register a tool. `hidden` keeps it out of tools/list.

    A hidden tool is still registered and still callable - probe.py, mmt_selftest and
    mmt_intercity_options all reach it through TOOLS - it is simply not advertised to a
    model. That distinction is the point: the single-mode searches are parts a caller
    kept using badly, not parts that stopped working.
    """
    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(**kwargs):
            # Every tool result - answers and handled errors alike - is recorded here.
            # This is the choke point rather than server.py's tools/call because
            # tools/probe.py and the harness drivers call TOOLS[...]["fn"] directly, and
            # an audit log with holes in it is worse than none.
            t0 = time.perf_counter()
            try:
                result = await fn(**kwargs)
            except MMTError as e:
                result = e.to_result()
            except TypeError as e:
                result = {"error": f"bad arguments: {e}", "kind": "bad_input"}
            except Exception as e:
                result = {"error": f"{type(e).__name__}: {e}", "kind": "unexpected"}
            CALLLOG.record(name, kwargs, result,
                           int((time.perf_counter() - t0) * 1000))
            return result
        TOOLS[name] = {"fn": wrapper, "schema": schema, "hidden": hidden,
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

    Prices are INR **PER NIGHT** - `nightly_base_inr`, `nightly_tax_inr`,
    `nightly_all_in_inr` - reported apart because MakeMyTrip displays them apart and
    the all-in figure is roughly 18% above the headline. **Report base and tax
    separately rather than only the all-in figure**: a blended number is how budgets
    end up understated, and acceptance runs collapse this split more often than they
    keep it.

    `stay_estimate_all_in_inr` is `nightly_all_in_inr x nights`. It is an ESTIMATE:
    MakeMyTrip quotes one representative nightly rate for the range rather than a
    per-date breakdown, so a stay spanning a price change will not match it exactly.
    Book-time totals come from the property, not from here.

    A wrong city code returns an empty result rather than an error, so the response
    carries a warning when that is what happened.
    """
    D.not_past(check_in, "check_in")
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
        if isinstance(h.get("nightly_all_in_inr"), (int, float)):
            h["stay_estimate_all_in_inr"] = round(h["nightly_all_in_inr"] * n)
    return {"city": city, "city_code": code, "check_in": check_in,
            "check_out": check_out, "nights": n, "rooms": rooms, "adults": adults,
            "total_in_city": response.get("hotelCountInCity"),
            "returned": len(hotels), "hotels": hotels,
            "note": "Signed-out retail rates, PER NIGHT. This server cannot book. "
                    "stay_estimate_all_in_inr is nightly x nights, an estimate.",
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

    Plan prices are PER NIGHT (`nightly_*`). `cheapest_stay_estimate_inr` multiplies the
    cheapest plan by `nights` and is an estimate, for the reason given on
    mmt_hotel_search. **Report base and tax separately**, not just the all-in figure.

    Includes meal plan, cancellation policy and inclusions. Flags properties where every
    plan includes breakfast, so a room-only rate that does not exist is never reported.
    """
    D.not_past(check_in, "check_in")
    code = HO.resolve_city(city)
    n = HO.nights(check_in, check_out)
    data = await HO.room_rates(hotel_id, code, check_in, check_out, adults=adults,
                               rooms=rooms, fresh=fresh)
    data["nights"] = n
    cheap = data.get("cheapest") or {}
    if isinstance(cheap.get("nightly_all_in_inr"), (int, float)):
        data["cheapest_stay_estimate_inr"] = round(cheap["nightly_all_in_inr"] * n)
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
    for i, st in enumerate(stays):
        D.not_past(st.get("check_in"), f"stays[{i}].check_in")

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
        # Rates are per night (BUG-16). Summing them across legs of different lengths
        # was the old bug in miniature - a two-night stay counted the same as a fortnight.
        for unit, stay in (("nightly_base_inr", "stay_base_inr"),
                           ("nightly_tax_inr", "stay_tax_inr"),
                           ("nightly_all_in_inr", "stay_all_in_inr")):
            if isinstance(row.get(unit), (int, float)):
                row[stay] = round(row[unit] * n)
        return row

    results = await gather_limited([price(s) for s in stays], limit=4)
    legs, errors = [], []
    for s, r in zip(stays, results):
        if isinstance(r, Exception):
            msg = r.message if isinstance(r, MMTError) else f"{type(r).__name__}: {r}"
            errors.append({"stay": s, "error": msg})
        else:
            legs.append(r)

    tb = sum(l["stay_base_inr"] for l in legs
             if isinstance(l.get("stay_base_inr"), (int, float)))
    tt = sum(l["stay_tax_inr"] for l in legs
             if isinstance(l.get("stay_tax_inr"), (int, float)))
    return {"legs": legs, "leg_count": len(legs),
            "total_nights": sum(l.get("nights") or 0 for l in legs),
            "total_base_estimate_inr": tb, "total_tax_estimate_inr": tt,
            "total_all_in_estimate_inr": tb + tt,
            "errors": errors,
            "note": "Retail OTA rates. Totals are ESTIMATES - each leg is a nightly rate "
                    "multiplied by its nights, because MakeMyTrip quotes one "
                    "representative nightly rate per range rather than a per-date "
                    "breakdown. An operator buys below these, so treat them as a "
                    "private benchmark rather than an opening number."}


# ------------------------------------------------------------------------ flights

@tool("mmt_flight_search", _obj({
    "origin": {**S_STR, "description": "IATA code or known city name."},
    "dest": S_STR, "date": {**S_STR, "description": "ISO YYYY-MM-DD."},
    "adults": S_INT, "children": S_INT, "infants": S_INT,
    "cabin": {**S_STR, "description": "E economy, W premium economy, B business."},
}, ["origin", "dest", "date"]), hidden=True)
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
    # `date` shadows datetime.date in this signature, so validate through the module.
    D.not_past(date, "date")
    o, d = FL.resolve_airport(origin), FL.resolve_airport(dest)
    return await FL.search(o, d, date, adults=adults, children=children,
                           infants=infants, cabin=cabin, fresh=fresh)


# ------------------------------------------------------------------------- trains

@tool("mmt_train_search", _obj({
    "origin": {**S_STR, "description": "Station code (MDU) or known city name."},
    "dest": S_STR, "date": {**S_STR, "description": "ISO YYYY-MM-DD."},
    "travel_class": {**S_STR, "description": "Blank for all classes, else 3A/2A/SL."},
    "indicative": {**S_BOOL, "description":
                   "When the date is past the booking window, also quote the furthest "
                   "date Indian Railways will price today. Default true."},
    "ac_only": {**S_BOOL, "description":
                "Keep only trains offering a priced A/C class, seated or sleeper. "
                "Default false - the raw listing is returned whole."},
    "fast_only": {**S_BOOL, "description":
                  "Keep only trains within 1.25x the quickest on the route. "
                  "Default false."},
}, ["origin", "dest", "date"]), hidden=True)
async def mmt_train_search(origin: str, dest: str, date: str, travel_class: str = "",
                           indicative: bool = True, ac_only: bool = False,
                           fast_only: bool = False, fresh: bool = False) -> dict:
    """Trains on a route for one date, with live class-by-class availability and fare.

    Returns each train with departure, arrival, duration, days it runs, and per class:
    quota, waitlist or availability status, fare, and MakeMyTrip's confirmation
    probability estimate.

    Indian Railways opens reservations 60 days ahead. Outside that window MakeMyTrip
    returns an empty page with HTTP 200, so this reports when booking opens instead of
    implying the route has no trains.

    It also quotes the furthest date Indian Railways WILL price today, on the same
    weekday, and returns it as `indicative`. That is a real fare for a different date,
    never the fare for the one you asked about - the block carries `quoted_for`,
    `days_out` and the requested date so the two cannot be confused. Without it the
    honest answer to a date 100 days out is silence, and silence is what makes a planner
    reach for a web estimate. Pass `indicative: false` to skip the extra lookup.

    `ac_only` keeps trains offering a priced air-conditioned class (1A/2A/3A/3E sleeper,
    CC/EC chair car) and `fast_only` keeps those within 1.25x the quickest on the route.
    Both default to FALSE here so the raw listing stays raw; mmt_intercity_options turns
    them on, because an unreserved 2S seat for nine hours is not a comparable to a
    flight. Whatever is filtered, a `filtered` summary says how many were dropped and
    why. Surviving trains are marked `vande_bharat` and carry `avg_kmph`.
    """
    src, dst = TR.resolve_station(origin), TR.resolve_station(dest)
    if not TR.in_window(date):
        details = {"booking_opens": TR.booking_opens(date), "route": f"{src}-{dst}"}
        quote_for = TR.furthest_bookable(date) if indicative else None
        if quote_for:
            # One extra tier-1 fetch, a couple of seconds. Failure here must not replace
            # the not_in_window answer, which is the thing the caller actually asked.
            block = {"quoted_for": quote_for, "requested_date": date,
                     "days_out": TR.ARP_DAYS,
                     "same_weekday": True,
                     "note": "Fares below are for quoted_for, the furthest date Indian "
                             "Railways prices today, chosen on the same weekday as the "
                             "requested date so the same services run. They are an "
                             "indication of what this route costs, NOT the fare for "
                             f"{date}, which cannot exist until "
                             f"{TR.booking_opens(date)}."}
            try:
                got = await TR.search(src, dst, quote_for, class_code=travel_class,
                                      fresh=fresh)
                kept, summary = TR.filter_trains(got.get("trains") or [],
                                                 ac_only=ac_only, fast_only=fast_only)
                block["train_count"] = len(kept)
                block["trains"] = kept
                if ac_only or fast_only:
                    block["filtered"] = summary
            except MMTError as e:
                block["error"] = e.message
                block["kind"] = e.kind
            except Exception as e:                       # never mask the real answer
                block["error"] = f"{type(e).__name__}: {e}"
                block["kind"] = "unexpected"
            details["indicative"] = block
        raise NotInWindow(
            f"{date} is outside Indian Railways' {TR.ARP_DAYS}-day reservation window, "
            "so MakeMyTrip has nothing to show yet.",
            hint=f"Booking for this date opens on {TR.booking_opens(date)}."
                 + (f" Indicative fares for {quote_for}, the furthest date currently "
                    f"priced, are included." if quote_for else ""),
            details=details)
    out = await TR.search(src, dst, date, class_code=travel_class, fresh=fresh)
    kept, summary = TR.filter_trains(out.get("trains") or [], ac_only=ac_only,
                                     fast_only=fast_only)
    out["trains"], out["train_count"] = kept, len(kept)
    if ac_only or fast_only:
        out["filtered"] = summary
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


# ------------------------------------------------------------------ intercity compare

MODES = ("flight", "train", "cab")
MAX_PER_MODE = 3


def _mode_list(modes) -> list[str]:
    if modes is None:
        return list(MODES)
    if not isinstance(modes, list) or not modes:
        raise BadInput("modes must be a non-empty array, or omitted for all of them")
    bad = [m for m in modes if m not in MODES]
    if bad:
        raise BadInput(f"unknown mode(s) {bad}; known: {list(MODES)}")
    return list(dict.fromkeys(modes))


def _train_label(train: dict, cls: dict) -> str:
    mark = " [Vande Bharat]" if train.get("vande_bharat") else ""
    return (f"{train.get('train_number')} {train.get('train_name')} "
            f"({cls.get('class')}){mark}")


def _train_rows(trains: list) -> list:
    """(train, cheapest priced A/C class) rows, Vande Bharat first.

    The preference is a stated one rather than a hidden re-ranking: a Vande Bharat is
    faster and newer than the sleeper it shares a corridor with, and a caller who asked
    for fast A/C options wants to see one before a 1970s express even when it costs
    more. Everything else stays cheapest-first, and the label says which is which.
    """
    rows = []
    for train in trains:
        classes = TR.ac_classes(train)
        if classes:
            rows.append((train, min(classes, key=lambda c: c["fare_inr"])))
    rows.sort(key=lambda p: (not p[0].get("vande_bharat"), p[1]["fare_inr"]))
    return rows


async def _sub(name: str, **kwargs) -> dict:
    """Call another tool through its own wrapper, so every leg lands in the call log as
    its own entry. Routing around the wrapper would make this one tool opaque to H6 and
    to the flight-search budget, which is exactly what the log exists to prevent."""
    return await TOOLS[name]["fn"](**kwargs)


@tool("mmt_intercity_options", _obj({
    "origin": {**S_STR, "description": "City name; also an IATA/station code where one "
                                       "applies. Cab legs need a registered place."},
    "dest": S_STR,
    "date": {**S_STR, "description": "ISO YYYY-MM-DD."},
    "adults": S_INT,
    "modes": {"type": "array", "items": {"type": "string"},
              "description": "Subset of flight/train/cab. Omit for all three."},
    "cabin": {**S_STR, "description": "Flights only: E, W or B."},
    "pickup_time": {**S_STR, "description":
                    "Cabs only: 24h HH:MM, default 10:00. Matters for an airport "
                    "transfer timed to a flight."},
}, ["origin", "dest", "date"]))
async def mmt_intercity_options(origin: str, dest: str, date: str, adults: int = 2,
                                modes: list | None = None, cabin: str = "E",
                                pickup_time: str = "10:00",
                                fresh: bool = False) -> dict:
    """Price one intercity leg by flight, train and cab at once, on comparable terms.

    **This is the interface for pricing a journey between two places** - the
    single-mode searches behind it are no longer exposed. Five of six acceptance runs
    that priced legs mode-by-mode omitted rail entirely, and mixing a per-adult airfare
    with a per-vehicle cab fare by hand is where trip totals go wrong. Modes that cannot
    apply are skipped, so a local transfer costs one cab quote and nothing else.

    Every option carries `party_total_inr` for the whole party alongside `per_unit_inr`
    and the `unit` it came in - flights and trains are per person, a cab is per vehicle,
    and conflating them is the most common way an itinerary total goes wrong.
    `duration_min` is normalised from three different source formats.

    **This does not recommend.** `dominated: true` marks an option that is both dearer
    and slower than another, which is a fact; choosing among the rest is a judgement
    about your whole itinerary - baggage, an early check-in, whether a 12-hour drive
    costs a day you wanted on a beach - and it is yours to make.

    `duration_min` is in-vehicle time as the source reports it. Airport and station
    transfers are NOT included; each option lists what it excludes, and those legs can
    be priced with mmt_cab_quote.

    Modes that cannot apply are skipped rather than guessed at - no airport pair means
    no flight search is spent - and modes that fail land in `unavailable` with the
    reason, so one blocked leg never costs you the other two. A train leg outside the
    60-day reservation window reports `not_in_window` with the date booking opens; that
    is the tool working, not failing.

    SLOW: a flight search alone is 30-60 s, so expect up to about 90 s for all three.
    It spends one flight search, which counts against any per-session budget you hold.
    """
    D.not_past(date, "date")
    wanted = _mode_list(modes)
    options: list[dict] = []
    unavailable: list[dict] = []
    calls: dict[str, int] = {}

    def note(mode: str, kind: str, message: str, **extra) -> None:
        unavailable.append({"mode": mode, "kind": kind, "reason": message, **extra})

    if "flight" in wanted:
        try:
            FL.resolve_airport(origin), FL.resolve_airport(dest)
        except MMTError as e:
            note("flight", "not_applicable", e.message,
                 hint="No airport pair resolves for this route, so no flight search "
                      "was spent on it.")
        else:
            calls["mmt_flight_search"] = 1
            r = await _sub("mmt_flight_search", origin=origin, dest=dest, date=date,
                           adults=adults, cabin=cabin, fresh=fresh)
            if r.get("error"):
                note("flight", r.get("kind") or "error", r["error"])
            else:
                everything = r.get("itineraries", [])
                # Both ends: an itinerary leaving from a nearby airport is as unusable
                # as one landing at one, and it is the cheaper-looking of the two.
                into = [i for i in everything if not i.get("alternate_airport")]
                skipped = len(everything) - len(into)
                cheapest = sorted(into, key=lambda x: x.get("all_in_inr") or 0)
                for it in cheapest[:MAX_PER_MODE]:
                    options.append({
                        "mode": "flight",
                        "label": f"{it.get('airline')} {it.get('flight_no')}"
                                 f"{'' if it.get('stops') else ' nonstop'}",
                        "per_unit_inr": it.get("all_in_inr"), "unit": "per adult",
                        "party_total_inr": CMP.party_total(it.get("all_in_inr"),
                                                           "per adult", adults),
                        "base_inr": it.get("base_inr"), "tax_inr": it.get("tax_inr"),
                        "duration_min": CMP.duration_minutes(it.get("duration")),
                        "depart": it.get("depart"), "arrive": it.get("arrive"),
                        "excludes": ["airport transfers at both ends"],
                        "source_tool": "mmt_flight_search",
                    })
                if skipped:
                    ends = {"arrival": len([i for i in everything
                                            if i.get("alternate_arrival")]),
                            "departure": len([i for i in everything
                                              if i.get("alternate_departure")])}
                    note("flight", "excluded_alternate_airports",
                         f"{skipped} itinerary(ies) use a different airport at one end "
                         f"({ends['arrival']} arrive elsewhere, {ends['departure']} "
                         f"depart elsewhere) and are not fares between {origin} and "
                         f"{dest}.", ends=ends)

    if "train" in wanted:
        try:
            for end in (origin, dest):
                if not TR.is_probable_station(end):
                    raise BadInput(
                        f"{end!r} is not a station name or code, so no train search "
                        f"was spent on this leg.")
            TR.resolve_station(origin), TR.resolve_station(dest)
        except MMTError as e:
            note("train", "not_applicable", e.message)
        else:
            calls["mmt_train_search"] = 1
            # An unreserved seat for nine hours is not a comparable to a flight, so
            # the comparison asks for air-conditioned and reasonably quick services.
            r = await _sub("mmt_train_search", origin=origin, dest=dest, date=date,
                           ac_only=True, fast_only=True, fresh=fresh)
            if r.get("error"):
                extra = {k: r[k] for k in ("booking_opens", "hint") if k in r}
                note("train", r.get("kind") or "error", r["error"], **extra)
                # A fare for the furthest bookable date is still worth comparing, as
                # long as it can never be mistaken for a fare on the requested one.
                ind = r.get("indicative") or {}
                for tr, cheap in _train_rows(ind.get("trains") or [])[:MAX_PER_MODE]:
                    options.append({
                        "mode": "train",
                        "label": _train_label(tr, cheap),
                        "per_unit_inr": cheap.get("fare_inr"),
                        "unit": "per passenger",
                        "party_total_inr": CMP.party_total(cheap.get("fare_inr"),
                                                           "per passenger", adults),
                        "duration_min": CMP.duration_minutes(tr.get("duration_min")),
                        "depart": tr.get("departure"), "arrive": tr.get("arrival"),
                        "vande_bharat": bool(tr.get("vande_bharat")),
                        "avg_kmph": tr.get("avg_kmph"),
                        "indicative": True,
                        "quoted_for_date": ind.get("quoted_for"),
                        "excludes": ["station transfers at both ends",
                                     f"not bookable until {r.get('booking_opens')}"],
                        "source_tool": "mmt_train_search",
                    })
            else:
                priced = _train_rows(r.get("trains", []))
                for tr, cheap in priced[:MAX_PER_MODE]:
                    options.append({
                        "mode": "train",
                        "label": _train_label(tr, cheap),
                        "per_unit_inr": cheap.get("fare_inr"),
                        "unit": "per passenger",
                        "party_total_inr": CMP.party_total(cheap.get("fare_inr"),
                                                           "per passenger", adults),
                        "duration_min": CMP.duration_minutes(tr.get("duration_min")),
                        "depart": tr.get("departure"), "arrive": tr.get("arrival"),
                        "vande_bharat": bool(tr.get("vande_bharat")),
                        "avg_kmph": tr.get("avg_kmph"),
                        "availability": cheap.get("status"),
                        "excludes": ["station transfers at both ends"],
                        "source_tool": "mmt_train_search",
                    })

    if "cab" in wanted:
        # Each mode names places in its own domain - IATA for flights, station codes for
        # trains, harvested places for cabs - so a natural "Bengaluru" -> "GOI" call
        # would fail the cab leg on a code. Try the city names a code maps to as well.
        try:
            _, cab_o = CB.resolve_place_loose(origin)
            _, cab_d = CB.resolve_place_loose(dest)
        except MMTError as e:
            note("cab", e.kind, e.message, hint=e.hint)
            cab_o = cab_d = None
        if cab_o is None:
            r = {"error": None}
        else:
            calls["mmt_cab_quote"] = 1
            r = await _sub("mmt_cab_quote", origin=cab_o, dest=cab_d, date=date,
                           pickup_time=pickup_time, fresh=fresh)
            if cab_o != origin.strip().lower() or cab_d != dest.strip().lower():
                note("cab", "resolved_names",
                     f"cab leg priced as {cab_o!r} -> {cab_d!r}; the names given resolve "
                     f"to codes the cab funnel does not know.")
        if r.get("error"):
            extra = {k: r[k] for k in ("hint",) if k in r}
            note("cab", r.get("kind") or "error", r["error"], **extra)
        else:
            seen: set = set()
            for cab in r.get("cabs", []):
                if cab.get("category") in seen:
                    continue
                seen.add(cab.get("category"))
                options.append({
                    "mode": "cab",
                    "label": f"{cab.get('car')} ({cab.get('category')}, "
                             f"{cab.get('vendor')})",
                    "per_unit_inr": cab.get("all_in_inr"), "unit": "per vehicle",
                    "party_total_inr": CMP.party_total(cab.get("all_in_inr"),
                                                       "per vehicle", adults),
                    "base_inr": cab.get("base_inr"),
                    "tax_inr": cab.get("tax_fees_inr"),
                    "duration_min": CMP.minutes_from_hours(r.get("approx_hours")),
                    "distance_km": r.get("distance_km"),
                    "excludes": [],
                    "source_tool": "mmt_cab_quote",
                })
                if len(seen) >= MAX_PER_MODE:
                    break

    CMP.mark_dominated(options)
    return {
        "route": f"{origin} -> {dest}", "date": date, "adults": adults,
        "options": CMP.sort_options(options),
        "option_count": len(options),
        "unavailable": unavailable,
        "calls_made": calls,
        "note": "party_total_inr is the whole party; per_unit_inr with `unit` is the "
                "convention the source quoted in. Flight and cab rows also carry "
                "base_inr and tax_inr: report those separately rather than only the "
                "all-in figure - a blended number is how budgets end up understated, "
                "and two acceptance runs in a row collapsed them. duration_min is "
                "in-vehicle time only - see each option's `excludes`. `dominated` means "
                "dearer AND slower than another option; the rest is your call.",
    }


# --------------------------------------------------------------------------- cabs

@tool("mmt_cab_quote", _obj({
    "origin": {**S_STR, "description": "Registered place name."},
    "dest": S_STR, "date": {**S_STR, "description": "ISO YYYY-MM-DD."},
    "pickup_time": {**S_STR, "description": "24h HH:MM, default 10:00."},
    "trip_type": {**S_STR, "description": "OW one-way or RT round trip."},
    "return_date": {**S_STR, "description": "ISO YYYY-MM-DD, required when trip_type is RT."},
}, ["origin", "dest", "date"]), hidden=True)
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

    **Check `match` before pricing against the result.** The suggest list is whatever
    MakeMyTrip's autocomplete returns, so a locality name can land on a hotel or a beach
    that merely contains the word. `match.confidence` is high/medium/low and a `warning`
    is raised to the top level when the resolved place is not a city and you did not ask
    for a venue. Fares are then quoted to that exact point, not to the locality.
    """
    place, tier = await HV.harvest_place(query)
    match = CB.match_quality(place, query, tier)
    nm = (save_as or place.get("city") or query).strip().lower()
    CB.save_place(nm, place)
    out = {"registered_as": nm, "place": place, "match": match,
           "known_places": sorted(CB.known_places())}
    # Surfaced at the top level too: a nested field is easy to skim past, and the whole
    # point is that a weak match should not be mistaken for a clean one.
    if match.get("warning"):
        out["warning"] = match["warning"]
    return out


# ---------------------------------------------------------------- meta and health

@tool("mmt_version", {"type": "object", "properties": {}, "required": []})
async def mmt_version() -> dict:
    """Report the exact code this server process is running.

    Returns the git commit the running process was loaded from, its code path and
    uptime. The commit is captured at process start, so this describes the code in
    memory, not the newer state on disk. If `loaded_at_commit` does not match the
    repository checkout you are working from, this is a stale server process -
    restart or re-register it before trusting any other tool result.
    """
    return VS.get_version()


@tool("mmt_capabilities", {"type": "object", "properties": {}, "required": []})
async def mmt_capabilities() -> dict:
    """What this server can and cannot price, and why. Worth calling before planning.

    Covers which tools are verified versus experimental, the booking windows that differ
    per travel mode, known gaps, and the deliberate absence of any booking path.
    """
    return {
        "version": VS.get_version(),
        "verified": {
            "hotel_search": "city plus dates to a priced list",
            "hotel_rates": "one property to every room and rate plan",
            "price_itinerary": "multi-stop total, summed server-side",
            "intercity_options": "THE way to price a journey between two places. "
                                 "The single-mode searches still run - this calls them "
                                 "- but they are no longer listed, because pricing a "
                                 "leg one mode at a time is how rail gets forgotten "
                                 "and how per-adult fares get added to per-vehicle "
                                 "ones. One leg priced by flight, train and cab, "
                                 "normalised to a party total with the source unit kept "
                                 "visible. PREFER THIS for an intercity leg: comparing "
                                 "per-adult fares against a per-vehicle cab by hand is "
                                 "where itinerary totals go wrong. It does not "
                                 "recommend - it marks options that are both dearer and "
                                 "slower as dominated and leaves the choice to you",
            "station_city": "station code to city code",
        },
        "experimental": {
            "cab_find_place": "drives the search form; falls back to a pasted URL",
        },
        "refuses": {
            "past dates": "flights, hotels, cabs and itineraries reject a date before "
                          "yesterday as bad_input, instantly. MakeMyTrip renders a past "
                          "date as an empty page, which reads as 'sold out' rather than "
                          "'wrong year' - and costs ~99 s to find out. If you resolved a "
                          "bare month and day, check the year against today's date first",
            "cab_quote same-day RT": "trip_type RT with return_date == date is "
                                     "rejected: MakeMyTrip answers it with the "
                                     "ONE-WAY listing, so quoting it as a round trip "
                                     "would be a wrong number under a right label. "
                                     "Quote it as OW - that is what those fares are",
        },
        "booking_windows": {
            "hotels": "none - any future date prices",
            "cabs": "none on this endpoint; the ~60-day limit is only the website's "
                    "date picker",
            "flights": "none",
            "trains": f"Indian Railways opens reservations {TR.ARP_DAYS} days ahead; "
                      "outside that MakeMyTrip returns an empty page with HTTP 200. "
                      "mmt_train_search then ALSO quotes the furthest date currently "
                      "priced, on the same weekday, under `indicative` - a real fare "
                      "for a different date, never the requested one. Use it to compare "
                      "rail against road and air; do not present it as the fare for the "
                      "day asked about. mmt_intercity_options additionally asks "
                      "for ac_only and fast_only, so the rail rows it compares "
                      "are air-conditioned services within 1.25x the quickest on "
                      "the route, Vande Bharat first where one runs",
        },
        "pricing_conventions": {
            "currency": "INR",
            "hotels": "PER NIGHT (nightly_base_inr / nightly_tax_inr / "
                      "nightly_all_in_inr). stay_estimate_all_in_inr is nightly x "
                      "nights and is an ESTIMATE - MakeMyTrip quotes one "
                      "representative nightly rate for a range, not a per-date "
                      "breakdown. These were mislabelled as stay totals before "
                      "2026-09-05; anything you were trained on that says otherwise "
                      "is out of date",
            "flights": "per adult, one way, for the cabin searched",
            "split": "base, tax and all-in are always reported separately",
        },
        "known_gaps": [
            "A wrong city or station code returns an empty result, not an error.",
            "Some properties are not sold on MakeMyTrip at all - absence is not "
            "the same as sold out.",
            "Local 8hr/80km cab day packages use a different funnel and are not built. "
            "Price a substitute (a short outstation one-way) or say you subtracted it - "
            "do not leave local transport off an itinerary silently.",
            "Hotel figures are per night. A stay line is nightly x nights and is an "
            "estimate: a range spanning a price change will not match it exactly.",
            "Rail rows in mmt_intercity_options are filtered: air-conditioned "
            "classes only (1A/2A/3A/3E sleeper, CC/EC chair car) and within 1.25x "
            "the quickest train on the route, because an unreserved seat for nine "
            "hours is not a comparable to a flight. Call mmt_train_search directly "
            "for the unfiltered listing - it returns everything by default.",
            "mmt_cab_find_place resolves against MakeMyTrip's own autocomplete, which "
            "lists venues alongside localities - a locality name can land on a hotel or "
            "a beach that merely contains the word. Read the `match` block it returns: "
            "`confidence` high/medium/low, and a top-level `warning` when the result is "
            "not a city and you did not ask for a venue. Fares are quoted to that exact "
            "point, not to the locality.",
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
            "version": VS.get_version(),
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
    flight_day = (today + timedelta(days=30)).isoformat()

    await run("hotel_search", mmt_hotel_search(city="Kochi", check_in=ci,
                                               check_out=co, limit=3, fresh=True))
    if not quick:
        await run("train_search", mmt_train_search(origin="MDU", dest="MS",
                                                   date=train_day, fresh=True))
        await run("cab_quote", mmt_cab_quote(origin="kochi", dest="rameswaram",
                                             date=cab_day, fresh=True))
        await run("station_city", mmt_station_city(origin="MDU", dest="MS", fresh=True))
        # Last, and only in the full run: a flight search drives a real page and is
        # the slowest thing here by an order of magnitude.
        await run("flight_search", mmt_flight_search(origin="BLR", dest="COK",
                                                     date=flight_day, adults=1,
                                                     fresh=True))

    passed = sum(1 for c in checks if c["ok"])
    return {"passed": passed, "total": len(checks), "checks": checks,
            "router_health": ROUTER.snapshot(), "session": SESSION.status(),
            "cache": CACHE.stats()}
