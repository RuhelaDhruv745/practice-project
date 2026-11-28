// Counts come straight from the API's `total` fields; nothing is recomputed here.
import { useQueries } from "@tanstack/react-query";
import { Link } from "react-router";

import { api } from "../api/client";
import { keys } from "../api/hooks";
import { Card, ErrorAlert, Loading } from "../components/ui";
import { LISTABLE_REVIEW_STATUSES, SEGMENT_NAMES } from "../types";

function CountTile({ label, value, to }: { label: string; value: number; to: string }) {
  return (
    <Link to={to} className="block rounded-md border border-slate-200 p-3 hover:bg-slate-50">
      <p className="text-xs uppercase text-slate-500">{label}</p>
      <p className="text-2xl font-semibold" data-testid={`count-${label}`}>
        {value}
      </p>
    </Link>
  );
}

export function DashboardPage() {
  const statusQueries = useQueries({
    queries: LISTABLE_REVIEW_STATUSES.map((status) => ({
      queryKey: keys.reviews(status, 1, 0),
      queryFn: () => api.listReviews({ status, limit: 1, offset: 0 }),
    })),
  });
  const allCustomers = useQueries({
    queries: [
      {
        queryKey: keys.customers(undefined, 1, 0),
        queryFn: () => api.listCustomers({ limit: 1, offset: 0 }),
      },
    ],
  })[0];
  const segmentQueries = useQueries({
    queries: SEGMENT_NAMES.map((segment) => ({
      queryKey: keys.customers(segment, 1, 0),
      queryFn: () => api.listCustomers({ segment, limit: 1, offset: 0 }),
    })),
  });

  const all = [...statusQueries, allCustomers, ...segmentQueries];
  const failed = all.find((q) => q.isError);

  return (
    <>
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      {failed && <ErrorAlert error={failed.error} />}
      <Card title="Review items by status">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {LISTABLE_REVIEW_STATUSES.map((status, i) => {
            const q = statusQueries[i];
            if (q.isPending) return <Loading key={status} />;
            if (q.isError) return null;
            return (
              <CountTile key={status} label={status} value={q.data.total} to="/reviews" />
            );
          })}
        </div>
      </Card>
      <Card title="Customers by primary segment">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
          {allCustomers.isPending ? (
            <Loading />
          ) : allCustomers.isError ? null : (
            <CountTile label="all customers" value={allCustomers.data.total} to="/customers" />
          )}
          {SEGMENT_NAMES.map((segment, i) => {
            const q = segmentQueries[i];
            if (q.isPending) return <Loading key={segment} />;
            if (q.isError) return null;
            return (
              <CountTile
                key={segment}
                label={segment}
                value={q.data.total}
                to={`/customers?segment=${segment}`}
              />
            );
          })}
        </div>
      </Card>
    </>
  );
}
