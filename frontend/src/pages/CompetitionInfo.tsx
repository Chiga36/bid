import { useEffect, useState } from "react";

import { addClarification, getScoringBands, listClarifications, setScoringBands } from "../api/tenders";
import type { BandValue, Clarification, ScoringBand } from "../api/types";
import { useTender } from "../context/TenderContext";

const BAND_VALUES: BandValue[] = [0, 25, 50, 75, 100];

export default function CompetitionInfo() {
  const { selectedTender, selectedTenderId } = useTender();
  const [bands, setBands] = useState<Record<BandValue, string>>({ 0: "", 25: "", 50: "", 75: "", 100: "" });
  const [savingBands, setSavingBands] = useState(false);
  const [clarifications, setClarifications] = useState<Clarification[]>([]);
  const [newClarification, setNewClarification] = useState("");

  useEffect(() => {
    if (!selectedTenderId) return;
    getScoringBands(selectedTenderId).then((existing) => {
      if (existing.length === 0) return;
      const next = { ...bands };
      existing.forEach((b) => (next[b.band_value] = b.descriptor_text));
      setBands(next);
    });
    listClarifications(selectedTenderId).then(setClarifications);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTenderId]);

  async function handleSaveBands() {
    if (!selectedTenderId) return;
    setSavingBands(true);
    const payload: ScoringBand[] = BAND_VALUES.filter((v) => bands[v].trim().length > 0).map((v) => ({
      band_value: v,
      descriptor_text: bands[v],
    }));
    await setScoringBands(selectedTenderId, payload);
    setSavingBands(false);
  }

  async function handleAddClarification() {
    if (!selectedTenderId || !newClarification.trim()) return;
    const created = await addClarification(selectedTenderId, { content_text: newClarification.trim() });
    setClarifications((prev) => [...prev, created]);
    setNewClarification("");
  }

  if (!selectedTenderId || !selectedTender) {
    return <p className="text-sm text-slate-500">Create or select a tender first (top right).</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-lg font-semibold text-slate-900">Competition Information</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <InfoField label="Competition Name" value={selectedTender.competition_name} />
        <InfoField label="Contract Reference" value={selectedTender.contract_reference ?? "—"} />
        <InfoField label="Purchasing Authority" value={selectedTender.purchasing_authority ?? "—"} />
        <InfoField label="Procedure Type" value={selectedTender.procedure_type ?? "—"} />
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="text-sm font-semibold text-slate-800">Scoring bands</p>
        <p className="mt-0.5 text-xs text-slate-500">
          This tender's own wording for each band — used verbatim by the Scoring agent, never reworded by the model.
        </p>
        <div className="mt-3 space-y-2">
          {BAND_VALUES.map((v) => (
            <div key={v} className="flex items-center gap-2">
              <span className="w-12 shrink-0 text-xs font-semibold text-slate-500">{v}</span>
              <input
                className="flex-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                placeholder={`Descriptor for band ${v}`}
                value={bands[v]}
                onChange={(e) => setBands((prev) => ({ ...prev, [v]: e.target.value }))}
              />
            </div>
          ))}
        </div>
        <button
          onClick={handleSaveBands}
          disabled={savingBands}
          className="mt-3 rounded-md bg-brand-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600"
        >
          {savingBands ? "Saving..." : "Save scoring bands"}
        </button>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="text-sm font-semibold text-slate-800">Clarification responses</p>
        <p className="mt-0.5 text-xs text-slate-500">
          Versioned and stored here. Resolving one into a question's locked register is a manual step — re-run Decompose on
          that question after reading it.
        </p>
        <ul className="mt-3 space-y-2">
          {clarifications.map((c) => (
            <li key={c.id} className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600">
              <span className="font-semibold text-slate-500">v{c.version_number}</span> — {c.content_text}
            </li>
          ))}
          {clarifications.length === 0 && <li className="text-xs text-slate-400">No clarifications yet.</li>}
        </ul>
        <div className="mt-3 flex gap-2">
          <input
            className="flex-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
            placeholder="New clarification text"
            value={newClarification}
            onChange={(e) => setNewClarification(e.target.value)}
          />
          <button
            onClick={handleAddClarification}
            className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}

function InfoField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-sm text-slate-800">{value}</p>
    </div>
  );
}
