# Reviewer UI (Streamlit)

PS deliverable #1. A thin client of the backend API in `docs/API_CONTRACTS.md`: it shows
what the API returns and sends reviewer actions. It computes no segment, eligibility,
amount, date or validation result. The backend is the only approval gate.

## Run

From the repo root, with the project venv active:

```bash
# Against the real backend (default http://localhost:8000)
API_BASE_URL=http://localhost:8000 python -m streamlit run reviewer_ui/app.py

# Against the in-memory fake (until the backend merges)
REVIEWER_UI_FAKE_API=1 python -m streamlit run reviewer_ui/app.py
```

PowerShell: `$env:REVIEWER_UI_FAKE_API="1"; python -m streamlit run reviewer_ui/app.py`.

## Pages

- **Customer**: pick a customer, *Evaluate* (segments, reason codes with evidence,
  confidence, strategy, offer checks, reminder stage, block reasons) and *Generate draft*
  (subject/body, validation findings with blocking ones highlighted, status), then edit,
  approve (optional 1-5 rubric) or reject (reason required).
- **Review queue**: `pending_review` and `blocked` items.
- **Audit trail**: filter by customer, review or event type.

Approve is shown only when the item is `pending_review`, its latest validation passed and
the decision is `draft_allowed` (`guards.can_approve`). A `409` from the API is still
shown as `error.code` / `error.message`.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit pages |
| `api_client.py` | One method per endpoint; errors become `ApiError(code, message)` |
| `guards.py` | Visual guards: `can_approve`, `can_edit`, `can_reject` |
| `formatting.py` | Pure display helpers; markdown escaping for untrusted text |
| `fake_api.py` | In-memory fake backend as an `httpx.MockTransport` (synthetic fixtures, toy validation) |

## Fake API

Customers `CUST-001`..`CUST-010` cover the six PS scenarios plus ineligible reward
(`CUST-010`), contradictory billing (`CUST-008`) and untrusted text with a validation
failure (`CUST-009`). The fake's only "validation" flags the word `guaranteed`; it is a
demo stand-in, not the real `PolicyEngine.validate`.

## Test

```bash
python -m pytest reviewer_ui -q
```
