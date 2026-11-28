"""Thin HTTP client for the backend API in docs/API_CONTRACTS.md.

The client sends requests and returns the decoded JSON exactly as the backend produced
it. It does not interpret, recompute or correct anything: segments, eligibility,
amounts, dates and approval rules are the backend's job. Every failure is turned into
an ``ApiError`` carrying ``error.code`` / ``error.message`` so the UI never has to show
a traceback.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT_SECONDS = 30.0

JsonDict = dict[str, Any]


class ApiError(Exception):
    """An API failure in the contract's ``ErrorResponse`` shape.

    ``status`` is the HTTP status, or ``None`` when the API could not be reached.
    Codes such as ``api_unreachable`` and ``invalid_response`` are client-side codes
    for failures that never produced a contract error body.
    """

    def __init__(
        self,
        status: int | None,
        code: str,
        message: str,
        details: JsonDict | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.details: JsonDict = details or {}


def base_url_from_env() -> str:
    """API base URL from ``API_BASE_URL``, without a trailing slash."""
    return (os.environ.get("API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def error_from_response(response: httpx.Response) -> ApiError:
    """Map a non-2xx response to an ``ApiError`` without leaking raw bodies."""
    try:
        payload = response.json()
    except ValueError:
        payload = None
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and isinstance(error.get("code"), str):
        message = error.get("message")
        details = error.get("details")
        return ApiError(
            status=response.status_code,
            code=error["code"],
            message=message if isinstance(message, str) else "",
            details=details if isinstance(details, dict) else {},
        )
    return ApiError(
        status=response.status_code,
        code="unexpected_response",
        message=f"The API returned HTTP {response.status_code} without an error body.",
    )


def _segment(value: str) -> str:
    """Percent-encode one path segment so an ID can never change the route."""
    return quote(value, safe="")


class ApiClient:
    """One method per endpoint in docs/API_CONTRACTS.md."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = (base_url or base_url_from_env()).rstrip("/")
        self._http = httpx.Client(
            base_url=self.base_url, transport=transport, timeout=timeout
        )

    def close(self) -> None:
        self._http.close()

    # --- transport ------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: JsonDict | None = None,
        params: JsonDict | None = None,
    ) -> Any:
        clean_params = (
            {k: v for k, v in params.items() if v is not None} if params else None
        )
        try:
            response = self._http.request(method, path, json=json, params=clean_params)
        except httpx.TimeoutException:
            raise ApiError(
                None,
                "api_timeout",
                f"The API at {self.base_url} did not respond in time.",
            ) from None
        except httpx.HTTPError:
            raise ApiError(
                None, "api_unreachable", f"Could not reach the API at {self.base_url}."
            ) from None
        if not response.is_success:
            raise error_from_response(response)
        try:
            return response.json()
        except ValueError:
            raise ApiError(
                response.status_code,
                "invalid_response",
                "The API returned a response that is not valid JSON.",
            ) from None

    # --- endpoints --------------------------------------------------------------

    def health(self) -> JsonDict:
        return self._request("GET", "/api/health")

    def list_customers(
        self, *, segment: str | None = None, limit: int = 50, offset: int = 0
    ) -> JsonDict:
        return self._request(
            "GET",
            "/api/customers",
            params={"segment": segment, "limit": limit, "offset": offset},
        )

    def get_customer(self, customer_id: str) -> JsonDict:
        return self._request("GET", f"/api/customers/{_segment(customer_id)}")

    def evaluate(self, customer_id: str) -> JsonDict:
        return self._request(
            "POST", "/api/classification/evaluate", json={"customer_id": customer_id}
        )

    def generate(self, customer_id: str) -> JsonDict:
        return self._request(
            "POST", "/api/messages/generate", json={"customer_id": customer_id}
        )

    def validate(self, customer_id: str, subject: str, body: str) -> JsonDict:
        return self._request(
            "POST",
            "/api/messages/validate",
            json={
                "customer_id": customer_id,
                "draft": {"subject": subject, "body": body},
            },
        )

    def list_reviews(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> JsonDict:
        return self._request(
            "GET",
            "/api/reviews/pending",
            params={"status": status, "limit": limit, "offset": offset},
        )

    def edit_review(
        self,
        review_id: str,
        *,
        reviewer_id: str,
        subject: str,
        body: str,
        comment: str | None = None,
    ) -> JsonDict:
        payload: JsonDict = {
            "reviewer_id": reviewer_id,
            "draft": {"subject": subject, "body": body},
        }
        if comment:
            payload["comment"] = comment
        return self._request(
            "PATCH", f"/api/reviews/{_segment(review_id)}", json=payload
        )

    def approve_review(
        self,
        review_id: str,
        *,
        reviewer_id: str,
        comment: str | None = None,
        rubric: JsonDict | None = None,
    ) -> JsonDict:
        payload: JsonDict = {"reviewer_id": reviewer_id, "rubric": rubric}
        if comment:
            payload["comment"] = comment
        return self._request(
            "POST", f"/api/reviews/{_segment(review_id)}/approve", json=payload
        )

    def reject_review(
        self,
        review_id: str,
        *,
        reviewer_id: str,
        comment: str,
        rubric: JsonDict | None = None,
    ) -> JsonDict:
        return self._request(
            "POST",
            f"/api/reviews/{_segment(review_id)}/reject",
            json={"reviewer_id": reviewer_id, "comment": comment, "rubric": rubric},
        )

    def list_audit(
        self,
        *,
        customer_id: str | None = None,
        review_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> JsonDict:
        return self._request(
            "GET",
            "/api/audit",
            params={
                "customer_id": customer_id,
                "review_id": review_id,
                "event_type": event_type,
                "limit": limit,
                "offset": offset,
            },
        )
