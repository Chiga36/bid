import { apiGet, apiPost, apiUpload } from "./http";
import type { Clarification, EvidenceChunk, ProcurementStage, Question, ScoringBand, Tender } from "./types";

export function listTenders() {
  return apiGet<Tender[]>("/tenders");
}

export function createTender(input: {
  competition_name: string;
  contract_reference?: string;
  purchasing_authority?: string;
  procedure_type?: string;
}) {
  return apiPost<Tender>("/tenders", input);
}

export function getTender(tenderId: number) {
  return apiGet<Tender>(`/tenders/${tenderId}`);
}

export function getScoringBands(tenderId: number) {
  return apiGet<ScoringBand[]>(`/tenders/${tenderId}/scoring-bands`);
}

export function setScoringBands(tenderId: number, bands: ScoringBand[]) {
  return apiPost(`/tenders/${tenderId}/scoring-bands`, bands);
}

export function listQuestions(tenderId: number) {
  return apiGet<Question[]>(`/tenders/${tenderId}/questions`);
}

export function addQuestionManually(
  tenderId: number,
  input: { title: string; question_text: string; category: string },
) {
  const params = new URLSearchParams(input);
  return apiPost<Question>(`/tenders/${tenderId}/questions?${params.toString()}`);
}

export function uploadTenderDocument(tenderId: number, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<Question[]>(`/tenders/${tenderId}/documents`, formData);
}

export function listClarifications(tenderId: number) {
  return apiGet<Clarification[]>(`/tenders/${tenderId}/clarifications`);
}

export function addClarification(tenderId: number, input: { question_id?: number; content_text: string }) {
  return apiPost<Clarification>(`/tenders/${tenderId}/clarifications`, input);
}

export function listEvidence(tenderId: number) {
  return apiGet<EvidenceChunk[]>(`/tenders/${tenderId}/evidence`);
}

export function uploadEvidence(tenderId: number, file: File, category: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("category", category);
  return apiUpload<{ chunks_ingested: number }>(`/tenders/${tenderId}/evidence`, formData);
}

export function listProcurementStages(tenderId: number) {
  return apiGet<ProcurementStage[]>(`/tenders/${tenderId}/procurement-stages`);
}
