"""Unit test for the Benchmark harness's band comparison — no Azure OpenAI needed, since this
only tests the arithmetic, not the Completeness/Scoring agents themselves (those already have
their own test coverage)."""
from app.routers.benchmark import compute_band_delta


def test_exact_match_is_zero_delta():
    assert compute_band_delta(predicted_band=75, known_band=75) == 0


def test_overprediction_is_positive_delta():
    assert compute_band_delta(predicted_band=100, known_band=50) == 50


def test_underprediction_is_negative_delta():
    assert compute_band_delta(predicted_band=25, known_band=75) == -50
