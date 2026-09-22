"""Deterministic checks. Plain code only, no LLM — sits between the locked register and
Completeness/Scoring, checking a draft against the limits Decomposition already found.

Word-count and diagram-count checks are exact and reliable: a real number compared against a
locked limit. Cross-reference and pass/fail-section checks are best-effort heuristics — real
cross-document validation would need more document structure than this POC captures, so their
output is a prompt for human review, not a hard guarantee. Same honesty standard as the
ingestion stub in app/ingestion.py.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

_IMAGE_OR_FIGURE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]*\)|(?:figure|diagram)\s+\d+", re.I)
_SECTION_REFERENCE_PATTERN = re.compile(r"(?:section|clause|appendix)\s+\d+(?:\.\d+)*", re.I)


@dataclass
class CheckResult:
    check_type: str  # word_count | diagram_count | cross_reference | pass_fail_section
    passed: bool
    detail: str


def check_word_count(draft_text: str, word_limit: Optional[int]) -> Optional[CheckResult]:
    if word_limit is None:
        return None
    actual = len(draft_text.split())
    passed = actual <= word_limit
    detail = f"{actual} words against a limit of {word_limit}" + ("" if passed else " — over limit")
    return CheckResult(check_type="word_count", passed=passed, detail=detail)


def check_diagram_count(draft_text: str, diagram_limit: Optional[int]) -> Optional[CheckResult]:
    if diagram_limit is None:
        return None
    actual = len(_IMAGE_OR_FIGURE_PATTERN.findall(draft_text))
    passed = actual <= diagram_limit
    detail = (
        f"{actual} diagram/figure reference(s) found against a limit of {diagram_limit}"
        + ("" if passed else " — over limit")
    )
    return CheckResult(check_type="diagram_count", passed=passed, detail=detail)


def check_cross_references(draft_text: str) -> CheckResult:
    """Best-effort: lists section/clause/appendix references for a human to verify manually.
    Does not confirm the referenced sections actually exist — always passes on its own."""
    matches = sorted(set(m.lower() for m in _SECTION_REFERENCE_PATTERN.findall(draft_text)))
    detail = (
        f"Found {len(matches)} reference(s): {', '.join(matches)} — verify manually, not auto-confirmed."
        if matches
        else "No section/clause/appendix references found."
    )
    return CheckResult(check_type="cross_reference", passed=True, detail=detail)


def check_pass_fail_section(draft_text: str, question_category: str) -> Optional[CheckResult]:
    """Best-effort: for a pass_fail/sq question, only confirms the draft isn't empty. A real
    mandatory-requirement check overlaps with what the Completeness agent already does per
    element — this stays intentionally minimal rather than duplicating that logic badly."""
    if question_category not in ("pass_fail", "sq"):
        return None
    passed = len(draft_text.strip()) > 0
    detail = "Draft is non-empty." if passed else "Draft is empty for a pass/fail question."
    return CheckResult(check_type="pass_fail_section", passed=passed, detail=detail)


def run_deterministic_checks(
    draft_text: str,
    word_limit: Optional[int],
    diagram_limit: Optional[int],
    question_category: str,
) -> List[CheckResult]:
    checks = [
        check_word_count(draft_text, word_limit),
        check_diagram_count(draft_text, diagram_limit),
        check_cross_references(draft_text),
        check_pass_fail_section(draft_text, question_category),
    ]
    return [c for c in checks if c is not None]
