def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc:
        return True
    except Exception:
        return False
    return False


def mk(m, cap, ttl=10):
    now = [0.0]
    log = []
    c = m.TTLCache(cap, ttl, clock=lambda: now[0], on_evict=lambda k, v, r: log.append((k, v, r)))
    return c, now, log


def tests(m):
    t = []

    def lru_basic():
        c, now, log = mk(m, 2)
        c.set("a", 1); c.set("b", 2); c.get("a"); c.set("c", 3)
        return c.keys() == ["a", "c"] and log == [("b", 2, "capacity")]
    t.append(("lru basic", lru_basic))

    def peek_no_recency():
        c, now, log = mk(m, 2)
        c.set("a", 1); c.set("b", 2); c.peek("a"); c.set("c", 3)
        return c.keys() == ["b", "c"] and log == [("a", 1, "capacity")]
    t.append(("peek keeps recency", peek_no_recency))

    def contains_no_recency():
        c, now, log = mk(m, 2)
        c.set("a", 1); c.set("b", 2); _ = "a" in c; c.set("c", 3)
        return "a" not in c and c.keys() == ["b", "c"]
    t.append(("contains keeps recency", contains_no_recency))

    def boundary():
        c, now, log = mk(m, 3)
        c.set("a", 1)
        now[0] = 9.999
        ok1 = c.get("a") == 1
        now[0] = 10.0
        return ok1 and c.get("a", "D") == "D" and log == [("a", 1, "expired")]
    t.append(("expiry boundary", boundary))

    def get_does_not_extend():
        c, now, log = mk(m, 3)
        c.set("a", 1); now[0] = 8; c.get("a"); now[0] = 10
        return c.get("a") is None
    t.append(("get doesn't extend ttl", get_does_not_extend))

    def purge_before_evict():
        c, now, log = mk(m, 2)
        c.set("a", 1, ttl=5); c.set("b", 2)
        c.get("a")  # a is MRU but will expire
        now[0] = 6
        c.set("c", 3)  # a expired -> purge it, b must survive
        return c.keys() == ["b", "c"] and log == [("a", 1, "expired")]
    t.append(("purge expired before LRU evict", purge_before_evict))

    def overwrite_live_no_evict():
        c, now, log = mk(m, 2)
        c.set("a", 1); c.set("b", 2); c.set("a", 9)
        return c.keys() == ["b", "a"] and log == [] and c.get("a") == 9 and len(c) == 2
    t.append(("overwrite live", overwrite_live_no_evict))

    def overwrite_refreshes_ttl():
        c, now, log = mk(m, 2)
        c.set("a", 1); now[0] = 8; c.set("a", 2); now[0] = 15
        return c.get("a") == 2
    t.append(("overwrite refreshes ttl", overwrite_refreshes_ttl))

    def overwrite_expired():
        c, now, log = mk(m, 2)
        c.set("a", 1); now[0] = 11; c.set("a", 2)
        return log == [("a", 1, "expired")] and c.get("a") == 2
    t.append(("overwrite expired key", overwrite_expired))

    def per_item_ttl():
        c, now, log = mk(m, 3)
        c.set("a", 1, ttl=1); c.set("b", 2, ttl=100); now[0] = 50
        return c.keys() == ["b"] and len(c) == 1
    t.append(("per-item ttl", per_item_ttl))

    def len_excludes_expired():
        c, now, log = mk(m, 5)
        for i in range(5):
            c.set(i, i, ttl=i + 1)
        now[0] = 3
        return len(c) == 2 and sorted(log) == [(0, 0, "expired"), (1, 1, "expired"), (2, 2, "expired")]
    t.append(("len excludes expired", len_excludes_expired))

    def callback_once():
        c, now, log = mk(m, 3)
        c.set("a", 1); now[0] = 20
        c.get("a"); "a" in c; c.peek("a"); len(c); c.keys(); c.delete("a"); c.set("b", 1)
        return log == [("a", 1, "expired")]
    t.append(("expired callback exactly once", callback_once))

    def delete_semantics():
        c, now, log = mk(m, 3)
        c.set("a", 1); c.set("b", 2, ttl=1)
        now[0] = 2
        r = (c.delete("a"), c.delete("a"), c.delete("b"), c.delete("zz"))
        return r == (True, False, False, False) and log == [("b", 2, "expired")]
    t.append(("delete", delete_semantics))

    def cap_zero():
        c, now, log = mk(m, 0)
        c.set("a", 1)
        return len(c) == 0 and c.get("a") is None and log == []
    t.append(("capacity 0", cap_zero))

    def cap_one_chain():
        c, now, log = mk(m, 1)
        c.set("a", 1); c.set("b", 2); c.set("c", 3)
        return c.keys() == ["c"] and log == [("a", 1, "capacity"), ("b", 2, "capacity")]
    t.append(("capacity 1 chain", cap_one_chain))

    def falsy_values():
        c, now, log = mk(m, 3)
        c.set("z", 0); c.set("n", None); c.set("e", "")
        return c.get("z", "D") == 0 and c.get("n", "D") is None and c.get("e", "D") == "" and "n" in c and len(c) == 3
    t.append(("falsy values are live", falsy_values))

    def no_callback_default():
        now = [0.0]
        c = m.TTLCache(1, 1, clock=lambda: now[0])
        c.set("a", 1); c.set("b", 2); now[0] = 5
        return len(c) == 0
    t.append(("works without on_evict", no_callback_default))

    def stress():
        import random
        from collections import OrderedDict
        rng = random.Random(3)
        c, now, log = mk(m, 4, ttl=5)
        model = OrderedDict()  # key -> (v, exp)
        mlog = []

        def mexpire(k):
            v, e = model[k]
            if now[0] >= e:
                del model[k]; mlog.append((k, v, "expired")); return True
            return False

        for step in range(400):
            now[0] += rng.choice([0, 0, 0.5, 1, 2])
            op, k = rng.choice(["set", "set", "get", "peek", "del"]), rng.randint(0, 6)
            if op == "set":
                ttl = rng.choice([None, 1, 3, 8])
                c.set(k, step, ttl=ttl)
                tt = 5 if ttl is None else ttl
                if k in model and not mexpire(k):
                    model[k] = (step, now[0] + tt); model.move_to_end(k); continue
                if len(model) >= 4:
                    for kk in list(model):
                        mexpire(kk)
                if len(model) >= 4:
                    kk, (vv, _) = model.popitem(last=False); mlog.append((kk, vv, "capacity"))
                model[k] = (step, now[0] + tt)
            elif op in ("get", "peek"):
                got = getattr(c, op)(k, "D")
                live = k in model and not mexpire(k)
                want = model[k][0] if live else "D"
                if live and op == "get":
                    model.move_to_end(k)
                if got != want:
                    return False
            else:
                live = k in model and not mexpire(k)
                if live:
                    del model[k]
                if c.delete(k) != live:
                    return False
        for kk in list(model):
            mexpire(kk)
        return c.keys() == list(model) and sorted(map(repr, log)) == sorted(map(repr, mlog))
    t.append(("randomized vs model", stress))

    t.append(("bad capacity", lambda: raises(ValueError, m.TTLCache, -1, 5)))
    t.append(("bad ttl", lambda: raises(ValueError, m.TTLCache, 2, 0)))
    t.append(("bad item ttl", lambda: raises(ValueError, mk(m, 2)[0].set, "a", 1, ttl=-1)))
    return t
