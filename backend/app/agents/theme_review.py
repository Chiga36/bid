"""Theme Review agent — the seven-prompt expert critique from the Bid Response Review Skills
toolkit. Complements Completeness (per-element status), Scoring (a 0-100 band), and
Recommendation (up to three capped fixes) with a single, richer, reviewer-voice critique:
strengths, gaps, Critical/High/Medium/Low-prioritised improvements, suggested replacement
wording, and five separate 1-5 scores. One LLM call, selected by the question's own theme
(already classified by Decomposition — see app/models.py's Theme enum).

No post-hoc verification pass here: unlike Decomposition/Completeness, this agent's output is
genuine synthesis (a summary, suggested wording, an improved plan), not verbatim extraction, so
there's nothing to substring-check. The no-fabrication discipline stays at the prompt level —
each of the seven prompts carries the toolkit's own instruction not to invent evidence.
"""
from app import llm_client
from app.models import Theme, ThemeReviewResult

AGENT_NAME = "theme_review"

_PROMPT_FILES = {
    Theme.UNDERSTANDING_OUTCOMES: "theme_review_understanding_outcomes_v1.txt",
    Theme.DELIVERY_METHODOLOGY: "theme_review_delivery_methodology_v1.txt",
    Theme.GOVERNANCE_STANDARDS: "theme_review_governance_standards_v1.txt",
    Theme.PERFORMANCE_QUALITY: "theme_review_performance_quality_v1.txt",
    Theme.CAPABILITY_KNOWLEDGE_TRANSFER: "theme_review_capability_knowledge_transfer_v1.txt",
    Theme.TEAM_RESOURCING: "theme_review_team_resourcing_v1.txt",
    Theme.RELEVANT_EXPERIENCE: "theme_review_relevant_experience_v1.txt",
}


def prompt_file_for_theme(theme: Theme) -> str:
    return _PROMPT_FILES[theme]


def run_theme_review(
    theme: Theme,
    question_text: str,
    evaluation_criteria: str,
    word_limit: str,
    draft_text: str,
    evidence_context: str,
) -> ThemeReviewResult:
    return llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file=prompt_file_for_theme(theme),
        variables={
            "question_text": question_text,
            "evaluation_criteria": evaluation_criteria or "(none available)",
            "word_limit": word_limit or "(not stated)",
            "draft_text": draft_text,
            "evidence_context": evidence_context or "(no matching evidence found in this tender's evidence library)",
        },
        response_model=ThemeReviewResult,
    )
