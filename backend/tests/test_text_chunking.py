"""Unit tests for the shared paragraph-boundary chunker (app/text_chunking.py), used by both the
Ingestion and Tender Requirements agents. Pure code, no Azure OpenAI credentials needed."""
from app.text_chunking import split_into_chunks


def test_split_into_chunks_keeps_short_text_as_one_chunk():
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = split_into_chunks(text, limit=1000)
    assert chunks == [text]


def test_split_into_chunks_splits_on_paragraph_boundaries_when_over_limit():
    paragraphs = [f"Paragraph {i} " + "x" * 20 for i in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = split_into_chunks(text, limit=100)
    assert len(chunks) > 1
    # every original paragraph must still be present, unsplit, in exactly one chunk
    rejoined = "\n\n".join(chunks)
    for p in paragraphs:
        assert p in rejoined


def test_split_into_chunks_handles_empty_text():
    assert split_into_chunks("", limit=1000) == []
