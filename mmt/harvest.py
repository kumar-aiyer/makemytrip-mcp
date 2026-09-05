"""UI driving - tier 2 only. The capability a browser buys that plain HTTP cannot.

MakeMyTrip exposes no cab-location autosuggest endpoint, so a place object with a
Google place_id can only be obtained by using the search form.

DOM facts proven by live diagnostic (2026-09-05):
- A login modal (SECTION.modalMain, data-cy=CommonModal_2) blocks all interaction
  until dismissed. Close via span.commonModal__close; a charDham banner may also
  appear - close via button.charDhamBanner__closeBtn.
- The cabs form defaults to the Outstation One-Way tab (li.b2c_selected) - no
  click needed.
- input#fromCity is a READONLY display widget. Clicking label[for='fromCity']
  opens a react-autosuggest overlay whose editable input is
  input.react-autosuggest__input (placeholder "From").
- The autosuggest endpoint is cabs.makemytrip.com/autocomplete/v3 - the URL
  contains "autocomplete", not "locations".
"""
from __future__ import annotations

import contextlib
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import config as C
from .errors import BadInput, Blocked
from .session import SESSION

SUGGEST_HINT = "autocomplete"   # proven: cabs.makemytrip.com/autocomplete/v3


async def _dismiss_popups(page) -> None:
    """Close the login modal and any banner that intercepts page interaction."""
    for sel in ("span.commonModal__close", "button.charDhamBanner__closeBtn"):
        with contextlib.suppress(Exception):
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click(timeout=4000)
                await page.wait_for_timeout(600)


async def harvest_place(query: str, *, timeout_ms: int = 25_000) -> dict[str, Any]:
    """Drive the cab search form to capture a full place object for `query`."""
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
        await page.goto(C.CAB_HOME + "?cc=IN&lang=eng", wait_until="domcontentloaded",
                        timeout=timeout_ms)
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=12_000)

        await _dismiss_popups(page)

        # Click the from-city widget label (NOT the readonly input) to open the
        # react-autosuggest overlay.
        await page.locator("label[for='fromCity']").click(timeout=8000)
        await page.wait_for_timeout(1000)

        # The overlay's editable input (placeholder "From").
        await page.locator("input.react-autosuggest__input").first.click(timeout=6000)
        await page.keyboard.type(query, delay=90)
        await page.wait_for_timeout(2500)

        # Select the best-matching rendered suggestion rather than blindly
        # pressing ArrowDown+Enter (which picks the first alphabetical entry -
        # "Goa" would select "Goalpara, Assam").
        await _click_best_suggestion(page, query)
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


async def _click_best_suggestion(page, query: str) -> None:
    """Click the rendered suggestion whose text best matches the query.

    Prefers an item whose text starts with the query (e.g. "Goa" over
    "Goalpara"), falling back to the first item containing it as a prefix-word.
    Never raises - the captured response remains usable even without a click.
    """
    with contextlib.suppress(Exception):
        items = page.locator("li.react-autosuggest__suggestion")
        count = await items.count()
        q = query.strip().lower()
        best_idx = -1
        for i in range(min(count, 8)):
            text = (await items.nth(i).text_content() or "").strip().lower()
            if text.startswith(q):
                best_idx = i          # exact prefix beats substring
                break
            if q in text and best_idx < 0:
                best_idx = i
        if best_idx < 0 and count > 0:
            best_idx = 0
        if best_idx >= 0:
            await items.nth(best_idx).click(timeout=4000)


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
