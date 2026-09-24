// Mirrors the backend's Pydantic models (backend/app/models.py). Kept as plain types, not
// generated, since the backend is small and stable enough that hand-keeping them in sync is
// simpler than adding a codegen step to a POC.

export type BandValue = 0 | 25 | 50 | 75 | 100;
export type QuestionCategory = "sq" | "pass_fail" | "scored";
export type ElementKind = "preamble" | "sub_question" | "word_limit" | "diagram_limit" | "weight" | "theme";
export type CompletenessStatus = "addressed" | "asserted_only" | "missing" | "unverified";
export type Confidence = "high" | "low";

export interface Tender {
  id: number;
  competition_name: string;
  contract_reference: string | null;
  purchasing_authority: string | null;
  procedure_type: string | null;
  created_at: string;
}

export interface ScoringBand {
  band_value: BandValue;
  descriptor_text: string;
}

export interface Question {
  id: number;
  tender_id: number;
  title: string;
  question_text: string;
  category: QuestionCategory;
  source_ref: string | null;
}

export interface ElementRow {
  id: number;
  question_id: number;
  kind: ElementKind;
  value_text: string;
  source_quote: string | null;
  elaboration: string | null;
  answer_guidance: string | null;
  extraction_method: "rule" | "llm";
  locked: boolean;
}

export interface Draft {
  id: number;
  question_id: number;
  version_number: number;
  content_text: string;
  created_at: string;
}

export interface CompletenessResult {
  element_id: number;
  status: CompletenessStatus;
  quote: string | null;
  rationale: string | null;
  verified: boolean;
}

export interface DeterministicCheckResult {
  check_type: string;
  passed: boolean;
  detail: string;
}

export interface ScoringRun {
  pass_number: string;
  band_value: BandValue;
  rationale: string | null;
  temperature: number | null;
}

export interface ScoringSummary {
  final_band: BandValue;
  confidence: Confidence;
  used_moderator: boolean;
  runs: ScoringRun[];
}

export interface GateResult {
  ready_to_submit: boolean;
  reason: string;
}

export interface RecommendationItem {
  rank: number;
  element_id: number | null;
  fix_summary: string;
  evidence_pointer: string | null;
  word_budget: number | null;
}

export interface Clarification {
  id: number;
  tender_id: number;
  question_id: number | null;
  content_text: string;
  version_number: number;
  created_at: string;
}

export interface ProcurementStage {
  id: number;
  source_document: string;
  stage_name: string;
  stage_date: string;
  created_at: string;
}

export interface EvidenceChunk {
  id: number;
  source_document: string;
  category: string;
  chunk_text: string;
  created_at: string;
}

export type ImprovementPriority = "Critical" | "High" | "Medium" | "Low";

export interface PrioritisedImprovement {
  priority: ImprovementPriority;
  description: string;
}

export interface GapEntry {
  sub_question: string;
  answer_excerpt: string;
  gap: string;
}

export interface ThemeReview {
  theme: string;
  theme_fit: string;
  evaluator_summary: string;
  strengths: string[];
  gaps: GapEntry[];
  prioritised_improvements: PrioritisedImprovement[];
  suggested_wording: string[];
  evidence_required: string[];
  improved_answer_plan: string;
  score_compliance: number;
  score_practicality: number;
  score_evidence: number;
  score_client_specificity: number;
  score_evaluator_confidence: number;
}

export interface AgentPrompt {
  agent: string;
  filename: string;
  content: string;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}
