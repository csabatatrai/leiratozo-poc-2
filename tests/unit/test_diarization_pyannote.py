"""PyannoteDiarizer teszt — HF token nélkül futunk (a felhasználó explicit így
döntött), ezért itt a DEGRADÁLT utat igazoljuk élesen: a hiányzó/el nem
fogadott licenc miatt a betöltés nem omlik össze induláskor, csak
diarize_batch hívásakor dob ModelUnavailableError-t (docs/phase1-terv.md 1. és
10. szakasz)."""
from __future__ import annotations

import os

import pytest

from leiratozo.domain.errors import ModelUnavailableError, NotSupportedError
from leiratozo.domain.models import AudioBuffer

pytestmark = pytest.mark.asyncio


@pytest.fixture
def diarizer_class():
    try:
        import pyannote.audio  # noqa: F401
    except ImportError:
        pytest.skip("pyannote.audio nincs telepítve ebben a venv-ben")
    from leiratozo.adapters.diarization.pyannote import PyannoteDiarizer

    return PyannoteDiarizer


async def test_init_does_not_crash_without_hf_token(diarizer_class, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    diarizer = diarizer_class()  # NEM szabad kivételt dobnia
    assert diarizer.mode == "batch"
    assert diarizer.name == "pyannote"


async def test_diarize_batch_raises_model_unavailable_without_token(
    diarizer_class, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    diarizer = diarizer_class()
    audio = AudioBuffer(samples=b"\x00\x00" * 16000, sample_rate=16000, duration_sec=1.0)

    with pytest.raises(ModelUnavailableError):
        await diarizer.diarize_batch(audio, [])


async def test_diarize_live_not_supported(diarizer_class):
    diarizer = diarizer_class()
    with pytest.raises(NotSupportedError):
        await diarizer.diarize_live(None, None)
