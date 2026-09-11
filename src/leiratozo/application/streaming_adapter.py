"""SlidingWindowStreamingAdapter — egy batch-only TranscriptionEngine-t
közelít élő streammé átfedő ablakokkal + merge-dzsel. Ez EXPLICIT közelítés
(docs/phase1-terv.md 4. szakasz), nem valódi kauzális streaming, és csak akkor
kerül bevetésre, ha a configolt ASR adapter `capabilities.supports_native_streaming`
mezője False.

MEGJEGYZÉS (2026-09-12, éles teszt talált hiba — ld. docs/manual_test_notes.md):
a korábbi verzió egy fix `overlap_bytes` farkot tartott meg a pufferből minden
flush után, és egy globális `emitted_word_count`-ot használt INDEXKÉNT az
ÚJRA lekért (minden hívásnál a teljes aktuális pufferre újratranszkribált)
szólistába. Ez két hibát okozott: (1) kevés/nagy tokent adó (szegmens-szintű)
ASR-eknél a darabszám-alapú "utolsó negyed" heurisztika szinte sosem
konfirmált semmit; (2) mivel a puffer minden flush után zsugorodik, a
KÖVETKEZŐ hívás szava-listája MÁS (0-tól újraindexelt) tartományra
vonatkozik, mint az előző — a puffer eleji, már megerősített tartalom emiatt
DUPLIKÁLTAN újra megjelenhetett a kimeneten. A mostani verzió ezt úgy oldja
meg, hogy (a) a stabil/bizonytalan szétválasztás IDŐALAPÚ, és (b) a
pufferből KIZÁRÓLAG a ténylegesen megerősített hangidő kerül eldobásra —
soha nem egy fix, feltételezett overlap-hossz —, globális idő-eltolás
(`_dropped_sec`) követésével, hogy a kimeneti időbélyegek a session
elejéhez, ne az aktuális (zsugorodó) pufferhez viszonyítva legyenek helyesek."""
from __future__ import annotations

from typing import AsyncIterator

from leiratozo.domain.models import (
    AudioBuffer,
    AudioChunk,
    PartialOrFinalTranscript,
    TranscriptSegment,
    TranscriptionHints,
    WordToken,
)
from leiratozo.ports.asr import TranscriptionEngine


class SlidingWindowStreamingAdapter:
    """Bufferelt, átfedő ablakokban hívja a becsomagolt engine transcribe_batch-ét,
    és a már nem változó (stabil) szó-fejrészt `is_final=True`-ként, a még
    bizonytalan farkot `is_final=False`-ként emittálja."""

    def __init__(
        self,
        engine: TranscriptionEngine,
        *,
        window_sec: float = 3.0,
        overlap_sec: float = 0.75,
        max_buffer_sec: float | None = None,
        language: str | None = None,
    ) -> None:
        if engine.capabilities.supports_native_streaming:
            raise ValueError(
                f"{engine.name} natívan támogat streaminget; a "
                "SlidingWindowStreamingAdapter-be csomagolása feleslegesen adná hozzá "
                "a közelítés késleltetését, előny nélkül."
            )
        self._engine = engine
        self._window_sec = window_sec
        self._overlap_sec = overlap_sec
        self._max_buffer_sec = max_buffer_sec if max_buffer_sec is not None else window_sec * 3
        self._language = language
        self._sample_rate: int | None = None
        self._buffer = bytearray()
        self._dropped_sec = 0.0  # a session eleje óta a pufferből eldobott (már megerősített) hangidő
        self._event_counter = 0
        self._session_id: str | None = None

    @property
    def name(self) -> str:
        return f"sliding-window({self._engine.name})"

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[PartialOrFinalTranscript]:
        async for chunk in audio_chunks:
            self._session_id = chunk.session_id
            self._sample_rate = chunk.sample_rate
            self._buffer.extend(chunk.samples)
            window_bytes = int(self._window_sec * chunk.sample_rate * 2)  # 16 bites PCM
            if len(self._buffer) < window_bytes:
                continue
            async for event in self._flush_window(is_final_window=False):
                yield event
        async for event in self._flush_window(is_final_window=True):
            yield event

    async def _flush_window(self, *, is_final_window: bool) -> AsyncIterator[PartialOrFinalTranscript]:
        """A `words` MINDIG az AKTUÁLIS (esetlegesen már zsugorított) puffer
        elejétől (helyi t=0) számított időbélyegeket ad — ezért a
        megerősített szavak globális (session-eleji) időbélyegét
        `_dropped_sec`-kel toljuk el kimenetkor, és a pufferből is pontosan
        annyi hangidőt (nem egy fix overlapet!) vágunk le, amennyi ténylegesen
        megerősödött — így a következő hívás helyi t=0-ja mindig a még
        NEM megerősített tartalom elejére esik, sosem ismétel."""
        if not self._buffer or self._sample_rate is None:
            return
        audio = AudioBuffer(
            samples=bytes(self._buffer),
            sample_rate=self._sample_rate,
            duration_sec=len(self._buffer) / (self._sample_rate * 2),
        )
        words = await self._engine.transcribe_batch(
            audio, language=self._language, hints=TranscriptionHints(language=self._language)
        )
        if not words:
            return

        if is_final_window or audio.duration_sec >= self._max_buffer_sec:
            # Biztonsági felső korlát (ld. modul docstring, 2026-09-12-i éles
            # teszt): ha a wrappelt engine olyan KEVÉS/NAGY szegmenst ad
            # (pl. egy teljes ablakot lefedő 1 szegmenst), hogy sosem esik a
            # stabil-küszöb alá, a puffer flush-onként nőne, sosem
            # zsugorodna — ez egyre lassabb újratranszkripciót, végül
            # kapcsolat-timeoutot és (a mögöttes ASR-nél) hosszú kontextusú
            # ismétlődés-hallucinációt okozott élesben (távoli végponttal
            # tesztelve). Ezért a puffer max. `_max_buffer_sec` fölött
            # KÉNYSZERŰEN mindent megerősítünk, hogy a puffer garantáltan
            # zsugorodjon — ritka esetben egy még nem teljesen stabil szöveg
            # is finalizálódhat emiatt, de ez jobb, mint a korlátlan növekedés.
            confirmed, tentative = words, []
        else:
            # Csak azok a szavak stabilak, amiknek a vége a (helyi) puffer
            # végétől legalább `overlap_sec`-kal korábbra esik — ez időalapú,
            # nem darabszám-alapú, tehát kevés/nagy tokennél (szegmens-szintű
            # ASR) is helyesen viselkedik.
            stable_cutoff_local = audio.duration_sec - self._overlap_sec
            confirmed = [w for w in words if w.end <= stable_cutoff_local]
            tentative = [w for w in words if w.end > stable_cutoff_local]

        if confirmed:
            yield self._make_event(self._shift_to_global(confirmed), is_final=True)
            confirmed_local_end = confirmed[-1].end
            drop_bytes = int(confirmed_local_end * self._sample_rate * 2)
            self._dropped_sec += confirmed_local_end
            self._buffer = self._buffer[drop_bytes:]
        if tentative:
            yield self._make_event(self._shift_to_global(tentative), is_final=False)

        if is_final_window:
            self._buffer = bytearray()

    def _shift_to_global(self, words: list[WordToken]) -> list[WordToken]:
        if self._dropped_sec == 0.0:
            return words
        return [w.model_copy(update={"start": w.start + self._dropped_sec, "end": w.end + self._dropped_sec}) for w in words]

    def _make_event(self, words: list[WordToken], *, is_final: bool) -> PartialOrFinalTranscript:
        self._event_counter += 1
        text = " ".join(w.word for w in words)
        kind = "final" if is_final else "partial"
        segment = TranscriptSegment(
            segment_id=f"live-{self._session_id}-{kind}-{self._event_counter}",
            start=words[0].start,
            end=words[-1].end,
            text=text,
            speaker_label="S?",  # diarizáció ezen a rétegen még nincs hozzárendelve
            is_final=is_final,
            words=words,
        )
        return PartialOrFinalTranscript(session_id=self._session_id or "", segment=segment, is_final=is_final)
