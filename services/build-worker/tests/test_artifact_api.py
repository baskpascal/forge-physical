import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from hardware_build import api
from hardware_build.models import Build
from hardware_build.settings import Settings


def _settings(tmp_path: Path, *, bucket: str | None = None) -> Settings:
    return Settings(build_artifact_dir=tmp_path / "artifacts", artifact_bucket=bucket)


def _allow_artifact(monkeypatch, artifact_path: str, *, build_id: str = "build-1") -> None:
    build = Build(
        id=build_id,
        prompt="Build a desk monitor",
        artifact_paths={"fixture": f"{build_id}/{artifact_path}"},
    )

    class Store:
        def get(self, build_id: str) -> Build:
            assert build_id == build.id
            return build

    monkeypatch.setattr(api, "get_store", Store)


def test_artifact_archive_includes_only_recorded_public_files(tmp_path: Path, monkeypatch):
    settings = _settings(tmp_path)
    recorded = settings.build_artifact_dir / "build-1" / "hardware/enclosure/base.stl"
    unrecorded = settings.build_artifact_dir / "build-1" / "hardware/enclosure/lid.stl"
    recorded.parent.mkdir(parents=True)
    recorded.write_bytes(b"recorded")
    unrecorded.write_bytes(b"unrecorded")
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    _allow_artifact(monkeypatch, "hardware/enclosure/base.stl")

    response = TestClient(api.app).get("/api/builds/build-1/artifacts.zip")

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.namelist() == ["hardware/enclosure/base.stl"]
        assert archive.read("hardware/enclosure/base.stl") == b"recorded"


def test_artifact_archive_rejects_invalid_build_id(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(api, "get_settings", lambda: _settings(tmp_path))

    response = TestClient(api.app).get("/api/builds/bad$id/artifacts.zip")

    assert response.status_code == 404


def test_artifact_archive_rejects_recorded_but_unavailable_files(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(api, "get_settings", lambda: _settings(tmp_path))
    _allow_artifact(monkeypatch, "hardware/enclosure/base.stl")

    response = TestClient(api.app).get("/api/builds/build-1/artifacts.zip")

    assert response.status_code == 404
    assert response.json()["detail"] == "No artifacts are available yet"


def test_individual_artifact_serves_local_stl(tmp_path: Path, monkeypatch):
    settings = _settings(tmp_path)
    path = settings.build_artifact_dir / "build-1" / "hardware/enclosure/base.stl"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"solid enclosure\nendsolid enclosure\n")
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    _allow_artifact(monkeypatch, "hardware/enclosure/base.stl")

    response = TestClient(api.app).get(
        "/api/builds/build-1/artifacts/hardware/enclosure/base.stl"
    )

    assert response.status_code == 200
    assert response.content.startswith(b"solid enclosure")
    assert response.headers["content-type"] == "model/stl"


def test_individual_artifact_rejects_traversal_and_internal_paths(tmp_path: Path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    _allow_artifact(monkeypatch, "hardware/enclosure/base.stl")
    client = TestClient(api.app)

    assert client.get(
        "/api/builds/build-1/artifacts/hardware/firmware/.pio/libdeps/private.txt"
    ).status_code == 404
    assert client.get(
        "/api/builds/build-1/artifacts/%2e%2e/data/build.json"
    ).status_code == 404


def test_individual_artifact_rejects_public_file_not_recorded_on_build(
    tmp_path: Path, monkeypatch
):
    settings = _settings(tmp_path)
    path = settings.build_artifact_dir / "build-1" / "hardware/enclosure/unlisted.stl"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"solid unlisted\nendsolid unlisted\n")
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    _allow_artifact(monkeypatch, "hardware/enclosure/base.stl")

    response = TestClient(api.app).get(
        "/api/builds/build-1/artifacts/hardware/enclosure/unlisted.stl"
    )

    assert response.status_code == 404


def test_individual_artifact_returns_pending_404(tmp_path: Path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    _allow_artifact(monkeypatch, "hardware/enclosure/lid.stl")

    response = TestClient(api.app).get(
        "/api/builds/build-1/artifacts/hardware/enclosure/lid.stl"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Artifact is not available yet"


def test_individual_artifact_falls_back_to_cloud_storage(tmp_path: Path, monkeypatch):
    settings = _settings(tmp_path, bucket="artifact-bucket")
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    _allow_artifact(monkeypatch, "hardware/enclosure/lid.stl")

    class Blob:
        content_type = None

        def exists(self):
            return True

        def download_as_bytes(self):
            return b"cloud-stl"

    class Bucket:
        def blob(self, name):
            assert name == "build-1/hardware/enclosure/lid.stl"
            return Blob()

    class Client:
        def bucket(self, name):
            assert name == "artifact-bucket"
            return Bucket()

    monkeypatch.setattr(api.storage, "Client", Client)
    response = TestClient(api.app).get(
        "/api/builds/build-1/artifacts/hardware/enclosure/lid.stl"
    )

    assert response.status_code == 200
    assert response.content == b"cloud-stl"
    assert response.headers["content-type"] == "model/stl"
