import time


class TTLCache:
    def __init__(self, capacity, ttl, clock=time.monotonic, on_evict=None):
        raise NotImplementedError
