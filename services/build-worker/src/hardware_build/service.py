from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from uuid import uuid4

import httpx
from google.cloud import run_v2

from .models import Build, BuildEvent, BuildStage, StartBuildResponse, now_iso
from .orchestrator import BuildOrchestrator
from .planning import product_has_motion_sensing, supported_update_change
from .security import redact_text
from .settings import Settings, get_settings
from .storage import BuildStore, get_store

_executor = ThreadPoolExecutor(max_workers=max(1, int(os.getenv("LOCAL_WORKER_THREADS", "2"))), thread_name_prefix="forge-build")


class DispatchNotAccepted(RuntimeError):
    """The dispatcher definitively rejected the request, so its lease may be released."""


class DispatchOutcomeUnknown(RuntimeError):
    """The request may have been accepted; retain the lease to prevent duplicate work."""


def _created_event(build: Build) -> BuildEvent:
    return BuildEvent(id=uuid4().hex, type="build.created", stage=BuildStage.IDEA, status="queued", message="Build accepted and queued for hardware execution.", metadata={"prompt": build.prompt})


def dispatch_build(build_id: str, settings: Settings | None = None, store: BuildStore | None = None) -> None:
    settings = settings or get_settings()
    store = store or get_store()
    if settings.worker_dispatch_url and not settings.internal_worker_token:
        raise DispatchNotAccepted("WORKER_DISPATCH_URL requires INTERNAL_WORKER_TOKEN from Secret Manager")
    build = store.get(build_id)
    build.dispatch_requested_at = now_iso()
    build.queue_position = 0
    store.save(build)
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
        try:
            client.run_job(request=request)
        except Exception as exc:
            raise DispatchOutcomeUnknown("Cloud Run Job dispatch outcome is unknown") from exc
        return
    if settings.worker_dispatch_url:
        headers = {"Authorization": f"Bearer {settings.internal_worker_token}"}
        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(f"{settings.worker_dispatch_url.rstrip('/')}/internal/run/{build_id}", headers=headers)
            if 400 <= response.status_code < 500:
                raise DispatchNotAccepted(f"Worker rejected dispatch with HTTP {response.status_code}")
            response.raise_for_status()
        except DispatchNotAccepted:
            raise
        except Exception as exc:
            raise DispatchOutcomeUnknown("HTTP worker dispatch outcome is unknown") from exc
        return
    try:
        _executor.submit(BuildOrchestrator(store, settings).run, build_id)
    except Exception as exc:
        raise DispatchNotAccepted("Local executor rejected dispatch") from exc


def try_dispatch_build(
    build_id: str,
    settings: Settings | None = None,
    store: BuildStore | None = None,
) -> int | None:
    """Claim and dispatch one queued build. Repeated calls are safe and capacity queues."""
    settings = settings or get_settings()
    store = store or get_store()
    claim = store.claim_build(build_id, settings)
    if not claim.claimed:
        if claim.position is not None:
            build = store.get(build_id)
            build.queue_position = claim.position
            store.save(build)
        return claim.position
    try:
        dispatch_build(build_id, settings, store)
    except DispatchOutcomeUnknown as exc:
        # A timeout can happen after Cloud Run accepted the request. Keeping the lease makes
        # retries safe: the accepted worker can start once, or expiration returns it to FIFO.
        store.add_event(
            build_id,
            BuildEvent(
                id=uuid4().hex,
                type="build.dispatch.pending_confirmation",
                stage=BuildStage.IDEA,
                status="queued",
                message="Hardware execution was requested and is awaiting confirmation.",
                metadata={"reason": type(exc.__cause__ or exc).__name__},
            ),
        )
        return 0
    except Exception as exc:
        store.release_build(build_id)
        build = store.get(build_id)
        build.queue_position = 1
        store.save(build)
        store.add_event(
            build_id,
            BuildEvent(
                id=uuid4().hex,
                type="build.dispatch.deferred",
                stage=BuildStage.IDEA,
                status="queued",
                message="Waiting for the hardware execution service to accept this queued build.",
                metadata={"reason": type(exc).__name__},
            ),
        )
        return 1
    return 0


def dispatch_next_queued(
    settings: Settings | None = None,
    store: BuildStore | None = None,
) -> str | None:
    """FIFO reconciliation used after completion and by status polling."""
    settings = settings or get_settings()
    store = store or get_store()
    for build_id in store.queued_build_ids():
        position = try_dispatch_build(build_id, settings, store)
        if position == 0:
            return build_id
        if position is not None:
            break
    return None


def create_build(prompt: str, *, dispatch: bool = True, store: BuildStore | None = None, settings: Settings | None = None, parent: Build | None = None, client_key: str = "mcp") -> StartBuildResponse:
    store = store or get_store()
    settings = settings or get_settings()
    build_id = uuid4().hex[:12]
    build = Build(
        id=build_id, prompt=redact_text(prompt, settings), version=(parent.version + 1 if parent else 1),
        parent_build_id=parent.id if parent else None,
    )
    admission_key = sha256(client_key.encode("utf-8")).hexdigest()[:24]
    store.check_request_budget(admission_key, settings)
    try:
        store.create(build)
        store.add_event(build_id, _created_event(build))
        queue_position = try_dispatch_build(build_id, settings, store) if dispatch else None
    except Exception:
        raise
    build = store.get(build_id)
    return StartBuildResponse(
        build_id=build_id,
        status=build.status,
        build_url=f"{settings.public_build_url.rstrip('/')}/build/{build_id}",
        queue_position=queue_position,
    )


def update_build(build_id: str, change: str, *, dispatch: bool = True, store: BuildStore | None = None, settings: Settings | None = None, client_key: str = "mcp") -> StartBuildResponse:
    store = store or get_store()
    parent = store.get(build_id)
    if not supported_update_change(change):
        raise ValueError(
            "Unsupported prototype update. Supported iterations include motion/orientation "
            "sensing, temperature thresholds, naming/text, and enclosure changes."
        )
    requests_motion = product_has_motion_sensing(None, change)
    has_motion_hardware = bool(
        parent.hardware
        and any(component.component_id == "mpu6050" for component in parent.hardware.components)
    )
    if requests_motion and (
        has_motion_hardware or product_has_motion_sensing(parent.product_spec, parent.prompt)
    ):
        raise ValueError("Motion sensing is already present in the parent build.")
    prompt = f"{parent.prompt}\n\nRequested update: {change}"
    return create_build(
        prompt,
        dispatch=dispatch,
        store=store,
        settings=settings,
        parent=parent,
        client_key=client_key,
    )


def status_payload(build_id: str, store: BuildStore | None = None) -> dict:
    store = store or get_store()
    try:
        store.reconcile_expired_leases()
    except Exception:
        # Reads remain available; the next poll/completion will retry reconciliation.
        pass
    build = store.get(build_id)
    if build.status.value == "queued":
        try:
            dispatch_next_queued(store=store)
        except Exception:
            # Status reads remain available while the best-effort reconciler retries later.
            pass
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
