"""Valódi "távoli HTTP ASR-végpont" adapter: egy már futó, akárki más által
üzemeltetett leiratozó-szolgáltatást hív ki HTTP-n (multipart file upload), a
TranscriptionEngine port mögött (docs/phase1-terv.md 1. szakasz: "minden
portra legalább 2 adapter" — ez egy HARMADIK, gyakorlati ASR-adapter, ami azt
demonstrálja, hogy a port nem csak in-process modelleket fogad el).

FONTOS — MODULARITÁS: ez az adapter NINCS egyetlen konkrét szerverhez kötve.
A `base_url` (+ `transcribe_path`/`health_path`/`api_key_env`) teljes egészében
configból jön (ld. config/config.remote-whisper.yaml) — egy MÁSIK, ugyanilyen
válaszsémájú végpontra váltás kódmódosítás nélkül, egyetlen config-sor
átírásával megy. Csak a `_parse_response` metódus feltételez egy konkrét,
de igen elterjedt "Whisper-API-szerű" válasz-JSON-t (ld. lent) — ha egy
JÖVŐBELI végpont ettől ELTÉRŐ szerkezetű választ ad, a helyes megoldás EGY ÚJ,
kis adapter-alosztály (vagy önálló osztály) írása, ami csak ezt az egy
metódust írja felül/cseréli, a HTTP/multipart/health-check logika
újrahasznosításával — pontosan úgy, ahogy a projekt minden más portjára is
több, egymástól független adapter épül.

Az alapértelmezett `_parse_response` válaszsémája egy konkrét, éles
Whisper-alapú TESZT-végponton lett felderítve valós hívással (2026-09-12,
ld. docs/manual_test_notes.md) — ez a teszt-végpont csak egy PÉLDÁNY volt,
nem architekturális függőség:
    {
      "text": str, "language": str, "language_probability": float,
      "duration_s": float, "processing_time_s": float, "rtf": float,
      "segments": [{"start": float, "end": float, "text": str}, ...]
    }
FONTOS KORLÁT: ez a séma csak SZEGMENS-szintű (nem szó-szintű) időbélyeget
ad. Ezért capabilities.supports_word_timestamps=False, és minden szegmensből
EGY WordToken lesz (a szegmens teljes szövegével) — ez durvább granularitású,
mint a faster-whisper/Vosk adapterek szó-szintű kimenete, és a
PassthroughAligner emiatt csak szegmens-pontossággal tudja a diarizációhoz
illeszteni a szöveget (ld. docs/tradeoffs_and_decisions.md)."""
from __future__ import annotations

import io
import wave
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


def _pcm16_to_wav_bytes(samples: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples)
    return buf.getvalue()


class RemoteHttpAsrEngine:
    name = "remote-http-asr"
    version = "unknown"
    capabilities = EngineCapabilities(
        supports_word_timestamps=False, supports_native_streaming=False, languages="auto"
    )

    def __init__(
        self,
        *,
        base_url: str,
        transcribe_path: str = "/transcribe",
        health_path: str = "/health",
        api_key_env: str | None = None,
        timeout_sec: float = 120.0,
        **_extra: Any,
    ) -> None:
        import os

        try:
            import httpx
        except ImportError as exc:
            raise ModelUnavailableError(
                "httpx csomag nincs telepítve (extra: asr-remote-http)"
            ) from exc

        type(self).version = getattr(httpx, "__version__", "unknown")
        self._base_url = base_url.rstrip("/")
        self._transcribe_url = f"{self._base_url}{transcribe_path}"
        self._health_url = f"{self._base_url}{health_path}"
        self._timeout_sec = timeout_sec
        self._api_key = os.environ.get(api_key_env) if api_key_env else None
        self._httpx = httpx

        try:
            resp = httpx.get(self._health_url, timeout=timeout_sec)
            resp.raise_for_status()
        except Exception as exc:
            raise ModelUnavailableError(
                f"Távoli ASR-végpont ({self._health_url}) nem érhető el induláskor: {exc}"
            ) from exc

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key} if self._api_key else {}

    async def transcribe_batch(
        self, audio: AudioBuffer, *, language: str | None, hints: TranscriptionHints
    ) -> list[WordToken]:
        wav_bytes = _pcm16_to_wav_bytes(audio.samples, audio.sample_rate)
        try:
            async with self._httpx.AsyncClient(timeout=self._timeout_sec) as client:
                response = await client.post(
                    self._transcribe_url,
                    files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                    headers=self._headers(),
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise ModelUnavailableError(f"Távoli ASR-hívás sikertelen ({self._transcribe_url}): {exc}") from exc

        return self._parse_response(payload, audio_duration_sec=audio.duration_sec)

    def _parse_response(self, payload: dict, *, audio_duration_sec: float) -> list[WordToken]:
        """Egy konkrét, "Whisper-API-szerű" válasz-JSON-t vár (ld. modul
        docstring). MÁS válaszsémájú végponthoz ÍRJ EGY ALOSZTÁLYT, ami csak
        ezt a metódust írja felül — a HTTP-hívás/health-check logikát
        (`__init__`, `transcribe_batch`) nem kell duplikálni."""
        confidence = float(payload.get("language_probability") or 0.9)
        confidence = max(0.0, min(1.0, confidence))
        segments = payload.get("segments") or []
        if not segments and payload.get("text"):
            # A végpont üres `segments`-et is adhat nem-üres `text` mellett —
            # ilyenkor a teljes audio hosszát használjuk egyetlen tokenhez.
            segments = [{"start": 0.0, "end": audio_duration_sec, "text": payload["text"]}]

        return [
            WordToken(
                word=seg["text"].strip(),
                start=float(seg["start"]),
                end=float(seg["end"]),
                confidence=confidence,
            )
            for seg in segments
            if seg.get("text", "").strip()
        ]

    def transcribe_stream(
        self, audio_chunks: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[PartialOrFinalTranscript]:
        raise NotSupportedError(
            f"{self.name} csak batch végpontot hív (nincs natív streaming a távoli szolgáltatásnál) — "
            "az alkalmazásréteg SlidingWindowStreamingAdapter-je közelíti."
        )
