// Visual guards only. They read the state the backend reported and decide nothing
// themselves; the backend re-checks every action and may still answer 409.
import type { ReviewItem } from "../types";

/** Approve is offered only for pending_review + passing validation + allowed decision. */
export function canApprove(item: ReviewItem): boolean {
  return (
    item.status === "pending_review" &&
    item.validation?.passed === true &&
    item.decision.status === "draft_allowed"
  );
}

/** Editable per the contract: pending_review, or blocked with a message. */
export function canEdit(item: ReviewItem): boolean {
  if (item.message === null) return false;
  return item.status === "pending_review" || item.status === "blocked";
}

/** Reject is accepted for pending_review and blocked items. */
export function canReject(item: ReviewItem): boolean {
  return item.status === "pending_review" || item.status === "blocked";
}
