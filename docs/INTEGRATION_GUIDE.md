# Integration Guide

One architecture baseline on `main`, five feature branches, one integration owner (the
architect). `main` is protected: no direct commits, no force-push, merge by PR only.

## Pull request flow
1. Member implements their assigned module (owned paths only).
2. Member runs module tests and `ruff check`.
3. Member commits with Conventional Commits.
4. Member pushes their feature branch.
5. Member opens a PR to `main` with the completion report in the description.
6. CI runs (lint + tests; later frontend and Docker build).
7. Team lead reviews the diff: ownership, contracts, safety rules, tests.
8. Team lead merges after approval (**squash merge** by default; merge commit for large multi-step PRs if history matters).
9. Other feature branches update from the latest `main` when they depend on the merged work or before their own PR.
10. Integration tests (`python -m pytest tests -q`) run on `main` after every merge.

Open PRs early and keep them small; several PRs per member are expected.

## Merge order
| # | Stream | Why this order |
|---|---|---|
| 1 | Backend foundation (health, customers, fakes, persistence) | Everyone integrates against it |
| 2 | Policy engine | Backend swaps in the real `PolicyEngine` |
| 3 | AI engine | Needs policy-built `VerifiedFacts` for real runs |
| 4 | Frontend (Streamlit first, then React) | Needs the real API |
| 5 | DevOps / QA (integration, e2e, Docker, CI) | Needs stable entry points |
| 6 | Final acceptance on `main` | All scenarios, blocked case, evaluation, Docker |

Member 5's data/fixtures PR is the exception: merge it as early as possible.

## Updating your branch from main
```bash
git fetch origin
git merge origin/main          # no rebase, no force-push on shared branches
python -m pytest -q            # rerun tests after every merge from main
git push
```

## Conflict procedure
Exclusive ownership and frozen contracts reduce conflicts; they do not guarantee zero.
1. Stop. Do not continue integrating other branches.
2. `git status` and `git diff` to see every conflicted file.
3. Inspect both sides and understand the intent of each change.
4. Resolve manually, preserving both intended behaviours. Never blindly use `git checkout --ours/--theirs` or `-X ours/theirs`.
5. Rerun the affected module tests and the integration tests.
6. Record the resolution (files, choice, reason) in the PR description.
7. If the conflict touches `contracts/` or another member's files, involve the owner and the architect.

## Integration checklist (per PR)
- [ ] Only the author's owned paths changed (`git diff --name-only origin/main...HEAD`).
- [ ] No contract drift: no duplicate models; `contracts/` untouched unless approved.
- [ ] Module tests and integration tests pass; CI green.
- [ ] No real LLM call in tests.
- [ ] No `.env`, keys, email addresses or real personal data.
- [ ] Safety rules hold: facts decided in code, drafts validated, approval required, mock delivery only.
- [ ] Completion report present with real test results and known limitations.
- [ ] README/docs updated if commands or behaviour changed.

## Contract-change process
1. Open an issue with the "Contract or ownership change" template: what, why, who is affected.
2. Architect approves or rejects.
3. Architect (or the requester, with approval) opens a PR that updates `contracts/`, `docs/API_CONTRACTS.md` and `docs/DATA_DICTIONARY.md` together.
4. After merge, every member merges `origin/main` and reruns tests.

## Final acceptance (on main)
All six PS scenarios plus the blocked case demonstrated, `python -m pytest -q` green,
evaluation script run with N stated, `docker compose up --build` works, README matches
reality. The architect approves the release.
