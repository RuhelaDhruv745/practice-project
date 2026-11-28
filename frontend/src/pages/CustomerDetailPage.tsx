import { useNavigate, useParams } from "react-router";

import { useCustomer, useEvaluate, useGenerate } from "../api/hooks";
import { DecisionPanel } from "../components/panels";
import { primaryButton, secondaryButton } from "../components/styles";
import { Card, ErrorAlert, Field, Loading } from "../components/ui";

export function CustomerDetailPage() {
  const { customerId = "" } = useParams();
  const navigate = useNavigate();
  const customer = useCustomer(customerId);
  const evaluate = useEvaluate();
  const generate = useGenerate();
  const decision = evaluate.data;

  const onGenerate = () =>
    generate.mutate(customerId, {
      onSuccess: (item) => navigate(`/reviews/${encodeURIComponent(item.review_id)}`),
    });

  return (
    <>
      <h1 className="text-2xl font-semibold">
        Customer <span className="font-mono">{customerId}</span>
      </h1>
      {customer.isPending ? (
        <Loading />
      ) : customer.isError ? (
        <ErrorAlert error={customer.error} />
      ) : (
        <>
          <Card title="Profile">
            <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Field label="First name">{customer.data.first_name}</Field>
              <Field label="Plan">{customer.data.plan}</Field>
              <Field label="Marketing consent">
                {customer.data.consent_marketing ? "yes" : "no"}
              </Field>
              <Field label="Months active">{customer.data.months_active}</Field>
              <Field label="Activity (30d)">{customer.data.activity_score_30d}</Field>
              <Field label="Activity (prev 30d)">{customer.data.activity_score_prev_30d}</Field>
              <Field label="On-time payments (12m)">{customer.data.on_time_payments_12m}</Field>
              <Field label="Bill status">{customer.data.bill_status}</Field>
              <Field label="Days overdue">{customer.data.days_overdue}</Field>
              <Field label="Amount due">{customer.data.amount_due}</Field>
              <Field label="Due date">{customer.data.due_date ?? "-"}</Field>
              <Field label="Last contacted (days ago)">
                {customer.data.last_contacted_days_ago ?? "never"}
              </Field>
            </dl>
            <div className="mt-4 flex gap-3">
              <button
                className={secondaryButton}
                disabled={evaluate.isPending}
                onClick={() => evaluate.mutate(customerId)}
              >
                {evaluate.isPending ? "Evaluating..." : "Evaluate"}
              </button>
              <button className={primaryButton} disabled={generate.isPending} onClick={onGenerate}>
                {generate.isPending ? "Generating..." : "Generate draft"}
              </button>
            </div>
          </Card>
          {evaluate.isError && <ErrorAlert error={evaluate.error} />}
          {generate.isError && <ErrorAlert error={generate.error} />}
          {decision && <DecisionPanel decision={decision} />}
        </>
      )}
    </>
  );
}
