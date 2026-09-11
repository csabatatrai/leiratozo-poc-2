"""Determinisztikus fake ASR adapter tesztekhez és a skeleton pipeline-hoz —
nincs ML-függőség. Szóközönként szeleteli a rögzített szöveget, és egyenletesen
elosztott időbélyeget rendel hozzá."""
from __future__ import annotations

from typing import AsyncIterator

from leiratozo.domain.errors import NotSupportedError
from leiratozo.domain.models import (
    AudioBuffer,
    AudioChunk,
    EngineCapabilities,
    PartialOrFinalTranscript,
    TranscriptionHints,
    WordToken,
)


class FakeTranscriptionEngine:
    name = "fake-asr"
    version = "0.0.1"
    capabilities = EngineCapabilities(
        supports_word_timestamps=True, supports_native_streaming=False, languages="auto"
    )

    def __init__(self, *, fixed_text: str = "ez egy teszt mondat") -> None:
        self._fixed_text = fixed_text

    async def transcribe_batch(
        self, audio: AudioBuffer, *, language: str | None, hints: TranscriptionHints
    ) -> list[WordToken]:
        words = self._fixed_text.split()
        if not words:
            return []
        step = audio.duration_sec / len(words) if audio.duration_sec else 0.3
        tokens: list[WordToken] = []
        t = 0.0
        for w in words:
            tokens.append(WordToken(word=w, start=t, end=t + step * 0.8, confidence=0.95))
            t += step
        return tokens

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[PartialOrFinalTranscript]:
        raise NotSupportedError(f"{self.name} nem implementál natív streaminget")
        yield  # pragma: no cover - unreachable, az async generátor formát adja meg
