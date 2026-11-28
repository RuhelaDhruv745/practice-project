// Short aliases for the generated OpenAPI schemas. Never hand-write models here:
// regenerate src/types/api.ts with `npm run gen:types` instead.
import type { components } from "./api";

type Schemas = components["schemas"];

export type AuditEvent = Schemas["AuditEvent"];
export type AuditEventType = Schemas["AuditEventType"];
export type ApproveRequest = Schemas["ApproveRequest"];
export type ApproveResponse = Schemas["ApproveResponse"];
export type CustomerProfile = Schemas["CustomerProfile"];
export type CustomerSummary = Schemas["CustomerSummary"];
export type DraftContent = Schemas["DraftContent"];
export type EditReviewRequest = Schemas["EditReviewRequest"];
export type ErrorResponse = Schemas["ErrorResponse"];
export type HealthResponse = Schemas["HealthResponse"];
export type MessageStatus = Schemas["MessageStatus"];
export type OutboxRecord = Schemas["OutboxRecord"];
export type PolicyDecision = Schemas["PolicyDecision"];
export type RejectRequest = Schemas["RejectRequest"];
export type ReviewItem = Schemas["ReviewItem"];
export type ReviewRubric = Schemas["ReviewRubric"];
export type SegmentName = Schemas["SegmentName"];
export type ValidationResult = Schemas["ValidationResult"];
export type CustomerPage = Schemas["Page_CustomerSummary_"];
export type ReviewPage = Schemas["Page_ReviewItem_"];
export type AuditPage = Schemas["Page_AuditEvent_"];

type Exhaustive<All, Listed> = [Exclude<All, Listed>] extends [never] ? true : never;

/** Every SegmentName, for filters and per-segment counts. The type check below fails
 * the build if the generated enum gains a value that is not listed here. */
export const SEGMENT_NAMES = [
  "consistent",
  "loyalty_candidate",
  "declining",
  "dormant",
  "payment_reminder",
] as const satisfies readonly SegmentName[];
export const SEGMENT_NAMES_COMPLETE: Exhaustive<SegmentName, (typeof SEGMENT_NAMES)[number]> =
  true;

export const AUDIT_EVENT_TYPES = [
  "profile_assembled",
  "classified",
  "policy_decided",
  "outreach_blocked",
  "draft_generated",
  "generation_failed",
  "draft_validated",
  "review_edited",
  "review_approved",
  "review_rejected",
  "message_delivered",
  "delivery_refused",
] as const satisfies readonly AuditEventType[];
export const AUDIT_EVENT_TYPES_COMPLETE: Exhaustive<
  AuditEventType,
  (typeof AUDIT_EVENT_TYPES)[number]
> = true;

/** Review statuses that GET /api/reviews/pending accepts. */
export const LISTABLE_REVIEW_STATUSES = [
  "pending_review",
  "blocked",
] as const satisfies readonly MessageStatus[];
