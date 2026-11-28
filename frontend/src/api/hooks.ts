// React Query wrappers around the API client. No business logic: they fetch, cache
// and store what the backend returns.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";

import type {
  ApproveRequest,
  EditReviewRequest,
  MessageStatus,
  RejectRequest,
  ReviewItem,
  SegmentName,
} from "../types";
import { LISTABLE_REVIEW_STATUSES } from "../types";
import { ApiError, api } from "./client";
import type { AuditFilters } from "./client";

export const keys = {
  customers: (segment?: SegmentName, limit?: number, offset?: number) =>
    ["customers", segment ?? "all", limit ?? 50, offset ?? 0] as const,
  customer: (id: string) => ["customer", id] as const,
  evaluation: (id: string) => ["evaluation", id] as const,
  reviews: (status: MessageStatus, limit?: number, offset?: number) =>
    ["reviews", status, limit ?? 50, offset ?? 0] as const,
  review: (id: string) => ["review", id] as const,
  audit: (filters: AuditFilters) => ["audit", filters] as const,
};

export function useCustomers(segment?: SegmentName, limit = 50, offset = 0) {
  return useQuery({
    queryKey: keys.customers(segment, limit, offset),
    queryFn: () => api.listCustomers({ segment, limit, offset }),
  });
}

export function useCustomer(customerId: string) {
  return useQuery({
    queryKey: keys.customer(customerId),
    queryFn: () => api.getCustomer(customerId),
  });
}

export function useReviews(status: MessageStatus, limit = 50, offset = 0) {
  return useQuery({
    queryKey: keys.reviews(status, limit, offset),
    queryFn: () => api.listReviews({ status, limit, offset }),
  });
}

export function useAudit(filters: AuditFilters, enabled = true) {
  return useQuery({
    queryKey: keys.audit(filters),
    queryFn: () => api.listAudit(filters),
    enabled,
  });
}

/** Store a review item returned by the API so the detail page can show it. */
export function rememberReview(client: QueryClient, item: ReviewItem): void {
  client.setQueryData(keys.review(item.review_id), item);
}

/**
 * The contract has no GET /api/reviews/{id}. The detail page uses the item the API
 * last returned (queue click, generate, edit, approve, reject) and otherwise looks
 * the ID up in the listable queues.
 */
export function useReview(reviewId: string) {
  return useQuery({
    queryKey: keys.review(reviewId),
    staleTime: Infinity,
    queryFn: async () => {
      for (const status of LISTABLE_REVIEW_STATUSES) {
        const page = await api.listReviews({ status, limit: 100 });
        const found = page.items.find((item) => item.review_id === reviewId);
        if (found) return found;
      }
      throw new ApiError(404, "review_not_found", "Review not found in the open queues.");
    },
  });
}

function useReviewMutation<TVars>(
  reviewId: string,
  call: (vars: TVars) => Promise<ReviewItem>,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: (item) => {
      rememberReview(client, item);
      void client.invalidateQueries({ queryKey: ["reviews"] });
      void client.invalidateQueries({ queryKey: ["audit"] });
    },
    onError: (error) => {
      // A 409 means our copy is stale; drop it so the next view refetches.
      if (error instanceof ApiError && error.status === 409) {
        void client.invalidateQueries({ queryKey: ["reviews"] });
      }
    },
    mutationKey: ["review-action", reviewId],
  });
}

export function useEditReview(reviewId: string) {
  return useReviewMutation(reviewId, (body: EditReviewRequest) =>
    api.editReview(reviewId, body),
  );
}

export function useRejectReview(reviewId: string) {
  return useReviewMutation(reviewId, (body: RejectRequest) => api.rejectReview(reviewId, body));
}

export function useApproveReview(reviewId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ApproveRequest) => api.approveReview(reviewId, body),
    onSuccess: (result) => {
      rememberReview(client, result.review);
      void client.invalidateQueries({ queryKey: ["reviews"] });
      void client.invalidateQueries({ queryKey: ["audit"] });
    },
    onError: () => {
      void client.invalidateQueries({ queryKey: ["reviews"] });
    },
  });
}

export function useEvaluate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (customerId: string) => api.evaluate(customerId),
    onSuccess: (decision) => {
      client.setQueryData(keys.evaluation(decision.customer_id), decision);
      void client.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

export function useGenerate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (customerId: string) => api.generate(customerId),
    onSuccess: (item) => {
      rememberReview(client, item);
      void client.invalidateQueries({ queryKey: ["reviews"] });
      void client.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
