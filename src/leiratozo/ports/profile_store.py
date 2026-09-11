"""ProfileStore port — titkosított CRUD biometrikus speaker-profilokra (GDPR,
5. kemény megkötés). A konkrét adaptereknek titkosítaniuk KELL az embedding-
vektort (és a display_name-et) nyugalmi állapotban."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from leiratozo.domain.models import Embedding, SpeakerProfile


@runtime_checkable
class ProfileStore(Protocol):
    async def save(self, profile: SpeakerProfile, embedding: Embedding) -> None: ...
    async def list_profiles(self) -> list[SpeakerProfile]: ...
    async def list_with_embeddings(self) -> list[tuple[SpeakerProfile, Embedding]]: ...
    async def delete(self, profile_id: str) -> bool:
        """True, ha volt mit törölni. Hard delete, nem soft — ld. 6. szakasz."""
        ...
