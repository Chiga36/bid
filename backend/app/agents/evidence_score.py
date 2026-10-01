"""Evidence Score agent.

A lightweight, single-purpose check — not the full Completeness/Theme Review path — run against
one sub-question's own answer text as the user writes it, before it's ever composed into the real
draft. Scores 0-5 how much the answer *itself* reads as concrete, provable past delivery (a named
example, a quantified outcome, past tense) rather than a vague or future-tense promise.

Deliberately does NOT query the evidence library (see vector_store.query_evidence) — this is a
judgement on the author's own writing, not a cross-reference against retrieved evidence. That
keeps the check fast, independent of what happens to be in the evidence library at the time, and
usable the moment a tender exists, before any evidence has even been uploaded. Decomposition's
own answer_guidance is the place that points at real retrieved evidence when genuinely relevant
(see app/agents/decomposition.py); this agent is purely about writing style and specificity.

Like every other agent, this module never touches the database directly and never persists
anything — routers own that; this only holds the LLM call.
"""
from typing import Optional

from app import llm_client
from app.models import EvidenceScoreResult

AGENT_NAME = "evidence_score"


def score_sub_answer_evidence(
    sub_question_text: str,
    elaboration: str,
    answer_text: str,
    tender_id: Optional[int] = None,
) -> EvidenceScoreResult:
    return llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="evidence_score_v1.txt",
        variables={
            "sub_question_text": sub_question_text,
            "elaboration": elaboration or "(none available)",
            "answer_text": answer_text,
        },
        response_model=EvidenceScoreResult,
        tender_id=tender_id,
    )
