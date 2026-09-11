"""Stub adapter — a valódi NVIDIA NeMo MSDD (Multi-scale Diarization Decoder)
integráció a 3. fázisban készül el (docs/phase1-terv.md 11. szakasz). Apache-2.0
licencű, nem igényel HF gated-repo elfogadást (szemben a pyannote-tal) —
architekturálisan eltérő második batch-diarizációs adapter."""
from __future__ import annotations


class NemoMsddDiarizer:
    name = "nemo-msdd"
    version = "unimplemented"
    mode = "batch"

    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "NemoMsddDiarizer 3. fázisos stub. Telepítsd a 'diarization-nemo' extrát és "
            "implementáld a diarize_batch-et — ld. docs/phase1-terv.md 11. szakasz."
        )
