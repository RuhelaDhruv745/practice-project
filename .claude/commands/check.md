---
description: Run pytest and ruff check, then report only failures and fixes
---
Run both, even if the first fails:

1. `.venv/Scripts/python.exe -m pytest -q`
2. `.venv/Scripts/python.exe -m ruff check .`

Report only failures. For each, give file:line, the cause and the suggested fix.
If both pass, say so in one line. Do not edit files.

- pytest exit code 5 means no tests were collected. Report "no tests yet", not a failure
  and not a pass.
- If `.venv` or a tool is missing, say which. Do not install anything.
