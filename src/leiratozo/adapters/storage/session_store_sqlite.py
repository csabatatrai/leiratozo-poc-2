"""Stub adapter — a valódi SQLite-alapú SessionStore a 3. fázisban készül el
(docs/phase1-terv.md 11. szakasz)."""
from __future__ import annotations


class SqliteSessionStore:
    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "SqliteSessionStore 3. fázisos stub — ld. docs/phase1-terv.md 11. szakasz."
        )
