// Read-only panels that display what the backend decided. Nothing here computes a
// segment, eligibility, amount, date or validation result.
import type { AuditEvent, PolicyDecision, ReviewItem, ValidationResult } from "../types";
import { show } from "./styles";
import { Badge, Card, Empty, Field } from "./ui";

function Evidence({ evidence }: { evidence: Record<string, unknown> | undefined }) {
  const entries = Object.entries(evidence ?? {});
  if (entries.length === 0) return null;
  return (
    <ul className="ml-4 list-disc text-xs text-slate-600">
      {entries.map(([key, value]) => (
        <li key={key}>
          <span className="font-mono">{key}</span>: {show(value)}
        </li>
      ))}
    </ul>
  );
}

export function DecisionPanel({ decision }: { decision: PolicyDecision }) {
  const { classification, strategy, facts } = decision;
  return (
    <div className="space-y-4">
      <Card title="Policy decision">
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Field label="Decision">
            <Badge value={decision.status} />
          </Field>
          <Field label="Primary segment">{classification.primary_segment ?? "none"}</Field>
          <Field label="As of date">{classification.as_of_date}</Field>
          <Field label="Policy versions">
            {Object.entries(classification.policy_versions)
              .map(([name, version]) => `${name} ${version}`)
              .join(", ") || "-"}
          </Field>
        </dl>
        {decision.status === "blocked" && (
          <div className="mt-3 rounded-md border border-red-300 bg-red-50 p-3" aria-label="Block reasons">
            <p className="text-sm font-semibold text-red-800">Outreach blocked by policy</p>
            <ul className="ml-4 list-disc text-sm text-red-800">
              {(decision.block_reasons ?? []).map((reason) => (
                <li key={reason} className="font-mono">
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      <Card title="Segments and reasons">
        {classification.segments.length === 0 ? (
          <Empty>No segment assigned.</Empty>
        ) : (
          <ul className="space-y-3">
            {classification.segments.map((assignment) => (
              <li key={assignment.segment} className="rounded border border-slate-200 p-3">
                <div className="flex items-center gap-3">
                  <Badge value={assignment.segment} />
                  <span className="text-sm text-slate-600">
                    confidence {show(assignment.confidence)}
                  </span>
                </div>
                <ul className="mt-2 space-y-1">
                  {assignment.reasons.map((reason) => (
                    <li key={reason.code} className="text-sm">
                      <span className="font-mono font-semibold">{reason.code}</span>:{" "}
                      {reason.description}
                      <Evidence evidence={reason.evidence} />
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Strategy">
        {strategy ? (
          <dl className="grid grid-cols-2 gap-3">
            <Field label="Segment">{strategy.segment}</Field>
            <Field label="Objective">{strategy.objective}</Field>
            <Field label="Tone">{strategy.tone}</Field>
            <Field label="Offer allowed">{strategy.offer_allowed ? "yes" : "no"}</Field>
            <div className="col-span-2">
              <Field label="Tone guidance">{strategy.tone_guidance}</Field>
            </div>
          </dl>
        ) : (
          <Empty>No strategy (outreach blocked).</Empty>
        )}
      </Card>

      <Card title="Offer checks">
        {(decision.offer_checks ?? []).length === 0 ? (
          <Empty>No offers checked.</Empty>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase text-slate-500">
                <th>Offer</th>
                <th>Eligible</th>
                <th>Failed rules</th>
              </tr>
            </thead>
            <tbody>
              {(decision.offer_checks ?? []).map((check) => (
                <tr key={check.offer_id} className="border-t border-slate-100">
                  <td className="font-mono">{check.offer_id}</td>
                  <td>{check.eligible ? "yes" : "no"}</td>
                  <td className="font-mono text-xs">{(check.failed_rules ?? []).join(", ") || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="Verified facts">
        {facts ? (
          <dl className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <Field label="First name">{facts.first_name}</Field>
            <Field label="Plan">{facts.plan}</Field>
            <Field label="Segment">{facts.segment}</Field>
            <Field label="Offer">
              {facts.offer
                ? `${facts.offer.offer_id}: ${facts.offer.description} (${facts.offer.value} ${facts.offer.unit}, expires ${facts.offer.expiry})`
                : "none"}
            </Field>
            <Field label="Reminder stage">{facts.reminder ? facts.reminder.stage : "none"}</Field>
            {facts.reminder && (
              <Field label="Amount due">
                {facts.reminder.amount_due} {facts.reminder.currency}, due {facts.reminder.due_date},{" "}
                {facts.reminder.days_overdue} days overdue
              </Field>
            )}
          </dl>
        ) : (
          <Empty>No facts released for drafting.</Empty>
        )}
      </Card>
    </div>
  );
}

export function ValidationPanel({ validation }: { validation: ValidationResult | null }) {
  if (!validation) {
    return (
      <Card title="Validation">
        <Empty>No draft was validated (blocked by policy before drafting).</Empty>
      </Card>
    );
  }
  const findings = validation.findings ?? [];
  return (
    <Card title="Validation">
      <div className="mb-2 flex items-center gap-3 text-sm">
        <Badge value={validation.passed ? "passed" : "failed"} />
        <span className="text-slate-500">validator {validation.validator_version}</span>
      </div>
      {findings.length === 0 ? (
        <Empty>No findings.</Empty>
      ) : (
        <ul className="space-y-2" aria-label="Validation findings">
          {findings.map((finding, index) => (
            <li
              key={`${finding.code}-${index}`}
              className={
                finding.severity === "blocking"
                  ? "rounded border border-red-300 bg-red-50 p-2 text-sm"
                  : "rounded border border-amber-300 bg-amber-50 p-2 text-sm"
              }
            >
              <div className="flex items-center gap-2">
                <Badge value={finding.severity} />
                <span className="font-mono font-semibold">{finding.code}</span>
              </div>
              <p>{finding.message}</p>
              <Evidence evidence={finding.evidence} />
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-slate-500">
        Checks run: {validation.checks_run.join(", ") || "-"}
      </p>
    </Card>
  );
}

export function DraftPreview({ item }: { item: ReviewItem }) {
  const message = item.message;
  if (!message) {
    return (
      <Card title="Draft">
        <Empty>No draft: the policy gate refused outreach.</Empty>
      </Card>
    );
  }
  return (
    <Card title={`Draft (revision ${item.revision})`}>
      <p className="text-xs text-slate-500">
        source {message.source}, {message.provider}/{message.model}, prompt {message.prompt_version}
      </p>
      <h3 className="mt-2 font-semibold" data-testid="draft-subject">
        {message.draft.subject}
      </h3>
      <p className="mt-2 whitespace-pre-wrap text-sm" data-testid="draft-body">
        {message.draft.body}
      </p>
    </Card>
  );
}

export function DecisionHistory({ item }: { item: ReviewItem }) {
  const decisions = item.decisions ?? [];
  return (
    <Card title="Reviewer actions">
      {decisions.length === 0 ? (
        <Empty>No reviewer actions yet.</Empty>
      ) : (
        <ul className="space-y-1 text-sm">
          {decisions.map((d, index) => (
            <li key={`${d.decided_at}-${index}`}>
              <span className="font-mono">{d.decided_at}</span> <Badge value={d.action} />{" "}
              {d.reviewer_id}
              {d.comment ? `: ${d.comment}` : ""}
              {d.rubric &&
                ` (relevance ${d.rubric.relevance}, clarity ${d.rubric.clarity}, personalisation ${d.rubric.personalisation}, call to action ${d.rubric.call_to_action}, tone ${d.rubric.tone})`}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function AuditTable({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) return <Empty>No audit events.</Empty>;
  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="text-xs uppercase text-slate-500">
          <th>Time</th>
          <th>Event</th>
          <th>Actor</th>
          <th>Customer</th>
          <th>Review</th>
          <th>Details</th>
        </tr>
      </thead>
      <tbody>
        {events.map((event) => (
          <tr key={event.event_id} className="border-t border-slate-100 align-top">
            <td className="font-mono text-xs">{event.occurred_at}</td>
            <td>
              <Badge value={event.event_type} />
            </td>
            <td>{event.actor}</td>
            <td className="font-mono text-xs">{event.customer_id ?? "-"}</td>
            <td className="font-mono text-xs">{event.review_id ?? "-"}</td>
            <td className="text-xs">
              {Object.entries(event.details ?? {})
                .map(([key, value]) => `${key}=${show(value)}`)
                .join("; ") || "-"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
