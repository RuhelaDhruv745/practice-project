"""LLM provider adapters behind one small interface.

- ``MockProvider``: deterministic draft built from VerifiedFacts. Used when no API key
  is configured and in every test. Never touches the network.
- ``AnthropicProvider``: default, via the ``anthropic`` SDK.
- ``GroqProvider``: fallback, via the ``openai`` SDK pointed at ``LLM_BASE_URL``.

Real providers retry rate limits (429), 5xx, timeouts and connection errors with bounded
exponential backoff. SDK-level retries are disabled so this is the only retry loop.
Keys come from the process environment only and are never logged; prompts are never
logged.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
import openai

from contracts.enums import OfferUnit, SegmentName
from contracts.models import OfferSnapshot, VerifiedFacts

logger = logging.getLogger(__name__)


DEFAULT_PROVIDER = "anthropic"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MOCK_MODEL = "mock-draft-v1"
MAX_OUTPUT_TOKENS = 1024


class ProviderError(RuntimeError):
    """A provider call failed for good (non-retryable, or retries exhausted).

    Messages are generic on purpose: no raw provider payloads, prompts or keys.
    """


class ProviderConfigError(ValueError):
    """LLM configuration in the environment is invalid or incomplete."""


@dataclass(frozen=True)
class PromptRequest:
    """One rendered prompt. ``facts`` is carried only so the mock can build its draft."""

    system: str
    user: str
    facts: VerifiedFacts


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(self, request: PromptRequest) -> str:
        """Return the model's raw text reply. Raise ProviderError on failure."""
        ...


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential backoff: delays base, 2*base, ... capped at max_delay."""

    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 8.0

    def delay_for(self, attempt: int) -> float:
        return min(
            self.base_delay_seconds * (2 ** (attempt - 1)), self.max_delay_seconds
        )


_TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (
    TimeoutError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    openai.APITimeoutError,
    openai.APIConnectionError,
)


def is_retryable_error(exc: BaseException) -> bool:
    """Rate limits, server errors, timeouts and connection errors are worth retrying."""
    if isinstance(exc, _TRANSIENT_ERRORS):
        return True
    status = getattr(exc, "status_code", None)
    return isinstance(status, int) and (status == 429 or status >= 500)


def call_with_backoff[T](
    call: Callable[[], T],
    *,
    provider_name: str,
    retry: RetryPolicy,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run ``call``, retrying transient failures; raise ProviderError when done."""
    for attempt in range(1, retry.max_attempts + 1):
        try:
            return call()
        except Exception as exc:
            error_type = type(exc).__name__
            if not is_retryable_error(exc):
                logger.warning(
                    "%s call failed (non-retryable %s)", provider_name, error_type
                )
                raise ProviderError(
                    f"{provider_name} request failed ({error_type})"
                ) from exc
            if attempt == retry.max_attempts:
                logger.warning(
                    "%s call failed after %d attempts (%s)",
                    provider_name,
                    attempt,
                    error_type,
                )
                raise ProviderError(
                    f"{provider_name} request failed after {attempt} attempts "
                    f"({error_type})"
                ) from exc
            delay = retry.delay_for(attempt)
            logger.info(
                "%s transient %s on attempt %d; retrying in %.1fs",
                provider_name,
                error_type,
                attempt,
                delay,
            )
            sleep(delay)
    raise ProviderError(f"{provider_name} request failed")  # pragma: no cover


# --- Mock --------------------------------------------------------------------

_MOCK_SUBJECTS: dict[SegmentName, str] = {
    SegmentName.CONSISTENT: "Thank you for being with us, {name}",
    SegmentName.LOYALTY_CANDIDATE: "A thank-you reward for you, {name}",
    SegmentName.DECLINING: "Something to make the most of your plan, {name}",
    SegmentName.DORMANT: "We would love to welcome you back, {name}",
    SegmentName.PAYMENT_REMINDER: "A reminder about your bill, {name}",
}

_MOCK_OPENINGS: dict[SegmentName, str] = {
    SegmentName.CONSISTENT: (
        "Thank you for staying with us on the {plan} plan. We appreciate it."
    ),
    SegmentName.LOYALTY_CANDIDATE: "Thank you for your loyalty on the {plan} plan.",
    SegmentName.DECLINING: "We hope the {plan} plan is still working well for you.",
    SegmentName.DORMANT: (
        "It has been a while, and we would be glad to see you on the {plan} plan again."
    ),
    SegmentName.PAYMENT_REMINDER: "This is a friendly note about your {plan} plan bill.",
}


def _offer_value_text(offer: OfferSnapshot) -> str:
    if offer.unit is OfferUnit.PERCENT:
        return f"{offer.value}%"
    if offer.unit is OfferUnit.GB:
        return f"{offer.value} GB"
    return f"INR {offer.value}"


def build_mock_draft(facts: VerifiedFacts) -> dict[str, str]:
    """Deterministic subject/body containing every required fact string verbatim."""
    name = facts.first_name
    subject = _MOCK_SUBJECTS[facts.segment].format(name=name)
    paragraphs = [f"Hi {name},", _MOCK_OPENINGS[facts.segment].format(plan=facts.plan)]
    if facts.offer is not None:
        offer = facts.offer
        paragraphs.append(
            f"We have {_offer_value_text(offer)} {offer.description} for you "
            f"(offer {offer.offer_id}), available until {offer.expiry.isoformat()}."
        )
    if facts.reminder is not None:
        reminder = facts.reminder
        paragraphs.append(
            f"Our records show {reminder.currency} {reminder.amount_due} was due on "
            f"{reminder.due_date.isoformat()}. Please arrange payment when you can."
        )
        paragraphs.append(reminder.support_path)
    paragraphs.append("Best regards,\nCustomer Care")
    return {"subject": subject[:150], "body": "\n\n".join(paragraphs)}


class MockProvider:
    """Offline provider. Same facts in, same JSON out."""

    name = "mock"

    def __init__(self, model: str = MOCK_MODEL) -> None:
        self.model = model

    def complete(self, request: PromptRequest) -> str:
        return json.dumps(build_mock_draft(request.facts), ensure_ascii=False)


# --- Anthropic ---------------------------------------------------------------


class AnthropicProvider:
    """Anthropic Claude via the Messages API. Default provider."""

    name = "anthropic"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: Any | None = None,
        retry: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not model:
            raise ProviderConfigError("anthropic provider needs a model id")
        self.model = model
        self._retry = retry or RetryPolicy()
        self._sleep = sleep
        if client is None:
            if not api_key:
                raise ProviderConfigError("anthropic provider needs an API key")
            client = anthropic.Anthropic(
                api_key=api_key, timeout=timeout_seconds, max_retries=0
            )
        self._client = client

    def complete(self, request: PromptRequest) -> str:
        def call() -> Any:
            return self._client.messages.create(
                model=self.model,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.3,
                system=request.system,
                messages=[{"role": "user", "content": request.user}],
            )

        response = call_with_backoff(
            call, provider_name=self.name, retry=self._retry, sleep=self._sleep
        )
        blocks = getattr(response, "content", None) or []
        return "".join(
            getattr(block, "text", "")
            for block in blocks
            if getattr(block, "type", None) == "text"
        )


# --- Groq (OpenAI-compatible) ------------------------------------------------


class GroqProvider:
    """Groq via the OpenAI-compatible Chat Completions API. Fallback provider."""

    name = "groq"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str = DEFAULT_GROQ_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: Any | None = None,
        retry: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not model:
            raise ProviderConfigError("groq provider needs a model id")
        self.model = model
        self.base_url = base_url
        self._retry = retry or RetryPolicy()
        self._sleep = sleep
        if client is None:
            if not api_key:
                raise ProviderConfigError("groq provider needs an API key")
            client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout_seconds,
                max_retries=0,
            )
        self._client = client

    def complete(self, request: PromptRequest) -> str:
        def call() -> Any:
            return self._client.chat.completions.create(
                model=self.model,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.user},
                ],
            )

        response = call_with_backoff(
            call, provider_name=self.name, retry=self._retry, sleep=self._sleep
        )
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""
        return choices[0].message.content or ""


# --- Selection from the process environment ----------------------------------


def _first_set(env: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = (env.get(name) or "").strip()
        if value:
            return value
    return None


def _timeout_from_env(env: Mapping[str, str]) -> float:
    raw = _first_set(env, "LLM_TIMEOUT_SECONDS")
    if raw is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
    except ValueError:
        raise ProviderConfigError("LLM_TIMEOUT_SECONDS must be a number") from None
    if timeout <= 0:
        raise ProviderConfigError("LLM_TIMEOUT_SECONDS must be positive")
    return timeout


def provider_from_env(env: Mapping[str, str] | None = None) -> LLMProvider:
    """Choose a provider from ``LLM_PROVIDER`` / ``LLM_MODEL`` / ``LLM_API_KEY`` /
    ``LLM_BASE_URL`` / ``LLM_TIMEOUT_SECONDS``.

    Provider-specific names from the example env file (``ANTHROPIC_API_KEY``,
    ``ANTHROPIC_MODEL``, ``GROQ_API_KEY``, ``GROQ_MODEL``, ``GROQ_BASE_URL``) are
    accepted as fallbacks. With no API key for a live provider the mock is used, so the
    app runs offline; a key without a model is a configuration error. Only the process
    environment is read; loading any env file is the application's job.
    """
    env = os.environ if env is None else env
    provider = (_first_set(env, "LLM_PROVIDER") or DEFAULT_PROVIDER).lower()
    if provider == "mock":
        return MockProvider()
    if provider not in {"anthropic", "groq"}:
        raise ProviderConfigError("LLM_PROVIDER must be one of: anthropic, groq, mock")

    prefix = provider.upper()
    api_key = _first_set(env, "LLM_API_KEY", f"{prefix}_API_KEY")
    if api_key is None:
        logger.info("no API key configured for %s; using mock provider", provider)
        return MockProvider()
    model = _first_set(env, "LLM_MODEL", f"{prefix}_MODEL")
    if model is None:
        raise ProviderConfigError(
            f"LLM_MODEL (or {prefix}_MODEL) must be set when using {provider}"
        )
    timeout = _timeout_from_env(env)
    if provider == "anthropic":
        return AnthropicProvider(model=model, api_key=api_key, timeout_seconds=timeout)
    base_url = _first_set(env, "LLM_BASE_URL", "GROQ_BASE_URL") or DEFAULT_GROQ_BASE_URL
    return GroqProvider(
        model=model, api_key=api_key, base_url=base_url, timeout_seconds=timeout
    )
