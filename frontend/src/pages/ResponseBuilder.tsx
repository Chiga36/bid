import { useEffect, useMemo, useState } from "react";

import {
  getGate,
  getScoring,
  runCompleteness,
  runDeterministicChecks,
  runRecommendations,
  runScoring,
  runThemeReview,
} from "../api/drafts";
import { createDraft, decomposeQuestion, getElements, listDrafts, lockRegister } from "../api/questions";
import { listQuestions } from "../api/tenders";
import type {
  CompletenessResult,
  DeterministicCheckResult,
  Draft,
  ElementRow,
  GateResult,
  Question,
  RecommendationItem,
  ScoringSummary,
  ThemeReview,
} from "../api/types";
import StatusPill from "../components/StatusPill";
import VersionHistoryPanel from "../components/VersionHistoryPanel";
import { useTender } from "../context/TenderContext";

export default function ResponseBuilder() {
  const { selectedTenderId } = useTender();

  const [questions, setQuestions] = useState<Question[]>([]);
  const [selectedQuestionId, setSelectedQuestionId] = useState<number | null>(null);

  const [elements, setElements] = useState<ElementRow[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState<number | null>(null);
  const [editorText, setEditorText] = useState("");

  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [completeness, setCompleteness] = useState<CompletenessResult[] | null>(null);
  const [checks, setChecks] = useState<DeterministicCheckResult[] | null>(null);
  const [scoring, setScoring] = useState<ScoringSummary | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationItem[] | null>(null);
  const [gate, setGate] = useState<GateResult | null>(null);
  const [themeReview, setThemeReview] = useState<ThemeReview | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedTenderId) return;
    listQuestions(selectedTenderId).then((qs) => {
      setQuestions(qs);
      setSelectedQuestionId((current) => current ?? qs[0]?.id ?? null);
    });
  }, [selectedTenderId]);

  useEffect(() => {
    if (selectedQuestionId === null) return;
    resetCoachResults();
    getElements(selectedQuestionId).then(setElements);
    listDrafts(selectedQuestionId).then((ds) => {
      setDrafts(ds);
      const latest = ds[ds.length - 1] ?? null;
      setSelectedDraftId(latest?.id ?? null);
      setEditorText(latest?.content_text ?? "");
    });
  }, [selectedQuestionId]);

  const selectedQuestion = questions.find((q) => q.id === selectedQuestionId) ?? null;
  const selectedDraft = drafts.find((d) => d.id === selectedDraftId) ?? null;
  const hasUnsavedChanges = selectedDraft ? selectedDraft.content_text !== editorText : editorText.length > 0;
  const isLocked = elements.length > 0 && elements.every((e) => e.locked);
  const subQuestionElements = elements.filter((e) => e.kind === "sub_question");
  const otherElements = elements.filter((e) => e.kind !== "sub_question");

  function resetCoachResults() {
    setCompleteness(null);
    setChecks(null);
    setScoring(null);
    setRecommendations(null);
    setGate(null);
    setThemeReview(null);
    setActionError(null);
  }

  async function withBusy(action: string, fn: () => Promise<void>) {
    setBusyAction(action);
    setActionError(null);
    try {
      await fn();
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setBusyAction(null);
    }
  }

  async function handleDecompose() {
    if (!selectedQuestionId) return;
    await withBusy("decompose", async () => {
      const els = await decomposeQuestion(selectedQuestionId);
      setElements(els);
    });
  }

  async function handleLock() {
    if (!selectedQuestionId) return;
    await withBusy("lock", async () => {
      const els = await lockRegister(selectedQuestionId);
      setElements(els);
    });
  }

  async function handleSaveVersion() {
    if (!selectedQuestionId) return;
    await withBusy("save", async () => {
      const draft = await createDraft(selectedQuestionId, editorText);
      const ds = await listDrafts(selectedQuestionId);
      setDrafts(ds);
      setSelectedDraftId(draft.id);
      resetCoachResults();
    });
  }

  function handleSelectVersion(draft: Draft) {
    setSelectedDraftId(draft.id);
    setEditorText(draft.content_text);
    resetCoachResults();
  }

  async function handleCheckCompleteness() {
    if (!selectedDraftId) return;
    await withBusy("completeness", async () => setCompleteness(await runCompleteness(selectedDraftId)));
  }

  async function handleRunChecks() {
    if (!selectedDraftId) return;
    await withBusy("checks", async () => setChecks(await runDeterministicChecks(selectedDraftId)));
  }

  async function handleScore() {
    if (!selectedDraftId) return;
    await withBusy("score", async () => setScoring(await runScoring(selectedDraftId)));
  }

  async function handleRecommend() {
    if (!selectedDraftId) return;
    await withBusy("recommend", async () => setRecommendations(await runRecommendations(selectedDraftId)));
  }

  async function handleGate() {
    if (!selectedDraftId) return;
    await withBusy("gate", async () => setGate(await getGate(selectedDraftId)));
  }

  async function handleThemeReview() {
    if (!selectedDraftId) return;
    await withBusy("theme-review", async () => setThemeReview(await runThemeReview(selectedDraftId)));
  }

  const coachDisabled = !selectedDraftId || hasUnsavedChanges;

  if (!selectedTenderId) {
    return <p className="text-sm text-slate-500">Create or select a tender first (top right).</p>;
  }

  return (
    <div className="grid h-full grid-cols-[280px_1fr_320px] gap-4">
      {/* Left: questions */}
      <div className="flex flex-col gap-2 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3">
        <p className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Questions</p>
        {questions.length === 0 && <p className="px-1 text-xs text-slate-400">No questions yet — add some via Data Ingestion.</p>}
        {questions.map((q) => (
          <button
            key={q.id}
            onClick={() => setSelectedQuestionId(q.id)}
            className={`rounded-md border px-3 py-2 text-left text-sm transition-colors ${
              q.id === selectedQuestionId ? "border-brand-300 bg-brand-50" : "border-transparent hover:bg-slate-50"
            }`}
          >
            <p className="font-medium text-slate-800">{q.title}</p>
            <p className="mt-0.5 text-xs text-slate-400">{q.category}</p>
          </button>
        ))}
      </div>

      {/* Middle: editor */}
      <div className="flex flex-col gap-3 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4">
        {!selectedQuestion ? (
          <p className="text-sm text-slate-400">Select a question to start drafting.</p>
        ) : (
          <>
            <div>
              <p className="text-sm font-semibold text-slate-900">{selectedQuestion.title}</p>
              <p className="mt-1 text-xs text-slate-500">{selectedQuestion.question_text}</p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleDecompose}
                disabled={busyAction === "decompose"}
                className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                {elements.length === 0 ? "Decompose question" : "Re-decompose (unlocked elements only)"}
              </button>
              <button
                onClick={handleLock}
                disabled={busyAction === "lock" || elements.length === 0}
                className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
              >
                Lock register
              </button>
              {isLocked && <StatusPill status="ready" label="Locked" />}
            </div>

            {otherElements.length > 0 && (
              <div className="rounded-md border border-slate-200 bg-slate-50 p-2 text-xs text-slate-600">
                {otherElements.map((el) => (
                  <div key={el.id} className="flex items-center justify-between border-b border-slate-100 py-1 last:border-0">
                    <span>
                      <span className="font-medium">{el.kind}</span>: {el.value_text}
                    </span>
                    {el.locked && <StatusPill status="ready" label="locked" />}
                  </div>
                ))}
              </div>
            )}

            {subQuestionElements.length > 0 && (
              <div className="flex flex-col gap-2">
                {subQuestionElements.map((el, i) => (
                  <div key={el.id} className="rounded-md border border-slate-200 bg-white p-2 text-xs">
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium text-slate-800">
                        Sub-question {i + 1}: <span className="font-normal">{el.value_text}</span>
                      </p>
                      {el.locked && <StatusPill status="ready" label="locked" />}
                    </div>
                    {el.elaboration && (
                      <p className="mt-1 pl-3 text-slate-600">
                        <span className="font-medium text-slate-500">What this is asking: </span>
                        {el.elaboration}
                      </p>
                    )}
                    {el.answer_guidance && (
                      <p className="mt-1 pl-3 text-slate-600">
                        <span className="font-medium text-slate-500">Suggested structure: </span>
                        {el.answer_guidance}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}

            <textarea
              className="min-h-[240px] flex-1 rounded-md border border-slate-300 p-3 text-sm"
              placeholder="Write the draft response here..."
              value={editorText}
              onChange={(e) => setEditorText(e.target.value)}
            />
            <div className="flex items-center justify-between">
              <button
                onClick={handleSaveVersion}
                disabled={busyAction === "save"}
                className="rounded-md bg-brand-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600"
              >
                Save new version
              </button>
              <span className="text-xs text-slate-400">
                {editorText.trim().split(/\s+/).filter(Boolean).length} words
                {hasUnsavedChanges && " · unsaved changes"}
              </span>
            </div>

            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Version history</p>
              <VersionHistoryPanel drafts={drafts} selectedDraftId={selectedDraftId} onSelect={handleSelectVersion} />
            </div>
          </>
        )}
      </div>

      {/* Right: coach */}
      <div className="flex flex-col gap-3 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Co-author Coach</p>
        {coachDisabled && (
          <p className="text-xs text-amber-600">
            {selectedDraftId ? "Save your changes as a new version before running the coach." : "Save a draft version first."}
          </p>
        )}
        {actionError && <p className="text-xs text-rose-600">{actionError}</p>}

        <CoachAction label="Run deterministic checks" busy={busyAction === "checks"} disabled={coachDisabled} onClick={handleRunChecks} />
        {checks && (
          <ResultList items={checks.map((c) => ({ key: c.check_type, status: c.passed ? "passed" : "failed", detail: c.detail }))} />
        )}

        <CoachAction label="Check completeness" busy={busyAction === "completeness"} disabled={coachDisabled} onClick={handleCheckCompleteness} />
        {completeness && (
          <ResultList
            items={completeness.map((c) => ({ key: `el-${c.element_id}`, status: c.status, detail: c.rationale ?? "" }))}
          />
        )}

        <CoachAction label="Suggest indicative score" busy={busyAction === "score"} disabled={coachDisabled} onClick={handleScore} />
        {scoring && (
          <div className="rounded-md border border-slate-200 p-2 text-xs">
            <p className="font-semibold text-slate-800">
              Band {scoring.final_band} <StatusPill status={scoring.confidence} />
            </p>
            {scoring.used_moderator && <p className="mt-1 text-slate-500">Moderator pass was used (passes disagreed).</p>}
          </div>
        )}

        <CoachAction label="Suggest fixes" busy={busyAction === "recommend"} disabled={coachDisabled} onClick={handleRecommend} />
        {recommendations && recommendations.length === 0 && <p className="text-xs text-slate-400">Nothing to fix.</p>}
        {recommendations && recommendations.length > 0 && (
          <ol className="list-decimal space-y-2 pl-4 text-xs text-slate-600">
            {recommendations.map((r) => (
              <li key={r.rank}>
                <p className="font-medium text-slate-800">{r.fix_summary}</p>
                {r.evidence_pointer && <p className="text-slate-500">Evidence: {r.evidence_pointer}</p>}
                {r.word_budget !== null && <p className="text-slate-400">~{r.word_budget} words</p>}
              </li>
            ))}
          </ol>
        )}

        <CoachAction label="Check ready to submit" busy={busyAction === "gate"} disabled={coachDisabled} onClick={handleGate} />
        {gate && (
          <div className="rounded-md border border-slate-200 p-2 text-xs">
            <StatusPill status={gate.ready_to_submit ? "ready" : "not_ready"} label={gate.ready_to_submit ? "Ready" : "Not ready"} />
            <p className="mt-1 text-slate-500">{gate.reason}</p>
          </div>
        )}

        <CoachAction
          label="Expert theme review"
          busy={busyAction === "theme-review"}
          disabled={coachDisabled}
          onClick={handleThemeReview}
        />
        {themeReview && <ThemeReviewPanel review={themeReview} subQuestions={subQuestionElements.map((e) => e.value_text)} />}
      </div>
    </div>
  );
}

function ThemeReviewPanel({ review, subQuestions }: { review: ThemeReview; subQuestions: string[] }) {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-slate-200 p-3 text-xs">
      <div>
        <p className="font-semibold text-slate-800">{review.theme}</p>
        <p className="mt-0.5 text-slate-500">{review.theme_fit}</p>
      </div>

      <p className="text-slate-600">{review.evaluator_summary}</p>

      <div className="grid grid-cols-5 gap-1 text-center">
        <ScoreTile label="Compliance" value={review.score_compliance} />
        <ScoreTile label="Practical" value={review.score_practicality} />
        <ScoreTile label="Evidence" value={review.score_evidence} />
        <ScoreTile label="Specificity" value={review.score_client_specificity} />
        <ScoreTile label="Confidence" value={review.score_evaluator_confidence} />
      </div>

      {review.strengths.length > 0 && (
        <div>
          <p className="font-semibold text-slate-700">Strengths</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-slate-600">
            {review.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {review.gaps.length > 0 && (
        <div>
          <p className="font-semibold text-slate-700">Gaps</p>
          <div className="mt-1 flex flex-col gap-2">
            {review.gaps.map((g, i) => {
              const matchedIndex = subQuestions.indexOf(g.sub_question);
              const number = matchedIndex >= 0 ? matchedIndex + 1 : i + 1;
              return (
                <div key={i} className="rounded-md border border-slate-100 bg-slate-50 p-2">
                  <p>
                    <span className="font-semibold text-slate-700">Sub-question {number}: </span>
                    {g.sub_question}
                  </p>
                  <p className="mt-0.5">
                    <span className="font-semibold text-slate-700">Answer {number}: </span>
                    {g.answer_excerpt ? g.answer_excerpt : <span className="italic text-slate-400">— not addressed —</span>}
                  </p>
                  <p className="mt-0.5">
                    <span className="font-semibold text-slate-700">Gap {number}: </span>
                    {g.gap}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {review.prioritised_improvements.length > 0 && (
        <div>
          <p className="font-semibold text-slate-700">Prioritised improvements</p>
          <ul className="mt-1 space-y-1.5">
            {review.prioritised_improvements.map((imp, i) => (
              <li key={i} className="flex items-start gap-2">
                <StatusPill status={`priority_${imp.priority.toLowerCase()}`} label={imp.priority} />
                <span className="text-slate-600">{imp.description}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {review.suggested_wording.length > 0 && (
        <div>
          <p className="font-semibold text-slate-700">Suggested wording</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-slate-600">
            {review.suggested_wording.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {review.evidence_required.length > 0 && (
        <div>
          <p className="font-semibold text-slate-700">Evidence still required</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-slate-600">
            {review.evidence_required.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <p className="font-semibold text-slate-700">Improved answer plan</p>
        <p className="mt-1 text-slate-600">{review.improved_answer_plan}</p>
      </div>
    </div>
  );
}

function ScoreTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-slate-50 py-1.5">
      <p className="text-sm font-semibold text-slate-800">{value}/5</p>
      <p className="text-[10px] uppercase tracking-wide text-slate-400">{label}</p>
    </div>
  );
}

function CoachAction({
  label,
  onClick,
  busy,
  disabled,
}: {
  label: string;
  onClick: () => void;
  busy: boolean;
  disabled: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy || disabled}
      className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-left text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {busy ? "Running..." : label}
    </button>
  );
}

function ResultList({ items }: { items: { key: string; status: string; detail: string }[] }) {
  const summary = useMemo(() => items, [items]);
  return (
    <div className="space-y-1 rounded-md border border-slate-200 p-2">
      {summary.map((item) => (
        <div key={item.key} className="flex items-start justify-between gap-2 text-xs">
          <span className="text-slate-500">{item.detail}</span>
          <StatusPill status={item.status} />
        </div>
      ))}
    </div>
  );
}
