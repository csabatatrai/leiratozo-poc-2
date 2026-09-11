from __future__ import annotations

import pytest

from leiratozo.config.schema import AppConfig

FAKE_CONFIG_OVERRIDES = {
    "queue": {"backend": "inline"},
    "models": {
        "vad": {"adapter": "fake"},
        "asr": {"adapter": "fake"},
        "diarization": {"batch_adapter": "fake", "live_adapter": "fake"},
        "speaker_embedding": {"adapter": "fake"},
    },
    "storage": {
        "job_store_adapter": "fake",
        "session_store_adapter": "fake",
        "profile_store": {"backend": "fake"},
    },
    "audio": {"decoder_adapter": "fake"},
    "logging": {"format": "console"},
}


@pytest.fixture
def fake_config() -> AppConfig:
    """Minden porthoz a fake adaptert választó config — ML-függőség nélkül
    futtatható pipeline-hoz és API-teszthez."""
    return AppConfig.model_validate(FAKE_CONFIG_OVERRIDES)
