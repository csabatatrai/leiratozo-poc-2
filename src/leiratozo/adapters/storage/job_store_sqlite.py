"""Stub adapter — a valódi SQLite-alapú JobStore (SQLAlchemy modellek,
Postgres-re cserélhető connection-stringgel) a 3. fázisban készül el
(docs/phase1-terv.md 7. és 11. szakasz)."""
from __future__ import annotations


class SqliteJobStore:
    def __init__(self, **params: object) -> None:
        raise NotImplementedError(
            "SqliteJobStore 3. fázisos stub — ld. docs/phase1-terv.md 11. szakasz."
        )
