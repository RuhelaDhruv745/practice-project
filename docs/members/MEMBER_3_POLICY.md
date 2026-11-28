# Member 3: Policy / Decision Engineer

Name: <fill in>

| | |
|---|---|
| Branch | `feature/policy-engine` |
| Worktree | `../team-policy` |
| Owns | `policy_engine/` (including validators in `policy_engine/compliance/`), `data/policies/`, `data/campaigns/` |
| Must not modify | `contracts/`, `backend/`, `ai_engine/`, `data/synthetic/`, `data/fixtures/`, `frontend/`, `reviewer_ui/`, root `tests/`, `infrastructure/`, `scripts/`, `.github/`, `.claude/`, `docs/`, root config files |
| Provides | `PolicyEngine.classify / decide / validate` (`contracts/interfaces.py`) |
| Consumes | `contracts.models`, `contracts.enums`, `data/policies/*.yaml`, `data/synthetic/customers.csv` and `data/fixtures/scenarios.jsonl` (for tests) |

## Head start
`policy_engine/config_loader.py` already loads and cross-checks the policy files
(`policy`, `segments`, `strategies`, `offers`, `reminders`, `blocked_terms`, and `validation` since Sprint 2) with 19
tests in `policy_engine/tests/test_config_loader.py`. Extend it; keep those tests green.

## Responsibilities
Every business fact is decided here, deterministically, with no LLM call: segments,
reason codes, confidence, strategy, offer eligibility, reminder stage, consent,
contact frequency, refusal, and independent validation of drafts. All thresholds stay
in YAML.

## Deliverables
- [ ] `policy_engine/classification/`: rules for `consistent`, `loyalty_candidate`, `declining`, `dormant`, `payment_reminder` using `segments.yaml` thresholds; multiple segments allowed; primary chosen by `priority`. Each segment has `ReasonCode`s with the evidence fields and values used.
- [ ] Confidence: deterministic and documented in a module docstring (suggested: start from 1.0 and reduce by how close the deciding value is to its threshold, clamped to [0.5, 1.0]). Same input, same output.
- [ ] `policy_engine/strategies/`: segment → `Strategy` from `strategies.yaml` (with tone guidance). For `payment_reminder`, the reminder stage tone wins.
- [ ] `policy_engine/eligibility/`: one `OfferCheck` per configured offer (eligible or not, with `failed_rules`): allowed segment, `months_active >= min_months_active`, `expiry >= as_of_date`, `channel == email`, strategy allows offers. At most one eligible offer goes into the facts.
- [ ] `policy_engine/billing/`: stage from `days_overdue` and `reminders.yaml`; builds `ReminderFacts` (amount, currency, due date, stage, support path).
- [ ] Gates in `decide`, each recorded as a `BlockReason`:
  - no marketing consent → `no_marketing_consent` (payment reminders exempt when `reminders_require_marketing_consent: false`),
  - `last_contacted_days_ago < min_days_between_contacts` → `contacted_too_recently`,
  - contradictory billing (e.g. `paid` with `days_overdue > 0`, `overdue` with `days_overdue == 0` or `amount_due == 0`) → `contradictory_billing_data`,
  - overdue without `due_date` or amount → `missing_evidence`,
  - no segment → `no_actionable_segment`.
- [ ] `VerifiedFacts` builder: only the fields the generator needs; nothing else from the profile.
- [ ] `policy_engine/compliance/`: `validate(draft, decision)` running every `FindingCode`:
  - amounts and numbers in text must match facts (amount due, offer value); dates must match due date or offer expiry,
  - offer IDs must be the eligible one (`unknown_offer`, `ineligible_offer`),
  - offers or discounts mentioned with no offer in facts → `unsupported_claim`,
  - blocked terms matched case-insensitively as **whole words/phrases** ("court" must not match "courteous"),
  - reminders must contain the support path → `missing_support_path`,
  - decision blocked for consent/frequency → `consent_gap` / `duplicate_outreach`,
  - email addresses or phone numbers other than the configured support number → `sensitive_data`,
  - `schema_invalid` for empty or oversize fields.
  Version the validator (`validator_version`).
- [ ] `policy_engine/engine.py`: class implementing `contracts.interfaces.PolicyEngine`, constructed from a loaded policy.

## Working around dependencies
You depend only on `contracts/` and YAML. Until Member 5's CSV lands, build `CustomerProfile` objects in tests. Afterwards, add a test that runs every row of `scenarios.jsonl` through `decide` and compares the expected segment/outcome.

## Testing requirements
- `policy_engine/tests/`: boundaries for every threshold (exactly 30% drop, activity 14.99 vs 15, 7/8 and 21/22 days overdue, tenure 23/24, expiry on `as_of_date`), each block reason, multi-segment priority, each `FindingCode` with a deliberately bad draft, whole-word matching, injection text in `first_name` has no effect on decisions.
- Run: `python -m pytest policy_engine/tests -q`, `python -m ruff check policy_engine`.

## Definition of done
Rules deterministic, documented and unit-tested; no LLM dependency; thresholds only in YAML; every bad-draft case blocked; only owned paths changed.

## Commit examples
`feat(policy): add reminder stage selection` · `feat(policy): add whole-word blocked term check` · `test(policy): cover 7/8 day boundary`

## Integration
Merges second, after backend foundation. Member 1 swaps `FakePolicyEngine` for yours. See `docs/INTEGRATION_GUIDE.md`.

## Startup prompt
```text
You are Member 3 (Policy/Decision) in a five-member team. Read, in order: CLAUDE.md,
docs/members/MEMBER_3_POLICY.md, docs/ARCHITECTURE.md, docs/API_CONTRACTS.md,
docs/DATA_DICTIONARY.md, docs/TEAM_ASSIGNMENTS.md.
Check you are on branch feature/policy-engine in worktree ../team-policy. Give me a
short implementation plan first and wait for my OK. Implement only paths under
policy_engine/, data/policies/ and data/campaigns/. Implement
contracts.interfaces.PolicyEngine deterministically, with no LLM calls and all
thresholds in YAML. Keep the existing config_loader tests green. Write tests with each
change, run python -m pytest policy_engine/tests -q and python -m ruff check
policy_engine, review the changed-file list (git diff --name-only main...HEAD), commit
with conventional commits, push only feature/policy-engine, and open a PR to main.
Finish with the completion report from my member file. Report failures honestly.
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
