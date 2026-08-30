from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The backend intentionally reads the process environment only. Cloud Run injects
    # secrets from Secret Manager; local development uses ADC and an ephemeral injector.
    model_config = SettingsConfigDict(extra="ignore")

    google_cloud_project: str | None = None
    google_cloud_region: str = "us-central1"
    google_genai_use_vertexai: bool = True
    gemini_model: str = "gemini-3.5-flash"
    build_store: str = "local"
    build_data_dir: Path = Path("./data")
    build_artifact_dir: Path = Path("./artifacts")
    artifact_bucket: str | None = None
    public_build_url: str = "http://localhost:3000"
    public_api_url: str = "http://127.0.0.1:8080"
    worker_dispatch_url: str | None = None
    cloud_run_job_name: str | None = None
    internal_worker_token: str | None = None
    platformio_cmd: str = "platformio"
    max_repair_attempts: int = 3
    wokwi_cli_token: str | None = None
    wokwi_cli_cmd: str = "wokwi-cli"

    @property
    def gemini_configured(self) -> bool:
        return bool(self.google_cloud_project and self.google_genai_use_vertexai)

    @property
    def secret_values(self) -> tuple[str, ...]:
        configured = [self.wokwi_cli_token, self.internal_worker_token]
        # Future Secret Manager env injections are redacted without requiring a new list here.
        configured.extend(
            value
            for name, value in os.environ.items()
            if re.search(r"(?:TOKEN|SECRET|PASSWORD|PRIVATE_KEY|API_KEY)$", name, re.I)
            and not name.upper().startswith("NEXT_PUBLIC_")
        )
        return tuple(dict.fromkeys(value for value in configured if value and len(value) >= 6))


@lru_cache
def get_settings() -> Settings:
    return Settings()
