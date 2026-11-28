"""Versioned prompt templates (Member 2). Every template has a prompt_version recorded in audit.

Templates are plain text files next to this module. Placeholders use
``string.Template`` syntax (``$name``) so JSON braces in the templates need no escaping
and substituted customer text is never re-expanded.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from string import Template

PROMPT_VERSION = "draft_v1"

_TEMPLATE_DIR = Path(__file__).resolve().parent


@cache
def load_template(name: str) -> Template:
    """Load a template file by stem, e.g. ``draft_v1_system``. Fails loudly if missing."""
    path = _TEMPLATE_DIR / f"{name}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"prompt template not found: {path.name}")
    return Template(path.read_text(encoding="utf-8"))


__all__ = ["PROMPT_VERSION", "load_template"]
