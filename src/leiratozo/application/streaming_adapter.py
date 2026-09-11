"""SlidingWindowStreamingAdapter — egy batch-only TranscriptionEngine-t
közelít élő streammé átfedő ablakokkal + merge-dzsel. Ez EXPLICIT közelítés
(docs/phase1-terv.md 4. szakasz), nem valódi kauzális streaming, és csak akkor
kerül bevetésre, ha a configolt ASR adapter `capabilities.supports_native_streaming`
mezője False."""
from __future__ import annotations

from typing import AsyncIterator

from leiratozo.domain.models import (
    AudioBuffer,
    AudioChunk,
    PartialOrFinalTranscript,
    TranscriptSegment,
    TranscriptionHints,
    WordToken,
)
from leiratozo.ports.asr import TranscriptionEngine


class SlidingWindowStreamingAdapter:
    """Bufferelt, átfedő ablakokban hívja a becsomagolt engine transcribe_batch-ét,
    és a már nem változó (stabil) szó-fejrészt `is_final=True`-ként, a még
    bizonytalan farkot `is_final=False`-ként emittálja."""

    def __init__(
        self,
        engine: TranscriptionEngine,
        *,
        window_sec: float = 3.0,
        overlap_sec: float = 0.75,
        language: str | None = None,
    ) -> None:
        if engine.capabilities.supports_native_streaming:
            raise ValueError(
                f"{engine.name} natívan támogat streaminget; a "
                "SlidingWindowStreamingAdapter-be csomagolása feleslegesen adná hozzá "
                "a közelítés késleltetését, előny nélkül."
            )
        self._engine = engine
        self._window_sec = window_sec
        self._overlap_sec = overlap_sec
        self._language = language
        self._sample_rate: int | None = None
        self._buffer = bytearray()
        self._emitted_word_count = 0
        self._session_id: str | None = None

    @property
    def name(self) -> str:
        return f"sliding-window({self._engine.name})"

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[PartialOrFinalTranscript]:
        async for chunk in audio_chunks:
            self._session_id = chunk.session_id
            self._sample_rate = chunk.sample_rate
            self._buffer.extend(chunk.samples)
            window_bytes = int(self._window_sec * chunk.sample_rate * 2)  # 16 bites PCM
            if len(self._buffer) < window_bytes:
                continue
            async for event in self._flush_window(is_final_window=False):
                yield event
        async for event in self._flush_window(is_final_window=True):
            yield event

    async def _flush_window(self, *, is_final_window: bool) -> AsyncIterator[PartialOrFinalTranscript]:
        """Minden ablakon két réteget különböztet meg: a `confirmed` fej-rész már
        nem fog megváltozni (a következő ablak sem írja felül) -> `is_final=True`;
        a `tentative` farok-rész a folyó overlap miatt még módosulhat a következő
        flush-nál -> `is_final=False`. Ez adja a valódi partial/final
        megkülönböztetést (2. kemény megkötés), NEM az, hogy melyik flush a
        stream-lezáró — a záró flush csupán azzal a különbséggel jár, hogy nincs
        több adat, tehát MINDEN megmaradt szó azonnal confirmed."""
        if not self._buffer or self._sample_rate is None:
            return
        audio = AudioBuffer(
            samples=bytes(self._buffer),
            sample_rate=self._sample_rate,
            duration_sec=len(self._buffer) / (self._sample_rate * 2),
        )
        words = await self._engine.transcribe_batch(
            audio, language=self._language, hints=TranscriptionHints(language=self._language)
        )
        new_words = words[self._emitted_word_count :]
        if not new_words:
            return

        if is_final_window:
            confirmed, tentative = new_words, []
        else:
            overlap_word_count = max(1, len(new_words) // 4)
            split = max(0, len(new_words) - overlap_word_count)
            confirmed, tentative = new_words[:split], new_words[split:]

        if confirmed:
            self._emitted_word_count += len(confirmed)
            yield self._make_event(confirmed, is_final=True)
        if tentative:
            yield self._make_event(tentative, is_final=False)

        if is_final_window:
            self._buffer = bytearray()
        else:
            overlap_bytes = int(self._overlap_sec * self._sample_rate * 2)
            self._buffer = self._buffer[-overlap_bytes:] if overlap_bytes else bytearray()

    def _make_event(self, words: list[WordToken], *, is_final: bool) -> PartialOrFinalTranscript:
        text = " ".join(w.word for w in words)
        kind = "final" if is_final else "partial"
        segment = TranscriptSegment(
            segment_id=f"live-{self._session_id}-{kind}-{self._emitted_word_count}",
            start=words[0].start,
            end=words[-1].end,
            text=text,
            speaker_label="S?",  # diarizáció ezen a rétegen még nincs hozzárendelve
            is_final=is_final,
            words=words,
        )
        return PartialOrFinalTranscript(session_id=self._session_id or "", segment=segment, is_final=is_final)
