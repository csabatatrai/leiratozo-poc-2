"""Aligner port — szó-szintű időbélyeg illesztése a diarizációs szegmensekkel
(7. kemény megkötés). Ld. docs/phase1-terv.md 3. szakasz: `passthrough`, ha az
ASR natívan ad szóidőbélyeget; `forced_alignment` fallback egyébként (3. fázis)."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from leiratozo.domain.models import DiarizedSegment, TranscriptSegment, WordToken


@runtime_checkable
class Aligner(Protocol):
    name: str

    async def align(
        self, words: list[WordToken], diarized_segments: list[DiarizedSegment]
    ) -> list[TranscriptSegment]: ...
