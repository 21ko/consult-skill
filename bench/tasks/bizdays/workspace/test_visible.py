from datetime import date
from bizdays import add_business_days, business_days_between, is_business_day

fri, sat, mon = date(2024, 11, 1), date(2024, 11, 2), date(2024, 11, 4)
checks = [
    (lambda: add_business_days(fri, 1), mon),
    (lambda: add_business_days(sat, -1), fri),
    (lambda: add_business_days(sat, 0), mon),
    (lambda: business_days_between(mon, date(2024, 11, 11)), 5),
    (lambda: business_days_between(date(2024, 11, 11), mon), -5),
    (lambda: is_business_day(date(2024, 11, 11), [date(2024, 11, 11)]), False),
]
fails = 0
for i, (fn, want) in enumerate(checks):
    got = fn()
    if got != want:
        fails += 1
        print(f"FAIL check {i}: got {got!r}, want {want!r}")
print("all visible tests passed" if not fails else f"{fails} failing")
