"""Endpoints, headers, magic strings and lookup tables.

Everything here was captured from live traffic. When MakeMyTrip changes something, this
is the first file to re-derive - see docs/API-REFERENCE.md for the capture recipe.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- paths and identity

STATE_DIR = Path(os.environ.get("MMT_MCP_HOME", Path.home() / ".makemytrip-mcp"))
PROFILE_DIR = STATE_DIR / "chrome-profile"
DIAG_DIR = STATE_DIR / "diagnostics"
DATA_FILE = STATE_DIR / "data.json"

# ------------------------------------------------------------------------ endpoints

MAPI = "https://mapi.makemytrip.com"
FLIGHTS_CB = "https://flights-cb.makemytrip.com"
RAILWAYS = "https://railways.makemytrip.com"
WWW = "https://www.makemytrip.com"

SEARCH_HOTELS = f"{MAPI}/clientbackend/cg/search-hotels/DESKTOP/2"
HOTEL_DETAIL = f"{WWW}/hotels/hotel-details/"
FLIGHT_SEARCH = f"{FLIGHTS_CB}/api/search-stream-dt"
TRAIN_LISTING = f"{WWW}/railways/listing"
GET_LOCUS = f"{RAILWAYS}/api/mobile/search/getLocusId"
CAB_LISTING = f"{WWW}/cabs/listing"
CAB_HOME = f"{WWW}/cabs/"
HOME = f"{WWW}/?cc=IN&lang=eng"

# Flights API header contract - captured from the site's own XHR (2026-09-05).
# search-stream-dt rejects the call with a 403 JSON naming each missing header
# in turn. The site sends ALL of these from its own JS:
#
#   authorization:  (context-generated bearer - changes per session)
#   app-ver: 1.0.0    device-id / deviceid / usr-mcid / vid / tid / mcid:
#                     the same device UUID repeated
#   os: DESKTOP       src: src           pfm: DESKTOP
#   language: eng     region: in         currency: INR    user-currency: INR
#   entity-name: india  user-country: IN  lob: B2C        source: MMT
#   profile-type: PERSONAL
#
# From an automated context every path we tested fails the same way (2026-09-05):
#   - ctx.request  -> Akamai "Access Denied" HTML (non-page TLS/cookie context)
#   - page.evaluate(fetch) with custom headers -> CORS preflight to flights-cb
#     is rejected (no user-session preflight cache), so the browser throws
#   - bare fetch (no headers) -> reaches the API, 403 "Missing Header app-ver"
#   - clicking Search -> results page renders the Akamai "200-ok" stub, so the
#     site's flight JS never runs on it
# The ONLY proven-working path is the user's real browser. If the server's Chrome
# profile is manually opened on MMT once, the preflight cache + sensor state may
# carry over to automation. See docs/API-REFERENCE.md for the manual capture recipe.

# ------------------------------------------------------------------- the magic bits

# The full experiment string the desktop hotel bundle sends.
# DO NOT TRIM. With a shortened value the API still returns 200 and the right hotels,
# but every priceDetail comes back null. See errors.NullPrices.
EXP_DATA = (
    "{APE:10,PAH:5,PAH5:T,WPAH:F,BNPL:T,MRS:T,PDO:PN,MCUR:T,ADDON:T,CHPC:T,AARI:T,"
    "NLP:Y,RCPN:T,PLRS:T,MMRVER:V3,BLACK:T,IAO:F,BNPL0:T,EMIDT:1,HAFC:T,CRI:T,ALC:T,"
    "LSTNRBY:T,PLV2:T,HIS:DEFAULT,HFC:T,VIDEO:0,MLOS:T,CV2:T,SOU:T,APT:T,AIP:T,"
    "PERNEW:T,RTBC:T,PCCE:T,FLTRPRCBKT:T,UGCV2:T,CRF:T,GALLERYV2:T}"
)

# Likewise complete. Same failure mode if trimmed.
FEATURE_FLAGS: dict[str, Any] = {
    "checkAvailability": True, "coupon": True, "extraAltAccoRequired": False,
    "flashDealClaimed": False, "freeCancellation": True, "mmtPrime": False,
    "originListingMap": False, "personalizedSearch": True, "persuasionSeg": "P1000",
    "persuasionSuppression": False, "persuasionsEngineHit": True,
    "persuasionsRequired": True, "poisRequiredOnMap": True,
    "reviewSummaryRequired": True, "selectiveHotels": False, "seoDS": False,
    "seoUrlRequired": False, "shortlistingRequired": False,
    "showRushDealsBottomSheet": True, "similarHotel": False, "soldOut": True,
    "staticData": True, "walletRequired": True,
}

FALLBACK_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")

# ---------------------------------------------------------------------- lookup data

CITY_CODES = {
    "bengaluru": "CTBLR", "bangalore": "CTBLR", "mangalore": "CTIXE",
    "mangaluru": "CTIXE", "coimbatore": "CTCJB", "kochi": "CTCOK", "cochin": "CTCOK",
    "alleppey": "CTXLL", "alappuzha": "CTXLL", "mararikulam": "CTXLL",
    "trivandrum": "CTTRV", "thiruvananthapuram": "CTTRV", "kanyakumari": "CTXKY",
    "rameswaram": "CTXAE", "madurai": "CTIXM", "chennai": "CTMAA", "delhi": "CTDEL",
    "mumbai": "CTBOM", "goa": "CTGOI", "hyderabad": "CTHYD", "pune": "CTPNQ",
    "jaipur": "CTJAI", "udaipur": "CTUDR", "varanasi": "CTVNS", "amritsar": "CTATQ",
}

STATIONS = {
    "bengaluru": "SBC", "bangalore": "SBC", "yesvantpur": "YPR", "mangalore": "MAJN",
    "mangaluru": "MAJN", "mangalore central": "MAQ", "coimbatore": "CBE",
    "kochi": "ERS", "ernakulam": "ERS", "ernakulam town": "ERN", "alleppey": "ALLP",
    "alappuzha": "ALLP", "trivandrum": "TVC", "thiruvananthapuram": "TVC",
    "kanyakumari": "CAPE", "nagercoil": "NCJ", "rameswaram": "RMM", "madurai": "MDU",
    "chennai egmore": "MS", "chennai central": "MAS", "chennai": "MAS",
    "new delhi": "NDLS", "delhi": "NDLS", "mumbai": "CSMT", "pune": "PUNE",
    "goa": "MAO", "madgaon": "MAO", "margao": "MAO", "thivim": "THVM",
    "vasco da gama": "VSG", "vasco": "VSG",
}

# MakeMyTrip splits Goa into two airports, confirmed live from its own autosuggest
# (2026-09-04): GOI "Goa (South) - Dabolim International" and GOX "Goa (North) -
# Manohar International" (Mopa). Bare "goa" stays GOI - that is the existing
# contract and the busier airport - but a caller who means Mopa can now say so.
AIRPORTS = {
    "bengaluru": "BLR", "bangalore": "BLR", "mangalore": "IXE", "mangaluru": "IXE",
    "coimbatore": "CJB", "kochi": "COK", "cochin": "COK", "trivandrum": "TRV",
    "thiruvananthapuram": "TRV", "madurai": "IXM", "chennai": "MAA", "delhi": "DEL",
    "mumbai": "BOM", "goa": "GOI", "hyderabad": "HYD",
    "goa south": "GOI", "dabolim": "GOI",
    "goa north": "GOX", "mopa": "GOX", "manohar": "GOX",
}

# --------------------------------------------------------------------------- state


def _read_data() -> dict[str, Any]:
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_data(data: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, DATA_FILE)


def load_data() -> dict[str, Any]:
    return _read_data()


def save_data(data: dict[str, Any]) -> None:
    _write_data(data)


# ------------------------------------------------------------------------- headers


def hotel_headers(ua: str | None = None) -> dict[str, str]:
    did = identity()   # one stable UUID, persisted x-process, cached in-process
    return {
        "Content-Type": "application/json", "Accept": "application/json",
        "currency": "INR", "entity-name": "india", "language": "eng", "os": "desktop",
        "region": "IN", "server": "b2c", "tid": "avc", "user-country": "IN",
        "user-currency": "INR", "vid": did, "visitor-id": did,
        "User-Agent": ua or FALLBACK_UA,
    }


_DID_CACHE: str | None = None


def identity() -> str:
    """One stable client-generated UUID, persisted and reused for every call.

    MakeMyTrip does not sign or validate this - it is a device/visitor id. Keeping it
    stable makes our traffic look like one browser rather than a swarm. Read once per
    process (and persisted on first use); never on every header build, so no sync file
    I/O sits in the async path.
    """
    global _DID_CACHE
    if _DID_CACHE:
        return _DID_CACHE
    did = _load_or_create_id()
    _DID_CACHE = did
    return did


def _load_or_create_id() -> str:
    data = _read_data()
    did = data.get("device_id")
    if not did:
        did = str(uuid.uuid4())
        data["device_id"] = did
        try:
            _write_data(data)
        except Exception:
            pass          # a read-only home dir must not take the server down
    return did


def flight_headers(ua: str | None = None) -> dict[str, str]:
    """A 403 body reading 'Missing Header <x>' names exactly what to add here."""
    did = identity()
    return {
        "Accept": "application/json", "mcid": did, "device-id": did,
        "app-ver": "8.0.0", "lob": "B2C", "pfm": "DESKTOP", "os": "desktop",
        "src": "mmt", "source": "mmt", "language": "eng", "currency": "INR",
        "region": "in", "tenant": "MMT", "platform": "desktop", "mmt-auth": "",
        "User-Agent": ua or FALLBACK_UA,
    }


def page_headers(ua: str | None = None) -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": ua or FALLBACK_UA,
    }
