import { apiGet, apiPost } from "./http";
import type { Draft, ElementRow, EvidenceScoreResult } from "./types";

export function decomposeQuestion(questionId: number) {
  return apiPost<ElementRow[]>(`/questions/${questionId}/decompose`);
}

export function getElements(questionId: number) {
  return apiGet<ElementRow[]>(`/questions/${questionId}/elements`);
}

export function lockRegister(questionId: number) {
  return apiPost<ElementRow[]>(`/questions/${questionId}/lock`);
}

export function listDrafts(questionId: number) {
  return apiGet<Draft[]>(`/questions/${questionId}/drafts`);
}

export function createDraft(questionId: number, contentText: string) {
  return apiPost<Draft>(`/questions/${questionId}/drafts`, { content_text: contentText });
}

export function scoreElementEvidence(elementId: number, answerText: string) {
  return apiPost<EvidenceScoreResult>(`/elements/${elementId}/evidence-score`, { answer_text: answerText });
}
