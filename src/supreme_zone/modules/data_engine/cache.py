from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from time import time
from typing import Any


@dataclass(slots=True)
class CacheEntry:
    value: Any
    expires_at: float


@dataclass(slots=True)
class MarketCache:
    ttl_seconds: int = 60
    max_items: int = 1_000
    _store: OrderedDict[str, CacheEntry] = field(default_factory=OrderedDict)

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expires_at = time() + float(ttl_seconds or self.ttl_seconds)
        if key in self._store:
            self._store.pop(key, None)
        self._store[key] = CacheEntry(value=value, expires_at=expires_at)
        while len(self._store) > self.max_items:
            self._store.popitem(last=False)

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at < time():
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return entry.value

    def contains(self, key: str) -> bool:
        return self.get(key) is not None

    def clear(self) -> None:
        self._store.clear()
