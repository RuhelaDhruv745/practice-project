"""Fact packing and untrusted-text handling for prompts (Member 2). Customer text is data, never instructions."""

from __future__ import annotations

from ai_engine.grounding.facts import (
    FACTS_CLOSE_TAG,
    FACTS_OPEN_TAG,
    encode_facts_block,
    missing_required_facts,
    pack_facts,
    required_fact_strings,
)

__all__ = [
    "FACTS_CLOSE_TAG",
    "FACTS_OPEN_TAG",
    "encode_facts_block",
    "missing_required_facts",
    "pack_facts",
    "required_fact_strings",
]
