# Data Dictionary

Prose version of `contracts/enums.py` and `contracts/models.py`. **The code is the source
of truth**; if this file and the code disagree, the code wins and this file is fixed.

**Rule: nobody redefines these models.** Import them from `contracts`. Need a new field or
model? Open a "Contract or ownership change" issue; the architect changes `contracts/`,
this file and `docs/API_CONTRACTS.md` in one PR.

Common conventions (all models inherit `Contract`):
- `extra="forbid"`: unknown fields are a validation error.
- `frozen=True`: instances are immutable; build a new one to change a value.
- Money is `Decimal` (JSON: decimal string, e.g. `"2000.00"`). Dates `YYYY-MM-DD`,
  timestamps ISO 8601 UTC.
- `Primitive` = `str | int | float | bool | None`.

## Enumerations (`contracts/enums.py`)

| Enum | Values | Meaning |
|---|---|---|
| `SegmentName` | `consistent`, `loyalty_candidate`, `declining`, `dormant`, `payment_reminder` | Rule-based segments. Rules in `policy_engine`, thresholds in `data/policies/segments.yaml` |
| `BillStatus` | `paid`, `due`, `overdue` | Billing state of the current bill |
| `OfferUnit` | `percent`, `inr`, `gb` | Unit of an offer's `value` |
| `Channel` | `email`, `sms` | Delivery channel of an offer / outbox record |
| `DecisionStatus` | `draft_allowed`, `blocked` | Outcome of the deterministic policy gate |
| `BlockReason` | `no_marketing_consent`, `contacted_too_recently`, `contradictory_billing_data`, `missing_evidence`, `no_actionable_segment` | Why outreach was refused |
| `FindingCode` | `schema_invalid`, `amount_mismatch`, `date_mismatch`, `unknown_offer`, `ineligible_offer`, `unsupported_claim`, `blocked_term`, `missing_support_path`, `consent_gap`, `duplicate_outreach`, `sensitive_data` | Validator checks (FR-07) |
| `Severity` | `blocking`, `warning` | A `blocking` finding fails validation |
| `MessageStatus` | `blocked`, `pending_review`, `approved`, `rejected`, `delivered` | Review item lifecycle; only `pending_review` can be approved |
| `ReviewAction` | `edit`, `approve`, `reject` | Reviewer action |
| `AuditEventType` | `profile_assembled`, `classified`, `policy_decided`, `outreach_blocked`, `draft_generated`, `generation_failed`, `draft_validated`, `review_edited`, `review_approved`, `review_rejected`, `message_delivered`, `delivery_refused` | Audit event kinds |

## Shared constrained types

| Name | Definition |
|---|---|
| `CustomerId` | `str`, pattern `^CUST-\d{3,6}$` (e.g. `CUST-001`) |
| `Score` | `float`, 0 ≤ x ≤ 100 |
| `Confidence` | `float`, 0 ≤ x ≤ 1 |
| `RubricScore` | `int`, 1 ≤ x ≤ 5 |

## Customer — `CustomerProfile` (FR-01)

Producer: Member 1 repository layer (assembled from DB). Consumers: Member 3, API.
Permitted fields only. There is **no** email, age, gender, religion, location, postcode or
any other protected-characteristic or proxy field, and adding one is rejected.

| Field | Type | Req. | Constraints | Meaning |
|---|---|---|---|---|
| `customer_id` | `CustomerId` | yes | `CUST-NNN` | Identifier |
| `first_name` | `str` | yes | 1–60 chars | Greeting name. **Untrusted text: data, never instructions** |
| `consent_marketing` | `bool` | yes | | Marketing contact allowed |
| `plan` | `str` | yes | 1–40 chars | Current plan name |
| `months_active` | `int` | yes | ≥ 0 | Tenure |
| `activity_score_30d` | `Score` | yes | 0–100 | Activity, last 30 days |
| `activity_score_prev_30d` | `Score` | yes | 0–100 | Activity, previous 30 days |
| `on_time_payments_12m` | `int` | yes | 0–12 | On-time payments, last 12 months |
| `bill_status` | `BillStatus` | yes | | Current bill state |
| `days_overdue` | `int` | yes | ≥ 0 | Days past due date |
| `amount_due` | `Decimal` | yes | ≥ 0, 2 decimal places | Amount owed (INR) |
| `due_date` | `date \| None` | yes (nullable) | | Due date of current bill |
| `last_contacted_days_ago` | `int \| None` | no (default `None`) | ≥ 0 | Days since last outreach; `None` = never |

Billing consistency (e.g. `paid` with `days_overdue > 0`) is **deliberately not enforced**
here, so the policy engine can block the record with `contradictory_billing_data`.

## CustomerSegment — `SegmentName`, `SegmentAssignment`, `ReasonCode` (FR-02)

Producer: Member 3.

`ReasonCode`

| Field | Type | Req. | Constraints | Meaning |
|---|---|---|---|---|
| `code` | `str` | yes | `^[A-Z][A-Z0-9_]+$` | Machine reason, e.g. `ACTIVITY_DROP_30PCT` |
| `description` | `str` | yes | non-empty | Human explanation |
| `evidence` | `dict[str, Primitive]` | yes | | Field names and values the rule used |

`SegmentAssignment`

| Field | Type | Req. | Constraints | Meaning |
|---|---|---|---|---|
| `segment` | `SegmentName` | yes | | Assigned segment |
| `confidence` | `Confidence` | yes | 0–1 | Deterministic confidence; method documented by Member 3 |
| `reasons` | `list[ReasonCode]` | yes | ≥ 1 | Why it was assigned |

## ClassificationResult (FR-02)

Producer: Member 3 (`PolicyEngine.classify`).

| Field | Type | Req. | Constraints | Meaning |
|---|---|---|---|---|
| `customer_id` | `CustomerId` | yes | | |
| `as_of_date` | `date` | yes | | Fixed policy date (`policy.yaml`) |
| `segments` | `list[SegmentAssignment]` | yes | may be empty | All matching segments |
| `primary_segment` | `SegmentName \| None` | yes | must be one of `segments`; required if any assigned | Drives the message (by `priority` in `segments.yaml`) |
| `policy_versions` | `dict[str, str]` | yes | | Version of each policy file used |

## Strategy (FR-03)

Producer: Member 3, from `data/policies/strategies.yaml`.

| Field | Type | Req. | Meaning |
|---|---|---|---|
| `segment` | `SegmentName` | yes | Segment the strategy is for |
| `objective` | `str` | yes | e.g. `thank`, `reward`, `re_engage`, `win_back`, `collect_politely` |
| `tone` | `str` | yes | Tone name (reminder stage tone overrides for `payment_reminder`) |
| `tone_guidance` | `str` | yes | Wording guidance given to the LLM |
| `offer_allowed` | `bool` | yes | Whether any offer may be attached |

## Offer (FR-04)

### YAML schema (`data/policies/offers.yaml`, validated by `policy_engine/config_loader.py`)

| Field | Type | Constraints |
|---|---|---|
| `offer_id` | `str` | `^[A-Z0-9]+(-[A-Z0-9]+)*$`, unique |
| `description` | `str` | non-empty; contains no numbers by convention |
| `value` | `Decimal` | > 0; ≤ 100 when `unit` is `percent` |
| `unit` | `OfferUnit` | |
| `expiry` | `date` | eligibility requires `as_of_date` ≤ expiry |
| `allowed_segments` | `list[SegmentName]` | ≥ 1; each segment's strategy must have `offer_allowed: true` |
| `min_months_active` | `int` | ≥ 0 |
| `channel` | `Channel` | |

### `OfferSnapshot` — an offer that passed every eligibility check, copied exactly

| Field | Type | Constraints |
|---|---|---|
| `offer_id` | `str` | same pattern as YAML |
| `description` | `str` | |
| `value` | `Decimal` | > 0 |
| `unit` | `OfferUnit` | |
| `expiry` | `date` | |
| `channel` | `Channel` | |

### `OfferCheck` — eligibility result per configured offer (explainability)

| Field | Type | Req. | Meaning |
|---|---|---|---|
| `offer_id` | `str` | yes | Offer checked |
| `eligible` | `bool` | yes | Passed all rules |
| `failed_rules` | `list[str]` | no (default `[]`) | e.g. `segment_not_allowed`, `expired`, `min_tenure`, `channel` |

## BillingStatus — `BillStatus`, `ReminderFacts` (FR-05)

`ReminderFacts` (producer: Member 3, only for `payment_reminder`)

| Field | Type | Constraints | Meaning |
|---|---|---|---|
| `stage` | `str` | | Stage name from `reminders.yaml` (`courteous`, `firm`, `final_notice`) |
| `days_overdue` | `int` | ≥ 1 | |
| `amount_due` | `Decimal` | > 0 | Exact amount the draft must quote |
| `currency` | `str` | 3 chars | e.g. `INR` |
| `due_date` | `date` | | Exact date the draft must quote |
| `support_path` | `str` | ≥ 10 chars | Support/dispute text the draft must include |

## VerifiedFacts (FR-06)

The **only** input the LLM receives. Built only by Member 3; consumed by Member 2.

| Field | Type | Req. | Meaning |
|---|---|---|---|
| `customer_id` | `CustomerId` | yes | For traceability (not for the prompt body if avoidable) |
| `first_name` | `str` | yes | Untrusted text |
| `plan` | `str` | yes | |
| `segment` | `SegmentName` | yes | Primary segment |
| `objective` | `str` | yes | |
| `tone` | `str` | yes | Effective tone |
| `tone_guidance` | `str` | yes | |
| `offer` | `OfferSnapshot \| None` | no | Present only if eligible |
| `reminder` | `ReminderFacts \| None` | no | Present only for reminders |

## PolicyDecision (FR-03/04/05/07 gate)

Producer: Member 3 (`PolicyEngine.decide`).

| Field | Type | Req. | Meaning |
|---|---|---|---|
| `customer_id` | `CustomerId` | yes | |
| `status` | `DecisionStatus` | yes | |
| `block_reasons` | `list[BlockReason]` | no (default `[]`) | |
| `classification` | `ClassificationResult` | yes | |
| `strategy` | `Strategy \| None` | no | |
| `offer_checks` | `list[OfferCheck]` | no (default `[]`) | |
| `facts` | `VerifiedFacts \| None` | no | |

Invariants: `blocked` ⇒ ≥ 1 block reason and `facts is None`.
`draft_allowed` ⇒ no block reasons, `strategy` and `facts` present.

## GeneratedMessage / DraftContent (FR-06)

`DraftContent` — the LLM's structured output, nothing else (producer: Member 2; also the
reviewer's edit payload).

| Field | Type | Constraints |
|---|---|---|
| `subject` | `str` | 1–150 chars |
| `body` | `str` | 1–4000 chars |

`GeneratedMessage` (producer: Member 2, `DraftGenerator.generate`)

| Field | Type | Meaning |
|---|---|---|
| `message_id` | `str` | Unique ID |
| `customer_id` | `CustomerId` | |
| `draft` | `DraftContent` | |
| `source` | `"llm" \| "reviewer_edit"` | Default `llm`; a reviewer edit is stored as a new message with `reviewer_edit` |
| `provider` | `str` | e.g. `anthropic`, `groq`, `mock`; `reviewer` for edits |
| `model` | `str` | Model ID used |
| `prompt_version` | `str` | Prompt template version |
| `generated_at` | `datetime` | UTC |

## ValidationResult / ValidationFinding / FindingCode (FR-07)

Producer: Member 3 (`PolicyEngine.validate`), for generated and edited drafts.

`ValidationFinding`

| Field | Type | Req. | Meaning |
|---|---|---|---|
| `code` | `FindingCode` | yes | Which check |
| `severity` | `Severity` | yes | `blocking` fails validation |
| `message` | `str` | yes | Human-readable finding |
| `evidence` | `dict[str, Primitive]` | no | e.g. expected vs found amount |

`ValidationResult`

| Field | Type | Req. | Meaning |
|---|---|---|---|
| `passed` | `bool` | yes | True **exactly** when no finding is `blocking` (enforced) |
| `findings` | `list[ValidationFinding]` | no | |
| `checks_run` | `list[FindingCode]` | yes | Which checks executed |
| `validator_version` | `str` | yes | For audit |

## ReviewItem / ReviewDecision / ReviewRubric (FR-08)

`ReviewItem` (producer: Member 1)

| Field | Type | Meaning |
|---|---|---|
| `review_id` | `str` | |
| `customer_id` | `CustomerId` | |
| `status` | `MessageStatus` | See state machine in `API_CONTRACTS.md` |
| `revision` | `int` ≥ 1 | Increments on each edit |
| `decision` | `PolicyDecision` | Evidence, segment, strategy |
| `message` | `GeneratedMessage \| None` | `None` when policy blocked |
| `validation` | `ValidationResult \| None` | Latest validation; `None` when policy blocked |
| `decisions` | `list[ReviewDecision]` | Every reviewer action on this item, oldest first (default `[]`) |
| `created_at`, `updated_at` | `datetime` | UTC |

`ReviewDecision`

| Field | Type | Constraints |
|---|---|---|
| `review_id` | `str` | |
| `action` | `ReviewAction` | |
| `reviewer_id` | `str` | `^[a-z0-9-]{3,40}$`, pseudonymous |
| `comment` | `str \| None` | ≤ 1000 chars; **required (non-blank) when `action` is `reject`** (enforced) |
| `rubric` | `ReviewRubric \| None` | |
| `decided_at` | `datetime` | |

`ReviewRubric`: `relevance`, `clarity`, `personalisation`, `call_to_action`, `tone`, each
`RubricScore` (1–5).

## AuditEvent (FR-09)

Producer: Member 1. Append-only.

| Field | Type | Req. | Meaning |
|---|---|---|---|
| `event_id` | `str` | yes | |
| `event_type` | `AuditEventType` | yes | |
| `occurred_at` | `datetime` | yes | UTC |
| `actor` | `str` | yes | `system` or a `reviewer_id`; an email address is rejected (enforced) |
| `customer_id` | `CustomerId \| None` | no | |
| `review_id`, `message_id` | `str \| None` | no | |
| `policy_versions` | `dict[str, str]` | no | |
| `prompt_version`, `model` | `str \| None` | no | |
| `details` | `dict[str, Primitive \| list[Primitive]]` | no | **Any string value containing an email address is rejected** |

## OutboxRecord (FR-10)

Producer: Member 1, only for an approved item whose re-validation passed.

| Field | Type | Meaning |
|---|---|---|
| `message_id`, `review_id` | `str` | |
| `customer_id` | `CustomerId` | Recipient is identified by ID; there is no email address |
| `channel` | `Channel` | `email` (mock) |
| `subject`, `body` | `str` | Final approved text |
| `approved_by` | `str` | `reviewer_id` |
| `delivered_at` | `datetime` | UTC |

## API request and response bodies (`contracts/api.py`)

Owner: architect. Used by Member 1's routes; Member 4 generates TypeScript types from them.

| Model | Fields | Used by |
|---|---|---|
| `CustomerRequest` | `customer_id` | `POST /api/classification/evaluate`, `POST /api/messages/generate` |
| `ValidateRequest` | `customer_id`, `draft: DraftContent` | `POST /api/messages/validate` |
| `EditReviewRequest` | `reviewer_id`, `draft: DraftContent`, `comment?` | `PATCH /api/reviews/{id}` |
| `ApproveRequest` | `reviewer_id`, `comment?`, `rubric?` | `POST /api/reviews/{id}/approve` |
| `RejectRequest` | `reviewer_id`, `comment` (required, non-blank), `rubric?` | `POST /api/reviews/{id}/reject` |
| `ApproveResponse` | `review: ReviewItem`, `outbox: OutboxRecord` | approve response |
| `CustomerSummary` | `customer_id`, `first_name`, `plan`, `bill_status`, `consent_marketing`, `primary_segment?` | `GET /api/customers` items |
| `Page[T]` | `items: list[T]`, `total` ≥ 0 | every list endpoint |
| `HealthResponse` | `status: "ok"`, `version`, `policy_versions`, `llm_provider`, `llm_mode: "live" \| "mock"` | `GET /api/health` |

`reviewer_id` everywhere matches `^[a-z0-9-]{3,40}$`.

## ErrorResponse

`{"error": ErrorDetail}` where `ErrorDetail` = `code: str`, `message: str`,
`details: dict[str, Primitive | list[Primitive]]` (default `{}`). Codes are listed in
`docs/API_CONTRACTS.md`.

## File data contracts (owner: Member 5)

### `data/synthetic/customers.csv`

- Header = the `CustomerProfile` field names, exactly, in the order above. No other
  columns (an extra column such as `email` or `age` must fail loading).
- `customer_id`: `CUST-NNN`. Booleans: `true` / `false`.
- `amount_due`: decimal string with two places (`0.00`, `2000.00`).
- `due_date`: `YYYY-MM-DD`, or empty when there is no current bill.
- `last_contacted_days_ago`: integer, or empty for never contacted.
- Synthetic values only. Each row is parsed into `CustomerProfile`.

### `data/fixtures/scenarios.jsonl`

One JSON object per line; one line per labelled customer.

| Key | Type | Meaning |
|---|---|---|
| `customer_id` | `str` | Row in `customers.csv` |
| `scenario` | `str` | e.g. `consistent`, `loyalty_candidate`, `declining`, `dormant`, `overdue_courteous`, `no_consent`, `recent_contact`, `ineligible_reward`, `contradictory_billing` |
| `expected_primary_segment` | `SegmentName \| null` | |
| `expected_status` | `DecisionStatus` | `draft_allowed` or `blocked` |
| `expected_block_reasons` | `list[BlockReason]` | `[]` when allowed |
| `expected_reminder_stage` | `str \| null` | Stage name for reminders |
| `expected_offer_id` | `str \| null` | Eligible offer, or `null` |

Example:
`{"customer_id": "CUST-009", "scenario": "overdue_courteous", "expected_primary_segment": "payment_reminder", "expected_status": "draft_allowed", "expected_block_reasons": [], "expected_reminder_stage": "courteous", "expected_offer_id": null}`
