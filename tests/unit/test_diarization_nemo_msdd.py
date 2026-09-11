"""NemoMsddDiarizer teszt — Apache-2.0, nyilvános modellek (nem igényel HF
tokent). Hálózat/telepítés hiányában skip-elődik; a NeMo toolkit nagy és lassú
telepítésű, ezért ez a teszt csak a diarizáció-specifikus (.venv-diar) venv-ben
fut le ténylegesen (docs/phase1-terv.md 11. szakasz)."""
from __future__ import annotations

import pytest

from leiratozo.domain.errors import NotSupportedError
from leiratozo.domain.models import AudioBuffer

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def diarizer():
    try:
        import nemo  # noqa: F401
    except ImportError:
        pytest.skip("nemo_toolkit nincs telepítve ebben a venv-ben")
    from leiratozo.adapters.diarization.nemo_msdd import NemoMsddDiarizer

    try:
        return NemoMsddDiarizer()
    except Exception as exc:  # pragma: no cover - hálózat/config letöltés hiánya
        pytest.skip(f"NeMo MSDD referencia-config nem tölthető be (hálózat?): {exc}")


async def test_diarize_batch_runs_and_returns_segments(diarizer):
    # ~4s szintetikus, csendes+zajos audio — a cél a pipeline futásának
    # igazolása, nem a diarizáció pontossága.
    audio = AudioBuffer(samples=b"\x10\x00" * 16000 * 4, sample_rate=16000, duration_sec=4.0)
    segments = await diarizer.diarize_batch(audio, [])
    assert isinstance(segments, list)
    for seg in segments:
        assert seg.speaker_label.startswith("S")
        assert seg.end > seg.start


async def test_diarize_live_not_supported(diarizer):
    with pytest.raises(NotSupportedError):
        await diarizer.diarize_live(None, None)
