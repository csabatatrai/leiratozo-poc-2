"""FfmpegAudioDecoder teszt — valódi ffmpeg binárissal, valódi MP3-fájlon fut.
Ha az ffmpeg bináris nem elérhető, skip-elődik."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from leiratozo.domain.errors import DecodeError

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def decoder():
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg bináris nincs telepítve")
    from leiratozo.adapters.audio_decoder.ffmpeg_decoder import FfmpegAudioDecoder

    return FfmpegAudioDecoder()


@pytest.fixture
def sample_mp3_bytes(tmp_path) -> bytes:
    path = tmp_path / "tone.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-ar",
            "44100",
            "-y",
            str(path),
            "-loglevel",
            "error",
        ],
        check=True,
    )
    return path.read_bytes()


async def test_decode_mp3_produces_16k_mono_pcm(decoder, sample_mp3_bytes: bytes):
    audio = await decoder.decode(sample_mp3_bytes, filename_hint="tone.mp3")
    assert audio.sample_rate == 16000
    assert audio.duration_sec == pytest.approx(2.0, abs=0.05)
    assert len(audio.samples) > 0


async def test_decode_empty_bytes_raises_decode_error(decoder):
    with pytest.raises(DecodeError):
        await decoder.decode(b"")


async def test_decode_garbage_bytes_raises_decode_error(decoder):
    with pytest.raises(DecodeError):
        await decoder.decode(b"this is not an audio file at all" * 10)
