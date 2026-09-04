"""Error taxonomy.

Every failure resolves to exactly one kind. This is the backbone of the whole server:
MakeMyTrip's characteristic failure is a silent HTTP 200 with nothing useful in it, and
this module's job is to turn those into sentences a person can act on.
"""
from __future__ import annotations

from typing import Any


class MMTError(Exception):
    """Base. `kind` drives router behaviour and the shape of the tool result."""

    kind = "unexpected"
    retry = False
    escalate = False

    def __init__(self, message: str, *, hint: str | None = None,
                 details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.details = details or {}

    def to_result(self) -> dict[str, Any]:
        out: dict[str, Any] = {"error": self.message, "kind": self.kind}
        if self.hint:
            out["hint"] = self.hint
        out.update(self.details)
        return out


class BadInput(MMTError):
    """Unknown city/place/station, malformed date. The caller can fix this."""
    kind = "bad_input"


class NotInWindow(MMTError):
    """Correct query, outside a booking window. NOT a failure - never escalates."""
    kind = "not_in_window"


class EmptyValid(MMTError):
    """Parsed cleanly, genuinely zero rows. NOT a failure - never escalates."""
    kind = "empty_valid"


class UnregisteredPlace(MMTError):
    """Cab place object unknown. Has a specific, documented remedy."""
    kind = "unregistered_place"


class Blocked(MMTError):
    """Akamai challenge, 403, or a bot interstitial. Escalate a tier and retry once."""
    kind = "blocked"
    retry = True
    escalate = True


class Transport(MMTError):
    """DNS, timeout, reset, or a proxy returning a stub body."""
    kind = "transport"
    retry = True
    escalate = True


class ShapeDrift(MMTError):
    """HTTP 200, expected keys absent. MakeMyTrip changed something."""
    kind = "shape_drift"
    escalate = True


class NullPrices(MMTError):
    """200, rows present, every price null.

    Its own kind because it is the one failure that otherwise reads as total success.
    Cause is almost always a trimmed expData / featureFlags block.
    """
    kind = "null_prices"


class BrowserUnavailable(MMTError):
    """Playwright missing, no launchable browser, or a crash that would not recover."""
    kind = "browser"
