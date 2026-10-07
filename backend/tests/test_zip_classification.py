"""Unit tests for zip_classification.classify_filename() — pure regex matching, no I/O."""
from app.zip_classification import classify_filename


def test_strategy_keywords():
    assert classify_filename("Tender Evaluation Criteria.docx") == "strategy"
    assert classify_filename("competition_overview.pdf") == "strategy"
    assert classify_filename("Instructions to Tenderers.docx") == "strategy"


def test_questionnaire_sr_number_pattern():
    assert classify_filename("SR2_Award_Questionnaire.xlsx") == "competition_info"
    assert classify_filename("SR-14 response form.xlsx") == "competition_info"
    assert classify_filename("sr 3 questionnaire.xlsx") == "competition_info"


def test_sr_pattern_does_not_match_unrelated_words():
    # "user" contains "sr" but not as a standalone "SR<number>" token.
    assert classify_filename("user_manual.pdf") is None


def test_context_keywords():
    assert classify_filename("Client Context Document.docx") == "context"
    assert classify_filename("Organisation Profile.pdf") == "context"


def test_credentials_keywords():
    assert classify_filename("Team CVs.pdf") == "credentials"
    assert classify_filename("Case Study - Riverside Council.docx") == "credentials"


def test_standards_keywords():
    assert classify_filename("ISO 9001 Certificate.pdf") == "standards"


def test_propositions_keywords():
    assert classify_filename("Pricing Proposition.pdf") == "propositions"


def test_high_scoring_responses_keywords():
    assert classify_filename("Previous Winning Bid.docx") == "high_scoring_responses"


def test_no_match_returns_none():
    assert classify_filename("random_notes.txt") is None


def test_first_matching_category_wins_on_priority_order():
    # Contains both a strategy keyword ("evaluation") and an SR-number pattern — strategy is
    # earlier in CATEGORY_KEYWORD_RULES, so it wins.
    assert classify_filename("SR2 evaluation notes.docx") == "strategy"


def test_case_insensitive():
    assert classify_filename("ISO CERTIFICATE.PDF") == "standards"
