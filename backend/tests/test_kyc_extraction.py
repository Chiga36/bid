"""Unit tests for the Know Your Client agent's honesty gate — same pattern as the other
report-nothing-found agents (methodology, scoring matrix, procurement timeline): the agent must
return None rather than a fabricated profile when the model itself says nothing genuine was
found, and must pass through the result untouched when it did find something."""
from app.agents import kyc
from app.models import KYCExtraction


def test_returns_none_when_no_client_info_found(monkeypatch):
    def fake_call_structured(**kwargs):
        return KYCExtraction(client_info_found=False)

    monkeypatch.setattr(kyc.llm_client, "call_structured", fake_call_structured)

    assert kyc.extract_kyc("some scoring matrix with no client detail") is None


def test_returns_extraction_when_client_info_found(monkeypatch):
    def fake_call_structured(**kwargs):
        return KYCExtraction(
            client_info_found=True,
            client_summary="A regional NHS trust modernising its digital services.",
            key_facts=["Currently served by an incumbent supplier since 2019."],
            considerations=["Emphasise continuity of care during transition."],
        )

    monkeypatch.setattr(kyc.llm_client, "call_structured", fake_call_structured)

    result = kyc.extract_kyc("a context document with real client detail")
    assert result is not None
    assert result.client_summary == "A regional NHS trust modernising its digital services."
    assert result.key_facts == ["Currently served by an incumbent supplier since 2019."]
    assert result.considerations == ["Emphasise continuity of care during transition."]
