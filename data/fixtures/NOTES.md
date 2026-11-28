# Fixture notes (Member 5)

All data is synthetic. `as_of_date` is 2026-11-28 (`data/policies/policy.yaml`).
For overdue rows, `due_date = as_of_date - days_overdue`. No value sits on a
threshold boundary; boundary tests belong to `policy_engine/tests`.

## Label semantics (`scenarios.jsonl`)

- `expected_primary_segment`: primary segment from classification by the `priority`
  list in `segments.yaml`. Classification runs even when outreach is blocked, so a
  blocked row still has a primary segment (`null` only when no rule matches).
- `expected_reminder_stage` and `expected_offer_id`: what ends up in
  `PolicyDecision.facts` (`reminder.stage`, `offer.offer_id`). A blocked decision
  carries no facts, so both are `null` for every blocked row.
- `expected_block_reasons`: the complete list (order irrelevant) of `BlockReason`s.

## Rule interpretation used to derive the labels

Thresholds from `segments.yaml`, offers from `offers.yaml`, stages from `reminders.yaml`,
gates from `policy.yaml` and `docs/members/MEMBER_3_POLICY.md`.

| Segment | Rule as interpreted |
|---|---|
| payment_reminder | `bill_status == overdue` and `days_overdue >= 1` |
| dormant | `activity_score_30d < 15` |
| declining | drop from `activity_score_prev_30d` to `activity_score_30d` is at least 30% |
| loyalty_candidate | `months_active >= 24`, `on_time_payments_12m >= 11`, `activity_score_30d >= 60`, bill not overdue |
| consistent | `on_time_payments_12m >= 11` and `activity_score_30d >= 40` |

Offer: segment in `allowed_segments`, `months_active >= min_months_active`,
`expiry >= as_of_date`, channel `email`, strategy `offer_allowed`.
Gates: consent (reminders exempt), `last_contacted_days_ago < 14`, contradictory billing,
overdue without `due_date`/amount, no segment.

## Rows

| ID | Scenario | Key values | Label reasoning |
|---|---|---|---|
| CUST-001 | consistent | on_time 12, act 55 (prev 58), 18 mo | consistent only (tenure and activity below loyalty) |
| CUST-002 | consistent | on_time 11, act 50, 36 mo, bill `due` (not overdue) | consistent; loyalty fails activity 50 < 60 |
| CUST-003 | loyalty_candidate | 48 mo, on_time 12, act 82 | loyalty + consistent, primary loyalty; LOYAL-10GB (48 >= 24, expiry 2027-01-31) |
| CUST-004 | loyalty_candidate | 30 mo, on_time 11, act 70 | as above |
| CUST-005 | declining | act 30 vs 65 (-54%), 14 mo | declining; REENGAGE-20 (14 >= 3, expiry 2026-12-31) |
| CUST-006 | declining | act 42 vs 75 (-44%), on_time 12, 40 mo | declining (+ consistent), primary declining; REENGAGE-20 |
| CUST-007 | dormant | act 8 vs 10 (-20%), 20 mo | dormant only; WINBACK-300 (20 >= 6) |
| CUST-008 | dormant | act 3 vs 25 (-88%), 9 mo | dormant + declining, primary dormant; WINBACK-300 (9 >= 6) |
| CUST-009 | overdue_courteous | 4 days, 649.00 | stage courteous (1-7) |
| CUST-010 | overdue_firm | 15 days, 1199.00 | stage firm (8-21) |
| CUST-011 | overdue_final_notice | 30 days, 2000.00, contacted 21 days ago | stage final_notice (22+) |
| CUST-012 | no_consent | consistent profile, consent false | blocked `no_marketing_consent` |
| CUST-013 | recent_contact | consistent profile, contacted 5 days ago | blocked `contacted_too_recently` (5 < 14); loyalty fails tenure 20 < 24 |
| CUST-014 | overdue_no_consent | consent false, 10 days, 780.00 | reminder allowed (`reminders_require_marketing_consent: false`), stage firm |
| CUST-015 | ineligible_reward | act 20 vs 60 (-67%), 2 mo | declining, allowed, REENGAGE-20 fails `min_tenure` (2 < 3) so no offer |
| CUST-016 | contradictory_billing | `paid` with `days_overdue` 12 | blocked `contradictory_billing_data`; primary consistent (not overdue, so no reminder segment) |
| CUST-017 | missing_evidence | `overdue` 9 days, 850.00, no `due_date` | blocked `missing_evidence`; primary payment_reminder |
| CUST-018 | prompt_injection_name | instruction-like `first_name`, consistent profile | consistent, allowed, no offer: the name must not change any decision |
| CUST-019 | no_actionable_segment | act 30 vs 35 (-14%), on_time 8 | no rule matches; blocked `no_actionable_segment` |

## Assumptions to confirm with Member 3

1. `payment_reminder` requires `bill_status == overdue` (CUST-016 is therefore primary
   `consistent`, not `payment_reminder`).
2. `consistent` does not exclude customers who are also declining (CUST-006); this only
   affects the secondary segment, not the primary label.
3. An allowed decision with no eligible offer is still `draft_allowed` (CUST-015).

## `bad_drafts.jsonl`

Each line: `case_id`, `customer_id`, `defect`, `draft` (`DraftContent`), and
`expected_finding_codes`. The validator must report **at least** these codes as
blocking findings (it may report more, e.g. an invented offer may also trip a number
check). BAD-13/14 target customers whose decision is blocked, to exercise
`consent_gap` / `duplicate_outreach`. The only email address in any fixture is the
deliberate `example.com` address in BAD-08 (sensitive-data detection); none appears in
`customers.csv`.
