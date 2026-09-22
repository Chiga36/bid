"""Unit tests for the Completeness agent's guardrails: the quote-substring check and the
lexical pre-filter. The Azure OpenAI call itself is monkeypatched out — these tests prove the
*wrapper* logic catches a fabricated quote, not that the model behaves well."""
from app.agents import completeness
from app.models import CompletenessCheckResult


def test_quote_verification_downgrades_fabricated_quote(monkeypatch):
    def fake_call_structured(**kwargs):
        return CompletenessCheckResult(
            status="addressed",
            quote="This sentence does not appear in the draft at all.",
            rationale="looks good",
        )

    monkeypatch.setattr(completeness.llm_client, "call_structured", fake_call_structured)

    result = completeness.check_element(
        element_id=1,
        element_value_text="Describe your mobilisation approach.",
        draft_text="Our mobilisation plan covers Day 1 readiness and transition.",
    )

    assert result.status == "unverified"
    assert result.verified is False


def test_quote_verification_accepts_real_quote(monkeypatch):
    def fake_call_structured(**kwargs):
        return CompletenessCheckResult(
            status="addressed",
            quote="Our mobilisation plan covers Day 1 readiness",
            rationale="explained clearly",
        )

    monkeypatch.setattr(completeness.llm_client, "call_structured", fake_call_structured)

    result = completeness.check_element(
        element_id=2,
        element_value_text="Describe your mobilisation approach.",
        draft_text="Our mobilisation plan covers Day 1 readiness and transition.",
    )

    assert result.status == "addressed"
    assert result.verified is True


def test_missing_with_empty_quote_is_verified_trivially(monkeypatch):
    def fake_call_structured(**kwargs):
        return CompletenessCheckResult(status="missing", quote="", rationale="not mentioned")

    monkeypatch.setattr(completeness.llm_client, "call_structured", fake_call_structured)

    result = completeness.check_element(
        element_id=3, element_value_text="Describe your exit plan.", draft_text="This draft covers pricing only."
    )

    assert result.status == "missing"
    assert result.verified is True


def test_lexical_prefilter_flags_trivially_missing():
    element_text = "Describe your cyber security incident response procedure."
    draft_text = "This draft only discusses pricing and commercial terms."
    assert completeness.lexical_prefilter(element_text, draft_text) is False


def test_lexical_prefilter_passes_when_overlap_exists():
    element_text = "Describe your cyber security incident response procedure."
    draft_text = "Our incident response procedure follows ISO 27001 security controls."
    assert completeness.lexical_prefilter(element_text, draft_text) is True
