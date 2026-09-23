"""Unit tests for the Decomposition agent's LLM-calling half (extract_prose_elements) — the
verbatim guard on each sub-question's `text`, and that `elaboration`/`answer_guidance` (genuine
synthesis, not extraction) pass through untouched when `text` verifies. LLM call monkeypatched
out, same pattern as test_ingestion_extraction.py / test_tender_requirements_extraction.py."""
from app.agents import decomposition
from app.models import DecompositionExtraction, SubQuestionExtraction, Theme


def test_verbatim_sub_question_is_kept_with_elaboration_and_guidance_intact(monkeypatch):
    def fake_call_structured(**kwargs):
        return DecompositionExtraction(
            preamble=None,
            sub_questions=[
                SubQuestionExtraction(
                    text="describe your approach to risk management",
                    elaboration="The evaluator wants a named, tender-relevant risk methodology.",
                    answer_guidance="Open with the top risk, state likelihood/impact, name the mitigation and owner.",
                )
            ],
            theme=Theme.DELIVERY_METHODOLOGY,
        )

    monkeypatch.setattr(decomposition.llm_client, "call_structured", fake_call_structured)

    candidates = decomposition.extract_prose_elements(
        "Please describe your approach to risk management for this contract."
    )
    sub_questions = [c for c in candidates if c.kind == "sub_question"]
    assert len(sub_questions) == 1
    assert sub_questions[0].value_text == "describe your approach to risk management"
    assert sub_questions[0].elaboration == "The evaluator wants a named, tender-relevant risk methodology."
    assert sub_questions[0].answer_guidance.startswith("Open with the top risk")


def test_non_verbatim_sub_question_is_dropped_entirely(monkeypatch):
    def fake_call_structured(**kwargs):
        return DecompositionExtraction(
            preamble=None,
            sub_questions=[
                SubQuestionExtraction(
                    text="This sentence was never in the source question at all.",
                    elaboration="Some elaboration that should never reach the DB.",
                    answer_guidance="Some guidance that should never reach the DB.",
                )
            ],
            theme=Theme.DELIVERY_METHODOLOGY,
        )

    monkeypatch.setattr(decomposition.llm_client, "call_structured", fake_call_structured)

    candidates = decomposition.extract_prose_elements("Please describe your approach to risk management.")
    assert all(c.kind != "sub_question" for c in candidates)


def test_theme_is_always_included_as_a_candidate(monkeypatch):
    def fake_call_structured(**kwargs):
        return DecompositionExtraction(preamble=None, sub_questions=[], theme=Theme.TEAM_RESOURCING)

    monkeypatch.setattr(decomposition.llm_client, "call_structured", fake_call_structured)

    candidates = decomposition.extract_prose_elements("Describe your team.")
    theme_candidates = [c for c in candidates if c.kind == "theme"]
    assert len(theme_candidates) == 1
    assert theme_candidates[0].value_text == Theme.TEAM_RESOURCING.value
