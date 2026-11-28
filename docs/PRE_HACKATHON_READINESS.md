# Pre-Hackathon Readiness

Snapshot: 2026-11-28, architect session on the lead's Windows machine. Re-check items
marked ⚠ on every member's laptop.

## 1. Environment (lead machine, measured)

| Tool | Status | Action if missing |
|---|---|---|
| Windows 11, PowerShell 5.1 + Git Bash | ✅ | |
| Git 2.46.2 | ✅ ⚠ folder owned by Administrators: git needs `-c safe.directory=...` | `git config --global --add safe.directory C:/Users/ASUS/practice-project` |
| GitHub CLI 2.106.0, authenticated | ✅ | `gh auth login` |
| Python 3.13.1 (`py -3.13`); default `python` is 3.12 | ✅ ⚠ | `winget install -e --id Python.Python.3.13` |
| Node 22.9.0, npm 11.3.0 | ✅ | `winget install -e --id OpenJS.NodeJS.LTS` |
| Docker 28.1.1, Compose 2.35.1 | ✅ installed; ⚠ engine not verified running | Start Docker Desktop, run `docker info` |
| Claude Code 2.1.332 | ✅ | |
| Azure CLI | ❌ not installed | `winget install -e --id Microsoft.AzureCLI` |
| make | ❌ not installed (optional) | `winget install -e --id ezwinports.make` or use `docs/DEVELOPMENT_GUIDE.md` commands |
| `.venv` with all module requirements | ✅ installed and resolving | |

## 2. Requirements coverage
FR-01 to FR-10 extracted with acceptance criteria, owners and playbook FR mapping in
`docs/REQUIREMENTS.md`. Open PS question resolved by user default (reminders do not
require marketing consent). Remaining open questions are listed there.

## 3. Architecture
Done: `ARCHITECTURE.md`, `TECH_STACK.md`, `DATABASE_DESIGN.md`, `SECURITY.md`,
`TESTING_STRATEGY.md`, `DEPLOYMENT.md`. Decisions: Streamlit + React over FastAPI,
Claude default with Groq and mock fallback, SQLite (PostgreSQL-compatible).

## 4. Assignments
`docs/TEAM_ASSIGNMENTS.md` (ownership matrix, dependency graph) and five member specs
in `docs/members/`, each with a startup prompt and completion-report template.
⚠ Fill in member names.

## 5. Worktrees
✅ Created on 2026-11-28 with `git worktree add`, all five branches pushed to GitHub.
Verified with `git worktree list`: every branch starts at the architecture commit
`8092b50`, which is an ancestor of `main` (merged in PR #3 as `0615267`).

| Member | Branch | Worktree (lead machine) |
|---|---|---|
| 1 Backend | `feature/backend` | `C:/Users/ASUS/team-backend` |
| 2 AI/LLM | `feature/ai-engine` | `C:/Users/ASUS/team-ai` |
| 3 Policy | `feature/policy-engine` | `C:/Users/ASUS/team-policy` |
| 4 Frontend | `feature/frontend` | `C:/Users/ASUS/team-frontend` |
| 5 DevOps/QA | `feature/devops-testing` | `C:/Users/ASUS/team-devops` |

Worktrees are local to the lead machine only. On separate laptops, each member clones
the repository and switches to their remote branch (section 13).

## 6. Git
✅ Baseline merged to `main` via PR #3 (merge commit `0615267`, CI green). Step 1a
(policy YAML and loader) is folded into the baseline; the retired
`feature/loyalty-assistant` branch was deleted after its merge.
⚠ Main branch protection (require PR + CI, no force-push) must be set by the repository
owner on GitHub: Settings → Rules → Rulesets.

## 7. Contracts
Code: `contracts/models.py`, `contracts/enums.py`, `contracts/api.py`,
`contracts/interfaces.py` (37 tests at baseline). Prose: `API_CONTRACTS.md`,
`DATA_DICTIONARY.md`. Frozen at version 1.0; changes via contract-change issue.

## 8. Test infrastructure
pytest configured for every module (`pyproject.toml`, importlib mode). Baseline: 37
tests pass, ruff clean. CI: `.github/workflows/ci.yml` (Python lint + tests; frontend
steps activate when `frontend/package.json` exists). No test calls a real LLM.
Vitest, React Testing Library and Playwright arrive with Member 4 and Member 5.

## 9. Docker
Strategy only (`docs/DEPLOYMENT.md`), `.dockerignore` in place. Dockerfiles and
`docker-compose.yml` wait for real entry points (Member 5).

## 10. Azure
Plan only: Container Apps preferred, App Service alternative. Nothing deployed, no
resources created. ⚠ Subscription, permissions and cost check still to do.

## 11. Missing credentials
| Credential | Needed for | Where it goes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Live drafting (default provider) | each member's local `.env` |
| `GROQ_API_KEY` | Fallback provider | `.env` |
| Azure subscription + OIDC federated credential | Deployment | GitHub environment secrets, later |
Without keys, `LLM_PROVIDER=mock` keeps everything runnable and demoable.

## 12. Remaining manual steps
1. ~~Review and merge the baseline PR.~~ Done (PR #3).
2. Protect `main` on GitHub; invite all five collaborators.
3. Fill member names in `docs/members/*.md`.
4. Each member: clone or open their worktree, create `.venv`, create `.env` from the example.
5. Install Azure CLI if the team will deploy; start Docker Desktop.
6. Rehearsal: one tiny PR per member, merged in order (playbook section 20).

## 13. Start commands for each member

Same machine (worktrees):

```powershell
cd ..\team-backend;  code .; claude   # Member 1
cd ..\team-ai;       code .; claude   # Member 2
cd ..\team-policy;   code .; claude   # Member 3
cd ..\team-frontend; code .; claude   # Member 4
cd ..\team-devops;   code .; claude   # Member 5
```

Separate laptops:

```powershell
git clone https://github.com/RuhelaDhruv745/practice-project.git
cd practice-project
git switch feature/<your-branch>      # backend | ai-engine | policy-engine | frontend | devops-testing
py -3.13 -m venv .venv; .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
claude
```

Then paste the **Startup prompt** from your `docs/members/MEMBER_<N>_*.md`.
Worktree folders also need their own `.venv` (it is git-ignored and not shared).
