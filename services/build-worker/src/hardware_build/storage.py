from __future__ import annotations

import json
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path

from google.cloud import firestore

from .models import Build, BuildEvent, now_iso
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
    def reserve_build(self, build_id: str, client_key: str, settings: Settings) -> None: ...

    @abstractmethod
    def release_build(self, build_id: str) -> None: ...


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

    def reserve_build(self, build_id: str, client_key: str, settings: Settings) -> None:
        if settings.build_max_concurrent <= 0 and settings.build_request_budget <= 0:
            return
        with self._lock:
            now = time.time()
            self._active_leases = {
                key: expiry for key, expiry in self._active_leases.items() if expiry > now
            }
            requests = [
                timestamp
                for timestamp in self._request_times[client_key]
                if timestamp > now - settings.build_request_window_seconds
            ]
            self._request_times[client_key] = requests
            if (
                settings.build_max_concurrent > 0
                and len(self._active_leases) >= settings.build_max_concurrent
            ):
                retry_after = int(min(self._active_leases.values()) - now) + 1
                raise BuildAdmissionRejected("global_concurrency", retry_after)
            if settings.build_request_budget > 0 and len(requests) >= settings.build_request_budget:
                retry_after = int(requests[0] + settings.build_request_window_seconds - now) + 1
                raise BuildAdmissionRejected("client_budget", retry_after)
            self._active_leases[build_id] = now + settings.build_lease_seconds
            requests.append(now)

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

    def reserve_build(self, build_id: str, client_key: str, settings: Settings) -> None:
        if settings.build_max_concurrent <= 0 and settings.build_request_budget <= 0:
            return
        transaction = self.client.transaction()
        reference = self._admission_ref()

        @firestore.transactional
        def reserve(transaction):
            snapshot = reference.get(transaction=transaction)
            payload = snapshot.to_dict() if snapshot.exists else {}
            now = time.time()
            leases = {
                key: float(expiry)
                for key, expiry in payload.get("leases", {}).items()
                if float(expiry) > now
            }
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
            if settings.build_max_concurrent > 0 and len(leases) >= settings.build_max_concurrent:
                retry_after = int(min(leases.values()) - now) + 1
                raise BuildAdmissionRejected("global_concurrency", retry_after)
            if settings.build_request_budget > 0 and len(requests) >= settings.build_request_budget:
                retry_after = int(requests[0] + settings.build_request_window_seconds - now) + 1
                raise BuildAdmissionRejected("client_budget", retry_after)
            leases[build_id] = now + settings.build_lease_seconds
            requests.append(now)
            request_map[client_key] = requests
            if len(request_map) > 256:
                newest_clients = sorted(
                    request_map,
                    key=lambda key: request_map[key][-1],
                    reverse=True,
                )[:256]
                request_map = {key: request_map[key] for key in newest_clients}
            transaction.set(
                reference,
                {"leases": leases, "requests": request_map, "updated_at": now_iso()},
            )

        try:
            reserve(transaction)
        except BuildAdmissionRejected:
            raise
        except Exception as exc:
            raise BuildAdmissionUnavailable("Build admission storage is unavailable") from exc

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
