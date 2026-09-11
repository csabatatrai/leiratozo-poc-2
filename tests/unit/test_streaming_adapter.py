"""A SlidingWindowStreamingAdapter (batch->streaming közelítés) tesztjei —
docs/phase1-terv.md 4. szakasz."""
from __future__ import annotations

import pytest

from leiratozo.adapters.asr.fake import FakeTranscriptionEngine
from leiratozo.application.streaming_adapter import SlidingWindowStreamingAdapter
from leiratozo.domain.models import AudioChunk, EngineCapabilities, WordToken


def test_wrapping_a_native_streaming_engine_raises():
    class NativeStreamingFake(FakeTranscriptionEngine):
        capabilities = EngineCapabilities(supports_word_timestamps=True, supports_native_streaming=True)

    with pytest.raises(ValueError):
        SlidingWindowStreamingAdapter(NativeStreamingFake())


async def _audio_chunks(session_id: str, n: int, sample_rate: int = 16000, chunk_ms: int = 500):
    n_bytes = int(sample_rate * (chunk_ms / 1000) * 2)
    for i in range(n):
        yield AudioChunk(samples=b"\x00" * n_bytes, sample_rate=sample_rate, sequence=i, session_id=session_id)


async def test_emits_events_with_is_final_flag_set():
    engine = FakeTranscriptionEngine(fixed_text="egy ketto harom negy ot hat het nyolc kilenc tiz")
    adapter = SlidingWindowStreamingAdapter(engine, window_sec=1.0, overlap_sec=0.25)

    events = [event async for event in adapter.transcribe_stream(_audio_chunks("sess-1", n=6))]

    assert events, "legalább egy eseményt kell emittálnia"
    assert all(isinstance(e.is_final, bool) for e in events)
    assert events[-1].is_final is True  # az utolsó, lezáró flush mindig final
    assert all(e.session_id == "sess-1" for e in events)


class _CoarseSegmentFakeEngine:
    """Egy nagy-szemcsés (szegmens-szintű, NEM szó-szintű) ASR-t szimulál —
    pontosan azt a valós hibát reprodukálja, amit a RemoteHttpAsrEngine élő
    (WebSocket, valódi távoli végponttal futtatott) manuális tesztje talált:
    egyetlen "szó" nála egy egész mondatnyi szöveg (ld. docs/manual_test_notes.md).
    Egy darabszám-alapú overlap-heurisztika ilyen kevés, nagy tokennél szinte
    SOSEM konfirmált volna semmit a stream vége előtt."""

    name = "coarse-fake"
    version = "0.0.1"
    capabilities = EngineCapabilities(supports_word_timestamps=True, supports_native_streaming=False)

    async def transcribe_batch(self, audio, *, language, hints):
        n_segments = max(1, int(audio.duration_sec))
        return [
            WordToken(word=f"segment{i}", start=float(i), end=float(i + 1), confidence=0.9)
            for i in range(n_segments)
        ]


async def test_coarse_segment_engine_confirms_before_stream_end():
    """Regressziós teszt egy valós, éles hibára: szegmens-szintű ASR-nél az
    IDŐALAPÚ (nem darabszám-alapú) stabil/bizonytalan szétválasztásnak már a
    stream vége ELŐTT is kell legalább egy is_final=True eseményt adnia."""
    engine = _CoarseSegmentFakeEngine()
    adapter = SlidingWindowStreamingAdapter(engine, window_sec=2.0, overlap_sec=0.5)

    events = [event async for event in adapter.transcribe_stream(_audio_chunks("sess-2", n=10, chunk_ms=500))]

    final_events = [e for e in events if e.is_final]
    assert len(final_events) > 1, (
        "csak a stream-lezáró flush adott is_final=True-t — ez épp az a regresszió, "
        "amit a régi darabszám-alapú heurisztika okozott coarse-grained ASR-eknél"
    )


async def test_confirmed_content_is_never_re_emitted_after_buffer_shrinks():
    """Regressziós teszt egy élesben ténylegesen megfigyelt hibára: a puffer
    flush utáni zsugorítása korábban egy fix "overlap" farkot tartott meg, és
    a következő hívás a zsugorodott pufferre ÚJRA t=0-tól transzkribált —
    emiatt a már megerősített tartalom (globális időbélyeggel) DUPLIKÁLTAN
    jelent meg a kimeneten (ld. docs/manual_test_notes.md, valós élő teszt egy
    távoli ASR-végponttal). Itt azt ellenőrizzük, hogy a végleges (is_final=True)
    szavak globális (start, end) időintervallumai sosem fedik át/ismétlik
    egymást."""
    engine = _CoarseSegmentFakeEngine()
    adapter = SlidingWindowStreamingAdapter(engine, window_sec=2.0, overlap_sec=0.5)

    events = [event async for event in adapter.transcribe_stream(_audio_chunks("sess-3", n=14, chunk_ms=500))]

    confirmed_ranges = [
        (w.start, w.end) for e in events if e.is_final for w in e.segment.words
    ]
    assert confirmed_ranges, "kellett volna legalább egy megerősített szónak lennie"
    assert len(confirmed_ranges) == len(set(confirmed_ranges)), (
        f"duplikált (start, end) időintervallum a végleges szavak között: {confirmed_ranges}"
    )
    # Időrendben, átfedés nélkül kell haladniuk (a második kezdete >= az első vége).
    for (start_a, end_a), (start_b, _end_b) in zip(confirmed_ranges, confirmed_ranges[1:]):
        assert start_b >= end_a, f"átfedő/visszalépő időintervallum: ({start_a},{end_a}) -> ({start_b},...)"


class _NeverStabilizingFakeEngine:
    """Legrosszabb eset: MINDIG egyetlen, a teljes (aktuális) puffert lefedő
    "szót" ad vissza — időalapú stabil-küszöb alapján ez a `max_buffer_sec`
    biztonsági korlát NÉLKÜL sosem konfirmálna semmit, tehát a puffer
    flush-onként nőne. Pontosan ezt a mintát figyeltem meg élesben egy távoli,
    szegmens-szintű ASR-t egy egész ablakot lefedő válasszal (ld. modul
    docstring) — a hosszan növekvő puffer végül kapcsolat-timeouthoz és a
    mögöttes Whisper-modell ismétlődés-hallucinációjához vezetett."""

    name = "never-stabilizing-fake"
    version = "0.0.1"
    capabilities = EngineCapabilities(supports_word_timestamps=True, supports_native_streaming=False)

    async def transcribe_batch(self, audio, *, language, hints):
        return [WordToken(word="blob", start=0.0, end=audio.duration_sec, confidence=0.9)]


async def test_max_buffer_sec_forces_periodic_confirmation():
    """A max_buffer_sec biztonsági korlát nélkül ez a teszt egyetlen
    is_final=True eseményt kapna (a stream-lezáráskor) — a korláttal viszont
    a puffernek időszakosan kényszerűen zsugorodnia kell, tehát TÖBB
    is_final=True eseménynek kell megjelennie a stream vége előtt is."""
    engine = _NeverStabilizingFakeEngine()
    adapter = SlidingWindowStreamingAdapter(engine, window_sec=1.0, overlap_sec=0.5, max_buffer_sec=2.0)

    events = [event async for event in adapter.transcribe_stream(_audio_chunks("sess-4", n=40, chunk_ms=500))]

    final_events = [e for e in events if e.is_final]
    assert len(final_events) >= 5, (
        f"csak {len(final_events)} is_final=True esemény érkezett — a max_buffer_sec "
        "biztonsági korlátnak rendszeresen kényszerítenie kellene a konfirmálást, "
        "különben a puffer korlátlanul nőhetne"
    )


async def test_no_events_for_empty_chunk_stream():
    engine = FakeTranscriptionEngine()
    adapter = SlidingWindowStreamingAdapter(engine)

    async def empty():
        return
        yield  # pragma: no cover

    events = [event async for event in adapter.transcribe_stream(empty())]
    assert events == []
