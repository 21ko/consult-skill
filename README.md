# consult: senior-level design decisions for cheap coding agents

A skill for **Claude Code and Codex**. It makes a cheap daily-driver model (Haiku) handle design
decisions the way a senior engineer does. Before writing code it runs a **written pre-mortem**:
every place that writes the thing being changed, every reader, parent/child inheritance, and the
reviewer's likely objections. For **cross-cutting changes** (a new column, table, status or shared
config) it escalates to a **board meeting** of stronger models (two Sonnet seats and an Opus chair)
and brings the board's resolution to you for approval.

**Measured result:** on cross-cutting changes in two real codebases, Haiku with this skill scored
**7.1/10** with a blind Opus judge, against **6.4 for Sonnet alone** and **6.2 for Haiku alone**,
for about $1.65 per task. On small, local features it makes no difference, and the skill is built
to stay cheap there. [Full results and caveats below.](#does-it-help-benchmarks)

```
skills/consult/
  SKILL.md             # the pre-mortem, escalation rules, board + stuck workflows (Agent Skills format)
  scripts/board.py     # board meeting: Sonnet seats deliberate in parallel, Opus chair writes the resolution
  scripts/consult.py   # one-on-one consult (unstuck / review / reply); stdlib only
bench/                 # round 1: spec-driven coding tasks with hidden tests
bench/design/          # round 2: vague product requests on real repos, blind Opus judge, rework loop
install.py             # installer (also packaged as `consult-install` for uvx)
pyproject.toml         # uv project: `uv run`, `uv build`, `uvx --from git+... consult-install`
```

## Install

With [uv](https://docs.astral.sh/uv/), no clone needed:

```bash
uvx --from git+https://github.com/21ko/consult-skill consult-install
```

Or from a clone:

```bash
uv run install.py                    # ~/.claude/skills + ~/.codex/skills + ~/.agents/skills
uv run install.py --target claude    # just Claude Code
uv run install.py --project path/to/repo   # per-repo instead of per-user
uv run install.py --uninstall
```

Same flags work with `uvx ... consult-install`. No uv? `python3 install.py` does the same thing.

Needs either the `claude` CLI (logged in) or `ANTHROPIC_API_KEY`. Everything is stdlib-only, so there is nothing
else to install.

**Why uv:** the skill's scripts declare their own environment ([PEP 723](https://peps.python.org/pep-0723/)
inline metadata), so `uv run scripts/consult.py` inside your project runs isolated. It never installs into,
syncs or changes your project's dependencies, whether your project uses uv, pip, poetry or no Python at all.
If you don't have uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux) or
`powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` (Windows).

## How it works

1. **Pre-mortem (every design task, about free).** Before the first edit, the agent posts a fixed template:
   the real need, today's code paths, **every writer / entry path** (with file:line), every reader,
   the decision and the rejected options, and the 5 most likely reasons a strict reviewer would reject
   the change. It then checks each prediction against the code.
2. **Board meeting (cross-cutting only, about $1–2, 2–4 min).** The trigger is mechanical, not left to the
   agent: a new column/table/status/config value, or more than one writer for the thing being changed.
   `board.py` runs an architect seat and a product seat (optionally security and skeptic) in parallel,
   lets them rebut each other once, and an Opus chair writes a **resolution**: the plan, rejected
   options, risks, and a "needs your decision" list with defaults. **The agent shows it to you and waits for approval.**
3. **Stuck (`consult.py unstuck`).** Same failure after 2 attempts → a diagnosis from a stronger model.

```bash
uv run scripts/board.py -q "User request: '...'. How should registration closing work?" \
  -c "<pre-mortem: writers, readers, decision, predictions>" --options "A: ..." "B: ..." --files app/authz.py
uv run scripts/consult.py unstuck -q "pytest: fixture db not found" -c "<attempts + output>"
```

Settings: `BOARD_SEAT_MODEL` (default `sonnet`), `BOARD_CHAIR_MODEL` (`opus`), `CONSULT_MODEL` (`opus`),
`CONSULT_LOG` (`off` to disable). Every call is logged with its cost in `.consult/log.jsonl`.

## Does it help? Benchmarks

All numbers come from the run records in `bench/design/results/` (scores and costs only; the apps' code,
diffs and judge comments were removed before publishing) (`uv run bench/design/summarize.py`
rebuilds every table). Total spend for round 2: about $82.

### Round 1: spec-driven coding tasks (`bench/`): no benefit
Six well-specified tasks with 68–109 hidden tests each. Haiku alone solved 11/11. The skill was correctly
never triggered, and forced reviews cost 27× more for no gain. **A clear spec is not where cheap models fail.**

### Round 2: vague product requests on real repos (`bench/design/`)
Requests like "let customers cancel" or "stop new people registering once it's full", on two real apps
(names and code withheld; only scores and costs are published):
- **App A**: Next.js + Postgres, 6 tasks.
- **App B**: FastAPI + Postgres + React, 3 tasks, added later to test whether the skill generalizes.

Each run works on a throwaway clone. It's checked by the repo's own typecheck/lint/tests and scored 1–10
by a **blind Opus judge** against a hidden checklist. The judge never sees the condition, the meeting logs
or the agent's summary.

**By kind of task, both repos:**

| | Haiku alone | Sonnet alone | **Haiku + consult skill** |
|---|---|---|---|
| Cross-cutting changes (new status / column / config: cancel, pricing, webhooks, close-registration) | 6.2 (n=8) | 6.4 (n=8) | **7.1** (n=9) |
| Smaller features (dashboard, offers, profile, missing-submissions, export) | 6.0 (n=10) | 6.2 (n=10) | 6.2 (n=7) |
| Model cost per task | $0.08–0.13 | $0.34–0.44 | $0.18 small / $1.65 cross-cutting |

**What we tried, and what didn't work:**

| setup | App A | App B | verdict |
|---|---|---|---|
| Haiku alone | 5.9 | 6.5 | baseline |
| Sonnet alone | 5.9 | 7.0 | 4× the cost; no better than Haiku on App A |
| Haiku + one-on-one consult (Sonnet) | 5.9 | – | **no gain**: asking a stronger model a question doesn't help when the question is shallow |
| Haiku + board on every task | 7.2 | – | good quality, but $1.36 a task even for small changes |
| Haiku + soft pre-mortem (v1) | 6.7 | 6.2 | **didn't generalize**: on the second repo Haiku loaded it but skipped the steps |
| **Haiku + consult skill (shipped)** | 6.7 | 6.6 | best on cross-cutting changes on both repos; neutral elsewhere |

**Counting your time.** On App A, a rework loop sent each run's review issues back to the same agent
session until the judge approved it (max 2 follow-ups). It then totaled model cost plus the judge's
estimate of reviewer minutes, at $60/h:

| setup | follow-ups to approval | your minutes | model $ | total |
|---|---|---|---|---|
| Haiku alone | 1.2 | 57 | $0.36 | $57 |
| Sonnet alone | 1.3 | 52 | $1.16 | $54 |
| Haiku + pre-mortem + board (v1) | 0.5 | 42 | $1.04 | **$43** |

Human time is about 99% of the real cost of a change. A setup that costs $1 more in tokens but saves
10 minutes of review wins easily.

**Caveats (read these):**
- **The judge is a model, not a person.** Scores vary by about ±1 point between identical runs, and the
  "minutes" are its estimates. Small samples (3–12 runs per cell) mean differences under ~1 point may be noise.
- I wrote the hidden checklists, and the v1 pre-mortem was written after seeing App A's judge feedback.
  That's why App B was added, and why the v1 soft version is not what ships.
- The board doesn't guarantee a good result (one pricing run scored 5 even with the board).
- The benchmark has no human in the loop. In real use you also review the board's resolution before any
  code is written, which these numbers don't capture.

### Reproduce
```bash
cd bench && uv run run_bench.py --trials 3 --conditions baseline,skill,skill_nudge
cd bench/design && uv run run_design.py --repo ~/your-repo --conditions baseline,ship2,sonnet --trials 2
uv run rework.py results/<stamp>.jsonl --rounds 2        # cost to shippable, incl. human time
DESIGN_TASKS=my-tasks.json uv run run_design.py --repo ~/other-repo --conditions baseline,ship2
uv run summarize.py
```
To benchmark your own repo, write a tasks file (see `bench/design/tasks.example.json`): a vague
prompt per task, a hidden checklist of what a strong solution considers, and the repo's check command.

## Contributing

Results from your own projects are the most useful contribution: open a
[field report](https://github.com/21ko/consult-skill/issues/new?template=benchmark_report.yml).
Changes to how the skill decides need before/after benchmark numbers on two repos. See
[CONTRIBUTING.md](CONTRIBUTING.md), the [Code of Conduct](CODE_OF_CONDUCT.md), and [SECURITY.md](SECURITY.md)
for reporting vulnerabilities privately.

## License

[MIT](LICENSE) © Yahya Kossor
