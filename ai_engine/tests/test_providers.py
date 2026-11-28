from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import httpx
import openai
import pytest

from ai_engine.generation.prompt_builder import render_prompt
from ai_engine.generation.providers import (
    AnthropicProvider,
    GroqProvider,
    MockProvider,
    PromptRequest,
    ProviderConfigError,
    ProviderError,
    RetryPolicy,
    is_retryable_error,
    provider_from_env,
)
from ai_engine.grounding.facts import missing_required_facts
from ai_engine.tests import factories
from contracts.models import DraftContent, VerifiedFacts

FAKE_KEY = "test-key-not-real-0000"


class StatusError(Exception):
    """Stands in for an SDK APIStatusError (only status_code matters)."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


def _request(facts: VerifiedFacts | None = None) -> PromptRequest:
    facts = facts or factories.make_facts()
    system, user = render_prompt(facts)
    return PromptRequest(system=system, user=user, facts=facts)


def _anthropic_reply(text: str) -> SimpleNamespace:
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def _groq_reply(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


class StubCreate:
    """Callable stub for ``client.messages.create`` / ``chat.completions.create``."""

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    def __call__(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _anthropic(
    outcomes: list[object], sleeps: list[float]
) -> tuple[AnthropicProvider, StubCreate]:
    create = StubCreate(outcomes)
    provider = AnthropicProvider(
        model="claude-test",
        client=SimpleNamespace(messages=SimpleNamespace(create=create)),
        retry=RetryPolicy(max_attempts=3, base_delay_seconds=0.5, max_delay_seconds=8),
        sleep=sleeps.append,
    )
    return provider, create


def _groq(
    outcomes: list[object], sleeps: list[float]
) -> tuple[GroqProvider, StubCreate]:
    create = StubCreate(outcomes)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    provider = GroqProvider(model="groq-test", client=client, sleep=sleeps.append)
    return provider, create


def _facts_id(facts: VerifiedFacts) -> str:
    suffix = f"-{facts.reminder.stage}" if facts.reminder else ""
    return facts.segment.value + suffix


# --- mock --------------------------------------------------------------------


def test_mock_provider_is_deterministic() -> None:
    request = _request(factories.reward_facts())
    first = MockProvider().complete(request)
    second = MockProvider().complete(request)
    assert first == second
    assert set(json.loads(first)) == {"subject", "body"}


@pytest.mark.parametrize("facts", factories.all_segment_facts(), ids=_facts_id)
def test_mock_draft_is_grounded_for_every_segment(facts: VerifiedFacts) -> None:
    draft = DraftContent.model_validate_json(MockProvider().complete(_request(facts)))
    assert missing_required_facts(draft, facts) == []
    assert facts.first_name in draft.body


def test_mock_mentions_no_offer_when_facts_have_none() -> None:
    draft = json.loads(MockProvider().complete(_request()))
    assert "offer" not in draft["body"].lower()


# --- anthropic ---------------------------------------------------------------


def test_anthropic_returns_text_and_sends_system_prompt() -> None:
    sleeps: list[float] = []
    provider, create = _anthropic(
        [_anthropic_reply('{"subject":"s","body":"b"}')], sleeps
    )
    request = _request()
    assert provider.complete(request) == '{"subject":"s","body":"b"}'
    call = create.calls[0]
    assert call["model"] == "claude-test"
    assert call["system"] == request.system
    assert call["messages"] == [{"role": "user", "content": request.user}]
    assert sleeps == []


def test_backoff_on_rate_limit_and_5xx_then_success() -> None:
    sleeps: list[float] = []
    provider, create = _anthropic(
        [StatusError(429), StatusError(503), _anthropic_reply("ok")], sleeps
    )
    assert provider.complete(_request()) == "ok"
    assert len(create.calls) == 3
    assert sleeps == [0.5, 1.0]  # exponential


def test_backoff_is_bounded_then_provider_error() -> None:
    sleeps: list[float] = []
    provider, create = _anthropic([StatusError(429)] * 5, sleeps)
    with pytest.raises(ProviderError, match="after 3 attempts"):
        provider.complete(_request())
    assert len(create.calls) == 3
    assert sleeps == [0.5, 1.0]


def test_timeout_is_retried() -> None:
    sleeps: list[float] = []
    provider, _ = _anthropic([TimeoutError(), _anthropic_reply("ok")], sleeps)
    assert provider.complete(_request()) == "ok"
    assert sleeps == [0.5]


def test_client_error_is_not_retried() -> None:
    sleeps: list[float] = []
    provider, create = _anthropic([StatusError(400)], sleeps)
    with pytest.raises(ProviderError):
        provider.complete(_request())
    assert len(create.calls) == 1
    assert sleeps == []


def test_backoff_delay_is_capped() -> None:
    policy = RetryPolicy(max_attempts=6, base_delay_seconds=1, max_delay_seconds=4)
    assert [policy.delay_for(a) for a in range(1, 6)] == [1, 2, 4, 4, 4]


def test_sdk_timeout_and_connection_errors_are_retryable() -> None:
    request = httpx.Request("POST", "https://example.invalid")
    assert is_retryable_error(openai.APITimeoutError(request=request))
    assert is_retryable_error(openai.APIConnectionError(request=request))
    assert not is_retryable_error(ValueError("nope"))


# --- groq --------------------------------------------------------------------


def test_groq_uses_chat_completions_json_mode() -> None:
    provider, create = _groq([_groq_reply("{}")], [])
    request = _request()
    assert provider.complete(request) == "{}"
    call = create.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"][0] == {"role": "system", "content": request.system}
    assert call["messages"][1] == {"role": "user", "content": request.user}


def test_groq_backoff_on_rate_limit() -> None:
    sleeps: list[float] = []
    provider, _ = _groq([StatusError(429), _groq_reply("ok")], sleeps)
    assert provider.complete(_request()) == "ok"
    assert sleeps == [1.0]


# --- selection from env -------------------------------------------------------


def test_env_mock_selected_explicitly() -> None:
    provider = provider_from_env({"LLM_PROVIDER": "mock", "LLM_API_KEY": FAKE_KEY})
    assert isinstance(provider, MockProvider)


def test_env_falls_back_to_mock_without_key() -> None:
    assert isinstance(provider_from_env({}), MockProvider)
    assert isinstance(provider_from_env({"LLM_PROVIDER": "groq"}), MockProvider)


def test_env_anthropic_is_default_with_key_and_model() -> None:
    provider = provider_from_env(
        {"LLM_API_KEY": FAKE_KEY, "LLM_MODEL": "claude-x", "LLM_TIMEOUT_SECONDS": "12"}
    )
    assert isinstance(provider, AnthropicProvider)
    assert provider.name == "anthropic"
    assert provider.model == "claude-x"


def test_env_accepts_provider_specific_names() -> None:
    provider = provider_from_env(
        {
            "LLM_PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": FAKE_KEY,
            "ANTHROPIC_MODEL": "claude-y",
        }
    )
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-y"


def test_env_groq_with_base_url() -> None:
    provider = provider_from_env(
        {
            "LLM_PROVIDER": "GROQ",
            "LLM_API_KEY": FAKE_KEY,
            "LLM_MODEL": "llama-test",
            "LLM_BASE_URL": "https://groq.example.invalid/v1",
        }
    )
    assert isinstance(provider, GroqProvider)
    assert provider.model == "llama-test"
    assert provider.base_url == "https://groq.example.invalid/v1"


def test_env_key_without_model_fails_loudly() -> None:
    with pytest.raises(ProviderConfigError, match="LLM_MODEL"):
        provider_from_env({"LLM_PROVIDER": "anthropic", "LLM_API_KEY": FAKE_KEY})


def test_env_unknown_provider_fails_loudly() -> None:
    with pytest.raises(ProviderConfigError):
        provider_from_env({"LLM_PROVIDER": "something-else"})


@pytest.mark.parametrize("value", ["abc", "0", "-5"])
def test_env_bad_timeout_fails_loudly(value: str) -> None:
    with pytest.raises(ProviderConfigError, match="LLM_TIMEOUT_SECONDS"):
        provider_from_env(
            {"LLM_API_KEY": FAKE_KEY, "LLM_MODEL": "m", "LLM_TIMEOUT_SECONDS": value}
        )


def test_api_key_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ai_engine")
    provider_from_env(
        {"LLM_PROVIDER": "groq", "LLM_API_KEY": FAKE_KEY, "LLM_MODEL": "m"}
    )
    provider_from_env({"LLM_PROVIDER": "anthropic"})
    provider, _ = _anthropic([StatusError(429)] * 3, [])
    with pytest.raises(ProviderError) as excinfo:
        provider.complete(_request())
    assert FAKE_KEY not in caplog.text
    assert FAKE_KEY not in str(excinfo.value)
