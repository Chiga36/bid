"""Unit tests for Deterministic checks — plain code, no Azure credentials needed."""
from app.agents.deterministic_checks import (
    check_cross_references,
    check_diagram_count,
    check_pass_fail_section,
    check_word_count,
    run_deterministic_checks,
)


def test_word_count_within_limit_passes():
    result = check_word_count("one two three four five", word_limit=10)
    assert result.passed is True
    assert result.check_type == "word_count"


def test_word_count_over_limit_fails():
    result = check_word_count("one two three four five", word_limit=3)
    assert result.passed is False
    assert "over limit" in result.detail


def test_word_count_skipped_when_no_limit_locked():
    assert check_word_count("some draft text", word_limit=None) is None


def test_diagram_count_within_limit_passes():
    draft = "See Figure 1 for the architecture overview."
    result = check_diagram_count(draft, diagram_limit=2)
    assert result.passed is True


def test_diagram_count_over_limit_fails():
    draft = "See Figure 1, Figure 2 and Figure 3 for details."
    result = check_diagram_count(draft, diagram_limit=1)
    assert result.passed is False


def test_cross_reference_is_informational_never_fails():
    draft = "As described in Section 4.2 and Appendix 3, our approach is..."
    result = check_cross_references(draft)
    assert result.passed is True
    assert "section 4.2" in result.detail.lower()


def test_pass_fail_section_flags_empty_draft():
    result = check_pass_fail_section("   ", question_category="pass_fail")
    assert result.passed is False


def test_pass_fail_section_skipped_for_scored_questions():
    assert check_pass_fail_section("some content", question_category="scored") is None


def test_run_deterministic_checks_combines_applicable_checks():
    draft = "one two three. See Figure 1."
    results = run_deterministic_checks(draft, word_limit=10, diagram_limit=1, question_category="scored")
    check_types = {r.check_type for r in results}
    assert check_types == {"word_count", "diagram_count", "cross_reference"}
