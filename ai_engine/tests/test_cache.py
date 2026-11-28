"""Dev response cache: opt-in, keyed by (prompt version, provider, model, facts)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_engine.generation import (
    DraftCache,
    LLMDraftGenerator,
    MockProvider,
    PromptRequest,
    cache_from_env,
    cache_key,
)
from ai_engine.generation.providers import build_mock_draft
from contracts.models import VerifiedFacts


class CountingProvider:
    """A 'live' provider stub: returns a valid draft and counts calls."""

    name = "anthropic"

    def __init__(self, model: str = "claude-test", reply: str | None = None) -> None:
        self.model = model
        self.calls = 0
        self._reply = reply

    def complete(self, request: PromptRequest) -> str:
        self.calls += 1
        if self._reply is not None:
            return self._reply
        return json.dumps(build_mock_draft(request.facts))


def test_cache_off_by_default() -> None:
    assert cache_from_env({}) is None
    assert cache_from_env({"LLM_CACHE": "0"}) is None


def test_cache_off_in_tests_by_env() -> None:
    generator = LLMDraftGenerator(provider=CountingProvider())
    assert generator.cache is None


def test_cache_enabled_from_env(tmp_path: Path) -> None:
    cache = cache_from_env({"LLM_CACHE": "1", "LLM_CACHE_DIR": str(tmp_path)})
    assert isinstance(cache, DraftCache)
    assert cache.directory == tmp_path


def test_env_cache_used_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LLM_CACHE", "true")
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path))
    generator = LLMDraftGenerator(provider=CountingProvider())
    assert isinstance(generator.cache, DraftCache)


def test_second_call_is_served_from_cache(
    tmp_path: Path, reminder_facts: VerifiedFacts
) -> None:
    provider = CountingProvider()
    generator = LLMDraftGenerator(provider=provider, cache=DraftCache(tmp_path))
    first = generator.generate(reminder_facts)
    second = generator.generate(reminder_facts)
    assert provider.calls == 1
    assert second.draft == first.draft
    assert second.message_id != first.message_id
    assert (second.provider, second.model, second.prompt_version) == (
        "anthropic",
        "claude-test",
        "draft_v1",
    )
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_cache_file_holds_no_prompt(
    tmp_path: Path, reminder_facts: VerifiedFacts
) -> None:
    generator = LLMDraftGenerator(
        provider=CountingProvider(), cache=DraftCache(tmp_path)
    )
    generator.generate(reminder_facts)
    (entry,) = tmp_path.glob("*.json")
    record = json.loads(entry.read_text(encoding="utf-8"))
    assert set(record) == {"subject", "body", "prompt_version", "provider", "model"}


def test_key_changes_with_model_version_and_facts(
    thanks_facts: VerifiedFacts, reward_facts: VerifiedFacts
) -> None:
    base = {"prompt_version": "draft_v1", "provider": "anthropic", "model": "m1"}
    key = cache_key(facts=thanks_facts, **base)
    assert key == cache_key(facts=thanks_facts, **base)
    assert key != cache_key(facts=reward_facts, **base)
    assert key != cache_key(facts=thanks_facts, **{**base, "model": "m2"})
    assert key != cache_key(facts=thanks_facts, **{**base, "prompt_version": "v2"})
    assert key != cache_key(facts=thanks_facts, **{**base, "provider": "groq"})


def test_model_change_is_a_miss(tmp_path: Path, thanks_facts: VerifiedFacts) -> None:
    first = CountingProvider(model="m1")
    LLMDraftGenerator(provider=first, cache=DraftCache(tmp_path)).generate(thanks_facts)
    second = CountingProvider(model="m2")
    LLMDraftGenerator(provider=second, cache=DraftCache(tmp_path)).generate(
        thanks_facts
    )
    assert (first.calls, second.calls) == (1, 1)


def test_mock_provider_never_cached(
    tmp_path: Path, thanks_facts: VerifiedFacts
) -> None:
    generator = LLMDraftGenerator(provider=MockProvider(), cache=DraftCache(tmp_path))
    assert generator.cache is None
    generator.generate(thanks_facts)
    assert not list(tmp_path.iterdir())


def test_failed_generation_is_not_cached(
    tmp_path: Path, thanks_facts: VerifiedFacts
) -> None:
    from contracts.interfaces import GenerationError

    provider = CountingProvider(reply="not json")
    generator = LLMDraftGenerator(provider=provider, cache=DraftCache(tmp_path))
    with pytest.raises(GenerationError):
        generator.generate(thanks_facts)
    assert not list(tmp_path.glob("*.json"))


def test_corrupt_entry_is_a_miss(tmp_path: Path, thanks_facts: VerifiedFacts) -> None:
    provider = CountingProvider()
    generator = LLMDraftGenerator(provider=provider, cache=DraftCache(tmp_path))
    key = generator._cache_key(thanks_facts)
    (tmp_path / f"{key}.json").write_text("{broken", encoding="utf-8")
    message = generator.generate(thanks_facts)
    assert provider.calls == 1
    assert message.draft.subject


def test_ungrounded_cache_entry_is_not_trusted(
    tmp_path: Path, reminder_facts: VerifiedFacts
) -> None:
    provider = CountingProvider()
    cache = DraftCache(tmp_path)
    generator = LLMDraftGenerator(provider=provider, cache=cache)
    key = generator._cache_key(reminder_facts)
    (tmp_path / f"{key}.json").write_text(
        json.dumps({"subject": "Hi", "body": "No facts here."}), encoding="utf-8"
    )
    message = generator.generate(reminder_facts)
    assert provider.calls == 1
    assert reminder_facts.reminder is not None
    assert reminder_facts.reminder.support_path in message.draft.body
