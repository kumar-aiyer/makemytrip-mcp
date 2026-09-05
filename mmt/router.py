"""Tier selection and circuit breaking.

T0 plain HTTP, T1 the browser's network stack without rendering, T2 a full page render.
Per endpoint class we keep a small state machine so a site-side change degrades us
gracefully instead of failing every call at the cheapest tier forever.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum


class Tier(IntEnum):
    HTTP = 0      # urllib - no browser. Only safe where no Akamai sensor was observed.
    REQUEST = 1   # playwright context.request - browser TLS + cookies, no rendering.
    PAGE = 2      # full page.goto + wait. Slow; solves challenges and drives UI.


class EndpointClass(str):
    pass


HOTEL_API = "hotel_api"
HOTEL_PAGE = "hotel_page"
FLIGHT_API = "flight_api"
TRAIN_PAGE = "train_page"
CAB_PAGE = "cab_page"
UI_DRIVE = "ui_drive"

# Preferred tier per endpoint class, and the ceiling it may escalate to. The ceiling for
# POST APIs (HOTEL_API) is the request tier: a POST has no page-load path, so "escalate
# to a render" must not be advertised for it - that would only re-run the identical tier.
PREFERRED: dict[str, tuple[Tier, Tier]] = {
    HOTEL_API:  (Tier.HTTP, Tier.PAGE),
    HOTEL_PAGE: (Tier.REQUEST, Tier.PAGE),
    FLIGHT_API: (Tier.REQUEST, Tier.PAGE),
    TRAIN_PAGE: (Tier.REQUEST, Tier.PAGE),
    CAB_PAGE:   (Tier.REQUEST, Tier.PAGE),
    UI_DRIVE:   (Tier.PAGE, Tier.PAGE),
}

OPEN_CIRCUIT_S = 120.0
DEMOTE_AFTER = 2


@dataclass
class Health:
    state: str = "healthy"           # healthy | degraded | broken
    consecutive_failures: int = 0
    opened_at: float | None = None
    last_success_tier: int | None = None
    successes: int = 0
    failures: int = 0


@dataclass
class Router:
    health: dict[str, Health] = field(default_factory=dict)
    force_min_tier: Tier | None = None   # test hook: pin the floor

    def _h(self, ec: str) -> Health:
        return self.health.setdefault(ec, Health())

    def plan(self, ec: str) -> list[Tier]:
        """Ordered tiers to attempt now. Empty list means the circuit is open."""
        h = self._h(ec)
        preferred, ceiling = PREFERRED.get(ec, (Tier.REQUEST, Tier.PAGE))
        if self.force_min_tier is not None:
            preferred = max(preferred, self.force_min_tier)
            ceiling = max(ceiling, self.force_min_tier)

        if h.state == "broken":
            if h.opened_at and (time.time() - h.opened_at) < OPEN_CIRCUIT_S:
                return []
            return [ceiling]
        if h.state == "degraded":
            start = min(Tier(int(preferred) + 1), ceiling)
            return sorted({start, ceiling})
        return sorted({preferred, ceiling})

    def record(self, ec: str, tier: Tier, ok: bool) -> None:
        h = self._h(ec)
        if ok:
            h.successes += 1
            h.consecutive_failures = 0
            h.last_success_tier = int(tier)
            h.opened_at = None
            h.state = "healthy" if h.state != "broken" else "degraded"
            return
        h.failures += 1
        h.consecutive_failures += 1
        if h.state == "healthy" and h.consecutive_failures >= DEMOTE_AFTER:
            h.state = "degraded"
        elif h.state == "degraded":
            h.state = "broken"
            h.opened_at = time.time()

    def snapshot(self) -> dict[str, dict]:
        return {
            ec: {
                "state": h.state,
                "consecutive_failures": h.consecutive_failures,
                "last_success_tier": h.last_success_tier,
                "successes": h.successes,
                "failures": h.failures,
                "circuit_open_for_s": (
                    round(OPEN_CIRCUIT_S - (time.time() - h.opened_at), 1)
                    if h.opened_at else None
                ),
            }
            for ec, h in self.health.items()
        }


ROUTER = Router()
