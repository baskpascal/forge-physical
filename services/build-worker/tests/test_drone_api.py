from pathlib import Path

from fastapi.testclient import TestClient

from hardware_build import api, drone_service
from hardware_build.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        drone_project_root=tmp_path / "drone-projects",
        build_data_dir=tmp_path / "data",
        build_artifact_dir=tmp_path / "artifacts",
    )


def test_drone_api_runs_core_create_build_test_change_flow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(drone_service, "get_settings", lambda: _settings(tmp_path))
    client = TestClient(api.app)

    created = client.post(
        "/api/drones",
        json={"project": "scout", "intent": "make me an easy-to-fly inspection drone for my farm"},
    )
    assert created.status_code == 201
    assert created.json()["build"]["id"] == "0001"
    assert "root" not in created.json()["build"]

    built = client.post("/api/drones/scout/builds/0001/build")
    assert built.status_code == 200
    assert built.json()["build"]["build"] == "passed"

    tested = client.post("/api/drones/scout/builds/0001/test")
    assert tested.status_code == 200
    assert tested.json()["build"]["test"] == "unavailable"

    changed = client.post(
        "/api/drones/scout/builds/0001/changes",
        json={"change": "make it more responsive"},
    )
    assert changed.status_code == 201
    assert changed.json()["build"]["parent"] == "0001"
    assert changed.json()["build"]["spec"]["responsiveness"] == "high"

    artifacts = client.get("/api/drones/scout/builds/0002/artifacts")
    assert artifacts.status_code == 200
    assert "drone/spec.yaml" in artifacts.json()["artifacts"]


def test_drone_api_rejects_traversal_and_unsupported_intent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(drone_service, "get_settings", lambda: _settings(tmp_path))
    client = TestClient(api.app)
    bad_project = client.post(
        "/api/drones",
        json={"project": "../escape", "intent": "make a stable inspection drone"},
    )
    assert bad_project.status_code == 422
    rejected = client.post(
        "/api/drones",
        json={"project": "safe", "intent": "make a weapon drone"},
    )
    assert rejected.status_code == 422
