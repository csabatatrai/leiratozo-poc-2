"""Két összehasonlítandó út kliensei:
  (a) `run_baseline_batch` — a NYERS, külső ASR-végpont közvetlen hívása
      (magát a leiratozo `RemoteHttpAsrEngine` adapterét újrahasználva, hogy
      ne duplikáljuk a HTTP-hívás logikáját).
  (b) `run_pipeline_batch` / `run_pipeline_live` — a MI teljes worker-ünk
      (VAD+ASR+diarizáció+aligner+speaker-match) hívása a saját HTTP/WS
      API-nkon keresztül, ami már fut valahol (docker compose vagy
      `python -m leiratozo.main`).

Ez a modul NEM importálja a FastAPI appot közvetlenül — a workert éles,
külön processzként/konténerként kell futtatni (ld. eval/README.md), hogy a
mérés a ténylegesen üzemeltetett rendszert tükrözze, ne egy in-process
tesztkliens-árnyékot."""
from __future__ import annotations

import asyncio
import json
import wave
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import websockets


@dataclass(frozen=True)
class BaselineResult:
    text: str
    raw_response: dict


async def run_baseline_batch(audio_path: Path, *, base_url: str, timeout_sec: float = 300.0) -> BaselineResult:
    """A nyers, külső ASR-végpont közvetlen hívása — a leiratozo
    RemoteHttpAsrEngine adaptert használja, hogy pontosan ugyanaz a HTTP-hívás
    történjen, mint amit a pipeline maga is tenne az ASR-lépésben."""
    from leiratozo.adapters.asr.remote_http import RemoteHttpAsrEngine
    from leiratozo.domain.models import AudioBuffer, TranscriptionHints

    engine = RemoteHttpAsrEngine(base_url=base_url, timeout_sec=timeout_sec)
    pcm, sample_rate = _wav_to_pcm16(audio_path)
    audio = AudioBuffer(samples=pcm, sample_rate=sample_rate, duration_sec=len(pcm) / (sample_rate * 2))
    tokens = await engine.transcribe_batch(audio, language=None, hints=TranscriptionHints())
    text = " ".join(t.word for t in tokens)
    return BaselineResult(text=text, raw_response={"tokens": [t.model_dump() for t in tokens]})


@dataclass(frozen=True)
class PipelineBatchResult:
    document: dict
    text: str


async def run_pipeline_batch(
    audio_path: Path, *, api_base_url: str, timeout_sec: float = 300.0, poll_interval_sec: float = 1.0
) -> PipelineBatchResult:
    """A SAJÁT worker-ünk POST /v1/jobs végpontja — beküldi a fájlt, majd
    pollozza a státuszt, amíg 'done'/'failed' nem lesz."""
    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        with audio_path.open("rb") as fh:
            resp = await client.post(f"{api_base_url}/v1/jobs", files={"file": (audio_path.name, fh, "audio/wav")})
        resp.raise_for_status()
        job_id = resp.json()["job_id"]

        deadline = asyncio.get_event_loop().time() + timeout_sec
        while True:
            status_resp = await client.get(f"{api_base_url}/v1/jobs/{job_id}")
            status_resp.raise_for_status()
            status = status_resp.json()["status"]
            if status == "done":
                break
            if status == "failed":
                raise RuntimeError(f"Pipeline job {job_id} failed: {status_resp.json()}")
            if asyncio.get_event_loop().time() > deadline:
                raise TimeoutError(f"Pipeline job {job_id} nem fejeződött be {timeout_sec}s alatt")
            await asyncio.sleep(poll_interval_sec)

        result_resp = await client.get(f"{api_base_url}/v1/jobs/{job_id}/result")
        result_resp.raise_for_status()
        document = result_resp.json()

    text = " ".join(seg["text"] for seg in document.get("segments", []))
    return PipelineBatchResult(document=document, text=text)


@dataclass
class PipelineLiveResult:
    events: list[dict] = field(default_factory=list)

    @property
    def final_text(self) -> str:
        return " ".join(e["segment"]["text"] for e in self.events if e["is_final"])


async def run_pipeline_live(
    audio_path: Path,
    *,
    ws_base_url: str,
    session_id: str,
    chunk_ms: int = 500,
    realtime: bool = True,
    trailing_wait_sec: float = 5.0,
) -> PipelineLiveResult:
    """A SAJÁT worker-ünk WS /v1/live/{session_id} végpontja: a fájlt
    chunk-okra bontva, (alapértelmezetten) valós idejű ütemezéssel streameli,
    és összegyűjti a partial/final eseményeket.

    FONTOS (ld. docs/manual_test_notes.md): a kliens a küldés befejezése után
    is még `trailing_wait_sec`-et vár zárás előtt, hogy a szerver záró
    (final) flush-a biztosan megérkezzen — egy azonnali zárás elveszítené azt
    (ez egy ismert, dokumentált protokoll-limitáció, nem ennek a kliensnek a
    hibája)."""
    pcm, sample_rate = _wav_to_pcm16(audio_path)
    chunk_bytes = int(sample_rate * (chunk_ms / 1000) * 2)
    chunks = [pcm[i : i + chunk_bytes] for i in range(0, len(pcm), chunk_bytes)]

    result = PipelineLiveResult()
    url = f"{ws_base_url}/v1/live/{session_id}"

    async with websockets.connect(url, max_size=None) as ws:

        async def sender():
            for chunk in chunks:
                await ws.send(chunk)
                if realtime:
                    await asyncio.sleep(chunk_ms / 1000)
            await asyncio.sleep(trailing_wait_sec)
            await ws.close()

        async def receiver():
            try:
                async for message in ws:
                    result.events.append(json.loads(message))
            except websockets.exceptions.ConnectionClosed:
                pass

        await asyncio.gather(sender(), receiver())

    return result


def _wav_to_pcm16(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as wf:
        if wf.getsampwidth() != 2:
            raise ValueError(f"{path}: csak 16-bites PCM wav támogatott ebben az eval-kliensben")
        sample_rate = wf.getframerate()
        pcm = wf.readframes(wf.getnframes())
        if wf.getnchannels() != 1:
            raise ValueError(
                f"{path}: mono (1 csatornás) wav várt, kaptunk {wf.getnchannels()} csatornát — "
                "konvertáld előbb (pl. ffmpeg -ac 1 -ar 16000)"
            )
    return pcm, sample_rate
