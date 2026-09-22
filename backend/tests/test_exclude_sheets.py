"""Unit tests for document_extraction.exclude_sheets() — pure text manipulation, no Azure
credentials or actual xlsx file needed."""
from app.document_extraction import exclude_sheets


def _sample_full_text():
    return (
        "## Sheet: Selection Questionnaires\n"
        "Question | Name\n"
        "1.1 | Confirm your registered company name.\n\n"
        "## Sheet: Award Questionnaires\n"
        "3.1.1 | Describe your mobilisation approach.\n"
        "3.1.2 | Describe your delivery methodology."
    )


def test_excludes_matching_sheet_case_insensitively():
    result = exclude_sheets(_sample_full_text(), ["selection questionnaire"])
    assert "Selection Questionnaires" not in result
    assert "registered company name" not in result
    assert "Award Questionnaires" in result
    assert "mobilisation approach" in result


def test_no_match_leaves_all_sheets_intact():
    result = exclude_sheets(_sample_full_text(), ["nonexistent sheet name"])
    assert "Selection Questionnaires" in result
    assert "Award Questionnaires" in result


def test_text_with_no_sheet_markers_is_a_no_op():
    text = "Just a plain document with no sheet structure at all."
    assert exclude_sheets(text, ["selection questionnaire"]) == text


def test_empty_pattern_list_keeps_everything():
    result = exclude_sheets(_sample_full_text(), [])
    assert "Selection Questionnaires" in result
    assert "Award Questionnaires" in result
