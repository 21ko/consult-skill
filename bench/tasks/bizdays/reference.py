from bisect import bisect_left
from datetime import date, datetime, timedelta

ONE = timedelta(days=1)


def _check(*ds):
    for d in ds:
        if not isinstance(d, date) or isinstance(d, datetime):
            raise TypeError("need date")


def _hol(holidays, observed):
    hs = set()
    for h in holidays:
        hs.add(h)
        if observed:
            if h.weekday() == 5:
                hs.add(h - ONE)
            elif h.weekday() == 6:
                hs.add(h + ONE)
    return sorted(h for h in hs if h.weekday() < 5)


def _weekdays(a, b):  # weekdays in [a, b), a <= b
    days = (b - a).days
    full, extra = divmod(days, 7)
    cnt = full * 5
    wd = a.weekday()
    for i in range(extra):
        if (wd + i) % 7 < 5:
            cnt += 1
    return cnt


def _count(a, b, hs):
    return _weekdays(a, b) - (bisect_left(hs, b) - bisect_left(hs, a))


def is_business_day(d, holidays=(), observed=False):
    _check(d)
    return d.weekday() < 5 and d not in set(_hol(holidays, observed))


def business_days_between(a, b, holidays=(), observed=False):
    _check(a, b)
    hs = _hol(holidays, observed)
    return _count(a, b, hs) if a <= b else -_count(b, a, hs)


def add_business_days(d, n, holidays=(), observed=False):
    _check(d)
    hs = _hol(holidays, observed)
    if n == 0:
        if d.weekday() < 5 and _count(d, d + ONE, hs) == 1:
            return d
        d, n = d - ONE, 1
    k = abs(n)
    span = k + 2 * (k // 5 + 2) + len(hs) + 7
    if n > 0:  # smallest b > d with count(d+1, b+1) == k
        lo, hi = 1, span
        while lo < hi:
            mid = (lo + hi) // 2
            if _count(d + ONE, d + timedelta(days=mid + 1), hs) >= k:
                hi = mid
            else:
                lo = mid + 1
        return d + timedelta(days=lo)
    lo, hi = 1, span  # largest b < d with count(b, d) == k  -> smallest offset
    while lo < hi:
        mid = (lo + hi) // 2
        if _count(d - timedelta(days=mid), d, hs) >= k:
            hi = mid
        else:
            lo = mid + 1
    return d - timedelta(days=lo)
