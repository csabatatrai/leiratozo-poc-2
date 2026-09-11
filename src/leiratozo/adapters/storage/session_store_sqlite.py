"""Valódi SQLite-alapú SessionStore — élő session állapot + per-adapter
diarizációs állapot (reconnect-támogatáshoz, docs/phase1-terv.md 10. szakasz).

Korlát: a `LiveDiarizationState.payload`-ot JSON-ként perzisztáljuk. Ez minden
JSON-szerializálható adapter-állapotra (dict-ekre, listákra, primitívekre) jó —
ha egy jövőbeli diarizációs adapter nem-JSON-szerializálható objektumot tenne a
payloadba (pl. egy natív klaszterező-objektumot), azt az adapternek magának kell
JSON-kompatibilis formára (pl. szerializált súlyokra) redukálnia, mielőtt a
state-et visszaadja."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import aiosqlite

from leiratozo.adapters.storage.job_store_sqlite import _resolve_path
from leiratozo.domain.errors import SessionNotFoundError
from leiratozo.domain.models import LiveDiarizationState, LiveSession, utcnow

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS diarization_state (
    session_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
"""


class SqliteSessionStore:
    def __init__(self, *, url: str = "sqlite:////data/sessions.db", **_extra: object) -> None:
        self._path = _resolve_path(url)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.executescript(_SCHEMA)

    async def create(self, session: LiveSession) -> None:
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT INTO sessions (session_id, data) VALUES (?, ?)",
                (session.session_id, session.model_dump_json()),
            )
            await conn.commit()

    async def get(self, session_id: str) -> LiveSession | None:
        async with aiosqlite.connect(self._path) as conn:
            async with conn.execute(
                "SELECT data FROM sessions WHERE session_id = ?", (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
        return LiveSession.model_validate_json(row[0]) if row else None

    async def update(self, session: LiveSession) -> None:
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT INTO sessions (session_id, data) VALUES (?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET data = excluded.data",
                (session.session_id, session.model_dump_json()),
            )
            await conn.commit()

    async def touch(self, session_id: str) -> None:
        session = await self.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        await self.update(session.model_copy(update={"last_activity_at": utcnow()}))

    async def save_diarization_state(self, session_id: str, state: LiveDiarizationState) -> None:
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT INTO diarization_state (session_id, payload) VALUES (?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET payload = excluded.payload",
                (session_id, json.dumps(state.payload)),
            )
            await conn.commit()

    async def get_diarization_state(self, session_id: str) -> LiveDiarizationState:
        async with aiosqlite.connect(self._path) as conn:
            async with conn.execute(
                "SELECT payload FROM diarization_state WHERE session_id = ?", (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
        payload = json.loads(row[0]) if row else {}
        return LiveDiarizationState(session_id=session_id, payload=payload)
