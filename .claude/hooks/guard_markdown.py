"""PreToolUse hook: block creating stray .md files inside the project.

Existing files and files outside the project (plans, memory) are not affected.
"""

import json
import os
import sys
from pathlib import Path

ROOT_FILES = {"readme.md", "notes.md", "claude.md"}
FOLDERS = {"docs", ".claude", ".github"}


def main():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    file_path = data["tool_input"].get("file_path", "").rstrip(". ")
    if not file_path.lower().endswith(".md"):
        return 0

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data["cwd"]).resolve()
    path = (Path(data.get("cwd") or root) / file_path).resolve()
    if path.exists() or not path.is_relative_to(root):
        return 0

    parts = [part.lower() for part in path.relative_to(root).parts]
    if (len(parts) == 1 and parts[0] in ROOT_FILES) or (
        len(parts) > 1 and parts[0] in FOLDERS
    ):
        return 0

    print(
        "Blocked: do not create new .md files here. Put notes in NOTES.md, or in "
        "docs/ for longer documents. Allowed: README.md, NOTES.md, CLAUDE.md, "
        "docs/, .claude/ and .github/.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
