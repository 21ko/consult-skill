from ttlcache import TTLCache

now = [0.0]
c = TTLCache(2, ttl=10, clock=lambda: now[0])
c.set("a", 1)
c.set("b", 2)
c.get("a")
c.set("c", 3)  # evicts b (LRU)
checks = [
    ("b evicted", "b" not in c),
    ("a kept", c.get("a") == 1),
    ("len 2", len(c) == 2),
]
now[0] = 10.0
checks.append(("a expired at boundary", c.get("a") is None))
fails = [n for n, ok in checks if not ok]
for n in fails:
    print("FAIL", n)
print("all visible tests passed" if not fails else f"{len(fails)} failing")
