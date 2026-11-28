# Requirements

Authority: `docs/problem-statement.md` (the PS). Anything not in the PS is labelled with
its source: **[playbook]** (HCLTech Hackathon Team Playbook) or **[architect]**
(decision made for this build). Owners: M1 Backend, M2 AI, M3 Policy, M4 Frontend,
M5 DevOps/QA, A Architect.

## 1. Functional requirements (PS numbering)

| ID | Capability | Requirement | Done when (acceptance) | Owner |
|---|---|---|---|---|
| FR-01 | Customer profile | Build a minimal profile from permitted fields only | `CustomerProfile` holds only the PS fields; unknown fields (email, age, gender, …) are rejected; no protected data in CSV | M5 data, M1 assembly, A contract |
| FR-02 | Segmentation | Assign one or more segments with reason codes and a confidence value | Every `SegmentAssignment` has ≥ 1 `ReasonCode` with evidence and a confidence in [0, 1]; primary segment chosen by configured priority | M3 |
| FR-03 | Strategy selection | Map each segment to an approved objective and tone from configuration | Editing `data/policies/strategies.yaml` changes the strategy with no code edit (test proves it) | M3 |
| FR-04 | Offer and reward checks | Validate eligibility, offer ID, value, expiry and channel in code | Ineligible or expired offers never appear in `VerifiedFacts`; every offer has an `OfferCheck` with failed rules | M3 |
| FR-05 | Billing reminders | Choose a reminder stage from days overdue, respectful tone, support path | Stage matches days overdue in every test, including boundaries 7/8 and 21/22; support path always present | M3 |
| FR-06 | Grounded drafting | Generate subject and body only from verified facts | LLM receives only `VerifiedFacts`, returns only `DraftContent`; no invented amount, date or offer passes validation | M2 (generation), M3 (validation) |
| FR-07 | Safety and compliance checks | Detect unsupported claims, blocked language, consent gaps and duplicate outreach | A bad draft gets `passed: false` with findings and cannot be approved | M3 |
| FR-08 | Human review | Show evidence, segment, strategy, draft and findings with approve, edit, reject | Each reviewer action is saved and audited; edited drafts are re-validated | M4 (UI), M1 (API) |
| FR-09 | Audit | Record versions, evidence fields, decisions and outcome without email addresses | A decision can be reconstructed from `GET /api/audit`; `AuditEvent` rejects emails | M1, A contract |
| FR-10 | Controlled delivery | Send only to a mock outbox, only after approval and passing checks | Approve returns `409` whenever any check failed; no real email path exists | M1 |

### Mapping to playbook numbering

The playbook follows the original HCLTech brief, whose order differs. Use PS IDs everywhere.

| Playbook ID | Playbook name | PS ID |
|---|---|---|
| FR-01 | Customer profile assembly | FR-01 |
| FR-02 | Transparent classification | FR-02 |
| FR-03 | Policy-based strategy | FR-03 |
| FR-04 | Grounded generation | **FR-06** |
| FR-05 | Offer/reward controls | **FR-04** |
| FR-06 | Billing controls | **FR-05** |
| FR-07 – FR-10 | Safety, review, audit, delivery | FR-07 – FR-10 |

### Additional functional details

| ID | Requirement | Source | Owner |
|---|---|---|---|
| FX-01 | Audit records also store prompt/template version and model version | [playbook] FR-09 | M1, M2 |
| FX-02 | Detect sensitive-data leakage in drafts (`sensitive_data` finding) | [playbook] FR-07 | M3 |
| FX-03 | Capture reviewer feedback rubric (relevance, clarity, personalisation, call to action, tone; 1–5) | PS success measures + [playbook] | M4, M1 |
| FX-04 | Contradictory or missing billing evidence blocks outreach with a reason | [playbook] scenarios | M3 |
| FX-05 | `POST /api/messages/validate` dry-run endpoint | [playbook] API list | M1 |

## 2. Mandatory scenarios

| # | Scenario | Signal | Expected result | Source |
|---|---|---|---|---|
| S1 | Consistent customer | Steady activity, all payments on time | `consistent`; thanks draft, no offer, no hard sell | PS |
| S2 | Loyalty candidate | Long tenure, high activity, on-time payments, no overdue bill | `loyalty_candidate`; exactly one eligible reward | PS |
| S3 | Declining activity | Activity ≥ 30% below previous 30 days | `declining`; relevant engagement offer | PS |
| S4 | Dormant | Activity below dormant threshold | `dormant`; gentle win-back with eligible offer | PS |
| S5 | Overdue bill | Known days overdue | `payment_reminder`; stage follows days, support/dispute path | PS |
| S6 | Blocked | No marketing consent, or contacted too recently | Blocked, reason recorded, no draft | PS |
| S7 | Ineligible reward | Segment matches but tenure/expiry/channel fails | Offer excluded; failed rules shown | [playbook] |
| S8 | Contradictory billing data | e.g. `paid` with `days_overdue > 0` | Blocked `contradictory_billing_data` | [playbook] |
| S9 | Missing evidence | e.g. overdue with no `due_date` | Blocked `missing_evidence` | [playbook] |
| S10 | Untrusted text | Instruction text inside customer/campaign data | Treated as data; draft still validated | PS safety rule |

## 3. Safety rules (each enforced in code or a test)

| ID | Rule | Enforced by |
|---|---|---|
| SR-01 | Code decides facts: segment, eligibility, stage, amounts, dates | `PolicyEngine.decide` (M3); LLM never receives the profile |
| SR-02 | The model only words; returns subject and body as structured output | `DraftContent` (extra fields rejected) |
| SR-03 | Every draft checked: numbers, dates, offer IDs match; blocked terms absent; reminders include support path | `PolicyEngine.validate` (M3) |
| SR-04 | A person approves; failed check blocks sending | Approve endpoint state checks + re-validation (M1) |
| SR-05 | Fair treatment: no protected characteristics or proxies in data or logic | `CustomerProfile` field allowlist; safety review |
| SR-06 | Consent and frequency: missing consent or recent contact blocks outreach | `BlockReason` in `decide` (M3) |
| SR-07 | Privacy: no email addresses or unnecessary personal data in audit | `AuditEvent` validator; no email field anywhere |
| SR-08 | Untrusted text is data, not instructions | Prompt delimiting (M2) + validators (M3) + scenario S10 |
| SR-09 | Safe delivery: mock outbox only | No SMTP/email SDK in dependencies (M1) |
| SR-10 | Secrets only in `.env`; never committed, logged or returned | `.gitignore`, hooks, `/api/health` shape |

## 4. Evaluation criteria (PS success measures)

Report only measured results, with the number of cases. No fabricated percentages.

| Measure | Method | Target |
|---|---|---|
| Segment accuracy | Predicted vs labelled `data/fixtures/scenarios.jsonl` | All six PS scenarios correct |
| Grounded drafts | Every amount, date, offer ID in approved drafts matches data | No mismatches |
| Validator catch rate | Deliberately bad drafts (invented offer, wrong amount, blocked term, missing support path) | Every bad draft blocked |
| Blocked cases | No-consent and recently-contacted customers | Blocked every time with reason |
| Reminder stage | Days overdue vs chosen stage incl. boundaries | Correct in every test |
| Reviewer rubric | 1–5 scores | Average with sample size |

## 5. Scope

**In:** rule-based segmentation with reason codes; deterministic offer, billing and
contact checks; LLM drafting with output validation; review screen (approve, edit,
reject); mock outbox; audit log; short evaluation.

**Out:** real email delivery or unreviewed bulk sending; charging, waiving or changing
accounts; ML segmentation or churn prediction; real customer data; protected
characteristics; real CRM or billing integration.

## 6. Non-functional requirements

| ID | Requirement | Source |
|---|---|---|
| NFR-01 | Reproducibility: fixed `as_of_date` in `data/policies/policy.yaml`; same input → same segments and checks | PS goal |
| NFR-02 | Explainability: every segment, block and finding carries a code and evidence | PS goal |
| NFR-03 | Privacy by design: no email field in data, API or audit | PS rule |
| NFR-04 | Resilience: retry with backoff on LLM rate limits; one retry on malformed output; provider switch by config | PS risks |
| NFR-05 | Offline demo: mock LLM mode when no key is set; deterministic policy always works | [playbook] demo fallback |
| NFR-06 | Policy changes need no code edits; invalid config fails fast at startup | PS FR-03 + [architect] |
| NFR-07 | Tests never call a real LLM API | CLAUDE.md |
| NFR-08 | Runs locally with `docker compose up --build` | [playbook] |

## 7. Assumptions

| ID | Assumption |
|---|---|
| AS-01 | All thresholds, offers, stages, tones and blocked terms live in `data/policies/*.yaml` and are editable assumptions, not learned values |
| AS-02 | About 15 synthetic customers in one CSV; three offers; currency INR |
| AS-03 | Payment reminders are service messages and do **not** require marketing consent (`reminders_require_marketing_consent: false`). Resolves the PS open question; defaulted by the user on 2026-11-28. Frequency rules still apply. |
| AS-04 | Reviewer identity is a pseudonymous label; no authentication in the hackathon build [architect] |
| AS-05 | Mock delivery moves an approved item straight to `delivered` [architect] |
| AS-06 | Only the email channel is drafted; SMS offers are ineligible for email [architect] |

## 8. Unresolved questions

| ID | Question | Proposed default |
|---|---|---|
| UQ-01 | Confidence method for segments | M3 proposes a deterministic, documented method (e.g. threshold margin) |
| UQ-02 | Should a reminder also be blocked by the recent-contact rule? | Yes (frequency applies to all outreach) until the client says otherwise |
| UQ-03 | Does the hackathon require deployment to Azure, or local demo only? | Prepare plan; deploy only with team approval |
| UQ-04 | Contact history: is `last_contacted_days_ago` updated after mock delivery? | Yes, in the database only; CSV stays the seed |
