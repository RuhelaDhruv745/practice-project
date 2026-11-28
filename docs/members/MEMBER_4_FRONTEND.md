# Member 4: Frontend Engineer

Name: <fill in>

| | |
|---|---|
| Branch | `feature/frontend` |
| Worktree | `../team-frontend` |
| Owns | `reviewer_ui/` (Streamlit, PS deliverable #1), `frontend/` (React + TypeScript, created by you with Vite) |
| Must not modify | `contracts/`, `backend/`, `ai_engine/`, `policy_engine/`, `data/`, root `tests/`, `infrastructure/`, `scripts/`, `.github/`, `.claude/`, `docs/`, root config files |
| Provides | Reviewer interfaces |
| Consumes | HTTP API in `docs/API_CONTRACTS.md` only |

## Responsibilities
Both UIs are **thin clients**. They display what the API returns and send reviewer
actions. They compute no segment, eligibility, amount or validation result, and they
never write to the outbox. The backend is the only gate; the UI adds a second, visual
guard (no approve button for blocked items).

## Deliverables

### Phase A: Streamlit reviewer app (do first; required deliverable)
- [ ] `reviewer_ui/app.py`, run with `python -m streamlit run reviewer_ui/app.py`; API base URL from `API_BASE_URL` (default `http://localhost:8000`).
- [ ] `reviewer_ui/requirements.txt` (streamlit, httpx or requests).
- [ ] Customer picker → evaluate → show segments, reason codes with evidence, confidence, strategy, offer checks, reminder stage, block reasons.
- [ ] Generate draft → show subject/body, validation findings (blocking highlighted), status.
- [ ] Edit (re-validated by API, show new findings), approve (with optional 1–5 rubric: relevance, clarity, personalisation, call to action, tone), reject (reason required).
- [ ] Approve hidden/disabled unless `status == pending_review` and `validation.passed`.
- [ ] Audit view filtered by customer or review.
- [ ] API errors shown using `error.code` / `error.message`; never a raw traceback.

### Phase B: React dashboard
- [ ] Create with `npm create vite@latest frontend -- --template react-ts`; add Tailwind, shadcn/ui, React Query, React Router.
- [ ] Types generated from the backend: `npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts` (script `npm run gen:types`). Do not hand-write duplicate models.
- [ ] Pages: dashboard (counts by status/segment), customer list/detail, review queue, review detail, audit log.
- [ ] Panels: evidence, segments + reasons + confidence, strategy, draft preview/editor, validation findings, reviewer rubric/feedback.
- [ ] Loading, empty and error states on every page; blocked items cannot be approved from the UI.
- [ ] `VITE_API_BASE_URL` for the API URL.

## Working around dependencies
Until Member 1's endpoints merge: Streamlit uses a small `reviewer_ui/fake_api.py` returning the JSON examples from `API_CONTRACTS.md`; React uses MSW (Mock Service Worker) handlers in `frontend/src/mocks/`. Switch to the real API by environment variable only.

## Testing requirements
- Streamlit: `reviewer_ui/tests/` with pytest for the API client and the "can approve" rule (Streamlit `AppTest` where practical).
- React: Vitest + React Testing Library for rendering a customer, editing, approve, reject, validation display, blocked state with no approve button, error state. Optional Playwright smoke test (coordinate with Member 5, who owns `tests/e2e`).
- Run: `python -m pytest reviewer_ui/tests -q`; in `frontend/`: `npm run lint`, `npm run test`, `npm run build`.

## Definition of done
Streamlit app covers all six scenarios end to end against the API; React build passes; reviewer actions explicit; blocked drafts cannot be approved through either UI; no business logic in UI code; only owned paths changed.

## Commit examples
`feat(frontend): add Streamlit review screen` · `feat(frontend): add review queue page` · `test(frontend): blocked item has no approve button`

## Integration
Merges fourth, after backend, policy and AI. Ship Streamlit in an early PR so the demo is safe even if React slips. See `docs/INTEGRATION_GUIDE.md`.

## Startup prompt
```text
You are Member 4 (Frontend) in a five-member team. Read, in order: CLAUDE.md,
docs/members/MEMBER_4_FRONTEND.md, docs/ARCHITECTURE.md, docs/API_CONTRACTS.md,
docs/DATA_DICTIONARY.md, docs/TEAM_ASSIGNMENTS.md.
Check you are on branch feature/frontend in worktree ../team-frontend. Give me a short
implementation plan first and wait for my OK. Implement only paths under reviewer_ui/
and frontend/. Build the Streamlit reviewer app first, then the React dashboard. The
UIs call the API only and contain no business logic; blocked items must never be
approvable. Write tests with each change, run them, review the changed-file list
(git diff --name-only main...HEAD), commit with conventional commits, push only
feature/frontend, and open a PR to main. Finish with the completion report from my
member file. Report failures honestly.
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
