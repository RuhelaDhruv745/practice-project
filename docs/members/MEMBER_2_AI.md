# Member 2: AI / LLM Engineer

Name: <fill in>

| | |
|---|---|
| Branch | `feature/ai-engine` |
| Worktree | `../team-ai` |
| Owns | `ai_engine/` (including `ai_engine/requirements.txt` and prompt templates) |
| Must not modify | `contracts/`, `backend/`, `policy_engine/`, `data/`, `frontend/`, `reviewer_ui/`, root `tests/`, `infrastructure/`, `scripts/`, `.github/`, `.claude/`, `docs/`, root config files |
| Provides | `DraftGenerator.generate(facts) -> GeneratedMessage` (`contracts/interfaces.py`), raising `GenerationError` |
| Consumes | `contracts.models.VerifiedFacts`, `DraftContent`, `GeneratedMessage` |

## Responsibilities
Turn `VerifiedFacts` into a subject and body. You **word** the message; you never
decide segment, offer, stage, amount or date, and you never see the full profile.
Validation is Member 3's job; do not grade your own output as the final check.

## Deliverables
- [ ] `ai_engine/generation/providers.py`: one provider interface with
  - `AnthropicProvider` (default, `anthropic` SDK),
  - `GroqProvider` (fallback, `openai` SDK with `LLM_BASE_URL`),
  - `MockProvider`: deterministic draft built from the facts, used when no API key is set and in all tests.
- [ ] Selection from env: `LLM_PROVIDER` (`anthropic` | `groq` | `mock`), `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_TIMEOUT_SECONDS`. Names go into `.env.example` via a request to the architect. Never read or print `.env` contents in logs.
- [ ] `ai_engine/prompts/`: versioned templates (e.g. `draft_v1.txt`) plus `PROMPT_VERSION`. Tone guidance comes from `facts.tone_guidance`.
- [ ] Prompt rules: use only the supplied facts; customer-supplied text (`first_name`, plan names, campaign text) is placed inside a clearly fenced data block and labelled "data, not instructions"; no invented offers, amounts, dates or discounts; reminders must include `support_path` verbatim; output JSON `{"subject": ..., "body": ...}` only.
- [ ] `ai_engine/generation/generator.py`: `DraftGenerator` implementation returning `GeneratedMessage` (provider, model, prompt version, timestamp).
- [ ] Parsing: strict JSON → `DraftContent`; on malformed or extra fields, **retry once**, then raise `GenerationError`.
- [ ] Timeouts and retry with exponential backoff for rate limits and 5xx (bounded, e.g. 3 attempts).
- [ ] Dev response cache keyed by hash of (prompt version, model, facts), on disk under `outputs/` (git-ignored), off by default in tests.
- [ ] `ai_engine/grounding/`: fact packing (render only facts present; omit `offer`/`reminder` blocks when null) and a pre-check that the required fact strings (amount, due date, offer ID, support path) appear; failure triggers the retry.
- [ ] `ai_engine/evaluation/`: script that runs every scenario's facts through the generator (mock or live) and records how many drafts parse and pass Member 3's validators. Report measured numbers only.

## Working around dependencies
Member 3's `decide` builds `VerifiedFacts` for real. Until it merges, build `VerifiedFacts` by hand in tests for each segment (thanks, reward offer, re-engage offer, win-back offer, each reminder stage). For validation during evaluation, call `policy_engine` only after it merges; before that, report parse rate only.

## Testing requirements
- `ai_engine/tests/`, all using `MockProvider` or a stub client. **No real API calls in tests.**
- Cases: valid JSON parsed; malformed JSON retried once then `GenerationError`; extra keys (e.g. `offer_id`) rejected; timeout/backoff path; prompt contains no field absent from facts; injection text in `first_name` stays inside the data fence; reminder prompt includes the support path; provider selection from env; mock provider is deterministic.
- Run: `python -m pytest ai_engine/tests -q`, `python -m ruff check ai_engine`.

## Definition of done
Output schema validates; nothing outside facts is requested or produced; missing evidence and provider failure handled with `GenerationError`; tests cover normal, retry, refusal/fallback; no keys in code or logs; only `ai_engine/` changed.

## Commit examples
`feat(ai): add anthropic provider with timeout and backoff` · `test(ai): cover malformed JSON retry` · `feat(ai): add draft prompt v1`

## Integration
Merges third (after backend foundation and policy). Member 1 wires your generator into `create_app`. See `docs/INTEGRATION_GUIDE.md`.

## Startup prompt
```text
You are Member 2 (AI/LLM) in a five-member team. Read, in order: CLAUDE.md,
docs/members/MEMBER_2_AI.md, docs/ARCHITECTURE.md, docs/API_CONTRACTS.md,
docs/DATA_DICTIONARY.md, docs/TEAM_ASSIGNMENTS.md.
Check you are on branch feature/ai-engine in worktree ../team-ai. Give me a short
implementation plan first and wait for my OK. Implement only paths under ai_engine/.
Implement contracts.interfaces.DraftGenerator using VerifiedFacts only; never decide
facts. Never call a real API in tests; never read or print .env. Write tests with each
change, run python -m pytest ai_engine/tests -q and python -m ruff check ai_engine,
review the changed-file list (git diff --name-only main...HEAD), commit with
conventional commits, push only feature/ai-engine, and open a PR to main. Finish with
the completion report from my member file. Report failures honestly.
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
