"""Unit tests for the Scoring agent's computed (not self-reported) confidence calculation."""
from app.agents.scoring import compute_confidence


def test_identical_bands_are_high_confidence():
    assert compute_confidence([50, 50, 50]) == "high"


def test_one_band_step_spread_is_high_confidence():
    assert compute_confidence([50, 50, 75]) == "high"


def test_two_band_step_spread_is_low_confidence():
    assert compute_confidence([25, 50, 75]) == "low"


def test_wide_spread_is_low_confidence():
    assert compute_confidence([0, 50, 100]) == "low"


def test_spread_threshold_override_from_business_rules():
    # A tender that configures a stricter (0-step) threshold should demand exact agreement.
    assert compute_confidence([50, 50, 75], spread_threshold_steps=0) == "low"
    # A tender that configures a looser (2-step) threshold should tolerate a wider spread.
    assert compute_confidence([25, 50, 75], spread_threshold_steps=2) == "high"
