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

# The ceiling above which a single body is not worth holding. This is a CACHING
# decision and nothing else: an oversized body is still returned to the caller.
# It used to be 2 MB and enforced by refusing the fetch outright, which killed
# mmt_hotel_rates the day a hotel detail page grew to 2.6 MB - both tiers failed and
# the tool had no working path at all. Sizes seen live: 2.6 MB hotel detail,
# 0.70-0.75 MB cab listing, 0.65 MB train listing.
PAGE_SIZE_CAP = 8 * 1024 * 1024


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
    def __init__(self, max_entries: int = MAX_ENTRIES,
                 byte_cap: int = PAGE_TIER_BYTE_CAP) -> None:
        self._d: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max = max_entries
        self._byte_cap = byte_cap
        self._bytes = 0
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _sizeof(value: Any) -> int:
        """Resident cost of an entry. Only whole-page text is worth counting - the
        JSON payloads are small and their true size is not len()-addressable."""
        if isinstance(value, dict):
            text = value.get("text")
            if isinstance(text, str):
                return len(text)
        return 0

    def _drop(self, k: str) -> None:
        item = self._d.pop(k, None)
        if item is not None:
            self._bytes -= self._sizeof(item[1])

    def get(self, k: str) -> Any | None:
        item = self._d.get(k)
        if item is None:
            self.misses += 1
            return None
        expires, value = item
        if time.time() > expires:
            self._drop(k)
            self.misses += 1
            return None
        self._d.move_to_end(k)
        self.hits += 1
        return value

    def put(self, k: str, value: Any, ttl: float = PRICE_TTL) -> None:
        self._drop(k)                       # replacing: uncount the old body first
        self._d[k] = (time.time() + ttl, value)
        self._bytes += self._sizeof(value)
        # Evict LRU until both budgets hold. The byte budget is what actually stops
        # 200 cached pages from becoming hundreds of MB resident; before this it was
        # a named constant that nothing read.
        while len(self._d) > self._max or (
                self._bytes > self._byte_cap and len(self._d) > 1):
            oldest = next(iter(self._d))
            self._drop(oldest)

    def clear(self) -> None:
        self._d.clear()
        self._bytes = 0

    def stats(self) -> dict[str, int]:
        return {"entries": len(self._d), "hits": self.hits, "misses": self.misses,
                "bytes": self._bytes}


CACHE = Cache()
