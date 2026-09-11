"""BatchTranscriptionService — a batch csővezetéket vezényli (docs/phase1-terv.md
12.1. szekvenciadiagram). Kizárólag portokon dolgozik, sosem importál konkrét
adaptert."""
from __future__ import annotations

from leiratozo.application.speaker_registration_service import SpeakerRegistrationService
from leiratozo.contracts.transcript_schema import ModelInfo, TranscriptDocument
from leiratozo.domain.errors import DecodeError, TooShortAudioError
from leiratozo.domain.models import JobStatus, TranscriptionHints, TranscriptJob, TranscriptSegment
from leiratozo.ports.aligner import Aligner
from leiratozo.ports.asr import TranscriptionEngine
from leiratozo.ports.audio_decoder import AudioDecoder
from leiratozo.ports.diarization import DiarizationEngine
from leiratozo.ports.job_store import JobStore
from leiratozo.ports.vad import VoiceActivityDetector

MIN_AUDIO_DURATION_SEC = 0.3


class BatchTranscriptionService:
    def __init__(
        self,
        *,
        audio_decoder: AudioDecoder,
        vad: VoiceActivityDetector,
        asr: TranscriptionEngine,
        diarizer: DiarizationEngine,
        aligner: Aligner,
        speaker_registration: SpeakerRegistrationService,
        job_store: JobStore,
        language: str | None = None,
    ) -> None:
        self._audio_decoder = audio_decoder
        self._vad = vad
        self._asr = asr
        self._diarizer = diarizer
        self._aligner = aligner
        self._speaker_registration = speaker_registration
        self._job_store = job_store
        self._language = language

    async def submit(self, raw_audio: bytes, filename_hint: str | None = None) -> TranscriptJob:
        job = TranscriptJob(language=self._language)
        await self._job_store.create(job)
        return job

    async def run(self, job_id: str, raw_audio: bytes, filename_hint: str | None = None) -> None:
        """2. fázisban szinkron-inline fut (nincs még queue-worker, ld. 3. fázis:
        Redis/arq). Az API réteg ezt közvetlenül hívja a POST /v1/jobs kérésből."""
        job = await self._job_store.get(job_id)
        job = job.model_copy(update={"status": JobStatus.RUNNING})
        await self._job_store.update(job)
        try:
            document = await self._process(job, raw_audio, filename_hint)
            await self._job_store.save_result(job_id, document)
            job = job.model_copy(update={"status": JobStatus.DONE})
        except (DecodeError, TooShortAudioError) as exc:
            job = job.model_copy(
                update={
                    "status": JobStatus.FAILED,
                    "error_code": exc.error_code,
                    "error_message": str(exc),
                }
            )
        await self._job_store.update(job)

    async def _process(
        self, job: TranscriptJob, raw_audio: bytes, filename_hint: str | None
    ) -> TranscriptDocument:
        audio = await self._audio_decoder.decode(raw_audio, filename_hint=filename_hint)
        if audio.duration_sec < MIN_AUDIO_DURATION_SEC:
            raise TooShortAudioError(f"Az audio hossza ({audio.duration_sec:.2f}s) a minimum alatt van")

        vad_segments = await self._vad.detect_speech(audio)
        words = await self._asr.transcribe_batch(
            audio, language=job.language, hints=TranscriptionHints(language=job.language)
        )
        diarized_segments = await self._diarizer.diarize_batch(audio, vad_segments)
        segments: list[TranscriptSegment] = await self._aligner.align(words, diarized_segments)

        matches = await self._speaker_registration.match_segments(audio, diarized_segments)
        enriched_segments = [
            segment.model_copy(
                update={
                    "known_speaker_id": matches[segment.segment_id].known_speaker_id,
                    "speaker_match_confidence": matches[segment.segment_id].confidence,
                }
            )
            if segment.segment_id in matches
            else segment
            for segment in segments
        ]

        return TranscriptDocument(
            job_id=job.job_id,
            session_id=None,
            mode="batch",
            language=job.language or "auto",
            audio_duration_sec=audio.duration_sec,
            audio_sample_rate=audio.sample_rate,
            audio_source_format=audio.source_format,
            models=ModelInfo.collect(
                vad=self._vad,
                asr=self._asr,
                diarization=self._diarizer,
                speaker_embedding=self._speaker_registration.embedding_engine,
            ),
            segments=enriched_segments,
        )
