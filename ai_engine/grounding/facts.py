"""Turn VerifiedFacts into the prompt's data block, and pre-check drafts for grounding.

Only fields present in VerifiedFacts are rendered; ``offer`` and ``reminder`` blocks are
omitted entirely when null so the model is never shown an empty slot it might fill.
``customer_id`` is kept out of the prompt: it is for traceability, not wording.

The pre-check here is a cheap local signal that triggers one retry. It does not replace
``PolicyEngine.validate`` (Member 3), which is the only approval gate.
"""

from __future__ import annotations

import json
import re
from typing import Any

from contracts.models import DraftContent, VerifiedFacts

FACTS_OPEN_TAG = "<facts>"
FACTS_CLOSE_TAG = "</facts>"

_WHITESPACE = re.compile(r"\s+")
_ESCAPED_LT = "\\" + "u003c"  # JSON escape for "<"
_ESCAPED_GT = "\\" + "u003e"  # JSON escape for ">"


def pack_facts(facts: VerifiedFacts) -> dict[str, Any]:
    """Render the facts the model may use as JSON-ready primitives (money as strings)."""
    packed: dict[str, Any] = {
        "customer": {"first_name": facts.first_name, "plan": facts.plan},
        "segment": facts.segment.value,
        "objective": facts.objective,
        "tone": facts.tone,
    }
    if facts.offer is not None:
        offer = facts.offer
        packed["offer"] = {
            "offer_id": offer.offer_id,
            "description": offer.description,
            "value": str(offer.value),
            "unit": offer.unit.value,
            "expiry": offer.expiry.isoformat(),
            "channel": offer.channel.value,
        }
    if facts.reminder is not None:
        reminder = facts.reminder
        packed["reminder"] = {
            "stage": reminder.stage,
            "days_overdue": reminder.days_overdue,
            "amount_due": str(reminder.amount_due),
            "currency": reminder.currency,
            "due_date": reminder.due_date.isoformat(),
            "support_path": reminder.support_path,
        }
    return packed


def encode_facts_block(facts: VerifiedFacts) -> str:
    """JSON-encode packed facts so untrusted text cannot break out of the data fence.

    JSON escaping neutralises quotes and newlines; ``<`` and ``>`` are additionally
    escaped as JSON unicode escapes (backslash + u003c / u003e, still valid JSON) so
    a value can never contain the literal ``</facts>`` closing tag.
    """
    encoded = json.dumps(pack_facts(facts), indent=2, ensure_ascii=False)
    return encoded.replace("<", _ESCAPED_LT).replace(">", _ESCAPED_GT)


def required_fact_strings(facts: VerifiedFacts) -> dict[str, str]:
    """Fact strings that must appear verbatim in the draft, keyed by fact name."""
    required: dict[str, str] = {}
    if facts.offer is not None:
        required["offer_id"] = facts.offer.offer_id
    if facts.reminder is not None:
        required["amount_due"] = str(facts.reminder.amount_due)
        required["due_date"] = facts.reminder.due_date.isoformat()
        required["support_path"] = facts.reminder.support_path
    return required


def _normalise(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def missing_required_facts(draft: DraftContent, facts: VerifiedFacts) -> list[str]:
    """Names of required facts absent from the draft (whitespace-insensitive).

    The support path must be in the body; other facts may be in subject or body.
    """
    full_text = _normalise(f"{draft.subject}\n{draft.body}")
    body = _normalise(draft.body)
    missing: list[str] = []
    for name, value in required_fact_strings(facts).items():
        haystack = body if name == "support_path" else full_text
        if _normalise(value) not in haystack:
            missing.append(name)
    return missing
