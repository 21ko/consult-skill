# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Rework loop: what does it really cost to get each run to shippable, counting the human?

  python rework.py results/<stamp>.jsonl [--rounds 3] [--rate 60] [--jobs 4]
  python rework.py --report-only results/<stamp>.rework.jsonl [--rate 60]

For every valid run of run_design.py:
  1. A blind Opus judge reviews the diff like a PR reviewer: approve (shippable) or not, the concrete issues
     it would send back, and how many minutes a senior reviewer needs to find and write them up.
  2. Not approved -> the issues go back to the SAME agent session (`claude --resume`) as the user's follow-up,
     the agent fixes, and the new diff is judged again. Up to --rounds follow-ups.
  3. Still not approved after the last round -> the judge estimates the minutes for a human to finish it.

Total cost = model $ (agent + consults, all rounds) + human minutes x --rate/60.
The judge's own cost is not counted: it stands in for the human reviewer, whose minutes are counted instead.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_design as RD  # noqa: E402

REVIEW_SUFFIX = """

Also act as the PR reviewer who must decide whether this can be merged. Reply with ONLY a JSON object:
{{"decisions": n, "conventions": n, "correctness": n, "ux": n, "overall": n, "checklist_hits": n_of_{n_items},
  "biggest_issue": "one sentence",
  "approve": true/false,      // would a careful senior reviewer merge this as is? (nits allowed, real gaps not)
  "issues": ["..."],          // if not approved: the concrete issues you would send back, most important first, max 5
  "review_minutes": n,        // minutes a senior human needs to read this change, find these issues and write them up
  "finish_minutes": n}}       // minutes for a senior human to fix the remaining issues themselves (0 if approved)"""

# the original prompt ends with its own "Reply with ONLY a JSON object: {...}" line; replace it
BASE = RD.JUDGE_PROMPT[:RD.JUDGE_PROMPT.index("Reply with ONLY a JSON object")].rstrip()
RD.JUDGE_PROMPT = BASE + REVIEW_SUFFIX

FOLLOWUP = """Code review on your change: not approved yet. Please address these issues, keep what is already
right, typecheck with `npx tsc --noEmit`, and reply with a short summary of what you changed.

{issues}"""


def session_id(work: Path) -> str | None:
    """The agent's own session (not consultant/board sub-sessions, which run in the same cwd)."""
    proj = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(work))
    marker = "reply with a short summary of what you decided and why"
    for f in sorted(proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
        with f.open(encoding="utf-8", errors="replace") as fh:
            head = "".join(next(fh, "") for _ in range(30))
        if marker in head:
            return f.stem
    return None


def consult_cost(work: Path) -> float:
    log = work / ".consult" / "log.jsonl"
    if not log.exists():
        return 0.0
    return sum(json.loads(l).get("cost_usd") or 0 for l in log.read_text(encoding="utf-8").splitlines() if l.strip())


def snapshot_diff(work: Path, name: str, diff_dir: Path) -> Path:
    RD.sh(["git", "add", "-A"], cwd=work)
    diff = RD.sh(["git", "diff", "--cached", "HEAD", "--", ".", ":(exclude)package-lock.json"], cwd=work).stdout
    p = diff_dir / name
    p.write_text(diff, encoding="utf-8")
    return p


def rework(rec: dict, repo: Path, rounds: int, diff_dir: Path) -> dict:
    work = Path(rec["dir"])
    root = work.parent
    cfg = RD.CONDITIONS[rec["cond"]]
    sid = session_id(work)
    out = {k: rec[k] for k in ("task", "cond", "trial", "model", "dir")}
    out.update(first_overall=rec.get("overall"), session=sid, rounds=[], error=None)
    model_cost = rec["agent_cost"] + rec["consult_cost"]
    consult_seen = consult_cost(work)
    diff_file = Path(rec["diff_file"])
    tsc_text = rec["tsc"]
    for rnd in range(rounds + 1):
        j = RD.judge(dict(rec, diff_file=str(diff_file), tsc=tsc_text), root, repo)
        out["rounds"].append({"round": rnd, "overall": j.get("overall"), "approve": j.get("approve"),
                              "issues": j.get("issues", []), "review_minutes": j.get("review_minutes"),
                              "finish_minutes": j.get("finish_minutes"), "judge_error": j.get("judge_error"),
                              "judge_cost": j.get("judge_cost", 0),
                              "model_cost_so_far": round(model_cost, 4)})
        if "overall" not in j:
            out["error"] = f"judge failed in round {rnd}"
            break
        if j.get("approve") or rnd == rounds:
            break
        if not sid:
            out["error"] = "agent session not found; cannot resume"
            break
        issues = "\n".join(f"- {i}" for i in (j.get("issues") or [j.get("biggest_issue", "")]))
        env = RD.agent_env()
        env.update(CONSULT_LOG=str(work / ".consult" / "log.jsonl"), CONSULT_MODEL=cfg.get("consult", "opus"))
        cmd = [RD.CLAUDE, "-p", FOLLOWUP.format(issues=issues), "--resume", sid, "--model", cfg["model"],
               "--output-format", "json", "--permission-mode", "acceptEdits", "--allowedTools", *RD.AGENT_TOOLS,
               "--setting-sources", "project", "--max-budget-usd", "8"]
        try:
            r = RD.sh(cmd, cwd=work, timeout=2400, env=env)
            res = json.loads(r.stdout)
        except Exception as e:  # noqa: BLE001
            out["error"] = f"agent resume failed in round {rnd + 1}: {e!r}"[:300]
            break
        if res.get("is_error") or not res.get("total_cost_usd"):
            out["error"] = f"agent resume invalid in round {rnd + 1}: {str(res.get('result'))[-200:]}"
            break
        sid = res.get("session_id") or sid
        now = consult_cost(work)
        model_cost += res["total_cost_usd"] + (now - consult_seen)
        consult_seen = now
        ok, tsc_text = RD.tsc(work)
        diff_file = snapshot_diff(work, f"{work.name}.r{rnd + 1}.diff", diff_dir)
    last = out["rounds"][-1]
    out["model_cost"] = round(model_cost, 4)
    out["approved"] = bool(last.get("approve"))
    out["followups"] = len(out["rounds"]) - 1
    # human time: reviewing every version they were shown, plus finishing it themselves if never approved
    out["review_minutes"] = sum(x.get("review_minutes") or 0 for x in out["rounds"])
    out["finish_minutes"] = 0 if out["approved"] else (last.get("finish_minutes") or 0)
    out["human_minutes"] = out["review_minutes"] + out["finish_minutes"]
    out["final_overall"] = last.get("overall")
    return out


def report(rows: list[dict], rate: float) -> str:
    ok = [r for r in rows if not r.get("error")]
    bad = [r for r in rows if r.get("error")]
    conds = [c for c in RD.CONDITIONS if any(r["cond"] == c for r in ok)]

    def m(rs, f):
        v = [f(r) for r in rs]
        v = [x for x in v if isinstance(x, (int, float))]
        return statistics.mean(v) if v else float("nan")

    def total(r):
        return r["model_cost"] + r["human_minutes"] * rate / 60

    L = [f"## Cost to shippable (human time at ${rate:.0f}/h)", "",
         "| condition | runs | first score | final score | approved | follow-ups | model $ | human min | **total $** |",
         "|---|---|---|---|---|---|---|---|---|"]
    for c in conds:
        rs = [r for r in ok if r["cond"] == c]
        L.append(f"| {c} | {len(rs)} | {m(rs, lambda r: r['first_overall']):.1f} | {m(rs, lambda r: r['final_overall']):.1f} | "
                 f"{sum(r['approved'] for r in rs)}/{len(rs)} | {m(rs, lambda r: r['followups']):.1f} | "
                 f"{m(rs, lambda r: r['model_cost']):.2f} | {m(rs, lambda r: r['human_minutes']):.0f} | "
                 f"**{m(rs, total):.2f}** |")
    L += ["", "Human minutes = reviewing every version + finishing it yourself if the agent never got it approved.",
          "", "## Total $ per task", "", "| task | " + " | ".join(conds) + " |", "|---|" + "---|" * len(conds)]
    for t in RD.TASKS:
        cells = []
        for c in conds:
            rs = [r for r in ok if r["task"] == t and r["cond"] == c]
            cells.append(" / ".join(f"{total(r):.0f}{'' if r['approved'] else '*'}" for r in rs) or "-")
        L.append(f"| {t} | " + " | ".join(cells) + " |")
    L += ["", "`*` = never approved; includes the human's minutes to finish it."]
    for rt in (30, 60, 120):
        best = sorted(conds, key=lambda c: m([r for r in ok if r["cond"] == c],
                                             lambda r: r["model_cost"] + r["human_minutes"] * rt / 60))
        L.append(f"- at ${rt}/h, cheapest overall: **{best[0]}**" if best else "")
    if bad:
        L += ["", f"Excluded {len(bad)} runs: " + "; ".join(f"{r['task']}/{r['cond']}#{r['trial']}: {r['error']}" for r in bad)]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?")
    ap.add_argument("--repo", help="the repo the runs were made on (required unless --report-only)")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--rate", type=float, default=60.0)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", default=None, help="comma list of task/cond to run, e.g. cancel-order/baseline")
    ap.add_argument("--report-only", default=None)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if a.report_only:
        rows = [json.loads(l) for l in Path(a.report_only).read_text(encoding="utf-8").splitlines() if l.strip()]
        print(report(rows, a.rate))
        return
    src = Path(a.results)
    recs = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    recs = [r for r in recs if not r.get("invalid") and "overall" in r and Path(r["dir"]).exists()]
    if a.only:
        want = set(a.only.split(","))
        recs = [r for r in recs if f"{r['task']}/{r['cond']}" in want]
    out = src.with_name(src.stem + ".rework.jsonl")
    diff_dir = src.parent / "diffs"
    diff_dir.mkdir(exist_ok=True)
    print(f"{len(recs)} runs -> {out}", flush=True)
    rows = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        futs = {ex.submit(rework, r, Path(a.repo).expanduser().resolve(), a.rounds, diff_dir): r for r in recs}
        for f in cf.as_completed(futs):
            try:
                r = f.result()
            except Exception as e:  # noqa: BLE001
                src_rec = futs[f]
                r = {k: src_rec[k] for k in ("task", "cond", "trial")}
                r["error"] = f"crashed: {e!r}"[:300]
            rows.append(r)
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(r) + "\n")
            print(f"[{len(rows)}/{len(recs)}] {r['task']:9} {r['cond']:18} approved={r.get('approved')} "
                  f"follow-ups={r.get('followups')} model=${r.get('model_cost', 0):.2f} human={r.get('human_minutes')}min "
                  f"err={r.get('error')}", flush=True)
    rep = report(rows, a.rate)
    out.with_suffix(".md").write_text(rep, encoding="utf-8")
    print("\n" + rep)


if __name__ == "__main__":
    main()
