---
name: consult
description: Before building anything that involves a design decision (data model or schema, which user or record something belongs to, new states or statuses, API contracts, where state lives, UI for a new feature, or a vague request that can be read several ways), run a short pre-mortem - decide, predict how the decision fails, check those predictions against the code, and fix the plan - then build. Escalate to a stronger model only for a question the code cannot answer. Also covers being stuck and a final self-review. Built for cheaper models like Haiku that run as the daily driver.
---

# Decide like a senior engineer: predict, verify, then build

You are probably a fast, cheap model. Your failure mode is not bad code; it is taking the first
plausible design and never asking how it will fail. A senior engineer's edge is that they **predict
the review before writing the code**. Do that yourself. It costs a few minutes and saves the user from
sending your work back.

## When

Before writing code, if the task involves any of: a data model / new field; identity (which user,
record or tenant); a new state or status; an API or contract others depend on; where state lives;
a new UI feature; or a vague request ("improve X", "make it real", "fix that").
Skip it for small, clear, local edits.

## The pre-mortem (write it out, briefly, before the first edit)

**1. Read first.** Find how it works today: the files involved, every parallel code path (e.g. two
storage backends, two clients), and **every consumer** of what you will change (grep for the type,
field, status or route).

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

**5. Fix the plan**, then build it end to end. Typecheck/test.

**6. Self-review before "done".** Re-read your diff against your step-3 list. Anything still open:
fix it, or state it plainly in your summary as a known limitation with the reason.

## Escalate only when the code can't answer

If, after step 4, a question is still open *and* a wrong guess would be costly (it is a product decision
only the user can make, or two designs look equally right and are hard to undo), hold a short meeting
with a stronger model. Bring your pre-mortem - it is far more useful correcting a concrete plan:

```
python <skill-dir>/scripts/consult.py decide -q "<the one open question>" -c "<your decision, rejected options, predictions and what you verified>" --files a b
python <skill-dir>/scripts/consult.py reply  -q "<answer its QUESTIONS or push back>"
python <skill-dir>/scripts/consult.py unstuck -q "<what fails>" -c "<attempts + exact output>"   # same failure after 2 attempts
```

At most one meeting per task. Most tasks need none.

In your final summary, include one line: the prediction from step 3 that changed your plan the most.
