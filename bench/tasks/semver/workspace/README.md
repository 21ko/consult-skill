# Task: semver range matching

Implement `satisfies(version: str, range_: str) -> bool` in `semver.py`.

## Versions
`MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]`, e.g. `1.2.3`, `1.0.0-alpha.1`, `2.0.0+sha.5`.
Build metadata is ignored for everything. An optional leading `v` or `=` is allowed (`v1.2.3`).
Invalid versions raise `ValueError`.

Precedence (SemVer 2.0): compare MAJOR, MINOR, PATCH numerically. A prerelease version
has lower precedence than the same version without one. Prerelease identifiers are split on `.`
and compared left to right: numeric identifiers compare numerically; numeric identifiers
always have lower precedence than alphanumeric ones; alphanumeric ones compare in ASCII order;
if all compared identifiers are equal, the version with more identifiers is higher.
(`1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta < 1.0.0-beta.2 < 1.0.0-beta.11 < 1.0.0-rc.1 < 1.0.0`)

## Ranges
- A range is one or more comparator *sets* joined by `||`. It matches if ANY set matches.
- A set is comparators separated by whitespace. It matches if ALL comparators match.
- Comparators: `=V`, `V`, `>V`, `>=V`, `<V`, `<=V`, where V may be partial (`1`, `1.2`) or use
  `x`/`X`/`*` wildcards (`1.x`, `1.2.*`).
- Empty range or `*` matches any version (subject to the prerelease rule below).

Desugaring (X = missing or wildcard part):
- `1.2.x`, `1.2` → `>=1.2.0 <1.3.0`;  `1.x`, `1` → `>=1.0.0 <2.0.0`
- `>1.2` → `>=1.3.0`; `>1` → `>=2.0.0`; `>=1.2` → `>=1.2.0`
- `<1.2` → `<1.2.0`; `<=1.2` → `<1.3.0`; `<=1` → `<2.0.0`
- Tilde: `~1.2.3` → `>=1.2.3 <1.3.0`; `~1.2` → `>=1.2.0 <1.3.0`; `~1` → `>=1.0.0 <2.0.0`
- Caret (don't change the left-most non-zero part):
  `^1.2.3` → `>=1.2.3 <2.0.0`; `^0.2.3` → `>=0.2.3 <0.3.0`; `^0.0.3` → `>=0.0.3 <0.0.4`;
  `^1.2` → `>=1.2.0 <2.0.0`; `^0.2` → `>=0.2.0 <0.3.0`; `^0.0` → `>=0.0.0 <0.1.0`; `^1` → `>=1.0.0 <2.0.0`; `^0` → `>=0.0.0 <1.0.0`
- Hyphen: `A - B` → `>=A <=B`. If A is partial, missing parts are 0. If B is partial,
  it becomes an exclusive upper bound: `1.2.3 - 2.3` → `>=1.2.3 <2.4.0`, `1.2.3 - 2` → `>=1.2.3 <3.0.0`.
- Tilde/caret/comparators may carry a prerelease: `^1.2.3-beta.2` → `>=1.2.3-beta.2 <2.0.0`.

## Prerelease rule
A version WITH a prerelease tag only satisfies a set if at least one comparator in that set
has a prerelease tag on the same `MAJOR.MINOR.PATCH` tuple (as written in the range, before desugaring
upper bounds). Otherwise it is excluded even if it is in the numeric range.
E.g. `1.2.3-alpha.7` satisfies `>1.2.3-alpha.3` but `3.4.5-alpha.9` does not;
`1.2.4-beta` does NOT satisfy `^1.2.3`.

Invalid ranges raise `ValueError`.
