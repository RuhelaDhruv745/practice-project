"""Render the draft_v1 prompt from VerifiedFacts.

Trusted instructions (objective, tone guidance from policy config) go in the
instruction area. Every fact value, including untrusted customer text, goes only inside
the JSON-encoded ``<facts>`` data block. Rules about offers and reminders are added
only when the facts carry them, so the prompt never mentions a fact that is absent.
"""

from __future__ import annotations

from ai_engine.grounding.facts import encode_facts_block
from ai_engine.prompts import PROMPT_VERSION, load_template
from contracts.models import VerifiedFacts

_OFFER_RULE = (
    "- Mention the offer in the facts once. Include its offer_id, value, unit and "
    "expiry date exactly as written. Do not add any other offer or discount."
)
_NO_OFFER_RULE = "- There is no offer for this customer. Do not mention any offer."
_REMINDER_RULE = (
    "- This is a payment reminder. Quote amount_due with its currency and due_date "
    "exactly as written in the facts.\n"
    "- Include this support path in the body verbatim, word for word:\n"
    "  {support_path}"
)


def _conditional_rules(facts: VerifiedFacts) -> str:
    rules = [_OFFER_RULE if facts.offer is not None else _NO_OFFER_RULE]
    if facts.reminder is not None:
        rules.append(_REMINDER_RULE.format(support_path=facts.reminder.support_path))
    return "Rules for this message:\n" + "\n".join(rules) + "\n"


def _single_line(text: str) -> str:
    """Policy text is trusted, but keep it on one line so it cannot fake prompt structure."""
    return " ".join(text.split())


def render_prompt(
    facts: VerifiedFacts, *, version: str = PROMPT_VERSION
) -> tuple[str, str]:
    """Return ``(system, user)`` prompt text for one customer's verified facts."""
    system = load_template(f"{version}_system").substitute()
    user = load_template(f"{version}_user").substitute(
        objective=_single_line(facts.objective),
        tone=_single_line(facts.tone),
        tone_guidance=_single_line(facts.tone_guidance),
        conditional_rules=_conditional_rules(facts),
        facts_json=encode_facts_block(facts),
    )
    return system, user


RETRY_NOTE = (
    "\n\nYour previous reply was rejected because {reason}. Reply again with only a "
    'JSON object with exactly the keys "subject" and "body", using only the facts '
    "above."
)
