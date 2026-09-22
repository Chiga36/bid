"""Scoring agent.

Band descriptors always come verbatim from this tender's own `scoring_bands` rows — the model
matches evidence to an existing band, it never invents or rewords one. Three independent passes
run against a shuffled descriptor order each time, so they're not the same deterministic call
three times over. (The original design also varied temperature per pass; the configured Azure
deployment turned out to be a reasoning-tier model that rejects any non-default temperature —
see llm_client.call_structured — so shuffled order is now the sole decorrelation lever. Weaker
than temperature+order together, but still a real, non-fabricated signal, and the moderator pass
below exists precisely to catch the cases where that weaker decorrelation lets real disagreement
show through.) Confidence is computed in code from how much the three passes agree — never
self-reported by the model — and only feeds into whether a fourth, moderator pass (shown all
three prior outputs, to reconcile rather than re-score from scratch) is worth running at all.
"""
import random
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional

from app import llm_client
from app.models import ScoringModeratorResult, ScoringPassResult

AGENT_NAME = "scoring"


@dataclass
class ScoringBandRow:
    band_value: int
    descriptor_text: str


@dataclass
class ScoringPassRow:
    pass_number: str  # "1" | "2" | "3" | "moderator"
    band_value: int
    rationale: str
    temperature: Optional[float]


@dataclass
class ScoringSummaryRow:
    final_band: int
    confidence: str  # "high" | "low"
    used_moderator: bool
    runs: List[ScoringPassRow]


def _format_band_descriptors(bands: List[ScoringBandRow], shuffle_seed: int) -> str:
    ordered = list(bands)
    random.Random(shuffle_seed).shuffle(ordered)
    return "\n".join(f"- Band {b.band_value}: {b.descriptor_text}" for b in ordered)


def run_scoring_pass(draft_text: str, bands: List[ScoringBandRow], shuffle_seed: int) -> ScoringPassResult:
    band_descriptors = _format_band_descriptors(bands, shuffle_seed)
    return llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="scoring_pass_v1.txt",
        variables={"band_descriptors": band_descriptors, "draft_text": draft_text},
        response_model=ScoringPassResult,
    )


def compute_confidence(band_values: List[int], spread_threshold_steps: int = 1) -> str:
    """Pure arithmetic, no model call. Spread measured in band steps (25 points apart = 1 step).
    A spread at or below `spread_threshold_steps` counts as high confidence; anything wider is
    low and should trigger the moderator pass. The default (1) matches the original design;
    routers may override it per tender from the `business_rules` table
    (rule_key='scoring_confidence_spread_steps') without changing this function's behaviour for
    any caller that doesn't pass it."""
    spread_steps = (max(band_values) - min(band_values)) // 25
    return "high" if spread_steps <= spread_threshold_steps else "low"


def run_moderator(
    draft_text: str, bands: List[ScoringBandRow], passes: List[ScoringPassResult]
) -> ScoringModeratorResult:
    band_descriptors = _format_band_descriptors(bands, shuffle_seed=0)
    variables = {"band_descriptors": band_descriptors, "draft_text": draft_text}
    for i, p in enumerate(passes, start=1):
        variables[f"pass_{i}_band"] = p.band_value
        variables[f"pass_{i}_rationale"] = p.rationale
    return llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="scoring_moderator_v1.txt",
        variables=variables,
        response_model=ScoringModeratorResult,
    )


def run_scoring(draft_text: str, bands: List[ScoringBandRow], spread_threshold_steps: int = 1) -> ScoringSummaryRow:
    pass_results: List[ScoringPassResult] = [run_scoring_pass(draft_text, bands, shuffle_seed=i) for i in range(3)]
    runs = [
        ScoringPassRow(
            pass_number=str(i + 1),
            band_value=result.band_value,
            rationale=result.rationale,
            temperature=None,  # not sent to the model — see module docstring
        )
        for i, result in enumerate(pass_results)
    ]

    confidence = compute_confidence([r.band_value for r in pass_results], spread_threshold_steps)
    used_moderator = confidence == "low"

    if used_moderator:
        moderator_result = run_moderator(draft_text, bands, pass_results)
        runs.append(
            ScoringPassRow(
                pass_number="moderator",
                band_value=moderator_result.band_value,
                rationale=moderator_result.rationale,
                temperature=None,
            )
        )
        final_band = moderator_result.band_value
    else:
        final_band = Counter(r.band_value for r in pass_results).most_common(1)[0][0]

    return ScoringSummaryRow(
        final_band=final_band,
        confidence=confidence,
        used_moderator=used_moderator,
        runs=runs,
    )
