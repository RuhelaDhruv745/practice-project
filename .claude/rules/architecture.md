# Architecture rules

- Code decides facts. Segment, offer eligibility, billing stage, amounts, dates, consent and contact-frequency outcomes come from `policy_engine/` only.
- The LLM only words the message. `ai_engine/` receives `VerifiedFacts` and returns `DraftContent` (`subject`, `body`). It never sees `CustomerProfile` and never chooses offers or stages.
- Every draft, generated or human-edited, passes `PolicyEngine.validate` before it can be approved. A blocking finding blocks it.
- Approval and delivery gating lives only in `backend/`. `reviewer_ui/` and `frontend/` are thin HTTP clients with no business logic.
- Delivery is a mock outbox. No code path sends real email.
- Policy values (thresholds, segments, offers, tones, reminder stages, blocked terms) live in `data/policies/*.yaml`, never hardcoded.
- The backend depends on the `Protocol`s in `contracts/interfaces.py`, not on concrete classes.
- Keep the stack small: no vector DB, queue, Kubernetes or extra databases without an approved requirement.
- Detail: `docs/ARCHITECTURE.md`, `docs/API_CONTRACTS.md`, `docs/DATA_DICTIONARY.md`.
