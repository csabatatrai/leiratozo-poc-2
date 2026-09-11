"""Stub adapter — a valódi Resemblyzer (GE2E d-vector) integráció a 3. fázisban
készül el (docs/phase1-terv.md 11. szakasz). Architekturálisan eltér az
ECAPA-TDNN-től (x-vector) — ez adja a második embedding-adapter kontrasztját."""
from __future__ import annotations


class ResemblyzerEngine:
    name = "resemblyzer"
    version = "unimplemented"
    embedding_dim = 256

    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "ResemblyzerEngine 3. fázisos stub. Telepítsd az 'embedding-resemblyzer' "
            "extrát és implementáld az extract_embedding(_for_segments)-et — ld. "
            "docs/phase1-terv.md 11. szakasz."
        )
