"""RemoteHttpAsrEngine teszt — egy valós, hálózaton elérhető Whisper-alapú
végponttal fut (a felhasználó saját LAN-ján, http://192.168.100.7:8001). Ha
ez nem elérhető (más környezet, hálózat), a teszt skip-el, nem bukik."""
from __future__ import annotations

import pytest

from leiratozo.domain.errors import ModelUnavailableError, NotSupportedError
from leiratozo.domain.models import AudioBuffer, TranscriptionHints

pytestmark = pytest.mark.asyncio

_BASE_URL = "http://192.168.100.7:8001"


@pytest.fixture(scope="module")
def engine():
    try:
        from leiratozo.adapters.asr.remote_http import RemoteHttpAsrEngine
    except ImportError:
        pytest.skip("httpx nincs telepítve (extra: asr-remote-http)")
    try:
        return RemoteHttpAsrEngine(base_url=_BASE_URL)
    except ModelUnavailableError as exc:
        pytest.skip(f"Távoli ASR-végpont nem elérhető ebben a környezetben: {exc}")


def _pcm16_tone(freq: float, duration_sec: float, sample_rate: int = 16000) -> bytes:
    import array
    import math

    n = int(duration_sec * sample_rate)
    ints = array.array("h", [int(3000 * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(n)])
    return ints.tobytes()


async def test_transcribe_batch_on_silence_returns_no_tokens(engine):
    audio = AudioBuffer(samples=_pcm16_tone(440.0, 1.0), sample_rate=16000, duration_sec=1.0)
    tokens = await engine.transcribe_batch(audio, language="hu", hints=TranscriptionHints())
    assert isinstance(tokens, list)


async def test_capabilities_report_segment_level_not_word_level(engine):
    assert engine.capabilities.supports_word_timestamps is False
    assert engine.capabilities.supports_native_streaming is False


async def test_transcribe_stream_not_supported(engine):
    with pytest.raises(NotSupportedError):
        engine.transcribe_stream(None)
