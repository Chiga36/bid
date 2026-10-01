"""Unit tests for the Evidence Score agent — a lightweight, single-purpose check scoped to one
sub-question's own answer text, judged purely on the answer's own writing (never queries
vector_store — see agents/evidence_score.py's docstring for why). LLM call monkeypatched out,
same pattern as test_kyc_extraction.py."""
from app.agents import evidence_score
from app.models import EvidenceScoreResult


def test_score_and_rationale_pass_through(monkeypatch):
    def fake_call_structured(**kwargs):
        return EvidenceScoreResult(score=4, rationale="Cites a specific, past-tense example with a quantified outcome.")

    monkeypatch.setattr(evidence_score.llm_client, "call_structured", fake_call_structured)

    result = evidence_score.score_sub_answer_evidence(
        sub_question_text="Describe your approach to onboarding.",
        elaboration="The evaluator wants a named, tender-relevant onboarding methodology.",
        answer_text="On the Acme Council contract we reduced onboarding time by 40% using a structured buddy system.",
        tender_id=1,
    )
    assert result.score == 4
    assert "quantified outcome" in result.rationale.lower()


def test_module_never_imports_vector_store():
    """The whole point of this behavior: scoring must work identically regardless of what's in
    (or not in) the evidence library — it's judging the answer's own writing style, not
    cross-referencing retrieved content. Asserted at the module level (not just "not called in
    this test") so a future regression that reintroduces the import is caught immediately."""
    assert not hasattr(evidence_score, "vector_store")


def test_variables_passed_to_prompt_never_include_an_evidence_context(monkeypatch):
    captured_variables = {}

    def fake_call_structured(**kwargs):
        captured_variables.update(kwargs["variables"])
        return EvidenceScoreResult(score=0, rationale="Future-tense promise, no past-tense proof.")

    monkeypatch.setattr(evidence_score.llm_client, "call_structured", fake_call_structured)

    evidence_score.score_sub_answer_evidence(
        sub_question_text="Describe your approach to onboarding.",
        elaboration="",
        answer_text="We will ensure a robust onboarding process.",
        tender_id=1,
    )
    assert "evidence_context" not in captured_variables
    assert captured_variables["elaboration"] == "(none available)"
    assert captured_variables["answer_text"] == "We will ensure a robust onboarding process."
