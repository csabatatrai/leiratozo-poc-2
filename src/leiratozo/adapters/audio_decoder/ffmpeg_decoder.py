"""Stub adapter — a valódi ffmpeg-alapú (pl. `av` csomag) dekódolás a 3.
fázisban készül el (docs/phase1-terv.md 11. szakasz). Cél: wav/mp3/m4a/ogg/flac
-> 16kHz mono PCM AudioBuffer."""
from __future__ import annotations


class FfmpegAudioDecoder:
    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "FfmpegAudioDecoder 3. fázisos stub. Telepítsd az 'audio' extrát és implementáld "
            "a decode-ot — ld. docs/phase1-terv.md 11. szakasz."
        )
