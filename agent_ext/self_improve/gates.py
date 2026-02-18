from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List

from .models import GatePlan, GateResults


def run_import_check() -> tuple[bool, str]:
    # Try importing the main packages as a sanity check.
    code = (
        "import agent_ext\n"
        "import agent_patterns\n"
        "print('imports_ok')\n"
    )
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    ok = p.returncode == 0 and "imports_ok" in (p.stdout or "")
    return ok, (p.stdout + "\n" + p.stderr).strip()


def run_compile_check() -> tuple[bool, str]:
    p = subprocess.run([sys.executable, "-m", "compileall", "-q", "agent_ext", "agent_patterns"],
                       capture_output=True, text=True)
    ok = p.returncode == 0
    return ok, (p.stdout + "\n" + p.stderr).strip()


def run_pytest(paths: List[str]) -> tuple[bool, str]:
    if not paths:
        return True, "pytest skipped (no paths)"
    p = subprocess.run([sys.executable, "-m", "pytest", *paths], capture_output=True, text=True)
    ok = p.returncode == 0
    return ok, (p.stdout + "\n" + p.stderr).strip()


def run_gates(plan: GatePlan) -> GateResults:
    details = {}
    ok = True

    if plan.import_check:
        iok, out = run_import_check()
        details["import_check"] = out
        ok = ok and iok

    if plan.compile_check:
        cok, out = run_compile_check()
        details["compile_check"] = out
        ok = ok and cok

    if plan.pytest_paths:
        pok, out = run_pytest(plan.pytest_paths)
        details["pytest"] = out
        ok = ok and pok

    return GateResults(ok=ok, details=details)
