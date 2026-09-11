from __future__ import annotations

import pytest

from leiratozo.domain.errors import AdapterNotFoundError
from leiratozo.registry import plugin_registry


def test_resolve_known_adapter_returns_ref():
    ref = plugin_registry.resolve("asr", "fake")
    assert ref.port_kind == "asr"
    assert ref.adapter_name == "fake"
    assert ":" in ref.dotted_path


def test_resolve_unknown_adapter_raises_adapter_not_found():
    with pytest.raises(AdapterNotFoundError):
        plugin_registry.resolve("asr", "does-not-exist")


def test_resolve_unknown_port_raises_adapter_not_found():
    with pytest.raises(AdapterNotFoundError):
        plugin_registry.resolve("not-a-port", "fake")


def test_instantiate_fake_asr_adapter_builds_a_working_instance():
    from leiratozo.adapters.asr.fake import FakeTranscriptionEngine

    engine = plugin_registry.instantiate("asr", "fake", {})
    assert isinstance(engine, FakeTranscriptionEngine)


def test_instantiate_phase3_stub_raises_not_implemented_not_import_error():
    """A 3. fázisos stub adapterek import-biztosak (fail-fast a registry-
    feloldásnál működik), de példányosításkor NotImplementedError-t dobnak,
    amíg a valódi integráció el nem készül."""
    with pytest.raises(NotImplementedError):
        plugin_registry.instantiate("asr", "faster_whisper", {})


def test_register_allows_adding_new_adapters_without_editing_the_module():
    plugin_registry.register("asr", "custom-test-adapter", "leiratozo.adapters.asr.fake:FakeTranscriptionEngine")
    ref = plugin_registry.resolve("asr", "custom-test-adapter")
    assert ref.adapter_name == "custom-test-adapter"
