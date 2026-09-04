"""Unified fetch across the three tiers, with routing, retries, caching and diagnostics.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, TypeVar

from . import config as C
from .cache import CACHE, PAGE_SIZE_CAP, PRICE_TTL, key as cache_key
from .errors import Blocked, MMTError, ShapeDrift, Transport
from .router import ROUTER, Tier
from .session import SESSION

T = TypeVar("T")

BLOCK_MARKERS = ("Access Denied", "Reference #", "akamai", "Pardon Our Interruption",
                 "bot detection")


@dataclass
class FetchResult:
    text: str = ""
    data: Any = None
    tier_used: int = -1
    status: int = 0
    elapsed_ms: int = 0
    cached: bool = False
    fetched_at: str = ""
    attempts: list[str] = field(default_factory=list)

    def meta(self) -> dict[str, Any]:
        return {"tier_used": self.tier_used, "elapsed_ms": self.elapsed_ms,
                "cached": self.cached, "fetched_at": self.fetched_at}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def _looks_blocked(status: int, text: str) -> bool:
    if status in (403, 429):
        return True
    head = text[:4000]
    return any(m.lower() in head.lower() for m in BLOCK_MARKERS)


# --------------------------------------------------------------------------- tier 0

def _t0_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={**headers, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        raise Transport(f"{type(e).__name__}: {e}",
                        hint="No network path to MakeMyTrip, or a proxy refused it.") from e


def _t0_post(url: str, body: dict, headers: dict[str, str],
             timeout: float) -> tuple[int, str]:
    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=raw, method="POST",
        headers={**headers, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        raise Transport(f"{type(e).__name__}: {e}",
                        hint="No network path to MakeMyTrip, or a proxy refused it.") from e


# ------------------------------------------------------------------- tier 1 and 2

async def _t1_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str]:
    api = await SESSION.request()
    async with SESSION.slot():
        r = await api.get(url, headers=headers, timeout=timeout * 1000)
        return r.status, await r.text()


async def _t1_post(url: str, body: dict, headers: dict[str, str],
                   timeout: float) -> tuple[int, str]:
    api = await SESSION.request()
    async with SESSION.slot():
        r = await api.post(url, data=body, headers=headers, timeout=timeout * 1000)
        return r.status, await r.text()


async def _t2_get(url: str, wait_for: str | None, timeout: float) -> tuple[int, str]:
    """Full page render - solves bot interstitials but pays for rendering."""
    async with SESSION.page() as page:
        resp = await page.goto(url, wait_until=wait_for or "load", timeout=timeout * 1000)
        if resp is None:
            raise Transport("The page did not respond.")
        await page.wait_for_load_state("networkidle")
        return resp.status, await page.content()


# --------------------------------------------------------------------- public fetch

_LAST_BLOCKED: dict[str, float] = {}
_RECOVER_AFTER_S = 5.0


async def _maybe_recover(ec: str) -> None:
    """Close the stale-clearance loop (F1): when an endpoint class accumulates two
    blocked results, relaunch the browser fresh (same profile) and re-warm before the
    next attempt. Without this, a stale Akamai cookie deadlocks until the idle reap."""
    now = time.time()
    prev = _LAST_BLOCKED.get(ec)
    _LAST_BLOCKED[ec] = now
    if prev is None or (now - prev) > _RECOVER_AFTER_S:
        return
    await SESSION.close()
    await SESSION.ensure()
    with contextlib.suppress(Exception):
        await SESSION.warmup(force=True)
async def get_text(url: str, *, ec: str, headers: dict[str, str] | None = None,
                   wait_for: str | None = None, timeout: float = 45.0,
                   fresh: bool = False, cache_ttl: float = PRICE_TTL,
                   cache_id: str | None = None,
                   validate: Callable[[str], bool] | None = None) -> FetchResult:
    """GET with caching. `validate`, when given, runs on the body before caching:
    a silent-200 body that fails the caller's check is never cached (F3)."""
    ck = cache_id or cache_key("GET:" + ec, {"url": url})
    if not fresh:
        hit = CACHE.get(ck)
        if hit is not None:
            return FetchResult(text=hit["text"], status=200, tier_used=hit["tier"],
                               cached=True, fetched_at=hit["at"], elapsed_ms=0)

    plan = ROUTER.plan(ec)
    if not plan:
        raise Blocked(f"Circuit open for {ec} after repeated failures.",
                      hint="Wait about two minutes, or call mmt_selftest to re-probe.")

    last: MMTError | None = None
    attempts: list[str] = []
    for tier in plan:
        t0 = time.time()
        try:
            hdrs = headers or C.page_headers(SESSION.ua)
            if tier == Tier.HTTP:
                status, text = await asyncio.to_thread(_t0_get, url, hdrs, timeout)
            elif tier == Tier.REQUEST:
                status, text = await _t1_get(url, hdrs, timeout)
            else:
                status, text = await _t2_get(url, wait_for, timeout)

            if _looks_blocked(status, text):
                raise Blocked(f"MakeMyTrip refused the request (HTTP {status}) at "
                              f"tier {int(tier)}.",
                              hint="Escalating to a real browser render usually clears "
                                   "this; a persistent block means the client IP is "
                                   "flagged.")
            if status >= 400:
                raise Transport(f"HTTP {status} from MakeMyTrip.")

            # Whole-HTML bodies are capped so a cache full of pages cannot balloon
            # into hundreds of MB resident (F5).
            if len(text) > PAGE_SIZE_CAP:
                raise ShapeDrift(
                    f"HTTP 200 body of {len(text):,} bytes exceeds the "
                    f"{PAGE_SIZE_CAP:,}-byte page cache cap.",
                    hint="MakeMyTrip changed the page, or a proxy wrapped it. This is "
                         "not cached, so the next call re-fetches fresh.")

            ROUTER.record(ec, tier, True)
            res = FetchResult(text=text, status=status, tier_used=int(tier),
                              elapsed_ms=int((time.time() - t0) * 1000),
                              fetched_at=_now_iso(), attempts=attempts)
            if validate is not None and not validate(text):
                raise ShapeDrift("Payload failed the caller's validity check.",
                                 hint="Silent 200 with an unusable body. Not cached.")
            CACHE.put(ck, {"text": text, "tier": int(tier), "at": res.fetched_at},
                      ttl=cache_ttl)
            return res
        except MMTError as e:
            ROUTER.record(ec, tier, False)
            attempts.append(f"tier{int(tier)}:{e.kind}")
            last = e
            if not e.escalate:
                raise
            await _maybe_recover(ec)
            await asyncio.sleep(0.6 + random.random() * 0.6)
        except Exception as e:
            ROUTER.record(ec, tier, False)
            attempts.append(f"tier{int(tier)}:{type(e).__name__}")
            last = Transport(f"{type(e).__name__}: {e}")
            await asyncio.sleep(0.6 + random.random() * 0.6)

    assert last is not None
    last.details["attempts"] = attempts
    raise last
async def post_json(url: str, body: dict, *, ec: str,
                    headers: dict[str, str] | None = None, timeout: float = 45.0,
                    fresh: bool = False, cache_ttl: float = PRICE_TTL,
                    validate: Callable[[dict], bool] | None = None) -> FetchResult:
    """JSON POST (the hotel search API). `validate` gates caching exactly as in get_text."""
    ck = cache_key("POST:" + ec, {"url": url, "body": body})
    if not fresh:
        hit = CACHE.get(ck)
        if hit is not None:
            return FetchResult(data=hit["data"], status=200, tier_used=hit["tier"],
                               cached=True, fetched_at=hit["at"], elapsed_ms=0)

    plan = ROUTER.plan(ec)
    if not plan:
        raise Blocked(f"Circuit open for {ec} after repeated failures.",
                      hint="Wait about two minutes, or call mmt_selftest to re-probe.")

    last: MMTError | None = None
    attempts: list[str] = []
    for tier in plan:
        if tier == Tier.PAGE:
            tier = Tier.REQUEST      # no page-render path for a POST API
        t0 = time.time()
        try:
            hdrs = headers or C.hotel_headers(SESSION.ua)
            if tier == Tier.HTTP:
                status, text = await asyncio.to_thread(_t0_post, url, body, hdrs, timeout)
            else:
                status, text = await _t1_post(url, body, hdrs, timeout)

            if _looks_blocked(status, text):
                raise Blocked(f"MakeMyTrip refused the request (HTTP {status}).",
                              hint="Escalating to the browser network stack usually "
                                   "clears this.")
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                raise Transport(
                    "MakeMyTrip returned a non-JSON body. Something between this machine "
                    f"and MakeMyTrip is intercepting the request. Body began: {text[:120]!r}",
                    hint="A captive proxy or TLS interceptor returns 200 with a stub "
                         "body. This is not a problem with the request.") from None
            if status >= 400:
                raise Transport(f"HTTP {status}: {text[:200]}")

            ROUTER.record(ec, tier, True)
            res = FetchResult(data=data, status=status, tier_used=int(tier),
                              elapsed_ms=int((time.time() - t0) * 1000),
                              fetched_at=_now_iso(), attempts=attempts)
            if validate is not None and not validate(data):
                raise ShapeDrift("Payload failed the caller's validity check.",
                                 hint="Silent 200 with an unusable body. Not cached.")
            CACHE.put(ck, {"data": data, "tier": int(tier), "at": res.fetched_at},
                      ttl=cache_ttl)
            return res
        except MMTError as e:
            ROUTER.record(ec, tier, False)
            attempts.append(f"tier{int(tier)}:{e.kind}")
            last = e
            if not e.escalate:
                raise
            await _maybe_recover(ec)
            await asyncio.sleep(0.6 + random.random() * 0.6)
        except Exception as e:
            ROUTER.record(ec, tier, False)
            attempts.append(f"tier{int(tier)}:{type(e).__name__}")
            last = Transport(f"{type(e).__name__}: {e}")
            await asyncio.sleep(0.6 + random.random() * 0.6)

    assert last is not None
    last.details["attempts"] = attempts
    raise last


async def gather_limited(coros: Iterable[Awaitable[T]], limit: int = 4,
                         jitter_ms: tuple[int, int] = (150, 400)) -> list:
    """Bounded-concurrency gather with jitter. Exceptions are returned, not raised, so
    one failed leg never aborts an itinerary."""
    sema = asyncio.Semaphore(limit)

    async def run(c: Awaitable[T]):
        async with sema:
            await asyncio.sleep(random.uniform(*jitter_ms) / 1000)
            try:
                return await c
            except Exception as e:
                return e

    return await asyncio.gather(*(run(c) for c in coros))


def require(cond: bool, message: str, *, hint: str | None = None) -> None:
    if not cond:
        raise ShapeDrift(message, hint=hint or
                         "MakeMyTrip changed a payload shape. See docs/API-REFERENCE.md "
                         "for the re-capture recipe.")