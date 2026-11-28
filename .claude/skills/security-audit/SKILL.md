---
name: security-audit
description: Security, privacy and safety audit of the branch or whole project - secrets, personal data, protected attributes, prompt injection, LLM deciding facts, and send paths that bypass validation or approval. Use before merging data, prompt, audit, delivery or deployment changes, and before the demo.
---

# Security audit

1. Scope: branch diff (`git diff main...HEAD`) or the whole project, as asked.
2. Secrets: search for key-like strings (`sk-`, `gsk_`, `api_key`, `AZURE_`, `password`) outside `.env.example`; confirm `.env` and `outputs/` are git-ignored. Never open `.env`.
3. Personal data: no email field in `data/synthetic/`; no email addresses in audit, logs or prompts; `AuditEvent` validation not bypassed.
4. Fairness: no protected characteristics or proxies in data, `data/policies/` or rules.
5. Fact boundary: `ai_engine` receives only `VerifiedFacts`; no LLM output feeds a segment, offer, stage, amount or date.
6. Send paths: trace every route to the mock outbox; each requires `pending_review`, passed re-validation, `draft_allowed` and an approve call. Check edits, retries, errors and any bulk action.
7. Prompt injection: customer/campaign text is passed as quoted data; test fixture with an instruction in `first_name` is blocked or harmless.
8. Errors and Docker/CI: no stack traces or secrets in responses; no secrets in images or workflows.
9. Ask the `security-reviewer` agent with the diff or file list, merge its findings with yours.
10. Report findings most severe first (`severity | file:line | finding | fix`) and what you could not check.
