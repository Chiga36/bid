"""Completeness agent.

Per locked element: closed-book, isolated, per-element LLM check (only that element's text and
the relevant draft text ever go into the prompt — no other elements, no draft history, no
retrieval tool registered on the call). Every claimed quote is verified as a real substring of
the draft with a plain string check immediately after the call; a quote that doesn't check out
downgrades the result to "unverified" in code, not by asking the model again. A cheap lexical
pre-filter can short-circuit a trivially missing element straight to "missing" without spending
an LLM call on it at all.

Only `preamble` and `constraint` elements are real prose requirements a draft can "address" —
`word_limit`/`diagram_limit` are already checked numerically by Deterministic checks, and
`weight`/`theme` are classification metadata, not content. Running those through this agent
produced confusing, occasionally self-contradicting results in practice (e.g. a word-limit
element coming back "missing" while Deterministic checks correctly reported it as within limit)
and made the "top band, no findings" gate practically unreachable, since a theme or limit element
can essentially never be "addressed" in prose. Callers (see app/routers/completeness.py and
app/routers/benchmark.py) filter to COMPLETENESS_ELEMENT_KINDS before calling run_completeness —
kept here, not duplicated per call site, so the two stay in sync.
"""
from dataclasses import dataclass
from typing import List, Optional

from rapidfuzz import fuzz

from app import llm_client
from app.models import CompletenessCheckResult

AGENT_NAME = "completeness"

COMPLETENESS_ELEMENT_KINDS = ("preamble", "constraint")

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "your", "you", "will", "must", "from",
    "have", "shall", "should", "into", "their", "which", "such", "each", "when", "where",
}
_MIN_TOKEN_LEN = 4
_FUZZY_THRESHOLD = 80


@dataclass
class CompletenessResultRow:
    element_id: int
    status: str  # addressed | asserted_only | missing | unverified
    quote: str
    rationale: str
    verified: bool


def _key_terms(element_value_text: str) -> List[str]:
    tokens = [t.strip(".,:;()").lower() for t in element_value_text.split()]
    return [t for t in tokens if len(t) >= _MIN_TOKEN_LEN and t not in _STOPWORDS]


def lexical_prefilter(element_value_text: str, draft_text: str) -> bool:
    """Returns False only when NONE of the element's key terms have any plausible match anywhere
    in the draft — the cheap, obvious "missing" case. Returns True whenever there's enough
    overlap that the addressed-vs-asserted-only judgement genuinely needs the model."""
    terms = _key_terms(element_value_text)
    if not terms:
        return True  # nothing to check lexically; let the model decide
    draft_lower = draft_text.lower()
    return any(fuzz.partial_ratio(term, draft_lower) >= _FUZZY_THRESHOLD for term in terms)


def check_element(element_id: int, element_value_text: str, draft_text: str) -> CompletenessResultRow:
    result: CompletenessCheckResult = llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="completeness_check_v1.txt",
        variables={"element_text": element_value_text, "draft_text": draft_text},
        response_model=CompletenessCheckResult,
    )

    quote = result.quote or ""
    verified = (quote == "") or (quote in draft_text)
    status = result.status if verified else "unverified"

    return CompletenessResultRow(
        element_id=element_id,
        status=status,
        quote=quote,
        rationale=result.rationale,
        verified=verified,
    )


def run_completeness(
    draft_text: str,
    elements: List[dict],  # each: {"id": int, "value_text": str}
) -> List[CompletenessResultRow]:
    results: List[CompletenessResultRow] = []
    for element in elements:
        if not lexical_prefilter(element["value_text"], draft_text):
            results.append(
                CompletenessResultRow(
                    element_id=element["id"],
                    status="missing",
                    quote="",
                    rationale="No overlapping terms found between this requirement and the draft.",
                    verified=True,
                )
            )
            continue
        results.append(check_element(element["id"], element["value_text"], draft_text))
    return results
