import type { Draft } from "../api/types";

interface VersionHistoryPanelProps {
  drafts: Draft[];
  selectedDraftId: number | null;
  onSelect: (draft: Draft) => void;
}

export default function VersionHistoryPanel({ drafts, selectedDraftId, onSelect }: VersionHistoryPanelProps) {
  if (drafts.length === 0) {
    return <p className="text-xs text-slate-400">No versions saved yet.</p>;
  }
  return (
    <ul className="max-h-40 space-y-1 overflow-y-auto">
      {[...drafts].reverse().map((draft) => (
        <li key={draft.id}>
          <button
            onClick={() => onSelect(draft)}
            className={`w-full rounded-md border px-2 py-1.5 text-left text-xs transition-colors ${
              draft.id === selectedDraftId
                ? "border-brand-300 bg-brand-50 text-brand-700"
                : "border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            <span className="font-medium">v{draft.version_number}</span>{" "}
            <span className="text-slate-400">{new Date(draft.created_at).toLocaleString()}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
