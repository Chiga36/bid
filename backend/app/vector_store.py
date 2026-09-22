"""Thin wrapper around ChromaDB. One persistent local collection, filtered by tender_id at query
time — content is never retrieved across tenders. Uses Chroma's bundled default embedding
function (a small local model) rather than a separate Azure OpenAI embeddings deployment: `.env`
only defines one Azure deployment (a chat model), and adding a second cloud dependency for
embeddings isn't justified at POC scale. This is a deliberate trade-off, not an oversight — revisit
if retrieval quality turns out to matter more than expected.

The same collection holds two different kinds of content, kept apart by a `doc_type` metadata
field: case-study/CV/credential "evidence" (what Recommendation cites as proof), and
"tender_requirement" (extracted from the tender instructions document — what Decomposition and
Completeness use for context). Every query filters on both `tender_id` and `doc_type` as hard
pre-filters, never as a ranking signal, so a tender-instruction sentence can never be mistaken
for case-study evidence, or vice versa.
"""
from pathlib import Path
from typing import List

import chromadb

from app.config import settings

_CHROMA_DIR = settings.data_dir / "chroma"
_COLLECTION_NAME = "evidence"

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
        _collection = _client.get_or_create_collection(name=_COLLECTION_NAME)
    return _collection


def _add(tender_id: int, chunk_ids: List[str], chunk_texts: List[str], source_document: str, doc_type: str) -> None:
    if not chunk_texts:
        return
    collection = _get_collection()
    collection.add(
        ids=chunk_ids,
        documents=chunk_texts,
        metadatas=[
            {"tender_id": tender_id, "source_document": source_document, "doc_type": doc_type} for _ in chunk_texts
        ],
    )


def _query(tender_id: int, query_text: str, top_k: int, doc_type: str) -> List[str]:
    collection = _get_collection()
    if collection.count() == 0:
        return []
    result = collection.query(
        query_texts=[query_text],
        n_results=top_k,
        where={"$and": [{"tender_id": tender_id}, {"doc_type": doc_type}]},
    )
    documents = result.get("documents") or [[]]
    return documents[0]


def add_evidence(tender_id: int, chunk_ids: List[str], chunk_texts: List[str], source_document: str) -> None:
    _add(tender_id, chunk_ids, chunk_texts, source_document, doc_type="evidence")


def query_evidence(tender_id: int, query_text: str, top_k: int = 3) -> List[str]:
    """Returns up to `top_k` case-study/CV/credential evidence chunks for this tender only."""
    return _query(tender_id, query_text, top_k, doc_type="evidence")


def add_tender_requirements(tender_id: int, chunk_ids: List[str], chunk_texts: List[str], source_document: str) -> None:
    _add(tender_id, chunk_ids, chunk_texts, source_document, doc_type="tender_requirement")


def query_tender_requirements(tender_id: int, query_text: str, top_k: int = 5) -> List[str]:
    """Returns up to `top_k` extracted tender-requirement chunks for this tender only."""
    return _query(tender_id, query_text, top_k, doc_type="tender_requirement")
