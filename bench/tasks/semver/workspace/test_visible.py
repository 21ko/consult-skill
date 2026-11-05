from semver import satisfies

cases = [
    ("1.2.3", "^1.0.0", True),
    ("2.0.0", "^1.0.0", False),
    ("1.2.3", "~1.2.0", True),
    ("1.3.0", "~1.2.0", False),
    ("1.2.3", ">=1.0.0 <2.0.0", True),
    ("3.0.0", "1.x || >=3", True),
]
fails = 0
for v, r, want in cases:
    got = satisfies(v, r)
    if got != want:
        fails += 1
        print(f"FAIL satisfies({v!r}, {r!r}) = {got}, want {want}")
print("all visible tests passed" if not fails else f"{fails} failing")
