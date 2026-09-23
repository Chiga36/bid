import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/builder", label: "Response Builder" },
  { to: "/ingestion", label: "Data Ingestion" },
  { to: "/status", label: "Status Report" },
  { to: "/info", label: "Competition Info" },
  { to: "/skills", label: "Agent Skills" },
];

export default function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  if (collapsed) {
    return (
      <aside className="flex w-14 shrink-0 flex-col items-center border-r border-slate-200 bg-white py-4">
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-500 text-sm font-semibold text-white">
          B
        </span>
        <button
          onClick={onToggle}
          title="Expand sidebar"
          aria-label="Expand sidebar"
          className="mt-4 flex h-6 w-6 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          ›
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-5 py-4">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-500 text-sm font-semibold text-white">
            B
          </span>
          <span className="text-sm font-semibold text-slate-900">Bid Co-author</span>
        </div>
        <button
          onClick={onToggle}
          title="Collapse sidebar"
          aria-label="Collapse sidebar"
          className="flex h-6 w-6 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          ‹
        </button>
      </div>
      <nav className="flex flex-col gap-1 px-3 py-4">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
