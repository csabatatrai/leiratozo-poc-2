"""Stub adapter — a valódi Vosk integráció a 3. fázisban készül el (docs/phase1-terv.md
11. szakasz). Ez az egyetlen ASR adapter, aminek capabilities.supports_native_streaming
True lesz (valódi, kauzális streaming, Kaldi-alapú)."""
from __future__ import annotations

from leiratozo.domain.models import EngineCapabilities


class VoskEngine:
    name = "vosk"
    version = "unimplemented"
    capabilities = EngineCapabilities(
        supports_word_timestamps=True, supports_native_streaming=True, languages="auto"
    )

    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "VoskEngine 3. fázisos stub. Telepítsd az 'asr-vosk' extrát és implementáld "
            "a transcribe_batch/transcribe_stream-et — ld. docs/phase1-terv.md 11. szakasz."
        )
