import { describe, expect, it } from "vitest";

import { errorFromBody } from "../api/client";
import { canApprove, canEdit, canReject } from "../api/guards";
import { initialReviews } from "../mocks/fixtures";
import type { ReviewItem } from "../types";

describe("errorFromBody", () => {
  it("reads the contract ErrorResponse shape", () => {
    const err = errorFromBody(409, {
      error: { code: "review_already_decided", message: "Already decided.", details: { a: 1 } },
    });
    expect(err.status).toBe(409);
    expect(err.code).toBe("review_already_decided");
    expect(err.message).toBe("Already decided.");
    expect(err.details).toEqual({ a: 1 });
  });

  it("does not echo a body that is not an ErrorResponse", () => {
    const err = errorFromBody(500, "<html>Traceback secret</html>");
    expect(err.code).toBe("unexpected_response");
    expect(err.message).not.toContain("Traceback");
  });
});

describe("visual guards", () => {
  const [pending, validationBlocked, policyBlocked] = initialReviews();
  const withStatus = (item: ReviewItem, status: ReviewItem["status"]): ReviewItem => ({
    ...item,
    status,
  });

  it("allows approve only for pending_review with passing validation", () => {
    expect(canApprove(pending)).toBe(true);
    expect(canApprove(validationBlocked)).toBe(false);
    expect(canApprove(policyBlocked)).toBe(false);
    expect(canApprove(withStatus(pending, "delivered"))).toBe(false);
    expect(canApprove(withStatus(pending, "rejected"))).toBe(false);
  });

  it("never allows approve when the decision is blocked, whatever the status", () => {
    expect(canApprove(withStatus(policyBlocked, "pending_review"))).toBe(false);
  });

  it("allows edit only when a message exists and the item is open", () => {
    expect(canEdit(pending)).toBe(true);
    expect(canEdit(validationBlocked)).toBe(true);
    expect(canEdit(policyBlocked)).toBe(false);
    expect(canEdit(withStatus(pending, "delivered"))).toBe(false);
  });

  it("allows reject for pending_review and blocked only", () => {
    expect(canReject(pending)).toBe(true);
    expect(canReject(policyBlocked)).toBe(true);
    expect(canReject(withStatus(pending, "rejected"))).toBe(false);
  });
});
