# Security and Privacy

Scope: hackathon prototype on synthetic data, mock delivery only. These controls are
still enforced in code or tests, because the brief makes them non-negotiable.

## Threat model

| # | Threat | Impact | Control | Enforced in |
|---|---|---|---|---|
| T1 | API keys committed or printed | Account abuse, cost | Secrets only in `.env` (git-ignored); `.env.example` holds names only; Claude hook blocks reading `.env`; `/api/health` never returns keys | `.gitignore`, `.claude/hooks/protect_env.py`, `.claude/settings.json`, `backend/` config |
| T2 | PII in LLM prompts | Data leaves the system | LLM receives `VerifiedFacts` only (no profile, no IDs beyond need); there is no email field in any model | `contracts/models.py` (`VerifiedFacts`, `CustomerProfile extra=forbid`), `ai_engine/` |
| T3 | PII in logs or audit | Privacy breach | `AuditEvent` rejects email addresses in `details`; logs carry IDs and codes, not field values or draft bodies | `contracts/models.py`, `backend/` logging |
| T4 | Prompt injection via customer/campaign text (e.g. `first_name`) | LLM obeys data | Untrusted fields wrapped in delimited data block; system prompt states data is not instructions; output always validated, so an injected offer/amount is blocked | `ai_engine/prompts/`, `policy_engine/compliance/` |
| T5 | LLM invents amount, date, offer or eligibility | Wrong commitment to customer | Code decides facts; LLM returns `DraftContent` (subject, body) only; validators compare every number, date and offer ID with `VerifiedFacts` | `policy_engine/`, `contracts/models.py` (`DraftContent extra=forbid`) |
| T6 | Approval bypass: approve blocked item, edit after validation, retry path, bulk action | Unreviewed or unsafe message delivered | Status machine; approve requires `pending_review` + passed validation + `draft_allowed`; edits re-validate; approve re-validates before writing outbox; no bulk endpoint | `backend/` services, `docs/API_CONTRACTS.md` |
| T7 | Missing consent / duplicate outreach | Regulatory breach | Checked in `decide` (gate) and again in `validate` (`consent_gap`, `duplicate_outreach`) | `policy_engine/` |
| T8 | Protected characteristics or proxies influence treatment | Unfair treatment | No such fields exist (`CustomerProfile extra=forbid`); CSV loader rejects extra columns; reviewers check rules for proxies (e.g. name-based inference) | `contracts/`, `backend/` seed, `security-reviewer` agent |
| T9 | Real email sent | Harm to real people | Delivery is a mock writing to DB + `outputs/outbox.jsonl`; no SMTP/email SDK dependency | `backend/` delivery service, dependency review |
| T10 | CORS too open | Other origins drive the reviewer API | Allow-list only the local UI origins (`http://localhost:5173`, `http://localhost:8501`) via config | `backend/app/main.py` |
| T11 | Dependency supply chain | Malicious package | Minimal deps, per-module `requirements.txt`, new deps need architect approval; CI can run `pip-audit` / `npm audit` (advisory) | `requirements*.txt`, `.github/workflows/` |
| T12 | Error responses leak internals | Info disclosure | `ErrorResponse` envelope; 500 hides stack traces | `backend/` middleware |

## Secrets handling

| Rule | Detail |
|---|---|
| Location | Local: `.env` only (never committed, never read or printed by tools or Claude). Names documented in `.env.example`. |
| Loading | `python-dotenv` in the backend/ai_engine settings module; values never logged |
| Missing key | App starts in `LLM_MODE=mock`; health shows `mock`; no crash, no key in error text |
| CI | No LLM secrets in CI; tests mock the LLM |
| Azure (later) | Container Apps secrets or Azure Key Vault references with managed identity; never in images, compose files or the repo |
| Leak response | Revoke the key at the provider first, then remove from history; tell the architect |

## Logging rules

- Log: request ID, endpoint, status code, customer_id, review_id, event type, finding codes,
  durations.
- Never log: secrets, raw prompts with customer text, draft bodies, full profiles,
  email addresses.
- Audit trail (`audit_event`) is the record of decisions; application logs are for debugging.

## Data rules

- Synthetic data only; no real customer data in repo, fixtures, screenshots or demos.
- No protected characteristics or proxies in data, config or logic.
- Minimum data: only `CustomerProfile` fields exist.

## Reporting

Found a security or privacy problem? Open an issue labelled `security` (no secret values in
the issue), notify the architect, and do not merge affected PRs until resolved. Run the
`security-reviewer` agent on changes to data, config, LLM, audit or delivery code.
