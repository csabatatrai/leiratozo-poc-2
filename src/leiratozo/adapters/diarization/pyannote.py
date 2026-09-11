"""Valódi pyannote.audio batch diarizációs adapter (mode="batch"). HF gated-repo
licenc-elfogadást és tokent igényel (10. kemény megkötés, docs/phase1-terv.md 6.
és 11. szakasz) — hiányzó/érvénytelen token esetén NEM omlik össze induláskor: a
betöltési kísérlet hibáját elraktározza, és csak diarize_batch hívásakor dob
ModelUnavailableError-t. A ServiceContainer ezt degradált portként kezeli (ld.
registry/plugin_registry.py: instantiate_or_degrade/DegradedAdapter) — a
csomag-hiányt (ImportError) viszont a plugin registry már fail-fast elkapja
azelőtt, hogy ide eljutnánk, ezért az itt catch-elt ImportError csak védelmi
dupla biztosítás."""
from __future__ import annotations

from typing import Any

from leiratozo.domain.errors import ModelUnavailableError, NotSupportedError
from leiratozo.domain.models import AudioBuffer, AudioChunk, DiarizedSegment, LiveDiarizationState, VadSegment, new_id


def _pcm16_to_tensor(samples: bytes) -> Any:
    import array

    import torch

    ints = array.array("h")
    usable = len(samples) - (len(samples) % 2)
    ints.frombytes(samples[:usable])
    floats = [s / 32768.0 for s in ints]
    return torch.tensor([floats], dtype=torch.float32)


class PyannoteDiarizer:
    name = "pyannote"
    version = "unknown"
    mode = "batch"

    def __init__(
        self,
        *,
        model: str = "pyannote/speaker-diarization-3.1",
        hf_token_env: str = "HF_TOKEN",
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        **_extra: Any,
    ) -> None:
        import os

        self._min_speakers = min_speakers
        self._max_speakers = max_speakers
        self._pipeline = None
        self._load_error: ModelUnavailableError | None = None

        try:
            import pyannote.audio as pyannote_audio
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise ModelUnavailableError(
                "pyannote.audio csomag nincs telepítve (extra: diarization-pyannote)"
            ) from exc

        type(self).version = getattr(pyannote_audio, "__version__", "unknown")
        token = os.environ.get(hf_token_env)
        try:
            pipeline = Pipeline.from_pretrained(model, use_auth_token=token)
            if pipeline is None:
                raise RuntimeError(
                    "Pipeline.from_pretrained() None-t adott vissza — ez tipikusan el nem "
                    "fogadott HF licencet vagy hiányzó/érvénytelen tokent jelez."
                )
            self._pipeline = pipeline
        except Exception as exc:  # betöltési/licenc/token hiba -> degradált port, nem crash
            self._load_error = ModelUnavailableError(
                f"pyannote pipeline ('{model}') nem tölthető be — valószínűleg hiányzó/el nem "
                f"fogadott HF licenc vagy érvénytelen '{hf_token_env}' token: {exc}"
            )

    async def diarize_batch(self, audio: AudioBuffer, vad_segments: list[VadSegment]) -> list[DiarizedSegment]:
        if self._load_error is not None:
            raise self._load_error

        waveform = _pcm16_to_tensor(audio.samples)
        kwargs: dict[str, Any] = {}
        if self._min_speakers is not None:
            kwargs["min_speakers"] = self._min_speakers
        if self._max_speakers is not None:
            kwargs["max_speakers"] = self._max_speakers

        diarization = self._pipeline({"waveform": waveform, "sample_rate": audio.sample_rate}, **kwargs)

        segments: list[DiarizedSegment] = []
        label_map: dict[str, str] = {}
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            mapped = label_map.setdefault(speaker, f"S{len(label_map) + 1}")
            segments.append(
                DiarizedSegment(segment_id=new_id("seg-"), start=turn.start, end=turn.end, speaker_label=mapped)
            )
        return segments

    async def diarize_live(
        self, audio_chunk: AudioChunk, state: LiveDiarizationState
    ) -> tuple[list[DiarizedSegment], LiveDiarizationState]:
        raise NotSupportedError("PyannoteDiarizer csak diarize_batch-et támogat (mode=batch)")
