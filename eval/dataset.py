"""Egy kiértékelési eset ("case") betöltése egy manifest.json-ból. Ld.
eval/README.md a séma pontos leírásáért és egy minimál példáért."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KnownSpeaker:
    speaker_id: str
    enrollment_audio_path: Path


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    description: str
    audio_path: Path
    reference_transcript_path: Path | None
    reference_rttm_path: Path | None
    known_speakers: list[KnownSpeaker]

    @property
    def reference_transcript(self) -> str | None:
        if self.reference_transcript_path is None:
            return None
        return self.reference_transcript_path.read_text(encoding="utf-8")

    def has_transcript_ground_truth(self) -> bool:
        return self.reference_transcript_path is not None and self.reference_transcript_path.exists()

    def has_diarization_ground_truth(self) -> bool:
        return self.reference_rttm_path is not None and self.reference_rttm_path.exists()

    def has_known_speakers(self) -> bool:
        return len(self.known_speakers) > 0


def load_case(manifest_path: str | Path) -> EvalCase:
    manifest_path = Path(manifest_path)
    with manifest_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    base_dir = manifest_path.parent

    def _resolve(rel_path: str | None) -> Path | None:
        return (base_dir / rel_path) if rel_path else None

    known_speakers = [
        KnownSpeaker(
            speaker_id=entry["speaker_id"],
            enrollment_audio_path=base_dir / entry["enrollment_audio_path"],
        )
        for entry in raw.get("known_speakers", [])
    ]

    return EvalCase(
        case_id=raw["id"],
        description=raw.get("description", ""),
        audio_path=base_dir / raw["audio_path"],
        reference_transcript_path=_resolve(raw.get("reference_transcript_path")),
        reference_rttm_path=_resolve(raw.get("reference_rttm_path")),
        known_speakers=known_speakers,
    )
