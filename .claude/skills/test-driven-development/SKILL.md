---
name: test-driven-development
description: Red-green-refactor loop for this project, with boundary cases, block reasons and a mocked LLM. Use while implementing any rule, endpoint, validator or generator behaviour.
---

# Test-driven development

1. Pick one behaviour from your member spec or `docs/REQUIREMENTS.md` (note the FR ID).
2. Write a failing test in your module's `tests/` that states the expected outcome using `contracts/` models. Include the boundary values (e.g. 7/8 and 21/22 days overdue, exactly 30% drop, expiry equal to `as_of_date`).
3. Run it and confirm it fails for the right reason: `python -m pytest <module> -q -k <name>`.
4. Write the smallest code that passes. Policy values come from `data/policies/*.yaml`, never literals in code.
5. Run the module tests again; all must pass.
6. Refactor with tests green; run `python -m ruff format .` and `python -m ruff check .`.
7. For every refusal path, assert the specific `BlockReason` or `FindingCode`, not just "not sent".
8. LLM work: mock the provider client; test malformed JSON, extra fields, retry-once then `GenerationError`.
9. Record the actual pass/fail counts for your completion report. Never invent results.
