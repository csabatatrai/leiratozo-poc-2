"""Fake decoder: a nyers bájtokat már PCM-ként kezeli, ffmpeg hívása nélkül —
tesztekhez és a skeleton API demózásához."""
from __future__ import annotations

from leiratozo.domain.errors import DecodeError
from leiratozo.domain.models import AudioBuffer


class FakeAudioDecoder:
    def __init__(self, *, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate

    async def decode(self, raw_bytes: bytes, *, filename_hint: str | None = None) -> AudioBuffer:
        if not raw_bytes:
            raise DecodeError("Üres audio-payload")
        duration_sec = len(raw_bytes) / (self._sample_rate * 2)
        return AudioBuffer(
            samples=raw_bytes, sample_rate=self._sample_rate, duration_sec=duration_sec, source_format=filename_hint
        )
