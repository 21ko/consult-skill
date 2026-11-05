import re

_V = re.compile(r"^[v=]?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")
_P = re.compile(r"^[v=]?(x|X|\*|\d+)(?:\.(x|X|\*|\d+)(?:\.(x|X|\*|\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?)?)?$")
_OP = re.compile(r"^(>=|<=|>|<|=|~|\^)?(.*)$")


def _pre(s):
    return tuple(int(i) if i.isdigit() else i for i in s.split(".")) if s else ()


def _parse_v(s):
    m = _V.match(s.strip())
    if not m:
        raise ValueError(s)
    return int(m[1]), int(m[2]), int(m[3]), _pre(m[4])


def _key(v):
    M, m, p, pre = v
    pk = (1,) if not pre else (0,) + tuple((0, i) if isinstance(i, int) else (1, i) for i in pre)
    return (M, m, p, pk)


def _parse_partial(s):
    mt = _P.match(s)
    if not mt:
        raise ValueError(s)
    parts = []
    for g in (mt[1], mt[2], mt[3]):
        if g is None or g in "xX*" or (parts and parts[-1] is None):
            parts.append(None)
        else:
            parts.append(int(g))
    pre = _pre(mt[4]) if parts[2] is not None else ()
    return parts[0], parts[1], parts[2], pre


def _comp(op, s):
    M, m, p, pre = _parse_partial(s)
    full = (M, m, p, pre)
    if M is None:
        return []
    if op in ("", "="):
        if p is not None:
            return [("=", full)]
        if m is not None:
            return [(">=", (M, m, 0, ())), ("<", (M, m + 1, 0, ()))]
        return [(">=", (M, 0, 0, ())), ("<", (M + 1, 0, 0, ()))]
    if op == ">":
        if p is not None:
            return [(">", full)]
        return [(">=", (M, m + 1, 0, ()) if m is not None else (M + 1, 0, 0, ()))]
    if op == ">=":
        return [(">=", (M, m or 0, p or 0, pre))]
    if op == "<":
        return [("<", (M, m or 0, p or 0, pre))]
    if op == "<=":
        if p is not None:
            return [("<=", full)]
        return [("<", (M, m + 1, 0, ()) if m is not None else (M + 1, 0, 0, ()))]
    lo = (">=", (M, m or 0, p or 0, pre))
    if op == "~":
        hi = (M, m + 1, 0, ()) if m is not None else (M + 1, 0, 0, ())
        return [lo, ("<", hi)]
    if op == "^":
        if p is not None:
            hi = (M + 1, 0, 0, ()) if M > 0 else (0, m + 1, 0, ()) if m > 0 else (0, 0, p + 1, ())
        elif m is not None:
            hi = (M + 1, 0, 0, ()) if M > 0 else (0, m + 1, 0, ())
        else:
            hi = (M + 1, 0, 0, ())
        return [lo, ("<", hi)]
    raise ValueError(op)


def _hyphen(a, b):
    M, m, p, pre = _parse_partial(a)
    out = [] if M is None else [(">=", (M, m or 0, p or 0, pre))]
    M, m, p, pre = _parse_partial(b)
    if M is not None:
        if p is not None:
            out.append(("<=", (M, m, p, pre)))
        else:
            out.append(("<", (M, m + 1, 0, ()) if m is not None else (M + 1, 0, 0, ())))
    return out


def _written_pre(s):
    M, m, p, pre = _parse_partial(s)
    return [(M, m, p)] if pre else []


def _parse_set(s):
    toks = s.split()
    prims, pres, i = [], [], 0
    while i < len(toks):
        if i + 2 < len(toks) and toks[i + 1] == "-":
            prims += _hyphen(toks[i], toks[i + 2])
            pres += _written_pre(toks[i]) + _written_pre(toks[i + 2])
            i += 3
            continue
        t = toks[i]
        if t in (">", ">=", "<", "<=", "=", "~", "^") and i + 1 < len(toks):
            t += toks[i + 1]
            i += 1
        op, rest = _OP.match(t).groups()
        if not rest:
            raise ValueError(t)
        prims += _comp(op or "", rest)
        pres += _written_pre(rest)
        i += 1
    return prims, pres


def satisfies(version, range_):
    v = _parse_v(version)
    k = _key(v)
    sets = [_parse_set(s) for s in range_.split("||")]
    for prims, pres in sets:
        ok = True
        for op, b in prims:
            kb = _key(b)
            ok = {"=": k == kb, ">": k > kb, ">=": k >= kb, "<": k < kb, "<=": k <= kb}[op]
            if not ok:
                break
        if ok and v[3] and v[:3] not in pres:
            ok = False
        if ok:
            return True
    return False
