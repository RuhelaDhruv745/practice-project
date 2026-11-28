import { useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";

import { rememberReview, useReviews } from "../api/hooks";
import { Badge, Card, Empty, ErrorAlert, Loading } from "../components/ui";
import type { MessageStatus } from "../types";
import { LISTABLE_REVIEW_STATUSES } from "../types";

export function ReviewQueuePage() {
  const [params, setParams] = useSearchParams();
  const status: MessageStatus =
    LISTABLE_REVIEW_STATUSES.find((s) => s === params.get("status")) ?? "pending_review";
  const query = useReviews(status, 100, 0);
  const client = useQueryClient();

  return (
    <>
      <h1 className="text-2xl font-semibold">Review queue</h1>
      <div className="flex gap-2" role="tablist">
        {LISTABLE_REVIEW_STATUSES.map((s) => (
          <button
            key={s}
            role="tab"
            aria-selected={s === status}
            className={
              s === status
                ? "rounded-md bg-indigo-600 px-3 py-1 text-sm text-white"
                : "rounded-md border border-slate-300 bg-white px-3 py-1 text-sm"
            }
            onClick={() => setParams({ status: s })}
          >
            {s}
          </button>
        ))}
      </div>
      <Card>
        {query.isPending ? (
          <Loading />
        ) : query.isError ? (
          <ErrorAlert error={query.error} />
        ) : query.data.items.length === 0 ? (
          <Empty>No {status} items.</Empty>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase text-slate-500">
                <th>Review</th>
                <th>Customer</th>
                <th>Status</th>
                <th>Segment</th>
                <th>Validation</th>
                <th>Subject</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((item) => (
                <tr key={item.review_id} className="border-t border-slate-100">
                  <td>
                    <Link
                      className="font-mono text-indigo-700"
                      to={`/reviews/${encodeURIComponent(item.review_id)}`}
                      onClick={() => rememberReview(client, item)}
                    >
                      {item.review_id}
                    </Link>
                  </td>
                  <td className="font-mono">{item.customer_id}</td>
                  <td>
                    <Badge value={item.status} />
                  </td>
                  <td>{item.decision.classification.primary_segment ?? "none"}</td>
                  <td>
                    {item.validation ? (
                      <Badge value={item.validation.passed ? "passed" : "failed"} />
                    ) : (
                      "-"
                    )}
                  </td>
                  <td>{item.message?.draft.subject ?? "-"}</td>
                  <td className="font-mono text-xs">{item.updated_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {query.isSuccess && (
          <p className="mt-2 text-xs text-slate-500">Total: {query.data.total}</p>
        )}
      </Card>
    </>
  );
}
