import random
import unicodedata


def raises(exc, fn, *a):
    try:
        fn(*a)
    except exc:
        return True
    except Exception:
        return False
    return False


def _w(s):
    return sum(0 if unicodedata.combining(c) or c in "​‍"
               else 2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


E = "é"


def tests(m):
    t = []
    cases = [
        (("The quick brown fox", 10), ["The quick", "brown fox"]),
        (("a b c", 1), ["a", "b", "c"]),
        (("hello", 3), ["hel", "lo"]),
        (("hi abcdefgh xy", 4), ["hi", "abcd", "efgh", "xy"]),
        (("hi abcdefg xy", 4), ["hi", "abcd", "efg", "xy"]),
        (("abcdefg x", 4), ["abcd", "efg", "x"]),
        (("abcdef x", 4), ["abcd", "ef x"]),
        (("日本語のテキスト", 6), ["日本語", "のテキ", "スト"]),
        (("日本語", 5), ["日本", "語"]),
        (("ab 日本", 5), ["ab", "日本"]),
        (("ab 日", 5), ["ab 日"]),
        ((f"caf{E} caf{E}", 5), [f"caf{E}", f"caf{E}"]),
        ((f"caf{E} ok", 7), [f"caf{E} ok"]),
        ((E * 3, 2), [E * 2, E]),
        (("日本", 1), ["日", "本"]),
        (("a日b", 2), ["a", "日", "b"]),
        (("a b\n\n\n  \nc d", 10), ["a b", "", "c d"]),
        (("\n\nx\n\n", 5), ["x"]),
        (("  ", 3), []),
        (("", 3), []),
        (("a\nb", 10), ["a b"]),
        (("a\tb   c", 10), ["a b c"]),
        (("p1\n \t\np2\n\np3", 80), ["p1", "", "p2", "", "p3"]),
        (("one two three four five six", 9), ["one two", "three", "four five", "six"]),
        (("exactly10c", 10), ["exactly10c"]),
        (("a​b c", 3), ["a​b", "c"]),
        (("a​b c", 4), ["a​b c"]),
        (("x " + "y" * 9, 3), ["x", "yyy", "yyy", "yyy"]),
    ]
    for args, want in cases:
        t.append((f"wrap{args!r}", lambda a=args, w=want: m.wrap(*a) == w))
    for s, want in [("日本a", 5), (E, 1), ("a​b", 2), ("", 0), ("ｱ", 1), ("Ａ", 2), ("한국", 4)]:
        t.append((f"display_width({s!r})", lambda s=s, w=want: m.display_width(s) == w))
    for bad in (0, -1, 2.5):
        t.append((f"width {bad!r} raises", lambda b=bad: raises(ValueError, m.wrap, "abc", b)))
    rng = random.Random(11)
    alphabet = list("abcdefghij") + ["日", "本", "語", E, "ü"]
    for k in range(30):
        width = rng.randint(1, 12)
        words = ["".join(rng.choice(alphabet) for _ in range(rng.randint(1, 15))) for _ in range(rng.randint(1, 20))]
        text = " ".join(words)

        def prop(text=text, width=width, words=words):
            lines = m.wrap(text, width)
            if any(l != l.strip() or not l for l in lines):
                return False
            for l in lines:
                if _w(l) > width and not (width == 1 and _w(l) == 2 and len(l.split()) == 1 and len(l) <= 2):
                    return False
            # no content lost or reordered
            if "".join(text.split()) != "".join("".join(l.split()) for l in lines):
                return False
            # combining marks never start a line
            return all(unicodedata.combining(l[0]) == 0 for l in lines)
        t.append((f"random prop#{k}", prop))
    return t
