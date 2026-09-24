import { useState } from "react";
import { Outlet } from "react-router-dom";

import { createTender } from "../api/tenders";
import { useTender } from "../context/TenderContext";
import Sidebar from "./Sidebar";

export default function Layout() {
  const { tenders, selectedTenderId, selectTender, refreshTenders } = useTender();
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  async function handleCreate() {
    if (!newName.trim()) return;
    const tender = await createTender({ competition_name: newName.trim() });
    await refreshTenders();
    selectTender(tender.id);
    setNewName("");
    setCreating(false);
  }

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-brand-600 bg-brand-700 px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium uppercase tracking-wide text-blue-200">Account</span>
            {tenders.length > 0 ? (
              <select
                className="rounded-md border border-white/30 bg-white px-2 py-1 text-sm text-slate-800"
                value={selectedTenderId ?? ""}
                onChange={(e) => selectTender(Number(e.target.value))}
              >
                {tenders.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.competition_name}
                  </option>
                ))}
              </select>
            ) : (
              <span className="text-sm text-blue-100">No Account yet</span>
            )}
          </div>

          {creating ? (
            <div className="flex items-end gap-2">
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-blue-100">
                  Competition name <span className="text-rose-300">*</span>
                </span>
                <input
                  autoFocus
                  className="rounded-md border border-white/30 px-2 py-1 text-sm"
                  placeholder="Competition name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                />
              </label>
              <button
                className="rounded-md bg-white px-3 py-1 text-sm font-medium text-brand-700 hover:bg-blue-50"
                onClick={handleCreate}
              >
                Create
              </button>
              <button className="text-sm text-blue-100 hover:text-white" onClick={() => setCreating(false)}>
                Cancel
              </button>
            </div>
          ) : (
            <button
              className="rounded-md border border-white bg-white px-3 py-1 text-sm font-medium text-brand-700 hover:bg-blue-50"
              onClick={() => setCreating(true)}
            >
              + New Account
            </button>
          )}
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
