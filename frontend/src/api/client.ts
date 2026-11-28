// Thin HTTP client for docs/API_CONTRACTS.md. It returns the backend JSON as is and
// turns every failure into an ApiError carrying error.code / error.message.
import type {
  ApproveRequest,
  ApproveResponse,
  AuditEventType,
  AuditPage,
  CustomerPage,
  CustomerProfile,
  EditReviewRequest,
  HealthResponse,
  MessageStatus,
  PolicyDecision,
  RejectRequest,
  ReviewItem,
  ReviewPage,
  SegmentName,
} from "../types";

export const DEFAULT_API_BASE_URL = "http://localhost:8000";

export function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  return (configured || DEFAULT_API_BASE_URL).replace(/\/+$/, "");
}

type Details = Record<string, unknown>;

export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string;
  readonly details: Details;

  constructor(status: number | null, code: string, message: string, details: Details = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Map a non-2xx response body to an ApiError without echoing raw bodies. */
export function errorFromBody(status: number, body: unknown): ApiError {
  const error = isRecord(body) ? body.error : undefined;
  if (isRecord(error) && typeof error.code === "string") {
    return new ApiError(
      status,
      error.code,
      typeof error.message === "string" ? error.message : "",
      isRecord(error.details) ? error.details : {},
    );
  }
  return new ApiError(
    status,
    "unexpected_response",
    `The API returned HTTP ${status} without an error body.`,
  );
}

type Query = Record<string, string | number | undefined | null>;

interface RequestOptions {
  body?: unknown;
  query?: Query;
}

function buildUrl(path: string, query?: Query): string {
  const url = new URL(`${apiBaseUrl()}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), {
      method,
      headers: options.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(null, "api_unreachable", `Could not reach the API at ${apiBaseUrl()}.`);
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    if (!response.ok) throw errorFromBody(response.status, undefined);
    throw new ApiError(response.status, "invalid_response", "The API returned invalid JSON.");
  }
  if (!response.ok) throw errorFromBody(response.status, payload);
  return payload as T;
}

/** Percent-encode one path segment so an ID can never change the route. */
const seg = (value: string) => encodeURIComponent(value);

export interface AuditFilters {
  customer_id?: string;
  review_id?: string;
  event_type?: AuditEventType;
  limit?: number;
  offset?: number;
}

export const api = {
  health: () => request<HealthResponse>("GET", "/api/health"),

  listCustomers: (params: { segment?: SegmentName; limit?: number; offset?: number } = {}) =>
    request<CustomerPage>("GET", "/api/customers", { query: { ...params } }),

  getCustomer: (customerId: string) =>
    request<CustomerProfile>("GET", `/api/customers/${seg(customerId)}`),

  evaluate: (customerId: string) =>
    request<PolicyDecision>("POST", "/api/classification/evaluate", {
      body: { customer_id: customerId },
    }),

  generate: (customerId: string) =>
    request<ReviewItem>("POST", "/api/messages/generate", { body: { customer_id: customerId } }),

  listReviews: (params: { status?: MessageStatus; limit?: number; offset?: number } = {}) =>
    request<ReviewPage>("GET", "/api/reviews/pending", { query: { ...params } }),

  editReview: (reviewId: string, body: EditReviewRequest) =>
    request<ReviewItem>("PATCH", `/api/reviews/${seg(reviewId)}`, { body }),

  approveReview: (reviewId: string, body: ApproveRequest) =>
    request<ApproveResponse>("POST", `/api/reviews/${seg(reviewId)}/approve`, { body }),

  rejectReview: (reviewId: string, body: RejectRequest) =>
    request<ReviewItem>("POST", `/api/reviews/${seg(reviewId)}/reject`, { body }),

  listAudit: (params: AuditFilters = {}) =>
    request<AuditPage>("GET", "/api/audit", { query: { ...params } }),
};
