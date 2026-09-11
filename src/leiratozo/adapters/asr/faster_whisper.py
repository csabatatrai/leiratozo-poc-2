"""Valódi faster-whisper (CTranslate2) ASR adapter. Batch-natív, szó-szintű
időbélyeget ad (word_timestamps=True) — capabilities.supports_native_streaming
mindig False, ld. docs/phase1-terv.md 4. szakasz: az élő közelítést az
alkalmazásréteg SlidingWindowStreamingAdapter-je adja hozzá, ez az adapter
sosem implementál valódi streaminget."""
from __future__ import annotations

from typing import Any, AsyncIterator

from leiratozo.domain.errors import ModelUnavailableError, NotSupportedError
from leiratozo.domain.models import (
    AudioBuffer,
    AudioChunk,
    EngineCapabilities,
    PartialOrFinalTranscript,
    TranscriptionHints,
    WordToken,
)


def _pcm16_bytes_to_float32(samples: bytes) -> Any:
    """faster-whisper `WhisperModel.transcribe` numpy float32 tömböt (vagy
    fájlútvonalat/file-like objektumot) vár — egy sima Python listát/bájtsorozatot
    NEM fogad el (av.open-nal próbálná dekódolni file-ként).

    A numpy importot SZÁNDÉKOSAN itt, függvényen belül tartjuk (nem modulszinten)
    — a modulnak import-biztosnak kell maradnia numpy/faster-whisper nélkül is,
    hogy a plugin registry fail-fast feloldása (registry/plugin_registry.py)
    tiszta AdapterNotFoundError-t adjon, ne egy véletlen ModuleNotFoundError-t a
    fájl tetejéről (ld. docs/phase1-terv.md 1. szakasz)."""
    import numpy as np

    usable_len = len(samples) - (len(samples) % 2)
    ints = np.frombuffer(samples[:usable_len], dtype="<i2")
    return (ints.astype(np.float32)) / 32768.0


class FasterWhisperEngine:
    name = "faster-whisper"
    version = "unknown"
    capabilities = EngineCapabilities(
        supports_word_timestamps=True, supports_native_streaming=False, languages="auto"
    )

    def __init__(
        self,
        *,
        model_size: str = "tiny",
        device: str = "auto",
        compute_type: str = "int8",
        **extra_params: Any,
    ) -> None:
        try:
            import faster_whisper
        except ImportError as exc:  # pragma: no cover - csomag hiánya, nem futásidejű eset
            raise ModelUnavailableError(
                "faster-whisper csomag nincs telepítve (extra: asr-faster-whisper)"
            ) from exc

        resolved_device = self._resolve_device(device)
        type(self).version = getattr(faster_whisper, "__version__", "unknown")
        try:
            self._model = faster_whisper.WhisperModel(
                model_size, device=resolved_device, compute_type=compute_type, **extra_params
            )
        except Exception as exc:  # letöltési/licenc/eszköz hiba -> nem-fatális, degradált port
            raise ModelUnavailableError(
                f"faster-whisper modell ('{model_size}') nem tölthető be: {exc}"
            ) from exc

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    async def transcribe_batch(
        self, audio: AudioBuffer, *, language: str | None, hints: TranscriptionHints
    ) -> list[WordToken]:
        pcm = _pcm16_bytes_to_float32(audio.samples)
        segments, _info = self._model.transcribe(
            pcm,
            language=language,
            initial_prompt=hints.initial_prompt,
            word_timestamps=True,
        )
        tokens: list[WordToken] = []
        for segment in segments:
            words = getattr(segment, "words", None) or []
            for word in words:
                tokens.append(
                    WordToken(
                        word=word.word.strip(),
                        start=word.start,
                        end=word.end,
                        confidence=float(max(0.0, min(1.0, (word.probability or 0.0)))),
                    )
                )
        return tokens

    def transcribe_stream(
        self, audio_chunks: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[PartialOrFinalTranscript]:
        raise NotSupportedError(
            f"{self.name} batch-natív, nem implementál natív streaminget — "
            "az alkalmazásréteg SlidingWindowStreamingAdapter-je közelíti."
        )
