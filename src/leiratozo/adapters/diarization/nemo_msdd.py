"""Valódi NVIDIA NeMo MSDD (Multi-scale Diarization Decoder) batch diarizációs
adapter (mode="batch"). Apache-2.0 licencű, NEM igényel HF gated-repo
elfogadást (szemben a pyannote-tal) — ld. docs/phase1-terv.md 11. szakasz.

A NeMo diarizációs pipeline fájl-manifest + RTTM-alapú (nem in-memory API) —
ez az adapter ezt a workflow-t rejti el a DiarizationEngine port mögé:
  1. az AudioBuffer-t ideiglenes 16kHz mono wav fájlba írja,
  2. egy egysoros manifest.json-t készít hozzá,
  3. a NeMo hivatalos `diar_infer_telephonic.yaml` referencia-configját tölti le
     és cache-eli (első használatkor), és felülírja benne a manifest/output
     útvonalakat,
  4. lefuttatja a `ClusteringDiarizer`-t (ami a config-ban hivatkozott,
     nyilvános NGC-modelleket — VAD, speaker-embedding, MSDD — automatikusan
     letölti/cache-eli),
  5. a kimeneti RTTM fájlt DiarizedSegment listává alakítja.
"""
from __future__ import annotations

import json
import tempfile
import wave
from pathlib import Path
from typing import Any

from leiratozo.domain.errors import ModelUnavailableError, NotSupportedError
from leiratozo.domain.models import AudioBuffer, AudioChunk, DiarizedSegment, LiveDiarizationState, VadSegment, new_id

_DEFAULT_CONFIG_URL = (
    "https://raw.githubusercontent.com/NVIDIA/NeMo/main/examples/speaker_tasks/"
    "diarization/conf/inference/diar_infer_telephonic.yaml"
)
_DEFAULT_CACHE_DIR = Path(".cache/nemo_msdd")


def _download_config(config_url: str) -> Path:
    from urllib.request import urlretrieve

    _DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = _DEFAULT_CACHE_DIR / "diar_infer_telephonic.yaml"
    if not target.exists():
        try:
            urlretrieve(config_url, target)
        except Exception as exc:
            raise ModelUnavailableError(f"NeMo diarizációs referencia-config letöltése sikertelen: {exc}") from exc
    return target


def _write_wav(samples: bytes, sample_rate: int) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples)
    return Path(tmp.name)


def _write_manifest(wav_path: Path, out_dir: Path) -> Path:
    manifest_path = out_dir / "manifest.json"
    entry = {
        "audio_filepath": str(wav_path),
        "offset": 0,
        "duration": None,
        "label": "infer",
        "text": "-",
        "num_speakers": None,
        "rttm_filepath": None,
        "uem_filepath": None,
    }
    with manifest_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return manifest_path


def _parse_rttm(rttm_path: Path) -> list[DiarizedSegment]:
    segments: list[DiarizedSegment] = []
    label_map: dict[str, str] = {}
    if not rttm_path.exists():
        return segments
    with rttm_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) < 8 or parts[0] != "SPEAKER":
                continue
            start = float(parts[3])
            duration = float(parts[4])
            raw_label = parts[7]
            mapped = label_map.setdefault(raw_label, f"S{len(label_map) + 1}")
            segments.append(
                DiarizedSegment(segment_id=new_id("seg-"), start=start, end=start + duration, speaker_label=mapped)
            )
    return segments


class NemoMsddDiarizer:
    name = "nemo-msdd"
    version = "unknown"
    mode = "batch"

    def __init__(
        self,
        *,
        config_url: str = _DEFAULT_CONFIG_URL,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        **_extra: Any,
    ) -> None:
        self._min_speakers = min_speakers
        self._max_speakers = max_speakers
        self._load_error: ModelUnavailableError | None = None

        try:
            import nemo
        except ImportError as exc:
            raise ModelUnavailableError(
                "nemo_toolkit csomag nincs telepítve (extra: diarization-nemo)"
            ) from exc

        type(self).version = getattr(nemo, "__version__", "unknown")
        try:
            self._config_path = _download_config(config_url)
        except ModelUnavailableError as exc:
            self._load_error = exc
            self._config_path = None

    async def diarize_batch(self, audio: AudioBuffer, vad_segments: list[VadSegment]) -> list[DiarizedSegment]:
        if self._load_error is not None:
            raise self._load_error

        from omegaconf import OmegaConf

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            wav_path = _write_wav(audio.samples, audio.sample_rate)
            manifest_path = _write_manifest(wav_path, out_dir)

            config = OmegaConf.load(str(self._config_path))
            config.diarizer.manifest_filepath = str(manifest_path)
            config.diarizer.out_dir = str(out_dir)
            if self._max_speakers is not None:
                config.diarizer.clustering.parameters.max_num_speakers = self._max_speakers

            try:
                from nemo.collections.asr.models import ClusteringDiarizer

                diarizer_model = ClusteringDiarizer(cfg=config)
                diarizer_model.diarize()
            except Exception as exc:
                raise ModelUnavailableError(f"NeMo MSDD diarizáció futtatása sikertelen: {exc}") from exc
            finally:
                wav_path.unlink(missing_ok=True)

            rttm_path = out_dir / "pred_rttms" / f"{wav_path.stem}.rttm"
            return _parse_rttm(rttm_path)

    async def diarize_live(
        self, audio_chunk: AudioChunk, state: LiveDiarizationState
    ) -> tuple[list[DiarizedSegment], LiveDiarizationState]:
        raise NotSupportedError("NemoMsddDiarizer csak diarize_batch-et támogat (mode=batch)")
