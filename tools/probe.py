#!/usr/bin/env python3
"""Live acceptance harness. Run this on the machine that will host the server.

    python tools/probe.py

Everything here needs real network access to makemytrip.com from a normal (residential)
connection. Datacenter IPs are refused by MakeMyTrip's CDN with HTTP 403.
"""
from __future__ import annotations

import asyncio
import contextlib
import pathlib
import sys
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mmt import tools as T                     # noqa: E402
from mmt.session import SESSION                # noqa: E402

OK, BAD = "PASS", "FAIL"


def line(t: str) -> None:
    print("\n" + "-" * 72 + f"\n{t}\n" + "-" * 72)


async def gate(name: str, coro, verify=None) -> bool:
    try:
        r = await coro
    except Exception as e:
        print(f"  -> {BAD}  {name}: {type(e).__name__}: {e}")
        return False
    if isinstance(r, dict) and r.get("error"):
        print(f"  -> {BAD}  {name}: [{r.get('kind')}] {r['error']}")
        if r.get("hint"):
            print(f"        hint: {r['hint']}")
        return False
    ok, note = (verify(r) if verify else (True, ""))
    print(f"  -> {'PASS' if ok else 'FAIL'}  {name}  {note}")
    return ok


async def main() -> int:
    today = date.today()
    soon_in = (today + timedelta(days=30)).isoformat()
    soon_out = (today + timedelta(days=32)).isoformat()
    train_day = (today + timedelta(days=30)).isoformat()
    # Far out, but not absurdly: measured 2026-09-04, a +200d Kochi-Rameswaram search
    # renders a full page with genuinely zero cabs, while +45d returns nine. There is
    # no booking window on this endpoint, but vendors do stop bidding eventually.
    far_day = (today + timedelta(days=120)).isoformat()

    results: dict[str, bool] = {}

    line("G0  setup and warmup")
    results["setup"] = await gate(
        "browser reachable", T.TOOLS["mmt_setup_status"]["fn"](),
        lambda r: (bool(r.get("ready")), f"browser={r.get('browser')} "
                                         f"warm={(r.get('warmup') or {}).get('had_abck')}"))

    line("G1  hotel search, with prices")
    def v_search(r):
        hs = r.get("hotels") or []
        priced = [h for h in hs if h.get("nightly_all_in_inr")]
        for h in hs[:3]:
            print(f"     {str(h['name'])[:38]:40} base {h['nightly_base_inr']} + tax "
                  f"{h['nightly_tax_inr']} = {h['nightly_all_in_inr']}/night "
                  f"(stay est {h.get('stay_estimate_all_in_inr')})")
        return bool(priced), f"{len(priced)}/{len(hs)} priced"
    results["hotel_search"] = await gate(
        "hotel search", T.TOOLS["mmt_hotel_search"]["fn"](
            city="Kochi", check_in=soon_in, check_out=soon_out, limit=3, fresh=True),
        v_search)

    line("G2  pin one property, and check the arithmetic")
    def v_pin(r):
        legs = r.get("legs") or []
        if not legs:
            return False, "no legs"
        l = legs[0]
        good = (l["nightly_all_in_inr"] == l["nightly_base_inr"] + l["nightly_tax_inr"]
                and l["stay_all_in_inr"] == round(l["nightly_all_in_inr"] * l["nights"]))
        print(f"     {l['name']}: {l['nightly_base_inr']} + {l['nightly_tax_inr']} = "
              f"{l['nightly_all_in_inr']}/night x {l['nights']}n = "
              f"{l['stay_all_in_inr']}")
        return good, "base + tax == all_in, and stay == nightly x nights"
    results["pin"] = await gate(
        "pinned property", T.TOOLS["mmt_price_itinerary"]["fn"](stays=[{
            "hotel_id": "201211061904322411", "city": "Kochi",
            "check_in": soon_in, "check_out": soon_out, "label": "Courtyard Kochi"}],
            fresh=True), v_pin)

    line("G3  room-level rate plans (the tier-escalation path)")
    def v_rates(r):
        for p in (r.get("rate_plans") or [])[:4]:
            print(f"     {str(p['room'])[:26]:28} {str(p['plan'])[:34]:36} "
                  f"{p['nightly_base_inr']} + {p['nightly_tax_inr']} = "
                  f"{p['nightly_all_in_inr']}/night")
        return r.get("rate_plan_count", 0) > 0, f"tier={r.get('tier_used')}"
    results["rate_plans"] = await gate(
        "rate plans", T.TOOLS["mmt_hotel_rates"]["fn"](
            hotel_id="201211061904322411", city="Kochi", check_in=soon_in,
            check_out=soon_out, fresh=True), v_rates)

    line("G4  flights (slow - drives the site's own search page)")
    def v_fl(r):
        for it in (r.get("itineraries") or [])[:4]:
            alt = "  [other airport]" if it.get("alternate_airport") else ""
            print(f"     {it['airline']} {it['flight_no']} {it['depart']} -> "
                  f"{it['arrive']}  {it['from']}-{it['to']}  "
                  f"base {it['base_inr']} + tax {it['tax_inr']} = "
                  f"{it['all_in_inr']}{alt}")
        if not r.get("itineraries"):
            print(f"     stream returned {r.get('raw_len')} bytes but nothing parsed - "
                  "if that is near zero the results page was stubbed (funnel-first "
                  "rule, see RUNBOOK); if it is large, re-derive parse_stream")
        bad = [it for it in (r.get("itineraries") or [])
               if it["base_inr"] is not None and it["tax_inr"] is not None
               and round(it["base_inr"] + it["tax_inr"], 2) != round(it["all_in_inr"], 2)]
        return bool(r.get("itineraries")) and not bad, f"{r.get('parsed_count')} parsed"
    results["flights"] = await gate(
        "flight search", T.TOOLS["mmt_flight_search"]["fn"](
            origin="BLR", dest="IXE", date=soon_in, fresh=True), v_fl)

    line("G5  trains inside the booking window")
    def v_tr(r):
        for t in (r.get("trains") or [])[:3]:
            c = (t.get("classes") or [{}])[0]
            print(f"     {t['train_number']} {str(t['train_name'])[:24]:26} "
                  f"{t['departure']}->{t['arrival']} {t['duration']}  "
                  f"{c.get('class')} {c.get('status_pretty')} {c.get('fare_inr')}")
        return r.get("train_count", 0) > 0, f"{r.get('train_count')} trains"
    results["trains"] = await gate(
        "train search", T.TOOLS["mmt_train_search"]["fn"](
            origin="MDU", dest="MS", date=train_day, fresh=True), v_tr)

    line("G6  trains outside the window must explain, not report zero")
    r = await T.TOOLS["mmt_train_search"]["fn"](origin="MDU", dest="MS", date=far_day)
    good = r.get("kind") == "not_in_window" and r.get("booking_opens")
    print(f"     {r.get('error')}\n     opens: {r.get('booking_opens')}")
    print(f"  -> {'PASS' if good else 'FAIL'}  window handling")
    results["train_window"] = bool(good)

    line("G7  station to city code")
    results["station_city"] = await gate(
        "getLocusId", T.TOOLS["mmt_station_city"]["fn"](origin="MDU", dest="MS",
                                                        fresh=True),
        lambda r: (r.get("from_city_code") == "CTIXM",
                   f"{r.get('from_city_code')} / {r.get('to_city_code')}"))

    line("G8  cabs, including a far-future date (no booking window applies)")
    def v_cab(r):
        for c in (r.get("cabs") or [])[:5]:
            print(f"     {str(c['car'])[:20]:22} {str(c['category']):10} "
                  f"{str(c['vendor']):12} {c['base_inr']} + {c['tax_fees_inr']} = "
                  f"{c['all_in_inr']}  ({c['all_in_per_km_inr']}/km)")
        return r.get("cab_count", 0) > 0, f"{r.get('distance_km')} km"
    results["cabs"] = await gate(
        "cab quote", T.TOOLS["mmt_cab_quote"]["fn"](
            origin="kochi", dest="rameswaram", date=far_day, fresh=True), v_cab)

    line("G9  cache serves a repeat call")
    import time
    t0 = time.time()
    await T.TOOLS["mmt_hotel_search"]["fn"](city="Kochi", check_in=soon_in,
                                            check_out=soon_out, limit=3)
    dt = time.time() - t0
    results["cache"] = dt < 1.0
    print(f"  -> {'PASS' if dt < 1.0 else 'FAIL'}  repeat call took {dt:.2f}s")

    line("summary")
    for k, v in results.items():
        print(f"  {k:16} {'PASS' if v else 'FAIL'}")
    core = all(results.get(k) for k in ("hotel_search", "pin", "cache"))
    print(f"\nCore hotel pricing: {'USABLE' if core else 'BROKEN'}")
    print("Optional/experimental failures above are acceptable - see docs/RUNBOOK.md")
    await SESSION.close()
    return 0 if core else 1


async def _guarded() -> int:
    try:
        return await main()
    finally:
        # Always reap the browser. A gate that raises must not leave Chrome holding
        # the profile - the next launch would be handed off to it and exit.
        with contextlib.suppress(Exception):
            await SESSION.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_guarded()))
