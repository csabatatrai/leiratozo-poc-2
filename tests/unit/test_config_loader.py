"""A rétegzett config-betöltés tesztjei: kód-defaultok -> YAML -> env (env nyer).
Ld. docs/phase1-terv.md 7. szakasz."""
from __future__ import annotations

import os

import pytest

from leiratozo.config.loader import load_config


def test_defaults_when_no_yaml_and_no_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CONFIG_PATH", raising=False)
    monkeypatch.delenv("MODELS__ASR__ADAPTER", raising=False)

    config = load_config()

    assert config.models.asr.adapter == "faster_whisper"
    assert config.device.default == "auto"


def test_yaml_overrides_code_defaults(tmp_path, monkeypatch: pytest.MonkeyPatch):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("models:\n  asr:\n    adapter: vosk\ndevice:\n  default: cpu\n", encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH", str(yaml_path))
    monkeypatch.delenv("MODELS__ASR__ADAPTER", raising=False)

    config = load_config()

    assert config.models.asr.adapter == "vosk"
    assert config.device.default == "cpu"


def test_env_wins_over_yaml(tmp_path, monkeypatch: pytest.MonkeyPatch):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("models:\n  asr:\n    adapter: vosk\n", encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH", str(yaml_path))
    monkeypatch.setenv("MODELS__ASR__ADAPTER", "faster_whisper")

    config = load_config()

    assert config.models.asr.adapter == "faster_whisper"

    monkeypatch.delenv("MODELS__ASR__ADAPTER", raising=False)


def test_init_kwargs_win_over_everything(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MODELS__ASR__ADAPTER", "vosk")
    from leiratozo.config.schema import AsrModelConfig, ModelsConfig

    config = load_config(models=ModelsConfig(asr=AsrModelConfig(adapter="fake")))

    assert config.models.asr.adapter == "fake"
    monkeypatch.delenv("MODELS__ASR__ADAPTER", raising=False)
