"""Evidence Score agent.

A lightweight, single-purpose check — not the full Completeness/Theme Review path — run against
one sub-question's own answer text as the user writes it, before it's ever composed into the real
draft. Scores 0-5 how genuinely the given answer is grounded in real, retrievable evidence (a
named example, a quantified outcome) rather than a generic, unsubstantiated claim, using the same
"cite only from retrieved evidence, never invent" discipline as Recommendation and Theme Review's
own score_evidence.

Like every other agent, this module never touches the database directly and never persists
anything — routers own that; this only holds the LLM call.
"""
from app import llm_client, vector_store
from app.models import EvidenceScoreResult

AGENT_NAME = "evidence_score"


def score_sub_answer_evidence(
    sub_question_text: str,
    elaboration: str,
    answer_text: str,
    tender_id: int,
) -> EvidenceScoreResult:
    evidence_chunks = vector_store.query_evidence(tender_id, sub_question_text)
    evidence_context = "\n\n".join(evidence_chunks) if evidence_chunks else "(none retrieved)"
    return llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="evidence_score_v1.txt",
        variables={
            "sub_question_text": sub_question_text,
            "elaboration": elaboration or "(none available)",
            "evidence_context": evidence_context,
            "answer_text": answer_text,
        },
        response_model=EvidenceScoreResult,
        tender_id=tender_id,
    )
