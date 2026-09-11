"""Stub adapter — a valódi pyannote.audio integráció a 3. fázisban készül el
(docs/phase1-terv.md 11. szakasz). HF gated-repo licenc-elfogadást és tokent
igényel (10. kemény megkötés); hiányuk esetén a 3. fázisban ModelUnavailableError-t
kell dobnia, nem a szolgáltatást elvinnie."""
from __future__ import annotations


class PyannoteDiarizer:
    name = "pyannote"
    version = "unimplemented"
    mode = "batch"

    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "PyannoteDiarizer 3. fázisos stub. Telepítsd a 'diarization-pyannote' extrát, "
            "állítsd be a HF tokent (security.huggingface_token_env), és implementáld a "
            "diarize_batch-et — ld. docs/phase1-terv.md 6. és 11. szakasz."
        )
