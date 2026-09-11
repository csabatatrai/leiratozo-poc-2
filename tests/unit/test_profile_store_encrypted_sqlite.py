"""EncryptedSqliteProfileStore tesztek — a legfontosabb a nyers .db fájl
bájtszintű ellenőrzése: a plaintext display_name/embedding-érték SOSEM
jelenhet meg benne (GDPR, 5. kemény megkötés, docs/phase1-terv.md 6. szakasz)."""
from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

from leiratozo.adapters.storage.profile_store_encrypted_sqlite import (
    EncryptedSqliteProfileStore,
    ProfileStoreConfigError,
)
from leiratozo.domain.models import Embedding, SpeakerProfile

ENV_VAR = "PROFILE_ENCRYPTION_KEY_TEST"


@pytest.fixture
def encryption_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv(ENV_VAR, key)
    return key


@pytest.fixture
def store(tmp_path, encryption_key: str) -> EncryptedSqliteProfileStore:
    return EncryptedSqliteProfileStore(path=str(tmp_path / "profiles.db"), encryption_key_env=ENV_VAR)


async def test_missing_encryption_key_fails_fast(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(ProfileStoreConfigError):
        EncryptedSqliteProfileStore(path=str(tmp_path / "profiles.db"), encryption_key_env=ENV_VAR)


async def test_invalid_encryption_key_fails_fast(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(ENV_VAR, "not-a-valid-fernet-key")
    with pytest.raises(ProfileStoreConfigError):
        EncryptedSqliteProfileStore(path=str(tmp_path / "profiles.db"), encryption_key_env=ENV_VAR)


async def test_save_list_round_trip(store: EncryptedSqliteProfileStore):
    profile = SpeakerProfile(display_name="Kovács Anna")
    embedding = Embedding(vector=(0.1, -0.2, 0.3), dim=3)

    await store.save(profile, embedding)

    profiles = await store.list_profiles()
    assert len(profiles) == 1
    assert profiles[0].profile_id == profile.profile_id
    assert profiles[0].display_name == "Kovács Anna"

    with_embeddings = await store.list_with_embeddings()
    assert with_embeddings[0][1].vector == pytest.approx((0.1, -0.2, 0.3))


async def test_delete_is_hard_delete(store: EncryptedSqliteProfileStore):
    profile = SpeakerProfile(display_name="Teszt Elek")
    await store.save(profile, Embedding(vector=(1.0,), dim=1))

    assert await store.delete(profile.profile_id) is True
    assert await store.list_profiles() == []
    assert await store.delete(profile.profile_id) is False  # már nincs mit törölni


async def test_raw_db_file_never_contains_plaintext_display_name_or_embedding(
    store: EncryptedSqliteProfileStore, tmp_path
):
    secret_name = "Teljesen-Egyedi-Titkos-Nev-Marker-9f3e"
    embedding = Embedding(vector=(0.123456, -0.987654, 0.555555), dim=3)
    profile = SpeakerProfile(display_name=secret_name)
    await store.save(profile, embedding)

    db_path = tmp_path / "profiles.db"
    raw_bytes = db_path.read_bytes()

    # A plaintext display_name egyáltalán nem jelenhet meg a fájlban.
    assert secret_name.encode() not in raw_bytes
    # Az embedding-értékek szöveges (json-szerű) reprezentációja se jelenhet meg.
    assert b"0.123456" not in raw_bytes
    assert b"-0.987654" not in raw_bytes
    # A profile_id (nem PII, nem titkosított) viszont igenis megjelenhet nyersen.
    assert profile.profile_id.encode() in raw_bytes


async def test_profile_id_is_not_derived_from_display_name(store: EncryptedSqliteProfileStore):
    profile = SpeakerProfile(display_name="Nagy Péter")
    await store.save(profile, Embedding(vector=(1.0, 2.0), dim=2))
    assert "Nagy" not in profile.profile_id
    assert "Péter" not in profile.profile_id
