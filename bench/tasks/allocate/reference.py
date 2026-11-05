import re
from fractions import Fraction


def allocate(total, weights):
    if not isinstance(total, int) or isinstance(total, bool):
        raise TypeError("total must be int")
    if not weights or any(w < 0 for w in weights):
        raise ValueError("bad weights")
    ws = [Fraction(w) for w in weights]
    s = sum(ws)
    if s == 0:
        raise ValueError("all zero")
    if total < 0:
        return [-x for x in allocate(-total, weights)]
    quotas = [total * w / s for w in ws]
    shares = [q.numerator // q.denominator for q in quotas]
    rem = total - sum(shares)
    order = sorted(range(len(ws)), key=lambda i: (-(quotas[i] - shares[i]), i))
    for i in order[:rem]:
        shares[i] += 1
    return shares


_AMT = re.compile(r"^(-)?\$?(\d{1,3}(?:,\d{3})+|\d+)?(?:\.(\d{1,2}))?$")


def parse_amount(s):
    m = _AMT.match(s.strip())
    if not m or (m[2] is None and m[3] is None):
        raise ValueError(s)
    whole = int((m[2] or "0").replace(",", ""))
    frac = int((m[3] or "0").ljust(2, "0"))
    c = whole * 100 + frac
    return -c if m[1] else c


def format_cents(c):
    sign = "-" if c < 0 else ""
    d, r = divmod(abs(c), 100)
    return f"{sign}${d:,}.{r:02d}"


def split_bill(amount, n):
    if n < 1:
        raise ValueError("n")
    return allocate(parse_amount(amount), [1] * n)
