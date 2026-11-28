from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app import seed
from backend.app.models import CommunicationPreferenceRow, CustomerRow
from backend.app.repositories import CustomerRepository
from backend.app.seed import SeedError, read_profiles, seed_customers
from backend.tests.conftest import CUSTOMERS_CSV

HEADER = CUSTOMERS_CSV.read_text(encoding="utf-8").splitlines()[0]
ROWS = CUSTOMERS_CSV.read_text(encoding="utf-8").splitlines()[1:]


def _write(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "customers.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _customer_count(app: FastAPI) -> int:
    with app.state.session_factory() as session:
        return session.execute(select(func.count()).select_from(CustomerRow)).scalar()


def test_seed_loads_all_rows(app: FastAPI, empty_client: TestClient) -> None:
    read, changed = seed_customers(app.state.session_factory, CUSTOMERS_CSV)

    assert (read, changed) == (4, 4)
    assert _customer_count(app) == 4
    with app.state.session_factory() as session:
        profile = CustomerRepository(session).get_profile("CUST-003")
    assert profile is not None
    assert profile.amount_due == Decimal("2000.00")
    assert profile.activity_score_30d == 5.0


def test_seed_is_idempotent(app: FastAPI, empty_client: TestClient) -> None:
    seed_customers(app.state.session_factory, CUSTOMERS_CSV)
    with app.state.session_factory() as session:
        stamps_before = dict(
            session.execute(
                select(
                    CommunicationPreferenceRow.customer_id,
                    CommunicationPreferenceRow.updated_at,
                )
            ).all()
        )

    read, changed = seed_customers(app.state.session_factory, CUSTOMERS_CSV)

    assert (read, changed) == (4, 0)
    assert _customer_count(app) == 4
    with app.state.session_factory() as session:
        stamps_after = dict(
            session.execute(
                select(
                    CommunicationPreferenceRow.customer_id,
                    CommunicationPreferenceRow.updated_at,
                )
            ).all()
        )
    assert stamps_after == stamps_before


def test_seed_updates_changed_rows(
    app: FastAPI, empty_client: TestClient, tmp_path: Path
) -> None:
    seed_customers(app.state.session_factory, CUSTOMERS_CSV)
    edited = ROWS[0].replace("Unlimited 599", "Unlimited 799")
    path = _write(tmp_path, HEADER, edited, *ROWS[1:])

    assert seed_customers(app.state.session_factory, path) == (4, 1)
    assert empty_client.get("/api/customers/CUST-001").json()["plan"] == "Unlimited 799"


def test_seed_rejects_unknown_columns(
    app: FastAPI, empty_client: TestClient, tmp_path: Path
) -> None:
    path = _write(tmp_path, HEADER + ",email", ROWS[0] + ",x")

    with pytest.raises(SeedError, match="unknown columns: email"):
        seed_customers(app.state.session_factory, path)
    assert _customer_count(app) == 0


def test_seed_rejects_missing_columns(tmp_path: Path) -> None:
    header = HEADER.replace(",plan", "")
    with pytest.raises(SeedError, match="missing columns: plan"):
        read_profiles(_write(tmp_path, header))


def test_last_contacted_column_is_optional(tmp_path: Path) -> None:
    header = HEADER.removesuffix(",last_contacted_days_ago")
    row = ROWS[0].rsplit(",", 1)[0]

    (profile,) = read_profiles(_write(tmp_path, header, row))

    assert profile.last_contacted_days_ago is None


def test_seed_invalid_row_writes_nothing_and_hides_values(
    app: FastAPI, empty_client: TestClient, tmp_path: Path
) -> None:
    bad = ROWS[1].replace(",14,", ",leak@example.com,")
    path = _write(tmp_path, HEADER, ROWS[0], bad)

    with pytest.raises(SeedError) as excinfo:
        seed_customers(app.state.session_factory, path)

    assert "line 3" in str(excinfo.value)
    assert "months_active" in str(excinfo.value)
    assert "@" not in str(excinfo.value)
    assert _customer_count(app) == 0  # all-or-nothing


def test_seed_rejects_duplicate_ids(tmp_path: Path) -> None:
    with pytest.raises(SeedError, match="duplicate customer_id"):
        read_profiles(_write(tmp_path, HEADER, ROWS[0], ROWS[0]))


def test_seed_cli(tmp_path: Path) -> None:
    db_url = f"sqlite:///{(tmp_path / 'out' / 'cli.db').as_posix()}"

    assert seed.main(["--csv", str(CUSTOMERS_CSV), "--database-url", db_url]) == 0
    assert seed.main(["--csv", str(CUSTOMERS_CSV), "--database-url", db_url]) == 0
    assert (tmp_path / "out" / "cli.db").is_file()
    assert (
        seed.main(["--csv", str(tmp_path / "nope.csv"), "--database-url", db_url]) == 1
    )
