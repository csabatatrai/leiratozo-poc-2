"""Valódi ffmpeg-alapú AudioDecoder: tetszőleges bemeneti formátumot (wav/mp3/
m4a/ogg/flac/...) egységes 16kHz mono 16-bit PCM AudioBuffer-ré normalizál.

A rendszer `ffmpeg` binárisát hívja subprocessben (NEM PyAV-kötést) — ez a
Docker runtime image-ben már amúgy is telepítve van (ld. Dockerfile), és
elkerüli egy külön natív Python-binding verzió-összeférhetőségi kockázatát
ugyanazért az eredményért."""
from __future__ import annotations

import asyncio
import shutil
from typing import Any

from leiratozo.domain.errors import DecodeError
from leiratozo.domain.models import AudioBuffer

_TARGET_SAMPLE_RATE = 16000


class FfmpegAudioDecoder:
    def __init__(self, *, ffmpeg_binary: str = "ffmpeg", **_extra: Any) -> None:
        if shutil.which(ffmpeg_binary) is None:
            raise DecodeError(f"'{ffmpeg_binary}' bináris nem található a PATH-on")
        self._ffmpeg_binary = ffmpeg_binary

    async def decode(self, raw_bytes: bytes, *, filename_hint: str | None = None) -> AudioBuffer:
        if not raw_bytes:
            raise DecodeError("Üres audio-payload")

        proc = await asyncio.create_subprocess_exec(
            self._ffmpeg_binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "-",
            "-f",
            "s16le",
            "-ar",
            str(_TARGET_SAMPLE_RATE),
            "-ac",
            "1",
            "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(input=raw_bytes)
        if proc.returncode != 0 or not stdout:
            raise DecodeError(
                f"ffmpeg dekódolás sikertelen ({filename_hint or 'ismeretlen fájl'}): "
                f"{stderr.decode(errors='replace')[:500]}"
            )

        duration_sec = len(stdout) / (_TARGET_SAMPLE_RATE * 2)
        return AudioBuffer(
            samples=stdout,
            sample_rate=_TARGET_SAMPLE_RATE,
            duration_sec=duration_sec,
            source_format=filename_hint,
        )
