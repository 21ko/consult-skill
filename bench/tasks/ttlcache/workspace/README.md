# Task: LRU cache with TTL

Implement `TTLCache` in `ttlcache.py`.

```python
TTLCache(capacity: int, ttl: float, clock=time.monotonic, on_evict=None)
```
- `capacity` must be an int >= 0 and `ttl` must be > 0, else `ValueError`.
- `clock()` returns the current time in seconds. Tests inject a fake clock.
- An item set at time `t` with ttl `T` **expires** when `clock() >= t + T`. Expired items act as if
  they are absent.
- `on_evict(key, value, reason)`, if given, is called exactly once whenever an item leaves the cache
  because it **expired** (`reason="expired"`, whenever the cache notices) or for **capacity**
  (`reason="capacity"`). It is NOT called for `delete()` or when a live key is overwritten by `set()`.

Methods:
- `set(key, value, ttl=None)`: insert or overwrite. A per-item `ttl` overrides the default (must be > 0,
  else `ValueError`). Overwriting a live key updates value and expiry, makes it most recently used,
  and never evicts anything. Overwriting an expired key counts as that item expiring
  (callback with `"expired"`), then inserting fresh.
  Inserting a new key into a full cache: FIRST remove all expired items; only if still full,
  evict the least recently used live item. With `capacity == 0`, `set` stores nothing (no callback).
- `get(key, default=None)`: value if live (marks it most recently used), else `default`.
- `peek(key, default=None)`: like `get` but does NOT change recency.
- `delete(key) -> bool`: True if a live item was removed.
- `__len__`: number of live items. `__contains__`: liveness check, does not change recency.
- `keys() -> list`: live keys ordered least → most recently used.
