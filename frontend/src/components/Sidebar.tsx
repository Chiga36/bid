import { useState } from "react";
import { NavLink } from "react-router-dom";

// Plain inline SVGs (24x24, stroke-based), no icon library — consistent with the rest of this
// app's zero-dependency style. One per nav destination, shown alone in the collapsed rail and
// alongside the label when expanded.
function ResponseBuilderIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M4 5h16v10H9l-4 4V5z" />
      <line x1="7" y1="9" x2="17" y2="9" />
      <line x1="7" y1="12.5" x2="13" y2="12.5" />
    </svg>
  );
}

function DataIngestionIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M4 15v4a1 1 0 001 1h14a1 1 0 001-1v-4" />
      <path d="M12 3v10" />
      <path d="M8 7l4-4 4 4" />
    </svg>
  );
}

function StatusReportIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <line x1="5" y1="20" x2="5" y2="12" />
      <line x1="11" y1="20" x2="11" y2="7" />
      <line x1="17" y1="20" x2="17" y2="15" />
      <line x1="3" y1="20" x2="21" y2="20" />
    </svg>
  );
}

function CompetitionInfoIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="8.5" />
      <line x1="12" y1="11" x2="12" y2="16" />
      <circle cx="12" cy="7.7" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

function AgentOverviewIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="3.5" y="3.5" width="7.5" height="7.5" rx="1.2" />
      <rect x="13" y="3.5" width="7.5" height="7.5" rx="1.2" />
      <rect x="3.5" y="13" width="7.5" height="7.5" rx="1.2" />
      <rect x="13" y="13" width="7.5" height="7.5" rx="1.2" />
    </svg>
  );
}

const NAV_ITEMS = [
  { to: "/builder", label: "Response Builder", Icon: ResponseBuilderIcon },
  { to: "/ingestion", label: "Data Ingestion", Icon: DataIngestionIcon },
  { to: "/status", label: "Status Report", Icon: StatusReportIcon },
  { to: "/info", label: "Competition Info", Icon: CompetitionInfoIcon },
  { to: "/skills", label: "Agent Overview", Icon: AgentOverviewIcon },
];

// Renders /kpmg-logo.png (frontend/public/kpmg-logo.png — anything under public/ is served at
// the site root by Vite, no import/bundling step needed). Falls back to a plain "K" mark if the
// file is ever missing, so nothing looks broken. The real logo is a wide mark (~2.6:1), so the
// collapsed rail constrains by max-width rather than a fixed height — a fixed h-7 would render it
// wider than the rail itself and spill out.
function KpmgLogo({ collapsed }: { collapsed: boolean }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-white text-sm font-semibold text-brand-700">
        K
      </span>
    );
  }
  return (
    <img
      src="/kpmg-logo.png"
      alt="KPMG"
      className={collapsed ? "h-auto max-w-[36px] object-contain" : "h-7 w-auto object-contain"}
      onError={() => setFailed(true)}
    />
  );
}

// This app's own mark, distinct from the KPMG logo above it — a simple original pen-over-paper
// icon (plain inline SVG, not a copied stock-image asset).
function PenPaperIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <rect x="4" y="3" width="13" height="17" rx="1.5" />
      <line x1="7" y1="7.5" x2="14" y2="7.5" />
      <line x1="7" y1="11" x2="14" y2="11" />
      <path d="M14 15.5 L21 8.5 L19.5 7 L12.5 14 L12 16 Z" />
    </svg>
  );
}

const RAIL_WIDTH = "w-14"; // 56px — always reserved in the page's flex layout, hover or not
const EXPANDED_WIDTH = "w-60"; // 240px — only while hovered, overlaid on top of the main content

// No click target anywhere here — expansion is purely mouse-driven (hover to preview, move away
// to collapse). The outer div always reserves RAIL_WIDTH of real layout space so the rest of the
// page never reflows; the actual <aside> is absolutely positioned inside it and grows past that
// reserved width on hover, overlaying the main content rather than pushing it.
export default function Sidebar() {
  const [hovered, setHovered] = useState(false);

  return (
    <div className={`relative ${RAIL_WIDTH} shrink-0`}>
      <aside
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className={`absolute left-0 top-0 z-30 flex h-full flex-col overflow-hidden border-r border-brand-600 bg-brand-700 shadow-lg transition-[width] duration-200 ease-out ${
          hovered ? EXPANDED_WIDTH : RAIL_WIDTH
        }`}
      >
        {hovered ? (
          <div className="flex flex-col gap-3 border-b border-brand-600 px-5 py-4">
            <KpmgLogo collapsed={false} />
            <div className="flex items-center gap-2">
              <PenPaperIcon className="h-4 w-4 shrink-0 text-white" />
              <span className="whitespace-nowrap text-sm font-semibold text-white">Bid Co-author</span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 border-b border-brand-600 px-2 py-4">
            <KpmgLogo collapsed />
            <PenPaperIcon className="h-5 w-5 text-white" />
          </div>
        )}

        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              title={label}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  hovered ? "" : "justify-center"
                } ${isActive ? "bg-white text-brand-700" : "text-blue-100 hover:bg-brand-600 hover:text-white"}`
              }
            >
              <Icon className="h-5 w-5 shrink-0" />
              {hovered && <span className="whitespace-nowrap">{label}</span>}
            </NavLink>
          ))}
        </nav>
      </aside>
    </div>
  );
}
