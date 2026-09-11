"""In-memory JobStore / SessionStore / ProfileStore fake-ek tesztekhez és a
skeleton pipeline demózásához.

FIGYELEM: az InMemoryProfileStore NEM titkosít és NEM perzisztens — kizárólag
teszt/skeleton célra, sosem élesben. Az éles ProfileStore-nak az
encrypted_sqlite adapternek kell lennie (3. fázis, GDPR — docs/phase1-terv.md
6. szakasz)."""
from __future__ import annotations

from leiratozo.contracts.transcript_schema import TranscriptDocument
from leiratozo.domain.errors import SessionNotFoundError
from leiratozo.domain.models import Embedding, LiveDiarizationState, LiveSession, SpeakerProfile, TranscriptJob, utcnow


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, TranscriptJob] = {}
        self._results: dict[str, TranscriptDocument] = {}

    async def create(self, job: TranscriptJob) -> None:
        self._jobs[job.job_id] = job

    async def get(self, job_id: str) -> TranscriptJob:
        return self._jobs[job_id]

    async def update(self, job: TranscriptJob) -> None:
        self._jobs[job.job_id] = job

    async def save_result(self, job_id: str, document: TranscriptDocument) -> None:
        self._results[job_id] = document

    async def get_result(self, job_id: str) -> TranscriptDocument | None:
        return self._results.get(job_id)


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}
        self._diar_state: dict[str, LiveDiarizationState] = {}

    async def create(self, session: LiveSession) -> None:
        self._sessions[session.session_id] = session

    async def get(self, session_id: str) -> LiveSession | None:
        return self._sessions.get(session_id)

    async def update(self, session: LiveSession) -> None:
        self._sessions[session.session_id] = session

    async def touch(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        self._sessions[session_id] = session.model_copy(update={"last_activity_at": utcnow()})

    async def save_diarization_state(self, session_id: str, state: LiveDiarizationState) -> None:
        self._diar_state[session_id] = state

    async def get_diarization_state(self, session_id: str) -> LiveDiarizationState:
        return self._diar_state.setdefault(session_id, LiveDiarizationState(session_id=session_id))


class InMemoryProfileStore:
    def __init__(self) -> None:
        self._profiles: dict[str, tuple[SpeakerProfile, Embedding]] = {}

    async def save(self, profile: SpeakerProfile, embedding: Embedding) -> None:
        self._profiles[profile.profile_id] = (profile, embedding)

    async def list_profiles(self) -> list[SpeakerProfile]:
        return [p for p, _ in self._profiles.values()]

    async def list_with_embeddings(self) -> list[tuple[SpeakerProfile, Embedding]]:
        return list(self._profiles.values())

    async def delete(self, profile_id: str) -> bool:
        return self._profiles.pop(profile_id, None) is not None
