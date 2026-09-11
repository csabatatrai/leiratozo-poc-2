"""Dependency wiring: az AppConfig + plugin registry alapján építi fel az
alkalmazás-szolgáltatásokat. Ez (és maguk az adapterek) az egyetlen hely, ami
konkrét adapter-azonosítót lát — de azt is csak configon keresztül, sosem
hardkódolva."""
from __future__ import annotations

from functools import lru_cache

from leiratozo.application.batch_service import BatchTranscriptionService
from leiratozo.application.live_service import LiveSessionService
from leiratozo.application.speaker_registration_service import SpeakerRegistrationService
from leiratozo.config.loader import load_config
from leiratozo.config.schema import AppConfig
from leiratozo.domain.models import TranscriptJob
from leiratozo.registry.plugin_registry import DegradedAdapter, instantiate, instantiate_or_degrade


@lru_cache
def get_config() -> AppConfig:
    return load_config()


class ServiceContainer:
    """Egyszer épül fel induláskor (ld. api.app.create_app), és
    `app.state.services`-ként érhető el.

    Az ML-modell-portok (vad/asr/diarizer_*/speaker_embedding) `instantiate_or_
    degrade`-en keresztül épülnek: hiányzó HF token/licenc/eszköz/letöltési
    hiba (`ModelUnavailableError`) esetén a port `DegradedAdapter`-ré válik —
    ez NEM dönti el a teljes szolgáltatást, csak az adott portot igénylő
    kéréseket bukja (docs/phase1-terv.md 1. és 10. szakasz). Hiányzó
    csomag/rossz adapter-név (`AdapterNotFoundError`) VISZONT fail-fast marad —
    az konfigurációs hiba, nem futásidejű degradáció. A storage-portok
    (job/session/profile store) sima `instantiate`-tel épülnek: azok hibája
    (pl. hiányzó titkosítási kulcs) legyen azonnal látható, ne rejtse el a
    degradáció."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

        self.vad = instantiate_or_degrade("vad", config.models.vad.adapter, config.models.vad.params)
        self.asr = instantiate_or_degrade("asr", config.models.asr.adapter, config.models.asr.params)
        self.audio_decoder = instantiate("audio_decoder", config.audio.decoder_adapter, {})
        self.aligner = instantiate("aligner", "passthrough", {})
        self.diarizer_batch = instantiate_or_degrade(
            "diarization_batch", config.models.diarization.batch_adapter, config.models.diarization.params
        )
        self.diarizer_live = instantiate_or_degrade(
            "diarization_live", config.models.diarization.live_adapter, config.models.diarization.params
        )
        self.speaker_embedding = instantiate_or_degrade(
            "speaker_embedding", config.models.speaker_embedding.adapter, config.models.speaker_embedding.params
        )
        self.job_store = instantiate(
            "job_store", config.storage.job_store_adapter, {"url": config.storage.job_store_url}
        )
        self.session_store = instantiate(
            "session_store", config.storage.session_store_adapter, {"url": config.storage.session_store_url}
        )
        self.profile_store = instantiate(
            "profile_store",
            config.storage.profile_store.backend,
            {
                "path": config.storage.profile_store.path,
                "encryption_key_env": config.storage.profile_store.encryption_key_env,
            },
        )

        self.speaker_registration = SpeakerRegistrationService(
            self.speaker_embedding,
            self.profile_store,
            similarity_threshold=config.speaker_matching.similarity_threshold,
            unknown_label=config.speaker_matching.unknown_label,
        )
        self.batch_service = BatchTranscriptionService(
            audio_decoder=self.audio_decoder,
            vad=self.vad,
            asr=self.asr,
            diarizer=self.diarizer_batch,
            aligner=self.aligner,
            speaker_registration=self.speaker_registration,
            job_store=self.job_store,
        )
        self.live_service = LiveSessionService(
            asr=self.asr,
            diarizer=self.diarizer_live,
            speaker_registration=self.speaker_registration,
            session_store=self.session_store,
            window_sec=config.streaming.chunk_ms / 1000 * 6,
            overlap_sec=config.streaming.overlap_ms / 1000,
        )

        self._arq_pool = None  # csak queue.backend=="redis" esetén, ld. start()

    def degraded_ports(self) -> dict[str, str]:
        """port_kind -> hibaüzenet azokra a portokra, amik DegradedAdapter-ré
        estek. Üres dict = minden ML-modell-port rendben betöltve. Ld. GET
        /readyz (api/routes/health.py)."""
        candidates = {
            "vad": self.vad,
            "asr": self.asr,
            "diarization_batch": self.diarizer_batch,
            "diarization_live": self.diarizer_live,
            "speaker_embedding": self.speaker_embedding,
        }
        return {
            port_kind: str(adapter.error)
            for port_kind, adapter in candidates.items()
            if isinstance(adapter, DegradedAdapter)
        }

    async def start(self) -> None:
        """FastAPI lifespan-ból hívva induláskor. `queue.backend=="inline"`
        esetén nincs teendő (ld. submit_batch_job)."""
        if self.config.queue.backend == "redis":
            from arq import create_pool
            from arq.connections import RedisSettings

            self._arq_pool = await create_pool(RedisSettings.from_dsn(self.config.queue.url))

    async def stop(self) -> None:
        if self._arq_pool is not None:
            await self._arq_pool.close()

    async def submit_batch_job(self, raw_audio: bytes, filename_hint: str | None = None) -> TranscriptJob:
        """A job létrehozása után `queue.backend` szerint dönt: `inline` esetén
        (config/config.fake.yaml, tesztek) a kérést kiszolgáló process-ben fut le
        szinkron-inline, ahogy a 2. fázisban; `redis` esetén (production
        alapértelmezés) egy külön worker process dolgozza fel (ld. queue/worker.py)
        — a hívó azonnal 'queued' állapotú job-ot kap vissza."""
        job = await self.batch_service.submit(raw_audio, filename_hint=filename_hint)
        if self.config.queue.backend == "inline":
            await self.batch_service.run(job.job_id, raw_audio, filename_hint=filename_hint)
        else:
            if self._arq_pool is None:
                raise RuntimeError(
                    "queue.backend=='redis', de a ServiceContainer.start() nem futott le "
                    "(hiányzó FastAPI lifespan-indítás) — ld. api/app.py."
                )
            await self._arq_pool.enqueue_job("run_batch_job", job.job_id, raw_audio, filename_hint)
        return job
