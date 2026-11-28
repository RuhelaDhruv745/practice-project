---
name: feature-development
description: Plan and implement one assigned feature inside your owned paths, with tests, ending in a commit, push and completion report. Use when starting any feature from your member spec.
---

# Feature development

1. Confirm your role: `git branch --show-current` and your `docs/members/MEMBER_<N>_*.md`. List your owned paths from `docs/TEAM_ASSIGNMENTS.md`.
2. Read `CLAUDE.md`, your member spec, `docs/API_CONTRACTS.md`, `docs/DATA_DICTIONARY.md` and the `contracts/` models you will use. Inspect only the relevant code.
3. Write a short plan: goal, files to create or change (owned paths only), contracts used, tests, risks. If any file is outside your paths, stop and draft a "Contract or ownership change" issue instead.
4. Implement in small steps using the `test-driven-development` skill. Use fakes for other members' modules.
5. Run your module tests and `python -m ruff check .`; fix failures. Never weaken tests to pass.
6. Review: `git diff --name-only main...HEAD` must list only owned paths. Use the `code-review` skill, and `security-audit` if you touched data, prompts, audit or delivery.
7. Commit with Conventional Commits and module scope, e.g. `feat(policy): add reminder stage selection`. Push your branch only.
8. Write the completion report: files created, files modified, features completed, tests passed, tests failed, known limitations, integration dependencies, commit hash.
