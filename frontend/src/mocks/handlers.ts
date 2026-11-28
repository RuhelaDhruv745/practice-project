// MSW handlers that imitate the backend contract with an in-memory store.
// This is a fake backend for development and tests only; the real decisions are
// made by the FastAPI backend. The mock "validator" fails drafts that contain
// MOCK_BLOCKED_TERM so edit flows can be demonstrated.
import { http, HttpResponse } from "msw";

import type {
  ApproveRequest,
  AuditEvent,
  EditReviewRequest,
  RejectRequest,
  ReviewItem,
} from "../types";
import {
  decisions,
  failingValidation,
  initialAudit,
  initialReviews,
  passingValidation,
  profiles,
  summaryOf,
} from "./fixtures";

export const MOCK_BLOCKED_TERM = "legal action";
const NOW = "2026-11-01T10:00:00Z";

interface Db {
  reviews: ReviewItem[];
  audit: AuditEvent[];
  nextId: number;
}

let db: Db = createDb();

function createDb(): Db {
  return { reviews: initialReviews(), audit: initialAudit(), nextId: 100 };
}

export function resetMockDb(): void {
  db = createDb();
}

function error(status: number, code: string, message: string, details = {}) {
  return HttpResponse.json({ error: { code, message, details } }, { status });
}

function page<T>(items: T[], url: URL, defaultLimit: number) {
  const limit = Number(url.searchParams.get("limit") ?? defaultLimit);
  const offset = Number(url.searchParams.get("offset") ?? 0);
  return { items: items.slice(offset, offset + limit), total: items.length };
}

function record(event: Omit<AuditEvent, "event_id" | "occurred_at" | "actor"> & { actor?: string }) {
  db.nextId += 1;
  db.audit.unshift({ actor: "system", ...event, event_id: `EVT-${db.nextId}`, occurred_at: NOW });
}

function findReview(id: string) {
  return db.reviews.find((r) => r.review_id === id);
}

function replace(item: ReviewItem) {
  db.reviews = db.reviews.map((r) => (r.review_id === item.review_id ? item : r));
}

const API = "*/api";

export const handlers = [
  http.get(`${API}/health`, () =>
    HttpResponse.json({
      status: "ok",
      version: "0.1.0",
      policy_versions: { policy: "1.0" },
      llm_provider: "mock",
      llm_mode: "mock",
    }),
  ),

  http.get(`${API}/customers`, ({ request }) => {
    const url = new URL(request.url);
    const segment = url.searchParams.get("segment");
    const summaries = profiles
      .map(summaryOf)
      .filter((s) => !segment || s.primary_segment === segment);
    return HttpResponse.json(page(summaries, url, 50));
  }),

  http.get(`${API}/customers/:customerId`, ({ params }) => {
    const profile = profiles.find((p) => p.customer_id === params.customerId);
    return profile ? HttpResponse.json(profile) : error(404, "customer_not_found", "Customer not found.");
  }),

  http.post(`${API}/classification/evaluate`, async ({ request }) => {
    const body = (await request.json()) as { customer_id?: string };
    const decision = body.customer_id ? decisions[body.customer_id] : undefined;
    return decision ? HttpResponse.json(decision) : error(404, "customer_not_found", "Customer not found.");
  }),

  http.post(`${API}/messages/generate`, async ({ request }) => {
    const body = (await request.json()) as { customer_id?: string };
    const decision = body.customer_id ? decisions[body.customer_id] : undefined;
    if (!decision || !body.customer_id) return error(404, "customer_not_found", "Customer not found.");
    db.nextId += 1;
    const allowed = decision.status === "draft_allowed" && decision.facts;
    const item: ReviewItem = {
      review_id: `REV-${db.nextId}`,
      customer_id: body.customer_id,
      status: allowed ? "pending_review" : "blocked",
      revision: 1,
      decision,
      message: allowed
        ? {
            message_id: `MSG-${db.nextId}`,
            customer_id: body.customer_id,
            draft: {
              subject: `Hello ${decision.facts?.first_name}`,
              body: `Hi ${decision.facts?.first_name},\n\nA message about your ${decision.facts?.plan} plan.`,
            },
            source: "llm",
            provider: "mock",
            model: "mock-model",
            prompt_version: "1.0",
            generated_at: NOW,
          }
        : null,
      validation: allowed ? passingValidation() : null,
      decisions: [],
      created_at: NOW,
      updated_at: NOW,
    };
    db.reviews.push(item);
    record({
      event_type: allowed ? "draft_generated" : "outreach_blocked",
      customer_id: item.customer_id,
      review_id: item.review_id,
    });
    return HttpResponse.json(item, { status: 201 });
  }),

  http.get(`${API}/reviews/pending`, ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get("status") ?? "pending_review";
    return HttpResponse.json(page(db.reviews.filter((r) => r.status === status), url, 50));
  }),

  http.patch(`${API}/reviews/:reviewId`, async ({ params, request }) => {
    const item = findReview(String(params.reviewId));
    if (!item) return error(404, "review_not_found", "Review not found.");
    const editable =
      item.message !== null && (item.status === "pending_review" || item.status === "blocked");
    if (!editable) return error(409, "review_not_editable", "This review cannot be edited.");
    const body = (await request.json()) as EditReviewRequest;
    const text = `${body.draft.subject}\n${body.draft.body}`.toLowerCase();
    const validation = text.includes(MOCK_BLOCKED_TERM)
      ? failingValidation(MOCK_BLOCKED_TERM)
      : passingValidation();
    const updated: ReviewItem = {
      ...item,
      revision: item.revision + 1,
      status: validation.passed ? "pending_review" : "blocked",
      message: {
        ...item.message!,
        message_id: `${item.message!.message_id}-r${item.revision + 1}`,
        draft: body.draft,
        source: "reviewer_edit",
        generated_at: NOW,
      },
      validation,
      decisions: [
        ...(item.decisions ?? []),
        {
          review_id: item.review_id,
          action: "edit",
          reviewer_id: body.reviewer_id,
          comment: body.comment ?? null,
          rubric: null,
          decided_at: NOW,
        },
      ],
      updated_at: NOW,
    };
    replace(updated);
    record({ event_type: "review_edited", customer_id: item.customer_id, review_id: item.review_id });
    return HttpResponse.json(updated);
  }),

  http.post(`${API}/reviews/:reviewId/approve`, async ({ params, request }) => {
    const item = findReview(String(params.reviewId));
    if (!item) return error(404, "review_not_found", "Review not found.");
    if (["approved", "rejected", "delivered"].includes(item.status)) {
      return error(409, "review_already_decided", "This review is already decided.");
    }
    if (
      item.status !== "pending_review" ||
      !item.validation?.passed ||
      item.decision.status !== "draft_allowed" ||
      !item.message
    ) {
      return error(409, "review_not_approvable", "Validation failed; draft cannot be approved.", {
        status: item.status,
      });
    }
    const body = (await request.json()) as ApproveRequest;
    const updated: ReviewItem = {
      ...item,
      status: "delivered",
      decisions: [
        ...(item.decisions ?? []),
        {
          review_id: item.review_id,
          action: "approve",
          reviewer_id: body.reviewer_id,
          comment: body.comment ?? null,
          rubric: body.rubric ?? null,
          decided_at: NOW,
        },
      ],
      updated_at: NOW,
    };
    replace(updated);
    record({ event_type: "review_approved", customer_id: item.customer_id, review_id: item.review_id });
    record({ event_type: "message_delivered", customer_id: item.customer_id, review_id: item.review_id });
    return HttpResponse.json({
      review: updated,
      outbox: {
        message_id: item.message.message_id,
        review_id: item.review_id,
        customer_id: item.customer_id,
        channel: "email",
        subject: item.message.draft.subject,
        body: item.message.draft.body,
        approved_by: body.reviewer_id,
        delivered_at: NOW,
      },
    });
  }),

  http.post(`${API}/reviews/:reviewId/reject`, async ({ params, request }) => {
    const item = findReview(String(params.reviewId));
    if (!item) return error(404, "review_not_found", "Review not found.");
    if (!["pending_review", "blocked"].includes(item.status)) {
      return error(409, "review_already_decided", "This review is already decided.");
    }
    const body = (await request.json()) as RejectRequest;
    if (!body.comment || !body.comment.trim()) {
      return error(422, "validation_error", "A rejection needs a reason.", { errors: ["comment"] });
    }
    const updated: ReviewItem = {
      ...item,
      status: "rejected",
      decisions: [
        ...(item.decisions ?? []),
        {
          review_id: item.review_id,
          action: "reject",
          reviewer_id: body.reviewer_id,
          comment: body.comment,
          rubric: body.rubric ?? null,
          decided_at: NOW,
        },
      ],
      updated_at: NOW,
    };
    replace(updated);
    record({ event_type: "review_rejected", customer_id: item.customer_id, review_id: item.review_id });
    return HttpResponse.json(updated);
  }),

  http.get(`${API}/audit`, ({ request }) => {
    const url = new URL(request.url);
    const customerId = url.searchParams.get("customer_id");
    const reviewId = url.searchParams.get("review_id");
    const eventType = url.searchParams.get("event_type");
    const events = db.audit.filter(
      (e) =>
        (!customerId || e.customer_id === customerId) &&
        (!reviewId || e.review_id === reviewId) &&
        (!eventType || e.event_type === eventType),
    );
    return HttpResponse.json(page(events, url, 100));
  }),
];
