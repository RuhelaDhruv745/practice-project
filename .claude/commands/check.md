---
description: Run pytest and ruff check, then report only failures and fixes
argument-hint: "[module path, e.g. policy_engine]"
---
Scope: $ARGUMENTS (if empty, the whole repo; pytest uses `testpaths` from `pyproject.toml`).

Run both, even if the first fails:

1. `.venv/Scripts/python.exe -m pytest -q $ARGUMENTS`
2. `.venv/Scripts/python.exe -m ruff check .`

If `frontend/package.json` exists and the scope is empty or `frontend`, also run
`npm --prefix frontend run lint` and `npm --prefix frontend test -- --run`.

Report only failures. For each, give file:line, the cause and the suggested fix.
If everything passes, say so in one line with the pass counts. Do not edit files.

- pytest exit code 5 means no tests were collected. Report "no tests yet", not a failure
  and not a pass.
- If `.venv`, `node_modules` or a tool is missing, say which. Do not install anything.
