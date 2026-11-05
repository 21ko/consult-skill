# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""A/B benchmark: does the `consult` skill make Haiku better?

Conditions:
  baseline  - Haiku alone
  skill     - Haiku + consult skill (it decides by itself when to consult Opus/Sonnet)
  sonnet    - Sonnet alone (reference point: "why not just use the bigger model?")
  opus      - Opus alone (reference point)

Each run: fresh copy of the task workspace -> `claude -p` headless -> hidden tests -> cost.

  python run_bench.py --trials 3 --conditions baseline,skill --jobs 4
  python run_bench.py --report-only results/<run>.jsonl
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_SRC = HERE.parent / "skills" / "consult"
sys.path.insert(0, str(HERE))
from grade import MODULE  # noqa: E402

PROMPT = ("Implement the task described in README.md in this directory. It must be fully correct "
          "according to the spec, including every edge case - it will be graded by a much larger "
          "hidden test suite. Visible tests: `python test_visible.py`. When you are finished, reply DONE.")

CONDITIONS = {
    "baseline": {"model": "haiku", "skill": False},
    "skill": {"model": "haiku", "skill": True},
    # same, plus one sentence telling the agent the skill exists (tests "does it help when used?")
    "skill_nudge": {"model": "haiku", "skill": True,
                    "suffix": " You have a `consult` skill for escalating to a stronger model; follow its guidance."},
    "sonnet": {"model": "sonnet", "skill": False},
    "opus": {"model": "opus", "skill": False},
}


def run_one(task: str, cond: str, trial: int, root: Path, consult_model: str, timeout: int) -> dict:
    cfg = CONDITIONS[cond]
    work = root / f"{task}__{cond}__{trial}"
    shutil.copytree(HERE / "tasks" / task / "workspace", work)
    if cfg["skill"]:
        shutil.copytree(SKILL_SRC, work / ".claude" / "skills" / "consult")
    git = ["git", "-c", "user.name=bench", "-c", "user.email=bench@local"]
    subprocess.run(git + ["init", "-q"], cwd=work, check=True)
    (work / ".gitignore").write_text(".consult/\n.claude/\n__pycache__/\n")
    subprocess.run(git + ["add", "-A"], cwd=work, check=True)
    subprocess.run(git + ["commit", "-qm", "task"], cwd=work, check=True)

    env = {k: v for k, v in os.environ.items() if k != "CONSULT_NESTED"}
    env.update(CONSULT_LOG=str(work / ".consult" / "log.jsonl"), CONSULT_MODEL=consult_model)
    cmd = [shutil.which("claude"), "-p", PROMPT + cfg.get("suffix", ""), "--model", cfg["model"], "--output-format", "json",
           # sandboxed-ish: edits auto-accepted, shell limited to `python ...`; everything else denied
           "--permission-mode", "acceptEdits",
           "--allowedTools", "Read", "Edit", "Write", "Glob", "Grep", "Skill",
           "Bash(python *)", "Bash(python3 *)", "Bash(py *)",
           "--setting-sources", "project",
           "--max-budget-usd", "5"]
    t0 = time.time()
    rec = {"task": task, "cond": cond, "trial": trial, "model": cfg["model"], "dir": str(work)}
    try:
        r = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        try:
            out = json.loads(r.stdout)
        except json.JSONDecodeError:
            out = {"is_error": True, "result": (r.stdout + r.stderr)[-500:]}
    except subprocess.TimeoutExpired:
        out = {"is_error": True, "result": "timeout"}
    rec.update(seconds=round(time.time() - t0, 1), agent_cost=out.get("total_cost_usd") or 0.0,
               turns=out.get("num_turns"), agent_error=bool(out.get("is_error")),
               final=str(out.get("result", ""))[-300:])

    consults = []
    log = work / ".consult" / "log.jsonl"
    if log.exists():
        consults = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    rec.update(consults=len(consults), consult_modes=[c["mode"] for c in consults],
               consult_cost=round(sum(c.get("cost_usd") or 0 for c in consults), 4))
    rec["total_cost"] = round(rec["agent_cost"] + rec["consult_cost"], 4)

    try:
        g = subprocess.run([sys.executable, str(HERE / "grade.py"), task, str(work / f"{MODULE[task]}.py")],
                           capture_output=True, text=True, timeout=180, cwd=HERE)
        grade = json.loads(g.stdout.strip().splitlines()[-1])
    except Exception as e:  # infinite loop, crash...
        grade = {"passed": 0, "total": None, "error": repr(e)[:200]}
    rec.update(passed=grade["passed"], total=grade["total"], failures=grade.get("failures", [])[:10],
               solved=grade["total"] is not None and grade["passed"] == grade["total"])
    return rec


def report(rows: list[dict]) -> str:
    def agg(rs):
        fr = [r["passed"] / r["total"] for r in rs if r["total"]]
        return {
            "n": len(rs),
            "solved": sum(r["solved"] for r in rs),
            "score": 100 * statistics.mean(fr) if fr else 0,
            "cost": statistics.mean(r["total_cost"] for r in rs),
            "cons": statistics.mean(r["consults"] for r in rs),
            "ccost": statistics.mean(r["consult_cost"] for r in rs),
            "sec": statistics.mean(r["seconds"] for r in rs),
        }

    conds = [c for c in CONDITIONS if any(r["cond"] == c for r in rows)]
    tasks = sorted({r["task"] for r in rows})
    lines = ["## Overall", "",
             "| condition | runs | fully solved | avg hidden-test score | avg cost $ | of which consult $ | consults/run | avg time s |",
             "|---|---|---|---|---|---|---|---|"]
    for c in conds:
        a = agg([r for r in rows if r["cond"] == c])
        lines.append(f"| {c} | {a['n']} | {a['solved']}/{a['n']} ({100*a['solved']/a['n']:.0f}%) | {a['score']:.1f}% | "
                     f"{a['cost']:.3f} | {a['ccost']:.3f} | {a['cons']:.1f} | {a['sec']:.0f} |")
    lines += ["", "## Per task (avg hidden-test score % / fully solved)", "",
              "| task | " + " | ".join(conds) + " |", "|---|" + "---|" * len(conds)]
    for t in tasks:
        cells = []
        for c in conds:
            rs = [r for r in rows if r["task"] == t and r["cond"] == c]
            if rs:
                a = agg(rs)
                cells.append(f"{a['score']:.0f}% ({a['solved']}/{a['n']})")
            else:
                cells.append("-")
        lines.append(f"| {t} | " + " | ".join(cells) + " |")
    modes = {}
    for r in rows:
        for m in r["consult_modes"]:
            modes[m] = modes.get(m, 0) + 1
    if modes:
        lines += ["", "Consultations by mode: " + ", ".join(f"{k}={v}" for k, v in sorted(modes.items()))]
    errs = [r for r in rows if r["agent_error"]]
    if errs:
        lines += ["", f"Agent errors/timeouts: {len(errs)} runs"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default=",".join(MODULE))
    ap.add_argument("--conditions", default="baseline,skill")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--consult-model", default="opus")
    ap.add_argument("--timeout", type=int, default=1500)
    ap.add_argument("--out", default=None)
    ap.add_argument("--workdir", default=None, help="where run workspaces go (default: temp)")
    ap.add_argument("--report-only", default=None)
    a = ap.parse_args()

    if a.report_only:
        rows = [json.loads(l) for l in Path(a.report_only).read_text().splitlines() if l.strip()]
        print(report(rows))
        return

    stamp = time.strftime("%Y%m%d-%H%M%S")
    root = Path(a.workdir or tempfile.gettempdir()) / f"consult-bench-{stamp}"
    root.mkdir(parents=True)
    out = Path(a.out or HERE / "results" / f"{stamp}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    jobs = [(t, c, i) for i in range(a.trials) for t in a.tasks.split(",") for c in a.conditions.split(",")]
    print(f"{len(jobs)} runs -> {out}\nworkspaces: {root}", flush=True)
    rows = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        futs = {ex.submit(run_one, t, c, i, root, a.consult_model, a.timeout): (t, c, i) for t, c, i in jobs}
        for f in cf.as_completed(futs):
            try:
                r = f.result()
            except Exception as e:
                t, c, i = futs[f]
                print(f"!! {t}/{c}/{i} crashed: {e!r}", flush=True)
                continue
            rows.append(r)
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(r) + "\n")
            print(f"[{len(rows)}/{len(jobs)}] {r['task']:9} {r['cond']:8} #{r['trial']} "
                  f"{r['passed']}/{r['total']} consults={r['consults']} ${r['total_cost']:.3f} {r['seconds']}s",
                  flush=True)
    rep = report(rows)
    out.with_suffix(".md").write_text(rep, encoding="utf-8")
    print("\n" + rep)


if __name__ == "__main__":
    main()
