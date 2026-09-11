"""Valódi (nem mockolt) teszt a FasterWhisperEngine-re — a "tiny" modellel fut,
CPU-n. A tartalmi pontosság nem cél, csak hogy a csővezeték ténylegesen
lefusson és a port-kontraktusnak megfelelő formátumot adjon vissza."""
from __future__ import annotations

import struct

import pytest

from leiratozo.domain.errors import NotSupportedError
from leiratozo.domain.models import AudioBuffer, TranscriptionHints


def _tone_wav_bytes(duration_sec: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Egyszerű, licencmentes szintetikus hang (halk szinusz) PCM16 mono bájtokként."""
    import math

    n = int(duration_sec * sample_rate)
    samples = [int(2000 * math.sin(2 * math.pi * 220 * i / sample_rate)) for i in range(n)]
    return struct.pack(f"<{n}h", *samples)


@pytest.fixture(scope="module")
def engine():
    try:
        from leiratozo.adapters.asr.faster_whisper import FasterWhisperEngine
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"faster-whisper import sikertelen: {exc}")
    try:
        return FasterWhisperEngine(model_size="tiny", device="cpu", compute_type="int8")
    except Exception as exc:
        pytest.skip(f"faster-whisper 'tiny' modell nem tölthető be (hálózat?): {exc}")


async def test_transcribe_batch_runs_on_real_model_and_returns_word_tokens(engine):
    audio = AudioBuffer(
        samples=_tone_wav_bytes(2.0), sample_rate=16000, duration_sec=2.0, source_format="raw-pcm16"
    )
    tokens = await engine.transcribe_batch(audio, language="en", hints=TranscriptionHints())
    assert isinstance(tokens, list)
    for token in tokens:
        assert token.start >= 0.0
        assert token.end >= token.start
        assert 0.0 <= token.confidence <= 1.0


def test_capabilities_report_batch_native_not_streaming(engine):
    assert engine.capabilities.supports_native_streaming is False
    assert engine.capabilities.supports_word_timestamps is True


async def test_transcribe_stream_raises_not_supported(engine):
    async def _empty():
        return
        yield  # pragma: no cover

    with pytest.raises(NotSupportedError):
        async for _ in engine.transcribe_stream(_empty()):
            pass
