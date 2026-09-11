"""Valódi Vosk (Kaldi) ASR adapter — ez az EGYETLEN ASR adapter, aminek
capabilities.supports_native_streaming=True, mert a KaldiRecognizer ténylegesen
inkrementálisan, kauzálisan dolgozza fel a chunkokat (nincs szükség a
SlidingWindowStreamingAdapter közelítésre). Ld. docs/phase1-terv.md 4. szakasz."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.request import urlretrieve
import zipfile

from leiratozo.domain.errors import ModelUnavailableError
from leiratozo.domain.models import (
    AudioBuffer,
    AudioChunk,
    EngineCapabilities,
    PartialOrFinalTranscript,
    TranscriptSegment,
    TranscriptionHints,
    WordToken,
)

_DEFAULT_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
_DEFAULT_CACHE_DIR = Path(".cache/vosk")


def _ensure_model(model_path: str | None, model_url: str) -> str:
    """Ha nincs explicit model_path megadva, letölti (és .gitignore-olt helyi
    könyvtárban cache-eli) a model_url alatti Vosk-modellt. Sosem kerül a
    modellsúly a git repóba."""
    if model_path:
        return model_path
    cache_dir = _DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    model_name = model_url.rsplit("/", 1)[-1]
    if model_name.endswith(".zip"):
        model_name = model_name[: -len(".zip")]
    target_dir = cache_dir / model_name
    if target_dir.exists():
        return str(target_dir)
    zip_path = cache_dir / f"{model_name}.zip"
    try:
        urlretrieve(model_url, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(cache_dir)
    except Exception as exc:
        raise ModelUnavailableError(f"Vosk modell letöltése sikertelen ({model_url}): {exc}") from exc
    finally:
        zip_path.unlink(missing_ok=True)
    return str(target_dir)


class VoskEngine:
    name = "vosk"
    version = "unknown"
    capabilities = EngineCapabilities(
        supports_word_timestamps=True, supports_native_streaming=True, languages="auto"
    )

    def __init__(
        self,
        *,
        model_path: str | None = None,
        model_url: str = _DEFAULT_MODEL_URL,
        sample_rate: int = 16000,
        **extra: Any,
    ) -> None:
        try:
            import vosk
        except ImportError as exc:
            raise ModelUnavailableError("vosk csomag nincs telepítve (extra: asr-vosk)") from exc

        type(self).version = getattr(vosk, "__version__", "unknown")
        vosk.SetLogLevel(-1)
        resolved_path = _ensure_model(model_path, model_url)
        try:
            self._model = vosk.Model(resolved_path)
        except Exception as exc:
            raise ModelUnavailableError(f"Vosk modell nem tölthető be ({resolved_path}): {exc}") from exc
        self._vosk = vosk
        self._sample_rate = sample_rate

    async def transcribe_batch(
        self, audio: AudioBuffer, *, language: str | None, hints: TranscriptionHints
    ) -> list[WordToken]:
        recognizer = self._vosk.KaldiRecognizer(self._model, audio.sample_rate)
        recognizer.SetWords(True)
        recognizer.AcceptWaveform(audio.samples)
        result = json.loads(recognizer.FinalResult())
        return self._result_to_tokens(result)

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[PartialOrFinalTranscript]:
        recognizer = self._vosk.KaldiRecognizer(self._model, self._sample_rate)
        recognizer.SetWords(True)
        session_id = ""
        emitted = 0
        async for chunk in audio_chunks:
            session_id = chunk.session_id
            if recognizer.AcceptWaveform(chunk.samples):
                tokens = self._result_to_tokens(json.loads(recognizer.Result()))
                if tokens:
                    emitted += len(tokens)
                    yield self._make_event(session_id, tokens, is_final=True, idx=emitted)
            else:
                partial_text = json.loads(recognizer.PartialResult()).get("partial", "")
                if partial_text:
                    tokens = [WordToken(word=w, start=0.0, end=0.0, confidence=0.5) for w in partial_text.split()]
                    yield self._make_event(session_id, tokens, is_final=False, idx=emitted)
        tokens = self._result_to_tokens(json.loads(recognizer.FinalResult()))
        if tokens:
            emitted += len(tokens)
            yield self._make_event(session_id, tokens, is_final=True, idx=emitted)

    @staticmethod
    def _result_to_tokens(result: dict) -> list[WordToken]:
        words = result.get("result") or []
        return [
            WordToken(word=w["word"], start=w["start"], end=w["end"], confidence=float(w.get("conf", 0.9)))
            for w in words
        ]

    @staticmethod
    def _make_event(
        session_id: str, tokens: list[WordToken], *, is_final: bool, idx: int
    ) -> PartialOrFinalTranscript:
        text = " ".join(t.word for t in tokens)
        segment = TranscriptSegment(
            segment_id=f"vosk-{session_id}-{'final' if is_final else 'partial'}-{idx}",
            start=tokens[0].start if tokens else 0.0,
            end=tokens[-1].end if tokens else 0.0,
            text=text,
            speaker_label="S?",
            is_final=is_final,
            words=tokens,
        )
        return PartialOrFinalTranscript(session_id=session_id, segment=segment, is_final=is_final)
