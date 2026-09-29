import { useEffect, useState } from "react";

import { getTenderPrompt, resetTenderPrompt, saveTenderPrompt } from "../api/prompts";

export interface PromptFileOption {
  label: string;
  filename: string;
}

interface SkillEditorModalProps {
  agentName: string;
  promptFiles: PromptFileOption[];
  tenderId: number;
  onClose: () => void;
}

// Edits are always scoped to `tenderId` — saving here never touches the shared default file on
// disk or any other tender's own customisation (see backend/app/routers/prompts.py's
// PUT/DELETE /tenders/{id}/prompt-overrides/{file}).
export default function SkillEditorModal({ agentName, promptFiles, tenderId, onClose }: SkillEditorModalProps) {
  const [selectedFile, setSelectedFile] = useState(promptFiles[0]?.filename ?? "");
  const [content, setContent] = useState("");
  const [isOverride, setIsOverride] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedFile) return;
    setLoading(true);
    setError(null);
    getTenderPrompt(tenderId, selectedFile)
      .then((prompt) => {
        setContent(prompt.content_text);
        setIsOverride(prompt.is_override);
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [tenderId, selectedFile]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const result = await saveTenderPrompt(tenderId, selectedFile, content);
      setIsOverride(result.is_override);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    setSaving(true);
    setError(null);
    try {
      const result = await resetTenderPrompt(tenderId, selectedFile);
      setContent(result.content_text);
      setIsOverride(result.is_override);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-6" onClick={onClose}>
      <div
        className="flex h-[90vh] w-full max-w-5xl flex-col gap-3 rounded-lg bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-800">Edit Skill: {agentName}</p>
            <p className="mt-0.5 text-xs text-slate-500">
              Changes here only apply to this tender — every other tender keeps using the default.
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" aria-label="Close">
            ✕
          </button>
        </div>

        {promptFiles.length > 1 && (
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium text-slate-600">Prompt file</span>
            <select
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={selectedFile}
              onChange={(e) => setSelectedFile(e.target.value)}
            >
              {promptFiles.map((f) => (
                <option key={f.filename} value={f.filename}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>
        )}

        <div>
          {isOverride ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700">
              Using your customisation for this tender
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">
              Using the default
            </span>
          )}
        </div>

        {error && <p className="text-xs text-rose-600">{error}</p>}

        {loading ? (
          <p className="text-xs text-slate-400">Loading...</p>
        ) : (
          <textarea
            className="min-h-0 flex-1 resize-none rounded-md border border-slate-300 p-3 font-mono text-xs"
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        )}

        <div className="flex items-center justify-between">
          <button
            onClick={handleReset}
            disabled={saving || loading || !isOverride}
            className="text-xs font-medium text-slate-500 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Reset to default
          </button>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || loading}
              className="rounded-md bg-brand-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
