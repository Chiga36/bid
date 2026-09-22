"""Read-only view of the real, live prompt files each agent uses — no editing. Prompts aren't
DB-backed; this endpoint reads app/prompts/*.txt directly, so what the UI shows is always exactly
what the next agent call will actually send, not a cached or separately-maintained copy."""
from typing import List

from fastapi import APIRouter

from app.config import settings
from app.models import AgentPromptOut

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
