import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listKycInsights } from "../api/tenders";
import type { KYCInsight } from "../api/types";
import { useTender } from "../context/TenderContext";

export default function KYC() {
  const { selectedTenderId } = useTender();
  const navigate = useNavigate();
  const [insights, setInsights] = useState<KYCInsight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!selectedTenderId) return;
    setLoading(true);
    listKycInsights(selectedTenderId)
      .then(setInsights)
      .finally(() => setLoading(false));
  }, [selectedTenderId]);

  if (!selectedTenderId) {
    return <p className="text-sm text-slate-500">Create or select a tender first (top right).</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Know Your Client</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Extracted automatically from the Strategy and Context upload — who this client is, and what to keep in mind
          before writing the tender response for them specifically.
        </p>
      </div>

      {loading && <p className="text-sm text-slate-400">Loading...</p>}

      {!loading && insights.length === 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">
            No client insight extracted yet. Upload the tender instructions document under Strategy and Context in Data
            Ingestion, or check back after ingestion finishes.
          </p>
        </div>
      )}

      {insights.map((insight) => (
        <div key={insight.id} className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
            From: {insight.source_document}
          </p>

          {insight.client_summary && (
            <div>
              <p className="text-sm font-semibold text-slate-800">Who this client is</p>
              <p className="mt-1 text-sm text-slate-600">{insight.client_summary}</p>
            </div>
          )}

          {insight.key_facts.length > 0 && (
            <div>
              <p className="text-sm font-semibold text-slate-800">Key facts</p>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-slate-600">
                {insight.key_facts.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
          )}

          {insight.considerations.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm font-semibold text-amber-800">Keep in mind before writing this response</p>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-amber-700">
                {insight.considerations.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}

      <div className="flex items-center justify-between rounded-lg border border-brand-200 bg-brand-50 px-4 py-3">
        <span className="text-sm text-brand-700">Ready to start drafting responses?</span>
        <button
          onClick={() => navigate("/builder")}
          className="rounded-md bg-brand-500 px-4 py-1.5 text-xs font-medium text-white hover:bg-brand-600"
        >
          Next: Response Builder →
        </button>
      </div>
    </div>
  );
}
