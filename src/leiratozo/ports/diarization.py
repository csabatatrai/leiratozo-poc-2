"""DiarizationEngine port. Ld. docs/phase1-terv.md 2.2. és 5. szakasz.

A batch és az élő diarizáció EXPLICIT különböző minőségi szint, nem ugyanaz az
algoritmus két módban futtatva — egy adapter csak a `mode`-jának megfelelő
metódust (diarize_batch VAGY diarize_live) implementálja.
"""
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from leiratozo.domain.models import AudioBuffer, AudioChunk, DiarizedSegment, LiveDiarizationState, VadSegment


@runtime_checkable
class DiarizationEngine(Protocol):
    name: str
    version: str
    mode: Literal["batch", "live_approx"]

    async def diarize_batch(
        self, audio: AudioBuffer, vad_segments: list[VadSegment]
    ) -> list[DiarizedSegment]:
        """Teljes audio-n dolgozó, pontos, offline diarizáció."""
        ...

    async def diarize_live(
        self, audio_chunk: AudioChunk, state: LiveDiarizationState
    ) -> tuple[list[DiarizedSegment], LiveDiarizationState]:
        """Stateful, best-effort. A `state` a SessionStore-on keresztül
        perzisztálódik, hogy reconnect után folytatható legyen a klaszterezés."""
        ...
