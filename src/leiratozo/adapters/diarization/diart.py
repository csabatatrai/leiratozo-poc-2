"""Stub adapter — a valódi `diart` (élő diarizáció) integráció a 3. fázisban
készül el (docs/phase1-terv.md 11. szakasz). mode=live_approx: best-effort,
session előrehaladtával stabilizálódó klaszterezés (5. szakasz)."""
from __future__ import annotations


class DiartLiveDiarizer:
    name = "diart"
    version = "unimplemented"
    mode = "live_approx"

    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "DiartLiveDiarizer 3. fázisos stub. Telepítsd a 'diarization-diart' extrát és "
            "implementáld a diarize_live-ot — ld. docs/phase1-terv.md 11. szakasz."
        )
