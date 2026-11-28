# Coding standards

- Python 3.13. Format with `ruff format`, lint with `ruff check` (config in `pyproject.toml`). Both must be clean before commit.
- Type-hint every public function. Use `from __future__ import annotations`.
- Use the Pydantic models in `contracts/` for data crossing a module boundary. Do not define look-alike models.
- Money is `Decimal`, never `float`. Dates are `date`; timestamps are timezone-aware UTC `datetime`.
- No "today" from the system clock inside policy rules: use `as_of_date` from `data/policies/policy.yaml`.
- Small functions, explicit names, no clever metaprogramming. Docstrings explain why, not what.
- Fail loudly on bad config or data (`ConfigError`, validation errors); never silently default a business value.
- Frontend: TypeScript strict mode, ESLint clean, types generated from the backend OpenAPI schema.
- Ask before adding a dependency; add it to your own module's `requirements.txt` (or `frontend/package.json`).
- Do not create new `.md` files outside `README.md`, `NOTES.md`, `CLAUDE.md`, `docs/`, `.claude/` and `.github/`.
