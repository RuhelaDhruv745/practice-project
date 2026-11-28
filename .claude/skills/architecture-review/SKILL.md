---
name: architecture-review
description: Review a proposed design, contract change or PR against the project architecture - code decides facts, LLM only words, validation before review, approval before mock delivery, exclusive ownership. Use before approving a contract change or merging a cross-module PR.
---

# Architecture review

1. Read `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/API_CONTRACTS.md`, `docs/DATA_DICTIONARY.md`, `docs/TEAM_ASSIGNMENTS.md` and `contracts/`.
2. Identify what is proposed or changed: files, modules, contracts, endpoints.
3. Check the fact boundary: segment, eligibility, stage, amounts, dates, consent and frequency are computed only in `policy_engine`; `ai_engine` sees only `VerifiedFacts`.
4. Check the gates: every draft (generated or edited) goes through `PolicyEngine.validate`; approve requires `pending_review` + passed validation + `draft_allowed`; delivery is mock only.
5. Check contracts: no redefined models; endpoint paths, codes and error codes match; any contract change updates `contracts/`, both docs and tests in one PR with a version bump.
6. Check ownership: every changed path belongs to the author (`docs/TEAM_ASSIGNMENTS.md`).
7. Check policy lives in `data/policies/*.yaml`, not code; no protected attributes or proxies.
8. Check complexity: no new infrastructure (queue, vector DB, extra DB) without a requirement.
9. Report: verdict (approve / changes needed / reject), findings most severe first with `file:line`, and options with a recommendation for any open decision.
