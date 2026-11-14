"""
tools.py — the agent's hands. Plain Python functions with a @tool label.

The LLM never touches the disk itself. It asks for a tool by name,
our code runs the function, and the returned string goes back to it.

    read_file  → see the code
    edit_file  → change it (exact old → new replace, never a full rewrite)
    run_file   → run it and see if the error is gone
"""

import shutil
import subprocess
import sys
from pathlib import Path

from langchain_core.tools import tool

# The agent may only touch files inside the folder you run it from (your project).
WORKDIR = Path.cwd().resolve()
MAX_OUTPUT = 3000  # characters; long tracebacks get cut so they don't flood the context
LIBRARY_DIRS = {".venv", "venv", "site-packages"}  # the bug is never "fix the library"


def _safe_path(path: str) -> Path:
    """Resolve a path (relative or absolute, as it appears in a trace) and refuse anything outside WORKDIR."""
    p = (WORKDIR / path).resolve()
    if not p.is_relative_to(WORKDIR):
        raise ValueError(f"{path} is outside the project folder {WORKDIR}")
    return p


@tool
def read_file(path: str) -> str:
    """Read a file and return its contents with line numbers."""
    try:
        lines = _safe_path(path).read_text().splitlines()
    except Exception as e:
        return f"ERROR: {e}"
    return "\n".join(f"{i:4} | {line}" for i, line in enumerate(lines, start=1))


@tool
def edit_file(path: str, old: str, new: str) -> str:
    """Replace the exact text `old` with `new` in a file.
    `old` must appear exactly once. Do not include line numbers in it."""
    try:
        p = _safe_path(path)
        code = p.read_text()
    except Exception as e:
        return f"ERROR: {e}"

    if LIBRARY_DIRS & set(p.parts):
        return "ERROR: that file is library code. Fix the project code that calls it instead."

    count = code.count(old)
    if count == 0:
        return "ERROR: `old` text not found. Read the file again and copy it exactly."
    if count > 1:
        return f"ERROR: `old` text appears {count} times. Include more surrounding lines so it is unique."

    backup = p.with_name(p.name + ".bak")
    if not backup.exists():  # keep the original from before the first edit
        shutil.copy(p, backup)

    p.write_text(code.replace(old, new, 1))
    return f"OK: edited {path} (original saved as {backup.name})"


@tool
def run_file(path: str) -> str:
    """Run a Python file and return its exit code, stdout and stderr."""
    try:
        p = _safe_path(path)
        result = subprocess.run(
            [sys.executable, str(p)],
            capture_output=True, text=True, timeout=10, cwd=WORKDIR,
        )
    except subprocess.TimeoutExpired:
        return "ERROR: timed out after 10 seconds"
    except Exception as e:
        return f"ERROR: {e}"

    out = f"exit code: {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return out[-MAX_OUTPUT:]


TOOLS = [read_file, edit_file, run_file]
TOOL_MAP = {t.name: t for t in TOOLS}
