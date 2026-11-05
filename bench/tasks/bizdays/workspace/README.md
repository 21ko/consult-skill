# Task: business-day arithmetic

Implement in `bizdays.py` (stdlib only). Business days are Monday–Friday that are not holidays.

All functions take `holidays` (any iterable of `datetime.date`, possibly a one-shot generator;
default empty) and `observed` (bool, default False).
If `observed` is True, a holiday that falls on a Saturday is ALSO observed on the preceding Friday,
and one on a Sunday is ALSO observed on the following Monday.

Inputs must be `datetime.date` objects that are **not** `datetime.datetime` → otherwise `TypeError`.

## `is_business_day(d, holidays=(), observed=False) -> bool`

## `add_business_days(d, n, holidays=(), observed=False) -> date`
- `n > 0`: move forward one calendar day at a time, counting only business days, stop when `n` counted.
- `n < 0`: same, moving backward.
- `n == 0`: return `d` if it is a business day, else the next business day after it.
- Example: Friday + 1 → Monday; Saturday + 1 → Monday; Saturday − 1 → Friday.

## `business_days_between(a, b, holidays=(), observed=False) -> int`
Number of business days in the half-open interval `[a, b)` if `a <= b`;
if `a > b` it is the negative of the count in `[b, a)`.

## Performance
Must handle huge spans quickly: `business_days_between(date(1,1,1), date(9999,12,31), holidays=<1000 dates>)`
and `add_business_days(d, 1_000_000)` should each take well under a second.
