"""Opt-in on-disk cache of accepted drafts, for development only.

Saves API calls and money while iterating on the UI or the evaluation script. It is off
by default; enable with ``LLM_CACHE=1``. Files go under ``outputs/llm_cache/`` (the
whole ``outputs/`` folder is git-ignored) unless ``LLM_CACHE_DIR`` points elsewhere.

What is cached: only drafts that already parsed and passed the grounding pre-check, so
a bad reply is never replayed. The key is a SHA-256 hash of (prompt version, provider,
model, verified facts); changing any of them is a miss. Prompts and keys are never
stored. The mock provider is never cached: it is deterministic and free.

A cache hit still goes through ``PolicyEngine.validate`` in the backend like any draft.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from contracts.models import DraftContent, VerifiedFacts

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = REPO_ROOT / "outputs" / "llm_cache"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def cache_key(
    *, prompt_version: str, provider: str, model: str, facts: VerifiedFacts
) -> str:
    """Stable hash of everything that determines the prompt and the model used."""
    payload = {
        "prompt_version": prompt_version,
        "provider": provider,
        "model": model,
        "facts": facts.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class DraftCache:
    """One JSON file per key: ``{"subject": ..., "body": ...}`` plus provenance."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> DraftContent | None:
        path = self._path(key)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return DraftContent(subject=data["subject"], body=data["body"])
        except (OSError, ValueError, KeyError, TypeError, ValidationError):
            # A corrupt entry is a miss, never an error: the provider is asked again.
            logger.warning("ignoring unreadable cache entry %s", path.name)
            return None

    def put(
        self,
        key: str,
        draft: DraftContent,
        *,
        prompt_version: str,
        provider: str,
        model: str,
    ) -> None:
        record = {
            "subject": draft.subject,
            "body": draft.body,
            "prompt_version": prompt_version,
            "provider": provider,
            "model": model,
        }
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            tmp = self._path(key).with_suffix(".tmp")
            tmp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._path(key))
        except OSError:
            # The cache is a convenience; failing to write it must not fail generation.
            logger.warning("could not write cache entry %s", key[:12])


def cache_from_env(env: Mapping[str, str] | None = None) -> DraftCache | None:
    """``DraftCache`` when ``LLM_CACHE`` is truthy, else ``None`` (the default)."""
    env = os.environ if env is None else env
    if (env.get("LLM_CACHE") or "").strip().lower() not in _TRUTHY:
        return None
    directory = (env.get("LLM_CACHE_DIR") or "").strip()
    return DraftCache(Path(directory) if directory else DEFAULT_CACHE_DIR)
