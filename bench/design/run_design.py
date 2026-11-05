# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Round 2: design-decision benchmark on a real repo, graded by a blind Opus judge.

  python run_design.py --repo ~/your-repo --conditions baseline,ship2,sonnet --trials 2
  python run_design.py --report-only results/<stamp>.jsonl

Per run: `git clone` the repo into a temp dir (your repo is never modified), junction
node_modules, run the agent headless, typecheck, capture the diff, then a fresh Opus judge scores the
diff against a hidden checklist. The judge never sees the condition, the consult logs or the agent's summary.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_SRC = HERE.parent.parent / "skills" / "consult"
# Task file (DESIGN_TASKS, default tasks.example.json): a plain list of tasks, or a dict that also configures the repo:
#   {"agent_prompt": "...{task}...", "check": "bash check.sh {work}", "extra_tools": [...], "path_prepend": "...",
#    "node_modules": ["frontend"], "conventions_hint": "...", "tasks": [...]}
TASKS_FILE = Path(os.environ.get("DESIGN_TASKS", HERE / "tasks.example.json"))
_spec = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
SPEC = _spec if isinstance(_spec, dict) else {"tasks": _spec}
TASKS = {t["id"]: t for t in SPEC["tasks"]}
CLAUDE = shutil.which("claude")

AGENT_PROMPT = SPEC.get("agent_prompt") or """{task}

Work in this repository. Make sensible product and engineering decisions and implement the
change end-to-end, following the codebase's existing conventions. Typecheck with `npx tsc --noEmit`.
You can't run the dev server. When you're done, reply with a short summary of what you decided and why."""
CONVENTIONS_HINT = SPEC.get("conventions_hint", "the codebase's existing architecture and conventions")

NUDGE = "\n\nYou have a `consult` skill for meeting with a stronger model; follow its guidance."

CONDITIONS = {
    "baseline": {"model": "haiku", "skill": False},
    "skill": {"model": "haiku", "skill": True},
    "skill_nudge": {"model": "haiku", "skill": True, "suffix": NUDGE},
    "skill_nudge_sonnet": {"model": "haiku", "skill": True, "suffix": NUDGE, "consult": "sonnet"},
    # board meeting (Sonnet seats + Opus chair). No human in a benchmark -> user pre-approves the board's defaults.
    "board": {"model": "haiku", "skill": True, "consult": "sonnet", "skill_src": "staging",
              "suffix": "\n\nYou have a `consult` skill: convene its board meeting before building, per its guidance. "
                        "The user is unavailable and pre-approves the board's recommendation and default answers, "
                        "so implement right after the meeting."},
    # pre-mortem: Haiku predicts how its own decision fails and verifies against the code; consults only if stuck
    "reflect": {"model": "haiku", "skill": True, "consult": "sonnet", "skill_src": "reflect",
                "suffix": "\n\nYou have a `consult` skill for making design decisions; follow its guidance."},
    # what we ship: pre-mortem by default, board only for cross-cutting changes / open product questions
    "ship": {"model": "haiku", "skill": True, "consult": "sonnet", "skill_src": "ship",
             "suffix": "\n\nYou have a `consult` skill for making design decisions; follow its guidance. "
                       "The user is unavailable and pre-approves a board's recommendation and default answers, "
                       "so if you convene one, implement right after it."},
    "ship2": {"model": "haiku", "skill": True, "consult": "sonnet", "skill_src": "ship2",
              "suffix": "\n\nYou have a `consult` skill for making design decisions; follow its guidance. "
                        "The user is unavailable and pre-approves a board's recommendation and default answers, "
                        "so if you convene one, implement right after it."},
    "sonnet": {"model": "sonnet", "skill": False},
    "opus": {"model": "opus", "skill": False},
}

AGENT_TOOLS = ["Read", "Edit", "Write", "Glob", "Grep", "Skill",
               "Bash(npx tsc *)", "Bash(python *)", "Bash(python3 *)",
               "Bash(git diff *)", "Bash(git status *)", "Bash(git log *)", "Bash(ls *)"] + SPEC.get("extra_tools", [])

JUDGE_PROMPT = """You are a strict staff engineer grading one engineer's change to this repository.
The repository in the current directory is the ORIGINAL code (before the change). The change is the diff below.
You may read repo files to judge consistency with existing conventions.

## The request the engineer received
{task}

## What a strong solution considers (hidden checklist, the engineer did not see it)
{checklist}

## Typecheck after the change
{tsc}

## The diff
```diff
{diff}
```

Grade from 1 to 10 on each axis (10 = what an excellent senior engineer would ship; 5 = works but with notable
gaps; 1 = broken or misses the point). Be calibrated and harsh: unverified claims count for nothing; only the diff counts.
- decisions: quality of the product/design decisions (interpreting the request, trade-offs, the identity/data/state choices)
- conventions: fits the existing architecture ({conventions_hint})
- correctness: would it actually work, end-to-end, without breaking anything
- ux: states, accessibility, polish (for backend-only tasks: API ergonomics and docs)

Reply with ONLY a JSON object:
{{"decisions": n, "conventions": n, "correctness": n, "ux": n, "overall": n, "checklist_hits": n_of_{n_items}, "biggest_issue": "one sentence"}}"""


def sh(cmd, cwd, timeout=600, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env=env)


def prepare(repo: Path, dest: Path) -> None:
    sh(["git", "clone", "-q", "--no-hardlinks", str(repo), str(dest)], cwd=dest.parent, timeout=300)
    for sub in SPEC.get("node_modules", ["."]):
        src_nm, dst_nm = repo / sub / "node_modules", dest / sub / "node_modules"
        if not src_nm.exists():
            continue
        if os.name == "nt":  # junction: no admin rights needed
            sh(["cmd", "/c", "mklink", "/J", str(dst_nm), str(src_nm)], cwd=dest)
        else:
            os.symlink(src_nm, dst_nm, target_is_directory=True)
    with open(dest / ".git" / "info" / "exclude", "a") as fh:
        fh.write("\n.consult/\n.claude/\nnode_modules\n*.tsbuildinfo\n")


def agent_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k != "CONSULT_NESTED"}
    if SPEC.get("path_prepend"):
        env["PATH"] = SPEC["path_prepend"] + os.pathsep + env.get("PATH", "")
    return env


def tsc(work: Path) -> tuple[bool, str]:
    """The repo's check: `npx tsc` by default, or the task file's "check" command."""
    if SPEC.get("check"):
        r = subprocess.run(SPEC["check"].format(work=str(work), here=str(HERE)), shell=True, cwd=work,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900, env=agent_env())
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, ("PASS (" + SPEC["check"].split()[0] + " checks)" if r.returncode == 0 else f"FAIL:\n{out[-3000:]}")
    r = sh([shutil.which("npx") or "npx", "tsc", "--noEmit", "-p", "."], cwd=work, timeout=300)
    out = (r.stdout + r.stderr).strip()
    errs = len(re.findall(r"error TS\d+", out))
    return r.returncode == 0, ("PASS (no type errors)" if r.returncode == 0 else f"FAIL - {errs} type errors:\n{out[-3000:]}")


def run_agent(task_id, cond, trial, repo, root, consult_model, timeout):
    cfg = CONDITIONS[cond]
    work = root / f"{task_id}__{cond}__{trial}"
    prepare(repo, work)
    if cfg["skill"]:
        variant = cfg.get("skill_src")
        src = {"staging": HERE / "variants" / "board",  # the board-first version, formerly staging/
               "reflect": HERE / "variants" / "reflect",
               "ship": HERE / "variants" / "ship",
               "ship2": HERE / "variants" / "ship2"}.get(variant, SKILL_SRC)
        if not src.exists():
            src = SKILL_SRC
        dest = work / ".claude" / "skills" / "consult"
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
        if not (dest / "scripts").exists():  # variants that only change SKILL.md reuse the shipped scripts
            shutil.copytree(SKILL_SRC / "scripts", dest / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    env = agent_env()
    env.update(CONSULT_LOG=str(work / ".consult" / "log.jsonl"), CONSULT_MODEL=cfg.get("consult", consult_model))
    prompt = AGENT_PROMPT.format(task=TASKS[task_id]["prompt"]) + cfg.get("suffix", "")
    cmd = [CLAUDE, "-p", prompt, "--model", cfg["model"], "--output-format", "json",
           "--permission-mode", "acceptEdits", "--allowedTools", *AGENT_TOOLS,
           "--setting-sources", "project", "--max-budget-usd", "8"]
    t0 = time.time()
    try:
        r = sh(cmd, cwd=work, timeout=timeout, env=env)
        out = json.loads(r.stdout)
    except subprocess.TimeoutExpired:
        out = {"is_error": True, "result": "timeout"}
    except json.JSONDecodeError:
        out = {"is_error": True, "result": (r.stdout + r.stderr)[-500:]}
    rec = {"task": task_id, "cond": cond, "trial": trial, "model": cfg["model"], "dir": str(work),
           "seconds": round(time.time() - t0, 1), "agent_cost": out.get("total_cost_usd") or 0.0,
           "turns": out.get("num_turns"), "agent_error": bool(out.get("is_error")),
           "summary": str(out.get("result", ""))[-1500:]}
    log = work / ".consult" / "log.jsonl"
    consults = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.exists() else []
    rec.update(consults=len(consults), consult_modes=[c["mode"] for c in consults],
               consult_cost=round(sum(c.get("cost_usd") or 0 for c in consults), 4))
    rec["tsc_pass"], rec["tsc"] = tsc(work)
    sh(["git", "add", "-A"], cwd=work)
    diff = sh(["git", "diff", "--cached", "HEAD", "--", ".", ":(exclude)package-lock.json"], cwd=work).stdout
    diff_dir = Path(os.environ.get("DESIGN_DIFF_DIR", root))
    diff_dir.mkdir(parents=True, exist_ok=True)
    (diff_dir / f"{work.name}.diff").write_text(diff, encoding="utf-8")
    rec["diff_lines"] = sum(1 for l in diff.splitlines() if l[:1] in "+-" and l[:3] not in ("+++", "---"))
    rec["diff_file"] = str(diff_dir / f"{work.name}.diff")
    board = sorted((work / ".consult").glob("board-*.md")) if (work / ".consult").exists() else []
    if board:  # keep the board resolution(s) for inspection
        for i, b in enumerate(board):
            shutil.copy(b, diff_dir / f"{work.name}.board{i}.md")
    return rec


def judge(rec, root, repo):
    """Blind judge: runs in a pristine clone so it can't see skill files, consult logs or the agent's summary."""
    jdir = root / f"judge__{Path(rec['dir']).name}"
    shutil.rmtree(jdir, ignore_errors=True)  # a stale clone from an interrupted judge would make `git clone` fail
    prepare(repo, jdir)
    diff = Path(rec["diff_file"]).read_text(encoding="utf-8")
    if len(diff) > 90000:
        diff = diff[:90000] + "\n[... diff truncated ...]"
    t = TASKS[rec["task"]]
    prompt = JUDGE_PROMPT.format(task=t["prompt"], checklist="\n".join(f"- {c}" for c in t["checklist"]),
                                 tsc=rec["tsc"][:3000], diff=diff or "(empty diff: no changes made)",
                                 n_items=len(t["checklist"]), conventions_hint=CONVENTIONS_HINT)
    # prompt via stdin (it is long)
    r = subprocess.run([CLAUDE, "-p", "--model", "opus", "--output-format", "json", "--setting-sources", "project",
                        "--tools", "Read,Grep,Glob", "--max-budget-usd", "2"], cwd=jdir, input=prompt, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900, env=dict(os.environ, CONSULT_NESTED="1"))
    scores = {"judge_error": f"no JSON in judge output: {(r.stdout or r.stderr)[-300:]}"}
    try:
        out = json.loads(r.stdout)
        text = out.get("result", "") or ""
        dec = json.JSONDecoder()
        for i in [m.start() for m in re.finditer(r"\{", text)]:  # first parseable object with "overall"
            try:
                obj, _ = dec.raw_decode(text[i:])
            except ValueError:
                continue
            if isinstance(obj, dict) and "overall" in obj:
                scores = obj
                break
        scores["judge_cost"] = out.get("total_cost_usd") or 0
        if out.get("is_error"):
            scores.setdefault("judge_error", f"judge is_error: {text[-200:]}")
    except Exception as e:
        scores = {"judge_error": repr(e)[:200]}
    shutil.rmtree(jdir, ignore_errors=True)
    return scores


def report(rows):
    bad = [r for r in rows if r.get("invalid") or "overall" not in r]
    rows = [r for r in rows if r not in bad]
    conds = [c for c in CONDITIONS if any(r["cond"] == c for r in rows)]
    axes = ["overall", "decisions", "conventions", "correctness", "ux"]

    def m(rs, k):
        v = [r[k] for r in rs if isinstance(r.get(k), (int, float))]
        return statistics.mean(v) if v else float("nan")

    L = ["## Overall (blind Opus judge, 1-10)", "",
         "| condition | runs | " + " | ".join(axes) + " | tsc pass | avg cost $ (agent+consult) | consults/run | avg min |",
         "|---|---|" + "---|" * len(axes) + "---|---|---|---|"]
    for c in conds:
        rs = [r for r in rows if r["cond"] == c]
        L.append(f"| {c} | {len(rs)} | " + " | ".join(f"{m(rs, a):.1f}" for a in axes) +
                 f" | {sum(r['tsc_pass'] for r in rs)}/{len(rs)} | {m(rs, 'total_cost'):.2f} | {m(rs, 'consults'):.1f} | {m(rs, 'seconds')/60:.1f} |")
    L += ["", "## Overall score per task", "", "| task | " + " | ".join(conds) + " |", "|---|" + "---|" * len(conds)]
    for t in TASKS:
        cells = []
        for c in conds:
            rs = [r for r in rows if r["task"] == t and r["cond"] == c]
            cells.append(" / ".join(str(r.get("overall", "?")) for r in rs) or "-")
        L.append(f"| {t} | " + " | ".join(cells) + " |")
    modes = {}
    for r in rows:
        for x in r["consult_modes"]:
            modes[x] = modes.get(x, 0) + 1
    if modes:
        L += ["", "Consultations by mode: " + ", ".join(f"{k}={v}" for k, v in sorted(modes.items()))]
    if bad:
        L += ["", f"Excluded {len(bad)} invalid runs (agent error / no judge score): "
              + ", ".join(f"{r['task']}/{r['cond']}#{r['trial']}" for r in bad)]
    L += ["", "## Biggest issue per run", ""]
    for r in sorted(rows, key=lambda r: (r["task"], r["cond"], r["trial"])):
        L.append(f"- **{r['task']} / {r['cond']} #{r['trial']}** ({r.get('overall', '?')}/10): {r.get('biggest_issue', r.get('judge_error', ''))}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="path to the git repo to benchmark on (it is cloned, never modified)")
    ap.add_argument("--tasks", default=",".join(TASKS))
    ap.add_argument("--conditions", default="baseline,skill,skill_nudge,sonnet")
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--consult-model", default="opus")
    ap.add_argument("--timeout", type=int, default=2400)
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--report-only", default=None)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if a.report_only:
        print(report([json.loads(l) for l in Path(a.report_only).read_text(encoding="utf-8").splitlines() if l.strip()]))
        return
    repo = Path(a.repo).expanduser().resolve()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    root = Path(a.workdir or tempfile.gettempdir()) / f"design-bench-{stamp}-{os.getpid()}"  # pid: parallel runs never collide
    root.mkdir(parents=True)
    out = Path(os.environ.get("DESIGN_RESULTS_DIR", HERE / "results")) / f"{stamp}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    jobs = [(t, c, i) for i in range(a.trials) for t in a.tasks.split(",") for c in a.conditions.split(",")]
    random.Random(0).shuffle(jobs)
    print(f"{len(jobs)} runs -> {out}\nworkspaces: {root}", flush=True)

    def full(job):
        rec = run_agent(*job, repo, root, a.consult_model, a.timeout)
        rec["total_cost"] = round(rec["agent_cost"] + rec["consult_cost"], 4)
        # an agent that errored or spent nothing never actually ran (e.g. usage limit hit)
        rec["invalid"] = rec["agent_error"] or rec["agent_cost"] == 0
        if rec["invalid"]:
            rec["judge_error"] = f"agent run invalid: {rec['summary'][-200:]}"
        else:
            rec.update(judge(rec, root, repo))
            rec["invalid"] = "overall" not in rec
        return rec

    rows = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        futs = {ex.submit(full, j): j for j in jobs}
        for f in cf.as_completed(futs):
            try:
                r = f.result()
            except Exception as e:
                print(f"!! {futs[f]} crashed: {e!r}", flush=True)
                continue
            rows.append(r)
            if len(rows) >= 3 and all(x.get("invalid") and x["agent_cost"] == 0 for x in rows[-3:]):
                print("!! 3 empty runs in a row (usage limit?) - cancelling the rest", flush=True)
                for other in futs:
                    other.cancel()
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(r) + "\n")
            print(f"[{len(rows)}/{len(jobs)}] {r['task']:9} {r['cond']:11} #{r['trial']} overall={r.get('overall')} "
                  f"tsc={'ok' if r['tsc_pass'] else 'FAIL'} consults={r['consults']} ${r['total_cost']:.2f} "
                  f"{r['seconds']/60:.1f}min", flush=True)
    rep = report(rows)
    out.with_suffix(".md").write_text(rep, encoding="utf-8")
    print("\n" + rep)


if __name__ == "__main__":
    main()
