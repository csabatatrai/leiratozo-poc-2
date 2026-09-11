"""Valódi Silero VAD adapter — a 6. kemény megkötés szerint kötelező
előfeldolgozó lépés minden más port elé (docs/phase1-terv.md). A modellt
`torch.hub`-on keresztül tölti be (nem igényel HF tokent, se külön pip
csomagot a `torch`-on felül, ld. pyproject.toml `vad-silero` extra)."""
from __future__ import annotations

from typing import Any

from leiratozo.domain.errors import ModelUnavailableError
from leiratozo.domain.models import AudioBuffer, VadSegment


def _pcm16_bytes_to_float_tensor(samples: bytes) -> Any:
    import array

    import torch

    ints = array.array("h")
    usable = len(samples) - (len(samples) % 2)
    ints.frombytes(samples[:usable])
    floats = [s / 32768.0 for s in ints]
    return torch.tensor(floats, dtype=torch.float32)


class SileroVad:
    name = "silero-vad"
    version = "unknown"

    def __init__(
        self,
        *,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100,
        repo: str = "snakers4/silero-vad",
        **_extra: Any,
    ) -> None:
        self._threshold = threshold
        self._min_speech_duration_ms = min_speech_duration_ms
        self._min_silence_duration_ms = min_silence_duration_ms

        try:
            import torch
        except ImportError as exc:
            raise ModelUnavailableError("torch csomag nincs telepítve (extra: vad-silero)") from exc

        type(self).version = getattr(torch, "__version__", "unknown")
        try:
            model, utils = torch.hub.load(repo_or_dir=repo, model="silero_vad", force_reload=False, trust_repo=True)
        except Exception as exc:
            raise ModelUnavailableError(f"Silero VAD modell nem tölthető be ({repo}): {exc}") from exc

        self._model = model
        self._get_speech_timestamps = utils[0]

    async def detect_speech(self, audio: AudioBuffer) -> list[VadSegment]:
        if audio.duration_sec <= 0:
            return []
        wav = _pcm16_bytes_to_float_tensor(audio.samples)
        timestamps = self._get_speech_timestamps(
            wav,
            self._model,
            sampling_rate=audio.sample_rate,
            threshold=self._threshold,
            min_speech_duration_ms=self._min_speech_duration_ms,
            min_silence_duration_ms=self._min_silence_duration_ms,
        )
        return [
            VadSegment(start=ts["start"] / audio.sample_rate, end=ts["end"] / audio.sample_rate)
            for ts in timestamps
        ]
