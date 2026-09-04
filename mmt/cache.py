"""TTL + LRU cache. In memory only - a stale rupee figure resurrected from disk three
days later is worse than a slow call."""
from __future__ import annotations

import json
import time
from collections import OrderedDict
from typing import Any

PRICE_TTL = 20 * 60
STRUCTURAL_TTL = 24 * 60 * 60
MAX_ENTRIES = 200
# get_text caches whole page HTML (train/cab listing pages are megabytes each) under the
# same MAX_ENTRIES budget. Capping page-tier bytes separately keeps 200 pages from
# ballooning to hundreds of MB resident. get_text sets this when its value is text.
PAGE_TIER_BYTE_CAP = 32 * 1024 * 1024

# Payloads sized 1.27 MB (hotel detail) / 0.65 MB (train listing) / 0.77 MB (cab);
# a 2 MB ceiling leaves the server no excuse for holding dozens of full pages.
PAGE_SIZE_CAP = 2 * 1024 * 1024


def key(tool: str, args: dict[str, Any]) -> str:
    def norm(v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        if isinstance(v, dict):
            return {k: norm(x) for k, x in sorted(v.items())}
        if isinstance(v, list):
            return [norm(x) for x in v]
        return v
    clean = {k: norm(v) for k, v in sorted(args.items()) if k != "fresh"}
    return tool + "|" + json.dumps(clean, sort_keys=True, default=str)


class Cache:
    def __init__(self, max_entries: int = MAX_ENTRIES) -> None:
        self._d: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max = max_entries
        self.hits = 0
        self.misses = 0

    def get(self, k: str) -> Any | None:
        item = self._d.get(k)
        if item is None:
            self.misses += 1
            return None
        expires, value = item
        if time.time() > expires:
            self._d.pop(k, None)
            self.misses += 1
            return None
        self._d.move_to_end(k)
        self.hits += 1
        return value

    def put(self, k: str, value: Any, ttl: float = PRICE_TTL) -> None:
        self._d[k] = (time.time() + ttl, value)
        self._d.move_to_end(k)
        while len(self._d) > self._max:
            self._d.popitem(last=False)

    def clear(self) -> None:
        self._d.clear()

    def stats(self) -> dict[str, int]:
        return {"entries": len(self._d), "hits": self.hits, "misses": self.misses}


CACHE = Cache()
