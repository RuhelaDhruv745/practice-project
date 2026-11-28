// Small presentational primitives. Customer and draft text is always rendered as a
// React text node, never as HTML.
import type { ReactNode } from "react";

import { ApiError } from "../api/client";

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      {title && <h2 className="mb-3 text-lg font-semibold text-slate-800">{title}</h2>}
      {children}
    </section>
  );
}

export function Loading({ label = "Loading..." }: { label?: string }) {
  return (
    <p role="status" className="text-sm text-slate-500">
      {label}
    </p>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm italic text-slate-500">{children}</p>;
}

/** Show error.code / error.message from the API; never a stack trace. */
export function ErrorAlert({ error }: { error: unknown }) {
  const code = error instanceof ApiError ? error.code : "client_error";
  const message =
    error instanceof ApiError
      ? error.message || "The API returned an error."
      : "Something went wrong in the dashboard.";
  return (
    <div role="alert" className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">
      <span className="font-mono font-semibold">{code}</span>
      <span>: {message}</span>
    </div>
  );
}

const BADGE_TONES: Record<string, string> = {
  pending_review: "bg-amber-100 text-amber-800",
  blocked: "bg-red-100 text-red-800",
  rejected: "bg-slate-200 text-slate-700",
  approved: "bg-emerald-100 text-emerald-800",
  delivered: "bg-emerald-100 text-emerald-800",
  draft_allowed: "bg-emerald-100 text-emerald-800",
  passed: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
  blocking: "bg-red-100 text-red-800",
  warning: "bg-amber-100 text-amber-800",
};

export function Badge({ value }: { value: string }) {
  const tone = BADGE_TONES[value] ?? "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-block rounded px-2 py-0.5 font-mono text-xs ${tone}`}>{value}</span>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-900">{children}</dd>
    </div>
  );
}
