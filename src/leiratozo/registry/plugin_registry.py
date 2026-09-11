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

from leiratozo.domain.errors import AdapterNotFoundError, ModelUnavailableError

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


class DegradedAdapter:
    """Helyettesítő objektum egy olyan modell-adapter helyén, ami betöltéskor
    `ModelUnavailableError`-t dobott (pl. hiányzó HF token/licenc-elfogadás —
    docs/phase1-terv.md 1. és 10. szakasz). A ServiceContainer NEM omlik össze
    emiatt: ez az objektum minden portmetódus-hívásra ugyanazt a hibát dobja,
    de a `name`/`version`/`capabilities`/`mode`/`embedding_dim` attribútumok
    biztonságosan olvashatók (pl. /v1/config, ModelInfo.collect), hogy azok NE
    hasaljanak el a degradált port miatt."""

    from leiratozo.domain.models import EngineCapabilities as _EngineCapabilities

    def __init__(self, port_kind: str, adapter_name: str, error: ModelUnavailableError) -> None:
        self.name = f"{adapter_name}-degraded"
        self.version = "unavailable"
        self.embedding_dim = 0
        self.mode = "batch"
        self.capabilities = self._EngineCapabilities(
            supports_word_timestamps=False, supports_native_streaming=False, languages="auto"
        )
        self.port_kind = port_kind
        self.adapter_name = adapter_name
        self.error = error

    def __getattr__(self, item: str):
        async def _raise(*_args: Any, **_kwargs: Any) -> Any:
            raise self.error

        return _raise


def instantiate_or_degrade(port_kind: str, adapter_name: str, params: dict[str, Any] | None = None) -> Any:
    """Mint `instantiate`, de `ModelUnavailableError`-t (hiányzó token/licenc/
    eszköz/letöltési hiba) elfog és `DegradedAdapter`-ré alakít, hogy a hívó
    (ServiceContainer) tovább élhessen — más portok emiatt nem esnek el. Az
    `AdapterNotFoundError` (hiányzó csomag/config hiba) VISZONT tovább terjed:
    az fail-fast konfigurációs hiba, nem futásidejű degradáció."""
    try:
        return instantiate(port_kind, adapter_name, params)
    except ModelUnavailableError as exc:
        return DegradedAdapter(port_kind, adapter_name, exc)
