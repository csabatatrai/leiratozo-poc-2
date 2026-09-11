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
from leiratozo.registry.plugin_registry import instantiate


@lru_cache
def get_config() -> AppConfig:
    return load_config()


class ServiceContainer:
    """Egyszer épül fel induláskor (ld. api.app.create_app), és
    `app.state.services`-ként érhető el. Éles adapter-nevekkel (pl.
    faster_whisper) a konkrét modell-implementációk hiányában NotImplementedError-t
    dob — 2. fázisban a `config/config.fake.yaml` (adapter: fake mindenhol) ad
    futtatható, végponttól-végpontig tesztelhető pipeline-t."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

        self.vad = instantiate("vad", config.models.vad.adapter, config.models.vad.params)
        self.asr = instantiate("asr", config.models.asr.adapter, config.models.asr.params)
        self.audio_decoder = instantiate("audio_decoder", config.audio.decoder_adapter, {})
        self.aligner = instantiate("aligner", "passthrough", {})
        self.diarizer_batch = instantiate(
            "diarization_batch", config.models.diarization.batch_adapter, config.models.diarization.params
        )
        self.diarizer_live = instantiate(
            "diarization_live", config.models.diarization.live_adapter, config.models.diarization.params
        )
        self.speaker_embedding = instantiate(
            "speaker_embedding", config.models.speaker_embedding.adapter, config.models.speaker_embedding.params
        )
        self.job_store = instantiate("job_store", config.storage.job_store_adapter, {})
        self.session_store = instantiate("session_store", config.storage.session_store_adapter, {})
        self.profile_store = instantiate("profile_store", config.storage.profile_store.backend, {})

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
