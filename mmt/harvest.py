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
    """Pick the best place object, preferring regional relevance over prefix luck.

    Priority: exact name == query, then first-segment == query, then places whose
    secondary_text contains the query (they are IN the region - e.g. "Panaji"
    with secondary "Goa, India" for query "goa"), then first-segment startswith,
    then substring, then the first place seen. This stops "goa" matching
    "Goalpara, Assam" (prefix luck) when a place actually in Goa exists.
    """
    q = query.strip().lower()
    exact = seg = regional = prefix = substr = best = None
    for body in bodies:
        for node in _walk(body):
            if not isinstance(node, dict) or not node.get("place_id"):
                continue
            name = str(node.get("city") or node.get("main_text") or "").lower()
            first = name.split(",")[0].strip()
            secondary = str(node.get("secondary_text") or "").lower()
            if name == q:
                exact = exact or node
            elif first == q:
                seg = seg or node
            elif q in secondary:
                regional = regional or node
            elif first.startswith(q):
                prefix = prefix or node
            elif q in name:
                substr = substr or node
            best = best or node
    return exact or seg or regional or prefix or substr or best


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


async def harvest_flight_search(origin: str, dest: str, iso_date: str, *,
                                adults: int = 2, children: int = 0, infants: int = 0,
                                cabin: str = "E", timeout_ms: int = 90_000) -> str:
    """Return the raw search-stream body for one flight search.

    The API cannot be called directly (findings.md BUG-7), so this does what a person
    does: open the flights funnel, then the results page, and read the SSE response
    the page itself receives. The funnel visit is load-bearing - going straight to
    /flight/search gets the Akamai "200-ok" stub, exactly as /cabs/listing does.

    The body must be read only after the stream closes; reading a response that is
    still open yields an empty string.
    """
    from . import flights as FL

    responses: list[Any] = []

    async with SESSION.page() as page:
        def on_response(resp) -> None:
            if "search-stream" in resp.url:
                responses.append(resp)

        page.on("response", on_response)
        await page.goto(C.WWW + "/flights/?cc=IN&lang=eng",
                        wait_until="domcontentloaded", timeout=timeout_ms)
        await page.wait_for_timeout(6000)
        await _dismiss_popups(page)

        url = FL.page_url(origin, dest, iso_date, adults=adults, children=children,
                          infants=infants, cabin=cabin)
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        best = ""
        done: set[int] = set()
        deadline = timeout_ms / 1000.0
        waited = 0.0
        while waited < deadline:
            try:
                await page.wait_for_timeout(2500)
            except Exception as e:
                # The browser can go away under a long search. Keep whatever the
                # stream already delivered; the caller decides if it is enough.
                if "closed" not in str(e).lower():
                    raise
                raise Blocked(
                    "The browser closed during the flight search.",
                    hint="A flight search drives a real page for up to a minute and is "
                         "the longest call this server makes. Retry once; if it keeps "
                         "happening, mmt_setup_status will say whether the browser is "
                         "healthy.") from None
            waited += 2.5
            for resp in list(responses):
                # Awaiting the same response twice spawns a second waiter that
                # outlives the page and logs a stray "Target closed".
                if id(resp) in done:
                    continue
                done.add(id(resp))
                with contextlib.suppress(Exception):
                    await resp.finished()
                    body = await resp.text()
                    if len(body) > len(best):
                        best = body
            if len(best) > 20_000:
                break
        return best
