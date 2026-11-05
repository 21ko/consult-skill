from money import allocate, parse_amount, format_cents, split_bill

checks = [
    (lambda: allocate(100, [1, 1, 1]), [34, 33, 33]),
    (lambda: allocate(11, [1, 1, 2]), [3, 3, 5]),
    (lambda: parse_amount("$1,234.56"), 123456),
    (lambda: parse_amount(".5"), 50),
    (lambda: format_cents(-5), "-$0.05"),
    (lambda: split_bill("$100.00", 3), [3334, 3333, 3333]),
]
fails = 0
for i, (fn, want) in enumerate(checks):
    got = fn()
    if got != want:
        fails += 1
        print(f"FAIL check {i}: got {got!r}, want {want!r}")
print("all visible tests passed" if not fails else f"{fails} failing")
