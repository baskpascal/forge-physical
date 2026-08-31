from __future__ import annotations

import json
import mimetypes
from pathlib import Path, PurePosixPath

from google.cloud import storage
from pydantic import BaseModel

from .models import Build
from .settings import Settings

_PUBLIC_ARTIFACTS = {
    "hardware/product.json",
    "hardware/hardware.json",
    "hardware/verification.json",
    "hardware/semantic-alignment.json",
    "hardware/firmware/platformio.ini",
    "hardware/firmware/.pio/build/esp32-s3-devkitc-1/firmware.bin",
    "hardware/firmware/.pio/build/esp32-s3-devkitc-1/firmware.elf",
}
_PUBLIC_ARTIFACT_PREFIXES = (
    "hardware/firmware/src/",
    "hardware/simulation/",
    "hardware/enclosure/",
)
_ARTIFACT_MEDIA_TYPES = {
    ".bin": "application/octet-stream",
    ".cpp": "text/plain; charset=utf-8",
    ".elf": "application/octet-stream",
    ".ini": "text/plain; charset=utf-8",
    ".json": "application/json",
    ".stl": "model/stl",
}


def public_artifact_path(value: str) -> str | None:
    """Return a canonical public artifact path, or None for unsafe/internal paths."""
    if not value or "\\" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    canonical = path.as_posix()
    if canonical in _PUBLIC_ARTIFACTS or canonical.startswith(_PUBLIC_ARTIFACT_PREFIXES):
        return canonical
    return None


def build_public_artifact_paths(build: Build) -> set[str]:
    """Canonicalize only the public artifacts explicitly recorded on a build."""
    allowed: set[str] = set()
    build_prefix = f"{build.id}/"
    for stored_path in build.artifact_paths.values():
        relative = stored_path.removeprefix(build_prefix)
        canonical = public_artifact_path(relative)
        if canonical is not None:
            allowed.add(canonical)
    return allowed


def artifact_media_type(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    return _ARTIFACT_MEDIA_TYPES.get(suffix) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def artifact_files(build_root: Path):
    """Yield only user-facing artifacts, excluding tool caches and object files."""
    for path in build_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(build_root).as_posix()
        if public_artifact_path(relative):
            yield path


class ArtifactWorkspace:
    def __init__(self, settings: Settings, build_id: str):
        self.root = settings.build_artifact_dir.resolve() / build_id / "hardware"
        self.root.mkdir(parents=True, exist_ok=True)

    def directory(self, name: str) -> Path:
        path = self.root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, relative: str, value: BaseModel | dict | list) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = value.model_dump(mode="json", by_alias=True) if isinstance(value, BaseModel) else value
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def relative(self, path: Path) -> str:
        return str(path.relative_to(self.root.parent.parent)).replace("\\", "/")

    def persist_build_inputs(self, build: Build) -> dict[str, str]:
        paths: dict[str, str] = {}
        if build.product_spec:
            paths["product"] = self.relative(self.write_json("product.json", build.product_spec))
        if build.hardware:
            paths["hardware"] = self.relative(self.write_json("hardware.json", build.hardware))
        return paths

    def publish(self, bucket_name: str) -> int:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        count = 0
        build_root = self.root.parent
        for path in artifact_files(build_root):
            blob_name = f"{build_root.name}/{path.relative_to(build_root).as_posix()}"
            bucket.blob(blob_name).upload_from_filename(path)
            count += 1
        return count
