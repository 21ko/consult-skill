# Task: money allocation

Implement these in `money.py`. All amounts are integer **cents**.

## `allocate(total: int, weights: list) -> list[int]`
Split `total` proportionally to `weights` (non-negative ints or floats).
- Use **exact** arithmetic (totals can be huge, e.g. 10**18).
- Each share starts as the floor of its exact quota `total * w / sum(weights)`.
- Leftover cents go one at a time to the shares with the largest fractional remainder;
  ties go to the lower index.
- The result always sums exactly to `total`.
- Negative total: return the negation of `allocate(-total, weights)`.
- `ValueError` if weights is empty, any weight is negative, or all weights are zero.
- `TypeError` if `total` is not an `int` (bools count as not int).

Examples: `allocate(100, [1, 1, 1]) == [34, 33, 33]`, `allocate(11, [1, 1, 2]) == [3, 3, 5]`.

## `parse_amount(s: str) -> int`
Parse a dollar string into cents. Surrounding whitespace is ignored. Format:
optional `-`, then optional `$`, then digits with optional thousands separators, then an optional
`.` with 1–2 digits.
- Thousands separators: if present, they must be correct groups (`1,234,567` ok; `12,34`, `1,2345`, `,100`, `1,,000` invalid).
- `.5` is allowed (= 50 cents); `1.` is invalid; more than 2 decimals is invalid.
- `$-1` is invalid (sign goes before `$`).
- Anything else → `ValueError`.

Examples: `"$1,234.56" → 123456`, `"-$0.01" → -1`, `"1.5" → 150`, `".5" → 50`.

## `format_cents(c: int) -> str`
`123456 → "$1,234.56"`, `-5 → "-$0.05"`, `0 → "$0.00"`.

## `split_bill(amount: str, n: int) -> list[int]`
Split a parsed amount into `n` equal shares using `allocate`. `ValueError` if `n < 1`.
