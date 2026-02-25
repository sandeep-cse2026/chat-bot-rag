"""Thread-safe in-memory TTL cache for API responses.

Provides a simple cache with automatic expiration to avoid
hammering external APIs with repeated identical queries.

Usage:
    cache = TTLCache(ttl_seconds=300, max_size=256)
    cache.set("search:naruto", data)
    result = cache.get("search:naruto")  # returns data or None if expired
"""
from __future__ import annotations

import threading
import time
from typing import Any


class TTLCache:
    """Thread-safe in-memory cache with TTL expiration and max size eviction.

    Attributes:
        _store: Dict mapping cache keys to (expiry_timestamp, value) tuples.
        _ttl: Time-to-live in seconds for cached entries.
        _max_size: Maximum number of entries before eviction.
        _lock: Threading lock for thread-safe access.
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 256) -> None:
        """Initialize the cache.

        Args:
            ttl_seconds: How long entries live before expiring (default: 5 min).
            max_size: Max number of cached entries (default: 256).
        """
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """Get a value from the cache.

        Args:
            key: Cache key to look up.

        Returns:
            Cached value if present and not expired, otherwise None.
        """
        with self._lock:
            if key in self._store:
                expiry, value = self._store[key]
                if time.monotonic() < expiry:
                    return value
                # Expired — remove it
                del self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Store a value in the cache with TTL.

        If the cache is full, expired entries are evicted first.
        If still full after eviction, the oldest entry is removed.

        Args:
            key: Cache key.
            value: Value to cache.
        """
        with self._lock:
            # Evict expired entries if at capacity
            if len(self._store) >= self._max_size and key not in self._store:
                self._evict_expired()
                # If still full, remove the oldest entry
                if len(self._store) >= self._max_size:
                    oldest_key = min(self._store, key=lambda k: self._store[k][0])
                    del self._store[oldest_key]

            self._store[key] = (time.monotonic() + self._ttl, value)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from the cache.

        Args:
            key: Cache key to remove.

        Returns:
            True if the key existed and was removed, False otherwise.
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """Remove all entries from the cache."""
        with self._lock:
            self._store.clear()

    @property
    def size(self) -> int:
        """Return the current number of entries (including potentially expired)."""
        return len(self._store)

    def _evict_expired(self) -> None:
        """Remove all expired entries. Must be called while holding the lock."""
        now = time.monotonic()
        self._store = {k: v for k, v in self._store.items() if v[0] > now}

    @staticmethod
    def make_key(prefix: str, **kwargs: Any) -> str:
        """Generate a deterministic cache key from a prefix and keyword args.

        Args:
            prefix: Cache key prefix (e.g., "jikan:search_anime").
            **kwargs: Parameters to include in the key.

        Returns:
            Deterministic string key.

        Example:
            >>> TTLCache.make_key("jikan:search", q="naruto", limit=5)
            'jikan:search:limit=5&q=naruto'
        """
        if not kwargs:
            return prefix
        sorted_params = "&".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None)
        return f"{prefix}:{sorted_params}" if sorted_params else prefix
