import { useEffect, useState } from "react";

import { listAgentPrompts } from "../api/prompts";
import type { AgentPrompt } from "../api/types";

export default function AgentSkills() {
  const [prompts, setPrompts] = useState<AgentPrompt[] | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    listAgentPrompts().then(setPrompts);
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Agent Skills</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          The real prompt each agent sends to the model, read directly from{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5 text-xs">app/prompts/</code>. Read-only in this build —
          editing prompts here would need the backend to persist changes, which isn't wired up yet.
        </p>
      </div>

      {prompts === null ? (
        <p className="text-sm text-slate-400">Loading...</p>
      ) : (
        <div className="flex flex-col gap-2">
          {prompts.map((p) => (
            <div key={p.filename} className="rounded-lg border border-slate-200 bg-white">
              <button
                onClick={() => setExpanded(expanded === p.filename ? null : p.filename)}
                className="flex w-full items-center justify-between px-4 py-3 text-left"
              >
                <span>
                  <span className="text-sm font-semibold text-slate-800">{p.agent}</span>{" "}
                  <span className="text-xs text-slate-400">{p.filename}</span>
                </span>
                <span className="text-xs text-slate-400">{expanded === p.filename ? "Hide" : "View prompt"}</span>
              </button>
              {expanded === p.filename && (
                <pre className="whitespace-pre-wrap border-t border-slate-100 bg-slate-50 px-4 py-3 text-xs text-slate-700">
                  {p.content}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
