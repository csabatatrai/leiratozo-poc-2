"""A SlidingWindowStreamingAdapter (batch->streaming közelítés) tesztjei —
docs/phase1-terv.md 4. szakasz."""
from __future__ import annotations

import pytest

from leiratozo.adapters.asr.fake import FakeTranscriptionEngine
from leiratozo.application.streaming_adapter import SlidingWindowStreamingAdapter
from leiratozo.domain.models import AudioChunk, EngineCapabilities


def test_wrapping_a_native_streaming_engine_raises():
    class NativeStreamingFake(FakeTranscriptionEngine):
        capabilities = EngineCapabilities(supports_word_timestamps=True, supports_native_streaming=True)

    with pytest.raises(ValueError):
        SlidingWindowStreamingAdapter(NativeStreamingFake())


async def _audio_chunks(session_id: str, n: int, sample_rate: int = 16000, chunk_ms: int = 500):
    n_bytes = int(sample_rate * (chunk_ms / 1000) * 2)
    for i in range(n):
        yield AudioChunk(samples=b"\x00" * n_bytes, sample_rate=sample_rate, sequence=i, session_id=session_id)


async def test_emits_events_with_is_final_flag_set():
    engine = FakeTranscriptionEngine(fixed_text="egy ketto harom negy ot hat het nyolc kilenc tiz")
    adapter = SlidingWindowStreamingAdapter(engine, window_sec=1.0, overlap_sec=0.25)

    events = [event async for event in adapter.transcribe_stream(_audio_chunks("sess-1", n=6))]

    assert events, "legalább egy eseményt kell emittálnia"
    assert all(isinstance(e.is_final, bool) for e in events)
    assert events[-1].is_final is True  # az utolsó, lezáró flush mindig final
    assert all(e.session_id == "sess-1" for e in events)


async def test_no_events_for_empty_chunk_stream():
    engine = FakeTranscriptionEngine()
    adapter = SlidingWindowStreamingAdapter(engine)

    async def empty():
        return
        yield  # pragma: no cover

    events = [event async for event in adapter.transcribe_stream(empty())]
    assert events == []
