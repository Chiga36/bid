"""Unit tests for the Evidence Score agent — a lightweight, single-purpose check scoped to one
sub-question's own answer text. LLM call and vector_store.query_evidence monkeypatched out, same
pattern as test_kyc_extraction.py."""
from app.agents import evidence_score
from app.models import EvidenceScoreResult


def test_score_and_rationale_pass_through(monkeypatch):
    monkeypatch.setattr(evidence_score.vector_store, "query_evidence", lambda tender_id, q, **kwargs: ["Acme Council case study: reduced onboarding time by 40%."])

    def fake_call_structured(**kwargs):
        return EvidenceScoreResult(score=4, rationale="Cites a specific, relevant case study with a quantified outcome.")

    monkeypatch.setattr(evidence_score.llm_client, "call_structured", fake_call_structured)

    result = evidence_score.score_sub_answer_evidence(
        sub_question_text="Describe your approach to onboarding.",
        elaboration="The evaluator wants a named, tender-relevant onboarding methodology.",
        answer_text="On the Acme Council contract we reduced onboarding time by 40% using a structured buddy system.",
        tender_id=1,
    )
    assert result.score == 4
    assert "case study" in result.rationale.lower()


def test_no_retrieved_evidence_still_returns_a_result(monkeypatch):
    monkeypatch.setattr(evidence_score.vector_store, "query_evidence", lambda tender_id, q, **kwargs: [])

    captured_variables = {}

    def fake_call_structured(**kwargs):
        captured_variables.update(kwargs["variables"])
        return EvidenceScoreResult(score=1, rationale="No specific evidence cited, generic claim only.")

    monkeypatch.setattr(evidence_score.llm_client, "call_structured", fake_call_structured)

    result = evidence_score.score_sub_answer_evidence(
        sub_question_text="Describe your approach to onboarding.",
        elaboration="",
        answer_text="We have significant experience in this area.",
        tender_id=1,
    )
    assert result.score == 1
    assert captured_variables["evidence_context"] == "(none retrieved)"
    assert captured_variables["elaboration"] == "(none available)"
