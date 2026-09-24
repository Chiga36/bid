"""Unit tests for the Completeness agent's guardrails: the quote-substring check and the
empty-draft short-circuit in run_completeness (the only case that skips a model call — see
app/agents/completeness.py's docstring for why the old keyword-overlap pre-filter was removed).
The Azure OpenAI call itself is monkeypatched out — these tests prove the *wrapper* logic catches
a fabricated quote, not that the model behaves well."""
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


def test_empty_draft_short_circuits_every_element_without_a_model_call(monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("the model should never be called for an empty draft")

    monkeypatch.setattr(completeness.llm_client, "call_structured", fail_if_called)

    results = completeness.run_completeness(
        draft_text="   ",
        elements=[{"id": 1, "value_text": "Describe your cyber security incident response procedure."}],
    )
    assert len(results) == 1
    assert results[0].status == "missing"
    assert results[0].verified is True


def test_non_empty_draft_always_goes_to_the_model_even_with_no_word_overlap(monkeypatch):
    # This is the regression case: a draft that addresses the requirement using entirely
    # different vocabulary ("measures" vs "metrics") must still reach the model, not get
    # silently marked "missing" by a keyword heuristic.
    def fake_call_structured(**kwargs):
        return CompletenessCheckResult(
            status="addressed",
            quote="We track a comprehensive set of measures across delivery performance.",
            rationale="The draft addresses this via its measures framework, using different wording for the same concept.",
        )

    monkeypatch.setattr(completeness.llm_client, "call_structured", fake_call_structured)

    results = completeness.run_completeness(
        draft_text="We track a comprehensive set of measures across delivery performance.",
        elements=[{"id": 1, "value_text": "The KPIs and metrics you will apply."}],
    )
    assert len(results) == 1
    assert results[0].status == "addressed"
