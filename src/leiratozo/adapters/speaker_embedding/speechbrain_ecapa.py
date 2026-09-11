"""Stub adapter — a valódi SpeechBrain ECAPA-TDNN (x-vector) integráció a
3. fázisban készül el (docs/phase1-terv.md 11. szakasz)."""
from __future__ import annotations


class SpeechBrainEcapaEngine:
    name = "speechbrain-ecapa"
    version = "unimplemented"
    embedding_dim = 192

    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "SpeechBrainEcapaEngine 3. fázisos stub. Telepítsd az 'embedding-speechbrain' "
            "extrát és implementáld az extract_embedding(_for_segments)-et — ld. "
            "docs/phase1-terv.md 11. szakasz."
        )
