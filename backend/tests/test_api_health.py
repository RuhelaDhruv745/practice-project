from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.main import create_app
from backend.tests.fakes import FakeDraftGenerator, FakePolicyEngine
from contracts.api import HealthResponse


def test_health_reports_versions_and_mock_mode(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    health = HealthResponse.model_validate(response.json())
    assert health.status == "ok"
    assert health.version == "0.1.0"
    assert health.policy_versions == {"policy": "1.0", "segments": "1.0"}
    assert health.llm_provider == "mock"
    assert health.llm_mode == "mock"


def test_health_live_mode_never_reveals_key(tmp_path: Path) -> None:
    secret = "sk-ant-test-not-a-real-key-123456"
    settings = Settings.from_env(
        {
            "LLM_PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": secret,
            "DATABASE_URL": f"sqlite:///{(tmp_path / 'h.db').as_posix()}",
        }
    )
    app = create_app(
        FakePolicyEngine(), FakeDraftGenerator(), settings, policy_versions={}
    )
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.json()["llm_mode"] == "live"
    assert response.json()["llm_provider"] == "anthropic"
    assert secret not in response.text
    assert secret not in repr(settings)


def test_default_policy_versions_come_from_policy_yaml(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'v.db').as_posix()}")
    app = create_app(FakePolicyEngine(), FakeDraftGenerator(), settings)
    with TestClient(app) as client:
        versions = client.get("/api/health").json()["policy_versions"]

    assert "policy" in versions
    assert all(isinstance(v, str) and v for v in versions.values())


def test_openapi_schema_is_served(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert "/api/health" in schema["paths"]
    assert "/api/customers" in schema["paths"]
    assert "/api/customers/{customer_id}" in schema["paths"]
