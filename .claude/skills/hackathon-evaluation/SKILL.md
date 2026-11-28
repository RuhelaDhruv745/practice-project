---
name: hackathon-evaluation
description: Run the scenario evaluation and fill docs/EVALUATION_REPORT.md with measured results only - segment accuracy, groundedness, validator catch rate, blocked cases, reminder stages and reviewer rubric. Use before the demo and after any policy or prompt change.
---

# Hackathon evaluation

1. Confirm inputs exist: `data/fixtures/scenarios.jsonl`, `data/synthetic/customers.csv`, `data/policies/*.yaml`. If missing, say which and stop.
2. Run the evaluation tests (`python -m pytest tests/evaluation -q`) with the LLM mocked; record pass/fail counts exactly.
3. Segment accuracy: predicted primary segment vs label for every scenario; report `correct / total`.
4. Blocked cases: every no-consent, recently-contacted, contradictory and missing-evidence case blocked with the expected `BlockReason`; report counts.
5. Reminder stage: chosen stage vs days overdue for every overdue case, including boundaries.
6. Validator catch rate: run the deliberately bad drafts (invented offer, wrong amount, wrong date, blocked term, missing support path); report `blocked / total`.
7. Groundedness: for approved drafts, every amount, date and offer ID matches the facts; report mismatches.
8. Reviewer rubric: average of real reviewer scores (relevance, clarity, personalisation, call to action, tone) with sample size; if none were collected, say so.
9. Update `docs/EVALUATION_REPORT.md` with the numbers, the number of cases, the date, policy versions, and known limitations (synthetic data, small set, assumed thresholds).
10. Never estimate or round up a metric that was not run.
