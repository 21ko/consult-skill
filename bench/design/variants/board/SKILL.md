---
name: consult
description: Convene a board meeting of stronger models (Sonnet seats plus an Opus chair) to decide how to build something, then present the board's resolution to the user for approval before writing code. Use for design decisions that are costly to get wrong (data model or schema changes, how users or identity are resolved, new states or statuses, API contracts, where state lives, UI patterns for a new feature) and for vague requests ("improve X", "make it real", "fix that") that can be read several ways. Also offers a quick one-on-one consult when stuck (same failure after 2 attempts) and a review of a non-trivial change before reporting it done. Built for cheaper models like Haiku that run as the daily driver.
---

# Board meetings with stronger models

You are probably a fast, cheap model. You're good at executing, but you tend to take a request at
face value and run with the first plausible design. For decisions that are expensive to undo, don't
decide alone: **prepare a brief, convene the board, and bring its resolution to the user.**

The scripts live in `scripts/`, in the same folder as this SKILL.md. Run them from the project root.

| Tool | When | Cost and time |
|---|---|---|
| `board.py` | a design or product decision before building | ~$1–3, ~2–3 min |
| `consult.py unstuck` | the same failure after 2 attempts | ~$0.05–1 |
| `consult.py review --diff` | before saying "done" on a multi-file change | ~$0.05–1 |

## 1. The board meeting (`board.py`)

**Convene it** before writing code when the task involves any of these:
- a data model, schema or new field, and which storage backends it must work in
- identity: which user, record or tenant something belongs to
- a new state or status, and everything that reads statuses (UI, i18n, webhooks, APIs)
- an API or contract that other code, agents or clients depend on
- a vague request with several reasonable readings, or a new UI feature with real UX choices

**Skip it** for small, clear, local changes. One board per task is normally enough.

### Step 1: prepare the brief (this is your job)
Research first. Find how things work today: the relevant files, every parallel code path, and
everything that consumes the thing you'd change. Then write the brief:

```
python <skill-dir>/scripts/board.py \
  -q "User request: '<quote it>'. <the decision to make>" \
  -c "<what exists today, with file paths; constraints; conventions you noticed>" \
  --options "A: <option>" "B: <option>" \
  [--files key/file.ts other/file.ts] [--seats architect,product,security,skeptic]
```

**The meeting takes 2–4 minutes. Run it with a long command timeout** (in Claude Code, Bash
`timeout: 600000`), or the shell will kill it. The default seats are `architect,product`. Add `security` when the change involves auth, payments,
outbound messages or webhooks, and `skeptic` for big bets. The board members read the repo
themselves and check your brief.

### Step 2: present the resolution to the user and WAIT
The script prints a **Board resolution**: recommendation, why, the plan, rejected options, dissent
and risks, and a **Needs your decision** list.

- Show the user the resolution. Don't paraphrase it into one line: the user is the decision maker.
- Ask them to approve, and to answer the "Needs your decision" questions. Each question already has
  the board's default answer.
- **Do not start implementing until the user approves.** If they change something, follow their choice.
- The exception: the user has already said they pre-approve the board's decision (for example
  "use the board's defaults"). Then proceed without waiting.

### Step 3: implement the approved plan
Follow the plan step by step. It names every file and code path, so don't drop steps quietly. If one
turns out to be wrong once you're in the code, tell the user why you deviated.

### Step 4: review
`python <skill-dir>/scripts/consult.py review -q "Implemented the board's plan: <title>" --diff --context-file .consult/board-<stamp>.md`

## 2. One-on-one consult (`consult.py`)

```
python <skill-dir>/scripts/consult.py unstuck -q "<what fails>" -c "<attempts + exact output>" --files a b
python <skill-dir>/scripts/consult.py decide  -q "<small decision>" -c "<your plan + rejected option>"
python <skill-dir>/scripts/consult.py reply   -q "<answer its QUESTIONS, or push back>"   # same meeting
python <skill-dir>/scripts/consult.py review  -q "<what you did>" --diff
```

These are multi-turn. If the answer contains `QUESTIONS:` or `MEETING: open`, reply. If you
disagree with what you see in the code, say so with `reply`; don't follow it blindly. Meetings cap at 4 turns.

## Settings and notes
- Models: `BOARD_SEAT_MODEL` (default `sonnet`), `BOARD_CHAIR_MODEL` (`opus`), `CONSULT_MODEL` (`opus`; `sonnet` is cheaper).
- Backends: the `claude` CLI (the user's login) first, then `ANTHROPIC_API_KEY`.
- Everything is logged with its cost in `.consult/log.jsonl`. Resolutions are saved as `.consult/board-*.md`.
- Works the same from Claude Code and Codex: they're just shell commands.
