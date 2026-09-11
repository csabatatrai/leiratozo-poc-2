"""Futásidejű, szanitizált config-introspekció — docs/phase1-terv.md 9. és 14.
szakasz. Csak aktív adapter-neveket/verziókat ad vissza, titkokat sosem."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/v1", tags=["config"])


@router.get("/config")
async def get_runtime_config(request: Request) -> dict:
    services = request.app.state.services
    cfg = services.config
    return {
        "schema_version": "1.0",
        "models": {
            "vad": {"adapter": cfg.models.vad.adapter, "name": services.vad.name, "version": services.vad.version},
            "asr": {"adapter": cfg.models.asr.adapter, "name": services.asr.name, "version": services.asr.version},
            "diarization_batch": {
                "adapter": cfg.models.diarization.batch_adapter,
                "name": services.diarizer_batch.name,
                "version": services.diarizer_batch.version,
            },
            "diarization_live": {
                "adapter": cfg.models.diarization.live_adapter,
                "name": services.diarizer_live.name,
                "version": services.diarizer_live.version,
            },
            "speaker_embedding": {
                "adapter": cfg.models.speaker_embedding.adapter,
                "name": services.speaker_embedding.name,
                "version": services.speaker_embedding.version,
            },
        },
        "device": cfg.device.default,
        "streaming": {"transport": cfg.streaming.transport, "chunk_ms": cfg.streaming.chunk_ms},
    }
