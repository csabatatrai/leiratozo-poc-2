"""Fake VAD: az egész audio-t egyetlen beszéd-szegmensnek tekinti."""
from __future__ import annotations

from leiratozo.domain.models import AudioBuffer, VadSegment


class FakeVad:
    name = "fake-vad"
    version = "0.0.1"

    def __init__(self, *, threshold: float = 0.5) -> None:
        self._threshold = threshold

    async def detect_speech(self, audio: AudioBuffer) -> list[VadSegment]:
        if audio.duration_sec <= 0:
            return []
        return [VadSegment(start=0.0, end=audio.duration_sec)]
