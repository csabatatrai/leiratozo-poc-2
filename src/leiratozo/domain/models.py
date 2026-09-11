"""Domain entities és value objectek.

Ez a modul KIZÁRÓLAG standard könyvtárat és pydantic-ot importálhat — semmilyen
ML/framework-függőség (torch, whisper, pyannote stb.) nem kerülhet ide. Ez teszi
lehetővé, hogy a domain-mag és az alkalmazásréteg ML-függőségek nélkül,
fake adapterekkel tesztelhető legyen. Ld. docs/phase1-terv.md 1. szakasz.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid4().hex}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Audio value objectek (nem pydantic — nyers mintaadatot hordoznak) ------------


@dataclass(frozen=True, slots=True)
class AudioBuffer:
    """Dekódolt, normalizált audio: PCM minták egy rögzített mintavételi rátán."""

    samples: bytes
    sample_rate: int
    duration_sec: float
    source_format: str | None = None


@dataclass(frozen=True, slots=True)
class AudioChunk:
    """Egy streamelt audio-darab, beküldési sorrendben egy élő session-ön belül."""

    samples: bytes
    sample_rate: int
    sequence: int
    session_id: str


# --- ASR ---------------------------------------------------------------------------


class EngineCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    supports_word_timestamps: bool
    supports_native_streaming: bool
    """False esetén az adapter transcribe_stream-je NotSupportedError-t dob, és az
    alkalmazásréteg egy SlidingWindowStreamingAdapter dekorátorral közelíti — ez
    explicit, dokumentált közelítés, nem valódi kauzális streaming (4. szakasz)."""
    languages: list[str] | Literal["auto"] = "auto"


class TranscriptionHints(BaseModel):
    model_config = ConfigDict(frozen=True)

    language: str | None = None
    initial_prompt: str | None = None


class WordToken(BaseModel):
    model_config = ConfigDict(frozen=True)

    word: str
    start: float
    end: float
    confidence: float = Field(ge=0, le=1)


# --- VAD -----------------------------------------------------------------------------


class VadSegment(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: float
    end: float


# --- Diarizáció ------------------------------------------------------------------------


class DiarizedSegment(BaseModel):
    model_config = ConfigDict(frozen=True)

    segment_id: str
    start: float
    end: float
    speaker_label: str
    """Diarizációs-lokális címke (pl. "S1") — NEM regisztrált identitás. A regisztrált
    identitáshoz a SpeakerRegistrationService rendel known_speaker_id-t felül."""


@dataclass
class LiveDiarizationState:
    """Opaque, adapter-specifikus állapot, ami egy élő session chunkjai között
    perzisztálódik (SessionStore-on keresztül) — ez teszi lehetővé, hogy egy
    diarizációs adapter reconnect után folytatni tudja a klaszterezést. A domain-
    és alkalmazásréteg sosem néz bele a `payload`-ba."""

    session_id: str
    payload: dict[str, Any] = field(default_factory=dict)


# --- Speaker embedding / regisztráció --------------------------------------------------


@dataclass(frozen=True, slots=True)
class Embedding:
    vector: tuple[float, ...]
    dim: int


class SpeakerProfile(BaseModel):
    """Csak metaadat — maga az embedding-vektor titkosítva él a ProfileStore-ban,
    és ez a modell sosem tartalmazza (GDPR, docs/phase1-terv.md 6. szakasz)."""

    model_config = ConfigDict(frozen=True)

    profile_id: str = Field(default_factory=lambda: new_id("spk_"))
    display_name: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class SpeakerMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    known_speaker_id: str | None
    confidence: float = Field(ge=0, le=1)


# --- Transzkript-szegmensek (speaker-match utáni, kimeneti-kontraktus-kész) -------------


class TranscriptSegment(BaseModel):
    segment_id: str
    start: float
    end: float
    text: str
    speaker_label: str
    known_speaker_id: str | None = None
    speaker_match_confidence: float | None = Field(default=None, ge=0, le=1)
    asr_confidence: float | None = Field(default=None, ge=0, le=1)
    is_final: bool = True
    words: list[WordToken] = Field(default_factory=list)


class PartialOrFinalTranscript(BaseModel):
    """Egy inkrementális esemény, amit egy élő session emittál."""

    session_id: str
    segment: TranscriptSegment
    is_final: bool


# --- Job-ok és élő session-ök -------------------------------------------------------------


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TranscriptJob(BaseModel):
    job_id: str = Field(default_factory=new_id)
    status: JobStatus = JobStatus.QUEUED
    language: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class LiveSessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    EXPIRED = "expired"


class LiveSession(BaseModel):
    session_id: str = Field(default_factory=new_id)
    status: LiveSessionStatus = LiveSessionStatus.ACTIVE
    language: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    last_activity_at: datetime = Field(default_factory=utcnow)
