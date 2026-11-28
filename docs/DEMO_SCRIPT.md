# Demo Script (3–5 minutes)

Owner: **Member 5**. Follows playbook section 14.

Customer IDs are the **planned** scenario IDs. Member 5 confirms them in
`data/fixtures/scenarios.jsonl` and `data/synthetic/customers.csv`; update this table
if they change. All records are synthetic.

| ID | Scenario | Expected result |
|---|---|---|
| CUST-001 | Consistent | Thank-you draft, no offer |
| CUST-002 | Loyalty candidate | Reward draft with one eligible offer |
| CUST-003 | Declining activity | Re-engagement draft with an eligible offer |
| CUST-004 | Dormant | Gentle win-back draft with an eligible offer |
| CUST-005 | Overdue bill | Reminder at the correct stage, with a support/dispute path |
| CUST-006 | Missing marketing consent | Blocked, reason `no_marketing_consent` |
| CUST-007 | Ineligible reward (playbook) | Offer excluded, failed eligibility rules shown |
| CUST-008 | Contradictory billing (playbook) | Blocked, reason `contradictory_billing_data` |

## Before the demo
1. `docker compose up --build`, or run the backend and UI locally (docs/DEVELOPMENT_GUIDE.md).
2. Check `GET /api/health` shows the policy versions and the `llm_mode`.
3. Start with a fresh database (seeded from the synthetic CSV) so the audit log is short.

## Walkthrough
| Step | Time | Show | Say |
|---|---|---|---|
| 1 | 0:00 | Dashboard, customer list | "Synthetic customers only; no protected attributes in the data." |
| 2 | 0:30 | CUST-001: evidence, segment, reason codes, confidence | "Code decides the segment; every segment has a reason." |
| 3 | 1:00 | Generate for CUST-001: draft, validation passed | "The LLM only words verified facts, then validators check them." |
| 4 | 1:30 | CUST-003: strategy and offer checks | "Eligibility is deterministic; the model cannot pick offers." |
| 5 | 2:00 | CUST-005: billing facts, reminder stage, support path | "Firmness follows days overdue from config; amounts come from data." |
| 6 | 2:45 | CUST-006 (and CUST-008): blocked with reason, approve disabled | "Refusal is a feature: no consent means no message, recorded in audit." |
| 7 | 3:30 | Edit a valid draft to add a blocked term: validation fails. Fix it, then approve. Show the mock outbox record and the audit trail. | "Edits are re-validated; nothing is sent without approval; the audit has no email addresses." |
| 8 | 4:30 | Close | "Policy in YAML, facts in code, words by the LLM, decisions by a person." |

## Fallbacks
- **No API key, rate limit or no Wi-Fi:** set `LLM_PROVIDER=mock` and restart the
  backend. Policy decisions, validation, review, outbox and audit all still work, and
  drafts come from the deterministic mock generator.
- **UI problem:** show the same flow in the Streamlit reviewer (`reviewer_ui`), or
  through the FastAPI `/docs` page.
- **Total failure:** use the recorded screen capture or screenshots
  (Member 5 records them after the rehearsal).
