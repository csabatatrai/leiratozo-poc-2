"""A stabil, verziózott JSON kimeneti kontraktus — docs/phase1-terv.md 8. szakasz.

Bármilyen NEM tisztán additív változtatás itt SCHEMA_VERSION emelést és a
README-ben dokumentálást igényel.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from leiratozo.domain.models import TranscriptSegment

SCHEMA_VERSION = "1.0"


class SingleModelInfo(BaseModel):
    name: str
    version: str
    extra: dict = Field(default_factory=dict)


class ModelInfo(BaseModel):
    vad: SingleModelInfo
    asr: SingleModelInfo
    diarization: SingleModelInfo
    speaker_embedding: SingleModelInfo

    @classmethod
    def collect(cls, *, vad: object, asr: object, diarization: object, speaker_embedding: object) -> "ModelInfo":
        def _info(engine: object, **extra: object) -> SingleModelInfo:
            return SingleModelInfo(name=engine.name, version=engine.version, extra=extra)  # type: ignore[attr-defined]

        asr_extra: dict = {}
        if hasattr(asr, "capabilities"):
            asr_extra["streaming_mode"] = (
                "native" if asr.capabilities.supports_native_streaming else "approximated"  # type: ignore[attr-defined]
            )
        diar_extra: dict = {}
        if hasattr(diarization, "mode"):
            diar_extra["mode"] = diarization.mode  # type: ignore[attr-defined]

        return cls(
            vad=_info(vad),
            asr=_info(asr, **asr_extra),
            diarization=_info(diarization, **diar_extra),
            speaker_embedding=_info(speaker_embedding),
        )


class SpeakerAggregate(BaseModel):
    speaker_label: str
    known_speaker_id: str | None
    total_speech_sec: float
    segment_ids: list[str]


def _aggregate_speakers(segments: list[TranscriptSegment]) -> list[SpeakerAggregate]:
    by_speaker: dict[str, dict] = {}
    for seg in segments:
        bucket = by_speaker.setdefault(
            seg.speaker_label,
            {"known_speaker_id": seg.known_speaker_id, "total": 0.0, "ids": []},
        )
        bucket["total"] += max(0.0, seg.end - seg.start)
        bucket["ids"].append(seg.segment_id)
        if seg.known_speaker_id:
            bucket["known_speaker_id"] = seg.known_speaker_id
    return [
        SpeakerAggregate(
            speaker_label=label,
            known_speaker_id=data["known_speaker_id"],
            total_speech_sec=round(data["total"], 3),
            segment_ids=data["ids"],
        )
        for label, data in sorted(by_speaker.items())
    ]


class TranscriptDocument(BaseModel):
    schema_version: str = SCHEMA_VERSION
    job_id: str | None = None
    session_id: str | None = None
    mode: Literal["batch", "live"]
    language: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    audio_duration_sec: float
    audio_sample_rate: int
    audio_source_format: str | None = None
    models: ModelInfo
    speakers_detected: list[str] = Field(default_factory=list)
    segments: list[TranscriptSegment] = Field(default_factory=list)
    speaker_aggregates: list[SpeakerAggregate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _derive_aggregates(self) -> "TranscriptDocument":
        if not self.speakers_detected:
            self.speakers_detected = sorted({s.speaker_label for s in self.segments})
        if not self.speaker_aggregates and self.segments:
            self.speaker_aggregates = _aggregate_speakers(self.segments)
        return self
