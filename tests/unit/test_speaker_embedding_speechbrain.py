"""Valódi SpeechBrain ECAPA-TDNN adapter teszt — tényleges modellel fut (nyilvános,
HF token nem szükséges). Hálózat/letöltés hiányában skip-elődik."""
from __future__ import annotations

import struct
import math

import pytest

from leiratozo.domain.models import AudioBuffer

pytestmark = pytest.mark.asyncio


def _tone_pcm16(freq: float, duration_sec: float, sample_rate: int = 16000) -> bytes:
    n = int(duration_sec * sample_rate)
    samples = [int(3000 * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(n)]
    return struct.pack(f"<{n}h", *samples)


@pytest.fixture(scope="module")
def engine():
    try:
        from leiratozo.adapters.speaker_embedding.speechbrain_ecapa import SpeechBrainEcapaEngine
    except ImportError:
        pytest.skip("speechbrain nincs telepítve ebben a venv-ben")
    try:
        return SpeechBrainEcapaEngine()
    except Exception as exc:  # pragma: no cover - hálózat/letöltés hiánya
        pytest.skip(f"SpeechBrain ECAPA modell nem tölthető be (hálózat?): {exc}")


async def test_extract_embedding_returns_192_dim_vector(engine):
    audio = AudioBuffer(samples=_tone_pcm16(220.0, 1.5), sample_rate=16000, duration_sec=1.5)
    embedding = await engine.extract_embedding(audio)
    assert embedding.dim == 192
    assert len(embedding.vector) == 192
    assert any(v != 0.0 for v in embedding.vector)


async def test_different_audio_gives_different_embeddings(engine):
    audio_a = AudioBuffer(samples=_tone_pcm16(220.0, 1.5), sample_rate=16000, duration_sec=1.5)
    audio_b = AudioBuffer(samples=_tone_pcm16(880.0, 1.5), sample_rate=16000, duration_sec=1.5)

    emb_a = await engine.extract_embedding(audio_a)
    emb_b = await engine.extract_embedding(audio_b)

    assert emb_a.vector != emb_b.vector
