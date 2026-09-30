import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { createTender, deleteTender } from "../api/tenders";
import type { Tender } from "../api/types";
import WebThreads from "../components/WebThreads";
import { useTender } from "../context/TenderContext";

export default function Home() {
  const { tenders, selectTender, refreshTenders } = useTender();
  const navigate = useNavigate();
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function handleCreated(id: number) {
    // New Tender -> straight to Data Ingestion, not Response Builder: there's nothing to draft
    // yet, and this is the natural next step for a first-time user. Existing Tenders (below)
    // skip straight to Response Builder since they've presumably already been ingested.
    await refreshTenders();
    selectTender(id);
    navigate("/ingestion");
  }

  function handleSelect(id: number) {
    selectTender(id);
    navigate("/builder");
  }

  // Irreversible — deletes every question/draft/evidence/agent-run for this tender, so a plain
  // click can't trigger it. "Delete" arms a confirm state on that same tile; a second click
  // ("Confirm delete") within it is the actual destructive action.
  async function handleDelete(id: number) {
    setDeletingId(id);
    try {
      await deleteTender(id);
      await refreshTenders();
    } finally {
      setDeletingId(null);
      setConfirmingDeleteId(null);
    }
  }

  return (
    <div className="relative min-h-full overflow-hidden bg-brand-700">
      <div className="absolute inset-0">
        <WebThreads
          color1="#00338D"
          color2="#5AA9E6"
          color3="#FFFFFF"
          speed={0.2}
          threadCount={6}
          frequency={5.0}
          spread={0.18}
          taper={1.0}
          position={0.12}
          fanMode="center"
          glow={0.02}
          falloff={0.6}
          thickness={1.1}
          brightness={0.7}
          opacity={1.0}
          mirror={true}
          shimmer={false}
          grain={true}
          grainIntensity={0.05}
          mouseInteraction={true}
          mouseStrength={0.3}
        />
      </div>

      <div className="relative flex flex-col gap-12 px-10 py-12">
        <div className="flex flex-col gap-4">
          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-white/30 bg-white/10 px-3 py-1 text-xs font-medium text-white backdrop-blur-sm">
            <span aria-hidden>✦</span> AI-Powered Bid Assistant
          </span>

          <h1 className="text-5xl font-bold tracking-tight text-white">
            Bid<span className="font-light text-blue-200">Co</span>
          </h1>

          <p className="max-w-xl text-sm leading-relaxed text-blue-100">
            Draft, decompose and score UK public-sector tender responses end to end — extract requirements and
            evaluation criteria straight from the tender documents, get an expert critique from a theme specialist,
            and check every answer against what the buyer actually asked for before you submit.
          </p>
        </div>

        <div>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-blue-100">Tenders</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <NewAccountTile onCreated={handleCreated} />
            {tenders.map((t) => (
              <AccountTile
                key={t.id}
                tender={t}
                onClick={() => handleSelect(t.id)}
                confirmingDelete={confirmingDeleteId === t.id}
                deleting={deletingId === t.id}
                onRequestDelete={() => setConfirmingDeleteId(t.id)}
                onCancelDelete={() => setConfirmingDeleteId(null)}
                onConfirmDelete={() => handleDelete(t.id)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function AccountTile({
  tender,
  onClick,
  confirmingDelete,
  deleting,
  onRequestDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  tender: Tender;
  onClick: () => void;
  confirmingDelete: boolean;
  deleting: boolean;
  onRequestDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  return (
    <div className="group relative flex flex-col gap-2 rounded-xl border border-white/20 bg-white/5 p-4 backdrop-blur-sm transition-colors hover:border-white/40 hover:bg-white/10">
      <button onClick={onClick} className="flex flex-col gap-2 text-left" disabled={confirmingDelete}>
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-white">
          <FolderIcon className="h-4 w-4" />
        </span>
        <span className="mt-1 truncate text-sm font-semibold text-white">{tender.competition_name}</span>
        <span className="truncate text-xs text-blue-100/80">{tender.purchasing_authority ?? tender.contract_reference ?? "—"}</span>
      </button>

      {confirmingDelete ? (
        <div className="flex items-center gap-2 border-t border-white/10 pt-2">
          <span className="flex-1 text-[11px] text-rose-200">Delete permanently?</span>
          <button
            onClick={onConfirmDelete}
            disabled={deleting}
            className="rounded-md bg-rose-500 px-2 py-1 text-[11px] font-medium text-white hover:bg-rose-600 disabled:opacity-50"
          >
            {deleting ? "Deleting..." : "Confirm delete"}
          </button>
          <button onClick={onCancelDelete} disabled={deleting} className="text-[11px] text-blue-100 hover:text-white">
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={onRequestDelete}
          title="Delete tender"
          aria-label={`Delete ${tender.competition_name}`}
          className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-md text-blue-100/60 opacity-0 transition-opacity hover:bg-white/10 hover:text-rose-300 group-hover:opacity-100"
        >
          <TrashIcon className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

// This tile IS the account-creation entry point on Home — a persistent first tile in the grid
// (present whether zero or many Tenders exist), not a separate empty-state layout. Styled as a
// solid light card (matching the reference's "New Project" tile) so it reads as the clear primary
// action against the dark, animated surroundings.
function NewAccountTile({ onCreated }: { onCreated: (id: number) => void }) {
  const [open, setOpen] = useState(false);

  if (open) {
    return (
      <div className="rounded-xl bg-white p-4 shadow-lg">
        <NewAccountForm onCreated={onCreated} onCancel={() => setOpen(false)} />
      </div>
    );
  }

  return (
    <button
      onClick={() => setOpen(true)}
      className="flex flex-col justify-center gap-2 rounded-xl bg-white p-4 text-left shadow-lg transition-transform hover:-translate-y-0.5"
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-lg leading-none text-white">+</span>
      <span className="mt-1 text-sm font-semibold text-slate-800">New Tender</span>
      <span className="text-xs text-slate-400">Start fresh</span>
    </button>
  );
}

function NewAccountForm({ onCreated, onCancel }: { onCreated: (id: number) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleCreate() {
    if (!name.trim()) return;
    setSaving(true);
    const tender = await createTender({ competition_name: name.trim() });
    setSaving(false);
    setName("");
    onCreated(tender.id);
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="flex flex-col gap-1 text-left">
        <span className="text-xs font-medium text-slate-600">
          Competition name <span className="text-rose-600">*</span>
        </span>
        <input
          autoFocus
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          placeholder="e.g. Technology and Data Services 2027-2032"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreate()}
        />
      </label>
      <div className="flex items-center gap-2">
        <button
          onClick={handleCreate}
          disabled={saving || !name.trim()}
          className="rounded-md bg-brand-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saving ? "Creating..." : "Create account"}
        </button>
        <button onClick={onCancel} className="text-xs text-slate-500 hover:text-slate-700">
          Cancel
        </button>
      </div>
    </div>
  );
}

function FolderIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M3.5 6.5a1 1 0 011-1h5l2 2h8a1 1 0 011 1v9a1 1 0 01-1 1h-15a1 1 0 01-1-1v-11z" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M4 6.5h16" />
      <path d="M8.5 6.5V5a1.5 1.5 0 011.5-1.5h4A1.5 1.5 0 0115.5 5v1.5" />
      <path d="M6.5 6.5l1 13.5a1.5 1.5 0 001.5 1.5h6a1.5 1.5 0 001.5-1.5l1-13.5" />
    </svg>
  );
}
