from calc import evaluate

checks = [("1+2*3", 7), ("(1+2)*3", 9), ("2^3^2", 512), ("-2^2", -4), ("7/2", 3.5), ("-7%3", 2)]
fails = 0
for expr, want in checks:
    got = evaluate(expr)
    if got != want:
        fails += 1
        print(f"FAIL evaluate({expr!r}) = {got!r}, want {want!r}")
print("all visible tests passed" if not fails else f"{fails} failing")
