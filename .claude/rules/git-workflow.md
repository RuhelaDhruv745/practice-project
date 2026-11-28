# Git workflow rules

- Never commit or push to `main` directly. Work on your assigned `feature/*` branch only.
- Never force-push, `reset --hard`, delete branches or worktrees, or rewrite pushed history without explicit approval.
- Commit small, logically complete changes with Conventional Commits and the module as scope, e.g. `feat(policy): add reminder stage selection`.
- Before committing: run tests and `ruff check`, and check `git diff --name-only main...HEAD` lists only your owned paths.
- Never commit `.env`, keys, `outputs/`, `.venv/` or real data.
- Push your branch and open a PR to `main` using the PR template; include the completion report.
- The architect reviews and merges in order: backend, policy, AI, frontend, DevOps/QA.
- After a merge to `main`, update your branch with `git merge origin/main` (not rebase of pushed work), rerun tests.
- On conflicts: stop, inspect both sides, preserve intended behaviour, rerun tests, record the resolution in the PR. Never blindly use `--ours`/`--theirs`.
- In this repo on Windows, git may need `-c safe.directory=<repo path>` if the folder owner differs.
