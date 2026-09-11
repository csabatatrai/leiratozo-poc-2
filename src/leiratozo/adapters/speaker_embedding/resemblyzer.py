"""Valódi Resemblyzer (GE2E d-vector) speaker-embedding adapter — architekturálisan
eltér az ECAPA-TDNN-től (LSTM-alapú GE2E, nem x-vector), ld. docs/phase1-terv.md
11. szakasz. Nyilvános, becsomagolt modellsúly, HF token nem szükséges.

Megjegyzés: a `resemblyzer.preprocess_wav` alapból `webrtcvad`-dal von ki csendet
— ezt SZÁNDÉKOSAN kihagyjuk (a VAD már megelőző lépésként lefutott a pipeline-ban,
ld. 6. kemény megkötés / VoiceActivityDetector port), és a már VAD-szűrt PCM-et
adjuk közvetlenül a VoiceEncoder-nek, hogy ne legyen felesleges, dupla,
NEM-configolható VAD-függőség (webrtcvad) az embedding-adapterben."""
from __future__ import annotations

from typing import Any

from leiratozo.domain.errors import ModelUnavailableError
from leiratozo.domain.models import AudioBuffer, DiarizedSegment, Embedding

_SAMPLE_WIDTH_BYTES = 2
_TARGET_SAMPLE_RATE = 16000


def _pcm16_bytes_to_float_array(samples: bytes) -> Any:
    import numpy as np

    usable_len = len(samples) - (len(samples) % _SAMPLE_WIDTH_BYTES)
    ints = np.frombuffer(samples[:usable_len], dtype="<i2")
    return (ints.astype(np.float32)) / 32768.0


def _slice_by_time(audio: AudioBuffer, start: float, end: float) -> bytes:
    start_byte = max(0, int(start * audio.sample_rate) * _SAMPLE_WIDTH_BYTES)
    end_byte = min(len(audio.samples), int(end * audio.sample_rate) * _SAMPLE_WIDTH_BYTES)
    return audio.samples[start_byte:end_byte] or audio.samples


class ResemblyzerEngine:
    name = "resemblyzer"
    version = "unknown"
    embedding_dim = 256

    def __init__(self, **_extra: Any) -> None:
        try:
            import resemblyzer
            from resemblyzer import VoiceEncoder
        except ImportError as exc:
            raise ModelUnavailableError(
                "resemblyzer csomag nincs telepítve (extra: embedding-resemblyzer)"
            ) from exc

        type(self).version = getattr(resemblyzer, "__version__", "unknown")
        try:
            self._encoder = VoiceEncoder()
        except Exception as exc:
            raise ModelUnavailableError(f"Resemblyzer modell nem tölthető be: {exc}") from exc

    def _embed_pcm16(self, samples: bytes, sample_rate: int) -> Embedding:
        wav = _pcm16_bytes_to_float_array(samples)
        if sample_rate != _TARGET_SAMPLE_RATE:
            # A VoiceEncoder 16kHz-re épül; ha a bemenet más rátán jön, a
            # librosa-t (resemblyzer tranzitív függősége) használjuk resample-hez.
            import librosa

            wav = librosa.resample(wav, orig_sr=sample_rate, target_sr=_TARGET_SAMPLE_RATE)
        vector = self._encoder.embed_utterance(wav).tolist()
        return Embedding(vector=tuple(vector), dim=len(vector))

    async def extract_embedding(self, audio: AudioBuffer) -> Embedding:
        return self._embed_pcm16(audio.samples, audio.sample_rate)

    async def extract_embeddings_for_segments(
        self, audio: AudioBuffer, segments: list[DiarizedSegment]
    ) -> dict[str, Embedding]:
        return {
            seg.segment_id: self._embed_pcm16(_slice_by_time(audio, seg.start, seg.end), audio.sample_rate)
            for seg in segments
        }
