"""Stub adapter — a valódi, mezőszinten titkosított (AES-GCM, `cryptography`
csomag) SQLite ProfileStore a 3. fázisban készül el. Ez a GDPR-kritikus adapter
(5. kemény megkötés, docs/phase1-terv.md 6. szakasz): a kulcsot a
PROFILE_ENCRYPTION_KEY env-változóból kell olvasnia, sosem az image-be sütve."""
from __future__ import annotations


class EncryptedSqliteProfileStore:
    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "EncryptedSqliteProfileStore 3. fázisos stub — ld. docs/phase1-terv.md 6. és "
            "11. szakasz."
        )
