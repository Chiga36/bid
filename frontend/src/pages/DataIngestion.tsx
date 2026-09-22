import { useState } from "react";

import { uploadEvidence, uploadTenderDocument } from "../api/tenders";
import FileDropzone from "../components/FileDropzone";
import { useTender } from "../context/TenderContext";

// Only "Questionnaire" drives question extraction (POST /tenders/{id}/documents); the other
// five all feed the tender-scoped evidence library (POST /tenders/{id}/evidence), tagged with
// their own category — see the plan's "Frontend category -> backend mapping" section for why.
// "Questionnaire" (key unchanged: competition_info) and "Strategy and Context" are the two
// mandatory categories — see MANDATORY_CATEGORY_KEYS below.
const CATEGORIES: { key: string; title: string; description: string; target: "document" | "evidence" }[] = [
  {
    key: "strategy_and_context",
    title: "Strategy and Context",
    description: "The competition tender instructions document — evaluation methodology and the full requirements register are extracted from this.",
    target: "evidence",
  },
  {
    key: "competition_info",
    title: "Questionnaire",
    description: "The Award Questionnaire spreadsheet (xlsx). Selection Questionnaire sheets are excluded automatically — only Award Questionnaire questions are extracted, verbatim.",
    target: "document",
  },
  {
    key: "credentials",
    title: "Credentials",
    description: "Case studies, past performance, and team biographies.",
    target: "evidence",
  },
  {
    key: "standards",
    title: "Standards",
    description: "ISO certifications, compliance documents, and quality-assurance procedures.",
    target: "evidence",
  },
  {
    key: "propositions",
    title: "Propositions",
    description: "Value propositions, pricing models, and service catalogues.",
    target: "evidence",
  },
  {
    key: "high_scoring_responses",
    title: "High Scoring Responses",
    description: "Previous winning bids and top-rated answers.",
    target: "evidence",
  },
];

type FilesByCategory = Record<string, File[]>;

const MANDATORY_CATEGORY_KEYS = ["competition_info", "strategy_and_context"] as const;

export default function DataIngestion() {
  const { selectedTenderId } = useTender();
  const [filesByCategory, setFilesByCategory] = useState<FilesByCategory>({});
  const [running, setRunning] = useState(false);
  const [resultLog, setResultLog] = useState<string[]>([]);

  const totalFiles = Object.values(filesByCategory).reduce((sum, files) => sum + files.length, 0);
  const missingMandatory = MANDATORY_CATEGORY_KEYS.filter((key) => (filesByCategory[key] ?? []).length === 0);
  const missingMandatoryTitles = missingMandatory.map(
    (key) => CATEGORIES.find((c) => c.key === key)?.title ?? key
  );

  async function handleExecute() {
    if (!selectedTenderId) return;
    setRunning(true);
    const log: string[] = [];

    for (const category of CATEGORIES) {
      const files = filesByCategory[category.key] ?? [];
      for (const file of files) {
        try {
          if (category.target === "document") {
            const questions = await uploadTenderDocument(selectedTenderId, file);
            log.push(`${category.title}: "${file.name}" -> ${questions.length} question(s) extracted.`);
          } else {
            const result = await uploadEvidence(selectedTenderId, file, category.key);
            log.push(`${category.title}: "${file.name}" -> ${result.chunks_ingested} evidence chunk(s) ingested.`);
          }
        } catch (err) {
          log.push(`${category.title}: "${file.name}" failed — ${(err as Error).message}`);
        }
      }
    }

    if (log.length === 0) {
      log.push("No files were added in any category, so nothing was uploaded. That's fine — add files whenever you're ready.");
    }
    setResultLog(log);
    setRunning(false);
  }

  if (!selectedTenderId) {
    return <p className="text-sm text-slate-500">Create or select a tender first (top right).</p>;
  }

  let executeHint: string;
  if (missingMandatory.length > 0) {
    executeHint = `Add a file to ${missingMandatoryTitles.join(" and ")} to enable this — both are required.`;
  } else if (totalFiles === 0) {
    executeHint = "Add files above to enable this.";
  } else {
    executeHint = `${totalFiles} file(s) ready`;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Knowledge Base Ingestion</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Upload tender and supporting documents to the Bid Co-author agent. Questionnaire and
          Strategy and Context are required before you can run the Ingestion agent. The other four
          categories are optional — upload as few or as many files as you have. More files
          generally means more context for the agents to work with.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {CATEGORIES.map((category) => (
          <FileDropzone
            key={category.key}
            title={category.title}
            description={category.description}
            files={filesByCategory[category.key] ?? []}
            onFilesChange={(files) => setFilesByCategory((prev) => ({ ...prev, [category.key]: files }))}
          />
        ))}
      </div>

      <div className="flex items-center gap-3">
        <button
          disabled={running || totalFiles === 0 || missingMandatory.length > 0}
          onClick={handleExecute}
          className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {running ? "Running..." : "Execute Ingestion Agent"}
        </button>
        <span className="text-xs text-slate-400">{executeHint}</span>
      </div>

      {resultLog.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold text-slate-800">Ingestion results</p>
          <ul className="mt-2 space-y-1 text-xs text-slate-600">
            {resultLog.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
