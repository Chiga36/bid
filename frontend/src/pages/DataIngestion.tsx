import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { commitZipUpload, inspectZipUpload, uploadEvidence, uploadTenderDocument } from "../api/tenders";
import type { ZipInspectResult } from "../api/types";
import FileDropzone from "../components/FileDropzone";
import { useTender } from "../context/TenderContext";

// Only "Questionnaire" drives question extraction (POST /tenders/{id}/documents); the other
// six all feed the tender-scoped evidence library (POST /tenders/{id}/evidence), tagged with
// their own category — see the plan's "Frontend category -> backend mapping" section for why.
// "Strategy" and "Questionnaire" (key unchanged: competition_info) are the two mandatory
// categories, shown in step 1 of the wizard below; the rest (including Context) are optional,
// step 2. Context started out mandatory alongside Strategy, but PPT files there were taking a
// very long time to render once deployed to App Service — moved to optional so a tender can be
// ingested without waiting on it; Know Your Client just has nothing to show until it's uploaded.
const MANDATORY_CATEGORIES: { key: string; title: string; description: string; target: "document" | "evidence" }[] = [
  {
    key: "strategy",
    title: "Strategy",
    description: "The competition tender instructions document — evaluation methodology, the full requirements register, the scoring matrix and the procurement timeline are extracted from this.",
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
    key: "context",
    title: "Context",
    description: "A client background document — who the client is, their priorities and situation. Know Your Client is extracted from this, and only this.",
    target: "evidence",
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

const ALL_CATEGORIES = [...MANDATORY_CATEGORIES, ...OPTIONAL_CATEGORIES];
const MANDATORY_CATEGORY_KEYS = MANDATORY_CATEGORIES.map((c) => c.key);

// "A" / "A and B" / "A, B and C" — Array.join(" and ") alone reads oddly once there are 3+
// mandatory categories ("A and B and C").
function joinWithAnd(items: string[]): string {
  if (items.length <= 1) return items.join("");
  if (items.length === 2) return items.join(" and ");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

type FilesByCategory = Record<string, File[]>;
type Step = 1 | 2 | 3;
type Mode = "manual" | "zip";

const STEPS: { n: Step; label: string; sub: string }[] = [
  { n: 1, label: "Mandatory Input", sub: "Fill the required information" },
  { n: 2, label: "Optional Input", sub: "Seek or skip" },
  { n: 3, label: "Submit", sub: "Review & process" },
];

export default function DataIngestion() {
  const { selectedTenderId } = useTender();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("manual");
  const [step, setStep] = useState<Step>(1);
  const [filesByCategory, setFilesByCategory] = useState<FilesByCategory>({});
  const [running, setRunning] = useState(false);
  const [resultLog, setResultLog] = useState<string[]>([]);
  const [failedFiles, setFailedFiles] = useState<{ name: string; message: string }[]>([]);
  const [redirecting, setRedirecting] = useState(false);

  // ZIP mode — its own 3-step flow (pick -> review & assign -> commit), sharing resultLog/
  // failedFiles/redirecting above with the manual flow once a commit actually runs.
  const [zipStep, setZipStep] = useState<1 | 2 | 3>(1);
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [inspecting, setInspecting] = useState(false);
  const [inspectError, setInspectError] = useState<string | null>(null);
  const [zipInspectResult, setZipInspectResult] = useState<ZipInspectResult | null>(null);
  const [assignments, setAssignments] = useState<Record<string, string | null>>({});
  const [committing, setCommitting] = useState(false);

  // Once ingestion has actually processed something, move the user on to Know Your Client
  // automatically after a moment — the new workflow is Data Ingestion -> KYC -> Response
  // Builder, so KYC (not Response Builder) is the natural next step for a first-time user. A
  // few seconds' delay (rather than instant) keeps the result log below on screen long enough
  // to actually read; "Continue now" skips the wait for anyone who doesn't want it.
  useEffect(() => {
    if (!redirecting) return;
    const timer = setTimeout(() => navigate("/kyc"), 2500);
    return () => clearTimeout(timer);
  }, [redirecting, navigate]);

  const totalFiles = Object.values(filesByCategory).reduce((sum, files) => sum + files.length, 0);
  const missingMandatory = MANDATORY_CATEGORY_KEYS.filter((key) => (filesByCategory[key] ?? []).length === 0);
  const missingMandatoryTitles = missingMandatory.map(
    (key) => MANDATORY_CATEGORIES.find((c) => c.key === key)?.title ?? key
  );

  function setCategoryFiles(key: string, files: File[]) {
    setFilesByCategory((prev) => ({ ...prev, [key]: files }));
  }

  // How far the stepper lets you click ahead: once every mandatory doc is in, every step is
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
    setFailedFiles([]);
    const log: string[] = [];
    const failures: { name: string; message: string }[] = [];
    let successCount = 0;

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
          successCount += 1;
        } catch (err) {
          const message = (err as Error).message || "Something went wrong.";
          log.push(`${category.title}: "${file.name}" failed — ${message}`);
          failures.push({ name: file.name, message });
        }
      }
    }

    if (log.length === 0) {
      log.push("No files were added in any category, so nothing was uploaded. That's fine — add files whenever you're ready.");
    }
    setResultLog(log);
    setFailedFiles(failures);
    setRunning(false);
    // Only auto-advance if something actually succeeded — if every upload failed, stay put so
    // the errors above are visible and actionable rather than scrolled away from.
    if (successCount > 0) {
      setRedirecting(true);
    }
  }

  async function handleInspectZip() {
    if (!selectedTenderId || !zipFile) return;
    setInspecting(true);
    setInspectError(null);
    try {
      const result = await inspectZipUpload(selectedTenderId, zipFile);
      setZipInspectResult(result);
      const initial: Record<string, string | null> = {};
      result.files.forEach((f) => {
        initial[f.filename] = f.suggested_category;
      });
      setAssignments(initial);
      setZipStep(2);
    } catch (err) {
      setInspectError((err as Error).message || "Something went wrong reading that ZIP.");
    } finally {
      setInspecting(false);
    }
  }

  async function handleCommitZip() {
    if (!selectedTenderId || !zipInspectResult) return;
    setCommitting(true);
    setFailedFiles([]);
    try {
      const result = await commitZipUpload(selectedTenderId, zipInspectResult.staging_id, assignments);
      const log: string[] = [];
      const failures: { name: string; message: string }[] = [];
      let successCount = 0;
      for (const r of result.results) {
        if (r.success) {
          log.push(`"${r.filename}" -> ${r.message}`);
          successCount += 1;
        } else {
          log.push(`"${r.filename}" failed — ${r.message}`);
          failures.push({ name: r.filename, message: r.message });
        }
      }
      if (log.length === 0) {
        log.push("No files were assigned a category, so nothing was uploaded.");
      }
      setResultLog(log);
      setFailedFiles(failures);
      setZipStep(3);
      if (successCount > 0) {
        setRedirecting(true);
      }
    } catch (err) {
      const message = (err as Error).message || "Something went wrong.";
      setFailedFiles([{ name: zipFile?.name ?? "ZIP upload", message }]);
      setZipStep(3);
    } finally {
      setCommitting(false);
    }
  }

  function resetZipFlow() {
    setZipStep(1);
    setZipFile(null);
    setZipInspectResult(null);
    setAssignments({});
    setResultLog([]);
    setFailedFiles([]);
  }

  if (!selectedTenderId) {
    return <p className="text-sm text-slate-500">Create or select a tender first (top right).</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      {failedFiles.length > 0 && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 p-3">
          <ul className="space-y-0.5 text-sm font-medium text-rose-700">
            {failedFiles.map((f, i) => (
              <li key={i}>
                "{f.name}" file could not be processed — {f.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h1 className="text-lg font-semibold text-slate-900">Knowledge Base Ingestion</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Upload tender and supporting documents to the Bid Co-author agent. Strategy and Questionnaire are required
          before you can run the Ingestion agent. The other five categories are optional — upload as few or as many
          files as you have. More files generally means more context for the agents to work with.
        </p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => setMode("manual")}
          className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
            mode === "manual" ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          Manual upload
        </button>
        <button
          onClick={() => setMode("zip")}
          className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
            mode === "zip" ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          Upload via ZIP
        </button>
      </div>

      {mode === "manual" && (
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
                    ? `Add a file to ${joinWithAnd(missingMandatoryTitles)} to continue — both are required.`
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

              {redirecting && (
                <div className="flex items-center justify-between rounded-lg border border-brand-200 bg-brand-50 px-4 py-3">
                  <span className="text-sm text-brand-700">Taking you to Know Your Client...</span>
                  <button
                    onClick={() => navigate("/kyc")}
                    className="rounded-md bg-brand-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600"
                  >
                    Continue now →
                  </button>
                </div>
              )}
            </StepBody>
          )}
        </div>
      </div>
      )}

      {mode === "zip" && (
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          {zipStep === 1 && (
            <StepBody>
              <FileDropzone
                index={1}
                title="Document pack (.zip)"
                description="Upload the whole tender document pack as one ZIP file. We'll unzip it, guess each file's category from its name, and let you review everything before anything is ingested."
                files={zipFile ? [zipFile] : []}
                onFilesChange={(files) => setZipFile(files[files.length - 1] ?? null)}
                required
              />
              {inspectError && <p className="text-sm font-medium text-rose-600">{inspectError}</p>}
              <div className="flex items-center justify-end">
                <button
                  disabled={!zipFile || inspecting}
                  onClick={handleInspectZip}
                  className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {inspecting ? "Inspecting..." : "Inspect ZIP"}
                </button>
              </div>
            </StepBody>
          )}

          {zipStep === 2 && zipInspectResult && (
            <StepBody>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-800">Review & assign categories</p>
                <p className="mt-1 text-xs text-slate-500">
                  We matched {zipInspectResult.files.filter((f) => f.suggested_category).length} of{" "}
                  {zipInspectResult.files.length} file(s) automatically. Check each one before continuing —
                  unmatched files need a category picked by hand, or can be skipped.
                </p>
              </div>

              <div className="overflow-hidden rounded-lg border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-xs uppercase text-slate-400">
                    <tr>
                      <th className="px-4 py-2 text-left">File</th>
                      <th className="px-4 py-2 text-left">Size</th>
                      <th className="px-4 py-2 text-left">Category</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {zipInspectResult.files.map((f) => (
                      <tr key={f.filename}>
                        <td className="px-4 py-2 text-slate-700">
                          {f.filename}
                          {!f.suggested_category && (
                            <span className="ml-2 text-[11px] font-medium text-amber-600">no match — pick one</span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-slate-500">{(f.size_bytes / (1024 * 1024)).toFixed(1)} MB</td>
                        <td className="px-4 py-2">
                          <select
                            value={assignments[f.filename] ?? ""}
                            onChange={(e) =>
                              setAssignments((prev) => ({ ...prev, [f.filename]: e.target.value || null }))
                            }
                            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                          >
                            <option value="">Skip this file</option>
                            {ALL_CATEGORIES.map((c) => (
                              <option key={c.key} value={c.key}>
                                {c.title}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center justify-between">
                <button onClick={() => setZipStep(1)} className="text-sm text-slate-500 hover:text-slate-700">
                  ← Back
                </button>
                <button
                  disabled={committing}
                  onClick={handleCommitZip}
                  className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {committing ? "Processing..." : "Start Data Ingestion"}
                </button>
              </div>
            </StepBody>
          )}

          {zipStep === 3 && (
            <StepBody>
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

              {redirecting && (
                <div className="flex items-center justify-between rounded-lg border border-brand-200 bg-brand-50 px-4 py-3">
                  <span className="text-sm text-brand-700">Taking you to Know Your Client...</span>
                  <button
                    onClick={() => navigate("/kyc")}
                    className="rounded-md bg-brand-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600"
                  >
                    Continue now →
                  </button>
                </div>
              )}

              <div>
                <button onClick={resetZipFlow} className="text-sm text-slate-500 hover:text-slate-700">
                  ← Upload another ZIP
                </button>
              </div>
            </StepBody>
          )}
        </div>
      )}
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
