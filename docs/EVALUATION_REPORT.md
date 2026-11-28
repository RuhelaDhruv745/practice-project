# Evaluation Report

Owner: **Member 5**. Status: **template, nothing has been run yet.**

Rules: report only measurements that were actually run, generated from test output by
the evaluation harness in `tests/evaluation/`. Every row states its sample size. Never
fill a cell by hand with an estimate.

- Run date: not yet run
- Commit: not yet run
- Policy versions: not yet run
- LLM provider / model / prompt version: not yet run
- Command: `python -m pytest tests/evaluation` (planned)

## Results by measure (from docs/problem-statement.md)

| Measure | Method | Target (proposed) | Sample size (n) | Result | Status |
|---|---|---|---|---|---|
| Segment accuracy | Predicted primary segment vs labelled `scenarios.jsonl` | All six PS scenarios correct | not yet run | not yet run | not yet run |
| Grounded drafts | Every amount, date and offer ID in approved drafts matches the source data | No mismatches | not yet run | not yet run | not yet run |
| Validator catch rate | Deliberately bad drafts (invented offer, wrong amount, wrong date, blocked term, missing support path) through `PolicyEngine.validate` | Every bad draft blocked | not yet run | not yet run | not yet run |
| Blocked cases | No-consent and recently-contacted customers | Blocked every time, with a reason | not yet run | not yet run | not yet run |
| Reminder stage | Days overdue vs chosen stage, including the boundaries 1/7/8/21/22 | Correct in every test | not yet run | not yet run | not yet run |
| Reviewer rubric | Reviewer scores relevance, clarity, personalisation, call to action and tone (1–5) | Reported as an average | not yet run | not yet run | not yet run |

## Additional cases (playbook)

| Case | Expected | n | Result |
|---|---|---|---|
| Ineligible reward | Offer excluded, failed rules listed | not yet run | not yet run |
| Contradictory billing data | Blocked, `contradictory_billing_data` | not yet run | not yet run |
| Missing evidence | Blocked, `missing_evidence` | not yet run | not yet run |
| Prompt injection text in customer data | Treated as data; validators still pass or block correctly | not yet run | not yet run |
| Approve after failed validation | `409 review_not_approvable`, no outbox record | not yet run | not yet run |

## Per-scenario detail

| Scenario ID | Expected segment / outcome | Predicted | Decision | Validation | Notes |
|---|---|---|---|---|---|
| not yet run | | | | | |

## Known limitations
- Synthetic data and a small scenario set: results do not show real-world accuracy.
- Thresholds are assumptions in `data/policies/`, not learned from data.
- Rubric scores come from team members, not independent reviewers; the sample is small.
- LLM output varies between runs; the evaluation records the provider, model and prompt version.
