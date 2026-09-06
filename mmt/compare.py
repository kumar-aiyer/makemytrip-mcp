"""Normalising three transport modes onto one comparable footing.

The whole reason `mmt_intercity_options` exists is that flights, trains and cabs are
quoted in three different units and three different time formats, and every subject that
has compared them by hand has got something wrong:

  flights   per adult          duration as a string, "01h 20m"
  trains    per passenger      duration already in minutes
  cabs      per VEHICLE        duration as approximate hours, a float

Multiplying the per-vehicle figure by head count, or failing to multiply the per-adult
one, is the same family of error as BUG-16. Doing it here once, with the unit kept
visible on every row, is the point of the tool.

Nothing in this module estimates. A flight is 80 minutes in the air and some hours
door-to-door, and the difference is real - but inventing it would be fabrication, so the
caller is handed the source figure plus an explicit note of what it excludes.
"""
from __future__ import annotations

import re
from typing import Any

HHMM_RE = re.compile(r"(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?", re.I)


def duration_minutes(value: Any) -> int | None:
    """Minutes from whatever a source calls a duration.

    Accepts an int/float already in minutes, or the "01h 20m" / "1h" / "45m" strings the
    flight parser produces. Returns None rather than guessing.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value >= 0 else None
    m = HHMM_RE.match(str(value).strip())
    if not m or not any(m.groups()):
        return None
    hours = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    total = hours * 60 + mins
    return total or None


def minutes_from_hours(value: Any) -> int | None:
    """Cab quotes report approximate hours, and fractionally since BUG-15."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(round(float(value) * 60))
    except (TypeError, ValueError):
        return None


def party_total(per_unit: Any, unit: str, adults: int) -> int | None:
    """What the whole party pays. `unit` is carried through to the caller unchanged so
    the underlying convention stays visible rather than being buried in a total."""
    if per_unit is None or isinstance(per_unit, bool):
        return None
    try:
        value = float(per_unit)
    except (TypeError, ValueError):
        return None
    if unit == "per vehicle":
        return int(round(value))
    return int(round(value * max(int(adults), 1)))


def mark_dominated(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag options that are both dearer AND slower than some other option.

    This is the only ranking the server does, and it is deliberately the only kind that
    is a fact rather than a preference: whether an extra four hours is worth Rs 3,000 is
    the caller's judgement about their own itinerary. Dominance just clears away the
    rows no judgement could pick.

    An option missing either figure is never marked - we cannot show it is beaten. An
    option flagged `indicative` (a fare for a different date) can be dominated but never
    dominates: it is not a price you can actually pay on the day in question.
    """
    for a in options:
        a["dominated"] = False
    comparable = [o for o in options
                  if o.get("party_total_inr") is not None
                  and o.get("duration_min") is not None]
    for a in comparable:
        for b in comparable:
            # An indicative price is for a different date, so it cannot prove another
            # option is beaten - it can only be beaten itself.
            if a is b or b.get("indicative"):
                continue
            cheaper_or_equal = b["party_total_inr"] <= a["party_total_inr"]
            faster_or_equal = b["duration_min"] <= a["duration_min"]
            strictly_better = (b["party_total_inr"] < a["party_total_inr"]
                               or b["duration_min"] < a["duration_min"])
            if cheaper_or_equal and faster_or_equal and strictly_better:
                a["dominated"] = True
                break
    return options


def sort_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Undominated first, then by party total. Not a recommendation - just a readable
    order with the rows worth thinking about at the top."""
    return sorted(options, key=lambda o: (
        o.get("dominated", False),
        o.get("party_total_inr") is None,
        o.get("party_total_inr") or 0,
        o.get("duration_min") or 0,
    ))
