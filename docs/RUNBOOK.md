# Runbook

## Triage order

1. `mmt_setup_status` — is there a working browser?
2. `mmt_selftest` — which capability broke, and which tier is each endpoint on?
3. `<state>/diagnostics/failures.jsonl` — the last failures: endpoint, error kind,
   message and which tiers were attempted. Metadata only — response bodies and
   screenshots are not stored.
4. `MMT_HEADFUL=1` — watch the browser. Fastest way to understand a block.

## Symptoms

| Symptom | Cause | Fix |
|---|---|---|
| HTTP 200, hotels listed, every price `null` | `expData` / `featureFlags` trimmed | Restore both complete in `mmt/config.py`. Surfaces as `null_prices` |
| 403 from everything, all tiers | Datacenter IP, or the client IP is flagged | Run from a residential connection. Verified: cloud VMs get `403 AkamaiGHost` |
| `blocked` at T1, works at T2 | Akamai wants a rendered challenge | Nothing to do — the router escalates. Persistent T2 means slow but working |
| Hotels missing from the response | Shape moved off `personalizedSections[].hotels` | `mmt/hotels.py::flatten` |
| `Missing Header <x>` (403) on flights | The flights gate wants another header | Add `<x>` to `config.flight_headers()` — the error names it |
| Detail page has no `__INITIAL_STATE__` | Interstitial, or the page changed | Router escalates to T2; if T2 also fails, `mmt_hotel_search` still gives property-level pricing |
| Zero trains for a real route | Date outside the 60-day window | Expected. The result carries `booking_opens` |
| Every train shows unavailable | Someone "fixed" the `availablity` misspelling | Spell it MakeMyTrip's way |
| Zero cabs, HTTP 200 | Place object trimmed or missing `place_id` | Re-harvest with `mmt_cab_find_place` |
| Empty result for a real city | Wrong locus code | The tool warns; check `cityLocationDetail` |
| 200 with a non-JSON body | Captive proxy or TLS interceptor | The error says so explicitly — it is not a request problem |
| Server starts, no tools appear | stdout polluted | Only protocol frames on stdout; everything else to stderr |
| Server appears to hang | Buffered stdout | `PYTHONUNBUFFERED=1` |
| `UnicodeEncodeError` on `₹` | Windows cp1252 console | `PYTHONIOENCODING=utf-8` |
| First call times out in OpenClaw | Cold start launches a browser | Raise `requestTimeoutMs` well above 20 s |
| Plugin absent after install | Zip root wrong, or a bad plugin name | `unzip -l`; kebab-case name |

## When MakeMyTrip changes something

1. `mmt_selftest` to identify which capability broke.
2. Re-capture per [API-REFERENCE.md](API-REFERENCE.md) §7.
3. Save a trimmed real payload into `tests/fixtures/`.
4. Extend `tests/test_parsers.py` **first**, then fix the parser.
5. `python tools/probe.py` to confirm live.

Assert on structure and arithmetic (`base + tax == all_in`), never on particular prices.

## Performance budget

| Operation | Target |
|---|---|
| `tools/list` | < 2 s, no browser |
| Cold start incl. warmup | < 20 s, once per session |
| Hotel search (warm) | < 3 s |
| Rate plans / trains / cabs (warm) | < 5 s |
| 14-leg itinerary | < 25 s |
| Cab place harvest | < 30 s |
| Cached repeat | < 50 ms |

A warm call consistently over ~8 s means the router is sitting at T2. `mmt_selftest` shows
which endpoint class and why.

## Politeness

One stable device id, concurrency capped at 4, 150–400 ms jitter between batched calls, one
retry maximum, no scheduled polling. Keep usage conversational. If MakeMyTrip starts
returning 403 at every tier from a residential connection, stop rather than working around it.
