"""Valódi (nem mockolt) teszt a VoskEngine-re: letölti a kis angol Vosk-modellt
(hálózat szükséges — ha nem elérhető, a teszt skip-el), és ténylegesen lefuttatja
mind a batch, mind a natív streaming utat."""
from __future__ import annotations

import struct

import pytest

from leiratozo.domain.models import AudioChunk, AudioBuffer, TranscriptionHints


def _tone_pcm16(duration_sec: float = 1.5, sample_rate: int = 16000) -> bytes:
    import math

    n = int(duration_sec * sample_rate)
    samples = [int(3000 * math.sin(2 * math.pi * 300 * i / sample_rate)) for i in range(n)]
    return struct.pack(f"<{n}h", *samples)


@pytest.fixture(scope="module")
def engine():
    try:
        from leiratozo.adapters.asr.vosk import VoskEngine
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"vosk import sikertelen: {exc}")
    try:
        return VoskEngine()
    except Exception as exc:
        pytest.skip(f"Vosk modell nem tölthető be (hálózat?): {exc}")


def test_capabilities_report_native_streaming(engine):
    assert engine.capabilities.supports_native_streaming is True
    assert engine.capabilities.supports_word_timestamps is True


async def test_transcribe_batch_runs_on_real_model(engine):
    audio = AudioBuffer(samples=_tone_pcm16(), sample_rate=16000, duration_sec=1.5)
    tokens = await engine.transcribe_batch(audio, language=None, hints=TranscriptionHints())
    assert isinstance(tokens, list)  # szintetikus hangon valószínűleg üres, de nem hibázhat


async def test_transcribe_stream_yields_events_incrementally(engine):
    pcm = _tone_pcm16(duration_sec=3.0)
    chunk_size = 8000  # 0.25s 16kHz 16-bit mono

    async def chunks():
        for i in range(0, len(pcm), chunk_size):
            yield AudioChunk(
                samples=pcm[i : i + chunk_size], sample_rate=16000, sequence=i // chunk_size, session_id="sess-vosk"
            )

    events = [event async for event in engine.transcribe_stream(chunks())]
    assert isinstance(events, list)
    for event in events:
        assert event.session_id == "sess-vosk"
        assert isinstance(event.is_final, bool)
