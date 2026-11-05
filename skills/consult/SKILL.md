---
name: consult
description: Make design decisions like a senior engineer. Before building anything that involves a design decision (data model or schema, which user or record something belongs to, new states or statuses, API contracts, where state lives, UI for a new feature, or a vague request that can be read several ways), run a short pre-mortem - decide, predict how the decision fails, check those predictions against the code, fix the plan - then build. For cross-cutting changes (a new status or state, shared config, a data-model change many parts of the code read) or a product question the code can't answer, escalate to a board meeting of stronger models (Sonnet seats + Opus chair) and bring its resolution to the user. Also covers being stuck. Built for cheaper models like Haiku that run as the daily driver.
---

# Decide like a senior engineer: predict, verify, then build

You are probably a fast, cheap model. Your failure mode is not bad code; it is taking the first
plausible design and never asking how it will fail. A senior engineer's edge is that they **predict
the review before writing the code**. Do that yourself first. It costs a few minutes and saves the
user from sending your work back. Escalate to stronger models only where your own pre-mortem can't settle it.

| Step | When | Cost |
|---|---|---|
| Pre-mortem (below) | any task with a design decision | ~free (your own tokens) |
| `scripts/board.py` | cross-cutting change, or a product question the code can't answer | ~$1–3, 2–4 min |
| `scripts/consult.py unstuck` | the same failure after 2 attempts | ~$0.05–1 |

Skip all of it for small, clear, local edits.

## 1. The pre-mortem

**Before your first edit, post the pre-mortem as a message using exactly the headings in the template at
the end of this section.** Not in your head: written out. Skipping it is the #1 way cheap models ship
work that gets sent back.

**1. Read first.** Find how it works today: the files involved, every parallel code path (e.g. two
storage backends, two clients), and **every consumer** of what you will change (grep for the type,
field, status or route).
- **Every writer, not just the first one you found.** If you gate, validate or change something, grep for
  every place that creates or updates it (`INSERT INTO <table>`, the db function, every route that calls it:
  invites, imports, admin tools, background jobs). Never conclude "one check here covers every path"
  without listing the paths you checked.
- **Groups and inheritance.** If the record belongs to a parent (event/team, org/user, tenant, order/line item),
  decide where the setting lives and how every child path reads it.

**2. Decide.** State the user's real need in one line (for a vague request: what would they actually
measure as "fixed"?). Then your decision, and the 1-2 alternatives you rejected and why.

**3. Predict the rejection.** Imagine a strict senior reviewer sends your finished change back. Write
the 5 most likely reasons. Always check these:
- **Identity**: how does the code know *which* user/record this is? "The first one", name matching,
  or trusting a client-supplied id is a rejection.
- **Authorization**: who may call this, and is that enforced on the server, not just hidden in the UI?
- **Consumers**: what else reads this type/status/field (other pages, badges, i18n, webhooks, APIs,
  docs, agent prompts)? A new field nobody else reads is usually a sign you bypassed the existing flow.
- **All code paths**: every backend, schema/migration, both languages if the UI is translated.
- **State lifetime**: what survives refresh, back navigation, a shared link, a retry, a second click?
- **Failure and edge states**: loading, empty vs. "nothing matches", errors, slow or failing external calls
  (never block a request on them), duplicates and races.
- **Scope**: what did you add that nobody asked for? Cut it.

**4. Verify each prediction against the code.** For every item, look: is it actually a problem here,
and what does the codebase already do for it (an existing helper, status, pattern)? Prefer reusing the
existing flow over inventing a parallel one.

**5. Escalate or fix the plan.** Convene the board (section 2) if ANY of these is true. Don't judge it yourself;
these are mechanical:
- your plan **adds a database column or table, a new status/state value, or a shared config value**; or
- step 1 found **more than one writer or entry path** for the thing you are changing; or
- a question is still open after step 4 that only the user can answer, and a wrong guess is costly.

Otherwise fix the plan yourself and build it end to end. Typecheck/test.

**6. Self-review before "done".** Re-read your diff against your step-3 list. Anything still open:
fix it, or state it plainly in your summary as a known limitation with the reason.

In your final summary, include one line: the prediction from step 3 that changed your plan the most.

**Template (post this before the first edit):**
```
PRE-MORTEM
Real need: <one line>
Today: <files; parallel paths; group/inheritance>
Writers/entry paths: <every place that creates or updates it, with file:line>
Readers/consumers: <every place that reads it>
Decision: <one line>   Rejected: <option - why>
Predicted rejections (and what the code says): 1..5
Board? <yes/no - which mechanical trigger>
```

## 2. The board meeting (`board.py`)

Your pre-mortem is the brief. Pass it in; the board members read the repo themselves and check it.

```
uv run <skill-dir>/scripts/board.py \
  -q "User request: '<quote it>'. <the decision to make>" \
  -c "<what exists today (file paths), your decision, rejected options, your step-3 predictions and what you verified>" \
  --options "A: <option>" "B: <option>" \
  [--files key/file.ts other/file.ts] [--seats architect,product,security,skeptic]
```

**It takes 2–4 minutes: run it with a long command timeout** (in Claude Code, Bash `timeout: 600000`).
Default seats are `architect,product`. Add `security` for auth, payments, outbound messages or webhooks.

The script prints a **Board resolution** (recommendation, plan, rejected options, risks, and a
**Needs your decision** list with default answers).
- Show the user the resolution and ask them to approve and answer the "Needs your decision" items.
  **Don't implement until they approve**, unless they already said to go with the board's defaults.
- Then implement the plan step by step. If a step turns out wrong in the code, tell the user why you deviated.
- One board per task is normally enough.

## 3. Stuck (`consult.py unstuck`)

Same error or failing check after 2 attempts, or you are guessing at the cause:

```
uv run <skill-dir>/scripts/consult.py unstuck -q "<what fails>" -c "<attempts + exact output>" --files a b
uv run <skill-dir>/scripts/consult.py reply   -q "<answer its QUESTIONS, or push back>"   # same meeting
```

## Settings and notes
- Models: `BOARD_SEAT_MODEL` (default `sonnet`), `BOARD_CHAIR_MODEL` (`opus`), `CONSULT_MODEL` (`opus`; `sonnet` is cheaper).
- Backends: the `claude` CLI (the user's login) first, then `ANTHROPIC_API_KEY`.
- Run the scripts with `uv run` (they declare their own isolated environment, so this never touches the
  project's dependencies). Without uv, use `python3 <skill-dir>/scripts/...` instead; they are stdlib-only.
- Everything is logged with its cost in `.consult/log.jsonl`; board resolutions are saved as `.consult/board-*.md`.
- Works the same from Claude Code and Codex: they're plain shell commands.
