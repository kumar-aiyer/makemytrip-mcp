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


async def _t2_get(url: str, wait_for: str | None, timeout: float,
                  funnel_url: str | None = None) -> tuple[int, str]:
    """Full page render - solves bot interstitials but pays for rendering.

    `funnel_url`, when given, is loaded first in the same page. Akamai serves the
    169-byte "200-OK" stub instead of /cabs/listing to a browser that arrives there
    cold; visiting the funnel page (/cabs/) first establishes the sensor and referer
    chain a real user would have, and the listing then renders in full. Verified
    2026-09-04: cold -> stub, funnel-first -> 10 cab cards.
    """
    async with SESSION.page() as page:
        if funnel_url:
            with contextlib.suppress(Exception):
                await page.goto(funnel_url, wait_until="domcontentloaded",
                                timeout=timeout * 1000)
                await page.wait_for_timeout(6000)
        resp = await page.goto(url, wait_until=wait_for or "load", timeout=timeout * 1000)
        if resp is None:
            raise Transport("The page did not respond.")
        # Best effort. A page that never goes quiet (ads, polling) must not fail a
        # fetch whose content is already there - the validator decides that.
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=15_000)
        return resp.status, await page.content()


async def _evaluate_retrying(page, script: str, arg: Any, attempts: int = 4):
    """page.evaluate, retried across the homepage's periodic self-navigation.

    The MMT homepage re-navigates itself every few seconds (Akamai sensor). An
    evaluate that lands on one of those moments dies with "Execution context was
    destroyed" - a timing accident, not a refusal, so retry rather than escalate.
    """
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await page.evaluate(script, arg)
        except Exception as e:
            if "Execution context was destroyed" not in str(e):
                raise
            last = e
            with contextlib.suppress(Exception):
                await page.wait_for_timeout(1500 * (i + 1))
    raise Transport(f"In-page fetch could not run: {last}",
                    hint="The page kept navigating under the call. Retrying usually "
                         "clears it.")


async def _t2_post(url: str, body: dict, headers: dict[str, str],
                   timeout: float) -> tuple[int, str]:
    """POST via in-page fetch() from a page allowed to make it.

    The browser's JS engine and live cookie jar get past the Akamai sensor checks
    that reject a T1/ctx.request POST - still true on a self-launched Chrome, where
    ctx.request.post returns the six-byte "200-OK" stub (re-measured 2026-09-05).

    Two details are load-bearing and were both found the hard way: the page must be
    a hotel *listing* page (see C.HOTEL_API_CONTEXT), and its cookies must be left
    alone.
    """
    async with SESSION.page() as page:
        # Cookies are deliberately NOT cleared. The original T2-POST recipe cleared
        # them to get "fresh clearance", but measured 2026-09-05 that is exactly what
        # breaks the call now: cleared, the fetch dies as "TypeError: Failed to fetch";
        # left alone, it returns the full payload.
        await page.goto(C.HOTEL_API_CONTEXT, wait_until="domcontentloaded",
                        timeout=timeout * 1000)
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("load", timeout=15_000)
        await page.wait_for_timeout(1500)
        safe = {k: v for k, v in headers.items()
                if k.lower() not in ('user-agent', 'accept-encoding', 'connection',
                                     'cookie', 'cookie2', 'origin', 'referer',
                                     'host', 'via', 'upgrade')}
        res = await _evaluate_retrying(page, """async ({url, body, headers}) => {
            try {
                const r = await fetch(url, {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify(body),
                    credentials: 'include'
                });
                return {status: r.status, text: await r.text()};
            } catch(e) {
                return {error: e.toString()};
            }
        }""", {"url": url, "body": body, "headers": safe})
        if "error" in res:
            raise Transport(f"In-page POST fetch failed: {res['error']}",
                            hint="The browser may have been reaped, or the request was blocked.")
        return res["status"], res["text"]


async def _t2_fetch_get(url: str, headers: dict[str, str], timeout: float,
                        context_url: str) -> tuple[int, str]:
    """GET an API via in-page fetch() from a same-site context page.

    For API endpoints on other subdomains (flights-cb, mapi), navigating the
    browser directly to the API URL is a NAVIGATION request, which Akamai
    blocks. A real browser never does that - the site's page calls the API via
    XHR with its own origin, referer and sensor state. This mirrors that: load
    the context page (e.g. www.makemytrip.com/flights/), then fetch the API
    from inside it with credentials.
    """
    async with SESSION.page() as page:
        await page.goto(context_url, wait_until="domcontentloaded",
                        timeout=timeout * 1000)
        safe = {k: v for k, v in headers.items()
                if k.lower() not in ('user-agent', 'accept-encoding', 'connection',
                                     'cookie', 'cookie2', 'origin', 'referer',
                                     'host', 'via', 'upgrade')}
        res = await page.evaluate("""async ({url, headers}) => {
            try {
                const r = await fetch(url, {
                    method: 'GET',
                    headers: headers,
                    credentials: 'include'
                });
                return {status: r.status, text: await r.text()};
            } catch(e) {
                return {error: e.toString()};
            }
        }""", {"url": url, "headers": safe})
        if "error" in res:
            raise Transport(f"In-page GET fetch failed: {res['error']}",
                            hint="The context page may have been blocked, or the API "
                                 "rejected the cross-origin call.")
        return res["status"], res["text"]


# --------------------------------------------------------------------- public fetch

_LAST_BLOCKED: dict[str, float] = {}
_RECOVER_AFTER_S = 5.0


async def _maybe_recover(ec: str, kind: str) -> None:
    """Close the stale-clearance loop (F1): only a *blocked* outcome means the Akamai
    clearance itself is stale. Two such outcomes within a few seconds relaunch the
    browser fresh on the same profile - a fresh context plus a page warm beats retrying
    a rejected one."""
    if kind != "blocked":
        return
    now = time.time()
    prev = _LAST_BLOCKED.get(ec)
    _LAST_BLOCKED[ec] = now
    if prev is None or (now - prev) > _RECOVER_AFTER_S:
        return
    await SESSION.close()
    # ensure() re-launches and single-warms (close() clears the warm flag), so an
    # explicit warmup here would navigate the homepage twice.
    await SESSION.ensure()


def _record_failure(ec: str, err: MMTError) -> None:
    """Best-effort failure record for the runbook triage step. Metadata only - full
    response bodies and screenshots are deliberately not written."""
    try:
        C.DIAG_DIR.mkdir(parents=True, exist_ok=True)
        with (C.DIAG_DIR / "failures.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "at": _now_iso(), "ec": ec, "kind": err.kind,
                "message": err.message, "attempts": err.details.get("attempts"),
            }) + "\n")
    except Exception:
        pass


async def get_text(url: str, *, ec: str, headers: dict[str, str] | None = None,
                   wait_for: str | None = None, timeout: float = 45.0,
                   fresh: bool = False, cache_ttl: float = PRICE_TTL,
                   cache_id: str | None = None, context_url: str | None = None,
                   funnel_url: str | None = None,
                   validate: Callable[[str], bool] | None = None) -> FetchResult:
    """GET with caching. `validate`, when given, runs on the body before caching:
    a silent-200 body that fails the caller's check is never cached (F3). A validator
    may return False for a generic unusable body, or raise an MMTError to name the
    specific kind (e.g. NullPrices) - either way the body is not cached."""
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
            elif context_url is not None:
                # API endpoints on other subdomains: fetch from a context page
                # (in-page XHR) rather than navigating to the API URL directly.
                status, text = await _t2_fetch_get(url, hdrs, timeout, context_url)
            else:
                status, text = await _t2_get(url, wait_for, timeout, funnel_url)

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

            res = FetchResult(text=text, status=status, tier_used=int(tier),
                              elapsed_ms=int((time.time() - t0) * 1000),
                              fetched_at=_now_iso(), attempts=attempts)
            if validate is not None and not validate(text):
                # A validator returns False for a generic unusable body, or raises an
                # MMTError to name the specific kind (e.g. NullPrices) - either way the
                # body is not a routing success and is never cached: record(True) waits
                # until this gate passes.
                raise ShapeDrift("Payload failed the caller's validity check.",
                                 hint="Silent 200 with an unusable body. Not cached.")
            ROUTER.record(ec, tier, True)
            CACHE.put(ck, {"text": text, "tier": int(tier), "at": res.fetched_at},
                      ttl=cache_ttl)
            return res
        except MMTError as e:
            ROUTER.record(ec, tier, False)
            attempts.append(f"tier{int(tier)}:{e.kind}")
            last = e
            if not e.escalate:
                raise
            await _maybe_recover(ec, e.kind)
            await asyncio.sleep(0.6 + random.random() * 0.6)
        except Exception as e:
            ROUTER.record(ec, tier, False)
            attempts.append(f"tier{int(tier)}:{type(e).__name__}")
            last = Transport(f"{type(e).__name__}: {e}")
            await asyncio.sleep(0.6 + random.random() * 0.6)

    assert last is not None
    last.details["attempts"] = attempts
    _record_failure(ec, last)
    raise last


async def post_json(url: str, body: dict, *, ec: str,
                    headers: dict[str, str] | None = None, timeout: float = 45.0,
                    fresh: bool = False, cache_ttl: float = PRICE_TTL,
                    cache_id: str | None = None,
                    validate: Callable[[dict], bool] | None = None) -> FetchResult:
    """JSON POST (the hotel search API). `validate` gates caching exactly as in get_text:
    return False, or raise an MMTError to name the specific failure kind.

    `cache_id` exists because the body is not a usable cache key: it carries a fresh
    requestId per call, so keying on it gave every search its own entry and the cache
    never hit. Callers pass a key built from what the search actually means."""
    ck = cache_id or cache_key("POST:" + ec, {"url": url, "body": body})
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
            pass  # _t2_post handles this below
        t0 = time.time()
        try:
            hdrs = headers or C.hotel_headers(SESSION.ua)
            if tier == Tier.HTTP:
                status, text = await asyncio.to_thread(_t0_post, url, body, hdrs, timeout)
            elif tier == Tier.REQUEST:
                status, text = await _t1_post(url, body, hdrs, timeout)
            else:
                status, text = await _t2_post(url, body, hdrs, timeout)

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

            res = FetchResult(data=data, status=status, tier_used=int(tier),
                              elapsed_ms=int((time.time() - t0) * 1000),
                              fetched_at=_now_iso(), attempts=attempts)
            if validate is not None and not validate(data):
                # Same contract as get_text: a validator returns False for a generic
                # unusable body, or raises an MMTError (e.g. NullPrices) to name the
                # specific kind. Either way the body is never cached, and record(True)
                # waits until this gate passes.
                raise ShapeDrift("Payload failed the caller's validity check.",
                                 hint="Silent 200 with an unusable body. Not cached.")
            ROUTER.record(ec, tier, True)
            CACHE.put(ck, {"data": data, "tier": int(tier), "at": res.fetched_at},
                      ttl=cache_ttl)
            return res
        except MMTError as e:
            ROUTER.record(ec, tier, False)
            attempts.append(f"tier{int(tier)}:{e.kind}")
            last = e
            if not e.escalate:
                raise
            await _maybe_recover(ec, e.kind)
            await asyncio.sleep(0.6 + random.random() * 0.6)
        except Exception as e:
            ROUTER.record(ec, tier, False)
            attempts.append(f"tier{int(tier)}:{type(e).__name__}")
            last = Transport(f"{type(e).__name__}: {e}")
            await asyncio.sleep(0.6 + random.random() * 0.6)

    assert last is not None
    last.details["attempts"] = attempts
    _record_failure(ec, last)
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