"""LiveSessionService — az élő/streaming utat vezényli. Ld. docs/phase1-terv.md
4-5. szakasz az explicit batch/streaming és offline/élő diarizáció
kompromisszumokért, amiket ez az implementáció kódol.

2. fázis (skeleton) korlát: a per-chunk audio és a diarizer közötti pontos
illesztés (melyik bájtok tartoznak melyik ASR-eseményhez) a 3. fázisban, a
tényleges adapterek mellett finomodik — itt a session-szintű vezénylés és az
állapot-perzisztencia (reconnect) a bizonyítandó kontraktus, fake adapterekkel
tesztelve."""
from __future__ import annotations

from typing import AsyncIterator

from leiratozo.application.speaker_registration_service import SpeakerRegistrationService
from leiratozo.application.streaming_adapter import SlidingWindowStreamingAdapter
from leiratozo.domain.errors import SessionExpiredError, SessionNotFoundError
from leiratozo.domain.models import (
    AudioChunk,
    LiveDiarizationState,
    LiveSession,
    LiveSessionStatus,
    PartialOrFinalTranscript,
)
from leiratozo.ports.asr import TranscriptionEngine
from leiratozo.ports.diarization import DiarizationEngine
from leiratozo.ports.session_store import SessionStore


class LiveSessionService:
    def __init__(
        self,
        *,
        asr: TranscriptionEngine,
        diarizer: DiarizationEngine,
        speaker_registration: SpeakerRegistrationService,
        session_store: SessionStore,
        window_sec: float,
        overlap_sec: float,
        language: str | None = None,
    ) -> None:
        self._diarizer = diarizer
        self._speaker_registration = speaker_registration
        self._session_store = session_store
        self._language = language
        self._asr: TranscriptionEngine | SlidingWindowStreamingAdapter
        if asr.capabilities.supports_native_streaming:
            self._asr = asr
        else:
            self._asr = SlidingWindowStreamingAdapter(
                asr, window_sec=window_sec, overlap_sec=overlap_sec, language=language
            )

    async def open_session(self, session_id: str | None = None) -> LiveSession:
        session = LiveSession(session_id=session_id) if session_id else LiveSession()
        await self._session_store.create(session)
        await self._session_store.save_diarization_state(
            session.session_id, LiveDiarizationState(session_id=session.session_id)
        )
        return session

    async def resume_session(self, session_id: str) -> LiveSession:
        session = await self._session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Nincs élő session '{session_id}' azonosítóval")
        if session.status == LiveSessionStatus.EXPIRED:
            raise SessionExpiredError(f"A(z) '{session_id}' élő session lejárt")
        return session

    async def process_chunks(
        self, session_id: str, audio_chunks: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[PartialOrFinalTranscript]:
        async for event in self._asr.transcribe_stream(audio_chunks):
            diar_state = await self._session_store.get_diarization_state(session_id)
            placeholder_chunk = AudioChunk(samples=b"", sample_rate=16000, sequence=0, session_id=session_id)
            diarized, diar_state = await self._diarizer.diarize_live(placeholder_chunk, diar_state)
            await self._session_store.save_diarization_state(session_id, diar_state)
            speaker_label = diarized[0].speaker_label if diarized else event.segment.speaker_label
            segment = event.segment.model_copy(update={"speaker_label": speaker_label})
            await self._session_store.touch(session_id)
            yield event.model_copy(update={"segment": segment})

    async def close_session(self, session_id: str) -> None:
        session = await self._session_store.get(session_id)
        if session is not None:
            await self._session_store.update(session.model_copy(update={"status": LiveSessionStatus.CLOSED}))
