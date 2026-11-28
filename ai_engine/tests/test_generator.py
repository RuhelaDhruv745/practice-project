from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from ai_engine.generation.generator import (
    DraftParseError,
    LLMDraftGenerator,
    parse_draft,
)
from ai_engine.generation.providers import MockProvider, PromptRequest, ProviderError
from ai_engine.prompts import PROMPT_VERSION
from ai_engine.tests import factories
from contracts.interfaces import DraftGenerator, GenerationError
from contracts.models import GeneratedMessage, VerifiedFacts

FIXED_NOW = datetime(2026, 11, 28, 9, 30, tzinfo=UTC)
VALID = json.dumps(
    {"subject": "Thank you, Asha", "body": "Hi Asha, thanks for staying."}
)


class ScriptedProvider:
    """Returns (or raises) scripted replies in order and records every request."""

    name = "stub"
    model = "stub-model-1"

    def __init__(self, replies: list[object]) -> None:
        self.replies = list(replies)
        self.requests: list[PromptRequest] = []

    def complete(self, request: PromptRequest) -> str:
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


def _generator(provider: object) -> LLMDraftGenerator:
    return LLMDraftGenerator(
        provider,  # type: ignore[arg-type]
        clock=lambda: FIXED_NOW,
        id_factory=lambda: "msg-test-1",
    )


# --- parsing -----------------------------------------------------------------


def test_parse_valid_json() -> None:
    draft = parse_draft(VALID)
    assert draft.subject == "Thank you, Asha"
    assert draft.body.startswith("Hi Asha")


def test_parse_tolerates_single_code_fence() -> None:
    assert parse_draft(f"```json\n{VALID}\n```").subject == "Thank you, Asha"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not json",
        f"Sure! Here is your email: {VALID}",
        "[]",
        json.dumps({"subject": "s"}),
        json.dumps({"subject": "s", "body": "b", "offer_id": "LOYAL-10GB"}),
        json.dumps({"subject": "s", "body": 5}),
        json.dumps({"subject": "", "body": "b"}),
        json.dumps({"subject": "x" * 151, "body": "b"}),
        json.dumps({"subject": "s", "body": "b" * 4001}),
    ],
    ids=[
        "empty",
        "prose",
        "prose-wrapped",
        "array",
        "missing-body",
        "extra-key",
        "wrong-type",
        "empty-subject",
        "subject-too-long",
        "body-too-long",
    ],
)
def test_parse_rejects_bad_output(raw: str) -> None:
    with pytest.raises(DraftParseError):
        parse_draft(raw)


def test_extra_key_error_names_the_key() -> None:
    raw = json.dumps({"subject": "s", "body": "b", "offer_id": "X"})
    with pytest.raises(DraftParseError, match="offer_id"):
        parse_draft(raw)


# --- generate ----------------------------------------------------------------


def test_generate_returns_contract_message_with_metadata(thanks_facts) -> None:
    provider = ScriptedProvider([VALID])
    message = _generator(provider).generate(thanks_facts)

    assert isinstance(message, GeneratedMessage)
    assert message.message_id == "msg-test-1"
    assert message.customer_id == thanks_facts.customer_id
    assert message.source == "llm"
    assert message.provider == "stub"
    assert message.model == "stub-model-1"
    assert message.prompt_version == PROMPT_VERSION
    assert message.generated_at == FIXED_NOW
    assert len(provider.requests) == 1


def test_malformed_json_retried_once_then_generation_error(thanks_facts) -> None:
    provider = ScriptedProvider(["not json", "{still not json"])
    with pytest.raises(GenerationError, match="2 attempts"):
        _generator(provider).generate(thanks_facts)
    assert len(provider.requests) == 2


def test_malformed_then_valid_succeeds_with_correction_note(thanks_facts) -> None:
    provider = ScriptedProvider(["oops", VALID])
    message = _generator(provider).generate(thanks_facts)
    assert message.draft.subject == "Thank you, Asha"
    first, second = provider.requests
    assert "rejected" not in first.user
    assert "rejected because the reply was not valid JSON" in second.user
    assert second.system == first.system


def test_extra_keys_rejected_and_never_returned(reward_facts) -> None:
    sneaky = json.dumps(
        {"subject": "Reward", "body": "Offer LOYAL-10GB", "offer_id": "FREE-99"}
    )
    provider = ScriptedProvider([sneaky, sneaky])
    with pytest.raises(GenerationError, match="offer_id"):
        _generator(provider).generate(reward_facts)
    assert len(provider.requests) == 2


def test_ungrounded_reminder_retried_then_generation_error(reminder_facts) -> None:
    ungrounded = json.dumps({"subject": "Bill", "body": "Please pay INR 750 soon."})
    provider = ScriptedProvider([ungrounded, ungrounded])
    with pytest.raises(GenerationError, match="support_path"):
        _generator(provider).generate(reminder_facts)
    assert len(provider.requests) == 2
    assert "did not include these facts verbatim" in provider.requests[1].user


def test_ungrounded_then_grounded_succeeds(reminder_facts) -> None:
    support = reminder_facts.reminder.support_path
    grounded = json.dumps(
        {
            "subject": "A reminder about your bill",
            "body": f"Hi Asha, INR 749.00 was due on 2026-11-20.\n\n{support}",
        }
    )
    ungrounded = json.dumps({"subject": "Bill", "body": "Please pay soon."})
    provider = ScriptedProvider([ungrounded, grounded])
    message = _generator(provider).generate(reminder_facts)
    assert support in message.draft.body


def test_provider_failure_raises_generation_error_without_extra_retry(
    thanks_facts,
) -> None:
    provider = ScriptedProvider([ProviderError("stub request failed (StatusError)")])
    with pytest.raises(GenerationError) as excinfo:
        _generator(provider).generate(thanks_facts)
    assert isinstance(excinfo.value.__cause__, ProviderError)
    assert len(provider.requests) == 1


def test_generator_only_sends_verified_facts(reward_facts) -> None:
    provider = ScriptedProvider([MockProvider().complete(_mock_request(reward_facts))])
    _generator(provider).generate(reward_facts)
    assert provider.requests[0].facts is reward_facts


def _mock_request(facts: VerifiedFacts) -> PromptRequest:
    return PromptRequest(system="", user="", facts=facts)


@pytest.mark.parametrize(
    "facts",
    factories.all_segment_facts(),
    ids=lambda f: f.segment.value + (f"-{f.reminder.stage}" if f.reminder else ""),
)
def test_mock_end_to_end_for_every_segment(facts: VerifiedFacts) -> None:
    generator = LLMDraftGenerator(MockProvider())
    message = generator.generate(facts)
    assert message.provider == "mock"
    assert message.model == "mock-draft-v1"
    assert message.prompt_version == PROMPT_VERSION
    assert message.generated_at.tzinfo is not None
    assert generator.mode == "mock"


def test_mock_generation_is_deterministic(reminder_facts) -> None:
    generator = LLMDraftGenerator(MockProvider())
    assert (
        generator.generate(reminder_facts).draft
        == generator.generate(reminder_facts).draft
    )


def test_satisfies_draft_generator_protocol() -> None:
    generator: DraftGenerator = LLMDraftGenerator(MockProvider())
    assert callable(generator.generate)


def test_default_provider_comes_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_MODEL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "GROQ_API_KEY",
        "GROQ_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    assert LLMDraftGenerator().provider.name == "mock"
