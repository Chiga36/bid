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
import { createDraft, decomposeQuestion, getElements, listDrafts, lockRegister, scoreElementEvidence } from "../api/questions";
import { listQuestions } from "../api/tenders";
import type {
  CompletenessResult,
  DeterministicCheckResult,
  Draft,
  ElementRow,
  EvidenceScoreResult,
  GateResult,
  Question,
  RecommendationItem,
  ScoringRun,
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

  // Per-sub-question scratch work — keyed by element_id, which is globally unique, so switching
  // questions and back naturally keeps each question's own answers without needing an explicit
  // reset. Never persisted anywhere on its own; it only becomes durable once "Compose into draft"
  // folds it into editorText and that's saved as a real version, same as the rest of this page.
  const [answersByElement, setAnswersByElement] = useState<Record<number, string>>({});
  const [elementScores, setElementScores] = useState<Record<number, EvidenceScoreResult>>({});
  const [checkingElementId, setCheckingElementId] = useState<number | null>(null);

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

  // `retryable` covers every agent action here except draft creation: re-running Decompose,
  // Completeness, Scoring, etc. is always safe (they either overwrite unlocked state or just
  // produce a fresh assessment — see each endpoint's own idempotency notes). Silently retrying
  // absorbs the kind of one-off transient hiccup that previously needed a second manual click
  // (e.g. a backend agent's first call in a while doing some one-time setup) without the user
  // ever seeing it. `createDraft`, by contrast, is NOT idempotent — a silent retry after a
  // response that failed to arrive (but whose request the server actually completed) would
  // create a genuine duplicate version, so save explicitly opts out.
  async function withBusy(action: string, fn: () => Promise<void>, retryable = true) {
    setBusyAction(action);
    setActionError(null);
    try {
      await fn();
    } catch (firstErr) {
      if (!retryable) {
        reportActionError(firstErr);
      } else {
        try {
          await fn();
        } catch (err) {
          reportActionError(err);
        }
      }
    } finally {
      setBusyAction(null);
    }
  }

  function reportActionError(err: unknown) {
    // A failed fetch (e.g. the backend process dying mid-request) can surface as an Error with
    // an empty .message — `actionError && <p>...` would then render nothing at all, silently
    // resetting the button with no visible sign anything went wrong. Never let that happen:
    // always show *something* if a coach action actually failed.
    const message = err instanceof Error && err.message ? err.message : "Something went wrong — please try again.";
    setActionError(message);
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
    // retryable=false: unlike every other action here, creating a draft is not idempotent — a
    // silent retry after a response that simply failed to arrive (but whose request the server
    // had already completed) would create a genuine duplicate version in the history.
    await withBusy(
      "save",
      async () => {
        const draft = await createDraft(selectedQuestionId, editorText);
        const ds = await listDrafts(selectedQuestionId);
        setDrafts(ds);
        setSelectedDraftId(draft.id);
        resetCoachResults();
        // Mark this question's green submitted-version dot immediately rather than waiting on a
        // full re-fetch of the questions list.
        setQuestions((prev) => prev.map((q) => (q.id === selectedQuestionId ? { ...q, has_draft: true } : q)));
      },
      false
    );
  }

  function handleSelectVersion(draft: Draft) {
    setSelectedDraftId(draft.id);
    setEditorText(draft.content_text);
    resetCoachResults();
  }

  function handleAnswerChange(elementId: number, text: string) {
    setAnswersByElement((prev) => ({ ...prev, [elementId]: text }));
  }

  async function handleCheckEvidence(el: ElementRow) {
    const answerText = (answersByElement[el.id] ?? "").trim();
    if (!answerText) return;
    setCheckingElementId(el.id);
    setActionError(null);
    try {
      const result = await scoreElementEvidence(el.id, answerText);
      setElementScores((prev) => ({ ...prev, [el.id]: result }));
    } catch (err) {
      reportActionError(err);
    } finally {
      setCheckingElementId(null);
    }
  }

  // Always available regardless of how many boxes are filled — empty ones just contribute
  // nothing, same as the main draft box itself has never required anything in particular.
  // Overwrites editorText, same as selecting a different version already does; the main draft box
  // stays freely editable afterward for final polish before Save.
  function handleComposeIntoDraft() {
    const composed = subQuestionElements
      .map((el) => (answersByElement[el.id] ?? "").trim())
      .filter((text) => text.length > 0)
      .join("\n\n");
    setEditorText(composed);
  }

  async function handleCheckCompleteness() {
    if (!selectedDraftId) return;
    await withBusy("completeness", async () => setCompleteness(await runCompleteness(selectedDraftId)));
  }

  async function handleRunChecks() {
    if (!selectedDraftId) return;
    await withBusy("checks", async () => setChecks(await runDeterministicChecks(selectedDraftId)));
  }

  async function handleExpertReview() {
    if (!selectedDraftId) return;
    // Indicative Score and Theme Review used to be two separate coach actions with two separate
    // result blocks — too much for a bid writer to read as unrelated outputs when they're really
    // two views of the same judgement on the same draft. Run both and render them as one panel
    // (see the merged block below): the band up front, then the full expert critique.
    await withBusy("expert-review", async () => {
      const [scoreResult, reviewResult] = await Promise.all([runScoring(selectedDraftId), runThemeReview(selectedDraftId)]);
      setScoring(scoreResult);
      setThemeReview(reviewResult);
    });
  }

  async function handleRecommend() {
    if (!selectedDraftId) return;
    await withBusy("recommend", async () => setRecommendations(await runRecommendations(selectedDraftId)));
  }

  async function handleGate() {
    if (!selectedDraftId) return;
    await withBusy("gate", async () => setGate(await getGate(selectedDraftId)));
  }

  const coachDisabled = !selectedDraftId || hasUnsavedChanges;
  const attemptedCount = questions.filter((q) => q.has_draft).length;

  if (!selectedTenderId) {
    return <p className="text-sm text-slate-500">Create or select a tender first (top right).</p>;
  }

  return (
    <div className="grid h-full grid-cols-[280px_1fr_320px] gap-4">
      {/* Left: questions */}
      <div className="flex flex-col gap-2 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3">
        <div className="flex items-center justify-between px-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Questions</p>
          {questions.length > 0 && <QuestionsProgress attempted={attemptedCount} total={questions.length} />}
        </div>
        {questions.length === 0 && <p className="px-1 text-xs text-slate-400">No questions yet — add some via Data Ingestion.</p>}
        {questions.map((q) => (
          <button
            key={q.id}
            onClick={() => setSelectedQuestionId(q.id)}
            className={`rounded-md border px-3 py-2 text-left text-sm transition-colors ${
              q.id === selectedQuestionId ? "border-brand-300 bg-brand-50" : "border-transparent hover:bg-slate-50"
            }`}
          >
            <p className="flex items-center gap-1.5 font-medium text-slate-800">
              {q.has_draft && (
                <span
                  title="At least one version submitted"
                  className="h-2 w-2 shrink-0 rounded-full bg-emerald-500"
                />
              )}
              <span className="truncate">{q.title}</span>
            </p>
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
                className="flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busyAction === "decompose" && <Spinner />}
                {busyAction === "decompose"
                  ? "Decomposing..."
                  : elements.length === 0
                  ? "Decompose question"
                  : "Re-decompose (unlocked elements only)"}
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
                {subQuestionElements.map((el, i) => {
                  const answerText = answersByElement[el.id] ?? "";
                  const score = elementScores[el.id];
                  const checking = checkingElementId === el.id;
                  return (
                    <div key={el.id} className="rounded-md border border-slate-200 bg-white p-2 text-xs">
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-medium text-slate-800">
                          Sub-question {i + 1}: <span className="font-normal">{el.value_text}</span>
                        </p>
                        <div className="flex shrink-0 items-center gap-1.5">
                          {score && (
                            <span
                              title={score.rationale}
                              className="flex items-center gap-1 rounded-full bg-brand-50 px-1.5 py-0.5 font-semibold text-brand-700"
                            >
                              Evidence <ScoreDots value={score.score} /> {score.score}/5
                            </span>
                          )}
                          {el.locked && <StatusPill status="ready" label="locked" />}
                        </div>
                      </div>
                      {el.elaboration && (
                        <p className="mt-1 pl-3 text-slate-600">
                          <span className="font-medium text-slate-500">What this is asking: </span>
                          {el.elaboration}
                        </p>
                      )}
                      {el.answer_guidance && el.answer_guidance.length > 0 && (
                        <div className="mt-1 pl-3 text-slate-600">
                          <span className="font-medium text-slate-500">Suggested structure: </span>
                          <ul className="mt-0.5 list-disc space-y-0.5 pl-4">
                            {el.answer_guidance.map((point, j) => (
                              <li key={j}>{point}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <textarea
                        className="mt-2 min-h-[70px] w-full rounded-md border border-slate-300 p-2 text-xs"
                        placeholder="Write your answer to this sub-question here, including evidence..."
                        value={answerText}
                        onChange={(e) => handleAnswerChange(el.id, e.target.value)}
                      />
                      <div className="mt-1.5 flex items-center justify-between">
                        <button
                          onClick={() => handleCheckEvidence(el)}
                          disabled={checking || !answerText.trim()}
                          className="flex items-center gap-1.5 rounded-md border border-slate-300 px-2 py-1 font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {checking && <Spinner />}
                          {checking ? "Checking..." : "Check evidence"}
                        </button>
                        {score && <span className="text-slate-400">{score.rationale}</span>}
                      </div>
                    </div>
                  );
                })}

                <button
                  onClick={handleComposeIntoDraft}
                  className="self-start rounded-md border border-brand-300 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-50"
                >
                  Compose into draft ↓
                </button>
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
          <div className="flex flex-col gap-2">
            <CompletenessLegend />
            {completeness.map((c) => {
              const element = elements.find((e) => e.id === c.element_id);
              return (
                <details
                  key={c.element_id}
                  className="group rounded-md border border-slate-200 text-xs [&::-webkit-details-marker]:hidden"
                >
                  <summary className="flex cursor-pointer list-none items-start justify-between gap-2 p-2 font-medium text-slate-800">
                    <span className="flex items-start gap-1.5">
                      <span className="mt-0.5 text-slate-400 transition-transform group-open:rotate-90">▸</span>
                      <span>{element ? element.value_text : `Element ${c.element_id}`}</span>
                    </span>
                    <CompletenessSymbol status={c.status} />
                  </summary>
                  <div className="border-t border-slate-100 p-2 text-slate-600">
                    {c.quote && <p className="text-slate-500">Quote: "{c.quote}"</p>}
                    {c.rationale && <p className="mt-1">{c.rationale}</p>}
                  </div>
                </details>
              );
            })}
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
          label="Expert review & score"
          busy={busyAction === "expert-review"}
          disabled={coachDisabled}
          onClick={handleExpertReview}
        />
        {themeReview && (
          <ThemeReviewPanel
            review={themeReview}
            scoring={scoring}
            subQuestions={subQuestionElements.map((e) => e.value_text)}
          />
        )}
      </div>
    </div>
  );
}

function ThemeReviewPanel({
  review,
  scoring,
  subQuestions,
}: {
  review: ThemeReview;
  scoring: ScoringSummary | null;
  subQuestions: string[];
}) {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-slate-200 p-3 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-slate-800">{review.theme}</p>
          <p className="mt-0.5 text-slate-500">{review.theme_fit}</p>
        </div>
        {scoring && (
          <span className="shrink-0 rounded-full bg-brand-50 px-2 py-1 text-center text-xs font-semibold text-brand-700">
            Band {scoring.final_band}
          </span>
        )}
      </div>

      {review.evaluator_summary.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-4 text-slate-600">
          {review.evaluator_summary.map((point, i) => (
            <li key={i}>{point}</li>
          ))}
        </ul>
      )}

      <div className="flex flex-col gap-1 rounded-md border border-slate-100 p-2">
        <ScoreRow label="Compliance" value={review.score_compliance} />
        <ScoreRow label="Practicality" value={review.score_practicality} />
        <ScoreRow label="Evidence" value={review.score_evidence} />
        <ScoreRow label="Client specificity" value={review.score_client_specificity} />
        <ScoreRow label="Evaluator confidence" value={review.score_evaluator_confidence} />
      </div>

      {scoring && (
        <div className="rounded-md border border-slate-100 p-2">
          {scoring.used_moderator && <p className="text-slate-500">Moderator pass was used (passes disagreed).</p>}
          <ScoringRationale runs={scoring.runs} usedModerator={scoring.used_moderator} />
        </div>
      )}

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

      {review.improved_answer_plan.length > 0 && (
        <div>
          <p className="font-semibold text-slate-700">Improved answer plan</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-slate-600">
            {review.improved_answer_plan.map((point, i) => (
              <li key={i}>{point}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ScoringRationale({ runs, usedModerator }: { runs: ScoringRun[]; usedModerator: boolean }) {
  const moderatorRun = runs.find((r) => r.pass_number === "moderator");
  const passRuns = runs.filter((r) => r.pass_number !== "moderator");

  if (usedModerator && moderatorRun?.rationale) {
    return (
      <div className="mt-2 flex flex-col gap-2">
        <div>
          <p className="font-semibold text-slate-700">Why this score</p>
          <p className="mt-0.5 text-slate-600">{moderatorRun.rationale}</p>
        </div>
        {passRuns.length > 0 && (
          <div>
            <p className="font-semibold text-slate-700">Individual assessments</p>
            <div className="mt-1 flex flex-col gap-1.5">
              {passRuns.map((r) => (
                <p key={r.pass_number} className="text-slate-600">
                  <span className="font-medium text-slate-500">
                    Assessment {r.pass_number} (Band {r.band_value}):{" "}
                  </span>
                  {r.rationale}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="mt-2 flex flex-col gap-1.5">
      <p className="font-semibold text-slate-700">Why this score</p>
      {passRuns.map((r) => (
        <p key={r.pass_number} className="text-slate-600">
          <span className="font-medium text-slate-500">Assessment {r.pass_number}: </span>
          {r.rationale}
        </p>
      ))}
    </div>
  );
}

function ScoreRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-2 py-0.5">
      <span className="text-slate-500">{label}</span>
      <span className="flex items-center gap-1.5">
        <ScoreDots value={value} />
        <span className="w-6 text-right font-semibold text-slate-800">{value}/5</span>
      </span>
    </div>
  );
}

// "Attempted" = has_draft (see backend's GET /tenders/{id}/questions) — at least one version has
// been saved for that question. A ring rather than a plain fraction since it's meant to be
// glanceable — how far through the tender you are — not something you have to read closely.
function QuestionsProgress({ attempted, total }: { attempted: number; total: number }) {
  const size = 44;
  const strokeWidth = 4.5;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const fraction = total > 0 ? attempted / total : 0;
  const offset = circumference * (1 - fraction);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} title={`${attempted} of ${total} questions attempted`}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e2e8f0" strokeWidth={strokeWidth} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#00338D"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.3s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-[9px] font-semibold leading-none text-slate-700">
        {attempted}/{total}
      </div>
    </div>
  );
}

function ScoreDots({ value }: { value: number }) {
  return (
    <span className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className={`h-1.5 w-1.5 rounded-full ${n <= value ? "bg-brand-500" : "bg-slate-200"}`} />
      ))}
    </span>
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
      className="flex w-full items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-left text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {busy && <Spinner />}
      {busy ? "Running..." : label}
    </button>
  );
}

function Spinner() {
  return (
    <svg className="h-3 w-3 shrink-0 animate-spin text-slate-500" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

const COMPLETENESS_SYMBOLS: Record<string, { symbol: string; className: string; label: string }> = {
  addressed: { symbol: "✓", className: "text-emerald-600", label: "Addressed" },
  asserted_only: { symbol: "~", className: "text-amber-600", label: "Asserted only — claimed but not explained" },
  missing: { symbol: "✗", className: "text-rose-600", label: "Missing" },
  unverified: { symbol: "?", className: "text-rose-600", label: "Unverified — quote didn't check out" },
};

function CompletenessSymbol({ status }: { status: string }) {
  const entry = COMPLETENESS_SYMBOLS[status] ?? { symbol: "•", className: "text-slate-400", label: status };
  return (
    <span className={`shrink-0 text-sm font-bold ${entry.className}`} title={entry.label}>
      {entry.symbol}
    </span>
  );
}

function CompletenessLegend() {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 rounded-md bg-slate-50 p-2 text-[11px] text-slate-500">
      {Object.values(COMPLETENESS_SYMBOLS).map((entry) => (
        <span key={entry.label} className="flex items-center gap-1">
          <span className={`text-sm font-bold ${entry.className}`}>{entry.symbol}</span>
          {entry.label}
        </span>
      ))}
    </div>
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
