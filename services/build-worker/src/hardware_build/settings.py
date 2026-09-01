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
    vertex_location: str = "us"
    google_genai_use_vertexai: bool = True
    gemini_model: str = "gemini-3.5-flash"
    # Semantic alignment is optional telemetry. Enable explicitly with EMBEDDING_MODELS
    # after defining how its result influences product decisions.
    embedding_models: str = ""
    build_store: str = "local"
    build_data_dir: Path = Path("./data")
    build_artifact_dir: Path = Path("./artifacts")
    artifact_bucket: str | None = None
    public_build_url: str = "http://localhost:3000"
    public_api_url: str = "http://127.0.0.1:8080"
    worker_dispatch_url: str | None = None
    cloud_run_job_name: str | None = None
    internal_worker_token: str | None = None
    build_max_concurrent: int = 3
    # Capacity is a queue concern; this separate per-client budget is only abuse protection.
    # Twenty requests/hour supports normal iterative work while bounding public cost.
    build_request_budget: int = 20
    build_request_window_seconds: int = 3600
    build_lease_seconds: int = 300
    build_heartbeat_seconds: int = 60
    build_reconcile_seconds: int = 30
    embedding_max_concurrency: int = 3
    platformio_cmd: str = "platformio"
    max_repair_attempts: int = 3
    wokwi_cli_token: str | None = None
    wokwi_cli_cmd: str = "wokwi-cli"
    # Server-owned workspace for Drone Alpha. Never accept an arbitrary client
    # filesystem path over the public API or MCP.
    drone_project_root: Path = Path("./drone-projects")

    @property
    def gemini_configured(self) -> bool:
        return bool(self.google_cloud_project and self.google_genai_use_vertexai)

    @property
    def embedding_model_ids(self) -> tuple[str, ...]:
        return tuple(model.strip() for model in self.embedding_models.split(";") if model.strip())

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
