"""PostToolUse hook: format and lint the edited .py file, and report back."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_ruff(root):
    for candidate in (root / ".venv/Scripts/ruff.exe", root / ".venv/bin/ruff"):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("ruff")


def warn_missing_once(session_id):
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", session_id)
    try:
        (Path(tempfile.gettempdir()) / f"claude-ruff-missing-{safe_id}").touch(
            exist_ok=False
        )
    except FileExistsError:
        return
    message = "ruff not found, so Python files are not auto-formatted. See requirements-dev.txt."
    print(json.dumps({"systemMessage": message}))


def run(ruff, root, *args):
    return subprocess.run(
        [ruff, *args],
        cwd=root,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=12,
    )


def main():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    file_path = data["tool_input"].get("file_path", "")
    if not file_path.lower().endswith(".py"):
        return 0

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data["cwd"]).resolve()
    path = (Path(data.get("cwd") or root) / file_path).resolve()
    if not path.is_file() or not path.is_relative_to(root):
        return 0
    name = path.relative_to(root)
    if ".venv" in name.parts:
        return 0

    ruff = find_ruff(root)
    if not ruff:
        warn_missing_once(data.get("session_id", ""))
        return 0

    before = path.read_bytes()
    formatted = run(ruff, root, "format", "--force-exclude", str(path))
    checked = run(
        ruff, root, "check", "--force-exclude", "--output-format=concise", str(path)
    )

    notes = []
    if path.read_bytes() != before:
        notes.append(f"ruff format changed {name}. Read it again before the next edit.")
    for label, result in (("format", formatted), ("check", checked)):
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip()[:2000]
            notes.append(f"ruff {label} reported problems in {name}:\n{output}")

    if notes:
        reply = {"hookEventName": "PostToolUse", "additionalContext": "\n".join(notes)}
        print(json.dumps({"hookSpecificOutput": reply}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
