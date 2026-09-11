"""Determinisztikus fake embedding adapter: audio/szegmens-tartalmat egy kis,
fix méretű vektorba hash-el, hogy a koszinusz-hasonlóság alapú matching-logika
ML-függőség nélkül tesztelhető legyen."""
from __future__ import annotations

import hashlib

from leiratozo.domain.models import AudioBuffer, DiarizedSegment, Embedding

_DIM = 8


def _vector_from_bytes(data: bytes) -> Embedding:
    digest = hashlib.sha256(data).digest()[:_DIM]
    vector = tuple((b / 255.0) * 2 - 1 for b in digest)
    return Embedding(vector=vector, dim=_DIM)


class FakeSpeakerEmbeddingEngine:
    name = "fake-embedding"
    version = "0.0.1"
    embedding_dim = _DIM

    async def extract_embedding(self, audio: AudioBuffer) -> Embedding:
        return _vector_from_bytes(audio.samples[:64] or b"silence")

    async def extract_embeddings_for_segments(
        self, audio: AudioBuffer, segments: list[DiarizedSegment]
    ) -> dict[str, Embedding]:
        return {seg.segment_id: _vector_from_bytes(seg.speaker_label.encode()) for seg in segments}
