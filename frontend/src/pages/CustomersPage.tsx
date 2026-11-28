import { Link, useSearchParams } from "react-router";

import { useCustomers } from "../api/hooks";
import { inputClass, secondaryButton } from "../components/styles";
import { Badge, Card, Empty, ErrorAlert, Loading } from "../components/ui";
import type { SegmentName } from "../types";
import { SEGMENT_NAMES } from "../types";

const PAGE_SIZE = 25;

function parseSegment(value: string | null): SegmentName | undefined {
  return SEGMENT_NAMES.find((s) => s === value);
}

export function CustomersPage() {
  const [params, setParams] = useSearchParams();
  const segment = parseSegment(params.get("segment"));
  const offset = Math.max(0, Number(params.get("offset") ?? 0) || 0);
  const query = useCustomers(segment, PAGE_SIZE, offset);

  const update = (next: { segment?: string; offset?: number }) => {
    const merged = new URLSearchParams(params);
    if (next.segment !== undefined) {
      if (next.segment) merged.set("segment", next.segment);
      else merged.delete("segment");
      merged.delete("offset");
    }
    if (next.offset !== undefined) merged.set("offset", String(next.offset));
    setParams(merged);
  };

  return (
    <>
      <h1 className="text-2xl font-semibold">Customers</h1>
      <Card>
        <label className="flex items-center gap-2 text-sm">
          Segment
          <select
            className={`${inputClass} w-56`}
            value={segment ?? ""}
            onChange={(e) => update({ segment: e.target.value })}
          >
            <option value="">All</option>
            {SEGMENT_NAMES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </Card>
      <Card>
        {query.isPending ? (
          <Loading />
        ) : query.isError ? (
          <ErrorAlert error={query.error} />
        ) : query.data.items.length === 0 ? (
          <Empty>No customers match.</Empty>
        ) : (
          <>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase text-slate-500">
                  <th>Customer</th>
                  <th>First name</th>
                  <th>Plan</th>
                  <th>Bill status</th>
                  <th>Marketing consent</th>
                  <th>Primary segment</th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((c) => (
                  <tr key={c.customer_id} className="border-t border-slate-100">
                    <td>
                      <Link className="font-mono text-indigo-700" to={`/customers/${c.customer_id}`}>
                        {c.customer_id}
                      </Link>
                    </td>
                    <td>{c.first_name}</td>
                    <td>{c.plan}</td>
                    <td>{c.bill_status}</td>
                    <td>{c.consent_marketing ? "yes" : "no"}</td>
                    <td>{c.primary_segment ? <Badge value={c.primary_segment} /> : "none"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-3 flex items-center gap-3 text-sm">
              <button
                className={secondaryButton}
                disabled={offset === 0}
                onClick={() => update({ offset: Math.max(0, offset - PAGE_SIZE) })}
              >
                Previous
              </button>
              <span>
                {offset + 1}-{offset + query.data.items.length} of {query.data.total}
              </span>
              <button
                className={secondaryButton}
                disabled={offset + query.data.items.length >= query.data.total}
                onClick={() => update({ offset: offset + PAGE_SIZE })}
              >
                Next
              </button>
            </div>
          </>
        )}
      </Card>
    </>
  );
}
