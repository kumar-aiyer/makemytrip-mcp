"""UI driving - tier 2 only. The capability a browser buys that plain HTTP cannot.

MakeMyTrip exposes no cab-location autosuggest endpoint, so a place object with a
Google place_id can only be obtained by using the search form.
"""
from __future__ import annotations

import contextlib
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import config as C
from .errors import BadInput, Blocked
from .session import SESSION

SUGGEST_HINT = "locations"


async def harvest_place(query: str, *, timeout_ms: int = 25_000) -> dict[str, Any]:
    """Drive the cab search form to capture a full place object for `query`.

    The location field is genuinely flaky: the overlay input sometimes does not take
    focus, so a click-wait-type sequence is retried once. Do not interleave other
    interactions between the click and the type - it closes the overlay.
    """
    captured: list[dict] = []

    async with SESSION.page() as page:
        async def on_response(resp):
            try:
                if SUGGEST_HINT in resp.url and resp.request.resource_type in (
                        "xhr", "fetch"):
                    body = await resp.json()
                    captured.append(body)
            except Exception:
                pass

        page.on("response", on_response)
        await page.goto(C.CAB_HOME + "?cc=IN&lang=eng", wait_until="domcontentloaded")
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=12_000)

        typed = False
        for attempt in range(2):
            try:
                field = page.locator(
                    "input[placeholder*='From' i], input[id*='from' i], "
                    "input[type='text']").first
                await field.click(timeout=8_000)
                await page.wait_for_timeout(3000)
                await page.keyboard.type(query, delay=90)
                typed = True
                break
            except Exception:
                if attempt == 1:
                    raise Blocked(
                        "Could not focus the cab location field.",
                        hint="Run with MMT_HEADFUL=1 to watch what the page does, or "
                             "fall back to mmt_cab_add_place with a pasted URL.")
                await page.wait_for_timeout(1500)

        if typed:
            await page.wait_for_timeout(2500)
            with contextlib.suppress(Exception):
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
            await page.wait_for_timeout(1500)

        url_now = page.url

    place = _place_from_captured(captured, query) or _place_from_url(url_now)
    if not place:
        raise BadInput(
            f"Could not capture a place object for {query!r}.",
            hint="Search that route once on makemytrip.com/cabs and paste the listing "
                 "URL into mmt_cab_add_place instead - the manual path always works.",
            details={"page_url": url_now})
    return place


def _place_from_captured(bodies: list[dict], query: str) -> dict[str, Any] | None:
    q = query.strip().lower()
    best: dict[str, Any] | None = None
    for body in bodies:
        for node in _walk(body):
            if not isinstance(node, dict) or not node.get("place_id"):
                continue
            name = str(node.get("city") or node.get("main_text") or "").lower()
            if q in name or name in q:
                return node
            best = best or node
    return best


def _place_from_url(url: str) -> dict[str, Any] | None:
    qs = parse_qs(urlparse(url).query)
    for side in ("from", "fromCity", "to"):
        raw = (qs.get(side) or [None])[0]
        if not raw or raw == "null":
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("place_id"):
            return obj
    return None


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)
