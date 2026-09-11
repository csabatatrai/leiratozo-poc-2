"""DiartLiveDiarizer teszt. Ebben a munkamenetben a `diart` csomag telepítése
két különböző módon is valódi környezeti akadályba futott (ld.
adapters/diarization/diart.py modul docstring: host Python 3.14 + gcc hiánya,
illetve egy tiszta konténerben torchaudio/pyannote verzió-inkompatibilitás) —
ezért ez a teszt itt várhatóan skip-elődik, de a diart telepíthető (kompatibilis
verziókombinációjú) környezetben élesen lefut."""
from __future__ import annotations

import pytest

from leiratozo.domain.errors import ModelUnavailableError, NotSupportedError
from leiratozo.domain.models import AudioChunk, LiveDiarizationState

pytestmark = pytest.mark.asyncio


@pytest.fixture
def diarizer_class():
    try:
        import diart  # noqa: F401
    except ImportError:
        pytest.skip("diart nincs telepítve (vagy inkompatibilis a többi telepített csomaggal) ebben a venv-ben")
    from leiratozo.adapters.diarization.diart import DiartLiveDiarizer

    return DiartLiveDiarizer


async def test_init_does_not_crash(diarizer_class):
    diarizer = diarizer_class()
    assert diarizer.mode == "live_approx"
    assert diarizer.name == "diart"


async def test_diarize_batch_not_supported(diarizer_class):
    diarizer = diarizer_class()
    with pytest.raises(NotSupportedError):
        await diarizer.diarize_batch(None, [])


async def test_diarize_live_runs_or_reports_model_unavailable(diarizer_class):
    diarizer = diarizer_class()
    chunk = AudioChunk(samples=b"\x00\x00" * 1600, sample_rate=16000, sequence=0, session_id="sess-1")
    state = LiveDiarizationState(session_id="sess-1")
    try:
        segments, new_state = await diarizer.diarize_live(chunk, state)
        assert isinstance(segments, list)
        assert new_state.session_id == "sess-1"
    except ModelUnavailableError:
        pytest.skip("diart mögötti modell nem tölthető be ebben a környezetben (token/licenc)")
