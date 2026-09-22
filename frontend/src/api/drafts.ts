// Draft-scoped agent actions — everything that hangs off /drafts/{id}/...
import { apiGet, apiPost } from "./http";
import type {
  CompletenessResult,
  DeterministicCheckResult,
  GateResult,
  RecommendationItem,
  ScoringSummary,
  ThemeReview,
} from "./types";

export function runCompleteness(draftId: number) {
  return apiPost<CompletenessResult[]>(`/drafts/${draftId}/completeness`);
}

export function getCompleteness(draftId: number) {
  return apiGet<CompletenessResult[]>(`/drafts/${draftId}/completeness`);
}

export function runDeterministicChecks(draftId: number) {
  return apiPost<DeterministicCheckResult[]>(`/drafts/${draftId}/deterministic-checks`);
}

export function getDeterministicChecks(draftId: number) {
  return apiGet<DeterministicCheckResult[]>(`/drafts/${draftId}/deterministic-checks`);
}

export function runScoring(draftId: number) {
  return apiPost<ScoringSummary>(`/drafts/${draftId}/score`);
}

export function getScoring(draftId: number) {
  return apiGet<ScoringSummary>(`/drafts/${draftId}/score`);
}

export function runRecommendations(draftId: number) {
  return apiPost<RecommendationItem[]>(`/drafts/${draftId}/recommendations`);
}

export function getRecommendations(draftId: number) {
  return apiGet<RecommendationItem[]>(`/drafts/${draftId}/recommendations`);
}

export function getGate(draftId: number) {
  return apiGet<GateResult>(`/drafts/${draftId}/gate`);
}

export function runThemeReview(draftId: number) {
  return apiPost<ThemeReview>(`/drafts/${draftId}/theme-review`);
}

export function getThemeReview(draftId: number) {
  return apiGet<ThemeReview>(`/drafts/${draftId}/theme-review`);
}
