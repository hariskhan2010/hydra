#!/usr/bin/env python3
"""hydra eval harness (A7 / B9).

For each case under eval/cases/<name>/:

    case.toml        { tasks = "tasks.toml", check = "python -m pytest -q" }
    repo/            seed files copied into a fresh git repo
    tasks.toml       the hydra task file

The harness makes a temp git repo from repo/, runs `hydra run` then
`hydra merge`, checks out the integration branch, runs `check`, and records
pass/fail. Results (raw) go to eval/results/<timestamp>.json.

No number is published anywhere unless it came out of this script. SWE-bench-
Verified integration is a documented stub (see README) — it needs Docker and the
dataset, which this dev box can't run.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
RESULTS = ROOT / "results"
HYDRA_PKG = ROOT.parent


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "eval", "GIT_AUTHOR_EMAIL": "e@e",
                        "GIT_COMMITTER_NAME": "eval", "GIT_COMMITTER_EMAIL": "e@e",
                        **_os_environ()})


def _os_environ():
    import os
    return dict(os.environ)


def _hydra(args, cwd):
    env = {**_os_environ(), "PYTHONPATH": str(HYDRA_PKG)}
    return subprocess.run([sys.executable, "-m", "hydra.cli", *args],
                          cwd=cwd, capture_output=True, text=True, env=env, timeout=1800)


def run_case(case_dir: Path) -> dict:
    spec = tomllib.loads((case_dir / "case.toml").read_text(encoding="utf-8"))
    name = case_dir.name
    t0 = time.time()
    with TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        shutil.copytree(case_dir / "repo", repo)
        shutil.copy(case_dir / spec.get("tasks", "tasks.toml"), repo / "tasks.toml")
        if (case_dir / "hydra.toml").exists():
            shutil.copy(case_dir / "hydra.toml", repo / "hydra.toml")
        _git(["init", "-q", "-b", "main"], repo)
        _git(["add", "-A"], repo)
        _git(["commit", "-q", "-m", "seed"], repo)

        r_run = _hydra(["run", "tasks.toml"], repo)
        r_merge = _hydra(["merge"], repo)
        merged_branch = None
        for ln in r_merge.stdout.splitlines():
            if ln.startswith("merged ") and "→ branch " in ln:
                merged_branch = ln.split("→ branch ", 1)[1].strip()
        if merged_branch:
            _git(["checkout", "-q", merged_branch], repo)

        check = spec["check"]
        r_check = subprocess.run(check, cwd=repo, shell=True, capture_output=True,
                                 text=True, env=_os_environ(), timeout=600)
        passed = r_check.returncode == 0
        return {
            "case": name,
            "passed": passed,
            "seconds": round(time.time() - t0, 1),
            "run_ok": r_run.returncode == 0,
            "merge_ok": r_merge.returncode == 0,
            "merged_branch": merged_branch,
            "check_output": (r_check.stdout + r_check.stderr)[-1500:],
        }


def main() -> int:
    names = sys.argv[1:]
    dirs = [CASES / n for n in names] if names else sorted(p for p in CASES.iterdir() if p.is_dir())
    if not dirs:
        print("no eval cases found under eval/cases/")
        return 1
    RESULTS.mkdir(exist_ok=True)
    out = []
    npass = 0
    for d in dirs:
        res = run_case(d)
        out.append(res)
        npass += res["passed"]
        mark = "PASS" if res["passed"] else "FAIL"
        print(f"[{mark}] {res['case']}  ({res['seconds']}s)")
        if not res["passed"]:
            print(f"       run_ok={res['run_ok']} merge_ok={res['merge_ok']}")
            for ln in res["check_output"].splitlines()[-8:]:
                print(f"       {ln}")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (RESULTS / f"{stamp}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n{npass}/{len(dirs)} passed → eval/results/{stamp}.json")
    return 0 if npass == len(dirs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
