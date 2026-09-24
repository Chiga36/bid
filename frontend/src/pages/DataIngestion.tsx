import { useState } from "react";

import { uploadEvidence, uploadTenderDocument } from "../api/tenders";
import FileDropzone from "../components/FileDropzone";
import { useTender } from "../context/TenderContext";

// Only "Questionnaire" drives question extraction (POST /tenders/{id}/documents); the other
// five all feed the tender-scoped evidence library (POST /tenders/{id}/evidence), tagged with
// their own category — see the plan's "Frontend category -> backend mapping" section for why.
// "Questionnaire" (key unchanged: competition_info) and "Strategy and Context" are the two
// mandatory categories, shown in step 1 of the wizard below; the rest are optional, step 2.
const MANDATORY_CATEGORIES: { key: string; title: string; description: string; target: "document" | "evidence" }[] = [
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
];

const OPTIONAL_CATEGORIES: { key: string; title: string; description: string; target: "document" | "evidence" }[] = [
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

const ALL_CATEGORIES = [...MANDATORY_CATEGORIES, ...OPTIONAL_CATEGORIES];
const MANDATORY_CATEGORY_KEYS = MANDATORY_CATEGORIES.map((c) => c.key);

type FilesByCategory = Record<string, File[]>;
type Step = 1 | 2 | 3;

const STEPS: { n: Step; label: string; sub: string }[] = [
  { n: 1, label: "Mandatory field", sub: "Fill the required information" },
  { n: 2, label: "Optional section", sub: "Seek or skip" },
  { n: 3, label: "Submit", sub: "Review & process" },
];

export default function DataIngestion() {
  const { selectedTenderId } = useTender();
  const [step, setStep] = useState<Step>(1);
  const [filesByCategory, setFilesByCategory] = useState<FilesByCategory>({});
  const [running, setRunning] = useState(false);
  const [resultLog, setResultLog] = useState<string[]>([]);

  const totalFiles = Object.values(filesByCategory).reduce((sum, files) => sum + files.length, 0);
  const missingMandatory = MANDATORY_CATEGORY_KEYS.filter((key) => (filesByCategory[key] ?? []).length === 0);
  const missingMandatoryTitles = missingMandatory.map(
    (key) => MANDATORY_CATEGORIES.find((c) => c.key === key)?.title ?? key
  );

  function setCategoryFiles(key: string, files: File[]) {
    setFilesByCategory((prev) => ({ ...prev, [key]: files }));
  }

  // How far the stepper lets you click ahead: once both mandatory docs are in, every step is
  // reachable; until then, you can only ever be on (or click back to) step 1.
  let reachableStep: Step = 1;
  if (missingMandatory.length === 0) {
    reachableStep = 3;
  } else if (step > 1) {
    reachableStep = 2;
  }

  async function handleExecute() {
    if (!selectedTenderId) return;
    setRunning(true);
    const log: string[] = [];

    for (const category of ALL_CATEGORIES) {
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

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Knowledge Base Ingestion</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Upload tender and supporting documents to the Bid Co-author agent. Questionnaire and Strategy and Context
          are required before you can run the Ingestion agent. The other four categories are optional — upload as
          few or as many files as you have. More files generally means more context for the agents to work with.
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <Stepper current={step} reachable={reachableStep} onSelect={setStep} />

        <div className="mt-6">
          {step === 1 && (
            <StepBody>
              {MANDATORY_CATEGORIES.map((category, i) => (
                <FileDropzone
                  key={category.key}
                  index={i + 1}
                  title={category.title}
                  description={category.description}
                  files={filesByCategory[category.key] ?? []}
                  onFilesChange={(files) => setCategoryFiles(category.key, files)}
                  required
                />
              ))}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">
                  {missingMandatory.length > 0
                    ? `Add a file to ${missingMandatoryTitles.join(" and ")} to continue — both are required.`
                    : "Both mandatory documents are ready."}
                </span>
                <button
                  disabled={missingMandatory.length > 0}
                  onClick={() => setStep(2)}
                  className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  Continue to Next →
                </button>
              </div>
            </StepBody>
          )}

          {step === 2 && (
            <StepBody>
              {OPTIONAL_CATEGORIES.map((category, i) => (
                <FileDropzone
                  key={category.key}
                  index={i + 1}
                  title={category.title}
                  description={category.description}
                  files={filesByCategory[category.key] ?? []}
                  onFilesChange={(files) => setCategoryFiles(category.key, files)}
                />
              ))}
              <div className="flex items-center justify-between">
                <button onClick={() => setStep(1)} className="text-sm text-slate-500 hover:text-slate-700">
                  ← Back
                </button>
                <div className="flex items-center gap-3">
                  <button onClick={() => setStep(3)} className="text-sm font-medium text-slate-500 hover:text-slate-700">
                    Skip
                  </button>
                  <button
                    onClick={() => setStep(3)}
                    className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600"
                  >
                    Continue to Next →
                  </button>
                </div>
              </div>
            </StepBody>
          )}

          {step === 3 && (
            <StepBody>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-800">Review before submitting</p>
                <ul className="mt-2 space-y-1 text-xs text-slate-600">
                  {ALL_CATEGORIES.map((category) => {
                    const count = (filesByCategory[category.key] ?? []).length;
                    return (
                      <li key={category.key} className="flex items-center justify-between">
                        <span>
                          {category.title}
                          {MANDATORY_CATEGORY_KEYS.includes(category.key) && <span className="ml-0.5 text-rose-600">*</span>}
                        </span>
                        <span className={count > 0 ? "font-medium text-slate-700" : "text-slate-400"}>
                          {count} file{count === 1 ? "" : "s"}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>

              <div className="flex items-center justify-between">
                <button onClick={() => setStep(2)} className="text-sm text-slate-500 hover:text-slate-700">
                  ← Back
                </button>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-400">{totalFiles} file(s) ready</span>
                  <button
                    disabled={running || totalFiles === 0}
                    onClick={handleExecute}
                    className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    {running ? "Processing..." : "Execute Ingestion Agent"}
                  </button>
                </div>
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
            </StepBody>
          )}
        </div>
      </div>
    </div>
  );
}

function StepBody({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-4">{children}</div>;
}

function Stepper({
  current,
  reachable,
  onSelect,
}: {
  current: Step;
  reachable: Step;
  onSelect: (step: Step) => void;
}) {
  return (
    <div className="flex items-start">
      {STEPS.map((s, i) => {
        const done = s.n < current;
        const active = s.n === current;
        const clickable = s.n <= reachable;

        let badgeClass = "border-2 border-slate-300 text-slate-400";
        if (done || active) {
          badgeClass = "bg-brand-500 text-white";
        }
        if (active) {
          badgeClass += " ring-4 ring-brand-100";
        }

        return (
          <div key={s.n} className="flex flex-1 items-start last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <button
                disabled={!clickable}
                onClick={() => clickable && onSelect(s.n)}
                className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold transition-colors ${badgeClass} ${
                  clickable ? "cursor-pointer" : "cursor-not-allowed"
                }`}
              >
                {done ? "✓" : s.n}
              </button>
              <div className="text-center">
                <p className={`text-xs font-semibold ${s.n <= current ? "text-slate-800" : "text-slate-400"}`}>{s.label}</p>
                <p className="text-[11px] text-slate-400">{s.sub}</p>
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`mx-3 mt-5 h-0.5 flex-1 ${s.n < current ? "bg-brand-500" : "bg-slate-200"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
