"""Date validation shared by the priced tools.

BUG-18: a search for a date in the past used to be answered by driving a live page.
`mmt_flight_search("BLR", "GOI", "2025-12-15")` run in September 2026 spent 99 seconds
rendering MakeMyTrip's search UI and came back `empty_valid` - "no itineraries parsed" -
which reads like "that route is sold out" rather than "you asked about last December".
The hotel searches beside it failed with `transport` and tripped the circuit breaker.

Trains have always answered this class of question instantly, because Indian Railways'
60-day window forces the check. Flights, hotels and cabs had no reason to look, so they
never did. A past date is knowable before a byte leaves the machine.

The failure is not exotic. A model given a bare "December 15th" has to pick a year, and
picking the most recent December it can remember is the obvious wrong answer.
"""
from __future__ import annotations

from datetime import date, timedelta

from .errors import BadInput

# Rejecting anything before *yesterday* rather than before today, deliberately. The
# server runs wherever it runs and MakeMyTrip sells in IST; a strict "before today" test
# would refuse a legitimate same-day search for a caller a timezone or two west. One
# day of slack costs nothing against the nine-month errors this exists to catch.
GRACE_DAYS = 1


def parse_iso(value: str, field: str = "date") -> date:
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        raise BadInput(f"{field} must be ISO YYYY-MM-DD, not {value!r}") from None


def not_past(value: str, field: str = "date", *, today: date | None = None) -> date:
    """Parse an ISO date and refuse one that is meaningfully in the past."""
    d = parse_iso(value, field)
    floor = (today or date.today()) - timedelta(days=GRACE_DAYS)
    if d < floor:
        raise BadInput(
            f"{field} {value} is in the past.",
            hint="MakeMyTrip only sells future travel; a past date renders an empty "
                 "page that looks like 'sold out'. If you resolved a bare month and "
                 f"day, the year is probably wrong - today is {today or date.today()}.")
    return d
