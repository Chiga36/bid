"""Unit test for the evaluation-methodology formatting helper — the one pure, DB/LLM-free piece
of this feature. extract_methodology() itself is a single LLM call with no post-hoc guardrail
logic to unit-test the way Completeness's quote-check has, so it isn't covered here."""
from app.agents.methodology import format_methodology_context


def test_no_summaries_returns_empty_string():
    assert format_methodology_context([]) == ""


def test_single_summary_returned_as_is():
    assert format_methodology_context(["Scored on a 0/25/50/75/100 basis."]) == "Scored on a 0/25/50/75/100 basis."


def test_multiple_summaries_are_bulleted():
    result = format_methodology_context(["First summary.", "Second summary."])
    assert result == "- First summary.\n\n- Second summary."
