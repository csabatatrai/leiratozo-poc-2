"""Valódi SQLite-alapú JobStore. Kulcs-érték táblákként tárolja a job-okat és
eredményeket (JSON blobként) — nincs szükség ORM-re ezen a skálán (docs/phase1-terv.md
7. szakasz: "kis-közepes, single-node"). Postgres-re cserélhető később ugyanazon
Protocol mögött, kódmódosítás nélkül máshol a rendszerben."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite

from leiratozo.contracts.transcript_schema import TranscriptDocument
from leiratozo.domain.models import TranscriptJob

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_results (
    job_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
"""


def _resolve_path(url: str) -> str:
    """A `storage.job_store_url` egy `sqlite:////abs/path.db` connection-string-
    szerű alak lehet (12-factor konvenció) — ha nincs `sqlite:` prefix, nyers
    fájlútvonalként kezeljük."""
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///") :] or ":memory:"
    if url.startswith("sqlite://"):
        return url[len("sqlite://") :] or ":memory:"
    return url


class SqliteJobStore:
    def __init__(self, *, url: str = "sqlite:////data/jobs.db", **_extra: object) -> None:
        self._path = _resolve_path(url)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        # Séma-inicializálás szinkron, mert az __init__ (plugin_registry.instantiate)
        # nem async — az aiosqlite-hoz csak a tényleges lekérdezéseknél nyúlunk.
        with sqlite3.connect(self._path) as conn:
            conn.executescript(_SCHEMA)

    async def create(self, job: TranscriptJob) -> None:
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT INTO jobs (job_id, data) VALUES (?, ?)",
                (job.job_id, job.model_dump_json()),
            )
            await conn.commit()

    async def get(self, job_id: str) -> TranscriptJob:
        async with aiosqlite.connect(self._path) as conn:
            async with conn.execute("SELECT data FROM jobs WHERE job_id = ?", (job_id,)) as cursor:
                row = await cursor.fetchone()
        if row is None:
            raise KeyError(job_id)
        return TranscriptJob.model_validate_json(row[0])

    async def update(self, job: TranscriptJob) -> None:
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT INTO jobs (job_id, data) VALUES (?, ?) "
                "ON CONFLICT(job_id) DO UPDATE SET data = excluded.data",
                (job.job_id, job.model_dump_json()),
            )
            await conn.commit()

    async def save_result(self, job_id: str, document: TranscriptDocument) -> None:
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT INTO job_results (job_id, data) VALUES (?, ?) "
                "ON CONFLICT(job_id) DO UPDATE SET data = excluded.data",
                (job_id, document.model_dump_json()),
            )
            await conn.commit()

    async def get_result(self, job_id: str) -> TranscriptDocument | None:
        async with aiosqlite.connect(self._path) as conn:
            async with conn.execute("SELECT data FROM job_results WHERE job_id = ?", (job_id,)) as cursor:
                row = await cursor.fetchone()
        return TranscriptDocument.model_validate_json(row[0]) if row else None
