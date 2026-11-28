---
name: code-review
description: Review your branch's changes before a PR - ownership, contracts, project rules, tests and bugs - using the read-only code-reviewer agent. Use before every push that will go into a PR.
---

# Code review (project)

1. List changes: `git diff --name-only main...HEAD` and `git status --short`.
2. If any secrets file (`.env`, keys) appears, stop and report it as critical. Never open it.
3. Get the diff: `git diff main...HEAD`. Reviewer agents cannot run git, so pass this diff to them.
4. Ask the `code-reviewer` agent to review the diff, naming your member number and branch.
5. If the diff touches `data/`, `data/policies/`, `ai_engine/`, `policy_engine/compliance/`, audit or delivery code, also ask the `security-reviewer` agent.
6. Run the module tests and `python -m ruff check .`; note the actual results.
7. Fix critical and high findings, rerun tests, and list any accepted lower findings with reasons in the PR.
8. Output: findings table (`severity | file:line | finding | fix`), test results, and remaining risks.
