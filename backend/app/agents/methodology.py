"""Evaluation methodology extraction.

One LLM call per "Strategy and Context" document, checking whether it genuinely discusses how the
buyer evaluates responses. Most documents won't — the model is explicitly allowed to report
nothing found rather than stretch a summary out of unrelated content, the same no-fabrication
standard used everywhere else in this codebase.

Like every other agent, this module never touches the database directly — routers own fetching
and persisting; this only holds the LLM call and a pure formatting helper.
"""
from typing import List, Optional

from app import llm_client
from app.models import MethodologyExtraction

AGENT_NAME = "methodology"


def extract_methodology(document_text: str) -> Optional[str]:
    result: MethodologyExtraction = llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="methodology_extract_v1.txt",
        variables={"document_text": document_text},
        response_model=MethodologyExtraction,
    )
    if not result.methodology_found or not result.summary:
        return None
    return result.summary


def format_methodology_context(summaries: List[str]) -> str:
    """Turns however many extracted summaries a tender has into one prompt-ready block, or an
    empty string if there are none — callers splice this straight into a prompt template, so an
    empty result must be safe to include as-is (no dangling header with nothing under it)."""
    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0]
    return "\n\n".join(f"- {s}" for s in summaries)
