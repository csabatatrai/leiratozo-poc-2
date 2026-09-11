"""Determinisztikus fake diarizációs adapterek: batch módban VAD-szegmensenként
váltogatja a beszélőt; élő módban session-ön belüli, egyszerű round-robin
klaszterezést szimulál a `state.payload`-ban tárolt számlálóval."""
from __future__ import annotations

from leiratozo.domain.models import AudioBuffer, AudioChunk, DiarizedSegment, LiveDiarizationState, VadSegment, new_id


class FakeBatchDiarizer:
    name = "fake-diarizer-batch"
    version = "0.0.1"
    mode = "batch"

    def __init__(self, *, min_speakers: int = 1, max_speakers: int = 8) -> None:
        self._max_speakers = max(1, max_speakers)

    async def diarize_batch(self, audio: AudioBuffer, vad_segments: list[VadSegment]) -> list[DiarizedSegment]:
        source = vad_segments or [VadSegment(start=0.0, end=audio.duration_sec)]
        segments = []
        for i, vad in enumerate(source):
            label = f"S{(i % self._max_speakers) + 1}"
            segments.append(
                DiarizedSegment(segment_id=new_id("seg-"), start=vad.start, end=vad.end, speaker_label=label)
            )
        return segments

    async def diarize_live(self, audio_chunk: AudioChunk, state: LiveDiarizationState):
        raise NotImplementedError("FakeBatchDiarizer csak diarize_batch-et támogat (mode=batch)")


class FakeLiveDiarizer:
    name = "fake-diarizer-live"
    version = "0.0.1"
    mode = "live_approx"

    def __init__(self, *, min_speakers: int = 1, max_speakers: int = 8) -> None:
        self._max_speakers = max(1, max_speakers)

    async def diarize_batch(self, audio: AudioBuffer, vad_segments: list[VadSegment]):
        raise NotImplementedError("FakeLiveDiarizer csak diarize_live-ot támogat (mode=live_approx)")

    async def diarize_live(self, audio_chunk: AudioChunk, state: LiveDiarizationState):
        count = state.payload.get("chunk_count", 0)
        label = f"S{(count % self._max_speakers) + 1}"
        state.payload["chunk_count"] = count + 1
        segment = DiarizedSegment(segment_id=new_id("live-seg-"), start=0.0, end=0.0, speaker_label=label)
        return [segment], state
