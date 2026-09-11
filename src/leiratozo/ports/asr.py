"""TranscriptionEngine port (ASR). Ld. docs/phase1-terv.md 2.1. és 4. szakasz.

Ha `capabilities.supports_native_streaming` False, `transcribe_stream`
NotSupportedError-t dob, és az alkalmazásréteg egy SlidingWindowStreamingAdapter
dekorátorral (application/streaming_adapter.py) közelíti — ez explicit,
dokumentált közelítés, nem valódi kauzális streaming.
"""
from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from leiratozo.domain.models import (
    AudioBuffer,
    AudioChunk,
    EngineCapabilities,
    PartialOrFinalTranscript,
    TranscriptionHints,
    WordToken,
)


@runtime_checkable
class TranscriptionEngine(Protocol):
    name: str
    version: str
    capabilities: EngineCapabilities

    async def transcribe_batch(
        self,
        audio: AudioBuffer,
        *,
        language: str | None,
        hints: TranscriptionHints,
    ) -> list[WordToken]:
        """Teljes audio-n dolgozó, szó-szintű időbélyeget adó batch felismerés."""
        ...

    def transcribe_stream(
        self, audio_chunks: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[PartialOrFinalTranscript]:
        """Csak akkor kötelező implementálni, ha capabilities.supports_native_streaming
        True; egyébként NotSupportedError-t kell dobnia."""
        ...
