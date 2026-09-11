"""Health/readiness — docs/phase1-terv.md 9. szakasz."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict:
    """2. fázis (skeleton): a readiness mindig 'ready'-t jelez, mihelyt az app
    elindult, mert a ServiceContainer eagerly példányosítja az adaptereket. A
    3. fázisban ez port-szintű `degraded` állapotot fog tükrözni (hiányzó
    licenc/token/GPU esetén) — ld. docs/phase1-terv.md 1. szakasz."""
    return {"status": "ready"}
