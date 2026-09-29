"""Read-only view of the real, live default prompt files each agent uses, plus per-tender skill
customisation (see app/llm_client.py's call_structured() for how an override actually takes
effect). Defaults aren't DB-backed — GET /agent-prompts reads app/prompts/*.txt directly, so what
it shows is always exactly what a tender with no customisation will actually get, not a cached or
separately-maintained copy. Overrides ARE DB-backed (see the prompt_overrides table) and never
touch the file on disk — every other tender is completely unaffected by one tender's edit."""
from typing import List

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.db import db_session
from app.models import AgentPromptOut, TenderPromptIn, TenderPromptOut

router = APIRouter(tags=["prompts"])

# Filename prefix -> human-readable agent name.
_AGENT_LABELS = {
    "decomposition": "Decomposition",
    "completeness": "Completeness",
    "scoring": "Scoring",
    "recommendation": "Recommendation",
}


def _infer_agent_label(filename: str) -> str:
    prefix = filename.split("_", 1)[0]
    return _AGENT_LABELS.get(prefix, prefix.capitalize())


@router.get("/agent-prompts", response_model=List[AgentPromptOut])
def list_agent_prompts():
    prompts = []
    for path in sorted(settings.prompts_dir.glob("*.txt")):
        prompts.append(
            AgentPromptOut(
                agent=_infer_agent_label(path.name),
                filename=path.name,
                content=path.read_text(encoding="utf-8"),
            )
        )
    return prompts


def _default_prompt_text(prompt_file: str) -> str:
    path = settings.prompts_dir / prompt_file
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"No prompt file named '{prompt_file}'.")
    return path.read_text(encoding="utf-8")


def _require_tender(tender_id: int) -> None:
    with db_session() as conn:
        tender = conn.execute("SELECT id FROM tenders WHERE id = ?", (tender_id,)).fetchone()
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")


@router.get("/tenders/{tender_id}/prompt-overrides/{prompt_file}", response_model=TenderPromptOut)
def get_tender_prompt(tender_id: int, prompt_file: str):
    _require_tender(tender_id)
    with db_session() as conn:
        override = conn.execute(
            "SELECT content_text FROM prompt_overrides WHERE tender_id = ? AND prompt_file = ?",
            (tender_id, prompt_file),
        ).fetchone()
    if override is not None:
        return TenderPromptOut(prompt_file=prompt_file, content_text=override["content_text"], is_override=True)
    return TenderPromptOut(prompt_file=prompt_file, content_text=_default_prompt_text(prompt_file), is_override=False)


@router.put("/tenders/{tender_id}/prompt-overrides/{prompt_file}", response_model=TenderPromptOut)
def save_tender_prompt(tender_id: int, prompt_file: str, body: TenderPromptIn):
    """Upserts this tender's own customisation of `prompt_file` — every other tender's calls to
    this same prompt_file are completely unaffected, and llm_client picks this up on the very
    next call (no caching, no restart needed — see call_structured's tender_id resolution)."""
    _require_tender(tender_id)
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO prompt_overrides (tender_id, prompt_file, content_text)
            VALUES (?, ?, ?)
            ON CONFLICT(tender_id, prompt_file)
            DO UPDATE SET content_text = excluded.content_text, updated_at = datetime('now')
            """,
            (tender_id, prompt_file, body.content_text),
        )
    return TenderPromptOut(prompt_file=prompt_file, content_text=body.content_text, is_override=True)


@router.delete("/tenders/{tender_id}/prompt-overrides/{prompt_file}", response_model=TenderPromptOut)
def reset_tender_prompt(tender_id: int, prompt_file: str):
    """Reverts this tender back to the shared default — deletes the override row outright rather
    than keeping any history; there's no undo beyond re-typing the customisation."""
    _require_tender(tender_id)
    with db_session() as conn:
        conn.execute(
            "DELETE FROM prompt_overrides WHERE tender_id = ? AND prompt_file = ?", (tender_id, prompt_file)
        )
    return TenderPromptOut(prompt_file=prompt_file, content_text=_default_prompt_text(prompt_file), is_override=False)
