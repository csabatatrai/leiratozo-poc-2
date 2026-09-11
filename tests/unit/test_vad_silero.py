"""SileroVad teszt — valódi torch.hub modellel. Hálózat/torch hiányában
skip-elődik. A cél: a modell lefusson és jól formázott VadSegment listát
adjon vissza (nem a pontosság mérése szintetikus hangon)."""
from __future__ import annotations

import pytest

from leiratozo.domain.models import AudioBuffer, VadSegment

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def vad():
    try:
        from leiratozo.adapters.vad.silero import SileroVad
    except ImportError:
        pytest.skip("torch nincs telepítve ebben a venv-ben")
    try:
        return SileroVad()
    except Exception as exc:  # pragma: no cover - hálózat/letöltés hiánya
        pytest.skip(f"Silero VAD modell nem tölthető be (hálózat?): {exc}")


async def test_detect_speech_on_silence_returns_empty(vad):
    audio = AudioBuffer(samples=b"\x00\x00" * 16000 * 2, sample_rate=16000, duration_sec=2.0)
    segments = await vad.detect_speech(audio)
    assert segments == []


async def test_detect_speech_returns_well_formed_segments_type(vad):
    # Szintetikus szinuszhullám nem "beszéd", de a hívásnak hibamentesen,
    # helyes típussal kell visszatérnie (a pontosság nem ennek a tesztnek a célja).
    import array
    import math

    n = 16000 * 2
    ints = array.array("h", [int(3000 * math.sin(2 * math.pi * 200 * i / 16000)) for i in range(n)])
    audio = AudioBuffer(samples=ints.tobytes(), sample_rate=16000, duration_sec=2.0)

    segments = await vad.detect_speech(audio)
    assert isinstance(segments, list)
    for seg in segments:
        assert isinstance(seg, VadSegment)
        assert seg.end > seg.start


async def test_detect_speech_on_empty_duration_returns_empty(vad):
    audio = AudioBuffer(samples=b"", sample_rate=16000, duration_sec=0.0)
    assert await vad.detect_speech(audio) == []
