# Team isolation rules

- Ownership is defined in `docs/TEAM_ASSIGNMENTS.md`. If a path is not yours, do not edit it.
- Member 1: `backend/`. Member 2: `ai_engine/`. Member 3: `policy_engine/`, `data/policies/`, `data/campaigns/`. Member 4: `frontend/`, `reviewer_ui/`. Member 5: `data/synthetic/`, `data/fixtures/`, root `tests/`, `infrastructure/`, `scripts/`, `.github/workflows/`, `docker-compose.yml`, `.dockerignore`.
- Architect: `contracts/`, `docs/` (except Member 5's docs), `.claude/`, root config files, `CLAUDE.md`, `README.md`.
- Before any edit, confirm your role from your branch name and `docs/members/MEMBER_<N>_*.md`.
- Need a change elsewhere? Open an issue explaining what and why, and wait for approval. Do not edit first and ask later.
- Develop against fakes and mocks of other modules (`contracts/interfaces.py`, API examples) instead of waiting or editing their code.
- Shared files (`pyproject.toml`, root `requirements.txt`, `.env.example`) change only through the architect.
- Report incomplete work honestly in your completion report.
