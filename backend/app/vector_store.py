"""Thin wrapper around ChromaDB. One persistent local collection, filtered by tender_id at query
time — evidence is never retrieved across tenders. Uses Chroma's bundled default embedding
function (a small local model) rather than a separate Azure OpenAI embeddings deployment: `.env`
only defines one Azure deployment (a chat model), and adding a second cloud dependency for
embeddings isn't justified at POC scale. This is a deliberate trade-off, not an oversight — revisit
if evidence-retrieval quality turns out to matter more than expected.
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


def add_evidence(tender_id: int, chunk_ids: List[str], chunk_texts: List[str], source_document: str) -> None:
    if not chunk_texts:
        return
    collection = _get_collection()
    collection.add(
        ids=chunk_ids,
        documents=chunk_texts,
        metadatas=[{"tender_id": tender_id, "source_document": source_document} for _ in chunk_texts],
    )


def query_evidence(tender_id: int, query_text: str, top_k: int = 3) -> List[str]:
    """Returns up to `top_k` evidence chunk texts for this tender only — the metadata filter is
    a hard pre-filter, not a ranking signal, so evidence never crosses tender lines."""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    result = collection.query(
        query_texts=[query_text],
        n_results=top_k,
        where={"tender_id": tender_id},
    )
    documents = result.get("documents") or [[]]
    return documents[0]
