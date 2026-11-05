#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Board meeting: several stronger models deliberate on a decision and the chair writes a resolution
for the USER to approve.

  1. Brief    - the calling agent (e.g. Haiku) supplies the question, its research and candidate options
  2. Positions- each board seat (default: architect + product, on Sonnet) answers independently, in parallel
  3. Debate   - each seat sees the others' positions once and agrees / objects / adds what was missed
  4. Chair    - Opus synthesizes a board resolution: recommendation, why, rejected options, dissent,
                risks, and the questions only the user can answer

Usage:
  uv run board.py -q "How should order cancellation work?" -c "<brief: what exists, constraints>" \
      --options "A: status=cancelled + notify the customer" "B: soft-delete" --files src/models.ts src/db.ts

The resolution is printed and saved to .consult/board-<timestamp>.md. Show it to the user and wait for approval.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import consult as C  # noqa: E402

SEATS = {
    "architect": "You are the ARCHITECT on the board. Focus on data model, state and status lifecycles, API "
                 "contracts, every code path that must change (look for parallel implementations, e.g. two "
                 "storage backends, and for every consumer of a changed type), migration and failure modes.",
    "product": "You are the PRODUCT & UX lead on the board. Focus on what the user actually needs (the real "
               "intent behind a vague request), user flows, UI states (loading, empty, error, confirmation), "
               "copy and i18n, accessibility, and what to deliberately leave out (scope).",
    "security": "You are the SECURITY & RELIABILITY lead on the board. Focus on authorization (who may do this), "
                "abuse, data integrity, races, idempotency, external side effects (messages, calls, webhooks) "
                "and what happens when they fail.",
    "skeptic": "You are the SKEPTIC on the board. Attack the proposed plan: find the hidden assumption, the "
               "simpler alternative, the requirement nobody asked about, and the thing that will break in production.",
}

BOARD_RULES = """
You sit on a board that is deciding how to build something for a user. A junior agent prepared the brief.
You can read the repository (Read/Grep/Glob). Verify claims in the brief against the code; don't trust it blindly.
Be concrete: file paths, functions, statuses, fields. Keep it under ~350 words. Structure:
POSITION: the option you back (or a better one), in one line
WHY: 3-5 bullets
MUST NOT MISS: things any solution must handle, from your seat's angle
QUESTION FOR THE USER: only if a real product decision can't be inferred from the code (else 'none')"""

DEBATE = """Here are the other board members' positions. Respond once, under ~200 words:
AGREE: what you now accept
OBJECT: what you still disagree with and why (cite code where you can)
MISSED: anything nobody has raised yet
FINAL POSITION: one line

{others}"""

CHAIR = """You are the CHAIR of the board (the strongest model). Below are the brief and the board's deliberation.
Write the BOARD RESOLUTION that will be shown to the USER for approval before any code is written.
Verify the key facts in the repo yourself if needed. Decide; don't just summarize. Format exactly:

# Board resolution: <short title>
**Recommendation:** <the solution in 2-3 sentences>
## Why
- ...
## The plan
<numbered implementation steps, naming the files / functions to change; include every code path that must
change, e.g. all storage backends, every consumer of a changed status/type, docs/manifests>
## Options considered and rejected
- <option>: <why not>
## Dissent and risks
- ...
## Needs your decision
<numbered questions only the user can answer, each with the board's default answer. 'None' if there are none>

---
{brief}

## Board positions (round 1)
{positions}

## Debate (round 2)
{debate}"""


def call(prompt: str, model: str, system: str, session=None, read=True):
    errors = []
    for backend in (lambda: C.via_cli(prompt, model, read, session, system=system),
                    lambda: C.via_api(prompt, model, session, system=system)):
        try:
            return backend()
        except Exception as e:  # try next backend
            errors.append(str(e))
    raise RuntimeError("no backend worked: " + " | ".join(errors))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--question", "-q", required=True)
    ap.add_argument("--context", "-c", help="your brief: the user's request, what exists today, constraints")
    ap.add_argument("--options", nargs="*", help="candidate options you are considering")
    ap.add_argument("--files", nargs="*", help="key files (seats can also read the repo themselves)")
    ap.add_argument("--context-file", action="append")
    ap.add_argument("--seats", default=os.environ.get("BOARD_SEATS", "architect,product"),
                    help=f"comma list from {','.join(SEATS)}")
    ap.add_argument("--seat-model", default=os.environ.get("BOARD_SEAT_MODEL", "sonnet"))
    ap.add_argument("--chair-model", default=os.environ.get("BOARD_CHAIR_MODEL", "opus"))
    ap.add_argument("--no-debate", action="store_true", help="skip round 2 (cheaper)")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if os.environ.get("CONSULT_NESTED"):
        print("board: refusing nested meeting.", file=sys.stderr)
        return 2

    parts = [f"## Decision to make\n{a.question}"]
    if a.context:
        parts.append(f"## Brief from the agent\n{a.context}")
    if a.options:
        parts.append("## Options the agent is considering\n" + "\n".join(f"- {o}" for o in a.options))
    for cf_ in a.context_file or []:
        parts.append(f"## {cf_}\n{Path(cf_).read_text(encoding='utf-8', errors='replace')}")
    for f in a.files or []:
        if Path(f).is_file():
            parts.append(f"## File: {f}\n```\n{Path(f).read_text(encoding='utf-8', errors='replace')[:15000]}\n```")
    brief = "\n\n".join(parts)[: C.MAX_CONTEXT_CHARS]
    seats = [s.strip() for s in a.seats.split(",") if s.strip() in SEATS]
    t0, cost = time.time(), 0.0

    print(f"Board convened: {', '.join(seats)} ({a.seat_model}), chair ({a.chair_model}).", file=sys.stderr, flush=True)
    with cf.ThreadPoolExecutor(len(seats)) as ex:
        r1 = dict(zip(seats, ex.map(lambda s: call(brief, a.seat_model, SEATS[s] + BOARD_RULES), seats)))
    positions = {s: r[0] for s, r in r1.items()}
    cost += sum(r[1] or 0 for r in r1.values())

    debate = {}
    if not a.no_debate and len(seats) > 1:
        def rebut(s):
            others = "\n\n".join(f"### {o.upper()}\n{p}" for o, p in positions.items() if o != s)
            return call(DEBATE.format(others=others), a.seat_model, SEATS[s] + BOARD_RULES, session=r1[s][2])
        with cf.ThreadPoolExecutor(len(seats)) as ex:
            r2 = dict(zip(seats, ex.map(rebut, seats)))
        debate = {s: r[0] for s, r in r2.items()}
        cost += sum(r[1] or 0 for r in r2.values())

    fmt = lambda d: "\n\n".join(f"### {k.upper()}\n{v}" for k, v in d.items()) or "(skipped)"
    resolution, c_cost, _ = call(CHAIR.format(brief=brief, positions=fmt(positions), debate=fmt(debate)),
                                 a.chair_model, "You chair a technical board meeting. Be decisive and concrete.")
    cost += c_cost or 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = C.state_dir() / f"board-{stamp}.md"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f"{resolution}\n\n---\n<details><summary>Board deliberation</summary>\n\n"
                       f"{fmt(positions)}\n\n## Debate\n{fmt(debate)}\n</details>\n", encoding="utf-8")
    except OSError:
        pass
    C.log({"ts": time.time(), "mode": "board", "model": f"{a.seat_model}x{len(seats)}+{a.chair_model}",
           "question": a.question[:300], "seconds": round(time.time() - t0, 1), "cost_usd": round(cost, 4),
           "answer_chars": len(resolution)})
    print(resolution.strip())
    print(f"\n(Saved to {out}. Board cost ${cost:.2f}, {time.time() - t0:.0f}s.)")
    print("\n>>> Show this resolution to the user and WAIT for approval (or their answers to 'Needs your decision') "
          "before implementing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
