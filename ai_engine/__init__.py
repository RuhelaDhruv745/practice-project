"""AI / LLM drafting engine (Member 2).

Implements contracts.interfaces.DraftGenerator: words a subject and body from
VerifiedFacts only. Never decides segments, offers, stages, amounts or dates.
Provider is configurable (anthropic default, groq fallback, mock for tests/offline)."""
