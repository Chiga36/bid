"""Unit test for the Ingestion agent's verbatim-verification guard on extracted questions (LLM
call monkeypatched out, same pattern as test_completeness_verification.py — proving the wrapper
catches a fabricated question, not that the model behaves well). Chunking logic itself now lives
in, and is tested by, test_text_chunking.py — it's shared with the Tender Requirements agent."""
from app.agents import ingestion
from app.models import ExtractedQuestion, QuestionExtractionResult


def test_extract_from_chunk_drops_non_verbatim_question(monkeypatch):
    def fake_call_structured(**kwargs):
        return QuestionExtractionResult(
            questions=[
                ExtractedQuestion(
                    title="Mobilisation",
                    question_text="This sentence was never in the source chunk at all.",
                    category="scored",
                )
            ]
        )

    monkeypatch.setattr(ingestion.llm_client, "call_structured", fake_call_structured)

    result = ingestion._extract_from_chunk("Describe your mobilisation approach. Maximum 200 words.")
    assert result == []


def test_extract_from_chunk_accepts_verbatim_question(monkeypatch):
    def fake_call_structured(**kwargs):
        return QuestionExtractionResult(
            questions=[
                ExtractedQuestion(
                    title="Mobilisation",
                    question_text="Describe your mobilisation approach.",
                    category="scored",
                )
            ]
        )

    monkeypatch.setattr(ingestion.llm_client, "call_structured", fake_call_structured)

    result = ingestion._extract_from_chunk("Describe your mobilisation approach. Maximum 200 words.")
    assert len(result) == 1
    assert result[0].title == "Mobilisation"
    assert result[0].category == "scored"
