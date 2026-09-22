"""Shared paragraph-boundary chunking, used by every agent that has to hand a long document to
the model in bounded pieces (Ingestion, Tender Requirements) rather than one unbounded call."""
from typing import List


def split_into_chunks(text: str, limit: int) -> List[str]:
    """Splits on paragraph boundaries (blank lines) so a requirement/question is never cut
    mid-sentence unless a single paragraph alone exceeds the limit — greedily packs paragraphs
    into chunks no larger than `limit` characters."""
    paragraphs = [p for p in text.split("\n\n") if p]
    if not paragraphs:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for para in paragraphs:
        para_len = len(para) + 2
        if current and current_len + para_len > limit:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += para_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks
