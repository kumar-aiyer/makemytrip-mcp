"""Browser lifecycle. All Playwright access goes through here.

Playwright is imported lazily so the server starts, lists tools and answers
mmt_setup_status on a machine where it is not installed.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

from . import config as C
from .errors import BrowserUnavailable

CHANNEL_PREFERENCE = ("chrome", "msedge", None)  # None => bundled chromium

# Chrome binaries to self-launch, in preference order. See _launch_cdp for why a
# self-launched browser beats one Playwright starts for us.
_CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
_CHROME_ON_PATH = ("google-chrome", "google-chrome-stable", "chromium",
                   "chromium-browser", "microsoft-edge")


def find_chrome() -> str | None:
    """The first real Chrome/Edge executable on this machine, or None."""
    override = os.environ.get("MMT_CHROME_PATH")
    if override:
        return override if os.path.exists(override) else None
    for path in _CHROME_CANDIDATES:
        if path and os.path.exists(path):
            return path
    for name in _CHROME_ON_PATH:
        found = shutil.which(name)
        if found:
            return found
    return None


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


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
        self._browser = None          # set only on the CDP path
        self._proc: subprocess.Popen | None = None
        self._keepalive = None        # a tab that is never closed; see _finish_launch
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
            if self._ctx is not None and not self._alive():
                # A self-launched Chrome can exit on its own (a crash, or the user
                # closing the window). The stale context would then fail every call
                # with TargetClosedError forever, so drop it and relaunch.
                await self._teardown()
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
        """Attach to a self-launched Chrome; fall back to Playwright's own launcher.

        Akamai serves a 169-byte "200-OK" stub instead of the real page on the
        cabs-listing and flight-results routes when the browser was *started by*
        Playwright, however the launch is configured. The same Chrome binary,
        started as an ordinary process and attached to over the DevTools protocol,
        gets the real page - verified 2026-09-04 on /cabs/listing (10 cab cards) and
        on a live flight search (a 114 KB search-stream). So self-launch first, and
        keep the old path as the fallback for machines with no Chrome or Edge.
        """
        C.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []
        with contextlib.suppress(Exception):
            if await self._launch_cdp(errors):
                return
        await self._launch_playwright(errors)

    async def _launch_cdp(self, errors: list[str]) -> bool:
        from playwright.async_api import async_playwright

        exe = find_chrome()
        if not exe:
            errors.append("cdp: no Chrome or Edge executable found")
            return False

        port = _free_port()
        args = [
            exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={C.PROFILE_DIR}",
            "--no-first-run", "--no-default-browser-check",
            "--disable-features=Translate",
            "--lang=en-IN",
            "--window-size=1440,900",
            "about:blank",
        ]
        if self.cfg.headless:
            args.insert(1, "--headless=new")
        try:
            self._proc = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            errors.append(f"cdp spawn: {type(e).__name__}: {e}")
            return False

        if self._pw is None:
            self._pw = await async_playwright().start()
        endpoint = f"http://127.0.0.1:{port}"
        last: Exception | None = None
        for _ in range(40):
            if self._proc.poll() is not None:
                last = RuntimeError(f"Chrome exited with code {self._proc.returncode} "
                                    "(is the profile already open in another window?)")
                break
            try:
                self._browser = await self._pw.chromium.connect_over_cdp(endpoint)
                break
            except Exception as e:
                last = e
                await asyncio.sleep(0.5)
        if self._browser is None:
            errors.append(f"cdp attach: {type(last).__name__ if last else 'Timeout'}: {last}")
            self._kill_proc()
            return False

        self._ctx = (self._browser.contexts[0] if self._browser.contexts
                     else await self._browser.new_context())
        self.browser_desc = f"{os.path.basename(exe)} (self-launched, CDP)"
        # A self-launched Chrome quits when its last tab closes, and every worker
        # page here is closed after use. Hold one tab open for the session's life.
        with contextlib.suppress(Exception):
            self._keepalive = (self._ctx.pages[0] if self._ctx.pages
                               else await self._ctx.new_page())
        await self._finish_launch()
        return True

    async def _launch_playwright(self, errors: list[str]) -> None:
        from playwright.async_api import async_playwright

        if self._pw is None:
            self._pw = await async_playwright().start()

        channels = (self.cfg.channel,) if self.cfg.channel else CHANNEL_PREFERENCE
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

        await self._finish_launch()

    async def _finish_launch(self) -> None:
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

    def _kill_proc(self) -> None:
        if self._proc is None:
            return
        with contextlib.suppress(Exception):
            self._proc.terminate()
            self._proc.wait(timeout=10)
        with contextlib.suppress(Exception):
            if self._proc.poll() is None:
                self._proc.kill()
        self._proc = None

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

    def _alive(self) -> bool:
        """False once the browser has gone away underneath us."""
        if self._browser is not None:
            with contextlib.suppress(Exception):
                if not self._browser.is_connected():
                    return False
        if self._proc is not None and self._proc.poll() is not None:
            return False
        return True

    async def _teardown(self) -> None:
        """Drop every browser handle. Caller must hold self._lock."""
        self._warm = False
        if self._idle_task:
            self._idle_task.cancel()
            self._idle_task = None
        self._keepalive = None
        if self._browser is not None:
            with contextlib.suppress(Exception):
                await self._browser.close()
            self._browser = None
            self._ctx = None
        if self._ctx is not None:
            with contextlib.suppress(Exception):
                await self._ctx.close()
            self._ctx = None
        self._kill_proc()
        await self._shutdown_pw()

    async def close(self) -> None:
        async with self._lock:
            await self._teardown()

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
