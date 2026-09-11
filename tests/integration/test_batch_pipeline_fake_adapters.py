"""Integrációs teszt: a teljes batch csővezeték (AudioDecoder -> VAD -> ASR ->
Diarizáció -> Aligner -> SpeakerMatch) fake adapterekkel, a valódi
BatchTranscriptionService-en keresztül — docs/phase1-terv.md 12.1. szekvencia."""
from __future__ import annotations

from leiratozo.adapters.aligner.passthrough import PassthroughAligner
from leiratozo.adapters.asr.fake import FakeTranscriptionEngine
from leiratozo.adapters.audio_decoder.fake import FakeAudioDecoder
from leiratozo.adapters.diarization.fake import FakeBatchDiarizer
from leiratozo.adapters.speaker_embedding.fake import FakeSpeakerEmbeddingEngine
from leiratozo.adapters.storage.fake import InMemoryJobStore, InMemoryProfileStore
from leiratozo.adapters.vad.fake import FakeVad
from leiratozo.application.batch_service import BatchTranscriptionService
from leiratozo.application.speaker_registration_service import SpeakerRegistrationService
from leiratozo.domain.models import JobStatus


def _build_service(job_store: InMemoryJobStore) -> BatchTranscriptionService:
    speaker_registration = SpeakerRegistrationService(
        FakeSpeakerEmbeddingEngine(), InMemoryProfileStore(), similarity_threshold=0.72
    )
    return BatchTranscriptionService(
        audio_decoder=FakeAudioDecoder(),
        vad=FakeVad(),
        asr=FakeTranscriptionEngine(),
        diarizer=FakeBatchDiarizer(),
        aligner=PassthroughAligner(),
        speaker_registration=speaker_registration,
        job_store=job_store,
        language="hu",
    )


async def test_full_batch_pipeline_produces_a_valid_document():
    job_store = InMemoryJobStore()
    service = _build_service(job_store)

    raw_audio = b"\x00\x01" * 16000 * 3  # ~3s 16kHz 16-bit mono
    job = await service.submit(raw_audio, filename_hint="sample.wav")
    await service.run(job.job_id, raw_audio, filename_hint="sample.wav")

    updated_job = await job_store.get(job.job_id)
    assert updated_job.status == JobStatus.DONE

    document = await job_store.get_result(job.job_id)
    assert document is not None
    assert document.schema_version == "1.0"
    assert document.mode == "batch"
    assert document.segments, "kell legyen legalább egy szegmens"
    for segment in document.segments:
        assert segment.words, "minden szegmensnek kell legyen szó-szintű időbélyege"
        assert segment.speaker_label.startswith("S")


async def test_too_short_audio_fails_the_job_without_raising():
    job_store = InMemoryJobStore()
    service = _build_service(job_store)

    raw_audio = b"\x00\x00"  # ~0.0000625s -> a minimum alatt
    job = await service.submit(raw_audio)
    await service.run(job.job_id, raw_audio)

    updated_job = await job_store.get(job.job_id)
    assert updated_job.status == JobStatus.FAILED
    assert updated_job.error_code == "audio_too_short"


async def test_empty_audio_decode_error_fails_the_job():
    job_store = InMemoryJobStore()
    service = _build_service(job_store)

    job = await service.submit(b"")
    await service.run(job.job_id, b"")

    updated_job = await job_store.get(job.job_id)
    assert updated_job.status == JobStatus.FAILED
    assert updated_job.error_code == "decode_error"
