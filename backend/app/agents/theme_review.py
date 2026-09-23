"""Theme Review agent — the seven-prompt expert critique from the Bid Response Review Skills
toolkit. Complements Completeness (per-element status), Scoring (a 0-100 band), and
Recommendation (up to three capped fixes) with a single, richer, reviewer-voice critique:
strengths, gaps, Critical/High/Medium/Low-prioritised improvements, suggested replacement
wording, and five separate 1-5 scores. One LLM call, selected by the question's own theme
(already classified by Decomposition — see app/models.py's Theme enum).

Mostly genuine synthesis (a summary, suggested wording, an improved plan), not verbatim
extraction, so there's nothing to substring-check for most fields — the no-fabrication discipline
for those stays at the prompt level, each of the seven prompts carrying the toolkit's own
instruction not to invent evidence. The one exception is `gaps[].answer_excerpt`: each gap is
explicitly anchored to one of this question's real, locked sub-questions and a real quote from
the draft, and that quote IS verified as a genuine substring of `draft_text` after the call,
exactly like Completeness verifies its own quotes — see `_verify_gap_excerpts` below.
"""
import re
from typing import List

from app import llm_client
from app.models import GapEntry, Theme, ThemeReviewResult

_LEADING_NUMBER_PATTERN = re.compile(r"^\s*\d+[.)]\s*")

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


def _format_sub_questions_block(sub_questions: List[str]) -> str:
    if not sub_questions:
        return "(none available — treat the whole question as a single sub-question)"
    return "\n".join(f"{i}. {text}" for i, text in enumerate(sub_questions, start=1))


def _verify_gap_excerpts(gaps: List[GapEntry], draft_text: str) -> List[GapEntry]:
    """Blanks (never drops) any answer_excerpt that isn't a genuine substring of the draft —
    the gap description itself is still valid even when the model's quote wasn't real. Also
    strips a leading "1. "/"1) " numeral the model sometimes echoes back from the numbered
    sub_questions_block it was given, in code rather than relying on prompt wording alone — the
    frontend matches gap.sub_question against the question's own sub-question list by exact
    text, and a stray numeral would silently break that match."""
    verified: List[GapEntry] = []
    for g in gaps:
        excerpt = g.answer_excerpt if g.answer_excerpt and g.answer_excerpt in draft_text else ""
        sub_question = _LEADING_NUMBER_PATTERN.sub("", g.sub_question)
        verified.append(GapEntry(sub_question=sub_question, answer_excerpt=excerpt, gap=g.gap))
    return verified


def run_theme_review(
    theme: Theme,
    question_text: str,
    evaluation_criteria: str,
    word_limit: str,
    draft_text: str,
    evidence_context: str,
    sub_questions: List[str],
) -> ThemeReviewResult:
    result = llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file=prompt_file_for_theme(theme),
        variables={
            "question_text": question_text,
            "evaluation_criteria": evaluation_criteria or "(none available)",
            "word_limit": word_limit or "(not stated)",
            "draft_text": draft_text,
            "evidence_context": evidence_context or "(no matching evidence found in this tender's evidence library)",
            "sub_questions_block": _format_sub_questions_block(sub_questions),
        },
        response_model=ThemeReviewResult,
    )
    result.gaps = _verify_gap_excerpts(result.gaps, draft_text)
    return result
