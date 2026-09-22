"""Unit tests for the Ingestion agent: the paragraph-boundary chunking logic (pure code), and
the verbatim-verification guard on extracted questions (LLM call monkeypatched out, same pattern
as test_completeness_verification.py — proving the wrapper catches a fabricated question, not
that the model behaves well)."""
from app.agents import ingestion
from app.models import ExtractedQuestion, QuestionExtractionResult


def test_split_into_chunks_keeps_short_text_as_one_chunk():
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = ingestion._split_into_chunks(text, limit=1000)
    assert chunks == [text]


def test_split_into_chunks_splits_on_paragraph_boundaries_when_over_limit():
    paragraphs = [f"Paragraph {i} " + "x" * 20 for i in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = ingestion._split_into_chunks(text, limit=100)
    assert len(chunks) > 1
    # every original paragraph must still be present, unsplit, in exactly one chunk
    rejoined = "\n\n".join(chunks)
    for p in paragraphs:
        assert p in rejoined


def test_split_into_chunks_handles_empty_text():
    assert ingestion._split_into_chunks("", limit=1000) == []


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
