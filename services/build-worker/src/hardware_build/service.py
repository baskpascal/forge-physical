from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
from google.cloud import run_v2

from .models import Build, BuildEvent, BuildStage, StartBuildResponse, now_iso
from .orchestrator import BuildOrchestrator
from .planning import supported_update_change
from .security import redact_text
from .settings import Settings, get_settings
from .storage import BuildStore, get_store

_executor = ThreadPoolExecutor(max_workers=max(1, int(os.getenv("LOCAL_WORKER_THREADS", "2"))), thread_name_prefix="forge-build")


def _created_event(build: Build) -> BuildEvent:
    return BuildEvent(id=uuid4().hex, type="build.created", stage=BuildStage.IDEA, status="queued", message="Build accepted. The hardware worker is taking over.", metadata={"prompt": build.prompt})


def dispatch_build(build_id: str, settings: Settings | None = None, store: BuildStore | None = None) -> None:
    settings = settings or get_settings()
    store = store or get_store()
    if settings.cloud_run_job_name:
        client = run_v2.JobsClient()
        request = run_v2.RunJobRequest(
            name=settings.cloud_run_job_name,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(
                        env=[run_v2.EnvVar(name="BUILD_ID", value=build_id)]
                    )
                ]
            ),
        )
        client.run_job(request=request)
        return
    if settings.worker_dispatch_url:
        if not settings.internal_worker_token:
            raise RuntimeError("WORKER_DISPATCH_URL requires INTERNAL_WORKER_TOKEN from Secret Manager")
        headers = {"Authorization": f"Bearer {settings.internal_worker_token}"}
        with httpx.Client(timeout=10) as client:
            response = client.post(f"{settings.worker_dispatch_url.rstrip('/')}/internal/run/{build_id}", headers=headers)
            response.raise_for_status()
        return
    _executor.submit(BuildOrchestrator(store, settings).run, build_id)


def create_build(prompt: str, *, dispatch: bool = True, store: BuildStore | None = None, settings: Settings | None = None, parent: Build | None = None) -> StartBuildResponse:
    store = store or get_store()
    settings = settings or get_settings()
    build_id = uuid4().hex[:12]
    build = Build(
        id=build_id, prompt=redact_text(prompt, settings), version=(parent.version + 1 if parent else 1),
        parent_build_id=parent.id if parent else None,
    )
    store.create(build)
    store.add_event(build_id, _created_event(build))
    if dispatch:
        dispatch_build(build_id, settings, store)
    return StartBuildResponse(build_id=build_id, status=build.status, build_url=f"{settings.public_build_url.rstrip('/')}/build/{build_id}")


def update_build(build_id: str, change: str, *, dispatch: bool = True, store: BuildStore | None = None, settings: Settings | None = None) -> StartBuildResponse:
    store = store or get_store()
    parent = store.get(build_id)
    if not supported_update_change(change):
        raise ValueError(
            "Unsupported prototype update. This release supports adding motion/orientation sensing."
        )
    prompt = f"{parent.prompt}\n\nRequested update: {change}"
    return create_build(prompt, dispatch=dispatch, store=store, settings=settings, parent=parent)


def status_payload(build_id: str, store: BuildStore | None = None) -> dict:
    store = store or get_store()
    build = store.get(build_id)
    events = store.events(build_id)
    payload = build.model_dump(mode="json", by_alias=True)
    payload["events"] = [event.model_dump(mode="json") for event in events]
    return payload


def artifacts_payload(build_id: str, store: BuildStore | None = None, settings: Settings | None = None) -> dict:
    store = store or get_store()
    settings = settings or get_settings()
    build = store.get(build_id)
    return {
        "build_id": build_id,
        "status": build.status,
        "artifacts": build.artifact_paths,
        "download_url": f"{settings.public_api_url.rstrip('/')}/api/builds/{build_id}/artifacts.zip",
        "storage": f"gs://{settings.artifact_bucket}/{build_id}/" if settings.artifact_bucket else "local",
        "updated_at": now_iso(),
    }
