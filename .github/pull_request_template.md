## Summary
<!-- What this PR does, in 1-3 sentences. Link the issue: Closes #N -->

- **Member / role:** <!-- e.g. Member 3, Policy -->
- **Branch:** <!-- e.g. feature/policy-engine -->
- **Requirements covered:** <!-- e.g. FR-02, FR-05 (docs/REQUIREMENTS.md) -->

## Ownership and contracts
- [ ] Every changed path is owned by my role (`git diff --name-only main...HEAD` checked against `docs/TEAM_ASSIGNMENTS.md`)
- [ ] I used models from `contracts/` and did not redefine them
- [ ] No contract change, **or** an approved "Contract or ownership change" issue is linked and `contracts/`, `docs/API_CONTRACTS.md` and `docs/DATA_DICTIONARY.md` are updated together
- [ ] No new dependency, **or** it was approved and added only to my module's requirements file

## Tests (actual results, not estimates)
```
<!-- paste the summary lines, e.g. "42 passed in 1.2s" and "ruff: All checks passed!" -->
```
- [ ] Module tests pass locally
- [ ] `ruff check` and `ruff format --check` are clean
- [ ] No test calls a real LLM API or needs an API key

## Safety checklist
- [ ] No secrets, `.env` files, keys or tokens committed
- [ ] No email addresses or real personal data in code, data, prompts, logs or audit records
- [ ] No protected characteristics or proxies in data or logic
- [ ] Facts (segment, eligibility, stage, amounts, dates) come from `policy_engine`, not the LLM or a UI
- [ ] No path to the mock outbox without validation and human approval; edited drafts re-validated
- [ ] Customer or campaign text treated as data, never instructions

## Completion report
- **Files created:**
- **Files modified:**
- **Features completed:**
- **Tests passed:**
- **Tests failed:**
- **Known limitations:**
- **Integration dependencies:**
- **Commit hash(es):**
