"""Flights.

The search-stream endpoint is **Server-Sent Events**, not a run of concatenated JSON
documents, and each `data:` frame is base64-encoded gzip. The field names here were
read off a real 114 KB payload captured 2026-09-04 (BLR-GOI, 2026-12-15); the fixture
in tests/fixtures is a trimmed copy of it.

The API cannot be called directly from this program. It gates on a session-generated
authorization token plus a header set that only a real user session obtains, and every
non-page path is Akamai-denied - the evidence chain is in config.py and findings.md
BUG-7. What does work is what a person does: drive the site's own search form and read
the response the page itself receives. That is `harvest.harvest_flight_search`, and it
is why a flight search costs ~40 s rather than ~1 s.

MakeMyTrip answers a search with nearby-airport alternatives too - a BLR-GOI search
returns itineraries into GOX (Mopa) and even SDW (Sindhudurg). Each itinerary
therefore carries its own `from`/`to`, and one that does not land at the requested
airport is flagged rather than quietly counted as a fare for it.
"""
from __future__ import annotations

import base64
import gzip
import html
import json
import re
import time
import uuid
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode

from . import config as C
from .errors import BadInput, Blocked, EmptyValid

_TAG_RE = re.compile(r"<[^>]+>")
_MONEY_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def resolve_airport(name: str) -> str:
    n = (name or "").strip()
    if not n:
        raise BadInput("airport is required")
    # Known names always win over the three-letter guess. "goa" is three alpha
    # characters, and GOA is Genoa, Italy - the same trap BUG-4 fixed for stations.
    code = C.AIRPORTS.get(n.lower())
    if code:
        return code
    if len(n) == 3 and n.isalpha():
        return n.upper()
    raise BadInput(f"unknown airport {name!r}",
                   hint="Pass an IATA code (BLR, IXE, COK) or one of: " +
                        ", ".join(sorted(set(C.AIRPORTS))))


def search_url(origin: str, dest: str, iso_date: str, *, adults: int = 2,
               children: int = 0, infants: int = 0, cabin: str = "E") -> str:
    """The API URL. Kept because it documents the wire contract and is unit-tested;
    the live path drives the form instead - see the module docstring."""
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


def page_url(origin: str, dest: str, iso_date: str, *, adults: int = 2,
             children: int = 0, infants: int = 0, cabin: str = "E") -> str:
    """The human results URL, so a figure can be cited back to its source."""
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        raise BadInput("date must be ISO YYYY-MM-DD") from None
    return C.WWW + "/flight/search?" + urlencode({
        "itinerary": f"{origin.upper()}-{dest.upper()}-{d.strftime('%d/%m/%Y')}",
        "tripType": "O", "paxType": f"A-{adults}_C-{children}_I-{infants}",
        "intl": "false", "cabinClass": cabin, "lang": "eng",
    })


# --------------------------------------------------------------------- the stream


def decode_stream(text: str) -> list[dict[str, Any]]:
    """SSE frames -> JSON documents.

    Each frame's `data:` value is either plain JSON (the handshake and the loading
    message) or base64-encoded gzip (every frame carrying results). Anything that
    decodes to neither is skipped rather than raised on: a partial trailing frame is
    normal on a stream that was still open when the page stopped reading it.
    """
    docs: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", text):
        payload = "".join(line[5:].strip() for line in block.splitlines()
                          if line.startswith("data:"))
        if not payload:
            continue
        doc = _decode_frame(payload)
        if isinstance(doc, dict):
            docs.append(doc)
    return docs


def _decode_frame(payload: str) -> dict[str, Any] | None:
    if payload.startswith("{"):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None
    try:
        return json.loads(gzip.decompress(base64.b64decode(payload)).decode("utf-8"))
    except Exception:
        return None


def parse_stream(text: str, max_results: int = 25, *, dest: str | None = None,
                 origin: str | None = None) -> list[dict[str, Any]]:
    return parse_docs(decode_stream(text), max_results, dest=dest, origin=origin)


def parse_docs(docs: list[dict[str, Any]], max_results: int = 25, *,
               dest: str | None = None,
               origin: str | None = None) -> list[dict[str, Any]]:
    """Pure. `dest` and `origin` are the requested airports, used to flag itineraries
    that land - or depart - somewhere else.

    BUG-19: only arrivals were checked. On a GOI->BLR search that let
    `FLY91 IC 5301 SDW->BLR` through unflagged, and it leaves from Sindhudurg, 85 km
    from Goa. A subject built an itinerary that drove to Dabolim and boarded at SDW.
    A nearby airport is no less wrong for being at the start of the journey.
    """
    found: list[dict[str, Any]] = []
    for doc in docs:
        journeys = doc.get("journeyMap") or {}
        for card in _cards(doc):
            it = _itinerary(card, journeys, dest, origin)
            if it is not None:
                found.append(it)

    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for it in sorted(found, key=lambda x: x["all_in_inr"]):
        key = (it["flight_no"], it["depart"], it["all_in_inr"])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
        if len(out) >= max_results:
            break
    return out


def _cards(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """cardList is a list of card *groups*, each itself a list of cards."""
    out: list[dict[str, Any]] = []
    for group in doc.get("cardList") or []:
        if isinstance(group, dict):
            out.append(group)
        elif isinstance(group, list):
            out.extend(c for c in group if isinstance(c, dict))
    return out


def _itinerary(card: dict[str, Any], journeys: dict[str, Any],
               dest: str | None,
               origin: str | None = None) -> dict[str, Any] | None:
    fare = card.get("fare")
    if not isinstance(fare, (int, float)):
        return None

    base, tax = _fare_breakup(card)
    legs = [journeys[k] for k in (card.get("journeyKeys") or []) if k in journeys]
    first = legs[0] if legs else {}
    last = legs[-1] if legs else {}
    # stops within each leg, plus one for every connection between legs
    stops = (sum(leg.get("stops") or 0 for leg in legs) + max(len(legs) - 1, 0)
             if legs else None)
    to_code = last.get("arrCityCd")

    out: dict[str, Any] = {
        "all_in_inr": float(fare),
        "base_inr": base,
        "tax_inr": tax,
        "airline": _plain((card.get("simpleAirlineHeading") or {}).get("nm")),
        "flight_no": card.get("flightNumber"),
        "depart": first.get("depTime"),
        "arrive": last.get("arrTime"),
        "duration": _plain(first.get("flightDuration")) or _plain(card.get("duration")),
        "stops": stops,
        "from": first.get("depCityCd"),
        "to": to_code,
    }
    if first.get("depTimeStampStr") and last.get("arrTimeStampStr"):
        out["arrives_next_day"] = first["depTimeStampStr"] != last["arrTimeStampStr"]
    # MakeMyTrip volunteers nearby airports at BOTH ends. Saying so is the difference
    # between a cheaper option and a wrong number - or, at the departure end, an
    # itinerary that cannot be flown as written.
    from_code = out["from"]
    if dest and to_code and to_code.upper() != dest.upper():
        out["alternate_airport"] = True
        out["alternate_arrival"] = to_code
    if origin and from_code and from_code.upper() != origin.upper():
        out["alternate_airport"] = True
        out["alternate_departure"] = from_code
    return out


def _fare_breakup(card: dict[str, Any]) -> tuple[float | None, float | None]:
    """Base and surcharges, kept apart - a blended figure is against the rules."""
    items = (card.get("fareBreakup") or {}).get("fareBreakUpItems") or []
    amounts: dict[str, float] = {}
    for item in items:
        label = _plain(item.get("text"))
        value = _money(item.get("amount"))
        if label and value is not None:
            amounts[label.lower()] = value
    return amounts.get("base fare"), amounts.get("surcharges")


def _plain(value: Any) -> str | None:
    """MakeMyTrip wraps display strings in <font> tags. Strip them."""
    if not isinstance(value, str):
        return None
    text = html.unescape(_TAG_RE.sub("", value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _money(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = _plain(value)
    if not text:
        return None
    m = _MONEY_RE.search(text)
    return float(m.group(0).replace(",", "")) if m else None


# ---------------------------------------------------------------------- the search


async def search(origin: str, dest: str, iso_date: str, *, adults: int = 2,
                 children: int = 0, infants: int = 0, cabin: str = "E",
                 max_results: int = 25, fresh: bool = False) -> dict[str, Any]:
    """One route, one date. Slow by construction - see the module docstring."""
    from . import harvest as HV
    from .cache import CACHE, PRICE_TTL, key as cache_key

    ck = cache_key("FLIGHT", {"o": origin, "d": dest, "date": iso_date,
                              "pax": (adults, children, infants), "cabin": cabin})
    if not fresh:
        hit = CACHE.get(ck)
        if hit is not None:
            out = dict(hit["out"])
            out["cached"] = True
            out["fetched_at"] = hit["at"]
            return out

    t0 = time.time()
    try:
        raw = await HV.harvest_flight_search(origin, dest, iso_date, adults=adults,
                                             children=children, infants=infants,
                                             cabin=cabin)
    except Blocked:
        # One retry, on a fresh browser. A flight search is the longest call here and
        # a browser that went away mid-search is a transient, not a refusal.
        from .session import SESSION
        await SESSION.recover()
        raw = await HV.harvest_flight_search(origin, dest, iso_date, adults=adults,
                                             children=children, infants=infants,
                                             cabin=cabin)
    itineraries = parse_stream(raw, max_results, dest=dest, origin=origin)
    out: dict[str, Any] = {
        "route": f"{origin.upper()}-{dest.upper()}",
        "date": iso_date,
        "pax": f"A-{adults}_C-{children}_I-{infants}",
        "cabin": cabin,
        "fare_basis": ("Fares are as MakeMyTrip lists them, per adult, for the "
                       "searched cabin. base_inr + tax_inr == all_in_inr."),
        "parsed_count": len(itineraries),
        "itineraries": itineraries,
        "source_url": page_url(origin, dest, iso_date, adults=adults,
                               children=children, infants=infants, cabin=cabin),
        "raw_len": len(raw),
        "tier_used": 2,
        "elapsed_ms": int((time.time() - t0) * 1000),
        "cached": False,
        "fetched_at": _now(),
    }
    landing_elsewhere = [i for i in itineraries if i.get("alternate_arrival")]
    leaving_elsewhere = [i for i in itineraries if i.get("alternate_departure")]
    if landing_elsewhere or leaving_elsewhere:
        parts = []
        if landing_elsewhere:
            parts.append(f"{len(landing_elsewhere)} land at a different airport than "
                         f"{dest.upper()}")
        if leaving_elsewhere:
            parts.append(f"{len(leaving_elsewhere)} depart from a different airport "
                         f"than {origin.upper()}")
        # NOT .capitalize() - it lowercases the rest of the string, and the rest of
        # this string is airport codes.
        joined = " and ".join(parts)
        out["note"] = (
            joined[:1].upper() + joined[1:] +
            " - MakeMyTrip volunteers nearby airports at both ends. Each itinerary "
            "carries its own `from`/`to`; anything flagged `alternate_airport` is not "
            f"a fare between {origin.upper()} and {dest.upper()}, and a cheaper one "
            "usually hides a long road transfer.")

    if not itineraries:
        raise EmptyValid(
            f"No flight itineraries parsed for {origin.upper()}-{dest.upper()} on "
            f"{iso_date}.",
            hint=("The search page returned "
                  f"{len(raw)} bytes of stream. If that is near zero the results page "
                  "was blocked (see findings.md BUG-7); if it is large the payload "
                  "shape moved and parse_stream needs re-deriving from a capture."),
            details={k: out[k] for k in ("route", "date", "pax", "raw_len",
                                         "source_url")})

    CACHE.put(ck, {"out": out, "at": out["fetched_at"]}, ttl=PRICE_TTL)
    return out


def _now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
