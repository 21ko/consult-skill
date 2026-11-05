# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Aggregate every valid design-bench run into the tables used in the README.

  python summarize.py            # markdown to stdout
  python summarize.py --json     # machine-readable

Reads results/*.jsonl (app A) and results/app-b/*.jsonl (app B), skipping invalid runs and the
known-broken early batches (results/broken-usage-limit, results/pilot, and the 07:05 run whose
repo version differs from the public one).
"""
from __future__ import annotations

import glob
import json
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKIP = ("070544",)
NAMES = {
    "baseline": "Haiku alone",
    "skill_nudge_sonnet": "Haiku + 1:1 consult (Sonnet)",
    "board": "Haiku + board every task",
    "reflect": "Haiku + pre-mortem (v1, soft)",
    "ship": "Haiku + pre-mortem + board (v1)",
    "ship2": "**Haiku + consult skill (shipped)**",
    "sonnet": "Sonnet alone",
}
ORDER = ["baseline", "sonnet", "skill_nudge_sonnet", "board", "reflect", "ship", "ship2"]


def load(pattern: str) -> list[dict]:
    rows = []
    for f in sorted(glob.glob(str(HERE / pattern))):
        if "rework" in f or any(s in f for s in SKIP):
            continue
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            if not r.get("invalid") and isinstance(r.get("overall"), (int, float)):
                rows.append(r)
    return rows


def load_rework() -> list[dict]:
    rows = []
    for f in sorted(glob.glob(str(HERE / "results" / "*.rework.jsonl"))):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            if not r.get("error"):
                rows.append(r)
    return rows


def first_try(rows: list[dict]) -> dict:
    out = {}
    for c in ORDER:
        rs = [r for r in rows if r["cond"] == c]
        if rs:
            out[c] = {"n": len(rs), "score": st.mean(r["overall"] for r in rs),
                      "cost": st.mean(r["total_cost"] for r in rs),
                      "check_pass": sum(bool(r["tsc_pass"]) for r in rs),
                      "board_rate": sum("board" in r.get("consult_modes", []) for r in rs) / len(rs)}
    return out


def per_task(rows: list[dict]) -> dict:
    tasks = list(dict.fromkeys(r["task"] for r in rows))
    return {t: {c: [r["overall"] for r in rows if r["task"] == t and r["cond"] == c] for c in ORDER} for t in tasks}


def rework_table(rows: list[dict], rate: float = 60.0) -> dict:
    out = {}
    for c in ORDER:
        rs = [r for r in rows if r["cond"] == c]
        if rs:
            out[c] = {"n": len(rs), "approved": sum(r["approved"] for r in rs),
                      "followups": st.mean(r["followups"] for r in rs),
                      "human_min": st.mean(r["human_minutes"] for r in rs),
                      "model_cost": st.mean(r["model_cost"] for r in rs),
                      "total": st.mean(r["model_cost"] + r["human_minutes"] * rate / 60 for r in rs)}
    return out


def md() -> str:
    L = []
    for label, pattern in (("App A (Next.js + Postgres, 6 tasks)", "results/*.jsonl"),
                           ("App B (FastAPI + React, 3 tasks)", "results/app-b/*.jsonl")):
        rows = load(pattern)
        ft = first_try(rows)
        L += [f"### {label}", "", "| setup | runs | first-try score | model $/task | board used | checks pass |",
              "|---|---|---|---|---|---|"]
        for c, v in ft.items():
            L.append(f"| {NAMES[c]} | {v['n']} | {v['score']:.1f} | ${v['cost']:.2f} | {v['board_rate']:.0%} | {v['check_pass']}/{v['n']} |")
        pt = per_task(rows)
        cs = [c for c in ORDER if c in ft]
        L += ["", "| task | " + " | ".join(NAMES[c].replace("**", "") for c in cs) + " |", "|---|" + "---|" * len(cs)]
        for t, d in pt.items():
            L.append(f"| {t} | " + " | ".join("/".join(f"{x:g}" for x in d[c]) or "-" for c in cs) + " |")
        L.append("")
    rw = rework_table(load_rework())
    L += ["### Cost to shippable work, App A (human time at $60/h)", "",
          "| setup | runs | approved | follow-ups | your minutes | model $ | total $ |", "|---|---|---|---|---|---|---|"]
    for c, v in rw.items():
        L.append(f"| {NAMES[c]} | {v['n']} | {v['approved']}/{v['n']} | {v['followups']:.1f} | {v['human_min']:.0f} | "
                 f"${v['model_cost']:.2f} | ${v['total']:.0f} |")
    return "\n".join(L)


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps({"app_a": {"first_try": first_try(load("results/*.jsonl")), "per_task": per_task(load("results/*.jsonl"))},
                          "app_b": {"first_try": first_try(load("results/app-b/*.jsonl")),
                                        "per_task": per_task(load("results/app-b/*.jsonl"))},
                          "rework": rework_table(load_rework())}, indent=1))
    else:
        print(md())
