"""Valódi `diart` élő diarizációs adapter (mode="live_approx"). A diart alapból
pyannote szegmentációs/embedding modellekre épül, tehát — a pyannote.audio
adapterhez hasonlóan — HF gated-repo licenc-elfogadást és tokent igényelhet;
hiányzó/érvénytelen token esetén NEM omlik össze induláskor, csak diarize_live
hívásakor dob ModelUnavailableError-t (ld. pyannote.py adapter, ugyanaz a minta).

FONTOS ARCHITEKTURÁLIS MEGJEGYZÉS (docs/phase1-terv.md 5. és 10. szakasz): a
diart pipeline belső klaszterező-állapota (embedding-puffer, centroidok) NEM
JSON-szerializálható olcsón, ezért ez az adapter a session-önkénti diart
pipeline-példányt a SAJÁT (process-lokális) memóriájában tartja
(`self._sessions`), NEM a SessionStore-on átküldött `LiveDiarizationState.
payload`-ban — az utóbbi csak egy könnyű "aktív session" jelzőt hordoz. Ennek
következménye: a diart-alapú élő diarizáció state-je EGY workerhez kötött —
több worker közötti horizontális skálázásnál session-affinitás routing
szükséges (ami a "kis-közepes, single-node" célnál, docs/phase1-terv.md 0.
szakasz, nem korlátozó tényező).

MEGJEGYZÉS A TESZTELÉSRŐL: ezt az adaptert ebben a munkamenetben NEM sikerült
élesen validálni — a `diart` pip-csomag telepítése két különböző módon is
valódi, dokumentált akadályba futott: (1) a host Python 3.14-en a `diart`
`numpy<2` pin-je fordítást igényelt volna, C-fordító (gcc) nélkül; (2) egy
tiszta python:3.11 konténerben a `diart` maga által behúzott `torchaudio`
verzió inkompatibilis volt a vele együtt telepített `pyannote.audio`
verzióval (`AttributeError: module 'torchaudio' has no attribute
'AudioMetaData'`). Ez utóbbi önmagában is jelzi, hogy éles telepítéskor a
`diart`+`pyannote.audio`+`torch`+`torchaudio` verziókombinációt explicit
pinnelni kell (ld. pyproject.toml `diarization-diart` extra — 3. fázis utáni
karbantartási feladat)."""
from __future__ import annotations

from typing import Any

from leiratozo.domain.errors import ModelUnavailableError, NotSupportedError
from leiratozo.domain.models import AudioChunk, DiarizedSegment, LiveDiarizationState, new_id


class DiartLiveDiarizer:
    name = "diart"
    version = "unknown"
    mode = "live_approx"

    def __init__(self, *, min_speakers: int | None = None, max_speakers: int | None = None, **_extra: Any) -> None:
        self._min_speakers = min_speakers
        self._max_speakers = max_speakers
        self._sessions: dict[str, Any] = {}
        self._load_error: ModelUnavailableError | None = None
        self._pipeline_cls = None
        self._config_cls = None

        try:
            import diart as diart_pkg
            from diart import SpeakerDiarization, SpeakerDiarizationConfig
        except ImportError as exc:
            raise ModelUnavailableError("diart csomag nincs telepítve (extra: diarization-diart)") from exc

        type(self).version = getattr(diart_pkg, "__version__", "unknown")
        try:
            # Egy próba-pipeline felépítése induláskor lelepli a mögöttes
            # pyannote szegmentációs/embedding modell letöltési/licenc hibáit,
            # anélkül hogy ez a teljes ServiceContainer-t elvinné (ld. modul
            # docstring + registry/plugin_registry.py DegradedAdapter).
            SpeakerDiarization(SpeakerDiarizationConfig())
            self._pipeline_cls = SpeakerDiarization
            self._config_cls = SpeakerDiarizationConfig
        except Exception as exc:
            self._load_error = ModelUnavailableError(
                f"diart pipeline nem tölthető be — valószínűleg hiányzó/el nem fogadott HF "
                f"licenc a mögöttes pyannote szegmentációs modellhez: {exc}"
            )

    def _get_or_create_session(self, session_id: str) -> Any:
        pipeline = self._sessions.get(session_id)
        if pipeline is None:
            pipeline = self._pipeline_cls(self._config_cls())
            self._sessions[session_id] = pipeline
        return pipeline

    async def diarize_live(
        self, audio_chunk: AudioChunk, state: LiveDiarizationState
    ) -> tuple[list[DiarizedSegment], LiveDiarizationState]:
        if self._load_error is not None:
            raise self._load_error

        import numpy as np
        from pyannote.core import SlidingWindow, SlidingWindowFeature

        pipeline = self._get_or_create_session(audio_chunk.session_id)

        pcm = np.frombuffer(audio_chunk.samples, dtype="<i2").astype(np.float32) / 32768.0
        window = SlidingWindow(start=0.0, duration=1.0 / audio_chunk.sample_rate, step=1.0 / audio_chunk.sample_rate)
        feature = SlidingWindowFeature(pcm.reshape(-1, 1), window)

        outputs = pipeline([feature])
        segments: list[DiarizedSegment] = []
        label_map: dict[str, str] = state.payload.setdefault("label_map", {})
        for annotation, _ in outputs:
            for turn, _, speaker in annotation.itertracks(yield_label=True):
                mapped = label_map.setdefault(speaker, f"S{len(label_map) + 1}")
                segments.append(
                    DiarizedSegment(segment_id=new_id("live-seg-"), start=turn.start, end=turn.end, speaker_label=mapped)
                )
        state.payload["session_active"] = True
        return segments, state

    async def diarize_batch(self, audio, vad_segments):
        raise NotSupportedError("DiartLiveDiarizer csak diarize_live-ot támogat (mode=live_approx)")
