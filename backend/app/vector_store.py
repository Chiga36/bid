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

# Reserved sentinel for cross-tender global evidence (see app/schema.sql's global_evidence_chunks
# table). Safe forever: tenders.id is INTEGER PRIMARY KEY AUTOINCREMENT, which SQLite guarantees
# starts at 1 and never reuses, so 0 can never collide with a real tender_id.
_GLOBAL_TENDER_ID = 0

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


def _query(tender_id: int, query_text: str, top_k: int, doc_type: str, include_global: bool = False) -> List[str]:
    collection = _get_collection()
    if collection.count() == 0:
        return []
    tender_filter = (
        {"$or": [{"tender_id": tender_id}, {"tender_id": _GLOBAL_TENDER_ID}]} if include_global else {"tender_id": tender_id}
    )
    result = collection.query(
        query_texts=[query_text],
        n_results=top_k,
        where={"$and": [tender_filter, {"doc_type": doc_type}]},
    )
    documents = result.get("documents") or [[]]
    return documents[0]


def add_evidence(tender_id: int, chunk_ids: List[str], chunk_texts: List[str], source_document: str) -> None:
    _add(tender_id, chunk_ids, chunk_texts, source_document, doc_type="evidence")


def query_evidence(tender_id: int, query_text: str, top_k: int = 3) -> List[str]:
    """Returns up to `top_k` case-study/CV/credential evidence chunks — this tender's own
    uploads plus the cross-tender global evidence library (see add_global_evidence), merged and
    ranked together by relevance so a bid team never has to re-upload the same case study to
    every tender to have it considered."""
    return _query(tender_id, query_text, top_k, doc_type="evidence", include_global=True)


def add_global_evidence(chunk_ids: List[str], chunk_texts: List[str], source_document: str) -> None:
    """Adds evidence not tied to any specific tender — picked up automatically by every future
    query_evidence call, for every tender, via the _GLOBAL_TENDER_ID sentinel."""
    _add(_GLOBAL_TENDER_ID, chunk_ids, chunk_texts, source_document, doc_type="evidence")


def delete_chunks(chunk_ids: List[str]) -> None:
    """Removes vectors by id — used when a global evidence document is deleted, so Chroma never
    keeps serving a chunk whose DB row (and therefore provenance) no longer exists."""
    if not chunk_ids:
        return
    collection = _get_collection()
    collection.delete(ids=chunk_ids)


def delete_tender_evidence(tender_id: int) -> None:
    """Removes every vector belonging to one tender — both doc_types (evidence and
    tender_requirement) — used when a tender itself is deleted. Filters by metadata rather than
    needing stored chunk ids, since per-tender evidence/tender-requirement uploads never persist
    their generated chunk ids in the relational DB (unlike global_evidence_chunks)."""
    collection = _get_collection()
    if collection.count() == 0:
        return
    collection.delete(where={"tender_id": tender_id})


def add_tender_requirements(tender_id: int, chunk_ids: List[str], chunk_texts: List[str], source_document: str) -> None:
    _add(tender_id, chunk_ids, chunk_texts, source_document, doc_type="tender_requirement")


def query_tender_requirements(tender_id: int, query_text: str, top_k: int = 5) -> List[str]:
    """Returns up to `top_k` extracted tender-requirement chunks for this tender only."""
    return _query(tender_id, query_text, top_k, doc_type="tender_requirement")
