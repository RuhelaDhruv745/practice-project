"""Smoke test: the module-level app (real policy engine + LLM generator) imports and
serves /api/health. No lifespan, no database, no LLM call."""

from __future__ import annotations

from fastapi.testclient import TestClient

from contracts.api import HealthResponse

CONTRACT_PATHS = {
    "/api/health",
    "/api/customers",
    "/api/customers/{customer_id}",
    "/api/classification/evaluate",
    "/api/messages/generate",
    "/api/messages/validate",
    "/api/reviews/pending",
    "/api/reviews/{review_id}",
    "/api/reviews/{review_id}/approve",
    "/api/reviews/{review_id}/reject",
    "/api/audit",
}


def test_module_level_app_wires_real_implementations() -> None:
    from ai_engine.generation import LLMDraftGenerator
    from backend.app.main import app
    from policy_engine.engine import RuleBasedPolicyEngine

    assert isinstance(app.state.policy_engine, RuleBasedPolicyEngine)
    assert isinstance(app.state.generator, LLMDraftGenerator)

    response = TestClient(app).get("/api/health")  # no lifespan: no DB file

    assert response.status_code == 200
    health = HealthResponse.model_validate(response.json())
    assert health.llm_mode == app.state.generator.mode


def test_openapi_lists_every_contract_endpoint() -> None:
    from backend.app.main import app

    paths = set(TestClient(app).get("/openapi.json").json()["paths"])

    assert CONTRACT_PATHS <= paths
