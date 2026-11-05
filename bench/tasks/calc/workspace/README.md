# Task: arithmetic expression evaluator

Implement `evaluate(expr: str)` in `calc.py`. Do **not** use `eval`/`exec`/`ast.literal_eval`.

## Syntax
- Numbers: `12` (int), `1.5`, `.5`, `5.` (float). No exponent notation (`1e3` is invalid).
- Binary operators: `+ - * / % ^`; unary prefix `+` and `-` (may be stacked: `--3`, `-+-3`).
- Parentheses. Whitespace (spaces/tabs) is allowed between any tokens and ignored.
- Implicit multiplication is not allowed (`2(3)` is invalid). Two numbers in a row is invalid (`1 2`).

## Semantics (highest precedence first)
1. `^` exponentiation, **right**-associative: `2^3^2 == 512`. Its right operand may start with a
   unary sign: `2^-1 == 0.5`.
2. unary `+`/`-`: binds *looser* than `^`: `-2^2 == -4`, `(-2)^2 == 4`, `-2^-2 == -0.25`.
3. `* / %` left-associative. `/` is true division (always float). `%` follows Python semantics
   (result has the sign of the divisor): `-7%3 == 2`, `7%-3 == -2`.
4. `+ -` left-associative.

Result types follow Python: int op int stays int except `/` (float) and int `^` negative int (float).

## Errors
- Malformed input → `ValueError` (empty, dangling operator, unbalanced parens, bad tokens, `()`, ...).
- Division/modulo by zero, or `0 ^ negative` → `ZeroDivisionError`.

## Robustness
Must handle deep inputs: 1000 levels of nested parentheses, 1000 stacked unary minus signs,
chains of 1000 `^` operators, and sums of 5000 terms.
