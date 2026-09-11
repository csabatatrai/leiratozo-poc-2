"""Élő streaming WebSocket végpont — docs/phase1-terv.md 4-5., 9. szakasz. 2.
fázis (skeleton): a vezénylés fake adapterekkel végponttól-végpontig működik;
a backpressure/reconnect finomítása 3. fázisban valódi adapterekkel folytatódik."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from leiratozo.domain.models import AudioChunk

router = APIRouter(prefix="/v1/live", tags=["live"])


@router.websocket("/{session_id}")
async def live_session(websocket: WebSocket, session_id: str) -> None:
    services = websocket.app.state.services
    await websocket.accept()
    existing = await services.session_store.get(session_id)
    if existing is None:
        await services.live_service.open_session(session_id)

    async def _receive_chunks():
        sequence = 0
        while True:
            try:
                data = await websocket.receive_bytes()
            except WebSocketDisconnect:
                return
            yield AudioChunk(samples=data, sample_rate=16000, sequence=sequence, session_id=session_id)
            sequence += 1

    try:
        async for event in services.live_service.process_chunks(session_id, _receive_chunks()):
            await websocket.send_json(
                {
                    "session_id": event.session_id,
                    "is_final": event.is_final,
                    "segment": event.segment.model_dump(mode="json"),
                }
            )
    finally:
        await services.live_service.close_session(session_id)
