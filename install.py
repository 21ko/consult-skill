# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Install the `consult` skill for Claude Code and/or Codex.

  uv run install.py                 # user-level, both Claude Code and Codex (or: python install.py)
  uv run install.py --target claude # only Claude Code (~/.claude/skills)
  uv run install.py --target codex  # only Codex (~/.codex/skills and ~/.agents/skills)
  uv run install.py --project DIR   # install into a repo instead (DIR/.claude/skills, DIR/.agents/skills)
  uv run install.py --uninstall

Without cloning: `uvx --from git+https://github.com/21ko/consult-skill consult-install` (same flags).
"""
import argparse
import shutil
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# From a clone: <repo>/skills/consult. From the package (uvx / uv tool install): consult_skill/skill.
SRC = next((p for p in (_HERE / "skills" / "consult", _HERE / "skill") if (p / "SKILL.md").exists()),
           _HERE / "skills" / "consult")


def targets(kind, project):
    base = Path(project).resolve() if project else Path.home()
    claude = [base / ".claude" / "skills"]
    codex = [base / ".agents" / "skills"] + ([] if project else [base / ".codex" / "skills"])
    return {"claude": claude, "codex": codex, "all": claude + codex}[kind]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["all", "claude", "codex"], default="all")
    ap.add_argument("--project")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()
    for d in targets(a.target, a.project):
        dest = d / "consult"
        if dest.exists():
            shutil.rmtree(dest)
        if a.uninstall:
            print(f"removed {dest}")
            continue
        shutil.copytree(SRC, dest, ignore=shutil.ignore_patterns("__pycache__"))
        print(f"installed {dest}")


if __name__ == "__main__":
    main()
