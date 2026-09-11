"""Contract-teszt a JSON kimeneti kontraktusra — docs/phase1-terv.md 8. szakasz.
Ha ez a teszt egy nem-additív változás miatt bukik, a SCHEMA_VERSION-t emelni
kell és a README-ben dokumentálni."""
from __future__ import annotations

import json

from leiratozo.contracts.transcript_schema import (
    SCHEMA_VERSION,
    ModelInfo,
    SingleModelInfo,
    TranscriptDocument,
)
from leiratozo.domain.models import TranscriptSegment, WordToken


def _sample_models() -> ModelInfo:
    info = SingleModelInfo(name="fake", version="0.0.1")
    return ModelInfo(vad=info, asr=info, diarization=info, speaker_embedding=info)


def test_schema_version_is_the_documented_one():
    assert SCHEMA_VERSION == "1.0"


def test_transcript_document_round_trips_through_json():
    doc = TranscriptDocument(
        job_id="job-1",
        mode="batch",
        language="hu",
        audio_duration_sec=3.87,
        audio_sample_rate=16000,
        audio_source_format="mp3",
        models=_sample_models(),
        segments=[
            TranscriptSegment(
                segment_id="seg-0001",
                start=0.42,
                end=3.87,
                text="Szia, hogy vagy?",
                speaker_label="S1",
                known_speaker_id="spk_7f2a9c11",
                speaker_match_confidence=0.86,
                asr_confidence=0.94,
                is_final=True,
                words=[WordToken(word="Szia", start=0.42, end=0.71, confidence=0.97)],
            )
        ],
    )

    raw = doc.model_dump_json()
    restored = TranscriptDocument.model_validate(json.loads(raw))

    assert restored.schema_version == "1.0"
    assert restored.segments[0].speaker_label == "S1"
    assert restored.segments[0].known_speaker_id == "spk_7f2a9c11"


def test_speakers_detected_and_aggregates_are_derived_when_omitted():
    doc = TranscriptDocument(
        mode="batch",
        language="hu",
        audio_duration_sec=10.0,
        audio_sample_rate=16000,
        models=_sample_models(),
        segments=[
            TranscriptSegment(segment_id="s1", start=0.0, end=2.0, text="a", speaker_label="S1"),
            TranscriptSegment(segment_id="s2", start=2.0, end=5.0, text="b", speaker_label="S2"),
            TranscriptSegment(segment_id="s3", start=5.0, end=6.5, text="c", speaker_label="S1"),
        ],
    )

    assert doc.speakers_detected == ["S1", "S2"]
    aggregates = {a.speaker_label: a for a in doc.speaker_aggregates}
    assert aggregates["S1"].total_speech_sec == 3.5  # (2.0-0.0) + (6.5-5.0)
    assert aggregates["S1"].segment_ids == ["s1", "s3"]
    assert aggregates["S2"].total_speech_sec == 3.0


def test_unknown_speaker_is_null_not_forced():
    doc = TranscriptDocument(
        mode="batch",
        language="hu",
        audio_duration_sec=1.0,
        audio_sample_rate=16000,
        models=_sample_models(),
        segments=[TranscriptSegment(segment_id="s1", start=0.0, end=1.0, text="x", speaker_label="S1")],
    )
    assert doc.segments[0].known_speaker_id is None
