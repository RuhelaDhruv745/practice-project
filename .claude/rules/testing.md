---
paths:
  - "**/tests/**"
  - "tests/**"
  - "frontend/**/*.test.*"
---

# Testing rules

- Run `python -m pytest` (or your module's tests) after every code change, and report the actual result.
- Tests never call a real LLM API. Mock the provider or use a fake `DraftGenerator`.
- Tests never need network access or an API key; CI has none.
- Unit tests live in the owning module (`<module>/tests/`). Cross-module tests live in root `tests/` (Member 5).
- Cover boundaries explicitly: 7/8 and 21/22 days overdue, exactly 30% activity drop, offer expiry on `as_of_date`, minimum tenure.
- Every blocked path needs a test asserting the block reason, not just "not sent".
- Use synthetic fixtures from `data/fixtures/` or build contract objects in the test. No real data.
- Never weaken a test or edit data/config to make a test pass. Fix the code or report the failure.
- Never report a metric you did not compute from an actual test run.
