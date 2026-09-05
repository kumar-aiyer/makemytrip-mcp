"""Offline tests. No network, no browser, no Playwright required.

These assert on STRUCTURE and ARITHMETIC, not on particular rupee figures - live prices
drift daily and a test that pins them is a test that fails for the wrong reason.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mmt import cabs as CB          # noqa: E402
from mmt import flights as FL       # noqa: E402
from mmt import hotels as HO        # noqa: E402
from mmt import rsc                 # noqa: E402
from mmt import state as ST         # noqa: E402
from mmt import trains as TR        # noqa: E402
from mmt.errors import BadInput, NullPrices   # noqa: E402
from mmt.router import (Router, Tier, HOTEL_API, TRAIN_PAGE)   # noqa: E402

FIX = pathlib.Path(__file__).parent / "fixtures"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))


# ------------------------------------------------------------------ state / hotels

def test_initial_state() -> None:
    html = (FIX / "hotel_detail.html").read_text(encoding="utf-8")
    st = ST.extract(html)
    check("state: extracted", st is not None)
    check("state: brace inside a string does not truncate the object",
          st is not None and "hotelDetail" in st)


def test_rate_plans() -> None:
    st = ST.extract((FIX / "hotel_detail.html").read_text(encoding="utf-8"))
    out = HO.parse_rate_plans(st)
    cheapest = out["cheapest"]
    check("hotel: plans parsed", out["rate_plan_count"] == 2, str(out["rate_plan_count"]))
    check("hotel: base and tax kept apart",
          cheapest["base_inr"] is not None and cheapest["tax_inr"] is not None)
    check("hotel: all_in == base + tax",
          cheapest["all_in_inr"] == cheapest["base_inr"] + cheapest["tax_inr"])
    check("hotel: TOTAL_AMOUNT ignored (it is base only)",
          cheapest["all_in_inr"] > cheapest["base_inr"])
    check("hotel: cheapest sorts first",
          out["rate_plans"][0]["all_in_inr"] <= out["rate_plans"][1]["all_in_inr"])
    check("hotel: breakfast-only flag false when a room-only plan exists",
          out["breakfast_only_rates"] is False)
    check("hotel: meal plan preserved", cheapest["meal_plan"] == "NO_MEAL")


def test_hotel_api_shape() -> None:
    data = json.loads((FIX / "search_hotels.json").read_text(encoding="utf-8"))
    resp = data["response"]
    hotels = HO.flatten(resp)
    check("api: hotels found under personalizedSections", len(hotels) == 2)
    check("api: city validated", HO.city_ok(resp) is True)
    s = HO.summarise(hotels[0])
    check("api: summary arithmetic", s["all_in_inr"] == s["base_inr"] + s["tax_inr"])
    check("api: coupon surfaced", HO.summarise(hotels[1])["coupon"]["code"] == "MMTSAVE")
    check("api: not all prices null", HO.all_prices_null(hotels) is False)

    nulled = json.loads((FIX / "search_hotels_nullprices.json").read_text("utf-8"))
    check("api: null-price trap detected",
          HO.all_prices_null(HO.flatten(nulled["response"])) is True)


def test_hotel_urls() -> None:
    u = HO.detail_url("201211061904322411", "CTCOK", "2026-12-22", "2026-12-24")
    check("url: ISO converted to MMDDYYYY", "checkin=12222026" in u and
          "checkout=12242026" in u, u)
    check("url: roomStayQualifier for 1 room / 2 adults",
          "roomStayQualifier=2e0e" in u)
    u2 = HO.detail_url("1", "CTCOK", "2026-12-22", "2026-12-24", adults=2, rooms=2)
    check("url: roomStayQualifier repeats per room", "2e0e2e0e" in u2)
    check("nights: computed", HO.nights("2026-12-22", "2026-12-24") == 2)


# ------------------------------------------------------------------------- RSC

def test_rsc() -> None:
    html = (FIX / "trains_listing.html").read_text(encoding="utf-8")
    blob = rsc.blob(html)
    check("rsc: chunks split mid-line reassemble", "trainNumber" in blob)
    table = rsc.chunks(blob)
    check("rsc: non-JSON preload lines skipped", "1" not in table)
    check("rsc: reference table built", "32" in table)
    resolved = rsc.resolve(table["32"], table)
    check("rsc: $refs resolved", isinstance(resolved["tbsAvailability"], list))
    check("rsc: balanced() is string-aware",
          rsc.balanced('{"a":"}"}', 0) == '{"a":"}"}')


# ---------------------------------------------------------------------- trains

def test_trains() -> None:
    html = (FIX / "trains_listing.html").read_text(encoding="utf-8")
    out = TR.parse(html, iso_date="2026-09-11", src="NDLS", dest="MAS")
    check("train: parsed", out["train_count"] == 1)
    t = out["trains"][0]
    check("train: duration formatted", t["duration"] == "33h 30m", t["duration"])
    check("train: runs daily", t["runs_on"] == "daily")
    check("train: classes parsed", len(t["classes"]) == 2)
    check("train: cheapest class first", t["classes"][0]["fare_inr"] == 2245)
    check("train: MMT's 'availablity' misspelling honoured",
          t["classes"][0]["status"] == "AVAILABLE-0021")
    check("train: waitlist status preserved",
          t["classes"][1]["status"] == "GNWL12/WL9")
    check("train: confirm probability numeric",
          t["classes"][1]["confirm_probability_pct"] == 97.0)

    empty = TR.parse((FIX / "trains_empty.html").read_text(encoding="utf-8"))
    check("train: empty page yields zero trains, not a crash",
          empty["train_count"] == 0)


def test_train_window() -> None:
    check("train: booking_opens is date minus 60",
          TR.booking_opens("2026-12-30") == "2026-10-31")
    check("train: 18 Dec opens 19 Oct",
          TR.booking_opens("2026-12-18") == "2026-10-19")
    u = TR.listing_url("MDU", "MS", "2026-12-30")
    check("train: url uses YYYYMMDD", "date=20261230" in u, u)
    check("train: cosmetic city params left blank", "srcCity=&" in u or
          "srcCity=" in u)


# ------------------------------------------------------------------------ cabs

def test_cabs() -> None:
    for name in ("cabs_listing.html", "cabs_listing_pretty.html"):
        out = CB.parse((FIX / name).read_text(encoding="utf-8"),
                       iso_date="2026-12-22", route="Kochi -> Rameswaram")
        tag = "compact" if "pretty" not in name else "pretty-printed"
        check(f"cab ({tag}): quotes parsed", out["cab_count"] == 2)
        check(f"cab ({tag}): distance from summaryText", out["distance_km"] == 438)
        check(f"cab ({tag}): hours from summaryText", out["approx_hours"] == 10)
        c = out["cabs"][0]
        check(f"cab ({tag}): all_in == base + fees",
              c["all_in_inr"] == c["base_inr"] + c["tax_fees_inr"])
        check(f"cab ({tag}): per-km derived",
              c["all_in_per_km_inr"] == round(c["all_in_inr"] / 438, 2))
        check(f"cab ({tag}): cheapest first",
              out["cabs"][0]["all_in_inr"] <= out["cabs"][1]["all_in_inr"])
        check(f"cab ({tag}): vendor captured", c["vendor"] == "Savaari")


def test_cab_urls() -> None:
    u = CB.listing_url(CB.BUILTIN_PLACES["kochi"], CB.BUILTIN_PLACES["rameswaram"],
                       "2026-12-22")
    check("cab: url uses DD-MM-YYYY", "departDate=22-12-2026" in u, u)
    check("cab: place_id present in url", "place_id" in u)
    back = CB.place_from_url(u)
    check("cab: place objects round-trip",
          back["from"]["locusV2Id"] == "CTCOK" and back["to"]["locusV2Id"] == "CTXAE")
    try:
        CB.resolve_place("Madurai")
        check("cab: unknown place raises", False)
    except Exception as e:
        check("cab: unknown place explains the remedy",
              "mmt_cab_add_place" in str(getattr(e, "hint", "")))



def test_train_bad_date() -> None:
    for fn, label in ((TR.in_window, "in_window"), (TR.booking_opens, "booking_opens")):
        try:
            fn("not-a-date")
            check(f"train: {label} rejects a non-ISO date", False)
        except BadInput:
            check(f"train: {label} rejects a non-ISO date as bad_input", True)
        except Exception as e:
            check(f"train: {label} rejects a non-ISO date as bad_input", False,
                  type(e).__name__)


# --------------------------------------------------------------------- flights

def test_flight_airports() -> None:
    check("flight: goa resolves to GOI, not the alpha-code guess GOA (Genoa)",
          FL.resolve_airport("goa") == "GOI", FL.resolve_airport("goa"))
    check("flight: goa north is GOX (Mopa)", FL.resolve_airport("goa north") == "GOX")
    check("flight: mopa is GOX", FL.resolve_airport("mopa") == "GOX")
    check("flight: an unknown three-letter code still passes through",
          FL.resolve_airport("IXE") == "IXE")
    try:
        FL.resolve_airport("nowhere city")
        check("flight: unknown airport raises", False)
    except BadInput as e:
        check("flight: unknown airport lists what is known", "BLR" in str(e.hint))


def test_flight_urls() -> None:
    u = FL.search_url("BLR", "GOI", "2026-12-15")
    check("flight: api url uses YYYYMMDD", "it=BLR-GOI-20261215" in u, u)
    p = FL.page_url("BLR", "GOI", "2026-12-15", adults=2)
    check("flight: page url uses DD/MM/YYYY",
          "itinerary=BLR-GOI-15%2F12%2F2026" in p, p)
    check("flight: page url carries pax", "paxType=A-2_C-0_I-0" in p)


def test_flight_stream() -> None:
    """Fields verified against a real 114 KB capture (BLR-GOI, 2026-12-15)."""
    sse = (FIX / "flight_stream.sse").read_text(encoding="utf-8")
    docs = FL.decode_stream(sse)
    check("flight: SSE frames decode (base64 gzip)", len(docs) == 3, str(len(docs)))
    check("flight: the results frame carries cardList and journeyMap",
          any("cardList" in d and "journeyMap" in d for d in docs))

    its = FL.parse_stream(sse, dest="GOI")
    check("flight: itineraries parsed", len(its) == 3, str(len(its)))
    check("flight: sorted cheapest first",
          [i["all_in_inr"] for i in its] == sorted(i["all_in_inr"] for i in its))

    by_no = {i["flight_no"]: i for i in its}
    nonstop = by_no.get("6E 309", {})
    check("flight: fare", nonstop.get("all_in_inr") == 5193.0)
    check("flight: base and tax kept apart",
          nonstop.get("base_inr") == 3446.0 and nonstop.get("tax_inr") == 1747.0)
    check("flight: airline name, tags stripped", nonstop.get("airline") == "IndiGo")
    check("flight: flight number", nonstop.get("flight_no") == "6E 309")
    check("flight: depart", nonstop.get("depart") == "15:30")
    check("flight: arrive", nonstop.get("arrive") == "16:50")
    check("flight: duration, tags stripped", nonstop.get("duration") == "01h 20m")
    check("flight: stops", nonstop.get("stops") == 0)
    check("flight: from/to airport codes",
          nonstop.get("from") == "BLR" and nonstop.get("to") == "GOX")

    connecting = by_no.get("IX 1548, IX 1051", {})
    check("flight: a connection counts one stop", connecting.get("stops") == 1)
    check("flight: connection arrives at the requested airport",
          connecting.get("to") == "GOI")

    for it in its:
        if it["base_inr"] is None or it["tax_inr"] is None:
            continue
        check(f"flight: base + tax == all_in ({it['flight_no']})",
              round(it["base_inr"] + it["tax_inr"], 2) == round(it["all_in_inr"], 2),
              f"{it['base_inr']} + {it['tax_inr']} vs {it['all_in_inr']}")

    # MakeMyTrip volunteers nearby airports; a GOI search returns GOX and SDW too.
    check("flight: a different arrival airport is flagged",
          by_no["6E 309"].get("alternate_airport") is True)
    check("flight: the requested airport is not flagged",
          "alternate_airport" not in connecting)


def test_flight_stream_junk() -> None:
    check("flight: empty stream yields no itineraries", FL.parse_stream("") == [])
    check("flight: a stub body yields no itineraries", FL.parse_stream("200-OK") == [])
    check("flight: an undecodable data frame is skipped, not raised on",
          FL.parse_stream("id: 2\nevent: response\ndata: notbase64!!\n\n") == [])
    doc = json.loads((FIX / "flight_stream.json").read_text(encoding="utf-8"))
    check("flight: parse_docs works on a decoded document too",
          len(FL.parse_docs([doc])) == 3)


# ---------------------------------------------------------------------- router

def test_router() -> None:
    r = Router()
    check("router: healthy plans the preferred tier",
          r.plan(HOTEL_API)[0] == Tier.HTTP)
    r.record(HOTEL_API, Tier.HTTP, False)
    check("router: one failure stays healthy",
          r.health[HOTEL_API].state == "healthy")
    r.record(HOTEL_API, Tier.HTTP, False)
    check("router: two failures degrade", r.health[HOTEL_API].state == "degraded")
    check("router: degraded skips the cheap tier",
          Tier.HTTP not in r.plan(HOTEL_API))
    r.record(HOTEL_API, Tier.REQUEST, False)
    check("router: a third failure opens the circuit",
          r.health[HOTEL_API].state == "broken")
    check("router: open circuit returns no plan", r.plan(HOTEL_API) == [])
    r.record(HOTEL_API, Tier.REQUEST, True)
    check("router: success recovers", r.health[HOTEL_API].state != "broken")

    r2 = Router()
    check("router: train pages start at the browser tier",
          r2.plan(TRAIN_PAGE)[0] == Tier.REQUEST)


# ------------------------------------------------------------------ validators

def test_validators() -> None:
    # Empty-but-valid must NOT be treated as a shape error (R1): a wrong city code
    # returns a valid-looking empty payload; a zero-train stream or zero-cab page is
    # still a correct answer.
    check("validator: empty hotel response is valid", HO.body_valid({"response": {}}))
    hot = json.loads((FIX / "search_hotels.json").read_text(encoding="utf-8"))
    check("validator: priced hotels valid",
          HO.body_valid(hot) is True)
    nulled = json.loads((FIX / "search_hotels_nullprices.json").read_text("utf-8"))
    try:
        HO.body_valid(nulled)
        check("validator: all-null prices raise NullPrices", False)
    except NullPrices:
        check("validator: all-null prices raise NullPrices", True)
    check("validator: missing response invalid", HO.body_valid({"x": 1}) is False)

    tr_html = (FIX / "trains_listing.html").read_text(encoding="utf-8")
    check("validator: trains page valid", TR.body_valid(tr_html) is True)
    check("validator: trains interstitial invalid", TR.body_valid("<html></html>") is False)
    check("validator: empty train stream valid (no trains)",
          TR.body_valid("<html>self.__next_f.push([1,\"[\\\"0\\\",null]\"])</html>") is True)

    cab_html = (FIX / "cabs_listing.html").read_text(encoding="utf-8")
    check("validator: cab page valid", CB.body_valid(cab_html) is True)
    check("validator: cab interstitial invalid", CB.body_valid("<html></html>") is False)


def test_recover_gating() -> None:
    """R4: recovery follows blocked outcomes only, and only when two land close
    together - a Transport/ShapeDrift pair must never restart the shared browser."""
    import asyncio
    from unittest.mock import AsyncMock, patch

    from mmt import fetch as F
    from mmt.session import Session

    async def run() -> None:
        calls: list[str] = []
        s = AsyncMock(Session)

        async def close():
            calls.append("close")

        async def ensure():
            calls.append("ensure")

        s.close = close
        s.ensure = ensure

        with patch.object(F, "SESSION", s):
            F._LAST_BLOCKED.clear()
            await F._maybe_recover("hotel_api", "transport")
            await F._maybe_recover("hotel_api", "transport")
            check("recover: non-blocked never recovers", calls == [])

            F._LAST_BLOCKED.clear()
            await F._maybe_recover("hotel_api", "blocked")
            check("recover: one blocked waits for the second", calls == [])

            await F._maybe_recover("hotel_api", "blocked")
            check("recover: two blocked -> one fresh session",
                  calls == ["close", "ensure"])

    asyncio.run(run())


def test_null_prices_through_fetch() -> None:
    """Bug-1 regression: a null-price body must surface as kind=null_prices (with the
    specific remedy) through the real fetch path - never a generic shape_drift - and
    must not be cached."""
    import asyncio
    from unittest.mock import patch

    from mmt import fetch as F

    body = (FIX / "search_hotels_nullprices.json").read_text(encoding="utf-8")

    async def run():
        def fake(url, b, h, t):
            return 200, body
        with patch.object(F, "_t0_post", fake), patch.object(F, "_t1_post", fake), \
             patch.object(F, "ROUTER", Router()):
            F.CACHE.clear()
            url = "https://x.test"
            payload = {"q": 1}
            try:
                await F.post_json(url, payload, ec="hotel_api", validate=HO.body_valid)
                check("null_prices: raises through fetch", False)
            except NullPrices as e:
                check("null_prices: raises through fetch", True)
                check("null_prices: kind is null_prices", e.kind == "null_prices")
                hit = F.CACHE.get(
                    F.cache_key("POST:hotel_api", {"url": url, "body": payload}))
                check("null_prices: not cached", hit is None)

    asyncio.run(run())


def main() -> int:
    for fn in (test_initial_state, test_rate_plans, test_hotel_api_shape,
               test_hotel_urls, test_rsc, test_trains, test_train_window,
               test_cabs, test_cab_urls, test_train_bad_date, test_flight_airports,
               test_flight_urls, test_flight_stream, test_flight_stream_junk,
               test_router, test_validators,
               test_recover_gating, test_null_prices_through_fetch):
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, f"{type(e).__name__}: {e}")

    width = max(len(n) for n, _, _ in RESULTS)
    failed = 0
    for name, ok, detail in RESULTS:
        if not ok:
            failed += 1
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}")
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
