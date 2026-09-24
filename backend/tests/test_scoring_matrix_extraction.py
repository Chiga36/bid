"""Unit tests for the Scoring Matrix agent — the deterministic pre-filter (no LLM call) and the
verbatim guard on extracted descriptor_text (LLM call monkeypatched out), same pattern as
test_tender_requirements_extraction.py."""
from app.agents import scoring_matrix
from app.document_extraction import RawTable
from app.models import ExtractedScoringBand, ScoringMatrixExtractionResult


def test_looks_like_scoring_matrix_detects_signal_words():
    assert scoring_matrix._looks_like_scoring_matrix("Quality Criteria | Score Band\nGood | 75")


def test_looks_like_scoring_matrix_detects_percentage_bands():
    assert scoring_matrix._looks_like_scoring_matrix("0% | 25% | 50% | 75% | 100%")


def test_looks_like_scoring_matrix_rejects_unrelated_table():
    assert not scoring_matrix._looks_like_scoring_matrix("Contact | Email\nJohn Smith | john@example.com")


def test_extract_scoring_bands_skips_oversized_tables(monkeypatch):
    calls = []
    monkeypatch.setattr(scoring_matrix, "_extract_from_table", lambda t: calls.append(t) or [])
    huge_table = RawTable(rows=[["Quality Criteria", "Score"]] + [["row", "x"] for _ in range(100)])
    result = scoring_matrix.extract_scoring_bands([huge_table])
    assert result == []
    assert calls == []


def test_extract_scoring_bands_skips_tables_with_no_signal(monkeypatch):
    calls = []
    monkeypatch.setattr(scoring_matrix, "_extract_from_table", lambda t: calls.append(t) or [])
    unrelated_table = RawTable(rows=[["Contact", "Email"], ["John Smith", "john@example.com"]])
    result = scoring_matrix.extract_scoring_bands([unrelated_table])
    assert result == []
    assert calls == []


def test_non_verbatim_descriptor_is_dropped(monkeypatch):
    def fake_call_structured(**kwargs):
        return ScoringMatrixExtractionResult(
            is_scoring_matrix=True,
            bands=[ExtractedScoringBand(band_value=75, descriptor_text="This text was never in the table at all.")],
        )

    monkeypatch.setattr(scoring_matrix.llm_client, "call_structured", fake_call_structured)

    table = RawTable(rows=[["Score Band", "Quality Criteria"], ["75", "Good response with minor gaps."]])
    result = scoring_matrix._extract_from_table(table)
    assert result == []


def test_verbatim_descriptor_is_kept(monkeypatch):
    def fake_call_structured(**kwargs):
        return ScoringMatrixExtractionResult(
            is_scoring_matrix=True,
            bands=[ExtractedScoringBand(band_value=75, descriptor_text="Good response with minor gaps.")],
        )

    monkeypatch.setattr(scoring_matrix.llm_client, "call_structured", fake_call_structured)

    table = RawTable(rows=[["Score Band", "Quality Criteria"], ["75", "Good response with minor gaps."]])
    result = scoring_matrix._extract_from_table(table)
    assert len(result) == 1
    assert result[0].band_value == 75
    assert result[0].descriptor_text == "Good response with minor gaps."


def test_not_a_scoring_matrix_returns_no_bands(monkeypatch):
    def fake_call_structured(**kwargs):
        return ScoringMatrixExtractionResult(is_scoring_matrix=False, bands=[])

    monkeypatch.setattr(scoring_matrix.llm_client, "call_structured", fake_call_structured)

    table = RawTable(rows=[["Score", "Weighting"], ["Q1", "20%"]])
    result = scoring_matrix._extract_from_table(table)
    assert result == []


def test_extract_scoring_bands_returns_first_verified_table(monkeypatch):
    def fake_extract(table):
        # Only the second table (identifiable by its first cell) yields real bands.
        if table.rows[0][0] == "Quality Criteria":
            return [scoring_matrix.ExtractedBand(band_value=75, descriptor_text="Good.")]
        return []

    monkeypatch.setattr(scoring_matrix, "_extract_from_table", fake_extract)

    first_table = RawTable(rows=[["Score", "Weighting"], ["Q1", "20%"]])
    second_table = RawTable(rows=[["Quality Criteria", "Score"], ["Good.", "75"]])
    result = scoring_matrix.extract_scoring_bands([first_table, second_table])
    assert len(result) == 1
    assert result[0].descriptor_text == "Good."
