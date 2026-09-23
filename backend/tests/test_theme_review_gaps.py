"""Unit tests for the Theme Review agent's one verbatim guard — GapEntry.answer_excerpt is
verified as a genuine substring of the draft after the call and blanked (never dropped) if it
doesn't check out, exactly like Completeness verifies its own quotes. LLM call monkeypatched out,
same pattern as the other agents' verbatim-guard tests."""
from app.agents import theme_review
from app.models import GapEntry, PrioritisedImprovement, Theme, ThemeReviewResult


def _fake_result(gaps):
    return ThemeReviewResult(
        theme_fit="Fits.",
        evaluator_summary="Summary.",
        strengths=["Strength one."],
        gaps=gaps,
        prioritised_improvements=[PrioritisedImprovement(priority="High", description="Fix it.")],
        suggested_wording=["Try this instead."],
        evidence_required=[],
        improved_answer_plan="Plan.",
        score_compliance=3,
        score_practicality=3,
        score_evidence=3,
        score_client_specificity=3,
        score_evaluator_confidence=3,
    )


def test_fabricated_answer_excerpt_is_blanked_but_gap_is_kept(monkeypatch):
    draft_text = "We will mobilise the team within two weeks of contract award."

    def fake_call_structured(**kwargs):
        return _fake_result(
            [
                GapEntry(
                    sub_question="Describe your mobilisation approach.",
                    answer_excerpt="This sentence was never in the draft at all.",
                    gap="No named risks or owners are given for mobilisation.",
                )
            ]
        )

    monkeypatch.setattr(theme_review.llm_client, "call_structured", fake_call_structured)

    result = theme_review.run_theme_review(
        theme=Theme.DELIVERY_METHODOLOGY,
        question_text="Describe your mobilisation approach.",
        evaluation_criteria="",
        word_limit="",
        draft_text=draft_text,
        evidence_context="",
        sub_questions=["Describe your mobilisation approach."],
    )

    assert len(result.gaps) == 1
    assert result.gaps[0].answer_excerpt == ""
    assert result.gaps[0].gap == "No named risks or owners are given for mobilisation."
    assert result.gaps[0].sub_question == "Describe your mobilisation approach."


def test_verbatim_answer_excerpt_is_kept(monkeypatch):
    draft_text = "We will mobilise the team within two weeks of contract award."

    def fake_call_structured(**kwargs):
        return _fake_result(
            [
                GapEntry(
                    sub_question="Describe your mobilisation approach.",
                    answer_excerpt="We will mobilise the team within two weeks of contract award.",
                    gap="No named risks or owners are given for mobilisation.",
                )
            ]
        )

    monkeypatch.setattr(theme_review.llm_client, "call_structured", fake_call_structured)

    result = theme_review.run_theme_review(
        theme=Theme.DELIVERY_METHODOLOGY,
        question_text="Describe your mobilisation approach.",
        evaluation_criteria="",
        word_limit="",
        draft_text=draft_text,
        evidence_context="",
        sub_questions=["Describe your mobilisation approach."],
    )

    assert result.gaps[0].answer_excerpt == draft_text


def test_sub_questions_block_formats_as_numbered_list():
    block = theme_review._format_sub_questions_block(["First ask.", "Second ask."])
    assert block == "1. First ask.\n2. Second ask."


def test_empty_sub_questions_gives_fallback_text():
    block = theme_review._format_sub_questions_block([])
    assert "none available" in block
