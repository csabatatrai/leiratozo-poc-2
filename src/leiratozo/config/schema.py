"""Rétegzett config-séma (pydantic-settings): kód-defaultok -> YAML
(`CONFIG_PATH`) -> env változók (env nyer, 12-factor). Ld. docs/phase1-terv.md
7. szakasz — ez a modul a konkrét YAML-példa Python-tükörképe."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    api_key_env: str | None = "API_KEY"


class QueueConfig(BaseModel):
    backend: Literal["redis", "inline"] = "redis"
    """`inline`: a batch job szinkron-inline fut a kérést kiszolgáló process-ben
    (nincs külön worker/Redis-függés) — kizárólag dev/teszt célra (ld.
    config/config.fake.yaml). `redis`: valódi arq-alapú queue, külön worker
    process dolgozza fel (ld. queue/worker.py) — ez a production alapértelmezés."""
    url: str = "redis://redis:6379/0"


class ProfileStoreConfig(BaseModel):
    backend: str = "encrypted_sqlite"
    path: str = "/data/profiles.db"
    encryption_key_env: str = "PROFILE_ENCRYPTION_KEY"


class StorageConfig(BaseModel):
    job_store_adapter: str = "sqlite"
    session_store_adapter: str = "sqlite"
    job_store_url: str = "sqlite:////data/jobs.db"
    session_store_url: str = "sqlite:////data/sessions.db"
    profile_store: ProfileStoreConfig = Field(default_factory=ProfileStoreConfig)
    model_cache_dir: str = "/models"


class AudioConfig(BaseModel):
    decoder_adapter: str = "ffmpeg"


class SecurityConfig(BaseModel):
    huggingface_token_env: str = "HF_TOKEN"
    require_license_ack: bool = True


class RetentionConfig(BaseModel):
    profile_retention_days: int | None = None
    job_result_retention_days: int | None = 30


class DeviceConfig(BaseModel):
    default: Literal["auto", "cpu", "cuda"] = "auto"


class AsrModelConfig(BaseModel):
    adapter: str = "faster_whisper"
    params: dict = Field(default_factory=dict)


class VadModelConfig(BaseModel):
    adapter: str = "silero"
    params: dict = Field(default_factory=dict)


class DiarizationModelConfig(BaseModel):
    batch_adapter: str = "pyannote"
    live_adapter: str = "diart"
    params: dict = Field(default_factory=dict)


class SpeakerEmbeddingModelConfig(BaseModel):
    adapter: str = "speechbrain_ecapa"
    params: dict = Field(default_factory=dict)


class ModelsConfig(BaseModel):
    vad: VadModelConfig = Field(default_factory=VadModelConfig)
    asr: AsrModelConfig = Field(default_factory=AsrModelConfig)
    diarization: DiarizationModelConfig = Field(default_factory=DiarizationModelConfig)
    speaker_embedding: SpeakerEmbeddingModelConfig = Field(default_factory=SpeakerEmbeddingModelConfig)


class SpeakerMatchingConfig(BaseModel):
    similarity_threshold: float = Field(default=0.72, ge=0, le=1)
    unknown_label: str = "unknown"


class StreamingConfig(BaseModel):
    chunk_ms: int = 500
    overlap_ms: int = 200
    transport: Literal["websocket"] = "websocket"
    stabilization_window_sec: float = 3.0


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: Literal["json", "console"] = "json"


class AppConfig(BaseSettings):
    """Gyökér-config. Éles használatban `config.loader.load_config()`-on
    keresztül épül fel (YAML + env réteg), nem közvetlen példányosítással."""

    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore")

    server: ServerConfig = Field(default_factory=ServerConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    device: DeviceConfig = Field(default_factory=DeviceConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    speaker_matching: SpeakerMatchingConfig = Field(default_factory=SpeakerMatchingConfig)
    streaming: StreamingConfig = Field(default_factory=StreamingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    preload_models: bool = True
