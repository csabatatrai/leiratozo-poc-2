"""VoiceActivityDetector port — kötelező előfeldolgozó lépés (6. kemény megkötés)."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from leiratozo.domain.models import AudioBuffer, VadSegment


@runtime_checkable
class VoiceActivityDetector(Protocol):
    name: str
    version: str

    async def detect_speech(self, audio: AudioBuffer) -> list[VadSegment]: ...
