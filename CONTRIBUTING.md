# Contributing to consult

Thanks for helping. This project is a skill for coding agents, and its whole claim rests on measured
results, so the main rule is simple: **changes to how the skill makes decisions need evidence.**

## Ways to help

- **Report results from your own use.** The most valuable contribution right now. Did the board catch
  something real? Did the pre-mortem miss something, or fire when it shouldn't have? Open a
  [benchmark / field report](../../issues/new?template=benchmark_report.yml). Please don't paste
  private code.
- **Fix bugs** in the scripts (`skills/consult/scripts/`) or the installer.
- **Improve the benchmark** (`bench/design/`): new task files for public repos, better checks, less noise.
- **Improve the skill** (`skills/consult/SKILL.md`): read the next section first.

## Changing the skill's behavior

`SKILL.md` is what the agent follows, and small wording changes can move the results a lot. (The
"soft" first version looked great on one repo and did nothing on a second one.) So for any change to
the pre-mortem, the escalation rules or the board prompts:

1. Say what failure you're fixing, ideally with a transcript excerpt or a judge comment.
2. Run the design benchmark on **at least two repos** with the current version and yours, same tasks,
   at least 2 trials each:
   ```bash
   cd bench/design
   cp -r ../../skills/consult variants/mine    # put your edited SKILL.md here
   DESIGN_TASKS=your-tasks.json uv run run_design.py --repo ~/repo-a --conditions baseline,ship2,mine --trials 2
   uv run summarize.py
   ```
   Add a `"mine"` entry to `CONDITIONS` in `run_design.py` (copy the `ship2` one and point `skill_src`
   at your variant).
3. Put the before/after table in the PR. Don't include results or diffs from private code.

Wording fixes, typo fixes and docs don't need a benchmark.

## Development setup

You need [uv](https://docs.astral.sh/uv/). Everything is standard-library Python 3.9+, so there is nothing to install.

```bash
git clone https://github.com/21ko/consult-skill && cd consult-skill
uv run install.py --project /tmp/try-it         # install into a scratch folder to test
uv run skills/consult/scripts/consult.py --help
uv build                                         # check the package still builds
```

The scripts need the `claude` CLI (logged in) or `ANTHROPIC_API_KEY` to make real calls. A test call
with `--model sonnet --no-read` costs about $0.02.

## Pull requests

- Keep each PR to one change, and describe what you changed and how you checked it.
- Keep scripts stdlib-only and keep the `# /// script` header at the top. It makes `uv run` isolate them
  from the user's project.
- Never commit API keys, `.consult/` logs, or code and diffs from private repositories.
- By contributing you agree your work is released under the [MIT License](LICENSE) and that you follow
  the [Code of Conduct](CODE_OF_CONDUCT.md).
