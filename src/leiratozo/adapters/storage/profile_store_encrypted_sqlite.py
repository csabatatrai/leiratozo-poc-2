"""Valódi, mezőszinten titkosított SQLite ProfileStore — a GDPR-kritikus adapter
(5. kemény megkötés, docs/phase1-terv.md 6. szakasz).

- `profile_id` UUID (nem beszédes PII).
- `display_name` és az embedding-vektor Fernet-tel (AES-128-CBC + HMAC,
  `cryptography` csomag) titkosítva kerül a nyugalmi tárolóba — a nyers .db
  fájl bájtszinten sosem tartalmazza a plaintext értéket.
- A kulcsot a `PROFILE_ENCRYPTION_KEY`-szerű env-változóból olvassuk (a nevét a
  configból kapjuk, `encryption_key_env` paraméterként) — HIÁNYZÓ kulcs esetén
  world-readable hibával, NEM csendes plaintext-fallback-kel bukik.
- `delete()` HARD delete (DELETE FROM), nem soft-flag — right-to-erasure.
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
from pathlib import Path

import aiosqlite

from leiratozo.domain.models import Embedding, SpeakerProfile, utcnow

_SCHEMA = """
CREATE TABLE IF NOT EXISTS speaker_profiles (
    profile_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    display_name_enc TEXT,
    embedding_enc TEXT NOT NULL
);
"""


class ProfileStoreConfigError(RuntimeError):
    """Hiányzó/érvénytelen titkosítási kulcs — fail-fast, nem eshet vissza
    plaintext tárolásra."""


def _load_fernet(encryption_key_env: str):
    from cryptography.fernet import Fernet

    raw_key = os.environ.get(encryption_key_env)
    if not raw_key:
        raise ProfileStoreConfigError(
            f"A '{encryption_key_env}' env-változó (titkosítási kulcs) nincs beállítva — "
            "a speaker-profil storage NEM indulhat el titkosítás nélkül (GDPR, "
            "docs/phase1-terv.md 6. szakasz). Generálj egyet: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
    except Exception as exc:
        raise ProfileStoreConfigError(
            f"A '{encryption_key_env}' érvénytelen Fernet-kulcs (32 bájt, urlsafe-base64): {exc}"
        ) from exc


class EncryptedSqliteProfileStore:
    def __init__(
        self,
        *,
        path: str = "/data/profiles.db",
        encryption_key_env: str = "PROFILE_ENCRYPTION_KEY",
        **_extra: object,
    ) -> None:
        self._fernet = _load_fernet(encryption_key_env)
        self._path = path
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.executescript(_SCHEMA)

    def _encrypt_str(self, value: str) -> str:
        return base64.urlsafe_b64encode(self._fernet.encrypt(value.encode())).decode()

    def _decrypt_str(self, token: str) -> str:
        return self._fernet.decrypt(base64.urlsafe_b64decode(token)).decode()

    async def save(self, profile: SpeakerProfile, embedding: Embedding) -> None:
        display_name_enc = self._encrypt_str(profile.display_name) if profile.display_name else None
        embedding_json = json.dumps({"vector": list(embedding.vector), "dim": embedding.dim})
        embedding_enc = self._encrypt_str(embedding_json)
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT INTO speaker_profiles (profile_id, created_at, display_name_enc, embedding_enc) "
                "VALUES (?, ?, ?, ?)",
                (profile.profile_id, profile.created_at.isoformat(), display_name_enc, embedding_enc),
            )
            await conn.commit()

    async def list_profiles(self) -> list[SpeakerProfile]:
        async with aiosqlite.connect(self._path) as conn:
            async with conn.execute(
                "SELECT profile_id, created_at, display_name_enc FROM speaker_profiles"
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            SpeakerProfile(
                profile_id=row[0],
                created_at=_parse_dt(row[1]),
                display_name=self._decrypt_str(row[2]) if row[2] else None,
            )
            for row in rows
        ]

    async def list_with_embeddings(self) -> list[tuple[SpeakerProfile, Embedding]]:
        async with aiosqlite.connect(self._path) as conn:
            async with conn.execute(
                "SELECT profile_id, created_at, display_name_enc, embedding_enc FROM speaker_profiles"
            ) as cursor:
                rows = await cursor.fetchall()
        result: list[tuple[SpeakerProfile, Embedding]] = []
        for profile_id, created_at, display_name_enc, embedding_enc in rows:
            profile = SpeakerProfile(
                profile_id=profile_id,
                created_at=_parse_dt(created_at),
                display_name=self._decrypt_str(display_name_enc) if display_name_enc else None,
            )
            payload = json.loads(self._decrypt_str(embedding_enc))
            embedding = Embedding(vector=tuple(payload["vector"]), dim=payload["dim"])
            result.append((profile, embedding))
        return result

    async def delete(self, profile_id: str) -> bool:
        async with aiosqlite.connect(self._path) as conn:
            cursor = await conn.execute("DELETE FROM speaker_profiles WHERE profile_id = ?", (profile_id,))
            await conn.commit()
            return cursor.rowcount > 0


def _parse_dt(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)
