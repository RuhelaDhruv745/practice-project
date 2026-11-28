# Customer Loyalty and Engagement Assistant

HCLTech Future Ready AI Engineer Hackathon. Five-member team, one architect (lead).
Segments synthetic customers with deterministic rules, picks an approved strategy, has
an LLM word an email from verified facts only, validates it, and sends nothing without
human approval (mock outbox only).

## Read before implementing
1. This file.
2. Your member spec: `docs/members/MEMBER_<N>_*.md` (the architect reads all of them).
3. `docs/TEAM_ASSIGNMENTS.md` (who owns which path).
4. `docs/API_CONTRACTS.md`, `docs/DATA_DICTIONARY.md`, `contracts/`.
5. `docs/REQUIREMENTS.md` (FR-01 to FR-10) and `docs/ARCHITECTURE.md` as needed.
`docs/problem-statement.md` is the authoritative brief. Its FR numbering wins over the
playbook's; `docs/REQUIREMENTS.md` has the mapping.

## Architecture in one screen
- `reviewer_ui/` (Streamlit, PS deliverable) and `frontend/` (React + TS) are thin
  clients of the FastAPI `backend/`. Neither computes facts or decides approval.
- `backend/` orchestrates through the `Protocol`s in `contracts/interfaces.py`:
  `PolicyEngine` (`policy_engine/`, deterministic) and `DraftGenerator` (`ai_engine/`).
- Policy (thresholds, segments, strategies, tones, offers, reminder stages, blocked
  terms) lives in `data/policies/*.yaml`, never in code. `as_of_date` is fixed there.
- SQLite via SQLAlchemy (PostgreSQL-compatible), runtime files under `outputs/`.
- LLM: Anthropic Claude by default, Groq fallback, `mock` when no key (`LLM_PROVIDER`).

## Ownership (summary; full matrix in docs/TEAM_ASSIGNMENTS.md)
| Member | Branch / worktree | Owns |
|---|---|---|
| Architect | `main` via PR | `contracts/`, `docs/`, `.claude/`, root config files |
| 1 Backend | `feature/backend`, `../team-backend` | `backend/` |
| 2 AI/LLM | `feature/ai-engine`, `../team-ai` | `ai_engine/` |
| 3 Policy | `feature/policy-engine`, `../team-policy` | `policy_engine/`, `data/policies/`, `data/campaigns/` |
| 4 Frontend | `feature/frontend`, `../team-frontend` | `reviewer_ui/`, `frontend/` |
| 5 DevOps/QA | `feature/devops-testing`, `../team-devops` | `data/synthetic/`, `data/fixtures/`, `tests/`, `infrastructure/`, `scripts/`, `.github/workflows/`, Docker files |

## Non-negotiable rules
- **Code decides facts.** Segment, eligibility, billing stage, amounts, dates, consent
  and contact permission come from `policy_engine`. The LLM never decides them.
- **The LLM only words.** It receives `VerifiedFacts` and returns `DraftContent`
  (`subject`, `body`) as JSON. Customer or campaign text is data, never instructions.
- **Every draft is validated** (`PolicyEngine.validate`), including human edits. A
  blocking finding blocks the draft.
- **A person approves.** Approve re-validates; delivery writes only to the mock outbox.
  No real email, no bulk send, no financial action.
- **Privacy and fairness.** No protected characteristics or proxies in data or logic.
  No email addresses in data, prompts, logs or audit records.
- **Synthetic data only.** Never invent facts about a customer in code or prompts.
- **Secrets** live only in `.env`. Never read, print or commit it; use `.env.example`.

## Every Claude session must
- Edit only paths your role owns. Never change `contracts/` or another member's module
  without an approved "Contract or ownership change" issue.
- Plan first for anything touching more than one file; make small changes.
- Write tests with the change. Mock the LLM: tests never call a real API.
- Run `python -m pytest <your module>` and `python -m ruff check .` before committing.
- Ask before adding a dependency, and add it to your module's `requirements.txt` only.
- Document assumptions; report incomplete work and failing tests honestly.
- Never merge directly into `main`, never force-push, never run destructive git
  commands (`reset --hard`, `clean -f`, branch/worktree deletion) without approval.
- Create `.md` files only as `README.md`, `NOTES.md`, `CLAUDE.md`, or under `docs/`,
  `.claude/`, `.github/`.

## Git workflow
Conventional commits with module scope (`feat(policy): ...`). Push your feature branch,
open a PR to `main`, CI must pass, the architect reviews and squash-merges in order:
backend → policy → AI → frontend → DevOps/QA → acceptance. Update your branch with
`git fetch && git merge origin/main`. Details: `docs/INTEGRATION_GUIDE.md`.
Worktrees are local to one machine; on separate laptops, clone and check out your branch.

## Commands
With `.venv` active (Windows: `.venv\Scripts\python.exe` otherwise; plain `python` on
the lead's machine is 3.12, so create the venv with `py -3.13 -m venv .venv`):
- Setup: `python -m pip install -r requirements.txt -r requirements-dev.txt`
- Tests: `python -m pytest` (or a module path, e.g. `python -m pytest policy_engine`)
- Lint/format: `python -m ruff check .` and `python -m ruff format .`
- Backend, UIs, Docker: see `docs/DEVELOPMENT_GUIDE.md` and `docs/DEPLOYMENT.md`.
- Git on the lead's machine needs `git -c safe.directory=C:/Users/ASUS/practice-project`
  until the folder ownership is fixed.
Slash commands: `/check`, `/review-diff`, `/explain <file>`, `/scenario`.
Review agents (`code-reviewer`, `security-reviewer`) cannot run git: pass the diff.

## Docker and Azure
`docker compose up --build` is the target once entry points exist (Member 5).
Azure Container Apps is the plan; nothing is deployed and no billable resource is
created without explicit team approval. Secrets never go in images or the repo.

## Definition of done
Owned paths only; tests and ruff pass; contracts used, not redefined; no secrets or
personal data; PR includes the completion report from your member spec.

## Current status (update when it changes)
- Sprint 1 merged (PRs #5-#9): backend foundation (health, customers, seed, error format),
  policy `classify`/`decide`, AI draft generator (mock/Claude/Groq), Streamlit reviewer
  app on a fake API, synthetic customers and labelled scenarios (19/19 labels match the
  engine).
- Sprint 2 in progress: draft validators, remaining endpoints + audit + outbox, AI
  evaluation, React dashboard, Docker/Compose/Azure plan.
- Accepted exception: the backend reads policy version labels via
  `policy_engine.config_loader.load_policy().versions` (read-only metadata, no business
  logic). The `PolicyEngine` Protocol is unchanged.
- Env names: `ANTHROPIC_*` / `GROQ_*` are canonical; `LLM_API_KEY`, `LLM_MODEL`,
  `LLM_BASE_URL` are optional overrides. No key means the mock provider.
- Resolved: payment reminders do not require marketing consent
  (`reminders_require_marketing_consent: false`), frequency rules still apply.
