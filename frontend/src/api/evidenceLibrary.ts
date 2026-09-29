import { apiDelete, apiGet, apiUpload } from "./http";
import type { GlobalEvidenceChunk, GlobalEvidenceUpload } from "./types";

export function listGlobalEvidence() {
  return apiGet<GlobalEvidenceChunk[]>("/evidence-library");
}

export function uploadGlobalEvidence(file: File, category: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("category", category);
  return apiUpload<GlobalEvidenceUpload>("/evidence-library", formData);
}

export function deleteGlobalEvidenceDocument(sourceDocument: string) {
  return apiDelete<{ source_document: string; chunks_deleted: number }>(
    `/evidence-library/document/${encodeURIComponent(sourceDocument)}`,
  );
}
