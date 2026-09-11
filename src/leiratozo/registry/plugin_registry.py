"""Lusta plugin-registry: egy configból jövő adapter-azonosítót importálható
osztályra old fel, anélkül hogy nehéz ML-függőséget importálna, amíg az
azonosítót ténylegesen nem kérik (docs/phase1-terv.md 1. szakasz).

A port-kind kulcsok szándékosan különböznek a diarizáció batch/élő módjára
(`diarization_batch` / `diarization_live`), mert ezek architekturálisan eltérő
adaptereket takarnak (5. szakasz) — nem ugyanannak a portnak két paraméterezése.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from leiratozo.domain.errors import AdapterNotFoundError

# port_kind -> adapter_name -> "module.path:ClassName"
_REGISTRY: dict[str, dict[str, str]] = {
    "asr": {
        "faster_whisper": "leiratozo.adapters.asr.faster_whisper:FasterWhisperEngine",
        "vosk": "leiratozo.adapters.asr.vosk:VoskEngine",
        "fake": "leiratozo.adapters.asr.fake:FakeTranscriptionEngine",
    },
    "diarization_batch": {
        "pyannote": "leiratozo.adapters.diarization.pyannote:PyannoteDiarizer",
        "nemo_msdd": "leiratozo.adapters.diarization.nemo_msdd:NemoMsddDiarizer",
        "fake": "leiratozo.adapters.diarization.fake:FakeBatchDiarizer",
    },
    "diarization_live": {
        "diart": "leiratozo.adapters.diarization.diart:DiartLiveDiarizer",
        "fake": "leiratozo.adapters.diarization.fake:FakeLiveDiarizer",
    },
    "speaker_embedding": {
        "speechbrain_ecapa": "leiratozo.adapters.speaker_embedding.speechbrain_ecapa:SpeechBrainEcapaEngine",
        "resemblyzer": "leiratozo.adapters.speaker_embedding.resemblyzer:ResemblyzerEngine",
        "fake": "leiratozo.adapters.speaker_embedding.fake:FakeSpeakerEmbeddingEngine",
    },
    "vad": {
        "silero": "leiratozo.adapters.vad.silero:SileroVad",
        "fake": "leiratozo.adapters.vad.fake:FakeVad",
    },
    "audio_decoder": {
        "ffmpeg": "leiratozo.adapters.audio_decoder.ffmpeg_decoder:FfmpegAudioDecoder",
        "fake": "leiratozo.adapters.audio_decoder.fake:FakeAudioDecoder",
    },
    "aligner": {
        "passthrough": "leiratozo.adapters.aligner.passthrough:PassthroughAligner",
        "fake": "leiratozo.adapters.aligner.passthrough:PassthroughAligner",
    },
    "job_store": {
        "sqlite": "leiratozo.adapters.storage.job_store_sqlite:SqliteJobStore",
        "fake": "leiratozo.adapters.storage.fake:InMemoryJobStore",
    },
    "session_store": {
        "sqlite": "leiratozo.adapters.storage.session_store_sqlite:SqliteSessionStore",
        "fake": "leiratozo.adapters.storage.fake:InMemorySessionStore",
    },
    "profile_store": {
        "encrypted_sqlite": "leiratozo.adapters.storage.profile_store_encrypted_sqlite:EncryptedSqliteProfileStore",
        "fake": "leiratozo.adapters.storage.fake:InMemoryProfileStore",
    },
}


@dataclass(frozen=True, slots=True)
class AdapterRef:
    port_kind: str
    adapter_name: str
    dotted_path: str


def resolve(port_kind: str, adapter_name: str) -> AdapterRef:
    try:
        dotted_path = _REGISTRY[port_kind][adapter_name]
    except KeyError as exc:
        raise AdapterNotFoundError(
            f"Nincs '{adapter_name}' nevű adapter regisztrálva a(z) '{port_kind}' porthoz."
        ) from exc
    return AdapterRef(port_kind=port_kind, adapter_name=adapter_name, dotted_path=dotted_path)


def load_class(ref: AdapterRef) -> type:
    module_path, _, class_name = ref.dotted_path.partition(":")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise AdapterNotFoundError(
            f"A(z) '{ref.adapter_name}' adapter ({ref.port_kind} port) nem importálható "
            f"({module_path}): {exc}. Lehet, hogy hiányzik az opcionális függőség-csoportja "
            f"— ld. pyproject.toml [project.optional-dependencies]."
        ) from exc
    return getattr(module, class_name)


def instantiate(port_kind: str, adapter_name: str, params: dict[str, Any] | None = None) -> Any:
    """Fail-fast feloldás + import; a visszaadott példány saját __init__-je a
    nehéz modellbetöltést még halogathatja (warmup), a `preload_models`
    configtól függően — ld. 1. szakasz."""
    ref = resolve(port_kind, adapter_name)
    cls = load_class(ref)
    return cls(**(params or {}))


def register(port_kind: str, adapter_name: str, dotted_path: str) -> None:
    """Teszteknek vagy integrátoroknak: további adapter regisztrálása e modul
    módosítása nélkül."""
    _REGISTRY.setdefault(port_kind, {})[adapter_name] = dotted_path
