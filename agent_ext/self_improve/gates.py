from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List

from .models import GatePlan, GateResults


def run_import_check(*, cwd: Path | None = None) -> tuple[bool, str]:
    # Try importing the main packages as a sanity check.
    code = (
        "import agent_ext\n"
        "import agent_patterns\n"
        "print('imports_ok')\n"
    )
    kw = {"capture_output": True, "text": True}
    if cwd is not None:
        kw["cwd"] = str(cwd)
    p = subprocess.run([sys.executable, "-c", code], **kw)
    ok = p.returncode == 0 and "imports_ok" in (p.stdout or "")
    return ok, (p.stdout + "\n" + p.stderr).strip()


def run_compile_check(*, cwd: Path | None = None) -> tuple[bool, str]:
    # Compile agent_ext and repo root (agent_patterns package lives at root, no agent_patterns/ dir)
    kw = {"capture_output": True, "text": True}
    if cwd is not None:
        kw["cwd"] = str(cwd)
    p = subprocess.run([sys.executable, "-m", "compileall", "-q", "."], **kw)
    ok = p.returncode == 0
    return ok, (p.stdout + "\n" + p.stderr).strip()


def run_pytest(paths: List[str], *, cwd: Path | None = None) -> tuple[bool, str]:
    if not paths:
        return True, "pytest skipped (no paths)"
    kw = {"capture_output": True, "text": True}
    if cwd is not None:
        kw["cwd"] = str(cwd)
    p = subprocess.run([sys.executable, "-m", "pytest", *paths], **kw)
    ok = p.returncode == 0
    return ok, (p.stdout + "\n" + p.stderr).strip()


def run_gates(plan: GatePlan, *, repo_root: Path | None = None) -> GateResults:
    cwd = Path(repo_root) if repo_root is not None else None
    details = {}
    ok = True

    if plan.import_check:
        iok, out = run_import_check(cwd=cwd)
        details["import_check"] = out
        ok = ok and iok

    if plan.compile_check:
        cok, out = run_compile_check(cwd=cwd)
        details["compile_check"] = out
        ok = ok and cok

    if plan.pytest_paths:
        pok, out = run_pytest(plan.pytest_paths, cwd=cwd)
        details["pytest"] = out
        ok = ok and pok

    return GateResults(ok=ok, details=details)
