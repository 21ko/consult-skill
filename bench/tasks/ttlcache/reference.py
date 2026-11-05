import time
from collections import OrderedDict


class TTLCache:
    def __init__(self, capacity, ttl, clock=time.monotonic, on_evict=None):
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 0:
            raise ValueError("capacity")
        if not ttl > 0:
            raise ValueError("ttl")
        self.capacity, self.ttl, self.clock, self.on_evict = capacity, ttl, clock, on_evict
        self._d = OrderedDict()  # key -> (value, expires_at)

    def _expired(self, key, now):
        v, exp = self._d[key]
        if now >= exp:
            del self._d[key]
            if self.on_evict:
                self.on_evict(key, v, "expired")
            return True
        return False

    def _live(self, key):
        return key in self._d and not self._expired(key, self.clock())

    def _purge(self):
        now = self.clock()
        for k in list(self._d):
            self._expired(k, now)

    def set(self, key, value, ttl=None):
        if ttl is None:
            ttl = self.ttl
        if not ttl > 0:
            raise ValueError("ttl")
        if self.capacity == 0:
            return
        now = self.clock()
        if key in self._d and not self._expired(key, now):
            self._d[key] = (value, now + ttl)
            self._d.move_to_end(key)
            return
        if len(self._d) >= self.capacity:
            self._purge()
        if len(self._d) >= self.capacity:
            k, (v, _) = self._d.popitem(last=False)
            if self.on_evict:
                self.on_evict(k, v, "capacity")
        self._d[key] = (value, now + ttl)

    def get(self, key, default=None):
        if not self._live(key):
            return default
        self._d.move_to_end(key)
        return self._d[key][0]

    def peek(self, key, default=None):
        return self._d[key][0] if self._live(key) else default

    def delete(self, key):
        if self._live(key):
            del self._d[key]
            return True
        return False

    def __contains__(self, key):
        return self._live(key)

    def __len__(self):
        self._purge()
        return len(self._d)

    def keys(self):
        self._purge()
        return list(self._d)
