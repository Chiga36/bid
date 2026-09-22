from typing import List

from fastapi import APIRouter, HTTPException

from app.db import db_session
from app.models import BusinessRuleIn, BusinessRuleOut

router = APIRouter(tags=["business-rules"])


@router.post("/tenders/{tender_id}/business-rules", response_model=BusinessRuleOut)
def set_business_rule(tender_id: int, rule: BusinessRuleIn):
    with db_session() as conn:
        tender = conn.execute("SELECT id FROM tenders WHERE id = ?", (tender_id,)).fetchone()
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")
        conn.execute(
            """
            INSERT INTO business_rules (tender_id, rule_key, rule_value, description)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tender_id, rule_key) DO UPDATE SET rule_value = excluded.rule_value, description = excluded.description
            """,
            (tender_id, rule.rule_key, rule.rule_value, rule.description),
        )
        row = conn.execute(
            "SELECT * FROM business_rules WHERE tender_id = ? AND rule_key = ?", (tender_id, rule.rule_key)
        ).fetchone()
    return dict(row)


@router.get("/tenders/{tender_id}/business-rules", response_model=List[BusinessRuleOut])
def list_business_rules(tender_id: int):
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM business_rules WHERE tender_id = ? ORDER BY id", (tender_id,)).fetchall()
    return [dict(r) for r in rows]
