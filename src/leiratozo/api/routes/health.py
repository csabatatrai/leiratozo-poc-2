"""Health/readiness — docs/phase1-terv.md 9. szakasz."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict:
    """A ServiceContainer eagerly próbálja betölteni a modelleket induláskor;
    egy hiányzó HF token/licenc/eszköz nem dönti el a szolgáltatást, csak az
    érintett portot jelöli `degraded`-nek (docs/phase1-terv.md 1. és 10.
    szakasz) — ez a végpont ezt teszi láthatóvá, nem csak egy statikus "ready"-t
    ad vissza."""
    services = request.app.state.services
    degraded = services.degraded_ports()
    return {"status": "ready" if not degraded else "degraded", "degraded_ports": degraded}
