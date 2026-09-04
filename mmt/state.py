"""window.__INITIAL_STATE__ extraction from server-rendered MakeMyTrip HTML."""
from __future__ import annotations

import json
import re
from typing import Any

from .rsc import balanced

STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*")


def extract(html: str) -> dict[str, Any] | None:
    """Pull __INITIAL_STATE__ out of SSR HTML. None when absent.

    Absent usually means an Akamai interstitial rather than a shape change - the caller
    decides whether to escalate a tier.
    """
    m = STATE_RE.search(html)
    if not m:
        return None
    i = html.find("{", m.end())
    if i < 0:
        return None
    raw = balanced(html, i)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
