"""Passthrough aligner: feltételezi, hogy az ASR adapter már szó-szintű
időbélyeget adott (capabilities.supports_word_timestamps=True), és pusztán
időbeli átfedés alapján szórja szét a szavakat a diarizációs szegmensek
között — nincs szükség forced-alignment modellre. Ld. docs/phase1-terv.md
3. szakasz a `forced_alignment` fallback esetéért (3. fázis), amikor az ASR
csak szegmens-szintű időt ad."""
from __future__ import annotations

from leiratozo.domain.models import DiarizedSegment, TranscriptSegment, WordToken


class PassthroughAligner:
    name = "passthrough"

    async def align(
        self, words: list[WordToken], diarized_segments: list[DiarizedSegment]
    ) -> list[TranscriptSegment]:
        segments: list[TranscriptSegment] = []
        for diar in sorted(diarized_segments, key=lambda s: s.start):
            bucket = [w for w in words if diar.start <= (w.start + w.end) / 2 < diar.end]
            if not bucket:
                continue
            text = " ".join(w.word for w in bucket)
            avg_conf = sum(w.confidence for w in bucket) / len(bucket)
            segments.append(
                TranscriptSegment(
                    segment_id=diar.segment_id,
                    start=bucket[0].start,
                    end=bucket[-1].end,
                    text=text,
                    speaker_label=diar.speaker_label,
                    asr_confidence=round(avg_conf, 4),
                    is_final=True,
                    words=bucket,
                )
            )
        return segments
