import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import init_db
from app.routers import (
    benchmark,
    business_rules,
    checks,
    clarifications,
    completeness,
    decomposition,
    drafts,
    evidence,
    evidence_library,
    gate,
    prompts,
    recommendations,
    scoring,
    tenders,
    theme_review,
    zip_ingestion,
)

app = FastAPI(
    title="Bid Co-Author API",
    description="Backend-first POC: tenders, decomposition, completeness, and scoring agents.",
)

app.add_middleware(
    CORSMiddleware,
    # Any port on localhost/127.0.0.1 or a private LAN IP, not a hardcoded host:port — Vite
    # auto-increments past 5173 when it's taken, and the frontend's own API base URL now derives
    # from window.location.hostname (see frontend/src/api/http.ts) so it works when opened from
    # another device's LAN IP too. A hardcoded allow_origins list would make every request fail
    # the moment either of those varies, not just warn. Still scoped to private/local ranges
    # only (localhost, 127.0.0.0/8, 10.0.0.0/8, 172.16-31.0.0/12, 192.168.0.0/16) — never a
    # public origin.
    allow_origin_regex=(
        r"^http://(localhost"
        r"|127\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
        r"|192\.168\.\d{1,3}\.\d{1,3}"
        r"):\d+$"
    ),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_size_to_bytes(size_str: str) -> int:
    match = re.match(r"^\s*(\d+)\s*([kKmMgG]?[bB])?\s*$", size_str)
    if not match:
        return 200 * 1024 * 1024  # sensible default if the env var is malformed
    value = int(match.group(1))
    unit = (match.group(2) or "b").lower()
    multiplier = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}.get(unit, 1)
    return value * multiplier


_MAX_PAYLOAD_BYTES = _parse_size_to_bytes(settings.payload_max_size)


@app.middleware("http")
async def enforce_max_payload_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_PAYLOAD_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Payload too large"})
    return await call_next(request)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(tenders.router)
app.include_router(decomposition.router)
app.include_router(drafts.router)
app.include_router(completeness.router)
app.include_router(scoring.router)
app.include_router(checks.router)
app.include_router(gate.router)
app.include_router(clarifications.router)
app.include_router(business_rules.router)
app.include_router(evidence.router)
app.include_router(evidence_library.router)
app.include_router(prompts.router)
app.include_router(recommendations.router)
app.include_router(benchmark.router)
app.include_router(theme_review.router)
app.include_router(zip_ingestion.router)


@app.get("/health")
def health():
    return {"status": "ok"}
