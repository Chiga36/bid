"""Unit tests for the scoring decision gate's pure logic (app.routers.gate.compute_gate),
against mocked rows — no live database needed."""
from app.routers.gate import compute_gate


def test_no_scoring_run_yet():
    result = compute_gate(None, [], [])
    assert result.ready_to_submit is False
    assert "no scoring run" in result.reason.lower()


def test_below_top_band_is_not_ready():
    scoring_summary = {"final_band": 75}
    completeness_rows = [{"element_id": 1, "status": "addressed"}]
    result = compute_gate(scoring_summary, completeness_rows, [])
    assert result.ready_to_submit is False
    assert "75" in result.reason


def test_unaddressed_element_blocks_even_at_top_band():
    scoring_summary = {"final_band": 100}
    completeness_rows = [{"element_id": 1, "status": "missing"}]
    result = compute_gate(scoring_summary, completeness_rows, [])
    assert result.ready_to_submit is False
    assert "not fully addressed" in result.reason


def test_failed_deterministic_check_blocks_even_at_top_band():
    scoring_summary = {"final_band": 100}
    completeness_rows = [{"element_id": 1, "status": "addressed"}]
    check_rows = [{"check_type": "word_count", "passed": 0}]
    result = compute_gate(scoring_summary, completeness_rows, check_rows)
    assert result.ready_to_submit is False
    assert "word_count" in result.reason


def test_top_band_all_addressed_no_failed_checks_is_ready():
    scoring_summary = {"final_band": 100}
    completeness_rows = [{"element_id": 1, "status": "addressed"}, {"element_id": 2, "status": "addressed"}]
    check_rows = [{"check_type": "word_count", "passed": 1}]
    result = compute_gate(scoring_summary, completeness_rows, check_rows)
    assert result.ready_to_submit is True


def test_only_latest_completeness_row_per_element_counts():
    scoring_summary = {"final_band": 100}
    # element 1 was "missing" on an earlier run, then fixed and re-checked as "addressed" —
    # ascending id order means the later row must win.
    completeness_rows = [
        {"element_id": 1, "status": "missing"},
        {"element_id": 1, "status": "addressed"},
    ]
    result = compute_gate(scoring_summary, completeness_rows, [])
    assert result.ready_to_submit is True
