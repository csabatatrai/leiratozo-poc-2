"""Valódi SpeechBrain ECAPA-TDNN (x-vector) speaker-embedding adapter. Nyilvános
modell ("speechbrain/spkrec-ecapa-voxceleb"), HF token NEM szükséges — ld.
docs/phase1-terv.md 11. szakasz."""
from __future__ import annotations

from typing import Any

from leiratozo.domain.errors import ModelUnavailableError
from leiratozo.domain.models import AudioBuffer, DiarizedSegment, Embedding

_SAMPLE_WIDTH_BYTES = 2  # 16 bites PCM


def _pcm16_bytes_to_float_list(samples: bytes) -> list[float]:
    import array

    ints = array.array("h")
    usable_len = len(samples) - (len(samples) % _SAMPLE_WIDTH_BYTES)
    ints.frombytes(samples[:usable_len])
    return [s / 32768.0 for s in ints]


def _slice_by_time(audio: AudioBuffer, start: float, end: float) -> bytes:
    start_byte = max(0, int(start * audio.sample_rate) * _SAMPLE_WIDTH_BYTES)
    end_byte = min(len(audio.samples), int(end * audio.sample_rate) * _SAMPLE_WIDTH_BYTES)
    return audio.samples[start_byte:end_byte] or audio.samples


class SpeechBrainEcapaEngine:
    name = "speechbrain-ecapa"
    version = "unknown"
    embedding_dim = 192

    def __init__(
        self,
        *,
        source: str = "speechbrain/spkrec-ecapa-voxceleb",
        savedir: str = ".cache/speechbrain/ecapa",
        **_extra: Any,
    ) -> None:
        try:
            import speechbrain
            import torch
            from speechbrain.inference.speaker import EncoderClassifier
        except ImportError as exc:
            raise ModelUnavailableError(
                "speechbrain csomag nincs telepítve (extra: embedding-speechbrain)"
            ) from exc

        type(self).version = getattr(speechbrain, "__version__", "unknown")
        try:
            self._classifier = EncoderClassifier.from_hparams(source=source, savedir=savedir)
        except Exception as exc:
            raise ModelUnavailableError(f"SpeechBrain ECAPA modell nem tölthető be ({source}): {exc}") from exc
        self._torch = torch

    def _embed_pcm16(self, samples: bytes) -> Embedding:
        floats = _pcm16_bytes_to_float_list(samples)
        if not floats:
            floats = [0.0]
        wav = self._torch.tensor([floats], dtype=self._torch.float32)
        with self._torch.no_grad():
            raw = self._classifier.encode_batch(wav)
        vector = raw.squeeze().tolist()
        return Embedding(vector=tuple(vector), dim=len(vector))

    async def extract_embedding(self, audio: AudioBuffer) -> Embedding:
        return self._embed_pcm16(audio.samples)

    async def extract_embeddings_for_segments(
        self, audio: AudioBuffer, segments: list[DiarizedSegment]
    ) -> dict[str, Embedding]:
        return {seg.segment_id: self._embed_pcm16(_slice_by_time(audio, seg.start, seg.end)) for seg in segments}
