"""Valódi (fájlalapú) SQLite JobStore/SessionStore tesztek — docs/phase1-terv.md
11. szakasz, 5. modul (API-réteg: batch job-modell)."""
from __future__ import annotations

import pytest

from leiratozo.adapters.storage.job_store_sqlite import SqliteJobStore
from leiratozo.adapters.storage.session_store_sqlite import SqliteSessionStore
from leiratozo.contracts.transcript_schema import ModelInfo, SingleModelInfo, TranscriptDocument
from leiratozo.domain.errors import SessionNotFoundError
from leiratozo.domain.models import JobStatus, LiveDiarizationState, LiveSession, TranscriptJob


@pytest.fixture
def job_store(tmp_path) -> SqliteJobStore:
    return SqliteJobStore(url=f"sqlite:///{tmp_path}/jobs.db")


@pytest.fixture
def session_store(tmp_path) -> SqliteSessionStore:
    return SqliteSessionStore(url=f"sqlite:///{tmp_path}/sessions.db")


async def test_job_create_get_update_round_trip(job_store: SqliteJobStore):
    job = TranscriptJob(language="hu")
    await job_store.create(job)

    fetched = await job_store.get(job.job_id)
    assert fetched.job_id == job.job_id
    assert fetched.status == JobStatus.QUEUED

    updated = fetched.model_copy(update={"status": JobStatus.DONE})
    await job_store.update(updated)

    reread = await job_store.get(job.job_id)
    assert reread.status == JobStatus.DONE


async def test_job_get_unknown_raises_keyerror(job_store: SqliteJobStore):
    with pytest.raises(KeyError):
        await job_store.get("does-not-exist")


async def test_job_result_round_trip_survives_reload(tmp_path):
    db_url = f"sqlite:///{tmp_path}/jobs2.db"
    store_a = SqliteJobStore(url=db_url)
    job = TranscriptJob()
    await store_a.create(job)

    info = SingleModelInfo(name="fake", version="0.0.1")
    document = TranscriptDocument(
        job_id=job.job_id,
        mode="batch",
        language="hu",
        audio_duration_sec=1.0,
        audio_sample_rate=16000,
        models=ModelInfo(vad=info, asr=info, diarization=info, speaker_embedding=info),
    )
    await store_a.save_result(job.job_id, document)

    # Új SqliteJobStore példány (más "process" szimulálása) -> a fájlból olvas.
    store_b = SqliteJobStore(url=db_url)
    reread = await store_b.get_result(job.job_id)
    assert reread is not None
    assert reread.schema_version == "1.0"
    assert reread.job_id == job.job_id


async def test_missing_result_is_none(job_store: SqliteJobStore):
    assert await job_store.get_result("no-such-job") is None


async def test_session_create_get_update(session_store: SqliteSessionStore):
    session = LiveSession()
    await session_store.create(session)

    fetched = await session_store.get(session.session_id)
    assert fetched is not None
    assert fetched.session_id == session.session_id

    assert await session_store.get("does-not-exist") is None


async def test_session_touch_updates_last_activity(session_store: SqliteSessionStore):
    session = LiveSession()
    await session_store.create(session)

    await session_store.touch(session.session_id)
    fetched = await session_store.get(session.session_id)
    assert fetched.last_activity_at >= session.last_activity_at


async def test_session_touch_unknown_raises(session_store: SqliteSessionStore):
    with pytest.raises(SessionNotFoundError):
        await session_store.touch("does-not-exist")


async def test_diarization_state_round_trip(session_store: SqliteSessionStore):
    state = LiveDiarizationState(session_id="sess-1", payload={"chunk_count": 3, "speakers": ["S1", "S2"]})
    await session_store.save_diarization_state("sess-1", state)

    reread = await session_store.get_diarization_state("sess-1")
    assert reread.payload == {"chunk_count": 3, "speakers": ["S1", "S2"]}


async def test_diarization_state_defaults_to_empty_payload(session_store: SqliteSessionStore):
    state = await session_store.get_diarization_state("never-seen-session")
    assert state.session_id == "never-seen-session"
    assert state.payload == {}
