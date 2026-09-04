# Design

## The problem this shape solves

MakeMyTrip refuses plain HTTP clients. Verified: a `curl` from a datacenter IP gets
`403 AkamaiGHost` on `www.makemytrip.com` and `mapi.makemytrip.com`, while
`pypi.org`, `google.com` and `api.github.com` all return 200 from the same machine. Two
variables are confounded (IP reputation and TLS fingerprint) but the conclusion is
actionable either way: **look like a browser, and run from a residential connection.**

The load-bearing API is Playwright's `BrowserContext.request`. It issues HTTP through
Chromium's own network stack — real TLS fingerprint, the context's cookie jar, browser-shaped
headers — **without rendering a page**. That is the same condition under which every finding
in [API-REFERENCE.md](API-REFERENCE.md) was originally observed, so the reference transfers
directly rather than being extrapolated across a client boundary. It also sidesteps CORS,
which is the only thing that blocks the flights endpoint from in-page JavaScript.

## Tiers

| Tier | Mechanism | Latency | Used for |
|---|---|---|---|
| **T0** | `urllib` | 0.2–0.8 s | The hotel JSON API only — no bot sensor observed on that host |
| **T1** | `context.request` | 0.3–1.5 s | **Default.** All JSON APIs and all three RSC/SSR pages |
| **T2** | `page.goto` + wait | 4–12 s | Bot interstitials, and driving forms |

`mmt/router.py` keeps a state machine per *endpoint class*:

```
HEALTHY --(2 consecutive failures)--> DEGRADED --(1 failure)--> BROKEN
   ^                                      |                        |
   +-----(1 success)----------------------+---(1 success)----------+
```

`HEALTHY` tries the preferred tier and escalates once on failure. `DEGRADED` skips the cheap
tier. `BROKEN` opens the circuit for 120 s and fails fast rather than burning 12 s per call.

**Escalation is one-way within a call and decays over time**, so a transient blip does not
pin the server to the slow tier. Every result carries `tier_used`, so slowness is visible as
a number rather than a vague feeling.

**Empty-but-valid results never escalate.** Zero trains outside the booking window and zero
cabs for an unregistered place are *correct answers*. Escalating on them wastes 12 s and
teaches the router the wrong thing, so the parser boundary distinguishes "transport failed"
from "parsed cleanly, no rows".

## Session

One browser, launched lazily on the first *data* call — `mmt_capabilities` and
`mmt_setup_status` answer without one, so `tools/list` stays under two seconds.

- **Persistent profile** at `<state>/chrome-profile`, so Akamai cookies survive restarts.
- **Warmup** navigates the homepage once and asserts `_abck` / `bm_sz` landed.
- **Browser preference**: `chrome` → `msedge` → bundled Chromium. Driving a browser the
  machine already has avoids a 150 MB download and gives a better fingerprint. The UA is read
  from the browser actually launched rather than hard-coded — a Chrome-141 UA over a
  Chromium-120 TLS fingerprint is more suspicious than either alone.
- **Idle reap** after 300 s; the next call relaunches transparently.
- **Locks**: one for session mutation, one serializing page operations (concurrent
  `page.goto` on a single context is where flakiness lives), and a semaphore of 4 for
  tier-1 requests.
- **Jitter** of 150–400 ms between batched calls. Fourteen identical requests landing in the
  same 50 ms is the signature this is trying not to emit.

## Errors

Every failure resolves to exactly one kind (`mmt/errors.py`). This is the core of the design,
because MakeMyTrip's characteristic failure is a **silent HTTP 200**:

| Kind | Retry | Escalate | Why it exists |
|---|---|---|---|
| `bad_input` | no | no | Unknown city/station/place; the error lists the valid set |
| `not_in_window` | no | **no** | Train dates beyond 60 days; carries `booking_opens` |
| `empty_valid` | no | **no** | Genuinely zero rows |
| `unregistered_place` | no | no | Cab place unknown; names the remedy |
| `blocked` | once | yes | Akamai challenge or 403 |
| `transport` | once | yes | DNS, timeout, or a proxy stub body |
| `shape_drift` | no | once | 200 with expected keys missing |
| `null_prices` | no | no | 200, rows present, all prices null |
| `browser` | once | — | No launchable browser; points at `mmt_setup_status` |

`null_prices` earns its own kind because it is the one failure that otherwise reads as total
success: correct hotels, every rupee figure `null`. A generic error would let it surface as
"no prices available for these dates".

## Caching

Keyed on the canonical normalized arguments. 20 minutes for prices, 24 hours for structural
lookups, never persisted to disk — a stale rupee figure resurrected three days later is worse
than a slow call. Every result carries `cached` and `fetched_at`, so any number presented to
a user can be dated. `fresh: true` bypasses.

A response is cached **only after the caller's parser validates it**: a silent HTTP 200 whose
body has no usable prices (the `null_prices` trap) is a failure and is never cached, so the bad
body cannot be resurrected for 20 minutes. Whole-HTML pages (train/cab listings) are held under
a byte budget so a cache full of pages cannot balloon into hundreds of MB resident.

## Layering

```
server.py  ->  mmt/tools.py  ->  domain modules  ->  fetch  ->  router  ->  session
```

Nothing calls back up. Parsers are **pure functions from text to dicts** and import nothing
from `session`, `router` or `fetch` — which is why `tests/test_parsers.py` runs its 63
assertions with no network and no browser, and why most of the real test value is free.

## Protocol

MCP is implemented directly rather than through an SDK, so the only runtime dependency is
Playwright — and even that is optional. The SDK route would pull in `pydantic-core`, a
compiled wheel that must match the host's exact Python build, which is a poor fit for
something distributed as a zip a user accepts in a chat window.

stdin is read on a worker thread rather than through `loop.connect_read_pipe`: that API does
not work on Windows' ProactorEventLoop and fails on any stdin that cannot be polled. stdout
carries protocol frames and nothing else; diagnostics go to stderr.

`initialize` negotiates the protocol revision: the server replies with the client's requested
version when it is one the server also supports (`2025-06-18`, `2025-03-26`, `2024-11-05`),
else with its own latest.

## Deliberately absent

No booking, cart, hold, checkout or payment path. No login, session cookies, `mmt-auth`, or
member rates. No credential storage — there are no credentials, which is a property worth
keeping. No scheduled polling or price-history collection.
