# Development Guide

## Prerequisites
| Tool | Version | Check |
|---|---|---|
| Python | 3.13 | `py -3.13 --version` (Windows) / `python3.13 --version` |
| Node.js | 22 LTS | `node --version` (frontend only) |
| Git, GitHub CLI | recent | `git --version`, `gh auth status` |
| Docker Desktop | with Compose v2 | `docker compose version` (later phases) |
| Claude Code | recent | `claude --version` |

## Python setup

**Windows (PowerShell)**
```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
```

**macOS / Linux**
```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Root `requirements.txt` only includes each module's `requirements.txt`. Add a package
to **your module's** file; never edit the root file (architect-owned).

## Secrets
Copy `.env.example` to `.env` and fill values locally. Never commit `.env`, never paste
keys in chat, PRs or logs. Without an API key the AI engine runs in mock mode.

## Git ownership warning (Windows)
If git reports "dubious ownership", the folder is owned by another account. Either run
`git config --global --add safe.directory <repo path>` once, or prefix commands with
`git -c safe.directory=<repo path>`.

## Tests and lint
| Scope | Command |
|---|---|
| Everything (Python) | `python -m pytest -q` |
| One module | `python -m pytest policy_engine/tests -q` (or `backend/tests`, `ai_engine/tests`, `contracts/tests`, `reviewer_ui/tests`, `tests`) |
| Lint / format | `python -m ruff check .` / `python -m ruff format .` |
| Frontend | in `frontend/`: `npm ci`, `npm run lint`, `npm run test`, `npm run build` |

Tests never call a real LLM API.

## Running the app (once the entry points exist)
| Component | Command | URL |
|---|---|---|
| Backend (Member 1) | `python -m uvicorn backend.app.main:app --reload` | http://localhost:8000/docs |
| Seed data | `python -m backend.app.seed` | |
| Streamlit reviewer (Member 4) | `python -m streamlit run reviewer_ui/app.py` | http://localhost:8501 |
| React dashboard (Member 4) | in `frontend/`: `npm run dev` | http://localhost:5173 |
| All containers (Member 5) | `docker compose up --build` | see `docs/DEPLOYMENT.md` |

`make` targets exist for macOS/Linux/CI; on Windows use the commands above (or install
make with `winget install ezwinports.make`).

## Worktrees (one shared machine)
Run from the main repository after the baseline is on `main`:
```bash
git worktree add ../team-backend  -b feature/backend        main
git worktree add ../team-ai       -b feature/ai-engine      main
git worktree add ../team-policy   -b feature/policy-engine  main
git worktree add ../team-frontend -b feature/frontend       main
git worktree add ../team-devops   -b feature/devops-testing main
git worktree list
```
Each worktree needs its own `.venv` (and `node_modules` for frontend) and its own `.env`.
Launch: `cd ../team-backend; code .; claude`.

## Five laptops (worktrees are local only)
Worktrees are not shared across machines. GitHub is the synchronisation point:
```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
git fetch origin
git switch feature/<your-branch>     # tracks origin/feature/<your-branch>
```
Then set up Python/Node as above and start Claude Code in that folder.

## Daily loop
1. `git fetch origin` and merge `origin/main` into your branch if it moved (see `INTEGRATION_GUIDE.md`).
2. Plan → small change → tests → `ruff` → commit (Conventional Commits) → push your branch.
3. Check `git diff --name-only main...HEAD` lists only your owned paths.
