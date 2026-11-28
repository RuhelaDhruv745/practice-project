import { useSearchParams } from "react-router";

import { useAudit } from "../api/hooks";
import { AuditTable } from "../components/panels";
import { inputClass } from "../components/styles";
import { Card, ErrorAlert, Loading } from "../components/ui";
import { AUDIT_EVENT_TYPES } from "../types";

export function AuditPage() {
  const [params, setParams] = useSearchParams();
  const customerId = params.get("customer_id") ?? "";
  const reviewId = params.get("review_id") ?? "";
  const eventType = AUDIT_EVENT_TYPES.find((t) => t === params.get("event_type"));
  const query = useAudit({
    customer_id: customerId || undefined,
    review_id: reviewId || undefined,
    event_type: eventType,
    limit: 100,
  });

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };

  return (
    <>
      <h1 className="text-2xl font-semibold">Audit log</h1>
      <Card>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <label className="text-sm">
            Customer ID
            <input
              className={inputClass}
              value={customerId}
              placeholder="CUST-001"
              onChange={(e) => set("customer_id", e.target.value.trim())}
            />
          </label>
          <label className="text-sm">
            Review ID
            <input
              className={inputClass}
              value={reviewId}
              onChange={(e) => set("review_id", e.target.value.trim())}
            />
          </label>
          <label className="text-sm">
            Event type
            <select
              className={inputClass}
              value={eventType ?? ""}
              onChange={(e) => set("event_type", e.target.value)}
            >
              <option value="">All</option>
              {AUDIT_EVENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
        </div>
      </Card>
      <Card>
        {query.isPending ? (
          <Loading />
        ) : query.isError ? (
          <ErrorAlert error={query.error} />
        ) : (
          <>
            <AuditTable events={query.data.items} />
            <p className="mt-2 text-xs text-slate-500">Total: {query.data.total} (newest first)</p>
          </>
        )}
      </Card>
    </>
  );
}
