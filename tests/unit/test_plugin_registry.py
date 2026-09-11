from __future__ import annotations

import pytest

from leiratozo.domain.errors import AdapterNotFoundError
from leiratozo.registry import plugin_registry


class _StillAStub:
    """Modulszintű, self-contained stub-osztály a lenti teszthez — azért itt,
    mert a plugin registry `getattr(module, class_name)`-nel oldja fel a
    dotted_path-ot, ami nem tud egy függvényen belül definiált (nested,
    `<locals>` qualname-ű) osztályt megtalálni."""

    def __init__(self, **params: object) -> None:
        raise NotImplementedError("még nincs implementálva")


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
    """Egy még-nem-implementált (stub) adapter import-biztos legyen (fail-fast a
    registry-feloldásnál működik), de példányosításkor NotImplementedError-t
    dobjon. Saját, self-contained stubot regisztrálunk a teszthez, hogy ez a
    teszt ne öregedjen el amint az egyes valódi ML-adapterek elkészülnek (3.
    fázis modulonként halad)."""
    plugin_registry.register(
        "asr", "still-a-stub-for-test", f"{_StillAStub.__module__}:{_StillAStub.__qualname__}"
    )
    with pytest.raises(NotImplementedError):
        plugin_registry.instantiate("asr", "still-a-stub-for-test", {})


def test_register_allows_adding_new_adapters_without_editing_the_module():
    plugin_registry.register("asr", "custom-test-adapter", "leiratozo.adapters.asr.fake:FakeTranscriptionEngine")
    ref = plugin_registry.resolve("asr", "custom-test-adapter")
    assert ref.adapter_name == "custom-test-adapter"
