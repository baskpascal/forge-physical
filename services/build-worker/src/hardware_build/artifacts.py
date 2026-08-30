from __future__ import annotations

import json
from pathlib import Path

from google.cloud import storage
from pydantic import BaseModel

from .models import Build
from .settings import Settings


def artifact_files(build_root: Path):
    """Yield only user-facing artifacts, excluding tool caches and object files."""
    exact = {
        "hardware/product.json",
        "hardware/hardware.json",
        "hardware/verification.json",
        "hardware/firmware/platformio.ini",
        "hardware/firmware/.pio/build/esp32-s3-devkitc-1/firmware.bin",
        "hardware/firmware/.pio/build/esp32-s3-devkitc-1/firmware.elf",
    }
    prefixes = (
        "hardware/firmware/src/",
        "hardware/simulation/",
        "hardware/enclosure/",
    )
    for path in build_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(build_root).as_posix()
        if relative in exact or relative.startswith(prefixes):
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
