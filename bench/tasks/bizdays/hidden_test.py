import random
import time
from datetime import date, datetime, timedelta

ONE = timedelta(days=1)


def _hs(hol, observed):
    s = set(hol)
    if observed:
        for h in hol:
            if h.weekday() == 5:
                s.add(h - ONE)
            if h.weekday() == 6:
                s.add(h + ONE)
    return s


def _isb(d, hs):
    return d.weekday() < 5 and d not in hs


def brute_add(d, n, hol, observed):
    hs = _hs(hol, observed)
    if n == 0:
        while not _isb(d, hs):
            d += ONE
        return d
    step = ONE if n > 0 else -ONE
    k = abs(n)
    while k:
        d += step
        if _isb(d, hs):
            k -= 1
    return d


def brute_between(a, b, hol, observed):
    hs = _hs(hol, observed)
    lo, hi, sgn = (a, b, 1) if a <= b else (b, a, -1)
    c = 0
    while lo < hi:
        c += _isb(lo, hs)
        lo += ONE
    return sgn * c


def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc:
        return True
    except Exception:
        return False
    return False


def timed(fn, limit=1.5):
    t = time.perf_counter()
    r = fn()
    return r, time.perf_counter() - t < limit


def tests(m):
    t = []
    fri, sat, sun, mon = date(2024, 11, 1), date(2024, 11, 2), date(2024, 11, 3), date(2024, 11, 4)
    vets = date(2024, 11, 11)
    fixed = [
        (lambda: m.add_business_days(fri, 1), mon), (lambda: m.add_business_days(fri, 0), fri),
        (lambda: m.add_business_days(sat, 0), mon), (lambda: m.add_business_days(sat, 1), mon),
        (lambda: m.add_business_days(sun, -1), fri), (lambda: m.add_business_days(mon, -1), fri),
        (lambda: m.add_business_days(date(2024, 11, 6), 5), date(2024, 11, 13)),
        (lambda: m.add_business_days(date(2024, 11, 8), 1, {vets}), date(2024, 11, 12)),
        (lambda: m.add_business_days(date(2024, 11, 12), -1, [vets]), date(2024, 11, 8)),
        (lambda: m.add_business_days(vets, 0, [vets]), date(2024, 11, 12)),
        (lambda: m.business_days_between(mon, vets), 5), (lambda: m.business_days_between(vets, mon), -5),
        (lambda: m.business_days_between(mon, mon), 0), (lambda: m.business_days_between(sat, sun), 0),
        (lambda: m.business_days_between(fri, sat), 1), (lambda: m.business_days_between(mon, date(2024, 11, 18), [vets]), 9),
        # 2026-07-04 is a Saturday -> observed Friday 2026-07-03
        (lambda: m.is_business_day(date(2026, 7, 3), [date(2026, 7, 4)]), True),
        (lambda: m.is_business_day(date(2026, 7, 3), [date(2026, 7, 4)], observed=True), False),
        # 2027-07-04 is a Sunday -> observed Monday 2027-07-05
        (lambda: m.add_business_days(date(2027, 7, 2), 1, [date(2027, 7, 4)], observed=True), date(2027, 7, 6)),
        (lambda: m.business_days_between(date(2027, 6, 28), date(2027, 7, 12), [date(2027, 7, 4)], True), 9),
        # generator holidays must work (consumed once)
        (lambda: m.add_business_days(date(2024, 11, 8), 1, (d for d in [vets])), date(2024, 11, 12)),
        (lambda: m.business_days_between(mon, date(2024, 11, 18), (d for d in [vets])), 9),
        (lambda: m.add_business_days(date(2024, 11, 8), 2, iter([vets, date(2024, 11, 12)])), date(2024, 11, 14)),
        # duplicate / weekend holidays must not double-count
        (lambda: m.business_days_between(mon, date(2024, 11, 18), [vets, vets, sat]), 9),
    ]
    for i, (fn, want) in enumerate(fixed):
        t.append((f"fixed#{i}", lambda fn=fn, w=want: fn() == w))
    rng = random.Random(7)
    for k in range(40):
        a = date(2020, 1, 1) + timedelta(days=rng.randint(0, 2000))
        n = rng.randint(-60, 60)
        hol = [date(2020, 1, 1) + timedelta(days=rng.randint(0, 2200)) for _ in range(rng.randint(0, 120))]
        obs = rng.random() < 0.5
        b = a + timedelta(days=rng.randint(-90, 90))
        t.append((f"rand add#{k}", lambda a=a, n=n, h=hol, o=obs: m.add_business_days(a, n, h, o) == brute_add(a, n, h, o)))
        t.append((f"rand between#{k}", lambda a=a, b=b, h=hol, o=obs: m.business_days_between(a, b, h, o) == brute_between(a, b, h, o)))
    big_h = [date(1, 1, 1) + timedelta(days=rng.randint(0, 3_000_000)) for _ in range(1000)]

    def perf_between():
        r, fast = timed(lambda: m.business_days_between(date(1, 1, 1), date(9999, 12, 31), big_h))
        nh = len({h for h in big_h if h.weekday() < 5})
        days = (date(9999, 12, 31) - date(1, 1, 1)).days
        full, extra = divmod(days, 7)
        wk = full * 5 + sum(1 for i in range(extra) if (date(1, 1, 1).weekday() + i) % 7 < 5)
        return fast and r == wk - nh

    def perf_add():
        r, fast = timed(lambda: m.add_business_days(date(2000, 1, 3), 1_000_000))
        return fast and r == date(2000, 1, 3) + timedelta(days=1_400_000)

    t.append(("perf between 1..9999", perf_between))
    t.append(("perf add 1e6", perf_add))
    t.append(("datetime rejected", lambda: raises(TypeError, m.add_business_days, datetime(2024, 1, 1), 1)))
    t.append(("datetime rejected between", lambda: raises(TypeError, m.business_days_between, date(2024, 1, 1), datetime(2024, 2, 1))))
    t.append(("str rejected", lambda: raises(TypeError, m.is_business_day, "2024-01-01")))
    return t
