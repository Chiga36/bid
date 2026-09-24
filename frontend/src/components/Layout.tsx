import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";

import { createTender } from "../api/tenders";
import { useTender } from "../context/TenderContext";
import Sidebar from "./Sidebar";

const SIDEBAR_COLLAPSED_KEY = "bid-coauthor:sidebar-collapsed";

export default function Layout() {
  const { tenders, selectedTenderId, selectTender, refreshTenders } = useTender();
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(sidebarCollapsed));
    } catch {
      // per-viewer convenience only — fine to lose this across a session if storage is unavailable
    }
  }, [sidebarCollapsed]);

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
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed((prev) => !prev)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-400">Tender</span>
            {tenders.length > 0 ? (
              <select
                className="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-800"
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
              <span className="text-sm text-slate-400">No tenders yet</span>
            )}
          </div>

          {creating ? (
            <div className="flex items-end gap-2">
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-slate-600">
                  Competition name <span className="text-rose-600">*</span>
                </span>
                <input
                  autoFocus
                  className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                  placeholder="Competition name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                />
              </label>
              <button
                className="rounded-md bg-brand-500 px-3 py-1 text-sm font-medium text-white hover:bg-brand-600"
                onClick={handleCreate}
              >
                Create
              </button>
              <button className="text-sm text-slate-500" onClick={() => setCreating(false)}>
                Cancel
              </button>
            </div>
          ) : (
            <button
              className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100"
              onClick={() => setCreating(true)}
            >
              + New tender
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
