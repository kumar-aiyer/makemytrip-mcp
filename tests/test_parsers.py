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
from mmt import hotels as HO        # noqa: E402
from mmt import rsc                 # noqa: E402
from mmt import state as ST         # noqa: E402
from mmt import trains as TR        # noqa: E402
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


def main() -> int:
    for fn in (test_initial_state, test_rate_plans, test_hotel_api_shape,
               test_hotel_urls, test_rsc, test_trains, test_train_window,
               test_cabs, test_cab_urls, test_router):
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
