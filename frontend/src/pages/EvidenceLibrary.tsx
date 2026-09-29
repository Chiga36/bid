import { useEffect, useState } from "react";

import { deleteGlobalEvidenceDocument, listGlobalEvidence, uploadGlobalEvidence } from "../api/evidenceLibrary";
import type { GlobalEvidenceChunk } from "../api/types";
import FileDropzone from "../components/FileDropzone";

// Same category vocabulary as Data Ingestion's optional evidence categories (see
// DataIngestion.tsx's OPTIONAL_CATEGORIES) — kept as its own small local copy rather than a
// shared import, since this page's upload flow (one category applied to a batch, uploaded
// immediately) is shaped differently from the wizard there.
const CATEGORIES = [
  { key: "credentials", title: "Credentials" },
  { key: "standards", title: "Standards" },
  { key: "propositions", title: "Propositions" },
  { key: "high_scoring_responses", title: "High Scoring Responses" },
];

interface DocumentGroup {
  source_document: string;
  category: string;
  chunk_count: number;
}

function groupByDocument(chunks: GlobalEvidenceChunk[]): DocumentGroup[] {
  const groups = new Map<string, DocumentGroup>();
  for (const chunk of chunks) {
    const existing = groups.get(chunk.source_document);
    if (existing) {
      existing.chunk_count += 1;
    } else {
      groups.set(chunk.source_document, { source_document: chunk.source_document, category: chunk.category, chunk_count: 1 });
    }
  }
  return Array.from(groups.values());
}

export default function EvidenceLibrary() {
  const [chunks, setChunks] = useState<GlobalEvidenceChunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState(CATEGORIES[0].key);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [deletingDoc, setDeletingDoc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    setLoading(true);
    listGlobalEvidence()
      .then(setChunks)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  async function handleUpload() {
    if (pendingFiles.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of pendingFiles) {
        await uploadGlobalEvidence(file, category);
      }
      setPendingFiles([]);
      refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(sourceDocument: string) {
    setDeletingDoc(sourceDocument);
    setError(null);
    try {
      await deleteGlobalEvidenceDocument(sourceDocument);
      setChunks((prev) => prev.filter((c) => c.source_document !== sourceDocument));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setDeletingDoc(null);
    }
  }

  const documents = groupByDocument(chunks);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Evidence Library</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Past case studies, CVs, credentials and high-scoring responses — uploaded once here, not tied to any
          specific tender. Every tender's Recommendation agent and evidence suggestions automatically draw on this
          library alongside that tender's own uploads, so you never need to re-upload the same evidence per bid.
        </p>
      </div>

      {error && <p className="text-sm text-rose-600">{error}</p>}

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-3">
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium text-slate-600">Category</span>
            <select
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {CATEGORIES.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-3">
          <FileDropzone
            index={1}
            title="Add evidence"
            description="Case studies, CVs, credentials, or previous high-scoring responses."
            files={pendingFiles}
            onFilesChange={setPendingFiles}
          />
        </div>

        <button
          onClick={handleUpload}
          disabled={uploading || pendingFiles.length === 0}
          className="mt-3 rounded-md bg-brand-500 px-4 py-1.5 text-xs font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {uploading ? "Uploading..." : `Upload ${pendingFiles.length || ""} file(s)`}
        </button>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="text-sm font-semibold text-slate-800">Library contents</p>
        {loading && <p className="mt-2 text-xs text-slate-400">Loading...</p>}
        {!loading && documents.length === 0 && (
          <p className="mt-2 text-xs text-slate-400">No global evidence uploaded yet.</p>
        )}
        {documents.length > 0 && (
          <ul className="mt-3 divide-y divide-slate-100">
            {documents.map((doc) => (
              <li key={doc.source_document} className="flex items-center justify-between gap-3 py-2 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-medium text-slate-700">{doc.source_document}</p>
                  <p className="text-xs text-slate-400">
                    {CATEGORIES.find((c) => c.key === doc.category)?.title ?? doc.category} · {doc.chunk_count} chunk
                    {doc.chunk_count === 1 ? "" : "s"}
                  </p>
                </div>
                <button
                  onClick={() => handleDelete(doc.source_document)}
                  disabled={deletingDoc === doc.source_document}
                  className="shrink-0 text-xs font-medium text-rose-500 hover:text-rose-600 disabled:opacity-40"
                >
                  {deletingDoc === doc.source_document ? "Deleting..." : "Delete"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
