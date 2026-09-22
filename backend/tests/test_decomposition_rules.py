"""Unit tests for the deterministic (non-LLM) half of the Decomposition agent.
No Azure OpenAI credentials needed — this only exercises plain code."""
from app.agents.decomposition import extract_limits_and_weights
from app.document_extraction import RawTable


def test_word_limit_extraction():
    section_text = "Responses must be a maximum of 500 words and should address all criteria."
    candidates = extract_limits_and_weights("Mobilisation approach", section_text, [])
    word_limits = [c for c in candidates if c.kind == "word_limit"]
    assert len(word_limits) == 1
    assert word_limits[0].value_text == "500"
    assert word_limits[0].extraction_method == "rule"


def test_diagram_limit_extraction():
    section_text = "You may include up to 2 diagrams to support your answer."
    candidates = extract_limits_and_weights("Delivery model", section_text, [])
    diagram_limits = [c for c in candidates if c.kind == "diagram_limit"]
    assert len(diagram_limits) == 1
    assert diagram_limits[0].value_text == "2"


def test_no_limit_found_returns_no_candidate_for_that_kind():
    section_text = "This section has no explicit word or diagram limit stated."
    candidates = extract_limits_and_weights("Some question", section_text, [])
    assert all(c.kind not in ("word_limit", "diagram_limit") for c in candidates)


def test_weight_extraction_from_table():
    table = RawTable(
        rows=[
            ["Question", "Weighting %"],
            ["Mobilisation approach", "20"],
            ["Delivery model", "15"],
        ]
    )
    candidates = extract_limits_and_weights("Mobilisation approach", "no limits here", [table])
    weights = [c for c in candidates if c.kind == "weight"]
    assert len(weights) == 1
    assert weights[0].value_text == "20"


def test_weight_extraction_ignores_table_without_weight_column():
    table = RawTable(rows=[["Question", "Notes"], ["Mobilisation approach", "see appendix"]])
    candidates = extract_limits_and_weights("Mobilisation approach", "no limits here", [table])
    assert all(c.kind != "weight" for c in candidates)


def test_word_count_label_phrasing_is_recognised():
    # Real tender phrasing distinct from "maximum 500 words" — the number follows a "word count:"
    # label rather than sitting right after "maximum".
    section_text = "Explain your approach. Maximum word count: 600 (diagrams are excluded)."
    candidates = extract_limits_and_weights("Understanding of Objectives", section_text, [])
    word_limits = [c for c in candidates if c.kind == "word_limit"]
    assert len(word_limits) == 1
    assert word_limits[0].value_text == "600"


def test_inline_percentage_weight_is_extracted_without_a_table():
    # Real tender phrasing: weighting stated inline in the question's own title, no separate
    # scoring-matrix table to cross-reference at all.
    section_text = "Understanding of Objectives and Risks (6%) Tenderers should outline..."
    candidates = extract_limits_and_weights("Understanding of Objectives", section_text, [])
    weights = [c for c in candidates if c.kind == "weight"]
    assert len(weights) == 1
    assert weights[0].value_text == "6"


def test_inline_weight_takes_priority_over_table_lookup():
    # If a question states its own weighting inline, that should win even when a (possibly
    # stale or mismatched) table is also present.
    table = RawTable(rows=[["Question", "Weighting %"], ["Understanding of Objectives", "99"]])
    section_text = "Understanding of Objectives and Risks (6%) Tenderers should outline..."
    candidates = extract_limits_and_weights("Understanding of Objectives", section_text, [table])
    weights = [c for c in candidates if c.kind == "weight"]
    assert len(weights) == 1
    assert weights[0].value_text == "6"
