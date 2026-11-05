#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Consult a stronger model (Sonnet / Opus) from a cheaper agent (e.g. Haiku).

Works from any agent host (Claude Code, Codex, ...) because it only needs a shell.

Backends, tried in order:
  1. `claude` CLI in headless mode (uses the user's existing Claude login)
  2. Anthropic Messages API via ANTHROPIC_API_KEY (stdlib only, no pip install)

Modes:
  decide  - "hold a meeting": describe the situation + options, get a decision
  review  - ask the strong model to review your work (git diff + files) before finishing
  reply   - continue the current meeting: answer its QUESTIONS, push back, or report back
  unstuck - you tried things and they failed; get a diagnosis and next step

Usage examples:
  uv run consult.py decide  --question "Which approach?" --context "..."
  uv run consult.py unstuck --question "Test X still fails" --context-file notes.md
  uv run consult.py review  --question "Implemented feature Y per README" --diff --files src/a.py
  echo "long context" | uv run consult.py decide --question "..." --stdin

Every call is appended to .consult/log.jsonl in the current directory
(set CONSULT_LOG to change, or CONSULT_LOG=off to disable).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DEFAULT_MODEL = os.environ.get("CONSULT_MODEL", "opus")
API_MODEL_IDS = {
    "opus": "claude-opus-5-5",
    "sonnet": "claude-sonnet-5-5",
    "haiku": "claude-haiku-5-5",
}
MAX_CONTEXT_CHARS = int(os.environ.get("CONSULT_MAX_CHARS", "60000"))
MAX_TURNS = int(os.environ.get("CONSULT_MAX_TURNS", "4"))

SYSTEM = """You are a senior engineer in a meeting with a junior, cheaper AI coding agent.
The agent tends to take short answers at face value and skip deep reasoning, so your job is to
make it THINK: challenge its assumptions and make sure it understands why, not just what.
This is a multi-turn meeting: the agent can reply to you, answer your questions or push back.
Rules:
- If you lack information that would change the decision (user intent, constraints, existing
  conventions in the repo), you may reply with `QUESTIONS:` (at most 3, numbered) instead of
  deciding. You can also read files in the repo yourself when tools are available - prefer that.
- Otherwise give ONE clear recommendation. Do not list options without choosing.
- If the agent's premise is wrong, say so first.
- Point at specific files, functions, lines, edge cases. Name the trade-off you are accepting.
- Never write more than ~40 lines of code; prefer describing the change.
- End with `NEXT:` (concrete next actions) and then `MEETING: open` if you want the agent to
  report back / answer something, or `MEETING: closed` if it has enough to proceed."""

MODE_PROMPTS = {
    "decide": "The agent must make a decision and wants your call.\n"
              "Reply with: DECISION (one line), WHY (2-4 bullets), RISKS to watch, NEXT.",
    "unstuck": "The agent is stuck: its attempts are failing.\n"
               "Reply with: DIAGNOSIS (most likely root cause), EVIDENCE that would confirm it, "
               "FIX (what to change), NEXT.",
    "review": "The agent believes it finished and wants a review before reporting done.\n"
              "Check the work against the stated requirements. Look hard for bugs, missed edge cases, "
              "spec violations, untested paths, and (for UI/design work) inconsistency with the existing "
              "design system, accessibility, empty/loading/error states. Reply with: VERDICT (SHIP or FIX), "
              "ISSUES (numbered, most severe first, each with file/line and why), NEXT.\n"
              "Only flag real problems; say SHIP if it is genuinely correct.\n"
              "Also check SCOPE: list under UNREQUESTED CHANGES anything in the diff the user did not ask for and "
              "that the task doesn't need (refactors, renames, new deps, config/formatting churn, extra features). "
              "Those should be reverted and mentioned as suggestions instead.",
    "check": "GATE CHECK. The agent wants to either ASK THE USER a question or TAKE A STEP the user did not "
             "explicitly ask for. You protect the user's time and their codebase. Users hate (a) questions whose "
             "answer is in the repo, the request, or common sense, (b) being asked permission for what they "
             "already requested, and (c) unrequested changes they then have to undo.\n"
             "Look in the repo if it helps. Reply in at most 8 lines:\n"
             "VERDICT: ASK | DONT_ASK | PROCEED | DONT_DO | SUGGEST_ONLY\n"
             "- ASK: only for a real decision that only the user can make, where a wrong guess is costly. Give a "
             "  sharper version of the question, with a recommended default answer.\n"
             "- DONT_ASK: give the answer, or say exactly where to find it (file/command), or the sensible default.\n"
             "- PROCEED: the step is required to fulfil the request.\n"
             "- DONT_DO / SUGGEST_ONLY: out of scope. Don't do it; at most mention it in the final summary.\n"
             "WHY: one line. No MEETING line needed.",
    "reply": "",  # continue the current meeting
}


def gather(args: argparse.Namespace) -> str:
    parts: list[str] = [f"## Question\n{args.question}"]
    if args.context:
        parts.append(f"## Context\n{args.context}")
    for cf in args.context_file or []:
        parts.append(f"## Context file: {cf}\n{Path(cf).read_text(encoding='utf-8', errors='replace')}")
    if args.stdin:
        parts.append(f"## Additional context\n{sys.stdin.read()}")
    if args.diff:
        try:
            diff = subprocess.run(["git", "diff", "HEAD"], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=30).stdout
            untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                                       capture_output=True, text=True, timeout=30).stdout.split()
            if diff.strip():
                parts.append(f"## git diff\n```diff\n{diff}\n```")
            for u in untracked:
                if u.startswith(".consult/"):
                    continue
                args.files = (args.files or []) + [u]
        except Exception as e:  # not a git repo, etc.
            parts.append(f"(git diff unavailable: {e})")
    for f in dict.fromkeys(args.files or []):
        p = Path(f)
        if p.is_file():
            parts.append(f"## File: {f}\n```\n{p.read_text(encoding='utf-8', errors='replace')}\n```")
    text = "\n\n".join(parts)
    if len(text) > MAX_CONTEXT_CHARS:
        text = text[:MAX_CONTEXT_CHARS] + "\n\n[...context truncated...]"
    if args.mode == "reply":
        return f"(The agent replies in the same meeting.)\n\n{text}"
    return f"{MODE_PROMPTS[args.mode]}\n\n{text}"


def state_dir() -> Path:
    target = os.environ.get("CONSULT_LOG", ".consult/log.jsonl")
    return Path(".consult") if target == "off" else Path(target).parent


def load_session() -> dict | None:
    p = state_dir() / "session.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_session(s: dict) -> None:
    try:
        d = state_dir()
        d.mkdir(parents=True, exist_ok=True)
        (d / "session.json").write_text(json.dumps(s), encoding="utf-8")
    except OSError:
        pass


def via_cli(prompt: str, model: str, allow_read: bool, session: dict | None,
            system: str = SYSTEM) -> tuple[str, float | None, dict]:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI not found")
    cmd = [exe, "-p", "--model", model, "--output-format", "json",
           "--append-system-prompt", system,
           # keep the consultant lean: no user plugins/hooks, read-only tools
           "--setting-sources", "project",
           "--tools", "Read,Grep,Glob" if allow_read else ""]
    if session and session.get("cli_session_id"):
        cmd += ["--resume", session["cli_session_id"]]
    env = dict(os.environ, CONSULT_NESTED="1")
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=int(os.environ.get("CONSULT_TIMEOUT", "600")), env=env)
    if r.returncode != 0:
        raise RuntimeError(f"claude CLI failed ({r.returncode}): {r.stderr[-800:] or r.stdout[-800:]}")
    data = json.loads(r.stdout)
    if data.get("is_error"):
        raise RuntimeError(f"claude CLI error: {data.get('result')}")
    answer = data.get("result", "")
    new = dict(session or {}, backend="cli", cli_session_id=data.get("session_id"))
    return answer, data.get("total_cost_usd"), new


def via_api(prompt: str, model: str, session: dict | None,
            system: str = SYSTEM) -> tuple[str, float | None, dict]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    history = list((session or {}).get("messages", []))
    history.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": API_MODEL_IDS.get(model, model),
        "max_tokens": 4000,
        "system": system,
        "messages": history,
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    history.append({"role": "assistant", "content": text})
    return text, None, dict(session or {}, backend="api", messages=history)


def log(entry: dict) -> None:
    target = os.environ.get("CONSULT_LOG", ".consult/log.jsonl")
    if target == "off":
        return
    try:
        p = Path(target)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=sorted(MODE_PROMPTS))
    ap.add_argument("--question", "-q", required=True, help="what you need decided / reviewed")
    ap.add_argument("--context", "-c", help="what you tried, constraints, options considered")
    ap.add_argument("--context-file", action="append", help="file with extra context (repeatable)")
    ap.add_argument("--files", nargs="*", help="source files to include verbatim")
    ap.add_argument("--diff", action="store_true", help="include `git diff HEAD` + untracked files")
    ap.add_argument("--stdin", action="store_true", help="read extra context from stdin")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="opus (default) | sonnet | full model id")
    ap.add_argument("--no-read", action="store_true", help="don't let the consultant read files itself")
    args = ap.parse_args()
    try:  # Windows consoles default to cp1252; answers contain unicode
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    if os.environ.get("CONSULT_NESTED"):
        print("consult: refusing nested consultation (you ARE the consultant).", file=sys.stderr)
        return 2

    session = None
    if args.mode == "reply":
        session = load_session()
        if not session:
            print("consult: no open meeting; start one with decide/unstuck/review.", file=sys.stderr)
            return 2
        if session.get("turns", 0) >= MAX_TURNS:
            print(f"consult: meeting reached {MAX_TURNS} turns. Decide yourself now, "
                  "or start a new meeting with a sharper question.", file=sys.stderr)
            return 3
        args.model = session.get("model", args.model)

    prompt = gather(args)
    t0 = time.time()
    errors = []
    backends = [lambda: via_cli(prompt, args.model, not args.no_read, session),
                lambda: via_api(prompt, args.model, session)]
    if session and session.get("backend") == "api":
        backends.reverse()
    for backend in backends:
        try:
            answer, cost, new_session = backend()
            break
        except Exception as e:
            errors.append(str(e))
    else:
        print("consult: no backend worked:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1

    turns = (session or {}).get("turns", 0) + 1
    new_session.update(model=args.model, mode=(session or {}).get("mode", args.mode), turns=turns)
    save_session(new_session)
    log({"ts": time.time(), "mode": args.mode, "model": args.model, "question": args.question[:300],
         "turn": turns, "seconds": round(time.time() - t0, 1), "cost_usd": cost, "answer_chars": len(answer)})
    print(f"=== {args.model} says ({args.mode}, turn {turns}/{MAX_TURNS}) ===\n{answer.strip()}")
    if "MEETING: open" in answer and turns < MAX_TURNS:
        print("\n(The consultant expects a reply: "
              "`uv run <skill-dir>/scripts/consult.py reply -q \"...\"` (or python3))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
