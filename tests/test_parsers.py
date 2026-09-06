"""Offline tests. No network, no browser, no Playwright required.

These assert on STRUCTURE and ARITHMETIC, not on particular rupee figures - live prices
drift daily and a test that pins them is a test that fails for the wrong reason.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mmt import cabs as CB          # noqa: E402
from mmt import calllog as CALLLOG  # noqa: E402
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
          cheapest["nightly_base_inr"] is not None
          and cheapest["nightly_tax_inr"] is not None)
    check("hotel: all_in == base + tax",
          cheapest["nightly_all_in_inr"]
          == cheapest["nightly_base_inr"] + cheapest["nightly_tax_inr"])
    check("hotel: TOTAL_AMOUNT ignored (it is base only)",
          cheapest["nightly_all_in_inr"] > cheapest["nightly_base_inr"])
    check("hotel: cheapest sorts first",
          out["rate_plans"][0]["nightly_all_in_inr"]
          <= out["rate_plans"][1]["nightly_all_in_inr"])
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
    check("api: summary arithmetic",
          s["nightly_all_in_inr"] == s["nightly_base_inr"] + s["nightly_tax_inr"])
    check("api: no un-suffixed price key survives the rename (BUG-16)",
          not {"all_in_inr", "base_inr", "tax_inr",
               "all_in_per_night_inr"} & set(s))
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


def test_cab_summary_hours() -> None:
    r"""BUG-15 regression: fractional hours. `\d+` did not truncate 11.5 to 11 - it
    backtracked past the decimal point and matched the 5, so an 11.5 hour drive was
    reported as 5, which reads as plausible and is off by a factor of two."""
    cases = [
        ("Rates for *603 Kms* approx distance | *11.5 hr(s)* approx time", 603, 11.5),
        ("Rates for *438 Kms* approx distance | *10 hr(s)* approx time", 438, 10),
        ("Rates for *40 Kms* approx distance | *4 hr(s)* approx time", 40, 4),
        ("Rates for *1,203 Kms* approx distance | *22.25 hr(s)* approx", 1203, 22.25),
        ("", None, None),
    ]
    for text, km, hrs in cases:
        got_km, got_hrs = CB.parse_summary(text)
        check(f"cab summary: {km} km", got_km == km, f"got {got_km}")
        check(f"cab summary: {hrs} hr", got_hrs == hrs, f"got {got_hrs}")
    check("cab summary: whole hours stay int",
          isinstance(CB.parse_summary("*10 hr(s)*")[1], int))


def test_cab_trip_validation() -> None:
    """BUG-14 regression: MakeMyTrip answers a same-day RT with the one-way listing,
    so the tool must refuse the shape rather than relabel one-way fares."""
    CB.validate_trip("2026-12-19", "OW", "")
    CB.validate_trip("2026-12-19", "RT", "2026-12-20")
    check("cab trip: OW and a real RT are accepted", True)
    for dep, tt, ret, why in (
            ("2026-12-19", "RT", "2026-12-19", "same-day RT"),
            ("2026-12-19", "RT", "2026-12-18", "return before departure"),
            ("2026-12-19", "RT", "", "RT with no return_date"),
            ("2026-12-19", "XX", "", "unknown trip_type"),
            ("19-12-2026", "OW", "", "non-ISO date")):
        try:
            CB.validate_trip(dep, tt, ret)
            check(f"cab trip: rejects {why}", False)
        except BadInput:
            check(f"cab trip: rejects {why}", True)


def test_cache_byte_budget() -> None:
    """BUG-13's other half: PAGE_TIER_BYTE_CAP was a constant nothing read, so the
    only thing bounding memory was a hard reject of big pages."""
    from mmt.cache import Cache

    c = Cache(max_entries=100, byte_cap=1000)
    for i in range(5):
        c.put(f"k{i}", {"text": "x" * 300, "tier": 2, "at": ""}, ttl=60)
    check("cache: byte cap evicts LRU", c.stats()["bytes"] <= 1000,
          str(c.stats()))
    check("cache: newest survives eviction", c.get("k4") is not None)
    check("cache: oldest evicted", c.get("k0") is None)

    c2 = Cache(max_entries=100, byte_cap=10_000)
    c2.put("a", {"text": "y" * 500, "tier": 2, "at": ""}, ttl=60)
    c2.put("a", {"text": "y" * 100, "tier": 2, "at": ""}, ttl=60)
    check("cache: replacing a key does not double-count",
          c2.stats()["bytes"] == 100, str(c2.stats()))
    check("cache: entry count is right after replace", c2.stats()["entries"] == 1)
    c2.clear()
    check("cache: clear resets the byte count", c2.stats()["bytes"] == 0)

    c3 = Cache(max_entries=100, byte_cap=10)
    c3.put("only", {"text": "z" * 5000, "tier": 2, "at": ""}, ttl=60)
    check("cache: a single oversized entry is kept, not spun on",
          c3.get("only") is not None)


def test_oversize_body_through_fetch() -> None:
    """BUG-13 regression: a body over PAGE_SIZE_CAP must still be RETURNED - it just
    does not get cached. It used to raise ShapeDrift on every tier, which left
    mmt_hotel_rates with no working path the day a detail page grew to 2.6 MB."""
    import asyncio
    from unittest.mock import patch

    from mmt import fetch as F
    from mmt.cache import PAGE_SIZE_CAP

    body = "<html>" + ("q" * (PAGE_SIZE_CAP + 1000)) + "</html>"

    async def run():
        def fake_t0(url, h, t):                     # tier 0 is called off-thread
            return 200, body

        async def fake_t1(url, h, t):               # tier 1 is awaited
            return 200, body

        async def never(*a, **k):                   # a render here means the cheap
            raise AssertionError("escalated to the browser tier")   # tiers regressed

        with patch.object(F, "_t0_get", fake_t0), patch.object(F, "_t1_get", fake_t1),              patch.object(F, "_t2_get", never), patch.object(F, "ROUTER", Router()):
            F.CACHE.clear()
            url = "https://oversize.test"
            res = await F.get_text(url, ec=TRAIN_PAGE)
            check("oversize: returned, not raised", len(res.text) == len(body))
            check("oversize: not cached",
                  F.CACHE.get(F.cache_key("GET:" + TRAIN_PAGE, {"url": url})) is None)
            res2 = await F.get_text(url, ec=TRAIN_PAGE)
            check("oversize: re-fetches rather than serving a stale hit",
                  res2.cached is False)
            F.CACHE.clear()

    asyncio.run(run())


def test_call_log() -> None:
    """The audit log H6 should be scored against. It must capture answers AND handled
    errors, digest the full body even when it inlines a truncated one, and never let a
    logging problem reach the caller."""
    import asyncio
    import os
    import tempfile
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmp:
        diag = pathlib.Path(tmp) / "diagnostics"
        with patch.object(CALLLOG.C, "DIAG_DIR", diag):
            CALLLOG.record("mmt_demo", {"a": 1}, {"all_in_inr": 4367, "tier_used": 2,
                                                  "cached": False}, 123)
            CALLLOG.record("mmt_demo", {"a": 2},
                           {"error": "nope", "kind": "bad_input"}, 4)
            rows = CALLLOG.read()

        check("calllog: both calls recorded", len(rows) == 2, str(len(rows)))
        ok, err = rows
        check("calllog: success flagged ok", ok["ok"] is True)
        check("calllog: routing facts captured",
              ok["tier_used"] == 2 and ok["cached"] is False)
        check("calllog: result inlined for spot-checks",
              ok["result"]["all_in_inr"] == 4367)
        check("calllog: digest present", len(ok["result_sha256"]) == 64)
        check("calllog: handled error recorded, not dropped",
              err["ok"] is False and err["kind"] == "bad_input")

        # a body over the inline cap keeps its digest but drops the body
        with patch.object(CALLLOG.C, "DIAG_DIR", diag),              patch.object(CALLLOG, "MAX_RESULT", 50):
            big = {"rows": ["x" * 200]}
            CALLLOG.record("mmt_big", {}, big, 1)
            rows = CALLLOG.read()
        last = rows[-1]
        check("calllog: oversized body not inlined", "result" not in last)
        check("calllog: oversized body still flagged",
              last.get("result_truncated") is True)
        import hashlib, json as _json
        full = _json.dumps(big, sort_keys=True, default=str, ensure_ascii=False)
        check("calllog: digest is over the FULL body, not the stored one",
              last["result_sha256"] == hashlib.sha256(full.encode()).hexdigest())

        # disabled by env
        with patch.dict(os.environ, {"MMT_CALL_LOG": "0"}):
            check("calllog: MMT_CALL_LOG=0 disables it", CALLLOG.enabled() is False)

    # an unwritable log must never break a call: DIAG_DIR under a regular FILE, so
    # mkdir raises NotADirectoryError inside record()
    with tempfile.TemporaryDirectory() as tmp2:
        blocker = pathlib.Path(tmp2) / "iam_a_file"
        blocker.write_text("x", encoding="utf-8")
        with patch.object(CALLLOG.C, "DIAG_DIR", blocker / "cannot" / "exist"):
            CALLLOG.record("mmt_demo", {}, {"x": 1}, 1)
    check("calllog: a broken log cannot break a call", True)

    # and the decorator actually calls it
    from mmt import tools as T
    recorded = []
    with patch.object(T.CALLLOG, "record", lambda *a: recorded.append(a)):
        asyncio.run(T.TOOLS["mmt_version"]["fn"]())
    check("calllog: the @tool decorator records", len(recorded) == 1,
          str(len(recorded)))
    check("calllog: decorator passes the tool name",
          recorded and recorded[0][0] == "mmt_version")


def test_past_date_guard() -> None:
    """BUG-18: a past date used to be answered by driving a live page for 99 seconds and
    returning empty_valid, which reads as 'sold out' rather than 'wrong year'."""
    import asyncio

    from mmt import dates as D
    from mmt import tools as T

    today = datetime.date(2026, 9, 5)
    for bad in ("2025-12-15", "2026-09-03"):
        try:
            D.not_past(bad, "date", today=today)
            check(f"dates: rejects {bad}", False)
        except BadInput as e:
            check(f"dates: rejects {bad}", True)
            check(f"dates: {bad} hint names the year trap", "year" in (e.hint or ""))
    # today and yesterday stay legal - the server and MakeMyTrip are timezones apart
    for ok in ("2026-09-05", "2026-09-04", "2026-12-15"):
        D.not_past(ok, "date", today=today)
    check("dates: today, yesterday and future all accepted", True)
    try:
        D.parse_iso("15-12-2026")
        check("dates: rejects non-ISO", False)
    except BadInput:
        check("dates: rejects non-ISO", True)

    # and every priced tool refuses before touching the network
    for name, args in (
            ("mmt_flight_search", {"origin": "BLR", "dest": "GOI", "date": "2025-12-15"}),
            ("mmt_hotel_search", {"city": "Goa", "check_in": "2025-12-15",
                                  "check_out": "2025-12-21"}),
            ("mmt_hotel_rates", {"hotel_id": "1", "city": "Goa",
                                 "check_in": "2025-12-15", "check_out": "2025-12-21"}),
            ("mmt_cab_quote", {"origin": "goa", "dest": "panaji",
                               "date": "2025-12-15"}),
            ("mmt_price_itinerary", {"stays": [{"hotel_id": "1", "city": "Goa",
                                                "check_in": "2025-12-15",
                                                "check_out": "2025-12-16"}]}),
    ):
        r = asyncio.run(T.TOOLS[name]["fn"](**args))
        check(f"past date: {name} says bad_input",
              r.get("kind") == "bad_input", str(r.get("kind")))


def test_place_match_quality() -> None:
    """BUG-17, from two acceptance runs: "Calangute Goa" registered as "Goa beach" and
    "Palolem Goa" as "Bibhitaki Hostel Palolem Goa" - the same hostel twice - with
    nothing in the result saying the match was a guess."""
    from mmt import harvest as HV

    check("place: query variants shorten from the right",
          HV._query_variants("Palolem Goa") == ["palolem goa", "palolem"])
    check("place: a single-word query is unchanged",
          HV._query_variants("goa") == ["goa"])

    def body(*places):
        return [{"data": list(places)}]

    locality = {"place_id": "L", "main_text": "Palolem",
                "secondary_text": "Goa, India", "is_city": True}
    hostel = {"place_id": "H", "main_text": "Bibhitaki Hostel Palolem Goa",
              "secondary_text": "Palolem, Goa, India", "is_city": False}

    # the hostel is listed first, exactly as it was live
    place, tier = HV._place_from_captured(body(hostel, locality), "Palolem Goa")
    check("place: locality beats a hostel that merely contains the words",
          place["place_id"] == "L", f"{place['place_id']} via {tier}")
    check("place: and says it matched on a shortened query",
          tier.endswith("_shortened"), tier)

    # the regional rule that made "goa" work must survive
    panaji = {"place_id": "P", "main_text": "Panaji", "secondary_text": "Goa, India",
              "is_city": True}
    goalpara = {"place_id": "G", "main_text": "Goalpara",
                "secondary_text": "Assam, India", "is_city": True}
    place, tier = HV._place_from_captured(body(goalpara, panaji), "goa")
    check("place: 'goa' still prefers a place IN Goa over prefix luck",
          place["place_id"] == "P", f"{place['place_id']} via {tier}")

    # grading
    m = CB.match_quality(locality, "Palolem Goa", "segment_shortened")
    check("match: a city on a strong tier is high confidence",
          m["confidence"] == "high" and "warning" not in m, str(m))
    m = CB.match_quality(hostel, "Palolem Goa", "substring")
    check("match: a hostel for a locality query is low confidence",
          m["confidence"] == "low", str(m))
    check("match: and warns, naming what it actually got",
          "Bibhitaki" in m.get("warning", ""))
    airport = {"place_id": "A", "main_text": "Dabolim Airport", "is_city": False}
    m = CB.match_quality(airport, "Dabolim Airport Goa", "segment_shortened")
    check("match: asking for a venue and getting one is not a warning",
          m["confidence"] == "high" and "warning" not in m, str(m))
    beach = {"place_id": "B", "main_text": "Goa beach", "is_city": False}
    m = CB.match_quality(beach, "Calangute Goa", "substring")
    check("match: 'Calangute Goa' -> 'Goa beach' warns", "warning" in m)


def test_compare_normalisation() -> None:
    """The unit arithmetic is the whole reason mmt_intercity_options exists: flights are
    per adult, trains per passenger, cabs per VEHICLE, and every subject that has mixed
    them by hand has got something wrong."""
    from mmt import compare as CMP

    check("compare: flight duration string", CMP.duration_minutes("01h 20m") == 80)
    check("compare: hours only", CMP.duration_minutes("12h") == 720)
    check("compare: minutes only", CMP.duration_minutes("45m") == 45)
    check("compare: already minutes", CMP.duration_minutes(690) == 690)
    check("compare: unparseable is None, not a guess",
          CMP.duration_minutes("about a day") is None)
    check("compare: None stays None", CMP.duration_minutes(None) is None)
    check("compare: fractional cab hours", CMP.minutes_from_hours(11.5) == 690)

    check("compare: per adult x2", CMP.party_total(4367, "per adult", 2) == 8734)
    check("compare: per passenger x2", CMP.party_total(1250, "per passenger", 2) == 2500)
    check("compare: PER VEHICLE is not multiplied",
          CMP.party_total(12161, "per vehicle", 2) == 12161)
    check("compare: missing price stays None",
          CMP.party_total(None, "per adult", 2) is None)

    # dominance: dearer AND slower than something else
    opts = [
        {"label": "flight", "party_total_inr": 8734, "duration_min": 80},
        {"label": "cab", "party_total_inr": 12161, "duration_min": 690},
        {"label": "train", "party_total_inr": 2500, "duration_min": 800},
        {"label": "unknown", "party_total_inr": None, "duration_min": None},
    ]
    CMP.mark_dominated(opts)
    by = {o["label"]: o["dominated"] for o in opts}
    check("compare: cab is dominated (dearer and slower than the flight)", by["cab"])
    check("compare: the flight is not dominated", not by["flight"])
    check("compare: a cheap slow train is NOT dominated - it is a real trade-off",
          not by["train"])
    check("compare: an option missing figures is never marked dominated",
          not by["unknown"])

    ordered = [o["label"] for o in CMP.sort_options(opts)]
    check("compare: undominated first, then by price",
          ordered[0] == "train" and ordered[-1] == "cab", str(ordered))


def test_cab_place_candidates() -> None:
    """Each mode names places in its own domain, so a natural cross-mode call like
    Bengaluru -> GOI would fail the cab leg on an IATA code it has never seen."""
    check("cab names: an IATA code offers its city names",
          "goa" in CB.place_candidates("GOI"), str(CB.place_candidates("GOI")))
    check("cab names: BLR offers bengaluru",
          "bengaluru" in CB.place_candidates("BLR"))
    check("cab names: a plain name is offered first",
          CB.place_candidates("goa")[0] == "goa")
    check("cab names: aliases still apply",
          "kochi" in CB.place_candidates("cochin"))


def test_intercity_options() -> None:
    """Orchestration: one blocked mode must never cost the caller the other two, and a
    mode that cannot apply must not spend a flight search on it."""
    import asyncio
    from unittest.mock import patch

    from mmt import tools as T

    flight_ok = {"itineraries": [
        {"all_in_inr": 4367.0, "base_inr": 3222.0, "tax_inr": 1145.0,
         "airline": "IndiGo", "flight_no": "6E 6554", "duration": "01h 20m",
         "stops": 0, "depart": "19:00", "arrive": "20:20", "to": "GOI"},
        {"all_in_inr": 3099.0, "airline": "FLY91", "flight_no": "IC 5302",
         "duration": "01h 45m", "stops": 0, "alternate_airport": True, "to": "SDW"},
    ]}
    train_window = {"error": "outside the 60-day window", "kind": "not_in_window",
                    "booking_opens": "2026-10-16"}
    cab_ok = {"distance_km": 603, "approx_hours": 11.5, "cabs": [
        {"all_in_inr": 12161, "base_inr": 11216, "tax_fees_inr": 945,
         "car": "WagonR, Swift", "category": "HATCHBACK", "vendor": "Savaari"},
        {"all_in_inr": 12407, "car": "Dzire, Etios", "category": "SEDAN",
         "vendor": "Savaari"},
    ]}

    async def fake(name, **kw):
        return {"mmt_flight_search": flight_ok, "mmt_train_search": train_window,
                "mmt_cab_quote": cab_ok}[name]

    # hermetic: the cab leg must not depend on what .state happens to hold
    loose = lambda n: ({}, n.strip().lower())

    with patch.object(T, "_sub", fake), patch.object(T.CB, "resolve_place_loose", loose):
        r = asyncio.run(T.TOOLS["mmt_intercity_options"]["fn"](
            origin="Bengaluru", dest="GOI", date="2026-12-15", adults=2))

    modes = [o["mode"] for o in r["options"]]
    check("intercity: flight and cab both priced", "flight" in modes and "cab" in modes)
    flight = next(o for o in r["options"] if o["mode"] == "flight")
    check("intercity: flight party total is per-adult x2",
          flight["party_total_inr"] == 8734, str(flight["party_total_inr"]))
    check("intercity: flight keeps base/tax apart",
          flight["base_inr"] == 3222.0 and flight["tax_inr"] == 1145.0)
    check("intercity: alternate-airport itinerary excluded from options",
          all("FLY91" not in o["label"] for o in r["options"]))
    check("intercity: and the exclusion is reported",
          any(u["kind"] == "excluded_alternate_airports" for u in r["unavailable"]))

    cab = next(o for o in r["options"] if o["mode"] == "cab")
    check("intercity: cab party total is NOT multiplied by adults",
          cab["party_total_inr"] == 12161, str(cab["party_total_inr"]))
    check("intercity: cab duration from fractional hours",
          cab["duration_min"] == 690, str(cab["duration_min"]))
    check("intercity: cab is dominated by the flight", cab["dominated"] is True)

    train = next((u for u in r["unavailable"] if u["mode"] == "train"), None)
    check("intercity: a blocked train does not abort the run", train is not None)
    check("intercity: and carries booking_opens forward",
          train and train.get("booking_opens") == "2026-10-16")
    check("intercity: flight search counted for the budget",
          r["calls_made"].get("mmt_flight_search") == 1)
    check("intercity: every option states what it excludes",
          all("excludes" in o for o in r["options"]))

    # a route with no airport pair must not spend a flight search
    async def fake_cab_only(name, **kw):
        if name == "mmt_flight_search":
            raise AssertionError("spent a flight search on a route with no airports")
        return {"mmt_train_search": train_window, "mmt_cab_quote": cab_ok}[name]

    with patch.object(T, "_sub", fake_cab_only),          patch.object(T.CB, "resolve_place_loose", loose):
        r2 = asyncio.run(T.TOOLS["mmt_intercity_options"]["fn"](
            origin="goa", dest="kulem", date="2026-12-19", adults=2))
    check("intercity: no airport pair means no flight search spent",
          "mmt_flight_search" not in r2["calls_made"])
    check("intercity: and it says why",
          any(u["mode"] == "flight" and u["kind"] == "not_applicable"
              for u in r2["unavailable"]))

    # modes filter and validation
    with patch.object(T, "_sub", fake), patch.object(T.CB, "resolve_place_loose", loose):
        r3 = asyncio.run(T.TOOLS["mmt_intercity_options"]["fn"](
            origin="Bengaluru", dest="GOI", date="2026-12-15", modes=["cab"]))
    check("intercity: modes filter is honoured",
          set(r3["calls_made"]) == {"mmt_cab_quote"}, str(r3["calls_made"]))
    r4 = asyncio.run(T.TOOLS["mmt_intercity_options"]["fn"](
        origin="Bengaluru", dest="GOI", date="2026-12-15", modes=["helicopter"]))
    check("intercity: an unknown mode is bad_input", r4.get("kind") == "bad_input")
    r5 = asyncio.run(T.TOOLS["mmt_intercity_options"]["fn"](
        origin="Bengaluru", dest="GOI", date="2025-12-15"))
    check("intercity: past date refused before any call", r5.get("kind") == "bad_input")

def test_furthest_bookable() -> None:
    """A date past the 60-day window has no fare, but the same route on the furthest
    bookable date does - and that beats the silence that sends planners to a web
    estimate. Matched on weekday, because train schedules vary by day."""
    t = datetime.date(2026, 9, 5)
    got = TR.furthest_bookable("2026-12-15", today=t)          # a Tuesday
    check("furthest: returns a date inside the window", got == "2026-11-03", str(got))
    check("furthest: matches the requested weekday",
          datetime.date.fromisoformat(got).weekday()
          == datetime.date(2026, 12, 15).weekday())
    check("furthest: never past the boundary",
          (datetime.date.fromisoformat(got) - t).days <= TR.ARP_DAYS)
    check("furthest: and not in the past",
          datetime.date.fromisoformat(got) >= t)
    check("furthest: a bookable date needs no substitute",
          TR.furthest_bookable("2026-10-01", today=t) is None)
    check("furthest: the boundary itself needs none",
          TR.furthest_bookable("2026-11-04", today=t) is None)


def test_train_indicative_fare() -> None:
    """not_in_window must stay the headline answer; the indicative fare rides along and
    can never be mistaken for the requested date."""
    import asyncio
    from unittest.mock import patch

    from mmt import tools as T

    fake_trains = {"train_count": 1, "trains": [
        {"train_number": "12779", "train_name": "GOA EXPRESS", "duration_min": 800,
         "departure": "15:15", "arrival": "04:35",
         "classes": [{"class": "3A", "fare_inr": 1250, "status": "AVAILABLE"}]}]}

    async def fake_search(src, dst, iso_date, **kw):
        return dict(fake_trains, date=iso_date)

    with patch.object(T.TR, "search", fake_search):
        r = asyncio.run(T.TOOLS["mmt_train_search"]["fn"](
            origin="SBC", dest="MAO", date="2026-12-15"))

    check("indicative: still reports not_in_window", r.get("kind") == "not_in_window")
    check("indicative: still says when booking opens",
          r.get("booking_opens") == "2026-10-16", str(r.get("booking_opens")))
    ind = r.get("indicative") or {}
    check("indicative: a fare block is attached", bool(ind.get("trains")), str(ind)[:80])
    check("indicative: it names the date it is FOR",
          ind.get("quoted_for") and ind["quoted_for"] != "2026-12-15",
          str(ind.get("quoted_for")))
    check("indicative: it repeats the requested date so the two cannot be confused",
          ind.get("requested_date") == "2026-12-15")
    check("indicative: and says outright it is not that fare",
          "NOT the fare for 2026-12-15" in ind.get("note", ""))

    # opt out
    with patch.object(T.TR, "search", fake_search):
        r2 = asyncio.run(T.TOOLS["mmt_train_search"]["fn"](
            origin="SBC", dest="MAO", date="2026-12-15", indicative=False))
    check("indicative: can be switched off", "indicative" not in r2)

    # a failing extra lookup must not replace the real answer
    async def boom(*a, **k):
        raise RuntimeError("network gone")

    with patch.object(T.TR, "search", boom):
        r3 = asyncio.run(T.TOOLS["mmt_train_search"]["fn"](
            origin="SBC", dest="MAO", date="2026-12-15"))
    check("indicative: a failed lookup leaves not_in_window intact",
          r3.get("kind") == "not_in_window")
    check("indicative: and records why it has no fare",
          (r3.get("indicative") or {}).get("kind") == "unexpected")


def test_intercity_indicative_train() -> None:
    """An indicative train belongs in the comparison, flagged - but it must never make a
    bookable option look beaten, because it is a price for a different day."""
    import asyncio
    from unittest.mock import patch

    from mmt import compare as CMP
    from mmt import tools as T

    train_out = {
        "error": "outside the window", "kind": "not_in_window",
        "booking_opens": "2026-10-16",
        "indicative": {"quoted_for": "2026-11-03", "requested_date": "2026-12-15",
                       "trains": [{"train_number": "12779", "train_name": "GOA EXP",
                                   "duration_min": 800, "departure": "15:15",
                                   "arrival": "04:35",
                                   "classes": [{"class": "3A", "fare_inr": 1250}]}]}}
    flight_ok = {"itineraries": [
        {"all_in_inr": 4367.0, "airline": "IndiGo", "flight_no": "6E 6554",
         "duration": "01h 20m", "stops": 0, "to": "GOI"}]}

    async def fake(name, **kw):
        return {"mmt_flight_search": flight_ok, "mmt_train_search": train_out,
                "mmt_cab_quote": {"cabs": [], "distance_km": 603}}[name]

    loose = lambda n: ({}, n.strip().lower())
    with patch.object(T, "_sub", fake), patch.object(T.CB, "resolve_place_loose", loose):
        r = asyncio.run(T.TOOLS["mmt_intercity_options"]["fn"](
            origin="Bengaluru", dest="GOI", date="2026-12-15", adults=2))

    train = next((o for o in r["options"] if o["mode"] == "train"), None)
    check("intercity: the indicative train appears as an option", train is not None)
    check("intercity: flagged indicative", train and train.get("indicative") is True)
    check("intercity: carrying the date it was quoted for",
          train and train.get("quoted_for_date") == "2026-11-03")
    check("intercity: and warning it is not bookable yet",
          train and any("not bookable" in x for x in train["excludes"]))
    check("intercity: party total still per passenger x2",
          train and train["party_total_inr"] == 2500)
    check("intercity: not_in_window is still reported alongside",
          any(u["mode"] == "train" and u["kind"] == "not_in_window"
              for u in r["unavailable"]))

    flight = next(o for o in r["options"] if o["mode"] == "flight")
    check("intercity: a cheaper indicative train does NOT dominate a bookable flight",
          flight["dominated"] is False)

    # the rule itself, directly
    opts = [{"party_total_inr": 2500, "duration_min": 800, "indicative": True},
            {"party_total_inr": 8734, "duration_min": 80}]
    CMP.mark_dominated(opts)
    check("compare: an indicative option never dominates", opts[1]["dominated"] is False)
    check("compare: but it can itself be dominated",
          CMP.mark_dominated([{"party_total_inr": 9000, "duration_min": 900,
                               "indicative": True},
                              {"party_total_inr": 100, "duration_min": 10}])[0]
          ["dominated"] is True)


def main() -> int:
    for fn in (test_initial_state, test_rate_plans, test_hotel_api_shape,
               test_hotel_urls, test_rsc, test_trains, test_train_window,
               test_cabs, test_cab_urls, test_train_bad_date, test_flight_airports,
               test_flight_urls, test_flight_stream, test_flight_stream_junk,
               test_router, test_validators,
               test_recover_gating, test_null_prices_through_fetch,
               test_cab_summary_hours, test_cab_trip_validation,
               test_cache_byte_budget, test_oversize_body_through_fetch,
               test_call_log, test_past_date_guard, test_place_match_quality,
               test_compare_normalisation, test_cab_place_candidates,
               test_furthest_bookable, test_train_indicative_fare,
               test_intercity_indicative_train,
               test_intercity_options):
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
