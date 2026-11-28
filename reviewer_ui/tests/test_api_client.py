"""ApiClient: request shapes and error mapping, with httpx.MockTransport (no network)."""

from __future__ import annotations

import json

import httpx
import pytest

from reviewer_ui.api_client import (
    DEFAULT_BASE_URL,
    ApiClient,
    ApiError,
    base_url_from_env,
    error_from_response,
)


class Recorder:
    def __init__(self, response: httpx.Response | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.response = response or httpx.Response(200, json={"ok": True})

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.response

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def last_json(self) -> dict:
        return json.loads(self.last.content)


def make(recorder: Recorder) -> ApiClient:
    return ApiClient("http://api.test/", transport=httpx.MockTransport(recorder))


def test_base_url_from_env_default_and_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("API_BASE_URL", raising=False)
    assert base_url_from_env() == DEFAULT_BASE_URL
    monkeypatch.setenv("API_BASE_URL", "http://backend:9000/")
    assert base_url_from_env() == "http://backend:9000"
    assert ApiClient().base_url == "http://backend:9000"


def test_get_endpoints_use_contract_paths_and_drop_empty_params() -> None:
    rec = Recorder()
    client = make(rec)
    client.health()
    assert (rec.last.method, rec.last.url.path) == ("GET", "/api/health")
    client.list_customers(limit=10)
    assert rec.last.url.path == "/api/customers"
    assert dict(rec.last.url.params) == {"limit": "10", "offset": "0"}
    client.get_customer("CUST-001")
    assert rec.last.url.path == "/api/customers/CUST-001"
    client.list_reviews(status="blocked")
    assert rec.last.url.path == "/api/reviews/pending"
    assert rec.last.url.params["status"] == "blocked"
    client.list_audit(review_id="REV-0001")
    assert rec.last.url.path == "/api/audit"
    assert dict(rec.last.url.params) == {
        "review_id": "REV-0001",
        "limit": "100",
        "offset": "0",
    }


def test_path_ids_are_encoded_so_they_cannot_change_the_route() -> None:
    rec = Recorder()
    make(rec).get_customer("../reviews/x")
    assert rec.last.url.raw_path.decode() == "/api/customers/..%2Freviews%2Fx"


def test_post_bodies_match_contract() -> None:
    rec = Recorder()
    client = make(rec)
    client.evaluate("CUST-001")
    assert rec.last.url.path == "/api/classification/evaluate"
    assert rec.last_json() == {"customer_id": "CUST-001"}
    client.generate("CUST-002")
    assert rec.last.url.path == "/api/messages/generate"
    assert rec.last_json() == {"customer_id": "CUST-002"}
    client.validate("CUST-003", "S", "B")
    assert rec.last.url.path == "/api/messages/validate"
    assert rec.last_json() == {
        "customer_id": "CUST-003",
        "draft": {"subject": "S", "body": "B"},
    }


def test_review_actions_match_contract() -> None:
    rec = Recorder()
    client = make(rec)
    client.edit_review("REV-1", reviewer_id="reviewer-1", subject="S", body="B")
    assert (rec.last.method, rec.last.url.path) == ("PATCH", "/api/reviews/REV-1")
    assert rec.last_json() == {
        "reviewer_id": "reviewer-1",
        "draft": {"subject": "S", "body": "B"},
    }
    rubric = dict.fromkeys(
        ("relevance", "clarity", "personalisation", "call_to_action", "tone"), 4
    )
    client.approve_review(
        "REV-1", reviewer_id="reviewer-1", comment="ok", rubric=rubric
    )
    assert (rec.last.method, rec.last.url.path) == (
        "POST",
        "/api/reviews/REV-1/approve",
    )
    assert rec.last_json() == {
        "reviewer_id": "reviewer-1",
        "comment": "ok",
        "rubric": rubric,
    }
    client.reject_review("REV-1", reviewer_id="reviewer-1", comment="off tone")
    assert rec.last.url.path == "/api/reviews/REV-1/reject"
    assert rec.last_json() == {
        "reviewer_id": "reviewer-1",
        "comment": "off tone",
        "rubric": None,
    }


def test_contract_error_body_maps_to_code_message_details() -> None:
    body = {
        "error": {
            "code": "review_not_approvable",
            "message": "Validation failed; draft cannot be approved.",
            "details": {
                "status": "pending_review",
                "blocking_findings": ["blocked_term"],
            },
        }
    }
    client = make(Recorder(httpx.Response(409, json=body)))
    with pytest.raises(ApiError) as info:
        client.approve_review("REV-1", reviewer_id="reviewer-1")
    err = info.value
    assert (err.status, err.code) == (409, "review_not_approvable")
    assert err.message == "Validation failed; draft cannot be approved."
    assert err.details["blocking_findings"] == ["blocked_term"]


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, "bad_request"),
        (404, "customer_not_found"),
        (404, "review_not_found"),
        (409, "review_not_editable"),
        (409, "review_already_decided"),
        (422, "validation_error"),
        (502, "generation_failed"),
        (500, "internal_error"),
    ],
)
def test_each_contract_error_code_is_preserved(status: int, code: str) -> None:
    resp = httpx.Response(status, json={"error": {"code": code, "message": "m"}})
    err = error_from_response(resp)
    assert (err.status, err.code, err.message, err.details) == (status, code, "m", {})


def test_non_json_error_never_leaks_raw_body() -> None:
    resp = httpx.Response(500, text="Traceback (most recent call last): secret")
    client = make(Recorder(resp))
    with pytest.raises(ApiError) as info:
        client.health()
    assert info.value.code == "unexpected_response"
    assert "Traceback" not in str(info.value)
    assert "secret" not in str(info.value)


def test_json_error_without_contract_shape_is_generic() -> None:
    err = error_from_response(httpx.Response(500, json={"detail": "boom"}))
    assert err.code == "unexpected_response"
    assert "boom" not in err.message


def test_unreachable_and_timeout_become_api_errors() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ApiError) as info:
        ApiClient("http://api.test", transport=httpx.MockTransport(refuse)).health()
    assert (info.value.status, info.value.code) == (None, "api_unreachable")
    with pytest.raises(ApiError) as info:
        ApiClient("http://api.test", transport=httpx.MockTransport(slow)).health()
    assert info.value.code == "api_timeout"


def test_success_with_invalid_json_is_reported() -> None:
    client = make(Recorder(httpx.Response(200, text="<html>")))
    with pytest.raises(ApiError) as info:
        client.health()
    assert info.value.code == "invalid_response"
