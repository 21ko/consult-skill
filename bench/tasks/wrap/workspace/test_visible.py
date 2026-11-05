from wrap import wrap, display_width

checks = [
    (lambda: wrap("The quick brown fox", 10), ["The quick", "brown fox"]),
    (lambda: wrap("hi abcdefg xy", 4), ["hi", "abcd", "efg", "xy"]),
    (lambda: wrap("abcdef x", 4), ["abcd", "ef x"]),
    (lambda: wrap("日本語", 5), ["日本", "語"]),
    (lambda: wrap("a b\n\nc", 10), ["a b", "", "c"]),
    (lambda: display_width("日本a"), 5),
]
fails = 0
for i, (fn, want) in enumerate(checks):
    got = fn()
    if got != want:
        fails += 1
        print(f"FAIL check {i}: got {got!r}, want {want!r}")
print("all visible tests passed" if not fails else f"{fails} failing")
