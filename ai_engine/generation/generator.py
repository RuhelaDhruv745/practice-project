"""DraftGenerator implementation (contracts.interfaces.DraftGenerator).

Flow: render prompt from VerifiedFacts -> provider -> strict JSON parse into
DraftContent -> local grounding pre-check. A malformed, extra-key or ungrounded reply is
retried once with a short correction note; a second failure raises GenerationError.
Transient provider errors are already retried with backoff inside the provider; a
provider failure that survives that raises GenerationError immediately.

The grounding pre-check is a cheap local signal, not approval: PolicyEngine.validate
(Member 3) still checks every draft.

An optional dev cache (``ai_engine.generation.cache``, opt-in via ``LLM_CACHE=1``)
returns a previously accepted draft for identical (prompt version, provider, model,
facts). The mock provider is never cached.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import ValidationError

from ai_engine.generation.cache import DraftCache, cache_from_env, cache_key
from ai_engine.generation.prompt_builder import RETRY_NOTE, render_prompt
from ai_engine.generation.providers import (
    LLMProvider,
    PromptRequest,
    ProviderError,
    provider_from_env,
)
from ai_engine.grounding.facts import missing_required_facts
from ai_engine.prompts import PROMPT_VERSION
from contracts.interfaces import GenerationError
from contracts.models import DraftContent, GeneratedMessage, VerifiedFacts

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2  # first try plus exactly one retry
_ALLOWED_KEYS = frozenset({"subject", "body"})
_CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(?P<inner>.*)\n```$", re.DOTALL)


class DraftParseError(ValueError):
    """The model reply is not exactly a JSON object with string subject and body."""


def parse_draft(raw: str) -> DraftContent:
    """Strictly parse a model reply into DraftContent.

    Accepts one JSON object with exactly ``subject`` and ``body`` (strings). A single
    surrounding markdown code fence is tolerated; any other text, extra keys (for
    example ``offer_id``) or wrong types are rejected.
    """
    text = (raw or "").strip()
    fenced = _CODE_FENCE.match(text)
    if fenced:
        text = fenced.group("inner").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise DraftParseError("the reply was not valid JSON") from None
    if not isinstance(data, dict):
        raise DraftParseError("the reply was not a JSON object")
    keys = set(data)
    if keys != _ALLOWED_KEYS:
        # Key names are model output: bound them before they reach logs or errors.
        extra = [key[:40] for key in sorted(keys - _ALLOWED_KEYS)[:5]]
        missing = sorted(_ALLOWED_KEYS - keys)
        parts = []
        if extra:
            parts.append(f"unexpected keys {extra}")
        if missing:
            parts.append(f"missing keys {missing}")
        raise DraftParseError("the JSON object had " + " and ".join(parts))
    if not all(isinstance(data[k], str) for k in _ALLOWED_KEYS):
        raise DraftParseError("subject and body must both be strings")
    try:
        return DraftContent(subject=data["subject"].strip(), body=data["body"].strip())
    except ValidationError:
        raise DraftParseError(
            "subject or body was empty or too long (subject max 150, body max 4000)"
        ) from None


class _FromEnv:
    """Sentinel: read the cache setting from the process environment."""


_FROM_ENV = _FromEnv()


def _new_message_id() -> str:
    return f"msg-{uuid.uuid4().hex}"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class LLMDraftGenerator:
    """Words a message from VerifiedFacts only. Satisfies DraftGenerator."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        *,
        prompt_version: str = PROMPT_VERSION,
        clock: Callable[[], datetime] = _utc_now,
        id_factory: Callable[[], str] = _new_message_id,
        cache: DraftCache | None | _FromEnv = _FROM_ENV,
    ) -> None:
        self.provider = provider if provider is not None else provider_from_env()
        self.prompt_version = prompt_version
        resolved = cache_from_env() if isinstance(cache, _FromEnv) else cache
        # The mock is deterministic and free, so caching it would only hide changes.
        self.cache = None if self.provider.name == "mock" else resolved
        self._clock = clock
        self._id_factory = id_factory

    @property
    def mode(self) -> str:
        """``mock`` or ``live``, for the backend's health endpoint."""
        return "mock" if self.provider.name == "mock" else "live"

    def _message(self, facts: VerifiedFacts, draft: DraftContent) -> GeneratedMessage:
        return GeneratedMessage(
            message_id=self._id_factory(),
            customer_id=facts.customer_id,
            draft=draft,
            source="llm",
            provider=self.provider.name,
            model=self.provider.model,
            prompt_version=self.prompt_version,
            generated_at=self._clock(),
        )

    def _cache_key(self, facts: VerifiedFacts) -> str:
        return cache_key(
            prompt_version=self.prompt_version,
            provider=self.provider.name,
            model=self.provider.model,
            facts=facts,
        )

    def _cached_draft(self, facts: VerifiedFacts) -> DraftContent | None:
        if self.cache is None:
            return None
        draft = self.cache.get(self._cache_key(facts))
        # Re-check grounding so a stale or hand-edited entry is never trusted blindly.
        if draft is None or missing_required_facts(draft, facts):
            return None
        logger.info("cache hit for %s", facts.customer_id)
        return draft

    def _store(self, facts: VerifiedFacts, draft: DraftContent) -> None:
        if self.cache is None:
            return
        self.cache.put(
            self._cache_key(facts),
            draft,
            prompt_version=self.prompt_version,
            provider=self.provider.name,
            model=self.provider.model,
        )

    def generate(self, facts: VerifiedFacts) -> GeneratedMessage:
        cached = self._cached_draft(facts)
        if cached is not None:
            return self._message(facts, cached)
        system, user = render_prompt(facts, version=self.prompt_version)
        reason: str | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            prompt_user = (
                user if reason is None else user + RETRY_NOTE.format(reason=reason)
            )
            request = PromptRequest(system=system, user=prompt_user, facts=facts)
            try:
                raw = self.provider.complete(request)
            except ProviderError as exc:
                logger.warning(
                    "generation failed for %s: provider error", facts.customer_id
                )
                raise GenerationError(
                    f"LLM provider '{self.provider.name}' failed: {exc}"
                ) from exc
            try:
                draft = parse_draft(raw)
            except DraftParseError as exc:
                reason = str(exc)
                logger.info(
                    "attempt %d for %s rejected: %s", attempt, facts.customer_id, reason
                )
                continue
            missing = missing_required_facts(draft, facts)
            if missing:
                reason = "the draft did not include these facts verbatim: " + ", ".join(
                    missing
                )
                logger.info(
                    "attempt %d for %s rejected: %s", attempt, facts.customer_id, reason
                )
                continue
            self._store(facts, draft)
            return self._message(facts, draft)
        raise GenerationError(
            f"no valid draft after {MAX_ATTEMPTS} attempts; last problem: {reason}"
        )
