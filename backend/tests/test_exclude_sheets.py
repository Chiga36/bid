"""Unit tests for document_extraction.exclude_sheets() / keep_only_sheets() — pure text
manipulation, no Azure credentials or actual xlsx file needed."""
from app.document_extraction import exclude_sheets, keep_only_sheets


def _sample_full_text():
    return (
        "## Sheet: Selection Questionnaires\n"
        "Question | Name\n"
        "1.1 | Confirm your registered company name.\n\n"
        "## Sheet: Award Questionnaires\n"
        "3.1.1 | Describe your mobilisation approach.\n"
        "3.1.2 | Describe your delivery methodology.\n\n"
        "## Sheet: Other Content\n"
        "What is your company registration number for our records?"
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


def test_keep_only_sheets_drops_everything_except_the_match():
    """The allowlist used for Questionnaire uploads (routers/tenders.py) — proves a sheet with an
    unpredictable name (here, 'Other Content', standing in for a cover page/instructions tab/
    anything else a real workbook might carry) never reaches question extraction, without having
    to know its name in advance."""
    result = keep_only_sheets(_sample_full_text(), ["award questionnaire"])
    assert "Award Questionnaires" in result
    assert "mobilisation approach" in result
    assert "Selection Questionnaires" not in result
    assert "registered company name" not in result
    assert "Other Content" not in result
    assert "registration number for our records" not in result


def test_keep_only_sheets_no_match_returns_nothing():
    result = keep_only_sheets(_sample_full_text(), ["nonexistent sheet name"])
    assert result == ""


def test_keep_only_sheets_text_with_no_sheet_markers_is_a_no_op():
    text = "Just a plain document with no sheet structure at all."
    assert keep_only_sheets(text, ["award questionnaire"]) == text
