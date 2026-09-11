"""SpeakerEmbeddingEngine port. Ld. docs/phase1-terv.md 2.3. és 4. kemény megkötés.

Ez a port szándékosan NEM tud semmit küszöbről, tárolásról, vagy
ismert/ismeretlen döntésről — az a SpeakerRegistrationService (application
réteg) felelőssége, elkülönítve a diarizációtól és az embedding-extrakciótól.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from leiratozo.domain.models import AudioBuffer, DiarizedSegment, Embedding


@runtime_checkable
class SpeakerEmbeddingEngine(Protocol):
    name: str
    version: str
    embedding_dim: int

    async def extract_embedding(self, audio: AudioBuffer) -> Embedding:
        """Regisztrációs mintából egy profil-embedding kinyerése."""
        ...

    async def extract_embeddings_for_segments(
        self, audio: AudioBuffer, segments: list[DiarizedSegment]
    ) -> dict[str, Embedding]:
        """segment_id -> embedding, diarizált szegmensekre."""
        ...
