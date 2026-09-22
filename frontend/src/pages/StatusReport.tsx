import { useEffect, useState } from "react";

import { getGate, getScoring } from "../api/drafts";
import { listDrafts } from "../api/questions";
import { listQuestions } from "../api/tenders";
import { ApiError } from "../api/types";
import type { GateResult, Question, ScoringSummary } from "../api/types";
import StatusPill from "../components/StatusPill";
import { useTender } from "../context/TenderContext";

// Computed client-side from the existing per-question/per-draft endpoints rather than a new
// aggregate backend endpoint — an N+1-call pattern that's fine at POC scale and keeps this page
// (read-only) from adding backend surface area. Flagged in the plan, not a silent shortcut.
interface Row {
  question: Question;
  wordCount: number;
  scoring: ScoringSummary | null;
  gate: GateResult | null;
}

async function safeGetScoring(draftId: number): Promise<ScoringSummary | null> {
  try {
    return await getScoring(draftId);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export default function StatusReport() {
  const { selectedTenderId } = useTender();
  const [rows, setRows] = useState<Row[] | null>(null);

  useEffect(() => {
    if (!selectedTenderId) return;
    let cancelled = false;

    async function load() {
      const questions = await listQuestions(selectedTenderId!);
      const results: Row[] = [];
      for (const question of questions) {
        const drafts = await listDrafts(question.id);
        const latest = drafts[drafts.length - 1];
        if (!latest) {
          results.push({ question, wordCount: 0, scoring: null, gate: null });
          continue;
        }
        const wordCount = latest.content_text.trim().split(/\s+/).filter(Boolean).length;
        const scoring = await safeGetScoring(latest.id);
        const gate = await getGate(latest.id);
        results.push({ question, wordCount, scoring, gate });
      }
      if (!cancelled) setRows(results);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [selectedTenderId]);

  if (!selectedTenderId) {
    return <p className="text-sm text-slate-500">Create or select a tender first (top right).</p>;
  }

  function statusFor(row: Row): { status: string; label: string } {
    if (row.wordCount === 0) return { status: "slate", label: "Not started" };
    if (row.gate?.ready_to_submit) return { status: "ready", label: "Ready" };
    return { status: "not_ready", label: "Needs review" };
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-lg font-semibold text-slate-900">Status Report</h1>

      {rows === null ? (
        <p className="text-sm text-slate-400">Loading...</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-400">No questions yet — add some via Data Ingestion.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-2">Question</th>
                <th className="px-4 py-2">Word Count</th>
                <th className="px-4 py-2">Score band</th>
                <th className="px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const { status, label } = statusFor(row);
                return (
                  <tr key={row.question.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-2 text-slate-800">{row.question.title}</td>
                    <td className="px-4 py-2 text-slate-500">{row.wordCount} words</td>
                    <td className="px-4 py-2 text-slate-500">{row.scoring ? row.scoring.final_band : "—"}</td>
                    <td className="px-4 py-2">
                      <StatusPill status={status} label={label} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
