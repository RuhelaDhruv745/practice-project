// Review detail: evidence, decision, draft, validation, reviewer actions, audit.
// The approve control is a visual guard only; the backend re-validates and may 409.
import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router";

import { canApprove, canEdit, canReject } from "../api/guards";
import {
  useApproveReview,
  useAudit,
  useEditReview,
  useRejectReview,
  useReview,
} from "../api/hooks";
import {
  AuditTable,
  DecisionHistory,
  DecisionPanel,
  DraftPreview,
  ValidationPanel,
} from "../components/panels";
import { dangerButton, inputClass, primaryButton, secondaryButton } from "../components/styles";
import { Badge, Card, ErrorAlert, Loading } from "../components/ui";
import type { OutboxRecord, ReviewItem, ReviewRubric } from "../types";

const DEFAULT_REVIEWER = "reviewer-1";

const RUBRIC_FIELDS = [
  ["relevance", "Relevance"],
  ["clarity", "Clarity"],
  ["personalisation", "Personalisation"],
  ["call_to_action", "Call to action"],
  ["tone", "Tone"],
] as const satisfies readonly (readonly [keyof ReviewRubric, string])[];

type RubricDraft = Partial<Record<keyof ReviewRubric, number>>;

function ReviewerField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <label className="block text-sm">
      Reviewer ID
      <input className={inputClass} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function EditForm({ item, reviewer }: { item: ReviewItem; reviewer: string }) {
  const edit = useEditReview(item.review_id);
  const [subject, setSubject] = useState(item.message?.draft.subject ?? "");
  const [body, setBody] = useState(item.message?.draft.body ?? "");
  const [comment, setComment] = useState("");

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    edit.mutate({
      reviewer_id: reviewer,
      draft: { subject, body },
      comment: comment.trim() ? comment : null,
    });
  };

  return (
    <Card title="Edit draft">
      <form className="space-y-2" onSubmit={onSubmit}>
        <label className="block text-sm">
          Subject
          <input className={inputClass} value={subject} onChange={(e) => setSubject(e.target.value)} />
        </label>
        <label className="block text-sm">
          Body
          <textarea
            className={`${inputClass} h-40`}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          Edit comment (optional)
          <input className={inputClass} value={comment} onChange={(e) => setComment(e.target.value)} />
        </label>
        <button type="submit" className={secondaryButton} disabled={edit.isPending}>
          {edit.isPending ? "Re-validating..." : "Save edit and re-validate"}
        </button>
      </form>
      {edit.isError && <ErrorAlert error={edit.error} />}
      {edit.isSuccess && (
        <p role="status" className="mt-2 text-sm">
          Re-validated revision {edit.data.revision}:{" "}
          <Badge value={edit.data.validation?.passed ? "passed" : "failed"} /> status{" "}
          <Badge value={edit.data.status} />
        </p>
      )}
    </Card>
  );
}

function RubricInputs({
  rubric,
  onChange,
}: {
  rubric: RubricDraft;
  onChange: (next: RubricDraft) => void;
}) {
  return (
    <fieldset className="grid grid-cols-2 gap-2 md:grid-cols-5">
      <legend className="text-sm">Rubric (optional, 1-5; fill all five or none)</legend>
      {RUBRIC_FIELDS.map(([key, label]) => (
        <label key={key} className="text-xs">
          {label}
          <select
            className={inputClass}
            value={rubric[key] ?? ""}
            onChange={(e) =>
              onChange({ ...rubric, [key]: e.target.value ? Number(e.target.value) : undefined })
            }
          >
            <option value="">-</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      ))}
    </fieldset>
  );
}

/** The rubric is sent only when complete; the API validates the scores. */
function completeRubric(draft: RubricDraft): ReviewRubric | null | "partial" {
  const values = RUBRIC_FIELDS.map(([key]) => draft[key]);
  if (values.every((v) => v === undefined)) return null;
  if (values.some((v) => v === undefined)) return "partial";
  return draft as ReviewRubric;
}

function ApprovePanel({
  item,
  reviewer,
  onDelivered,
}: {
  item: ReviewItem;
  reviewer: string;
  onDelivered: (outbox: OutboxRecord) => void;
}) {
  const approve = useApproveReview(item.review_id);
  const [comment, setComment] = useState("");
  const [rubric, setRubric] = useState<RubricDraft>({});
  const complete = completeRubric(rubric);

  return (
    <Card title="Approve">
      <div className="space-y-2">
        <RubricInputs rubric={rubric} onChange={setRubric} />
        <label className="block text-sm">
          Comment (optional)
          <input className={inputClass} value={comment} onChange={(e) => setComment(e.target.value)} />
        </label>
        {complete === "partial" && (
          <p className="text-xs text-amber-700">Fill all five rubric scores or clear them.</p>
        )}
        <button
          className={primaryButton}
          disabled={approve.isPending || complete === "partial"}
          onClick={() =>
            complete !== "partial" &&
            approve.mutate(
              {
                reviewer_id: reviewer,
                comment: comment.trim() ? comment : null,
                rubric: complete,
              },
              { onSuccess: (result) => onDelivered(result.outbox) },
            )
          }
        >
          {approve.isPending ? "Approving..." : "Approve and deliver to mock outbox"}
        </button>
      </div>
      {approve.isError && <ErrorAlert error={approve.error} />}
    </Card>
  );
}

function RejectPanel({ item, reviewer }: { item: ReviewItem; reviewer: string }) {
  const reject = useRejectReview(item.review_id);
  const [reason, setReason] = useState("");
  const hasReason = reason.trim().length > 0;

  return (
    <Card title="Reject">
      <label className="block text-sm">
        Reason (required)
        <textarea
          className={`${inputClass} h-20`}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </label>
      <button
        className={`${dangerButton} mt-2`}
        disabled={!hasReason || reject.isPending}
        onClick={() => hasReason && reject.mutate({ reviewer_id: reviewer, comment: reason })}
      >
        {reject.isPending ? "Rejecting..." : "Reject"}
      </button>
      {reject.isError && <ErrorAlert error={reject.error} />}
    </Card>
  );
}

function OutboxNotice({ outbox }: { outbox: OutboxRecord }) {
  return (
    <div role="status" className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm">
      Delivered to the mock outbox at <span className="font-mono">{outbox.delivered_at}</span> via{" "}
      {outbox.channel}, approved by {outbox.approved_by}.
    </div>
  );
}

function ApproveUnavailable({ item }: { item: ReviewItem }) {
  if (item.status !== "pending_review" && item.status !== "blocked") return null;
  const why =
    item.decision.status === "blocked"
      ? "Outreach was blocked by policy; this item can never be approved."
      : item.validation?.passed === false
        ? "Validation failed; edit the draft until it passes, or reject it."
        : "This item is not in a state the API will approve.";
  return (
    <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800" data-testid="approve-unavailable">
      Approve unavailable. {why}
    </div>
  );
}

export function ReviewDetailPage() {
  const { reviewId = "" } = useParams();
  const review = useReview(reviewId);
  const audit = useAudit({ review_id: reviewId, limit: 100 }, reviewId !== "");
  const [reviewer, setReviewer] = useState(DEFAULT_REVIEWER);
  const [outbox, setOutbox] = useState<OutboxRecord | null>(null);

  if (review.isPending) return <Loading />;
  if (review.isError) return <ErrorAlert error={review.error} />;
  const item = review.data;

  return (
    <>
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">
          Review <span className="font-mono">{item.review_id}</span>
        </h1>
        <Badge value={item.status} />
        <Link className="text-sm text-indigo-700" to={`/customers/${item.customer_id}`}>
          {item.customer_id}
        </Link>
      </div>
      {outbox && <OutboxNotice outbox={outbox} />}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <DraftPreview item={item} />
          <ValidationPanel validation={item.validation} />
          <Card title="Reviewer">
            <ReviewerField value={reviewer} onChange={setReviewer} />
          </Card>
          {canApprove(item) ? (
            <ApprovePanel item={item} reviewer={reviewer} onDelivered={setOutbox} />
          ) : (
            <ApproveUnavailable item={item} />
          )}
          {canEdit(item) && (
            <EditForm key={item.review_id} item={item} reviewer={reviewer} />
          )}
          {canReject(item) && <RejectPanel item={item} reviewer={reviewer} />}
          <DecisionHistory item={item} />
        </div>
        <div className="space-y-4">
          <DecisionPanel decision={item.decision} />
        </div>
      </div>

      <Card title="Audit trail">
        {audit.isPending ? (
          <Loading />
        ) : audit.isError ? (
          <ErrorAlert error={audit.error} />
        ) : (
          <AuditTable events={audit.data.items} />
        )}
      </Card>
    </>
  );
}
