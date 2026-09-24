"""Unit tests for the Procurement Timeline agent: the table pre-filter, the table/prose fallback
order, and the verbatim guard on both paths. LLM calls monkeypatched out, same pattern as
test_scoring_matrix_extraction.py / test_tender_requirements_extraction.py."""
from app.agents import procurement_timeline
from app.document_extraction import RawTable
from app.models import (
    ExtractedProcurementStage,
    ProcurementTimelineProseResult,
    ProcurementTimelineTableResult,
)


def test_looks_like_timetable_detects_signal_words():
    assert procurement_timeline._looks_like_timetable("Procurement Timetable\nITT issued | 1 March 2026")


def test_looks_like_timetable_rejects_unrelated_table():
    assert not procurement_timeline._looks_like_timetable("Contact | Email\nJohn Smith | john@example.com")


def test_table_result_verbatim_guard_drops_fabricated_values(monkeypatch):
    def fake_call_structured(**kwargs):
        return ProcurementTimelineTableResult(
            is_procurement_timeline=True,
            stages=[ExtractedProcurementStage(stage_name="Invented stage", stage_date="1 January 2099")],
        )

    monkeypatch.setattr(procurement_timeline.llm_client, "call_structured", fake_call_structured)

    table = RawTable(rows=[["Stage", "Date"], ["ITT issued", "1 March 2026"]])
    result = procurement_timeline._extract_from_table(table)
    assert result == []


def test_table_result_keeps_verbatim_stage(monkeypatch):
    def fake_call_structured(**kwargs):
        return ProcurementTimelineTableResult(
            is_procurement_timeline=True,
            stages=[ExtractedProcurementStage(stage_name="ITT issued", stage_date="1 March 2026")],
        )

    monkeypatch.setattr(procurement_timeline.llm_client, "call_structured", fake_call_structured)

    table = RawTable(rows=[["Stage", "Date"], ["ITT issued", "1 March 2026"]])
    result = procurement_timeline._extract_from_table(table)
    assert len(result) == 1
    assert result[0].stage_name == "ITT issued"
    assert result[0].stage_date == "1 March 2026"


def test_not_a_timetable_table_returns_no_stages(monkeypatch):
    def fake_call_structured(**kwargs):
        return ProcurementTimelineTableResult(is_procurement_timeline=False, stages=[])

    monkeypatch.setattr(procurement_timeline.llm_client, "call_structured", fake_call_structured)

    table = RawTable(rows=[["Score", "Weighting"], ["Q1", "20%"]])
    result = procurement_timeline._extract_from_table(table)
    assert result == []


def test_prose_result_verbatim_guard(monkeypatch):
    def fake_call_structured(**kwargs):
        return ProcurementTimelineProseResult(
            stages=[ExtractedProcurementStage(stage_name="Invented stage", stage_date="1 January 2099")]
        )

    monkeypatch.setattr(procurement_timeline.llm_client, "call_structured", fake_call_structured)

    result = procurement_timeline._extract_from_chunk("Tender submission deadline: 14 April 2026.")
    assert result == []


def test_extract_procurement_stages_falls_back_to_prose_when_no_table_matches(monkeypatch):
    monkeypatch.setattr(procurement_timeline, "_extract_from_tables", lambda tables: [])

    def fake_prose(document_text):
        return [procurement_timeline.ExtractedStage(stage_name="ITT issued", stage_date="1 March 2026")]

    monkeypatch.setattr(procurement_timeline, "_extract_from_prose", fake_prose)

    result = procurement_timeline.extract_procurement_stages([], "some document text")
    assert len(result) == 1
    assert result[0].stage_name == "ITT issued"


def test_extract_procurement_stages_prefers_table_result_over_prose(monkeypatch):
    monkeypatch.setattr(
        procurement_timeline,
        "_extract_from_tables",
        lambda tables: [procurement_timeline.ExtractedStage(stage_name="From table", stage_date="1 March 2026")],
    )

    def fail_if_called(document_text):
        raise AssertionError("prose fallback should not run when a table already yielded stages")

    monkeypatch.setattr(procurement_timeline, "_extract_from_prose", fail_if_called)

    result = procurement_timeline.extract_procurement_stages(["a table"], "some document text")
    assert len(result) == 1
    assert result[0].stage_name == "From table"
