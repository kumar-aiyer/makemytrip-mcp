"""Browser lifecycle. All Playwright access goes through here.

Playwright is imported lazily so the server starts, lists tools and answers
mmt_setup_status on a machine where it is not installed.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

from . import config as C
from .errors import BrowserUnavailable

CHANNEL_PREFERENCE = ("chrome", "msedge", None)  # None => bundled chromium


@dataclass
class SessionConfig:
    headless: bool = os.environ.get("MMT_HEADLESS", "0" if (os.environ.get("MMT_HEADFUL", "") == "1" or os.name == "nt") else "1").lower() in ("1", "true", "yes")
    channel: str | None = os.environ.get("MMT_BROWSER_CHANNEL") or None
    idle_timeout_s: float = float(os.environ.get("MMT_IDLE_TIMEOUT", "300"))
    nav_timeout_ms: int = 45_000
    request_timeout_ms: int = 30_000
    locale: str = "en-IN"
    timezone_id: str = "Asia/Kolkata"


def playwright_available() -> tuple[bool, str]:
    try:
        import playwright  # noqa: F401
        from playwright.async_api import async_playwright  # noqa: F401
    except Exception as e:  # pragma: no cover - environment dependent
        return False, f"{type(e).__name__}: {e}"
    return True, ""


class Session:
    """Owns one persistent browser context, warmed and reused."""

    def __init__(self, cfg: SessionConfig | None = None) -> None:
        self.cfg = cfg or SessionConfig()
        self._pw = None
        self._ctx = None
        self._lock = asyncio.Lock()
        self._page_lock = asyncio.Lock()
        self._sema = asyncio.Semaphore(4)
        self._warm = False
        self._last_used = 0.0
        self._idle_task: asyncio.Task | None = None
        self.ua: str | None = None
        self.browser_desc: str = "not started"

    # ------------------------------------------------------------------ lifecycle

    async def ensure(self):
        ok, why = playwright_available()
        if not ok:
            raise BrowserUnavailable(
                "Playwright is not installed, so only the plain-HTTP tier is available.",
                hint="Run:  python -m pip install playwright   then, if no Chrome or "
                     "Edge is present, python -m playwright install chromium. "
                     "Call mmt_setup_status for a full diagnosis.",
                details={"import_error": why},
            )
        async with self._lock:
            if self._ctx is not None:
                self._touch()
                return self._ctx
            await self._launch()
            self._touch()
        if not self._warm:
            try:
                await self.warmup()
            except Exception:
                pass
        return self._ctx

    async def _launch(self) -> None:
        from playwright.async_api import async_playwright

        C.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._pw = await async_playwright().start()

        channels = (self.cfg.channel,) if self.cfg.channel else CHANNEL_PREFERENCE
        errors: list[str] = []
        for ch in channels:
            try:
                kwargs: dict[str, Any] = dict(
                    user_data_dir=str(C.PROFILE_DIR),
                    headless=self.cfg.headless,
                    locale=self.cfg.locale,
                    timezone_id=self.cfg.timezone_id,
                    viewport={"width": 1440, "height": 900},
                    args=["--disable-blink-features=AutomationControlled"],
                )
                if ch:
                    kwargs["channel"] = ch
                self._ctx = await self._pw.chromium.launch_persistent_context(**kwargs)
                self.browser_desc = ch or "bundled chromium"
                break
            except Exception as e:
                errors.append(f"{ch or 'chromium'}: {type(e).__name__}: {e}")
                continue

        if self._ctx is None:
            await self._shutdown_pw()
            raise BrowserUnavailable(
                "No launchable browser found.",
                hint="Install Google Chrome or Microsoft Edge, or run "
                     "python -m playwright install chromium.",
                details={"attempts": errors},
            )

        self._ctx.set_default_timeout(self.cfg.request_timeout_ms)
        self._ctx.set_default_navigation_timeout(self.cfg.nav_timeout_ms)
        # Derive the UA from the browser actually launched. A mismatched UA and TLS
        # fingerprint is more suspicious than either alone.
        try:
            page = await self._ctx.new_page()
            self.ua = await page.evaluate("() => navigator.userAgent")
            await page.close()
        except Exception:
            self.ua = C.FALLBACK_UA
        self._start_idle_timer()

    async def warmup(self, force: bool = False) -> dict[str, Any]:
        """Navigate the homepage once to obtain Akamai clearance."""
        if self._warm and not force:
            return {"ok": True, "skipped": True}
        if self._ctx is None:
            await self.ensure()
            if self._warm and not force:
                return {"ok": True, "skipped": True}
        async with self._lock:
            if self._warm and not force:
                return {"ok": True, "skipped": True}
            if self._ctx is None:
                await self._launch()
                self._touch()
            t0 = time.time()
            page = await self._ctx.new_page()
            nav_err: Exception | None = None
            try:
                await page.goto(C.HOME, wait_until="domcontentloaded")
                with contextlib.suppress(Exception):
                    await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception as e:
                nav_err = e
            finally:
                with contextlib.suppress(Exception):
                    await page.close()
            if nav_err is not None:
                return {
                    "ok": False,
                    "error": f"{type(nav_err).__name__}: {nav_err}",
                    "had_abck": False,
                    "had_bm_sz": False,
                    "elapsed_ms": int((time.time() - t0) * 1000),
                    "ua": self.ua,
                    "browser": self.browser_desc,
                }
            names = {c["name"] for c in await self._ctx.cookies()}
            self._warm = True
            return {
                "ok": True,
                "had_abck": "_abck" in names,
                "had_bm_sz": "bm_sz" in names,
                "elapsed_ms": int((time.time() - t0) * 1000),
                "ua": self.ua,
                "browser": self.browser_desc,
            }

    async def request(self):
        ctx = await self.ensure()
        return ctx.request

    @contextlib.asynccontextmanager
    async def page(self) -> AsyncIterator[Any]:
        """Serialized page for tier-2 work. Always closed, even on exception."""
        ctx = await self.ensure()
        async with self._page_lock:
            page = await ctx.new_page()
            try:
                yield page
            finally:
                with contextlib.suppress(Exception):
                    await page.close()
                self._touch()

    @contextlib.asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Concurrency limiter for tier-1 requests."""
        async with self._sema:
            yield
        self._touch()

    async def is_healthy(self) -> bool:
        if self._ctx is None:
            return False
        try:
            names = {c["name"] for c in await self._ctx.cookies()}
            return "_abck" in names
        except Exception:
            return False

    async def recover(self) -> None:
        await self.close()
        await self.ensure()

    async def close(self) -> None:
        async with self._lock:
            self._warm = False
            if self._idle_task:
                self._idle_task.cancel()
                self._idle_task = None
            if self._ctx is not None:
                with contextlib.suppress(Exception):
                    await self._ctx.close()
                self._ctx = None
            await self._shutdown_pw()

    async def _shutdown_pw(self) -> None:
        if self._pw is not None:
            with contextlib.suppress(Exception):
                await self._pw.stop()
            self._pw = None

    # ----------------------------------------------------------------- idle reaper

    def _touch(self) -> None:
        self._last_used = time.time()

    def _start_idle_timer(self) -> None:
        if self._idle_task is not None:
            return

        async def reaper() -> None:
            try:
                while True:
                    await asyncio.sleep(30)
                    if self._ctx is None:
                        return
                    if time.time() - self._last_used > self.cfg.idle_timeout_s:
                        await self.close()
                        return
            except asyncio.CancelledError:
                return

        with contextlib.suppress(RuntimeError):
            self._idle_task = asyncio.get_running_loop().create_task(reaper())

    def status(self) -> dict[str, Any]:
        ok, why = playwright_available()
        return {
            "playwright_installed": ok,
            "playwright_error": why or None,
            "browser": self.browser_desc,
            "running": self._ctx is not None,
            "warm": self._warm,
            "headless": self.cfg.headless,
            "user_agent": self.ua,
            "profile_dir": str(C.PROFILE_DIR),
        }


SESSION = Session()
