"""Strukturált JSON logolás. SOHA ne kerüljön logba nyers audio, embedding,
display_name vagy más PII (docs/phase1-terv.md 6. szakasz) — a formatter egy
explicit tiltólistát alkalmaz az `extra_fields`-re. Hívd meg egyszer,
folyamatindításkor: `configure_logging(...)`."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_FORBIDDEN_KEYS = {"audio", "embedding", "display_name", "raw_bytes", "samples", "vector"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            payload["correlation_id"] = correlation_id
        extra = getattr(record, "extra_fields", None)
        if extra:
            for key, value in extra.items():
                if key in _FORBIDDEN_KEYS:
                    continue
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)
