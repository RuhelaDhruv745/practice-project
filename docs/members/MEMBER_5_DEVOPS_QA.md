# Member 5: DevOps / QA / Data Engineer

Name: <fill in>

| | |
|---|---|
| Branch | `feature/devops-testing` |
| Worktree | `../team-devops` |
| Owns | `data/synthetic/`, `data/fixtures/`, root `tests/` (integration, e2e, evaluation), `infrastructure/`, `scripts/`, `docker-compose.yml`, `.dockerignore`, `.github/workflows/`, `docs/TESTING_STRATEGY.md`, `docs/DEPLOYMENT.md`, `docs/DEMO_SCRIPT.md`, `docs/EVALUATION_REPORT.md` |
| Must not modify | `contracts/`, `backend/`, `ai_engine/`, `policy_engine/`, `data/policies/`, `data/campaigns/`, `frontend/`, `reviewer_ui/`, `.claude/`, other `docs/`, root config files (`pyproject.toml`, `requirements*.txt`, `.env.example`, `.gitignore`, `Makefile`) |
| Provides | Synthetic data and labelled scenarios, integration/e2e/evaluation tests, CI, containers, deployment templates |
| Consumes | `contracts.models` (CSV columns = `CustomerProfile` fields), HTTP API, all modules for integration |

## Responsibilities
Make the system reproducible and measurable: data, fixtures, the evaluation harness,
CI, Docker and the Azure plan. Every reported metric comes from an actual run.

## Deliverables (in this order)
- [ ] **Day 1 first:** `data/synthetic/customers.csv`, columns exactly the `CustomerProfile` fields, IDs `CUST-001`…, synthetic values only, no email or protected attributes. About 15 rows covering:
  consistent ×2, loyalty candidate ×2, declining ×2, dormant ×2, overdue courteous / firm / final, no marketing consent (blocked), contacted too recently (blocked), overdue + no consent (reminder allowed by default), ineligible reward (e.g. loyalty-like but tenure below offer minimum), contradictory billing (`paid` with `days_overdue > 0`), and one row with an instruction-like `first_name` (prompt-injection case). Coordinate exact thresholds with `data/policies/segments.yaml`.
- [ ] `data/fixtures/scenarios.jsonl`: one labelled line per row: `customer_id`, `scenario`, `expected_primary_segment`, `expected_status` (`draft_allowed`/`blocked`), `expected_block_reasons`, `expected_reminder_stage`, `expected_offer_id`.
- [ ] `data/fixtures/bad_drafts.jsonl`: deliberately bad drafts (invented offer, wrong amount, wrong date, blocked term, missing support path, email address) with the expected `FindingCode`.
- [ ] `tests/integration/`: policy engine + generator (mock) + validator across all scenarios; DB persistence and audit through the backend.
- [ ] `tests/e2e/`: full API flow (generate → edit → approve → outbox; blocked case cannot be approved); Playwright UI smoke test once a UI exists.
- [ ] `tests/evaluation/` + `scripts/run_evaluation.py`: computes segment accuracy, reminder-stage accuracy, blocked-case rate, validator catch rate on bad drafts, groundedness of approved drafts, rubric average with sample size. Writes `outputs/evaluation.json`; you copy measured results into `docs/EVALUATION_REPORT.md` with N stated.
- [ ] `.github/workflows/ci.yml`: extend the baseline (ruff + pytest) with a frontend job (`npm ci`, lint, test, build) once `frontend/` exists, and Docker build check once Dockerfiles exist.
- [ ] Docker **only after entry points exist**: `infrastructure/docker/backend.Dockerfile`, `frontend.Dockerfile` (multi-stage, static serve), `reviewer_ui.Dockerfile`; non-root users; health checks; `docker-compose.yml` with SQLite volume, env from runtime, documented ports. Target: `docker compose up --build`.
- [ ] `infrastructure/azure/`: Azure Container Apps templates (Bicep or `az` script) + GitHub Actions deploy workflow **disabled/manual**. No deploy, no billable resources, no secrets without explicit team approval.
- [ ] Docs you own: `TESTING_STRATEGY.md`, `DEPLOYMENT.md`, `DEMO_SCRIPT.md`, `EVALUATION_REPORT.md` (measured numbers only).

## Working around dependencies
Data and fixtures need nothing. Integration tests can start against `contracts` with fakes, then switch to real modules as they merge. E2E waits for Member 1; Docker waits for stable entry points (`backend.app.main:app`, `reviewer_ui/app.py`, `frontend` build).

## Testing requirements
- A test that validates every CSV row as `CustomerProfile` and every scenario line's schema.
- Evaluation never calls a real LLM in CI (mock provider). Live runs are manual and labelled as such.
- Run: `python -m pytest tests -q`, `python -m ruff check tests scripts`.

## Definition of done
Reproducible local setup; CI green on PRs; container health checks work; deployment steps and required secrets documented (names only); evaluation numbers come from real runs with N stated; only owned paths changed.

## Commit examples
`feat(data): add synthetic customers for six scenarios` · `test(e2e): blocked customer cannot be approved` · `ci: add frontend build job` · `build(docker): add backend image with non-root user`

## Integration
Merges fifth, then you run the final acceptance suite on `main`. See `docs/INTEGRATION_GUIDE.md`.

## Startup prompt
```text
You are Member 5 (DevOps/QA/Data) in a five-member team. Read, in order: CLAUDE.md,
docs/members/MEMBER_5_DEVOPS_QA.md, docs/ARCHITECTURE.md, docs/API_CONTRACTS.md,
docs/DATA_DICTIONARY.md, docs/TEAM_ASSIGNMENTS.md.
Check you are on branch feature/devops-testing in worktree ../team-devops. Give me a
short implementation plan first and wait for my OK. Start with the synthetic customer
CSV and scenarios.jsonl. Implement only my owned paths. Synthetic data only, no email
or protected attributes. Never fabricate metrics; never deploy or create cloud
resources. Write tests with each change, run python -m pytest tests -q and
python -m ruff check tests scripts, review the changed-file list
(git diff --name-only main...HEAD), commit with conventional commits, push only
feature/devops-testing, and open a PR to main. Finish with the completion report from
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
