from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from google.cloud import firestore

from .models import Build, BuildEvent, now_iso
from .settings import Settings, get_settings


class BuildNotFoundError(KeyError):
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


class LocalJsonBuildStore(BuildStore):
    """Durable local adapter for development; production uses FirestoreBuildStore."""

    def __init__(self, root: Path):
        self.root = root / "builds"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

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
