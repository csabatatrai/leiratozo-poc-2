"""API-réteg integrációs smoke teszt: fake-adapteres configgal felépített
FastAPI app, a docs/phase1-terv.md 9. szakasz végpont-kontraktusa szerint.

A WebSocket élő végpont vezénylését a unit/integrációs tesztek (streaming
adapter, live diarizáció) már lefedik tiszta domain-szinten; itt csak azt
ellenőrizzük, hogy a route regisztrálva van — a TestClient szinkron
websocket-kezelése és az async generátor alapú streaming együtt könnyen
instabil tesztet adna, ami nem éri meg a kockázatot a skeleton fázisban."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

from leiratozo.api.app import create_app
from leiratozo.config.schema import AppConfig


def _client(fake_config: AppConfig) -> TestClient:
    app = create_app(fake_config)
    return TestClient(app)


def test_health_and_ready(fake_config: AppConfig):
    with _client(fake_config) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        ready_body = client.get("/readyz").json()
        assert ready_body == {"status": "ready", "degraded_ports": {}}


def test_runtime_config_reports_selected_adapters(fake_config: AppConfig):
    with _client(fake_config) as client:
        body = client.get("/v1/config").json()
        assert body["schema_version"] == "1.0"
        assert body["models"]["asr"]["adapter"] == "fake"
        assert body["models"]["diarization_batch"]["adapter"] == "fake"


def _all_paths(routes) -> set[str]:
    """Rekurzívan bejárja az app.routes-ot, beleértve a FastAPI újabb
    verzióiban include_router mögött megjelenő `_IncludedRouter` wrappert
    (`.original_router.routes`) is."""
    paths: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            paths |= _all_paths(getattr(original_router, "routes", []))
        sub_routes = getattr(route, "routes", None)
        if sub_routes:
            paths |= _all_paths(sub_routes)
    return paths


def test_live_websocket_route_is_registered(fake_config: AppConfig):
    app = create_app(fake_config)
    assert "/v1/live/{session_id}" in _all_paths(app.routes)


def test_batch_job_submit_status_and_result_round_trip(fake_config: AppConfig):
    with _client(fake_config) as client:
        raw_audio = b"\x00\x01" * 16000 * 2  # ~2s 16kHz 16-bit mono
        files = {"file": ("sample.wav", io.BytesIO(raw_audio), "audio/wav")}

        submit_resp = client.post("/v1/jobs", files=files)
        assert submit_resp.status_code == 202
        job_id = submit_resp.json()["job_id"]

        status_resp = client.get(f"/v1/jobs/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "done"

        result_resp = client.get(f"/v1/jobs/{job_id}/result")
        assert result_resp.status_code == 200
        document = result_resp.json()
        assert document["schema_version"] == "1.0"
        assert document["segments"]


def test_unknown_job_result_is_404(fake_config: AppConfig):
    with _client(fake_config) as client:
        resp = client.get("/v1/jobs/does-not-exist/result")
        assert resp.status_code == 404


def test_speaker_register_list_delete_round_trip(fake_config: AppConfig):
    with _client(fake_config) as client:
        files = {"file": ("enroll.wav", io.BytesIO(b"\x00\x01" * 16000 * 3), "audio/wav")}

        register_resp = client.post("/v1/speakers", files=files, params={"display_name": "Teszt Elek"})
        assert register_resp.status_code == 201
        profile_id = register_resp.json()["profile_id"]

        list_resp = client.get("/v1/speakers")
        assert any(p["profile_id"] == profile_id for p in list_resp.json())

        delete_resp = client.delete(f"/v1/speakers/{profile_id}")
        assert delete_resp.status_code == 204

        list_after_delete = client.get("/v1/speakers").json()
        assert all(p["profile_id"] != profile_id for p in list_after_delete)


def test_delete_unknown_speaker_is_404(fake_config: AppConfig):
    with _client(fake_config) as client:
        resp = client.delete("/v1/speakers/spk_does-not-exist")
        assert resp.status_code == 404
