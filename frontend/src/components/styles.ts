// Shared class names and a value formatter (no business logic).

/** Render an evidence value exactly as the API sent it. */
export function show(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (Array.isArray(value)) return value.map(show).join(", ");
  return String(value);
}

export const buttonClass =
  "rounded-md px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50";
export const primaryButton = `${buttonClass} bg-indigo-600 text-white hover:bg-indigo-700`;
export const secondaryButton = `${buttonClass} border border-slate-300 bg-white text-slate-800 hover:bg-slate-50`;
export const dangerButton = `${buttonClass} bg-red-600 text-white hover:bg-red-700`;
export const inputClass =
  "w-full rounded-md border border-slate-300 px-2 py-1 text-sm focus:border-indigo-500 focus:outline-none";
