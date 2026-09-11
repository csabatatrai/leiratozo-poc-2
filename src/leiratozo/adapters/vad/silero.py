"""Stub adapter — a valódi Silero VAD integráció a 3. fázisban készül el
(docs/phase1-terv.md 11. szakasz). VAD kötelező előfeldolgozó lépés (6. kemény
megkötés)."""
from __future__ import annotations


class SileroVad:
    name = "silero-vad"
    version = "unimplemented"

    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "SileroVad 3. fázisos stub. Telepítsd a 'vad-silero' extrát és implementáld a "
            "detect_speech-et — ld. docs/phase1-terv.md 11. szakasz."
        )
