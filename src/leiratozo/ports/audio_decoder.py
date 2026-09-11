"""AudioDecoder port — tetszőleges bemeneti formátum (wav/mp3/m4a/ogg/flac)
egységes 16kHz mono PCM AudioBuffer-ré normalizálása."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from leiratozo.domain.models import AudioBuffer


@runtime_checkable
class AudioDecoder(Protocol):
    async def decode(self, raw_bytes: bytes, *, filename_hint: str | None = None) -> AudioBuffer:
        """DecodeError-t dob dekódolhatatlan bemenetre."""
        ...
