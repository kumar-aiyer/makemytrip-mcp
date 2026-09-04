"""Hotels: city search, pinning one property, and room-level rate plans."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from urllib.parse import urlencode

from . import config as C
from . import state as ST
from .cache import STRUCTURAL_TTL
from .errors import BadInput, EmptyValid, NullPrices, ShapeDrift
from .fetch import get_text, post_json
from .router import HOTEL_API, HOTEL_PAGE


def resolve_city(name: str) -> str:
    n = (name or "").strip()
    if not n:
        raise BadInput("city is required")
    if n.upper().startswith("CT") and len(n) >= 5 and n[2:].isalnum():
        return n.upper()
    code = C.CITY_CODES.get(n.lower())
    if not code:
        raise BadInput(
            f"unknown city {name!r}",
            hint="Known: " + ", ".join(sorted(set(C.CITY_CODES))) +
                 ". Or pass a locus code directly, e.g. CTCOK.")
    return code


def nights(check_in: str, check_out: str) -> int:
    try:
        a = date.fromisoformat(check_in)
        b = date.fromisoformat(check_out)
    except ValueError as e:
        raise BadInput(f"dates must be ISO YYYY-MM-DD ({e})") from None
    n = (b - a).days
    if n <= 0:
        raise BadInput("check_out must be after check_in")
    return n


def build_body(*, city_code: str, check_in: str, check_out: str, adults: int = 2,
               rooms: int = 1, child_ages: list[int] | None = None, limit: int = 20,
               hotel_ids: list[str] | None = None, star_rating: int | None = None,
               last_hotel_id: str | None = None) -> dict[str, Any]:
    """Assemble the search-hotels body.

    expData and featureFlags go in COMPLETE. Trimming them returns HTTP 200 with the
    right hotels and every price null - see errors.NullPrices.
    """
    did = C.identity()
    rid = str(uuid.uuid4())
    search: dict[str, Any] = {
        "checkIn": check_in, "checkOut": check_out,
        "cityCode": city_code, "countryCode": "IN", "currency": "INR",
        "lastFetchedWindowInfo": "", "lastHotelCategory": None,
        "lastHotelId": last_hotel_id, "limit": limit,
        "locationId": city_code, "locationType": "city",
        "nearBySearch": False, "personalCorpBooking": False,
        "personalizedSearch": True, "preAppliedFilter": False, "rmDHS": False,
        "roomStayCandidates": [{"adultCount": adults, "childAges": child_ages or [],
                                "rooms": rooms}],
        "totalHotelsShown": None, "userSearchType": "city",
    }
    if hotel_ids:
        search["hotelIds"] = list(hotel_ids)
        search["userSearchType"] = "hotel"

    filters = []
    if star_rating:
        filters.append({"filterGroup": "STAR_RATING", "filterRange": None,
                        "filterValue": str(star_rating), "isRangeFilter": False})

    return {
        "appliedBatchKeys": [],
        "deviceDetails": {"appVersion": "152.0.0.0", "bookingDevice": "DESKTOP",
                          "deviceId": did, "deviceName": None, "deviceType": "DESKTOP",
                          "networkType": "WiFi"},
        "expData": C.EXP_DATA,
        "featureFlags": dict(C.FEATURE_FLAGS),
        "filterCriteria": filters,
        "filterRemovedCriteria": None,
        "hotelHighlightCities": ["DUBW", "NYC"],
        "imageDetails": {"categories": [{"count": 1, "height": 162,
                                         "imageFormat": "webp", "type": "H",
                                         "width": 243}],
                         "types": ["professional"]},
        "matchMakerDetails": {},
        "requestDetails": {"channel": "B2Cweb", "couponCount": 2,
                           "forwardBookingFlow": False, "funnelSource": "HOTELS",
                           "idContext": "B2C", "journeyId": rid, "loggedIn": False,
                           "pageContext": "LISTING", "requestId": rid, "seoCorp": False,
                           "subPageContext": "",
                           "trafficSource": {"flowType": "funnel"},
                           "visitNumber": 1, "visitorId": did},
        "reviewDetails": {"otas": ["MMT", "TA", "MANUAL"],
                          "tagTypes": ["BASE", "WHAT_GUESTS_SAY"]},
        "searchCriteria": search,
        "sortCriteria": None,
        "userLocation": {"city": "CTBLR", "country": "IND", "state": "STKAR"},
    }


async def search(city_code: str, check_in: str, check_out: str, *, adults: int = 2,
                 rooms: int = 1, child_ages: list[int] | None = None,
                 limit: int = 20, hotel_ids: list[str] | None = None,
                 star_rating: int | None = None, fresh: bool = False) -> tuple[dict, Any]:
    body = build_body(city_code=city_code, check_in=check_in, check_out=check_out,
                      adults=adults, rooms=rooms, child_ages=child_ages, limit=limit,
                      hotel_ids=hotel_ids, star_rating=star_rating)

    def _valid(data: dict) -> bool:
        if not isinstance(data, dict) or "response" not in data:
            return False
        hotels = flatten(data["response"])
        return bool(hotels) and not all_prices_null(hotels)

    res = await post_json(C.SEARCH_HOTELS, body, ec=HOTEL_API, fresh=fresh,
                          validate=_valid)
    data = res.data
    if not isinstance(data, dict) or "response" not in data:
        raise ShapeDrift("search-hotels returned no `response` object.")
    return data["response"], res


def flatten(response: dict) -> list[dict]:
    """Hotels live at response.personalizedSections[N].hotels[], not response.hotels."""
    out: list[dict] = []
    seen: set[str] = set()
    for section in response.get("personalizedSections") or []:
        for h in section.get("hotels") or []:
            hid = h.get("id")
            if hid in seen:
                continue
            seen.add(hid)
            out.append(h)
    return out


def city_ok(response: dict) -> bool:
    return bool(response.get("cityLocationDetail") or response.get("locationDetail"))


def all_prices_null(hotels: list[dict]) -> bool:
    if not hotels:
        return False
    return all(not (h.get("priceDetail") or {}).get("price") for h in hotels)


def summarise(h: dict) -> dict[str, Any]:
    """Base, tax and all-in stay separate. These are stay totals, not per night."""
    p = h.get("priceDetail") or {}
    coupon = p.get("coupon") or {}
    loc = h.get("locationDetail") if isinstance(h.get("locationDetail"), dict) else {}
    return {
        "hotel_id": h.get("id"),
        "name": h.get("name"),
        "star": h.get("starRating"),
        "sold_out": bool(h.get("soldOut")),
        "base_inr": p.get("price"),
        "tax_inr": p.get("totalTax"),
        "all_in_inr": p.get("priceWithTax"),
        "extra_fees_inr": p.get("totalAdditionalFees"),
        "rate_plan_code": p.get("ratePlanCode"),
        "coupon": ({"code": coupon.get("code"), "amount": coupon.get("couponAmount"),
                    "description": coupon.get("description")} if coupon else None),
        "review": (h.get("reviewSummary") or {}).get("cumulativeRating"),
        "locality": ((loc or {}).get("address") or {}).get("locality"),
        "detail_url": h.get("detailDeeplinkUrl") or h.get("seoUrl"),
    }


# ---------------------------------------------------------------- detail page (SSR)

def detail_url(hotel_id: str, city_code: str, check_in: str, check_out: str,
               adults: int = 2, rooms: int = 1) -> str:
    """Dates go in as ISO and out as MMDDYYYY.

    roomStayQualifier is "<adults>e<children>e" once per room: 1 room / 2 adults is
    '2e0e'; 2 rooms is '2e0e2e0e'.
    """
    def mmddyyyy(iso: str) -> str:
        y, m, d = iso.split("-")
        return f"{m}{d}{y}"

    params = {
        "hotelId": hotel_id, "_uCurrency": "INR",
        "checkin": mmddyyyy(check_in), "checkout": mmddyyyy(check_out),
        "city": city_code, "country": "IN", "locusId": city_code,
        "locusType": "city", "roomStayQualifier": f"{adults}e0e" * rooms,
        "isPropSearch": "T", "cc": "IN", "lang": "eng",
    }
    return C.HOTEL_DETAIL + "?" + urlencode(params)


def parse_rate_plans(initial_state: dict) -> dict[str, Any]:
    """Pure. Walk __INITIAL_STATE__ into a flat list of rate plans.

    BASE_FARE and TAXES are kept apart and summed here. TOTAL_AMOUNT in the payload is
    base only - a field named 'total' that is not the total.
    """
    detail = initial_state.get("hotelDetail") or {}
    sr = detail.get("searchRooms") or {}
    static = detail.get("staticDetail") or {}
    hd = static.get("hotelDetails") or {}
    name = hd.get("name") or hd.get("hotelName")

    plans: list[dict[str, Any]] = []
    for room in sr.get("exactRoomsDetail") or []:
        for rp in room.get("ratePlans") or []:
            pd = rp.get("priceDetails") or {}
            if isinstance(pd, list):
                pd = pd[0] if pd else {}
            bk = pd.get("priceBreakup") or {}
            base, tax = bk.get("BASE_FARE"), bk.get("TAXES")
            all_in = (base + tax) if isinstance(base, (int, float)) and \
                isinstance(tax, (int, float)) else None
            plans.append({
                "room": room.get("roomName"),
                "room_code": room.get("roomCode"),
                "beds": room.get("bedCount"),
                "room_size": room.get("roomSize"),
                "plan": rp.get("name"),
                "meal_plan": rp.get("mealPlan"),
                "pay_mode": rp.get("payMode"),
                "cancellation": _cancel_text(rp.get("cancellationPolicy")),
                "inclusions": [i.get("text") if isinstance(i, dict) else i
                               for i in (rp.get("inclusionsList") or [])][:6],
                "base_inr": base,
                "tax_inr": tax,
                "all_in_inr": all_in,
                "avail_count": pd.get("availCount"),
                "rate_plan_code": rp.get("rpc") or pd.get("ratePlanCode"),
            })

    plans.sort(key=lambda p: (p["all_in_inr"] is None, p["all_in_inr"] or 0))
    breakfast_only = bool(plans) and all(
        "breakfast" in (p.get("plan") or "").lower() for p in plans)
    return {
        "hotel_name": name,
        "currency": sr.get("searchRoomsCurrency") or "INR",
        "rate_plan_count": len(plans),
        "rate_plans": plans,
        "cheapest": plans[0] if plans else None,
        "breakfast_only_rates": breakfast_only,
    }


def _cancel_text(cp: Any) -> str | None:
    if isinstance(cp, dict):
        for k in ("text", "title", "policyText", "cancellationText"):
            if cp.get(k):
                return str(cp[k])
        return None
    return str(cp) if cp else None


async def room_rates(hotel_id: str, city_code: str, check_in: str, check_out: str, *,
                     adults: int = 2, rooms: int = 1,
                     fresh: bool = False) -> dict[str, Any]:
    url = detail_url(hotel_id, city_code, check_in, check_out, adults, rooms)
    res = await get_text(url, ec=HOTEL_PAGE, wait_for="networkidle", fresh=fresh)
    st = ST.extract(res.text)
    if st is None:
        raise ShapeDrift(
            "The hotel detail page came back without __INITIAL_STATE__.",
            hint="Usually an Akamai interstitial. mmt_hotel_search still gives "
                 "property-level pricing for this hotel.",
            details={"bytes": len(res.text), "tier_used": res.tier_used})
    parsed = parse_rate_plans(st)
    if not parsed["rate_plan_count"]:
        raise EmptyValid(
            "No rate plans on this property for those dates.",
            hint="Usually genuinely sold out. Check sold_out in mmt_hotel_search.")
    parsed["url"] = url
    parsed.update(res.meta())
    return parsed
