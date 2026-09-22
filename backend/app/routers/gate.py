"""The 'Top band and no findings?' decision gate from the workflow diagram. Ready to submit only
if the latest scoring run hit the top band, every locked element's latest completeness status is
'addressed', and no deterministic check that was actually run failed. Deterministic checks that
were never run don't block the gate — they simply weren't part of this evaluation, and that
omission is visible in the response's `reason` text rather than silently assumed passing.

`compute_gate` is pure and DB-free by design, so the decision logic is unit-testable against
mocked rows without a live database — the router below only does the fetching.
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException

from app.db import db_session
from app.models import GateOut

router = APIRouter(tags=["gate"])

_TOP_BAND = 100


def _latest_by_key(rows: List[Dict], key_field: str) -> Dict:
    latest = {}
    for row in rows:  # rows must be in ascending id order, so the last write per key wins
        latest[row[key_field]] = row
    return latest


def compute_gate(
    scoring_summary: Optional[Dict],
    completeness_rows: List[Dict],
    check_rows: List[Dict],
) -> GateOut:
    if scoring_summary is None:
        return GateOut(ready_to_submit=False, reason="No scoring run yet for this draft.")

    if not completeness_rows:
        return GateOut(ready_to_submit=False, reason="No completeness check run yet for this draft.")

    latest_completeness = _latest_by_key(completeness_rows, "element_id")
    unaddressed = [r for r in latest_completeness.values() if r["status"] != "addressed"]

    latest_checks = _latest_by_key(check_rows, "check_type")
    failed_checks = [r for r in latest_checks.values() if not r["passed"]]

    if scoring_summary["final_band"] < _TOP_BAND:
        return GateOut(
            ready_to_submit=False,
            reason=f"Scoring band is {scoring_summary['final_band']}, below the top band of {_TOP_BAND}.",
        )
    if unaddressed:
        return GateOut(
            ready_to_submit=False,
            reason=f"{len(unaddressed)} element(s) are not fully addressed: "
            + ", ".join(f"element {r['element_id']} ({r['status']})" for r in unaddressed),
        )
    if failed_checks:
        return GateOut(
            ready_to_submit=False,
            reason="Failed deterministic check(s): " + ", ".join(r["check_type"] for r in failed_checks),
        )

    checked_note = "" if check_rows else " (note: deterministic checks were never run for this draft)"
    return GateOut(
        ready_to_submit=True,
        reason="Top band achieved, all elements addressed, no failed deterministic checks." + checked_note,
    )


@router.get("/drafts/{draft_id}/gate", response_model=GateOut)
def get_gate(draft_id: int):
    with db_session() as conn:
        draft = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")

        scoring_summary_row = conn.execute(
            "SELECT * FROM scoring_summary WHERE draft_id = ? ORDER BY id DESC LIMIT 1", (draft_id,)
        ).fetchone()
        completeness_rows = conn.execute(
            "SELECT * FROM completeness_results WHERE draft_id = ? ORDER BY id", (draft_id,)
        ).fetchall()
        check_rows = conn.execute(
            "SELECT * FROM deterministic_check_results WHERE draft_id = ? ORDER BY id", (draft_id,)
        ).fetchall()

    return compute_gate(
        dict(scoring_summary_row) if scoring_summary_row else None,
        [dict(r) for r in completeness_rows],
        [dict(r) for r in check_rows],
    )
