from __future__ import annotations

import json
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from google.cloud import firestore

from .models import Build, BuildEvent, BuildStatus, now_iso
from .settings import Settings, get_settings


class BuildNotFoundError(KeyError):
    pass


class BuildAdmissionRejected(RuntimeError):
    def __init__(self, reason: str, retry_after: int):
        super().__init__(reason)
        self.reason = reason
        self.retry_after = max(1, retry_after)


class BuildAdmissionUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class QueueClaim:
    claimed: bool
    position: int | None = None


class BuildStore(ABC):
    @abstractmethod
    def create(self, build: Build) -> None: ...

    @abstractmethod
    def save(self, build: Build) -> None: ...

    @abstractmethod
    def get(self, build_id: str) -> Build: ...

    @abstractmethod
    def add_event(self, build_id: str, event: BuildEvent) -> None: ...

    @abstractmethod
    def events(self, build_id: str) -> list[BuildEvent]: ...

    @abstractmethod
    def check_request_budget(self, client_key: str, settings: Settings) -> None: ...

    @abstractmethod
    def claim_build(self, build_id: str, settings: Settings) -> QueueClaim: ...

    @abstractmethod
    def start_execution(self, build_id: str) -> Build | None: ...

    @abstractmethod
    def has_active_lease(self, build_id: str) -> bool: ...

    @abstractmethod
    def renew_build(self, build_id: str, settings: Settings) -> bool: ...

    @abstractmethod
    def queued_build_ids(self) -> list[str]: ...

    @abstractmethod
    def release_build(self, build_id: str) -> None: ...

    @abstractmethod
    def reconcile_expired_leases(self) -> list[str]: ...


class LocalJsonBuildStore(BuildStore):
    """Durable local adapter for development; production uses FirestoreBuildStore."""

    def __init__(self, root: Path):
        self.root = root / "builds"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._active_leases: dict[str, float] = {}
        self._request_times: defaultdict[str, list[float]] = defaultdict(list)

    def _path(self, build_id: str) -> Path:
        return self.root / f"{build_id}.json"

    def _read(self, build_id: str) -> dict:
        path = self._path(build_id)
        if not path.exists():
            raise BuildNotFoundError(build_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, build_id: str, payload: dict) -> None:
        path = self._path(build_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(path)

    def create(self, build: Build) -> None:
        with self._lock:
            if self._path(build.id).exists():
                raise ValueError(f"Build already exists: {build.id}")
            self._write(build.id, {"build": build.model_dump(mode="json"), "events": []})

    def save(self, build: Build) -> None:
        with self._lock:
            payload = self._read(build.id)
            build.updated_at = now_iso()
            payload["build"] = build.model_dump(mode="json")
            self._write(build.id, payload)

    def get(self, build_id: str) -> Build:
        with self._lock:
            return Build.model_validate(self._read(build_id)["build"])

    def add_event(self, build_id: str, event: BuildEvent) -> None:
        with self._lock:
            payload = self._read(build_id)
            payload["events"].append(event.model_dump(mode="json"))
            self._write(build_id, payload)

    def events(self, build_id: str) -> list[BuildEvent]:
        with self._lock:
            return [BuildEvent.model_validate(item) for item in self._read(build_id)["events"]]

    def check_request_budget(self, client_key: str, settings: Settings) -> None:
        if settings.build_request_budget <= 0:
            return
        with self._lock:
            now = time.time()
            requests = [
                timestamp
                for timestamp in self._request_times[client_key]
                if timestamp > now - settings.build_request_window_seconds
            ]
            self._request_times[client_key] = requests
            if settings.build_request_budget > 0 and len(requests) >= settings.build_request_budget:
                retry_after = int(requests[0] + settings.build_request_window_seconds - now) + 1
                raise BuildAdmissionRejected("client_budget", retry_after)
            requests.append(now)

    # Backwards-compatible name for callers outside the package. Capacity is intentionally
    # not reserved here anymore; builds queue before they claim an execution slot.
    def reserve_build(self, build_id: str, client_key: str, settings: Settings) -> None:
        if settings.build_max_concurrent <= 0 and settings.build_request_budget <= 0:
            return
        with self._lock:
            now = time.time()
            self._prune_leases(now)
            requests = [
                timestamp
                for timestamp in self._request_times[client_key]
                if timestamp > now - settings.build_request_window_seconds
            ]
            if settings.build_max_concurrent > 0 and len(self._active_leases) >= settings.build_max_concurrent:
                retry_after = int(min(self._active_leases.values()) - now) + 1
                raise BuildAdmissionRejected("global_concurrency", retry_after)
            if settings.build_request_budget > 0 and len(requests) >= settings.build_request_budget:
                retry_after = int(requests[0] + settings.build_request_window_seconds - now) + 1
                raise BuildAdmissionRejected("client_budget", retry_after)
            self._active_leases[build_id] = now + settings.build_lease_seconds
            requests.append(now)
            self._request_times[client_key] = requests

    def _prune_leases(self, now: float) -> None:
        self._active_leases = {
            key: expiry for key, expiry in self._active_leases.items() if expiry > now
        }

    def reconcile_expired_leases(self) -> list[str]:
        """Return orphaned in-flight builds to FIFO after their worker lease expires."""
        with self._lock:
            now = time.time()
            expired = [build_id for build_id, expiry in self._active_leases.items() if expiry <= now]
            self._prune_leases(now)
            recovered: list[str] = []
            for build_id in expired:
                try:
                    build = self.get(build_id)
                except BuildNotFoundError:
                    continue
                was_in_flight = build.status.value in {
                    "planning", "building", "testing", "repairing"
                }
                if was_in_flight:
                    build.status = BuildStatus.QUEUED
                    build.queue_position = None
                    build.execution_started_at = None
                if was_in_flight or build.status.value == "queued":
                    build.dispatch_requested_at = None
                    self.save(build)
                    self.add_event(
                        build_id,
                        BuildEvent(
                            id=f"lease-expired-{int(now * 1000)}",
                            type="build.lease.expired",
                            stage=build.stage,
                            status="queued",
                            message="Worker lease expired; build returned to the execution queue.",
                            metadata={"recovery": "automatic"},
                        ),
                    )
                    recovered.append(build_id)
            return recovered

    def queued_build_ids(self) -> list[str]:
        with self._lock:
            self.reconcile_expired_leases()
            queued: list[Build] = []
            for path in self.root.glob("*.json"):
                build = Build.model_validate(json.loads(path.read_text(encoding="utf-8"))["build"])
                if build.status.value == "queued":
                    queued.append(build)
            return [build.id for build in sorted(queued, key=lambda item: item.created_at)]

    def claim_build(self, build_id: str, settings: Settings) -> QueueClaim:
        with self._lock:
            now = time.time()
            self._prune_leases(now)
            if build_id in self._active_leases:
                return QueueClaim(False, None)
            queued = self.queued_build_ids()
            if build_id not in queued:
                return QueueClaim(False, None)
            if settings.build_max_concurrent > 0 and len(self._active_leases) >= settings.build_max_concurrent:
                waiting = [queued_id for queued_id in queued if queued_id not in self._active_leases]
                return QueueClaim(False, waiting.index(build_id) + 1)
            self._active_leases[build_id] = now + settings.build_lease_seconds
            return QueueClaim(True, 0)

    def start_execution(self, build_id: str) -> Build | None:
        with self._lock:
            self._prune_leases(time.time())
            if build_id not in self._active_leases:
                return None
            build = self.get(build_id)
            if build.status.value != "queued":
                return None
            build.status = BuildStatus.PLANNING
            build.execution_started_at = now_iso()
            build.queue_position = 0
            self.save(build)
            return build

    def has_active_lease(self, build_id: str) -> bool:
        with self._lock:
            self._prune_leases(time.time())
            return build_id in self._active_leases

    def renew_build(self, build_id: str, settings: Settings) -> bool:
        with self._lock:
            now = time.time()
            self._prune_leases(now)
            if build_id not in self._active_leases:
                return False
            self._active_leases[build_id] = now + settings.build_lease_seconds
            return True

    def release_build(self, build_id: str) -> None:
        with self._lock:
            self._active_leases.pop(build_id, None)


class FirestoreBuildStore(BuildStore):
    """Firestore is the production source of truth for builds and event streams."""

    def __init__(self, project: str | None):
        self.client = firestore.Client(project=project)

    def _ref(self, build_id: str):
        return self.client.collection("builds").document(build_id)

    def create(self, build: Build) -> None:
        self._ref(build.id).create(build.model_dump(mode="json"))

    def save(self, build: Build) -> None:
        build.updated_at = now_iso()
        self._ref(build.id).set(build.model_dump(mode="json"), merge=False)

    def get(self, build_id: str) -> Build:
        snapshot = self._ref(build_id).get()
        if not snapshot.exists:
            raise BuildNotFoundError(build_id)
        return Build.model_validate(snapshot.to_dict())

    def add_event(self, build_id: str, event: BuildEvent) -> None:
        self._ref(build_id).collection("events").document(event.id).set(event.model_dump(mode="json"))

    def events(self, build_id: str) -> list[BuildEvent]:
        query = self._ref(build_id).collection("events").order_by("created_at")
        return [BuildEvent.model_validate(snapshot.to_dict()) for snapshot in query.stream()]

    def _admission_ref(self):
        return self.client.collection("system").document("build-admission")

    def check_request_budget(self, client_key: str, settings: Settings) -> None:
        if settings.build_request_budget <= 0:
            return
        transaction = self.client.transaction()
        reference = self._admission_ref()

        @firestore.transactional
        def reserve(transaction):
            snapshot = reference.get(transaction=transaction)
            payload = snapshot.to_dict() if snapshot.exists else {}
            now = time.time()
            request_map = {
                key: recent
                for key, timestamps in payload.get("requests", {}).items()
                if (
                    recent := [
                        float(timestamp)
                        for timestamp in timestamps
                        if float(timestamp) > now - settings.build_request_window_seconds
                    ]
                )
            }
            requests = request_map.get(client_key, [])
            if settings.build_request_budget > 0 and len(requests) >= settings.build_request_budget:
                retry_after = int(requests[0] + settings.build_request_window_seconds - now) + 1
                raise BuildAdmissionRejected("client_budget", retry_after)
            requests.append(now)
            request_map[client_key] = requests
            if len(request_map) > 256:
                newest_clients = sorted(
                    request_map,
                    key=lambda key: request_map[key][-1],
                    reverse=True,
                )[:256]
                request_map = {key: request_map[key] for key in newest_clients}
            transaction.set(reference, {**payload, "requests": request_map, "updated_at": now_iso()})

        try:
            reserve(transaction)
        except BuildAdmissionRejected:
            raise
        except Exception as exc:
            raise BuildAdmissionUnavailable("Build admission storage is unavailable") from exc

    def reserve_build(self, build_id: str, client_key: str, settings: Settings) -> None:
        transaction = self.client.transaction()
        reference = self._admission_ref()

        @firestore.transactional
        def reserve(transaction):
            snapshot = reference.get(transaction=transaction)
            payload = snapshot.to_dict() if snapshot.exists else {}
            now = time.time()
            leases = {key: float(expiry) for key, expiry in payload.get("leases", {}).items() if float(expiry) > now}
            request_map = {
                key: recent
                for key, timestamps in payload.get("requests", {}).items()
                if (recent := [float(value) for value in timestamps if float(value) > now - settings.build_request_window_seconds])
            }
            requests = request_map.get(client_key, [])
            if settings.build_max_concurrent > 0 and len(leases) >= settings.build_max_concurrent:
                raise BuildAdmissionRejected("global_concurrency", int(min(leases.values()) - now) + 1)
            if settings.build_request_budget > 0 and len(requests) >= settings.build_request_budget:
                raise BuildAdmissionRejected("client_budget", int(requests[0] + settings.build_request_window_seconds - now) + 1)
            leases[build_id] = now + settings.build_lease_seconds
            requests.append(now)
            request_map[client_key] = requests
            transaction.set(reference, {"leases": leases, "requests": request_map, "updated_at": now_iso()})

        try:
            reserve(transaction)
        except BuildAdmissionRejected:
            raise
        except Exception as exc:
            raise BuildAdmissionUnavailable("Build admission storage is unavailable") from exc

    def queued_build_ids(self) -> list[str]:
        self.reconcile_expired_leases()
        query = self.client.collection("builds").where("status", "==", "queued").order_by("created_at")
        return [snapshot.id for snapshot in query.stream()]

    def claim_build(self, build_id: str, settings: Settings) -> QueueClaim:
        queued = self.queued_build_ids()
        if build_id not in queued:
            return QueueClaim(False, None)
        transaction = self.client.transaction()
        reference = self._admission_ref()
        build_reference = self._ref(build_id)

        @firestore.transactional
        def claim(transaction):
            build_snapshot = build_reference.get(transaction=transaction)
            if not build_snapshot.exists or build_snapshot.to_dict().get("status") != "queued":
                return QueueClaim(False, None)
            snapshot = reference.get(transaction=transaction)
            payload = snapshot.to_dict() if snapshot.exists else {}
            now = time.time()
            leases = {
                key: float(expiry)
                for key, expiry in payload.get("leases", {}).items()
                if float(expiry) > now
            }
            if build_id in leases:
                return QueueClaim(False, None)
            if settings.build_max_concurrent > 0 and len(leases) >= settings.build_max_concurrent:
                waiting = [queued_id for queued_id in queued if queued_id not in leases]
                return QueueClaim(False, waiting.index(build_id) + 1)
            waiting = [queued_id for queued_id in queued if queued_id not in leases]
            if waiting and waiting[0] != build_id:
                return QueueClaim(False, waiting.index(build_id) + 1)
            leases[build_id] = now + settings.build_lease_seconds
            transaction.set(reference, {**payload, "leases": leases, "updated_at": now_iso()})
            transaction.update(build_reference, {"queue_position": 0})
            return QueueClaim(True, 0)

        try:
            return claim(transaction)
        except Exception as exc:
            raise BuildAdmissionUnavailable("Build queue storage is unavailable") from exc

    def start_execution(self, build_id: str) -> Build | None:
        transaction = self.client.transaction()
        reference = self._ref(build_id)
        admission_reference = self._admission_ref()

        @firestore.transactional
        def start(transaction):
            admission_snapshot = admission_reference.get(transaction=transaction)
            leases = admission_snapshot.to_dict().get("leases", {}) if admission_snapshot.exists else {}
            if float(leases.get(build_id, 0)) <= time.time():
                return None
            snapshot = reference.get(transaction=transaction)
            if not snapshot.exists or snapshot.to_dict().get("status") != "queued":
                return None
            started_at = now_iso()
            transaction.update(
                reference,
                {"status": "planning", "execution_started_at": started_at, "queue_position": 0},
            )
            payload = snapshot.to_dict()
            payload["status"] = "planning"
            payload["execution_started_at"] = started_at
            payload["queue_position"] = 0
            return Build.model_validate(payload)

        return start(transaction)

    def has_active_lease(self, build_id: str) -> bool:
        snapshot = self._admission_ref().get()
        if not snapshot.exists:
            return False
        expiry = snapshot.to_dict().get("leases", {}).get(build_id)
        return expiry is not None and float(expiry) > time.time()

    def reconcile_expired_leases(self) -> list[str]:
        """Best-effort recovery; each build update is guarded by the admission transaction."""
        snapshot = self._admission_ref().get()
        if not snapshot.exists:
            return []
        now = time.time()
        expired = [
            build_id
            for build_id, expiry in snapshot.to_dict().get("leases", {}).items()
            if float(expiry) <= now
        ]
        recovered: list[str] = []
        for build_id in expired:
            transaction = self.client.transaction()
            admission_reference = self._admission_ref()
            build_reference = self._ref(build_id)

            @firestore.transactional
            def recover(
                transaction,
                admission_reference=admission_reference,
                build_reference=build_reference,
                build_id=build_id,
            ):
                admission = admission_reference.get(transaction=transaction)
                payload = admission.to_dict() if admission.exists else {}
                leases = dict(payload.get("leases", {}))
                if float(leases.get(build_id, now + 1)) > now:
                    return False
                leases.pop(build_id, None)
                build_snapshot = build_reference.get(transaction=transaction)
                status = build_snapshot.to_dict().get("status") if build_snapshot.exists else None
                was_in_flight = status in {
                    "planning", "building", "testing", "repairing"
                }
                if was_in_flight:
                    transaction.update(
                        build_reference,
                        {
                            "status": "queued",
                            "queue_position": None,
                            "dispatch_requested_at": None,
                            "execution_started_at": None,
                        },
                    )
                elif status == "queued":
                    transaction.update(build_reference, {"dispatch_requested_at": None})
                transaction.set(admission_reference, {**payload, "leases": leases, "updated_at": now_iso()})
                return was_in_flight or status == "queued"

            if recover(transaction):
                try:
                    build = self.get(build_id)
                    self.add_event(
                        build_id,
                        BuildEvent(
                            id=f"lease-expired-{int(now * 1000)}",
                            type="build.lease.expired",
                            stage=build.stage,
                            status="queued",
                            message="Worker lease expired; build returned to the execution queue.",
                            metadata={"recovery": "automatic"},
                        ),
                    )
                except BuildNotFoundError:
                    pass
                recovered.append(build_id)
        return recovered

    def renew_build(self, build_id: str, settings: Settings) -> bool:
        transaction = self.client.transaction()
        reference = self._admission_ref()

        @firestore.transactional
        def renew(transaction):
            snapshot = reference.get(transaction=transaction)
            if not snapshot.exists:
                return False
            payload = snapshot.to_dict()
            leases = payload.get("leases", {})
            if build_id not in leases:
                return False
            leases[build_id] = time.time() + settings.build_lease_seconds
            transaction.update(reference, {"leases": leases, "updated_at": now_iso()})
            return True

        return renew(transaction)

    def release_build(self, build_id: str) -> None:
        transaction = self.client.transaction()
        reference = self._admission_ref()

        @firestore.transactional
        def release(transaction):
            snapshot = reference.get(transaction=transaction)
            if not snapshot.exists:
                return
            payload = snapshot.to_dict()
            leases = payload.get("leases", {})
            if build_id not in leases:
                return
            leases.pop(build_id, None)
            transaction.update(reference, {"leases": leases, "updated_at": now_iso()})

        release(transaction)


_store: BuildStore | None = None


def make_store(settings: Settings) -> BuildStore:
    if settings.build_store.lower() == "firestore":
        return FirestoreBuildStore(settings.google_cloud_project)
    return LocalJsonBuildStore(settings.build_data_dir)


def get_store() -> BuildStore:
    global _store
    if _store is None:
        _store = make_store(get_settings())
    return _store


def set_store(store: BuildStore | None) -> None:
    global _store
    _store = store
