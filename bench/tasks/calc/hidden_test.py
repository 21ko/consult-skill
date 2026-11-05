import math


def raises(exc, fn, *a):
    try:
        fn(*a)
    except exc:
        return True
    except Exception:
        return False
    return False


def same(got, want):
    if type(got) is not type(want):
        return False
    if isinstance(want, float):
        return math.isclose(got, want, rel_tol=1e-12)
    return got == want


def tests(m):
    t = []
    cases = [
        ("1+2*3", 7), ("(1+2)*3", 9), ("2^3^2", 512), ("-2^2", -4), ("(-2)^2", 4), ("2^-1", 0.5),
        ("2*-3", -6), ("2--3", 5), ("--3", 3), ("-+-3", 3), ("7/2", 3.5), ("6/3", 2.0), ("7%3", 1),
        ("-7%3", 2), ("7%-3", -2), ("2^10", 1024), ("2^0.5", 2 ** 0.5), ("1.5+.5", 2.0), ("5.", 5.0),
        (" 1 +\t2 ", 3), ("10-4-3", 3), ("100/10/5", 2.0), ("2^-2^2", 0.0625), ("-2^-2", -0.25),
        ("3-2^2*2", -5), ("8%3^2", 8), ("(((1)))", 1), ("1-(-(-(1)))", 0), ("2^100", 2 ** 100),
        ("4*2", 8), ("1.0*2", 2.0), ("-(2)^2", -4), ("2^(1+1)^3", 256), ("10/4*2", 5.0),
        ("10-2+3", 11), ("2*3%4", 2), ("+5", 5), ("0", 0), ("007", 7), ("-0.5^2", -0.25),
    ]
    for e, want in cases:
        t.append((f"evaluate({e!r})", lambda e=e, w=want: same(m.evaluate(e), w)))
    deep = [
        ("(" * 1000 + "1" + ")" * 1000, 1),
        ("-" * 1000 + "1", 1),
        ("-" * 999 + "1", -1),
        ("1^" * 1000 + "1", 1),
        ("+".join(["1"] * 5000), 5000),
        ("2^" + "(" * 900 + "3" + ")" * 900, 8),
    ]
    for e, want in deep:
        t.append((f"deep len={len(e)} {e[:12]!r}", lambda e=e, w=want: same(m.evaluate(e), w)))
    for e in ["", "  ", "1 +", "(1", "1)", "1 2", "1..2", ".", "2 ^", "* 3", "1 + * 2", "2(3)", "()",
              "1 ++", "abc", "1 & 2", "1e3", "(1+2", "1+2)", ")(", "--", "(1)(2)"]:
        t.append((f"ValueError {e!r}", lambda e=e: raises(ValueError, m.evaluate, e)))
    for e in ["1/0", "1%0", "0^-1", "1/(2-2)", "5/0.0"]:
        t.append((f"ZeroDivisionError {e!r}", lambda e=e: raises(ZeroDivisionError, m.evaluate, e)))
    t.append(("no eval", lambda: raises(ValueError, m.evaluate, "__import__('os')")))
    return t
