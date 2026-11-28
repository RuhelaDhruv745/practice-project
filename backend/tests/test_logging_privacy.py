"""Logs never contain email addresses or keys."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.logging import RedactingFilter, redact
from backend.app.seed import SeedError, seed_customers
from backend.tests.conftest import CUSTOMERS_CSV


def test_requests_and_seed_never_log_at_sign(
    app: FastAPI,
    client: TestClient,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)

    client.get("/api/health")
    client.get("/api/customers")
    client.get("/api/customers/CUST-001")
    client.get("/api/customers/someone@example.com")  # user text in the path
    seed_customers(app.state.session_factory, CUSTOMERS_CSV)
    lines = CUSTOMERS_CSV.read_text(encoding="utf-8").splitlines()
    bad = tmp_path / "bad.csv"
    bad.write_text(
        lines[0] + "\n" + lines[1].replace("Asha", "x" * 61 + "@example.com") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(SeedError):
        seed_customers(app.state.session_factory, bad)

    # Server-side loggers only; the test client's own httpx log is not the app's.
    server = [r for r in caplog.records if r.name.startswith(("backend", "uvicorn"))]
    assert server, "expected access/seed log lines"
    assert not [r.getMessage() for r in server if "@" in r.getMessage()]
    assert any("route=/api/customers/{customer_id}" in r.message for r in server)


def test_uvicorn_access_log_is_redacted(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/1.1" %d',
        "127.0.0.1:5000",
        "GET",
        "/api/customers/someone@example.com",
        404,
    )

    assert caplog.records
    assert "@" not in caplog.text


def test_redact_masks_emails_keys_and_at_signs() -> None:
    text = redact("user a.b@example.com key sk-ant-abcdefghijkl other @x")

    assert "@" not in text
    assert "example.com" not in text
    assert "abcdefghijkl" not in text


def test_redacting_filter_rewrites_record() -> None:
    record = logging.LogRecord(
        "backend.test", logging.INFO, __file__, 1, "contact %s", ("x@y.org",), None
    )

    assert RedactingFilter().filter(record) is True
    assert "@" not in record.getMessage()
