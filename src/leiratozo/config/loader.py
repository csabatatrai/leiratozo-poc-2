"""Rétegzett config-betöltés: kód-defaultok -> `CONFIG_PATH` YAML -> env
változók. Az env mindig felülír mindent (12-factor). Ld. docs/phase1-terv.md
7. szakasz a teljes sémáért/példáért.

A pydantic-settings `settings_customise_sources` mechanizmusát használjuk, hogy
a forrás-prioritás explicit és tesztelt legyen, ne kézzel írt dict-merge-eken
múljon."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Tuple, Type

import yaml
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from leiratozo.config.schema import AppConfig


def _load_yaml_from_env() -> dict[str, Any]:
    raw_path = os.environ.get("CONFIG_PATH")
    if not raw_path:
        return {}
    path = Path(raw_path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class _YamlSettingsSource(PydanticBaseSettingsSource):
    """pydantic-settings forrás, ami a CONFIG_PATH YAML fájlt olvassa be."""

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:  # pragma: no cover
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return _load_yaml_from_env()


class ConfiguredAppConfig(AppConfig):
    """AppConfig a YAML réteggel bedrótozva. Prioritás (legmagasabbtól):
    explicit __init__ kwargs > env változók > CONFIG_PATH YAML > kód-defaultok."""

    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _YamlSettingsSource(settings_cls),
            file_secret_settings,
        )


def load_config(**overrides: Any) -> AppConfig:
    """Az effektív AppConfig felépítése. Az `overrides` explicit __init__
    kwargs-ként viselkedik, mindent felülír — főleg teszteknek hasznos."""
    return ConfiguredAppConfig(**overrides)
