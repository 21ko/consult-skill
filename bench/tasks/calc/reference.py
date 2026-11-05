import re
import sys

_TOK = re.compile(r"\s*(?:(\d+\.\d*|\.\d+|\d+)|([-+*/%^()]))")


def _tokens(s):
    pos, out = 0, []
    s = s.rstrip()
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m:
            raise ValueError(f"bad token at {pos}")
        num, op = m.groups()
        out.append(("n", float(num) if "." in num else int(num)) if num else ("o", op))
        pos = m.end()
    return out


BIN = {"+": (10, 11), "-": (10, 11), "*": (20, 21), "/": (20, 21), "%": (20, 21), "^": (40, 39)}


def _apply(op, a, b):
    if op == "+": return a + b
    if op == "-": return a - b
    if op == "*": return a * b
    if op == "/": return a / b
    if op == "%": return a % b
    return a ** b


def evaluate(expr):
    toks = _tokens(expr)
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, 20000))
    try:
        i = 0

        def parse(rbp):
            nonlocal i
            if i >= len(toks):
                raise ValueError("unexpected end")
            kind, v = toks[i]
            i += 1
            if kind == "n":
                left = v
            elif v in "+-":
                operand = parse(30)
                left = -operand if v == "-" else +operand
            elif v == "(":
                left = parse(0)
                if i >= len(toks) or toks[i] != ("o", ")"):
                    raise ValueError("missing )")
                i += 1
            else:
                raise ValueError(f"unexpected {v}")
            while i < len(toks):
                kind, v = toks[i]
                if kind != "o" or v not in BIN:
                    if kind == "n" or v == "(":
                        raise ValueError("missing operator")
                    break
                lbp, nrbp = BIN[v]
                if lbp <= rbp:
                    break
                i += 1
                right = parse(nrbp)
                left = _apply(v, left, right)
            return left

        r = parse(0)
        if i != len(toks):
            raise ValueError("trailing input")
        return r
    finally:
        sys.setrecursionlimit(old)
