"""Unit test for the Tender Requirements agent's verbatim-verification guard (LLM call
monkeypatched out, same pattern as test_ingestion_extraction.py) — chunking itself is shared
and already covered by test_text_chunking.py."""
from app.agents import tender_requirements
from app.models import TenderRequirement, TenderRequirementExtractionResult


def test_extract_from_chunk_drops_non_verbatim_requirement(monkeypatch):
    def fake_call_structured(**kwargs):
        return TenderRequirementExtractionResult(
            requirements=[
                TenderRequirement(
                    category="mandatory_requirement",
                    requirement_text="This sentence was never in the source chunk at all.",
                    strength="mandatory",
                )
            ]
        )

    monkeypatch.setattr(tender_requirements.llm_client, "call_structured", fake_call_structured)

    result = tender_requirements._extract_from_chunk("Bidders must hold ISO 27001 certification at the time of submission.")
    assert result == []


def test_extract_from_chunk_accepts_verbatim_requirement(monkeypatch):
    def fake_call_structured(**kwargs):
        return TenderRequirementExtractionResult(
            requirements=[
                TenderRequirement(
                    category="mandatory_requirement",
                    requirement_text="Bidders must hold ISO 27001 certification",
                    strength="mandatory",
                )
            ]
        )

    monkeypatch.setattr(tender_requirements.llm_client, "call_structured", fake_call_structured)

    result = tender_requirements._extract_from_chunk("Bidders must hold ISO 27001 certification at the time of submission.")
    assert len(result) == 1
    assert result[0].category == "mandatory_requirement"
    assert result[0].strength == "mandatory"
