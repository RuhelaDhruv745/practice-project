# Member 1: Backend Engineer

Name: <fill in>

| | |
|---|---|
| Branch | `feature/backend` |
| Worktree | `../team-backend` |
| Owns | `backend/` (including `backend/requirements.txt`) |
| Must not modify | `contracts/`, `policy_engine/`, `ai_engine/`, `data/`, `frontend/`, `reviewer_ui/`, root `tests/`, `infrastructure/`, `scripts/`, `.github/`, `.claude/`, `docs/`, root config files (`pyproject.toml`, `requirements*.txt`, `.env.example`, `.gitignore`, `Makefile`, `docker-compose.yml`, `.dockerignore`) |
| Provides | HTTP API in `docs/API_CONTRACTS.md` |
| Consumes | `contracts.models`, `contracts.enums`, `contracts.interfaces` (`PolicyEngine`, `DraftGenerator`), `data/synthetic/customers.csv` |

## Responsibilities
You own the FastAPI service that orchestrates the pipeline, persists state, enforces
the review state machine and writes the mock outbox and audit log. You decide **no**
business facts: segments, eligibility, stages, amounts and dates come from
`PolicyEngine`; wording comes from `DraftGenerator`.

## Deliverables
- [ ] `backend/app/main.py` with an app factory `create_app(policy_engine, generator, settings)` so tests inject fakes. Module-level `app` for `uvicorn backend.app.main:app`.
- [ ] `backend/app/core/`: settings from environment (`DATABASE_URL`, default `sqlite:///outputs/app.db`), structured logging that never logs emails, keys or message bodies at INFO.
- [ ] `backend/app/database/` + `backend/app/models/`: SQLAlchemy 2.x models per `docs/DATABASE_DESIGN.md` (customers, review items with revisions, audit events, outbox). Postgres-compatible types only.
- [ ] `backend/app/repositories/`: one repository per aggregate. Customer repository assembles `CustomerProfile` with permitted fields only.
- [ ] Seed command `python -m backend.app.seed` loading `data/synthetic/customers.csv` (rejects unknown columns, idempotent).
- [ ] `backend/app/api/`: every endpoint in `docs/API_CONTRACTS.md` with the exact request/response schemas and status codes.
- [ ] `backend/app/middleware/`: error handlers producing `ErrorResponse` for every non-2xx, no stack traces.
- [ ] `backend/app/services/`: orchestration `decide → generate → validate → review item` via the Protocols only.
- [ ] Fakes in `backend/tests/fakes.py`: `FakePolicyEngine`, `FakeDraftGenerator` (until Members 2 and 3 merge).
- [ ] Review state machine exactly as in `API_CONTRACTS.md`. Edit re-validates. Approve **re-validates immediately before delivery** and refuses (`409`, audit `delivery_refused`) unless status is `pending_review`, latest validation passed and decision is `draft_allowed`.
- [ ] Mock outbox: `OutboxRecord` row plus JSONL export to `outputs/outbox.jsonl`. No SMTP, no network delivery anywhere.
- [ ] Audit: every pipeline step and reviewer action written as `AuditEvent` (with policy versions, prompt version, model). Append-only.
- [ ] `/api/health` reports `llm_mode` without revealing keys.
- [ ] OpenAPI at `/docs` matches the contract (Member 4 generates types from it).

## Working around dependencies
| Waiting for | Workaround |
|---|---|
| Member 3 `PolicyEngine` | `FakePolicyEngine` returning hand-built `PolicyDecision` / `ValidationResult` |
| Member 2 `DraftGenerator` | `FakeDraftGenerator` returning a fixed `GeneratedMessage`; one that raises `GenerationError` |
| Member 5 CSV | 3–4 inline rows in a test fixture CSV under `backend/tests/` |

When 2 and 3 merge, wire the real implementations in `main.py` only.

## Testing requirements
- `backend/tests/`: schema tests, API tests with FastAPI `TestClient` (or httpx), repository tests on a temp SQLite file, error-format tests.
- Must-have cases: blocked decision creates `blocked` item with no message; approve on blocked → 409; approve after failing edit → 409; approve when validation passes → outbox record + `delivered`; reject requires reason; audit events contain no `@` addresses; `generation_failed` → 502 and no item.
- Never call a real LLM. Run: `python -m pytest backend/tests -q` and `python -m ruff check backend`.

## Definition of done
Endpoints conform to `API_CONTRACTS.md`; all tests above pass; no secrets; `/docs` works; only `backend/` changed; dependencies documented in the PR.

## Commit examples
`feat(backend): add review approve endpoint with re-validation` ·
`test(backend): cover 409 on approving blocked item` · `fix(backend): exclude body from info logs`

## Integration
Merge first (backend foundation). Open the PR early with health, customers and fakes, then follow-up PRs. See `docs/INTEGRATION_GUIDE.md`.

## Startup prompt
```text
You are Member 1 (Backend) in a five-member team. Read, in order: CLAUDE.md,
docs/members/MEMBER_1_BACKEND.md, docs/ARCHITECTURE.md, docs/API_CONTRACTS.md,
docs/DATA_DICTIONARY.md, docs/TEAM_ASSIGNMENTS.md.
Check you are on branch feature/backend in worktree ../team-backend (git status,
git worktree list). Give me a short implementation plan first and wait for my OK.
Implement only paths under backend/. Use contracts/ models and Protocols; never
redefine them. Use fakes for PolicyEngine and DraftGenerator until they merge.
Write tests with each change, run python -m pytest backend/tests -q and
python -m ruff check backend, review the changed-file list
(git diff --name-only main...HEAD), commit with conventional commits, push only
feature/backend, and open a PR to main. Finish with the completion report from
my member file. Report failures honestly.
```

## Completion report
```text
Files created:
Files modified:
Features completed:
Tests passed: (command + count)
Tests failed: (command + names, or "none")
Known limitations:
Integration dependencies:
Commit hash(es):
```
