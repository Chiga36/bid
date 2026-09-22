type Tone = "green" | "amber" | "red" | "slate";

const TONE_CLASSES: Record<Tone, string> = {
  green: "bg-emerald-50 text-emerald-700 border-emerald-200",
  amber: "bg-amber-50 text-amber-700 border-amber-200",
  red: "bg-rose-50 text-rose-700 border-rose-200",
  slate: "bg-slate-100 text-slate-600 border-slate-200",
};

// Central place mapping backend status strings to a visual tone, so every page reads the same
// status the same way rather than each page inventing its own colour logic.
const STATUS_TONE: Record<string, Tone> = {
  addressed: "green",
  asserted_only: "amber",
  missing: "red",
  unverified: "red",
  high: "green",
  low: "amber",
  ready: "green",
  not_ready: "amber",
  passed: "green",
  failed: "red",
  // Prefixed deliberately: "high"/"low" above already mean confidence (high=good=green), the
  // opposite sense from urgency (high priority=urgent, not good) — these must not collide.
  priority_critical: "red",
  priority_high: "amber",
  priority_medium: "amber",
  priority_low: "slate",
};

export default function StatusPill({ label, status }: { label?: string; status: string }) {
  const tone = STATUS_TONE[status] ?? "slate";
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}>
      {label ?? status.replace(/_/g, " ")}
    </span>
  );
}
