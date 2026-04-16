"""Simple in-memory TTL cache for scored vault results."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    """Thread-safe-enough (GIL) in-memory cache with per-entry TTL."""

    def __init__(self, default_ttl: float = 300.0) -> None:
        self.default_ttl = default_ttl
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        ttl = ttl if ttl is not None else self.default_ttl
        self._store[key] = _CacheEntry(value=value, expires_at=time.monotonic() + ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        now = time.monotonic()
        return sum(1 for e in self._store.values() if e.expires_at > now)
