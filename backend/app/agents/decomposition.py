"""Decomposition agent.

Word/diagram limits and weightings are extracted with plain code (regex over parsed text,
column-mapping over parsed tables) — never the model — because these exact numbers are trusted
as ground truth by everything downstream. Preamble/constraints/theme genuinely need the model to
read the question, but every span it returns is verified as a real substring of the source text
before it is written to the database; anything that fails is dropped, not guessed at.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from rapidfuzz import fuzz

from app import llm_client
from app.document_extraction import RawTable
from app.models import DecompositionExtraction

AGENT_NAME = "decomposition"

# Ordered (pattern, kind) pairs. First match per section wins for a given kind.
_LIMIT_PATTERNS = [
    (re.compile(r"(?:maximum(?:\s+of)?|no more than|up to)\s+([\d,]+)\s*words?\b", re.I), "word_limit"),
    (re.compile(r"([\d,]+)\s*words?\s*(?:maximum|limit)\b", re.I), "word_limit"),
    # "Maximum word count: 600" — real tender phrasing (word count as its own label, number
    # after the colon) distinct from "maximum 600 words" above.
    (re.compile(r"word\s*count\s*:?\s*(?:of\s+)?(?:maximum\s+)?([\d,]+)\b", re.I), "word_limit"),
    (
        re.compile(
            r"(?:maximum(?:\s+of)?|no more than|up to)\s+(\d+)\s*(?:diagrams?|images?|figures?)\b",
            re.I,
        ),
        "diagram_limit",
    ),
    (
        re.compile(
            r"(?:maximum(?:\s+of)?|no more than|up to)\s+(\d+)\s*(?:sides?\s+of\s+A4|pages?)\b",
            re.I,
        ),
        "diagram_limit",
    ),
]

# "(6%)" or "(12.5%)" appearing right after a question's title — the inline weighting style used
# by some real tender spreadsheets, where there's no separate clean scoring-matrix table to
# cross-reference (see _find_weight_in_tables below for the other style).
_INLINE_WEIGHT_PATTERN = re.compile(r"\((\d{1,3}(?:\.\d+)?)\s*%\)")


@dataclass
class ElementCandidate:
    kind: str
    value_text: str
    source_quote: Optional[str]
    extraction_method: str  # "rule" | "llm"


def extract_limits_and_weights(
    question_title: str,
    section_text: str,
    tables: List[RawTable],
) -> List[ElementCandidate]:
    """Pure code: no LLM call. Word/diagram limits from regex over `section_text`; weighting
    from a fuzzy-matched row in `tables` (the parsed scoring matrix)."""
    candidates: List[ElementCandidate] = []
    seen_kinds = set()

    for pattern, kind in _LIMIT_PATTERNS:
        if kind in seen_kinds:
            continue
        match = pattern.search(section_text)
        if match:
            candidates.append(
                ElementCandidate(
                    kind=kind,
                    value_text=match.group(1).replace(",", ""),
                    source_quote=match.group(0),
                    extraction_method="rule",
                )
            )
            seen_kinds.add(kind)

    # Inline "(6%)" style is tried first — it's unambiguous when present (right there in the
    # question's own text) — falling back to cross-referencing a separate scoring-matrix table
    # only when the question doesn't state its own weighting inline.
    weight = _find_inline_weight(section_text) or _find_weight_in_tables(question_title, tables)
    if weight is not None:
        candidates.append(
            ElementCandidate(
                kind="weight",
                value_text=weight,
                source_quote=None,
                extraction_method="rule",
            )
        )

    return candidates


def _find_inline_weight(section_text: str) -> Optional[str]:
    match = _INLINE_WEIGHT_PATTERN.search(section_text)
    return match.group(1) if match else None


def _find_weight_in_tables(question_title: str, tables: List[RawTable]) -> Optional[str]:
    """Fuzzy-matches `question_title` against the first column of each table row, and looks for
    a weighting-like column on the matched row. Heuristic, first-pass — validate against a real
    scoring matrix early (see README "First run checklist") and tighten if it misfires."""
    best_row = None
    best_score = 0.0
    weight_col_idx = None

    for table in tables:
        if not table.rows:
            continue
        header = [str(c).strip().lower() for c in table.rows[0]]
        candidate_weight_idx = next(
            (i for i, col in enumerate(header) if "weight" in col or "%" in col), None
        )
        if candidate_weight_idx is None:
            continue
        for row in table.rows[1:]:
            if not row:
                continue
            score = fuzz.partial_ratio(question_title.lower(), str(row[0]).lower())
            if score > best_score:
                best_score = score
                best_row = row
                weight_col_idx = candidate_weight_idx

    if best_row is not None and best_score >= 75 and weight_col_idx is not None:
        try:
            return str(best_row[weight_col_idx]).strip()
        except IndexError:
            return None
    return None


def extract_prose_elements(
    question_text: str,
    evaluation_methodology_context: str = "",
    tender_instructions_context: str = "",
) -> List[ElementCandidate]:
    """LLM call, constrained to verbatim extraction. Every span the model returns is checked
    against `question_text` with a plain substring test — the model cannot get a fabricated
    span past this function. `evaluation_methodology_context` and `tender_instructions_context`
    (if any) are background only, used to inform theme classification and understanding of what
    this question is really asking — the prompt explicitly forbids copying from either into
    preamble or constraints, which stay verbatim-from-the-question-only regardless."""
    result: DecompositionExtraction = llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="decomposition_extract_v1.txt",
        variables={
            "question_text": question_text,
            "evaluation_methodology_section": _format_background_section(evaluation_methodology_context),
            "tender_instructions_section": _format_background_section(tender_instructions_context),
        },
        response_model=DecompositionExtraction,
    )

    candidates: List[ElementCandidate] = []

    if result.preamble and result.preamble in question_text:
        candidates.append(
            ElementCandidate(
                kind="preamble",
                value_text=result.preamble,
                source_quote=result.preamble,
                extraction_method="llm",
            )
        )

    for constraint in result.constraints:
        if constraint and constraint in question_text:
            candidates.append(
                ElementCandidate(
                    kind="constraint",
                    value_text=constraint,
                    source_quote=constraint,
                    extraction_method="llm",
                )
            )
        # Silently dropped if not a verbatim match — no fabricated constraint reaches the DB.

    candidates.append(
        ElementCandidate(
            kind="theme",
            value_text=result.theme.value,
            source_quote=None,
            extraction_method="llm",
        )
    )

    return candidates


def _format_background_section(context: str) -> str:
    return context if context else "(none available)"


def run_decomposition(
    question_title: str,
    question_text: str,
    tables: List[RawTable],
    evaluation_methodology_context: str = "",
    tender_instructions_context: str = "",
) -> List[ElementCandidate]:
    """Orchestrates both extraction layers. Callers (the router) are responsible for persisting
    the returned candidates to `elements` with locked=0 — decomposition never locks its own
    output. `evaluation_methodology_context` comes from app/agents/methodology.py's
    format_methodology_context(); `tender_instructions_context` comes from a
    query_tender_requirements() retrieval scoped to this question — both fetched by the router,
    this function stays DB-free."""
    candidates = extract_limits_and_weights(question_title, question_text, tables)
    candidates.extend(extract_prose_elements(question_text, evaluation_methodology_context, tender_instructions_context))
    return candidates
