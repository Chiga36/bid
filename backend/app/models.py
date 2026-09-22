"""Pydantic models: both the API's request/response shapes and the structured-output schemas
that agents force Azure OpenAI to return through (via llm_client.call_structured)."""
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

BandValue = Literal[0, 25, 50, 75, 100]
QuestionCategory = Literal["sq", "pass_fail", "scored"]
ElementKind = Literal["preamble", "constraint", "word_limit", "diagram_limit", "weight", "theme"]
CompletenessStatus = Literal["addressed", "asserted_only", "missing", "unverified"]
Confidence = Literal["high", "low"]


class Theme(str, Enum):
    """The seven fixed review themes. The model can only ever return one of these — never invent an eighth."""

    UNDERSTANDING_OUTCOMES = "Understanding & Outcomes"
    DELIVERY_METHODOLOGY = "Delivery Methodology"
    GOVERNANCE_STANDARDS = "Governance & Standards"
    PERFORMANCE_QUALITY = "Performance, Quality & Standards"
    CAPABILITY_KNOWLEDGE_TRANSFER = "Capability & Knowledge Transfer"
    TEAM_RESOURCING = "Team & Resourcing"
    RELEVANT_EXPERIENCE = "Relevant Experience"


# ---------------------------------------------------------------------------
# API request/response models
# ---------------------------------------------------------------------------

class TenderCreate(BaseModel):
    competition_name: str
    contract_reference: Optional[str] = None
    purchasing_authority: Optional[str] = None
    procedure_type: Optional[str] = None


class TenderOut(TenderCreate):
    id: int
    created_at: str


class ScoringBandIn(BaseModel):
    band_value: BandValue
    descriptor_text: str


class QuestionOut(BaseModel):
    id: int
    tender_id: int
    title: str
    question_text: str
    category: QuestionCategory
    source_ref: Optional[str] = None


class ElementOut(BaseModel):
    id: int
    question_id: int
    kind: ElementKind
    value_text: str
    source_quote: Optional[str] = None
    extraction_method: Literal["rule", "llm"]
    locked: bool


class DraftCreate(BaseModel):
    content_text: str


class DraftOut(BaseModel):
    id: int
    question_id: int
    version_number: int
    content_text: str
    created_at: str


class CompletenessResultOut(BaseModel):
    element_id: int
    status: CompletenessStatus
    quote: Optional[str] = None
    rationale: Optional[str] = None
    verified: bool


class ScoringRunOut(BaseModel):
    pass_number: str
    band_value: BandValue
    rationale: Optional[str] = None
    temperature: Optional[float] = None


class ScoringSummaryOut(BaseModel):
    final_band: BandValue
    confidence: Confidence
    used_moderator: bool
    runs: List[ScoringRunOut]


# ---------------------------------------------------------------------------
# LLM structured-output schemas (one per agent call that touches the model).
# These are passed straight to llm_client.call_structured() as the target shape.
# ---------------------------------------------------------------------------

class DecompositionExtraction(BaseModel):
    """Output of the Decomposition agent's prose-extraction LLM call.
    preamble/constraints MUST be verbatim substrings of the source question text —
    llm_client verifies this and drops anything that isn't, before it reaches the DB."""

    preamble: Optional[str] = Field(default=None, description="Verbatim preamble sentence, if present")
    constraints: List[str] = Field(default_factory=list, description="Verbatim constraint sentences")
    theme: Theme


class CompletenessCheckResult(BaseModel):
    """Output of the Completeness agent's per-element LLM call.
    The model may only ever propose addressed/asserted_only/missing — 'unverified' is assigned
    later, in code, if `quote` fails the substring check against the draft."""

    status: Literal["addressed", "asserted_only", "missing"]
    quote: str = Field(description="Verbatim sentence from the draft supporting this status")
    rationale: str


class MethodologyExtraction(BaseModel):
    """Output of the methodology-extraction agent's single LLM call. The model is explicitly
    allowed to report nothing found — most documents won't discuss evaluation methodology at
    all, and forcing a summary out of them would be fabrication."""

    methodology_found: bool
    summary: Optional[str] = Field(
        default=None, description="Summary of the evaluation methodology, only if genuinely present"
    )


class ScoringPassResult(BaseModel):
    band_value: BandValue
    rationale: str


class ScoringModeratorResult(BaseModel):
    band_value: BandValue
    rationale: str


class RecommendationItem(BaseModel):
    element_reference: str = Field(description="Short label of which requirement this fix addresses")
    fix_summary: str
    evidence_pointer: str = Field(description="Where to find supporting evidence — a pointer, not written text")
    word_budget: int = Field(description="Suggested word budget for this fix")


class RecommendationResult(BaseModel):
    """Capped at 3 by the schema itself, not just the prompt — mirrors the 'top three fixes'
    design agreed earlier: a synthesiser output, not a dump of every possible improvement."""

    fixes: List[RecommendationItem] = Field(max_length=3)


# ---------------------------------------------------------------------------
# Additional API response models for the second build pass
# ---------------------------------------------------------------------------

class DeterministicCheckOut(BaseModel):
    check_type: str
    passed: bool
    detail: str


class GateOut(BaseModel):
    ready_to_submit: bool
    reason: str


class ClarificationCreate(BaseModel):
    question_id: Optional[int] = None
    content_text: str


class ClarificationOut(BaseModel):
    id: int
    tender_id: int
    question_id: Optional[int] = None
    content_text: str
    version_number: int
    created_at: str


class BusinessRuleIn(BaseModel):
    rule_key: str
    rule_value: str
    description: Optional[str] = None


class BusinessRuleOut(BusinessRuleIn):
    id: int
    tender_id: int


class RecommendationOut(BaseModel):
    rank: int
    element_id: Optional[int] = None
    fix_summary: str
    evidence_pointer: Optional[str] = None
    word_budget: Optional[int] = None


class BenchmarkCaseCreate(BaseModel):
    question_id: int
    historical_draft_text: str
    known_band: BandValue
    outcome_notes: Optional[str] = None


class BenchmarkCaseOut(BenchmarkCaseCreate):
    id: int
    tender_id: int
    created_at: str


class BenchmarkResultOut(BaseModel):
    benchmark_case_id: int
    predicted_band: BandValue
    predicted_confidence: Confidence
    band_delta: int


class ExtractedQuestion(BaseModel):
    title: str
    question_text: str = Field(description="Verbatim excerpt from the source text covering this question's full ask")
    category: QuestionCategory


class QuestionExtractionResult(BaseModel):
    """Output of the ingestion agent's per-chunk LLM call. May legitimately be empty — a chunk
    of narrative or administrative boilerplate with no real question in it should return no
    questions, not a forced one."""

    questions: List[ExtractedQuestion]


class PrioritisedImprovement(BaseModel):
    priority: Literal["Critical", "High", "Medium", "Low"]
    description: str


class ThemeReviewResult(BaseModel):
    """Output of the Theme Review agent — one shared shape across all seven theme prompts, per
    the toolkit's own 'Standard output required from every skill' section. Genuine synthesis
    (a summary, suggested wording, an improved plan), not verbatim extraction — there is nothing
    here to substring-verify the way Decomposition/Completeness do; the no-fabrication discipline
    stays at the prompt level, matching the toolkit's own instruction not to invent evidence."""

    theme_fit: str
    evaluator_summary: str
    strengths: List[str]
    gaps: List[str]
    prioritised_improvements: List[PrioritisedImprovement]
    suggested_wording: List[str]
    evidence_required: List[str]
    improved_answer_plan: str
    score_compliance: int = Field(ge=1, le=5)
    score_practicality: int = Field(ge=1, le=5)
    score_evidence: int = Field(ge=1, le=5)
    score_client_specificity: int = Field(ge=1, le=5)
    score_evaluator_confidence: int = Field(ge=1, le=5)


class ThemeReviewOut(ThemeReviewResult):
    theme: str


class AgentPromptOut(BaseModel):
    agent: str
    filename: str
    content: str
