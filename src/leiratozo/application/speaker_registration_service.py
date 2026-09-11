"""SpeakerRegistrationService — a réteg, ami SZIGORÚAN a diarizáció FÖLÖTT él,
és a nyers embeddingekből ismert/ismeretlen beszélő-identitást csinál (4-5.
kemény megkötés, docs/phase1-terv.md 6. szakasz). A diarizáció és az
embedding-extrakció semmit nem tud küszöbről, tárolásról vagy
ismert/ismeretlen döntésről — az a logika kizárólag itt él, önálló egység-
tesztekkel."""
from __future__ import annotations

import math

from leiratozo.domain.errors import ProfileNotFoundError
from leiratozo.domain.models import AudioBuffer, DiarizedSegment, Embedding, SpeakerMatch, SpeakerProfile
from leiratozo.ports.profile_store import ProfileStore
from leiratozo.ports.speaker_embedding import SpeakerEmbeddingEngine


def cosine_similarity(a: Embedding, b: Embedding) -> float:
    if a.dim != b.dim:
        raise ValueError(f"Embedding dimenzió-eltérés: {a.dim} vs {b.dim}")
    dot = sum(x * y for x, y in zip(a.vector, b.vector))
    norm_a = math.sqrt(sum(x * x for x in a.vector))
    norm_b = math.sqrt(sum(y * y for y in b.vector))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SpeakerRegistrationService:
    def __init__(
        self,
        embedding_engine: SpeakerEmbeddingEngine,
        profile_store: ProfileStore,
        *,
        similarity_threshold: float,
        unknown_label: str = "unknown",
    ) -> None:
        self._embedding_engine = embedding_engine
        self._profile_store = profile_store
        self._similarity_threshold = similarity_threshold
        self._unknown_label = unknown_label

    @property
    def embedding_engine(self) -> SpeakerEmbeddingEngine:
        return self._embedding_engine

    async def register(self, audio: AudioBuffer, display_name: str | None = None) -> SpeakerProfile:
        embedding = await self._embedding_engine.extract_embedding(audio)
        profile = SpeakerProfile(display_name=display_name)
        await self._profile_store.save(profile, embedding)
        return profile

    async def list_profiles(self) -> list[SpeakerProfile]:
        return await self._profile_store.list_profiles()

    async def delete(self, profile_id: str) -> None:
        deleted = await self._profile_store.delete(profile_id)
        if not deleted:
            raise ProfileNotFoundError(f"Nincs '{profile_id}' azonosítójú speaker-profil")

    async def match_segments(
        self, audio: AudioBuffer, segments: list[DiarizedSegment]
    ) -> dict[str, SpeakerMatch]:
        """segment_id -> SpeakerMatch. Küszöb alatt vagy üres regisztráció esetén
        SOSEM kényszerít találatot (4-5. kemény megkötés): ilyenkor `unknown`."""
        if not segments:
            return {}
        embeddings = await self._embedding_engine.extract_embeddings_for_segments(audio, segments)
        profiles = await self._profile_store.list_with_embeddings()
        results: dict[str, SpeakerMatch] = {}
        for segment in segments:
            emb = embeddings.get(segment.segment_id)
            if emb is None or not profiles:
                results[segment.segment_id] = SpeakerMatch(known_speaker_id=None, confidence=0.0)
                continue
            best_id: str | None = None
            best_score = 0.0
            for profile, profile_embedding in profiles:
                score = cosine_similarity(emb, profile_embedding)
                if score > best_score:
                    best_id, best_score = profile.profile_id, score
            if best_id is not None and best_score >= self._similarity_threshold:
                results[segment.segment_id] = SpeakerMatch(known_speaker_id=best_id, confidence=best_score)
            else:
                results[segment.segment_id] = SpeakerMatch(known_speaker_id=None, confidence=best_score)
        return results
