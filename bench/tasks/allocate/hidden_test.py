import random
from fractions import Fraction


def _expected(total, weights):
    neg = total < 0
    total = abs(total)
    ws = [Fraction(w) for w in weights]
    s = sum(ws)
    q = [total * w / s for w in ws]
    sh = [x.numerator // x.denominator for x in q]
    for i in sorted(range(len(ws)), key=lambda i: (-(q[i] - sh[i]), i))[: total - sum(sh)]:
        sh[i] += 1
    return [-x for x in sh] if neg else sh


def raises(exc, fn, *a):
    try:
        fn(*a)
    except exc:
        return True
    except Exception:
        return False
    return False


def tests(mod):
    t = []
    eq = [
        ((100, [1, 1, 1]), [34, 33, 33]), ((5, [1] * 7), [1, 1, 1, 1, 1, 0, 0]),
        ((-100, [1, 1, 1]), [-34, -33, -33]), ((10, [3, 0, 7]), [3, 0, 7]), ((1, [0, 1]), [0, 1]),
        ((7, [1, 2]), [2, 5]), ((11, [1, 1, 2]), [3, 3, 5]), ((0, [1, 2]), [0, 0]),
        ((10**18 + 1, [1, 1]), [5 * 10**17 + 1, 5 * 10**17]),
        ((10**18, [1, 2, 3]), _expected(10**18, [1, 2, 3])),
        ((100, [0.1, 0.2, 0.7]), [10, 20, 70]), ((-7, [1, 2]), [-2, -5]),
        ((3, [1, 1, 1, 1]), [1, 1, 1, 0]), ((2, [1, 3, 1]), [1, 1, 0]),
    ]
    for args, want in eq:
        t.append((f"allocate{args}", lambda a=args, w=want: mod.allocate(*a) == w))
    rng = random.Random(42)
    for k in range(25):
        total = rng.randint(-10**12, 10**12)
        ws = [rng.randint(0, 50) for _ in range(rng.randint(1, 9))]
        ws[0] += 1
        t.append((f"allocate random#{k}", lambda a=(total, ws): mod.allocate(*a) == _expected(*a)))
    for args, exc in [((100, []), ValueError), ((100, [1, -1]), ValueError), ((100, [0, 0]), ValueError),
                      ((1.5, [1]), TypeError), ((True, [1]), TypeError)]:
        t.append((f"allocate{args} raises", lambda a=args, e=exc: raises(e, mod.allocate, *a)))
    for s, want in [("12.34", 1234), ("$1,234.56", 123456), ("-$1,234.56", -123456), ("1.5", 150),
                    (".5", 50), ("  7 ", 700), ("0", 0), ("1,000,000", 100000000), ("-0.01", -1),
                    ("$0.05", 5), ("999", 99900)]:
        t.append((f"parse {s!r}", lambda s=s, w=want: mod.parse_amount(s) == w))
    for s in ["1.234", "12,34", "1,2345.00", "$", "", "abc", "1.", "--1", "$-1", "1,,000", ",100", "1 000", "-"]:
        t.append((f"parse {s!r} raises", lambda s=s: raises(ValueError, mod.parse_amount, s)))
    for c, want in [(123456, "$1,234.56"), (-5, "-$0.05"), (0, "$0.00"), (100000000, "$1,000,000.00"),
                    (-123456789, "-$1,234,567.89"), (99, "$0.99")]:
        t.append((f"format {c}", lambda c=c, w=want: mod.format_cents(c) == w))
    t.append(("split_bill 100/3", lambda: mod.split_bill("$100.00", 3) == [3334, 3333, 3333]))
    t.append(("split_bill neg", lambda: mod.split_bill("-$0.05", 2) == [-3, -2]))
    t.append(("split_bill n=0", lambda: raises(ValueError, mod.split_bill, "1", 0)))
    return t
