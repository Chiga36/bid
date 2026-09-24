import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { useTender } from "../context/TenderContext";
import Sidebar from "./Sidebar";

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

// The account selector/creator that used to live here was a duplicate of what the Home page's
// own Accounts section already does — switching or creating an account now happens there.
// This is just a lightweight "you are here" indicator + a way back to that section.
function AccountBadge() {
  const { selectedTender } = useTender();
  const navigate = useNavigate();

  if (!selectedTender) return null;

  return (
    <button
      onClick={() => navigate("/")}
      title={selectedTender.competition_name}
      className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-xs font-semibold text-brand-700 hover:ring-2 hover:ring-white/50"
    >
      {initials(selectedTender.competition_name)}
    </button>
  );
}

export default function Layout() {
  const isHome = useLocation().pathname === "/";

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-end border-b border-brand-600 bg-brand-700 px-6 py-3">
          <AccountBadge />
        </header>
        <main className={`flex-1 overflow-y-auto ${isHome ? "" : "p-6"}`}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
