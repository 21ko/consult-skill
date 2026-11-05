# Round 1: spec-driven coding tasks (Haiku vs Haiku+consult)

Stopped early once the result was clear. Every condition was at 100%. Consult model: Opus.

## Overall

| condition | runs | fully solved | avg hidden-test score | avg cost $ | of which consult $ | consults/run | avg time s |
|---|---|---|---|---|---|---|---|
| baseline | 11 | 11/11 (100%) | 100.0% | 0.013 | 0.000 | 0.0 | 68 |
| skill | 10 | 10/10 (100%) | 100.0% | 0.014 | 0.000 | 0.0 | 60 |
| skill_nudge | 10 | 10/10 (100%) | 100.0% | 0.348 | 0.329 | 1.2 | 114 |

## Per task (avg hidden-test score % / fully solved)

| task | baseline | skill | skill_nudge |
|---|---|---|---|
| allocate | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| bizdays | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| calc | 100% (1/1) | 100% (1/1) | 100% (1/1) |
| semver | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| ttlcache | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| wrap | 100% (2/2) | 100% (1/1) | 100% (1/1) |

Consultations by mode: review=12
