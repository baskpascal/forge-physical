from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_build import api
from hardware_build.service import (
    DispatchNotAccepted,
    DispatchOutcomeUnknown,
    create_build,
    try_dispatch_build,
)
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
        client_key="test-client",
    )

    with pytest.raises(BuildAdmissionRejected) as caught:
        create_build(
            "Build another supported low voltage temperature alarm",
            dispatch=False,
            store=store,
            settings=settings,
            client_key="test-client",
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


def test_fourth_build_is_queued_instead_of_capacity_429(tmp_path: Path, monkeypatch):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path, build_max_concurrent=3, build_request_budget=20)
    monkeypatch.setattr("hardware_build.service.dispatch_build", lambda *_args, **_kwargs: None)

    responses = [
        create_build(
            f"Build supported low voltage temperature alarm {index}",
            store=store,
            settings=settings,
            client_key="test-client",
        )
        for index in range(4)
    ]

    assert [response.queue_position for response in responses] == [0, 0, 0, 1]
    assert responses[3].status.value == "queued"


def test_queue_claim_is_idempotent(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path)
    build = create_build(
        "Build a supported low voltage alarm",
        dispatch=False,
        store=store,
        settings=settings,
    )

    assert store.claim_build(build.build_id, settings).claimed
    assert not store.claim_build(build.build_id, settings).claimed


def test_expired_lease_and_budget_are_reclaimed(tmp_path: Path, monkeypatch):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path, build_max_concurrent=1, build_request_budget=1)
    clock = iter((100.0, 200.0))
    monkeypatch.setattr("hardware_build.storage.time.time", lambda: next(clock))

    store.reserve_build("first", "test-client", settings)
    store.reserve_build("second", "test-client", settings)

    assert "second" in store._active_leases


def test_api_never_reports_capacity_as_rate_limit(monkeypatch):
    def rejected(*_args, **_kwargs):
        raise BuildAdmissionRejected("global_concurrency", 17)

    monkeypatch.setattr(api, "create_build", rejected)
    response = TestClient(api.app).post(
        "/api/builds",
        headers={"Origin": "http://localhost:3000"},
        json={"prompt": "Build a supported temperature alarm"},
    )

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert "Retry-After" in response.headers["access-control-expose-headers"]


def test_api_returns_429_only_for_abuse_budget(monkeypatch):
    def rejected(*_args, **_kwargs):
        raise BuildAdmissionRejected("client_budget", 17)

    monkeypatch.setattr(api, "create_build", rejected)
    response = TestClient(api.app).post(
        "/api/builds",
        json={"prompt": "Build a supported temperature alarm"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "17"
    assert "request limit" in response.json()["detail"].lower()


def test_start_requires_live_lease_and_is_idempotent(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path)
    response = create_build(
        "Build a supported low voltage alarm",
        dispatch=False,
        store=store,
        settings=settings,
    )

    assert store.start_execution(response.build_id) is None
    assert store.claim_build(response.build_id, settings).claimed
    started = store.start_execution(response.build_id)
    assert started is not None and started.status.value == "planning"
    assert store.start_execution(response.build_id) is None


def test_expired_running_lease_is_requeued_and_reclaimable(tmp_path: Path, monkeypatch):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path, build_max_concurrent=1, build_lease_seconds=30)
    clock = {"now": 100.0}
    monkeypatch.setattr("hardware_build.storage.time.time", lambda: clock["now"])
    response = create_build(
        "Build a supported low voltage alarm",
        dispatch=False,
        store=store,
        settings=settings,
    )
    assert store.claim_build(response.build_id, settings).claimed
    assert store.start_execution(response.build_id) is not None

    clock["now"] = 131.0
    assert store.reconcile_expired_leases() == [response.build_id]
    recovered = store.get(response.build_id)
    assert recovered.status.value == "queued"
    assert recovered.execution_started_at is None
    assert store.claim_build(response.build_id, settings).claimed


def test_fifo_position_counts_waiters_ahead(tmp_path: Path):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path, build_max_concurrent=1, build_request_budget=20)
    builds = [
        create_build(
            f"Build supported low voltage alarm {index}",
            dispatch=False,
            store=store,
            settings=settings,
            client_key=str(index),
        )
        for index in range(3)
    ]
    assert store.claim_build(builds[0].build_id, settings).claimed
    claim = store.claim_build(builds[2].build_id, settings)
    assert not claim.claimed
    assert claim.position == 2


def test_dispatch_timeout_after_accept_retains_lease(tmp_path: Path, monkeypatch):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path)
    response = create_build(
        "Build a supported low voltage alarm",
        dispatch=False,
        store=store,
        settings=settings,
    )
    monkeypatch.setattr(
        "hardware_build.service.dispatch_build",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(DispatchOutcomeUnknown("timeout")),
    )

    assert try_dispatch_build(response.build_id, settings, store) == 0
    assert store.has_active_lease(response.build_id)
    event_types = [event.type for event in store.events(response.build_id)]
    assert "build.dispatch.pending_confirmation" in event_types


def test_definitive_dispatch_failure_releases_lease(tmp_path: Path, monkeypatch):
    store = LocalJsonBuildStore(tmp_path / "data")
    settings = _settings(tmp_path)
    response = create_build(
        "Build a supported low voltage alarm",
        dispatch=False,
        store=store,
        settings=settings,
    )
    monkeypatch.setattr(
        "hardware_build.service.dispatch_build",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(DispatchNotAccepted("rejected")),
    )

    assert try_dispatch_build(response.build_id, settings, store) == 1
    assert not store.has_active_lease(response.build_id)


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


def test_firestore_queue_preserves_fifo_without_composite_index(monkeypatch):
    class QueueSnapshot:
        def __init__(self, build_id, created_at):
            self.id = build_id
            self.created_at = created_at

        def to_dict(self):
            return {"status": "queued", "created_at": self.created_at}

    class EqualityQuery:
        def __init__(self):
            self.filter = None

        def where(self, field, operator, value):
            self.filter = (field, operator, value)
            return self

        def order_by(self, _field):
            raise AssertionError("Queue admission must not require a composite index")

        def stream(self):
            return iter(
                [
                    QueueSnapshot("later", "2026-01-02T00:00:00+00:00"),
                    QueueSnapshot("first-b", "2026-01-01T00:00:00+00:00"),
                    QueueSnapshot("first-a", "2026-01-01T00:00:00+00:00"),
                ]
            )

    query = EqualityQuery()
    store = FirestoreBuildStore.__new__(FirestoreBuildStore)
    store.client = type("Client", (), {"collection": lambda _self, _name: query})()
    monkeypatch.setattr(store, "reconcile_expired_leases", lambda: [])

    assert store.queued_build_ids() == ["first-a", "first-b", "later"]
    assert query.filter == ("status", "==", "queued")
