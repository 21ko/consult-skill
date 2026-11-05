# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Grade a solution: python grade.py <task> <solution_file>  -> prints JSON {passed,total,failures}."""
import importlib.util
import json
import sys
from pathlib import Path

TASKS = Path(__file__).parent / "tasks"
MODULE = {"semver": "semver", "allocate": "money", "bizdays": "bizdays",
          "ttlcache": "ttlcache", "wrap": "wrap", "calc": "calc"}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    task, sol = sys.argv[1], sys.argv[2]
    hidden = load("hidden_" + task, TASKS / task / "hidden_test.py")
    try:
        mod = load(MODULE[task], sol)
    except Exception as e:
        print(json.dumps({"passed": 0, "total": len(hidden.tests(None)), "error": f"import failed: {e!r}"}))
        return
    results = hidden.tests(mod)
    fails = []
    for name, fn in results:
        try:
            ok = bool(fn())
        except Exception as e:
            ok = False
            name += f" [{type(e).__name__}: {e}]"
        if not ok:
            fails.append(name)
    print(json.dumps({"passed": len(results) - len(fails), "total": len(results), "failures": fails[:40]}))


if __name__ == "__main__":
    main()
