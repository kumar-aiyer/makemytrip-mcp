"""Browser lifecycle. All Playwright access goes through here.

Playwright is imported lazily so the server starts, lists tools and answers
mmt_setup_status on a machine where it is not installed.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import signal
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



def _profile_pids() -> list[int]:
    """PIDs of browsers holding *our* profile directory, and only ours.

    Matched on the absolute profile path in the command line, so a user's own Chrome
    is never a candidate. Used to clear orphans left by a killed run - without this
    they hold the profile lock, and every later launch hands its startup URL to the
    orphan and exits (the about:blank tab-storm).
    """
    prof = str(C.PROFILE_DIR).lower()
    pids: list[int] = []
    try:
        if os.name == "nt":
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe' or "
                 "Name='msedge.exe'\" | ForEach-Object "
                 "{ \"$($_.ProcessId)|$($_.CommandLine)\" }"],
                capture_output=True, text=True, timeout=25)
        else:
            out = subprocess.run(["ps", "-eo", "pid=,args="],
                                 capture_output=True, text=True, timeout=25)
    except Exception:
        return pids
    for line in (out.stdout or "").splitlines():
        line = line.strip()
        if not line or prof not in line.lower():
            continue
        head = line.split("|", 1)[0] if os.name == "nt" else line.split(None, 1)[0]
        try:
            pids.append(int(head.strip()))
        except ValueError:
            continue
    return pids


def sweep_orphans() -> int:
    """Kill browsers holding our profile. Returns how many were killed."""
    killed = 0
    for pid in _profile_pids():
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True, timeout=20)
            else:
                os.kill(pid, signal.SIGKILL)
            killed += 1
        except Exception:
            continue
    return killed


class Session:
    """Owns one persistent browser context, warmed and reused."""

    def __init__(self, cfg: SessionConfig | None = None) -> None:
        self.cfg = cfg or SessionConfig()
        self._pw = None
        self._ctx = None
        self._browser = None          # set only on the CDP path
        self._proc: subprocess.Popen | None = None
        self._keepalive = None        # a tab that is never closed; see _finish_launch
        self._no_cdp = False          # set once the CDP path has proved unusable
        self._inflight = 0            # operations holding a page or a request slot
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
                warm = await self.warmup()
            except Exception:
                warm = {"ok": False}
            # A self-launched Chrome that could not take the profile lock still starts
            # ("Chrome cannot read and write to its data directory") but browses
            # nothing, and every later call then fails in ways that look like the site
            # refusing us. Clearance cookies are the cheap proof it is really working.
            if self._browser is not None and not warm.get("had_abck"):
                async with self._lock:
                    await self._teardown()
                    self._no_cdp = True
                    await self._launch()
                    self._touch()
                with contextlib.suppress(Exception):
                    await self.warmup(force=True)
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
        if not self._no_cdp:
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

        for attempt in range(2):
            if await self._spawn_and_attach(exe, errors):
                break
            if attempt == 0:
                # Almost always an orphan holding the profile lock: Chrome then hands
                # the launch to it and exits 0, which reads as "Chrome exited".
                killed = await asyncio.to_thread(sweep_orphans)
                errors.append(f"cdp: swept {killed} orphaned browser process(es)")
                await asyncio.sleep(2.0)
        else:
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

    async def _spawn_and_attach(self, exe: str, errors: list[str]) -> bool:
        from playwright.async_api import async_playwright

        port = _free_port()
        args = [
            exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={os.path.abspath(C.PROFILE_DIR)}",
            "--no-first-run", "--no-default-browser-check",
            "--disable-features=Translate",
            "--lang=en-IN",
            "--window-size=1440,900",
            # No startup URL on purpose. If this launch is ever handed off to an
            # instance already holding the profile, a URL here becomes a stray tab in
            # the user's window - that is the about:blank tab-storm.
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
            self._inflight += 1
            try:
                yield page
            finally:
                self._inflight -= 1
                with contextlib.suppress(Exception):
                    await page.close()
                self._touch()

    @contextlib.asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Concurrency limiter for tier-1 requests."""
        async with self._sema:
            self._inflight += 1
            try:
                yield
            finally:
                self._inflight -= 1
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
        had_proc = self._proc is not None
        self._kill_proc()
        if had_proc:
            # The process we spawned is not necessarily the browser (see _alive), so
            # reap by profile rather than trusting the handle. Leaking these is what
            # filled a window with about:blank tabs.
            with contextlib.suppress(Exception):
                await asyncio.to_thread(sweep_orphans)
        if had_proc:
            # Chrome releases its user-data-dir lock a moment after the process goes.
            # Relaunching into it too early gives "Chrome cannot read and write to its
            # data directory" and a browser that is alive but useless - which then
            # fails every later call in a way that looks like a site problem.
            await asyncio.sleep(1.5)
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
                    if self._inflight:
                        # Idle means idle. A flight search holds one page for up to a
                        # minute and touches nothing while it does; reaping under it
                        # closed the browser mid-search.
                        self._touch()
                        continue
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
            "cdp": self._browser is not None,
            "user_agent": self.ua,
            "profile_dir": str(C.PROFILE_DIR),
        }


SESSION = Session()
