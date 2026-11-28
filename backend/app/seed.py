"""Seed customers from a CSV of CustomerProfile columns.

Usage: ``python -m backend.app.seed [--csv PATH] [--database-url URL]``.

Every row is validated through the ``CustomerProfile`` contract before anything is
written; unknown columns (for example an email column) reject the whole file. Writes
happen in one transaction and are idempotent: re-running with the same file changes
nothing. Error messages name rows and fields, never values (values may be customer
text).
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.logging import configure_logging, get_logger
from backend.app.core.settings import Settings
from backend.app.database import create_db_engine, init_db, session_factory
from backend.app.repositories import CustomerRepository
from contracts.models import CustomerProfile

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = REPO_ROOT / "data" / "synthetic" / "customers.csv"

_log = get_logger("seed")


class SeedError(ValueError):
    """The CSV cannot be loaded; nothing was written."""


def _check_columns(header: Sequence[str] | None) -> None:
    if not header:
        raise SeedError("CSV has no header row")
    known = set(CustomerProfile.model_fields)
    unknown = sorted(set(header) - known)
    if unknown:
        raise SeedError(f"unknown columns: {', '.join(unknown)}")
    required = {n for n, f in CustomerProfile.model_fields.items() if f.is_required()}
    missing = sorted(required - set(header))
    if missing:
        raise SeedError(f"missing columns: {', '.join(missing)}")
    if len(header) != len(set(header)):
        raise SeedError("duplicate column names")


def read_profiles(csv_path: Path) -> list[CustomerProfile]:
    """Parse and validate every row; raise SeedError on the first problem."""
    if not csv_path.is_file():
        raise SeedError(f"CSV not found: {csv_path.name}")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _check_columns(reader.fieldnames)
        profiles: list[CustomerProfile] = []
        seen: set[str] = set()
        for line_no, row in enumerate(reader, start=2):
            if None in row:
                raise SeedError(f"line {line_no}: more values than columns")
            values = {k: (None if v == "" else v) for k, v in row.items()}
            try:
                profile = CustomerProfile.model_validate(values)
            except ValidationError as exc:
                fields = sorted({str(e["loc"][0]) for e in exc.errors() if e["loc"]})
                raise SeedError(
                    f"line {line_no}: invalid fields: {', '.join(fields)}"
                ) from None
            if profile.customer_id in seen:
                raise SeedError(f"line {line_no}: duplicate customer_id")
            seen.add(profile.customer_id)
            profiles.append(profile)
    return profiles


def seed_customers(factory: sessionmaker[Session], csv_path: Path) -> tuple[int, int]:
    """Load the CSV in one transaction. Returns (rows read, rows changed)."""
    profiles = read_profiles(csv_path)
    changed = 0
    with factory.begin() as session:
        repo = CustomerRepository(session)
        for profile in profiles:
            changed += repo.upsert(profile)
    _log.info("seed complete; rows=%d changed=%d", len(profiles), changed)
    return len(profiles), changed


def main(argv: Sequence[str] | None = None) -> int:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Seed customers from a CSV file.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--database-url", default=settings.database_url)
    args = parser.parse_args(argv)

    configure_logging(settings.log_level)
    engine = create_db_engine(args.database_url)
    try:
        init_db(engine)
        seed_customers(session_factory(engine), args.csv)
    except SeedError as exc:
        _log.error("seed failed: %s", exc)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
