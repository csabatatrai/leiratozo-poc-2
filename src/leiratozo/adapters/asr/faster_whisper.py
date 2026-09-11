"""Stub adapter — a valódi faster-whisper integráció a 3. fázisban készül el
(docs/phase1-terv.md 11. szakasz). Import-biztos az opcionális `faster-whisper`
függőség nélkül is, hogy a plugin registry skeleton-fázisban feloldhassa;
példányosításkor NotImplementedError-t dob a 3. fázisig."""
from __future__ import annotations

from leiratozo.domain.models import EngineCapabilities


class FasterWhisperEngine:
    name = "faster-whisper"
    version = "unimplemented"
    capabilities = EngineCapabilities(
        supports_word_timestamps=True, supports_native_streaming=False, languages="auto"
    )

    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "FasterWhisperEngine 3. fázisos stub. Telepítsd az 'asr-faster-whisper' "
            "extrát és implementáld a transcribe_batch-et — ld. docs/phase1-terv.md 11. szakasz."
        )
