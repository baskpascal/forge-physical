from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_build import api
from hardware_build.service import create_build
from hardware_build.settings import Settings
from hardware_build.storage import (
    BuildAdmissionRejected,
    BuildAdmissionUnavailable,
    FirestoreBuildStore,
    LocalJsonBuildStore,
)


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "build_data_dir": tmp_path / "data",
        "build_artifact_dir": tmp_path / "artifacts",
        "build_max_concurrent": 2,
        "build_request_budget": 2,
        "build_request_window_seconds": 60,
        "build_lease_seconds": 30,
    }
    values.update(overrides)
    return Settings(**values)


def test_client_budget_rejects_without_creating_an_orphan(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path, build_request_budget=1)

    create_build(
        "Build a supported low voltage temperature alarm",
        dispatch=False,
        store=store,
        settings=settings,
        client_key="judge",
    )

    with pytest.raises(BuildAdmissionRejected) as caught:
        create_build(
            "Build another supported low voltage temperature alarm",
            dispatch=False,
            store=store,
            settings=settings,
            client_key="judge",
        )

    assert caught.value.reason == "client_budget"
    assert len(list(store.root.glob("*.json"))) == 1


def test_concurrent_reservations_never_exceed_global_cap(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path, build_request_budget=10)

    def reserve(index: int) -> bool:
        try:
            store.reserve_build(f"build-{index}", f"client-{index}", settings)
        except BuildAdmissionRejected:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        admitted = list(executor.map(reserve, range(8)))

    assert sum(admitted) == settings.build_max_concurrent


def test_expired_lease_and_budget_are_reclaimed(tmp_path: Path, monkeypatch):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path, build_max_concurrent=1, build_request_budget=1)
    clock = iter((100.0, 200.0))
    monkeypatch.setattr("hardware_build.storage.time.time", lambda: next(clock))

    store.reserve_build("first", "judge", settings)
    store.reserve_build("second", "judge", settings)

    assert "second" in store._active_leases


def test_api_returns_retry_after_for_capacity_rejection(monkeypatch):
    def rejected(*_args, **_kwargs):
        raise BuildAdmissionRejected("global_concurrency", 17)

    monkeypatch.setattr(api, "create_build", rejected)
    response = TestClient(api.app).post(
        "/api/builds",
        headers={"Origin": "http://localhost:3000"},
        json={"prompt": "Build a supported temperature alarm"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "17"
    assert "Retry-After" in response.headers["access-control-expose-headers"]


def test_api_fails_closed_when_admission_storage_is_unavailable(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise BuildAdmissionUnavailable("offline")

    monkeypatch.setattr(api, "create_build", unavailable)
    response = TestClient(api.app).post(
        "/api/builds",
        json={"prompt": "Build a supported temperature alarm"},
    )

    assert response.status_code == 503
    assert response.headers["retry-after"] == "30"


def test_limits_can_be_disabled_for_trusted_internal_execution(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path, build_max_concurrent=0, build_request_budget=0)

    for index in range(5):
        store.reserve_build(f"build-{index}", "trusted", settings)

    assert store._active_leases == {}


class _Snapshot:
    def __init__(self, payload=None, *, exists=True):
        self.exists = exists
        self._payload = payload or {}

    def to_dict(self):
        return self._payload


class _Reference:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def get(self, *, transaction):
        return self.snapshot


class _Transaction:
    def __init__(self):
        self.writes = []

    def set(self, reference, payload):
        self.writes.append(("set", reference, payload))

    def update(self, reference, payload):
        self.writes.append(("update", reference, payload))


class _FirestoreClient:
    def __init__(self, snapshot):
        self.reference = _Reference(snapshot)
        self.transaction_instance = _Transaction()

    def collection(self, _name):
        return self

    def document(self, _name):
        return self.reference

    def transaction(self):
        return self.transaction_instance


def _firestore_store(snapshot):
    store = FirestoreBuildStore.__new__(FirestoreBuildStore)
    store.client = _FirestoreClient(snapshot)
    return store


def test_firestore_admission_persists_lease_and_prunes_expired_clients(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr("hardware_build.storage.firestore.transactional", lambda function: function)
    monkeypatch.setattr("hardware_build.storage.time.time", lambda: 100.0)
    snapshot = _Snapshot(
        {
            "leases": {"expired": 90.0},
            "requests": {"old-client": [1.0], "current": [90.0]},
        }
    )
    store = _firestore_store(snapshot)

    store.reserve_build("new-build", "current", _settings(tmp_path))

    _, _, payload = store.client.transaction_instance.writes[0]
    assert payload["leases"] == {"new-build": 130.0}
    assert payload["requests"] == {"current": [90.0, 100.0]}


def test_firestore_admission_failure_is_reported_as_unavailable(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("hardware_build.storage.firestore.transactional", lambda function: function)

    class BrokenReference(_Reference):
        def get(self, *, transaction):
            raise OSError("firestore offline")

    store = _firestore_store(_Snapshot())
    store.client.reference = BrokenReference(_Snapshot())

    with pytest.raises(BuildAdmissionUnavailable):
        store.reserve_build("new-build", "current", _settings(tmp_path))
